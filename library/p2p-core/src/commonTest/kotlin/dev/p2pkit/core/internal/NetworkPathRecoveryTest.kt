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
import dev.p2pkit.core.testfixtures.createTestKit
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.isActive
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
    ): P2pKit = createTestKit {
        appId = AppId("com.example.test")
        deviceName = name
        peerIdStorage = InMemoryPeerIdStorage(seed = PeerId("alice-id"))
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
    fun newlyRegisteredSessionReceivesRetainedUnsatisfiedPathWithoutReEmission() =
        runBlocking<Unit> {
            val firstPair = FakeConnectionPair()
            val secondPair = FakeConnectionPair()
            val outgoing = ArrayDeque<RawConnection>().apply {
                add(firstPair.a)
                add(secondPair.a)
            }
            val fake = FakeNetworkPathObserver(initial = NetworkPathStatus.Satisfied)
            val alice = outgoingKit(
                "Alice",
                ReconnectPolicy.Disabled,
                fake
            ) { outgoing.removeFirstOrNull() ?: error("unexpected extra dial") }
            val bob = incomingKit("Bob", listOf(firstPair.b, secondPair.b))
            try {
                val first = withTimeout(5_000) { alice.connect(targetPeer()) }
                assertEquals(ConnectionState.Connected, first.state.value)

                fake.emit(NetworkPathStatus.Unsatisfied)
                assertEquals(
                    ConnectionState.Failed,
                    withTimeout(5_000) { first.state.first { it == ConnectionState.Failed } }
                )
                // The local terminal transition closes the raw connection,
                // but the remote reader observes that close asynchronously.
                // Establish the next-dial precondition from Bob's public
                // session state instead of racing its terminal watcher under
                // a saturated full-suite run.
                withTimeout(5_000) {
                    bob.sessions.first { it.isEmpty() }
                }

                // Do not emit path state again. A StateFlow will not re-emit
                // the same value, so registration must consume the manager's
                // retained authority rather than relying on the prior event.
                val second = withTimeout(5_000) { alice.connect(targetPeer()) }
                assertEquals(
                    ConnectionState.Failed,
                    withTimeout(5_000) { second.state.first { it == ConnectionState.Failed } },
                    "a new session must not become Connected while the retained path is Unsatisfied"
                )
                assertTrue(outgoing.isEmpty(), "both queued connections must have been consumed")
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
            pair1.a.breakWithException(RuntimeException("simulated wire break"))
            fake.emit(NetworkPathStatus.Unsatisfied)
            withTimeout(5_000) {
                session.state.first { it == ConnectionState.Reconnecting }
            }

            // Wake the parked retry by emitting Satisfied. The generation-
            // counter signal (AUDIT-2026-06 fix in SessionManager) retains the
            // transition even if it lands before the handler parks, so a single
            // emit is now race-free.
            fake.emit(NetworkPathStatus.Satisfied)

            // Bounded well under retryDelayMillis (5_000) to prove the signal
            // woke the handler early rather than the delay expiring. 3_500ms
            // (not a tighter 2_000) keeps the assertion robust when the full
            // test suite runs in parallel and saturates the CPU — the rearm
            // handshake still completes far inside the 5 s delay
            // (AUDIT-2026-06).
            val rearmed = withTimeout(3_500) {
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
        override val descriptor =
            dev.p2pkit.core.transport.TransportDescriptor.dataOnly(transport.type)
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
