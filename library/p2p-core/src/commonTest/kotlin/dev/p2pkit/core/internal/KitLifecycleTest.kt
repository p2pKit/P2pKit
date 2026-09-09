package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.FeatureState
import dev.p2pkit.core.NetworkPathObserver
import dev.p2pkit.core.NetworkPathStatus
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pState
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.FakeDiscoveryTransport
import dev.p2pkit.core.testfixtures.MemorySecureIdentityStorage
import dev.p2pkit.core.testfixtures.RecordingLogger
import dev.p2pkit.core.testfixtures.createSecureTestKit
import dev.p2pkit.core.testfixtures.createTestKit
import dev.p2pkit.core.testfixtures.withTestKit
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.DiscoveryTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportDescriptor
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlin.concurrent.Volatile
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancel
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.channels.ClosedReceiveChannelException
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.coroutines.yield
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertSame
import kotlin.test.assertTrue

/**
 * Verifies that [P2pKit.stop] actually calls cleanup on every registered
 * transport, and that a fresh kit constructed after `stop()` is independent
 * of the previous one.
 *
 * This guards against the class of bug seen in the v0.1 sample apps where the
 * UI's Stop button left the kit's mDNS/TCP listeners alive — that was a UI
 * lifecycle bug, but this test pins the library-side contract that the UI
 * fix relies on.
 */
class KitLifecycleTest {

    @Test
    fun stopClearsPeerRegistrySnapshots() = runBlocking {
        val transport = TrackingTransport()
        withTestKit(create = { recording ->
            createTestKit {
                logger = recording
                appId = AppId("stop-clears-peers-test")
                deviceName = "Test"
                transports { register(TrackingFactory(transport)) }
            }
        }) { kit ->
            withTimeout(5_000) { transport.awaitPeerCollector() }
            transport.emitPeer(
                PeerEvent.Found(
                    InternalPeer(
                        publicPeer = Peer(
                            id = PeerId("discovered-before-stop"),
                            name = "Peer",
                            platform = Platform.JVM_DESKTOP,
                            supportedTransports = setOf(TransportKind.LAN)
                        ),
                        transportHints = emptyList()
                    )
                )
            )
            assertEquals(1, withTimeout(5_000) { kit.peers.first { it.size == 1 } }.size)

            kit.stop()

            assertTrue(kit.peers.value.isEmpty())
            assertEquals(null, kit.lastSeen(PeerId("discovered-before-stop")))
        }
    }

    @Test
    fun stopClosesDataTransportAndStopsDiscoveryAdvertising() {
        runBlocking {
            val transport = TrackingTransport()
            withTestKit(create = { recording ->
                createTestKit {
                    logger = recording
                    appId = AppId("lifecycle-test")
                    deviceName = "Test"
                    transports { register(TrackingFactory(transport)) }
                }
            }) { kit ->
                kit.startAdvertising()
                kit.startDiscovery()
                assertTrue(transport.advertisingStarted, "startAdvertising never propagated to transport")
                assertTrue(transport.discoveryStarted, "startDiscovery never propagated to transport")

                kit.stop()

                assertEquals(P2pState.Stopped, kit.state.value)
                assertTrue(transport.dataClosed, "DataTransport.close() should have been called")
                assertTrue(transport.advertisingStopped, "stopAdvertising should have been called")
                assertTrue(transport.discoveryStopped, "stopDiscovery should have been called")
            }
        }
    }

    @Test
    fun defaultBackgroundPolicyStopsBothRequestedFeatures() = runBlocking {
        val transport = TrackingTransport()
        withTestKit(create = { recording ->
            createTestKit {
                logger = recording
                appId = AppId("background-feature-stop-test")
                deviceName = "Test"
                transports { register(TrackingFactory(transport)) }
            }
        }) { kit ->
            kit.startAdvertising()
            kit.startDiscovery()
            assertEquals(FeatureState.Active, kit.advertisingState.value)
            assertEquals(FeatureState.Active, kit.discoveryState.value)

            kit.notifyAppBackgrounded()

            withTimeout(5_000) {
                kit.advertisingState.first { it == FeatureState.Idle }
            }
            withTimeout(5_000) {
                kit.discoveryState.first { it == FeatureState.Idle }
            }
            assertTrue(transport.advertisingStopped)
            assertTrue(transport.discoveryStopped)
            assertEquals(P2pState.Running, kit.state.value)
            assertFalse(transport.dataClosed, "backgrounding is not terminal kit stop")

            kit.notifyAppForegrounded()
            assertEquals(FeatureState.Idle, kit.advertisingState.value)
            assertEquals(FeatureState.Idle, kit.discoveryState.value)
            kit.startAdvertising()
            kit.startDiscovery()
            assertEquals(FeatureState.Active, kit.advertisingState.value)
            assertEquals(FeatureState.Active, kit.discoveryState.value)
        }
    }

    @Test
    fun backgroundAdvertisingFailureIsObservableAndStillStopsEveryDiscoveryTransport() = runBlocking {
        assertBackgroundStopFailureRemainsObservable(IllegalStateException("advertising cleanup failed"))
    }

    @Test
    fun backgroundProviderCancellationIsObservableAndStillStopsEveryDiscoveryTransport() = runBlocking {
        assertBackgroundStopFailureRemainsObservable(CancellationException("provider cleanup cancelled"))
    }

    // Characterization of existing cleanup semantics: both provider failures already become typed
    // feature failures under NonCancellable cleanup; neither is structural cancellation of the kit.
    private suspend fun assertBackgroundStopFailureRemainsObservable(providerFailure: Throwable) {
        val failing = RollbackDiscoveryTransport(TransportKind.LAN).apply {
            stopAdvertisingFailure = providerFailure
        }
        val healthy = RollbackDiscoveryTransport(TransportKind.BLE)
        lateinit var recording: RecordingLogger
        var expectedWarnings = emptyList<RecordingLogger.Entry>()
        val store = MemorySecureIdentityStorage()
        try {
            withTestKit(
                create = { recorder ->
                    recording = recorder
                    P2pKit.create {
                        appId = AppId("background-stop-failure-channel")
                        deviceName = "Test"
                        secureIdentityStorage = store
                        strictSessionInvariants = true
                        security { mode = SecurityMode.AuthenticatedV2(PeerAuthorizationPolicy.RejectUnknown) }
                        logger = recorder
                        transports {
                            register(RollbackDiscoveryFactory(failing))
                            register(RollbackDiscoveryFactory(healthy))
                        }
                    }
                },
                verifyDiagnostics = { recorder -> assertLifecycleDiagnostics(recorder, expectedWarnings) }
            ) { kit ->
                try {
                    kit.startAdvertising()
                    kit.startDiscovery()
                    kit.notifyAppBackgrounded()
                    val failed = withTimeout(5_000) {
                        assertIs<FeatureState.Failed>(kit.advertisingState.first { it is FeatureState.Failed })
                    }
                    withTimeout(5_000) { kit.discoveryState.first { it == FeatureState.Idle } }
                    val error = assertIs<P2pError.ConnectionFailed>(failed.error)
                    expectedWarnings = listOf(
                        lifecycleWarning("stop advertising failed for LAN discovery transport", providerFailure),
                        lifecycleWarning("Background advertising stop failed", error)
                    )
                    val aggregate = assertIs<CleanupAggregateException>(error.cause)
                    assertSame(providerFailure, aggregate.issues.single().cause)
                    assertEquals(1, failing.stopAdvertisingCalls)
                    assertEquals(1, healthy.stopAdvertisingCalls)
                    assertEquals(1, failing.stopDiscoveryCalls)
                    assertEquals(1, healthy.stopDiscoveryCalls)
                    assertTrue(failing.advertisingActive, "failed cleanup must not be presented as settled")
                    assertFalse(healthy.advertisingActive)
                    assertFalse(failing.discoveryActive)
                    assertFalse(healthy.discoveryActive)
                    assertEquals(P2pState.Running, kit.state.value)
                    val warning = recording.entries.single { it.message == "Background advertising stop failed" }
                    assertEquals(RecordingLogger.Level.WARN, warning.level)
                    assertSame(error, warning.throwable, "the logger and feature flow must describe the same failure")
                } finally {
                    failing.stopAdvertisingFailure = null
                }
            }
        } finally {
            store.clear()
        }
    }

    @Test
    fun freshKitAfterStopIsIndependent() {
        runBlocking {
            val first = TrackingTransport()
            withTestKit(create = { recording ->
                createTestKit {
                    logger = recording
                    appId = AppId("indep-test")
                    deviceName = "First"
                    transports { register(TrackingFactory(first)) }
                }
            }) { k1 ->
                k1.startAdvertising()
                k1.stop()
                assertTrue(first.dataClosed)
            }

            // After stopping the first kit, a brand-new kit with a separate
            // transport should not see any state leak from the first.
            val second = TrackingTransport()
            withTestKit(create = { recording ->
                createTestKit {
                    logger = recording
                    appId = AppId("indep-test")
                    deviceName = "Second"
                    transports { register(TrackingFactory(second)) }
                }
            }) { k2 ->
                assertFalse(second.dataClosed, "Fresh transport should not be closed before any start")
                assertFalse(second.advertisingStarted, "Fresh transport should not have any advertising history")

                k2.startAdvertising()
                assertTrue(second.advertisingStarted)
                assertFalse(second.dataClosed)

                k2.stop()
                assertTrue(second.dataClosed)
            }
        }
    }

    /**
     * AUDIT-2026-06 (stop-hang fix): a transport whose `start()` hangs holds
     * the kit's start mutex from inside `ensureStarted`. `stop()` must not
     * park uncancellably behind it — it bounds the mutex acquisition (5 s)
     * and falls back to lock-less teardown. And when the hung `start()`
     * finally returns, the late `ensureStarted` must observe `stopped` and
     * refuse to latch Running over the Stopped kit.
     */
    @Test
    fun stopCompletesWhenATransportStartHangs() {
        runBlocking {
            val transport = HungStartTransport()
            var expectedStopFailure: P2pError.ConnectionFailed? = null
            var expectedWarnings = emptyList<RecordingLogger.Entry>()
            // Preserve the deliberately cached failure; the scope must not hide a net failure in it.
            val repeatedStopFailure = assertFailsWith<P2pError.ConnectionFailed> {
                withTestKit(
                    create = { recorder ->
                        createTestKit {
                            logger = recorder
                            appId = AppId("stop-hang-test")
                            deviceName = "Test"
                            transports { register(HungStartFactory(transport)) }
                        }
                    },
                    verifyDiagnostics = { recorder -> assertLifecycleDiagnostics(recorder, expectedWarnings) }
                ) { kit ->
                    // Park ensureStarted inside transport.start() while it holds the
                    // start mutex. start() is expected to fail once stop() tears the
                    // kit down (the post-bind stopped re-check throws); swallow it —
                    // this coroutine exists only to keep the mutex held.
                    val starter = launch { runCatching { kit.start() } }
                    try {
                        transport.startEntered.await()

                        // Pre-fix, stop() parked forever on the held mutex and this
                        // outer bound (3x the 5 s mutex-acquisition bound) fired.
                        val stopFailure = assertFailsWith<P2pError.ConnectionFailed> {
                            withTimeout(15_000) { kit.stop() }
                        }
                        expectedStopFailure = stopFailure
                        expectedWarnings = startupStopDiagnostics(stopFailure, observerTimeout = false)
                        assertEquals(P2pState.Stopped, kit.state.value)
                        assertTrue(
                            transport.dataClosed,
                            "lock-less teardown must still close the data transport"
                        )

                        // Release the hung start(): the late ensureStarted resumes, must
                        // see `stopped` after its bind loop, and must NOT latch Running.
                        transport.releaseStart.complete(Unit)
                        withTimeout(15_000) { starter.join() }
                        assertEquals(
                            P2pState.Stopped, kit.state.value,
                            "a late ensureStarted must not overwrite Stopped with Running/Failed"
                        )
                    } finally {
                        withContext(NonCancellable) {
                            transport.releaseStart.complete(Unit)
                            starter.cancelAndJoin()
                        }
                    }
                }
            }
            assertSame(expectedStopFailure, repeatedStopFailure)
            assertTrue(
                repeatedStopFailure.suppressedExceptions.isEmpty(),
                "expected cached stop failure must not conceal teardown/net failures"
            )
        }
    }

