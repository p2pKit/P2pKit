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
    Steady("Steady · 30 minutes"), Deadlines("Cancellation / deadline"), Adaptive("Smart · find stable load"),
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
    public val endedAtEpochMillis: Long = 0,
    public val mode: String = "Pair",
    public val groupId: String = "",
    public val p50Micros: Long = 0,
    public val failedResponses: Long = 0,
    public val smart: RpcSmartTestResult? = null,
    public val telemetryMessages: Long = 0,
) {
    public val direction: String get() = "$clientPlatform → $hostPlatform"
    public val title: String get() = "$direction · ${phase.title}: $status · " +
        "$correctResponses responses · ${elapsedMillis / 1_000}s"
    public val detail: String get() = buildString {
        appendLine("$mode · started by $initiatedBy · run $runId")
        if (groupId.isNotEmpty()) appendLine("Group: $groupId")
        appendLine("Source: $sourceSha")
        appendLine("Initialization ${initializationMillis} ms · measured ${elapsedMillis} ms")
        appendLine("$correctResponses correct / $calls attempted · $failedResponses failed · $missedSchedules missed")
        appendLine(if (latencySamples > 0) "p50 ${p50Micros / 1_000} ms · p95 ${p95Micros / 1_000} ms · " +
            "p99 ${p99Micros / 1_000} ms" else "Latency unavailable")
        failureCode?.let { appendLine("Outcome: $it") }
        clientResources?.let { appendLine("Client: ${it.title}"); appendLine(it.environmentTitle) }
        initiatingHostResources?.let { appendLine("Host: ${it.title}"); appendLine(it.environmentTitle) }
        smart?.let { value ->
            appendLine(value.title)
            appendLine("Confirmed target ${value.highestConfirmedTargetRps}/s · workers drained: " +
                value.workerCleanupVerified)
            value.limitations.forEach { appendLine(it) }
            value.steps.forEach { step ->
                appendLine(step.title)
                appendLine("${step.attempts} attempted · ${step.errors} errors · ${step.timeouts} timeouts · " +
                    "${step.missed} missed · p50 ${step.p50Micros / 1_000} ms · p99 ${step.p99Micros / 1_000} ms")
            }
        }
    }
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
    public val attempts: Long = 0,
    public val failures: Long = 0,
    public val p50Micros: Long = 0,
    public val p95Micros: Long = 0,
    public val p99Micros: Long = 0,
    public val targetRps: Int = 0,
    public val concurrency: Int = 1,
    public val inFlight: Int = 0,
    public val startedAtEpochMillis: Long = 0,
    public val hostResources: RpcDeviceTestResources? = null,
) {
    public val monitorText: String get() = "$direction · $title · $stage\n" +
        "${elapsedSeconds}s · $calls correct / $attempts attempts · $failures failed · $inFlight in flight\n" +
        "p50 ${p50Micros / 1_000} ms · p95 ${p95Micros / 1_000} ms · p99 ${p99Micros / 1_000} ms" +
        (if (targetRps > 0) " · target $targetRps/s · concurrency $concurrency" else "")
}

@Serializable
internal data class DeviceTestCommand(val runId: String, val sourceSha: String, val phase: RpcDeviceTestPhase,
    val mode: String = "Pair", val groupId: String = "", val smartSettings: RpcSmartTestSettings? = null)

@Serializable
internal data class DeviceTestDelay(val millis: Int, val body: String)

@Serializable
internal data class DeviceTestBegin(val command: DeviceTestCommand, val clientPlatform: String,
    val startedAtEpochMillis: Long, val initiatedBy: String)

@Serializable
internal data class DeviceTestUpdate(val command: DeviceTestCommand, val correctResponses: Long,
    val elapsedSeconds: Long, val plannedSeconds: Long, val attempts: Long = correctResponses,
    val failures: Long = 0, val p50Micros: Long = 0, val p95Micros: Long = 0, val p99Micros: Long = 0,
    val targetRps: Int = 0, val concurrency: Int = 1, val inFlight: Int = 0)

@Serializable
internal data class DeviceTestTelemetry(val resources: RpcDeviceTestResources? = null)

internal object DeviceTestContract {
    val start = RpcNotification("device-tests.start", 1, DeviceTestCommand.serializer(), limitBytes = 1_024)
    val cancel = RpcNotification("device-tests.cancel", 1, String.serializer(), limitBytes = 128)
    val source = RpcProcedure("device-tests.source", 1, String.serializer(),
        String.serializer(), String.serializer(), requestLimitBytes = 128, responseLimitBytes = 128)
    val acknowledgement = RpcProcedure("device-tests.ack", 1, DeviceTestCommand.serializer(),
        String.serializer(), String.serializer(), requestLimitBytes = 1_024, responseLimitBytes = 128)
    val report = RpcProcedure("device-tests.report", 1, RpcDeviceTestReport.serializer(),
        String.serializer(), String.serializer(), requestLimitBytes = 65_536, responseLimitBytes = 128)
    val delayed = RpcProcedure("device-tests.delayed", 1, DeviceTestDelay.serializer(),
        String.serializer(), String.serializer(), requestLimitBytes = 2_048, responseLimitBytes = 2_048)
    val begin = RpcProcedure("device-tests.begin", 1, DeviceTestBegin.serializer(),
        String.serializer(), String.serializer(), requestLimitBytes = 1_024, responseLimitBytes = 128)
    val progress = RpcProcedure("device-tests.progress", 1, DeviceTestUpdate.serializer(),
        String.serializer(), String.serializer(), requestLimitBytes = 1_024, responseLimitBytes = 128)
    val telemetry = RpcProcedure("device-tests.telemetry", 1, DeviceTestCommand.serializer(),
        DeviceTestTelemetry.serializer(), String.serializer(), requestLimitBytes = 1_024, responseLimitBytes = 4_096)
}

