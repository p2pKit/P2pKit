package dev.p2pkit.core.internal

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.KeepAliveConfig
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.protocol.DefaultP2pProtocol
import dev.p2pkit.core.protocol.ProtocolEvent
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.RecordingLogger
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestCoroutineScheduler
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/** Virtual diagnostic deadlines, with real bounded settlement of the existing independent cleanup workers. */
@OptIn(ExperimentalCoroutinesApi::class)
class StuckReconnectWatchdogTest {

    @Test
    fun resolvedEpisodeCannotWarnEarlyDuringANewerReconnect() = runBlocking {
        withFixture {
            loseConnection("episode A")
            advanceBy(1_000)
            rearm()
            advanceBy(1_000)
            loseConnection("episode B")
            repeat(3) { session.notifyPathLost() }
            scheduler.runCurrent()

            advanceBy(28_000)
            assertTrue(stuckWarnings.isEmpty(), "episode A's deadline must not diagnose episode B")
            advanceBy(1_999)
            assertTrue(stuckWarnings.isEmpty(), "the new episode has not reached its own deadline")
            advanceBy(1)
            assertEquals(1, stuckWarnings.size)
            assertTrue("cause=peer error: episode B" in stuckWarnings.single())
            advanceBy(30_000)
            assertEquals(1, stuckWarnings.size, "duplicate loss signals must not arm extra diagnostics")
        }
    }

    @Test
    fun successfulFlapsRetireEveryDiagnosticWithoutGrowingSessionChildren() = runBlocking {
        withFixture {
            val baselineCount = liveChildren().size
            repeat(10) {
                val beforeLoss = liveChildren()
                loseConnection()
                val watchdog = (liveChildren() - beforeLoss).single()
                advanceBy(100)
                rearm()
                assertTrue(watchdog.isCancelled && watchdog.isCompleted)
                assertEquals(baselineCount, liveChildren().size, "successful flap ${it + 1} retained a timer")
            }
            advanceBy(30_000)
            assertTrue(stuckWarnings.isEmpty())
            logger.assertNoUnexpectedWarnOrError()
        }
    }

    @Test
    fun eagerlyEnteredHandlerOwnsAnUnstartedTimerAndImmediateRearmCancelsIt() = runBlocking {
        withFixture(eager = true) {
            val beforeLoss = liveChildren()
            val timersAtHandlerEntry = CompletableDeferred<List<Job>>()
            val handlerJob = CompletableDeferred<Job>()
            val accepted = CompletableDeferred<Boolean>()
            val replacement = newEpoch()
            session.reconnectHandler = object : ReconnectHandler {
                override suspend fun onConnectionLost(session: P2pSessionImpl) {
                    handlerJob.complete(checkNotNull(currentCoroutineContext()[Job]))
                    // This handler enters inline, before onConnectionLost can
                    // reach the old fire-and-forget launch after the handler.
                    timersAtHandlerEntry.complete(
                        (liveChildren() - beforeLoss).filter { !it.isActive && !it.isCompleted }
                    )
                    accepted.complete(session.rearmWith(replacement.pair.a, replacement.events))
                }
            }

            session.notifyPathLost()
            assertTrue(timersAtHandlerEntry.isCompleted, "the handler must enter eagerly, not after a scheduler tick")
            val registered = timersAtHandlerEntry.await()
            assertEquals(1, registered.size, "register the LAZY timer before allowing an immediate reconnect handler")
            assertTrue(settle {
                accepted.await().also { handlerJob.await().join() }
            })
            assertEquals(ConnectionState.Connected, session.state.value)
            assertTrue(registered.single().isCancelled && registered.single().isCompleted)
            assertEquals(beforeLoss.size, liveChildren().size)
            advanceBy(30_000)
            logger.assertNoUnexpectedWarnOrError()
        }
    }

    @Test
    fun localClosingRetiresDiagnosticBeforeWaitingForTheCloseFrame() = runBlocking {
        withFixture {
            val beforeLoss = liveChildren()
            loseConnection()
            val watchdog = (liveChildren() - beforeLoss).single()
            current.pair.a.suspendWrites()
            val closing = async(start = CoroutineStart.UNDISPATCHED) { session.close() }
            try {
                scheduler.runCurrent()
                assertEquals(ConnectionState.Closing, session.state.value)
                assertTrue(watchdog.isCancelled && watchdog.isCompleted, "Closing must retire the parked timer")
                advanceBy(30_000)
                assertTrue(stuckWarnings.isEmpty())
            } finally {
                current.pair.a.resumeWrites()
                settle { closing.await() }
            }
            assertEquals(ConnectionState.Closed, session.state.value)
        }
    }