    /**
     * P1-07 (2026-07 coverage plan): the documented lifecycle sequence
     * `Idle -> Starting -> Running`, observed deterministically by parking
     * the bind loop mid-start.
     */
    @Test
    fun startDrivesIdleThroughStartingToRunning() {
        runBlocking {
            val transport = HungStartTransport()
            withTestKit(
                create = { recorder ->
                    createTestKit {
                        logger = recorder
                        appId = AppId("state-machine-test")
                        deviceName = "Test"
                        transports { register(HungStartFactory(transport)) }
                    }
                }
            ) { kit ->
                assertEquals(P2pState.Idle, kit.state.value, "a fresh kit must report Idle")

                val starter = launch { kit.start() }
                try {
                    transport.startEntered.await()
                    assertEquals(
                        P2pState.Starting, kit.state.value,
                        "state must report Starting while the bind loop is in flight"
                    )

                    transport.releaseStart.complete(Unit)
                    withTimeout(15_000) { starter.join() }
                    assertEquals(P2pState.Running, kit.state.value, "successful start must reach Running")

                    kit.stop()
                } finally {
                    withContext(NonCancellable) {
                        transport.releaseStart.complete(Unit)
                        starter.cancelAndJoin()
                    }
                }
            }
        }
    }

    /**
     * P1-07 (2026-07 coverage plan): a transport bind failure surfaces as the
     * typed [P2pError.TransportStartFailed] attributed to the failing
     * transport, publishes [P2pState.Failed] carrying that exact error, and
     * does NOT latch — the next `start()` re-runs the bind and reaches
     * Running.
     */
    @Test
    fun bindFailureSurfacesTypedFailedStateAndDoesNotLatch() {
        runBlocking {
            val transport = FakeDataTransport()
            val bindRefusal = IllegalStateException("simulated OS bind refusal")
            transport.startFailure = bindRefusal
            withTestKit(
                create = { recorder ->
                    createTestKit {
                        logger = recorder
                        appId = AppId("bind-failure-test")
                        deviceName = "Test"
                        transports { register(DataOnlyFactory(transport)) }
                    }
                }
            ) { kit ->
                val thrown = assertFailsWith<P2pError.TransportStartFailed> { kit.start() }
                assertEquals(TransportKind.LAN, thrown.transportKind)
                assertSame(bindRefusal, thrown.underlying, "the OS-level cause must be preserved")
                val failed = kit.state.value
                assertIs<P2pState.Failed>(failed, "bind failure must publish P2pState.Failed")
                assertSame(thrown, failed.error, "Failed must carry the thrown error instance")
                assertEquals(
                    1,
                    transport.stopCalls,
                    "even the failing transport may have acquired resources and must be rolled back"
                )

                // A failed start must not latch: the retry re-runs the bind.
                transport.startFailure = null
                withTimeout(15_000) { kit.start() }
                assertEquals(P2pState.Running, kit.state.value, "retried start must reach Running")
                assertEquals(
                    2, transport.startCalls,
                    "the retry must re-run transport.start(), not fast-path a latched failure"
                )

                kit.stop()
            }
        }
    }

    @Test
    fun lazyConnectSurfacesTransportStartFailureBeforeDialing() = runBlocking<Unit> {
        val transport = FakeDataTransport().also {
            it.startFailure = IllegalStateException("lazy bind failed")
        }
        withTestKit(
            create = { recorder ->
                createTestKit {
                    logger = recorder
                    appId = AppId("lazy-connect-start-failure")
                    deviceName = "Test"
                    transports { register(DataOnlyFactory(transport)) }
                }
            }
        ) { kit ->
            val peer = Peer(
                id = PeerId("remote-peer"),
                name = "Remote",
                platform = Platform.JVM_DESKTOP,
                supportedTransports = setOf(TransportKind.LAN)
            )

            val failure = assertFailsWith<P2pError.TransportStartFailed> {
                kit.connect(peer)
            }
            assertEquals(TransportKind.LAN, failure.transportKind)
            assertTrue(transport.connectCalls.isEmpty())
            assertIs<P2pState.Failed>(kit.state.value)
        }
    }

    @Test
    fun terminalKitRejectsFeatureWorkWhileKitStopRemainsIdempotent() = runBlocking<Unit> {
        val transport = TrackingTransport()
        withTestKit(
            create = { recorder ->
                createTestKit {
                    logger = recorder
                    appId = AppId("terminal-public-contract")
                    deviceName = "Test"
                    transports { register(TrackingFactory(transport)) }
                }
            }
        ) { kit ->
            val peer = Peer(
                id = PeerId("remote-peer"),
                name = "Remote",
                platform = Platform.JVM_DESKTOP,
                supportedTransports = setOf(TransportKind.LAN)
            )

            kit.stop()

            kit.stop()
            assertEquals(P2pState.Stopped, kit.state.value)
            assertFailsWith<IllegalStateException> { kit.start() }
            assertFailsWith<IllegalStateException> { kit.startAdvertising() }
            assertFailsWith<IllegalStateException> { kit.startDiscovery() }
            assertFailsWith<IllegalStateException> { kit.stopAdvertising() }
            assertFailsWith<IllegalStateException> { kit.stopDiscovery() }
            assertFailsWith<IllegalStateException> { kit.connect(peer) }
        }
    }

    @Test
    fun partialDataStartupRollsBackInReverseAndSameInstancesRetry() = runBlocking {
        val calls = mutableListOf<String>()
        val first = StartupProbeTransport(TransportKind.LAN, "first", calls)
        val second = StartupProbeTransport(TransportKind.BLE, "second", calls).also {
            it.startFailure = IllegalStateException("second bind failed after acquisition")
        }
        withTestKit(
            create = { recorder ->
                createTestKit {
                    logger = recorder
                    appId = AppId("data-start-rollback-test")
                    deviceName = "Test"
                    transports {
                        register(DataOnlyFactory(first))
                        register(DataOnlyFactory(second))
                    }
                }
            }
        ) { kit ->
            assertFailsWith<P2pError.TransportStartFailed> { kit.start() }
            assertEquals(
                listOf("start:first", "start:second", "stop:second", "stop:first"),
                calls,
                "rollback must include the failing transport and run in reverse entry order"
            )
            assertFalse(first.active)
            assertFalse(second.active)
            assertFalse(first.closed)
            assertFalse(second.closed)

            second.startFailure = null
            kit.start()
            assertEquals(
                listOf(
                    "start:first", "start:second", "stop:second", "stop:first",
                    "start:first", "start:second"
                ),
                calls
            )
            assertTrue(first.active)
            assertTrue(second.active)

            kit.stop()
            assertTrue(first.closed)
            assertTrue(second.closed)
        }
    }

    @Test
    fun dataStartupWithUnsettledRollbackRetainsFailingTransportAttribution() = runBlocking {
        val calls = mutableListOf<String>()
        val cleanupFailure = IllegalStateException("first listener stop failed")
        val bindFailure = IllegalStateException("second listener bind failed")
        val first = StartupProbeTransport(TransportKind.LAN, "first", calls).also {
            it.stopFailure = cleanupFailure
        }
        val second = StartupProbeTransport(TransportKind.BLE, "second", calls).also {
            it.startFailure = bindFailure
        }
        val store = MemorySecureIdentityStorage()
        try {
            withTestKit(
                create = { recorder ->
                    createSecureTestKit(
                        appId = AppId("data-rollback-attribution"),
                        name = "Test",
                        store = store,
                        transport = first,
                        authorization = PeerAuthorizationPolicy.RejectUnknown
                    ) {
                        logger = recorder
                        transports { register(DataOnlyFactory(second)) }
                    }
                },
                verifyDiagnostics = { recorder ->
                    assertLifecycleDiagnostics(recorder, listOf(lifecycleWarning(
                        "Late lifecycle cleanup failed for LAN data startup",
                        cleanupFailure
                    )))
                }
            ) { kit ->
                try {
                    val failure = assertFailsWith<P2pError.TransportStartFailed> { kit.start() }
                    assertEquals(TransportKind.BLE, failure.transportKind)
                    assertSame(failure, assertIs<P2pState.Failed>(kit.state.value).error)
                    val aggregate = assertIs<CleanupAggregateException>(failure.cause)
                    assertEquals("failed data startup", aggregate.operation)
                    assertSame(cleanupFailure, aggregate.issues.single().cause)
                    val original = assertIs<P2pError.TransportStartFailed>(failure.suppressedExceptions.single())
                    assertEquals(TransportKind.BLE, original.transportKind)
                    assertSame(bindFailure, original.cause)
                    assertEquals(listOf("start:first", "start:second", "stop:second", "stop:first"), calls)

                    assertSame(failure, assertFailsWith<P2pError.TransportStartFailed> { kit.start() })
                    assertEquals(4, calls.size, "a blocked retry must not re-enter any transport")
                } finally {
                    first.stopFailure = null
                }
            }
        } finally {
            store.clear()
        }
        assertTrue(first.closed)
        assertTrue(second.closed)
    }

    /** Advertising failure/retry is retained without corrupting discovery or kit state. */
    @Test
    fun advertisingFailureIsIndependentAndRetryReachesActive() {
        runBlocking {
            val transport = TrackingTransport()
            withTestKit(
                create = { recorder ->
                    createTestKit {
                        logger = recorder
                        appId = AppId("readvertise-test")
                        deviceName = "Test"
                        transports { register(TrackingFactory(transport)) }
                    }
                }
            ) { kit ->
                kit.start()
                assertEquals(P2pState.Running, kit.state.value)

                transport.advertiseFailure = RuntimeException("simulated mDNS registration refusal")
                val thrown = assertFailsWith<P2pError.ConnectionFailed> { kit.startAdvertising() }
                val failed = assertIs<FeatureState.Failed>(
                    kit.advertisingState.value,
                    "advertising must retain its own failure"
                )
                assertSame(thrown, failed.error)
                assertEquals(P2pState.Running, kit.state.value)
                assertEquals(FeatureState.Idle, kit.discoveryState.value)

                kit.startDiscovery()
                assertEquals(FeatureState.Active, kit.discoveryState.value)
                assertIs<FeatureState.Failed>(kit.advertisingState.value)

                transport.advertiseFailure = null
                kit.startAdvertising()
                assertEquals(FeatureState.Active, kit.advertisingState.value)
                assertEquals(FeatureState.Active, kit.discoveryState.value)
                assertEquals(P2pState.Running, kit.state.value)

                kit.stop()
            }
        }
    }

    @Test
    fun cancellationDuringFeatureRetryCleanupDoesNotStrandStarting() = runBlocking {
        val transport = RetryCleanupCancellationTransport()
        withTestKit(
            create = { recorder ->
                createTestKit {
                    logger = recorder
                    appId = AppId("cancel-feature-retry-cleanup-test")
                    deviceName = "Test"
                    transports { register(RetryCleanupCancellationFactory(transport)) }
                }
            },
            verifyDiagnostics = { recorder ->
                assertLifecycleDiagnostics(recorder, listOf(lifecycleWarning(
                    "Late lifecycle cleanup failed for LAN advertising",
                    transport.firstRollbackFailure
                )))
            }
        ) { kit ->
            assertFailsWith<P2pError.ConnectionFailed> { kit.startAdvertising() }
            assertIs<FeatureState.Failed>(kit.advertisingState.value)
            assertEquals(1, transport.startAdvertisingCalls)
            assertEquals(1, transport.stopAdvertisingCalls)

            var thrown: Throwable? = null
            val retry = launch {
                try {
                    kit.startAdvertising()
                } catch (failure: Throwable) {
                    thrown = failure
                    throw failure
                }
            }
            try {
                transport.retryCleanupEntered.await()
                retry.cancelAndJoin()

                assertIs<CancellationException>(thrown)
                assertEquals(
                    FeatureState.Idle,
                    kit.advertisingState.value,
                    "cancelled retry cleanup must settle the feature transaction"
                )
                assertEquals(3, transport.stopAdvertisingCalls)
                assertFalse(transport.advertisingActive)

                kit.startAdvertising()
                assertEquals(FeatureState.Active, kit.advertisingState.value)
                assertEquals(2, transport.startAdvertisingCalls)
            } finally {
                withContext(NonCancellable) { retry.cancelAndJoin() }
            }
        }
    }

