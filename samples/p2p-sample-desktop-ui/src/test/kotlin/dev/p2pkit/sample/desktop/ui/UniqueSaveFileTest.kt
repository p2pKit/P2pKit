package dev.p2pkit.sample.desktop.ui

import dev.p2pkit.sample.diagnostics.reservedFileDestination
import dev.p2pkit.sample.diagnostics.cleanupStaleTransferPartsOnce

import java.io.File
import java.nio.file.Files
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.runBlocking
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * 2026-07 P1-32 (SMP-1): unit contract for the samples' incoming-file
 * destination-uniquification helper. Two same-named offers must land on
 * distinct paths (no overwrite) and the claim must be atomic (no two claims
 * of one path, so no interleaved writes). The CLI and Android samples carry
 * the same platform-neutral claim contract; this suite pins the JVM copy.
 * The two-offer re-send over a real session remains a manual recipe
 * (INTERNAL_TESTING.md).
 */
class UniqueSaveFileTest {

    private val tempDirs = mutableListOf<File>()

    private fun newTempDir(): File =
        Files.createTempDirectory("p2pkit-unique-save-test").toFile().also { tempDirs += it }

    @AfterTest
    fun cleanUp() {
        tempDirs.forEach { it.deleteRecursively() }
        tempDirs.clear()
    }

    @Test
    fun sameNameRepeatedlyYieldsDistinctNumberedPaths() {
        val dir = newTempDir()
        val first = uniqueSaveFile(dir, "photo.png")
        val second = uniqueSaveFile(dir, "photo.png")
        val third = uniqueSaveFile(dir, "photo.png")

        assertEquals("photo.png", first.name)
        assertEquals("photo (1).png", second.name)
        assertEquals("photo (2).png", third.name)
        assertTrue(first.exists() && second.exists() && third.exists(), "each claim must create its file")
        assertEquals(3, setOf(first.absolutePath, second.absolutePath, third.absolutePath).size)
    }

    @Test
    fun extensionlessNameGetsNumberedSuffixAfterTheBase() {
        val dir = newTempDir()
        assertEquals("notes", uniqueSaveFile(dir, "notes").name)
        assertEquals("notes (1)", uniqueSaveFile(dir, "notes").name)
    }

    @Test
    fun leadingDotNameIsTreatedAsExtensionless() {
        val dir = newTempDir()
        // lastIndexOf('.') == 0 → the whole name is the base (a dotfile has
        // no "extension" to preserve); pinned so a refactor cannot start
        // emitting " (1).bashrc"-style names.
        assertEquals(".bashrc", uniqueSaveFile(dir, ".bashrc").name)
        assertEquals(".bashrc (1)", uniqueSaveFile(dir, ".bashrc").name)
    }

    @Test
    fun preExistingFileIsNeverReturnedForTheSameName() {
        val dir = newTempDir()
        File(dir, "report.pdf").writeText("already on disk")

        val claimed = uniqueSaveFile(dir, "report.pdf")

        assertEquals("report (1).pdf", claimed.name, "an existing destination must never be reused")
        assertEquals("already on disk", File(dir, "report.pdf").readText(), "the existing file is untouched")
    }

    @Test
    fun pathAndDotSegmentsStayInsideTheClaimDirectory() {
        val dir = newTempDir()
        val pathLike = uniqueSaveFile(dir, "../escape.txt")
        val dot = uniqueSaveFile(dir, "..")

        assertEquals(dir.canonicalFile, pathLike.parentFile.canonicalFile)
        assertEquals(".._escape.txt", pathLike.name)
        assertEquals("untitled", dot.name)
        assertTrue(pathLike.exists() && dot.exists())
        assertTrue(!File(dir.parentFile, "escape.txt").exists(), "a peer name must not escape the inbox")
    }

    @Test
    fun concurrentClaimsOfOneNameNeverCollide() {
        val dir = newTempDir()
        val threads = 8
        val claimsPerThread = 5
        val pool = Executors.newFixedThreadPool(threads)
        try {
            val futures = (1..threads).map {
                pool.submit<List<String>> {
                    (1..claimsPerThread).map { uniqueSaveFile(dir, "chunked.bin").absolutePath }
                }
            }
            val claimed = futures.flatMap { it.get(30, TimeUnit.SECONDS) }

            assertEquals(
                threads * claimsPerThread,
                claimed.toSet().size,
                "the createNewFile claim must be atomic: no two transfers may share a destination"
            )
            claimed.forEach { path -> assertTrue(File(path).exists(), "claimed path must exist: $path") }
        } finally {
            pool.shutdownNow()
        }
    }

    @Test
    fun unwritableDirectoryFailsDeterministicallyWithoutLooping() {
        val missing = File(newTempDir(), "does/not/exist")

        assertFailsWith<java.io.IOException> { uniqueSaveFile(missing, "ghost.txt") }
    }

    @Test
    fun reservedDestinationAbortRemovesTheSampleOwnedClaim() = runBlocking {
        val dir = newTempDir()
        val claimed = uniqueSaveFile(dir, "cancelled.bin")
        val destination = reservedFileDestination(claimed)
        destination.openSink()

        destination.abort(cause = null)
        destination.abort(cause = null)

        assertFalse(claimed.exists(), "aborting must remove the empty namespace reservation")
        assertEquals(emptyList(), dir.list()?.toList())
    }

    @Test
    fun firstUseCleanupRemovesOnlySdkPartFiles() {
        val dir = newTempDir()
        val stale = File(dir, ".p2pkit-crashed.123.part").also { it.writeText("partial") }
        val unrelated = File(dir, "keep.part").also { it.writeText("user data") }

        cleanupStaleTransferPartsOnce(dir)

        assertFalse(stale.exists())
        assertTrue(unrelated.exists())
        assertEquals("user data", unrelated.readText())
    }
}
