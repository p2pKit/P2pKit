package dev.p2pkit.sample.android

import java.io.File
import java.io.IOException
import java.nio.file.Files
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertSame

class IncomingFileDestinationTest {
    private val temporaryDirectories = mutableListOf<File>()

    @AfterTest
    fun cleanUp() {
        temporaryDirectories.forEach { directory -> directory.deleteRecursively() }
        temporaryDirectories.clear()
    }

    @Test
    fun repeatedNamePreservesExistingFileAndUsesSuffix() {
        val directory = newTemporaryDirectory()
        val first = uniqueDestination(directory, "photo.png")
        first.writeText("first transfer")

        val second = uniqueDestination(directory, "photo.png")

        assertEquals("photo.png", first.name)
        assertEquals("photo (1).png", second.name)
        assertEquals("first transfer", first.readText())
    }

    @Test
    fun filesystemFailureStopsAfterFirstCandidate() {
        val directory = newTemporaryDirectory()
        val failure = IOException("injected storage failure")
        var attempts = 0

        val thrown = assertFailsWith<IOException> {
            uniqueDestination(directory, "photo.png") {
                attempts += 1
                throw failure
            }
        }

        assertEquals(1, attempts)
        assertSame(failure, thrown.cause)
        assertEquals("cannot claim destination ${File(directory, "photo.png").absolutePath}", thrown.message)
    }

    private fun newTemporaryDirectory(): File =
        Files.createTempDirectory("p2pkit-android-unique-destination").toFile()
            .also { directory -> temporaryDirectories += directory }
}
