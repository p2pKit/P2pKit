package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pError
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
import dev.p2pkit.core.testfixtures.StatefulTestFailure
import dev.p2pkit.core.testfixtures.createTestKit
import dev.p2pkit.core.testfixtures.withTestKit
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.channels.ClosedSendChannelException
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.channels.Channel
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

    private fun outgoingKit(
        name: String,
        outgoing: RawConnection,
        recordingLogger: RecordingLogger
    ): P2pKit =
        createTestKit {
            logger = recordingLogger
            appId = AppId("com.example.test")
            deviceName = name
            // Multi-peer protocol fixtures must not inherit platform-persistent
            // identity from a previous JVM/iOS test process.
            peerIdStorage = InMemoryPeerIdStorage(seed = PeerId("alice-id"))
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
        transport: DataTransport,
        recordingLogger: RecordingLogger
    ): P2pKit = createTestKit {
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
        lateinit var bobLogger: RecordingLogger
        val bobTransport = FakeDataTransport(
            preStagedIncoming = listOf(badPair.b, goodPair.b)
        )
        withTestKit(
            create = { recorder ->
                bobLogger = recorder
                incomingKit("Bob", bobTransport, recorder)
            },
            verifyDiagnostics = { recorder ->
                val diagnostics = recorder.entries.filter {
                    it.level == RecordingLogger.Level.WARN || it.level == RecordingLogger.Level.ERROR
                }
                assertEquals(1, diagnostics.size)
                val entry = diagnostics.single()
                assertEquals(RecordingLogger.Level.WARN, entry.level)
                assertEquals("Incoming session setup failed", entry.message)
                val failure = assertIs<P2pError.ConnectionFailed>(entry.throwable)
                // This peer was already hung up before the kit could send its first HELLO.
                val closed = assertIs<ClosedSendChannelException>(failure.cause)
                assertEquals("Channel was closed", closed.message)
                assertEquals("Plaintext HELLO failed: ${closed.message}", failure.reason)
                assertTrue(failure.suppressedExceptions.isEmpty())
                assertTrue(closed.suppressedExceptions.isEmpty())
            }
        ) { bob ->
            withTestKit(
                create = { recorder ->
                    outgoingKit("Alice", goodPair.a, recordingLogger = recorder)
                }
            ) { alice ->
                val outgoingDeferred = async { alice.connect(syntheticPeer("bob-id", "Bob")) }
                // The invariant: despite the earlier failed inbound handling, the
                // subsequent well-formed inbound connection still yields a session.
                val incomingSession = withTimeout(5_000) { bob.incomingSessions.first() }
                withTimeout(5_000) { outgoingDeferred.await() }
                assertEquals("Alice", incomingSession.peer.name)

                // The failed inbound handling was surfaced via the injectable
                // logger (not swallowed, not escalated).
                awaitLogged(bobLogger) { it.contains(setupFailedFragment) }
            }
        }
    }

    @Test
    fun acceptLoopFailureIsSurfacedAndKitSurvives() = runBlocking {
        val pair = FakeConnectionPair()
        lateinit var bobLogger: RecordingLogger
        val acceptFailure = StatefulTestFailure("emulated accept failure")
        val bobIncoming = FakeDataTransport(preStagedIncoming = listOf(pair.b))
        val bobTransport = SingleAcceptFailureTransport(bobIncoming)
        withTestKit(
            create = { recorder ->
                bobLogger = recorder
                incomingKit("Bob", bobTransport, recorder)
            },
            verifyDiagnostics = { recorder -> assertAcceptFailureDiagnostics(recorder, acceptFailure) }
        ) { bob ->
            withTestKit(
                create = { recorder ->
                    outgoingKit("Alice", pair.a, recordingLogger = recorder)
                }
            ) { alice ->
                val outgoingDeferred = async { alice.connect(syntheticPeer("bob-id", "Bob")) }
                val incomingSession = withTimeout(5_000) { bob.incomingSessions.first() }
                val outgoing = withTimeout(5_000) { outgoingDeferred.await() }

                // Terminate the incoming flow with a cause — the exact signature
                // the shipped accept loops produce when accept() fails while the
                // transport is not closed (F3 / TST-3).
                bobIncoming.failIncoming(acceptFailure)

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

                // Shutdown still terminates promptly after the accept-loop failure.
                withTimeout(5_000) { alice.stop() }
                withTimeout(5_000) { bob.stop() }
            }
        }
    }

    @Test
    fun acceptLoopFailureIsRecollectedAndAcceptsTheNextConnection() = runBlocking {
        val pair = FakeConnectionPair()
        lateinit var logger: RecordingLogger
        val acceptFailure = IllegalStateException("emulated transient accept failure")
        val transport = RecoveringDataTransport(firstFailure = acceptFailure)
        withTestKit(
            create = { recorder ->
                logger = recorder
                createTestKit {
                    appId = AppId("com.example.test")
                    deviceName = "Bob"
                    this.logger = recorder
                    peerIdStorage = InMemoryPeerIdStorage(seed = PeerId("bob-id"))
                    keepAlive {
                        pingIntervalMillis = 60_000
                        timeoutMillis = 120_000
                    }
                    transports { register(RecoveringTransportFactory(transport)) }
                }
            },
            verifyDiagnostics = { recorder -> assertAcceptFailureDiagnostics(recorder, acceptFailure) }
        ) { bob ->
            withTestKit(
                create = { recorder ->
                    outgoingKit("Alice", pair.a, recordingLogger = recorder)
                }
            ) { alice ->
                withTimeout(5_000) { transport.recollected.await() }
                transport.emitIncoming(pair.b)

                val outgoing = async { alice.connect(syntheticPeer("bob-id", "Bob")) }
                val incoming = withTimeout(5_000) { bob.incomingSessions.first() }
                withTimeout(5_000) { outgoing.await() }

                assertEquals("Alice", incoming.peer.name)
                awaitLogged(logger) { it.contains(acceptLoopEndedFragment) }
            }
        }
    }

    @Test
    fun transportThrownCancellationIsRecollectedWhileCollectorRemainsActive() = runBlocking {
        val pair = FakeConnectionPair()
        lateinit var logger: RecordingLogger
        val acceptFailure = CancellationException("transport-owned cancellation")
        val transport = RecoveringDataTransport(firstFailure = acceptFailure)
        withTestKit(
            create = { recorder ->
                logger = recorder
                createTestKit {
                    appId = AppId("com.example.test")
                    deviceName = "Bob"
                    this.logger = recorder
                    peerIdStorage = InMemoryPeerIdStorage(seed = PeerId("bob-id"))
                    keepAlive {
                        pingIntervalMillis = 60_000
                        timeoutMillis = 120_000
                    }
                    transports { register(RecoveringTransportFactory(transport)) }
                }
            },
            verifyDiagnostics = { recorder -> assertAcceptFailureDiagnostics(recorder, acceptFailure) }
        ) { bob ->
            withTestKit(
                create = { recorder ->
                    outgoingKit("Alice", pair.a, recordingLogger = recorder)
                }
            ) { alice ->
                withTimeout(5_000) { transport.recollected.await() }
                transport.emitIncoming(pair.b)

                val outgoing = async { alice.connect(syntheticPeer("bob-id", "Bob")) }
                val incoming = withTimeout(5_000) { bob.incomingSessions.first() }
                withTimeout(5_000) { outgoing.await() }

                assertEquals("Alice", incoming.peer.name)
                awaitLogged(logger) { it.contains(acceptLoopEndedFragment) }
            }
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
            // Also reject normal-completion warnings, not just the exception branch's wording.
            bobLogger.assertNoUnexpectedWarnOrError()
        } finally {
            runCatching { bob.stop() }
        }
    }

    /** One controlled source failure, with no escalation or extra shutdown/recollection diagnostics. */
    private fun assertAcceptFailureDiagnostics(recorder: RecordingLogger, failure: Throwable) {
        assertEquals(
            listOf(RecordingLogger.Entry(RecordingLogger.Level.WARN, "inbound acceptance ended for LAN", failure)),
            recorder.entries.filter {
                it.level == RecordingLogger.Level.WARN || it.level == RecordingLogger.Level.ERROR
            }
        )
        assertTrue(failure.suppressedExceptions.isEmpty())
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
    private val transport: DataTransport
) : TransportFactory {
    override val descriptor =
        dev.p2pkit.core.transport.TransportDescriptor.dataOnly(transport.type)
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = null)
}

