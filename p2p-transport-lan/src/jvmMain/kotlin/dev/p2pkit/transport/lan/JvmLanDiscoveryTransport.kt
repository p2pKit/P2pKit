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
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
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

    private val lock = Mutex()
    private var jmdns: JmDNS? = null
    private var advertisedInfo: ServiceInfo? = null
    private var listener: ServiceListener? = null
    private var advertising: Boolean = false
    private var discovering: Boolean = false

    override suspend fun startAdvertising(localPeer: LocalPeerInfo) = lock.withLock {
        ensureJmdns()
        if (advertising) return@withLock
        val info = ServiceInfo.create(
            LanConstants.SERVICE_TYPE_JMDNS,
            // Service instance name — must be unique on the network. Using the
            // local peer id satisfies that; some browsers display it.
            registration.localPeerId.value,
            registration.tcpPort,
            /* weight = */ 0,
            /* priority = */ 0,
            mapOf(
                LanConstants.TXT_PEER_ID to registration.localPeerId.value,
                LanConstants.TXT_APP_ID to registration.appId.value,
                LanConstants.TXT_DEVICE_NAME to localPeer.deviceName,
                LanConstants.TXT_PLATFORM to localPeer.platform.name,
                LanConstants.TXT_CAPABILITIES to localPeer.supportedTransports.joinToString(",") { it.name },
                LanConstants.TXT_PROTOCOL_VERSION to LanConstants.PROTOCOL_VERSION.toString()
            )
        )
        withContext(Dispatchers.IO) { jmdns!!.registerService(info) }
        advertisedInfo = info
        advertising = true
    }

    override suspend fun stopAdvertising() = lock.withLock {
        val info = advertisedInfo
        if (info != null) {
            withContext(Dispatchers.IO) { jmdns?.unregisterService(info) }
        }
        advertisedInfo = null
        advertising = false
        maybeCloseJmdns()
    }

    override suspend fun startDiscovery() = lock.withLock {
        ensureJmdns()
        if (discovering) return@withLock
        val l = object : ServiceListener {
            override fun serviceAdded(event: ServiceEvent) {
                // Trigger asynchronous resolution; we react in serviceResolved.
                jmdns?.requestServiceInfo(event.type, event.name, true)
            }

            override fun serviceRemoved(event: ServiceEvent) {
                val info = event.info ?: return
                val pid = info.getPropertyString(LanConstants.TXT_PEER_ID) ?: return
                if (pid == registration.localPeerId.value) return
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
                val host = selectRoutableHost(info.inetAddresses.toList()) ?: return
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
                    )
                )
                _events.tryEmit(PeerEvent.Found(internalPeer))
            }
        }
        withContext(Dispatchers.IO) {
            jmdns!!.addServiceListener(LanConstants.SERVICE_TYPE_JMDNS, l)
        }
        listener = l
        discovering = true
    }

    override suspend fun stopDiscovery() = lock.withLock {
        val l = listener
        if (l != null) {
            withContext(Dispatchers.IO) { jmdns?.removeServiceListener(LanConstants.SERVICE_TYPE_JMDNS, l) }
        }
        listener = null
        discovering = false
        maybeCloseJmdns()
    }

    private suspend fun ensureJmdns() {
        if (jmdns != null) return
        jmdns = withContext(Dispatchers.IO) { JmDNS.create() }
    }

    private suspend fun maybeCloseJmdns() {
        if (advertising || discovering) return
        val handle = jmdns ?: return
        jmdns = null
        withContext(Dispatchers.IO) { runCatching { handle.close() } }
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
