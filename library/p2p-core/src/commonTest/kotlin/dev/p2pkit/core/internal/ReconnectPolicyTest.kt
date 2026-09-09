package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.RecordingLogger
import dev.p2pkit.core.testfixtures.StatefulTestFailure
import dev.p2pkit.core.testfixtures.createTestKit
import dev.p2pkit.core.testfixtures.withTestKit
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertSame
import kotlin.test.assertTrue

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
 *   - retry delays are tiny except for lifecycle-interposition scenarios;
 *     their 1000 ms delay is not evidence that retries have stopped.
 *   - state observation always goes through `state.first { ... }` with a
 *     bounded `withTimeout`. No arbitrary sleeps for synchronization.
 *   - retry retirement is observed by joining the actual session runtime,
 *     without cancelling it. Public Closed alone does not prove that every
 *     owned retry child has finished.
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
        recording: P2pLogger,
        outgoingFactory: () -> RawConnection
    ): P2pKit = createTestKit {
        logger = recording
        appId = AppId("com.example.test")
        deviceName = name
        peerIdStorage = InMemoryPeerIdStorage(seed = PeerId("alice-id"))
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

    private fun incomingKit(
        name: String,
        preStaged: List<RawConnection>,
        recording: P2pLogger
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
                register(ReconnectTestFactory(FakeDataTransport(preStagedIncoming = preStaged)))
            }
        }

    /** Only a finite ordered prefix of this controlled factory's failed retry budget is valid. */
    private fun assertFailedReconnectDiagnostics(
        recorder: RecordingLogger,
        wireDiagnostic: RecordingLogger.Entry?,
        maxAttempts: Int,
        failureReason: String,
        exhausted: Boolean = false
    ) {
        val diagnostics = recorder.entries.filter {
            it.level == RecordingLogger.Level.WARN || it.level == RecordingLogger.Level.ERROR
        }
        val retryFailures = (1..maxAttempts).map { attempt ->
            RecordingLogger.Entry(
                RecordingLogger.Level.WARN,
                "reconnect: attempt=$attempt/$maxAttempts peer=bob-id name=Bob FAILED " +
                    "dialed=LAN:?:? source=FALLBACK reason=$failureReason"
            )
        }
        // The body may stop a retry episode at any point. Enumerate the source-defined prefixes,
        // not an expected count obtained from the log. Exhaustion must publish the entire budget.
        val permittedCounts = if (exhausted) maxAttempts..maxAttempts else 0..maxAttempts
        assertTrue(
            permittedCounts.any { count ->
                diagnostics == listOfNotNull(wireDiagnostic) + retryFailures.take(count)
            },
            "unexpected diagnostics outside the controlled retry sequence: $diagnostics"
        )
    }

    /** Observe retry invocation while preserving the real driver and onWillReconnect callback. */
    private fun P2pSessionImpl.observeReconnectEntry(): CompletableDeferred<Unit> {
        val entered = CompletableDeferred<Unit>()
        val delegate = checkNotNull(reconnectHandler)
        reconnectHandler = object : ReconnectHandler by delegate {
            override suspend fun onConnectionLost(session: P2pSessionImpl) {
                entered.complete(Unit)
                delegate.onConnectionLost(session)
            }
        }
        return entered
    }

    @Test
    fun disabledPolicyTransitionsDirectlyToFailed() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        val wireFailure = StatefulTestFailure("simulated wire break")
        var expectedWireDiagnostic: RecordingLogger.Entry? = null
        withTestKit(
            create = { recorder ->
                outgoingKit("Alice", ReconnectPolicy.Disabled, recording = recorder) { pair.a }
            },
            verifyDiagnostics = { recorder ->
                assertEquals(
                    listOfNotNull(expectedWireDiagnostic),
                    recorder.entries.filter {
                        it.level == RecordingLogger.Level.WARN || it.level == RecordingLogger.Level.ERROR
                    }
                )
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    incomingKit("Bob", listOf(pair.b), recording = recorder)
                }
            ) { bob ->
                val session = withTimeout(5_000) { alice.connect(targetPeer()) }
                // alice.connect returning means the handshake completed on both
                // sides — no need to observe bob.incomingSessions (it's replay=0
                // and the emit may have happened before we could subscribe).
                assertEquals(ConnectionState.Connected, session.state.value)

                expectedWireDiagnostic = RecordingLogger.Entry(
                    RecordingLogger.Level.WARN,
                    "Session ${session.id}: routeEvents failed",
                    wireFailure
                )
                pair.a.breakWithException(wireFailure)

                val terminal = withTimeout(5_000) {
                    session.state.first { it == ConnectionState.Failed || it == ConnectionState.Closed }
                }
                assertEquals(
                    ConnectionState.Failed, terminal,
                    "Disabled policy must transition broken sessions to Failed, never via Reconnecting"
                )
            }
        }
    }

    @Test
    fun enabledPolicyEmitsReconnectingOnConnectionLoss() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        val queue = ArrayDeque<RawConnection>().apply { add(pair.a) }
        val wireFailure = StatefulTestFailure("simulated wire break")
        var expectedWireDiagnostic: RecordingLogger.Entry? = null
        withTestKit(
            create = { recorder ->
                outgoingKit(
                    "Alice",
                    ReconnectPolicy.Enabled(maxAttempts = 3, retryDelayMillis = 10),
                    recording = recorder
                ) {
                    queue.removeFirstOrNull() ?: throw RuntimeException("no more connections")
                }
            },
            verifyDiagnostics = { recorder ->
                assertFailedReconnectDiagnostics(
                    recorder = recorder,
                    wireDiagnostic = expectedWireDiagnostic,
                    maxAttempts = 3,
                    failureReason = "RuntimeException: no more connections"
                )
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    incomingKit("Bob", listOf(pair.b), recording = recorder)
                }
            ) { bob ->
                val session = withTimeout(5_000) { alice.connect(targetPeer()) }
                // alice.connect returning means the handshake completed on both
                // sides — no need to observe bob.incomingSessions (it's replay=0
                // and the emit may have happened before we could subscribe).
                assertEquals(ConnectionState.Connected, session.state.value)

                expectedWireDiagnostic = RecordingLogger.Entry(
                    RecordingLogger.Level.WARN,
                    "Session ${session.id}: routeEvents failed",
                    wireFailure
                )
                pair.a.breakWithException(wireFailure)

                val reconnecting = withTimeout(5_000) {
                    session.state.first { it == ConnectionState.Reconnecting }
                }
                assertEquals(ConnectionState.Reconnecting, reconnecting)
            }
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
        val wireFailure = StatefulTestFailure("simulated wire break")
        var expectedWireDiagnostic: RecordingLogger.Entry? = null
        withTestKit(
            create = { recorder ->
                outgoingKit(
                    "Alice",
                    ReconnectPolicy.Enabled(maxAttempts = 5, retryDelayMillis = 20),
                    recording = recorder
                ) {
                    attempts.update { it + 1 }
                    queue.removeFirstOrNull() ?: throw RuntimeException("no more connections")
                }
            },
            verifyDiagnostics = { recorder ->
                assertEquals(
                    listOfNotNull(expectedWireDiagnostic),
                    recorder.entries.filter {
                        it.level == RecordingLogger.Level.WARN || it.level == RecordingLogger.Level.ERROR
                    }
                )
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    incomingKit("Bob", listOf(pair1.b, pair2.b), recording = recorder)
                }
            ) { bob ->
                val session = withTimeout(5_000) { alice.connect(targetPeer()) }
                // alice.connect returning means the handshake completed on both
                // sides — no need to observe bob.incomingSessions (it's replay=0
                // and the emit may have happened before we could subscribe).
                assertEquals(ConnectionState.Connected, session.state.value)

                expectedWireDiagnostic = RecordingLogger.Entry(
                    RecordingLogger.Level.WARN,
                    "Session ${session.id}: routeEvents failed",
                    wireFailure
                )
                pair1.a.breakWithException(wireFailure)
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
            }
        }
    }

    @Test
    fun enabledPolicyFailsAfterMaxAttempts() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        val attempts = MutableStateFlow(0)
        val maxAttempts = 3
        val wireFailure = StatefulTestFailure("simulated wire break")
        var expectedWireDiagnostic: RecordingLogger.Entry? = null
        withTestKit(
            create = { recorder ->
                outgoingKit(
                    "Alice",
                    ReconnectPolicy.Enabled(maxAttempts = maxAttempts, retryDelayMillis = 10),
                    recording = recorder
                ) {
                    val n = attempts.value
                    attempts.update { it + 1 }
                    if (n == 0) pair.a else throw RuntimeException("simulated transport unreachable")
                }
            },
            verifyDiagnostics = { recorder ->
                assertFailedReconnectDiagnostics(
                    recorder = recorder,
                    wireDiagnostic = expectedWireDiagnostic,
                    maxAttempts = maxAttempts,
                    failureReason = "RuntimeException: simulated transport unreachable",
                    exhausted = true
                )
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    incomingKit("Bob", listOf(pair.b), recording = recorder)
                }
            ) { bob ->
                val session = withTimeout(5_000) { alice.connect(targetPeer()) }

                expectedWireDiagnostic = RecordingLogger.Entry(
                    RecordingLogger.Level.WARN,
                    "Session ${session.id}: routeEvents failed",
                    wireFailure
                )
                pair.a.breakWithException(wireFailure)

                val terminal = withTimeout(5_000) {
                    session.state.first { it == ConnectionState.Failed || it == ConnectionState.Closed }
                }
                assertEquals(ConnectionState.Failed, terminal)
                assertEquals(
                    1 + maxAttempts, attempts.value,
                    "Factory should be called initial + exactly $maxAttempts retries"
                )
            }
        }
    }

    @Test
    fun closeDuringReconnectStopsRetriesAndEndsClosed() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        val attempts = MutableStateFlow(0)
        val wireFailure = StatefulTestFailure("simulated wire break")
        var expectedWireDiagnostic: RecordingLogger.Entry? = null
        withTestKit(
            create = { recorder ->
                outgoingKit(
                    "Alice",
                    ReconnectPolicy.Enabled(maxAttempts = 5, retryDelayMillis = 1_000),
                    recording = recorder
                ) {
                    val n = attempts.value
                    attempts.update { it + 1 }
                    if (n == 0) pair.a else throw RuntimeException("simulated transport unreachable")
                }
            },
            verifyDiagnostics = { recorder ->
                assertFailedReconnectDiagnostics(
                    recorder = recorder,
                    wireDiagnostic = expectedWireDiagnostic,
                    maxAttempts = 5,
                    failureReason = "RuntimeException: simulated transport unreachable"
                )
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    incomingKit("Bob", listOf(pair.b), recording = recorder)
                }
            ) { bob ->
                val session = assertIs<P2pSessionImpl>(withTimeout(5_000) { alice.connect(targetPeer()) })

                val reconnectEntered = session.observeReconnectEntry()
                expectedWireDiagnostic = RecordingLogger.Entry(
                    RecordingLogger.Level.WARN,
                    "Session ${session.id}: routeEvents failed",
                    wireFailure
                )
                pair.a.breakWithException(wireFailure)
                withTimeout(5_000) {
                    session.state.first { it == ConnectionState.Reconnecting }
                    reconnectEntered.await()
                }

                val attemptsAtClose = attempts.value
                session.close()
                assertEquals(
                    ConnectionState.Closed, session.state.value,
                    "Manual close() must take precedence over reconnect exhaustion"
                )
                // Join the actual retry owner rather than sampling a short absence window.
                withTimeout(5_000) { session.awaitRuntimeTermination() }
                assertEquals(
                    attemptsAtClose, attempts.value,
                    "Factory must not be called after close()"
                )
                assertEquals(
                    ConnectionState.Closed, session.state.value,
                    "State must remain Closed after close() — never flip to Failed"
                )
            }
        }
    }

    @Test
    fun kitStopDuringReconnectStopsRetries() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        val attempts = MutableStateFlow(0)
        val wireFailure = StatefulTestFailure("simulated wire break")
        var expectedWireDiagnostic: RecordingLogger.Entry? = null
        withTestKit(
            create = { recorder ->
                outgoingKit(
                    "Alice",
                    ReconnectPolicy.Enabled(maxAttempts = 5, retryDelayMillis = 1_000),
                    recording = recorder
                ) {
                    val n = attempts.value
                    attempts.update { it + 1 }
                    if (n == 0) pair.a else throw RuntimeException("simulated transport unreachable")
                }
            },
            verifyDiagnostics = { recorder ->
                assertFailedReconnectDiagnostics(
                    recorder = recorder,
                    wireDiagnostic = expectedWireDiagnostic,
                    maxAttempts = 5,
                    failureReason = "RuntimeException: simulated transport unreachable"
                )
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    incomingKit("Bob", listOf(pair.b), recording = recorder)
                }
            ) { bob ->
                val session = assertIs<P2pSessionImpl>(withTimeout(5_000) { alice.connect(targetPeer()) })

                val reconnectEntered = session.observeReconnectEntry()
                expectedWireDiagnostic = RecordingLogger.Entry(
                    RecordingLogger.Level.WARN,
                    "Session ${session.id}: routeEvents failed",
                    wireFailure
                )
                pair.a.breakWithException(wireFailure)
                withTimeout(5_000) {
                    session.state.first { it == ConnectionState.Reconnecting }
                    reconnectEntered.await()
                }

                alice.stop()
                assertEquals(
                    ConnectionState.Closed, session.state.value,
                    "kit.stop() must leave reconnecting sessions terminally Closed"
                )
                // A dial that crossed the stop boundary before shutdown acquired
                // session ownership is allowed to finish being cancelled. The
                // contract begins when stop() returns: no later retry may start.
                val attemptsAfterStop = attempts.value
                withTimeout(5_000) { session.awaitRuntimeTermination() }
                assertEquals(
                    attemptsAfterStop, attempts.value,
                    "Factory must not be called after kit.stop() returns"
                )
            }
        }
    }

    @Test
    fun concurrentConnectDuringReconnectReturnsSameSession() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        val wireFailure = StatefulTestFailure("simulated wire break")
        var expectedWireDiagnostic: RecordingLogger.Entry? = null
        withTestKit(
            create = { recorder ->
                outgoingKit(
                    "Alice",
                    ReconnectPolicy.Enabled(maxAttempts = 5, retryDelayMillis = 1_000),
                    recording = recorder
                ) {
                    // First call serves initial connect; later calls fail to keep the
                    // session pinned in Reconnecting for the duration of this test.
                    if (pair.a.state.value == ConnectionState.Connected) pair.a
                    else throw RuntimeException("simulated transport unreachable")
                }
            },
            verifyDiagnostics = { recorder ->
                assertFailedReconnectDiagnostics(
                    recorder = recorder,
                    wireDiagnostic = expectedWireDiagnostic,
                    maxAttempts = 5,
                    failureReason = "RuntimeException: simulated transport unreachable"
                )
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    incomingKit("Bob", listOf(pair.b), recording = recorder)
                }
            ) { bob ->
                val firstSession = withTimeout(5_000) { alice.connect(targetPeer()) }

                expectedWireDiagnostic = RecordingLogger.Entry(
                    RecordingLogger.Level.WARN,
                    "Session ${firstSession.id}: routeEvents failed",
                    wireFailure
                )
                pair.a.breakWithException(wireFailure)
                withTimeout(5_000) { firstSession.state.first { it == ConnectionState.Reconnecting } }

                val secondSession = withTimeout(5_000) { alice.connect(targetPeer()) }
                assertSame(
                    firstSession, secondSession,
                    "connect() during Reconnecting must return the existing session"
                )
            }
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
        withTestKit(
            create = { recorder ->
                outgoingKit(
                    "Alice",
                    ReconnectPolicy.Enabled(maxAttempts = 5, retryDelayMillis = 1_000),
                    recording = recorder
                ) {
                    queue.removeFirstOrNull() ?: throw RuntimeException("no more connections")
                }
            },
            verifyDiagnostics = { recorder ->
                assertFailedReconnectDiagnostics(
                    recorder = recorder,
                    wireDiagnostic = null,
                    maxAttempts = 5,
                    failureReason = "RuntimeException: no more connections"
                )
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    incomingKit("Bob", listOf(pair.b), recording = recorder)
                }
            ) { bob ->
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
            }
        }
    }

    @Test
    fun responderStopDuringAsymmetricHandshakeSendsCloseBeforeTransportTeardown() = runBlocking<Unit> {
        // Reproduce the hosted Apple race without scheduler timing: Alice's
        // HELLO write reports success but is withheld from Bob, while Bob's
        // HELLO reaches Alice. Alice can therefore publish Connected while
        // Bob is still an in-flight handshake absent from bob.sessions.
        val pair = FakeConnectionPair()
        val withheldAlice = FirstWriteWithheldConnection(pair.a)
        val attempts = MutableStateFlow(0)
        withTestKit(
            create = { recorder ->
                outgoingKit(
                    "Alice",
                    ReconnectPolicy.Enabled(maxAttempts = 3, retryDelayMillis = 500),
                    recording = recorder
                ) {
                    val n = attempts.value
                    attempts.update { it + 1 }
                    if (n == 0) withheldAlice else throw RuntimeException("unexpected reconnect")
                }
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    incomingKit("Bob", listOf(pair.b), recording = recorder)
                }
            ) { bob ->
                val session = withTimeout(5_000) { alice.connect(targetPeer()) }
                withheldAlice.firstWriteWithheld.await()
                assertEquals(ConnectionState.Connected, session.state.value)
                assertTrue(
                    bob.sessions.value.isEmpty(),
                    "the fixture must stop Bob inside the pre-registration handshake gap"
                )
                val terminal = async(start = CoroutineStart.UNDISPATCHED) {
                    session.state.first { it == ConnectionState.Closed }
                }

                bob.stop()

                assertEquals(ConnectionState.Closed, withTimeout(5_000) { terminal.await() })
                assertEquals(
                    1,
                    attempts.value,
                    "tracked setup shutdown must send CLOSE and never trigger Alice reconnect"
                )
            }
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
        withTestKit(
            create = { recorder ->
                outgoingKit(
                    "Alice",
                    ReconnectPolicy.Enabled(maxAttempts = 5, retryDelayMillis = 1_000),
                    recording = recorder
                ) {
                    val n = attempts.value
                    attempts.update { it + 1 }
                    if (n == 0) pair.a else throw RuntimeException("no more connections")
                }
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    incomingKit("Bob", listOf(pair.b), recording = recorder)
                }
            ) { bob ->
                val session = assertIs<P2pSessionImpl>(withTimeout(5_000) { alice.connect(targetPeer()) })
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

                // A CLOSE frame may correct a transient Reconnecting state.
                // All owned retry work must finish before the no-redial assertion.
                withTimeout(5_000) { session.awaitRuntimeTermination() }
                assertEquals(
                    1, attempts.value,
                    "dial factory must not be re-invoked after a remote CLOSE frame"
                )
                assertEquals(ConnectionState.Closed, session.state.value)
            }
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
            withTestKit(
                create = { recorder ->
                    outgoingKit(
                        "Alice",
                        ReconnectPolicy.Enabled(maxAttempts = 5, retryDelayMillis = 1_000),
                        recording = recorder
                    ) {
                        val n = attempts.value
                        attempts.update { it + 1 }
                        if (n == 0) pair.a else throw RuntimeException("no more connections")
                    }
                }
            ) { alice ->
                withTestKit(
                    create = { recorder ->
                        incomingKit("Bob", listOf(pair.b), recording = recorder)
                    }
                ) { bob ->
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
                }
            }
        }
    }
}

/** Holds exactly the first write while allowing the reverse direction through. */
private class FirstWriteWithheldConnection(
    private val delegate: RawConnection
) : RawConnection {
    val firstWriteWithheld = CompletableDeferred<Unit>()
    private val writeLock = Mutex()
    private var withholdFirst = true

    override val state: StateFlow<ConnectionState> = delegate.state

    override suspend fun write(bytes: ByteArray) {
        val withheld = writeLock.withLock {
            if (withholdFirst) {
                withholdFirst = false
                true
            } else {
                false
            }
        }
        if (withheld) {
            firstWriteWithheld.complete(Unit)
        } else {
            delegate.write(bytes)
        }
    }

    override fun read(): Flow<ByteArray> = delegate.read()

    override suspend fun close() = delegate.close()
}

private class ReconnectTestFactory(private val transport: FakeDataTransport) : TransportFactory {
    override val descriptor =
        dev.p2pkit.core.transport.TransportDescriptor.dataOnly(transport.type)
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = null)
}
