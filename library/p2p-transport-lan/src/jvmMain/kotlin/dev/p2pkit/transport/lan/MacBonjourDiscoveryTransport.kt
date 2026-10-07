package dev.p2pkit.transport.lan

import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.DiscoveryTransport
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.PeerEvent
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.launch
import java.io.Closeable
import java.io.IOException

/** Explicit-index DNS-SD is independent of scoped TCP; neither one is evidence of delivery to another device. */
internal class MacBonjourDiscoveryTransport(
    private val registration: LanServiceRegistration,
    private val policy: OrganizationLan,
    private val role: LanRole,
    private val api: MacBonjourCalls = MacBonjourNative,
    private val snapshot: () -> JvmLanSocketSnapshot? = ::readJvmLanSocketSnapshot,
) : DiscoveryTransport {
    override val type: TransportKind = TransportKind.LAN
    private val relay = ReliablePeerEventRelay()
    override val events: Flow<PeerEvent> = relay.events
    private val admissions = JvmServiceAdmissions()
    private val failureBackoff = MacBonjourFailureBackoff()
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private val coordinator = JmdnsLifecycleCoordinator(operations(), scope, Dispatchers.IO)
    private val watcher by lazy {
        JvmLanNetworkWatcher(scope, 1_000, Dispatchers.IO, { target()?.first }) { _, _, admit ->
            coordinator.scheduleRebind("scoped Bonjour selected interface changed", admit = admit)
        }
    }

    private fun target(): Pair<JvmLanBindTarget, Int>? = macBonjourTarget(policy, snapshot())

    override suspend fun startAdvertising(localPeer: LocalPeerInfo) {
        check(role == LanRole.Host) { "A dial-only LAN transport cannot advertise" }
        coordinator.startAdvertising(localPeer)
    }
    override suspend fun stopAdvertising() = coordinator.stopAdvertising()
    override suspend fun startDiscovery() = coordinator.startDiscovery()
    override suspend fun stopDiscovery() {
        try { coordinator.stopDiscovery() } finally { admissions.drain(); relay.clear() }
    }
    override suspend fun refresh() = coordinator.refreshDiscovery { }

    private class Session(val index: Int) : Closeable {
        val tokens = linkedSetOf<Token>()
        @Volatile var active = true
        override fun close() {
            active = false
            val errors = tokens.toList().mapNotNull { token ->
                runCatching { token.close(); tokens.remove(token) }.exceptionOrNull()
            }
            if (errors.isNotEmpty()) throw IOException("Scoped Bonjour session cleanup failed", errors.first())
        }
    }
    private class Token(val localPeer: LocalPeerInfo? = null, val lease: JvmListenerLease? = null) : Closeable {
        @Volatile var active = true
        private var retry: Job? = null
        @Synchronized fun retry(scope: CoroutineScope, waitMillis: Long, action: () -> Unit) {
            if (!active || retry != null) return
            retry = scope.launch(start = CoroutineStart.LAZY) { delay(waitMillis); action() }.also { it.start() }
        }
        var worker: MacBonjourWorker? = null
        var browser: MacBonjourBrowser? = null
        override fun close() {
            synchronized(this) { active = false; retry?.cancel() }
            lease?.deactivate()
            worker?.close()
            browser?.verifyClosed()
        }
    }

    private fun operations(): JmdnsLifecycleOps<JvmLanBindTarget, Session> =
        object : JmdnsLifecycleOps<JvmLanBindTarget, Session> {
            override fun createHandleBlocking(
                target: JvmLanBindTarget?, forRebind: Boolean,
            ): JmdnsHandleBinding<JvmLanBindTarget, Session> {
                val selected = target() ?: throw IOException("Scoped Bonjour selected LAN unavailable")
                return JmdnsHandleBinding(selected.first, Session(selected.second))
            }
            override fun closeHandleBlocking(handle: Session) = handle.close()
            override fun createServiceToken(localPeer: LocalPeerInfo): Any = Token(localPeer = localPeer)
            override fun registerServiceBlocking(handle: Session, token: Any) {
                val owner = token as Token
                handle.tokens += owner
                // Pure TXT construction shares exactly the existing wire codec, not a JmDNS socket/instance.
                val info = buildJmdnsServiceInfo(registration, checkNotNull(owner.localPeer))
                val ref = MacBonjourRef(api, handle.index)
                val worker = MacBonjourWorker(ref, { source, running, ready ->
                    var announced = false
                    while (running()) {
                        source.poll(100)?.let { event ->
                            check(event.kind == 4 && event.name == registration.localPeerId.value)
                            if (!announced) { announced = true; ready() }
                        }
                    }
                }, { error -> failure(handle, owner, error) })
                owner.worker = worker
                worker.start { ref.open(2, registration.protocolVersion, registration.localPeerId.value,
                    info.port, info.textBytes) }
                worker.awaitRegistration()
            }
            override fun unregisterServiceBlocking(handle: Session, token: Any) = remove(handle, token as Token)
            override fun createListenerToken(handle: Session): Any = Token(lease = JvmListenerLease(
                onStagingOverflow = { admissions.drain(); relay.clear() },
            ))
            override fun addListenerBlocking(handle: Session, token: Any) {
                val owner = token as Token
                val lease = checkNotNull(owner.lease)
                handle.tokens += owner
                val ref = MacBonjourRef(api, handle.index)
                val browser = MacBonjourBrowser(registration, policy, handle.index, api, { name, event ->
                    lease.publishIfActive(name) {
                        val record = event?.let { validateMacBonjourRecord(it, registration, policy) }
                        if (record == null) admissions.removeAndPublish(name, lease) { relay.remove(it) }
                        else {
                            val endpoint = checkNotNull(record.numericEndpoint)
                            admissions.admitAndPublish(name, record.peerId, lease) {
                                relay.upsert(record.toInternalPeer(
                                    lanTransportHints(listOf(endpoint.host), endpoint.port)))
                            }
                        }
                    }
                })
                owner.browser = browser
                val worker = MacBonjourWorker(ref, browser::run, { error -> failure(handle, owner, error) })
                owner.worker = worker
                worker.start { ref.open(1, registration.protocolVersion) }
            }
            override fun activateListenerBlocking(token: Any) {
                // A newly scoped browse is an authoritative fresh snapshot. A vanished record need not
                // generate Remove in the new browser, so never retain the predecessor's managed-lifetime state.
                admissions.drain()
                relay.clear()
                (token as Token).lease?.activate()
            }
            override fun deactivateListenerToken(token: Any) {
                (token as Token).lease?.let { it.deactivate(); admissions.listenerDeactivated(it) }
            }
            override fun removeListenerBlocking(handle: Session, token: Any) = remove(handle, token as Token)
            private fun remove(handle: Session, token: Token) {
                token.close()
                handle.tokens.remove(token)
            }
            override fun currentNetwork(): JvmLanBindTarget? = target()?.first
            override fun observedNetwork(): JvmLanBindTarget? = watcher.observedTarget()
            override fun observedDefaultNetwork(): Any? = null
            override fun isWatcherActive(): Boolean = watcher.isActive()
            override fun acquireMulticastLock() = Unit
            override fun releaseMulticastLock() = Unit
            override fun startNetworkWatcher(boundNetwork: JvmLanBindTarget?) = watcher.start(boundNetwork)
            override fun stopNetworkWatcher() = watcher.stop()
            override fun logDebug(message: String) = JvmLanDiag.log("bonjour", message)
            override fun logWarn(message: String, error: Throwable?) =
                JvmLanDiag.log("bonjour", "$message (${error?.javaClass?.simpleName})")
        }

    private fun failure(handle: Session, token: Token, error: Throwable) {
        fun retire() {
            if (!handle.active || !token.active) return
            admissions.drain()
            relay.clear()
            JvmLanDiag.log("bonjour", "Scoped Bonjour failed (${error.javaClass.simpleName}); retiring generation")
            token.retry(scope, failureBackoff.nextDelay()) {
                coordinator.scheduleRebind("scoped Bonjour callback failure", force = true,
                    admit = { handle.active && token.active })
            }
        }
        val lease = token.lease
        // Serialize withdrawal against listener retirement; an old callback may not clear the new generation.
        if (lease == null) retire() else lease.publishIfActive("native-failure") { retire() }
    }
}

