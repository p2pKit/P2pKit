package dev.p2pkit.core.transfer

import java.io.File
import java.io.IOException
import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue
import kotlinx.coroutines.runBlocking
import kotlinx.io.Buffer

class OwnedStagingDirectoryJvmTest {
    @Test
    fun publicOverloadPublishesAtomicallyFromDistinctSameFilesystemDirectory() = runBlocking {
        withDirectories { parent, stage ->
            val target = File(parent, "target.bin").also { it.writeText("old") }
            val destination = durableFileDestination(target, stage, 0)
            val payload = byteArrayOf(1, 3, 5, 7)
            val buffer = Buffer().apply { write(payload) }
            destination.openSink().write(buffer, buffer.size)
            assertEquals("old", target.readText(), "staging must not alter the reserved target")
            assertEquals(1, stage.listFiles()!!.size)
            assertEquals(Files.getFileStore(parent.toPath()), Files.getFileStore(stage.toPath()))
            destination.commit()
            destination.abort(null)
            assertContentEquals(payload, target.readBytes())
            assertTrue(stage.listFiles()!!.isEmpty())
        }
    }

    @Test
    fun failedSourceDirectoryBarrierRetainsPublishedFileAndRetriesBothBarriers() = runBlocking {
        withDirectories { parent, stage ->
            val events = mutableListOf<File>()
            var failStage = true
            val target = File(parent, "target.bin")
            val destination = JvmDurableFileDestination(target, stagingDirectory = stage,
                operatingSystemName = "Linux", syncDirectory = {
                    events += it
                    if (it == stage && failStage) {
                        failStage = false
                        throw IOException("injected staging directory sync failure")
                    }
                })
            val buffer = Buffer().apply { write(byteArrayOf(8, 9)) }
            destination.openSink().write(buffer, buffer.size)
            assertFailsWith<IOException> { destination.commit() }
            assertContentEquals(byteArrayOf(8, 9), target.readBytes())
            destination.commit()
            destination.abort(null)
            assertEquals(listOf(parent, stage, parent, stage), events)
            assertContentEquals(byteArrayOf(8, 9), target.readBytes())
        }
    }

    @Test
    fun abortRemovesOnlyOwnedPartAndNeverDeletesExistingTarget() = runBlocking {
        withDirectories { parent, stage ->
            val target = File(parent, "target.bin").also { it.writeText("prior") }
            val destination = durableFileDestination(target, stage, 0)
            destination.openSink()
            destination.abort(null)
            assertEquals("prior", target.readText())
            assertTrue(stage.listFiles()!!.isEmpty())
        }
    }

    @Test
    fun symbolicLinkStagingIsRejectedBeforeOpeningPayload() = withDirectories { parent, stage ->
        val link = File(parent, "stage-link")
        Files.createSymbolicLink(link.toPath(), stage.toPath())
        assertFailsWith<IllegalArgumentException> { durableFileDestination(File(parent, "target"), link, 0) }
        assertTrue(stage.listFiles()!!.isEmpty())
    }

    @Test
    fun symbolicLinkIsRejectedEvenWhenCanonicalizationPreservesItsSpelling() = withDirectories { parent, stage ->
        val link = File(parent, "stage-link")
        Files.createSymbolicLink(link.toPath(), stage.toPath())
        assertTrue(Files.isSymbolicLink(link.toPath()))
        val directory = CanonicalIdentityFile(link)
        assertEquals(directory, directory.canonicalFile)
        assertFailsWith<IllegalArgumentException> { durableFileDestination(File(parent, "target"), directory, 0) }
        assertTrue(stage.listFiles()!!.isEmpty())
    }

    @Test
    fun symbolicLinkAncestorIsRejectedBeforeOpeningPayload() = withDirectories { parent, stage ->
        val nested = File(stage, "nested").also { check(it.mkdir()) }
        val link = File(parent, "stage-link")
        Files.createSymbolicLink(link.toPath(), stage.toPath())
        val directory = CanonicalIdentityFile(File(link, nested.name))
        assertTrue(directory.isDirectory)
        assertFailsWith<IllegalArgumentException> { durableFileDestination(File(parent, "target"), directory, 0) }
        assertTrue(nested.listFiles()!!.isEmpty())
    }

    @Test
    fun symbolicLinkBeforeParentTraversalIsNotNormalizedAway() = withDirectories { parent, stage ->
        val link = File(parent, "stage-link")
        Files.createSymbolicLink(link.toPath(), stage.toPath())
        val directory = CanonicalIdentityFile(File(link, "../${stage.name}"))
        assertTrue(directory.isDirectory)
        assertFailsWith<IllegalArgumentException> { durableFileDestination(File(parent, "target"), directory, 0) }
        assertTrue(stage.listFiles()!!.isEmpty())
    }

    // Model a platform whose File canonicalization keeps a real symbolic link's
    // spelling. NIO still reads the actual filesystem; no attribute result is faked.
    private class CanonicalIdentityFile(file: File) : File(file.absolutePath) {
        override fun getAbsoluteFile(): File = this
        override fun getCanonicalFile(): File = this
    }

    private inline fun withDirectories(block: (File, File) -> Unit) {
        val parent = Files.createTempDirectory("p2pkit-owned-stage-").toFile().canonicalFile
        val stage = File(parent, "owned").also { check(it.mkdir()) }
        try { block(parent, stage) } finally { parent.deleteRecursively() }
    }
}
