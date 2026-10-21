package dev.p2pkit.sample.android

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.transfer.FileTransferDestination
import java.io.File
import java.io.IOException
import java.nio.file.Files
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.io.RawSink
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Real files/coroutine handoff; the delegate stands in only for post-handoff SDK ownership. */
class PreparedIncomingDestinationTest {
    @Test
    fun cancelledEntryDoesNotAllocate() = runBlocking {
        var allocations = 0
        val task = launch(start = CoroutineStart.UNDISPATCHED) {
            coroutineContext[Job]!!.cancel()
            prepareIncomingDestination { allocations++; error("must not allocate") }
        }
        task.join()
        assertTrue(task.isCancelled)
        assertEquals(0, allocations)
    }

    @Test
    fun cancelledIoReturnRemovesOnlyTheNewReservation() = runBlocking {
        withDirectory { directory ->
            val existing = File(directory, "received.bin").also { it.writeText("existing") }
            var allocated: File? = null
            var destination: TestDestination? = null
            var handedOff = false
            val task = launch {
                val owner = coroutineContext[Job]!!
                prepareIncomingDestination(wrap = { TestDestination(it).also { value -> destination = value } }) {
                    val claim = uniqueDestination(directory, existing.name)
                    allocated = claim
                    // Exact bug boundary: synchronous allocation completes, then IO return is cancelled.
                    owner.cancel()
                    IncomingFileLocation(claim, "app-private")
                }
                handedOff = true
            }
            task.join()
            assertTrue(task.isCancelled)
            assertFalse(handedOff)
            assertEquals("received (1).bin", allocated!!.name)
            assertFalse(allocated.exists())
            assertEquals(1, destination!!.aborts)
            assertEquals("existing", existing.readText())
            assertEquals(listOf(existing.name), directory.list()!!.toList())
        }
    }

    @Test
    fun wrapperFailureRemovesTheClaimAndPreservesTheFailure() = runBlocking {
        withDirectory { directory ->
            val failure = IOException("wrapper failed")
            val thrown = try {
                prepareIncomingDestination(wrap = { throw failure }) {
                    IncomingFileLocation(uniqueDestination(directory, "received.bin"), "app-private")
                }
                null
            } catch (error: Throwable) { error }
            assertSame(failure, thrown?.cause ?: thrown)
            assertTrue(directory.list()!!.isEmpty())
        }
    }

    @Test
    fun allocationFailureNeverDeletesAnExistingFileOrConstructsAWrapper() = runBlocking {
        withDirectory { directory ->
            val existing = File(directory, "existing.bin").also { it.writeText("keep") }
            val failure = IOException("cannot create")
            var wrappers = 0
            val thrown = try {
                prepareIncomingDestination(wrap = { wrappers++; TestDestination(it) }) { throw failure }
                null
            } catch (error: Throwable) { error }
            assertSame(failure, thrown?.cause ?: thrown)
            assertEquals(0, wrappers)
            assertEquals("keep", existing.readText())
        }
    }

    @Test
    fun successfulHandoffLeavesClaimForTheDestinationAndAcceptFailureCanAbortIt() = runBlocking {
        withDirectory { directory ->
            val prepared = prepareIncomingDestination(wrap = ::TestDestination) {
                IncomingFileLocation(uniqueDestination(directory, "received.bin"), "app-scoped-external")
            }
            assertEquals("app-scoped-external", prepared.location.storageDomain)
            assertTrue(prepared.location.file.exists())
            val destination = prepared.destination as TestDestination
            assertEquals(0, destination.aborts)
            // The caller retains the existing accept-failure abort path after successful handoff.
            prepared.destination.abort(null)
            assertFalse(prepared.location.file.exists())
            assertEquals(1, destination.aborts)
        }
    }

    @Test
    fun helperNeverReclaimsAPublishedTargetAfterSuccessfulHandoff() = runBlocking {
        withDirectory { directory ->
            val prepared = prepareIncomingDestination(wrap = ::TestDestination) {
                IncomingFileLocation(uniqueDestination(directory, "received.bin"), "app-private")
            }
            prepared.destination.commit()
            prepared.destination.abort(null)
            assertEquals("published", prepared.location.file.readText())
        }
    }

    @Test
    fun cleanupFailureIsSuppressedOnTheOriginalCancellation() = runBlocking {
        withDirectory { directory ->
            val cleanupFailure = IOException("abort failed")
            val cancellation = CancellationException("cancelled allocation handoff")
            var observed: Throwable? = null
            var claim: File? = null
            val task = launch {
                val owner = coroutineContext[Job]!!
                try {
                    prepareIncomingDestination(wrap = { TestDestination(it, cleanupFailure) }) {
                        val file = uniqueDestination(directory, "received.bin").also { claim = it }
                        owner.cancel(cancellation)
                        IncomingFileLocation(file, "app-private")
                    }
                } catch (error: CancellationException) { observed = error }
            }
            task.join()
            assertSame(cancellation, observed?.cause ?: observed)
            assertEquals(listOf(cleanupFailure), observed!!.suppressedExceptions)
            assertFalse(claim!!.exists())
        }
    }

    private class TestDestination(
        private val target: File,
        private val abortFailure: Throwable? = null,
    ) : FileTransferDestination {
        var aborts = 0
        private var committed = false
        override fun openSink(): RawSink = error("payload sink is outside this handoff test")
        override suspend fun commit() {
            target.writeText("published")
            committed = true
        }
        override suspend fun abort(cause: P2pError.FileTransferFailed?) {
            aborts++
            if (!committed) check(target.delete() || !target.exists())
            abortFailure?.let { throw it }
        }
    }

    private suspend fun withDirectory(block: suspend (File) -> Unit) {
        val directory = Files.createTempDirectory("incoming-handoff-").toFile()
        try { block(directory) } finally { check(directory.deleteRecursively()) }
    }
}