    @Test
    fun terminalClaimRetiresDiagnosticBeforeTerminalStatePublication() = runBlocking {
        val claimed = CompletableDeferred<Unit>()
        val releaseClaim = CompletableDeferred<Unit>()
        withFixture(afterTerminalClaim = {
            claimed.complete(Unit)
            releaseClaim.await()
        }) {
            try {
                val beforeLoss = liveChildren()
                loseConnection()
                val watchdog = (liveChildren() - beforeLoss).single()
                val exhausting = async(start = CoroutineStart.UNDISPATCHED) { session.markFailedAfterExhaustion() }
                try {
                    assertTrue(claimed.isCompleted)
                    scheduler.runCurrent()
                    assertEquals(ConnectionState.Reconnecting, session.state.value)
                    assertTrue(watchdog.isCancelled && watchdog.isCompleted, "terminal ownership must retire the timer")
                    advanceBy(30_000)
                    assertTrue(stuckWarnings.isEmpty(), "a claimed terminal epoch is not a stuck reconnect")
                } finally {
                    releaseClaim.complete(Unit)
                    settle { exhausting.await() }
                }
                assertEquals(ConnectionState.Failed, session.state.value)
            } finally {
                releaseClaim.complete(Unit)
            }
        }
    }

    private suspend fun withFixture(
        eager: Boolean = false,
        afterTerminalClaim: suspend () -> Unit = {},
        block: suspend Fixture.() -> Unit
    ) {
        val fixture = Fixture(eager, afterTerminalClaim)
        try {
            fixture.block()
        } finally {
            fixture.cleanup()
        }
    }

    private class Fixture(eager: Boolean, afterTerminalClaim: suspend () -> Unit) {
        val scheduler = TestCoroutineScheduler()
        private val supervisor = SupervisorJob()
        private val scope = CoroutineScope(
            (if (eager) UnconfinedTestDispatcher(scheduler) else StandardTestDispatcher(scheduler)) + supervisor
        )
        private val ownedEpochs = mutableListOf<Epoch>()
        var current = newEpoch()
            private set
        val logger = RecordingLogger()
        val session = P2pSessionImpl(
            id = "stuck-reconnect-watchdog",
            peer = Peer(PeerId("watchdog-peer"), "Peer", Platform.JVM_DESKTOP, setOf(TransportKind.LAN)),
            initialConnection = current.pair.a,
            initialEvents = current.events,
            protocol = DefaultP2pProtocol(clock = { scheduler.currentTime }),
            parentScope = scope,
            keepAlive = KeepAliveConfig(3_600_000, 7_200_000),
            clock = { scheduler.currentTime },
            logger = logger,
            afterTerminalClaimForTest = afterTerminalClaim
        )
        private val sessionJob = supervisor.children.single()
        val stuckWarnings: List<String>
            get() = logger.warnings.filter { "STUCK in Reconnecting" in it }

        init {
            session.reconnectHandler = object : ReconnectHandler {
                override suspend fun onConnectionLost(session: P2pSessionImpl) = Unit
            }
            session.start()
            scheduler.runCurrent()
        }

        fun newEpoch(): Epoch = Epoch().also { ownedEpochs += it }

        fun liveChildren(): Set<Job> = sessionJob.children.filterNot { it.isCompleted }.toSet()

        suspend fun loseConnection(reason: String? = null) {
            if (reason == null) session.notifyPathLost() else current.events.send(ProtocolEvent.PeerError(reason))
            scheduler.runCurrent()
            assertEquals(ConnectionState.Reconnecting, session.state.value)
        }

        fun advanceBy(millis: Long) {
            scheduler.advanceTimeBy(millis)
            scheduler.runCurrent()
        }

        suspend fun rearm() {
            val old = current
            val replacement = newEpoch()
            assertTrue(settle { session.rearmWith(replacement.pair.a, replacement.events) })
            current = replacement
            assertEquals(ConnectionState.Connected, session.state.value)
            assertEquals(ConnectionState.Closed, old.pair.a.state.value)
        }

        suspend fun <T> settle(block: suspend () -> T): T = coroutineScope {
            val operation = async(Dispatchers.Default) { block() }
            // runBlocking, rather than runTest, owns this real deadline.
            // Only runCurrent is pumped here: never jump virtual time while
            // a real cleanup worker is still settling an epoch or its reader.
            withTimeout(5_000) {
                while (!operation.isCompleted) {
                    scheduler.runCurrent()
                    delay(1)
                }
                scheduler.runCurrent()
                operation.await()
            }
        }

        suspend fun cleanup() = withContext(NonCancellable) {
            ownedEpochs.forEach { it.pair.a.resumeWrites() }
            try {
                settle {
                    session.close()
                    session.awaitRuntimeTermination()
                }
            } finally {
                supervisor.cancel()
                try {
                    settle { supervisor.join() }
                } finally {
                    ownedEpochs.forEach {
                        it.events.cancel()
                        it.pair.a.close()
                        it.pair.b.close()
                    }
                }
            }
        }
    }

    private class Epoch {
        val pair = FakeConnectionPair()
        val events = Channel<ProtocolEvent>(Channel.UNLIMITED)
    }
}
