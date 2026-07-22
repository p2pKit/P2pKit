package dev.p2pkit.core.internal

import dev.p2pkit.core.P2pLogger
import java.io.File
import java.net.URLClassLoader
import java.nio.file.Files
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
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
    fun sanitizerCollisionsUseIndependentHashedNamespaces() {
        val first = FilePeerIdStorage(tempDir, "tenant/a", P2pLogger.NoOp)
        val second = FilePeerIdStorage(tempDir, "tenant?a", P2pLogger.NoOp)
        assertEquals(
            sanitizeAppIdForFilesystem("tenant/a"),
            sanitizeAppIdForFilesystem("tenant?a"),
            "the fixture must reproduce the legacy collision"
        )

        assertNotEquals(first.storagePath, second.storagePath)
        assertNotEquals(first.loadOrGenerate(), second.loadOrGenerate())
    }

    @Test
    fun appIdsThatDifferAfterLegacyTruncationUseIndependentNamespaces() {
        val sharedPrefix = "a".repeat(64)
        val first = FilePeerIdStorage(tempDir, sharedPrefix + "-one", P2pLogger.NoOp)
        val second = FilePeerIdStorage(tempDir, sharedPrefix + "-two", P2pLogger.NoOp)
        assertEquals(
            sanitizeAppIdForFilesystem(sharedPrefix + "-one"),
            sanitizeAppIdForFilesystem(sharedPrefix + "-two")
        )
        assertNotEquals(first.storagePath, second.storagePath)
    }

    @Test
    fun malformedSurrogateAppIdsRemainDistinctBeforeHashing() {
        val first = FilePeerIdStorage(tempDir, "app-\uD800", P2pLogger.NoOp)
        val second = FilePeerIdStorage(tempDir, "app-\uD801", P2pLogger.NoOp)
        assertNotEquals(first.storagePath, second.storagePath)
    }

    @Test
    fun concurrentInstancesCommitOneProcessWinner() {
        val workers = 16
        val start = CountDownLatch(1)
        val executor = Executors.newFixedThreadPool(workers)
        try {
            val futures = (0 until workers).map {
                executor.submit<String> {
                    start.await()
                    FilePeerIdStorage(tempDir, "concurrent-app", P2pLogger.NoOp)
                        .loadOrGenerate()
                        .value
                }
            }
            start.countDown()
            val ids = futures.map { it.get(15, TimeUnit.SECONDS) }.toSet()
            assertEquals(1, ids.size, "every concurrent creator must return the durable winner")

            val storage = FilePeerIdStorage(tempDir, "concurrent-app", P2pLogger.NoOp)
            assertEquals(ids.single(), storage.loadOrGenerate().value)
            assertTrue(
                File(storage.storagePath).parentFile.listFiles().orEmpty()
                    .none { it.name.startsWith("peer-id-") && it.name.endsWith(".tmp") },
                "successful atomic creation must not retain temporary files"
            )
        } finally {
            executor.shutdownNow()
        }
    }

    @Test
    fun concurrentChildProcessesCommitOneDurableWinner() {
        val processCount = 4
        val go = File(tempDir, "go")
        val readyFiles = (0 until processCount).map { File(tempDir, "ready-$it") }
        val java = File(System.getProperty("java.home"), "bin/java").absolutePath
        val classpath = currentTestClasspath()
        val processes = readyFiles.map { ready ->
            ProcessBuilder(
                java,
                "-cp",
                classpath,
                FilePeerIdStorageProcessProbe::class.java.name,
                tempDir.absolutePath,
                "cross-process-app",
                go.absolutePath,
                ready.absolutePath
            ).redirectErrorStream(true).start()
        }
        try {
            awaitFiles(readyFiles)
            assertTrue(go.createNewFile(), "parent must release the child-process barrier once")
            val outputs = processes.map { process ->
                assertTrue(process.waitFor(20, TimeUnit.SECONDS), "PeerId child process timed out")
                val output = process.inputStream.bufferedReader().readText().trim()
                assertEquals(0, process.exitValue(), output)
                output.lineSequence().last { it.startsWith("PEER_ID=") }.removePrefix("PEER_ID=")
            }
            assertEquals(1, outputs.toSet().size, "all processes must observe one persisted PeerId")
        } finally {
            processes.filter { it.isAlive }.forEach { it.destroyForcibly() }
        }
    }

    @Test
    fun persistenceFailureIsMemoizedForTheStorageInstance() {
        val nonDirectoryRoot = File(tempDir, "root-file").also { it.writeText("not a directory") }
        val storage = FilePeerIdStorage(nonDirectoryRoot, "failure-app", P2pLogger.NoOp)

        val first = storage.loadOrGenerate()
        val second = storage.loadOrGenerate()

        assertEquals(first, second, "the same instance must not rotate identity after persistence failure")
        assertFalse(File(storage.storagePath).exists())
    }

    @Test
    fun blankHomeUsesExplicitTemporaryFallbackNeverWorkingDirectory() {
        JvmSystemPropertyTestGuard.withValues(
            mapOf("user.home" to "   ", "java.io.tmpdir" to tempDir.absolutePath)
        ) {
            val root = resolveJvmPeerIdRoot(P2pLogger.NoOp)
            assertEquals(File(tempDir, "p2pkit-fallback").canonicalFile, root.canonicalFile)
            assertNotEquals(File(".").canonicalFile, root.canonicalFile)
        }
    }

    @Test
    fun missingHomeAndTemporaryRootsFailExplicitly() {
        val nonDirectory = File(tempDir, "not-a-directory").also { it.writeText("x") }
        JvmSystemPropertyTestGuard.withValues(
            mapOf("user.home" to "", "java.io.tmpdir" to nonDirectory.absolutePath)
        ) {
            val failure = assertFailsWith<IllegalStateException> {
                resolveJvmPeerIdRoot(P2pLogger.NoOp)
            }
            assertTrue(failure.message.orEmpty().contains("working directory is never used"))
        }
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

    /** Writes the immediately previous hidden, sanitizer-keyed layout. */
    private fun writePreviousHiddenId(appId: String, id: String): File {
        val previous = File(File(File(tempDir, ".p2pkit"), sanitizeAppIdForFilesystem(appId)), "peer-id")
        previous.parentFile.mkdirs()
        previous.writeText(id)
        return previous
    }

    @Test
    fun previousHiddenSanitizerLayoutMigratesWithoutDeletingRollbackValue() {
        val previous = writePreviousHiddenId("test-app", "previous-hidden-id")

        val storage = FilePeerIdStorage(tempDir, "test-app", P2pLogger.NoOp)
        assertEquals("previous-hidden-id", storage.loadOrGenerate().value)
        assertEquals("previous-hidden-id", File(storage.storagePath).readText().trim())
        assertEquals(
            "previous-hidden-id",
            previous.readText().trim(),
            "migration input must remain intact for rollback"
        )
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

    private fun currentTestClasspath(): String {
        val entries = linkedSetOf<String>()
        System.getProperty("java.class.path").orEmpty()
            .split(File.pathSeparator)
            .filterTo(entries) { it.isNotBlank() }
        var loader: ClassLoader? = Thread.currentThread().contextClassLoader
        while (loader != null) {
            if (loader is URLClassLoader) {
                loader.urLs.mapNotNullTo(entries) { url ->
                    runCatching { File(url.toURI()).absolutePath }.getOrNull()
                }
            }
            loader = loader.parent
        }
        return entries.joinToString(File.pathSeparator)
    }

    private fun awaitFiles(files: List<File>) {
        val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(15)
        while (files.any { !it.exists() }) {
            check(System.nanoTime() < deadline) { "Child processes did not reach the start barrier" }
            Thread.sleep(5)
        }
    }

}

/** Separate JVM entry point used to prove the file lock across processes. */
internal object FilePeerIdStorageProcessProbe {
    @JvmStatic
    fun main(args: Array<String>) {
        val root = File(args[0])
        val appId = args[1]
        val go = File(args[2])
        val ready = File(args[3])
        check(ready.createNewFile())
        val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(15)
        while (!go.exists()) {
            check(System.nanoTime() < deadline) { "Parent did not release process barrier" }
            Thread.sleep(5)
        }
        val id = FilePeerIdStorage(root, appId, P2pLogger.NoOp).loadOrGenerate()
        println("PEER_ID=${id.value}")
    }
}
