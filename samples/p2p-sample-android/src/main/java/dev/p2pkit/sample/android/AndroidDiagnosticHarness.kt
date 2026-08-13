package dev.p2pkit.sample.android

import android.content.Context
import android.os.Build
import android.provider.Settings
import androidx.core.content.edit
import dev.p2pkit.core.BuildInfo
import dev.p2pkit.sample.diagnostics.DiagnosticConfiguration
import dev.p2pkit.sample.diagnostics.DiagnosticCorrelation
import dev.p2pkit.sample.diagnostics.DiagnosticCorrelationRegistry
import dev.p2pkit.sample.diagnostics.DiagnosticEnvironment
import dev.p2pkit.sample.diagnostics.DiagnosticEventNames
import dev.p2pkit.sample.diagnostics.DiagnosticEvidenceExporter
import dev.p2pkit.sample.diagnostics.DiagnosticOutcome
import dev.p2pkit.sample.diagnostics.DiagnosticRecord
import dev.p2pkit.sample.diagnostics.DiagnosticRecorder
import dev.p2pkit.sample.diagnostics.RollingJsonlFileSink
import dev.p2pkit.sample.diagnostics.anonymizeIdentifier
import java.io.File

/**
 * Explicit test-mode diagnostics owner for the Android sample. Only redacted
 * JSONL is persisted, under a bounded four-file rotation in no-backup storage.
 */
internal class AndroidDiagnosticHarness(
    context: Context,
    onEvent: () -> Unit
) {
    private val appContext = context.applicationContext
    private val preferences = appContext.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
    private val rollingSink = RollingJsonlFileSink(
        File(appContext.noBackupFilesDir, "test-diagnostics"),
        maxBytes = 2L * 1024L * 1024L,
        maxFiles = 4
    )

    val recorder: DiagnosticRecorder = DiagnosticRecorder(
        environment = DiagnosticEnvironment(
            platform = "android",
            operatingSystem = "Android ${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})",
            applicationVersion = BuildConfig.VERSION_NAME,
            buildNumber = BuildConfig.VERSION_CODE.toString(),
            gitCommitSha = BuildInfo.COMMIT,
            safeDeviceId = safeDeviceId(appContext)
        ),
        configuration = DiagnosticConfiguration(
            protocolVersion = "secure-v2",
            timeoutsMillis = mapOf(
                "keepAlive" to 6_000L,
                "fileOffer" to 30_000L,
                "durableCommit" to 30_000L
            ),
            retryValues = mapOf("pingInterval" to 2_000L),
            packetLimits = mapOf(
                "sampleReceiveQuotaBytes" to 50L * 1024L * 1024L,
                "diagnosticEvents" to 5_000L,
                "diagnosticBytes" to 5L * 1024L * 1024L
            ),
            faultInjection = mapOf("enabled" to "false"),
            values = mapOf(
                "testMode" to "true",
                "securityPolicy" to "authenticated-same-app-test-only"
            )
        ),
        eventSink = { json ->
            try {
                rollingSink(json)
            } finally {
                onEvent()
            }
        }
    )
    private val correlations = DiagnosticCorrelationRegistry(
        activeSessionId = { recorder.activeSessionId }
    )

    init {
        val restoredTest = preferences.getString(KEY_TEST_ID, null)
        val restoredSession = preferences.getString(KEY_SESSION_ID, null)
        val restoredRole = preferences.getString(KEY_ROLE, null)
        if (restoredTest != null && restoredSession != null && restoredRole != null) {
            runCatching {
                recorder.startSession(restoredTest, restoredRole, restoredSession)
                recorder.record(
                    DiagnosticRecord(
                        category = "application",
                        eventName = DiagnosticEventNames.APPLICATION_STARTED,
                        currentState = "recovered",
                        outcome = DiagnosticOutcome.RECOVERY,
                        details = mapOf("restoredTestSession" to "true")
                    )
                )
            }.onFailure {
                preferences.edit { clear() }
                recordUnassignedStartup()
            }
        } else {
            recordUnassignedStartup()
        }
    }

    fun beginSession(testId: String, role: String, requestedSessionId: String?): String {
        val sessionId = recorder.startSession(testId, role, requestedSessionId)
        correlations.resetSession()
        preferences.edit {
            putString(KEY_TEST_ID, recorder.activeTestId)
            putString(KEY_SESSION_ID, sessionId)
            putString(KEY_ROLE, recorder.activeRole)
        }
        recorder.record(
            DiagnosticRecord(
                category = "test",
                eventName = DiagnosticEventNames.TEST_MODE_ACTIVATED,
                currentState = "enabled",
                details = mapOf("persistentAcrossProcessRestart" to "true")
            )
        )
        return sessionId
    }

    fun complete(outcome: DiagnosticOutcome, reason: String, finalState: String) {
        recorder.completeSession(outcome, reason, finalState)
    }

    fun setLocalPeerId(peerId: String?) = correlations.setLocalPeerId(peerId)

    fun registerConnection(sessionId: String, peerId: String): DiagnosticCorrelation? =
        correlations.registerConnection(sessionId, peerId)

    fun removeConnection(sessionId: String): DiagnosticCorrelation? =
        correlations.removeConnection(sessionId)

    fun connectionForPeer(peerId: String): DiagnosticCorrelation? =
        correlations.connectionForPeer(peerId)

    fun registerTransfer(transferId: String, peerId: String): DiagnosticCorrelation? =
        correlations.registerTransfer(transferId, peerId)

    fun correlationForTransfer(transferId: String): DiagnosticCorrelation? =
        correlations.correlationForTransfer(transferId)

    fun export(): File = DiagnosticEvidenceExporter.export(
        recorder = recorder,
        directory = File(appContext.cacheDir, "test-evidence"),
        additionalFiles = rollingSink.evidenceFiles(recorder.activeSessionId)
    )

    fun clearCurrentSession(): Int {
        val current = recorder.activeSessionId
        val removed = recorder.clearCurrentSession()
        rollingSink.clearSession(current)
        preferences.edit { clear() }
        correlations.resetSession()
        return removed
    }

    fun shutdown() {
        recorder.record(
            DiagnosticRecord(
                category = "application",
                eventName = DiagnosticEventNames.APPLICATION_SHUTDOWN,
                currentState = "view-model-cleared"
            )
        )
        correlations.resetSession()
    }

    private fun recordUnassignedStartup() {
        recorder.record(
            DiagnosticRecord(
                category = "application",
                eventName = DiagnosticEventNames.APPLICATION_STARTED,
                currentState = "started",
                details = mapOf("testSessionSelected" to "false")
            )
        )
    }

    private companion object {
        const val PREFERENCES = "p2pkit-test-diagnostics"
        const val KEY_TEST_ID = "testId"
        const val KEY_SESSION_ID = "sessionId"
        const val KEY_ROLE = "role"
    }
}

private fun safeDeviceId(context: Context): String {
    // The value is used only as an in-package correlation input and is
    // immediately one-way hashed; it is never exported in raw form.
    @Suppress("HardwareIds")
    val androidId = Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID)
        ?.takeIf { it.isNotBlank() }
        ?: "${Build.MANUFACTURER}:${Build.MODEL}:${Build.VERSION.SDK_INT}"
    return anonymizeIdentifier("android:$androidId")
}
