package dev.p2pkit.transport.lan

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import android.os.Build
import android.util.Log
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.DiscoveryTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.TransportHint
import java.net.Inet4Address
import java.net.Inet6Address
import java.net.InetAddress
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/**
 * [DiscoveryTransport] backed by Android's [NsdManager].
 *
 * NsdManager's API is callback-based; this class wraps it in coroutine-friendly
 * primitives. Resolution of discovered services is sequential because some
 * Android API levels reject concurrent `resolveService` calls.
 *
 * Wi-Fi multicast lock: incoming mDNS multicast packets (224.0.0.251:5353) are
 * dropped by Android's Wi-Fi power-save firmware unless an app explicitly holds
 * a [WifiManager.MulticastLock]. The `CHANGE_WIFI_MULTICAST_STATE` permission
 * only **allows** acquiring the lock; the lock itself must also be held. Without
 * it, this transport can advertise (outgoing multicast works) but cannot
 * **receive** other peers' advertisements. The lock is acquired on first
 * start (advertise or discover, whichever comes first) and released when both
 * have stopped.
 *
 * Network-rotation rebind (v0.4): NsdManager's registration and discovery
 * listeners are bound to the network interface that was the system multicast
 * route at the time of `registerService` / `discoverServices`. When that
 * underlying network changes (Wi-Fi → hotspot, Wi-Fi → Ethernet, captive
 * portal accept), the listeners silently stop receiving multicast — peers
 * appear "lost forever" until the host app restarts discovery. To recover
 * automatically we watch [ConnectivityManager] for transitions and, after a
 * debounce settle window, unregister the old NSD listeners and register
 * fresh ones. Two complementary callbacks feed the rebind machinery:
 *
 *   - **Primary (V0.4-NSD):** filtered on `TRANSPORT_WIFI | TRANSPORT_ETHERNET`.
 *     Catches client-mode Wi-Fi/Ethernet appearance/loss and Wi-Fi→Wi-Fi
 *     handover.
 *   - **Default (V0.4-AP):** registered via `registerDefaultNetworkCallback`.
 *     Catches transitions the primary misses — most importantly the
 *     device-becomes-hotspot-host case where the AP interface is surfaced
 *     as tethering rather than as a client `TRANSPORT_WIFI` network.
 *
 * The debounced rebind runs in [rebindScope]; ConnectivityManager callbacks
 * themselves do no work beyond scheduling. Multicast-lock state is preserved
 * across rebinds.
 */
