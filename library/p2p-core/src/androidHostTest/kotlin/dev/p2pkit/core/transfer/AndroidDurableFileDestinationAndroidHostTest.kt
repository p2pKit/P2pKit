package dev.p2pkit.core.transfer

import java.io.File
import java.io.FileDescriptor
import java.io.FileOutputStream
import java.io.IOException
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.nio.file.attribute.PosixFileAttributeView
import java.nio.file.attribute.PosixFilePermissions
import kotlinx.coroutines.runBlocking
import kotlinx.io.Buffer
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertFailsWith
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Real staging streams and publication, with Android syscalls replaced at their host boundary. */
class AndroidDurableFileDestinationAndroidHostTest {
    @Test
    fun directoryFsyncFailureRemainsPrimaryAndCommitRetriesOnlyDirectoryPhase() = runBlocking {
        withTempDirectory("p2pkit-android-directory-retry-") { directory ->
            val target = File(directory, "received.bin").also { it.writeText("existing") }
            val payload = byteArrayOf(4, 5, 6)
            val events = mutableListOf<String>()
            val fsyncFailure = IOException("injected directory fsync failure")
            val closeFailure = IOException("injected directory close failure")
            var failFirstAttempt = true
            val destination = destinationWithHostDirectoryOperations(
                target = target,
                events = events,
                fsync = { if (failFirstAttempt) throw fsyncFailure },
                close = {
                    if (failFirstAttempt) {
                        failFirstAttempt = false
                        throw closeFailure
                    }
                }
            )
            try {
                val sink = destination.openSink()
                val buffer = Buffer().apply { write(payload) }
                sink.write(buffer, buffer.size)

                val failure = assertFailsWith<IOException> { destination.commit() }
                assertSame(fsyncFailure, failure)
                assertEquals(listOf(closeFailure), failure.suppressedExceptions)
                assertContentEquals(payload, target.readBytes())
                assertEquals(listOf("rename", "open", "fsync", "close"), events)

                destination.commit()
                destination.commit()
                assertEquals(listOf("rename", "open", "fsync", "close", "open", "fsync", "close"), events)
                assertEquals(listOf(target.name), directory.list()?.sorted())
            } finally {
                destination.abort(cause = null)
            }
            assertContentEquals(payload, target.readBytes())
        }
    }

    @Test
    fun directoryCloseOnlyFailureSurfacesAndAbortNeverDeletesPublishedTarget() = runBlocking {
        withTempDirectory("p2pkit-android-directory-close-") { directory ->
            val target = File(directory, "received.bin").also { it.writeText("existing") }
            val payload = byteArrayOf(7, 8, 9)
            val events = mutableListOf<String>()
            val closeFailure = IOException("injected directory close failure")
            val destination = destinationWithHostDirectoryOperations(
                target = target,
                events = events,
                close = { throw closeFailure }
            )
            try {
                val sink = destination.openSink()
                val buffer = Buffer().apply { write(payload) }
                sink.write(buffer, buffer.size)

                val failure = assertFailsWith<IOException> { destination.commit() }
                assertSame(closeFailure, failure)
                assertTrue(failure.suppressedExceptions.isEmpty())
                assertContentEquals(payload, target.readBytes())

                destination.abort(cause = null)
                destination.abort(cause = null)
                assertFailsWith<IllegalStateException> { destination.commit() }
                assertEquals(listOf("rename", "open", "fsync", "close"), events)
                assertEquals(listOf(target.name), directory.list()?.sorted())
                assertContentEquals(payload, target.readBytes())
            } finally {
                destination.abort(cause = null)
            }
        }
    }

