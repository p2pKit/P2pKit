package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.RecordingLogger
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.async
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * AUDIT-2026-07 (CON-3) / coverage plan P1-04, commonTest half.
 *
 * Pins the inbound-acceptance resilience invariants of
 * [SessionManager.startAcceptingIncoming]:
 *
 *  1. A failure while setting up ONE inbound connection is isolated: the
 *     failed connection is released and logged, and a subsequent well-formed
 *     inbound connection still produces a session.
 *  2. An accept-loop failure (the transport's incoming flow terminating with
 *     a cause, exactly what the shipped accept loops produce on an accept
 *     error while not closed — fixture change F3) is surfaced through the
 *     injectable logger, does NOT escalate into the kit scope, and leaves the
 *     kit and its established sessions fully functional.
 *  3. Clean shutdown still terminates the accept collector promptly and
 *     produces no failure diagnostics (CancellationException is never
 *     swallowed, never logged as an inbound failure).
 */
class InboundAcceptResilienceTest {

    /** Warn logged by [SessionManager.startAcceptingIncoming]'s catch. */
    private val acceptLoopEndedFragment = "inbound acceptance ended"

    /** Warn logged by [SessionManager.handleIncoming] on per-connection failure. */
    private val setupFailedFragment = "Incoming session setup failed"

    private fun outgoingKit(name: String, outgoing: RawConnection): P2pKit =
        P2pKit.create {
            appId = AppId("com.example.test")
            deviceName = name
            keepAlive {
                pingIntervalMillis = 60_000
                timeoutMillis = 120_000
            }
            transports {
                register(AcceptResilienceFactory(FakeDataTransport(outgoingConnection = { outgoing })))
            }
        }

    private fun incomingKit(
        name: String,
        transport: FakeDataTransport,
        recordingLogger: RecordingLogger
    ): P2pKit = P2pKit.create {
        appId = AppId("com.example.test")
        deviceName = name
        logger = recordingLogger
        // Seed the incoming peer's id to the value the outgoing side dials
        // ("bob-id") so the HELLO peerId matches (same pattern as
        // SessionFlowTest).
        peerIdStorage = InMemoryPeerIdStorage(seed = PeerId("bob-id"))
        keepAlive {
            pingIntervalMillis = 60_000
            timeoutMillis = 120_000
        }
        transports {
            register(AcceptResilienceFactory(transport))
        }
    }

