package dev.p2pkit.sample.android

import java.io.File
import java.io.IOException
import java.nio.file.Files
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNotEquals
import kotlin.test.assertSame
import kotlin.test.assertTrue

class IncomingFileDestinationTest {
    private val temporaryDirectories = mutableListOf<File>()

    @AfterTest
    fun cleanUp() {
        temporaryDirectories.forEach { directory -> directory.deleteRecursively() }
        temporaryDirectories.clear()
    }

    @Test
    fun externalIncomingDirectoryKeepsItsActualStorageLabel() {
        val external = File("synthetic-external-app-files")
        val location = incomingFileDirectory(external, "peer") { error("internal fallback must stay lazy") }

        assertEquals(File(external, "p2pkit-incoming/peer"), location.file)
        assertEquals("app-scoped-external", location.storageDomain)
    }

    @Test
    fun internalIncomingFallbackKeepsItsActualStorageLabel() {
        val internal = File("synthetic-internal-app-files")
        var fallbackCalls = 0
        val location = incomingFileDirectory(null, "peer") {
            fallbackCalls++
            internal
        }

        assertEquals(1, fallbackCalls)
        assertEquals(File(internal, "p2pkit-incoming/peer"), location.file)
        assertEquals("app-private", location.storageDomain)
    }

    @Test
    fun hostilePeerAndFileNamesStayInsideEitherSelectedStorageRoot() {
        val hostileNames = listOf("../../../evil.txt", "/etc/passwd", "a\\b:c", ".", "..", "", "bad\u0000name\n.txt")
        for (useExternal in listOf(true, false)) {
            val root = newTemporaryDirectory()
            for (name in hostileNames) {
                val location = incomingFileDirectory(root.takeIf { useExternal }, name) { root }
                val directory = location.file.also { it.mkdirs() }
                val first = uniqueDestination(directory, name)
                first.writeText("preserved")
                val second = uniqueDestination(directory, name)

                assertEquals(File(root, "p2pkit-incoming").canonicalFile, directory.canonicalFile.parentFile)
                assertEquals(directory.canonicalFile, first.canonicalFile.parentFile)
                assertEquals(directory.canonicalFile, second.canonicalFile.parentFile)
                assertNotEquals(first, second)
                assertEquals("preserved", first.readText())
                assertTrue(second.isFile)
            }
        }
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
