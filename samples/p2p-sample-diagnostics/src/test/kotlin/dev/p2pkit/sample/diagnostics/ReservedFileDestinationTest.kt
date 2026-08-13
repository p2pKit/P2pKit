package dev.p2pkit.sample.diagnostics

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.transfer.FileTransferDestination
import java.io.File
import java.io.IOException
import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlinx.coroutines.runBlocking
import kotlinx.io.RawSink

class ReservedFileDestinationTest {
    @Test
    fun delegateAbortFailureRetainsCleanupForRetry() = runBlocking {
        val root = Files.createTempDirectory("p2pkit-reserved-retry").toFile()
        try {
            val target = File(root, "target.bin").also { check(it.createNewFile()) }
            val delegate = FailingAbortDestination(failures = 1)
            val destination = reservedFileDestination(target, delegate)

            assertFailsWith<IOException> { destination.abort(null) }
            assertFalse(target.exists())
            assertFailsWith<IllegalStateException> { destination.commit() }
            assertFailsWith<IllegalStateException> { destination.openSink() }
            destination.abort(null)
            destination.abort(null)

            assertEquals(2, delegate.abortCalls)
        } finally {
            root.deleteRecursively()
        }
    }

    @Test
    fun reservationDeletionFailureRetainsCleanupForRetry() = runBlocking {
        val root = Files.createTempDirectory("p2pkit-reserved-delete").toFile()
        try {
            val target = File(root, "reserved").also { check(it.mkdir()) }
            val blocker = File(target, "still-open").also { check(it.createNewFile()) }
            val delegate = FailingAbortDestination(failures = 0)
            val destination = reservedFileDestination(target, delegate)

            assertFailsWith<IOException> { destination.abort(null) }
            assertEquals(1, delegate.abortCalls)
            check(blocker.delete())
            destination.abort(null)
            destination.abort(null)

            assertFalse(target.exists())
            assertEquals(2, delegate.abortCalls)
        } finally {
            root.deleteRecursively()
        }
    }
}

private class FailingAbortDestination(private var failures: Int) : FileTransferDestination {
    var abortCalls: Int = 0
        private set

    override fun openSink(): RawSink = error("not used")

    override suspend fun commit(): Unit = error("not used")

    override suspend fun abort(cause: P2pError.FileTransferFailed?) {
        abortCalls += 1
        if (failures > 0) {
            failures -= 1
            throw IOException("injected delegate cleanup failure")
        }
    }
}
