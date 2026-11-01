package dev.p2pkit.sample.rpc

import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcCallContext
import dev.p2pkit.rpc.RpcCallObservation
import dev.p2pkit.rpc.RpcClient
import dev.p2pkit.rpc.RpcConnectionState
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcExecutionEvidence
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
import kotlin.time.Clock
import kotlin.time.Duration
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
    public val clientResources: RpcDeviceTestResources? = null,
    public val initiatingHostResources: RpcDeviceTestResources? = null,
    public val scope: String = "INTERACTIVE_CONNECTED_DEVICE_RPC",
    public val clientPlatform: String = "Unknown",
    public val hostPlatform: String = "Unknown",
    public val startedAtEpochMillis: Long = 0,
    public val initiatedBy: String = "Client",
    public val observations: List<RpcDeviceTestObservation> = emptyList(),
    public val progressMessages: Long = 0,
) {
    public val direction: String get() = "$clientPlatform → $hostPlatform"
    public val title: String get() = "$direction · ${phase.title}: $status · " +
        "$correctResponses responses · ${elapsedMillis / 1_000}s"
}

public data class RpcDeviceTestProgress(
    public val runId: String = "",
    public val title: String = "No test running",
    public val running: Boolean = false,
    public val calls: Long = 0,
    public val elapsedSeconds: Long = 0,
    public val plannedSeconds: Long = 0,
    public val direction: String = "",
    public val stage: String = "Waiting for a test",
)

@Serializable
internal data class DeviceTestCommand(val runId: String, val sourceSha: String, val phase: RpcDeviceTestPhase)

@Serializable
internal data class DeviceTestDelay(val millis: Int, val body: String)

@Serializable
internal data class DeviceTestBegin(val command: DeviceTestCommand, val clientPlatform: String,
    val startedAtEpochMillis: Long, val initiatedBy: String)

@Serializable
internal data class DeviceTestUpdate(val command: DeviceTestCommand, val correctResponses: Long,
    val elapsedSeconds: Long, val plannedSeconds: Long)

internal object DeviceTestContract {
    val start = RpcNotification("device-tests.start", 1, DeviceTestCommand.serializer(), limitBytes = 1_024)
    val cancel = RpcNotification("device-tests.cancel", 1, String.serializer(), limitBytes = 128)
    val source = RpcProcedure("device-tests.source", 1, String.serializer(),
        String.serializer(), String.serializer(), requestLimitBytes = 128, responseLimitBytes = 128)
    val acknowledgement = RpcProcedure("device-tests.ack", 1, DeviceTestCommand.serializer(),
        String.serializer(), String.serializer(), requestLimitBytes = 1_024, responseLimitBytes = 128)
    val report = RpcProcedure("device-tests.report", 1, RpcDeviceTestReport.serializer(),
        String.serializer(), String.serializer(), requestLimitBytes = 16_384, responseLimitBytes = 128)
    val delayed = RpcProcedure("device-tests.delayed", 1, DeviceTestDelay.serializer(),
        String.serializer(), String.serializer(), requestLimitBytes = 2_048, responseLimitBytes = 2_048)
    val begin = RpcProcedure("device-tests.begin", 1, DeviceTestBegin.serializer(),
        String.serializer(), String.serializer(), requestLimitBytes = 1_024, responseLimitBytes = 128)
    val progress = RpcProcedure("device-tests.progress", 1, DeviceTestUpdate.serializer(),
        String.serializer(), String.serializer(), requestLimitBytes = 1_024, responseLimitBytes = 128)
}

/** Bounded results outlive a role. Platform screens persist the immutable JSON in their private app storage. */
public class RpcDeviceTestSession(internal val history: RpcRequestHistory = RpcRequestHistory()) {
    private val records = MutableStateFlow<List<RpcDeviceTestReport>>(emptyList())
    public val reports: List<RpcDeviceTestReport> get() = records.value
    private val latest = MutableStateFlow(RpcDeviceTestProgress())
    public val progress: RpcDeviceTestProgress get() = latest.value
    public val changes = records.asStateFlow()
    public val progressChanges = latest.asStateFlow()
    private val archivePending = MutableStateFlow<List<RpcDeviceTestReport>>(emptyList())
    /** Bounded pending writes apply backpressure instead of dropping a completed run. */
    public val unarchivedReports: List<RpcDeviceTestReport> get() = archivePending.value
    public val archiveAvailable: Boolean get() = archivePending.value.size < 100
    internal var platformName: String = "Unknown"
        private set

