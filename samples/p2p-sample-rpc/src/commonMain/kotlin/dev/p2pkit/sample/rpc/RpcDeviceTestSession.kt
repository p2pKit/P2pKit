package dev.p2pkit.sample.rpc

import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcCallContext
import dev.p2pkit.rpc.RpcClient
import dev.p2pkit.rpc.RpcConnectionState
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcHost
import dev.p2pkit.rpc.RpcHostConfiguration
import dev.p2pkit.rpc.RpcNotification
import dev.p2pkit.rpc.RpcNotifyResult
import dev.p2pkit.rpc.RpcProcedure
import dev.p2pkit.rpc.RpcReply
import dev.p2pkit.rpc.RpcRetry
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.json.Json
import kotlin.random.Random
import kotlin.time.Duration.Companion.milliseconds
import kotlin.time.TimeSource

/** Interactive connected-device exercises. Their actual peer count never stands in for a capacity cohort. */
@Serializable
public enum class RpcDeviceTestPhase(public val title: String) {
    Large("Large data"), Correctness("Correctness"), Reconnect("Disconnect / reconnect"),
    Steady("Steady · 30 minutes"), Deadlines("Cancellation / deadline"),
}

@Serializable
public data class RpcDeviceTestReport(
    public val runId: String,
    public val phase: RpcDeviceTestPhase,
    public val sourceSha: String,
    public val status: String,
    public val calls: Long,
    public val correctResponses: Long,
    public val elapsedMillis: Long,
    public val initializationMillis: Long,
    public val missedSchedules: Long,
    public val p95Micros: Long,
    public val p99Micros: Long,
    public val deliberateDisconnects: Int,
    public val expectedDeadlines: Int,
    public val callerCancellations: Int,
    public val failureCode: String?,
    public val measuredClientCount: Int = 1,
    public val latencyBucketMicros: Int = 1_000,
    public val latencySamples: Long = 0,
    public val scope: String = "INTERACTIVE_CONNECTED_DEVICE_RPC",
) {
    public val title: String get() = "${phase.title}: $status · $correctResponses responses · ${elapsedMillis / 1_000}s"
}

public data class RpcDeviceTestProgress(
    public val runId: String = "",
    public val title: String = "No test running",
    public val running: Boolean = false,
    public val calls: Long = 0,
    public val elapsedSeconds: Long = 0,
    public val plannedSeconds: Long = 0,
)

@Serializable
internal data class DeviceTestCommand(val runId: String, val sourceSha: String, val phase: RpcDeviceTestPhase)

@Serializable
internal data class DeviceTestDelay(val millis: Int, val body: String)

internal object DeviceTestContract {
    val start = RpcNotification("device-tests.start", 1, DeviceTestCommand.serializer(), limitBytes = 1_024)
    val cancel = RpcNotification("device-tests.cancel", 1, String.serializer(), limitBytes = 128)
    val acknowledgement = RpcProcedure("device-tests.ack", 1, DeviceTestCommand.serializer(),
        String.serializer(), String.serializer(), requestLimitBytes = 1_024, responseLimitBytes = 128)
    val report = RpcProcedure("device-tests.report", 1, RpcDeviceTestReport.serializer(),
        String.serializer(), String.serializer(), requestLimitBytes = 4_096, responseLimitBytes = 128)
    val delayed = RpcProcedure("device-tests.delayed", 1, DeviceTestDelay.serializer(),
        String.serializer(), String.serializer(), requestLimitBytes = 2_048, responseLimitBytes = 2_048)
}

/** Bounded results outlive a role. Platform screens persist the immutable JSON in their private app storage. */
public class RpcDeviceTestSession {
    private val records = MutableStateFlow<List<RpcDeviceTestReport>>(emptyList())
    public val reports: List<RpcDeviceTestReport> get() = records.value
    private val latest = MutableStateFlow(RpcDeviceTestProgress())
    public val progress: RpcDeviceTestProgress get() = latest.value
    public val changes = records.asStateFlow()
    public val progressChanges = latest.asStateFlow()
    private val runtime = MutableStateFlow<DeviceTestRuntime?>(null)

