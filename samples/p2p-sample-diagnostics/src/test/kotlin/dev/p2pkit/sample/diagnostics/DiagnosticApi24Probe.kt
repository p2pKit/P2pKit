package dev.p2pkit.sample.diagnostics

import java.io.File
import java.io.IOException
import java.util.zip.ZipFile

/** Loaded in isolation by [DiagnosticApi24CompatibilityTest]; no API26 class is available to this code. */
object DiagnosticApi24Probe {
    @JvmStatic
    fun record(): String {
        val recorder = recorder()
        recorder.startSession("test", "sender", "session")
        val summary = recorder.summary()
        check(summary.eventCount > 0) { "Missing APIs dropped every diagnostic event" }
        check(summary.droppedEventCount == 0L) { "Missing APIs dropped diagnostic events" }
        return requireNotNull(summary.startTimestamp)
    }

    @JvmStatic
    fun export(directory: File): String {
        val recorder = recorder()
        recorder.startSession("test", "sender", "session")
        val first = DiagnosticEvidenceExporter.export(recorder, directory)
        check(DiagnosticEvidenceExporter.verifyChecksums(first))
        recorder.record(DiagnosticRecord(category = "test", eventName = "test.repeated.export"))
        if (!renameCanReplace(directory)) {
            // A Windows JVM is not Android's POSIX filesystem. In that model,
            // require a visible failure and byte-for-byte preservation, not a skip.
            val original = first.readBytes()
            val failure = runCatching { DiagnosticEvidenceExporter.export(recorder, directory) }.exceptionOrNull()
            check(failure is IOException)
            check(first.readBytes().contentEquals(original))
            return "verified-preserved-failure"
        }
        val second = DiagnosticEvidenceExporter.export(recorder, directory)
        check(first == second)
        check(DiagnosticEvidenceExporter.verifyChecksums(second))
        ZipFile(second).use { zip ->
            val events = zip.getInputStream(zip.getEntry("events.jsonl")).bufferedReader().use { it.readText() }
            check("test.repeated.export" in events)
        }
        return "verified-replacement"
    }

    @JvmStatic
    fun replace(source: File, target: File) = replaceDiagnosticFile(source, target)

    @JvmStatic
    fun failedExport(directory: File): String {
        val recorder = recorder()
        recorder.startSession("test", "sender", "session")
        val target = File(
            directory,
            DiagnosticEvidenceExporter.evidenceFilename(
                "test", "android", requireNotNull(recorder.summary().startTimestamp), "session"
            )
        )
        check(target.mkdir())
        val existing = File(target, "unrelated").apply { writeText("preserved") }
        val failure = runCatching { DiagnosticEvidenceExporter.export(recorder, directory) }.exceptionOrNull()
        check(failure is IOException)
        check(existing.readText() == "preserved")
        check(recorder.snapshot().none { it.eventName == DiagnosticEventNames.EVIDENCE_EXPORTED })
        return "preserved"
    }

    private fun renameCanReplace(directory: File): Boolean {
        val source = File(directory, "rename-source").apply { writeText("new") }
        val target = File(directory, "rename-target").apply { writeText("old") }
        return try {
            source.renameTo(target).also { replaced ->
                check(target.readText() == if (replaced) "new" else "old")
                check(if (replaced) !source.exists() else source.readText() == "new")
            }
        } finally {
            if (source.exists()) check(source.delete())
            check(target.delete())
        }
    }

    private fun recorder(): DiagnosticRecorder = DiagnosticRecorder(
        environment = DiagnosticEnvironment(
            platform = "android",
            operatingSystem = "synthetic-api24-missing-classes",
            applicationVersion = "test",
            buildNumber = "test",
            gitCommitSha = "test",
            safeDeviceId = "synthetic"
        )
    )
}