/** Bounded results outlive a role. Platform screens persist the immutable JSON in their private app storage. */
public class RpcDeviceTestSession(internal val history: RpcRequestHistory = RpcRequestHistory()) {
    private val records = MutableStateFlow<List<RpcDeviceTestReport>>(emptyList())
    public val reports: List<RpcDeviceTestReport> get() = records.value
    private val latest = MutableStateFlow(RpcDeviceTestProgress())
    public val progress: RpcDeviceTestProgress get() = latest.value
    public val changes = records.asStateFlow()
    public val progressChanges = latest.asStateFlow()
    private val running = MutableStateFlow<Map<String, RpcDeviceTestProgress>>(emptyMap())
    public val activeTests: List<RpcDeviceTestProgress> get() = running.value.values.toList()
    public val activeTestChanges = running.asStateFlow()
    public val anyTestRunning: Boolean get() = running.value.isNotEmpty()
    private val safetyStop = MutableStateFlow<String?>(null)
    /** OS memory-pressure notifications interrupt existing tests; they never start a role. */
    public fun signalMemoryPressure() {
        if (anyTestRunning) { safetyStop.value = "MemoryPressureSignal"; runtime.value?.cancel() }
    }
    public var multiDeviceMode: Boolean = false
        private set
    public var smartSettings: RpcSmartTestSettings = RpcSmartTestSettings()
        private set
    @Throws(Exception::class)
    public fun configureSmartSafety(p95Millis: Int, p99Millis: Int, memoryMiB: Int, durationSeconds: Int) {
        check(!anyTestRunning)
        val value = smartSettings.copy(p95LimitMillis = p95Millis, p99LimitMillis = p99Millis,
            maximumMemoryBytes = memoryMiB.toLong() * 1_048_576, maximumMillis = durationSeconds.toLong() * 1_000)
        require(value.valid())
        smartSettings = value
    }
    @Throws(Exception::class)
    public fun setMultiDeviceMode(enabled: Boolean) {
        check(!anyTestRunning)
        multiDeviceMode = enabled
    }
    private val hiddenHistoryBefore = MutableStateFlow(0L)
    private val hiddenResults = MutableStateFlow<Set<String>>(emptySet())
    private val displayRevision = MutableStateFlow(0L)
    public val displayChanges = displayRevision.asStateFlow()
    private val resultDeletion = MutableStateFlow<String?>(null)
    public val resultDeletionInProgress: Boolean get() = resultDeletion.value != null
    public val displayedReports: List<RpcDeviceTestReport> get() = reports.filterNot { it.runId in hiddenResults.value }
    /** Display-only marker; does not mutate retained observations or immutable archives. */
    public fun clearDisplayedActivity() {
        hiddenHistoryBefore.value = history.entries().lastOrNull()?.localId ?: hiddenHistoryBefore.value
        hiddenResults.value = reports.map { it.runId }.toSet()
        displayRevision.update { it + 1 }
    }
    public fun showSavedResults() { hiddenResults.value = emptySet(); displayRevision.update { it + 1 } }

    /** Platform calls only after its explicit per-run deletion confirmation. Admission stays sealed until finish. */
    @Throws(Exception::class)
    public suspend fun beginResultDeletion(runId: String): Boolean {
        require(runId.matches(Regex("[a-f0-9]{32}")))
        return runtime.value?.reserveDeletion(runId) ?: reserveDeletion(runId)
    }
    internal fun reserveDeletion(runId: String): Boolean = !anyTestRunning &&
        unarchivedReports.isEmpty() && reports.any { it.runId == runId } && resultDeletion.compareAndSet(null, runId)

    @Throws(Exception::class)
    public fun finishResultDeletion(runId: String, deleted: Boolean) {
        check(resultDeletion.value == runId)
        if (deleted) {
            forgetDeletedResult(runId)
            hiddenResults.update { it - runId }
        }
        check(resultDeletion.compareAndSet(runId, null))
    }
    private val archivePending = MutableStateFlow<List<RpcDeviceTestReport>>(emptyList())
    private val restoredArchivePending = MutableStateFlow<Set<String>>(emptySet())
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
    public fun archivedResultMatchesForDeletion(report: RpcDeviceTestReport, text: String): Boolean {
        if (text.encodeToByteArray().size > 65_536) return false
        val archived = try { Json.decodeFromString<RpcDeviceTestReport>(text) } catch (_: Exception) { return false }
        return validDeviceTestReport(archived) && compactDeviceTestReport(archived) == compactDeviceTestReport(report)
    }
    public fun confirmArchived(runId: String) {
        archivePending.update { values -> values.filterNot { it.runId == runId } }
        restoredArchivePending.update { it - runId }
    }

    /** A restored compact index may omit observations already preserved in its immutable archive. */
    public fun archiveMatches(report: RpcDeviceTestReport, json: String): Boolean {
        if (json.encodeToByteArray().size > 65_536) return false
        val archived = try { Json.decodeFromString<RpcDeviceTestReport>(json) } catch (_: Exception) { return false }
        return validDeviceTestReport(archived) && (archived == report ||
            (report.runId in restoredArchivePending.value && report.observations.isEmpty() &&
                compactDeviceTestReport(archived) == report))
    }