    @Test
    fun concurrentAdvertisingStartsCoalesceAndActiveStartIsIdempotent() = runBlocking {
        val transport = GatedDiscoveryTransport()
        withTestKit(
            create = { recorder ->
                createTestKit {
                    logger = recorder
                    appId = AppId("coalesced-advertising-test")
                    deviceName = "Test"
                    transports { register(GatedDiscoveryFactory(transport)) }
                }
            }
        ) { kit ->
            val firstStart = launch { kit.startAdvertising() }
            try {
                transport.advertisingEntered.await()
                assertEquals(FeatureState.Starting, kit.advertisingState.value)

                val secondStart = launch { kit.startAdvertising() }
                yield()
                assertEquals(1, transport.startAdvertisingCalls)

                transport.releaseAdvertising.complete(Unit)
                withTimeout(5_000) {
                    firstStart.join()
                    secondStart.join()
                }
                assertEquals(FeatureState.Active, kit.advertisingState.value)
                assertEquals(1, transport.startAdvertisingCalls)

                kit.startAdvertising()
                assertEquals(1, transport.startAdvertisingCalls)
            } finally {
                withContext(NonCancellable) {
                    transport.releaseAdvertising.complete(Unit)
                    firstStart.cancelAndJoin()
                }
            }
        }
    }

    @Test
    fun stopDuringAdvertisingStartWinsAndRollsBackLateResource() = runBlocking {
        val transport = GatedDiscoveryTransport()
        withTestKit(
            create = { recorder ->
                createTestKit {
                    logger = recorder
                    appId = AppId("stop-during-advertising-test")
                    deviceName = "Test"
                    transports { register(GatedDiscoveryFactory(transport)) }
                }
            }
        ) { kit ->
            val start = launch { kit.startAdvertising() }
            try {
                transport.advertisingEntered.await()
                assertEquals(FeatureState.Starting, kit.advertisingState.value)

                val stop = launch { kit.stopAdvertising() }
                withTimeout(5_000) {
                    kit.advertisingState.first { it == FeatureState.Stopping }
                }

                transport.releaseAdvertising.complete(Unit)
                withTimeout(5_000) {
                    start.join()
                    stop.join()
                }
                assertEquals(FeatureState.Idle, kit.advertisingState.value)
                assertEquals(1, transport.startAdvertisingCalls)
                assertEquals(1, transport.stopAdvertisingCalls)
            } finally {
                withContext(NonCancellable) {
                    transport.releaseAdvertising.complete(Unit)
                    start.cancelAndJoin()
                }
            }
        }
    }

    @Test
    fun explicitFeatureStopFailsBoundedlyWhenStartupOwnerDoesNotSettle() = runBlocking {
        val transport = GatedDiscoveryTransport()
        val laterTransport = RollbackDiscoveryTransport(TransportKind.BLE)
        withTestKit(
            create = { recorder ->
                createTestKit {
                    logger = recorder
                    appId = AppId("bounded-feature-stop-test")
                    deviceName = "Test"
                    featureOperationSettleTimeoutMillisForTest = 50
                    transports {
                        register(GatedDiscoveryFactory(transport))
                        register(RollbackDiscoveryFactory(laterTransport))
                    }
                }
            }
        ) { kit ->
            val start = async { runCatching { kit.startAdvertising() } }
            try {
                transport.advertisingEntered.await()

                val failure = assertFailsWith<P2pError.ConnectionFailed> {
                    withTimeout(2_000) { kit.stopAdvertising() }
                }
                val aggregate = assertIs<CleanupAggregateException>(failure.cause)
                assertTrue(
                    aggregate.issues.any {
                        it.deadlineExceeded && it.resource.contains("advertising startup")
                    }
                )
                assertEquals(1, transport.stopAdvertisingCalls)
                assertIs<FeatureState.Failed>(kit.advertisingState.value)

                transport.releaseAdvertising.complete(Unit)
                assertTrue(start.await().isFailure, "late startup must lose its invalidated token")
                assertEquals(2, transport.stopAdvertisingCalls, "late completion must roll itself back")
                assertEquals(
                    0,
                    laterTransport.startAdvertisingCalls,
                    "a stale startup owner must not enter a later transport"
                )
            } finally {
                transport.releaseAdvertising.complete(Unit)
                start.await()
            }
        }
    }

    @Test
    fun concurrentFeatureStopCallersJoinOneTeardown() = runBlocking {
        val transport = GatedDiscoveryTransport(blockAdvertisingStop = true)
        withTestKit(
            create = { recorder ->
                createTestKit {
                    logger = recorder
                    appId = AppId("concurrent-feature-stop-test")
                    deviceName = "Test"
                    featureOperationSettleTimeoutMillisForTest = 50
                    transports { register(GatedDiscoveryFactory(transport)) }
                }
            }
        ) { kit ->
            transport.releaseAdvertising.complete(Unit)
            kit.startAdvertising()

            val first = async { runCatching { kit.stopAdvertising() } }
            try {
                transport.stopAdvertisingEntered.await()
                val second = async { runCatching { kit.stopAdvertising() } }

                assertEquals(
                    null,
                    withTimeoutOrNull(100) { second.await() },
                    "a follower feature stop must join rather than start a timed duplicate cleanup"
                )
                assertEquals(1, transport.stopAdvertisingCalls)

                transport.releaseStopAdvertising.complete(Unit)
                assertTrue(first.await().isSuccess)
                assertTrue(second.await().isSuccess)
                assertEquals(1, transport.stopAdvertisingCalls)
                assertEquals(FeatureState.Idle, kit.advertisingState.value)
            } finally {
                transport.releaseStopAdvertising.complete(Unit)
                first.await()
            }
        }
    }

    @Test
    fun partialAdvertisingFailureRollsBackEveryAttemptedTransport() = runBlocking {
        val first = RollbackDiscoveryTransport(TransportKind.LAN)
        val failure = IllegalStateException("second advertising transport failed")
        val second = RollbackDiscoveryTransport(TransportKind.BLE).apply {
            advertisingFailure = failure
        }
        withTestKit(
            create = { recorder ->
                createTestKit {
                    logger = recorder
                    appId = AppId("advertising-rollback-test")
                    deviceName = "Test"
                    transports {
                        register(RollbackDiscoveryFactory(first))
                        register(RollbackDiscoveryFactory(second))
                    }
                }
            }
        ) { kit ->
            val thrown = assertFailsWith<P2pError.ConnectionFailed> {
                kit.startAdvertising()
            }
            assertTrue(thrown.message.orEmpty().contains(failure.message.orEmpty()))
            assertEquals(1, first.stopAdvertisingCalls)
            assertEquals(1, second.stopAdvertisingCalls)
            assertFalse(first.advertisingActive)
            assertFalse(second.advertisingActive)
        }
    }

    @Test
    fun cancelledDiscoveryRollsBackEveryAttemptedTransportAndPreservesCancellation() = runBlocking {
        val first = RollbackDiscoveryTransport(TransportKind.LAN)
        val second = RollbackDiscoveryTransport(TransportKind.BLE, gateDiscovery = true)
        withTestKit(
            create = { recorder ->
                createTestKit {
                    logger = recorder
                    appId = AppId("discovery-cancellation-rollback-test")
                    deviceName = "Test"
                    transports {
                        register(RollbackDiscoveryFactory(first))
                        register(RollbackDiscoveryFactory(second))
                    }
                }
            }
        ) { kit ->
            var thrown: Throwable? = null
            val operation = launch {
                try {
                    kit.startDiscovery()
                } catch (error: Throwable) {
                    thrown = error
                    throw error
                }
            }
            try {
                second.discoveryEntered.await()
                operation.cancelAndJoin()

                assertIs<CancellationException>(thrown)
                assertEquals(1, first.stopDiscoveryCalls)
                assertEquals(1, second.stopDiscoveryCalls)
                assertFalse(first.discoveryActive)
                assertFalse(second.discoveryActive)
                assertEquals(FeatureState.Idle, kit.discoveryState.value)
            } finally {
                withContext(NonCancellable) {
                    operation.cancelAndJoin()
                }
            }
        }
    }

    /**
     * AUDIT-2026-07 (ARCH-1), P1-08: cancelling `kit.start()` mid-bind is a
     * routine host-lifecycle event (e.g. an Android scope tearing down). The
     * CancellationException must propagate as-is — never wrapped into
     * [P2pError.TransportStartFailed] — the public state must NOT flip to
     * Failed, and a subsequent `start()` must succeed.
     */
    @Test
    fun cancellingStartMidBindPropagatesCancellationAndDoesNotLatchFailed() {
        runBlocking {
            val transport = HungStartTransport()
            withTestKit(
                create = { recorder ->
                    createTestKit {
                        logger = recorder
                        appId = AppId("cancel-start-test")
                        deviceName = "Test"
                        transports { register(HungStartFactory(transport)) }
                    }
                }
            ) { kit ->
                var thrown: Throwable? = null
                val starter = launch {
                    try {
                        kit.start()
                    } catch (e: Throwable) {
                        thrown = e
                        throw e
                    }
                }
                try {
                    transport.startEntered.await()
                    assertEquals(P2pState.Starting, kit.state.value)

                    starter.cancelAndJoin()

                    assertIs<CancellationException>(
                        thrown,
                        "cancelling start() must surface the CancellationException, got: $thrown"
                    )
                    assertFalse(
                        thrown is P2pError,
                        "cancellation must never be wrapped into a typed P2pError"
                    )
                    assertEquals(
                        P2pState.Idle, kit.state.value,
                        "a cancelled start must roll back to the retryable Idle state"
                    )
                    assertEquals(1, transport.stopCalls, "cancelled startup must release partial resources")

                    // The cancelled attempt must not have latched anything: the next
                    // start() re-runs the bind and succeeds.
                    transport.releaseStart.complete(Unit)
                    withTimeout(15_000) { kit.start() }
                    assertEquals(P2pState.Running, kit.state.value, "start() after a cancelled attempt must succeed")

                    kit.stop()
                } finally {
                    withContext(NonCancellable) {
                        transport.releaseStart.complete(Unit)
                        starter.cancelAndJoin()
                    }
                }
            }
        }
    }

    @Test
    fun dataTransportThatCancelsThenReturnsCannotPublishRunning() = runBlocking {
        val transport = CancelThenReturnDataTransport()
        withTestKit(
            create = { recorder ->
                createTestKit {
                    logger = recorder
                    appId = AppId("cancel-return-data-start-test")
                    deviceName = "Test"
                    transports { register(DataOnlyFactory(transport)) }
                }
            }
        ) { kit ->
            var thrown: Throwable? = null
            val starter = launch {
                try {
                    kit.start()
                } catch (failure: Throwable) {
                    thrown = failure
                    throw failure
                }
            }
            try {
                starter.join()

                assertIs<CancellationException>(thrown)
                assertEquals(P2pState.Idle, kit.state.value)
                assertEquals(1, transport.stopCalls)
                assertFalse(transport.active)

                kit.start()
                assertEquals(P2pState.Running, kit.state.value)
                assertEquals(2, transport.startCalls)
                assertTrue(transport.active)
            } finally {
                withContext(NonCancellable) {
                    starter.cancelAndJoin()
                }
            }
        }
    }

    @Test
    fun discoveryTransportThatCancelsThenReturnsCannotPublishActive() = runBlocking {
        val transport = CancelThenReturnDiscoveryTransport()
        withTestKit(
            create = { recorder ->
                createTestKit {
                    logger = recorder
                    appId = AppId("cancel-return-discovery-start-test")
                    deviceName = "Test"
                    transports { register(CancelThenReturnDiscoveryFactory(transport)) }
                }
            }
        ) { kit ->
            var thrown: Throwable? = null
            val starter = launch {
                try {
                    kit.startAdvertising()
                } catch (failure: Throwable) {
                    thrown = failure
                    throw failure
                }
            }
            try {
                starter.join()

                assertIs<CancellationException>(thrown)
                assertEquals(FeatureState.Idle, kit.advertisingState.value)
                assertEquals(1, transport.stopAdvertisingCalls)
                assertFalse(transport.advertisingActive)

                kit.startAdvertising()
                assertEquals(FeatureState.Active, kit.advertisingState.value)
                assertEquals(2, transport.startAdvertisingCalls)
                assertTrue(transport.advertisingActive)
            } finally {
                withContext(NonCancellable) {
                    starter.cancelAndJoin()
                }
            }
        }
    }

    @Test
    fun pathObserverThatCancelsThenReturnsCannotPublishRunning() = runBlocking {
        val transport = RestartableStartTrackingTransport()
        val observer = CancelThenReturnObserver()
        withTestKit(
            create = { recorder ->
                createTestKit {
                    logger = recorder
                    appId = AppId("cancel-return-observer-start-test")
                    deviceName = "Test"
                    lifecycle { networkPathObserver = observer }
                    transports { register(DataOnlyFactory(transport)) }
                }
            }
        ) { kit ->
            var thrown: Throwable? = null
            val starter = launch {
                try {
                    kit.start()
                } catch (failure: Throwable) {
                    thrown = failure
                    throw failure
                }
            }
            try {
                starter.join()

                assertIs<CancellationException>(thrown)
                assertEquals(P2pState.Idle, kit.state.value)
                assertEquals(1, observer.closeCalls)
                assertFalse(observer.active)
                assertEquals(1, transport.stopCalls)

                kit.start()
                assertEquals(P2pState.Running, kit.state.value)
                assertEquals(2, observer.startCalls)
                assertTrue(observer.active)
            } finally {
                withContext(NonCancellable) {
                    starter.cancelAndJoin()
                }
            }
        }
    }

