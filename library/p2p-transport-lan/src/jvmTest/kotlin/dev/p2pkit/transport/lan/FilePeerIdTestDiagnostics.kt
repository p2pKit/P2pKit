package dev.p2pkit.transport.lan

import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.PeerId
import java.io.File
import java.io.IOException
import java.nio.channels.FileChannel
import java.nio.file.StandardOpenOption
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

/** Account for new legacy identity persistence without permitting unrelated or later diagnostics. */
internal fun KitTestDiagnostics.createWithFilePeerIdDiagnostics(
    home: File,
    recording: KitTestDiagnostics.Recording,
    verifyRuntimeDiagnostics: (List<KitTestDiagnostics.Recording.Entry>) -> Unit,
    build: (KitTestDiagnostics.Recording) -> P2pKit
): P2pKit {
    var constructionPrefix: List<KitTestDiagnostics.Recording.Entry>? = null
    val kit = create(
        recording = recording,
        verifyDiagnostics = { finalRecording ->
            val prefix = constructionPrefix
            if (prefix == null) {
                // A failed constructor never earns the runtime fixture's expected-warning allowance.
                finalRecording.assertQuiet()
            } else {
                val entries = finalRecording.entries
                assertEquals(prefix, entries.take(prefix.size), "Verified construction diagnostics changed")
                verifyRuntimeDiagnostics(entries.drop(prefix.size))
            }
        },
        build = build
    )
    // Register the returned kit with the teardown owner BEFORE assertions can fail. Probe now,
    // while the owned files exist; finish's afterStop cleanup may remove them before log checks.
    constructionPrefix = assertFilePeerIdConstruction(home, kit.localPeerId, recording)
    return kit
}

private fun assertFilePeerIdConstruction(
    home: File,
    peerId: PeerId,
    recording: KitTestDiagnostics.Recording
): List<KitTestDiagnostics.Recording.Entry> {
    // Each caller supplies a fresh per-kit home. Locate its one real durable record, not a path
    // extracted from a diagnostic or core-internal namespace API, and verify it is this kit's ID.
    val namespaces = File(home, ".p2pkit/peer-id-v2").listFiles()?.toList().orEmpty()
    assertEquals(1, namespaces.size, "A fresh kit home must contain exactly one PeerId namespace")
    val directory = namespaces.single()
    assertTrue(directory.isDirectory, "PeerId namespace must be a directory")
    val record = File(directory, "peer-id")
    assertTrue(record.isFile, "PeerId must have a durable record")
    assertEquals(peerId.value, record.readText(), "Persisted PeerId must match the constructed kit")

    val directoryFailure = try {
        FileChannel.open(directory.toPath(), StandardOpenOption.READ).use { it.force(true) }
        null
    } catch (failure: IOException) {
        failure
    }
    val entries = recording.entries
    if (directoryFailure == null) {
        assertEquals(emptyList(), entries, "Directory fsync succeeded; construction must be quiet")
    } else {
        // The file is persisted and atomically replaced; the documented directory fsync step is
        // best-effort on this actual provider. Exactly one matching warning, never an OS skip.
        assertEquals(1, entries.size, "Only the independently observed directory-fsync warning is expected")
        val entry = entries.single()
        assertEquals(KitTestDiagnostics.Recording.Level.WARN, entry.level)
        assertEquals("Could not fsync PeerId storage directory ${directory.absolutePath}", entry.message)
        val failure = assertIs<IOException>(entry.throwable)
        assertEquals(directoryFailure::class, failure::class)
        assertEquals(directoryFailure.message, failure.message)
        assertEquals(directoryFailure.cause, failure.cause)
        assertTrue(failure.suppressedExceptions.isEmpty())
    }
    return entries
}
