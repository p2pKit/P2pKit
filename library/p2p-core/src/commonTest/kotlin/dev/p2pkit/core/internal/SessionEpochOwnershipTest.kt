package dev.p2pkit.core.internal

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.KeepAliveConfig
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.protocol.DefaultP2pProtocol
import dev.p2pkit.core.protocol.P2pProtocol
import dev.p2pkit.core.protocol.ProtocolEvent
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlin.concurrent.atomics.AtomicInt
import kotlin.concurrent.atomics.ExperimentalAtomicApi
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertTrue

@OptIn(ExperimentalCoroutinesApi::class, ExperimentalAtomicApi::class)
class SessionEpochOwnershipTest {

    @Test
    fun terminalCloseCancelsAndJoinsSessionOwnedProtocolReader() = runTest {
        val harness = harness()
        val readerStopped = CompletableDeferred<Unit>()
        val reader = harness.scope.launch(start = CoroutineStart.UNDISPATCHED) {
            try {
                awaitCancellation()
            } finally {
                readerStopped.complete(Unit)
            }
        }
        val session = harness.newSession(initialReaderJob = reader)
        session.start()

        try {
            session.close()
            assertTrue(reader.isCompleted)
            assertTrue(readerStopped.isCompleted)
            assertEquals(ConnectionState.Closed, session.state.value)
        } finally {
            harness.supervisor.cancel()
        }
    }

    @Test
    fun rearmTransfersReaderOwnershipAndTerminalCloseSettlesReplacement() = runTest {
        val harness = harness()
        val oldReader = harness.scope.parkedReader()
        val session = harness.newSession(initialReaderJob = oldReader)
        session.start()
        val replacementPair = FakeConnectionPair()
        val replacementEvents = Channel<ProtocolEvent>(Channel.UNLIMITED)
        val replacementReader = harness.scope.parkedReader()

        try {
            assertTrue(
                session.rearmWith(
                    replacementPair.a,
                    replacementEvents,
                    newReaderJob = replacementReader
                )
            )
            assertTrue(oldReader.isCompleted, "the previous reader must be joined before adoption")
            assertTrue(replacementReader.isActive)
            assertEquals(ConnectionState.Closed, harness.pair.a.state.value)

            session.close()
            assertTrue(replacementReader.isCompleted)
            assertEquals(ConnectionState.Closed, replacementPair.a.state.value)
        } finally {
            harness.supervisor.cancel()
        }
    }

    @Test
    fun rearmCleanupNeverHoldsConnectionLockAgainstConcurrentClose() = runTest {
        lateinit var countedConnection: CloseCountingRawConnection
        val harness = harness(blockPong = true) { connection ->
            CloseCountingRawConnection(connection).also { countedConnection = it }
        }
        val session = harness.newSession()
        session.start()
        harness.events.send(ProtocolEvent.Ping)
        runCurrent()
        harness.blockingProtocol!!.pongEntered.await()

        val replacement = FakeConnectionPair()
        val rearm = async {
            session.rearmWith(
                replacement.a,
                Channel(Channel.UNLIMITED)
            )
        }
        runCurrent()

        val close = async(start = CoroutineStart.UNDISPATCHED) { session.close() }
        runCurrent()
        assertEquals(
            ConnectionState.Closing,
            session.state.value,
            "close must commit Closing while rearm waits for the old epoch"
        )

        harness.blockingProtocol.pongRelease.complete(Unit)
        runCurrent()
        withContext(Dispatchers.Default) {
            withTimeout(5_000) {
                rearm.join()
                close.join()
            }
        }
        assertFalse(rearm.await(), "a replacement must not commit after close wins")
        close.await()
        assertEquals(ConnectionState.Closed, session.state.value)
        assertEquals(ConnectionState.Closed, replacement.a.state.value)
        assertEquals(
            1,
            countedConnection.closeCalls.load(),
            "reconnect cleanup and terminal cleanup must share one raw close owner"
        )
        harness.supervisor.cancel()
    }