    @Test
    fun cancellingStartDuringPathObserverAttachmentRollsBackWholeStartup() {
        runBlocking {
            val transport = RestartableStartTrackingTransport()
            val observer = FirstStartSuspendsObserver()
            withTestKit(
                create = { recorder ->
                    createTestKit {
                        logger = recorder
                        appId = AppId("cancel-observer-start-test")
                        deviceName = "Test"
                        lifecycle { networkPathObserver = observer }
                        transports { register(DataOnlyFactory(transport)) }
                    }
                }
            ) { kit ->
                var thrown: Throwable? = null
                val starter = launch {
                    try {
                        kit.start()
                    } catch (failure: Throwable) {
                        thrown = failure
                        throw failure
                    }
                }
                try {
                    observer.firstStartEntered.await()
                    assertEquals(P2pState.Starting, kit.state.value)

                    starter.cancelAndJoin()

                    assertIs<CancellationException>(thrown)
                    assertEquals(P2pState.Idle, kit.state.value)
                    assertEquals(1, transport.stopCalls)
                    assertEquals(1, observer.closeCalls)

                    kit.start()
                    assertEquals(P2pState.Running, kit.state.value)
                    assertEquals(2, transport.startCalls)
                    assertEquals(2, observer.startCalls)
                } finally {
                    withContext(NonCancellable) {
                        starter.cancelAndJoin()
                    }
                }
            }
        }
    }

    @Test
    fun ordinaryObserverStartFailureIsDetachedBeforeStartupDegradesCleanly() = runBlocking {
        val transport = RestartableStartTrackingTransport()
        val observer = FailingStartObserver()
        withTestKit(
            create = { recorder ->
                createTestKit {
                    logger = recorder
                    appId = AppId("failed-observer-cleanup-test")
                    deviceName = "Test"
                    lifecycle { networkPathObserver = observer }
                    transports { register(DataOnlyFactory(transport)) }
                }
            },
            verifyDiagnostics = { recorder ->
                assertLifecycleDiagnostics(recorder, listOf(lifecycleWarning(
                    "NetworkPathObserver.start() failed; path-change recovery disabled for this session",
                    observer.startFailure
                )))
            }
        ) { kit ->
            kit.start()

            assertEquals(P2pState.Running, kit.state.value)
            assertEquals(1, observer.startCalls)
            assertEquals(1, observer.closeCalls)
            assertFalse(observer.active, "a partially acquired observer must be detached")
            assertEquals(
                0,
                transport.stopCalls,
                "clean observer degradation must leave the successfully started data path running"
            )

            kit.start()
            assertEquals(1, observer.startCalls, "successful degraded startup remains idempotent")
            assertEquals(1, transport.startCalls)
        }
        assertEquals(2, observer.closeCalls, "terminal stop may close the observer idempotently")
    }

    @Test
    fun cancellationDuringOrdinaryObserverFailureCleanupSettlesWholeStartup() = runBlocking {
        val transport = RestartableStartTrackingTransport()
        val observer = FailingStartWithFirstCloseSuspendingObserver()
        withTestKit(
            create = { recorder ->
                createTestKit {
                    logger = recorder
                    appId = AppId("cancel-observer-failure-cleanup-test")
                    deviceName = "Test"
                    lifecycle { networkPathObserver = observer }
                    transports { register(DataOnlyFactory(transport)) }
                }
            },
            verifyDiagnostics = { recorder ->
                assertLifecycleDiagnostics(recorder, listOf(lifecycleWarning(
                    "NetworkPathObserver.start() failed; path-change recovery disabled for this session",
                    observer.startFailure
                )))
            }
        ) { kit ->
            var thrown: Throwable? = null
            val starter = launch {
                try {
                    kit.start()
                } catch (failure: Throwable) {
                    thrown = failure
                    throw failure
                }
            }
            try {
                observer.firstCloseEntered.await()

                starter.cancelAndJoin()

                assertIs<CancellationException>(thrown)
                assertEquals(
                    P2pState.Idle,
                    kit.state.value,
                    "cancellation during observer cleanup must not strand Starting"
                )
                assertEquals(1, transport.stopCalls, "the already-bound data path must roll back")
                assertEquals(2, observer.closeCalls, "the cancellation compensator must retry cleanup")
                assertFalse(observer.active, "the retry must settle partial observer ownership")

                kit.start()
                assertEquals(P2pState.Running, kit.state.value)
                assertEquals(2, transport.startCalls)
                assertEquals(2, observer.startCalls)
            } finally {
                withContext(NonCancellable) { starter.cancelAndJoin() }
            }
        }
    }

    @Test
    fun observerStartWithUnsettledCleanupRollsBackDataAndFailsClosed() = runBlocking {
        val transport = RestartableStartTrackingTransport()
        val observer = FailingStartObserver(failClose = true)
        withTestKit(
            create = { recorder ->
                createTestKit {
                    logger = recorder
                    appId = AppId("failed-observer-uncertain-cleanup-test")
                    deviceName = "Test"
                    lifecycle { networkPathObserver = observer }
                    transports { register(DataOnlyFactory(transport)) }
                }
            },
            verifyDiagnostics = { recorder ->
                assertLifecycleDiagnostics(recorder, listOf(
                    lifecycleWarning(
                        "NetworkPathObserver.start() failed; path-change recovery disabled for this session",
                        observer.startFailure
                    ),
                    lifecycleWarning(
                        "Late lifecycle cleanup failed for network path observer startup",
                        observer.closeFailure
                    )
                ))
            }
        ) { kit ->
            try {
                val failure = assertFailsWith<P2pError.ConnectionFailed> { kit.start() }

                assertEquals(
                    "failed network-path observer startup cleanup was incomplete; " +
                        "call stop() and replace this P2pKit instance",
                    failure.reason
                )
                assertSame(observer.startFailure, failure.suppressedExceptions.single())
                val aggregate = assertIs<CleanupAggregateException>(failure.cause)
                assertEquals("failed network-path observer startup", aggregate.operation)
                assertSame(observer.closeFailure, aggregate.issues.single().cause)
                val failedState = assertIs<P2pState.Failed>(kit.state.value)
                assertSame(failure, failedState.error)
                assertTrue(observer.active, "failed detach retains uncertain native ownership")
                assertEquals(1, observer.startCalls)
                assertEquals(1, observer.closeCalls)
                assertEquals(1, transport.startCalls)
                assertEquals(1, transport.stopCalls)

                val retryFailure = assertFailsWith<P2pError.ConnectionFailed> { kit.start() }
                assertSame(failure, retryFailure)
                assertEquals(1, observer.startCalls, "uncertain ownership must block observer reattachment")
                assertEquals(1, transport.startCalls, "uncertain ownership must block data rebinding")
            } finally {
                observer.failClose = false
            }
        }
        assertFalse(observer.active, "terminal stop must retry retained observer cleanup")
        assertEquals(2, observer.closeCalls)
    }

    @Test
    fun observerCancellationWithStartedDataKeepsNonTransportAttribution() = runBlocking {
        assertObserverCancellationAttribution(includeData = true)
    }

    @Test
    fun observerCancellationWithDiscoveryOnlyKitKeepsNonTransportAttribution() = runBlocking {
        assertObserverCancellationAttribution(includeData = false)
    }

    private suspend fun assertObserverCancellationAttribution(includeData: Boolean) {
        val cancellation = CancellationException("observer attachment cancelled after acquisition")
        val observer = FailingStartObserver(failClose = true, startFailure = cancellation)
        val data = if (includeData) RestartableStartTrackingTransport() else null
        val discovery = FakeDiscoveryTransport()
        val store = MemorySecureIdentityStorage()
        try {
            withTestKit(
                create = { recorder ->
                    P2pKit.create {
                        logger = recorder
                        appId = AppId("observer-cancellation-attribution-$includeData")
                        deviceName = "Test"
                        secureIdentityStorage = store
                        strictSessionInvariants = true
                        security { mode = SecurityMode.AuthenticatedV2(PeerAuthorizationPolicy.RejectUnknown) }
                        lifecycle { networkPathObserver = observer }
                        transports {
                            register(object : TransportFactory {
                                override val descriptor = if (includeData) {
                                    TransportDescriptor.dataAndDiscovery(TransportKind.LAN)
                                } else {
                                    TransportDescriptor.discoveryOnly(TransportKind.LAN)
                                }

                                override fun build(context: TransportContext): TransportPair =
                                    TransportPair(data = data, discovery = discovery)
                            })
                        }
                    }
                },
                verifyDiagnostics = { recorder ->
                    assertLifecycleDiagnostics(recorder, listOf(lifecycleWarning(
                        "Late lifecycle cleanup failed for network path observer startup",
                        observer.closeFailure
                    )))
                }
            ) { kit ->
                try {
                    val thrown = assertFailsWith<CancellationException> { kit.start() }
                    assertSame(cancellation, thrown, "caller cancellation must remain the primary throwable")
                    val blocker = assertIs<P2pError.ConnectionFailed>(thrown.suppressedExceptions.single())
                    assertSame(blocker, assertIs<P2pState.Failed>(kit.state.value).error)
                    assertTrue(
                        blocker.reason.startsWith("cancelled network-path observer startup cleanup was incomplete")
                    )
                    val aggregate = assertIs<CleanupAggregateException>(blocker.cause)
                    assertEquals("cancelled network-path observer startup", aggregate.operation)
                    assertSame(observer.closeFailure, aggregate.issues.single().cause)
                    assertTrue(
                        blocker.suppressedExceptions.isEmpty(),
                        "the blocker must not point back to cancellation"
                    )
                    assertTrue(observer.active)
                    data?.let {
                        assertEquals(1, it.startCalls)
                        assertEquals(1, it.stopCalls)
                    }

                    assertSame(blocker, assertFailsWith<P2pError.ConnectionFailed> { kit.start() })
                    assertEquals(1, observer.startCalls, "retry must not reattach the observer")
                    assertEquals(1, observer.closeCalls, "retry must not repeat uncertain cleanup")
                    data?.let { assertEquals(1, it.startCalls, "retry must not rebind a data listener") }
                } finally {
                    observer.failClose = false
                }
            }
        } finally {
            store.clear()
        }
        assertFalse(observer.active)
        assertEquals(2, observer.closeCalls, "terminal stop must attempt retained cleanup")
    }

    @Test
    fun cancellationWithUnsettledDataRollbackFailsClosedAgainstDoubleStart() = runBlocking {
        val transport = CancellationWithHangingRollbackTransport()
        var expectedWarnings = emptyList<RecordingLogger.Entry>()
        withTestKit(
            create = { recorder ->
                createTestKit {
                    logger = recorder
                    appId = AppId("cancel-hung-rollback-test")
                    deviceName = "Test"
                    transports { register(DataOnlyFactory(transport)) }
                }
            },
            verifyDiagnostics = { recorder -> assertLifecycleDiagnostics(recorder, expectedWarnings) }
        ) { kit ->
            try {
                var cancellation: Throwable? = null
                val starter = launch {
                    try {
                        kit.start()
                    } catch (failure: Throwable) {
                        cancellation = failure
                        throw failure
                    }
                }
                transport.startEntered.await()

                starter.cancelAndJoin()

                val cancelled = assertIs<CancellationException>(cancellation)
                assertTrue(
                    cancelled.suppressedExceptions.any { it is P2pError.TransportStartFailed },
                    "caller cancellation must retain the fail-closed rollback diagnosis"
                )
                val failedState = assertIs<P2pState.Failed>(kit.state.value)
                val blocker = assertIs<P2pError.TransportStartFailed>(failedState.error)
                assertEquals(TransportKind.LAN, blocker.transportKind)
                val aggregate = assertIs<CleanupAggregateException>(blocker.cause)
                assertEquals("cancelled data startup", aggregate.operation)
                expectedWarnings = listOf(lifecycleWarning(
                    "Late lifecycle cleanup failed for LAN data startup",
                    assertCleanupTimeout(aggregate.issues.single(), "LAN data startup", 2_000)
                ))
                assertTrue(blocker.reason.contains("cleanup was incomplete"))
                assertEquals(1, transport.startCalls)
                assertEquals(1, transport.stopCalls)

                val retryFailure = assertFailsWith<P2pError.TransportStartFailed> { kit.start() }
                assertSame(blocker, retryFailure)
                assertEquals(
                    1,
                    transport.startCalls,
                    "a cleanup-blocked instance must never attempt a second listener bind"
                )
            } finally {
                transport.releaseHangingStop()
            }
        }
    }

