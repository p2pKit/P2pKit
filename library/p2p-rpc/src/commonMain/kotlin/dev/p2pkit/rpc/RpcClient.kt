package dev.p2pkit.rpc

import dev.p2pkit.core.FeatureState
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pSessionProfile
import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerAdmission
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.permission.P2pPermissionManager
import dev.p2pkit.rpc.internal.MonotonicRpcClock
import dev.p2pkit.rpc.internal.OwnedBytes
import dev.p2pkit.rpc.internal.RpcClientEngine
import dev.p2pkit.rpc.internal.RpcClock
import dev.p2pkit.rpc.internal.RpcNotifications
import dev.p2pkit.rpc.internal.SessionRpcLink
import dev.p2pkit.rpc.internal.WireKind
import dev.p2pkit.rpc.internal.WireMessage
import dev.p2pkit.rpc.internal.newWireId
import dev.p2pkit.rpc.internal.rpcBoundary
import dev.p2pkit.transport.lan.LanRole
import dev.p2pkit.transport.lan.OrganizationLan
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancel
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.withTimeoutOrNull
import kotlin.time.Duration
import kotlin.time.Duration.Companion.minutes
import kotlin.time.Duration.Companion.seconds

/** One selected pinned host, dial-only. No incoming peers, mesh, or durable/offline call queue. */
public class RpcClient private constructor(
    private val kit: P2pKit,
    public val trust: RpcTrust,
    private val scope: CoroutineScope,
    private val lan: OrganizationLan,
    private val selected: MutableStateFlow<PeerFingerprint?>,
    private val enrollmentPin: MutableStateFlow<PeerFingerprint?>,
    private val budget: PayloadBudget,
    private val clock: RpcClock,
    private val engine: RpcClientEngine,
    notificationDescriptors: Map<String, RpcNotification<*>>,
) {
    private val connectionLock = Mutex()
    private val closeLock = Mutex()
    private val closed = MutableStateFlow(false)
    public val diagnostics: StateFlow<RpcDiagnostics> = engine.diagnostics
    public val requestTotals: StateFlow<RpcRequestTotals> = engine.requestTotals
    public val state: StateFlow<RpcConnectionState> = engine.state
    public val permissions: P2pPermissionManager get() = kit.permissions
    public val fingerprint: PeerFingerprint get() = checkNotNull(kit.localFingerprint)
    /** Discovery is advisory only; connecting always pins a cryptographic identity. */
    public val discoveredPeers: StateFlow<List<Peer>> get() = kit.peers
    public val discoveryState: StateFlow<FeatureState> get() = kit.discoveryState

    /** Bounded current snapshots. Re-read for UI updates; manual peers and stale/unsigned claims are omitted. */
    public fun discoveredHosts(): List<RpcDiscoveredHost> = kit.peers.value.mapNotNull { peer ->
        kit.discoveryClaim(peer.id)?.let { RpcDiscoveredHost(it.peer, it.fingerprint) }
    }

    private val notificationBudget = PayloadBudget(1L * 1_048_576)
    private val notifications = RpcNotifications(scope, notificationDescriptors, budget, engine::notificationDropped)

    init {
        engine.onNotification = { notifications.offer(it) }
        trust.onRevoke = { if (selected.value == it) engine.close() }
        trust.onStorageFailure = { close() }
        scope.launch(start = CoroutineStart.UNDISPATCHED) {
            try { awaitCancellation() } finally {
                withContext(NonCancellable) {
                    try { close() } catch (_: Exception) { /* Public close can reobserve retained core cleanup. */ }
                }
            }
        }
    }

    @Throws(Exception::class)
    public suspend fun startDiscovery(): Unit = rpcBoundary { kit.startDiscovery() }

    @Throws(Exception::class)
    public suspend fun stopDiscovery(): Unit = rpcBoundary { kit.stopDiscovery() }

    @Throws(Exception::class)
    public suspend fun connect(host: RpcSelectedHost): Unit = connectionLock.withLock {
        if (!trust.isTrusted(host.fingerprint)) throw RpcFailure(RpcFailureKind.Unauthorized, RpcFailurePhase.Trust)
        val link = open(host, enrolling = false)
        try {
            if (engine.awaitReady().admission != PeerAdmission.Trusted) {
                throw RpcFailure(RpcFailureKind.Unauthorized, RpcFailurePhase.Negotiation)
            }
        } catch (failure: Exception) {
            try { link.close() } catch (_: Exception) { /* Do not overwrite the original failure/cancellation. */ }
            throw failure
        }
    }

    /** Scan a trusted local QR; host administrator approval persists BOTH sides before normal use. */
    @Throws(Exception::class)
    public suspend fun pair(invitation: RpcInvitation, timeout: Duration = 2.minutes): RpcSelectedHost =
        connectionLock.withLock {
            require(timeout.inWholeMilliseconds in 1..120_000)
            val pin = kit.parsePeerPairingQr(invitation.hostQr)
                ?: throw RpcFailure(RpcFailureKind.Authentication, RpcFailurePhase.Trust)
            val host = RpcSelectedHost(pin, invitation.endpoint)
            enroll(pin, timeout, WireKind.PairRequest, { open(host, enrolling = true) }) {
                val proof = invitation.proof()
                try { OwnedBytes.copy(proof, budget) } finally { proof.fill(0) }
            }
            host
        }

    /**
     * First-use approval WITHOUT an invitation secret. The caller must first display this fingerprint
     * and obtain informed local confirmation (or compare it through a trusted independent channel).
     * Discovery is not identity proof. The remote host must explicitly opt in and approve THIS client's
     * authenticated key. Saves trust only after approval, then closes; connect() performs fresh authentication.
     */
    @Throws(Exception::class)
    public suspend fun requestApproval(host: RpcSelectedHost, timeout: Duration = 2.minutes): RpcSelectedHost =
        connectionLock.withLock {
            enroll(host.fingerprint, timeout, WireKind.RequestApproval, { open(host, enrolling = true) }) { null }
            host
        }

    /** Same informed first-use requirements as the numeric overload; never approves on discovery alone. */
    @Throws(Exception::class)
    public suspend fun requestApproval(host: RpcDiscoveredHost, timeout: Duration = 2.minutes): Unit =
        connectionLock.withLock {
            enroll(host.fingerprint, timeout, WireKind.RequestApproval, { openDiscovered(host, true) }) { null }
        }

    /** The caller selects the host; this method never chooses the first advertisement or trusts a name/IP. */
    @Throws(Exception::class)
    public suspend fun connect(host: RpcDiscoveredHost): Unit = connectionLock.withLock {
        if (!trust.isTrusted(host.fingerprint)) throw RpcFailure(RpcFailureKind.Unauthorized, RpcFailurePhase.Trust)
        val link = openDiscovered(host, false)
        try {
            if (engine.awaitReady().admission != PeerAdmission.Trusted) {
                throw RpcFailure(RpcFailureKind.Unauthorized, RpcFailurePhase.Negotiation)
            }
        } catch (failure: Exception) {
            try { link.close() } catch (_: Exception) { /* Preserve failure; core retains cleanup. */ }
            throw failure
        }
    }

    private suspend fun enroll(
        pin: PeerFingerprint, timeout: Duration, kind: WireKind,
        openLink: suspend () -> SessionRpcLink, body: () -> OwnedBytes?,
    ) {
        require(timeout.inWholeMilliseconds in 1..120_000)
        val replies = Channel<WireKind>(4)
        val requestId = newWireId()
        engine.onPairMessage = { if (it.id == requestId) replies.trySend(it.kind) }
        var link: SessionRpcLink? = null
        var completed = false
        try {
            withTimeout(timeout.inWholeMilliseconds) {
                link = openLink()
                val ready = engine.awaitReady()
                if (ready.admission != PeerAdmission.Trusted) {
                    val request = WireMessage(kind, requestId, ready.incarnation, body = body())
                    try {
                        while (true) {
                            checkNotNull(link).offer(request, clock.now() + 1_000)
                            when (withTimeoutOrNull(500) { replies.receive() }) {
                                WireKind.PairApproved -> break
                                WireKind.PairDenied -> throw RpcFailure(
                                    RpcFailureKind.Unauthorized, RpcFailurePhase.Trust,
                                )
                                else -> delay(100)
                            }
                        }
                    } finally { request.release() }
                }
                // Trusted READY on a retry proves the host previously durably approved THIS client key.
                trust.approve(pin)
            }
            completed = true
        } catch (cancelled: TimeoutCancellationException) {
            if (!currentCoroutineContext().isActive) throw cancelled
            throw RpcFailure(RpcFailureKind.DeadlineExceeded, RpcFailurePhase.Trust)
        } finally {
            withContext(NonCancellable) {
                engine.onPairMessage = null
                replies.cancel()
                enrollmentPin.value = null
                try { link?.close() } catch (_: Exception) {
                    if (completed) throw RpcFailure(RpcFailureKind.Closed, RpcFailurePhase.Admission)
                }
            }
        }
    }

    private suspend fun openDiscovered(host: RpcDiscoveredHost, enrolling: Boolean): SessionRpcLink = rpcBoundary {
        preflightOpen(host.fingerprint, enrolling)
        val current = kit.discoveryClaim(host.peer.id)
        if (current?.fingerprint != host.fingerprint) {
            throw RpcFailure(RpcFailureKind.NotConnected, RpcFailurePhase.Admission)
        }
        // The restricted transport resolves only policy-checked numeric hints; no manual endpoint/route fallback.
        attach(kit.connect(current.peer, host.fingerprint))
    }

    @OptIn(ExperimentalP2pApi::class)
    private suspend fun open(host: RpcSelectedHost, enrolling: Boolean): SessionRpcLink = rpcBoundary {
        if (!lan.allows(host.endpoint.address)) throw RpcFailure(RpcFailureKind.Unauthorized, RpcFailurePhase.Admission)
        preflightOpen(host.fingerprint, enrolling)
        val peer = kit.networkProvisioning.createManualPeer(host.endpoint.address, host.endpoint.port, host.fingerprint)
        attach(kit.connect(peer))
    }

    private suspend fun preflightOpen(pin: PeerFingerprint, enrolling: Boolean) {
        if (closed.value) throw RpcFailure(RpcFailureKind.Closed, RpcFailurePhase.Admission)
        if (!permissions.hasRequiredPermissions()) throw RpcFailure(
            RpcFailureKind.PermissionMissing, RpcFailurePhase.Admission,
        )
        engine.close() // Explicit replacement never replays outstanding calls.
        selected.value = pin
        enrollmentPin.value = if (enrolling) pin else null
    }

    private suspend fun attach(session: dev.p2pkit.core.P2pSession): SessionRpcLink {
        val link = SessionRpcLink(session, scope, budget, notificationBudget, clock)
        try {
            link.start(onMessage = { engine.onMessage(link, it) }, onClosed = { engine.detach(link) })
            engine.attach(link)
            return link
        } catch (failure: Exception) {
            try { link.close() } catch (_: Exception) { /* Kit retains cleanup; preserve the original cause. */ }
            throw failure
        }
    }

    @Throws(Exception::class)
    public suspend fun <Q, R, E> call(
        procedure: RpcProcedure<Q, R, E>, request: Q,
        timeout: Duration = 10.seconds, retry: RpcRetry = RpcRetry.RecoverOnly(),
    ): RpcReply<R, E> = engine.call(procedure, request, timeout, retry)

    /** Same execution/retry semantics as call(), with correlation metadata on successful/business replies. */
    @Throws(Exception::class)
    public suspend fun <Q, R, E> callWithDetails(
        procedure: RpcProcedure<Q, R, E>, request: Q,
        timeout: Duration = 10.seconds, retry: RpcRetry = RpcRetry.RecoverOnly(),
    ): RpcCallDetails<R, E> = engine.callWithDetails(procedure, request, timeout, retry)

    /** Typed local collection only; does not send a subscription or promise remote receipt/replay. */
    public fun <T> notifications(notification: RpcNotification<T>): Flow<T> = notifications.flow(notification)

    /** Closes the selected connection and outstanding calls, retaining discovery and durable trust. No replay. */
    @Throws(Exception::class)
    public suspend fun disconnect(): Unit = connectionLock.withLock {
        try { engine.close() } finally { selected.value = null; enrollmentPin.value = null }
    }

    @Throws(Exception::class)
    public suspend fun close() {
        closed.value = true
        withContext(NonCancellable) {
            closeLock.withLock {
                var failed = false
                try {
                    try { engine.close(permanent = true) } catch (_: Exception) { failed = true }
                    notifications.close()
                    try { kit.stop() } catch (_: Exception) { failed = true }
                } finally { scope.cancel(); enrollmentPin.value = null; selected.value = null }
                if (failed) throw RpcFailure(RpcFailureKind.Closed, RpcFailurePhase.Admission)
            }
        }
    }

    public companion object {
        @Throws(Exception::class)
        public suspend fun create(
            platform: RpcPlatform, applicationScope: CoroutineScope, configure: RpcClientConfiguration.() -> Unit,
        ): RpcClient {
            val configuration = RpcClientConfiguration().apply(configure)
            val appId = requireNotNull(configuration.appId) { "RPC appId is required" }
            val lan = requireNotNull(configuration.lan) { "Explicit organization LAN policy is required" }
            val trust = RpcTrust.load(appId, RpcTrustPurpose.SelectedHosts,
                requireNotNull(configuration.trustStore) { "A local durable trust store is required" })
            val selected = MutableStateFlow<PeerFingerprint?>(null)
            val enrollment = MutableStateFlow<PeerFingerprint?>(null)
            val budget = PayloadBudget(configuration.limits.payloadBytes)
            val profile = P2pSessionProfile(admission = { identity ->
                val pin = identity.fingerprint
                if (pin != null && trust.healthy && pin == selected.value &&
                    (trust.isTrusted(pin) || pin == enrollment.value)) PeerAdmission.Trusted
                else PeerAdmission.Rejected
            }, payloadBudget = budget, maxTrustedSessions = 1, maxEnrollmentSessions = 0)
            val kit = rpcBoundary {
                platform.createKit(RpcKitSettings(appId, lan, LanRole.DialOnly, profile,
                    configuration.transportReconnect))
            }
            val scope = CoroutineScope(
                applicationScope.coroutineContext + SupervisorJob(applicationScope.coroutineContext[Job]),
            )
            val clock = MonotonicRpcClock()
            val engine = RpcClientEngine(scope, budget, clock, configuration.limits.callsPerClient)
            return RpcClient(kit, trust, scope, lan, selected, enrollment, budget, clock, engine,
                configuration.notifications.toMap())
        }
    }
}
