package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.NetworkPathStatus
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.FakeNetworkPathObserver
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
import kotlin.test.assertTrue

/**
 * Verifies §4: host-network path-change events propagate through
 * [SessionManager.applyPathChange] into individual sessions, reusing the
 * existing reconnect machinery rather than introducing a parallel path.
 *
 * Determinism: each test wires a [FakeNetworkPathObserver] into the kit
 * via `lifecycle { networkPathObserver = fake }` and drives status
 * transitions via `fake.emit(...)`. Session state is observed with bounded
 * `withTimeout` + `state.first { ... }` — no arbitrary sleeps.
 */
class NetworkPathRecoveryTest {

    private fun targetPeer(): Peer = Peer(
        id = PeerId("bob-id"),
        name = "Bob",
        platform = Platform.JVM_DESKTOP,
        supportedTransports = setOf(TransportKind.LAN)
    )

    private fun outgoingKit(
        name: String,
        policy: ReconnectPolicy,
        observer: FakeNetworkPathObserver,
        outgoingFactory: () -> RawConnection
    ): P2pKit = P2pKit.create {
        appId = AppId("com.example.test")
        deviceName = name
        keepAlive {
            // Very long PING so the only way `Connected` flips to
            // `Reconnecting` / `Failed` in the test window is via the
            // path-change signal — not via keep-alive timeout.
            pingIntervalMillis = 60_000
            timeoutMillis = 120_000
        }
        lifecycle {
            reconnectPolicy = policy
            networkPathObserver = observer
        }
        transports {
            register(PathRecoveryTestFactory(FakeDataTransport(outgoingConnection = outgoingFactory)))
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
            transports {
                register(PathRecoveryTestFactory(FakeDataTransport(preStagedIncoming = preStaged)))
            }
        }

    @Test
    fun pathUnsatisfiedTransitionsConnectedSessionToReconnecting() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        val fake = FakeNetworkPathObserver(initial = NetworkPathStatus.Satisfied)
        val alice = outgoingKit(
            "Alice",
            ReconnectPolicy.Enabled(maxAttempts = 5, retryDelayMillis = 5_000),
            fake
        ) { pair.a }
        val bob = incomingKit("Bob", listOf(pair.b))
        try {
            val session = withTimeout(5_000) { alice.connect(targetPeer()) }
            assertEquals(ConnectionState.Connected, session.state.value)

            fake.emit(NetworkPathStatus.Unsatisfied)

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
    fun pathUnsatisfiedTransitionsToFailedWhenReconnectDisabled() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        val fake = FakeNetworkPathObserver(initial = NetworkPathStatus.Satisfied)
        val alice = outgoingKit(
            "Alice",
            ReconnectPolicy.Disabled,
            fake
        ) { pair.a }
        val bob = incomingKit("Bob", listOf(pair.b))
        try {
            val session = withTimeout(5_000) { alice.connect(targetPeer()) }
            assertEquals(ConnectionState.Connected, session.state.value)

            fake.emit(NetworkPathStatus.Unsatisfied)

            val terminal = withTimeout(5_000) {
                session.state.first { it == ConnectionState.Failed || it == ConnectionState.Closed }
            }
            assertEquals(
                ConnectionState.Failed, terminal,
                "Without a reconnect handler, path-lost must take the session to Failed " +
                    "via the same onConnectionLost gate the PING-failure path uses."
            )
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun pathSatisfiedWakesParkedReconnectHandlerBeforeDelayExpires() = runBlocking<Unit> {
        // Two pairs: the first breaks, the second is what the retry will reach.
        // The retry delay is set to a value (5 s) that's deliberately longer
        // than the test would tolerate. If the path-satisfied signal does NOT
        // wake the handler early, the test would block for 5 s before the
        // retry fires and reach the withTimeout(2_000) wait below.
        val pair1 = FakeConnectionPair()
        val pair2 = FakeConnectionPair()
        val queue = ArrayDeque<RawConnection>().apply {
            add(pair1.a); add(pair2.a)
        }
        val attempts = MutableStateFlow(0)
        val fake = FakeNetworkPathObserver(initial = NetworkPathStatus.Satisfied)
        val alice = outgoingKit(
            "Alice",
            ReconnectPolicy.Enabled(maxAttempts = 3, retryDelayMillis = 5_000),
            fake
        ) {
            attempts.update { it + 1 }
            queue.removeFirstOrNull() ?: throw RuntimeException("no more connections")
        }
        val bob = incomingKit("Bob", listOf(pair1.b, pair2.b))
        try {
            val session = withTimeout(5_000) { alice.connect(targetPeer()) }
            assertEquals(ConnectionState.Connected, session.state.value)

            // Drive: drop the wire AND drop the path. Both fire
            // onConnectionLost; the connection lock short-circuits the
            // second one. Session is now Reconnecting and the handler is
            // parked in `withTimeoutOrNull(5_000) { pathSatisfied.first() }`.
            pair1.a.breakWith(RuntimeException("simulated wire break"))
            fake.emit(NetworkPathStatus.Unsatisfied)
            withTimeout(5_000) {
                session.state.first { it == ConnectionState.Reconnecting }
            }

            // Wake the parked retry by emitting Satisfied. Without the
            // signal, the test would have to wait the full 5 s.
            fake.emit(NetworkPathStatus.Satisfied)

            // Bounded < retryDelayMillis to prove the signal woke the
            // handler early.
            val rearmed = withTimeout(2_000) {
                session.state.first { it == ConnectionState.Connected }
            }
            assertEquals(ConnectionState.Connected, rearmed)
            assertEquals(
                2, attempts.value,
                "Expected initial connect + exactly one retry triggered by Satisfied wake-up"
            )
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun pathUnknownIsANoOp() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        val fake = FakeNetworkPathObserver(initial = NetworkPathStatus.Satisfied)
        val alice = outgoingKit(
            "Alice",
            ReconnectPolicy.Disabled,
            fake
        ) { pair.a }
        val bob = incomingKit("Bob", listOf(pair.b))
        try {
            val session = withTimeout(5_000) { alice.connect(targetPeer()) }
            assertEquals(ConnectionState.Connected, session.state.value)

            // Emit Unknown — must NOT touch the session.
            fake.emit(NetworkPathStatus.Unknown)
            // Small settle window; we don't have a state transition to wait
            // on because there shouldn't be one.
            delay(100)
            assertEquals(
                ConnectionState.Connected, session.state.value,
                "NetworkPathStatus.Unknown must be a no-op — it means 'no information', " +
                    "not 'no network'."
            )
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    private class PathRecoveryTestFactory(
        private val transport: FakeDataTransport
    ) : TransportFactory {
        override fun build(context: TransportContext): TransportPair =
            TransportPair(data = transport, discovery = null)
    }

    @Test
    fun observerLifecycleIsTiedToKitLifecycle() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        val fake = FakeNetworkPathObserver()
        val alice = outgoingKit(
            "Alice",
            ReconnectPolicy.Disabled,
            fake
        ) { pair.a }
        val bob = incomingKit("Bob", listOf(pair.b))
        try {
            // start() runs lazily on the first lifecycle call.
            assertEquals(0, fake.startCalled, "Observer must not start before ensureStarted")
            withTimeout(5_000) { alice.connect(targetPeer()) }
            assertTrue(
                fake.startCalled >= 1,
                "Observer.start must be called by ensureStarted (got ${fake.startCalled})"
            )

            // Idempotent — a second lifecycle call must not call start again.
            val startsBefore = fake.startCalled
            alice.startAdvertising()
            assertEquals(
                startsBefore, fake.startCalled,
                "Observer.start must be idempotent across kit.ensureStarted calls"
            )
        } finally {
            alice.stop()
            bob.stop()
            assertTrue(
                fake.closeCalled >= 1,
                "Observer.close must be called by kit.stop() (got ${fake.closeCalled})"
            )
        }
    }
}