    /**
     * AUDIT-2026-07 (ARCH-2), P1-09: an observer whose `start()` hangs while
     * holding its internal mutex (the shipped Android/iOS observers serialize
     * start/close on one mutex) makes `close()` block on that same mutex.
     * `stop()` must still complete within its documented bounds — 5 s
     * startMutex fallback + 5 s observer-close bound — attempt the observer
     * close, and latch Stopped.
     */
    @Test
    fun stopRemainsBoundedWhenObserverStartHangsAndCloseBlocksOnSameMutex() {
        runBlocking {
            val transport = TrackingTransport()
            val observer = MutexHeldObserver()
            var expectedStopFailure: P2pError.ConnectionFailed? = null
            var expectedWarnings = emptyList<RecordingLogger.Entry>()
            // Preserve the deliberately cached failure; the scope must not hide a net failure in it.
            val repeatedStopFailure = assertFailsWith<P2pError.ConnectionFailed> {
                withTestKit(
                    create = { recorder ->
                        createTestKit {
                            logger = recorder
                            appId = AppId("bounded-stop-observer-test")
                            deviceName = "Test"
                            lifecycle { networkPathObserver = observer }
                            transports { register(TrackingFactory(transport)) }
                        }
                    },
                    verifyDiagnostics = { recorder -> assertLifecycleDiagnostics(recorder, expectedWarnings) }
                ) { kit ->
                    // Park ensureStarted inside observer.start() with the observer's
                    // internal mutex held (the kit's startMutex is held too).
                    val starter = launch { kit.start() }
                    try {
                        observer.startEntered.await()

                        // Pre-fix, stop() parked forever inside pathObserver.close() on
                        // the observer's mutex; this outer bound (3x the two 5 s internal
                        // bounds) fired. Post-fix stop() is bounded.
                        val stopFailure = assertFailsWith<P2pError.ConnectionFailed> {
                            withTimeout(30_000) { kit.stop() }
                        }
                        expectedStopFailure = stopFailure
                        expectedWarnings = startupStopDiagnostics(stopFailure, observerTimeout = true)
                        assertEquals(P2pState.Stopped, kit.state.value)
                        assertTrue(transport.dataClosed, "teardown must still close the data transport")
                        assertTrue(observer.closeAttempted, "stop() must still attempt the observer close")
                        assertFalse(
                            observer.closeCompleted,
                            "close() cannot complete while the hung start() holds the observer's mutex"
                        )

                        // Cleanup: cancel the parked starter. The CancellationException
                        // must propagate out of kit.start() (AUDIT-2026-07 (ARCH-1)
                        // observer-start site) rather than latching state over Stopped.
                        starter.cancelAndJoin()
                        assertEquals(
                            P2pState.Stopped, kit.state.value,
                            "the cancelled late start must not overwrite Stopped"
                        )
                    } finally {
                        withContext(NonCancellable) {
                            observer.releaseStart.complete(Unit)
                            starter.cancelAndJoin()
                        }
                    }
                }
            }
            assertSame(expectedStopFailure, repeatedStopFailure)
            assertTrue(
                repeatedStopFailure.suppressedExceptions.isEmpty(),
                "expected cached stop failure must not conceal teardown/net failures"
            )
        }
    }

    /**
     * AUDIT-2026-07 (ARCH-2), P1-09: a `stop()` caller cancelled mid-teardown
     * must still complete the whole teardown — including the observer close,
     * whose first suspension point previously aborted it (the platform
     * monitor leaked and Stopped was never latched by that call).
     */
    @Test
    fun cancelledStopCallerStillClosesObserverAndLatchesStopped() {
        runBlocking {
            val transport = GatedCloseTransport()
            val observer = YieldingCloseObserver()
            withTestKit(
                create = { recorder ->
                    createTestKit {
                        logger = recorder
                        appId = AppId("cancelled-stop-test")
                        deviceName = "Test"
                        lifecycle { networkPathObserver = observer }
                        transports { register(GatedCloseFactory(transport)) }
                    }
                }
            ) { kit ->
                kit.start()
                assertEquals(P2pState.Running, kit.state.value)

                val stopper = launch { kit.stop() }
                try {
                    transport.closeEntered.await()
                    // Cancel the stopping caller while teardown is deterministically
                    // mid-flight, then let the parked transport close proceed.
                    stopper.cancel()
                    transport.releaseClose.complete(Unit)
                    withTimeout(15_000) { stopper.join() }

                    assertTrue(
                        observer.closeCompleted,
                        "a cancelled stop() caller must still run the observer close to completion"
                    )
                    assertTrue(transport.dataClosed, "teardown must still close the data transport")
                    assertEquals(
                        P2pState.Stopped, kit.state.value,
                        "a cancelled stop() caller must still latch Stopped"
                    )
                } finally {
                    withContext(NonCancellable) {
                        transport.releaseClose.complete(Unit)
                        stopper.cancelAndJoin()
                    }
                }
            }
        }
    }

    @Test
    fun lateAdvertisingCompletionIsRolledBackAfterStop() = runBlocking {
        val transport = GatedDiscoveryTransport()
        withTestKit(
            create = { recorder ->
                createTestKit {
                    logger = recorder
                    appId = AppId("late-advertising-test")
                    deviceName = "Test"
                    transports { register(GatedDiscoveryFactory(transport)) }
                }
            }
        ) { kit ->
            kit.start()

            var failure: Throwable? = null
            val advertiser = launch {
                try {
                    kit.startAdvertising()
                } catch (e: Throwable) {
                    failure = e
                }
            }
            try {
                transport.advertisingEntered.await()

                kit.stop()
                assertEquals(P2pState.Stopped, kit.state.value)
                transport.releaseAdvertising.complete(Unit)
                withTimeout(5_000) { advertiser.join() }

                assertIs<IllegalStateException>(failure)
                assertEquals(
                    2,
                    transport.stopAdvertisingCalls,
                    "stop must close the in-flight resource and its late completion must compensate again"
                )
                assertEquals(P2pState.Stopped, kit.state.value)
            } finally {
                withContext(NonCancellable) {
                    transport.releaseAdvertising.complete(Unit)
                    advertiser.cancelAndJoin()
                }
            }
        }
    }

    @Test
    fun lateDiscoveryCompletionIsRolledBackAfterStop() = runBlocking {
        val transport = GatedDiscoveryTransport()
        withTestKit(
            create = { recorder ->
                createTestKit {
                    logger = recorder
                    appId = AppId("late-discovery-test")
                    deviceName = "Test"
                    transports { register(GatedDiscoveryFactory(transport)) }
                }
            }
        ) { kit ->
            kit.start()

            var failure: Throwable? = null
            val discoverer = launch {
                try {
                    kit.startDiscovery()
                } catch (e: Throwable) {
                    failure = e
                }
            }
            try {
                transport.discoveryEntered.await()

                kit.stop()
                assertEquals(P2pState.Stopped, kit.state.value)
                transport.releaseDiscovery.complete(Unit)
                withTimeout(5_000) { discoverer.join() }

                assertIs<IllegalStateException>(failure)
                assertEquals(2, transport.stopDiscoveryCalls)
                assertEquals(P2pState.Stopped, kit.state.value)
            } finally {
                withContext(NonCancellable) {
                    transport.releaseDiscovery.complete(Unit)
                    discoverer.cancelAndJoin()
                }
            }
        }
    }

    @Test
    fun observerThatReturnsAfterStopCannotResurrectKit() = runBlocking {
        val transport = TrackingTransport()
        val observer = LateReturningObserver()
        var expectedStopFailure: P2pError.ConnectionFailed? = null
        var expectedWarnings = emptyList<RecordingLogger.Entry>()
        // Preserve the deliberately cached failure; the scope must not hide a net failure in it.
        val repeatedStopFailure = assertFailsWith<P2pError.ConnectionFailed> {
            withTestKit(
                create = { recorder ->
                    createTestKit {
                        logger = recorder
                        appId = AppId("late-observer-test")
                        deviceName = "Test"
                        lifecycle { networkPathObserver = observer }
                        transports { register(TrackingFactory(transport)) }
                    }
                },
                verifyDiagnostics = { recorder -> assertLifecycleDiagnostics(recorder, expectedWarnings) }
            ) { kit ->
                var failure: Throwable? = null
                val starter = launch {
                    try {
                        kit.start()
                    } catch (e: Throwable) {
                        failure = e
                    }
                }
                try {
                    observer.startEntered.await()

                    val stopFailure = assertFailsWith<P2pError.ConnectionFailed> {
                        withTimeout(15_000) { kit.stop() }
                    }
                    expectedStopFailure = stopFailure
                    expectedWarnings = startupStopDiagnostics(stopFailure, observerTimeout = false)
                    assertEquals(P2pState.Stopped, kit.state.value)
                    observer.releaseStart.complete(Unit)
                    withTimeout(5_000) { starter.join() }

                    assertIs<IllegalStateException>(failure)
                    assertEquals(
                        2,
                        observer.closeCalls,
                        "terminal teardown and the late-start compensation must both close idempotently"
                    )
                    assertEquals(P2pState.Stopped, kit.state.value)
                } finally {
                    withContext(NonCancellable) {
                        observer.releaseStart.complete(Unit)
                        starter.cancelAndJoin()
                    }
                }
            }
        }
        assertSame(expectedStopFailure, repeatedStopFailure)
        assertTrue(
            repeatedStopFailure.suppressedExceptions.isEmpty(),
            "expected cached stop failure must not conceal teardown/net failures"
        )
    }