    /** Restore richer details from the already validated immutable record, never from a new result. */
    @Throws(Exception::class)
    public fun hydrateArchived(report: RpcDeviceTestReport, json: String) {
        check(archiveMatches(report, json))
        val archived = Json.decodeFromString<RpcDeviceTestReport>(json)
        records.update { values -> values.map { if (it.runId == report.runId) archived else it } }
    }

    public val activity: List<RpcDeviceTestObservation> get() = history.entries()
        .filter { it.localId > hiddenHistoryBefore.value && it.procedure in deviceTestProcedures }
        .takeLast(32).map { it.testObservation() }

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
    private val resourceWindows = MutableStateFlow<Map<String, DeviceResourceWindow>>(emptyMap())
    private val currentResourceWindow = MutableStateFlow(DeviceResourceWindow("live"))
    private val currentLiveResources = MutableStateFlow<RpcDeviceLiveResources?>(null)
    public val liveResources: RpcDeviceLiveResources? get() = currentLiveResources.value
    public val liveResourceChanges = currentLiveResources.asStateFlow()
    public val currentResources: RpcDeviceTestResources? get() = currentResourceWindow.value.summary
    private val resourceOrigin = TimeSource.Monotonic.markNow()

    /** Frontend calls this from its existing foreground sampler; missing counters remain unavailable. */
    @Throws(Exception::class)
    public fun observeResources(cpuNanos: Long, memoryBytes: Long, memoryKind: String,
        threads: Int, threadKind: String, environment: RpcPhoneEnvironmentStats?) {
        require(cpuNanos >= 0 && memoryBytes > 0 && threads > 0)
        val millis = resourceOrigin.elapsedNow().inWholeMilliseconds
        val before = currentResourceWindow.value
        val span = millis - before.lastMillis
        currentLiveResources.value = RpcDeviceLiveResources(memoryBytes, memoryKind, threads, threadKind,
            if (before.summary != null && span > 0 && cpuNanos >= before.lastCpu)
                (cpuNanos - before.lastCpu).toDouble() / (span * 10_000.0) else null,
            environment?.batteryPercentMilli, environment?.batteryState ?: "unavailable",
            environment?.thermalState ?: "unavailable", environment?.batteryTemperatureMilliC,
            environment?.batteryCurrentMicroamps)
        currentResourceWindow.update {
            it.observe(millis, cpuNanos, memoryBytes, memoryKind, threads, threadKind, environment)
        }
        resourceWindows.update { values -> values.mapValues { (_, window) ->
            window.observe(millis, cpuNanos, memoryBytes, memoryKind, threads, threadKind, environment)
        } }
        if (environment?.requiresThermalStop == true) runtime.value?.cancel()
    }

    internal fun resources(runId: String): RpcDeviceTestResources? = resourceWindows.value[runId]?.summary

    internal fun beginResources(runId: String) {
        resourceWindows.update { values ->
            check(runId in values || values.size < DEVICE_TEST_MAX_PARALLEL)
            values + (runId to DeviceResourceWindow(runId))
        }
    }
    internal fun finishResources(runId: String): RpcDeviceTestResources? {
        while (true) {
            val values = resourceWindows.value
            val window = values[runId] ?: return null
            if (resourceWindows.compareAndSet(values, values - runId)) return window.summary
        }
    }

    /** Recent index is compact; immutable per-run archives retain the observations. */
    public fun exportJson(): String = Json.encodeToString(reports.map(::compactDeviceTestReport))

