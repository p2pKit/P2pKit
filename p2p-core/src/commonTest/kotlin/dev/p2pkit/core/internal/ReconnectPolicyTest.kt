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
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
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
 * [FakeConnectionPair]s the test controls directly. Failures are induced via
 * [dev.p2pkit.core.testfixtures.FakeRawConnection.breakWithException], which
 * lets the test observe the exact state transitions without timing on real
 * keepalives. The throwing signature is used deliberately: it routes the
 * loss through the session's defensive failure branch, giving a
 * deterministic connection-loss signal regardless of the remote-termination
 * classification race (TST-1 / SES-1). Once that classification is
 * deterministic, these can migrate to the production-shaped
 * [dev.p2pkit.core.testfixtures.FakeRawConnection.breakWith].
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
    ): P2pKit = P2pKit.create {
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
        P2pKit.create {
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
}

private class ReconnectTestFactory(private val transport: FakeDataTransport) : TransportFactory {
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = null)
}