    @Test
    fun outgoingConnectThatReturnsAfterStopCannotPublishSession() = runBlocking {
        val pair = FakeConnectionPair()
        val aliceTransport = GatedConnectTransport(pair.a)
        val bobTransport = FakeDataTransport(preStagedIncoming = listOf(pair.b))
        withTestKit(
            create = { recorder ->
                createTestKit {
                    logger = recorder
                    appId = AppId("late-connect-test")
                    deviceName = "Alice"
                    peerIdStorage = InMemoryPeerIdStorage(seed = PeerId("alice-id"))
                    transports { register(GatedConnectFactory(aliceTransport)) }
                }
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    createTestKit {
                        logger = recorder
                        appId = AppId("late-connect-test")
                        deviceName = "Bob"
                        peerIdStorage = InMemoryPeerIdStorage(seed = PeerId("bob-id"))
                        transports { register(DataOnlyFactory(bobTransport)) }
                    }
                },
                verifyDiagnostics = ::assertPreHelloDialAborted
            ) { bob ->
                try {
                    alice.start()
                    bob.start()
                    val target = Peer(
                        id = PeerId("bob-id"),
                        name = "Bob",
                        platform = Platform.JVM_DESKTOP,
                        supportedTransports = setOf(TransportKind.LAN)
                    )
                    var failure: Throwable? = null
                    val connector = launch {
                        try {
                            alice.connect(target)
                        } catch (e: Throwable) {
                            failure = e
                        }
                    }
                    aliceTransport.connectEntered.await()

                    alice.stop()
                    aliceTransport.releaseConnect.complete(Unit)
                    withTimeout(5_000) { connector.join() }

                    assertIs<IllegalStateException>(failure, "connect must fail with the terminal lifecycle error")
                    assertEquals(
                        ConnectionState.Closed,
                        pair.a.state.value,
                        "the raw connection created after stop must be closed before protocol setup"
                    )
                    assertTrue(alice.sessions.value.isEmpty(), "a late connection must never enter public sessions")
                    assertEquals(P2pState.Stopped, alice.state.value)
                } finally {
                    aliceTransport.releaseConnect.complete(Unit)
                }
            }
        }
    }

    @Test
    fun sessionCommittedBeforeStopIsIncludedInTeardown() = runBlocking {
        val pair = FakeConnectionPair()
        val watcherEntered = CompletableDeferred<Unit>()
        val releaseWatcher = CompletableDeferred<Unit>()
        val aliceTransport = FakeDataTransport(outgoingConnection = { pair.a })
        val bobTransport = FakeDataTransport(preStagedIncoming = listOf(pair.b))
        withTestKit(
            create = { recorder ->
                createTestKit {
                    logger = recorder
                    appId = AppId("committed-session-stop-test")
                    deviceName = "Alice"
                    peerIdStorage = InMemoryPeerIdStorage(seed = PeerId("alice-id"))
                    beforeTerminalWatcherRemovalForTest = {
                        watcherEntered.complete(Unit)
                        releaseWatcher.await()
                    }
                    transports { register(DataOnlyFactory(aliceTransport)) }
                }
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    createTestKit {
                        logger = recorder
                        appId = AppId("committed-session-stop-test")
                        deviceName = "Bob"
                        peerIdStorage = InMemoryPeerIdStorage(seed = PeerId("bob-id"))
                        transports { register(DataOnlyFactory(bobTransport)) }
                    }
                }
            ) { bob ->
                try {
                    val session = withTimeout(5_000) {
                        alice.connect(
                            Peer(
                                id = PeerId("bob-id"),
                                name = "Bob",
                                platform = Platform.JVM_DESKTOP,
                                supportedTransports = setOf(TransportKind.LAN)
                            )
                        )
                    }
                    assertEquals(ConnectionState.Connected, session.state.value)

                    session.close()
                    watcherEntered.await()
                    assertEquals(
                        listOf(session),
                        alice.sessions.value,
                        "the parked watcher must leave the terminal entry published before stop"
                    )

                    alice.stop()

                    assertEquals(
                        ConnectionState.Closed,
                        session.state.value,
                        "a registration committed before the terminal gate must be in stop's snapshot"
                    )
                    assertTrue(
                        alice.sessions.value.isEmpty(),
                        "stop must atomically empty public sessions before its watcher scope is cancelled"
                    )
                    assertEquals(P2pState.Stopped, alice.state.value)
                } finally {
                    releaseWatcher.complete(Unit)
                }
            }
        }
    }

    @Test
    fun concurrentStopCallersJoinOneTeardown() = runBlocking {
        val transport = GatedCloseTransport()
        withTestKit(
            create = { recorder ->
                createTestKit {
                    logger = recorder
                    appId = AppId("concurrent-stop-test")
                    deviceName = "Test"
                    transports { register(GatedCloseFactory(transport)) }
                }
            }
        ) { kit ->
            kit.start()

            val first = launch { kit.stop() }
            try {
                transport.closeEntered.await()
                val second = launch { kit.stop() }
                yield()
                assertFalse(second.isCompleted, "a follower stop must wait for the leader's teardown")

                transport.releaseClose.complete(Unit)
                withTimeout(5_000) {
                    first.join()
                    second.join()
                }
                assertEquals(1, transport.closeCalls)
                assertEquals(P2pState.Stopped, kit.state.value)
            } finally {
                withContext(NonCancellable) {
                    transport.releaseClose.complete(Unit)
                    first.cancelAndJoin()
                }
            }
        }
    }

    @Test
    fun terminalCleanupIsBoundedAttemptsEveryResourceAndSharesTheFailure() = runBlocking {
        val throwing = CleanupProbeTransport(TransportKind.LAN, CleanupBehavior.THROW)
        val hanging = CleanupProbeTransport(TransportKind.BLE, CleanupBehavior.HANG)
        val healthy = CleanupProbeTransport(TransportKind.RELAY, CleanupBehavior.SUCCEED)
        var expectedStopFailure: P2pError.ConnectionFailed? = null
        var expectedWarnings = emptyList<RecordingLogger.Entry>()
        // Preserve the deliberately cached failure; the scope must not hide a net failure in it.
        val repeatedStopFailure = assertFailsWith<P2pError.ConnectionFailed> {
            withTestKit(
                create = { recorder ->
                    createTestKit {
                        logger = recorder
                        appId = AppId("bounded-cleanup-test")
                        deviceName = "Test"
                        transports {
                            register(CleanupProbeFactory(throwing))
                            register(CleanupProbeFactory(hanging))
                            register(CleanupProbeFactory(healthy))
                        }
                    }
                },
                verifyDiagnostics = { recorder -> assertLifecycleDiagnostics(recorder, expectedWarnings) }
            ) { kit ->
                try {
                    kit.start()

                    val first = assertFailsWith<P2pError.ConnectionFailed> {
                        withTimeout(10_000) { kit.stop() }
                    }
                    expectedStopFailure = first
                    expectedWarnings = terminalResourceStopDiagnostics(first)
                    assertEquals(1, throwing.closeCalls)
                    assertEquals(1, hanging.closeCalls)
                    assertEquals(1, healthy.closeCalls)
                    assertTrue(healthy.closed, "a failed or hung sibling must not prevent later cleanup")
                    assertEquals(P2pState.Stopped, kit.state.value)

                    val aggregate = assertIs<CleanupAggregateException>(first.cause)
                    assertEquals(2, aggregate.issues.size)
                    assertTrue(aggregate.issues.any { it.resource.contains("LAN") })
                    assertTrue(aggregate.issues.any { it.resource.contains("BLE") })
                    hanging.releaseHangingClose()

                    val follower = assertFailsWith<P2pError.ConnectionFailed> { kit.stop() }
                    assertSame(first, follower, "all stop callers must observe the leader's exact result")
                } finally {
                    hanging.releaseHangingClose()
                }
            }
        }
        assertSame(expectedStopFailure, repeatedStopFailure)
        assertTrue(
            repeatedStopFailure.suppressedExceptions.isEmpty(),
            "expected cached stop failure must not conceal teardown/net failures"
        )
    }

    private fun lifecycleWarning(message: String, cause: Throwable? = null) =
        RecordingLogger.Entry(RecordingLogger.Level.WARN, message, cause)

    private fun assertLifecycleDiagnostics(recorder: RecordingLogger, expected: List<RecordingLogger.Entry>) {
        val actual = recorder.entries.filter {
            it.level == RecordingLogger.Level.WARN || it.level == RecordingLogger.Level.ERROR
        }
        assertEquals(expected, actual, "only the controlled lifecycle fault may be diagnosed")
    }

    private fun startupStopDiagnostics(
        failure: P2pError.ConnectionFailed,
        observerTimeout: Boolean
    ): List<RecordingLogger.Entry> {
        val aggregate = assertIs<CleanupAggregateException>(failure.cause)
        assertEquals("stop", aggregate.operation)
        val resources = buildList {
            add("transport startup transaction")
            if (observerTimeout) add("network path observer")
        }
        assertEquals(resources, aggregate.issues.map { it.resource })
        val startup = aggregate.issues.first()
        assertFalse(startup.deadlineExceeded)
        val startupFailure = assertIs<IllegalStateException>(startup.cause)
        assertEquals("start mutex was not released within 5000ms", startupFailure.message)
        assertTrue(startupFailure.suppressedExceptions.isEmpty())
        return buildList {
            add(lifecycleWarning(
                "stop(): startMutex not released within 5000ms " +
                    "(a transport start() is likely hung); tearing down without the lock"
            ))
            add(lifecycleWarning("stop failed for transport startup transaction", startupFailure))
            if (observerTimeout) {
                add(lifecycleWarning(
                    "stop failed for network path observer",
                    assertCleanupTimeout(aggregate.issues[1], "network path observer", 5_000)
                ))
            }
        }
    }

    private fun terminalResourceStopDiagnostics(failure: P2pError.ConnectionFailed): List<RecordingLogger.Entry> {
        val aggregate = assertIs<CleanupAggregateException>(failure.cause)
        assertEquals("stop", aggregate.operation)
        assertEquals(listOf("LAN data transport", "BLE data transport"), aggregate.issues.map { it.resource })
        val refused = aggregate.issues.first()
        assertFalse(refused.deadlineExceeded)
        val refusal = assertIs<IllegalStateException>(refused.cause)
        assertEquals("close failed for LAN", refusal.message)
        assertTrue(refusal.suppressedExceptions.isEmpty())
        return listOf(
            lifecycleWarning("stop failed for LAN data transport", refusal),
            lifecycleWarning(
                "stop failed for BLE data transport",
                assertCleanupTimeout(aggregate.issues[1], "BLE data transport", 6_000)
            )
        )
    }

    private fun assertCleanupTimeout(issue: CleanupIssue, resource: String, millis: Long): Throwable {
        assertEquals(resource, issue.resource)
        assertTrue(issue.deadlineExceeded)
        val failure = assertIs<IllegalStateException>(issue.cause)
        assertEquals("cleanup exceeded ${millis}ms", failure.message)
        val deadline = assertIs<OwnedOperationTimeoutException>(failure.cause)
        assertEquals("Operation timed out after $millis ms", deadline.message)
        assertTrue(failure.suppressedExceptions.isEmpty())
        assertTrue(deadline.suppressedExceptions.isEmpty())
        return failure
    }

    private fun assertPreHelloDialAborted(recorder: RecordingLogger) {
        val diagnostics = recorder.entries.filter {
            it.level == RecordingLogger.Level.WARN || it.level == RecordingLogger.Level.ERROR
        }
        assertTrue(diagnostics.size <= 1, "only one controlled pre-HELLO dial was abandoned")
        diagnostics.forEach { entry ->
            assertEquals(RecordingLogger.Level.WARN, entry.level)
            assertEquals("Incoming session setup failed", entry.message)
            val failure = assertIs<P2pError.ConnectionFailed>(entry.throwable)
            val eof = assertIs<ClosedReceiveChannelException>(failure.cause)
            assertEquals("Plaintext HELLO failed: ${eof.message}", failure.reason)
            assertTrue(failure.suppressedExceptions.isEmpty())
            assertTrue(eof.suppressedExceptions.isEmpty())
        }
    }

    @Test
    fun explicitFeatureStopAttemptsEveryTransportAndReportsFailures() = runBlocking {
        val stopFailure = IllegalStateException("cannot unregister")
        val failing = RollbackDiscoveryTransport(TransportKind.LAN).apply {
            stopAdvertisingFailure = stopFailure
        }
        val healthy = RollbackDiscoveryTransport(TransportKind.BLE)
        withTestKit(
            create = { recorder ->
                createTestKit {
                    logger = recorder
                    appId = AppId("feature-stop-cleanup-test")
                    deviceName = "Test"
                    transports {
                        register(RollbackDiscoveryFactory(failing))
                        register(RollbackDiscoveryFactory(healthy))
                    }
                }
            },
            verifyDiagnostics = { recorder ->
                assertLifecycleDiagnostics(recorder, listOf(lifecycleWarning(
                    "stop advertising failed for LAN discovery transport",
                    stopFailure
                )))
            }
        ) { kit ->
            try {
                kit.startAdvertising()
                val failure = assertFailsWith<P2pError.ConnectionFailed> {
                    kit.stopAdvertising()
                }
                assertIs<CleanupAggregateException>(failure.cause)
                assertEquals(1, failing.stopAdvertisingCalls)
                assertEquals(1, healthy.stopAdvertisingCalls)
                assertFalse(healthy.advertisingActive)
                assertIs<FeatureState.Failed>(kit.advertisingState.value)
                assertEquals(FeatureState.Idle, kit.discoveryState.value)
                assertEquals(P2pState.Running, kit.state.value)

                failing.stopAdvertisingFailure = null
                kit.startAdvertising()
                assertEquals(2, failing.stopAdvertisingCalls)
                assertEquals(2, healthy.stopAdvertisingCalls)
                assertTrue(failing.advertisingActive)
                assertTrue(healthy.advertisingActive)
                assertEquals(FeatureState.Active, kit.advertisingState.value)
            } finally {
                failing.stopAdvertisingFailure = null
            }
        }
    }
}

/**
 * Single transport that implements both [DataTransport] and [DiscoveryTransport]
 * and records every lifecycle call as a `Boolean` so the test can assert on it.
 */
private class TrackingTransport : DataTransport, DiscoveryTransport {

    override val type: TransportKind = TransportKind.LAN
    override val priority: Int = 100

    @Volatile var dataClosed: Boolean = false
    @Volatile var advertisingStarted: Boolean = false
    @Volatile var advertisingStopped: Boolean = false
    @Volatile var discoveryStarted: Boolean = false
    @Volatile var discoveryStopped: Boolean = false

    /** While non-null, [startAdvertising] throws it (P1-07 re-advertise leg). */
    @Volatile var advertiseFailure: Throwable? = null

    private val incomingChannel = Channel<RawConnection>(Channel.UNLIMITED)
    private val eventsFlow = MutableSharedFlow<PeerEvent>(extraBufferCapacity = 16)

