package dev.p2pkit.transport.lan

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.wifi.WifiManager
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
import javax.jmdns.JmDNS
import javax.jmdns.ServiceEvent
import javax.jmdns.ServiceInfo
import javax.jmdns.ServiceListener
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
import kotlinx.coroutines.withContext

/**
 * [DiscoveryTransport] backed by JmDNS — same in-process mDNS stack the JVM
 * transport uses, replacing the v0.4 `NsdManager`-based implementation.
 *
 * The motivation for the swap (task #25) is the v0.4 known limitation
 * documented in the README: `NsdManager` delegates to a long-lived system
 * daemon whose mDNS cache is opaque to apps, so when an iPhone peer rebinds
 * its listener port the Android side keeps dialing the stale port for the
 * duration of the daemon's TTL. JmDNS holds the cache in-process, exposes
 * `requestServiceInfo(force=true)` for per-peer invalidation, and gives the
 * SDK a real "re-query now" primitive — the actual cache-flush plumbing
 * lands in Phase 2; Phase 1 just gets the new mDNS stack online.
 *
 * Wire-compatibility: JmDNS uses the same `_p2pkit._tcp.local.` service
 * type and the same TXT keys as the v0.4 `NsdManager` and the iOS Bonjour
 * implementation, so a v0.5 Android peer is indistinguishable on the wire
 * from a v0.4 Android peer, a JVM peer, or an iOS peer.
 *
 * Wi-Fi multicast lock: incoming mDNS multicast packets (224.0.0.251:5353)
 * are dropped by Android's Wi-Fi power-save firmware unless an app
 * explicitly holds a [WifiManager.MulticastLock]. The
 * `CHANGE_WIFI_MULTICAST_STATE` permission only **allows** acquiring the
 * lock; the lock itself must also be held. Without it this transport can
 * advertise (outgoing multicast works) but cannot **receive** other
 * peers' advertisements. The lock is acquired on first start (advertise
 * or discover, whichever comes first) and released when both have
 * stopped.
 *
 * Network-rotation rebind (preserved from v0.4): JmDNS binds its
 * `MulticastSocket` to the [InetAddress] it was constructed with. When
 * the underlying network changes (Wi-Fi → hotspot, Wi-Fi → Ethernet,
 * captive portal accept) that socket silently stops receiving multicast.
 * The two complementary [ConnectivityManager] callbacks below feed the
 * debounced rebind machinery, which tears down the old [JmDNS] handle
 * and rebuilds a fresh one bound to the new interface's address:
 *
 *   - **Primary (V0.4-NSD):** filtered on `TRANSPORT_WIFI | TRANSPORT_ETHERNET`.
 *     Catches client-mode Wi-Fi/Ethernet appearance/loss and Wi-Fi→Wi-Fi
 *     handover.
 *   - **Default (V0.4-AP):** registered via `registerDefaultNetworkCallback`.
 *     Catches transitions the primary misses — most importantly the
 *     device-becomes-hotspot-host case where the AP interface is surfaced
 *     as tethering rather than as a client `TRANSPORT_WIFI` network.
 *
 * The debounced rebind runs in [rebindScope]; ConnectivityManager
 * callbacks themselves do no work beyond scheduling. Multicast-lock
 * state is preserved across rebinds.
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
    private val wifi: WifiManager? =
        context.applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager
    private val connectivity: ConnectivityManager =
        context.applicationContext.getSystemService(Context.CONNECTIVITY_SERVICE)
            as ConnectivityManager

    // JmDNS state (mirrors [JvmLanDiscoveryTransport])
    private var jmdns: JmDNS? = null
    private var advertisedInfo: ServiceInfo? = null
    private var serviceListener: ServiceListener? = null

    /**
     * Cached `LocalPeerInfo` from the most recent `startAdvertising` call.
     * Used by [rebindNow] to rebuild the [ServiceInfo] after a fresh
     * [JmDNS] handle is constructed on the new interface. Cleared in
     * `stopAdvertising` so a subsequent rebind cannot inadvertently
     * re-advertise after the host app stopped.
     */
    private var cachedLocalPeer: LocalPeerInfo? = null

    private var multicastLock: WifiManager.MulticastLock? = null

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
    private var observedNetwork: Network? = null

    /** Most recent system-default network reported by the default callback. */
    private var observedDefaultNetwork: Network? = null

    /** True once any onAvailable has fired on the primary callback — distinguishes startup from rotation. */
    private var hasEverObservedNetwork: Boolean = false

    /**
     * Network present at the time of the most recent successful JmDNS
     * (re)bind. Used by [rebindNow] to skip no-op rebinds when neither
     * observed signal has changed since we last bound. Guarded by [lock]
     * (set inside the bind path).
     */
    private var boundNetwork: Network? = null

    /** Default network present at the time of the most recent successful JmDNS bind. */
    private var boundDefaultNetwork: Network? = null

    // ──────────────────────────────────────────────────────────────────
    // DiscoveryTransport API
    // ──────────────────────────────────────────────────────────────────

    override suspend fun startAdvertising(localPeer: LocalPeerInfo) = lock.withLock {
        if (advertisedInfo != null) return@withLock

        acquireMulticastLockIfNeeded()
        ensureJmdns()

        val info = buildServiceInfo(localPeer)
        withContext(Dispatchers.IO) { jmdns!!.registerService(info) }
        advertisedInfo = info
        cachedLocalPeer = localPeer
        boundNetwork = connectivity.activeNetwork
        boundDefaultNetwork = connectivity.activeNetwork
        Log.d(
            TAG,
            "startAdvertising: registered, " +
                "boundNetwork=$boundNetwork boundDefaultNetwork=$boundDefaultNetwork"
        )
        ensureNetworkWatcherStarted()
    }

    override suspend fun stopAdvertising() = lock.withLock {
        val info = advertisedInfo ?: return@withLock
        withContext(Dispatchers.IO) { runCatching { jmdns?.unregisterService(info) } }
        advertisedInfo = null
        cachedLocalPeer = null
        Log.d(TAG, "stopAdvertising: unregistered")
        stopNetworkWatcherIfIdle()
        releaseMulticastLockIfIdle()
        closeJmdnsIfIdle()
    }

    override suspend fun startDiscovery() = lock.withLock {
        if (serviceListener != null) return@withLock

        acquireMulticastLockIfNeeded()
        ensureJmdns()

        val l = buildServiceListener()
        withContext(Dispatchers.IO) {
            jmdns!!.addServiceListener(LanConstants.SERVICE_TYPE_JMDNS, l)
        }
        serviceListener = l
        boundNetwork = connectivity.activeNetwork
        boundDefaultNetwork = connectivity.activeNetwork
        Log.d(
            TAG,
            "startDiscovery: listener added, " +
                "boundNetwork=$boundNetwork boundDefaultNetwork=$boundDefaultNetwork"
        )
        ensureNetworkWatcherStarted()
    }

    override suspend fun stopDiscovery() = lock.withLock {
        val l = serviceListener ?: return@withLock
        withContext(Dispatchers.IO) {
            runCatching { jmdns?.removeServiceListener(LanConstants.SERVICE_TYPE_JMDNS, l) }
        }
        serviceListener = null
        Log.d(TAG, "stopDiscovery: listener removed")
        stopNetworkWatcherIfIdle()
        releaseMulticastLockIfIdle()
        closeJmdnsIfIdle()
    }

    /**
     * V0.4-DISCOVERY-REFRESH + V0.5-FORCED-REFRESH: force a fresh round
     * of active mDNS queries plus per-peer cache invalidation.
     *
     * Two-step body, both steps under [lock]:
     *
     *   1. **Listener rotation** — remove + re-add the service listener.
     *      JmDNS issues a fresh generic browse query (PTR for the service
     *      type) whenever a listener is added, so any peer that has gone
     *      silent since the last query gets a chance to re-announce.
     *
     *   2. **Per-peer forced re-query** — iterate `JmDNS.list(type)` and
     *      call `requestServiceInfo(type, name, persistent=true)` for
     *      every cached non-self peer. Closes the v0.4 known limitation:
     *      when a remote peer rebinds its listener port the local cache
     *      keeps the stale port until the original TTL expires, and
     *      without this call reconnect dials the dead port. The forced
     *      re-query invalidates the cache entry and triggers a fresh
     *      SRV/TXT/A resolution — `serviceResolved` then fires with the
     *      peer's current port and `PeerRegistry` updates in time for
     *      the next reconnect attempt.
     *
     * Why the v0.4 `V0.4-D-ANDROID-NUDGE` is gone: it existed only to
     * nudge the platform NSD daemon to flush its opaque cache (which
     * was the v0.4 limitation in the first place). JmDNS owns the cache
     * in-process, so the targeted `requestServiceInfo` call above is
     * the real fix the v0.4 nudge was approximating.
     *
     * Logs the cached port per peer before the force re-query so the
     * subsequent `serviceResolved` line (which logs the post-refresh
     * host+port) makes the stale→fresh transition visible in logcat.
     *
     * No-op if discovery isn't currently running.
     */
    override suspend fun refresh() = lock.withLock {
        val old = serviceListener
        val handle = jmdns
        if (old == null || handle == null) {
            Log.d(TAG, "refresh: no listener active — skipping")
            return@withLock
        }
        Log.d(TAG, "refresh: rotating listener + force re-querying known peers")

        // Step 1: listener rotation — fresh generic browse.
        withContext(Dispatchers.IO) {
            runCatching { handle.removeServiceListener(LanConstants.SERVICE_TYPE_JMDNS, old) }
        }
        val fresh = buildServiceListener()
        val listenerOk = runCatching {
            withContext(Dispatchers.IO) {
                handle.addServiceListener(LanConstants.SERVICE_TYPE_JMDNS, fresh)
            }
            serviceListener = fresh
        }.onFailure { e ->
            // Leave serviceListener null so the next state change can
            // re-attempt cleanly via startDiscovery / rebindNow.
            serviceListener = null
            Log.w(TAG, "refresh: addServiceListener failed", e)
        }.isSuccess

        if (!listenerOk) return@withLock

        // Step 2: per-peer forced re-query. JmDNS.list() returns the
        // current cached ServiceInfo entries WITHOUT issuing a fresh
        // wire query — it's a pure cache read. requestServiceInfo(...,
        // persistent=true) then invalidates that entry and re-resolves.
        val cached = withContext(Dispatchers.IO) {
            runCatching { handle.list(LanConstants.SERVICE_TYPE_JMDNS) }
                .getOrDefault(emptyArray())
        }
        var forced = 0
        cached.forEach { info ->
            val pid = info.getPropertyString(LanConstants.TXT_PEER_ID) ?: info.name
            if (pid == registration.localPeerId.value) return@forEach
            val cachedPort = info.port
            Log.d(
                TAG,
                "refresh: force re-query pid=${pid.take(8)} " +
                    "name=${info.name} cachedPort=$cachedPort"
            )
            withContext(Dispatchers.IO) {
                runCatching {
                    handle.requestServiceInfo(info.type, info.name, true)
                }
            }
            forced++
        }
        Log.d(TAG, "refresh: complete (rotated listener; forced re-query for $forced peers)")
    }

    // ──────────────────────────────────────────────────────────────────
    // JmDNS lifecycle helpers
    // ──────────────────────────────────────────────────────────────────

    /**
     * Lazily creates the [JmDNS] handle bound to the current active
     * network's primary IPv4 address. Falls back to JmDNS's own default
     * (which enumerates interfaces internally) when [resolveBindAddress]
     * cannot determine an address — better than failing the start.
     *
     * Called under [lock] from `start*` and from [rebindNow] after the
     * old handle is closed.
     */
    private suspend fun ensureJmdns() {
        if (jmdns != null) return
        val bindAddr = resolveBindAddress(connectivity.activeNetwork)
        jmdns = withContext(Dispatchers.IO) {
            if (bindAddr != null) JmDNS.create(bindAddr) else JmDNS.create()
        }
        Log.d(
            TAG,
            "ensureJmdns: created handle bindAddr=${bindAddr?.hostAddress ?: "default"}"
        )
    }

    private suspend fun closeJmdnsIfIdle() {
        if (advertisedInfo != null || serviceListener != null) return
        val handle = jmdns ?: return
        jmdns = null
        withContext(Dispatchers.IO) { runCatching { handle.close() } }
        Log.d(TAG, "closeJmdnsIfIdle: closed handle")
    }

    /**
     * Pick the [InetAddress] to bind JmDNS's `MulticastSocket` to from the
     * given [Network]'s [android.net.LinkProperties]. Returns the first
     * non-loopback non-link-local IPv4 address; falls back to any
     * non-loopback IPv4 (covering 169.254/16 link-local on direct-cable
     * segments); returns `null` if no IPv4 candidate exists.
     *
     * IPv6 binding is deliberately not attempted at Phase 1 — JmDNS's
     * IPv6 path has fewer test miles, and every Android device that
     * carries LAN traffic in practice has IPv4 on the Wi-Fi interface.
     */
    private fun resolveBindAddress(network: Network?): InetAddress? {
        val net = network ?: return null
        val props = runCatching { connectivity.getLinkProperties(net) }.getOrNull() ?: return null
        props.linkAddresses
            .map { it.address }
            .firstOrNull { addr ->
                addr is Inet4Address &&
                    !addr.isLoopbackAddress &&
                    !addr.isLinkLocalAddress
            }?.let { return it }
        props.linkAddresses
            .map { it.address }
            .firstOrNull { addr -> addr is Inet4Address && !addr.isLoopbackAddress }
            ?.let { return it }
        return null
    }

    // ──────────────────────────────────────────────────────────────────
    // Service info / listener builders
    // ──────────────────────────────────────────────────────────────────

    private fun buildServiceInfo(localPeer: LocalPeerInfo): ServiceInfo =
        ServiceInfo.create(
            LanConstants.SERVICE_TYPE_JMDNS,
            // Service instance name — must be unique on the network. Using
            // the local peer id satisfies that; some browsers display it.
            registration.localPeerId.value,
            registration.tcpPort,
            /* weight = */ 0,
            /* priority = */ 0,
            mapOf(
                LanConstants.TXT_PEER_ID to registration.localPeerId.value,
                LanConstants.TXT_APP_ID to registration.appId.value,
                LanConstants.TXT_DEVICE_NAME to localPeer.deviceName,
                LanConstants.TXT_PLATFORM to localPeer.platform.name,
                LanConstants.TXT_CAPABILITIES to
                    localPeer.supportedTransports.joinToString(",") { it.name },
                LanConstants.TXT_PROTOCOL_VERSION to LanConstants.PROTOCOL_VERSION.toString()
            )
        )

    /**
     * Builds a fresh [ServiceListener]. A new instance is constructed for
     * every `addServiceListener` (initial, refresh, or rebind) — JmDNS
     * does not document whether listeners survive a remove + re-add
     * cycle, and reusing one risks subtle bugs.
     *
     * Note (vs. v0.4 NsdManager impl): no separate `resolve` step.
     * JmDNS's `serviceAdded → requestServiceInfo → serviceResolved`
     * chain replaces the v0.4 `NsdManager.ResolveListener` callback
     * dance, and `serviceResolved` re-fires automatically whenever a
     * peer re-announces with updated address records — so the
     * v0.4 `V0.4-RESOLVE-RETRY` queue (for peers that initially
     * announced only fe80:: before DHCP finished) is no longer needed:
     * the next natural re-announce will arrive with the routable
     * address and `serviceResolved` will fire again.
     */
    private fun buildServiceListener(): ServiceListener = object : ServiceListener {
        override fun serviceAdded(event: ServiceEvent) {
            jmdns?.requestServiceInfo(event.type, event.name, true)
        }

        override fun serviceRemoved(event: ServiceEvent) {
            val info = event.info ?: return
            val pid = info.getPropertyString(LanConstants.TXT_PEER_ID) ?: return
            if (pid == registration.localPeerId.value) return
            Log.d(TAG, "serviceRemoved: pid=${pid.take(8)} — emitting PeerEvent.Lost")
            _events.tryEmit(PeerEvent.Lost(PeerId(pid)))
        }

        override fun serviceResolved(event: ServiceEvent) {
            val info = event.info ?: return
            val pid = info.getPropertyString(LanConstants.TXT_PEER_ID) ?: return
            val app = info.getPropertyString(LanConstants.TXT_APP_ID) ?: return
            if (pid == registration.localPeerId.value) return
            if (app != registration.appId.value) return

            val name = info.getPropertyString(LanConstants.TXT_DEVICE_NAME) ?: pid
            val plat = info.getPropertyString(LanConstants.TXT_PLATFORM)
            val caps = info.getPropertyString(LanConstants.TXT_CAPABILITIES)
            val candidates = info.inetAddresses.toList()
            val host = selectRoutableHost(candidates)
            if (host == null) {
                // V0.4-IPV6: no routable address in this resolution. Typical
                // cause is a peer whose only advertised IP on this cycle is
                // an unscoped fe80:: link-local. Skip emitting Found —
                // JmDNS will re-fire serviceResolved on the peer's next
                // re-announce once a routable address is available.
                Log.d(
                    TAG,
                    "serviceResolved: pid=${pid.take(8)} no routable host in " +
                        "candidates=$candidates — skipping (will re-fire)"
                )
                return
            }
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
                "serviceResolved: pid=${pid.take(8)} host=$host port=$port — emitting PeerEvent.Found"
            )
            _events.tryEmit(PeerEvent.Found(internalPeer))
        }
    }

    // ──────────────────────────────────────────────────────────────────
    // Multicast lock
    // ──────────────────────────────────────────────────────────────────

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
        if (advertisedInfo != null || serviceListener != null) return
        val held = multicastLock ?: return
        multicastLock = null
        runCatching { if (held.isHeld) held.release() }
    }

    // ──────────────────────────────────────────────────────────────────
    // Network-rotation rebind
    // ──────────────────────────────────────────────────────────────────

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
                        // Very first signal since the watcher started: JmDNS
                        // was just bound to the current network, so we
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
     * JmDNS to re-bind regardless of whether the primary callback also
     * saw a change. Debounce + the two-target no-change check in
     * `rebindNow` absorb any redundant fires when both callbacks see the
     * same transition.
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
     * only when **both** advertising and discovery have been cleared.
     * The two callbacks are registered together
     * (`ensureNetworkWatcherStarted`) and unregistered together to keep
     * the lifecycle invariant tight.
     */
    private fun stopNetworkWatcherIfIdle() {
        if (advertisedInfo != null || serviceListener != null) return
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
     * Performs the actual JmDNS teardown + recreate cycle for whichever
     * of advertising / discovery is currently active. Runs under [lock]
     * so it cannot race with `startAdvertising` / `startDiscovery` /
     * `stop*`.
     *
     * Idempotency (two-target check, preserved from V0.4-AP):
     *   - If both watcher callbacks are null (watcher stopped after
     *     schedule), this is a no-op.
     *   - If BOTH the WIFI/ETHERNET observation AND the default-network
     *     observation are unchanged since the last successful bind,
     *     this is a no-op. `null` observedNetwork is a legitimate
     *     steady state in the hotspot-host case (the AP interface
     *     isn't surfaced as a TRANSPORT_WIFI network), and we still
     *     want JmDNS to re-bind so it picks up whatever multicast
     *     carrier is alive.
     *
     * The old [JmDNS] handle is closed and a fresh one is created bound
     * to the new interface's [InetAddress] (when one can be resolved).
     * Multicast-lock state is left untouched.
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

        val hadAdvertising = advertisedInfo != null
        val hadDiscovery = serviceListener != null
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

        // Close the old JmDNS handle — this also flushes its in-process
        // mDNS cache, so resolved peer addresses bound to the old
        // interface don't leak forward into the next round.
        val cached = cachedLocalPeer
        withContext(Dispatchers.IO) { runCatching { jmdns?.close() } }
        jmdns = null
        advertisedInfo = null
        serviceListener = null

        // Recreate JmDNS on the new interface.
        val newBindAddr = resolveBindAddress(target ?: defaultTarget)
        val fresh = withContext(Dispatchers.IO) {
            if (newBindAddr != null) JmDNS.create(newBindAddr) else JmDNS.create()
        }
        jmdns = fresh
        Log.d(
            TAG,
            "rebindNow: JmDNS recreated bindAddr=${newBindAddr?.hostAddress ?: "default"}"
        )

        if (hadAdvertising && cached != null) {
            val info = buildServiceInfo(cached)
            runCatching {
                withContext(Dispatchers.IO) { fresh.registerService(info) }
                advertisedInfo = info
                Log.d(TAG, "rebindNow: registerService completed on fresh JmDNS")
            }.onFailure { e ->
                Log.w(TAG, "rebindNow: registerService failed", e)
            }
        } else if (hadAdvertising) {
            Log.w(TAG, "rebindNow: cachedLocalPeer was null; advertising not restored")
        }

        if (hadDiscovery) {
            val l = buildServiceListener()
            runCatching {
                withContext(Dispatchers.IO) {
                    fresh.addServiceListener(LanConstants.SERVICE_TYPE_JMDNS, l)
                }
                serviceListener = l
                Log.d(TAG, "rebindNow: addServiceListener completed on fresh JmDNS")
            }.onFailure { e ->
                Log.w(TAG, "rebindNow: addServiceListener failed", e)
            }
        }

        boundNetwork = target
        boundDefaultNetwork = defaultTarget
        Log.d(
            TAG,
            "rebindNow: complete; boundNetwork=$target boundDefaultNetwork=$defaultTarget"
        )
    }

    private companion object {
        const val TAG = "P2pKitJmDNS"

        /**
         * Debounce window for back-to-back rotation signals. Android emits
         * multiple `onAvailable` / `onCapabilitiesChanged` ticks per single
         * physical handover (typically 100-400ms apart on Pixel devices);
         * 800ms catches a comfortable majority while keeping perceived
         * recovery latency bounded.
         */
        const val REBIND_DEBOUNCE_MILLIS = 800L
    }
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
 * Implementation is duplicated verbatim in `JvmLanDiscoveryTransport`
 * (jvmMain source set); see that file's comment for why. Keep both
 * copies in sync; the `HostSelectorTest` in `:p2p-transport-lan:jvmTest`
 * pins the JVM-side behaviour and serves as the de-facto contract.
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
