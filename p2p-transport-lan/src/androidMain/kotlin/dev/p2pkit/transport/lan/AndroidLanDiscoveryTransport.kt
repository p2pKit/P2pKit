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
 * automatically we watch [ConnectivityManager] for Wi-Fi/Ethernet rotation
 * events and, after a debounce settle window, unregister the old NSD
 * listeners and register fresh ones. The debounced rebind runs in
 * [rebindScope]; ConnectivityManager callbacks themselves do no work beyond
 * scheduling. Multicast-lock state is preserved across rebinds.
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

    /** ConnectivityManager callback, non-null iff watcher is active. */
    private var networkCallback: ConnectivityManager.NetworkCallback? = null

    private val networkLock = Any()

    /** Most recent network reported by the callback. `null` after `onLost`. */
    @Suppress("AnnotationOnSuperclass")
    private var observedNetwork: Network? = null

    /** True once any onAvailable has fired — distinguishes startup from rotation. */
    private var hasEverObservedNetwork: Boolean = false

    /**
     * Network present at the time of the most recent successful NSD register
     * (initial or post-rebind). Used by [rebindNow] to skip no-op rebinds when
     * the observed network has not actually changed since we last bound.
     * Guarded by [lock] (set inside the NSD register path).
     */
    private var boundNetwork: Network? = null

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
        Log.d(TAG, "startAdvertising: registerService submitted, boundNetwork=$boundNetwork")
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
        Log.d(TAG, "startDiscovery: discoverServices submitted, boundNetwork=$boundNetwork")
        ensureNetworkWatcherStarted()
    }

    override suspend fun stopDiscovery() = lock.withLock {
        val listener = discoveryListener ?: return@withLock
        runCatching { nsd.stopServiceDiscovery(listener) }
        discoveryListener = null
        Log.d(TAG, "stopDiscovery: stopServiceDiscovery submitted")
        stopNetworkWatcherIfIdle()
        releaseMulticastLockIfIdle()
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
                resolve(serviceInfo)
            }

            override fun onServiceLost(serviceInfo: NsdServiceInfo) {
                val pid = serviceInfo.serviceName ?: return
                if (pid == registration.localPeerId.value) return
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
                    // The next mDNS announcement may bring an IPv4 we can use.
                    Log.d(
                        TAG,
                        "resolve: rejecting peer=${pid.take(8)} — no routable host " +
                            "in candidates=$candidates"
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
                _events.tryEmit(PeerEvent.Found(internalPeer))
            }
        })
    }

    // ─────────────────────────────────────────────────────────────────────
    // Network-rotation rebind
    // ─────────────────────────────────────────────────────────────────────

    /**
     * Registers a [ConnectivityManager.NetworkCallback] that observes
     * Wi-Fi/Ethernet rotation events. Idempotent — calling again while a
     * callback is already registered is a no-op.
     *
     * Called from `startAdvertising` / `startDiscovery` inside the existing
     * [lock], so it never races with the rebind body.
     */
    private fun ensureNetworkWatcherStarted() {
        if (networkCallback != null) return
        val request = NetworkRequest.Builder()
            .addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
            .addTransportType(NetworkCapabilities.TRANSPORT_ETHERNET)
            .build()
        val cb = object : ConnectivityManager.NetworkCallback() {
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
        runCatching { connectivity.registerNetworkCallback(request, cb) }
            .onSuccess {
                networkCallback = cb
                Log.d(TAG, "ensureNetworkWatcherStarted: registered NetworkCallback (WIFI|ETHERNET)")
            }
            .onFailure { e ->
                Log.w(TAG, "ensureNetworkWatcherStarted: registerNetworkCallback failed", e)
            }
    }

    /**
     * Tears down the watcher and cancels any pending debounced rebind.
     * Called from `stopAdvertising` / `stopDiscovery` only when **both**
     * listeners have been cleared — symmetric with multicast-lock release.
     */
    private fun stopNetworkWatcherIfIdle() {
        if (registrationListener != null || discoveryListener != null) return
        val cb = networkCallback ?: return
        runCatching { connectivity.unregisterNetworkCallback(cb) }
        networkCallback = null
        pendingRebindJob?.cancel()
        pendingRebindJob = null
        synchronized(networkLock) {
            observedNetwork = null
            hasEverObservedNetwork = false
        }
        boundNetwork = null
        Log.d(TAG, "stopNetworkWatcherIfIdle: unregistered NetworkCallback and reset state")
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
     * Idempotency:
     *   - If [networkCallback] is null (watcher was stopped after schedule),
     *     this is a no-op.
     *   - If [observedNetwork] equals [boundNetwork] (the rotation that
     *     scheduled us was already absorbed by a prior rebind), this is a
     *     no-op.
     *
     * Listener instances are always rebuilt fresh — the old ones are
     * unregistered and discarded. Multicast-lock state is left untouched.
     */
    private suspend fun rebindNow(reason: String): Unit = lock.withLock {
        if (networkCallback == null) {
            Log.d(TAG, "rebindNow: watcher already stopped; skipping ($reason)")
            return@withLock
        }
        val target = synchronized(networkLock) { observedNetwork }
        if (target == null) {
            Log.d(TAG, "rebindNow: no observed network; skipping ($reason)")
            return@withLock
        }
        if (target == boundNetwork) {
            Log.d(TAG, "rebindNow: already bound to $target; skipping ($reason)")
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
            "rebindNow: starting; reason=$reason from=$boundNetwork to=$target " +
                "advertising=$hadAdvertising discovery=$hadDiscovery"
        )

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
        Log.d(TAG, "rebindNow: complete; boundNetwork=$target")
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