    public fun exportJson(): String = Json.encodeToString(reports)

    @Throws(Exception::class)
    public fun restoreJson(text: String) {
        require(text.length <= 512_000)
        val restored = Json.decodeFromString<List<RpcDeviceTestReport>>(text)
        require(restored.size <= 100 && restored.all(::validDeviceTestReport))
        require(restored.map { it.runId }.distinct().size == restored.size)
        check(records.value.isEmpty())
        records.value = restored
    }

    internal fun register(configuration: RpcHostConfiguration) {
        configuration.notification(DeviceTestContract.start)
        configuration.notification(DeviceTestContract.cancel)
        configuration.register(DeviceTestContract.acknowledgement, authorize = { it.fingerprint != null }) { c, command ->
            if (runtime.value?.acknowledge(c, command) == true) RpcReply.Success("Accepted")
            else RpcReply.ApplicationError("No matching test")
        }
        configuration.register(DeviceTestContract.report, authorize = { it.fingerprint != null }) { context, value ->
            if (runtime.value?.receive(context, value) == true) RpcReply.Success("Recorded")
            else RpcReply.ApplicationError("No matching active test")
        }
        configuration.register(DeviceTestContract.delayed, authorize = { it.fingerprint != null }) { _, value ->
            require(value.millis in 0..2_000 && value.body.length <= 1_024)
            delay(value.millis.toLong())
            RpcReply.Success(value.body)
        }
    }

    internal fun bind(scope: CoroutineScope, host: RpcHost?, client: RpcClient?): DeviceTestRuntime {
        return DeviceTestRuntime(scope, host, client, this).also { check(runtime.compareAndSet(null, it)) }
    }

    internal fun release(value: DeviceTestRuntime) { runtime.compareAndSet(value, null) }
    internal fun publish(value: RpcDeviceTestProgress) { latest.value = value }
    internal fun save(value: RpcDeviceTestReport) {
        records.update { previous ->
            if (previous.any { it.runId == value.runId }) previous
            else (previous + value).takeLast(100)
        }
    }
}

