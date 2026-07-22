package dev.p2pkit.transport.lan

import dev.p2pkit.core.PeerId
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.DiscoveryTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.PeerEvent
import java.net.Inet4Address
import java.net.Inet6Address
import java.net.InetAddress
import java.net.NetworkInterface
import javax.jmdns.JmDNS
import javax.jmdns.ServiceEvent
import javax.jmdns.ServiceInfo
import javax.jmdns.ServiceListener
import java.util.concurrent.ConcurrentHashMap
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext

/** One callback generation installed in JmDNS by the lifecycle coordinator. */
internal class JvmListenerLease {
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

/**
 * Thread-safe ownership for service instances admitted after complete TXT
 * validation. JmDNS removal callbacks commonly omit TXT data, so the exact
 * peer identity must come from this registry rather than the removal record.
 */
internal class JvmServiceAdmissions {
    private data class Admission(
        val peerId: PeerId,
        val owner: JvmListenerLease
    )

    private val entries = ConcurrentHashMap<String, Admission>()

    fun admit(instanceName: String, peerId: PeerId, owner: JvmListenerLease) {
        entries[instanceName] = Admission(peerId, owner)
    }

    fun remove(instanceName: String, callbackOwner: JvmListenerLease): PeerId? {
        val admission = entries[instanceName] ?: return null
        // A current listener may consume a removal for an entry admitted by
        // its deactivated predecessor. A stale listener can never withdraw
        // ownership installed by a newer active listener.
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
 * [DiscoveryTransport] backed by JmDNS for service registration and browsing.
 *
 * Lifecycle:
 *   - [startAdvertising] registers the security-profile-specific LAN service
 *     namespace (`_p2pkit._tcp.local.` for explicit legacy or
 *     `_p2pkit2._tcp.local.` for secure v2) with TXT records that carry our
 *     [LanServiceRegistration].
 *   - [startDiscovery] browses for that same profile-specific service type. When peers are
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

    /** Shared lifecycle scope used by the platform-neutral coordinator. */
    private val lifecycleScope: CoroutineScope =
        CoroutineScope(SupervisorJob() + Dispatchers.Default)

    @Volatile
    private var observedNetworkFingerprint: String? = null

    @Volatile
    private var networkWatcherJob: Job? = null

    private val coordinator = JmdnsLifecycleCoordinator<String, JmDNS>(
        ops = buildLifecycleOps(),
        rebindScope = lifecycleScope,
        ioContext = Dispatchers.IO
    )

    /** Service-instance ownership admitted only after full record validation. */
    private val serviceAdmissions = JvmServiceAdmissions()

    override suspend fun startAdvertising(localPeer: LocalPeerInfo) =
        coordinator.startAdvertising(localPeer)

    override suspend fun stopAdvertising() = coordinator.stopAdvertising()

    override suspend fun startDiscovery() = coordinator.startDiscovery()

    override suspend fun stopDiscovery() {
        coordinator.stopDiscovery()
        serviceAdmissions.drain().forEach { _events.tryEmit(PeerEvent.Lost(it)) }
    }

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
            // Service instance name — must be unique on the network. Using the
            // local peer id satisfies that; some browsers display it.
            registration.localPeerId.value,
            registration.tcpPort,
            /* weight = */ 0,
            /* priority = */ 0,
            properties
        )
    }

    private fun validatedRecord(info: ServiceInfo): ValidatedLanDiscoveryRecord? =
        validateLanDiscoveryRecord(
            properties = LanConstants.DISCOVERY_TXT_KEYS.associateWith(info::getPropertyString),
            expectedAppId = registration.appId,
            localPeerId = registration.localPeerId,
            securityProfile = registration.securityProfile
        )

    private fun buildListenerLease(handle: JmDNS): JvmListenerLease {
        val lease = JvmListenerLease()
        lease.listener = buildServiceListener(handle, lease)
        return lease
    }

