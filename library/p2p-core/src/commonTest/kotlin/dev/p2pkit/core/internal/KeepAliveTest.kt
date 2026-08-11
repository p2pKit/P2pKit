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
import dev.p2pkit.core.protocol.ProtocolEvent
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.transfer.PreparedFileSource
import dev.p2pkit.core.transfer.Sha256Digest
import kotlinx.io.Buffer
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.withContext
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * Pins the keep-alive contract from Spec §14, both directions:
 *  - **negative:** if no `PONG` is observed within `timeoutMillis`, the session
 *    transitions to [ConnectionState.Failed];
 *  - **positive:** while `PONG`s keep arriving the session stays
 *    [ConnectionState.Connected] across many timeout windows; and an inbound
 *    `PING` is answered with a `PONG` on the wire (the responder path).
 *
 * Each test constructs a [P2pSessionImpl] directly with a [FakeConnectionPair]
 * and a hand-fed events channel, so the keep-alive loop and event router can be
 * driven deterministically without a real socket or a SessionManager.
 *
 * Virtual time (fixture upgrade F9 / TST-12): the suite runs under `runTest`
 * with the session scope on a [StandardTestDispatcher] sharing the test
 * scheduler and the session/protocol clocks reading
 * `testScheduler.currentTime`, so keep-alive cadence and deadlines are exact
 * virtual-time arithmetic — no wall-clock waits, no scheduling jitter.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class KeepAliveTest {

    @Test
    fun slowMessageSubscriberDoesNotBlockPongOrRemoteClose() = runTest {
        val pair = FakeConnectionPair()
        val protocol = DefaultP2pProtocol(clock = { testScheduler.currentTime })
        val supervisor = SupervisorJob()
        val scope = CoroutineScope(StandardTestDispatcher(testScheduler) + supervisor)
        val events = Channel<ProtocolEvent>(Channel.UNLIMITED)
        val session = P2pSessionImpl(
            id = "control-plane-backpressure",
            peer = Peer(
                PeerId("slow-subscriber"),
                "Slow",
                Platform.JVM_DESKTOP,
                setOf(TransportKind.LAN)
            ),
            initialConnection = pair.a,
            initialEvents = events,
            protocol = protocol,
            parentScope = scope,
            keepAlive = KeepAliveConfig(60_000, 120_000),
            clock = { testScheduler.currentTime },
            logger = P2pLogger.NoOp
        )
        session.start()

        val firstDelivered = CompletableDeferred<Unit>()
        val releaseSubscriber = CompletableDeferred<Unit>()
        val subscriber = scope.launch(start = CoroutineStart.UNDISPATCHED) {
            session.incoming.collect {
                firstDelivered.complete(Unit)
                releaseSubscriber.await()
            }
        }
        val outbound = Channel<ProtocolEvent>(Channel.UNLIMITED)
        val decoder = scope.launch {
            protocol.events(pair.b).collect { outbound.send(it) }
        }

        try {
            events.send(ProtocolEvent.Message(P2pMessage.Text("first")))
            firstDelivered.await()
            // The delivery coroutine parks on this second message while the
            // protocol router remains free to process control events.
            events.send(ProtocolEvent.Message(P2pMessage.Text("second")))
            events.send(ProtocolEvent.Ping)
            assertEquals(ProtocolEvent.Pong, withTimeout(3_000) { outbound.receive() })

            events.send(ProtocolEvent.Close)
            assertEquals(
                ConnectionState.Closed,
                withTimeout(3_000) { session.state.first { it == ConnectionState.Closed } }
            )
        } finally {
            releaseSubscriber.complete(Unit)
            subscriber.cancel()
            decoder.cancel()
            supervisor.cancel()
        }
    }

    @Test
    fun applicationBacklogIsByteBoundedAndFailsInsteadOfDropping() = runTest {
        val pair = FakeConnectionPair()
        val protocol = DefaultP2pProtocol(clock = { testScheduler.currentTime })
        val supervisor = SupervisorJob()
        val scope = CoroutineScope(StandardTestDispatcher(testScheduler) + supervisor)
        val events = Channel<ProtocolEvent>(Channel.UNLIMITED)
        val session = P2pSessionImpl(
            id = "bounded-application-backlog",
            peer = Peer(PeerId("bounded-peer"), "Bounded", Platform.JVM_DESKTOP, setOf(TransportKind.LAN)),
            initialConnection = pair.a,
            initialEvents = events,
            protocol = protocol,
            parentScope = scope,
            keepAlive = KeepAliveConfig(60_000, 120_000),
            clock = { testScheduler.currentTime },
            logger = P2pLogger.NoOp
        )
        session.start()

        val firstDelivered = CompletableDeferred<Unit>()
        val releaseSubscriber = CompletableDeferred<Unit>()
        val subscriber = scope.launch(start = CoroutineStart.UNDISPATCHED) {
            session.incoming.collect {
                firstDelivered.complete(Unit)
                releaseSubscriber.await()
            }
        }
        try {
            events.send(ProtocolEvent.Message(P2pMessage.Text("block delivery")))
            firstDelivered.await()
            val maximumMessage = P2pMessage.Binary(ByteArray(4 * 1024 * 1024))
            events.send(ProtocolEvent.Message(maximumMessage))
            events.send(ProtocolEvent.Message(maximumMessage))
            events.send(ProtocolEvent.Message(P2pMessage.Binary(byteArrayOf(1))))

            assertEquals(
                ConnectionState.Failed,
                withTimeout(3_000) { session.state.first { it == ConnectionState.Failed } }
            )
        } finally {
            releaseSubscriber.complete(Unit)
            subscriber.cancel()
            supervisor.cancel()
        }
    }

    @Test
    fun inFlightApplicationMessageRemainsInsideBacklogLimit() = runTest {
        val pair = FakeConnectionPair()
        val protocol = DefaultP2pProtocol(clock = { testScheduler.currentTime })
        val supervisor = SupervisorJob()
        val scope = CoroutineScope(StandardTestDispatcher(testScheduler) + supervisor)
        val events = Channel<ProtocolEvent>(Channel.UNLIMITED)
        val deliveryClaimed = CompletableDeferred<Unit>()
        val releaseDelivery = CompletableDeferred<Unit>()
        var deliveryCalls = 0
        val session = P2pSessionImpl(
            id = "in-flight-backlog",
            peer = Peer(PeerId("in-flight-peer"), "Peer", Platform.JVM_DESKTOP, setOf(TransportKind.LAN)),
            initialConnection = pair.a,
            initialEvents = events,
            protocol = protocol,
            parentScope = scope,
            keepAlive = KeepAliveConfig(60_000, 120_000),
            clock = { testScheduler.currentTime },
            logger = P2pLogger.NoOp,
            beforeApplicationMessageEmitForTest = {
                if (deliveryCalls++ == 0) {
                    deliveryClaimed.complete(Unit)
                    releaseDelivery.await()
                }
            }
        )
        session.start()

        try {
            val maximumMessage = P2pMessage.Binary(ByteArray(4 * 1024 * 1024))
            events.send(ProtocolEvent.Message(maximumMessage))
            deliveryClaimed.await()
            events.send(ProtocolEvent.Message(maximumMessage))
            events.send(ProtocolEvent.Message(P2pMessage.Binary(byteArrayOf(1))))

            testScheduler.runCurrent()
            assertEquals(ConnectionState.Failed, session.state.value)
        } finally {
            releaseDelivery.complete(Unit)
            supervisor.cancel()
        }
    }

    @Test
    fun applicationBacklogIncludesRetainedMetadataBytes() = runTest {
        val pair = FakeConnectionPair()
        val protocol = DefaultP2pProtocol(clock = { testScheduler.currentTime })
        val supervisor = SupervisorJob()
        val scope = CoroutineScope(StandardTestDispatcher(testScheduler) + supervisor)
        val events = Channel<ProtocolEvent>(Channel.UNLIMITED)
        val deliveryClaimed = CompletableDeferred<Unit>()
        val releaseDelivery = CompletableDeferred<Unit>()
        var deliveryCalls = 0
        val session = P2pSessionImpl(
            id = "metadata-backlog",
            peer = Peer(PeerId("metadata-peer"), "Peer", Platform.JVM_DESKTOP, setOf(TransportKind.LAN)),
            initialConnection = pair.a,
            initialEvents = events,
            protocol = protocol,
            parentScope = scope,
            keepAlive = KeepAliveConfig(60_000, 120_000),
            clock = { testScheduler.currentTime },
            logger = P2pLogger.NoOp,
            beforeApplicationMessageEmitForTest = {
                if (deliveryCalls++ == 0) {
                    deliveryClaimed.complete(Unit)
                    releaseDelivery.await()
                }
            }
        )
        session.start()

        val metadata = ('a'..'h').associate { key ->
            key.toString() to "v".repeat(4_095)
        }
        try {
            val maximumWithMetadata = P2pMessage.Binary(
                ByteArray(4 * 1024 * 1024),
                metadata
            )
            events.send(ProtocolEvent.Message(maximumWithMetadata))
            deliveryClaimed.await()
            events.send(ProtocolEvent.Message(maximumWithMetadata))

            testScheduler.runCurrent()
            assertEquals(ConnectionState.Failed, session.state.value)
        } finally {
            releaseDelivery.complete(Unit)
            supervisor.cancel()
        }
    }

    @Test
    fun terminalStateCannotOvertakeApplicationDeliveryCancellation() = runTest {
        val pair = FakeConnectionPair()
        val protocol = DefaultP2pProtocol(clock = { testScheduler.currentTime })
        val supervisor = SupervisorJob()
        val scope = CoroutineScope(StandardTestDispatcher(testScheduler) + supervisor)
        val events = Channel<ProtocolEvent>(Channel.UNLIMITED)
        val deliveryEntered = CompletableDeferred<Unit>()
        val releaseDelivery = CompletableDeferred<Unit>()
        val terminalPublished = CompletableDeferred<Unit>()
        val releaseTerminal = CompletableDeferred<Unit>()
        val received = Channel<P2pMessage>(Channel.UNLIMITED)
        val session = P2pSessionImpl(
            id = "terminal-delivery-order",
            peer = Peer(PeerId("terminal-peer"), "Peer", Platform.JVM_DESKTOP, setOf(TransportKind.LAN)),
            initialConnection = pair.a,
            initialEvents = events,
            protocol = protocol,
            parentScope = scope,
            keepAlive = KeepAliveConfig(60_000, 120_000),
            clock = { testScheduler.currentTime },
            logger = P2pLogger.NoOp,
            beforeApplicationMessageEmitForTest = {
                deliveryEntered.complete(Unit)
                releaseDelivery.await()
            },
            afterTerminalStatePublishedForTest = {
                terminalPublished.complete(Unit)
                releaseTerminal.await()
            }
        )
        val subscriber = scope.launch(start = CoroutineStart.UNDISPATCHED) {
            session.incoming.collect(received::send)
        }
        session.start()

        try {
            events.send(ProtocolEvent.Message(P2pMessage.Text("must be cancelled")))
            deliveryEntered.await()
            events.send(ProtocolEvent.Close)
            terminalPublished.await()
            assertEquals(ConnectionState.Closed, session.state.value)

            releaseDelivery.complete(Unit)
            testScheduler.runCurrent()
            assertTrue(received.tryReceive().isFailure, "no message may appear after terminal publication")
        } finally {
            releaseTerminal.complete(Unit)
            releaseDelivery.complete(Unit)
            subscriber.cancel()
            supervisor.cancel()
        }
    }

    @Test
    fun parentCancellationAfterTerminalPublicationCannotSkipResourceCleanup() = runTest {
        val pair = FakeConnectionPair()
        val supervisor = SupervisorJob()
        val scope = CoroutineScope(StandardTestDispatcher(testScheduler) + supervisor)
        val events = Channel<ProtocolEvent>(Channel.UNLIMITED)
        val terminalPublished = CompletableDeferred<Unit>()
        val releaseTerminal = CompletableDeferred<Unit>()
        val session = P2pSessionImpl(
            id = "terminal-cleanup-cancellation-boundary",
            peer = Peer(
                PeerId("terminal-cleanup-peer"),
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
            logger = P2pLogger.NoOp,
            afterTerminalStatePublishedForTest = {
                terminalPublished.complete(Unit)
                releaseTerminal.await()
            }
        )
        session.start()

        try {
            events.send(ProtocolEvent.Close)
            terminalPublished.await()
            assertEquals(ConnectionState.Closed, session.state.value)

            // Cancel the exact parent that owns routeEvents while the
            // terminal state is visible but cleanup is deliberately paused.
            // Cleanup must remain one non-cancellable transaction.
            supervisor.cancel()
            releaseTerminal.complete(Unit)
            testScheduler.runCurrent()

            assertEquals(
                ConnectionState.Closed,
                withContext(Dispatchers.Default) {
                    withTimeout(5_000) {
                        pair.a.state.first { it == ConnectionState.Closed }
                    }
                }
            )
            assertFalse(session.runtimeJobIsActiveForTest)
            session.awaitRuntimeTermination()
        } finally {
            releaseTerminal.complete(Unit)
            supervisor.cancel()
        }
    }

    @Test
    fun terminalClaimRejectsWritesFileTransfersAndRearmBeforeStatePublication() = runTest {
        val pair = FakeConnectionPair()
        val replacement = FakeConnectionPair()
        val supervisor = SupervisorJob()
        val scope = CoroutineScope(StandardTestDispatcher(testScheduler) + supervisor)
        val events = Channel<ProtocolEvent>(Channel.UNLIMITED)
        val claimEntered = CompletableDeferred<Unit>()
        val releaseClaim = CompletableDeferred<Unit>()
        val session = P2pSessionImpl(
            id = "terminal-claim-admission",
            peer = Peer(
                PeerId("terminal-claim-peer"),
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
            logger = P2pLogger.NoOp,
            afterTerminalClaimForTest = {
                claimEntered.complete(Unit)
                releaseClaim.await()
            }
        )
        session.start()

        try {
            events.send(ProtocolEvent.Close)
            claimEntered.await()
            assertEquals(
                ConnectionState.Connected,
                session.state.value,
                "terminal state publication is deliberately held after the ownership claim"
            )

            assertFailsWith<P2pError.ConnectionFailed> {
                session.send(P2pMessage.Text("must not cross terminal claim"))
            }
            val prepared = object : PreparedFileSource {
                override val sizeBytes: Long = 0
                override val sha256: Sha256Digest = Sha256Digest(ByteArray(32))
                override fun open(): Buffer = Buffer()
            }
            val fileFailure = assertFailsWith<P2pError.FileTransferFailed> {
                session.sendFile("must-not-start.bin", null, prepared)
            }
            assertEquals(
                dev.p2pkit.core.FileTransferFailureKind.REMOTE_DISCONNECTED,
                fileFailure.kind
            )
            assertFalse(
                session.rearmWith(
                    replacement.a,
                    Channel(Channel.UNLIMITED)
                ),
                "a replacement epoch must not cross the terminal claim"
            )
            assertEquals(ConnectionState.Closed, replacement.a.state.value)

            releaseClaim.complete(Unit)
            assertEquals(
                ConnectionState.Closed,
                session.state.first { it == ConnectionState.Closed }
            )
        } finally {
            releaseClaim.complete(Unit)
            supervisor.cancel()
        }
    }

    @Test
    fun registrationCheckActivatesOnlyAfterCommitAndThenDropsDetachedMessages() = runTest {
        val pair = FakeConnectionPair()
        val protocol = DefaultP2pProtocol(clock = { testScheduler.currentTime })
        val supervisor = SupervisorJob()
        val scope = CoroutineScope(StandardTestDispatcher(testScheduler) + supervisor)
        val events = Channel<ProtocolEvent>(Channel.UNLIMITED)
        val received = Channel<P2pMessage>(Channel.UNLIMITED)
        val session = P2pSessionImpl(
            id = "detached-message-drop",
            peer = Peer(PeerId("detached-peer"), "Peer", Platform.JVM_DESKTOP, setOf(TransportKind.LAN)),
            initialConnection = pair.a,
            initialEvents = events,
            protocol = protocol,
            parentScope = scope,
            keepAlive = KeepAliveConfig(60_000, 120_000),
            clock = { testScheduler.currentTime },
            logger = P2pLogger.NoOp,
            lookupRegistration = { SessionRegistration(activeSessionId = null, isInPublicList = false) }
        )
        val subscriber = scope.launch(start = CoroutineStart.UNDISPATCHED) {
            session.incoming.collect(received::send)
        }
        session.start()

        try {
            events.send(ProtocolEvent.Message(P2pMessage.Text("pre-registration")))
            testScheduler.runCurrent()
            assertEquals(P2pMessage.Text("pre-registration"), received.receive())

            session.markRegistrationCommitted()
            events.send(ProtocolEvent.Message(P2pMessage.Text("zombie")))
            testScheduler.runCurrent()
            assertTrue(received.tryReceive().isFailure)
            assertEquals(ConnectionState.Connected, session.state.value)
        } finally {
            subscriber.cancel()
            supervisor.cancel()
        }
    }

    @Test
    fun timedOutNonCooperativeDeliveryCannotUnderflowBacklogAfterLateExit() = runTest {
        val pair = FakeConnectionPair()
        val supervisor = SupervisorJob()
        val scope = CoroutineScope(StandardTestDispatcher(testScheduler) + supervisor)
        val events = Channel<ProtocolEvent>(Channel.UNLIMITED)
        val deliveryEntered = CompletableDeferred<Unit>()
        val releaseDelivery = CompletableDeferred<Unit>()
        val deliveryDrainCompleted = CompletableDeferred<Unit>()
        val session = P2pSessionImpl(
            id = "late-delivery-exit",
            peer = Peer(PeerId("late-delivery-peer"), "Peer", Platform.JVM_DESKTOP, setOf(TransportKind.LAN)),
            initialConnection = pair.a,
            initialEvents = events,
            protocol = DefaultP2pProtocol(clock = { testScheduler.currentTime }),
            parentScope = scope,
            keepAlive = KeepAliveConfig(60_000, 120_000),
            clock = { testScheduler.currentTime },
            logger = P2pLogger.NoOp,
            beforeApplicationMessageEmitForTest = {
                deliveryEntered.complete(Unit)
                withContext(NonCancellable) { releaseDelivery.await() }
            },
            applicationDeliveryCloseTimeoutMillis = 50,
            afterApplicationDeliveryDrainForTest = { deliveryDrainCompleted.complete(Unit) }
        )
        session.start()

        try {
            events.send(ProtocolEvent.Message(P2pMessage.Text("retained")))
            deliveryEntered.await()
            events.send(ProtocolEvent.Message(P2pMessage.Text("queued behind retained")))
            testScheduler.runCurrent()
            events.send(ProtocolEvent.Close)
            assertEquals(
                ConnectionState.Closed,
                session.state.first { it == ConnectionState.Closed }
            )

            deliveryDrainCompleted.await()
            assertEquals(
                1 to "retained".encodeToByteArray().size.toLong(),
                session.applicationBacklogForTest(),
                "only the cancellation-ignoring in-flight message remains owned"
            )
            releaseDelivery.complete(Unit)
            testScheduler.runCurrent()

            assertEquals(0 to 0L, session.applicationBacklogForTest())
        } finally {
            releaseDelivery.complete(Unit)
            supervisor.cancel()
        }
    }

    @Test
    fun keepAliveUsesMonotonicClockAndFailsAtExactDeadline() = runTest {
        val pair = FakeConnectionPair()
        val protocol = DefaultP2pProtocol(clock = { testScheduler.currentTime })
        val supervisor = SupervisorJob()
        val scope = CoroutineScope(StandardTestDispatcher(testScheduler) + supervisor)
        val events = Channel<ProtocolEvent>(Channel.UNLIMITED)
        var wallClock = 10_000L
        val session = P2pSessionImpl(
            id = "monotonic-deadline",
            peer = Peer(
                PeerId("monotonic-peer"),
                "Monotonic",
                Platform.JVM_DESKTOP,
                setOf(TransportKind.LAN)
            ),
            initialConnection = pair.a,
            initialEvents = events,
            protocol = protocol,
            parentScope = scope,
            keepAlive = KeepAliveConfig(pingIntervalMillis = 50, timeoutMillis = 150),
            clock = { wallClock },
            monotonicClock = { testScheduler.currentTime },
            logger = P2pLogger.NoOp
        )
        session.start()

        try {
            wallClock = Long.MAX_VALUE
            testScheduler.advanceTimeBy(50)
            testScheduler.runCurrent()
            assertEquals(ConnectionState.Connected, session.state.value)

            wallClock = Long.MIN_VALUE
            testScheduler.advanceTimeBy(99)
            testScheduler.runCurrent()
            assertEquals(ConnectionState.Connected, session.state.value)

            testScheduler.advanceTimeBy(1)
            testScheduler.runCurrent()
            assertEquals(ConnectionState.Failed, session.state.value)
        } finally {
            supervisor.cancel()
        }
    }

    @Test
    fun sessionTransitionsToFailedWhenNoPongArrivesWithinTimeout() {
        runTest {
            val pair = FakeConnectionPair()
            val protocol = DefaultP2pProtocol(clock = { testScheduler.currentTime })
            val supervisor = SupervisorJob()
            val scope = CoroutineScope(StandardTestDispatcher(testScheduler) + supervisor)

            // No events ever land in this channel → the session never sees a
            // ProtocolEvent.Pong → keepalive deadline elapses.
            val events = Channel<ProtocolEvent>(Channel.UNLIMITED)

            val peer = Peer(
                id = PeerId("test-keepalive"),
                name = "Test",
                platform = Platform.JVM_DESKTOP,
                supportedTransports = setOf(TransportKind.LAN)
            )

            val session = P2pSessionImpl(
                id = "keepalive-test",
                peer = peer,
                initialConnection = pair.a,
                initialEvents = events,
                protocol = protocol,
                parentScope = scope,
                keepAlive = KeepAliveConfig(pingIntervalMillis = 50, timeoutMillis = 150),
                clock = { testScheduler.currentTime },
                logger = P2pLogger.NoOp
            )
            session.start()

            try {
                val terminal = withTimeout(3_000) {
                    session.state.first { it == ConnectionState.Failed || it == ConnectionState.Closed }
                }
                assertEquals(ConnectionState.Failed, terminal, "Session should fail due to missing PONG")

                // Sanity: the session did write *some* PINGs onto the wire
                // before failing (i.e., the loop ran at least once).
                assertTrue(
                    pair.a.writtenChunks.isNotEmpty(),
                    "Keep-alive loop should have written at least one PING frame"
                )
            } finally {
                supervisor.cancel()
            }
        }
    }

    @Test
    fun respondsToInboundPingWithPong() {
        runTest {
            val pair = FakeConnectionPair()
            val protocol = DefaultP2pProtocol(clock = { testScheduler.currentTime })
            val supervisor = SupervisorJob()
            val scope = CoroutineScope(StandardTestDispatcher(testScheduler) + supervisor)

            val events = Channel<ProtocolEvent>(Channel.UNLIMITED)
            val peer = Peer(
                id = PeerId("test-pong-responder"),
                name = "Test",
                platform = Platform.JVM_DESKTOP,
                supportedTransports = setOf(TransportKind.LAN)
            )

            val session = P2pSessionImpl(
                id = "pong-responder-test",
                peer = peer,
                initialConnection = pair.a,
                initialEvents = events,
                protocol = protocol,
                parentScope = scope,
                // Long ping interval: the session never emits a spontaneous PING
                // in the test window, so the ONLY frame it writes is the PONG
                // reply we assert on.
                keepAlive = KeepAliveConfig(pingIntervalMillis = 60_000, timeoutMillis = 120_000),
                clock = { testScheduler.currentTime },
                logger = P2pLogger.NoOp
            )
            session.start()

            try {
                // Decode whatever the session writes back onto the wire by
                // running the protocol's event reader on the PEER side (pair.b).
                val outbound = Channel<ProtocolEvent>(Channel.UNLIMITED)
                scope.launch { protocol.events(pair.b).collect { outbound.send(it) } }

                // Simulate an inbound PING arriving from the peer.
                events.send(ProtocolEvent.Ping)

                val reply = withTimeout(3_000) { outbound.receive() }
                assertEquals(
                    ProtocolEvent.Pong, reply,
                    "session must answer an inbound PING with a PONG frame"
                )
            } finally {
                supervisor.cancel()
            }
        }
    }

    @Test
    fun staysConnectedWhilePongsArriveWithinTimeout() {
        runTest {
            val pair = FakeConnectionPair()
            val protocol = DefaultP2pProtocol(clock = { testScheduler.currentTime })
            val supervisor = SupervisorJob()
            val scope = CoroutineScope(StandardTestDispatcher(testScheduler) + supervisor)

            val events = Channel<ProtocolEvent>(Channel.UNLIMITED)
            val peer = Peer(
                id = PeerId("test-keepalive-positive"),
                name = "Test",
                platform = Platform.JVM_DESKTOP,
                supportedTransports = setOf(TransportKind.LAN)
            )

            val session = P2pSessionImpl(
                id = "keepalive-positive-test",
                peer = peer,
                initialConnection = pair.a,
                initialEvents = events,
                protocol = protocol,
                parentScope = scope,
                // timeout (600ms virtual) is 24x the 25ms virtual PONG cadence
                // below; the 900ms virtual run still exceeds the timeout, so
                // the no-PONG baseline (the failure test above) WOULD have
                // failed — proving it is the PONGs keeping the session
                // Connected. All arithmetic is on the test scheduler's virtual
                // clock, so the margins are exact, not jitter-dependent.
                keepAlive = KeepAliveConfig(pingIntervalMillis = 50, timeoutMillis = 600),
                clock = { testScheduler.currentTime },
                logger = P2pLogger.NoOp
            )

            // Feed PONGs faster than the timeout for the whole run.
            val feeder = scope.launch {
                while (isActive) {
                    events.send(ProtocolEvent.Pong)
                    delay(25)
                }
            }
            session.start()

            try {
                delay(900)
                assertEquals(
                    ConnectionState.Connected, session.state.value,
                    "session must stay Connected while PONGs keep arriving within timeout"
                )
                assertTrue(
                    pair.a.writtenChunks.isNotEmpty(),
                    "keep-alive loop should have written PING frames during the run"
                )
            } finally {
                feeder.cancel()
                supervisor.cancel()
            }
        }
    }
}
