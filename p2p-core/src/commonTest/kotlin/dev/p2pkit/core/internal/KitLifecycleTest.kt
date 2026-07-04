package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.NetworkPathObserver
import dev.p2pkit.core.NetworkPathStatus
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pState
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.testfixtures.FakeDataTransport
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
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeout
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
            val kit = P2pKit.create {
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
            val k1 = P2pKit.create {
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
            val k2 = P2pKit.create {
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
            val kit = P2pKit.create {
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
            withTimeout(15_000) { kit.stop() }
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
            val kit = P2pKit.create {
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
            val kit = P2pKit.create {
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

    /**
     * P1-07 (2026-07 coverage plan) / AUDIT-2026-06 re-advertise fix: a
     * post-start advertise failure latches [P2pState.Failed]; a subsequent
     * successful `startAdvertising()` must clear it back to Running
     * (ensureStarted's success fast-path never re-runs the Running
     * transition, so this clearing is the only way out).
     */
    @Test
    fun successfulReadvertiseClearsLatchedFailed() {
        runBlocking {
            val transport = TrackingTransport()
            val kit = P2pKit.create {
                appId = AppId("readvertise-test")
                deviceName = "Test"
                transports { register(TrackingFactory(transport)) }
            }

            kit.start()
            assertEquals(P2pState.Running, kit.state.value)

            transport.advertiseFailure = RuntimeException("simulated mDNS registration refusal")
            assertFailsWith<P2pError.ConnectionFailed> { kit.startAdvertising() }
            assertIs<P2pState.Failed>(
                kit.state.value,
                "an advertise failure must surface through the lifecycle as Failed"
            )

            transport.advertiseFailure = null
            kit.startAdvertising()
            assertEquals(
                P2pState.Running, kit.state.value,
                "a successful re-advertise must clear latched Failed back to Running"
            )

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
            val kit = P2pKit.create {
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
                P2pState.Starting, kit.state.value,
                "a cancelled start must not corrupt public state to Failed"
            )

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
            val kit = P2pKit.create {
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
            withTimeout(30_000) { kit.stop() }
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
            val kit = P2pKit.create {
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

private class TrackingFactory(private val transport: TrackingTransport) : TransportFactory {
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = transport)
}

/**
 * [DataTransport] whose `start()` parks until the test releases it, so a test
 * can hold `ensureStarted` (and the kit's start mutex) hung at will.
 */
private class HungStartTransport : DataTransport {

    override val type: TransportKind = TransportKind.LAN
    override val priority: Int = 100

    @Volatile var dataClosed: Boolean = false

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

    override suspend fun close() {
        dataClosed = true
        incomingChannel.close()
    }
}

private class HungStartFactory(private val transport: HungStartTransport) : TransportFactory {
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = null)
}

/** Registers any data-only [DataTransport] (e.g. the shared [FakeDataTransport]). */
private class DataOnlyFactory(private val transport: DataTransport) : TransportFactory {
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = null)
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

    /** Completed by [close] the moment it is entered (teardown is now mid-flight). */
    val closeEntered = CompletableDeferred<Unit>()

    /** Completed by the test to let the parked [close] finish. */
    val releaseClose = CompletableDeferred<Unit>()

    private val incomingChannel = Channel<RawConnection>(Channel.UNLIMITED)

    override fun canConnect(peer: InternalPeer): Boolean = false
    override suspend fun connect(peer: InternalPeer): RawConnection =
        error("GatedCloseTransport does not produce outgoing connections")

    override fun incomingConnections(): Flow<RawConnection> = incomingChannel.receiveAsFlow()

    override suspend fun close() {
        closeEntered.complete(Unit)
        releaseClose.await()
        dataClosed = true
        incomingChannel.close()
    }
}

private class GatedCloseFactory(private val transport: GatedCloseTransport) : TransportFactory {
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = null)
}
