package dev.p2pkit.rpc

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pSessionProfile
import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.core.PeerAdmission
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerIdentity
import dev.p2pkit.core.permission.P2pPermissionManager
import dev.p2pkit.rpc.internal.EnrollmentGate
import dev.p2pkit.rpc.internal.MonotonicRpcClock
import dev.p2pkit.rpc.internal.RpcBodyCodec
import dev.p2pkit.rpc.internal.RpcClock
import dev.p2pkit.rpc.internal.RpcHostEngine
import dev.p2pkit.rpc.internal.SessionRpcLink
import dev.p2pkit.rpc.internal.WireKind
import dev.p2pkit.rpc.internal.WireMessage
import dev.p2pkit.rpc.internal.newWireId
import dev.p2pkit.rpc.internal.rpcBoundary
import dev.p2pkit.transport.lan.LanRole
import dev.p2pkit.transport.lan.OrganizationLan
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

public enum class RpcHostState { Idle, Starting, Running, Closed, Failed }
public class RpcPeerConnection internal constructor(
    public val peer: PeerIdentity,
    public val admission: PeerAdmission,
    public val state: ConnectionState,
    public val generation: Long,
)

/** Dedicated star-topology host. The application owns business logic, persistence, authorization and lifecycle. */
public class RpcHost private constructor(
    private val kit: P2pKit,
    public val trust: RpcTrust,
    private val scope: CoroutineScope,
    private val lan: OrganizationLan,
    private val advertise: Boolean,
    private val notificationDescriptors: Map<String, RpcNotification<*>>,
    private val engine: RpcHostEngine,
    private val clock: RpcClock,
    gate: EnrollmentGate,
    allowNearbyPairing: Boolean,
) {
    private val lifecycle = Mutex()
    private val closed = MutableStateFlow(false)
    private val terminalFailure = MutableStateFlow(false)
    private val hostState = MutableStateFlow(RpcHostState.Idle)
    public val state: StateFlow<RpcHostState> = hostState.asStateFlow()
    public val advertisingState: StateFlow<dev.p2pkit.core.FeatureState> get() = kit.advertisingState
    private val peerStates = MutableStateFlow<List<RpcPeerConnection>>(emptyList())
    public val connections: StateFlow<List<RpcPeerConnection>> = peerStates.asStateFlow()
    public val diagnostics: StateFlow<RpcDiagnostics> = engine.diagnostics
    /** Explicit administrator metadata, not diagnostic export or proof of remote delivery. */
    public val requests: StateFlow<RpcHostRequests> = engine.requests
    public val permissions: P2pPermissionManager get() = kit.permissions
    public val fingerprint: PeerFingerprint get() = checkNotNull(kit.localFingerprint)
    private val notificationBudget = PayloadBudget(1L * 1_048_576)
    public val pairing: RpcPairing = RpcPairing(scope, trust, clock, gate, engine.incarnation,
        checkNotNull(kit.localPairingQr), ::endpoint, allowNearbyPairing)

    init {
        engine.onPairRequest = pairing::onRequest
        trust.onRevoke = engine::revoke
        trust.onStorageFailure = { close() }
        // Install incoming collectors before start/listen/advertise. HELLO repeats handle remaining hot-flow races.
        scope.launch(start = CoroutineStart.UNDISPATCHED) {
            try {
                kit.incomingSessions.collect { session ->
                    val link = SessionRpcLink(session, scope, engine.budget, notificationBudget, clock)
                    // Continuous nearby admission must not let silent enrollment links occupy all four slots forever.
                    // Cancel the timer on detach so closed/replaced links cannot accumulate retained jobs.
                    val enrollmentExpiry = if (allowNearbyPairing && link.admission == PeerAdmission.EnrollmentOnly) {
                        scope.launch(start = CoroutineStart.LAZY) {
                            delay(120_000)
                            try { link.close() } catch (_: Exception) { /* Core retains incomplete cleanup. */ }
                        }
                    } else null
                    try {
                        engine.attach(link)
                        link.start(onMessage = { engine.onMessage(link, it) }, onClosed = {
                            enrollmentExpiry?.cancel()
                            try { pairing.onLinkClosed(link) } finally { engine.detach(link) }
                        })
                        enrollmentExpiry?.start()
                    } catch (failure: Exception) {
                        enrollmentExpiry?.cancel()
                        throw failure
                    }
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                // Losing the admission collector is terminal, never a silently running deaf host.
                terminalFailure.value = true
                try { close() } catch (_: Exception) { /* Public close retains the cleanup failure. */ }
            }
        }
        scope.launch(start = CoroutineStart.UNDISPATCHED) {
            kit.sessions.collectLatest { sessions ->
                if (sessions.isEmpty()) peerStates.value = emptyList()
                else combine(sessions.map { session ->
                    combine(session.state, session.connectionInfo) { state, info ->
                        RpcPeerConnection(session.peerIdentity, session.admission, state, info.generation)
                    }
                }) { it.toList() }.collect { peerStates.value = it }
            }
        }
        scope.launch(start = CoroutineStart.UNDISPATCHED) {
            try { awaitCancellation() } finally {
                withContext(NonCancellable) {
                    try { close() } catch (_: Exception) { hostState.value = RpcHostState.Failed }
                }
            }
        }
    }

    @Throws(Exception::class)
    public suspend fun start(): Unit = lifecycle.withLock {
        if (closed.value) throw RpcFailure(RpcFailureKind.Closed, RpcFailurePhase.Admission)
        if (hostState.value == RpcHostState.Running) return@withLock
        hostState.value = RpcHostState.Starting
        try {
            rpcBoundary {
                if (!permissions.hasRequiredPermissions()) throw RpcFailure(
                    RpcFailureKind.PermissionMissing, RpcFailurePhase.Admission)
                kit.start()
                if (advertise) kit.startAdvertising()
            }
            if (closed.value) throw RpcFailure(RpcFailureKind.Closed, RpcFailurePhase.Admission)
            hostState.value = RpcHostState.Running
        } catch (failure: Exception) {
            if (!closed.value) hostState.value = RpcHostState.Failed
            throw failure
        }
    }

    /** Numeric manual fallback uses the SAME identity pin and restrictions as discovery. */
    @Throws(Exception::class)
    public suspend fun endpoint(): RpcEndpoint = rpcBoundary {
        if (hostState.value != RpcHostState.Running) throw RpcFailure(RpcFailureKind.Closed, RpcFailurePhase.Admission)
        val info = kit.networkProvisioning.getManualConnectionInfo()
            ?: throw RpcFailure(RpcFailureKind.NotConnected, RpcFailurePhase.Admission)
        RpcEndpoint(lan.localAddress, info.port)
    }

    /** Enqueued means local acceptance only. The application chooses who may receive each business update. */
    @Throws(Exception::class)
    public suspend fun <T> tryNotify(
        peer: PeerFingerprint, notification: RpcNotification<T>, value: T,
    ): RpcNotifyResult {
        require(notificationDescriptors[notification.key] === notification) { "Register and reuse this notification" }
        if (!trust.isTrusted(peer)) return RpcNotifyResult.NotAuthorized
        val link = engine.trustedLink(peer) ?: return RpcNotifyResult.NotConnected
        val body = try { RpcBodyCodec.encode(notification.payload, value, notification.limitBytes, engine.budget) }
        catch (failure: RpcFailure) {
            if (failure.kind == RpcFailureKind.Overloaded) {
                engine.notificationDropped()
                return RpcNotifyResult.DroppedAtCapacity
            }
            throw failure
        }
        val message = WireMessage(WireKind.Notify, newWireId(), engine.incarnation,
            notification.name, notification.version, body = body)
        return try {
            if (link.offer(message, clock.now() + 1_000, notification = true) == null) {
                engine.notificationDropped()
                RpcNotifyResult.DroppedAtCapacity
            } else RpcNotifyResult.Enqueued
        } finally { message.release() }
    }

    /** Cancels owned work; non-cooperative application handlers may retain resources until they actually exit. */
    @Throws(Exception::class)
    public suspend fun close() {
        closed.value = true
        withContext(NonCancellable) {
            lifecycle.withLock {
                var failed = terminalFailure.value
                try {
                    try { pairing.close() } catch (_: Exception) { failed = true }
                    try { engine.close() } catch (_: Exception) { failed = true }
                    // Reobserve retained core cleanup on repeated calls after a reported failure.
                    try { kit.stop() } catch (_: Exception) { failed = true }
                } finally {
                    hostState.value = if (failed) RpcHostState.Failed else RpcHostState.Closed
                    scope.cancel()
                }
                if (failed) throw RpcFailure(RpcFailureKind.Closed, RpcFailurePhase.Admission)
            }
        }
    }

    public companion object {
        @Throws(Exception::class)
        public suspend fun create(
            platform: RpcPlatform, applicationScope: CoroutineScope, configure: RpcHostConfiguration.() -> Unit,
        ): RpcHost {
            val configuration = RpcHostConfiguration().apply(configure)
            val appId = requireNotNull(configuration.appId) { "RPC appId is required" }
            val lan = requireNotNull(configuration.lan) { "Explicit organization LAN policy is required" }
            val store = requireNotNull(configuration.trustStore) { "A local durable trust store is required" }
            val limits = configuration.limits
            require(configuration.requestHistoryCapacity in 0..256)
            val trust = RpcTrust.load(appId, RpcTrustPurpose.HostClients, store)
            val clock = MonotonicRpcClock()
            val gate = EnrollmentGate(clock)
            val budget = PayloadBudget(limits.payloadBytes)
            val profile = P2pSessionProfile(admission = { identity ->
                when {
                    !trust.healthy -> PeerAdmission.Rejected
                    identity.fingerprint?.let(trust::isTrusted) == true -> PeerAdmission.Trusted
                    gate.isOpen -> PeerAdmission.EnrollmentOnly
                    else -> PeerAdmission.Rejected
                }
            }, payloadBudget = budget, maxTrustedSessions = limits.trustedClients)
            val kit = rpcBoundary { platform.createKit(RpcKitSettings(appId, lan, LanRole.Host, profile)) }
            val scope = CoroutineScope(
                applicationScope.coroutineContext + SupervisorJob(applicationScope.coroutineContext[Job]),
            )
            val engine = RpcHostEngine(scope, configuration.procedures.toMap(), limits, budget, clock, trust::isTrusted,
                requestHistoryCapacity = configuration.requestHistoryCapacity)
            return RpcHost(kit, trust, scope, lan, configuration.advertise, configuration.notifications.toMap(),
                engine, clock, gate, configuration.allowNearbyPairing)
        }
    }
}
