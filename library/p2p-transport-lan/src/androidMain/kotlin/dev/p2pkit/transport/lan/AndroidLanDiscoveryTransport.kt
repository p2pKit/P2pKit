package dev.p2pkit.transport.lan

import android.content.Context
import android.net.ConnectivityManager
import android.net.LinkProperties
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.wifi.WifiManager
import dev.p2pkit.transport.lan.AndroidLanDiag as Log
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.DiscoveryTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.PeerEvent
import java.io.IOException
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
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** One callback generation installed in JmDNS by the lifecycle coordinator. */
internal class AndroidListenerLease {
    private val gate = Any()

    @Volatile
    private var active: Boolean = true

    lateinit var listener: ServiceListener

    /** Lock-free so a callback never nests two listener-generation locks. */
    fun isActive(): Boolean = active

    fun deactivate() = synchronized(gate) { active = false }

    fun publishIfActive(block: () -> Unit) = synchronized(gate) {
        if (active) block()
    }
}

/** Testable ownership for removals whose JmDNS event has no TXT payload. */
internal class AndroidServiceAdmissions {
    private data class Admission(
        val peerId: PeerId,
        val owner: AndroidListenerLease
    )

    private val entries = ConcurrentHashMap<String, Admission>()

    fun admit(instanceName: String, peerId: PeerId, owner: AndroidListenerLease) {
        entries[instanceName] = Admission(peerId, owner)
    }

    fun remove(instanceName: String, callbackOwner: AndroidListenerLease): PeerId? {
        val admission = entries[instanceName] ?: return null
        if (admission.owner !== callbackOwner && admission.owner.isActive()) return null
        return if (entries.remove(instanceName, admission)) admission.peerId else null
    }

    fun drain(): Set<PeerId> {
        val peers = entries.values.mapTo(mutableSetOf()) { it.peerId }
        entries.clear()
        return peers
    }
}

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
 * Wire-compatibility: JmDNS uses the profile-specific `_p2pkit._tcp.local.`
 * (explicit legacy) or `_p2pkit2._tcp.local.` (secure v2) service type and
 * the shared TXT schema used by the JVM and Apple implementations. Explicit
 * legacy peers therefore remain interoperable with older peers; secure v2 is
 * intentionally segregated and never negotiated from discovery data.
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
 * supplies the JmDNS/Android specifics behind [JmdnsLifecycleOps]. Android's
 * duplicated routing selector, AP/tether fallback, bounded constructor, and
 * TXT-less removal ownership are additionally pinned by `androidHostTest`;
 * physical callback and OEM multicast behavior remain device-validation work.
 */
