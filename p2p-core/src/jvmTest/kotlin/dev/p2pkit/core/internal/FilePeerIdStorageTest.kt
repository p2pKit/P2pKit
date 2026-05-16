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
