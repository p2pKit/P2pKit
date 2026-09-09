package dev.p2pkit.core.internal

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.KeepAliveConfig
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.protocol.DefaultP2pProtocol
import dev.p2pkit.core.protocol.FileOfferPayload
import dev.p2pkit.core.protocol.MessageId
import dev.p2pkit.core.protocol.P2pProtocol
import dev.p2pkit.core.protocol.ProtocolEvent
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.transfer.FileTransferState
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.Runnable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.yield
import kotlin.concurrent.atomics.AtomicInt
import kotlin.concurrent.atomics.ExperimentalAtomicApi
import kotlin.coroutines.CoroutineContext
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertTrue

@OptIn(ExperimentalCoroutinesApi::class, ExperimentalAtomicApi::class)
class SessionCleanupBudgetTest {

    @Test
    fun closePhasesShareEightSecondsRatherThanAddingAnotherRuntimeWait() = runTest {
        val fixture = Fixture(this, holdPhases = true)
        var closeJob: Job? = null
        try {
            fixture.events.send(ProtocolEvent.Message(P2pMessage.Text("held delivery")))
            runCurrent()
            assertTrue(fixture.deliveryEntered.isCompleted)
            val close = backgroundScope.async { runCatching { fixture.session.close() } }
            closeJob = close
            runCurrent()
            assertTrue(fixture.closeFrameEntered.isCompleted)
            advanceTimeBy(7_999L)
            runCurrent()
            assertFalse(close.isCompleted)
            assertTrue(fixture.connection.closeEntered.isCompleted)
            assertTrue(fixture.readerCancelling.isCompleted)

            advanceTimeBy(1L)
            runCurrent()
            assertTrue(close.isCompleted, "runtime join must not receive another two seconds")
            val issues = close.await().cleanupIssues()
            assertEquals(8_000L, testScheduler.currentTime)
            assertEquals(ConnectionState.Closed, fixture.session.state.value)
            assertEquals(
                listOf("raw connection", "protocol reader", "application delivery", "runtime"),
                issues.map { it.resource.removePrefix("session cleanup-budget ") }
            )
            assertTrue(issues.all { it.deadlineExceeded })
            assertFalse(fixture.connection.closeExited.isCompleted)
            assertFalse(checkNotNull(fixture.reader).isCompleted)
            assertEquals(1 to 538L, fixture.session.applicationBacklogForTest())
            assertEquals(1, fixture.connection.closeCalls.load())

            // Closed does not start a new timeout or silently erase the owner
            // result while genuinely noncooperative workers are still pending.
            assertEquals(issues, runCatching { fixture.session.close() }.cleanupIssues())
            assertEquals(8_000L, testScheduler.currentTime)
        } finally {
            fixture.releaseAndCancel()
            settleAtCurrentTime { closeJob?.isCompleted != false && fixture.supervisor.isCompleted }
        }
        assertTrue(fixture.connection.closeExited.isCompleted)
        assertEquals(0 to 0L, fixture.session.applicationBacklogForTest())
    }

