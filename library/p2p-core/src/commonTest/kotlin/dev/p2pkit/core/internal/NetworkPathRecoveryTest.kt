package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.NetworkPathStatus
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.FakeNetworkPathObserver
import dev.p2pkit.core.testfixtures.createTestKit
import dev.p2pkit.core.testfixtures.withTestKit
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.async
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
import kotlin.test.assertNotSame
import kotlin.test.assertSame
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
        recording: P2pLogger,
        outgoingFactory: () -> RawConnection
    ): P2pKit = createTestKit {
        logger = recording
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

    private fun incomingKit(
        name: String,
        preStaged: List<RawConnection>,
        recording: P2pLogger,
        transport: FakeDataTransport = FakeDataTransport(preStagedIncoming = preStaged)
    ): P2pKit =
        createTestKit {
            logger = recording
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
                register(PathRecoveryTestFactory(transport))
            }
        }

    @Test
    fun pathUnsatisfiedTransitionsConnectedSessionToReconnecting() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        val fake = FakeNetworkPathObserver(initial = NetworkPathStatus.Satisfied)
        withTestKit(
            create = { recorder ->
                outgoingKit(
                    "Alice",
                    ReconnectPolicy.Enabled(maxAttempts = 5, retryDelayMillis = 5_000),
                    fake,
                    recording = recorder
                ) { pair.a }
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    incomingKit("Bob", listOf(pair.b), recording = recorder)
                }
            ) { bob ->
                val session = withTimeout(5_000) { alice.connect(targetPeer()) }
                assertEquals(ConnectionState.Connected, session.state.value)

                fake.emit(NetworkPathStatus.Unsatisfied)

                val reconnecting = withTimeout(5_000) {
                    session.state.first { it == ConnectionState.Reconnecting }
                }
                assertEquals(ConnectionState.Reconnecting, reconnecting)
            }
        }
    }

    @Test
    fun pathUnsatisfiedTransitionsToFailedWhenReconnectDisabled() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        val fake = FakeNetworkPathObserver(initial = NetworkPathStatus.Satisfied)
        withTestKit(
            create = { recorder ->
                outgoingKit(
                    "Alice",
                    ReconnectPolicy.Disabled,
                    fake,
                    recording = recorder
                ) { pair.a }
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    incomingKit("Bob", listOf(pair.b), recording = recorder)
                }
            ) { bob ->
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
            }
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
            withTestKit(
                create = { recorder ->
                    outgoingKit(
                        "Alice",
                        ReconnectPolicy.Disabled,
                        fake,
                        recording = recorder
                    ) { outgoing.removeFirstOrNull() ?: error("unexpected extra dial") }
                }
            ) { alice ->
                withTestKit(
                    create = { recorder ->
                        incomingKit("Bob", listOf(firstPair.b, secondPair.b), recording = recorder)
                    }
                ) { bob ->
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
                }
            }
        }

    @Test
    fun pathSatisfiedWakesParkedReconnectHandlerBeforeDelayExpires() = runBlocking<Unit> {
        val pair1 = FakeConnectionPair()
        val pair2 = FakeConnectionPair()
        val bobTransport = FakeDataTransport(preStagedIncoming = listOf(pair1.b))
        val attempts = MutableStateFlow(0)
        val fake = FakeNetworkPathObserver(initial = NetworkPathStatus.Satisfied)
        val oldCloseEntered = CompletableDeferred<Unit>()
        val releaseOldClose = CompletableDeferred<Unit>()
        val firstRaw = object : RawConnection by pair1.a {
            override suspend fun close() {
                oldCloseEntered.complete(Unit)
                releaseOldClose.await()
                pair1.a.close()
            }
        }
        try {
            withTestKit(
                create = { recorder ->
                    outgoingKit(
                        "Alice",
                        ReconnectPolicy.Enabled(maxAttempts = 3, retryDelayMillis = 30_000),
                        fake,
                        recording = recorder
                    ) {
                        attempts.update { it + 1 }
                        when (attempts.value) {
                            1 -> firstRaw
                            2 -> {
                                // A second accept begins only when its matching dial starts.
                                bobTransport.emitIncoming(pair2.b)
                                pair2.a
                            }
                            else -> error("unexpected third transport dial")
                        }
                    }
                }
            ) { alice ->
                withTestKit(
                    create = { recorder -> incomingKit("Bob", emptyList(), recorder, bobTransport) }
                ) { bob ->
                    try {
                        val session = withTimeout(5_000) { alice.connect(targetPeer()) }
                        val oldBob = withTimeout(5_000) { bob.sessions.first { it.isNotEmpty() }.single() }
                        assertEquals(ConnectionState.Connected, oldBob.state.value)

                        // Path loss is the sole trigger; no independent wire break
                        // may conflate away the Unsatisfied input (#400).
                        fake.emit(NetworkPathStatus.Unsatisfied)
                        withTimeout(5_000) { session.state.first { it == ConnectionState.Reconnecting } }
                        // Retirement must precede any retry, not wait for its handshake.
                        withTimeout(5_000) { oldCloseEntered.await() }
                        assertEquals(1, attempts.value)
                        assertEquals(ConnectionState.Connected, pair1.a.state.value)
                        assertSame(oldBob, bob.sessions.value.single())
                        releaseOldClose.complete(Unit)

                        // Local close is not remote-store acknowledgement. Establish
                        // that independent precondition before testing wake/adoption.
                        withTimeout(5_000) { oldBob.state.first { it == ConnectionState.Failed } }
                        fake.emit(NetworkPathStatus.Satisfied)
                        // Timer expiry (30 s) cannot satisfy this 10 s wake assertion.
                        withTimeout(10_000) {
                            assertEquals(2, attempts.first { it >= 2 })
                            session.state.first { it == ConnectionState.Connected }
                        }
                        val newBob = withTimeout(5_000) {
                            bob.sessions.first { sessions ->
                                sessions.singleOrNull()?.let {
                                    it !== oldBob && it.state.value == ConnectionState.Connected
                                } == true
                            }.single()
                        }
                        assertNotSame(oldBob, newBob)
                        val received = async(start = CoroutineStart.UNDISPATCHED) {
                            withTimeout(5_000) { newBob.incoming.first() }
                        }
                        val message = P2pMessage.Text("usable replacement after path recovery")
                        session.send(message)
                        assertEquals(message, received.await())
                        assertEquals(2, attempts.value)
                    } finally {
                        releaseOldClose.complete(Unit)
                    }
                }
            }
        } finally {
            releaseOldClose.complete(Unit)
            pair1.a.close()
            pair1.b.close()
            pair2.a.close()
            pair2.b.close()
        }
    }

    @Test
    fun closeDuringPathRetirementSharesRawOwnerAndPreventsRetry() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        val path = FakeNetworkPathObserver(NetworkPathStatus.Satisfied)
        val calls = MutableStateFlow(0)
        val dials = MutableStateFlow(0)
        val entered = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        val raw = object : RawConnection by pair.a {
            override suspend fun close() {
                calls.update { it + 1 }
                entered.complete(Unit)
                release.await()
                pair.a.close()
            }
        }
        try {
            withTestKit(create = { recorder ->
                outgoingKit("Alice", ReconnectPolicy.Enabled(3, 30_000), path, recorder) {
                    dials.update { it + 1 }
                    check(dials.value == 1) { "Closing must prevent a replacement dial" }
                    raw
                }
            }) { alice ->
                withTestKit(create = { recorder -> incomingKit("Bob", listOf(pair.b), recorder) }) { bob ->
                    try {
                        val session = withTimeout(5_000) { alice.connect(targetPeer()) }
                        withTimeout(5_000) { bob.sessions.first { it.isNotEmpty() } }
                        path.emit(NetworkPathStatus.Unsatisfied)
                        withTimeout(5_000) { entered.await() }
                        val closing = async(start = CoroutineStart.UNDISPATCHED) { session.close() }
                        withTimeout(5_000) {
                            session.state.first { it == ConnectionState.Closing || it == ConnectionState.Closed }
                        }
                        path.emit(NetworkPathStatus.Satisfied)
                        assertEquals(1, calls.value)
                        release.complete(Unit)
                        withTimeout(5_000) {
                            closing.await()
                            (session as P2pSessionImpl).awaitRuntimeTermination()
                        }
                        assertEquals(ConnectionState.Closed, session.state.value)
                        assertEquals(1, calls.value)
                        assertEquals(1, dials.value)
                    } finally {
                        release.complete(Unit)
                    }
                }
            }
        } finally {
            release.complete(Unit)
            pair.a.close()
            pair.b.close()
        }
    }

    @Test
    fun pathUnknownIsANoOp() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        val fake = FakeNetworkPathObserver(initial = NetworkPathStatus.Satisfied)
        withTestKit(
            create = { recorder ->
                outgoingKit(
                    "Alice",
                    ReconnectPolicy.Disabled,
                    fake,
                    recording = recorder
                ) { pair.a }
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    incomingKit("Bob", listOf(pair.b), recording = recorder)
                }
            ) { bob ->
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
            }
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
        withTestKit(
            create = { recorder ->
                outgoingKit(
                    "Alice",
                    ReconnectPolicy.Disabled,
                    fake,
                    recording = recorder
                ) { pair.a }
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    incomingKit("Bob", listOf(pair.b), recording = recorder)
                }
            ) { bob ->
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

                // Local connect returns independently of the responder's commit. Join Bob's
                // single live setup before fixture teardown rather than stopping it at that gate.
                val incoming = withTimeout(5_000) {
                    bob.sessions.first { it.isNotEmpty() }.single()
                }
                assertEquals(ConnectionState.Connected, incoming.state.value)
            }
        }
        assertTrue(
            fake.closeCalled >= 1,
            "Observer.close must be called by kit.stop() (got ${fake.closeCalled})"
        )
    }
}
