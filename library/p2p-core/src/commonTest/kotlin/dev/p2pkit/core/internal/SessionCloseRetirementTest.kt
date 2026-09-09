package dev.p2pkit.core.internal

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.KeepAliveConfig
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.protocol.DefaultP2pProtocol
import dev.p2pkit.core.protocol.P2pProtocol
import dev.p2pkit.core.protocol.ProtocolEvent
import dev.p2pkit.core.protocol.ProtocolSessionState
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.yield
import kotlin.concurrent.atomics.AtomicInt
import kotlin.concurrent.atomics.ExperimentalAtomicApi
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

@OptIn(ExperimentalCoroutinesApi::class, ExperimentalAtomicApi::class)
class SessionCloseRetirementTest {

    @Test
    fun closeDoesNotWaitBehindAnOldWriterAfterRearmRetiresItsEpoch() = runTest {
        assertCloseSkipsRetiredEpoch(retireAfterCloseQueues = false)
    }

    @Test
    fun retirementEndsAnAlreadyQueuedCloseWaitWithoutReleasingTheWriter() = runTest {
        assertCloseSkipsRetiredEpoch(retireAfterCloseQueues = true)
    }

    @Test
    fun oldEpochRetirementDoesNotSuppressCloseOnAnAdoptedReplacement() = runTest {
        val fixture = Fixture(this)
        val rearming = backgroundScope.async { fixture.rearm() }
        var closing: Deferred<Unit>? = null
        try {
            runAtCurrentTimeUntil { rearming.isCompleted }
            assertTrue(rearming.await())
            assertEquals(1, fixture.initial.closeCalls.load())

            val close = backgroundScope.async(start = CoroutineStart.UNDISPATCHED) { fixture.session.close() }
            closing = close
            runAtCurrentTimeUntil { close.isCompleted }
            close.await()

            assertSame(fixture.replacement, fixture.protocol.closeTargets.tryReceive().getOrThrow())
            assertTrue(fixture.protocol.closeTargets.tryReceive().isFailure)
            assertEquals(1, fixture.replacement.closeCalls.load())
            assertTrue(fixture.replacementReader.isCompleted)
            assertEquals(ConnectionState.Closed, fixture.session.state.value)
        } finally {
            fixture.dispose()
            runAtCurrentTimeUntil {
                rearming.isCompleted && closing?.isCompleted != false && fixture.supervisor.isCompleted
            }
        }
    }

    private suspend fun TestScope.assertCloseSkipsRetiredEpoch(retireAfterCloseQueues: Boolean) {
        val retirementReached = CompletableDeferred<Unit>()
        val allowRetirement = CompletableDeferred<Unit>()
        val fixture = Fixture(this) {
            retirementReached.complete(Unit)
            if (retireAfterCloseQueues) allowRetirement.await()
        }
        val sending = backgroundScope.async(start = CoroutineStart.UNDISPATCHED) {
            fixture.session.send(P2pMessage.Text("held old-epoch write"))
        }
        val rearming = backgroundScope.async(start = CoroutineStart.UNDISPATCHED) { fixture.rearm() }
        var closing: Deferred<Unit>? = null
        try {
            assertTrue(fixture.protocol.messageEntered.isCompleted)
            runAtCurrentTimeUntil { retirementReached.isCompleted }
            if (!retireAfterCloseQueues) {
                runAtCurrentTimeUntil { fixture.initial.closeCompleted.isCompleted }
            }
            val closeStartedAt = testScheduler.currentTime
            val close = backgroundScope.async(start = CoroutineStart.UNDISPATCHED) { fixture.session.close() }
            closing = close
            if (retireAfterCloseQueues) {
                assertEquals(ConnectionState.Closing, fixture.session.state.value)
                assertFalse(close.isCompleted)
                allowRetirement.complete(Unit)
                runCurrent()
            }

            // Never advance the CLOSE deadline or release the admitted writer.
            // Only real cleanup workers are allowed to settle while the test
            // scheduler remains at this exact virtual instant.
            runAtCurrentTimeUntil { close.isCompleted }
            close.await()
            assertEquals(closeStartedAt, testScheduler.currentTime)
            assertEquals(ConnectionState.Closed, fixture.session.state.value)
            assertTrue(sending.isActive, "close must finish before the old writer releases sendMutex")
            assertTrue(fixture.protocol.closeTargets.tryReceive().isFailure)
            assertEquals(1, fixture.initial.closeCalls.load())

            fixture.protocol.releaseMessage.complete(Unit)
            runAtCurrentTimeUntil { sending.isCompleted && rearming.isCompleted }
            sending.await()
            assertFalse(rearming.await(), "Closing must reject the replacement epoch")
            assertEquals(1, fixture.replacement.closeCalls.load())
            assertTrue(fixture.replacementReader.isCompleted)
        } finally {
            allowRetirement.complete(Unit)
            fixture.dispose()
            runAtCurrentTimeUntil {
                sending.isCompleted && rearming.isCompleted && closing?.isCompleted != false &&
                    fixture.supervisor.isCompleted
            }
        }
    }

