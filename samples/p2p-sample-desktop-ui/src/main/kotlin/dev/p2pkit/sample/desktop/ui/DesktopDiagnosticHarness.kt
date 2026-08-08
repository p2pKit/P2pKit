package dev.p2pkit.sample.desktop.ui

import dev.p2pkit.core.BuildInfo
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.sample.diagnostics.DiagnosticConfiguration
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
import dev.p2pkit.sample.diagnostics.correlationConnectionId
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

    @Volatile
    var localPeerId: String = "local"
    @Volatile
    var latestPeerId: String? = null
    @Volatile
    var latestConnectionId: String? = null
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

    fun startSession(testId: String, role: String, sessionId: String?): String =
        recorder.startSession(testId, role, sessionId).also {
            recorder.record(
                DiagnosticRecord(
                    category = "test",
                    eventName = DiagnosticEventNames.TEST_MODE_ACTIVATED,
                    currentState = "enabled"
                )
            )
        }

    fun logger(delegate: P2pLogger): P2pLogger =
        StructuredSdkLogger(
            recorder,
            delegate,
            context = { Triple(latestPeerId, latestConnectionId, latestTransferId) }
        )

    fun frame(line: String) = StructuredFrameTrace.record(recorder, line, latestConnectionId)

    fun transport(line: String) {
        recorder.record(
            DiagnosticRecord(
                category = "transport",
                eventName = DiagnosticEventNames.TRANSPORT_LOG,
                details = mapOf("line" to line)
            )
        )
    }

    fun connection(peerId: String, state: String, previous: String? = null): String {
        val connection = correlationConnectionId(recorder.activeSessionId, localPeerId, peerId)
        latestPeerId = peerId
        latestConnectionId = connection
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
        return connection
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
        latestPeerId = peerId
        latestTransferId = transferId
        recorder.record(
            DiagnosticRecord(
                peerId = peerId,
                connectionId = latestConnectionId,
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

    fun hash(peerId: String, transferId: String?, size: Long, digest: String, receiver: Boolean) {
        recorder.record(
            DiagnosticRecord(
                peerId = peerId,
                connectionId = latestConnectionId,
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

    fun export(): File = DiagnosticEvidenceExporter.export(
        recorder,
        File(home, ".p2pkit/test-evidence"),
        additionalFiles = rolling.evidenceFiles()
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
    }
}
