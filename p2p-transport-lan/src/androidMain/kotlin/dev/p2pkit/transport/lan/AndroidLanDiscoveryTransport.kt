package dev.p2pkit.transport.lan

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.wifi.WifiManager
import android.util.Log
import dev.p2pkit.core.PeerId
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
import java.util.concurrent.ConcurrentHashMap
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
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
 *
 * 2026-07 (P1-14 seam): the lifecycle/rebind state machine itself — intent
 * flags vs live handles (AUDIT-2026-06 #5), the bounded create-retry, the
 * idle policy for the shared handle / multicast lock / watcher, and the
 * DSC-3/DSC-13 cleanup guarantees — lives in the platform-neutral
 * [JmdnsLifecycleCoordinator] (commonMain) and is pinned by
 * `JmdnsLifecycleCoordinatorTest` in `:p2p-transport-lan:jvmTest`. This class
 * supplies the JmDNS/Android specifics behind [JmdnsLifecycleOps]. Production
 * behavior is a verbatim port; the extraction exists so the machinery is
 * unit-testable at all (no instrumented Android tests by repo policy).
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

    private val wifi: WifiManager? =
        context.applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager
    private val connectivity: ConnectivityManager =
        context.applicationContext.getSystemService(Context.CONNECTIVITY_SERVICE)
            as ConnectivityManager

    private var multicastLock: WifiManager.MulticastLock? = null

    /**
     * Scope for the debounced rebind coroutine. Uses [SupervisorJob] so a
     * single failed rebind does not poison the scope for future rebinds.
     * Lifetime is the transport instance — children are cancelled via the
     * coordinator's pending-job handles when the watcher stops, but the
     * scope itself persists for re-use on the next start.
     */
    private val rebindScope: CoroutineScope =
        CoroutineScope(SupervisorJob() + Dispatchers.Default)

    /**
     * Primary [ConnectivityManager] callback filtered on
     * `TRANSPORT_WIFI | TRANSPORT_ETHERNET`. Tracks client-mode LAN
     * availability — Wi-Fi / Ethernet networks the device has joined as a
     * client. Non-null iff watcher is active.
     */
    @Volatile
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
    @Volatile
    private var defaultNetworkCallback: ConnectivityManager.NetworkCallback? = null

    private val networkLock = Any()

    /** Most recent network reported by the primary callback. `null` after `onLost`. */
    private var observedNetwork: Network? = null

    /** Most recent system-default network reported by the default callback. */
    private var observedDefaultNetwork: Network? = null

    /** True once any onAvailable has fired on the primary callback — distinguishes startup from rotation. */
    private var hasEverObservedNetwork: Boolean = false

    /**
     * The lifecycle/rebind state machine (see the class KDoc's 2026-07 note).
     * All start/stop/refresh/rebind serialization happens on the
     * coordinator's internal lock, exactly where the transport's own [Mutex]
     * used to sit.
     */
    private val coordinator = JmdnsLifecycleCoordinator<Network, JmDNS>(
        ops = buildOps(),
        rebindScope = rebindScope,
        ioContext = Dispatchers.IO
    )

    /** Callback generation owned by one coordinator listener token. */
    private class ListenerLease {
        private val gate = Any()
        private var active: Boolean = true
        lateinit var listener: ServiceListener

        fun isActive(): Boolean = synchronized(gate) { active }

        fun deactivate() = synchronized(gate) { active = false }

        fun publishIfActive(block: () -> Unit) = synchronized(gate) {
            if (active) block()
        }
    }

    private data class ServiceAdmission(
        val peerId: PeerId,
        val owner: ListenerLease
    )

    /** Service-instance ownership admitted only after full record validation. */
    private val admittedServices = ConcurrentHashMap<String, ServiceAdmission>()

    // ──────────────────────────────────────────────────────────────────
    // DiscoveryTransport API
    // ──────────────────────────────────────────────────────────────────

    override suspend fun startAdvertising(localPeer: LocalPeerInfo) =
        coordinator.startAdvertising(localPeer)

    override suspend fun stopAdvertising() = coordinator.stopAdvertising()

    override suspend fun startDiscovery() = coordinator.startDiscovery()

    override suspend fun stopDiscovery() {
        coordinator.stopDiscovery()
        val lost = admittedServices.values.mapTo(mutableSetOf()) { it.peerId }
        admittedServices.clear()
        lost.forEach { _events.tryEmit(PeerEvent.Lost(it)) }
    }

    /**
     * V0.4-DISCOVERY-REFRESH + V0.5-FORCED-REFRESH: force a fresh round
     * of active mDNS queries plus per-peer cache invalidation.
     *
     * Two-step body, both steps under the coordinator lock:
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
    override suspend fun refresh(): Unit = coordinator.refreshDiscovery { handle ->
        Log.d(TAG, "refresh: rotating listener + force re-querying known peers")

        // Listener rotation is transactionally owned by the coordinator.
        // Per-peer forced re-query: JmDNS.list() is NOT a pure
        // cache read — the default overload can block up to 6 s waiting for
        // service infos (ServiceCollector), and this runs under the
        // coordinator lock on the ~3 s reconnect refresh cadence. Use a short
        // snapshot timeout (AUDIT-2026-06 fix). requestServiceInfo(...,
        // persistent=true) then invalidates each entry and re-resolves.
        val cached = withContext(Dispatchers.IO) {
            runCatching { handle.list(registration.serviceTypeJmdns, 200L) }
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
    // JmdnsLifecycleOps — the JmDNS/Android specifics behind the coordinator
    // ──────────────────────────────────────────────────────────────────

    private fun buildOps(): JmdnsLifecycleOps<Network, JmDNS> =
        object : JmdnsLifecycleOps<Network, JmDNS> {

            override fun createHandleBlocking(target: Network?, forRebind: Boolean): JmDNS {
                // Issue #2 smoking gun: classify the network we're binding
                // JmDNS to. If transports=[CELLULAR] or [VPN] the bind picked
                // an interface that cannot carry LAN multicast/TCP —
                // discovery and dials will fail. The two prefixes below are
                // load-bearing diagnostic lines (docs/LAN_DIAGNOSTICS_PROTOCOL.md).
                if (forRebind) {
                    Log.d(
                        TAG,
                        "rebindNow: rebinding onto ${AndroidLanDiag.describeNetwork(connectivity, target)}"
                    )
                } else {
                    Log.d(TAG, "ensureJmdns: active ${AndroidLanDiag.describeNetwork(connectivity, target)}")
                    Log.d(TAG, "ensureJmdns: NICs:${AndroidLanDiag.describeInterfaces()}")
                }
                val bindAddr = resolveBindAddress(target)
                val fresh = if (bindAddr != null) JmDNS.create(bindAddr) else JmDNS.create()
                Log.d(
                    TAG,
                    (if (forRebind) "rebindNow: JmDNS recreated" else "ensureJmdns: created handle") +
                        " bindAddr=${bindAddr?.hostAddress ?: "default"}"
                )
                return fresh
            }

            override fun closeHandleBlocking(handle: JmDNS) {
                handle.close()
            }

            override fun createServiceToken(localPeer: LocalPeerInfo): Any =
                buildServiceInfo(localPeer)

            override fun registerServiceBlocking(handle: JmDNS, token: Any) {
                handle.registerService(token as ServiceInfo)
            }

            override fun unregisterServiceBlocking(handle: JmDNS, token: Any) {
                handle.unregisterService(token as ServiceInfo)
            }

            override fun createListenerToken(handle: JmDNS): Any =
                buildListenerLease(handle)

            override fun addListenerBlocking(handle: JmDNS, token: Any) {
                handle.addServiceListener(
                    registration.serviceTypeJmdns,
                    (token as ListenerLease).listener
                )
            }

            override fun deactivateListenerToken(token: Any) {
                (token as ListenerLease).deactivate()
            }

            override fun removeListenerBlocking(handle: JmDNS, token: Any) {
                handle.removeServiceListener(
                    registration.serviceTypeJmdns,
                    (token as ListenerLease).listener
                )
            }

            override fun reemitCachedPeersBlocking(handle: JmDNS) {
                // AUDIT-2026-07 (DSC-1): one heartbeat tick — snapshot the
                // already-resolved services from the local JmDNS cache and
                // re-emit Updated for each one that passes the same gates as
                // serviceResolved. Uses the short snapshot timeout refresh()
                // uses (no forced per-peer re-query — unlike refresh()'s
                // step 2 — so no added multicast; the B:317 snapshot-latency
                // deferral is untouched). Mirrors
                // JvmLanDiscoveryTransport.reemitCachedPeers.
                val cached = runCatching { handle.list(registration.serviceTypeJmdns, 200L) }
                    .getOrDefault(emptyArray())
                var reemitted = 0
                cached.forEach { info ->
                    val peer = cachedServiceInfoToInternalPeer(info) ?: return@forEach
                    if (_events.tryEmit(PeerEvent.Updated(peer))) reemitted++
                }
                if (reemitted > 0) {
                    Log.d(TAG, "heartbeat: re-emitted Updated for $reemitted cached peer(s)")
                }
            }

            override fun currentNetwork(): Network? = connectivity.activeNetwork

            override fun observedNetwork(): Network? =
                synchronized(networkLock) { this@AndroidLanDiscoveryTransport.observedNetwork }

            override fun observedDefaultNetwork(): Network? =
                synchronized(networkLock) { this@AndroidLanDiscoveryTransport.observedDefaultNetwork }

            override fun isWatcherActive(): Boolean =
                networkCallback != null || defaultNetworkCallback != null

            override fun acquireMulticastLock() = acquireMulticastLockIfNeeded()

            override fun releaseMulticastLock() {
                val held = multicastLock ?: return
                if (held.isHeld) held.release()
                // Clear ownership only after release succeeds. A failed
                // release remains retryable on the next terminal stop.
                multicastLock = null
            }

            override fun startNetworkWatcher() = ensureNetworkWatcherStarted()

            override fun stopNetworkWatcher() = stopNetworkWatcherNow()

            override fun logDebug(message: String) {
                Log.d(TAG, message)
            }

            override fun logWarn(message: String, error: Throwable?) {
                if (error != null) Log.w(TAG, message, error) else Log.w(TAG, message)
            }
        }

    /**
     * Pick the [InetAddress] to bind JmDNS's `MulticastSocket` to from the
     * given [Network]'s [android.net.LinkProperties]. Returns the first
     * non-loopback non-link-local IPv4 address; falls back to any
     * non-loopback IPv4 (covering 169.254/16 link-local on direct-cable
     * segments); returns `null` if no IPv4 candidate exists — JmDNS then
     * falls back to its own default interface enumeration, better than
     * failing the start.
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

    private fun buildServiceInfo(localPeer: LocalPeerInfo): ServiceInfo {
        val properties = buildLanTxtProperties(
            peerId = registration.localPeerId,
            appId = registration.appId,
            deviceName = localPeer.deviceName,
            platform = localPeer.platform,
            supportedTransports = localPeer.supportedTransports,
            protocolVersion = registration.protocolVersion,
            fingerprint = registration.fingerprint
        )
        return ServiceInfo.create(
            registration.serviceTypeJmdns,
            // Service instance name — must be unique on the network. Using
            // the local peer id satisfies that; some browsers display it.
            registration.localPeerId.value,
            registration.tcpPort,
            /* weight = */ 0,
            /* priority = */ 0,
            properties
        )
    }

    /**
     * Builds a fresh [ServiceListener] for [handle]. A new instance is
     * constructed for every `addServiceListener` (initial, refresh, or
     * rebind) — JmDNS does not document whether listeners survive a
     * remove + re-add cycle, and reusing one risks subtle bugs. The listener
     * captures the handle it is registered on (2026-07, P1-14 seam: the
     * mutable handle field moved into the coordinator) — same object the old
     * field read yielded in every live case, and a straggler event from an
     * already-replaced handle now re-queries via its own (possibly closed)
     * handle inside `runCatching` instead of poking the new one.
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
    private fun buildListenerLease(handle: JmDNS): ListenerLease {
        val lease = ListenerLease()
        lease.listener = buildServiceListener(handle, lease)
        return lease
    }

    private fun buildServiceListener(
        handle: JmDNS,
        lease: ListenerLease
    ): ServiceListener = object : ServiceListener {
        override fun serviceAdded(event: ServiceEvent) {
            if (!lease.isActive()) return
            runCatching { handle.requestServiceInfo(event.type, event.name, true) }
        }

        override fun serviceRemoved(event: ServiceEvent) {
            lease.publishIfActive {
                val admission = admittedServices[event.name] ?: return@publishIfActive
                if (admission.owner !== lease) return@publishIfActive
                if (!admittedServices.remove(event.name, admission)) return@publishIfActive
                Log.d(
                    TAG,
                    "serviceRemoved: instance=${sanitizeLanDiagnostic(event.name)} " +
                        "pid=${admission.peerId.value.take(8)} — emitting Lost"
                )
                _events.tryEmit(PeerEvent.Lost(admission.peerId))
            }
        }

        override fun serviceResolved(event: ServiceEvent) {
            if (!lease.isActive()) return
            val info = event.info ?: return
            val record = validatedRecord(info) ?: return
            if (event.name != record.peerId.value || info.name != record.peerId.value) {
                Log.d(TAG, "serviceResolved: service/TXT identity mismatch — skipping")
                return
            }
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
                    "serviceResolved: pid=${record.peerId.value.take(8)} no routable host in " +
                        "candidates=$candidates — skipping (will re-fire)"
                )
                return
            }
            val port = info.port
            if (port !in 1..65_535) return
            val internalPeer = record.toInternalPeer(
                TransportHint(type = TransportKind.LAN, host = host, port = port)
            )
            lease.publishIfActive {
                admittedServices[event.name] = ServiceAdmission(record.peerId, lease)
                Log.d(
                    TAG,
                    "serviceResolved: pid=${record.peerId.value.take(8)} " +
                        "candidates=[${candidates.joinToString(",") { it.hostAddress ?: it.toString() }}] " +
                        "selected=$host:$port — emitting PeerEvent.Found"
                )
                _events.tryEmit(PeerEvent.Found(internalPeer))
            }
        }
    }

    /**
     * AUDIT-2026-07 (DSC-1): maps an already-resolved cached [ServiceInfo] to
     * the same [InternalPeer] shape `serviceResolved` emits, applying the
     * identical gates — RBS-1 pid validation, appId filter, self skip,
     * routable-host selection. Returns `null` when the record must be
     * skipped. Keep in sync with `serviceResolved` in [buildServiceListener]
     * and with the JvmLanDiscoveryTransport twin (behavior-parity pair).
     */
    private fun cachedServiceInfoToInternalPeer(info: ServiceInfo): InternalPeer? {
        val record = validatedRecord(info) ?: return null
        if (info.name != record.peerId.value) return null
        val host = selectRoutableHost(info.inetAddresses.toList()) ?: return null
        if (info.port !in 1..65_535) return null
        return record.toInternalPeer(
            TransportHint(type = TransportKind.LAN, host = host, port = info.port)
        )
    }

    private fun validatedRecord(info: ServiceInfo): ValidatedLanDiscoveryRecord? =
        validateLanDiscoveryRecord(
            properties = LanConstants.DISCOVERY_TXT_KEYS.associateWith(info::getPropertyString),
            expectedAppId = registration.appId,
            localPeerId = registration.localPeerId,
            securityProfile = registration.securityProfile
        )

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

    // ──────────────────────────────────────────────────────────────────
    // Network-rotation watcher (rebind decisions live in the coordinator)
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
     * leaves that callback alone but ensures the other is up. Called by the
     * coordinator from `startAdvertising` / `startDiscovery` inside its
     * lock, so it never races with the rebind body.
     */
    private fun ensureNetworkWatcherStarted() {
        if (networkCallback == null) {
            val cb = buildPrimaryNetworkCallback()
            val request = NetworkRequest.Builder()
                .addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
                .addTransportType(NetworkCapabilities.TRANSPORT_ETHERNET)
                .build()
            try {
                connectivity.registerNetworkCallback(request, cb)
                networkCallback = cb
                Log.d(TAG, "ensureNetworkWatcherStarted: registered NetworkCallback (WIFI|ETHERNET)")
            } catch (error: Exception) {
                Log.w(TAG, "ensureNetworkWatcherStarted: registerNetworkCallback failed", error)
            }
        }
        if (defaultNetworkCallback == null) {
            val cb = buildDefaultNetworkCallback()
            try {
                connectivity.registerDefaultNetworkCallback(cb)
                defaultNetworkCallback = cb
                Log.d(TAG, "ensureNetworkWatcherStarted: registered DefaultNetworkCallback")
            } catch (error: Exception) {
                Log.w(TAG, "ensureNetworkWatcherStarted: registerDefaultNetworkCallback failed", error)
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
                    coordinator.scheduleRebind("onAvailable rotation: $prev -> $network")
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
     * saw a change. Debounce + the two-target no-change check in the
     * coordinator's `rebindNow` absorb any redundant fires when both
     * callbacks see the same transition.
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
                    coordinator.scheduleRebind("default network changed: $prev -> $network")
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
                    coordinator.scheduleRebind("default network lost: $network")
                } else {
                    Log.d(TAG, "DefaultNetworkCallback.onLost: $network (was not current default)")
                }
            }
        }

    /**
     * Tears down BOTH callbacks (primary + default) and resets observed
     * state. Invoked by the coordinator only when **both** advertising and
     * discovery intents have been cleared (its AUDIT-2026-06 #5 intent-based
     * idle check); the coordinator also cancels any pending debounced
     * rebind/retry in the same step. The two callbacks are registered
     * together (`ensureNetworkWatcherStarted`) and unregistered together to
     * keep the lifecycle invariant tight.
     */
    private fun stopNetworkWatcherNow() {
        var firstFailure: Exception? = null
        networkCallback?.let { cb ->
            try {
                connectivity.unregisterNetworkCallback(cb)
                networkCallback = null
            } catch (error: Exception) {
                firstFailure = error
                Log.w(TAG, "stopNetworkWatcherIfIdle: primary callback cleanup failed; retaining ownership", error)
            }
        }
        defaultNetworkCallback?.let { cb ->
            try {
                connectivity.unregisterNetworkCallback(cb)
                defaultNetworkCallback = null
            } catch (error: Exception) {
                val existing = firstFailure
                if (existing == null) firstFailure = error else existing.addSuppressed(error)
                Log.w(TAG, "stopNetworkWatcherIfIdle: default callback cleanup failed; retaining ownership", error)
            }
        }
        if (networkCallback == null && defaultNetworkCallback == null) {
            synchronized(networkLock) {
                observedNetwork = null
                observedDefaultNetwork = null
                hasEverObservedNetwork = false
            }
            Log.d(TAG, "stopNetworkWatcherIfIdle: unregistered both callbacks and reset state")
        }
        firstFailure?.let { throw it }
    }

    private companion object {
        const val TAG = "P2pKitJmDNS"
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