    @Test
    fun incomingSetupFailureDoesNotPreventSubsequentInboundSessions() = runBlocking {
        // A non-conforming inbound connection whose wire is already terminated:
        // the HELLO setup for it fails immediately (write fails / read is EOF).
        val badPair = FakeConnectionPair()
        badPair.hangUp(badPair.b)

        val goodPair = FakeConnectionPair()
        val bobLogger = RecordingLogger()
        val bobTransport = FakeDataTransport(
            preStagedIncoming = listOf(badPair.b, goodPair.b)
        )
        val bob = incomingKit("Bob", bobTransport, bobLogger)
        val alice = outgoingKit("Alice", goodPair.a)
        try {
            val outgoingDeferred = async { alice.connect(syntheticPeer("bob-id", "Bob")) }
            // The invariant: despite the earlier failed inbound handling, the
            // subsequent well-formed inbound connection still yields a session.
            val incomingSession = withTimeout(5_000) { bob.incomingSessions.first() }
            withTimeout(5_000) { outgoingDeferred.await() }
            assertEquals("Alice", incomingSession.peer.name)

            // The failed inbound handling was surfaced via the injectable
            // logger (not swallowed, not escalated).
            awaitLogged(bobLogger) { it.contains(setupFailedFragment) }
            bobLogger.assertNoUnexpectedWarnOrError { entry ->
                entry.level == RecordingLogger.Level.WARN &&
                    entry.message.contains(setupFailedFragment)
            }
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun acceptLoopFailureIsSurfacedAndKitSurvives() = runBlocking {
        val pair = FakeConnectionPair()
        val bobLogger = RecordingLogger()
        val bobTransport = FakeDataTransport(preStagedIncoming = listOf(pair.b))
        val bob = incomingKit("Bob", bobTransport, bobLogger)
        val alice = outgoingKit("Alice", pair.a)
        try {
            val outgoingDeferred = async { alice.connect(syntheticPeer("bob-id", "Bob")) }
            val incomingSession = withTimeout(5_000) { bob.incomingSessions.first() }
            val outgoing = withTimeout(5_000) { outgoingDeferred.await() }

            // Terminate the incoming flow with a cause — the exact signature
            // the shipped accept loops produce when accept() fails while the
            // transport is not closed (F3 / TST-3).
            bobTransport.failIncoming(IllegalStateException("emulated accept failure"))

            // The accept-loop failure is surfaced through the injectable
            // logger as a warn diagnostic...
            awaitLogged(bobLogger) { it.contains(acceptLoopEndedFragment) }

            // ...and the kit survives: the established session is unaffected
            // and still exchanges messages.
            val msg = exchangeMessage(
                from = outgoing,
                to = incomingSession,
                payload = P2pMessage.Text("still alive after accept-loop failure")
            )
            assertEquals(
                "still alive after accept-loop failure",
                assertIs<P2pMessage.Text>(msg).value
            )

            // No kit-scope escalation: the kit-scope CoroutineExceptionHandler
            // (AUDIT-2026-07 ARCH-4 rider) logs uncaught failures at error
            // level, so the absence of any error entry — and of any warn other
            // than the accept-loop diagnostic — proves the failure was handled
            // in the collector, not escalated.
            bobLogger.assertNoUnexpectedWarnOrError { entry ->
                entry.level == RecordingLogger.Level.WARN &&
                    entry.message.contains(acceptLoopEndedFragment)
            }

            // Shutdown still terminates promptly after the accept-loop failure.
            withTimeout(5_000) { alice.stop() }
            withTimeout(5_000) { bob.stop() }
        } finally {
            runCatching { alice.stop() }
            runCatching { bob.stop() }
        }
    }

    @Test
    fun cleanStopProducesNoInboundAcceptanceDiagnostics() = runBlocking {
        val bobLogger = RecordingLogger()
        val bobTransport = FakeDataTransport()
        val bob = incomingKit("Bob", bobTransport, bobLogger)
        try {
            bob.start()
            // Clean shutdown with the accept collector parked on a live
            // incoming flow: the collector must terminate promptly (bounded
            // stop) and cancellation must not be swallowed or misreported as
            // an inbound-acceptance failure.
            withTimeout(5_000) { bob.stop() }
            assertTrue(bobTransport.isClosed, "stop() must close the transport")
            assertTrue(
                bobLogger.warnings.none { it.contains(acceptLoopEndedFragment) },
                "clean shutdown must not be reported as an accept-loop failure"
            )
            assertTrue(
                bobLogger.errors.isEmpty(),
                "clean shutdown must not surface kit-scope errors, got: ${bobLogger.errors}"
            )
        } finally {
            runCatching { bob.stop() }
        }
    }

    /** Poll [logger]'s warn entries until [predicate] matches (bounded). */
    private suspend fun awaitLogged(
        logger: RecordingLogger,
        predicate: (String) -> Boolean
    ) {
        withTimeout(5_000) {
            while (logger.warnings.none(predicate)) delay(10)
        }
    }

    private suspend fun exchangeMessage(
        from: P2pSession,
        to: P2pSession,
        payload: P2pMessage
    ): P2pMessage = kotlinx.coroutines.coroutineScope {
        val ready = CompletableDeferred<Unit>()
        val received = async {
            to.incoming.onSubscription { ready.complete(Unit) }.first()
        }
        ready.await()
        from.send(payload)
        withTimeout(5_000) { received.await() }
    }

    private fun syntheticPeer(id: String, name: String): Peer = Peer(
        id = PeerId(id),
        name = name,
        platform = Platform.JVM_DESKTOP,
        supportedTransports = setOf(TransportKind.LAN)
    )
}

private class AcceptResilienceFactory(
    private val transport: FakeDataTransport
) : TransportFactory {
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = null)
}
