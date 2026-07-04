package dev.p2pkit.sample.desktop.ui

import java.io.File
import java.nio.file.Files
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * 2026-07 P1-32 (SMP-1): unit contract for the samples' incoming-file
 * destination-uniquification helper. Two same-named offers must land on
 * distinct paths (no overwrite) and the claim must be atomic (no two claims
 * of one path, so no interleaved writes). The CLI (`uniqueSaveFile` in
 * `p2p-sample-desktop`) and Android (`uniqueDestination`) samples carry the
 * same duplicated-verbatim algorithm — this suite is the de-facto contract
 * for all three copies. The two-offer re-send over a real session remains a
 * manual recipe (INTERNAL_TESTING.md).
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
    fun unwritableDirectoryReturnsTheCandidateWithoutLoopingOrThrowing() {
        val missing = File(newTempDir(), "does/not/exist")

        val candidate = uniqueSaveFile(missing, "ghost.txt")

        // The accept path's open-failure guard owns the error reporting; the
        // helper must hand back the first candidate instead of spinning.
        assertEquals("ghost.txt", candidate.name)
        assertFalse(candidate.exists())
    }
}