    private fun TestScope.runAtCurrentTimeUntil(ready: () -> Boolean) {
        // Blocking the runTest body prevents automatic virtual-time advancement
        // from outrunning production cleanup on its independent dispatcher.
        // The real timeout is only a harness deadlock guard, not the assertion.
        runBlocking(Dispatchers.Default) {
            withTimeout(5_000L) {
                while (!ready()) {
                    testScheduler.runCurrent()
                    yield()
                }
            }
        }
    }

    private class Fixture(testScope: TestScope, beforeRawClose: (suspend () -> Unit)? = null) {
        val supervisor = SupervisorJob(testScope.backgroundScope.coroutineContext[Job])
        private val scope = CoroutineScope(StandardTestDispatcher(testScope.testScheduler) + supervisor)
        val initial = CountingConnection(FakeConnectionPair().a)
        val replacement = CountingConnection(FakeConnectionPair().a)
        val protocol = HeldMessageProtocol(DefaultP2pProtocol(clock = { testScope.testScheduler.currentTime }))
        val replacementReader = scope.launch(start = CoroutineStart.UNDISPATCHED) { awaitCancellation() }
        val session = P2pSessionImpl(
            id = "close-retirement",
            peer = Peer(PeerId("close-retirement-peer"), "Peer", Platform.JVM_DESKTOP, setOf(TransportKind.LAN)),
            initialConnection = initial,
            initialEvents = Channel<ProtocolEvent>(Channel.UNLIMITED),
            protocol = protocol,
            parentScope = scope,
            keepAlive = KeepAliveConfig(60_000L, 120_000L),
            clock = { testScope.testScheduler.currentTime },
            logger = P2pLogger.NoOp,
            beforeRearmRawCloseForTest = beforeRawClose
        ).also { it.start() }

        suspend fun rearm(): Boolean = session.rearmWith(
            newConnection = replacement,
            newEvents = Channel(Channel.UNLIMITED),
            newReaderJob = replacementReader
        )

        fun dispose() {
            protocol.releaseMessage.complete(Unit)
            supervisor.cancel()
        }
    }

    private class HeldMessageProtocol(private val delegate: P2pProtocol) : P2pProtocol by delegate {
        val messageEntered = CompletableDeferred<Unit>()
        val releaseMessage = CompletableDeferred<Unit>()
        val closeTargets = Channel<RawConnection>(Channel.UNLIMITED)

        override suspend fun sendMessage(
            connection: RawConnection,
            message: P2pMessage,
            sessionState: ProtocolSessionState
        ) {
            messageEntered.complete(Unit)
            releaseMessage.await()
        }

        override suspend fun sendClose(connection: RawConnection) {
            closeTargets.trySend(connection).getOrThrow()
            delegate.sendClose(connection)
        }
    }

    private class CountingConnection(private val delegate: RawConnection) : RawConnection by delegate {
        val closeCalls = AtomicInt(0)
        val closeCompleted = CompletableDeferred<Unit>()

        override suspend fun close() {
            closeCalls.addAndFetch(1)
            delegate.close()
            closeCompleted.complete(Unit)
        }
    }
}
