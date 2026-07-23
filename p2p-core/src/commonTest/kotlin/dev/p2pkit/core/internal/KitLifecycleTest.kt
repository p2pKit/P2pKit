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
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.createTestKit
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.DiscoveryTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlin.concurrent.Volatile
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.withContext
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
    fun stopClosesDataTransportAndStopsDiscoveryAdvertising() {
        runBlocking {
            val transport = TrackingTransport()
            val kit = createTestKit {
                appId = AppId("lifecycle-test")
                deviceName = "Test"
                transports { register(TrackingFactory(transport)) }
            }

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

    @Test
    fun freshKitAfterStopIsIndependent() {
        runBlocking {
            val first = TrackingTransport()
            val k1 = createTestKit {
                appId = AppId("indep-test")
                deviceName = "First"
                transports { register(TrackingFactory(first)) }
            }
            k1.startAdvertising()
            k1.stop()
            assertTrue(first.dataClosed)

            // After stopping the first kit, a brand-new kit with a separate
            // transport should not see any state leak from the first.
            val second = TrackingTransport()
            val k2 = createTestKit {
                appId = AppId("indep-test")
                deviceName = "Second"
                transports { register(TrackingFactory(second)) }
            }
            assertFalse(second.dataClosed, "Fresh transport should not be closed before any start")
            assertFalse(second.advertisingStarted, "Fresh transport should not have any advertising history")

            k2.startAdvertising()
            assertTrue(second.advertisingStarted)
            assertFalse(second.dataClosed)

            k2.stop()
            assertTrue(second.dataClosed)
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
            val kit = createTestKit {
                appId = AppId("stop-hang-test")
                deviceName = "Test"
                transports { register(HungStartFactory(transport)) }
            }

            // Park ensureStarted inside transport.start() while it holds the
            // start mutex. start() is expected to fail once stop() tears the
            // kit down (the post-bind stopped re-check throws); swallow it —
            // this coroutine exists only to keep the mutex held.
            val starter = launch { runCatching { kit.start() } }
            transport.startEntered.await()

            // Pre-fix, stop() parked forever on the held mutex and this
            // outer bound (3x the 5 s mutex-acquisition bound) fired.
            assertFailsWith<P2pError.ConnectionFailed> {
                withTimeout(15_000) { kit.stop() }
            }
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
            val kit = createTestKit {
                appId = AppId("state-machine-test")
                deviceName = "Test"
                transports { register(HungStartFactory(transport)) }
            }

            assertEquals(P2pState.Idle, kit.state.value, "a fresh kit must report Idle")

            val starter = launch { kit.start() }
            transport.startEntered.await()
            assertEquals(
                P2pState.Starting, kit.state.value,
                "state must report Starting while the bind loop is in flight"
            )

            transport.releaseStart.complete(Unit)
            withTimeout(15_000) { starter.join() }
            assertEquals(P2pState.Running, kit.state.value, "successful start must reach Running")

            kit.stop()
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
            val kit = createTestKit {
                appId = AppId("bind-failure-test")
                deviceName = "Test"
                transports { register(DataOnlyFactory(transport)) }
            }

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

    @Test
    fun partialDataStartupRollsBackInReverseAndSameInstancesRetry() = runBlocking {
        val calls = mutableListOf<String>()
        val first = StartupProbeTransport(TransportKind.LAN, "first", calls)
        val second = StartupProbeTransport(TransportKind.BLE, "second", calls).also {
            it.startFailure = IllegalStateException("second bind failed after acquisition")
        }
        val kit = createTestKit {
            appId = AppId("data-start-rollback-test")
            deviceName = "Test"
            transports {
                register(DataOnlyFactory(first))
                register(DataOnlyFactory(second))
            }
        }

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

    /** Advertising failure/retry is retained without corrupting discovery or kit state. */
    @Test
    fun advertisingFailureIsIndependentAndRetryReachesActive() {
        runBlocking {
            val transport = TrackingTransport()
            val kit = createTestKit {
                appId = AppId("readvertise-test")
                deviceName = "Test"
                transports { register(TrackingFactory(transport)) }
            }

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

    @Test
    fun concurrentAdvertisingStartsCoalesceAndActiveStartIsIdempotent() = runBlocking {
        val transport = GatedDiscoveryTransport()
        val kit = createTestKit {
            appId = AppId("coalesced-advertising-test")
            deviceName = "Test"
            transports { register(GatedDiscoveryFactory(transport)) }
        }
        try {
            val firstStart = launch { kit.startAdvertising() }
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
            kit.stop()
        }
    }

    @Test
    fun stopDuringAdvertisingStartWinsAndRollsBackLateResource() = runBlocking {
        val transport = GatedDiscoveryTransport()
        val kit = createTestKit {
            appId = AppId("stop-during-advertising-test")
            deviceName = "Test"
            transports { register(GatedDiscoveryFactory(transport)) }
        }
        try {
            val start = launch { kit.startAdvertising() }
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
            kit.stop()
        }
    }

    @Test
    fun partialAdvertisingFailureRollsBackEveryAttemptedTransport() = runBlocking {
        val first = RollbackDiscoveryTransport(TransportKind.LAN)
        val failure = IllegalStateException("second advertising transport failed")
        val second = RollbackDiscoveryTransport(TransportKind.BLE).apply {
            advertisingFailure = failure
        }
        val kit = createTestKit {
            appId = AppId("advertising-rollback-test")
            deviceName = "Test"
            transports {
                register(RollbackDiscoveryFactory(first))
                register(RollbackDiscoveryFactory(second))
            }
        }
        try {
            val thrown = assertFailsWith<P2pError.ConnectionFailed> {
                kit.startAdvertising()
            }
            assertTrue(thrown.message.orEmpty().contains(failure.message.orEmpty()))
            assertEquals(1, first.stopAdvertisingCalls)
            assertEquals(1, second.stopAdvertisingCalls)
            assertFalse(first.advertisingActive)
            assertFalse(second.advertisingActive)
        } finally {
            kit.stop()
        }
    }

    @Test
    fun cancelledDiscoveryRollsBackEveryAttemptedTransportAndPreservesCancellation() = runBlocking {
        val first = RollbackDiscoveryTransport(TransportKind.LAN)
        val second = RollbackDiscoveryTransport(TransportKind.BLE, gateDiscovery = true)
        val kit = createTestKit {
            appId = AppId("discovery-cancellation-rollback-test")
            deviceName = "Test"
            transports {
                register(RollbackDiscoveryFactory(first))
                register(RollbackDiscoveryFactory(second))
            }
        }
        try {
            var thrown: Throwable? = null
            val operation = launch {
                try {
                    kit.startDiscovery()
                } catch (error: Throwable) {
                    thrown = error
                    throw error
                }
            }
            second.discoveryEntered.await()
            operation.cancelAndJoin()

            assertIs<CancellationException>(thrown)
            assertEquals(1, first.stopDiscoveryCalls)
            assertEquals(1, second.stopDiscoveryCalls)
            assertFalse(first.discoveryActive)
            assertFalse(second.discoveryActive)
            assertEquals(FeatureState.Idle, kit.discoveryState.value)
        } finally {
            kit.stop()
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
            val kit = createTestKit {
                appId = AppId("cancel-start-test")
                deviceName = "Test"
                transports { register(HungStartFactory(transport)) }
            }

            var thrown: Throwable? = null
            val starter = launch {
                try {
                    kit.start()
                } catch (e: Throwable) {
                    thrown = e
                    throw e
                }
            }
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
            val kit = createTestKit {
                appId = AppId("bounded-stop-observer-test")
                deviceName = "Test"
                lifecycle { networkPathObserver = observer }
                transports { register(TrackingFactory(transport)) }
            }

            // Park ensureStarted inside observer.start() with the observer's
            // internal mutex held (the kit's startMutex is held too).
            val starter = launch { kit.start() }
            observer.startEntered.await()

            // Pre-fix, stop() parked forever inside pathObserver.close() on
            // the observer's mutex; this outer bound (3x the two 5 s internal
            // bounds) fired. Post-fix stop() is bounded.
            assertFailsWith<P2pError.ConnectionFailed> {
                withTimeout(30_000) { kit.stop() }
            }
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
            val kit = createTestKit {
                appId = AppId("cancelled-stop-test")
                deviceName = "Test"
                lifecycle { networkPathObserver = observer }
                transports { register(GatedCloseFactory(transport)) }
            }

            kit.start()
            assertEquals(P2pState.Running, kit.state.value)

            val stopper = launch { kit.stop() }
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
        }
    }

    @Test
    fun lateAdvertisingCompletionIsRolledBackAfterStop() = runBlocking {
        val transport = GatedDiscoveryTransport()
        val kit = createTestKit {
            appId = AppId("late-advertising-test")
            deviceName = "Test"
            transports { register(GatedDiscoveryFactory(transport)) }
        }
        kit.start()

        var failure: Throwable? = null
        val advertiser = launch {
            try {
                kit.startAdvertising()
            } catch (e: Throwable) {
                failure = e
            }
        }
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
    }

    @Test
    fun lateDiscoveryCompletionIsRolledBackAfterStop() = runBlocking {
        val transport = GatedDiscoveryTransport()
        val kit = createTestKit {
            appId = AppId("late-discovery-test")
            deviceName = "Test"
            transports { register(GatedDiscoveryFactory(transport)) }
        }
        kit.start()

        var failure: Throwable? = null
        val discoverer = launch {
            try {
                kit.startDiscovery()
            } catch (e: Throwable) {
                failure = e
            }
        }
        transport.discoveryEntered.await()

        kit.stop()
        assertEquals(P2pState.Stopped, kit.state.value)
        transport.releaseDiscovery.complete(Unit)
        withTimeout(5_000) { discoverer.join() }

        assertIs<IllegalStateException>(failure)
        assertEquals(2, transport.stopDiscoveryCalls)
        assertEquals(P2pState.Stopped, kit.state.value)
    }

    @Test
    fun observerThatReturnsAfterStopCannotResurrectKit() = runBlocking {
        val transport = TrackingTransport()
        val observer = LateReturningObserver()
        val kit = createTestKit {
            appId = AppId("late-observer-test")
            deviceName = "Test"
            lifecycle { networkPathObserver = observer }
            transports { register(TrackingFactory(transport)) }
        }

        var failure: Throwable? = null
        val starter = launch {
            try {
                kit.start()
            } catch (e: Throwable) {
                failure = e
            }
        }
        observer.startEntered.await()

        assertFailsWith<P2pError.ConnectionFailed> {
            withTimeout(15_000) { kit.stop() }
        }
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
    }

    @Test
    fun outgoingConnectThatReturnsAfterStopCannotPublishSession() = runBlocking {
        val pair = FakeConnectionPair()
        val aliceTransport = GatedConnectTransport(pair.a)
        val bobTransport = FakeDataTransport(preStagedIncoming = listOf(pair.b))
        val alice = createTestKit {
            appId = AppId("late-connect-test")
            deviceName = "Alice"
            peerIdStorage = InMemoryPeerIdStorage(seed = PeerId("alice-id"))
            transports { register(GatedConnectFactory(aliceTransport)) }
        }
        val bob = createTestKit {
            appId = AppId("late-connect-test")
            deviceName = "Bob"
            peerIdStorage = InMemoryPeerIdStorage(seed = PeerId("bob-id"))
            transports { register(DataOnlyFactory(bobTransport)) }
        }
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
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun sessionCommittedBeforeStopIsIncludedInTeardown() = runBlocking {
        val pair = FakeConnectionPair()
        val watcherEntered = CompletableDeferred<Unit>()
        val releaseWatcher = CompletableDeferred<Unit>()
        val aliceTransport = FakeDataTransport(outgoingConnection = { pair.a })
        val bobTransport = FakeDataTransport(preStagedIncoming = listOf(pair.b))
        val alice = createTestKit {
            appId = AppId("committed-session-stop-test")
            deviceName = "Alice"
            peerIdStorage = InMemoryPeerIdStorage(seed = PeerId("alice-id"))
            beforeTerminalWatcherRemovalForTest = {
                watcherEntered.complete(Unit)
                releaseWatcher.await()
            }
            transports { register(DataOnlyFactory(aliceTransport)) }
        }
        val bob = createTestKit {
            appId = AppId("committed-session-stop-test")
            deviceName = "Bob"
            peerIdStorage = InMemoryPeerIdStorage(seed = PeerId("bob-id"))
            transports { register(DataOnlyFactory(bobTransport)) }
        }
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
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun concurrentStopCallersJoinOneTeardown() = runBlocking {
        val transport = GatedCloseTransport()
        val kit = createTestKit {
            appId = AppId("concurrent-stop-test")
            deviceName = "Test"
            transports { register(GatedCloseFactory(transport)) }
        }
        kit.start()

        val first = launch { kit.stop() }
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
    }

    @Test
    fun terminalCleanupIsBoundedAttemptsEveryResourceAndSharesTheFailure() = runBlocking {
        val throwing = CleanupProbeTransport(TransportKind.LAN, CleanupBehavior.THROW)
        val hanging = CleanupProbeTransport(TransportKind.BLE, CleanupBehavior.HANG)
        val healthy = CleanupProbeTransport(TransportKind.RELAY, CleanupBehavior.SUCCEED)
        val kit = createTestKit {
            appId = AppId("bounded-cleanup-test")
            deviceName = "Test"
            transports {
                register(CleanupProbeFactory(throwing))
                register(CleanupProbeFactory(hanging))
                register(CleanupProbeFactory(healthy))
            }
        }
        kit.start()

        val first = assertFailsWith<P2pError.ConnectionFailed> {
            withTimeout(10_000) { kit.stop() }
        }
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
    }

    @Test
    fun explicitFeatureStopAttemptsEveryTransportAndReportsFailures() = runBlocking {
        val failing = RollbackDiscoveryTransport(TransportKind.LAN).apply {
            stopAdvertisingFailure = IllegalStateException("cannot unregister")
        }
        val healthy = RollbackDiscoveryTransport(TransportKind.BLE)
        val kit = createTestKit {
            appId = AppId("feature-stop-cleanup-test")
            deviceName = "Test"
            transports {
                register(RollbackDiscoveryFactory(failing))
                register(RollbackDiscoveryFactory(healthy))
            }
        }
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
            kit.stop()
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

    override suspend fun start(): Result<Unit> {
        check(!closed)
        calls += "start:$label"
        active = true
        val failure = startFailure
        return if (failure == null) Result.success(Unit) else Result.failure(failure)
    }

    override suspend fun stop() {
        calls += "stop:$label"
        active = false
    }

    override fun canConnect(peer: InternalPeer): Boolean = false
    override suspend fun connect(peer: InternalPeer): RawConnection = error("not supported")
    override fun incomingConnections(): Flow<RawConnection> = emptyFlow()

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
    @Volatile var stopAdvertisingCalls: Int = 0
    @Volatile var stopDiscoveryCalls: Int = 0

    override fun canConnect(peer: InternalPeer): Boolean = false
    override suspend fun connect(peer: InternalPeer): RawConnection = error("not supported")
    override fun incomingConnections(): Flow<RawConnection> = incoming.receiveAsFlow()
    override suspend fun stop() = Unit
    override suspend fun close() { incoming.close() }
    override val events: Flow<PeerEvent> = peerEvents.asSharedFlow()

    override suspend fun startAdvertising(localPeer: LocalPeerInfo) {
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

/** Registers any data-only [DataTransport] (e.g. the shared [FakeDataTransport]). */
private class DataOnlyFactory(private val transport: DataTransport) : TransportFactory {
    override val descriptor =
        dev.p2pkit.core.transport.TransportDescriptor.dataOnly(transport.type)
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = null)
}

private class GatedDiscoveryTransport : DataTransport, DiscoveryTransport {
    override val type: TransportKind = TransportKind.LAN
    override val priority: Int = 100

    val advertisingEntered = CompletableDeferred<Unit>()
    val releaseAdvertising = CompletableDeferred<Unit>()
    val discoveryEntered = CompletableDeferred<Unit>()
    val releaseDiscovery = CompletableDeferred<Unit>()

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