    override fun canConnect(peer: InternalPeer): Boolean = false
    override suspend fun connect(peer: InternalPeer): RawConnection =
        error("TrackingTransport does not produce outgoing connections")

    override fun incomingConnections(): Flow<RawConnection> = incomingChannel.receiveAsFlow()

    override suspend fun stop() = Unit

    override suspend fun close() {
        dataClosed = true
        incomingChannel.close()
    }

    override val events: Flow<PeerEvent> = eventsFlow.asSharedFlow()

    suspend fun emitPeer(event: PeerEvent) {
        eventsFlow.emit(event)
    }

    suspend fun awaitPeerCollector() {
        eventsFlow.subscriptionCount.first { it > 0 }
    }

    override suspend fun startAdvertising(localPeer: LocalPeerInfo) {
        advertiseFailure?.let { throw it }
        advertisingStarted = true
    }

    override suspend fun stopAdvertising() {
        advertisingStopped = true
    }

    override suspend fun startDiscovery() {
        discoveryStarted = true
    }

    override suspend fun stopDiscovery() {
        discoveryStopped = true
    }
}

private class StartupProbeTransport(
    override val type: TransportKind,
    private val label: String,
    private val calls: MutableList<String>
) : DataTransport {
    override val priority: Int = 100
    @Volatile var active: Boolean = false
    @Volatile var closed: Boolean = false
    @Volatile var startFailure: Throwable? = null
    @Volatile var stopFailure: Throwable? = null

    override suspend fun start(): Result<Unit> {
        check(!closed)
        calls += "start:$label"
        active = true
        val failure = startFailure
        return if (failure == null) Result.success(Unit) else Result.failure(failure)
    }

    override suspend fun stop() {
        calls += "stop:$label"
        stopFailure?.let { throw it }
        active = false
    }

    override fun canConnect(peer: InternalPeer): Boolean = false
    override suspend fun connect(peer: InternalPeer): RawConnection = error("not supported")
    // A startup/rollback probe leaves acceptance idle; it does not model an ended listener.
    override fun incomingConnections(): Flow<RawConnection> = flow { awaitCancellation() }

    override suspend fun close() {
        active = false
        closed = true
    }
}

private class TrackingFactory(private val transport: TrackingTransport) : TransportFactory {
    override val descriptor =
        dev.p2pkit.core.transport.TransportDescriptor.dataAndDiscovery(transport.type)
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = transport)
}

private class RollbackDiscoveryFactory(
    private val transport: RollbackDiscoveryTransport
) : TransportFactory {
    override val descriptor =
        dev.p2pkit.core.transport.TransportDescriptor.dataAndDiscovery(transport.type)
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = transport)
}

private class RetryCleanupCancellationFactory(
    private val transport: RetryCleanupCancellationTransport
) : TransportFactory {
    override val descriptor =
        dev.p2pkit.core.transport.TransportDescriptor.dataAndDiscovery(transport.type)
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = transport)
}

/**
 * Leaves cleanup-required state on the first advertising failure, then parks
 * the retry's preparatory cleanup so cancellation can hit that exact window.
 */
private class RetryCleanupCancellationTransport : DataTransport, DiscoveryTransport {
    override val type: TransportKind = TransportKind.LAN
    override val priority: Int = 100
    private val incoming = Channel<RawConnection>(Channel.UNLIMITED)
    private val peerEvents = MutableSharedFlow<PeerEvent>(extraBufferCapacity = 1)
    val retryCleanupEntered = CompletableDeferred<Unit>()
    val firstRollbackFailure = IllegalStateException("first advertising rollback failed")

    @Volatile var advertisingActive: Boolean = false
    @Volatile var startAdvertisingCalls: Int = 0
    @Volatile var stopAdvertisingCalls: Int = 0

    override fun canConnect(peer: InternalPeer): Boolean = false
    override suspend fun connect(peer: InternalPeer): RawConnection = error("not supported")
    override fun incomingConnections(): Flow<RawConnection> = incoming.receiveAsFlow()
    override suspend fun stop() = Unit
    override suspend fun close() { incoming.close() }
    override val events: Flow<PeerEvent> = peerEvents.asSharedFlow()

    override suspend fun startAdvertising(localPeer: LocalPeerInfo) {
        startAdvertisingCalls += 1
        advertisingActive = true
        if (startAdvertisingCalls == 1) {
            throw IllegalStateException("first advertising registration failed")
        }
    }

    override suspend fun stopAdvertising() {
        stopAdvertisingCalls += 1
        when (stopAdvertisingCalls) {
            1 -> throw firstRollbackFailure
            2 -> {
                retryCleanupEntered.complete(Unit)
                CompletableDeferred<Unit>().await()
            }
        }
        advertisingActive = false
    }

    override suspend fun startDiscovery() = Unit
    override suspend fun stopDiscovery() = Unit
}

private class RollbackDiscoveryTransport(
    override val type: TransportKind,
    private val gateDiscovery: Boolean = false
) : DataTransport, DiscoveryTransport {
    override val priority: Int = 100
    private val incoming = Channel<RawConnection>(Channel.UNLIMITED)
    private val peerEvents = MutableSharedFlow<PeerEvent>(extraBufferCapacity = 1)
    val discoveryEntered = CompletableDeferred<Unit>()
    private val releaseDiscovery = CompletableDeferred<Unit>()

    @Volatile var advertisingFailure: Throwable? = null
    @Volatile var stopAdvertisingFailure: Throwable? = null
    @Volatile var advertisingActive: Boolean = false
    @Volatile var discoveryActive: Boolean = false
    @Volatile var startAdvertisingCalls: Int = 0
    @Volatile var stopAdvertisingCalls: Int = 0
    @Volatile var stopDiscoveryCalls: Int = 0

    override fun canConnect(peer: InternalPeer): Boolean = false
    override suspend fun connect(peer: InternalPeer): RawConnection = error("not supported")
    override fun incomingConnections(): Flow<RawConnection> = incoming.receiveAsFlow()
    override suspend fun stop() = Unit
    override suspend fun close() { incoming.close() }
    override val events: Flow<PeerEvent> = peerEvents.asSharedFlow()

    override suspend fun startAdvertising(localPeer: LocalPeerInfo) {
        startAdvertisingCalls += 1
        advertisingActive = true
        advertisingFailure?.let { throw it }
    }

    override suspend fun stopAdvertising() {
        stopAdvertisingCalls += 1
        stopAdvertisingFailure?.let { throw it }
        advertisingActive = false
    }

    override suspend fun startDiscovery() {
        discoveryActive = true
        if (gateDiscovery) {
            discoveryEntered.complete(Unit)
            releaseDiscovery.await()
        }
    }

    override suspend fun stopDiscovery() {
        stopDiscoveryCalls += 1
        discoveryActive = false
    }
}

/**
 * [DataTransport] whose `start()` parks until the test releases it, so a test
 * can hold `ensureStarted` (and the kit's start mutex) hung at will.
 */
private class HungStartTransport : DataTransport {

    override val type: TransportKind = TransportKind.LAN
    override val priority: Int = 100

    @Volatile var dataClosed: Boolean = false
    @Volatile var stopCalls: Int = 0

    /** Completed by [start] the moment it is entered (the mutex is now held hung). */
    val startEntered = CompletableDeferred<Unit>()

    /** Completed by the test to let the hung [start] return. */
    val releaseStart = CompletableDeferred<Unit>()

    private val incomingChannel = Channel<RawConnection>(Channel.UNLIMITED)

    override suspend fun start(): Result<Unit> {
        startEntered.complete(Unit)
        releaseStart.await()
        return Result.success(Unit)
    }

    override fun canConnect(peer: InternalPeer): Boolean = false
    override suspend fun connect(peer: InternalPeer): RawConnection =
        error("HungStartTransport does not produce outgoing connections")

    override fun incomingConnections(): Flow<RawConnection> = incomingChannel.receiveAsFlow()

    override suspend fun stop() {
        stopCalls += 1
        dataClosed = false
    }

    override suspend fun close() {
        dataClosed = true
        incomingChannel.close()
    }
}

private class HungStartFactory(private val transport: HungStartTransport) : TransportFactory {
    override val descriptor =
        dev.p2pkit.core.transport.TransportDescriptor.dataOnly(transport.type)
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = null)
}

private class RestartableStartTrackingTransport : DataTransport {
    override val type: TransportKind = TransportKind.LAN
    override val priority: Int = 100
    @Volatile var startCalls: Int = 0
    @Volatile var stopCalls: Int = 0
    private val incoming = Channel<RawConnection>(Channel.UNLIMITED)

    override suspend fun start(): Result<Unit> {
        startCalls += 1
        return Result.success(Unit)
    }

    override suspend fun stop() {
        stopCalls += 1
    }

    override fun canConnect(peer: InternalPeer): Boolean = false
    override suspend fun connect(peer: InternalPeer): RawConnection = error("not supported")
    override fun incomingConnections(): Flow<RawConnection> = incoming.receiveAsFlow()
    override suspend fun close() {
        incoming.close()
    }
}

private class CancelThenReturnDataTransport : DataTransport {
    override val type: TransportKind = TransportKind.LAN
    override val priority: Int = 100
    private val incoming = Channel<RawConnection>(Channel.UNLIMITED)

    @Volatile var startCalls: Int = 0
    @Volatile var stopCalls: Int = 0
    @Volatile var active: Boolean = false

    override suspend fun start(): Result<Unit> {
        startCalls += 1
        active = true
        if (startCalls == 1) {
            currentCoroutineContext().cancel(CancellationException("cancel after data acquisition"))
        }
        return Result.success(Unit)
    }

    override suspend fun stop() {
        stopCalls += 1
        active = false
    }

    override fun canConnect(peer: InternalPeer): Boolean = false
    override suspend fun connect(peer: InternalPeer): RawConnection = error("not supported")
    override fun incomingConnections(): Flow<RawConnection> = incoming.receiveAsFlow()
    override suspend fun close() {
        active = false
        incoming.close()
    }
}

private class CancelThenReturnDiscoveryFactory(
    private val transport: CancelThenReturnDiscoveryTransport
) : TransportFactory {
    override val descriptor =
        dev.p2pkit.core.transport.TransportDescriptor.dataAndDiscovery(transport.type)
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = transport)
}

private class CancelThenReturnDiscoveryTransport : DataTransport, DiscoveryTransport {
    override val type: TransportKind = TransportKind.LAN
    override val priority: Int = 100
    private val incoming = Channel<RawConnection>(Channel.UNLIMITED)
    private val peerEvents = MutableSharedFlow<PeerEvent>(extraBufferCapacity = 1)

    @Volatile var startAdvertisingCalls: Int = 0
    @Volatile var stopAdvertisingCalls: Int = 0
    @Volatile var advertisingActive: Boolean = false

    override fun canConnect(peer: InternalPeer): Boolean = false
    override suspend fun connect(peer: InternalPeer): RawConnection = error("not supported")
    override fun incomingConnections(): Flow<RawConnection> = incoming.receiveAsFlow()
    override suspend fun stop() = Unit
    override suspend fun close() {
        incoming.close()
    }
    override val events: Flow<PeerEvent> = peerEvents.asSharedFlow()

    override suspend fun startAdvertising(localPeer: LocalPeerInfo) {
        startAdvertisingCalls += 1
        advertisingActive = true
        if (startAdvertisingCalls == 1) {
            currentCoroutineContext().cancel(
                CancellationException("cancel after advertising acquisition")
            )
        }
    }

    override suspend fun stopAdvertising() {
        stopAdvertisingCalls += 1
        advertisingActive = false
    }

    override suspend fun startDiscovery() = Unit
    override suspend fun stopDiscovery() = Unit
}

private class FirstStartSuspendsObserver : NetworkPathObserver {
    private val _status = MutableStateFlow<NetworkPathStatus>(NetworkPathStatus.Unknown)
    override val status: StateFlow<NetworkPathStatus> = _status.asStateFlow()
    val firstStartEntered = CompletableDeferred<Unit>()
    private val never = CompletableDeferred<Unit>()
    @Volatile var startCalls: Int = 0
    @Volatile var closeCalls: Int = 0

    override suspend fun start() {
        startCalls += 1
        if (startCalls == 1) {
            firstStartEntered.complete(Unit)
            never.await()
        }
    }

    override suspend fun close() {
        closeCalls += 1
    }
}

private class CancelThenReturnObserver : NetworkPathObserver {
    private val _status = MutableStateFlow<NetworkPathStatus>(NetworkPathStatus.Unknown)
    override val status: StateFlow<NetworkPathStatus> = _status.asStateFlow()