internal class DeviceTestRuntime(
    private val scope: CoroutineScope,
    private val host: RpcHost?,
    private val client: RpcClient?,
    private val session: RpcDeviceTestSession,
) {
    private val lock = Mutex()
    private val active = MutableStateFlow<Job?>(null)
    private var pending: Pair<PeerFingerprint, DeviceTestCommand>? = null
    private var remoteResult: CompletableDeferred<RpcDeviceTestReport>? = null
    private var listener: Job? = null
    private var cancellationListener: Job? = null
    private val remoteEnabled = MutableStateFlow(false)
    private val closed = MutableStateFlow(false)
    private var acknowledgement: CompletableDeferred<Unit>? = null

    init {
        if (client != null) {
            listener = scope.launch {
                client.notifications(DeviceTestContract.start).collect { command ->
                    if (!validDeviceTestCommand(command) || command.sourceSha != RpcPhoneLab.compiledSource) {
                        return@collect
                    }
                    val job = scope.launch(start = CoroutineStart.LAZY) {
                        try {
                            val ack = client.call(DeviceTestContract.acknowledgement, command,
                                timeout = 5_000.milliseconds, retry = RpcRetry.RecoverOnly(1))
                            check(ack is RpcReply.Success)
                            execute(command)
                        } catch (cancelled: CancellationException) {
                            throw cancelled
                        } catch (_: Exception) {
                            session.save(emptyDeviceTestReport(command, "Failed", "StartAcknowledgementFailed"))
                        } finally {
                            active.compareAndSet(currentCoroutineContext()[Job], null)
                        }
                    }
                    if (remoteEnabled.value && !closed.value && session.reports.none { it.runId == command.runId } &&
                        client.state.value == RpcConnectionState.Ready && active.compareAndSet(null, job)
                    ) job.start() else job.cancel()
                }
            }
            cancellationListener = scope.launch {
                client.notifications(DeviceTestContract.cancel).collect { runId ->
                    if (session.progress.runId == runId) cancel()
                }
            }
        }
    }

    fun enableRemote(enabled: Boolean) { remoteEnabled.value = enabled && !closed.value }
    fun cancel() { active.value?.cancel() }

    suspend fun acknowledge(context: RpcCallContext, command: DeviceTestCommand): Boolean = lock.withLock {
        val expected = pending ?: return@withLock false
        context.peer.fingerprint == expected.first && command == expected.second &&
            acknowledgement?.complete(Unit) == true
    }

    suspend fun receive(context: RpcCallContext, value: RpcDeviceTestReport): Boolean = lock.withLock {
        val expected = pending ?: return@withLock false
        if (context.peer.fingerprint != expected.first || value.runId != expected.second.runId ||
            value.phase != expected.second.phase || value.sourceSha != expected.second.sourceSha ||
            !validDeviceTestReport(value) || acknowledgement?.isCompleted != true
        ) return@withLock false
        remoteResult?.complete(value) == true
    }

    suspend fun run(phase: RpcDeviceTestPhase, selectedPeer: String?) {
        val command = DeviceTestCommand(Random.nextBytes(16).joinToString("") {
            it.toUByte().toString(16).padStart(2, '0')
        }, RpcPhoneLab.compiledSource, phase)
        val job = checkNotNull(currentCoroutineContext()[Job])
        check(!closed.value && active.compareAndSet(null, job))
        try {
            if (host == null) execute(command) else {
                val pin = PeerFingerprint.parse(checkNotNull(selectedPeer))
                val result = CompletableDeferred<RpcDeviceTestReport>()
                val accepted = CompletableDeferred<Unit>()
                lock.withLock { pending = pin to command; remoteResult = result; acknowledgement = accepted }
                session.publish(RpcDeviceTestProgress(command.runId, "Waiting for the selected client", true))
                check(host.tryNotify(pin, DeviceTestContract.start, command) == RpcNotifyResult.Enqueued)
                try {
                    withTimeout(7_000) { accepted.await() }
                    session.publish(RpcDeviceTestProgress(command.runId, phase.title, true))
                    val report = withTimeout(if (phase == RpcDeviceTestPhase.Steady) 1_850_000 else 240_000) {
                        result.await()
                    }
                    session.save(report)
                } finally {
                    withContext(NonCancellable) { host.tryNotify(pin, DeviceTestContract.cancel, command.runId) }
                }
            }
        } catch (_: TimeoutCancellationException) {
            session.save(emptyDeviceTestReport(command, "Failed", "ClientAcknowledgementOrResultTimeout"))
        } catch (cancelled: CancellationException) {
            session.save(emptyDeviceTestReport(command, "Cancelled", "CallerCancelled"))
            throw cancelled
        } catch (_: Exception) {
            session.save(emptyDeviceTestReport(command, "Failed", "ClientUnarmedBusyOrUnavailable"))

        } finally {
            active.compareAndSet(job, null)
            withContext(NonCancellable) {
                lock.withLock { pending = null; remoteResult = null; acknowledgement = null }
            }
            session.publish(RpcDeviceTestProgress())
        }
    }

    private suspend fun execute(command: DeviceTestCommand) {
        val peer = checkNotNull(client)
        val initialization = TimeSource.Monotonic.markNow()
        var calls = 0L
        var correct = 0L
        var missed = 0L
        var disconnects = 0
        var deadlines = 0
        var cancellations = 0
        val buckets = LongArray(30_001)
        var latencySamples = 0L
        var measured = TimeSource.Monotonic.markNow()
        var initializationMillis = 0L
        var status = "Completed"
        var failureCode: String? = null
        var initialized = false
        val seconds = if (command.phase == RpcDeviceTestPhase.Steady) 1_800L else 0L
        suspend fun echo(large: Boolean = false, size: Int = RpcCapacityContract.ENCODED_BYTES) {
            currentCoroutineContext().ensureActive()
            check(peer.state.value == RpcConnectionState.Ready)
            val payload = if (large) "a".repeat(size - 2) else RpcCapacityContract.payload
            val started = TimeSource.Monotonic.markNow()
            calls++
            val reply = peer.call(if (large) RpcCapacityContract.largeEcho else RpcCapacityContract.echo,
                payload, timeout = 5_000.milliseconds, retry = RpcRetry.RecoverOnly(1))
            check(reply is RpcReply.Success && reply.value == payload)
            correct++
            latencySamples++
            buckets[started.elapsedNow().inWholeMilliseconds.coerceIn(0, 30_000).toInt()]++
            session.publish(RpcDeviceTestProgress(command.runId, command.phase.title, true, correct,
                measured.elapsedNow().inWholeSeconds, seconds))
        }
        try {
            withTimeout(30_000) { peer.state.first { it == RpcConnectionState.Ready } }
            initializationMillis = initialization.elapsedNow().inWholeMilliseconds
            measured = TimeSource.Monotonic.markNow()
            initialized = true
            when (command.phase) {
                RpcDeviceTestPhase.Large -> for (size in listOf(65_536, 262_144, 1_048_576)) echo(true, size)
                RpcDeviceTestPhase.Correctness -> {
                    repeat(10) { echo() }
                    calls++
                    val user = peer.call(RpcApplicationContract.getUser, UserQuery(123))
                    check(user is RpcReply.Success && user.value.userId == 123)
                    correct++
                    calls++
                    val invalid = peer.call(RpcApplicationContract.getUser, UserQuery(-1))
                    check(invalid is RpcReply.ApplicationError && invalid.error.code == ApplicationProblemCode.InvalidArgument)
                    correct++
                }
                RpcDeviceTestPhase.Reconnect -> repeat(5) {
                    peer.disconnect()
                    disconnects++
                    // The existing saved-pin discovery owner chooses a fresh endpoint; never reuse a stale IP here.
                    withTimeout(30_000) { peer.state.first { it == RpcConnectionState.Ready } }
                    echo()
                }
                RpcDeviceTestPhase.Steady -> {
                    var nextMillis = 0L
                    while (measured.elapsedNow().inWholeMilliseconds < 1_800_000) {
                        val now = measured.elapsedNow().inWholeMilliseconds
                        if (now < nextMillis) delay(nextMillis - now)
                        val lateness = (measured.elapsedNow().inWholeMilliseconds - nextMillis).coerceAtLeast(0)
                        val skipped = lateness / 100
                        missed += skipped
                        nextMillis += (skipped + 1) * 100
                        if (measured.elapsedNow().inWholeMilliseconds < 1_800_000) echo()
                    }
                }
                RpcDeviceTestPhase.Deadlines -> {
                    try {
                        peer.call(DeviceTestContract.delayed, DeviceTestDelay(500, "deadline"),
                            timeout = 25.milliseconds, retry = RpcRetry.RecoverOnly(1))
                        error("Deadline did not fire")
                    } catch (failure: RpcFailure) {
                        check(failure.kind == RpcFailureKind.DeadlineExceeded)
                        deadlines++
                    }
                    coroutineScope {
                        val child = async {
                            peer.call(DeviceTestContract.delayed, DeviceTestDelay(1_000, "cancel"))
                        }
                        delay(50)
                        check(!child.isCompleted)
                        child.cancelAndJoin()
                        check(child.isCancelled)
                    }
                    cancellations++ // Caller cancellation only; no claim that a remote effect was rolled back.
                    echo()
                }
            }
        } catch (cancelled: CancellationException) {
            status = "Cancelled"
            failureCode = "CallerCancelled"
        } catch (failure: RpcFailure) {
            status = "Interrupted"
            failureCode = "${failure.kind}/${failure.phase}/${failure.executionEvidence}"
        } catch (failure: Exception) {
            status = "Failed"
            failureCode = "LocalOrCorrectnessFailure"
        } finally {
            fun percentile(percent: Int): Long {
                if (latencySamples == 0L) return 0
                val target = (latencySamples * percent + 99) / 100
                var sum = 0L
                for (index in buckets.indices) { sum += buckets[index]; if (sum >= target) return (index + 1L) * 1_000 }
                return 30_001_000
            }
            val report = RpcDeviceTestReport(command.runId, command.phase, command.sourceSha, status, calls, correct,
                if (initialized) measured.elapsedNow().inWholeMilliseconds else 0,
                if (initialized) initializationMillis else initialization.elapsedNow().inWholeMilliseconds, missed,
                percentile(95), percentile(99), disconnects, deadlines, cancellations, failureCode,
                latencySamples = latencySamples)
            session.save(report)
            withContext(NonCancellable) {
                if (peer.state.value == RpcConnectionState.Ready) {
                    try { peer.call(DeviceTestContract.report, report, timeout = 5_000.milliseconds,
                        retry = RpcRetry.RecoverOnly(1)) } catch (_: Exception) { /* Local report remains saved. */ }
                }
            }
            session.publish(RpcDeviceTestProgress())
        }
    }

    suspend fun close() {
        closed.value = true
        remoteEnabled.value = false
        listener?.cancelAndJoin()
        cancellationListener?.cancelAndJoin()
        active.value?.cancelAndJoin()
        session.release(this)
    }
}

