package dev.p2pkit.core.transfer

import java.io.File
import java.io.FileDescriptor
import java.io.IOException
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue
import kotlinx.coroutines.runBlocking
import kotlinx.io.Buffer

/** Real files/atomic move; Android device-identity and fsync syscalls are explicit host seams. */
class OwnedStagingDirectoryAndroidHostTest {
    @Test
    fun sourceDirectorySyncFailurePreservesPublicationAndRetriesBothDirectories() = runBlocking {
        withDirectories { parent, stage ->
            val target = File(parent, "received.bin")
            val opened = mutableListOf<String>()
            var failStage = true
            var moves = 0
            val destination = AndroidDurableFileDestination(target, stagingDirectory = stage,
                sameFileSystem = { a, b -> Files.getFileStore(a.toPath()) == Files.getFileStore(b.toPath()) },
                chmod = { _, _ -> },
                rename = { from, to ->
                    moves += 1
                    Files.move(File(from).toPath(), File(to).toPath(),
                        StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
                },
                openDirectory = { opened += it; FileDescriptor() },
                fsyncDirectory = {
                    if (opened.last() == stage.path && failStage) {
                        failStage = false
                        throw IOException("injected source directory barrier")
                    }
                },
                closeDirectory = {})
            val buffer = Buffer().apply { write(byteArrayOf(3, 4)) }
            destination.openSink().write(buffer, buffer.size)
            assertEquals(1, stage.listFiles()!!.size)
            assertFailsWith<IOException> { destination.commit() }
            assertContentEquals(byteArrayOf(3, 4), target.readBytes())
            destination.commit()
            destination.abort(null)
            assertEquals(1, moves, "published retry must never move/reopen payload again")
            assertEquals(listOf(parent.path, stage.path, parent.path, stage.path), opened)
            assertTrue(stage.listFiles()!!.isEmpty())
        }
    }

    @Test
    fun differentDeviceIsRejectedBeforeOpeningPayload() = withDirectories { parent, stage ->
        var checks = 0
        assertFailsWith<IllegalArgumentException> {
            AndroidDurableFileDestination(File(parent, "target"), stagingDirectory = stage,
                sameFileSystem = { a, b ->
                    assertEquals(parent, a)
                    assertEquals(stage, b)
                    checks += 1
                    false
                })
        }
        assertEquals(1, checks)
        assertTrue(stage.listFiles()!!.isEmpty())
    }

    private inline fun withDirectories(block: (File, File) -> Unit) {
        val parent = Files.createTempDirectory("p2pkit-android-owned-stage-").toFile().canonicalFile
        val stage = File(parent, "owned").also { check(it.mkdir()) }
        try { block(parent, stage) } finally { parent.deleteRecursively() }
    }
}