    @Volatile var startCalls: Int = 0
    @Volatile var closeCalls: Int = 0
    @Volatile var active: Boolean = false

    override suspend fun start() {
        startCalls += 1
        active = true
        if (startCalls == 1) {
            currentCoroutineContext().cancel(
                CancellationException("cancel after observer acquisition")
            )
        }
    }

    override suspend fun close() {
        closeCalls += 1
        active = false
    }
}

/** Observer that acquires a resource before reporting the configured startup failure. */
private class FailingStartObserver(
    @Volatile var failClose: Boolean = false,
    val startFailure: Throwable = IllegalStateException("observer attach failed after partial acquisition")
) : NetworkPathObserver {
    private val _status = MutableStateFlow<NetworkPathStatus>(NetworkPathStatus.Unknown)
    override val status: StateFlow<NetworkPathStatus> = _status.asStateFlow()

    @Volatile var startCalls: Int = 0
    @Volatile var closeCalls: Int = 0
    @Volatile var active: Boolean = false

    val closeFailure = IllegalStateException("observer detach failed")

    override suspend fun start() {
        startCalls += 1
        active = true
        throw startFailure
    }

    override suspend fun close() {
        closeCalls += 1
        if (failClose) throw closeFailure
        active = false
    }
}

/** Ordinary attach failure whose first cleanup is interrupted with its caller. */
private class FailingStartWithFirstCloseSuspendingObserver : NetworkPathObserver {
    private val _status = MutableStateFlow<NetworkPathStatus>(NetworkPathStatus.Unknown)
    override val status: StateFlow<NetworkPathStatus> = _status.asStateFlow()
    val firstCloseEntered = CompletableDeferred<Unit>()
    val startFailure = IllegalStateException("observer attach failed before cleanup cancellation")

    @Volatile var startCalls: Int = 0
    @Volatile var closeCalls: Int = 0
    @Volatile var active: Boolean = false

    override suspend fun start() {
        startCalls += 1
        active = true
        if (startCalls == 1) {
            throw startFailure
        }
    }

    override suspend fun close() {
        closeCalls += 1
        if (closeCalls == 1) {
            firstCloseEntered.complete(Unit)
            CompletableDeferred<Unit>().await()
        }
        active = false
    }
}

private class CancellationWithHangingRollbackTransport : DataTransport {
    override val type: TransportKind = TransportKind.LAN
    override val priority: Int = 100
    val startEntered = CompletableDeferred<Unit>()
    private val releaseStop = CompletableDeferred<Unit>()
    private val incoming = Channel<RawConnection>(Channel.UNLIMITED)
    @Volatile var startCalls: Int = 0
    @Volatile var stopCalls: Int = 0

    override suspend fun start(): Result<Unit> {
        startCalls += 1
        startEntered.complete(Unit)
        CompletableDeferred<Unit>().await()
        return Result.success(Unit)
    }

    override suspend fun stop() {
        stopCalls += 1
        withContext(NonCancellable) { releaseStop.await() }
    }

    override fun canConnect(peer: InternalPeer): Boolean = false
    override suspend fun connect(peer: InternalPeer): RawConnection = error("not supported")
    override fun incomingConnections(): Flow<RawConnection> = incoming.receiveAsFlow()

    override suspend fun close() {
        releaseStop.complete(Unit)
        incoming.close()
    }

    fun releaseHangingStop() {
        releaseStop.complete(Unit)
    }
}

/** Registers any data-only [DataTransport] (e.g. the shared [FakeDataTransport]). */
private class DataOnlyFactory(private val transport: DataTransport) : TransportFactory {
    override val descriptor =
        dev.p2pkit.core.transport.TransportDescriptor.dataOnly(transport.type)
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = null)
}

private class GatedDiscoveryTransport(
    blockAdvertisingStop: Boolean = false
) : DataTransport, DiscoveryTransport {
    override val type: TransportKind = TransportKind.LAN
    override val priority: Int = 100

    val advertisingEntered = CompletableDeferred<Unit>()
    val releaseAdvertising = CompletableDeferred<Unit>()
    val discoveryEntered = CompletableDeferred<Unit>()
    val releaseDiscovery = CompletableDeferred<Unit>()
    val stopAdvertisingEntered = CompletableDeferred<Unit>()
    val releaseStopAdvertising = CompletableDeferred<Unit>().also {
        if (!blockAdvertisingStop) it.complete(Unit)
    }

    @Volatile var startAdvertisingCalls: Int = 0
    @Volatile var stopAdvertisingCalls: Int = 0
    @Volatile var startDiscoveryCalls: Int = 0
    @Volatile var stopDiscoveryCalls: Int = 0

    private val incoming = Channel<RawConnection>(Channel.UNLIMITED)
    private val peerEvents = MutableSharedFlow<PeerEvent>(extraBufferCapacity = 1)

    override fun canConnect(peer: InternalPeer): Boolean = false
    override suspend fun connect(peer: InternalPeer): RawConnection =
        error("GatedDiscoveryTransport does not connect")
    override fun incomingConnections(): Flow<RawConnection> = incoming.receiveAsFlow()
    override suspend fun stop() = Unit
    override suspend fun close() {
        incoming.close()
    }

    override val events: Flow<PeerEvent> = peerEvents.asSharedFlow()

    override suspend fun startAdvertising(localPeer: LocalPeerInfo) {
        startAdvertisingCalls += 1
        advertisingEntered.complete(Unit)
        releaseAdvertising.await()
    }

    override suspend fun stopAdvertising() {
        stopAdvertisingCalls += 1
        stopAdvertisingEntered.complete(Unit)
        releaseStopAdvertising.await()
    }

    override suspend fun startDiscovery() {
        startDiscoveryCalls += 1
        discoveryEntered.complete(Unit)
        releaseDiscovery.await()
    }

    override suspend fun stopDiscovery() {
        stopDiscoveryCalls += 1
    }
}

private class GatedDiscoveryFactory(
    private val transport: GatedDiscoveryTransport
) : TransportFactory {
    override val descriptor =
        dev.p2pkit.core.transport.TransportDescriptor.dataAndDiscovery(transport.type)
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = transport)
}

private class GatedConnectTransport(
    private val lateConnection: RawConnection
) : DataTransport {
    override val type: TransportKind = TransportKind.LAN
    override val priority: Int = 100

    val connectEntered = CompletableDeferred<Unit>()
    val releaseConnect = CompletableDeferred<Unit>()
    private val incoming = Channel<RawConnection>(Channel.UNLIMITED)

    override fun canConnect(peer: InternalPeer): Boolean = true

    override suspend fun connect(peer: InternalPeer): RawConnection {
        connectEntered.complete(Unit)
        releaseConnect.await()
        return lateConnection
    }

    override fun incomingConnections(): Flow<RawConnection> = incoming.receiveAsFlow()

    override suspend fun stop() = Unit

    override suspend fun close() {
        incoming.close()
    }
}

private class GatedConnectFactory(
    private val transport: GatedConnectTransport
) : TransportFactory {
    override val descriptor =
        dev.p2pkit.core.transport.TransportDescriptor.dataOnly(transport.type)
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = null)
}

private class LateReturningObserver : NetworkPathObserver {
    private val _status = MutableStateFlow<NetworkPathStatus>(NetworkPathStatus.Unknown)
    override val status: StateFlow<NetworkPathStatus> = _status.asStateFlow()

    val startEntered = CompletableDeferred<Unit>()
    val releaseStart = CompletableDeferred<Unit>()
    private val closeCallCount = MutableStateFlow(0)
    val closeCalls: Int get() = closeCallCount.value

    override suspend fun start() {
        startEntered.complete(Unit)
        releaseStart.await()
    }

    override suspend fun close() {
        closeCallCount.update { it + 1 }
    }
}

/**
 * [NetworkPathObserver] modeling the shipped Android/iOS observers' shape:
 * `start()` and `close()` serialize on one internal mutex. `start()` parks
 * holding the mutex until [releaseStart], so a `close()` issued meanwhile
 * blocks on that same mutex — the AUDIT-2026-07 (ARCH-2) scenario (P1-09).
 */
private class MutexHeldObserver : NetworkPathObserver {
    private val mutex = Mutex()
    private val _status = MutableStateFlow<NetworkPathStatus>(NetworkPathStatus.Unknown)
    override val status: StateFlow<NetworkPathStatus> = _status.asStateFlow()

    /** Completed by [start] once it holds the mutex (and is now parked). */
    val startEntered = CompletableDeferred<Unit>()

    /** Completed by the test to let the hung [start] return. */
    val releaseStart = CompletableDeferred<Unit>()

    @Volatile var closeAttempted: Boolean = false
    @Volatile var closeCompleted: Boolean = false

    override suspend fun start() {
        mutex.withLock {
            startEntered.complete(Unit)
            releaseStart.await()
        }
    }

    override suspend fun close() {
        closeAttempted = true
        mutex.withLock { closeCompleted = true }
    }
}

/**
 * [NetworkPathObserver] whose `close()` suspends before completing — the
 * shape of the shipped observers (dispatcher hop / internal mutex). Before
 * the AUDIT-2026-07 (ARCH-2) fix, a cancelled `stop()` caller aborted
 * `close()` at exactly that suspension point.
 */
private class YieldingCloseObserver : NetworkPathObserver {
    private val _status = MutableStateFlow<NetworkPathStatus>(NetworkPathStatus.Unknown)
    override val status: StateFlow<NetworkPathStatus> = _status.asStateFlow()

    @Volatile var closeCompleted: Boolean = false

    override suspend fun start() {}

    override suspend fun close() {
        yield()
        closeCompleted = true
    }
}

/**
 * [DataTransport] whose `close()` parks until the test releases it, so a
 * test can cancel a `stop()` caller while teardown is deterministically
 * mid-flight (P1-09).
 */
private class GatedCloseTransport : DataTransport {

    override val type: TransportKind = TransportKind.LAN
    override val priority: Int = 100

    @Volatile var dataClosed: Boolean = false
    private val closeCallCount = MutableStateFlow(0)
    val closeCalls: Int get() = closeCallCount.value

    /** Completed by [close] the moment it is entered (teardown is now mid-flight). */
    val closeEntered = CompletableDeferred<Unit>()

    /** Completed by the test to let the parked [close] finish. */
    val releaseClose = CompletableDeferred<Unit>()

    private val incomingChannel = Channel<RawConnection>(Channel.UNLIMITED)

    override fun canConnect(peer: InternalPeer): Boolean = false
    override suspend fun connect(peer: InternalPeer): RawConnection =
        error("GatedCloseTransport does not produce outgoing connections")

    override fun incomingConnections(): Flow<RawConnection> = incomingChannel.receiveAsFlow()

    override suspend fun stop() = Unit

    override suspend fun close() {
        closeCallCount.update { it + 1 }
        closeEntered.complete(Unit)
        releaseClose.await()
        dataClosed = true
        incomingChannel.close()
    }
}

private class GatedCloseFactory(private val transport: GatedCloseTransport) : TransportFactory {
    override val descriptor =
        dev.p2pkit.core.transport.TransportDescriptor.dataOnly(transport.type)
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = null)
}

private enum class CleanupBehavior { SUCCEED, THROW, HANG }

private class CleanupProbeTransport(
    override val type: TransportKind,
    private val cleanupBehavior: CleanupBehavior
) : DataTransport {
    override val priority: Int = 100
    private val incoming = Channel<RawConnection>(Channel.UNLIMITED)
    private val releaseClose = CompletableDeferred<Unit>()
    @Volatile var closeCalls: Int = 0
    @Volatile var closed: Boolean = false

    override fun canConnect(peer: InternalPeer): Boolean = false
    override suspend fun connect(peer: InternalPeer): RawConnection = error("not supported")
    override fun incomingConnections(): Flow<RawConnection> = incoming.receiveAsFlow()

    override suspend fun stop() = Unit

    override suspend fun close() {
        closeCalls += 1
        when (cleanupBehavior) {
            CleanupBehavior.SUCCEED -> {
                closed = true
                incoming.close()
            }
            CleanupBehavior.THROW -> throw IllegalStateException("close failed for $type")
            CleanupBehavior.HANG -> withContext(NonCancellable) { releaseClose.await() }
        }
    }

    fun releaseHangingClose() {
        releaseClose.complete(Unit)
    }
}

private class CleanupProbeFactory(
    private val transport: CleanupProbeTransport
) : TransportFactory {
    override val descriptor =
        dev.p2pkit.core.transport.TransportDescriptor.dataOnly(transport.type)
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = null)
}