    private fun buildServiceListener(
        handle: JmDNS,
        lease: JvmListenerLease
    ): ServiceListener = object : ServiceListener {
            override fun serviceAdded(event: ServiceEvent) {
                if (!lease.isActive()) return
                // Trigger asynchronous resolution; we react in serviceResolved.
                runCatching { handle.requestServiceInfo(event.type, event.name, true) }
            }

            override fun serviceRemoved(event: ServiceEvent) {
                lease.publishIfActive {
                    val peerId = serviceAdmissions.remove(event.name, lease)
                        ?: return@publishIfActive
                    JvmLanDiag.log(
                        "browse",
                        "serviceRemoved instance=${event.name} " +
                            "pid=${peerId.value.take(8)} — emitting Lost"
                    )
                    _events.tryEmit(PeerEvent.Lost(peerId))
                }
            }

            override fun serviceResolved(event: ServiceEvent) {
                if (!lease.isActive()) return
                val info = event.info ?: return
                val record = validatedRecord(info) ?: return
                if (event.name != record.peerId.value || info.name != record.peerId.value) {
                    JvmLanDiag.log("browse", "serviceResolved: service/TXT identity mismatch — skipping")
                    return
                }
                // Issue #2: log every advertised address and the ordered,
                // bounded candidates retained for fallback. A peer that only
                // advertises non-routable addresses (e.g. an unscoped fe80::)
                // shows up here as "no routable host".
                val candidates = info.inetAddresses.toList()
                val hosts = selectRoutableHosts(candidates, localLanInterfaceAddresses())
                if (hosts.isEmpty()) {
                    JvmLanDiag.log(
                        "browse",
                        "serviceResolved pid=${record.peerId.value.take(8)} name=${record.deviceName} " +
                            "candidates=[${candidates.joinToString(",") { it.hostAddress }}] " +
                            "— NO routable host, skipping (will re-fire)"
                    )
                    return
                }
                val port = info.port
                if (port !in 1..65_535) return
                val internalPeer = record.toInternalPeer(lanTransportHints(hosts, port))
                lease.publishIfActive {
                    serviceAdmissions.admit(event.name, record.peerId, lease)
                    JvmLanDiag.log(
                        "browse",
                        "serviceResolved pid=${record.peerId.value.take(8)} " +
                            "name=${record.deviceName} plat=${record.platform} " +
                            "candidates=[${candidates.joinToString(",") { it.hostAddress }}] " +
                            "ordered=${hosts.joinToString(",") { "$it:$port" }} — emitting PeerEvent.Found"
                    )
                    _events.tryEmit(PeerEvent.Found(internalPeer))
                }
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

    private fun buildLifecycleOps(): JmdnsLifecycleOps<String, JmDNS> =
        object : JmdnsLifecycleOps<String, JmDNS> {
            override fun createHandleBlocking(target: String?, forRebind: Boolean): JmDNS {
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
                        "JmDNS created: boundInterface=${fresh.inetAddress?.hostAddress} " +
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
                    (token as JvmListenerLease).listener
                )
            }

            override fun deactivateListenerToken(token: Any) {
                (token as JvmListenerLease).deactivate()
            }

            override fun removeListenerBlocking(handle: JmDNS, token: Any) {
                handle.removeServiceListener(
                    registration.serviceTypeJmdns,
                    (token as JvmListenerLease).listener
                )
            }

            override fun currentNetwork(): String = jvmLanNetworkFingerprint()
            override fun observedNetwork(): String? = observedNetworkFingerprint
            override fun observedDefaultNetwork(): String? = null
            override fun isWatcherActive(): Boolean = networkWatcherJob?.isActive == true
            override fun acquireMulticastLock() = Unit
            override fun releaseMulticastLock() = Unit
            override fun startNetworkWatcher() = startNetworkWatcherIfNeeded()
            override fun stopNetworkWatcher() = stopNetworkWatcherNow()

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

    private fun startNetworkWatcherIfNeeded() {
        if (networkWatcherJob?.isActive == true) return
        observedNetworkFingerprint = jvmLanNetworkFingerprint()
        networkWatcherJob = lifecycleScope.launch {
            while (isActive) {
                delay(NETWORK_WATCH_INTERVAL_MS)
                val next = jvmLanNetworkFingerprint()
                val previous = observedNetworkFingerprint
                if (next != previous) {
                    observedNetworkFingerprint = next
                    coordinator.scheduleRebind(
                        "JVM interface/address set changed: $previous -> $next"
                    )
                }
            }
        }
    }

    private fun stopNetworkWatcherNow() {
        networkWatcherJob?.cancel()
        networkWatcherJob = null
        observedNetworkFingerprint = null
    }
}

/**
 * Select an ordered, bounded list of safe dial candidates from [candidates].
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
 * When [localAddresses] contains valid interface prefixes, only same-subnet
 * candidates are admitted. If no usable prefix is available, the selector
 * retains the general routability filter for constrained environments. No
 * identity checks or network I/O occur here; peerId/appId validation happens
 * upstream and connection retry belongs to the data transport. The
 * implementation is duplicated in `AndroidLanDiscoveryTransport` because
 * the source sets cannot share JVM-only `InetAddress` code; keep both copies
 * in sync. [HostSelectorTest] pins the JVM contract for both implementations.
 */
internal data class LanInterfaceAddress(
    val address: InetAddress,
    val prefixLength: Int
)

/**
 * Return every safe candidate in deterministic dial order. When local
 * interface prefixes are known, only same-subnet addresses are admitted;
 * this prevents a same-link mDNS record from turning discovery into an
 * arbitrary routed-address dial. With no interface information the legacy
 * routability filter remains available for constrained JVM environments.
 */
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

internal fun localLanInterfaceAddresses(): List<LanInterfaceAddress> = runCatching {
    NetworkInterface.getNetworkInterfaces().toList()
        .asSequence()
        .filter { it.isUp && !it.isLoopback && !it.isPointToPoint && !it.isVirtual }
        .flatMap { network ->
            network.interfaceAddresses.asSequence().mapNotNull { entry ->
                val address = entry.address ?: return@mapNotNull null
                LanInterfaceAddress(address, entry.networkPrefixLength.toInt())
            }
        }
        .toList()
}.getOrDefault(emptyList())

internal fun jvmLanNetworkFingerprint(): String = runCatching {
    NetworkInterface.getNetworkInterfaces().toList()
        .asSequence()
        .filter { it.isUp && !it.isLoopback && !it.isPointToPoint && !it.isVirtual }
        .flatMap { network ->
            network.interfaceAddresses.asSequence().mapNotNull { entry ->
                entry.address?.hostAddress?.let { address ->
                    "${network.name}:$address/${entry.networkPrefixLength}"
                }
            }
        }
        .sorted()
        .joinToString("|")
}.getOrDefault("")

/**
 * Short snapshot timeout for JmDNS.list() during refresh: the default
 * overload waits up to 6 s for service infos, which would stall the
 * transport lock on the reconnect hot path.
 */
private const val JMDNS_LIST_SNAPSHOT_TIMEOUT_MS: Long = 200
private const val NETWORK_WATCH_INTERVAL_MS: Long = 1_000