    @Throws(Exception::class)
    public fun configureDeviceName(value: String) {
        require(value in deviceTestPlatforms && value != "Unknown")
        check(runtime.value == null)
        platformName = value
    }

    public fun reportJson(report: RpcDeviceTestReport): String = Json.encodeToString(report)
    public fun confirmArchived(runId: String) {
        archivePending.update { values -> values.filterNot { it.runId == runId } }
    }

    public val activity: List<RpcDeviceTestObservation> get() = history.entries()
        .filter { it.procedure in deviceTestProcedures }.takeLast(32).map { it.testObservation() }

    internal fun capture(context: RpcCallContext, procedure: String, encodedBytes: Int?): Long? =
        if (context.hostObservationId == null) null else history.begin(RpcRequestSide.Host, procedure, 1,
            encodedBytes?.let { "[generated test body; encodedBytes=$it]" } ?: "[test body omitted]",
            context.requestId.value,
            context.peer.fingerprint?.value, context.hostIncarnation, context.hostObservationId)

    internal fun response(capture: Long?, encodedBytes: Int) {
        // Handler return is only response preparation. Engine observation supplies its terminal outcome.
        history.hostResponse(capture, "[generated reply; encodedBytes=$encodedBytes]")
    }
    private val runtime = MutableStateFlow<DeviceTestRuntime?>(null)
    private val resourceWindow = MutableStateFlow<DeviceResourceWindow?>(null)
    private val resourceOrigin = TimeSource.Monotonic.markNow()

    /** Frontend calls this from its existing foreground sampler; missing counters remain unavailable. */
    @Throws(Exception::class)
    public fun observeResources(cpuNanos: Long, memoryBytes: Long, memoryKind: String,
        threads: Int, threadKind: String, environment: RpcPhoneEnvironmentStats?) {
        require(cpuNanos >= 0 && memoryBytes > 0 && threads > 0)
        val millis = resourceOrigin.elapsedNow().inWholeMilliseconds
        resourceWindow.update {
            it?.observe(millis, cpuNanos, memoryBytes, memoryKind, threads, threadKind, environment)
        }
        if (environment?.requiresThermalStop == true) runtime.value?.cancel()
    }

    internal fun beginResources(runId: String) { resourceWindow.value = DeviceResourceWindow(runId) }
    internal fun finishResources(runId: String): RpcDeviceTestResources? {
        while (true) {
            val window = resourceWindow.value?.takeIf { it.runId == runId } ?: return null
            if (resourceWindow.compareAndSet(window, null)) return window.summary
        }
    }

    /** Recent index is compact; immutable per-run archives retain the observations. */
    public fun exportJson(): String = Json.encodeToString(reports.map { it.copy(observations = emptyList()) })

    @Throws(Exception::class)
    public fun restoreJson(text: String) {
        require(text.length <= 512_000)
        val restored = Json.decodeFromString<List<RpcDeviceTestReport>>(text)
        require(restored.size <= 100 && restored.all(::validDeviceTestReport))
        require(restored.map { it.runId }.distinct().size == restored.size)
        check(records.value.isEmpty())
        records.value = restored
        archivePending.value = restored
    }