internal class AndroidLanDiscoveryTransport(
    private val context: Context,
    private val registration: LanServiceRegistration
) : DiscoveryTransport {

    override val type: TransportKind = TransportKind.LAN

    private val _events = MutableSharedFlow<PeerEvent>(
        replay = 0,
        extraBufferCapacity = 256,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )
    override val events: Flow<PeerEvent> = _events.asSharedFlow()

    private val lock = Mutex()
    private val nsd: NsdManager =
        context.applicationContext.getSystemService(Context.NSD_SERVICE) as NsdManager
    private val wifi: WifiManager? =
        context.applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager
    private val connectivity: ConnectivityManager =
        context.applicationContext.getSystemService(Context.CONNECTIVITY_SERVICE)
            as ConnectivityManager

    private var registrationListener: NsdManager.RegistrationListener? = null
    private var discoveryListener: NsdManager.DiscoveryListener? = null
    private var multicastLock: WifiManager.MulticastLock? = null

    /**
     * Cached `LocalPeerInfo` from the most recent `startAdvertising` call.
     * Used by [rebindNow] to rebuild the [NsdServiceInfo] on a fresh listener.
     * Cleared in `stopAdvertising` so a subsequent rebind cannot inadvertently
     * re-advertise after the host app stopped.
     */
    private var cachedLocalPeer: LocalPeerInfo? = null

    /**
     * Scope for the debounced rebind coroutine. Uses [SupervisorJob] so a
     * single failed rebind does not poison the scope for future rebinds.
     * Lifetime is the transport instance — children are cancelled via
     * [pendingRebindJob] handles when the watcher stops, but the scope
     * itself persists for re-use on the next start.
     */
    private val rebindScope: CoroutineScope =
        CoroutineScope(SupervisorJob() + Dispatchers.Default)

    /** The most recent debounced rebind job; cancelled when superseded. */
    private var pendingRebindJob: Job? = null

    /**
     * Primary [ConnectivityManager] callback filtered on
     * `TRANSPORT_WIFI | TRANSPORT_ETHERNET`. Tracks client-mode LAN
     * availability — Wi-Fi / Ethernet networks the device has joined as a
     * client. Non-null iff watcher is active.
     */
    private var networkCallback: ConnectivityManager.NetworkCallback? = null

    /**
     * V0.4-AP: secondary [ConnectivityManager] callback registered via
     * `registerDefaultNetworkCallback`. Catches transitions that the
     * primary `TRANSPORT_WIFI/ETHERNET` callback misses — most importantly
     * the device-becomes-hotspot-host case, where the AP interface is
     * surfaced as tethering rather than as a client-Wi-Fi `Network` and so
     * never fires `onAvailable` on the primary callback. The default
     * network's onLost (when client Wi-Fi goes away and there's no
     * replacement default) is also a valid rebind trigger.
     */
    private var defaultNetworkCallback: ConnectivityManager.NetworkCallback? = null

    private val networkLock = Any()

    /** Most recent network reported by the primary callback. `null` after `onLost`. */
    @Suppress("AnnotationOnSuperclass")
    private var observedNetwork: Network? = null

    /** Most recent system-default network reported by the default callback. */
    private var observedDefaultNetwork: Network? = null

    /** True once any onAvailable has fired on the primary callback — distinguishes startup from rotation. */
    private var hasEverObservedNetwork: Boolean = false

    /**
     * Network present at the time of the most recent successful NSD register
     * (initial or post-rebind). Used by [rebindNow] to skip no-op rebinds when
     * neither observed signal has changed since we last bound.
     * Guarded by [lock] (set inside the NSD register path).
     */
    private var boundNetwork: Network? = null

    /** Default network present at the time of the most recent successful NSD register. */
    private var boundDefaultNetwork: Network? = null

    // ──────────────────────────────────────────────────────────────────
    // V0.4-RESOLVE-RETRY: re-resolve rejected peers after a short delay.
    //
    // When [selectRoutableHost] returns null (e.g., peer advertised
    // fe80:: link-local only because its DHCP IPv4 hadn't completed yet
    // during a hotspot transition), we'd otherwise be stuck — NsdManager
    // does not re-resolve a known service on its own. Schedule a fresh
    // resolveService call after a short delay; by then the peer has
    // likely re-announced with the full address set.
    //
    // Capped per-peer to avoid storms (RESOLVE_RETRY_MAX_ATTEMPTS). The
    // retry jobs run on [rebindScope] (already SupervisorJob-backed).
    // Cancellation triggers: peer-Lost event, stopDiscovery,
    // rebindNow (the old NsdServiceInfo references would be stale after
    // a listener rebind anyway).
    // ──────────────────────────────────────────────────────────────────

    private val resolveRetryLock = Any()
    private val pendingResolveRetries: MutableMap<String, Job> = mutableMapOf()
    private val resolveRetryAttempts: MutableMap<String, Int> = mutableMapOf()

    override suspend fun startAdvertising(localPeer: LocalPeerInfo) = lock.withLock {
        if (registrationListener != null) return@withLock

        acquireMulticastLockIfNeeded()

        val info = buildServiceInfo(localPeer)
        val registered = CompletableDeferred<Unit>()
        val listener = buildRegistrationListener(registered)
        nsd.registerService(info, NsdManager.PROTOCOL_DNS_SD, listener)
        registrationListener = listener
        cachedLocalPeer = localPeer
        boundNetwork = connectivity.activeNetwork
        boundDefaultNetwork = connectivity.activeNetwork
        Log.d(
            TAG,
            "startAdvertising: registerService submitted, " +
                "boundNetwork=$boundNetwork boundDefaultNetwork=$boundDefaultNetwork"
        )
        ensureNetworkWatcherStarted()
        // Wait for confirmation so callers know we're really advertising.
        registered.await()
    }

    override suspend fun stopAdvertising() = lock.withLock {
        val listener = registrationListener ?: return@withLock
        runCatching { nsd.unregisterService(listener) }
        registrationListener = null
        cachedLocalPeer = null
        Log.d(TAG, "stopAdvertising: unregisterService submitted")
        stopNetworkWatcherIfIdle()
        releaseMulticastLockIfIdle()
    }

    override suspend fun startDiscovery() = lock.withLock {
        if (discoveryListener != null) return@withLock

        acquireMulticastLockIfNeeded()

        val listener = buildDiscoveryListener()
        nsd.discoverServices(LanConstants.SERVICE_TYPE_NSD, NsdManager.PROTOCOL_DNS_SD, listener)
        discoveryListener = listener
        boundNetwork = connectivity.activeNetwork
        boundDefaultNetwork = connectivity.activeNetwork
        Log.d(
            TAG,
            "startDiscovery: discoverServices submitted, " +
                "boundNetwork=$boundNetwork boundDefaultNetwork=$boundDefaultNetwork"
        )
        ensureNetworkWatcherStarted()
    }

    override suspend fun stopDiscovery() = lock.withLock {
        val listener = discoveryListener ?: return@withLock
        runCatching { nsd.stopServiceDiscovery(listener) }
        discoveryListener = null
        Log.d(TAG, "stopDiscovery: stopServiceDiscovery submitted")
        // V0.4-RESOLVE-RETRY: no more discovery → pending retries reference
        // service infos from a listener that's about to be torn down.
        clearAllResolveRetries("stopDiscovery")
        stopNetworkWatcherIfIdle()
        releaseMulticastLockIfIdle()
    }

    /**
     * V0.4-DISCOVERY-REFRESH: force a fresh round of NSD active queries.
     *
     * Called when a session enters Reconnecting. Two-part refresh:
     *
     * 1. Tear down + install a fresh discovery listener — the fresh
     *    `discoverServices` call sends new mDNS queries on the wire.
     * 2. **V0.4-D-ANDROID-NUDGE**: if we're currently advertising, also
     *    unregister + re-register our own service. The platform NSD
     *    daemon caches mDNS records aggressively, and the simple
     *    discovery restart in part 1 alone often returns cached
     *    resolutions (observed: 41ms turnaround serving a stale port).
     *    Forcing the local advertise registration through a full
     *    unregister/re-register cycle nudges the daemon's mDNS
     *    subsystem to flush related caches and re-emit traffic, which
     *    in turn coaxes peers to re-announce and fresh records to
     *    populate.
     *
     * No-op if discovery wasn't running (host stopped it explicitly).
     * Pending resolve retries are cleared because they reference the
     * old listener's service infos.
     */
    override suspend fun refresh() = lock.withLock {
        val oldListener = discoveryListener
        if (oldListener == null) {
            Log.d(TAG, "refresh: no discovery listener active — skipping")
            return@withLock
        }
        Log.d(TAG, "refresh: stop+start discoverServices to flush mDNS cache")
        runCatching { nsd.stopServiceDiscovery(oldListener) }
        // Stale pending re-resolves point at infos from the old listener
        // and would race a fresh round of onServiceFound emissions.
        clearAllResolveRetries("refresh")
        val freshListener = buildDiscoveryListener()
        runCatching {
            nsd.discoverServices(
                LanConstants.SERVICE_TYPE_NSD,
                NsdManager.PROTOCOL_DNS_SD,
                freshListener
            )
            discoveryListener = freshListener
            Log.d(TAG, "refresh: discoverServices submitted on fresh listener")
        }.onFailure { e ->
            // Leave discoveryListener null so the next state change can
            // re-attempt cleanly via startDiscovery / rebindNow.
            discoveryListener = null
            Log.w(TAG, "refresh: discoverServices failed", e)
        }
        nudgeOwnServiceRegistration()
    }

    /**
     * V0.4-D-ANDROID-NUDGE: unregister + (brief delay) + re-register our
     * own NSD service. Called from [refresh] while holding [lock].
     *
     * Rationale: even when [refresh]'s discovery restart returns a fresh
     * cached resolution, that resolution often carries a stale port
     * because Android's NSD daemon caches mDNS SRV records for an
     * extended TTL. Forcing the daemon to re-process our own advertise
     * cycle gives it a chance to:
     *  - flush the in-process cache for our service type,
     *  - re-emit local mDNS announcement traffic,
     *  - actively re-query for peers it already knows about.
     *
     * No-op when not currently advertising.
     */
    private suspend fun nudgeOwnServiceRegistration() {
        val oldAdvertiseListener = registrationListener
        val cached = cachedLocalPeer
        if (oldAdvertiseListener == null || cached == null) {
            Log.d(TAG, "refresh: nudge skipped — not currently advertising")
            return
        }
        Log.d(TAG, "refresh: nudge — unregistering own service to flush NSD cache")
        runCatching { nsd.unregisterService(oldAdvertiseListener) }
        registrationListener = null
        // Brief gap so the NSD daemon processes the goodbye before the
        // fresh register arrives — without this they can collapse into a
        // no-op (same name + same type observed as unchanged).
        delay(NUDGE_GAP_MILLIS)
        val info = buildServiceInfo(cached)
        val freshListener = buildRegistrationListener(confirmation = null)
        runCatching {
            nsd.registerService(info, NsdManager.PROTOCOL_DNS_SD, freshListener)
            registrationListener = freshListener
            Log.d(TAG, "refresh: nudge — own service re-registered")
        }.onFailure { e ->
            registrationListener = null
            Log.w(TAG, "refresh: nudge — own service re-register failed", e)
        }
    }

    private fun buildServiceInfo(localPeer: LocalPeerInfo): NsdServiceInfo =
        NsdServiceInfo().apply {
            serviceName = registration.localPeerId.value
            serviceType = LanConstants.SERVICE_TYPE_NSD
            port = registration.tcpPort
            setAttribute(LanConstants.TXT_PEER_ID, registration.localPeerId.value)
            setAttribute(LanConstants.TXT_APP_ID, registration.appId.value)
            setAttribute(LanConstants.TXT_DEVICE_NAME, localPeer.deviceName)
            setAttribute(LanConstants.TXT_PLATFORM, localPeer.platform.name)
            setAttribute(
                LanConstants.TXT_CAPABILITIES,
                localPeer.supportedTransports.joinToString(",") { it.name }
            )
            setAttribute(LanConstants.TXT_PROTOCOL_VERSION, LanConstants.PROTOCOL_VERSION.toString())
        }

    /**
     * Builds a fresh [NsdManager.RegistrationListener]. A new instance is
     * constructed for every register (initial or post-rebind) — Android does
     * not document whether listeners survive an unregister + re-register
     * cycle, and reusing one risks subtle bugs.
     *
     * The optional [confirmation] deferred is completed only by the initial
     * `startAdvertising` call (so the caller blocks until NSD confirms);
     * rebind-time registrations pass `null` because the rebind body runs
     * fire-and-forget under the lock.
     */
    private fun buildRegistrationListener(
        confirmation: CompletableDeferred<Unit>?
    ): NsdManager.RegistrationListener = object : NsdManager.RegistrationListener {
        override fun onServiceRegistered(serviceInfo: NsdServiceInfo) {
            confirmation?.complete(Unit)
        }

        override fun onRegistrationFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
            confirmation?.completeExceptionally(
                IllegalStateException("NsdManager registration failed: errorCode=$errorCode")
            )
            Log.w(TAG, "RegistrationListener.onRegistrationFailed: errorCode=$errorCode")
        }

        override fun onServiceUnregistered(serviceInfo: NsdServiceInfo) = Unit
        override fun onUnregistrationFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
            Log.w(TAG, "RegistrationListener.onUnregistrationFailed: errorCode=$errorCode")
        }
    }

    private fun buildDiscoveryListener(): NsdManager.DiscoveryListener =
        object : NsdManager.DiscoveryListener {
            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
                Log.w(TAG, "DiscoveryListener.onStartDiscoveryFailed: errorCode=$errorCode")
            }

            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {
                Log.w(TAG, "DiscoveryListener.onStopDiscoveryFailed: errorCode=$errorCode")
            }

            override fun onDiscoveryStarted(serviceType: String) = Unit
            override fun onDiscoveryStopped(serviceType: String) = Unit

            override fun onServiceFound(serviceInfo: NsdServiceInfo) {
                if (serviceInfo.serviceName == registration.localPeerId.value) return
                Log.d(TAG, "onServiceFound: pid=${serviceInfo.serviceName?.take(8)} — resolving")
                resolve(serviceInfo)
            }

            override fun onServiceLost(serviceInfo: NsdServiceInfo) {
                val pid = serviceInfo.serviceName ?: return
                if (pid == registration.localPeerId.value) return
                Log.d(TAG, "onServiceLost: pid=${pid.take(8)} — emitting PeerEvent.Lost (peer evicted from registry)")
                // V0.4-RESOLVE-RETRY: peer is gone — cancel any pending
                // re-resolve so we don't keep trying to reach a peer that
                // has explicitly left.
                clearResolveRetry(pid, "service lost")
                _events.tryEmit(PeerEvent.Lost(PeerId(pid)))
            }
        }

    private fun acquireMulticastLockIfNeeded() {
        if (multicastLock != null) return
        val wm = wifi ?: return
        val lock = wm.createMulticastLock("p2pkit-mdns").apply {
            setReferenceCounted(false)
            acquire()
        }
        multicastLock = lock
    }

    private fun releaseMulticastLockIfIdle() {
        if (registrationListener != null || discoveryListener != null) return
        val held = multicastLock ?: return
        multicastLock = null
        runCatching { if (held.isHeld) held.release() }
    }

    @Suppress("DEPRECATION") // Newer resolveService(Executor, ResolveListener) is API 34+; keep this until minSdk rises.
    private fun resolve(serviceInfo: NsdServiceInfo) {
        nsd.resolveService(serviceInfo, object : NsdManager.ResolveListener {
            override fun onResolveFailed(info: NsdServiceInfo, errorCode: Int) {
                // Silent: NsdManager.FAILURE_ALREADY_ACTIVE etc. happens under load.
            }

            override fun onServiceResolved(info: NsdServiceInfo) {
                val attrs = info.attributes ?: emptyMap()
                val pid = attrs[LanConstants.TXT_PEER_ID]?.decodeToString() ?: return
                val app = attrs[LanConstants.TXT_APP_ID]?.decodeToString() ?: return
                if (pid == registration.localPeerId.value) return
                if (app != registration.appId.value) return

                val name = attrs[LanConstants.TXT_DEVICE_NAME]?.decodeToString() ?: pid
                val plat = attrs[LanConstants.TXT_PLATFORM]?.decodeToString()
                val caps = attrs[LanConstants.TXT_CAPABILITIES]?.decodeToString()
                val candidates = collectHostCandidates(info)
                val host = selectRoutableHost(candidates)
                if (host == null) {
                    // V0.4-IPV6: no routable address — skip the Found event
                    // rather than publish an undialable hint. Typical cause is
                    // a peer whose only advertised IP on this resolution cycle
                    // is an unscoped fe80:: link-local IPv6 (EINVAL on dial).
                    Log.d(
                        TAG,
                        "resolve: rejecting peer=${pid.take(8)} — no routable host " +
                            "in candidates=$candidates"
                    )
                    // V0.4-RESOLVE-RETRY: the peer may have just re-announced
                    // mid-DHCP (only fe80:: bound so far). Schedule a fresh
                    // resolve in a few seconds — by then the host typically
                    // has a routable IPv4 too. Cap'd to avoid storms; see
                    // [scheduleResolveRetry] for the per-peer attempt counter.
                    scheduleResolveRetry(info, pid, "unroutable candidates=$candidates")
                    return
                }
                // V0.4-RESOLVE-RETRY: success — clear any pending retry for
                // this peer so a future re-resolve doesn't fire redundantly.
                clearResolveRetry(pid, "resolve succeeded with host=$host")
                val port = info.port

                val supportedTransports = caps
                    ?.split(",")
                    ?.mapNotNull { tag ->
                        runCatching { TransportKind.valueOf(tag.trim()) }.getOrNull()
                    }
                    ?.toSet()
                    ?: setOf(TransportKind.LAN)
                val platform = plat?.let {
                    runCatching { Platform.valueOf(it) }.getOrNull()
                } ?: Platform.UNKNOWN

                val internalPeer = InternalPeer(
                    publicPeer = Peer(
                        id = PeerId(pid),
                        name = name,
                        platform = platform,
                        supportedTransports = supportedTransports
                    ),
                    transportHints = listOf(
                        TransportHint(type = TransportKind.LAN, host = host, port = port)
                    )
                )
                Log.d(
                    TAG,
                    "onServiceResolved: pid=${pid.take(8)} host=$host port=$port — emitting PeerEvent.Found"
                )
                _events.tryEmit(PeerEvent.Found(internalPeer))
            }
        })
    }

    // ─────────────────────────────────────────────────────────────────────
    // Network-rotation rebind
    // ─────────────────────────────────────────────────────────────────────

    /**
     * Registers BOTH the primary `TRANSPORT_WIFI|ETHERNET` callback (V0.4-NSD)
     * AND the default-network callback (V0.4-AP). The two signals are
     * complementary: the primary covers client-mode LAN rotation; the
     * default covers everything else that mutates the system default,
     * most importantly the device-becomes-hotspot-host transition where
     * the AP interface is invisible to a transport-filtered request.
     *
     * Idempotent — calling again while either callback is already registered
     * leaves that callback alone but ensures the other is up. Called from
     * `startAdvertising` / `startDiscovery` inside the existing [lock], so
     * it never races with the rebind body.
     */
    private fun ensureNetworkWatcherStarted() {
        if (networkCallback == null) {
            val cb = buildPrimaryNetworkCallback()
            val request = NetworkRequest.Builder()
                .addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
                .addTransportType(NetworkCapabilities.TRANSPORT_ETHERNET)
                .build()
            runCatching { connectivity.registerNetworkCallback(request, cb) }
                .onSuccess {
                    networkCallback = cb
                    Log.d(TAG, "ensureNetworkWatcherStarted: registered NetworkCallback (WIFI|ETHERNET)")
                }
                .onFailure { e ->
                    Log.w(TAG, "ensureNetworkWatcherStarted: registerNetworkCallback failed", e)
                }
        }
        if (defaultNetworkCallback == null) {
            val cb = buildDefaultNetworkCallback()
            runCatching { connectivity.registerDefaultNetworkCallback(cb) }
                .onSuccess {
                    defaultNetworkCallback = cb
                    Log.d(TAG, "ensureNetworkWatcherStarted: registered DefaultNetworkCallback")
                }
                .onFailure { e ->
                    Log.w(TAG, "ensureNetworkWatcherStarted: registerDefaultNetworkCallback failed", e)
                }
        }
    }

    /**
     * Primary callback construction. Body unchanged from V0.4-NSD — only
     * client-mode WIFI/ETHERNET rotation triggers scheduleRebind here;
     * `onLost` is informational (clears state, awaits next onAvailable).
     */
    private fun buildPrimaryNetworkCallback(): ConnectivityManager.NetworkCallback =
        object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                val (prev, shouldRebind) = synchronized(networkLock) {
                    val p = observedNetwork
                    val isFirst = !hasEverObservedNetwork
                    observedNetwork = network
                    hasEverObservedNetwork = true
                    when {
                        // Very first signal since the watcher started: NSD
                        // was just registered on the current network, so we
                        // trust the implicit binding and skip rebind.
                        isFirst -> p to false
                        // Same network as before — capability tick, no
                        // rotation. Avoid redundant churn.
                        p == network -> p to false
                        // Different network: rotation. Schedule rebind.
                        else -> p to true
                    }
                }
                if (shouldRebind) {
                    Log.d(TAG, "NetworkCallback.onAvailable: rotation detected, prev=$prev now=$network")
                    scheduleRebind("onAvailable rotation: $prev -> $network")
                } else {
                    Log.d(TAG, "NetworkCallback.onAvailable: $network (no rebind)")
                }
            }

            override fun onLost(network: Network) {
                val cleared = synchronized(networkLock) {
                    if (observedNetwork == network) {
                        observedNetwork = null
                        true
                    } else false
                }
                if (cleared) {
                    Log.d(TAG, "NetworkCallback.onLost: $network (observed cleared; awaiting next onAvailable)")
                } else {
                    Log.d(TAG, "NetworkCallback.onLost: $network (was not current observed)")
                }
            }
        }

    /**
     * Default-network callback (V0.4-AP). Schedules a rebind on BOTH
     * onAvailable and onLost — the hotspot-host scenario surfaces as
     * "default Wi-Fi lost, no equivalent default replaces it" and we want
     * NSD to re-bind regardless of whether the primary callback also saw
     * a change. Debounce + the two-target no-change check in `rebindNow`
     * absorb any redundant fires when both callbacks see the same
     * transition.
     */
    private fun buildDefaultNetworkCallback(): ConnectivityManager.NetworkCallback =
        object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                val prev = synchronized(networkLock) {
                    val p = observedDefaultNetwork
                    observedDefaultNetwork = network
                    p
                }
                if (prev != network) {
                    Log.d(TAG, "DefaultNetworkCallback.onAvailable: prev=$prev now=$network")
                    scheduleRebind("default network changed: $prev -> $network")
                } else {
                    Log.d(TAG, "DefaultNetworkCallback.onAvailable: $network (no change)")
                }
            }

            override fun onLost(network: Network) {
                val cleared = synchronized(networkLock) {
                    if (observedDefaultNetwork == network) {
                        observedDefaultNetwork = null
                        true
                    } else false
                }
                if (cleared) {
                    Log.d(TAG, "DefaultNetworkCallback.onLost: $network (default cleared)")
                    scheduleRebind("default network lost: $network")
                } else {
                    Log.d(TAG, "DefaultNetworkCallback.onLost: $network (was not current default)")
                }
            }
        }

    /**
     * Tears down BOTH callbacks (primary + default) and cancels any pending
     * debounced rebind. Called from `stopAdvertising` / `stopDiscovery`
     * only when **both** NSD listeners have been cleared — symmetric with
     * multicast-lock release. The two callbacks are registered together
     * (`ensureNetworkWatcherStarted`) and unregistered together to keep the
     * lifecycle invariant tight.
     */
    private fun stopNetworkWatcherIfIdle() {
        if (registrationListener != null || discoveryListener != null) return
        if (networkCallback == null && defaultNetworkCallback == null) return

        networkCallback?.let { cb ->
            runCatching { connectivity.unregisterNetworkCallback(cb) }
            networkCallback = null
        }
        defaultNetworkCallback?.let { cb ->
            runCatching { connectivity.unregisterNetworkCallback(cb) }
            defaultNetworkCallback = null
        }
        pendingRebindJob?.cancel()
        pendingRebindJob = null
        synchronized(networkLock) {
            observedNetwork = null
            observedDefaultNetwork = null
            hasEverObservedNetwork = false
        }
        boundNetwork = null
        boundDefaultNetwork = null
        Log.d(TAG, "stopNetworkWatcherIfIdle: unregistered both callbacks and reset state")
    }

    /**
     * Debounces rebind requests. Each call cancels the previous pending job
     * and launches a fresh one after [REBIND_DEBOUNCE_MILLIS]. Multiple
     * back-to-back rotation events (typical of Android's
     * `onAvailable`/`onLost`/`onCapabilitiesChanged` storms on a single
     * physical handover) collapse into one actual rebind.
     *
     * No `lock` is taken here — that happens inside [rebindNow]. Callbacks
     * must remain cheap and non-blocking.
     */
    private fun scheduleRebind(reason: String) {
        pendingRebindJob?.cancel()
        Log.d(TAG, "scheduleRebind: $reason (debounce=${REBIND_DEBOUNCE_MILLIS}ms)")
        pendingRebindJob = rebindScope.launch {
            delay(REBIND_DEBOUNCE_MILLIS)
            rebindNow(reason)
        }
    }

    /**
     * Performs the actual unregister + re-register cycle for whichever of
     * advertising / discovery is currently active. Runs under [lock] so it
     * cannot race with `startAdvertising` / `startDiscovery` / `stop*`.
     *
     * Idempotency (V0.4-AP two-target check):
     *   - If both watcher callbacks are null (watcher was stopped after
     *     schedule), this is a no-op.
     *   - If BOTH the WIFI/ETHERNET observation AND the default-network
     *     observation are unchanged since the last successful bind, this
     *     is a no-op. The old "target == null → skip" is gone — `null`
     *     observedNetwork is a legitimate steady state in the hotspot-host
     *     case (the AP interface isn't surfaced as a TRANSPORT_WIFI
     *     network), and we still want NSD to re-bind so it picks up
     *     whatever multicast carrier is alive.
     *
     * Listener instances are always rebuilt fresh — the old ones are
     * unregistered and discarded. Multicast-lock state is left untouched.
     */
    private suspend fun rebindNow(reason: String): Unit = lock.withLock {
        if (networkCallback == null && defaultNetworkCallback == null) {
            Log.d(TAG, "rebindNow: watcher already stopped; skipping ($reason)")
            return@withLock
        }
        val target = synchronized(networkLock) { observedNetwork }
        val defaultTarget = synchronized(networkLock) { observedDefaultNetwork }

        val noChangeSinceLastBind =
            target == boundNetwork && defaultTarget == boundDefaultNetwork
        if (noChangeSinceLastBind) {
            Log.d(
                TAG,
                "rebindNow: no changes since last bind; skipping ($reason) " +
                    "transport=$boundNetwork default=$boundDefaultNetwork"
            )
            return@withLock
        }

        val hadAdvertising = registrationListener != null
        val hadDiscovery = discoveryListener != null
        if (!hadAdvertising && !hadDiscovery) {
            Log.d(TAG, "rebindNow: neither advertising nor discovery active; skipping ($reason)")
            return@withLock
        }

        Log.d(
            TAG,
            "rebindNow: starting; reason=$reason " +
                "transport: $boundNetwork -> $target  default: $boundDefaultNetwork -> $defaultTarget " +
                "advertising=$hadAdvertising discovery=$hadDiscovery"
        )

        // V0.4-RESOLVE-RETRY: the old discovery listener is about to be
        // torn down; pending retries reference NsdServiceInfos from it.
        // Discard them so we don't replay stale state against the new
        // listener. (The fresh listener will re-discover peers from
        // scratch via NsdManager's own announcement cycle.)
        clearAllResolveRetries("rebindNow")

        if (hadAdvertising) {
            val oldListener = registrationListener!!
            runCatching { nsd.unregisterService(oldListener) }
            registrationListener = null
            Log.d(TAG, "rebindNow: unregisterService submitted on old listener")

            val cached = cachedLocalPeer
            if (cached != null) {
                val info = buildServiceInfo(cached)
                val freshListener = buildRegistrationListener(confirmation = null)
                runCatching {
                    nsd.registerService(info, NsdManager.PROTOCOL_DNS_SD, freshListener)
                }.onSuccess {
                    registrationListener = freshListener
                    Log.d(TAG, "rebindNow: registerService submitted on fresh listener")
                }.onFailure { e ->
                    Log.w(TAG, "rebindNow: registerService failed", e)
                }
            } else {
                Log.w(TAG, "rebindNow: cachedLocalPeer was null; advertising not restored")
            }
        }

        if (hadDiscovery) {
            val oldListener = discoveryListener!!
            runCatching { nsd.stopServiceDiscovery(oldListener) }
            discoveryListener = null
            Log.d(TAG, "rebindNow: stopServiceDiscovery submitted on old listener")

            val freshListener = buildDiscoveryListener()
            runCatching {
                nsd.discoverServices(
                    LanConstants.SERVICE_TYPE_NSD,
                    NsdManager.PROTOCOL_DNS_SD,
                    freshListener
                )
            }.onSuccess {
                discoveryListener = freshListener
                Log.d(TAG, "rebindNow: discoverServices submitted on fresh listener")
            }.onFailure { e ->
                Log.w(TAG, "rebindNow: discoverServices failed", e)
            }
        }

        boundNetwork = target
        boundDefaultNetwork = defaultTarget
        Log.d(
            TAG,
            "rebindNow: complete; boundNetwork=$target boundDefaultNetwork=$defaultTarget"
        )
    }

    /**
     * V0.4-RESOLVE-RETRY: schedule a re-resolve for [pid] using [info].
     * The retry runs on [rebindScope] after [RESOLVE_RETRY_DELAY_MILLIS].
     *
     * Idempotent per peer — calling again with the same pid cancels the
     * prior pending retry and replaces it with a fresh one (attempt
     * counter is monotonic, not reset). Capped at
     * [RESOLVE_RETRY_MAX_ATTEMPTS] total attempts per peer; further
     * rejections are logged and the peer stays undiscovered.
     */
    private fun scheduleResolveRetry(info: NsdServiceInfo, pid: String, reason: String) {
        val nextAttempt: Int
        synchronized(resolveRetryLock) {
            val current = resolveRetryAttempts.getOrElse(pid) { 0 }
            if (current >= RESOLVE_RETRY_MAX_ATTEMPTS) {
                Log.d(
                    TAG,
                    "scheduleResolveRetry: peer=${pid.take(8)} max attempts " +
                        "($current/$RESOLVE_RETRY_MAX_ATTEMPTS) — giving up ($reason)"
                )
                return
            }
            nextAttempt = current + 1
            resolveRetryAttempts[pid] = nextAttempt
            // Cancel any prior pending retry for this peer; the most recent
            // schedule call wins.
            pendingResolveRetries[pid]?.cancel()
        }
        Log.d(
            TAG,
            "scheduleResolveRetry: peer=${pid.take(8)} attempt " +
                "$nextAttempt/$RESOLVE_RETRY_MAX_ATTEMPTS in ${RESOLVE_RETRY_DELAY_MILLIS}ms ($reason)"
        )
        val job = rebindScope.launch {
            delay(RESOLVE_RETRY_DELAY_MILLIS)
            Log.d(
                TAG,
                "scheduleResolveRetry: peer=${pid.take(8)} attempt $nextAttempt firing re-resolve"
            )
            resolve(info)
        }
        synchronized(resolveRetryLock) {
            pendingResolveRetries[pid] = job
        }
    }

    /**
     * Clear any pending resolve-retry state for [pid]. Called when a
     * resolve succeeds (peer is now discoverable), when the peer is Lost,
     * and during bulk cancellation in [stopDiscovery] / [rebindNow].
     */
    private fun clearResolveRetry(pid: String, reason: String) {
        synchronized(resolveRetryLock) {
            val job = pendingResolveRetries.remove(pid)
            val hadAttempts = resolveRetryAttempts.remove(pid) != null
            if (job != null || hadAttempts) {
                Log.d(TAG, "clearResolveRetry: peer=${pid.take(8)} ($reason)")
            }
            job?.cancel()
        }
    }

    private fun clearAllResolveRetries(reason: String) {
        synchronized(resolveRetryLock) {
            if (pendingResolveRetries.isEmpty() && resolveRetryAttempts.isEmpty()) return
            Log.d(
                TAG,
                "clearAllResolveRetries: cancelling ${pendingResolveRetries.size} pending retries ($reason)"
            )
            pendingResolveRetries.values.forEach { it.cancel() }
            pendingResolveRetries.clear()
            resolveRetryAttempts.clear()
        }
    }

    private companion object {
        const val TAG = "P2pKitNsd"

        /**
         * Debounce window for back-to-back rotation signals. Android emits
         * multiple `onAvailable` / `onCapabilitiesChanged` ticks per single
         * physical handover (typically 100-400ms apart on Pixel devices);
         * 800ms catches a comfortable majority while keeping perceived
         * recovery latency bounded.
         */
        const val REBIND_DEBOUNCE_MILLIS = 800L

        /**
         * V0.4-RESOLVE-RETRY: how long to wait before re-resolving a peer
         * whose first resolve produced no routable host. Sized to comfortably
         * exceed a typical hotspot DHCP completion window (~1-2 s on most
         * stacks).
         */
        const val RESOLVE_RETRY_DELAY_MILLIS = 3000L

        /**
         * V0.4-RESOLVE-RETRY: max total resolve attempts per peer (initial +
         * N-1 retries). With a 3 s delay and max 3 attempts, worst-case
         * wall-clock from first rejection to give-up is ~9 seconds — long
         * enough for slow DHCP without leaving a peer permanently stuck.
         */
        const val RESOLVE_RETRY_MAX_ATTEMPTS = 3

        /**
         * V0.4-D-ANDROID-NUDGE: gap between `unregisterService` and the
         * fresh `registerService` during a discovery refresh. Without a
         * non-zero gap the NSD daemon coalesces them into a no-op
         * (same service name + type appears unchanged); 200 ms is enough
         * for the daemon to process the goodbye before the new registration
         * arrives, while keeping the total refresh window short.
         */
        const val NUDGE_GAP_MILLIS = 200L
    }
}