    @Test
    fun expiredFollowerCannotReplaceOwnerResultOrDropQueuedMandatoryCleanup() = runTest {
        val queuedCleanup = QueuedCleanupDispatcher()
        val terminalPublished = CompletableDeferred<Unit>()
        val continueTerminal = CompletableDeferred<Unit>()
        val fixture = Fixture(this, cleanupDispatcher = queuedCleanup) {
            terminalPublished.complete(Unit)
            continueTerminal.await()
        }
        var closeJob: Job? = null
        val cleanupOwners = mutableListOf<Job>()
        try {
            fixture.events.send(
                ProtocolEvent.FileOffer(MessageId(ByteArray(16) { 1 }), FileOfferPayload("pending.txt", 0L, null))
            )
            runCurrent()
            val offer = assertIs<IncomingFileSession>(fixture.session.pendingFileOffers.value.single())
            val close = backgroundScope.async { runCatching { fixture.session.close() } }
            closeJob = close
            runCurrent()
            assertTrue(terminalPublished.isCompleted)
            assertEquals(ConnectionState.Closed, fixture.session.state.value)
            advanceTimeBy(7_500L)
            val follower = backgroundScope.async { runCatching { fixture.session.close() } }
            runCurrent()
            assertFalse(follower.isCompleted)
            advanceTimeBy(500L)
            runCurrent()
            assertTrue(follower.isCompleted)
            assertFalse(close.isCompleted, "an inline publication hook is not a preemptible controlled wait")
            val pending = follower.await().cleanupIssues().single()
            assertEquals("session cleanup-budget close transaction", pending.resource)
            assertTrue(pending.deadlineExceeded)
            assertEquals(8_000L, testScheduler.currentTime)

            // Expiry does not skip resource ownership or grant another phase.
            continueTerminal.complete(Unit)
            runCurrent()
            assertTrue(close.isCompleted)
            val issues = close.await().cleanupIssues()
            assertTrue(issues.any { it.resource.endsWith("raw connection") })
            assertTrue(issues.any { it.resource.endsWith("file-transfer terminalization") })
            assertTrue(issues.none { it.resource.endsWith("close transaction") })
            assertEquals(8_000L, testScheduler.currentTime)
            assertEquals(0, fixture.connection.closeCalls.load(), "callbacks remain deliberately queued")
            cleanupOwners += queuedCleanup.takeDispatchedJobs()
            assertEquals(2, cleanupOwners.size, "raw close and file terminalization each retain one owner")
            assertTrue(cleanupOwners.all { it.isActive })
            assertEquals(FileTransferState.Offered, offer.state.value)
            assertEquals(issues, runCatching { fixture.session.close() }.cleanupIssues())

            settleAtCurrentTime(
                tick = { queuedCleanup.runQueued() },
                ready = { cleanupOwners.all { it.isCompleted } }
            )
            assertEquals(1, fixture.connection.closeCalls.load())
            assertTrue(fixture.connection.closeExited.isCompleted)
            assertTrue(fixture.session.pendingFileOffers.value.isEmpty())
            assertIs<FileTransferState.Cancelled>(offer.state.value)
            assertEquals(issues, runCatching { fixture.session.close() }.cleanupIssues())
        } finally {
            continueTerminal.complete(Unit)
            fixture.releaseAndCancel()
            settleAtCurrentTime(
                tick = {
                    queuedCleanup.runQueued()
                    cleanupOwners += queuedCleanup.takeDispatchedJobs()
                },
                ready = {
                    closeJob?.isCompleted != false && fixture.supervisor.isCompleted &&
                        cleanupOwners.all { it.isCompleted }
                }
            )
            queuedCleanup.close()
        }
    }

    @Test
    fun completedResultWinsAtZeroAndPendingResultDoesNotCreateAnotherWait() = runTest {
        val budget = SessionCleanupBudget(8_000L, { testScheduler.currentTime }, StandardTestDispatcher(testScheduler))
        advanceTimeBy(8_000L)
        assertEquals(BoundedOperationResult.Success("settled"), budget.await(CompletableDeferred("settled"), 2_000L))
        val pending = assertIs<BoundedOperationResult.TimedOut>(budget.await(CompletableDeferred<Unit>(), 2_000L))
        assertEquals(0L, pending.timeoutMillis)
        assertEquals(8_000L, testScheduler.currentTime)
    }

    @Test
    fun deadlineDispatcherAdmissionConsumesTheOriginalBudget() = runTest {
        val deadlineDispatcher = QueuedCleanupDispatcher()
        val budget = SessionCleanupBudget(8_000L, { testScheduler.currentTime }, deadlineDispatcher)
        val awaiting = backgroundScope.async { budget.await(CompletableDeferred<Unit>(), 2_000L) }
        try {
            runCurrent()
            advanceTimeBy(8_000L)
            deadlineDispatcher.runQueued()
            runCurrent()
            assertTrue(awaiting.isCompleted)
            assertEquals(0L, assertIs<BoundedOperationResult.TimedOut>(awaiting.await()).timeoutMillis)
            assertEquals(8_000L, testScheduler.currentTime)
        } finally {
            awaiting.cancel()
            deadlineDispatcher.runQueued()
            runCurrent()
            deadlineDispatcher.close()
        }
    }

    @Test
    fun callerTimeoutRemainsCancellationRatherThanCleanupExpiry() = runTest {
        val budget = SessionCleanupBudget(8_000L, { testScheduler.currentTime }, StandardTestDispatcher(testScheduler))
        assertFailsWith<TimeoutCancellationException> {
            withTimeout(100L) { budget.await(CompletableDeferred<Unit>(), 2_000L) }
        }
        assertEquals(100L, testScheduler.currentTime)
    }

    private fun Result<Unit>.cleanupIssues(): List<CleanupIssue> =
        assertIs<CleanupAggregateException>(assertIs<P2pError.ConnectionFailed>(exceptionOrNull()).cause).issues

    private fun TestScope.settleAtCurrentTime(tick: () -> Unit = {}, ready: () -> Boolean) {
        // Only the offer-disposal helper uses a real worker. Keep virtual time
        // fixed while it returns to the deliberately queued cleanup owner.
        // This timeout is a harness deadlock guard, not the latency assertion.
        runBlocking(Dispatchers.Default) {
            withTimeout(5_000L) {
                do {
                    tick()
                    testScheduler.runCurrent()
                    yield()
                } while (!ready())
            }
        }
    }

