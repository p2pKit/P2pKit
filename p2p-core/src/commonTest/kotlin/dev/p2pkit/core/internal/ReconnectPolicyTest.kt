package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.createTestKit
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.async
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertSame

/**
 * Exercises [ReconnectPolicy.Enabled] behavior at the kit boundary.
 *
 * Each test wires an outgoing Alice and an incoming Bob against
 * [FakeConnectionPair]s the test controls directly. The pre-2026-07 tests
 * induce failures via
 * [dev.p2pkit.core.testfixtures.FakeRawConnection.breakWithException]; the
 * throwing signature is kept deliberately there — it pins the session's
 * defensive failure branch (routeEvents' catch-Throwable path), which stays a
 * supported classification route. The remote-termination determinism tests
 * added for AUDIT-2026-07 (SES-1) use the production-shaped
 * [FakeConnectionPair.hangUp] / peer-side `close()` instead, exercising the
 * exact EOF-vs-CLOSE-frame classification the shipped transports deliver
 * (P1-01 / P1-02).
 *
 * Determinism rules:
 *   - retry delays are tiny except where the test needs a window to interpose
 *     `close()` / `stop()` (then 1000 ms — comfortably longer than CI scheduling jitter).
 *   - state observation always goes through `state.first { ... }` with a
 *     bounded `withTimeout`. No arbitrary sleeps for synchronization.
 */
class ReconnectPolicyTest {

    private fun targetPeer(): Peer = Peer(
        id = PeerId("bob-id"),
        name = "Bob",
        platform = Platform.JVM_DESKTOP,
        supportedTransports = setOf(TransportKind.LAN)
    )

    private fun outgoingKit(
        name: String,
        policy: ReconnectPolicy,
        outgoingFactory: () -> RawConnection
    ): P2pKit = createTestKit {
        appId = AppId("com.example.test")
        deviceName = name
        keepAlive {
            pingIntervalMillis = 60_000
            timeoutMillis = 120_000
        }
        lifecycle {
            reconnectPolicy = policy
        }
        transports {
            register(ReconnectTestFactory(FakeDataTransport(outgoingConnection = outgoingFactory)))
        }
    }

    private fun incomingKit(name: String, preStaged: List<RawConnection>): P2pKit =
        createTestKit {
            appId = AppId("com.example.test")
            deviceName = name
            keepAlive {
                pingIntervalMillis = 60_000
                timeoutMillis = 120_000
            }
            // Match the dialed id ("bob-id") so the outgoing handshake's peerId
            // verification passes (mirrors production discovery).
            peerIdStorage = InMemoryPeerIdStorage(seed = PeerId("bob-id"))
            transports {
                register(ReconnectTestFactory(FakeDataTransport(preStagedIncoming = preStaged)))
            }
        }

