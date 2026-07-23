package dev.p2pkit.sample.diagnostics

import java.io.File

/**
 * Generates clearly marked synthetic packages that demonstrate the evidence
 * format. They are examples only and are never external-validation evidence.
 */
public fun main(args: Array<String>) {
    val output = File(args.singleOrNull() ?: error("usage: <output-directory>"))
    for (platform in listOf("android", "ios", "jvm-cli", "desktop-ui")) {
        generateExample(output, platform, succeeds = true)
        generateExample(output, platform, succeeds = false)
    }
    println(output.absolutePath)
}

private fun generateExample(output: File, platform: String, succeeds: Boolean) {
    val recorder = DiagnosticRecorder(
        environment = DiagnosticEnvironment(
            platform = platform,
            operatingSystem = "synthetic-os",
            applicationVersion = "example",
            buildNumber = "example",
            gitCommitSha = "0000000000000000000000000000000000000000",
            safeDeviceId = "synthetic-$platform"
        ),
        configuration = DiagnosticConfiguration(
            protocolVersion = "secure-v2",
            timeoutsMillis = mapOf("commit" to 30_000L),
            retryValues = mapOf("maxAttempts" to 5L),
            values = mapOf("syntheticExample" to "true")
        ),
        timestamp = {
            if (succeeds) "2026-07-23T15:45:00.000Z" else "2026-07-23T15:46:00.000Z"
        },
        idFactory = {
            if (succeeds) "session-example-success" else "session-example-failed"
        }
    )
    recorder.startSession(
        testId = "EXAMPLE-XFER",
        role = "sender",
        requestedSessionId = if (succeeds) "session-example-success" else "session-example-failed"
    )
    val connection = correlationConnectionId(
        recorder.activeSessionId,
        "synthetic-local",
        "synthetic-remote"
    )
    val transfer = if (succeeds) "xfer-example-success" else "xfer-example-failed"
    recorder.record(
        DiagnosticRecord(
            peerId = "synthetic-remote",
            connectionId = connection,
            category = "connection",
            eventName = DiagnosticEventNames.CONNECTION_AUTHENTICATED,
            currentState = "Connected",
            previousState = "Handshaking",
            outcome = DiagnosticOutcome.SUCCESS
        )
    )
    recorder.record(
        DiagnosticRecord(
            peerId = "synthetic-remote",
            connectionId = connection,
            transferId = transfer,
            category = "file",
            eventName = DiagnosticEventNames.FILE_SENDER_HASH,
            payloadSizeBytes = 204_800L,
            details = mapOf(
                "sha256" to "4b7f9e2f9f4ec9db45929d5f0b86a4b25076b44ba540c5f273fa7d9a479a6838",
                "synthetic" to "true"
            )
        )
    )
    if (succeeds) {
        recorder.record(
            DiagnosticRecord(
                peerId = "synthetic-remote",
                connectionId = connection,
                transferId = transfer,
                category = "transfer",
                eventName = DiagnosticEventNames.TRANSFER_DURABLE_COMMITTED,
                currentState = "Completed",
                direction = DiagnosticDirection.RECEIVED,
                packetType = "FILE_COMMIT",
                outcome = DiagnosticOutcome.SUCCESS
            )
        )
        recorder.record(
            DiagnosticRecord(
                peerId = "synthetic-remote",
                connectionId = connection,
                transferId = transfer,
                category = "file",
                eventName = DiagnosticEventNames.FILE_RECEIVER_HASH,
                payloadSizeBytes = 204_800L,
                details = mapOf(
                    "sha256" to "4b7f9e2f9f4ec9db45929d5f0b86a4b25076b44ba540c5f273fa7d9a479a6838",
                    "synthetic" to "true"
                )
            )
        )
        recorder.record(
            DiagnosticRecord(
                connectionId = connection,
                transferId = transfer,
                category = "file",
                eventName = DiagnosticEventNames.FILE_INTEGRITY_CHECKED,
                currentState = "match",
                outcome = DiagnosticOutcome.SUCCESS,
                details = mapOf("match" to "true", "synthetic" to "true")
            )
        )
        recorder.completeSession(DiagnosticOutcome.SUCCESS, "synthetic successful transfer", "Completed")
    } else {
        recorder.record(
            DiagnosticRecord(
                peerId = "synthetic-remote",
                connectionId = connection,
                transferId = transfer,
                category = "transfer",
                eventName = DiagnosticEventNames.TRANSFER_FAILED,
                severity = DiagnosticSeverity.ERROR,
                currentState = "Failed",
                previousState = "Sending",
                errorCode = "DIGEST_MISMATCH",
                errorDescription = "Synthetic receiver digest mismatch",
                outcome = DiagnosticOutcome.FAILURE,
                details = mapOf("synthetic" to "true")
            )
        )
        recorder.completeSession(DiagnosticOutcome.FAILURE, "synthetic intentional failure", "Failed")
    }
    DiagnosticEvidenceExporter.export(recorder, output)
}