    @Test
    fun remoteCloseCannotStealAnInProgressLocalCloseTransaction() = runTest {
        val harness = harness()
        val session = harness.newSession()
        session.start()
        harness.pair.a.suspendWrites()

        try {
            val localClose = async { session.close() }
            runCurrent()
            assertEquals(ConnectionState.Closing, session.state.value)

            harness.events.send(ProtocolEvent.Close)
            runCurrent()
            assertEquals(
                ConnectionState.Closing,
                session.state.value,
                "a remote terminal event must not take ownership from local close()"
            )

            harness.pair.a.resumeWrites()
            runCurrent()
            localClose.await()
            assertEquals(ConnectionState.Closed, session.state.value)
        } finally {
            harness.pair.a.resumeWrites()
            harness.supervisor.cancel()
        }
    }

    @Test
    fun rearmRejectsReusingTheCurrentRawConnection() = runTest {
        val harness = harness()
        val session = harness.newSession()
        session.start()

        try {
            val failure = assertFailsWith<dev.p2pkit.core.P2pError.ConnectionFailed> {
                session.rearmWith(
                    harness.pair.a,
                    Channel(Channel.UNLIMITED)
                )
            }
            assertIs<CleanupAggregateException>(failure.cause)
            assertEquals(ConnectionState.Failed, session.state.value)
            assertEquals(ConnectionState.Closed, harness.pair.a.state.value)
        } finally {
            harness.supervisor.cancel()
        }
    }

    private fun TestScope.harness(
        blockPong: Boolean = false,
        wrapConnection: (RawConnection) -> RawConnection = { it }
    ): Harness {
        val pair = FakeConnectionPair()
        val supervisor = SupervisorJob()
        val scope = CoroutineScope(StandardTestDispatcher(testScheduler) + supervisor)
        val events = Channel<ProtocolEvent>(Channel.UNLIMITED)
        val delegate = DefaultP2pProtocol(clock = { testScheduler.currentTime })
        val blocking = if (blockPong) BlockingPongProtocol(delegate) else null
        return Harness(
            pair,
            wrapConnection(pair.a),
            scope,
            supervisor,
            events,
            blocking,
            blocking ?: delegate
        )
    }

    private fun CoroutineScope.parkedReader(): Job = launch(start = CoroutineStart.UNDISPATCHED) {
        awaitCancellation()
    }

    private data class Harness(
        val pair: FakeConnectionPair,
        val initialConnection: RawConnection,
        val scope: CoroutineScope,
        val supervisor: Job,
        val events: Channel<ProtocolEvent>,
        val blockingProtocol: BlockingPongProtocol?,
        val protocol: P2pProtocol
    ) {
        fun newSession(initialReaderJob: Job? = null): P2pSessionImpl = P2pSessionImpl(
            id = "epoch-ownership-session",
            peer = Peer(
                PeerId("epoch-ownership-peer"),
                "Epoch peer",
                Platform.JVM_DESKTOP,
                setOf(TransportKind.LAN)
            ),
            initialConnection = initialConnection,
            initialEvents = events,
            initialReaderJob = initialReaderJob,
            protocol = protocol,
            parentScope = scope,
            keepAlive = KeepAliveConfig(60_000, 120_000),
            clock = { 0L },
            logger = P2pLogger.NoOp
        )
    }
}

@OptIn(ExperimentalAtomicApi::class)
private class CloseCountingRawConnection(
    private val delegate: RawConnection
) : RawConnection by delegate {
    val closeCalls = AtomicInt(0)

    override suspend fun close() {
        closeCalls.addAndFetch(1)
        delegate.close()
    }
}

private class BlockingPongProtocol(
    delegate: P2pProtocol
) : P2pProtocol by delegate {
    val pongEntered = CompletableDeferred<Unit>()
    val pongRelease = CompletableDeferred<Unit>()

    override suspend fun sendPong(connection: dev.p2pkit.core.transport.RawConnection) {
        pongEntered.complete(Unit)
        withContext(NonCancellable) { pongRelease.await() }
    }
}
