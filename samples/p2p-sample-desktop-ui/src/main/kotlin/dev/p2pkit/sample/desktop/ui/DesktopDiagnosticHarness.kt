package dev.p2pkit.sample.desktop.ui

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
import java.net.InetAddress

internal class DesktopDiagnosticHarness(
    private val onEvent: () -> Unit
) {
    private val home = File(System.getProperty("user.home") ?: ".")
    private val rolling = RollingJsonlFileSink(File(home, ".p2pkit/desktop-ui-test-diagnostics"))

    val recorder = DiagnosticRecorder(
        environment = DiagnosticEnvironment(
            platform = "desktop-ui",
            operatingSystem = "${System.getProperty("os.name")} ${System.getProperty("os.version")}",
            applicationVersion = System.getProperty("p2pkit.sample.appVersion") ?: "development",
            buildNumber = BuildInfo.COMMIT_SHORT,
            gitCommitSha = BuildInfo.COMMIT,
            safeDeviceId = anonymizeIdentifier(
                "desktop:${System.getProperty("user.home")}:${runCatching {
                    InetAddress.getLocalHost().hostName
                }.getOrDefault("host")}"
            )
        ),
        configuration = DiagnosticConfiguration(
            protocolVersion = "secure-v2",
            timeoutsMillis = mapOf("keepAlive" to 6_000L, "durableCommit" to 30_000L),
            retryValues = mapOf("configuredInSetup" to 1L),
            packetLimits = mapOf(
                "sampleReceiveQuotaBytes" to 50L * 1024L * 1024L,
                "diagnosticEvents" to 5_000L,
                "diagnosticBytes" to 5L * 1024L * 1024L
            ),
            faultInjection = mapOf("enabled" to "false"),
            values = mapOf("testMode" to "true")
        ),
        eventSink = { json ->
            try {
                rolling(json)
            } finally {
                onEvent()
            }
        }
    )

    private val correlations = DiagnosticCorrelationRegistry(
        activeSessionId = { recorder.activeSessionId }
    )

    @Volatile
    var localPeerId: String? = null
        set(value) {
            field = value
            correlations.setLocalPeerId(value)
        }
    @Volatile
    var latestTransferId: String? = null

    init {
        recorder.startSession("PS-T06", "both")
        recorder.record(
            DiagnosticRecord(
                category = "application",
                eventName = DiagnosticEventNames.APPLICATION_STARTED,
                currentState = "started",
                details = mapOf("testMode" to "true")
            )
        )
    }

    fun startSession(
        testId: String,
        role: String,
        sessionId: String?,
        activeConnections: List<DesktopDiagnosticConnectionSnapshot> = emptyList()
    ): String =
        recorder.startSession(testId, role, sessionId).also {
            correlations.resetSession()
            latestTransferId = null
            activeConnections.forEach { connection ->
                val correlation = correlations.registerConnection(
                    connection.sessionId,
                    connection.peerId
                )
                recorder.record(
                    DiagnosticRecord(
                        peerId = connection.peerId,
                        connectionId = correlation?.connectionId,
                        category = "connection",
                        eventName = DiagnosticEventNames.CONNECTION_STATE_CHANGED,
                        currentState = connection.state,
                        details = mapOf("sessionSnapshot" to "true")
                    )
                )
            }
            recorder.record(
                DiagnosticRecord(
                    category = "test",
                    eventName = DiagnosticEventNames.TEST_MODE_ACTIVATED,
                    currentState = "enabled"
                )
            )
        }

    fun logger(delegate: P2pLogger): P2pLogger =
        StructuredSdkLogger(recorder, delegate)

    fun frame(line: String) = StructuredFrameTrace.record(
        recorder = recorder,
        line = line,
        correlationForTransfer = correlations::correlationForTransfer
    )

    fun transport(line: String) {
        recorder.record(
            DiagnosticRecord(
                category = "transport",
                eventName = DiagnosticEventNames.TRANSPORT_LOG,
                details = mapOf("line" to line)
            )
        )
    }

    fun connection(
        sessionId: String,
        peerId: String,
        state: String,
        previous: String? = null
    ): String? {
        val connection = correlations.registerConnection(sessionId, peerId)?.connectionId
        recorder.record(
            DiagnosticRecord(
                peerId = peerId,
                connectionId = connection,
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
                    connectionId = connection,
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
        return connection
    }

    fun connectionIdFor(peerId: String): String? = correlations.connectionForPeer(peerId)?.connectionId

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

    fun hash(peerId: String, transferId: String, size: Long, digest: String, receiver: Boolean) {
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

    fun complete(outcome: DiagnosticOutcome) {
        recorder.completeSession(outcome, "operator selected ${outcome.name}", outcome.name)
    }

    fun summary() = recorder.summary(selectedTransferId = latestTransferId)

    fun export(): File = DiagnosticEvidenceExporter.export(
        recorder,
        File(home, ".p2pkit/test-evidence"),
        additionalFiles = rolling.evidenceFiles(recorder.activeSessionId)
    )

    fun clearCurrent(): Int {
        val sessionId = recorder.activeSessionId
        val removed = recorder.clearCurrentSession()
        rolling.clearSession(sessionId)
        return removed
    }

    fun shutdown() {
        recorder.record(
            DiagnosticRecord(
                category = "application",
                eventName = DiagnosticEventNames.APPLICATION_SHUTDOWN,
                currentState = "window-closed"
            )
        )
        correlations.resetSession()
    }
}

internal data class DesktopDiagnosticConnectionSnapshot(
    val sessionId: String,
    val peerId: String,
    val state: String
)
