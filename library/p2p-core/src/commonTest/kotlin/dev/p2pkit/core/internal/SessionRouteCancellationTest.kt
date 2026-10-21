package dev.p2pkit.core.internal

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.KeepAliveConfig
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.SessionFailureKind
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.protocol.DefaultP2pProtocol
import dev.p2pkit.core.protocol.ProtocolEvent
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.RecordingLogger
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.channels.ChannelIterator
import kotlinx.coroutines.channels.ReceiveChannel
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** A buffered channel failure may win over cancellation on its non-suspending receive path. */
class SessionRouteCancellationTest {
    @Test
    fun locallyCancelledRouteDoesNotReportBufferedCloseFailure() = runBlocking {
        withTimeout(5_000) {
            val fixture = Fixture(holdReceiveUntilRawClose = true)
            try {
                fixture.session.start()
                fixture.receiveEntered.await()
                fixture.session.close()
                fixture.session.awaitRuntimeTermination()
                assertFalse(fixture.routeWasActive.await(), "the real close transaction must cancel the epoch first")
                assertTrue(fixture.failureObserved.isCompleted, "the closed-channel failure must reach the router")
                assertEquals(ConnectionState.Closed, fixture.session.state.value)
                assertEquals(0 to 0L, fixture.session.applicationBacklogForTest())
                assertEquals(ConnectionState.Closed, fixture.pair.a.state.value)
                fixture.logger.assertNoUnexpectedWarnOrError()
            } finally {
                fixture.dispose()
            }
        }
    }

    @Test
    fun sameCloseFailureInActiveRouteIsStillReportedAndFailsSession() = runBlocking {
        withTimeout(5_000) {
            val fixture = Fixture()
            try {
                fixture.events.close(fixture.closeFailure)
                fixture.session.start()
                fixture.session.state.first { it == ConnectionState.Failed }
                fixture.session.awaitRuntimeTermination()
                val warning = fixture.logger.entries.single { it.level == RecordingLogger.Level.WARN }
                assertEquals("Session route-cancellation: routeEvents failed", warning.message)
                assertTrue(
                    warning.throwable === fixture.closeFailure || warning.throwable?.cause === fixture.closeFailure,
                    "coroutine stack recovery may copy the exception but must retain the exact original cause"
                )
                fixture.logger.assertNoUnexpectedWarnOrError { it == warning }
            } finally {
                fixture.dispose()
            }
        }
    }

    @Test
    fun remoteEofWithoutCloseStillFailsRatherThanBecomingCleanClose() = runBlocking {
        withTimeout(5_000) {
            val fixture = Fixture()
            try {
                fixture.events.close()
                fixture.session.start()
                fixture.session.state.first { it == ConnectionState.Failed }
                fixture.session.awaitRuntimeTermination()
                fixture.logger.assertNoUnexpectedWarnOrError()
            } finally {
                fixture.dispose()
            }
        }
    }

    @Test
    fun activeAuthenticationFailureRetainsTypedFailureAndDiagnostic() =
        assertTypedFailure(
            P2pError.AuthenticationFailed("test authentication failure"), SessionFailureKind.Authentication
        )

    @Test
    fun activeProtocolFailureRetainsTypedFailureAndDiagnostic() =
        assertTypedFailure(P2pError.ProtocolError("test protocol failure"), SessionFailureKind.Protocol)

    private fun assertTypedFailure(failure: P2pError, expectedKind: SessionFailureKind) = runBlocking {
        withTimeout(5_000) {
            val fixture = Fixture()
            try {
                fixture.events.close(failure)
                fixture.session.start()
                fixture.session.state.first { it == ConnectionState.Failed }
                fixture.session.awaitRuntimeTermination()
                assertEquals(expectedKind, fixture.session.connectionInfo.value.lastFailure?.kind)
                val warning = fixture.logger.entries.single { it.level == RecordingLogger.Level.WARN }
                assertSame(failure, warning.throwable)
                fixture.logger.assertNoUnexpectedWarnOrError { it == warning }
            } finally {
                fixture.dispose()
            }
        }
    }

    private class Fixture(private val holdReceiveUntilRawClose: Boolean = false) {
        val pair = FakeConnectionPair()
        val supervisor = SupervisorJob()
        val scope = CoroutineScope(Dispatchers.Default + supervisor)
        val logger = RecordingLogger()
        val events = Channel<ProtocolEvent>(Channel.UNLIMITED)
        val closeFailure = IllegalStateException("Secure connection is closed")
        val receiveEntered = CompletableDeferred<Unit>()
        val releaseReceive = CompletableDeferred<Unit>()
        val routeWasActive = CompletableDeferred<Boolean>()
        val failureObserved = CompletableDeferred<Unit>()
        private val gatedEvents = object : ReceiveChannel<ProtocolEvent> by events {
            override fun iterator(): ChannelIterator<ProtocolEvent> {
                val delegate = events.iterator()
                return object : ChannelIterator<ProtocolEvent> {
                    override suspend fun hasNext(): Boolean {
                        if (holdReceiveUntilRawClose) {
                            // Model a receive already in flight when raw close publishes its error.
                            // Same-dispatcher NonCancellable intentionally retains that late return;
                            // there is no sleep, loop, or production test hook.
                            val routeJob = checkNotNull(currentCoroutineContext()[Job])
                            receiveEntered.complete(Unit)
                            withContext(NonCancellable) { releaseReceive.await() }
                            routeWasActive.complete(routeJob.isActive)
                        }
                        return try {
                            delegate.hasNext()
                        } catch (failure: Throwable) {
                            if (failure === closeFailure || failure.cause === closeFailure) {
                                failureObserved.complete(Unit)
                            }
                            throw failure
                        }
                    }
                    override fun next(): ProtocolEvent = delegate.next()
                }
            }
        }
        private val raw = object : RawConnection by pair.a {
            override suspend fun close() {
                pair.a.close()
                if (holdReceiveUntilRawClose) {
                    events.close(closeFailure)
                    releaseReceive.complete(Unit)
                }
            }
        }
        val session = P2pSessionImpl(
            id = "route-cancellation",
            peer = Peer(PeerId("route-peer"), "Peer", Platform.JVM_DESKTOP, setOf(TransportKind.LAN)),
            initialConnection = raw,
            initialEvents = gatedEvents,
            protocol = DefaultP2pProtocol(clock = { 0L }),
            parentScope = scope,
            keepAlive = KeepAliveConfig(60_000, 120_000),
            clock = { 0L },
            logger = logger
        )

        suspend fun dispose() = withContext(NonCancellable) {
            withTimeout(5_000) {
                releaseReceive.complete(Unit)
                session.close()
                session.awaitRuntimeTermination()
                supervisor.cancelAndJoin()
                events.cancel()
                pair.a.close()
                pair.b.close()
            }
        }
    }
}