internal fun validDeviceTestCommand(command: DeviceTestCommand): Boolean =
    command.runId.matches(Regex("[a-f0-9]{32}")) && command.sourceSha.matches(Regex("[a-f0-9]{40}"))

internal fun validDeviceTestReport(value: RpcDeviceTestReport): Boolean =
    validDeviceTestCommand(DeviceTestCommand(value.runId, value.sourceSha, value.phase)) &&
        value.scope == "INTERACTIVE_CONNECTED_DEVICE_RPC" && value.measuredClientCount == 1 &&
        value.latencySamples in 0..value.correctResponses && value.latencyBucketMicros == 1_000 && value.status in setOf("Completed", "Failed", "Cancelled", "Interrupted") &&
        value.calls in 0..100_000 && value.correctResponses in 0..value.calls &&
        value.elapsedMillis in 0..1_850_000 && value.initializationMillis in 0..1_850_000 &&
        value.missedSchedules in 0..18_500 && value.p95Micros in 0..30_001_000 &&
        value.p99Micros in value.p95Micros..30_001_000 && value.deliberateDisconnects in 0..5 &&
        value.expectedDeadlines in 0..1 && value.callerCancellations in 0..1 &&
        (value.failureCode?.length ?: 0) <= 128 &&
        (value.status != "Completed" || (value.correctResponses == value.calls && value.calls >= when (value.phase) {
            RpcDeviceTestPhase.Large -> 3
            RpcDeviceTestPhase.Correctness -> 12
            RpcDeviceTestPhase.Reconnect -> 5
            RpcDeviceTestPhase.Steady, RpcDeviceTestPhase.Deadlines -> 1
        })) &&
        (value.status != "Completed" || value.phase != RpcDeviceTestPhase.Steady || value.elapsedMillis >= 1_800_000)

internal fun emptyDeviceTestReport(command: DeviceTestCommand, status: String, failure: String): RpcDeviceTestReport =
    RpcDeviceTestReport(command.runId, command.phase, command.sourceSha, status, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, failure)