internal class AndroidLanDiscoveryTransport(
    private val context: Context,
    private val registration: LanServiceRegistration,
    private val networkState: AndroidLanNetworkState = AndroidLanNetworkState()
) : DiscoveryTransport {

    override val type: TransportKind = TransportKind.LAN

    private val peerEventRelay = ReliablePeerEventRelay()
    override val events: Flow<PeerEvent> = peerEventRelay.events

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

    /** Polling fallback for AP/tether interfaces invisible to ConnectivityManager. */
    @Volatile
    private var interfaceWatcherJob: Job? = null

    @Volatile
    private var observedInterfaceFingerprint: String? = null

    @Volatile
    private var boundTarget: AndroidLanBindTarget? = null

    private val handleCreator = BoundedBlockingHandleCreator<JmDNS>(
        timeoutMillis = JMDNS_CREATE_TIMEOUT_MS,
        threadName = "p2pkit-jmdns-create-${registration.localPeerId.value.take(8)}",
        closeOrphan = JmDNS::close,
        onCleanupFailure = { error ->
            Log.w(
                TAG,
                "late JmDNS handle cleanup failed; further creation is blocked",
                error
            )
        }
    )

    /**
     * The lifecycle/rebind state machine (see the class KDoc's 2026-07 note).
     * All start/stop/refresh/rebind serialization happens on the
     * coordinator's internal lock, exactly where the transport's own `Mutex`
     * used to sit.
     */
    private val coordinator = JmdnsLifecycleCoordinator<AndroidLanBindTarget, JmDNS>(
        ops = buildOps(),
        rebindScope = rebindScope,
        ioContext = Dispatchers.IO
    )

    /** Service-instance ownership admitted only after full record validation. */
    private val admittedServices = AndroidServiceAdmissions()

    // ──────────────────────────────────────────────────────────────────
    // DiscoveryTransport API
    // ──────────────────────────────────────────────────────────────────

    override suspend fun startAdvertising(localPeer: LocalPeerInfo) =
        coordinator.startAdvertising(localPeer)

    override suspend fun stopAdvertising() = coordinator.stopAdvertising()

    override suspend fun startDiscovery() = coordinator.startDiscovery()

    override suspend fun stopDiscovery() {
        try {
            coordinator.stopDiscovery()
        } finally {
            // The coordinator deactivates the callback generation before a
            // native detach can fail. Drain transport-managed peer ownership
            // even on that retained-for-retry failure, or stale peers would
            // survive without any active callback able to remove them.
            admittedServices.drain()
            peerEventRelay.clear()
        }
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

    private fun buildOps(): JmdnsLifecycleOps<AndroidLanBindTarget, JmDNS> =
        object : JmdnsLifecycleOps<AndroidLanBindTarget, JmDNS> {

            override fun createHandleBlocking(
                target: AndroidLanBindTarget?,
                forRebind: Boolean
            ): JmDNS {
                val selected = target ?: currentBindTarget()
                    ?: throw IOException(
                        "No Wi-Fi, Ethernet, AP, or tether LAN address is available for JmDNS"
                    )
                // Issue #2 smoking gun: classify the network we're binding
                // JmDNS to. A null Network is expected only for an explicitly
                // selected AP/tether Java interface; cellular/VPN never enters
                // the bind target. The two prefixes below are load-bearing
                // diagnostic lines used by docs/validation/ procedures.
                if (forRebind) {
                    Log.d(
                        TAG,
                        "rebindNow: rebinding onto $selected " +
                            Log.describeNetwork(connectivity, selected.network)
                    )
                } else {
                    Log.d(
                        TAG,
                        "ensureJmdns: active $selected " +
                            Log.describeNetwork(connectivity, selected.network)
                    )
                    Log.d(TAG, "ensureJmdns: NICs:${Log.describeInterfaces()}")
                }
                val fresh = handleCreator.create {
                    JmDNS.create(selected.address, selected.address.hostAddress)
                }
                boundTarget = selected
                networkState.select(selected)
                Log.d(
                    TAG,
                    (if (forRebind) "rebindNow: JmDNS recreated" else "ensureJmdns: created handle") +
                        " bindAddr=${selected.address.hostAddress} iface=${selected.interfaceName}"
                )
                return fresh
            }

            override fun closeHandleBlocking(handle: JmDNS) {
                handle.close()
                boundTarget = null
                // Keep the last immutable route snapshot while the shared
                // handle is being recreated or discovery is temporarily
                // idle. TCP dials therefore remain interface-bound (or fail
                // on the stale route) instead of silently falling back to the
                // process-default cellular path. The data transport clears
                // the snapshot only on its permanent close.
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
                    (token as AndroidListenerLease).listener
                )
            }

            override fun deactivateListenerToken(token: Any) {
                (token as AndroidListenerLease).deactivate()
            }

            override fun removeListenerBlocking(handle: JmDNS, token: Any) {
                handle.removeServiceListener(
                    registration.serviceTypeJmdns,
                    (token as AndroidListenerLease).listener
                )
            }

            override fun currentNetwork(): AndroidLanBindTarget? = currentBindTarget()

            override fun observedNetwork(): AndroidLanBindTarget? =
                synchronized(networkLock) { this@AndroidLanDiscoveryTransport.observedNetwork }
                    ?.let { androidLanBindTargetForNetwork(connectivity, it) }

            override fun observedDefaultNetwork(): String? =
                synchronized(networkLock) {
                    this@AndroidLanDiscoveryTransport.observedDefaultNetwork?.toString()
                }

            override fun isWatcherActive(): Boolean =
                networkCallback != null ||
                    defaultNetworkCallback != null ||
                    interfaceWatcherJob?.isActive == true

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

    private fun currentBindTarget(): AndroidLanBindTarget? {
        synchronized(networkLock) {
            observedNetwork?.let { network ->
                androidLanBindTargetForNetwork(connectivity, network)?.let { return it }
            }
        }
        return currentAndroidLanBindTarget(connectivity)
    }

    private fun localLanInterfaceAddresses(): List<LanInterfaceAddress> {
        return boundTarget?.localAddresses
            ?: currentBindTarget()?.localAddresses
            ?: emptyList()
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
    private fun buildListenerLease(handle: JmDNS): AndroidListenerLease {
        val lease = AndroidListenerLease()
        lease.listener = buildServiceListener(handle, lease)
        return lease
    }

    private fun buildServiceListener(
        handle: JmDNS,
        lease: AndroidListenerLease
    ): ServiceListener = object : ServiceListener {
        override fun serviceAdded(event: ServiceEvent) {
            if (!lease.isActive()) return
            runCatching { handle.requestServiceInfo(event.type, event.name, true) }
        }

        override fun serviceRemoved(event: ServiceEvent) {
            lease.publishIfActive {
                val peerId = admittedServices.remove(event.name, lease)
                    ?: return@publishIfActive
                Log.d(
                    TAG,
                    "serviceRemoved: instance=${sanitizeLanDiagnostic(event.name)} " +
                        "pid=${peerId.value.take(8)} — withdrawing peer state"
                )
                peerEventRelay.remove(peerId)
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
            val hosts = selectRoutableHosts(candidates, localLanInterfaceAddresses())
            if (hosts.isEmpty()) {
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
            val internalPeer = record.toInternalPeer(lanTransportHints(hosts, port))
            lease.publishIfActive {
                admittedServices.admit(event.name, record.peerId, lease)
                Log.d(
                    TAG,
                    "serviceResolved: pid=${record.peerId.value.take(8)} " +
                        "candidates=[${candidates.joinToString(",") { it.hostAddress ?: it.toString() }}] " +
                        "ordered=${hosts.joinToString(",") { "$it:$port" }} — publishing peer state"
                )
                peerEventRelay.upsert(internalPeer)
            }
        }
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
        val lock = wm.createMulticastLock("p2pkit-mdns")
        lock.setReferenceCounted(false)
        // Publish ownership before acquire: if the platform throws after a
        // partial side effect, failed-start rollback and a later stop still
        // retain the only handle capable of releasing it.
        multicastLock = lock
        lock.acquire()
    }

    // ──────────────────────────────────────────────────────────────────
    // Network-rotation watcher (rebind decisions live in the coordinator)
    // ──────────────────────────────────────────────────────────────────

    /**
     * Registers the primary `TRANSPORT_WIFI|ETHERNET` callback (V0.4-NSD),
     * the default-network callback (V0.4-AP), and a bounded Java-interface
     * fingerprint watcher. The three signals are
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
        if (interfaceWatcherJob?.isActive != true) {
            observedInterfaceFingerprint = androidLanInterfaceFingerprint()
            interfaceWatcherJob = rebindScope.launch {
                while (isActive) {
                    delay(INTERFACE_WATCH_INTERVAL_MS)
                    val next = androidLanInterfaceFingerprint()
                    val previous = observedInterfaceFingerprint
                    if (next != previous) {
                        observedInterfaceFingerprint = next
                        Log.d(TAG, "AP/tether interface fingerprint changed: $previous -> $next")
                        coordinator.scheduleRebind(
                            "AP/tether interface/address set changed",
                            force = true
                        )
                    }
                }
            }
            Log.d(TAG, "ensureNetworkWatcherStarted: started AP/tether interface watcher")
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
                val previous = synchronized(networkLock) {
                    val p = observedNetwork
                    observedNetwork = network
                    p
                }
                // registerNetworkCallback reports the currently available
                // network once. Ignore that initial callback only when the
                // JmDNS handle is actually bound to the same Network; a null
                // or different selected network still requires a rebind.
                val alreadyBound = previous == null && networkState.selectedNetwork() == network
                if (previous != network && !alreadyBound) {
                    Log.d(TAG, "NetworkCallback.onAvailable: rotation detected, prev=$previous now=$network")
                    coordinator.scheduleRebind("onAvailable rotation: $previous -> $network")
                } else {
                    Log.d(TAG, "NetworkCallback.onAvailable: $network (no rebind)")
                }
            }

            override fun onLinkPropertiesChanged(network: Network, linkProperties: LinkProperties) {
                val current = synchronized(networkLock) { observedNetwork }
                if (current == network && isSafeAndroidLanNetwork(connectivity, network)) {
                    Log.d(TAG, "NetworkCallback.onLinkPropertiesChanged: $network")
                    coordinator.scheduleRebind("LAN addresses changed on $network", force = true)
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
     * rebind/retry in the same step. Both callbacks and the interface watcher
     * are started/stopped as one ownership group to keep the lifecycle
     * invariant tight.
     */
    private fun stopNetworkWatcherNow() {
        var firstFailure: Exception? = null
        interfaceWatcherJob?.cancel()
        interfaceWatcherJob = null
        observedInterfaceFingerprint = null
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
            }
            Log.d(TAG, "stopNetworkWatcherIfIdle: stopped callbacks/interface watcher and reset state")
        }
        firstFailure?.let { throw it }
    }

    private companion object {
        const val TAG = "P2pKitJmDNS"
        const val JMDNS_CREATE_TIMEOUT_MS: Long = 5_000
        const val INTERFACE_WATCH_INTERVAL_MS: Long = 1_000
    }
}

/**
 * Select an ordered, bounded list of safe dial candidates from `candidates`.
 * The caller publishes the complete list as routing hints so the data
 * transport can fall back when the first address is stale. The compatibility
 * [selectRoutableHost] helper below returns only the first candidate for older
 * tests/callers.
 *
 * Ordering is deterministic: IPv4 before IPv6, then original resolver order;
 * duplicates are removed and the result is capped at
 * [LanConstants.MAX_DIAL_CANDIDATES]. IPv4 link-local (169.254/16) is
 * accepted for direct-cable/auto-config segments. An [Inet6Address] whose
 * `scopeId` is non-zero is retained with its `%scope` suffix. Loopback,
 * wildcard, and unscoped IPv6 link-local addresses are rejected.
 *
 * When `localAddresses` contains valid interface prefixes, only same-subnet
 * candidates are admitted. If no usable prefix is available, the selector
 * retains the general routability filter for constrained environments. No
 * identity checks or network I/O occur here; peerId/appId validation happens
 * upstream and connection retry belongs to the data transport. The
 * implementation is duplicated in `JvmLanDiscoveryTransport` because the
 * source sets cannot share JVM-only `InetAddress` code; keep both copies in
 * sync. `HostSelectorTest` pins the JVM contract for both implementations.
 */
internal data class LanInterfaceAddress(
    val address: InetAddress,
    val prefixLength: Int
)

internal fun selectRoutableHosts(
    candidates: List<InetAddress>,
    localAddresses: List<LanInterfaceAddress> = emptyList()
): List<String> {
    val routable = candidates.withIndex().filter { (_, address) ->
        when (address) {
            is Inet4Address -> !address.isLoopbackAddress && !address.isAnyLocalAddress
            is Inet6Address -> !address.isLoopbackAddress &&
                !address.isAnyLocalAddress &&
                (!address.isLinkLocalAddress || address.scopeId != 0)
            else -> false
        }
    }
    val knownLocalAddresses = localAddresses.filter { local ->
        local.prefixLength in 1..(local.address.address.size * 8)
    }
    val admitted = if (knownLocalAddresses.isEmpty()) {
        routable
    } else {
        routable.filter { (_, candidate) ->
            knownLocalAddresses.any { local -> sameSubnet(candidate, local) }
        }
    }
    return admitted
        .sortedWith(compareBy<IndexedValue<InetAddress>>(
            { if (it.value is Inet4Address) 0 else 1 },
            { it.index }
        ))
        .mapNotNull { it.value.hostAddress }
        .distinct()
        .take(LanConstants.MAX_DIAL_CANDIDATES)
}

internal fun selectRoutableHost(candidates: List<InetAddress>): String? =
    selectRoutableHosts(candidates).firstOrNull()

private fun sameSubnet(candidate: InetAddress, local: LanInterfaceAddress): Boolean {
    val candidateBytes = candidate.address
    val localBytes = local.address.address
    if (candidateBytes.size != localBytes.size) return false
    val bitCount = candidateBytes.size * 8
    if (local.prefixLength !in 1..bitCount) return false
    if (candidate is Inet6Address && candidate.isLinkLocalAddress) {
        val local6 = local.address as? Inet6Address ?: return false
        if (!local6.isLinkLocalAddress || candidate.scopeId != local6.scopeId) return false
    }
    var remaining = local.prefixLength
    for (index in candidateBytes.indices) {
        if (remaining <= 0) return true
        val bits = minOf(8, remaining)
        val mask = (0xFF shl (8 - bits)) and 0xFF
        if ((candidateBytes[index].toInt() and mask) != (localBytes[index].toInt() and mask)) {
            return false
        }
        remaining -= bits
    }
    return true
}
