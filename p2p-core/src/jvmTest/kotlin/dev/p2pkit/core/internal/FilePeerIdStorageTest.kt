package dev.p2pkit.core.internal

import dev.p2pkit.core.P2pLogger
import java.io.File
import java.nio.file.Files
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class FilePeerIdStorageTest {

    private val tempDir: File = Files.createTempDirectory("p2pkit-pidstoragetest").toFile()

    @AfterTest
    fun cleanup() {
        tempDir.deleteRecursively()
    }

    @Test
    fun firstCallCreatesFileAndReturnsId() {
        val storage = FilePeerIdStorage(tempDir, "test-app", P2pLogger.NoOp)
        val id = storage.loadOrGenerate()
        assertNotNull(id)
        assertTrue(id.value.isNotBlank())
        assertTrue(File(storage.storagePath).exists(), "Storage file should be written on first call")
    }

    @Test
    fun secondCallReturnsTheSameIdFromDisk() {
        val a = FilePeerIdStorage(tempDir, "test-app", P2pLogger.NoOp)
        val id = a.loadOrGenerate()
        // A brand-new storage instance pointing at the same backing file should
        // load the persisted id, not regenerate.
        val b = FilePeerIdStorage(tempDir, "test-app", P2pLogger.NoOp)
        assertEquals(id, b.loadOrGenerate())
    }

    @Test
    fun corruptFileRegeneratesAndOverwrites() {
        val storage = FilePeerIdStorage(tempDir, "test-app", P2pLogger.NoOp)
        // Pre-create a file with blank content.
        File(storage.storagePath).also {
            it.parentFile.mkdirs()
            it.writeText("   \n\n  ")
        }
        val regenerated = storage.loadOrGenerate()
        assertTrue(regenerated.value.isNotBlank())
        // The fresh id must be persisted, not the blank content.
        val onDisk = File(storage.storagePath).readText().trim()
        assertEquals(regenerated.value, onDisk)
    }

    @Test
    fun differentAppIdsGetIndependentIds() {
        val app1 = FilePeerIdStorage(tempDir, "app-one", P2pLogger.NoOp).loadOrGenerate()
        val app2 = FilePeerIdStorage(tempDir, "app-two", P2pLogger.NoOp).loadOrGenerate()
        assertNotEquals(app1, app2)
    }

    @Test
    fun appIdSanitisationKeepsFilesUnderRoot() {
        val malicious = FilePeerIdStorage(tempDir, "../../etc/passwd", P2pLogger.NoOp)
        malicious.loadOrGenerate()
        val canonicalFile = File(malicious.storagePath).canonicalPath
        val canonicalRoot = tempDir.canonicalPath
        assertTrue(
            canonicalFile.startsWith(canonicalRoot),
            "Sanitised path $canonicalFile must remain under $canonicalRoot"
        )
    }

    // ---- Legacy-directory migration (2026-07 review P1-12, A04 §3 r3) ----

    /** Writes a peer-id file at the pre-AUDIT-2026-06 visible `p2pkit` location. */
    private fun writeLegacyId(appId: String, id: String): File {
        val legacyFile = File(File(File(tempDir, "p2pkit"), sanitizeAppIdForFilesystem(appId)), "peer-id")
        legacyFile.parentFile.mkdirs()
        legacyFile.writeText(id)
        return legacyFile
    }

    /**
     * AUDIT-2026-06 renamed the storage directory from the visible
     * `<root>/p2pkit` to the hidden `<root>/.p2pkit`. An id found only at the
     * legacy location must be adopted (returned as-is, preserving the desktop
     * identity) and re-persisted under the new hidden path.
     */
    @Test
    fun legacyVisibleDirIdIsAdoptedAndRePersistedUnderHiddenDir() {
        writeLegacyId("test-app", "legacy-id-123")

        val storage = FilePeerIdStorage(tempDir, "test-app", P2pLogger.NoOp)
        val loaded = storage.loadOrGenerate()

        assertEquals("legacy-id-123", loaded.value, "The legacy id must be adopted, not regenerated")
        val newFile = File(storage.storagePath)
        assertTrue(
            newFile.absolutePath.contains("${File.separator}.p2pkit${File.separator}"),
            "New storage path must live under the hidden .p2pkit dir: ${newFile.absolutePath}"
        )
        assertTrue(newFile.exists(), "Migration must re-persist the id under the hidden dir")
        assertEquals("legacy-id-123", newFile.readText().trim())
    }

    /**
     * After the one-time migration, a fresh storage instance must load the
     * migrated id from the new hidden path (identity is stable across
     * restarts that follow the rename).
     */
    @Test
    fun migratedIdIsLoadedFromHiddenDirBySubsequentInstances() {
        writeLegacyId("test-app", "legacy-id-456")
        FilePeerIdStorage(tempDir, "test-app", P2pLogger.NoOp).loadOrGenerate()

        val second = FilePeerIdStorage(tempDir, "test-app", P2pLogger.NoOp)
        assertEquals("legacy-id-456", second.loadOrGenerate().value)
    }

    /**
     * The hidden-path id wins when both locations hold an id: migration is
     * one-time and must never overwrite an id already established under
     * `.p2pkit` with a stale legacy value.
     */
    @Test
    fun existingHiddenDirIdTakesPrecedenceOverLegacyId() {
        writeLegacyId("test-app", "stale-legacy-id")
        val storage = FilePeerIdStorage(tempDir, "test-app", P2pLogger.NoOp)
        File(storage.storagePath).also {
            it.parentFile.mkdirs()
            it.writeText("current-hidden-id")
        }

        assertEquals("current-hidden-id", storage.loadOrGenerate().value)
        assertEquals(
            "current-hidden-id",
            File(storage.storagePath).readText().trim(),
            "The hidden-path id must not be overwritten by the legacy value"
        )
    }

    @Test
    fun sanitizationFunctionStripsTraversal() {
        // Direct sanitiser tests — easier to reason about than going through storage.
        assertEquals("com.example.transfer", sanitizeAppIdForFilesystem("com.example.transfer"))
        assertEquals("_", sanitizeAppIdForFilesystem(""))
        // `..` is collapsed to `._`; leading dots stripped.
        val sanitized = sanitizeAppIdForFilesystem("../../etc/passwd")
        assertTrue(!sanitized.contains("/"), "sanitised='$sanitized' must not contain a path separator")
        assertTrue(!sanitized.startsWith("."), "sanitised='$sanitized' must not start with a dot")
        assertTrue(!sanitized.contains(".."), "sanitised='$sanitized' must not contain '..'")
    }
}
