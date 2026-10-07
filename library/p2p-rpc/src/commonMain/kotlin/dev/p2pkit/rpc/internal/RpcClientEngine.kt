package dev.p2pkit.rpc.internal

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.core.PeerAdmission
import dev.p2pkit.core.SessionFailureKind
import dev.p2pkit.core.security.payloadSha256
import dev.p2pkit.rpc.RpcCallDetails
import dev.p2pkit.rpc.RpcConnectionState
import dev.p2pkit.rpc.RpcDiagnostics
import dev.p2pkit.rpc.RpcExecutionEvidence
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcFailurePhase
import dev.p2pkit.rpc.RpcProcedure
import dev.p2pkit.rpc.RpcReply
import dev.p2pkit.rpc.RpcRequestId
import dev.p2pkit.rpc.RpcRetry
import dev.p2pkit.rpc.RpcRetryAdvice
import dev.p2pkit.rpc.RpcRetrySafety
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.withTimeoutOrNull
import kotlin.random.Random
import kotlin.time.Duration
import kotlin.time.Duration.Companion.milliseconds
import kotlin.time.Duration.Companion.seconds

internal data class RpcReady(val incarnation: String, val admission: PeerAdmission, val generation: Long)

internal class RpcClientEngine(
    private val scope: CoroutineScope,
    private val budget: PayloadBudget,
    private val clock: RpcClock,
    outstandingLimit: Int = 8,
    private val jitter: (Long) -> Long = { Random.Default.nextLong(it + 1) },
) {
    private data class Negotiation(val id: String, val generation: Long)
    private class Attachment(val link: RpcLink) {
        val active = MutableStateFlow(true)
        val ready = MutableStateFlow<RpcReady?>(null)
        // These two fields are guarded by the engine lock.
        var negotiation: Negotiation? = null
        var monitor: Job? = null
    }
    private class Pending(
        val id: RpcRequestId,
        val name: String,
        val version: Int,
        val incarnation: String,
        val owner: Attachment,
    ) {
        val evidence = MutableStateFlow(RpcExecutionEvidence.NotSent)
        val replies = Channel<WireMessage>(4, onUndeliveredElement = { it.release() })
        var ticket: SendTicket? = null
    }

    private val slots = Semaphore(outstandingLimit)
    private val lock = Mutex()
    private val pending = mutableMapOf<String, Pending>()
    private var attachment: Attachment? = null
    private var terminated = false
    private val readiness = MutableStateFlow<RpcReady?>(null)
    val ready: StateFlow<RpcReady?> = readiness.asStateFlow()
    private val connection = MutableStateFlow(RpcConnectionState.Disconnected)
    val state: StateFlow<RpcConnectionState> = connection.asStateFlow()
    private val stats = MutableStateFlow(RpcDiagnostics())
    val diagnostics: StateFlow<RpcDiagnostics> = stats.asStateFlow()
    private val notificationCallback = MutableStateFlow<(suspend (WireMessage) -> Unit)?>(null)
    private val pairingCallback = MutableStateFlow<(suspend (WireMessage) -> Unit)?>(null)
    var onNotification: (suspend (WireMessage) -> Unit)?
        get() = notificationCallback.value
        set(value) { notificationCallback.value = value }
    var onPairMessage: (suspend (WireMessage) -> Unit)?
        get() = pairingCallback.value
        set(value) { pairingCallback.value = value }

    fun notificationDropped() {
        stats.update { it.copy(droppedNotifications = it.droppedNotifications + 1) }
    }

    suspend fun attach(current: RpcLink) {
        val owner = Attachment(current)
        val monitor = lock.withLock {
            check(attachment == null) { "Close the selected host connection before replacing it" }
            if (terminated || !scope.isActive) throw RpcFailure(RpcFailureKind.Closed, RpcFailurePhase.Negotiation)
            attachment = owner
            readiness.value = null
            connection.value = RpcConnectionState.Connecting
            scope.launch(start = CoroutineStart.LAZY) {
                try { observe(owner) } catch (cancelled: CancellationException) {
                    throw cancelled
                } catch (_: Exception) {
                    stats.update { it.copy(connectionFailures = it.connectionFailures + 1) }
                    lock.withLock {
                        if (attachment === owner) detachLocked(owner, RpcConnectionState.Failed)
                    }
                    try { current.close() } catch (_: Exception) { /* Kit retains transport cleanup. */ }
                }
            }.also { owner.monitor = it }
        }
        monitor.start()
    }

    private suspend fun observe(owner: Attachment) {
        val current = owner.link
        combine(current.transportState, current.generation) { state, info -> state to info.generation }
            .collectLatest { (transport, generation) ->
                val negotiation = lock.withLock {
                    if (attachment !== owner) return@collectLatest
                    owner.ready.value = null
                    readiness.value = null
                    owner.negotiation = if (transport == ConnectionState.Connected) {
                        Negotiation(newWireId(), generation)
                    } else null
                    connection.value = when (transport) {
                        ConnectionState.Connected -> {
                            RpcConnectionState.Negotiating
                        }
                        ConnectionState.Reconnecting -> RpcConnectionState.Reconnecting
                        ConnectionState.Closed, ConnectionState.Closing -> RpcConnectionState.Disconnected
                        ConnectionState.Failed -> RpcConnectionState.Failed
                        else -> RpcConnectionState.Connecting
                    }
                    owner.negotiation
                }
                if (negotiation != null) {
                    val negotiated = withTimeoutOrNull(5_000) {
                        while (isActive && owner.active.value && owner.ready.value?.generation != generation) {
                            current.offer(WireMessage(WireKind.Hello, negotiation.id), clock.now() + 1_000)
                            withTimeoutOrNull(250) { owner.ready.first { it?.generation == generation } }
                        }
                        owner.ready.value?.generation == generation
                    } ?: false
                    if (!negotiated && owner.active.value) current.close()
                }
            }
    }

    private fun detachLocked(owner: Attachment, state: RpcConnectionState) {
        attachment = null
        owner.active.value = false
        owner.ready.value = null
        owner.negotiation = null
        readiness.value = null
        connection.value = state
        // Closing a previous attachment must never cancel a newly selected host's calls/monitor.
        for (call in pending.values) {
            if (call.owner === owner) call.replies.close()
        }
    }

    suspend fun detach(current: RpcLink) {
        val monitor = lock.withLock {
            val owner = attachment?.takeIf { it.link === current } ?: return
            val state = if (current.failure.value != null) RpcConnectionState.Failed
            else RpcConnectionState.Disconnected
            detachLocked(owner, state)
            owner.monitor
        }
        monitor?.cancel()
    }

    suspend fun onMessage(current: RpcLink, message: WireMessage) {
        val owner = lock.withLock { attachment?.takeIf { it.link === current } } ?: return
        when (message.kind) {
            WireKind.Ready -> {
                val invalid = lock.withLock {
                    val query = owner.negotiation
                    if (attachment !== owner || query == null || query.id != message.id ||
                        query.generation != current.generation.value.generation ||
                        current.transportState.value != ConnectionState.Connected
                    ) return@withLock false // A delayed READY from an older generation cannot authorize this one.
                    val previous = owner.ready.value
                    if (previous != null && previous.incarnation != message.incarnation) return@withLock true
                    val ready = RpcReady(
                        message.incarnation,
                        if (message.code == 1) PeerAdmission.Trusted else PeerAdmission.EnrollmentOnly,
                        query.generation,
                    )
                    owner.ready.value = ready
                    readiness.value = ready
                    connection.value = if (message.code == 1) RpcConnectionState.Ready else RpcConnectionState.Pairing
                    false
                }
                if (invalid) protocolFailure(current)
            }
            WireKind.Notify -> {
                val ready = owner.ready.value ?: protocolFailure(current)
                if (ready.admission != PeerAdmission.Trusted || message.incarnation != ready.incarnation) {
                    protocolFailure(current)
                }
                onNotification?.invoke(message)
            }
            WireKind.PairPending, WireKind.PairApproved, WireKind.PairDenied -> {
                if (message.incarnation != owner.ready.value?.incarnation) protocolFailure(current)
                onPairMessage?.invoke(message)
            }
            WireKind.Success, WireKind.ApplicationError, WireKind.Failure, WireKind.Running -> {
                var invalid = false
                lock.withLock {
                    if (attachment !== owner) return@withLock
                    val call = pending[message.id] ?: return@withLock // Late or duplicate terminal response.
                    if (call.owner !== owner || message.name != call.name || message.version != call.version) {
                        invalid = true
                    } else {
                        val retained = message.retained()
                        if (call.replies.trySend(retained).isFailure) {
                            retained.release()
                            invalid = true
                        }
                    }
                }
                if (invalid) protocolFailure(current)
            }
            else -> protocolFailure(current)
        }
    }

    suspend fun awaitReady(timeout: Duration = 10.seconds): RpcReady {
        val owner = lock.withLock { attachment } ?: throw RpcFailure(
            RpcFailureKind.NotConnected, RpcFailurePhase.Negotiation,
        )
        return try {
            withTimeout(timeout.inWholeMilliseconds) {
                combine(owner.ready, owner.active, owner.link.transportState, owner.link.failure) {
                        ready, active, transport, failure ->
                    if (failure != null) throw RpcFailure(failure, RpcFailurePhase.Negotiation)
                    if (!active || transport in setOf(ConnectionState.Closed, ConnectionState.Failed)) {
                        throw RpcFailure(RpcFailureKind.NotConnected, RpcFailurePhase.Negotiation)
                    }
                    ready?.takeIf {
                        transport == ConnectionState.Connected &&
                            it.generation == owner.link.generation.value.generation
                    }
                }.first { it != null }!!
            }
        } catch (cancelled: TimeoutCancellationException) {
            if (!currentCoroutineContext().isActive) throw cancelled
            throw RpcFailure(RpcFailureKind.DeadlineExceeded, RpcFailurePhase.Negotiation)
        }
    }

    suspend fun <Q, R, E> call(
        procedure: RpcProcedure<Q, R, E>,
        request: Q,
        timeout: Duration,
        retry: RpcRetry,
    ): RpcReply<R, E> = callWithDetails(procedure, request, timeout, retry).reply

    suspend fun <Q, R, E> callWithDetails(
        procedure: RpcProcedure<Q, R, E>,
        request: Q,
        timeout: Duration,
        retry: RpcRetry,
    ): RpcCallDetails<R, E> {
        require(timeout >= 1.milliseconds && timeout <= 30.seconds)
        require(retry !is RpcRetry.Idempotent || procedure.retrySafety == RpcRetrySafety.Idempotent) {
            "Reinvocation requires both descriptor and caller idempotency opt-in"
        }
        if (!slots.tryAcquire()) {
            stats.update { it.copy(refusedCalls = it.refusedCalls + 1) }
            throw RpcFailure(RpcFailureKind.Overloaded, RpcFailurePhase.Admission)
        }
        val started = clock.now()
        val deadline = started + timeout.inWholeMilliseconds
        var call: Pending? = null
        var frozen: OwnedBytes? = null
        var digest: OwnedBytes? = null
        var completed = false
        try {
            return withTimeout(timeout.inWholeMilliseconds) {
                val (owner, initial) = lock.withLock {
                    val owner = attachment ?: throw RpcFailure(
                        RpcFailureKind.NotConnected, RpcFailurePhase.Admission)
                    val initial = owner.ready.value
                    if (initial == null || initial.admission != PeerAdmission.Trusted ||
                        owner.link.transportState.value != ConnectionState.Connected ||
                        owner.link.generation.value.generation != initial.generation
                    ) throw RpcFailure(RpcFailureKind.NotConnected, RpcFailurePhase.Admission)
                    owner to initial
                }
                val selected = owner.link
                val active = Pending(
                    RpcRequestId(newWireId()), procedure.name, procedure.version, initial.incarnation, owner,
                )
                call = active
                frozen = RpcBodyCodec.encode(procedure.request, request, procedure.requestLimitBytes, budget)
                digest = OwnedBytes.copy(payloadSha256(checkNotNull(frozen).bytes), budget)
                currentCoroutineContext().ensureActive()
                lock.withLock {
                    if (attachment !== owner) throw failure(active, RpcFailureKind.NotConnected)
                    pending[active.id.value] = active
                    stats.update {
                        it.copy(acceptedCalls = it.acceptedCalls + 1, runningCalls = pending.size,
                            retainedPayloadBytes = budget.retainedBytes.value)
                    }
                }
                var invoke = true
                var explicitReinvoke = false
                var retryAfter = 0L
                for (attempt in 1..retry.maxAttempts) {
                    if (attempt > 1) {
                        val cap = minOf(2_000L, 100L shl (attempt - 2))
                        delay(maxOf(retryAfter, jitter(cap)).coerceAtMost((deadline - clock.now()).coerceAtLeast(0)))
                    }
                    val connected = waitForSameHost(owner, initial, deadline, active)
                    if (connected.incarnation != initial.incarnation) {
                        throw failure(active, RpcFailureKind.HostRestarted)
                    }
                    val message = WireMessage(
                        if (invoke) WireKind.Invoke else WireKind.Status, active.id.value, initial.incarnation,
                        procedure.name, procedure.version,
                        budgetMillis = if (invoke) (deadline - clock.now()).coerceIn(1, 30_000).toInt() else 0,
                        attempt = attempt, code = if (explicitReinvoke && invoke) 1 else 0,
                        body = if (invoke) checkNotNull(frozen).retain() else checkNotNull(digest).retain()
                    )
                    val invoking = invoke
                    val previouslyAmbiguous = active.evidence.value == RpcExecutionEvidence.MayHaveExecuted
                    val ticket = try {
                        selected.offer(message, deadline, onStart = {
                            if (invoking) active.evidence.value = RpcExecutionEvidence.MayHaveExecuted
                        })
                    } finally { message.release() }
                    active.ticket = ticket
                    if (ticket == null) {
                        invoke = active.evidence.value != RpcExecutionEvidence.MayHaveExecuted
                        continue
                    }
                    val sendSucceeded = ticket.completion.await()
                    if (!sendSucceeded) {
                        invoke = active.evidence.value != RpcExecutionEvidence.MayHaveExecuted
                        continue
                    }
                    val remaining = (deadline - clock.now()).coerceAtLeast(1)
                    val waitMillis = if (attempt == retry.maxAttempts) remaining else remaining / 2
                    var received: WireMessage? = null
                    val outcome = try {
                        withTimeoutOrNull(waitMillis.coerceAtLeast(1)) {
                            receiveTerminal(active, deadline).also { received = it }
                        }
                    } catch (failure: Throwable) {
                        received?.release()
                        throw failure
                    }
                    if (outcome == null) { received?.release(); invoke = false; continue }
                    try {
                        if (outcome.incarnation != initial.incarnation) {
                            throw failure(active, RpcFailureKind.HostRestarted)
                        }
                        when (outcome.kind) {
                            WireKind.Success, WireKind.ApplicationError -> {
                                active.evidence.value = RpcExecutionEvidence.HandlerFinished
                                val body = outcome.body ?: throw failure(active, RpcFailureKind.InvalidPayload)
                                val reply: RpcReply<R, E> = if (outcome.kind == WireKind.Success) RpcReply.Success(
                                    RpcBodyCodec.decode(procedure.response, body, procedure.responseLimitBytes, budget)
                                ) else RpcReply.ApplicationError(
                                    RpcBodyCodec.decode(
                                        procedure.applicationError, body, procedure.errorLimitBytes, budget,
                                    )
                                )
                                completed = true
                                stats.update { it.copy(completedCalls = it.completedCalls + 1) }
                                sendControl(selected, active, checkNotNull(digest), WireKind.Receipt)
                                return@withTimeout RpcCallDetails(
                                    active.id, reply, (clock.now() - started).coerceAtLeast(0),
                                )
                            }
                            WireKind.Failure -> {
                                val reason = WireFailure.entries.first { it.code == outcome.code }
                                when (reason) {
                                    WireFailure.Overloaded -> {
                                        if (!invoking) throw failure(active, RpcFailureKind.UnknownOutcome)
                                        if (!previouslyAmbiguous) {
                                            active.evidence.value = RpcExecutionEvidence.RejectedBeforeExecution
                                        }
                                        invoke = !previouslyAmbiguous
                                        retryAfter = outcome.budgetMillis.toLong()
                                    }
                                    WireFailure.UnknownOutcome -> {
                                        if (retry is RpcRetry.Idempotent &&
                                            procedure.retrySafety == RpcRetrySafety.Idempotent
                                        ) {
                                            invoke = true
                                            explicitReinvoke = true
                                        } else throw failure(active, RpcFailureKind.UnknownOutcome,
                                            RpcRetryAdvice.ApplicationIdempotencyRequired)
                                    }
                                    else -> {
                                        if (invoking && !previouslyAmbiguous &&
                                            reason.evidence == RpcExecutionEvidence.RejectedBeforeExecution
                                        ) {
                                            active.evidence.value = reason.evidence
                                        }
                                        throw failure(active, reason.kind)
                                    }
                                }
                            }
                            else -> throw failure(active, RpcFailureKind.Protocol)
                        }
                    } finally { outcome.release() }
                }
                throw failure(active, when {
                    clock.now() >= deadline -> RpcFailureKind.DeadlineExceeded
                    active.evidence.value == RpcExecutionEvidence.RejectedBeforeExecution -> RpcFailureKind.Overloaded
                    active.evidence.value == RpcExecutionEvidence.NotSent -> RpcFailureKind.NotConnected
                    else -> RpcFailureKind.UnknownOutcome
                })
            }
        } catch (cancelled: TimeoutCancellationException) {
            if (!currentCoroutineContext().isActive) throw cancelled // caller's deadline remains cancellation
            throw call?.let { failure(it, RpcFailureKind.DeadlineExceeded) }
                ?: RpcFailure(RpcFailureKind.DeadlineExceeded, RpcFailurePhase.Encoding)
        } catch (caught: RpcFailure) {
            val active = call
            if (active != null && caught.requestId == null) throw RpcFailure(
                caught.kind, caught.phase, active.id, active.evidence.value, caught.retryAdvice,
            )
            throw caught
        } finally {
            withContext(NonCancellable) {
                call?.let { active ->
                    active.ticket?.cancelQueued()
                    lock.withLock {
                        pending.remove(active.id.value)
                        stats.update { it.copy(runningCalls = pending.size) }
                    }
                    if (!completed && active.evidence.value == RpcExecutionEvidence.MayHaveExecuted && digest != null) {
                        // Never leak a prior host's procedure/ID to a newly selected host.
                        sendControl(active.owner.link, active, checkNotNull(digest), WireKind.Cancel)
                    }
                    active.replies.cancel()
                }
                frozen?.release()
                digest?.release()
                stats.update { it.copy(retainedPayloadBytes = budget.retainedBytes.value) }
                slots.release()
            }
        }
    }

    private suspend fun receiveTerminal(call: Pending, deadline: Long): WireMessage {
        while (true) {
            val result = call.replies.receiveCatching().getOrNull()
                ?: throw failure(call, RpcFailureKind.UnknownOutcome)
            if (result.incarnation != call.incarnation || result.kind != WireKind.Running) return result
            result.release()
            if (clock.now() >= deadline) throw failure(call, RpcFailureKind.DeadlineExceeded)
        }
    }

    private suspend fun waitForSameHost(
        owner: Attachment, initial: RpcReady, deadline: Long, call: Pending,
    ): RpcReady {
        val current = owner.link
        if (!owner.active.value) throw failure(call, RpcFailureKind.NotConnected)
        current.failure.value?.let { throw failure(call, it) }
        when (current.generation.value.lastFailure?.kind) {
            SessionFailureKind.Authentication -> throw failure(call, RpcFailureKind.Authentication)
            SessionFailureKind.Authorization -> throw failure(call, RpcFailureKind.Unauthorized)
            SessionFailureKind.Protocol -> throw failure(call, RpcFailureKind.Protocol)
            else -> Unit
        }
        val terminalStates = setOf(ConnectionState.Closed, ConnectionState.Failed, ConnectionState.Closing)
        if (current.transportState.value in terminalStates) {
            throw failure(call, RpcFailureKind.UnknownOutcome)
        }
        val result = withTimeout((deadline - clock.now()).coerceAtLeast(1)) {
            combine(owner.ready, owner.active, current.transportState) { ready, active, transport ->
                if (!active || transport in terminalStates) {
                    throw failure(call, RpcFailureKind.NotConnected)
                }
                ready?.takeIf {
                    transport == ConnectionState.Connected && it.generation == current.generation.value.generation
                }
            }.first { it != null }
        }!!
        if (result.incarnation != initial.incarnation) throw failure(call, RpcFailureKind.HostRestarted)
        if (result.admission != PeerAdmission.Trusted) throw failure(call, RpcFailureKind.Unauthorized)
        return result
    }

    private suspend fun sendControl(current: RpcLink, call: Pending, digest: OwnedBytes, kind: WireKind) {
        val message = WireMessage(
            kind, call.id.value, call.incarnation, call.name, call.version, body = digest.retain(),
        )
        try {
            current.offer(message, clock.now() + 1_000)
        } catch (_: Exception) {
            // Best-effort controls cannot overwrite a completed reply or the caller's original failure.
            currentCoroutineContext().ensureActive()
        } finally { message.release() }
    }

    private fun failure(
        call: Pending, kind: RpcFailureKind, advice: RpcRetryAdvice = RpcRetryAdvice.Never,
    ): RpcFailure = RpcFailure(kind, RpcFailurePhase.AwaitingResponse, call.id, call.evidence.value, advice)

    private suspend fun protocolFailure(current: RpcLink): Nothing {
        stats.update { it.copy(protocolFailures = it.protocolFailures + 1) }
        current.close()
        throw RpcFailure(RpcFailureKind.Protocol, RpcFailurePhase.Decoding)
    }

    suspend fun close(permanent: Boolean = false) {
        withContext(NonCancellable) {
            val owner = lock.withLock {
                if (permanent) terminated = true
                attachment?.also { detachLocked(it, RpcConnectionState.Closed) }
                    ?: run { connection.value = RpcConnectionState.Closed; null }
            }
            owner?.monitor?.cancel()
            owner?.link?.close()
        }
    }
}
