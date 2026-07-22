package dev.p2pkit.transport.lan

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
import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.withContext

/**
 * [DiscoveryTransport] backed by JmDNS for service registration and browsing.
 *
 * Lifecycle:
 *   - [startAdvertising] registers a `_p2pkit._tcp.local.` service with TXT
 *     records that carry our [LanServiceRegistration].
 *   - [startDiscovery] browses for the same service type. When peers are
 *     resolved we filter by `appId`, skip ourselves, and emit
 *     [PeerEvent.Found] / [PeerEvent.Lost].
 *   - [stopAdvertising] / [stopDiscovery] revert each side independently.
 *   - The underlying [JmDNS] handle is shared between advertise and discover
 *     and lazily created on first use; closed when both sides have stopped.
 */
internal class JvmLanDiscoveryTransport(
    private val registration: LanServiceRegistration
) : DiscoveryTransport {

    override val type: TransportKind = TransportKind.LAN

    private val _events = MutableSharedFlow<PeerEvent>(
        replay = 0,
        extraBufferCapacity = 256,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )
    override val events: Flow<PeerEvent> = _events.asSharedFlow()

    /** Shared lifecycle/heartbeat scope used by the platform-neutral coordinator. */
    private val lifecycleScope: CoroutineScope =
        CoroutineScope(SupervisorJob() + Dispatchers.Default)

    private val coordinator = JmdnsLifecycleCoordinator<Unit, JmDNS>(
        ops = buildLifecycleOps(),
        rebindScope = lifecycleScope,
        ioContext = Dispatchers.IO
    )

    /** Callback generation owned by one coordinator listener token. */
    private class ListenerLease {
        val active = AtomicBoolean(true)
        lateinit var listener: ServiceListener
    }

    override suspend fun startAdvertising(localPeer: LocalPeerInfo) =
        coordinator.startAdvertising(localPeer)

    override suspend fun stopAdvertising() = coordinator.stopAdvertising()

    override suspend fun startDiscovery() = coordinator.startDiscovery()

    override suspend fun stopDiscovery() = coordinator.stopDiscovery()

    private fun buildServiceInfo(localPeer: LocalPeerInfo): ServiceInfo {
        val properties = mutableMapOf(
            LanConstants.TXT_PEER_ID to registration.localPeerId.value,
            LanConstants.TXT_APP_ID to registration.appId.value,
            LanConstants.TXT_DEVICE_NAME to localPeer.deviceName,
            LanConstants.TXT_PLATFORM to localPeer.platform.name,
            LanConstants.TXT_CAPABILITIES to localPeer.supportedTransports.joinToString(",") { it.name },
            LanConstants.TXT_PROTOCOL_VERSION to registration.protocolVersion.toString()
        ).apply {
            registration.fingerprint?.let { put(LanConstants.TXT_FINGERPRINT, it.value) }
        }
        return ServiceInfo.create(
            registration.serviceTypeJmdns,
            // Service instance name — must be unique on the network. Using the
            // local peer id satisfies that; some browsers display it.
            registration.localPeerId.value,
            registration.tcpPort,
            /* weight = */ 0,
            /* priority = */ 0,
            properties
        )
    }

    /** One coordinator-owned heartbeat tick over the handle's local cache. */
    private fun reemitCachedPeersBlocking(handle: JmDNS) {
        val cached = runCatching {
            handle.list(registration.serviceTypeJmdns, JMDNS_LIST_SNAPSHOT_TIMEOUT_MS)
        }.getOrDefault(emptyArray())
        var reemitted = 0
        cached.forEach { info ->
            val peer = cachedServiceInfoToInternalPeer(info) ?: return@forEach
            if (_events.tryEmit(PeerEvent.Updated(peer))) reemitted++
        }
        if (reemitted > 0) {
            JvmLanDiag.log("browse", "heartbeat: re-emitted Updated for $reemitted cached peer(s)")
        }
    }

    /**
     * AUDIT-2026-07 (DSC-1): maps an already-resolved cached [ServiceInfo] to
     * the same [InternalPeer] shape `serviceResolved` emits, applying the
     * identical gates — RBS-1 pid validation, appId filter, self skip,
     * routable-host selection. Returns `null` when the record must be
     * skipped. Keep in sync with `serviceResolved` in [buildServiceListener]
     * and with the AndroidLanDiscoveryTransport twin (behavior-parity pair).
     */
    private fun cachedServiceInfoToInternalPeer(info: ServiceInfo): InternalPeer? {
        val pid = validDiscoveryPeerIdOrNull(info.getPropertyString(LanConstants.TXT_PEER_ID))
            ?: return null
        val app = info.getPropertyString(LanConstants.TXT_APP_ID) ?: return null
        if (pid == registration.localPeerId.value) return null
        if (app != registration.appId.value) return null
        val security = validateLanDiscoverySecurityMetadata(
            profile = registration.securityProfile,
            protocolVersion = info.getPropertyString(LanConstants.TXT_PROTOCOL_VERSION),
            fingerprint = info.getPropertyString(LanConstants.TXT_FINGERPRINT)
        ) ?: return null

        val name = info.getPropertyString(LanConstants.TXT_DEVICE_NAME) ?: pid
        val plat = info.getPropertyString(LanConstants.TXT_PLATFORM)
        val caps = info.getPropertyString(LanConstants.TXT_CAPABILITIES)
        val host = selectRoutableHost(info.inetAddresses.toList()) ?: return null
        val port = info.port
        val supportedTransports = caps
            ?.split(",")
            ?.mapNotNull { tag -> runCatching { TransportKind.valueOf(tag.trim()) }.getOrNull() }
            ?.toSet()
            ?: setOf(TransportKind.LAN)
        val platform = plat?.let { runCatching { Platform.valueOf(it) }.getOrNull() } ?: Platform.UNKNOWN
        return InternalPeer(
            publicPeer = Peer(
                id = PeerId(pid),
                name = name,
                platform = platform,
                supportedTransports = supportedTransports
            ),
            transportHints = listOf(
                TransportHint(type = TransportKind.LAN, host = host, port = port)
            ),
            authenticationHint = security.authenticationHint
        )
    }

    private fun buildListenerLease(handle: JmDNS): ListenerLease {
        val lease = ListenerLease()
        lease.listener = buildServiceListener(handle) { lease.active.get() }
        return lease
    }

    private fun buildServiceListener(
        handle: JmDNS,
        isActive: () -> Boolean
    ): ServiceListener = object : ServiceListener {
            override fun serviceAdded(event: ServiceEvent) {
                if (!isActive()) return
                // Trigger asynchronous resolution; we react in serviceResolved.
                runCatching { handle.requestServiceInfo(event.type, event.name, true) }
            }

            override fun serviceRemoved(event: ServiceEvent) {
                if (!isActive()) return
                val info = event.info ?: return
                // AUDIT-2026-07 (RBS-1): validate the TXT pid before it can
                // reach the throwing PeerId constructor, and gate the lost
                // path on appId like the resolved path below — a malformed
                // or other-app record is skipped inside the JmDNS callback
                // instead of propagating an exception through it. Mirrors
                // AndroidLanDiscoveryTransport.serviceRemoved.
                val pid = validDiscoveryPeerIdOrNull(info.getPropertyString(LanConstants.TXT_PEER_ID))
                if (pid == null) {
                    JvmLanDiag.log("browse", "serviceRemoved: TXT pid missing or blank — skipping record")
                    return
                }
                if (info.getPropertyString(LanConstants.TXT_APP_ID) != registration.appId.value) return
                if (pid == registration.localPeerId.value) return
                if (validateLanDiscoverySecurityMetadata(
                        profile = registration.securityProfile,
                        protocolVersion = info.getPropertyString(LanConstants.TXT_PROTOCOL_VERSION),
                        fingerprint = info.getPropertyString(LanConstants.TXT_FINGERPRINT)
                    ) == null
                ) return
                if (isActive()) {
                    JvmLanDiag.log("browse", "serviceRemoved pid=${pid.take(8)} — emitting PeerEvent.Lost")
                    _events.tryEmit(PeerEvent.Lost(PeerId(pid)))
                }
            }

            override fun serviceResolved(event: ServiceEvent) {
                if (!isActive()) return
                val info = event.info ?: return
                // AUDIT-2026-07 (RBS-1): a blank pid must be skipped here,
                // not thrown from PeerId() inside the JmDNS callback.
                val pid = validDiscoveryPeerIdOrNull(info.getPropertyString(LanConstants.TXT_PEER_ID))
                    ?: run {
                        JvmLanDiag.log("browse", "serviceResolved: TXT pid missing or blank — skipping record")
                        return
                    }
                val app = info.getPropertyString(LanConstants.TXT_APP_ID) ?: return
                if (pid == registration.localPeerId.value) return
                if (app != registration.appId.value) return
                val security = validateLanDiscoverySecurityMetadata(
                    profile = registration.securityProfile,
                    protocolVersion = info.getPropertyString(LanConstants.TXT_PROTOCOL_VERSION),
                    fingerprint = info.getPropertyString(LanConstants.TXT_FINGERPRINT)
                ) ?: return

                val name = info.getPropertyString(LanConstants.TXT_DEVICE_NAME) ?: pid
                val plat = info.getPropertyString(LanConstants.TXT_PLATFORM)
                val caps = info.getPropertyString(LanConstants.TXT_CAPABILITIES)
                // Issue #2: log ALL candidate addresses the peer advertised and
                // which one selectRoutableHost picked to dial. A peer that only
                // advertised a non-routable address (e.g. an unscoped fe80::)
                // shows up here as "no routable host".
                val candidates = info.inetAddresses.toList()
                val host = selectRoutableHost(candidates) ?: run {
                    JvmLanDiag.log(
                        "browse",
                        "serviceResolved pid=${pid.take(8)} name=$name " +
                            "candidates=[${candidates.joinToString(",") { it.hostAddress }}] " +
                            "— NO routable host, skipping (will re-fire)"
                    )
                    return
                }
                val port = info.port
                val supportedTransports = caps
                    ?.split(",")
                    ?.mapNotNull { tag -> runCatching { TransportKind.valueOf(tag.trim()) }.getOrNull() }
                    ?.toSet()
                    ?: setOf(TransportKind.LAN)
                val platform = plat?.let { runCatching { Platform.valueOf(it) }.getOrNull() } ?: Platform.UNKNOWN

                val internalPeer = InternalPeer(
                    publicPeer = Peer(
                        id = PeerId(pid),
                        name = name,
                        platform = platform,
                        supportedTransports = supportedTransports
                    ),
                    transportHints = listOf(
                        TransportHint(type = TransportKind.LAN, host = host, port = port)
                    ),
                    authenticationHint = security.authenticationHint
                )
                JvmLanDiag.log(
                    "browse",
                    "serviceResolved pid=${pid.take(8)} name=$name plat=$plat " +
                        "candidates=[${candidates.joinToString(",") { it.hostAddress }}] " +
                        "selected=$host:$port — emitting PeerEvent.Found"
                )
                if (isActive()) _events.tryEmit(PeerEvent.Found(internalPeer))
            }
    }

    /**
     * V0.5-FORCED-REFRESH, JVM port (AUDIT-2026-06 fix). SessionManager
     * refires refresh() ~every 3 s for the entire Reconnecting window. The
     * Android transport rotates its service listener and force re-queries
     * every cached peer so stale SRV records (a peer whose listener port
     * rotated) re-resolve mid-reconnect; the JVM transport inherited the
     * interface's default no-op, leaving that documented recovery mechanism
     * inert on desktop. Mirrors AndroidLanDiscoveryTransport.refresh().
     * `list(type, timeout)` uses a short timeout: with the default 6 s
     * timeout JmDNS can block while it waits for service infos, and this
     * runs under the coordinator lifecycle lock.
     *
     * AUDIT-2026-06 (#7): the fresh listener is attached BEFORE the old one
     * is removed, and CancellationException is never swallowed. The previous
     * remove-then-`runCatching { add }` shape caught cancellations (and
     * genuine add failures) after the old listener was already gone, leaving
     * `listener = null` while `discovering` stayed true — at which point
     * refresh() (null-listener early-return) and startDiscovery()
     * (`discovering` guard) both became permanent no-ops and discovery was
     * dead until a full stopDiscovery/startDiscovery cycle. With add-first
     * ordering every failure path leaves at least one listener registered.
     */
    override suspend fun refresh(): Unit = coordinator.refreshDiscovery { handle ->
        val cached = withContext(Dispatchers.IO) {
            runCatching { handle.list(registration.serviceTypeJmdns, JMDNS_LIST_SNAPSHOT_TIMEOUT_MS) }
                .getOrDefault(emptyArray())
        }
        cached.forEach { info ->
            val pid = info.getPropertyString(LanConstants.TXT_PEER_ID) ?: info.name
            if (pid == registration.localPeerId.value) return@forEach
            withContext(Dispatchers.IO) {
                runCatching { handle.requestServiceInfo(info.type, info.name, true) }
            }
        }
    }

    private fun buildLifecycleOps(): JmdnsLifecycleOps<Unit, JmDNS> =
        object : JmdnsLifecycleOps<Unit, JmDNS> {
            override fun createHandleBlocking(target: Unit?, forRebind: Boolean): JmDNS {
                val bindAddress = System.getProperty("dev.p2pkit.test.jmdnsBindAddress")
                JvmLanDiag.log(
                    "bind",
                    "ensureJmdns: " +
                        (bindAddress?.let { "bindOverride=$it" }
                            ?: "JmDNS default interface selection (no override)")
                )
                runCatching {
                    JvmLanDiag.log(
                        "bind",
                        "InetAddress.getLocalHost()=${InetAddress.getLocalHost().hostAddress}"
                    )
                }
                JvmLanDiag.log("nic", "local interfaces:${JvmLanDiag.describeInterfaces()}")
                val fresh = if (bindAddress != null) {
                    JmDNS.create(InetAddress.getByName(bindAddress))
                } else {
                    JmDNS.create()
                }
                runCatching {
                    JvmLanDiag.log(
                        "bind",
                        "JmDNS created: boundInterface=${fresh.getInterface()?.hostAddress} " +
                            "name=${fresh.getName()}"
                    )
                }
                return fresh
            }

            override fun closeHandleBlocking(handle: JmDNS) = handle.close()

            override fun createServiceToken(localPeer: LocalPeerInfo): Any =
                buildServiceInfo(localPeer)

            override fun registerServiceBlocking(handle: JmDNS, token: Any) {
                val info = token as ServiceInfo
                handle.registerService(info)
                runCatching {
                    JvmLanDiag.log(
                        "advertise",
                        "registered pid=${registration.localPeerId.value.take(8)} " +
                            "port=${registration.tcpPort} " +
                            "publishedAddrs=[${info.inetAddresses.joinToString(",") { it.hostAddress }}]"
                    )
                }
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
                (token as ListenerLease).active.set(false)
            }

            override fun removeListenerBlocking(handle: JmDNS, token: Any) {
                handle.removeServiceListener(
                    registration.serviceTypeJmdns,
                    (token as ListenerLease).listener
                )
            }

            override fun reemitCachedPeersBlocking(handle: JmDNS) {
                this@JvmLanDiscoveryTransport.reemitCachedPeersBlocking(handle)
            }

            override fun currentNetwork(): Unit = Unit
            override fun observedNetwork(): Unit = Unit
            override fun observedDefaultNetwork(): Unit = Unit
            override fun isWatcherActive(): Boolean = false
            override fun acquireMulticastLock() = Unit
            override fun releaseMulticastLock() = Unit
            override fun startNetworkWatcher() = Unit
            override fun stopNetworkWatcher() = Unit

            override fun logDebug(message: String) {
                JvmLanDiag.log("lifecycle", message)
            }

            override fun logWarn(message: String, error: Throwable?) {
                JvmLanDiag.log(
                    "lifecycle",
                    message + (error?.let { " (${it::class.simpleName}: ${it.message})" } ?: "")
                )
            }
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
 *      direct-cable / auto-config segments.
 *   2. First [Inet6Address] that is neither loopback, wildcard, nor an
 *      unscoped link-local. An [Inet6Address] whose `scopeId` is non-zero
 *      is accepted because [InetAddress.getHostAddress] preserves the
 *      `%scope` suffix, producing a dialable string.
 *
 * Rejected outright: loopback (127.0.0.1, ::1), any-local (0.0.0.0, ::),
 * and `fe80::` IPv6 link-local with `scopeId == 0` (TCP rejects these with
 * EINVAL because no scope is known). Closes task #25.
 *
 * Intentionally NOT done here:
 *   - No retry / re-resolve fallback — pure function.
 *   - No normalization that strips `%scope` from accepted scoped addresses.
 *   - No identity-check changes — peerId/appId filtering happens upstream.
 *
 * Implementation is duplicated verbatim in `AndroidLanDiscoveryTransport`
 * (androidMain source set). The two source sets cannot share JVM-only
 * code via commonMain without adding a `jvmAndAndroidMain` source set —
 * larger build-config delta than warranted for ~20 lines. Keep both
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

/**
 * Short snapshot timeout for JmDNS.list() during refresh: the default
 * overload waits up to 6 s for service infos, which would stall the
 * transport lock on the reconnect hot path.
 */
private const val JMDNS_LIST_SNAPSHOT_TIMEOUT_MS: Long = 200