    private class Fixture(
        testScope: TestScope,
        holdPhases: Boolean = false,
        cleanupDispatcher: CoroutineDispatcher = StandardTestDispatcher(testScope.testScheduler),
        afterTerminalPublished: (suspend () -> Unit)? = null
    ) {
        val supervisor = SupervisorJob(testScope.backgroundScope.coroutineContext[Job])
        private val dispatcher = StandardTestDispatcher(testScope.testScheduler)
        private val scope = CoroutineScope(dispatcher + supervisor)
        val connection = HeldCleanupConnection(FakeConnectionPair().a, holdPhases)
        val events = Channel<ProtocolEvent>(Channel.UNLIMITED)
        val closeFrameEntered = CompletableDeferred<Unit>()
        private val releaseCloseFrame = CompletableDeferred<Unit>()
        val deliveryEntered = CompletableDeferred<Unit>()
        private val releaseDelivery = CompletableDeferred<Unit>()
        val readerCancelling = CompletableDeferred<Unit>()
        private val releaseReader = CompletableDeferred<Unit>()
        val reader = if (holdPhases) scope.launch(start = CoroutineStart.UNDISPATCHED) {
            try {
                awaitCancellation()
            } finally {
                withContext(NonCancellable) {
                    readerCancelling.complete(Unit)
                    releaseReader.await()
                }
            }
        } else null
        private val delegate = DefaultP2pProtocol(clock = { testScope.testScheduler.currentTime })
        private val protocol = object : P2pProtocol by delegate {
            override suspend fun sendClose(connection: RawConnection) {
                closeFrameEntered.complete(Unit)
                if (holdPhases) withContext(NonCancellable) { releaseCloseFrame.await() }
                delegate.sendClose(connection)
            }
        }
        val session = P2pSessionImpl(
            id = "cleanup-budget",
            peer = Peer(PeerId("cleanup-budget-peer"), "Peer", Platform.JVM_DESKTOP, setOf(TransportKind.LAN)),
            initialConnection = connection,
            initialEvents = events,
            initialReaderJob = reader,
            protocol = protocol,
            parentScope = scope,
            keepAlive = KeepAliveConfig(60_000L, 120_000L),
            clock = { testScope.testScheduler.currentTime },
            logger = P2pLogger.NoOp,
            beforeApplicationMessageEmitForTest = {
                deliveryEntered.complete(Unit)
                if (holdPhases) withContext(NonCancellable) { releaseDelivery.await() }
            },
            afterTerminalStatePublishedForTest = afterTerminalPublished,
            cleanupClock = { testScope.testScheduler.currentTime },
            cleanupOperationDispatcher = cleanupDispatcher,
            cleanupDeadlineDispatcher = dispatcher
        ).also { it.start() }

        fun releaseAndCancel() {
            releaseCloseFrame.complete(Unit)
            releaseDelivery.complete(Unit)
            releaseReader.complete(Unit)
            connection.releaseClose.complete(Unit)
            supervisor.cancel()
            events.close()
        }
    }

    private class HeldCleanupConnection(
        private val delegate: RawConnection,
        private val holdClose: Boolean
    ) : RawConnection by delegate {
        val closeCalls = AtomicInt(0)
        val closeEntered = CompletableDeferred<Unit>()
        val closeExited = CompletableDeferred<Unit>()
        val releaseClose = CompletableDeferred<Unit>()

        override suspend fun close() {
            closeCalls.addAndFetch(1)
            closeEntered.complete(Unit)
            if (holdClose) withContext(NonCancellable) { releaseClose.await() }
            delegate.close()
            closeExited.complete(Unit)
        }
    }

    /** Thread-safe queue: only the test admits cleanup work, never the session runtime. */
    private class QueuedCleanupDispatcher : CoroutineDispatcher() {
        private val queued = Channel<Runnable>(Channel.UNLIMITED)
        private val jobs = Channel<Job>(Channel.UNLIMITED)

        override fun dispatch(context: CoroutineContext, block: Runnable) {
            jobs.trySend(checkNotNull(context[Job])).getOrThrow()
            queued.trySend(block).getOrThrow()
        }

        fun runQueued() {
            while (true) (queued.tryReceive().getOrNull() ?: break).run()
        }

        fun takeDispatchedJobs(): List<Job> = buildList {
            while (true) add(jobs.tryReceive().getOrNull() ?: break)
        }

        fun close() {
            queued.close()
            jobs.close()
        }
    }
}