    @Test
    fun stagingPermissionsAreAppliedBeforeOpeningPayloadStream() = runBlocking {
        withTempDirectory("p2pkit-android-permissions-") { directory ->
            val target = File(directory, "received.bin")
            val events = mutableListOf<String>()
            val destination = AndroidDurableFileDestination(
                target = target,
                chmod = { path, mode ->
                    events += "chmod"
                    chmodForHost(path, mode)
                },
                openStream = { staging ->
                    events += "open"
                    assertEquals(listOf("chmod", "open"), events)
                    val store = Files.getFileStore(directory.toPath())
                    assertEquals(store, Files.getFileStore(staging.toPath()))
                    if (store.supportsFileAttributeView(PosixFileAttributeView::class.java)) {
                        assertEquals(
                            PosixFilePermissions.fromString("rw-------"),
                            Files.getPosixFilePermissions(staging.toPath())
                        )
                    }
                    FileOutputStream(staging, false)
                }
            )
            try {
                val sink = destination.openSink()
                val buffer = Buffer().apply { write(byteArrayOf(1, 2, 3)) }
                sink.write(buffer, buffer.size)
                assertFalse(target.exists())
                assertEquals(1, directory.listFiles().orEmpty().size)
                assertEquals(listOf("chmod", "open"), events)
            } finally {
                destination.abort(cause = null)
            }
            assertTrue(directory.listFiles().isNullOrEmpty())
        }
    }

    @Test
    fun rejectedStagingPermissionsNeverOpenPayloadAndRetainCleanupOwnership() = runBlocking {
        withTempDirectory("p2pkit-android-permission-failure-") { directory ->
            val target = File(directory, "received.bin").also { it.writeText("existing") }
            val chmodFailure = IOException("injected chmod failure")
            var openAttempts = 0
            val destination = AndroidDurableFileDestination(
                target = target,
                chmod = { path, mode ->
                    assertEquals(0x180, mode)
                    assertTrue(File(path).isFile)
                    throw chmodFailure
                },
                openStream = {
                    openAttempts += 1
                    FileOutputStream(it, false)
                }
            )

            assertSame(chmodFailure, assertFailsWith<IOException> { destination.openSink() })
            assertEquals(0, openAttempts)
            assertEquals(0L, directory.listFiles().orEmpty().single { it.extension == "part" }.length())
            assertFailsWith<IllegalStateException> { destination.openSink() }
            assertFailsWith<IllegalStateException> { destination.commit() }
            destination.abort(cause = null)
            destination.abort(cause = null)

            assertEquals("existing", target.readText())
            assertEquals(listOf(target.name), directory.list()?.sorted())
        }
    }

    @Test
    fun abortBeforeOpenLeavesNoStagingAndPreservesTarget() = runBlocking {
        withTempDirectory("p2pkit-android-unused-") { directory ->
            val target = File(directory, "received.bin").also { it.writeText("existing") }
            val destination = durableFileDestination(target)

            assertEquals(listOf(target.name), directory.list()?.sorted())
            destination.abort(cause = null)
            destination.abort(cause = null)

            assertFailsWith<IllegalStateException> { destination.openSink() }
            assertFailsWith<IllegalStateException> { destination.commit() }
            assertEquals("existing", target.readText())
            assertEquals(listOf(target.name), directory.list()?.sorted())
        }
    }

    @Test
    fun failedOpenRetainsStagingUntilAbort() = runBlocking {
        withTempDirectory("p2pkit-android-open-failure-") { directory ->
            val target = File(directory, "received.bin").also { it.writeText("existing") }
            val openFailure = IOException("injected staging open failure")
            var openAttempts = 0
            val destination = AndroidDurableFileDestination(
                target = target,
                chmod = ::chmodForHost,
                openStream = {
                    openAttempts += 1
                    assertTrue(it.isFile)
                    throw openFailure
                }
            )

            assertEquals(listOf(target.name), directory.list()?.sorted())
            assertSame(openFailure, assertFailsWith<IOException> { destination.openSink() })
            assertTrue(directory.listFiles().orEmpty().any { it.extension == "part" })
            assertFailsWith<IllegalStateException> { destination.openSink() }
            assertFailsWith<IllegalStateException> { destination.commit() }
            destination.abort(cause = null)
            destination.abort(cause = null)

            assertEquals(1, openAttempts)
            assertEquals("existing", target.readText())
            assertEquals(listOf(target.name), directory.list()?.sorted())
        }
    }