/** Native Bonjour scope is the positive interface index, never Java's source-binding approximation. */
internal fun macBonjourTarget(
    policy: OrganizationLan, snapshot: JvmLanSocketSnapshot?,
): Pair<JvmLanBindTarget, Int>? {
    snapshot ?: return null
    val network = snapshot.interfaces.singleOrNull { it.name == policy.interfaceName } ?: return null
    if (!network.isUp || !network.supportsMulticast || network.isLoopback || network.isVirtual ||
        network.isPointToPoint || isForbiddenLanInterface(network.name)) return null
    val index = snapshot.interfaceIndices[network.name]?.takeIf { it > 0 } ?: return null
    val address = network.addresses.map { it.address }.singleOrNull {
        it.address.size == 4 && policy.isLocal(it.hostAddress.orEmpty())
    } ?: return null
    return JvmLanBindTarget(network.name, address, "${network.name}:$index:${address.hostAddress}") to index
}

/** Cross-generation callback failures cannot reset the coordinator into an aggressive create/fail loop. */
internal class MacBonjourFailureBackoff(private val clock: () -> Long = System::nanoTime) {
    private var previous: Long? = null
    private var attempt = 0
    @Synchronized fun nextDelay(): Long {
        val now = clock()
        if (previous?.let { now - it >= 60_000_000_000L } == true) attempt = 0
        previous = now
        val result = minOf(30_000L, 1_000L shl minOf(attempt, 5))
        attempt = minOf(attempt + 1, 5)
        return result
    }
}