    internal fun register(configuration: RpcHostConfiguration) {
        configuration.notification(DeviceTestContract.start)
        configuration.notification(DeviceTestContract.cancel)
        configuration.register(DeviceTestContract.source, authorize = { it.fingerprint != null }) { _, value ->
            if (value == "source") RpcReply.Success(RpcPhoneLab.compiledSource)
            else RpcReply.ApplicationError("Unknown source request")
        }
        configuration.register(DeviceTestContract.acknowledgement,
            authorize = { it.fingerprint != null }) { c, command ->
            if (runtime.value?.acknowledge(c, command) == true) RpcReply.Success("Accepted")
            else RpcReply.ApplicationError("No matching test")
        }
        configuration.register(DeviceTestContract.report, authorize = { it.fingerprint != null }) { context, value ->
            if (runtime.value?.receive(context, value) == true) RpcReply.Success("Recorded")
            else RpcReply.ApplicationError("No matching active test")
        }
        configuration.register(DeviceTestContract.begin, authorize = { it.fingerprint != null }) { context, value ->
            runtime.value?.observeBegin(context, value)?.let { RpcReply.Success(it) }
                ?: RpcReply.ApplicationError("Test observer busy or source mismatch")
        }
        configuration.register(DeviceTestContract.progress, authorize = { it.fingerprint != null }) { context, value ->
            if (runtime.value?.observeProgress(context, value) == true) RpcReply.Success("Observed")
            else RpcReply.ApplicationError("No matching observed test")
        }
        configuration.register(DeviceTestContract.delayed, authorize = { it.fingerprint != null }) { context, value ->
            require(value.millis in 0..2_000 && value.body.length <= 1_024)
            val capture = capture(context, DeviceTestContract.delayed.name,
                Json.encodeToString(value).encodeToByteArray().size)
            delay(value.millis.toLong())
            response(capture, value.body.length + 2)
            RpcReply.Success(value.body)
        }
    }

    internal fun bind(scope: CoroutineScope, host: RpcHost?, client: RpcClient?): DeviceTestRuntime {
        return DeviceTestRuntime(scope, host, client, this).also { check(runtime.compareAndSet(null, it)) }
    }