/**
 * Returns the candidate [InetAddress]es Android NSD has resolved for a
 * peer's service. On API 34+ this is the full [NsdServiceInfo.hostAddresses]
 * list (multiple address families possible). On older APIs only a single
 * `info.host` is exposed by the platform; we wrap it in a single-element
 * list so [selectRoutableHost] applies uniformly.
 */
private fun collectHostCandidates(info: NsdServiceInfo): List<InetAddress> =
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
        info.hostAddresses
    } else {
        @Suppress("DEPRECATION") // info.host is the supported way on API < 34.
        listOfNotNull(info.host)
    }

/**
 * Pick the most-likely-routable host string from [candidates] for use as a
 * dial target. Returns `null` when no candidate is dialable — the caller
 * skips the corresponding discovery event rather than publish an unusable
 * hint.
 *
 * Precedence (V0.4-IPV6):
 *   1. First [Inet4Address] that is neither loopback nor wildcard.
 *      IPv4 link-local (169.254/16) IS accepted — sometimes dialable on
 *      direct-cable / auto-config segments and matches the prior JVM
 *      behaviour.
 *   2. First [Inet6Address] that is neither loopback, wildcard, nor an
 *      unscoped link-local. An [Inet6Address] whose `scopeId` is non-zero
 *      is accepted because [InetAddress.getHostAddress] preserves the
 *      `%scope` suffix, producing a dialable string.
 *
 * Rejected outright: loopback (127.0.0.1, ::1), any-local (0.0.0.0, ::),
 * and `fe80::` IPv6 link-local with `scopeId == 0` (the Test 3 case —
 * Android TCP returns EINVAL on these because no scope is known).
 *
 * Intentionally NOT done here:
 *   - No retry / re-resolve fallback — pure function.
 *   - No normalization that strips `%scope` from accepted scoped addresses.
 *   - No identity-check changes — peerId/appId filtering is the caller's
 *     responsibility and happens upstream.
 */
internal fun selectRoutableHost(candidates: List<InetAddress>): String? {
    candidates.firstOrNull { addr ->
        addr is Inet4Address && !addr.isLoopbackAddress && !addr.isAnyLocalAddress
    }?.let { return it.hostAddress }

    candidates.firstOrNull { addr ->
        addr is Inet6Address &&
            !addr.isLoopbackAddress &&
            !addr.isAnyLocalAddress &&
            (!addr.isLinkLocalAddress || addr.scopeId != 0)
    }?.let { return it.hostAddress }

    return null
}
