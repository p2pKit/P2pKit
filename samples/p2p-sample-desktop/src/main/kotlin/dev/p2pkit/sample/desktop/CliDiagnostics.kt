package dev.p2pkit.sample.desktop

import dev.p2pkit.core.BuildInfo
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.sample.diagnostics.DiagnosticConfiguration
import dev.p2pkit.sample.diagnostics.DiagnosticCorrelationRegistry
import dev.p2pkit.sample.diagnostics.DiagnosticDirection
import dev.p2pkit.sample.diagnostics.DiagnosticEnvironment
import dev.p2pkit.sample.diagnostics.DiagnosticEventNames
import dev.p2pkit.sample.diagnostics.DiagnosticEvidenceExporter
import dev.p2pkit.sample.diagnostics.DiagnosticOutcome
import dev.p2pkit.sample.diagnostics.DiagnosticRecord
import dev.p2pkit.sample.diagnostics.DiagnosticRecorder
import dev.p2pkit.sample.diagnostics.RollingJsonlFileSink
import dev.p2pkit.sample.diagnostics.StructuredFrameTrace
import dev.p2pkit.sample.diagnostics.StructuredSdkLogger
import dev.p2pkit.sample.diagnostics.anonymizeIdentifier
import java.io.File
import java.io.FileOutputStream
import java.net.InetAddress

/**
 * Process-local CLI diagnostic owner. `diag` commands and the optional
 * `log=<file>` argument expose structured JSONL without requiring a log
 * collector or IDE console.
 */
internal object CliDiagnostics {
    lateinit var recorder: DiagnosticRecorder
        private set
    private lateinit var rolling: RollingJsonlFileSink
    private lateinit var evidenceDirectory: File
    private lateinit var correlations: DiagnosticCorrelationRegistry
    private var directJsonl: File? = null
    private var configured = false
    private val directLock = Any()

    @Volatile
    var latestTransferId: String? = null
    @Volatile
    var localPeerId: String? = null
        set(value) {
            field = value
            if (::correlations.isInitialized) correlations.setLocalPeerId(value)
        }

    fun connectionIdFor(peerId: String): String? =
        correlations.connectionForPeer(peerId)?.connectionId

