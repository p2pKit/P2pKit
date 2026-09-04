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
import kotlin.test.assertTrue
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
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

    @Test
    fun postPublicationCommitFailureNeverDeletesTarget() = runBlocking {
        val root = Files.createTempDirectory("p2pkit-reserved-published").toFile()
        try {
            val target = File(root, "target.bin").also { check(it.createNewFile()) }
            val published = "verified payload".encodeToByteArray()
            val delegate = PublishingDestination(target, published, IOException("injected directory sync failure"))
            val destination = reservedFileDestination(target, delegate)

            assertFailsWith<IOException> { destination.commit() }
            destination.abort(null)
            destination.abort(null)

            assertTrue(target.exists())
            assertTrue(target.readBytes().contentEquals(published))
            assertFailsWith<IllegalStateException> { destination.openSink() }
            assertFailsWith<IllegalStateException> { destination.commit() }
            assertEquals(1, delegate.abortCalls)
        } finally {
            root.deleteRecursively()
        }
    }

    @Test
    fun postPublicationCommitFailureRemainsRetryable() = runBlocking {
        val root = Files.createTempDirectory("p2pkit-reserved-commit-retry").toFile()
        try {
            val target = File(root, "target.bin").also { check(it.createNewFile()) }
            val published = "verified payload".encodeToByteArray()
            val delegate = RetryingPublishingDestination(target, published)
            val destination = reservedFileDestination(target, delegate)

            assertFailsWith<IOException> { destination.commit() }
            destination.commit()
            destination.abort(null)

            assertTrue(target.readBytes().contentEquals(published))
            assertEquals(2, delegate.commitCalls)
            assertEquals(0, delegate.abortCalls)
        } finally {
            root.deleteRecursively()
        }
    }

    @Test
    fun cancellationAfterPublicationNeverDeletesTarget() = runBlocking {
        val root = Files.createTempDirectory("p2pkit-reserved-cancelled").toFile()
        try {
            val target = File(root, "target.bin").also { check(it.createNewFile()) }
            val published = "verified payload".encodeToByteArray()
            val publication = CompletableDeferred<Unit>()
            val delegate = CancellingPublishingDestination(target, published, publication)
            val destination = reservedFileDestination(target, delegate)

            val commit = launch { destination.commit() }
            publication.await()
            commit.cancelAndJoin()
            destination.abort(null)

            assertTrue(target.exists())
            assertTrue(target.readBytes().contentEquals(published))
            assertEquals(1, delegate.abortCalls)
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

private class PublishingDestination(
    private val target: File,
    private val contents: ByteArray,
    private val commitFailure: Throwable
) : FileTransferDestination {
    var abortCalls: Int = 0
        private set

    override fun openSink(): RawSink = error("not used")

    override suspend fun commit() {
        target.writeBytes(contents)
        throw commitFailure
    }

    override suspend fun abort(cause: P2pError.FileTransferFailed?) {
        abortCalls += 1
    }
}

private class CancellingPublishingDestination(
    private val target: File,
    private val contents: ByteArray,
    private val publication: CompletableDeferred<Unit>
) : FileTransferDestination {
    var abortCalls: Int = 0
        private set

    override fun openSink(): RawSink = error("not used")

    override suspend fun commit() {
        target.writeBytes(contents)
        publication.complete(Unit)
        awaitCancellation()
    }

    override suspend fun abort(cause: P2pError.FileTransferFailed?) {
        abortCalls += 1
    }
}

private class RetryingPublishingDestination(
    private val target: File,
    private val contents: ByteArray
) : FileTransferDestination {
    var commitCalls: Int = 0
        private set
    var abortCalls: Int = 0
        private set

    override fun openSink(): RawSink = error("not used")

    override suspend fun commit() {
        commitCalls += 1
        target.writeBytes(contents)
        if (commitCalls == 1) throw IOException("injected directory sync failure")
    }

    override suspend fun abort(cause: P2pError.FileTransferFailed?) {
        abortCalls += 1
    }
}
