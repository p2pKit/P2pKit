package dev.p2pkit.core.transfer

import kotlinx.io.Buffer
import kotlinx.io.RawSource
import kotlinx.io.readByteArray
import java.io.File
import java.io.FileInputStream
import java.io.IOException
import java.nio.file.FileSystemException
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

class PreparedJvmFileSourceTest {
    @Test
    fun preparationReleasesItsDescriptorAndEveryOpenReturnsVerifiedBytesAtZero() = withDirectory { directory ->
        for (payload in listOf(byteArrayOf(), byteArrayOf(1, 2, 3, 4))) {
            val file = File(directory, "source.bin").also { it.writeBytes(payload) }
            val streams = mutableListOf<ObservedFileInputStream>()
            val prepared = prepareJvmFileSource(file) { ObservedFileInputStream(file).also(streams::add) }
            assertEquals(1, streams.size)
            assertTrue(streams.single().wasClosed)
            assertEquals(payload.size.toLong(), prepared.sizeBytes)
            repeat(2) {
                prepared.open().use { source ->
                    assertContentEquals(payload, readAll(source))
                    assertFalse(streams.last().wasClosed)
                }
                assertTrue(streams.last().wasClosed)
            }
        }
    }

    @Test
    fun rejectedPreflightAndReadFailureCloseTheirOwnDescriptor() = withDirectory { directory ->
        val file = File(directory, "source.bin").also { it.writeBytes(byteArrayOf(1, 2, 3)) }
        val streams = mutableListOf<ObservedFileInputStream>()
        val prepared = prepareJvmFileSource(file) { ObservedFileInputStream(file).also(streams::add) }
        file.writeBytes(byteArrayOf(3, 2, 1))
        assertFailsWith<PreparedSourceChangedException> { prepared.open() }
        assertTrue(streams.all { it.wasClosed })

        val failure = IOException("synthetic accepted-read failure")
        val closeFailure = IOException("synthetic close failure")
        var opens = 0
        var accepted: ObservedFileInputStream? = null
        val failing = prepareJvmFileSource(file) {
            ObservedFileInputStream(file, if (opens++ > 0) failure else null, closeFailure.takeIf { opens > 1 })
                .also { if (opens > 1) accepted = it }
        }
        assertSame(failure, assertFailsWith<IOException> { failing.open() })
        assertTrue(accepted!!.wasClosed)
        assertEquals(listOf(closeFailure), failure.suppressed.toList())
    }

    @Test
    fun swappingPathAfterOpenCannotRedirectTheVerifiedDescriptor() = withDirectory { directory ->
        val original = byteArrayOf(1, 2, 3)
        val substitute = byteArrayOf(3, 2, 1)
        val file = File(directory, "source.bin").also { it.writeBytes(original) }
        val replacement = File(directory, "replacement.bin").also { it.writeBytes(substitute) }
        val prepared = prepareJvmFileSource(file)
        val windows = System.getProperty("os.name").startsWith("Windows", ignoreCase = true)
        prepared.open().use { source ->
            if (windows) {
                // Classic JDK 17 FileInputStream does not share deletion on Windows.
                // The same move must succeed after closing, ruling out an unrelated I/O failure.
                assertFailsWith<FileSystemException> {
                    Files.move(replacement.toPath(), file.toPath(), StandardCopyOption.REPLACE_EXISTING)
                }
                assertContentEquals(original, file.readBytes())
                assertContentEquals(substitute, replacement.readBytes())
            } else {
                Files.move(replacement.toPath(), file.toPath(), StandardCopyOption.REPLACE_EXISTING)
                assertContentEquals(substitute, file.readBytes())
            }
            assertContentEquals(original, readAll(source))
        }
        if (windows) Files.move(replacement.toPath(), file.toPath(), StandardCopyOption.REPLACE_EXISTING)
        assertFailsWith<PreparedSourceChangedException> { prepared.open() }
    }

    @Test
    fun growingFilePreflightReadsOnlyPreparedLengthPlusOneAndCloses() = withDirectory { directory ->
        val file = File(directory, "source.bin").also { it.writeBytes(byteArrayOf(1, 2, 3)) }
        val streams = mutableListOf<ObservedFileInputStream>()
        val prepared = prepareJvmFileSource(file) { ObservedFileInputStream(file).also(streams::add) }
        file.appendBytes(ByteArray(1024 * 1024))

        assertFailsWith<PreparedSourceChangedException> { prepared.open() }

        assertEquals(4, streams.last().bytesRead)
        assertTrue(streams.last().wasClosed)
    }

    private fun readAll(source: RawSource): ByteArray {
        val buffer = Buffer()
        while (source.readAtMostTo(buffer, 64 * 1024) != -1L) {
            // Drain this small synthetic source.
        }
        return buffer.readByteArray()
    }

    private fun withDirectory(block: (File) -> Unit) {
        val directory = Files.createTempDirectory("p2pkit-verified-source-").toFile()
        try {
            block(directory)
        } finally {
            assertTrue(directory.deleteRecursively())
        }
    }
}

private class ObservedFileInputStream(
    file: File,
    private val readFailure: IOException? = null,
    private val closeFailure: IOException? = null
) : FileInputStream(file) {
    var bytesRead = 0
        private set
    var wasClosed = false
        private set

    override fun read(bytes: ByteArray, offset: Int, length: Int): Int {
        readFailure?.let { throw it }
        return super.read(bytes, offset, length).also { if (it > 0) bytesRead += it }
    }

    override fun close() {
        if (wasClosed) return
        wasClosed = true
        super.close()
        closeFailure?.let { throw it }
    }
}