    @Test
    fun capacityPreflightRetainsConfiguredFreeSpace() = runBlocking {
        withTempDirectory("p2pkit-android-capacity-") { directory ->
            val accepted = AndroidDurableFileDestination(
                target = File(directory, "accepted.bin"),
                chmod = ::chmodForHost,
                usableSpace = { 9L },
                minimumFreeSpaceBytes = 5L
            )
            val rejected = AndroidDurableFileDestination(
                target = File(directory, "rejected.bin"),
                chmod = ::chmodForHost,
                usableSpace = { 9L },
                minimumFreeSpaceBytes = 5L
            )

            accepted.requireAvailableStorage(4L)
            val failure = assertFailsWith<IOException> {
                rejected.requireAvailableStorage(5L)
            }

            assertTrue(failure.message.orEmpty().contains("Insufficient usable space"))
            assertTrue(directory.listFiles().isNullOrEmpty(), "preflight must not create staging files")
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
                chmod = ::chmodForHost,
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
                chmod = ::chmodForHost,
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
            val closeFailure = IOException("injected sink close failure")
            var closeAttempts = 0
            var deleteAttempts = 0
            val destination = AndroidDurableFileDestination(
                target = target,
                chmod = ::chmodForHost,
                closeSink = { opened ->
                    closeAttempts += 1
                    // Release the handle before reporting failure so deletion is real on Windows too.
                    opened.close()
                    if (closeAttempts == 1) throw closeFailure
                },
                deleteTemp = { staging ->
                    deleteAttempts += 1
                    staging.delete()
                }
            )
            val sink = destination.openSink()
            try {
                val failure = assertFailsWith<IOException> { destination.abort(cause = null) }
                assertSame(closeFailure, failure.cause)
                assertEquals(0, failure.suppressedExceptions.size)
                assertEquals(1, closeAttempts)
                assertEquals(1, deleteAttempts)
                assertTrue(directory.listFiles().isNullOrEmpty())

                destination.abort(cause = null)
                assertEquals(2, closeAttempts)
                assertEquals(1, deleteAttempts)
            } finally {
                sink.close()
            }
        }
    }

    private fun destinationWithHostDirectoryOperations(
        target: File,
        events: MutableList<String>,
        fsync: () -> Unit = {},
        close: () -> Unit = {}
    ): AndroidDurableFileDestination {
        var descriptor: FileDescriptor? = null
        return AndroidDurableFileDestination(
            target = target,
            chmod = ::chmodForHost,
            rename = { staging, published ->
                events += "rename"
                Files.move(
                    File(staging).toPath(),
                    File(published).toPath(),
                    StandardCopyOption.ATOMIC_MOVE,
                    StandardCopyOption.REPLACE_EXISTING
                )
            },
            openDirectory = { path ->
                events += "open"
                assertEquals(assertNotNull(target.parentFile).absolutePath, path)
                assertNull(descriptor)
                FileDescriptor().also { descriptor = it }
            },
            fsyncDirectory = {
                events += "fsync"
                assertSame(descriptor, it)
                fsync()
            },
            closeDirectory = {
                events += "close"
                assertSame(descriptor, it)
                descriptor = null
                close()
            }
        )
    }

    private fun chmodForHost(path: String, mode: Int) {
        assertEquals(0x180, mode, "Android must request owner-only read/write before payload open")
        val staging = File(path).toPath()
        assertTrue(Files.isRegularFile(staging))
        // This host fixture cannot execute android.system.Os. On POSIX hosts,
        // apply the requested mode so the file-backed state machine sees real permissions.
        if (Files.getFileStore(staging).supportsFileAttributeView(PosixFileAttributeView::class.java)) {
            Files.setPosixFilePermissions(staging, PosixFilePermissions.fromString("rw-------"))
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