/** The survival test injects one accept fault; its separate recovery tests exercise fresh acceptance. */
private class SingleAcceptFailureTransport(
    private val delegate: FakeDataTransport
) : DataTransport by delegate {
    private var collected = false

    override fun incomingConnections(): Flow<RawConnection> = flow {
        // Recollecting the same failed channel would repeat its original cause forever. Park only
        // subsequent collections, while retaining the real first failIncoming flow and lifecycle.
        if (collected) awaitCancellation()
        collected = true
        delegate.incomingConnections().collect { emit(it) }
    }
}

private class RecoveringTransportFactory(
    private val transport: RecoveringDataTransport
) : TransportFactory {
    override val descriptor =
        dev.p2pkit.core.transport.TransportDescriptor.dataOnly(transport.type)
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = null)
}

private class RecoveringDataTransport(
    private val firstFailure: Throwable =
        IllegalStateException("emulated transient accept failure")
) : DataTransport {
    override val type: TransportKind = TransportKind.LAN
    override val priority: Int = 100
    private val incoming = Channel<RawConnection>(Channel.UNLIMITED)
    private var collections = 0
    val recollected = CompletableDeferred<Unit>()

    override fun canConnect(peer: InternalPeer): Boolean = false

    override suspend fun connect(peer: InternalPeer): RawConnection =
        error("outbound connect is not supported")

    override fun incomingConnections(): Flow<RawConnection> = flow {
        collections += 1
        if (collections == 1) {
            throw firstFailure
        }
        recollected.complete(Unit)
        incoming.receiveAsFlow().collect { emit(it) }
    }

    fun emitIncoming(connection: RawConnection) {
        check(incoming.trySend(connection).isSuccess)
    }

    override suspend fun stop() = Unit

    override suspend fun close() {
        incoming.close()
    }
}