    internal fun release(value: DeviceTestRuntime) { runtime.compareAndSet(value, null) }
    internal fun publish(value: RpcDeviceTestProgress) { latest.value = value }
    internal fun finishProgress(runId: String) {
        latest.update { if (it.runId == runId) RpcDeviceTestProgress() else it }
    }
    internal fun save(value: RpcDeviceTestReport) {
        require(validDeviceTestReport(value))
        if (records.value.any { it.runId == value.runId }) return
        archivePending.update { previous ->
            if (previous.any { it.runId == value.runId }) previous else {
                check(previous.size < 100) { "Archive pending writes are full; preserve prior results" }
                previous + value
            }
        }
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
    private var observedBegin: DeviceTestBegin? = null
    private var hostHistoryStart: Long = 0

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
                            execute(command, initiatedBy = "Host")
                        } catch (cancelled: CancellationException) {
                            session.save(emptyDeviceTestReport(command, "Cancelled", "CallerCancelledBeforeStart"))
                            throw cancelled
                        } catch (_: Exception) {
                            session.save(emptyDeviceTestReport(command, "Failed", "StartAcknowledgementFailed"))
                        } finally {
                            active.compareAndSet(currentCoroutineContext()[Job], null)
                            session.finishProgress(command.runId)
                        }
                    }
                    if (remoteEnabled.value && !closed.value && session.reports.none { it.runId == command.runId } &&
                        client.state.value == RpcConnectionState.Ready && active.compareAndSet(null, job)
                    ) {
                        session.publish(RpcDeviceTestProgress(command.runId, "Starting ${command.phase.title}", true))
                        job.start()
                    } else job.cancel()
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

    suspend fun observeBegin(context: RpcCallContext, begin: DeviceTestBegin): String? = lock.withLock {
        val pin = context.peer.fingerprint ?: return@withLock null
        if (host == null || closed.value || !validDeviceTestBegin(begin) ||
            begin.command.sourceSha != RpcPhoneLab.compiledSource || !session.archiveAvailable
        ) return@withLock null
        val expected = pending
        if (expected != null) {
            if (expected.first != pin || expected.second != begin.command ||
                acknowledgement?.isCompleted != true || observedBegin != null || begin.initiatedBy != "Host"
            ) return@withLock null
            observedBegin = begin
            session.publish(RpcDeviceTestProgress(begin.command.runId, begin.command.phase.title, true,
                direction = "${begin.clientPlatform} → ${session.platformName}", stage = "Client is initializing"))
            return@withLock session.platformName
        }
        if (begin.initiatedBy != "Client" || session.reports.any { it.runId == begin.command.runId }) {
            return@withLock null
        }
        val result = CompletableDeferred<RpcDeviceTestReport>()
        val observer = scope.launch(start = CoroutineStart.LAZY) {
            try {
                awaitRemote(begin.command, result)
            } catch (_: TimeoutCancellationException) {
                session.save(observedFailure(begin.command, "Interrupted", "ClientResultNotReceived"))
            } catch (cancelled: CancellationException) {
                session.save(observedFailure(begin.command, "Cancelled", "HostObservationCancelled"))
                throw cancelled
            } catch (_: Exception) {
                session.save(observedFailure(begin.command, "Failed", "HostObservationFailed"))
            } finally {
                val originalJob = currentCoroutineContext()[Job]
                withContext(NonCancellable) {
                    try {
                        if (!result.isCompleted) host.tryNotify(pin, DeviceTestContract.cancel, begin.command.runId)
                    } finally { clearRun(begin.command, originalJob) }
                }
            }
        }
        if (!active.compareAndSet(null, observer)) { observer.cancel(); return@withLock null }
        pending = pin to begin.command
        remoteResult = result
        acknowledgement = CompletableDeferred(Unit)
        observedBegin = begin
        hostHistoryStart = session.history.entries().lastOrNull()?.localId ?: 0
        session.beginResources(begin.command.runId)
        session.publish(RpcDeviceTestProgress(begin.command.runId, begin.command.phase.title, true,
            direction = "${begin.clientPlatform} → ${session.platformName}", stage = "Client is initializing"))
        observer.start()
        session.platformName
    }

    suspend fun observeProgress(context: RpcCallContext, value: DeviceTestUpdate): Boolean = lock.withLock {
        val expected = pending ?: return@withLock false
        if (context.peer.fingerprint != expected.first || value.command != expected.second ||
            observedBegin == null || !validDeviceTestUpdate(value) ||
            value.correctResponses < session.progress.calls || value.elapsedSeconds < session.progress.elapsedSeconds
        ) return@withLock false
        session.publish(RpcDeviceTestProgress(value.command.runId, value.command.phase.title, true,
            value.correctResponses, value.elapsedSeconds, value.plannedSeconds,
            "${checkNotNull(observedBegin).clientPlatform} → ${session.platformName}", "Client progress received"))
        true
    }

    private fun observedFailure(command: DeviceTestCommand, status: String, code: String): RpcDeviceTestReport {
        val metadata = observedBegin
        val resources = session.finishResources(command.runId)
        val thermal = resources?.thermalStopped == true
        return emptyDeviceTestReport(command, if (thermal) "Interrupted" else status,
            if (thermal) "ThermalStop" else code).copy(clientPlatform = metadata?.clientPlatform ?: "Unknown",
            hostPlatform = session.platformName, startedAtEpochMillis = metadata?.startedAtEpochMillis ?: 0,
            initiatedBy = metadata?.initiatedBy ?: "Host", observations = hostObservations(),
            initiatingHostResources = resources)
    }

    private fun hostObservations(): List<RpcDeviceTestObservation> = session.history.entries().filter {
        it.localId > hostHistoryStart && it.peerFingerprint == pending?.first?.value &&
            it.procedure in deviceTestProcedures
    }.takeLast(16).map { it.testObservation() }

    private suspend fun awaitRemote(command: DeviceTestCommand, result: CompletableDeferred<RpcDeviceTestReport>) {
        val report = withTimeout(if (command.phase == RpcDeviceTestPhase.Steady) 1_850_000 else 240_000) {
            result.await()
        }
        session.save(report.copy(initiatingHostResources = session.finishResources(command.runId),
            observations = (report.observations.takeLast(16) + hostObservations()).takeLast(32)))
    }

    private suspend fun clearRun(command: DeviceTestCommand, job: Job?) {
        session.finishResources(command.runId)
        active.compareAndSet(job, null)
        lock.withLock {
            if (pending?.second == command) {
                pending = null; remoteResult = null; acknowledgement = null; observedBegin = null
            }
        }
        session.finishProgress(command.runId)
    }

    suspend fun acknowledge(context: RpcCallContext, command: DeviceTestCommand): Boolean = lock.withLock {
        val expected = pending ?: return@withLock false
        context.peer.fingerprint == expected.first && command == expected.second &&
            acknowledgement?.complete(Unit) == true
    }

    suspend fun receive(context: RpcCallContext, value: RpcDeviceTestReport): Boolean = lock.withLock {
        val expected = pending ?: return@withLock false
        if (acknowledgement?.isCompleted != true ||
            !matchesDeviceTestResult(context.peer.fingerprint?.value, expected.first.value,
                value, expected.second, observedBegin, session.platformName)
        ) return@withLock false
        remoteResult?.complete(value) == true
    }

    suspend fun run(phase: RpcDeviceTestPhase, selectedPeer: String?) {
        val command = DeviceTestCommand(Random.nextBytes(16).joinToString("") {
            it.toUByte().toString(16).padStart(2, '0')
        }, RpcPhoneLab.compiledSource, phase)
        val job = checkNotNull(currentCoroutineContext()[Job])
        check(!closed.value && session.archiveAvailable && active.compareAndSet(null, job))
        try {
            if (host == null) execute(command) else {
                val pin = PeerFingerprint.parse(checkNotNull(selectedPeer))
                val result = CompletableDeferred<RpcDeviceTestReport>()
                val accepted = CompletableDeferred<Unit>()
                lock.withLock {
                    pending = pin to command; remoteResult = result; acknowledgement = accepted
                    hostHistoryStart = session.history.entries().lastOrNull()?.localId ?: 0
                }
                session.publish(RpcDeviceTestProgress(command.runId, "Waiting for the selected client", true))
                check(host.tryNotify(pin, DeviceTestContract.start, command) == RpcNotifyResult.Enqueued)
                try {
                    withTimeout(7_000) { accepted.await() }
                    session.beginResources(command.runId)
                    awaitRemote(command, result)
                } finally {
                    withContext(NonCancellable) {
                        if (!result.isCompleted) host.tryNotify(pin, DeviceTestContract.cancel, command.runId)
                    }
                }
            }
        } catch (_: TimeoutCancellationException) {
            session.save(observedFailure(command, "Failed", "ClientAcknowledgementOrResultTimeout"))
        } catch (cancelled: CancellationException) {
            session.save(observedFailure(command, "Cancelled", "CallerCancelled"))
            throw cancelled
        } catch (_: Exception) {
            session.save(observedFailure(command, "Failed", "ClientUnarmedBusyOrUnavailable"))

        } finally {
            withContext(NonCancellable) { clearRun(command, job) }
        }
    }

    private suspend fun execute(command: DeviceTestCommand, initiatedBy: String = "Client") {
        val peer = checkNotNull(client)
        val startedAt = Clock.System.now().toEpochMilliseconds()
        val historyStart = session.history.entries().lastOrNull()?.localId ?: 0
        var hostPlatform = "Unknown"
        var progressMessages = 0L
        var progressWriter: Job? = null
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
            val reply = invoke(if (large) RpcCapacityContract.largeEcho else RpcCapacityContract.echo,
                payload, encodedBytes = size)
            check(reply is RpcReply.Success && reply.value == payload)
            correct++
            latencySamples++
            buckets[started.elapsedNow().inWholeMilliseconds.coerceIn(0, 30_000).toInt()]++
            session.publish(RpcDeviceTestProgress(command.runId, command.phase.title, true, correct,
                measured.elapsedNow().inWholeSeconds, seconds, "${session.platformName} → $hostPlatform",
                "Reply checked: content matches"))
        }
        try {
            session.publish(RpcDeviceTestProgress(command.runId, "Checking connected source", true))
            withTimeout(30_000) { peer.state.first { it == RpcConnectionState.Ready } }
            val source = invoke(DeviceTestContract.source, "source")
            check(source is RpcReply.Success && source.value == command.sourceSha)
            val begin = invoke(DeviceTestContract.begin,
                DeviceTestBegin(command, session.platformName, startedAt, initiatedBy))
            check(begin is RpcReply.Success && begin.value in deviceTestPlatforms)
            hostPlatform = begin.value
            initializationMillis = initialization.elapsedNow().inWholeMilliseconds
            measured = TimeSource.Monotonic.markNow()
            initialized = true
            session.beginResources(command.runId)
            session.publish(RpcDeviceTestProgress(command.runId, command.phase.title, true, plannedSeconds = seconds,
                direction = "${session.platformName} → $hostPlatform", stage = "Source matched; workload starting"))
            progressWriter = scope.launch {
                while (true) {
                    delay(1_000)
                    val snapshot = session.progress
                    if (snapshot.runId == command.runId && snapshot.running &&
                        peer.state.value == RpcConnectionState.Ready
                    ) {
                        try {
                            val received = peer.call(DeviceTestContract.progress,
                                DeviceTestUpdate(command, snapshot.calls, snapshot.elapsedSeconds, seconds),
                                timeout = 1_000.milliseconds, retry = RpcRetry.RecoverOnly(1))
                            if (received is RpcReply.Success) progressMessages++
                        } catch (_: Exception) { /* No progress retry or extension of workload bounds. */ }
                    }
                }
            }
            when (command.phase) {
                RpcDeviceTestPhase.Large -> for (size in listOf(65_536, 262_144, 1_048_576)) echo(true, size)
                RpcDeviceTestPhase.Correctness -> {
                    repeat(10) { echo() }
                    calls++
                    val user = invoke(RpcApplicationContract.getUser, UserQuery(123))
                    check(user is RpcReply.Success && user.value.userId == 123)
                    correct++
                    calls++
                    val invalid = invoke(RpcApplicationContract.getUser, UserQuery(-1))
                    check(invalid is RpcReply.ApplicationError &&
                        invalid.error.code == ApplicationProblemCode.InvalidArgument)
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
                        invoke(DeviceTestContract.delayed, DeviceTestDelay(500, "deadline"), timeout = 25.milliseconds)
                        error("Deadline did not fire")
                    } catch (failure: RpcFailure) {
                        check(failure.kind == RpcFailureKind.DeadlineExceeded)
                        deadlines++
                    }
                    coroutineScope {
                        val child = async {
                            invoke(DeviceTestContract.delayed, DeviceTestDelay(1_000, "cancel"))
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
            withContext(NonCancellable) { progressWriter?.cancelAndJoin() }
            fun percentile(percent: Int): Long {
                if (latencySamples == 0L) return 0
                val target = (latencySamples * percent + 99) / 100
                var sum = 0L
                for (index in buckets.indices) { sum += buckets[index]; if (sum >= target) return (index + 1L) * 1_000 }
                return 30_001_000
            }
            val resources = session.finishResources(command.runId)
            if (resources?.thermalStopped == true) { status = "Interrupted"; failureCode = "ThermalStop" }
            val report = RpcDeviceTestReport(command.runId, command.phase, command.sourceSha, status, calls, correct,
                if (initialized) measured.elapsedNow().inWholeMilliseconds else 0,
                if (initialized) initializationMillis else initialization.elapsedNow().inWholeMilliseconds, missed,
                percentile(95), percentile(99), disconnects, deadlines, cancellations, failureCode,
                latencySamples = latencySamples, clientResources = resources, clientPlatform = session.platformName,
                hostPlatform = hostPlatform, startedAtEpochMillis = startedAt, initiatedBy = initiatedBy,
                observations = session.history.entries().filter {
                    it.localId > historyStart && it.procedure in deviceTestProcedures
                }.takeLast(32).map { it.testObservation() }, progressMessages = progressMessages)
            session.save(report)
            withContext(NonCancellable) {
                if (peer.state.value == RpcConnectionState.Ready) {
                    try { invoke(DeviceTestContract.report, report) }
                    catch (_: Exception) { /* Local report remains archived; Host receipt is not invented. */ }
                }
            }
            session.finishProgress(command.runId)
        }
    }

    private suspend fun <Q, R, E> invoke(procedure: RpcProcedure<Q, R, E>, request: Q,
        encodedBytes: Int? = null, timeout: Duration = 5_000.milliseconds): RpcReply<R, E> {
        val history = session.history
        val local = history.begin(RpcRequestSide.Client, procedure.name, procedure.version,
            encodedBytes?.let { "[generated test body; encodedBytes=$it]" } ?: "[test control; body omitted]")
        val observation = RpcCallObservation()
        history.bindClient(local, observation)
        val started = TimeSource.Monotonic.markNow()
        try {
            val details = checkNotNull(client).callWithObservation(procedure, request, observation,
                timeout = timeout, retry = RpcRetry.RecoverOnly(1))
            history.finish(local, if (details.reply is RpcReply.Success) RpcRequestOutcome.Succeeded
                else RpcRequestOutcome.BusinessError, details.elapsedMillis, "[reply received; body omitted]",
                requestId = details.requestId.value, evidence = RpcExecutionEvidence.HandlerFinished)
            return details.reply
        } catch (failure: Exception) {
            history.finish(local, when {
                failure is CancellationException -> RpcRequestOutcome.Cancelled
                failure is RpcFailure && failure.kind == RpcFailureKind.DeadlineExceeded -> RpcRequestOutcome.TimedOut
                else -> RpcRequestOutcome.RpcError
            }, started.elapsedNow().inWholeMilliseconds, errorCode = (failure as? RpcFailure)?.kind?.name,
                requestId = observation.progress.value.requestId,
                evidence = observation.progress.value.executionEvidence)
            throw failure
        } finally { history.unbindClient(local) }
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

internal fun validDeviceTestBegin(value: DeviceTestBegin): Boolean =
    validDeviceTestCommand(value.command) && value.clientPlatform in deviceTestPlatforms &&
        value.clientPlatform != "Unknown" && value.startedAtEpochMillis in 1..4_102_444_800_000 &&
        value.initiatedBy in setOf("Host", "Client")

internal fun validDeviceTestUpdate(value: DeviceTestUpdate): Boolean =
    validDeviceTestCommand(value.command) && value.correctResponses in 0..100_000 &&
        value.elapsedSeconds in 0..1_850 &&
        value.plannedSeconds == if (value.command.phase == RpcDeviceTestPhase.Steady) 1_800L else 0L

internal fun matchesObservedMetadata(
    report: RpcDeviceTestReport, begin: DeviceTestBegin?, hostPlatform: String,
): Boolean =
    begin != null && report.clientPlatform == begin.clientPlatform && report.hostPlatform == hostPlatform &&
        report.startedAtEpochMillis == begin.startedAtEpochMillis && report.initiatedBy == begin.initiatedBy

internal fun matchesDeviceTestResult(receivedPeer: String?, expectedPeer: String, report: RpcDeviceTestReport,
    command: DeviceTestCommand, begin: DeviceTestBegin?, hostPlatform: String): Boolean =
    receivedPeer == expectedPeer && report.runId == command.runId && report.phase == command.phase &&
        report.sourceSha == command.sourceSha && validDeviceTestReport(report) &&
        matchesObservedMetadata(report, begin, hostPlatform)

internal fun validDeviceTestReport(value: RpcDeviceTestReport): Boolean =
    validDeviceTestCommand(DeviceTestCommand(value.runId, value.sourceSha, value.phase)) &&
        value.clientPlatform in deviceTestPlatforms && value.hostPlatform in deviceTestPlatforms &&
        value.startedAtEpochMillis in 0..4_102_444_800_000 && value.initiatedBy in setOf("Host", "Client") &&
        value.observations.size <= 32 && value.observations.all(::validTestObservation) &&
        value.progressMessages in 0..1_850 &&
        validDeviceResources(value.clientResources) && validDeviceResources(value.initiatingHostResources) &&
        value.scope == "INTERACTIVE_CONNECTED_DEVICE_RPC" && value.measuredClientCount == 1 &&
        value.latencySamples in 0..value.correctResponses && value.latencyBucketMicros == 1_000 &&
        value.status in setOf("Completed", "Failed", "Cancelled", "Interrupted") &&
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
