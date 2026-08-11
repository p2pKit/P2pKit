package dev.p2pkit.core.internal

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.KeepAliveConfig
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.protocol.DefaultP2pProtocol
import dev.p2pkit.core.protocol.ProtocolEvent
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals

@OptIn(ExperimentalCoroutinesApi::class)
class SessionReconnectFailureTest {

    @Test
    fun unexpectedReconnectHandlerFailureTransitionsSessionToFailed() = runTest {
        val fixture = reconnectingSession()
        fixture.session.reconnectHandler = object : ReconnectHandler {
            override suspend fun onConnectionLost(session: P2pSessionImpl) {
                throw IllegalStateException("reconnect driver defect")
            }
        }
        fixture.session.start()

        fixture.events.close()
        testScheduler.runCurrent()

        assertEquals(ConnectionState.Failed, fixture.session.state.value)
        fixture.supervisor.cancel()
    }

    @Test
    fun peerErrorIsReconnectEligibleRatherThanUnconditionallyTerminal() = runTest {
        val fixture = reconnectingSession()
        val handlerEntered = CompletableDeferred<Unit>()
        fixture.session.reconnectHandler = object : ReconnectHandler {
            override suspend fun onConnectionLost(session: P2pSessionImpl) {
                handlerEntered.complete(Unit)
                awaitCancellation()
            }
        }
        fixture.session.start()

        fixture.events.send(ProtocolEvent.PeerError("remote retryable error"))
        handlerEntered.await()

        assertEquals(ConnectionState.Reconnecting, fixture.session.state.value)
        fixture.supervisor.cancel()
    }

    private fun kotlinx.coroutines.test.TestScope.reconnectingSession(): SessionFixture {
        val pair = FakeConnectionPair()
        val supervisor = SupervisorJob()
        val scope = CoroutineScope(StandardTestDispatcher(testScheduler) + supervisor)
        val events = Channel<ProtocolEvent>(Channel.UNLIMITED)
        val session = P2pSessionImpl(
            id = "reconnect-handler-failure",
            peer = Peer(
                PeerId("reconnect-peer"),
                "Peer",
                Platform.JVM_DESKTOP,
                setOf(TransportKind.LAN)
            ),
            initialConnection = pair.a,
            initialEvents = events,
            protocol = DefaultP2pProtocol(clock = { testScheduler.currentTime }),
            parentScope = scope,
            keepAlive = KeepAliveConfig(60_000, 120_000),
            clock = { testScheduler.currentTime },
            logger = P2pLogger.NoOp
        )
        return SessionFixture(session, events, supervisor)
    }

    private data class SessionFixture(
        val session: P2pSessionImpl,
        val events: Channel<ProtocolEvent>,
        val supervisor: Job
    )
}
