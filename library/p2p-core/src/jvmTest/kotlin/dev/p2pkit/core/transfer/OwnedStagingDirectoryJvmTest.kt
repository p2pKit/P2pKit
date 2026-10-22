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

    private inline fun withDirectories(block: (File, File) -> Unit) {
        val parent = Files.createTempDirectory("p2pkit-owned-stage-").toFile().canonicalFile
        val stage = File(parent, "owned").also { check(it.mkdir()) }
        try { block(parent, stage) } finally { parent.deleteRecursively() }
    }
}
