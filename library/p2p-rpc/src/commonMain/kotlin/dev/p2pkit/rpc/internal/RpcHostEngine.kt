package dev.p2pkit.rpc.internal

import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.core.PayloadLease
import dev.p2pkit.core.PeerAdmission
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerIdentity
import dev.p2pkit.core.security.payloadSha256
import dev.p2pkit.rpc.RpcCallContext
import dev.p2pkit.rpc.RpcDiagnostics
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcFailurePhase
import dev.p2pkit.rpc.RpcLimits
import dev.p2pkit.rpc.RpcRequestId
import dev.p2pkit.rpc.RpcRetrySafety
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.withTimeoutOrNull

/** In-memory execution/result ownership belongs to this host, never an individual connection. */
internal class RpcHostEngine(
    private val scope: CoroutineScope,
    private val procedures: Map<String, RegisteredProcedure>,
    private val limits: RpcLimits,
    val budget: PayloadBudget,
    private val clock: RpcClock,
    private val trusted: (PeerFingerprint) -> Boolean,
    val incarnation: String = newWireId(),
) {
    private data class Key(val peer: PeerFingerprint, val id: String)
    private enum class Stage { Queued, Running, Finalizing, Complete }
    private class Record(
        val key: Key,
        val identity: PeerIdentity,
        val procedure: RegisteredProcedure,
        val digest: ByteArray,
        val request: OwnedBytes,
        val decodeAllowance: PayloadLease,
        val resultAllowance: PayloadLease,
        val deadline: Long,
        var stage: Stage,
    ) {
        val executionBegan = MutableStateFlow(false)
        val cancelRequested = MutableStateFlow(false)
        val job = MutableStateFlow<Job?>(null)
        var completedAt: Long = 0
        var result: WireMessage? = null
    }

    private val lock = Mutex()
    private val records = mutableMapOf<Key, Record>()
    private val recordsPerPeer = mutableMapOf<PeerFingerprint, Int>()
    private val activePerPeer = mutableMapOf<PeerFingerprint, Int>()
    private val pending = ArrayDeque<Record>()
    private val completed = LinkedHashMap<Key, Record>()
    private val cachedBodies = LinkedHashMap<Key, Record>()
    private var cachedBytes = 0L
    private var running = 0
    private var closed = false
    private val links = mutableMapOf<PeerFingerprint, RpcLink>()
    private val ready = mutableSetOf<RpcLink>()
    private val stats = MutableStateFlow(RpcDiagnostics())
    val diagnostics: StateFlow<RpcDiagnostics> = stats.asStateFlow()
    var onPairRequest: (suspend (RpcLink, WireMessage) -> Unit)? = null

    private val sweeper = scope.launch {
        while (isActive) {
            delay(250)
            sweep()
        }
    }

    fun notificationDropped() {
        stats.update { it.copy(droppedNotifications = it.droppedNotifications + 1) }
    }

    suspend fun attach(link: RpcLink) {
        val fingerprint = checkNotNull(link.identity.fingerprint)
        val (accepted, old) = lock.withLock {
            if (closed) false to null else {
                val previous = links.put(fingerprint, link)
                if (previous != null && previous !== link) ready.remove(previous)
                true to previous
            }
        }
        if (!accepted) {
            link.close()
            throw RpcFailure(RpcFailureKind.Closed, RpcFailurePhase.Admission)
        }
        if (old != null && old !== link) {
            try { old.close() } catch (failure: Exception) {
                detach(link)
                link.close()
                throw failure
            }
        }
    }

    suspend fun detach(link: RpcLink) = lock.withLock {
        val pin = link.identity.fingerprint
        if (links[pin] === link) links.remove(pin)
        ready.remove(link)
    }

    suspend fun onMessage(link: RpcLink, message: WireMessage) {
        val pin = checkNotNull(link.identity.fingerprint)
        if (message.kind == WireKind.Hello) {
            val permitted = lock.withLock {
                val permitted = !closed && links[pin] === link &&
                    (link.admission == PeerAdmission.EnrollmentOnly || trusted(pin))
                // Admission and readiness are one transaction: detach/replacement must not be
                // followed by an old HELLO resurrecting an unreachable ready-link reference.
                if (permitted) ready.add(link)
                permitted
            }
            if (!permitted) { link.close(); return }
            send(link, WireMessage(WireKind.Ready, message.id, incarnation,
                code = if (link.admission == PeerAdmission.Trusted) 1 else 2))
            return
        }
        if (!lock.withLock { link in ready && links[pin] === link && !closed }) protocolFailure(link)
        if (message.incarnation != incarnation) {
            if (message.name.isNotEmpty()) refuse(link, message, WireFailure.HostRestarted) else link.close()
            return
        }
        if (message.kind == WireKind.PairRequest) {
            onPairRequest?.invoke(link, message) ?: protocolFailure(link)
            return
        }
        if (link.admission != PeerAdmission.Trusted || !trusted(pin)) {
            link.close()
            return
        }
        when (message.kind) {
            WireKind.Invoke -> invoke(link, message, pin)
            WireKind.Status, WireKind.Cancel, WireKind.Receipt -> control(link, message, pin)
            else -> protocolFailure(link)
        }
    }

    private suspend fun allowed(
        procedure: RegisteredProcedure, link: RpcLink, remainingMillis: Long = AUTHORIZATION_TIMEOUT_MILLIS,
    ): Boolean {
        val pin = link.identity.fingerprint ?: return false
        if (!trusted(pin) || remainingMillis <= 0) return false
        return try {
            // Also applies during NonCancellable result finalization: an otherwise cooperative
            // authorizer must not hold execution slots/leases forever after the handler exits.
            withTimeoutOrNull(minOf(remainingMillis, AUTHORIZATION_TIMEOUT_MILLIS)) {
                procedure.authorize(link.identity) && trusted(pin)
            } == true
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (_: Exception) { false }
    }

    private suspend fun invoke(link: RpcLink, message: WireMessage, pin: PeerFingerprint) {
        val firstDeadline = clock.now() + message.budgetMillis
        val body = checkNotNull(message.body)
        val digest = payloadSha256(body.bytes)
        // Check ID reuse before schema/size/refusal paths. An altered duplicate must never be
        // described as a definitely-not-executed new request when the original may be running.
        val original = lock.withLock {
            expireLocked()
            records[Key(pin, message.id)]
        }
        if (original != null && !matches(original, message, digest)) protocolFailure(link)
        val procedure = procedures[message.key]
        if (procedure == null) { refuse(link, message, WireFailure.UnknownProcedure); return }
        if (!allowed(procedure, link, firstDeadline - clock.now())) {
            val existing = original != null || lock.withLock { Key(pin, message.id) in records }
            refuse(link, message, when {
                existing -> WireFailure.AccessRevoked
                clock.now() >= firstDeadline -> WireFailure.DeadlineBeforeStart
                else -> WireFailure.Unauthorized
            })
            return
        }
        var altered = false
        val retained = lock.withLock {
            records[Key(pin, message.id)]?.let { record ->
                if (!matches(record, message, digest)) {
                    altered = true
                    return@let null
                }
                stats.update { it.copy(duplicateRequests = it.duplicateRequests + 1) }
                snapshotResult(record)
            }
        }
        if (altered) protocolFailure(link)
        if (retained != null) {
            sendOwned(link, retained)
            return
        }
        if (message.code == 1 && procedure.retrySafety != RpcRetrySafety.Idempotent) {
            refuse(link, message, WireFailure.InvalidPayload)
            return
        }
        if (clock.now() >= firstDeadline) { refuse(link, message, WireFailure.DeadlineBeforeStart); return }
        if (body.size > procedure.requestLimit) { refuse(link, message, WireFailure.InvalidPayload); return }
        var duplicate: WireMessage? = null
        var rejected = false
        var startImmediately: Record? = null
        var mismatch = false
        try {
            withContext(NonCancellable) {
                lock.withLock {
                    expireLocked()
                    val key = Key(pin, message.id)
                    val existing = records[key]
                    if (existing != null) {
                        mismatch = !matches(existing, message, digest)
                        if (!mismatch) {
                            duplicate = snapshotResult(existing)
                            stats.update { it.copy(duplicateRequests = it.duplicateRequests + 1) }
                        }
                        return@withLock
                    }
                    if (closed || !trusted(pin) || (activePerPeer[pin] ?: 0) >= limits.callsPerClient ||
                        records.size >= limits.totalRecords || (recordsPerPeer[pin] ?: 0) >= limits.recordsPerClient ||
                        (running >= limits.runningCalls && pending.size >= limits.queuedCalls)
                    ) { rejected = true; return@withLock }
                    val resultBytes = RpcBodyCodec.encodingAllowance(procedure.resultLimit)
                    val decodeBytes = 4L * body.size + 32_768
                    reclaimResultsFor(resultBytes + decodeBytes)
                    val resultAllowance = budget.tryReserve(resultBytes)
                    val decodeAllowance = budget.tryReserve(decodeBytes)
                    if (resultAllowance == null || decodeAllowance == null) {
                        resultAllowance?.release()
                        decodeAllowance?.release()
                        rejected = true
                        return@withLock
                    }
                    val stage = if (running < limits.runningCalls) Stage.Running else Stage.Queued
                    val record = Record(key, link.identity, procedure, digest, body.retain(), decodeAllowance,
                        resultAllowance, firstDeadline, stage)
                    records[key] = record // Dedup record precedes every possible handler start.
                    recordsPerPeer[pin] = (recordsPerPeer[pin] ?: 0) + 1
                    activePerPeer[pin] = (activePerPeer[pin] ?: 0) + 1
                    if (stage == Stage.Running) running++ else pending.addLast(record)
                    stats.update { it.copy(acceptedCalls = it.acceptedCalls + 1) }
                    publishLocked()
                    if (stage == Stage.Running) startImmediately = record
                }
                // No gap can leave an admitted record without an owner, even if this connection closes.
                // A queued record promoted by another completion already has THAT completion as owner.
                startImmediately?.let(::launchRecord)
            }
            if (mismatch) protocolFailure(link)
            duplicate?.let { send(link, it) }
            if (rejected) refuse(link, message, WireFailure.Overloaded)
        } finally {
            // Also covers cancellation while leaving the non-cancellable admission transaction.
            duplicate?.release()
        }
    }

    private suspend fun control(link: RpcLink, message: WireMessage, pin: PeerFingerprint) {
        val procedure = procedures[message.key]
        if (procedure == null || !allowed(procedure, link)) {
            refuse(link, message, WireFailure.AccessRevoked)
            return
        }
        var mismatch = false
        var response: WireMessage? = null
        var cancel: Record? = null
        lock.withLock {
            expireLocked()
            val record = records[Key(pin, message.id)]
            if (record == null) {
                if (message.kind == WireKind.Status) response = failure(message, WireFailure.UnknownOutcome)
                return@withLock
            }
            if (!matches(record, message, checkNotNull(message.body).bytes)) {
                mismatch = true
                return@withLock
            }
            when (message.kind) {
                WireKind.Receipt -> if (record.stage == Stage.Complete) dropResultBody(record)
                WireKind.Cancel -> if (record.stage != Stage.Complete) {
                    record.cancelRequested.value = true
                    cancel = record
                }
                WireKind.Status -> response = snapshotResult(record)
                else -> Unit
            }
        }
        if (mismatch) protocolFailure(link)
        cancel?.let {
            completeQueued(it, WireFailure.CancelledBeforeStart)
            // A queued record may have become Running since the control acquired the lock.
            it.job.value?.cancel()
        }
        response?.let { sendOwned(link, it) }
    }

    private fun matches(record: Record, message: WireMessage, digest: ByteArray): Boolean =
        record.procedure.key == message.key && constantTimeSame(record.digest, digest)

    private fun snapshotResult(record: Record): WireMessage = when (record.stage) {
        Stage.Queued, Stage.Running, Stage.Finalizing -> response(record, WireKind.Running)
        Stage.Complete -> record.result?.retained() ?: response(record, WireKind.Failure,
            code = WireFailure.ResultUnavailable.code)
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    private fun launchRecord(record: Record) {
        val job = scope.launch(start = CoroutineStart.ATOMIC) {
            var terminal: WireMessage? = null
            var encoded: EncodedReply? = null
            try {
                currentCoroutineContext().ensureActive()
                if (record.cancelRequested.value) throw CancellationException("RPC cancellation requested")
                val remaining = record.deadline - clock.now()
                if (remaining <= 0) {
                    terminal = response(record, WireKind.Failure, code = WireFailure.DeadlineBeforeStart.code)
                } else {
                    val result = withTimeout(remaining) {
                        record.procedure.execute(
                            RpcCallContext(record.identity, RpcRequestId(record.key.id), remaining), record.request,
                            budget, record.decodeAllowance, record.resultAllowance
                        ) {
                            if (!trusted(record.key.peer) || record.cancelRequested.value) {
                                throw CancellationException("RPC admission revoked or cancelled")
                            }
                            record.executionBegan.value = true
                        }.also { encoded = it }
                    }
                    terminal = response(record, result.kind, body = result.body)
                }
            } catch (_: TimeoutCancellationException) {
                terminal = response(record, WireKind.Failure, code = if (record.executionBegan.value) {
                    WireFailure.Deadline.code
                } else WireFailure.DeadlineBeforeStart.code)
            } catch (_: CancellationException) {
                terminal = response(record, WireKind.Failure, code = if (record.executionBegan.value) {
                    WireFailure.Cancelled.code
                } else WireFailure.CancelledBeforeStart.code)
            } catch (_: Exception) {
                terminal = response(record, WireKind.Failure, code = if (record.executionBegan.value) {
                    WireFailure.HandlerFailed.code
                } else WireFailure.InvalidPayload.code)
            } finally {
                // Prompt cancellation may discard a successfully encoded return value at withTimeout's boundary.
                encoded?.takeIf { terminal?.body !== it.body }?.body?.release()
                // Non-cooperative handlers keep their slot until this finally REALLY runs.
                withContext(NonCancellable) {
                    finish(
                        record, terminal ?: response(record, WireKind.Failure, code = WireFailure.HandlerFailed.code),
                    )
                }
            }
        }
        record.job.value = job
        if (record.cancelRequested.value) job.cancel()
    }

    private suspend fun finish(record: Record, terminal: WireMessage, authorizeResult: Boolean = true) {
        var next: Record? = null
        var target: RpcLink? = null
        // Returning cached or new results requires current application authorization, not only transport trust.
        val candidate = lock.withLock {
            links[record.key.peer]?.takeIf { it in ready && it.admission == PeerAdmission.Trusted }
        }
        val authorized = candidate != null && try {
            if (authorizeResult) allowed(record.procedure, candidate) else trusted(record.key.peer)
        } catch (_: CancellationException) { false }
        lock.withLock {
            if (record.stage == Stage.Complete) { terminal.release(); return }
            if (record.stage == Stage.Running) running--
            if (record.stage == Stage.Queued) pending.remove(record)
            activePerPeer.computeCount(record.key.peer, -1)
            record.stage = Stage.Complete
            record.completedAt = clock.now()
            record.request.release()
            record.decodeAllowance.release()
            if (terminal.body == null) record.resultAllowance.release()
            if (!closed) {
                record.result = terminal.retained()
                completed[record.key] = record
                if (terminal.body != null) {
                    cachedBodies[record.key] = record
                    cachedBytes += terminal.body.size
                    trimCache()
                }
                if (authorized && trusted(record.key.peer)) target = candidate
            } else {
                records.remove(record.key)
                recordsPerPeer.computeCount(record.key.peer, -1)
            }
            if (!closed && running < limits.runningCalls && pending.isNotEmpty()) {
                next = pending.removeFirst().also { it.stage = Stage.Running; running++ }
            }
            stats.update { it.copy(completedCalls = it.completedCalls + 1) }
            publishLocked()
        }
        try {
            next?.let(::launchRecord)
            target?.let { send(it, terminal) }
        } finally { terminal.release() }
    }

    private suspend fun completeQueued(record: Record, reason: WireFailure) {
        val claimed = lock.withLock {
            if (record.stage != Stage.Queued) false else {
                pending.remove(record)
                // Do not counterfeit a running-handler slot while removing cancelled queued work.
                record.stage = Stage.Finalizing
                true
            }
        }
        if (claimed) withContext(NonCancellable) {
            finish(record, response(record, WireKind.Failure, code = reason.code), authorizeResult = false)
        }
    }

    suspend fun revoke(pin: PeerFingerprint) {
        val affected = lock.withLock {
            records.values.filter { it.key.peer == pin && it.stage != Stage.Complete }.also { records ->
                records.forEach { it.cancelRequested.value = true }
            }
        }
        for (record in affected) {
            completeQueued(record, WireFailure.CancelledBeforeStart)
            record.job.value?.cancel()
        }
        lock.withLock { links[pin] }?.close()
    }

    suspend fun trustedLink(pin: PeerFingerprint): RpcLink? = lock.withLock {
        links[pin]?.takeIf { it in ready && it.admission == PeerAdmission.Trusted && trusted(pin) }
    }

    suspend fun sweep() {
        val expired = lock.withLock {
            expireLocked()
            publishLocked()
            pending.filter { clock.now() >= it.deadline }
        }
        expired.forEach { completeQueued(it, WireFailure.DeadlineBeforeStart) }
    }

    private fun expireLocked() {
        while (cachedBodies.isNotEmpty()) {
            val record = cachedBodies.values.first()
            if (clock.now() - record.completedAt < 30_000) break
            dropResultBody(record)
        }
        while (completed.isNotEmpty()) {
            val record = completed.values.first()
            if (clock.now() - record.completedAt < 60_000) break
            dropResultBody(record)
            record.result?.release()
            record.result = null
            completed.remove(record.key)
            records.remove(record.key)
            recordsPerPeer.computeCount(record.key.peer, -1)
        }
    }

    private fun trimCache() {
        while (cachedBytes > limits.resultCacheBytes && cachedBodies.isNotEmpty()) {
            dropResultBody(cachedBodies.values.first())
        }
    }

    private fun reclaimResultsFor(required: Long) {
        while (budget.capacityBytes - budget.retainedBytes.value < required && cachedBodies.isNotEmpty()) {
            dropResultBody(cachedBodies.values.first())
        }
    }

    private fun dropResultBody(record: Record) {
        val cached = record.result ?: return
        if (cached.body == null) return
        cachedBytes -= cached.body.size
        cachedBodies.remove(record.key)
        record.result = null // Tombstone remains, NEVER permits re-execution.
        cached.release()
    }

    private fun publishLocked() {
        stats.update {
            it.copy(
                runningCalls = running, queuedCalls = pending.size,
                retainedRecords = records.size, retainedPayloadBytes = budget.retainedBytes.value,
            )
        }
    }

    private fun response(record: Record, kind: WireKind, code: Int = 0, body: OwnedBytes? = null): WireMessage =
        WireMessage(
            kind, record.key.id, incarnation, record.procedure.name, record.procedure.version, code = code, body = body,
        )

    private fun failure(message: WireMessage, reason: WireFailure): WireMessage = WireMessage(
        WireKind.Failure, message.id, incarnation, message.name, message.version,
        budgetMillis = if (reason == WireFailure.Overloaded) 100 else 0, code = reason.code
    )

    private suspend fun refuse(link: RpcLink, message: WireMessage, reason: WireFailure) {
        stats.update { it.copy(refusedCalls = it.refusedCalls + 1) }
        send(link, failure(message, reason))
    }

    private suspend fun send(link: RpcLink, message: WireMessage) {
        try {
            if (link.offer(message, clock.now() + 10_000) != null) return
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (_: Exception) {
            // Result retention survives a failed connection; never launch an unowned retry.
        }
        stats.update { it.copy(connectionFailures = it.connectionFailures + 1) }
        try { link.close() } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (_: Exception) {
            // Explicit host/kit close reobserves retained transport cleanup. Do not kill the sweeper.
        }
    }

    private suspend fun sendOwned(link: RpcLink, message: WireMessage) {
        try { send(link, message) } finally { message.release() }
    }

    private suspend fun protocolFailure(link: RpcLink): Nothing {
        stats.update { it.copy(protocolFailures = it.protocolFailures + 1) }
        link.close()
        throw RpcFailure(RpcFailureKind.Protocol, RpcFailurePhase.Decoding)
    }

    suspend fun close() {
        sweeper.cancel()
        val snapshot = lock.withLock {
            closed = true
            records.values.forEach { it.cancelRequested.value = true }
            links.values.toList() to records.values.toList()
        }
        var cleanupFailed = false
        // Always seal/cancel work even when one transport reports an incomplete native teardown.
        for (record in snapshot.second) {
            try {
                completeQueued(record, WireFailure.CancelledBeforeStart)
                record.job.value?.cancel()
            } catch (_: Exception) { cleanupFailed = true }
        }
        for (batch in snapshot.first.chunked(16)) {
            val released = coroutineScope {
                batch.map { link -> async { runCatching { link.close() }.isSuccess } }.awaitAll()
            }
            if (released.any { !it }) cleanupFailed = true
        }
        lock.withLock {
            completed.values.forEach {
                it.result?.release()
                it.result = null
                records.remove(it.key)
                recordsPerPeer.computeCount(it.key.peer, -1)
            }
            completed.clear()
            cachedBodies.clear()
            cachedBytes = 0
            // Active records retain their leases until their actual jobs terminate.
            ready.clear()
            links.clear()
            publishLocked()
        }
        if (cleanupFailed) throw RpcFailure(RpcFailureKind.Closed, RpcFailurePhase.Admission)
    }

    private companion object {
        const val AUTHORIZATION_TIMEOUT_MILLIS: Long = 5_000
    }
}

private fun MutableMap<PeerFingerprint, Int>.computeCount(key: PeerFingerprint, delta: Int) {
    val next = (this[key] ?: 0) + delta
    check(next >= 0)
    if (next == 0) remove(key) else this[key] = next
}