    @Test
    fun disabledPolicyTransitionsDirectlyToFailed() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        val alice = outgoingKit("Alice", ReconnectPolicy.Disabled) { pair.a }
        val bob = incomingKit("Bob", listOf(pair.b))
        try {
            val session = withTimeout(5_000) { alice.connect(targetPeer()) }
            // alice.connect returning means the handshake completed on both
            // sides — no need to observe bob.incomingSessions (it's replay=0
            // and the emit may have happened before we could subscribe).
            assertEquals(ConnectionState.Connected, session.state.value)

            pair.a.breakWithException(RuntimeException("simulated wire break"))

            val terminal = withTimeout(5_000) {
                session.state.first { it == ConnectionState.Failed || it == ConnectionState.Closed }
            }
            assertEquals(
                ConnectionState.Failed, terminal,
                "Disabled policy must transition broken sessions to Failed, never via Reconnecting"
            )
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun enabledPolicyEmitsReconnectingOnConnectionLoss() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        val queue = ArrayDeque<RawConnection>().apply { add(pair.a) }
        val alice = outgoingKit(
            "Alice",
            ReconnectPolicy.Enabled(maxAttempts = 3, retryDelayMillis = 10)
        ) {
            queue.removeFirstOrNull() ?: throw RuntimeException("no more connections")
        }
        val bob = incomingKit("Bob", listOf(pair.b))
        try {
            val session = withTimeout(5_000) { alice.connect(targetPeer()) }
            // alice.connect returning means the handshake completed on both
            // sides — no need to observe bob.incomingSessions (it's replay=0
            // and the emit may have happened before we could subscribe).
            assertEquals(ConnectionState.Connected, session.state.value)

            pair.a.breakWithException(RuntimeException("simulated wire break"))

            val reconnecting = withTimeout(5_000) {
                session.state.first { it == ConnectionState.Reconnecting }
            }
            assertEquals(ConnectionState.Reconnecting, reconnecting)
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun enabledPolicyReturnsToConnectedOnSuccessfulRetry() = runBlocking<Unit> {
        val pair1 = FakeConnectionPair()
        val pair2 = FakeConnectionPair()
        val queue = ArrayDeque<RawConnection>().apply {
            add(pair1.a); add(pair2.a)
        }
        val attempts = MutableStateFlow(0)
        val alice = outgoingKit(
            "Alice",
            ReconnectPolicy.Enabled(maxAttempts = 5, retryDelayMillis = 20)
        ) {
            attempts.update { it + 1 }
            queue.removeFirstOrNull() ?: throw RuntimeException("no more connections")
        }
        val bob = incomingKit("Bob", listOf(pair1.b, pair2.b))
        try {
            val session = withTimeout(5_000) { alice.connect(targetPeer()) }
            // alice.connect returning means the handshake completed on both
            // sides — no need to observe bob.incomingSessions (it's replay=0
            // and the emit may have happened before we could subscribe).
            assertEquals(ConnectionState.Connected, session.state.value)

            pair1.a.breakWithException(RuntimeException("simulated wire break"))
            withTimeout(5_000) { session.state.first { it == ConnectionState.Reconnecting } }

            val rearmed = withTimeout(5_000) {
                session.state.first { it == ConnectionState.Connected }
            }
            assertEquals(ConnectionState.Connected, rearmed)
            assertEquals(
                2, attempts.value,
                "Expected initial connect + exactly one retry to succeed"
            )
            // Session identity preserved across the rearm — kit.sessions still
            // exposes the same P2pSession instance the caller is holding.
            assertSame(
                session, alice.sessions.value.firstOrNull(),
                "Public session identity must survive reconnect"
            )
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun enabledPolicyFailsAfterMaxAttempts() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        val attempts = MutableStateFlow(0)
        val maxAttempts = 3
        val alice = outgoingKit(
            "Alice",
            ReconnectPolicy.Enabled(maxAttempts = maxAttempts, retryDelayMillis = 10)
        ) {
            val n = attempts.value
            attempts.update { it + 1 }
            if (n == 0) pair.a else throw RuntimeException("simulated transport unreachable")
        }
        val bob = incomingKit("Bob", listOf(pair.b))
        try {
            val session = withTimeout(5_000) { alice.connect(targetPeer()) }

            pair.a.breakWithException(RuntimeException("simulated wire break"))

            val terminal = withTimeout(5_000) {
                session.state.first { it == ConnectionState.Failed || it == ConnectionState.Closed }
            }
            assertEquals(ConnectionState.Failed, terminal)
            assertEquals(
                1 + maxAttempts, attempts.value,
                "Factory should be called initial + exactly $maxAttempts retries"
            )
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun closeDuringReconnectStopsRetriesAndEndsClosed() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        val attempts = MutableStateFlow(0)
        val alice = outgoingKit(
            "Alice",
            ReconnectPolicy.Enabled(maxAttempts = 5, retryDelayMillis = 1_000)
        ) {
            val n = attempts.value
            attempts.update { it + 1 }
            if (n == 0) pair.a else throw RuntimeException("simulated transport unreachable")
        }
        val bob = incomingKit("Bob", listOf(pair.b))
        try {
            val session = withTimeout(5_000) { alice.connect(targetPeer()) }

            pair.a.breakWithException(RuntimeException("simulated wire break"))
            withTimeout(5_000) { session.state.first { it == ConnectionState.Reconnecting } }

            val attemptsAtClose = attempts.value
            session.close()
            assertEquals(
                ConnectionState.Closed, session.state.value,
                "Manual close() must take precedence over reconnect exhaustion"
            )
            // Give any in-flight retry a chance to run if it weren't cancelled.
            delay(150)
            assertEquals(
                attemptsAtClose, attempts.value,
                "Factory must not be called after close()"
            )
            assertEquals(
                ConnectionState.Closed, session.state.value,
                "State must remain Closed after close() — never flip to Failed"
            )
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun kitStopDuringReconnectStopsRetries() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        val attempts = MutableStateFlow(0)
        val alice = outgoingKit(
            "Alice",
            ReconnectPolicy.Enabled(maxAttempts = 5, retryDelayMillis = 1_000)
        ) {
            val n = attempts.value
            attempts.update { it + 1 }
            if (n == 0) pair.a else throw RuntimeException("simulated transport unreachable")
        }
        val bob = incomingKit("Bob", listOf(pair.b))
        try {
            val session = withTimeout(5_000) { alice.connect(targetPeer()) }

            pair.a.breakWithException(RuntimeException("simulated wire break"))
            withTimeout(5_000) { session.state.first { it == ConnectionState.Reconnecting } }

            val attemptsAtStop = attempts.value
            alice.stop()
            delay(150)
            assertEquals(
                attemptsAtStop, attempts.value,
                "Factory must not be called after kit.stop()"
            )
        } finally {
            bob.stop()
        }
    }

    @Test
    fun concurrentConnectDuringReconnectReturnsSameSession() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        val alice = outgoingKit(
            "Alice",
            ReconnectPolicy.Enabled(maxAttempts = 5, retryDelayMillis = 1_000)
        ) {
            // First call serves initial connect; later calls fail to keep the
            // session pinned in Reconnecting for the duration of this test.
            if (pair.a.state.value == ConnectionState.Connected) pair.a
            else throw RuntimeException("simulated transport unreachable")
        }
        val bob = incomingKit("Bob", listOf(pair.b))
        try {
            val firstSession = withTimeout(5_000) { alice.connect(targetPeer()) }

            pair.a.breakWithException(RuntimeException("simulated wire break"))
            withTimeout(5_000) { firstSession.state.first { it == ConnectionState.Reconnecting } }

            val secondSession = withTimeout(5_000) { alice.connect(targetPeer()) }
            assertSame(
                firstSession, secondSession,
                "connect() during Reconnecting must return the existing session"
            )
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun abruptRemoteTerminationWithoutCloseFrameDeterministicallyEntersReconnecting() = runBlocking<Unit> {
        // AUDIT-2026-07 (SES-1) / P1-01: the most common field event — the
        // peer's process goes away and the wire ends with no CLOSE frame
        // (EOF/reset signature). An outgoing session with
        // ReconnectPolicy.Enabled must classify that as a connection loss and
        // enter Reconnecting as its FIRST transition out of Connected — never
        // the clean-Closed outcome the pre-fix completion branch could latch.
        val pair = FakeConnectionPair()
        val queue = ArrayDeque<RawConnection>().apply { add(pair.a) }
        val alice = outgoingKit(
            "Alice",
            ReconnectPolicy.Enabled(maxAttempts = 5, retryDelayMillis = 1_000)
        ) {
            queue.removeFirstOrNull() ?: throw RuntimeException("no more connections")
        }
        val bob = incomingKit("Bob", listOf(pair.b))
        try {
            val session = withTimeout(5_000) { alice.connect(targetPeer()) }
            assertEquals(ConnectionState.Connected, session.state.value)

            // Subscribe to the FIRST transition out of Connected before the
            // hang-up so the Reconnecting edge cannot be missed (UNDISPATCHED
            // runs the collector to its first suspension point right here).
            val firstTransition = async(start = CoroutineStart.UNDISPATCHED) {
                session.state.first { it != ConnectionState.Connected }
            }

            // Production-shaped remote termination (fixture F1): Bob's end of
            // the wire goes away without a CLOSE frame.
            pair.hangUp(pair.b)

            assertEquals(
                ConnectionState.Reconnecting,
                withTimeout(5_000) { firstTransition.await() },
                "abrupt remote termination (no CLOSE frame) must deterministically enter " +
                    "Reconnecting under ReconnectPolicy.Enabled — never the clean-Closed outcome"
            )
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun remoteCloseFrameYieldsExactlyClosedAndNeverRedials() = runBlocking<Unit> {
        // AUDIT-2026-07 (SES-1) / P1-02: a peer-initiated clean close — CLOSE
        // frame, then the socket goes down — must end exactly Closed, never
        // Failed, and must never re-invoke the dial factory ("clean closes
        // never trigger retry"), even under ReconnectPolicy.Enabled.
        val pair = FakeConnectionPair()
        val attempts = MutableStateFlow(0)
        val alice = outgoingKit(
            "Alice",
            ReconnectPolicy.Enabled(maxAttempts = 5, retryDelayMillis = 1_000)
        ) {
            val n = attempts.value
            attempts.update { it + 1 }
            if (n == 0) pair.a else throw RuntimeException("no more connections")
        }
        val bob = incomingKit("Bob", listOf(pair.b))
        try {
            val session = withTimeout(5_000) { alice.connect(targetPeer()) }
            assertEquals(ConnectionState.Connected, session.state.value)

            // Peer-side clean close: Bob's session sends the CLOSE frame and
            // then tears its raw connection down — the exact
            // frame-then-socket-close sequence a shipped transport delivers.
            val bobSession = withTimeout(5_000) { bob.sessions.first { it.isNotEmpty() } }.first()
            bobSession.close()

            val terminal = withTimeout(5_000) {
                session.state.first { it == ConnectionState.Closed || it == ConnectionState.Failed }
            }
            assertEquals(
                ConnectionState.Closed, terminal,
                "a received CLOSE frame must classify as a clean close — exactly Closed, never Failed"
            )

            // Terminal Closed is latched (the retry loop re-checks state
            // before every dial), so the factory must never be re-invoked.
            delay(150)
            assertEquals(
                1, attempts.value,
                "dial factory must not be re-invoked after a remote CLOSE frame"
            )
            assertEquals(ConnectionState.Closed, session.state.value)
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun remoteCloseThenImmediateSocketCloseClassifiesCleanlyUnderRepetition() = runBlocking<Unit> {
        // AUDIT-2026-07 (SES-1) / P1-02 stress variant: CLOSE frame followed
        // immediately by the socket close, repeated. Every iteration must
        // converge on exactly Closed with no re-dial regardless of how the
        // raw-terminal observer interleaves with CLOSE-frame processing on
        // the kit's multi-threaded dispatcher.
        repeat(10) { iteration ->
            val pair = FakeConnectionPair()
            val attempts = MutableStateFlow(0)
            val alice = outgoingKit(
                "Alice",
                ReconnectPolicy.Enabled(maxAttempts = 5, retryDelayMillis = 1_000)
            ) {
                val n = attempts.value
                attempts.update { it + 1 }
                if (n == 0) pair.a else throw RuntimeException("no more connections")
            }
            val bob = incomingKit("Bob", listOf(pair.b))
            try {
                val session = withTimeout(5_000) { alice.connect(targetPeer()) }
                val bobSession = withTimeout(5_000) { bob.sessions.first { it.isNotEmpty() } }.first()
                bobSession.close()

                val terminal = withTimeout(5_000) {
                    session.state.first { it == ConnectionState.Closed || it == ConnectionState.Failed }
                }
                assertEquals(
                    ConnectionState.Closed, terminal,
                    "iteration $iteration: remote CLOSE must end exactly Closed, never Failed"
                )
                assertEquals(
                    1, attempts.value,
                    "iteration $iteration: dial factory must not be re-invoked after a remote CLOSE"
                )
            } finally {
                alice.stop()
                bob.stop()
            }
        }
    }
}

private class ReconnectTestFactory(private val transport: FakeDataTransport) : TransportFactory {
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = null)
}