    @Throws(Exception::class)
    public fun restoreJson(text: String) {
        require(text.length <= 8_388_608)
        val restored = Json.decodeFromString<List<RpcDeviceTestReport>>(text)
        require(restored.size <= 100 && restored.all(::validDeviceTestReport))
        require(restored.map { it.runId }.distinct().size == restored.size)
        check(records.value.isEmpty())
        restoredArchivePending.value = restored.map { it.runId }.toSet()
        archivePending.value = restored
        records.value = restored
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
        configuration.register(DeviceTestContract.telemetry, authorize = { it.fingerprint != null }) { context, value ->
            runtime.value?.telemetry(context, value)?.let { RpcReply.Success(it) }
                ?: RpcReply.ApplicationError("No matching active test")
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
        check(!resultDeletionInProgress)
        return DeviceTestRuntime(scope, host, client, this).also { check(runtime.compareAndSet(null, it)) }
    }

    internal fun release(value: DeviceTestRuntime) { runtime.compareAndSet(value, null) }
    internal fun publish(value: RpcDeviceTestProgress) {
        if (value.running && !anyTestRunning) safetyStop.value = null
        latest.value = value
        if (value.running && value.runId.isNotEmpty()) running.update { it + (value.runId to value) }
    }
    internal fun finishProgress(runId: String) {
        running.update { it - runId }
        latest.update { if (it.runId == runId) RpcDeviceTestProgress() else it }
    }
    internal val safetyStopReason: String? get() = safetyStop.value
    /** Called only after the platform has durably removed this exact immutable result. */
    @Throws(Exception::class)
    public fun forgetDeletedResult(runId: String) {
        require(runId.matches(Regex("[a-f0-9]{32}")))
        check(!anyTestRunning && unarchivedReports.none { it.runId == runId })
        records.update { it.filterNot { value -> value.runId == runId } }
        restoredArchivePending.update { it - runId }
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

internal const val DEVICE_TEST_MAX_PARALLEL = 16

internal fun compactDeviceTestReport(report: RpcDeviceTestReport): RpcDeviceTestReport =
    report.copy(observations = emptyList(), smart = report.smart?.copy(steps = emptyList(), limitations = emptyList()))

internal class DeviceTestRuntime(
    private val scope: CoroutineScope,
    private val host: RpcHost?,
    private val client: RpcClient?,
    private val session: RpcDeviceTestSession,
) {
    private class HostRun(val pin: PeerFingerprint, val command: DeviceTestCommand, val historyStart: Long) {
        val result = CompletableDeferred<RpcDeviceTestReport>()
        val acknowledged = CompletableDeferred<Unit>()
        var begin: DeviceTestBegin? = null
        var job: Job? = null
    }
    private val lock = Mutex()
    private val runs = linkedMapOf<String, HostRun>()
    private val hostJobs = MutableStateFlow<Map<String, Job>>(emptyMap())
    private val localJob = MutableStateFlow<Job?>(null)
    private var listener: Job? = null
    private var cancellationListener: Job? = null
    private val remoteEnabled = MutableStateFlow(false)
    private val closed = MutableStateFlow(false)

    init {
        if (client != null) {
            listener = scope.launch {
                client.notifications(DeviceTestContract.start).collect { command ->
                    if (!validDeviceTestCommand(command) || command.sourceSha != RpcPhoneLab.compiledSource ||
                        (command.mode == "Multi" && !session.multiDeviceMode)) return@collect
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
                            localJob.compareAndSet(currentCoroutineContext()[Job], null)
                            session.finishProgress(command.runId)
                        }
                    }
                    val admitted = lock.withLock {
                        remoteEnabled.value && !closed.value && !session.resultDeletionInProgress &&
                            session.archiveAvailable && session.reports.none { it.runId == command.runId } &&
                            client.state.value == RpcConnectionState.Ready && localJob.compareAndSet(null, job)
                    }
                    if (admitted) {
                        session.publish(RpcDeviceTestProgress(command.runId, "Starting ${command.phase.title}", true))
                        job.start()
                    } else job.cancel()
                }
            }
            cancellationListener = scope.launch {
                client.notifications(DeviceTestContract.cancel).collect { runId ->
                    if (session.activeTests.any { it.runId == runId }) cancel(runId)
                }
            }
        }
    }

    fun enableRemote(enabled: Boolean) { remoteEnabled.value = enabled && !closed.value }
    fun cancel(runId: String? = null) {
        if (runId == null || session.activeTests.any { it.runId == runId } && client != null) localJob.value?.cancel()
        hostJobs.value.filterKeys { runId == null || it == runId }.values.forEach(Job::cancel)
    }

    private fun admits(pin: PeerFingerprint, command: DeviceTestCommand): Boolean =
        !closed.value && !session.resultDeletionInProgress && host != null &&
            session.unarchivedReports.size + runs.size < 100 &&
            deviceTestAdmission(session.multiDeviceMode, runs.values.map { it.pin.value to it.command },
                pin.value, command)

    suspend fun observeBegin(context: RpcCallContext, begin: DeviceTestBegin): String? = lock.withLock {
        val pin = context.peer.fingerprint ?: return@withLock null
        if (closed.value || host == null || !validDeviceTestBegin(begin) ||
            begin.command.sourceSha != RpcPhoneLab.compiledSource) return@withLock null
        val existing = runs[begin.command.runId]
        if (existing != null) {
            if (existing.pin != pin || existing.command != begin.command ||
                !existing.acknowledged.isCompleted || existing.begin != null || begin.initiatedBy != "Host") {
                return@withLock null
            }
            existing.begin = begin
            publishBegin(begin)
            return@withLock session.platformName
        }
        if (begin.initiatedBy != "Client" || session.reports.any { it.runId == begin.command.runId } ||
            !admits(pin, begin.command)) return@withLock null
        val run = HostRun(pin, begin.command, session.history.entries().lastOrNull()?.localId ?: 0)
        val observer = scope.launch(start = CoroutineStart.LAZY) {
            try {
                awaitRemote(run)
            } catch (_: TimeoutCancellationException) {
                session.save(observedFailure(run, "Interrupted", "ClientResultNotReceived"))
            } catch (cancelled: CancellationException) {
                session.save(observedFailure(run, "Cancelled", "HostObservationCancelled"))
                throw cancelled
            } catch (_: Exception) {
                session.save(observedFailure(run, "Failed", "HostObservationFailed"))
            } finally {
                withContext(NonCancellable) {
                    try {
                        if (!run.result.isCompleted) host.tryNotify(pin, DeviceTestContract.cancel, begin.command.runId)
                    } finally { clearRun(run) }
                }
            }
        }
        run.job = observer
        run.begin = begin
        run.acknowledged.complete(Unit)
        runs[begin.command.runId] = run
        hostJobs.update { it + (begin.command.runId to observer) }
        session.beginResources(begin.command.runId)
        publishBegin(begin)
        observer.start()
        session.platformName
    }

    private fun publishBegin(begin: DeviceTestBegin) {
        session.publish(RpcDeviceTestProgress(begin.command.runId, begin.command.phase.title, true,
            direction = "${begin.clientPlatform} → ${session.platformName}", stage = "Client is initializing",
            startedAtEpochMillis = begin.startedAtEpochMillis))
    }

    suspend fun observeProgress(context: RpcCallContext, value: DeviceTestUpdate): Boolean = lock.withLock {
        val run = runs[value.command.runId] ?: return@withLock false
        val before = session.activeTests.firstOrNull { it.runId == value.command.runId }
        if (context.peer.fingerprint != run.pin || value.command != run.command || run.begin == null ||
            !validDeviceTestUpdate(value) || value.correctResponses < (before?.calls ?: 0) ||
            value.attempts < (before?.attempts ?: 0) || value.failures < (before?.failures ?: 0) ||
            value.elapsedSeconds < (before?.elapsedSeconds ?: 0)) return@withLock false
        session.publish(RpcDeviceTestProgress(value.command.runId, value.command.phase.title, true,
            value.correctResponses, value.elapsedSeconds, value.plannedSeconds,
            "${checkNotNull(run.begin).clientPlatform} → ${session.platformName}", "Client progress received",
            value.attempts, value.failures, value.p50Micros, value.p95Micros, value.p99Micros,
            value.targetRps, value.concurrency, value.inFlight, checkNotNull(run.begin).startedAtEpochMillis,
            session.resources(value.command.runId)))
        true
    }

    suspend fun telemetry(context: RpcCallContext, command: DeviceTestCommand): DeviceTestTelemetry? = lock.withLock {
        val run = runs[command.runId] ?: return@withLock null
        if (context.peer.fingerprint != run.pin || command != run.command || run.begin == null) return@withLock null
        DeviceTestTelemetry(session.resources(command.runId))
    }

    suspend fun reserveDeletion(runId: String): Boolean = lock.withLock {
        runs.isEmpty() && localJob.value == null && session.reserveDeletion(runId)
    }

    private fun hostObservations(run: HostRun): List<RpcDeviceTestObservation> = session.history.entries().filter {
        it.localId > run.historyStart && it.peerFingerprint == run.pin.value && it.procedure in deviceTestProcedures
    }.takeLast(16).map { it.testObservation() }

    private fun observedFailure(run: HostRun, status: String, code: String): RpcDeviceTestReport {
        val metadata = run.begin
        val resources = session.finishResources(run.command.runId)
        val thermal = resources?.thermalStopped == true
        val safety = session.safetyStopReason
        return emptyDeviceTestReport(run.command, if (thermal || safety != null) "Interrupted" else status,
            if (thermal) "ThermalStop" else safety ?: code).copy(clientPlatform = metadata?.clientPlatform ?: "Unknown",
            hostPlatform = session.platformName, startedAtEpochMillis = metadata?.startedAtEpochMillis ?: 0,
            endedAtEpochMillis = Clock.System.now().toEpochMilliseconds(),
            initiatedBy = metadata?.initiatedBy ?: "Host", observations = hostObservations(run),
            initiatingHostResources = resources)
    }

    private suspend fun awaitRemote(run: HostRun) {
        val report = withTimeout(if (run.command.phase == RpcDeviceTestPhase.Steady) 1_850_000 else
            if (run.command.phase == RpcDeviceTestPhase.Adaptive)
                (run.command.smartSettings?.maximumMillis ?: session.smartSettings.maximumMillis) + 35_000
            else 240_000) { run.result.await() }
        session.save(report.copy(initiatingHostResources = session.finishResources(run.command.runId),
            observations = (report.observations.takeLast(16) + hostObservations(run)).takeLast(32)))
    }

    private suspend fun clearRun(run: HostRun) {
        session.finishResources(run.command.runId)
        lock.withLock {
            if (runs[run.command.runId] === run) runs.remove(run.command.runId)
            hostJobs.update { it - run.command.runId }
        }
        session.finishProgress(run.command.runId)
    }

    suspend fun acknowledge(context: RpcCallContext, command: DeviceTestCommand): Boolean = lock.withLock {
        val run = runs[command.runId] ?: return@withLock false
        context.peer.fingerprint == run.pin && command == run.command && run.acknowledged.complete(Unit)
    }

    suspend fun receive(context: RpcCallContext, value: RpcDeviceTestReport): Boolean = lock.withLock {
        val run = runs[value.runId] ?: return@withLock false
        if (!run.acknowledged.isCompleted ||
            !matchesDeviceTestResult(context.peer.fingerprint?.value, run.pin.value,
                value, run.command, run.begin, session.platformName)) return@withLock false
        run.result.complete(value)
    }

    suspend fun run(phase: RpcDeviceTestPhase, selectedPeer: String?, groupId: String = "") {
        val command = DeviceTestCommand(newDeviceTestId(), RpcPhoneLab.compiledSource, phase,
            if (session.multiDeviceMode) "Multi" else "Pair", groupId,
            if (phase == RpcDeviceTestPhase.Adaptive) session.smartSettings else null)
        val job = checkNotNull(currentCoroutineContext()[Job])
        if (host == null) {
            lock.withLock {
                check(!closed.value && !session.resultDeletionInProgress && session.archiveAvailable &&
                    localJob.compareAndSet(null, job))
            }
            try { execute(command) } finally {
                localJob.compareAndSet(job, null)
                session.finishProgress(command.runId)
            }
            return
        }
        val pin = PeerFingerprint.parse(checkNotNull(selectedPeer))
        val run = HostRun(pin, command, session.history.entries().lastOrNull()?.localId ?: 0)
        run.job = job
        lock.withLock {
            check(admits(pin, command)) { "Host test slots busy" }
            runs[command.runId] = run
            hostJobs.update { it + (command.runId to job) }
        }
        try {
            session.publish(RpcDeviceTestProgress(command.runId, "Waiting for the selected client", true))
            check(host.tryNotify(pin, DeviceTestContract.start, command) == RpcNotifyResult.Enqueued)
            withTimeout(7_000) { run.acknowledged.await() }
            session.beginResources(command.runId)
            awaitRemote(run)
        } catch (_: TimeoutCancellationException) {
            session.save(observedFailure(run, "Failed", "ClientAcknowledgementOrResultTimeout"))
        } catch (cancelled: CancellationException) {
            session.save(observedFailure(run, "Cancelled", "CallerCancelled"))
            throw cancelled
        } catch (_: Exception) {
            session.save(observedFailure(run, "Failed", "ClientUnarmedBusyOrUnavailable"))
        } finally {
            withContext(NonCancellable) {
                try { if (!run.result.isCompleted) host.tryNotify(pin, DeviceTestContract.cancel, command.runId) }
                finally { clearRun(run) }
            }
        }
    }

    suspend fun runGroup(phase: RpcDeviceTestPhase, selectedPeers: List<String>) = coroutineScope {
        check(host != null && session.multiDeviceMode && selectedPeers.isNotEmpty() &&
            selectedPeers.size <= DEVICE_TEST_MAX_PARALLEL && selectedPeers.distinct().size == selectedPeers.size)
        val groupId = newDeviceTestId()
        selectedPeers.map { pin -> async { run(phase, pin, groupId) } }.forEach { it.await() }
    }

    private suspend fun execute(command: DeviceTestCommand, initiatedBy: String = "Client") {
        val peer = checkNotNull(client)
        val startedAt = Clock.System.now().toEpochMilliseconds()
        val historyStart = session.history.entries().lastOrNull()?.localId ?: 0
        var hostPlatform = "Unknown"
        var progressMessages = 0L
        var telemetryMessages = 0L
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
        var failedResponses = 0L
        var smartResult: RpcSmartTestResult? = null
        val remoteResources = MutableStateFlow<RpcDeviceTestResources?>(null)
        var failureStage = "Connecting"
        val seconds = if (command.phase == RpcDeviceTestPhase.Steady) 1_800L else 0L
        suspend fun echo(large: Boolean = false, size: Int = RpcCapacityContract.ENCODED_BYTES) {
            currentCoroutineContext().ensureActive()
            check(peer.state.value == RpcConnectionState.Ready)
            val payload = if (large) "a".repeat(size - 2) else RpcCapacityContract.payload
            val started = TimeSource.Monotonic.markNow()
            calls++
            session.publish(RpcDeviceTestProgress(command.runId, command.phase.title, true, correct,
                measured.elapsedNow().inWholeSeconds, seconds, "${session.platformName} → $hostPlatform",
                "Request sent; waiting for reply", attempts = calls, inFlight = 1, startedAtEpochMillis = startedAt))
            val reply = invoke(if (large) RpcCapacityContract.largeEcho else RpcCapacityContract.echo,
                payload, encodedBytes = size)
            check(reply is RpcReply.Success && reply.value == payload)
            correct++
            latencySamples++
            buckets[started.elapsedNow().inWholeMilliseconds.coerceIn(0, 30_000).toInt()]++
            session.publish(RpcDeviceTestProgress(command.runId, command.phase.title, true, correct,
                measured.elapsedNow().inWholeSeconds, seconds, "${session.platformName} → $hostPlatform",
                "Reply checked: content matches", attempts = calls,
                p50Micros = smartPercentile(buckets, latencySamples, 50),
                p95Micros = smartPercentile(buckets, latencySamples, 95),
                p99Micros = smartPercentile(buckets, latencySamples, 99), startedAtEpochMillis = startedAt))
        }
        try {
            session.publish(RpcDeviceTestProgress(command.runId, "Checking connected source", true))
            withTimeout(30_000) { peer.state.first { it == RpcConnectionState.Ready } }
            val source = invoke(DeviceTestContract.source, "source")
            failureStage = "SourceMismatch"
            check(source is RpcReply.Success && source.value == command.sourceSha)
            failureStage = "HostBusyOrTestModeMismatch"
            val begin = invoke(DeviceTestContract.begin,
                DeviceTestBegin(command, session.platformName, startedAt, initiatedBy))
            check(begin is RpcReply.Success && begin.value in deviceTestPlatforms)
            hostPlatform = begin.value
            initializationMillis = initialization.elapsedNow().inWholeMilliseconds
            measured = TimeSource.Monotonic.markNow()
            initialized = true
            failureStage = "ResponseCorrectnessFailure"
            session.beginResources(command.runId)
            session.publish(RpcDeviceTestProgress(command.runId, command.phase.title, true, plannedSeconds = seconds,
                direction = "${session.platformName} → $hostPlatform", stage = "Source matched; workload starting"))
            progressWriter = scope.launch {
                while (true) {
                    delay(1_000)
                    val snapshot = session.activeTests.firstOrNull { it.runId == command.runId }
                    if (snapshot != null && snapshot.running &&
                        peer.state.value == RpcConnectionState.Ready
                    ) {
                        try {
                            val received = peer.call(DeviceTestContract.progress,
                                DeviceTestUpdate(command, snapshot.calls, snapshot.elapsedSeconds, seconds,
                                    snapshot.attempts, snapshot.failures, snapshot.p50Micros, snapshot.p95Micros,
                                    snapshot.p99Micros, snapshot.targetRps, snapshot.concurrency, snapshot.inFlight),
                                timeout = 1_000.milliseconds, retry = RpcRetry.RecoverOnly(1))
                            if (received is RpcReply.Success) progressMessages++
                            val telemetry = peer.call(DeviceTestContract.telemetry, command,
                                timeout = 1_000.milliseconds, retry = RpcRetry.RecoverOnly(1))
                            if (telemetry is RpcReply.Success && validDeviceResources(telemetry.value.resources)) {
                                telemetryMessages++
                                remoteResources.value = telemetry.value.resources
                            }
                        } catch (_: Exception) { /* No progress retry or extension of workload bounds. */ }
                    }
                }
            }
            when (command.phase) {
                RpcDeviceTestPhase.Adaptive -> {
                    val output = runSmartTest(command.smartSettings ?: session.smartSettings, call = {
                        val started = TimeSource.Monotonic.markNow()
                        try {
                            if (peer.state.value != RpcConnectionState.Ready) SmartCall(false, 0,
                                fatal = "ConnectionNotReady") else {
                                val reply = invoke(RpcCapacityContract.echo, RpcCapacityContract.payload,
                                    encodedBytes = RpcCapacityContract.ENCODED_BYTES, timeout = 2_000.milliseconds)
                                val correctReply = reply is RpcReply.Success && reply.value == RpcCapacityContract.payload
                                SmartCall(correctReply, started.elapsedNow().inWholeMicroseconds,
                                fatal = if (correctReply) null else "ResponseCorruptionOrRejection")
                            }
                        } catch (cancelled: CancellationException) { throw cancelled }
                        catch (failure: RpcFailure) {
                            SmartCall(false, started.elapsedNow().inWholeMicroseconds,
                                timeout = failure.kind == RpcFailureKind.DeadlineExceeded,
                                fatal = if (failure.kind in setOf(RpcFailureKind.DeadlineExceeded,
                                        RpcFailureKind.Overloaded)) null else
                                    "ConnectionFailure/${failure.kind.name}")
                        }
                    }, clientResources = { session.resources(command.runId) },
                        hostResources = { remoteResources.value }, progress = { level, counters, stage ->
                            session.publish(RpcDeviceTestProgress(command.runId, command.phase.title, true,
                                counters.totalCorrect, measured.elapsedNow().inWholeSeconds, 0,
                                "${session.platformName} → $hostPlatform", stage, counters.totalAttempts,
                                counters.totalFailures, smartPercentile(counters.buckets, counters.correct, 50),
                                smartPercentile(counters.buckets, counters.correct, 95),
                                smartPercentile(counters.buckets, counters.correct, 99), level.rps,
                                level.concurrency, counters.inFlight, startedAt, remoteResources.value))
                        })
                    calls = output.attempts
                    correct = output.correct
                    failedResponses = output.failures
                    missed = output.missed
                    output.buckets.copyInto(buckets)
                    latencySamples = output.correct
                    smartResult = output.result
                    if (!output.result.stableLevelConfirmed) {
                        status = if (output.result.stopReason == "CallerCancelled") "Cancelled" else "Interrupted"
                        failureCode = output.result.stopReason
                    }
                }
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
            failureCode = failureStage
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
            session.safetyStopReason?.let { reason ->
                status = "Interrupted"
                failureCode = reason
                smartResult = smartResult?.copy(stopReason = reason)
            }
            val report = RpcDeviceTestReport(command.runId, command.phase, command.sourceSha, status, calls, correct,
                if (initialized) measured.elapsedNow().inWholeMilliseconds else 0,
                if (initialized) initializationMillis else initialization.elapsedNow().inWholeMilliseconds, missed,
                percentile(95), percentile(99), disconnects, deadlines, cancellations, failureCode,
                latencySamples = latencySamples, clientResources = resources, clientPlatform = session.platformName,
                hostPlatform = hostPlatform, startedAtEpochMillis = startedAt, initiatedBy = initiatedBy,
                endedAtEpochMillis = Clock.System.now().toEpochMilliseconds(), mode = command.mode,
                groupId = command.groupId, p50Micros = percentile(50), failedResponses = failedResponses,
                smart = smartResult,
                observations = session.history.entries().filter {
                    it.localId > historyStart && it.procedure in deviceTestProcedures
                }.takeLast(if (smartResult == null) 32 else 8).map { it.testObservation() },
                progressMessages = progressMessages, telemetryMessages = telemetryMessages)
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
        localJob.value?.cancelAndJoin()
        hostJobs.value.values.toList().forEach { it.cancelAndJoin() }
        session.release(this)
    }
}

internal fun validDeviceTestCommand(command: DeviceTestCommand): Boolean =
    command.runId.matches(Regex("[a-f0-9]{32}")) && command.sourceSha.matches(Regex("[a-f0-9]{40}")) &&
        command.mode in setOf("Pair", "Multi") &&
        (command.groupId.isEmpty() || command.mode == "Multi" && command.groupId.matches(Regex("[a-f0-9]{32}"))) &&
        (command.smartSettings == null || command.phase == RpcDeviceTestPhase.Adaptive && command.smartSettings.valid())

internal fun newDeviceTestId(): String = Random.nextBytes(16).joinToString("") {
    it.toUByte().toString(16).padStart(2, '0')
}

internal fun deviceTestAdmission(multiEnabled: Boolean, active: List<Pair<String, DeviceTestCommand>>,
    peer: String, command: DeviceTestCommand): Boolean = validDeviceTestCommand(command) &&
    active.size < DEVICE_TEST_MAX_PARALLEL && active.none { it.first == peer || it.second.runId == command.runId } &&
    if (command.mode == "Pair") active.isEmpty() else multiEnabled && active.all { it.second.mode == "Multi" }

internal fun validDeviceTestBegin(value: DeviceTestBegin): Boolean =
    validDeviceTestCommand(value.command) && value.clientPlatform in deviceTestPlatforms &&
        value.clientPlatform != "Unknown" && value.startedAtEpochMillis in 1..4_102_444_800_000 &&
        value.initiatedBy in setOf("Host", "Client")

internal fun validDeviceTestUpdate(value: DeviceTestUpdate): Boolean =
    validDeviceTestCommand(value.command) && value.correctResponses in 0..1_000_000 &&
        value.elapsedSeconds in 0..1_850 &&
        value.attempts in value.correctResponses..1_000_000 && value.failures in 0..value.attempts &&
        value.p50Micros in 0..value.p95Micros && value.p95Micros in 0..value.p99Micros &&
        value.p99Micros in 0..30_001_000 && value.targetRps in 0..5_000 && value.concurrency in 1..64 &&
        value.inFlight in 0..value.concurrency &&
        value.plannedSeconds == (if (value.command.phase == RpcDeviceTestPhase.Steady) 1_800L else 0L)

internal fun matchesObservedMetadata(
    report: RpcDeviceTestReport, begin: DeviceTestBegin?, hostPlatform: String,
): Boolean =
    begin != null && report.clientPlatform == begin.clientPlatform && report.hostPlatform == hostPlatform &&
        report.startedAtEpochMillis == begin.startedAtEpochMillis && report.initiatedBy == begin.initiatedBy

internal fun matchesDeviceTestResult(receivedPeer: String?, expectedPeer: String, report: RpcDeviceTestReport,
    command: DeviceTestCommand, begin: DeviceTestBegin?, hostPlatform: String): Boolean =
    receivedPeer == expectedPeer && report.runId == command.runId && report.phase == command.phase &&
        report.sourceSha == command.sourceSha && report.mode == command.mode && report.groupId == command.groupId &&
        (command.smartSettings == null || report.smart?.settings == command.smartSettings ||
            report.status != "Completed" && report.calls == 0L && report.smart == null) &&
        validDeviceTestReport(report) &&
        matchesObservedMetadata(report, begin, hostPlatform)

internal fun validDeviceTestReport(value: RpcDeviceTestReport): Boolean =
    validDeviceTestCommand(DeviceTestCommand(value.runId, value.sourceSha, value.phase, value.mode, value.groupId)) &&
        value.clientPlatform in deviceTestPlatforms && value.hostPlatform in deviceTestPlatforms &&
        value.startedAtEpochMillis in 0..4_102_444_800_000 && value.initiatedBy in setOf("Host", "Client") &&
        value.endedAtEpochMillis in 0..4_102_444_800_000 &&
        (value.endedAtEpochMillis == 0L || value.endedAtEpochMillis >= value.startedAtEpochMillis) &&
        value.p50Micros in 0..value.p95Micros && validSmartResult(value.smart) &&
        (value.smart == null || value.phase == RpcDeviceTestPhase.Adaptive) &&
        value.observations.size <= 32 && value.observations.all(::validTestObservation) &&
        value.progressMessages in 0..1_850 &&
        value.telemetryMessages in 0..1_850 &&
        validDeviceResources(value.clientResources) && validDeviceResources(value.initiatingHostResources) &&
        value.scope == "INTERACTIVE_CONNECTED_DEVICE_RPC" && value.measuredClientCount == 1 &&
        value.latencySamples in 0..value.correctResponses && value.latencyBucketMicros == 1_000 &&
        value.status in setOf("Completed", "Failed", "Cancelled", "Interrupted") &&
        value.calls in 0..(if (value.phase == RpcDeviceTestPhase.Adaptive) 1_000_000 else 100_000) &&
        value.correctResponses in 0..value.calls && value.failedResponses in 0..(value.calls - value.correctResponses) &&
        value.elapsedMillis in 0..1_850_000 && value.initializationMillis in 0..1_850_000 &&
        value.missedSchedules in 0..(if (value.phase == RpcDeviceTestPhase.Adaptive) 1_000_000 else 18_500) &&
        value.p95Micros in 0..30_001_000 &&
        value.p99Micros in value.p95Micros..30_001_000 && value.deliberateDisconnects in 0..5 &&
        value.expectedDeadlines in 0..1 && value.callerCancellations in 0..1 &&
        (value.failureCode?.length ?: 0) <= 128 &&
        (value.status != "Completed" || value.phase == RpcDeviceTestPhase.Adaptive &&
            value.smart?.stableLevelConfirmed == true && value.smart.workerCleanupVerified &&
            value.calls == value.correctResponses + value.failedResponses ||
            (value.status == "Completed" && value.phase != RpcDeviceTestPhase.Adaptive &&
            value.correctResponses == value.calls && value.calls >= when (value.phase) {
            RpcDeviceTestPhase.Large -> 3
            RpcDeviceTestPhase.Correctness -> 12
            RpcDeviceTestPhase.Reconnect -> 5
            RpcDeviceTestPhase.Steady, RpcDeviceTestPhase.Deadlines -> 1
            RpcDeviceTestPhase.Adaptive -> 1
        })) &&
        (value.status != "Completed" || value.phase != RpcDeviceTestPhase.Steady || value.elapsedMillis >= 1_800_000)

internal fun emptyDeviceTestReport(command: DeviceTestCommand, status: String, failure: String): RpcDeviceTestReport =
    RpcDeviceTestReport(command.runId, command.phase, command.sourceSha, status, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, failure,
        mode = command.mode, groupId = command.groupId)
