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
        // What addresses did JmDNS actually publish for us? These are the IPs
        // a remote peer will try to dial — if they include a non-LAN interface
        // that's the Issue #2 advertise-side failure.
        runCatching {
            JvmLanDiag.log(
                "advertise",
                "registered pid=${registration.localPeerId.value.take(8)} port=${registration.tcpPort} " +
                    "publishedAddrs=[${info.inetAddresses.joinToString(",") { it.hostAddress }}]"
            )
        }
        Unit
    }

    override suspend fun stopAdvertising() = lock.withLock {
        val info = advertisedInfo
        if (info != null) {
            // runCatching: a JmDNS throw here must still let state cleanup +
            // maybeCloseJmdns run, or the handle leaks and the transport is
            // wedged in a half-advertising state (AUDIT-2026-06 fix).
            withContext(Dispatchers.IO) { runCatching { jmdns?.unregisterService(info) } }
        }
        advertisedInfo = null
        advertising = false
        maybeCloseJmdns()
    }

    override suspend fun startDiscovery() = lock.withLock {
        ensureJmdns()
        if (discovering) return@withLock
        val l = buildServiceListener()
        withContext(Dispatchers.IO) {
            jmdns!!.addServiceListener(LanConstants.SERVICE_TYPE_JMDNS, l)
        }
        listener = l
        discovering = true
    }

    private fun buildServiceListener(): ServiceListener = object : ServiceListener {
            override fun serviceAdded(event: ServiceEvent) {
                // Trigger asynchronous resolution; we react in serviceResolved.
                jmdns?.requestServiceInfo(event.type, event.name, true)
            }

            override fun serviceRemoved(event: ServiceEvent) {
                val info = event.info ?: return
                val pid = info.getPropertyString(LanConstants.TXT_PEER_ID) ?: return
                if (pid == registration.localPeerId.value) return
                JvmLanDiag.log("browse", "serviceRemoved pid=${pid.take(8)} — emitting PeerEvent.Lost")
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
                    )
                )
                JvmLanDiag.log(
                    "browse",
                    "serviceResolved pid=${pid.take(8)} name=$name plat=$plat " +
                        "candidates=[${candidates.joinToString(",") { it.hostAddress }}] " +
                        "selected=$host:$port — emitting PeerEvent.Found"
                )
                _events.tryEmit(PeerEvent.Found(internalPeer))
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
     * runs under [lock].
     */
    override suspend fun refresh(): Unit = lock.withLock {
        val handle = jmdns
        val old = listener
        if (handle == null || old == null) return@withLock
        withContext(Dispatchers.IO) {
            runCatching { handle.removeServiceListener(LanConstants.SERVICE_TYPE_JMDNS, old) }
        }
        val fresh = buildServiceListener()
        val listenerOk = runCatching {
            withContext(Dispatchers.IO) {
                handle.addServiceListener(LanConstants.SERVICE_TYPE_JMDNS, fresh)
            }
            listener = fresh
        }.onFailure {
            // Leave null so the next startDiscovery can re-attach cleanly.
            listener = null
        }.isSuccess
        if (!listenerOk) return@withLock
        val cached = withContext(Dispatchers.IO) {
            runCatching { handle.list(LanConstants.SERVICE_TYPE_JMDNS, JMDNS_LIST_SNAPSHOT_TIMEOUT_MS) }
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

    override suspend fun stopDiscovery() = lock.withLock {
        val l = listener
        if (l != null) {
            withContext(Dispatchers.IO) {
                runCatching { jmdns?.removeServiceListener(LanConstants.SERVICE_TYPE_JMDNS, l) }
            }
        }
        listener = null
        discovering = false
        maybeCloseJmdns()
    }

    private suspend fun ensureJmdns() {
        if (jmdns != null) return
        // Internal/test-only opt-in for binding JmDNS to a specific local
        // address. Used by `JvmLanLoopbackTest` to work around macOS where
        // `InetAddress.getLocalHost()` resolves to 127.0.0.1 and JmDNS then
        // advertises a loopback IP, which `selectRoutableHost` rejects.
        // Production callers leave this unset and get the default behaviour.
        val bindAddress = System.getProperty("dev.p2pkit.test.jmdnsBindAddress")
        // Issue #2 forensic trail: dump every local NIC and the address JmDNS
        // is about to bind to BEFORE the bind, so a wrong-interface selection
        // (VPN / virtual / loopback / tethered-cellular) is visible.
        JvmLanDiag.log(
            "bind",
            "ensureJmdns: " +
                (bindAddress?.let { "bindOverride=$it" }
                    ?: "JmDNS default interface selection (no override)")
        )
        runCatching {
            JvmLanDiag.log("bind", "InetAddress.getLocalHost()=${InetAddress.getLocalHost().hostAddress}")
        }
        JvmLanDiag.log("nic", "local interfaces:${JvmLanDiag.describeInterfaces()}")
        jmdns = withContext(Dispatchers.IO) {
            if (bindAddress != null) JmDNS.create(InetAddress.getByName(bindAddress))
            else JmDNS.create()
        }
        runCatching {
            JvmLanDiag.log(
                "bind",
                "JmDNS created: boundInterface=${jmdns?.getInterface()?.hostAddress} name=${jmdns?.getName()}"
            )
        }
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

/**
 * Short snapshot timeout for JmDNS.list() during refresh: the default
 * overload waits up to 6 s for service infos, which would stall the
 * transport lock on the reconnect hot path.
 */
private const val JMDNS_LIST_SNAPSHOT_TIMEOUT_MS: Long = 200
