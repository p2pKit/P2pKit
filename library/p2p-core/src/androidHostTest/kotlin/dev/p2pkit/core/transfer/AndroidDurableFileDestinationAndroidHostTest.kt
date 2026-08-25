package dev.p2pkit.core.transfer

import java.io.File
import java.io.IOException
import java.nio.file.Files
import kotlinx.coroutines.runBlocking
import kotlinx.io.Buffer
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Host-executable parity proof for Android's platform destination abort state machine. */
class AndroidDurableFileDestinationAndroidHostTest {
    @Test
    fun capacityPreflightRetainsConfiguredFreeSpace() = runBlocking {
        withTempDirectory("p2pkit-android-capacity-") { directory ->
            val accepted = AndroidDurableFileDestination(
                target = File(directory, "accepted.bin"),
                usableSpace = { 9L },
                minimumFreeSpaceBytes = 5L
            )
            val rejected = AndroidDurableFileDestination(
                target = File(directory, "rejected.bin"),
                usableSpace = { 9L },
                minimumFreeSpaceBytes = 5L
            )

            accepted.requireAvailableStorage(4L)
            val failure = assertFailsWith<IOException> {
                rejected.requireAvailableStorage(5L)
            }

            assertTrue(failure.message.orEmpty().contains("Insufficient usable space"))
            accepted.abort(cause = null)
            rejected.abort(cause = null)
            assertTrue(directory.listFiles().isNullOrEmpty())
        }
    }

    @Test
    fun abortReportsAllFailuresAndRetriesOnlyIncompleteCleanup() = runBlocking {
        val directory = Files.createTempDirectory("p2pkit-android-abort-retry-").toFile()
        try {
            val target = File(directory, "received.bin").also { it.writeText("existing") }
            val closeFailure = IOException("injected sink close failure")
            var closeAttempts = 0
            var deleteAttempts = 0
            val destination = AndroidDurableFileDestination(
                target = target,
                closeSink = { opened ->
                    closeAttempts += 1
                    if (closeAttempts == 1) throw closeFailure
                    opened.close()
                },
                deleteTemp = { staging ->
                    deleteAttempts += 1
                    if (deleteAttempts == 1) false else staging.delete()
                }
            )
            val sink = destination.openSink()
            val buffer = Buffer().apply { write(byteArrayOf(1, 2, 3, 4)) }
            sink.write(buffer, buffer.size)

            val failure = assertFailsWith<IOException> { destination.abort(cause = null) }

            assertTrue(failure.message.orEmpty().contains("staging sink close"))
            assertTrue(failure.message.orEmpty().contains("staging file deletion"))
            assertSame(closeFailure, failure.cause)
            assertEquals(1, failure.suppressedExceptions.size)
            assertTrue(failure.suppressedExceptions.single().message.orEmpty().contains("still exists"))
            assertEquals(1, closeAttempts)
            assertEquals(1, deleteAttempts)
            assertTrue(directory.listFiles().orEmpty().any { it.extension == "part" })
            assertFailsWith<IllegalStateException> { destination.commit() }

            destination.abort(cause = null)
            destination.abort(cause = null)

            assertEquals(2, closeAttempts)
            assertEquals(2, deleteAttempts)
            assertEquals("existing", target.readText())
            assertEquals(listOf(target.name), directory.list()?.sorted())
        } finally {
            directory.deleteRecursively()
        }
    }

    @Test
    fun successfulCloseIsNotRepeatedWhenOnlyDeletionNeedsRetry() = runBlocking {
        withTempDirectory("p2pkit-android-delete-retry-") { directory ->
            val target = File(directory, "received.bin")
            var closeAttempts = 0
            var deleteAttempts = 0
            val destination = AndroidDurableFileDestination(
                target = target,
                closeSink = { opened ->
                    closeAttempts += 1
                    opened.close()
                },
                deleteTemp = { staging ->
                    deleteAttempts += 1
                    if (deleteAttempts == 1) false else staging.delete()
                }
            )
            destination.openSink()

            assertFailsWith<IOException> { destination.abort(cause = null) }
            assertEquals(1, closeAttempts)
            assertEquals(1, deleteAttempts)

            destination.abort(cause = null)
            assertEquals(1, closeAttempts)
            assertEquals(2, deleteAttempts)
            assertTrue(directory.listFiles().isNullOrEmpty())
        }
    }

    @Test
    fun successfulDeletionIsNotRepeatedWhenOnlyCloseNeedsRetry() = runBlocking {
        withTempDirectory("p2pkit-android-close-retry-") { directory ->
            val target = File(directory, "received.bin")
            var closeAttempts = 0
            var deleteAttempts = 0
            val destination = AndroidDurableFileDestination(
                target = target,
                closeSink = { opened ->
                    closeAttempts += 1
                    if (closeAttempts == 1) throw IOException("injected sink close failure")
                    opened.close()
                },
                deleteTemp = { staging ->
                    deleteAttempts += 1
                    staging.delete()
                }
            )
            destination.openSink()

            assertFailsWith<IOException> { destination.abort(cause = null) }
            assertEquals(1, closeAttempts)
            assertEquals(1, deleteAttempts)
            assertTrue(directory.listFiles().isNullOrEmpty())

            destination.abort(cause = null)
            assertEquals(2, closeAttempts)
            assertEquals(1, deleteAttempts)
        }
    }

    private inline fun withTempDirectory(prefix: String, block: (File) -> Unit) {
        val directory = Files.createTempDirectory(prefix).toFile()
        try {
            block(directory)
        } finally {
            directory.deleteRecursively()
        }
    }
}