    fun configure(options: CliLaunchOptions) {
        val home = File(System.getProperty("user.home") ?: ".")
        rolling = RollingJsonlFileSink(File(home, ".p2pkit/test-diagnostics"))
        evidenceDirectory = File(
            options.evidenceDirectory ?: File(home, ".p2pkit/test-evidence").path
        )
        directJsonl = options.jsonlFile?.let(::File)
        recorder = DiagnosticRecorder(
            environment = DiagnosticEnvironment(
                platform = "jvm-cli",
                operatingSystem = "${System.getProperty("os.name")} ${System.getProperty("os.version")}",
                applicationVersion = System.getProperty("p2pkit.sample.appVersion") ?: "development",
                buildNumber = BuildInfo.COMMIT_SHORT,
                gitCommitSha = BuildInfo.COMMIT,
                safeDeviceId = anonymizeIdentifier(
                    "jvm:${System.getProperty("user.home")}:${runCatching {
                        InetAddress.getLocalHost().hostName
                    }.getOrDefault("host")}"
                )
            ),
            configuration = DiagnosticConfiguration(
                protocolVersion = "secure-v2",
                timeoutsMillis = mapOf("keepAlive" to 6_000L, "durableCommit" to 30_000L),
                retryValues = mapOf("configuredByLaunch" to 1L),
                packetLimits = mapOf("sampleReceiveQuotaBytes" to 50L * 1024L * 1024L),
                faultInjection = mapOf("enabled" to "false"),
                values = mapOf("testMode" to "true")
            ),
            eventSink = { line ->
                runCatching { rolling(line) }
                directJsonl?.let { file ->
                    runCatching {
                        synchronized(directLock) {
                            file.parentFile?.mkdirs()
                            if (file.exists() && file.length() + line.toByteArray().size + 1 > 2L * 1024L * 1024L) {
                                val rotated = File(file.parentFile, "${file.name}.1")
                                rotated.delete()
                                file.renameTo(rotated)
                            }
                            FileOutputStream(file, true).bufferedWriter().use { writer ->
                                writer.appendLine(line)
                            }
                        }
                    }
                }
            }
        )
        correlations = DiagnosticCorrelationRegistry(
            activeSessionId = { recorder.activeSessionId }
        )
        correlations.setLocalPeerId(localPeerId)
        recorder.startSession(
            options.testId ?: "PS-T05",
            options.role ?: "both",
            options.sessionId
        )
        recorder.record(
            DiagnosticRecord(
                category = "application",
                eventName = DiagnosticEventNames.APPLICATION_STARTED,
                currentState = "started",
                details = mapOf(
                    "testMode" to "true",
                    "directJsonl" to (directJsonl != null).toString()
                )
            )
        )
        configured = true
    }

    fun logger(delegate: P2pLogger = StdErrLogger): P2pLogger =
        StructuredSdkLogger(recorder = recorder, delegate = delegate)

    fun frame(line: String) {
        if (!configured) return
        StructuredFrameTrace.record(
            recorder = recorder,
            line = line,
            correlationForTransfer = correlations::correlationForTransfer
        )
    }

    fun transport(line: String) {
        if (!configured) return
        recorder.record(
            DiagnosticRecord(
                category = "transport",
                eventName = DiagnosticEventNames.TRANSPORT_LOG,
                severity = if ("warn" in line.lowercase() || "error" in line.lowercase()) {
                    dev.p2pkit.sample.diagnostics.DiagnosticSeverity.WARNING
                } else {
                    dev.p2pkit.sample.diagnostics.DiagnosticSeverity.DEBUG
                },
                details = mapOf("line" to line)
            )
        )
    }

    fun connection(sessionId: String, peerId: String, state: String, previous: String? = null) {
        val connectionId = correlations.registerConnection(sessionId, peerId)?.connectionId
        recorder.record(
            DiagnosticRecord(
                peerId = peerId,
                connectionId = connectionId,
                category = "connection",
                eventName = DiagnosticEventNames.CONNECTION_STATE_CHANGED,
                previousState = previous,
                currentState = state,
                outcome = when (state) {
                    "Connected" -> DiagnosticOutcome.SUCCESS
                    "Reconnecting" -> DiagnosticOutcome.INTERRUPTION
                    "Failed" -> DiagnosticOutcome.FAILURE
                    "Closed" -> DiagnosticOutcome.CANCELLATION
                    else -> null
                }
            )
        )
        if (state == "Connected") {
            recorder.record(
                DiagnosticRecord(
                    peerId = peerId,
                    connectionId = connectionId,
                    category = "protocol",
                    eventName = DiagnosticEventNames.PROTOCOL_NEGOTIATED,
                    currentState = "secure-v2",
                    details = mapOf("feature" to "file-commit-sha256-v1")
                )
            )
        }
        if (state == "Closed" || state == "Failed") {
            correlations.removeConnection(sessionId)
        }
    }

    fun transfer(
        peerId: String,
        transferId: String,
        eventName: String,
        state: String? = null,
        size: Long? = null,
        direction: DiagnosticDirection = DiagnosticDirection.LOCAL,
        outcome: DiagnosticOutcome? = null,
        error: Throwable? = null,
        details: Map<String, String> = emptyMap()
    ) {
        val correlation = correlations.registerTransfer(transferId, peerId)
        latestTransferId = transferId
        recorder.record(
            DiagnosticRecord(
                peerId = peerId,
                connectionId = correlation?.connectionId,
                transferId = transferId,
                category = "transfer",
                eventName = eventName,
                currentState = state,
                payloadSizeBytes = size,
                direction = direction,
                outcome = outcome,
                errorCode = error?.javaClass?.simpleName?.uppercase(),
                errorDescription = error?.message,
                details = details
            )
        )
    }

    fun fileHash(peerId: String, transferId: String, size: Long, digest: String, receiver: Boolean) {
        val correlation = correlations.registerTransfer(transferId, peerId)
        recorder.record(
            DiagnosticRecord(
                peerId = peerId,
                connectionId = correlation?.connectionId,
                transferId = transferId,
                category = "file",
                eventName = if (receiver) {
                    DiagnosticEventNames.FILE_RECEIVER_HASH
                } else {
                    DiagnosticEventNames.FILE_SENDER_HASH
                },
                payloadSizeBytes = size,
                direction = if (receiver) DiagnosticDirection.RECEIVED else DiagnosticDirection.SENT,
                details = mapOf("sha256" to digest)
            )
        )
    }

    fun export(): File = DiagnosticEvidenceExporter.export(
        recorder = recorder,
        directory = evidenceDirectory,
        additionalFiles = rolling.evidenceFiles(recorder.activeSessionId)
    )

    fun clearCurrent() {
        val session = recorder.activeSessionId
        recorder.clearCurrentSession()
        rolling.clearSession(session)
        directJsonl?.let { file ->
            synchronized(directLock) {
                if (file.exists()) {
                    val retained = file.readLines().filterNot { "\"testSessionId\":\"$session\"" in it }
                    file.writeText(if (retained.isEmpty()) "" else retained.joinToString("\n") + "\n")
                }
            }
        }
    }

    fun startSession(testId: String, role: String, sessionId: String?): String =
        recorder.startSession(testId, role, sessionId).also {
            correlations.resetSession()
            latestTransferId = null
        }

    fun complete(outcome: DiagnosticOutcome, reason: String) {
        recorder.completeSession(outcome, reason, outcome.name)
    }

    fun close() {
        if (!configured) return
        recorder.record(
            DiagnosticRecord(
                category = "application",
                eventName = DiagnosticEventNames.APPLICATION_SHUTDOWN,
                currentState = "stopping"
            )
        )
        runCatching { export() }
        correlations.resetSession()
    }

    fun helpLine(): String =
        "diag [start <TEST-ID> [session] [role] | status | export | " +
            "fault <type> [expected-effect] | " +
            "complete <success|failure|cancelled|timeout|interrupted|recovered> | clear]"
}
