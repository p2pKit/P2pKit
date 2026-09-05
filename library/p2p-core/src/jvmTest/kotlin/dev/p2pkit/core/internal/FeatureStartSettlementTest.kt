package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.FeatureState
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pState
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.FakeNetworkPathObserver
import dev.p2pkit.core.testfixtures.createTestKit
import dev.p2pkit.core.transport.DiscoveryTransport
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.TransportCapability
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportDescriptor
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Reproduces real lifecycle-mutex contention, without adding a production suspension seam. */
class FeatureStartSettlementTest {
    @Test
    fun cancellationWhileSettlingAdvertisingFailureDoesNotRepeatRollback() =
        cancellationWhileSettlingFailure(advertising = true)

    @Test
    fun cancellationWhileSettlingDiscoveryFailureDoesNotRepeatRollback() =
        cancellationWhileSettlingFailure(advertising = false)

    @Test
    fun cancellationWhileSettlingAdvertisingRetryFailureDoesNotDiscardCleanup() =
        cancellationWhileSettlingFailure(advertising = true, retry = true)

    @Test
    fun cancellationWhileSettlingDiscoveryRetryFailureDoesNotDiscardCleanup() =
        cancellationWhileSettlingFailure(advertising = false, retry = true)

    private fun cancellationWhileSettlingFailure(advertising: Boolean, retry: Boolean = false) = runBlocking {
        val transport = FailingFeatureTransport(
            advertising,
            cleanupFailureCalls = if (retry) setOf(1, 2) else setOf(1)
        )
        val firstLockOwner = Any()
        val contenderOwner = Any()
        val rollbackLogged = CompletableDeferred<Boolean>()
        val contenderEntered = CompletableDeferred<Unit>()
        val releaseContender = CompletableDeferred<Unit>()
        val testThread = Thread.currentThread()
        var logThread: Thread? = null
        var captureCleanup = !retry
        lateinit var lifecycleMutex: Mutex
        val testLogger = object : P2pLogger by P2pLogger.NoOp {
            override fun warn(message: String, throwable: Throwable?) {
                if (captureCleanup && throwable === transport.cleanupFailure && !rollbackLogged.isCompleted) {
                    logThread = Thread.currentThread()
                    rollbackLogged.complete(lifecycleMutex.tryLock(firstLockOwner))
                }
            }
        }
        val kit = createTestKit {
            appId = AppId("feature-settlement-${if (advertising) "advertising" else "discovery"}")
            deviceName = "Settlement test"
            peerIdStorage = InMemoryPeerIdStorage()
            logger = testLogger
            networkPathObserver = FakeNetworkPathObserver()
            transports { register(FailingFeatureFactory(transport)) }
        }
        // Read the actual private lock. A synthetic cancellable hook would create
        // a new failure path rather than exercising the production commit gate.
        lifecycleMutex = P2pKitImpl::class.java.getDeclaredField("lifecycleMutex").let {
            it.isAccessible = true
            it.get(kit) as Mutex
        }
        var operation: Job? = null
        var contender: Job? = null
        var observedFailure: Throwable? = null
        try {
            if (advertising) kit.startDiscovery() else kit.startAdvertising()
            if (retry) {
                assertFailsWith<P2pError.ConnectionFailed> { kit.startFeature(advertising) }
                assertIs<FeatureState.Failed>(kit.featureState(advertising))
                captureCleanup = true
            }
            operation = launch {
                try {
                    kit.startFeature(advertising)
                } catch (failure: Throwable) {
                    observedFailure = failure
                }
            }
            assertTrue(withTimeout(5_000) { rollbackLogged.await() })
            assertSame(testThread, logThread, "rollback logging must resume on the test event loop")

            // Logging resumes this test on the same runBlocking event loop.
            // The start owner continues into its first NonCancellable lifecycle
            // check before this continuation runs, and queues for the held lock.
            // A second FIFO waiter then keeps the *next* commit acquisition
            // contended. Cancellation there used to re-enter the failure handler.
            // Retry preparation instead reaches settlement on its first lock.
            if (!retry) {
                contender = launch(start = CoroutineStart.UNDISPATCHED) {
                    lifecycleMutex.withLock(contenderOwner) {
                        contenderEntered.complete(Unit)
                        releaseContender.await()
                    }
                }
            }
            operation.cancel(CancellationException("caller canceled during failure settlement"))
            lifecycleMutex.unlock(firstLockOwner)
            if (!retry) withTimeout(5_000) { contenderEntered.await() }
            releaseContender.complete(Unit)
            withTimeout(5_000) { operation.join() }

            val featureState = kit.featureState(advertising)
            val expectedStops = if (retry) 2 else 1
            assertEquals(
                expectedStops,
                transport.stopCalls.get(),
                "one failed start must settle one rollback; final state=$featureState"
            )
            val failed = assertIs<FeatureState.Failed>(featureState)
            val aggregate = assertIs<CleanupAggregateException>(failed.error.cause)
            if (!retry) assertTrue(aggregate.issues.any { it.cause === transport.startFailure })
            assertTrue(aggregate.issues.any { it.cause === transport.cleanupFailure })
            val cancelled = assertIs<CancellationException>(observedFailure)
            assertTrue(cancelled.suppressedExceptions.any { it === failed.error })
            assertEquals(FeatureState.Active, kit.featureState(!advertising))
            assertEquals(P2pState.Running, kit.state.value)

            // A retained cleanup marker is observed behaviorally: retry must
            // clean the previous resource before entering a fresh start.
            transport.failStart = false
            kit.startFeature(advertising)
            assertEquals(expectedStops + 1, transport.stopCalls.get())
            assertEquals(2, transport.startCalls.get())
            assertEquals(FeatureState.Active, kit.featureState(advertising))
            assertEquals(FeatureState.Active, kit.featureState(!advertising))
        } finally {
            if (lifecycleMutex.holdsLock(firstLockOwner)) lifecycleMutex.unlock(firstLockOwner)
            releaseContender.complete(Unit)
            operation?.cancelAndJoin()
            contender?.cancelAndJoin()
            transport.failStart = false
            kit.stop()
        }
    }

    @Test
    fun cancellationDuringAdvertisingStopCheckpointSettlesBeforeStopOwnerRetriesCleanup() =
        cancellationDuringStopCheckpoint(advertising = true)

    @Test
    fun cancellationDuringDiscoveryStopCheckpointSettlesBeforeStopOwnerRetriesCleanup() =
        cancellationDuringStopCheckpoint(advertising = false)

    private fun cancellationDuringStopCheckpoint(advertising: Boolean) = runBlocking {
        val transport = FailingFeatureTransport(advertising).apply {
            failStart = false
            gateStart = true
            gateSecondStop = true
        }
        val lockOwner = Any()
        val rollbackLogged = CompletableDeferred<Boolean>()
        lateinit var lifecycleMutex: Mutex
        val testLogger = object : P2pLogger by P2pLogger.NoOp {
            override fun warn(message: String, throwable: Throwable?) {
                if (throwable === transport.cleanupFailure && !rollbackLogged.isCompleted) {
                    rollbackLogged.complete(lifecycleMutex.tryLock(lockOwner))
                }
            }
        }
        val kit = createTestKit {
            appId = AppId("feature-stop-settlement-test")
            deviceName = "Stop settlement test"
            peerIdStorage = InMemoryPeerIdStorage()
            logger = testLogger
            networkPathObserver = FakeNetworkPathObserver()
            transports { register(FailingFeatureFactory(transport)) }
        }
        lifecycleMutex = P2pKitImpl::class.java.getDeclaredField("lifecycleMutex").let {
            it.isAccessible = true
            it.get(kit) as Mutex
        }
        var start: Job? = null
        var stop: Job? = null
        var observedFailure: Throwable? = null
        try {
            if (advertising) kit.startDiscovery() else kit.startAdvertising()
            start = launch {
                try {
                    kit.startFeature(advertising)
                } catch (failure: Throwable) {
                    observedFailure = failure
                }
            }
            withTimeout(5_000) { transport.startEntered.await() }
            val stopping = async {
                if (advertising) kit.stopAdvertising() else kit.stopDiscovery()
            }
            stop = stopping
            withTimeout(5_000) {
                (if (advertising) kit.advertisingState else kit.discoveryState).first { it == FeatureState.Stopping }
            }
            transport.releaseStart.complete(Unit)
            assertTrue(withTimeout(5_000) { rollbackLogged.await() })
            start.cancel(CancellationException("cancel after stop-checkpoint rollback"))
            lifecycleMutex.unlock(lockOwner)

            withTimeout(5_000) { transport.secondStopEntered.await() }
            assertTrue(start.isCompleted, "the second cleanup must belong to the explicit stop, not the start")
            val failed = assertIs<FeatureState.Failed>(kit.featureState(advertising))
            val aggregate = assertIs<CleanupAggregateException>(failed.error.cause)
            assertTrue(aggregate.issues.any { it.cause === transport.cleanupFailure })
            val cancelled = assertIs<CancellationException>(observedFailure)
            assertTrue(cancelled.suppressedExceptions.any { it === failed.error })
            assertEquals(FeatureState.Active, kit.featureState(!advertising))

            transport.releaseSecondStop.complete(Unit)
            withTimeout(5_000) { stopping.await() }
            assertEquals(2, transport.stopCalls.get(), "the explicit stop owns one subsequent cleanup retry")
            assertEquals(FeatureState.Idle, kit.featureState(advertising))
            assertEquals(FeatureState.Active, kit.featureState(!advertising))
        } finally {
            if (lifecycleMutex.holdsLock(lockOwner)) lifecycleMutex.unlock(lockOwner)
            transport.releaseStart.complete(Unit)
            transport.releaseSecondStop.complete(Unit)
            start?.cancelAndJoin()
            stop?.cancelAndJoin()
            kit.stop()
        }
    }

    private suspend fun P2pKit.startFeature(advertising: Boolean) {
        if (advertising) startAdvertising() else startDiscovery()
    }

    private fun P2pKit.featureState(advertising: Boolean): FeatureState =
        if (advertising) advertisingState.value else discoveryState.value

    private class FailingFeatureTransport(
        private val advertising: Boolean,
        private val cleanupFailureCalls: Set<Int> = setOf(1)
    ) : DiscoveryTransport {
        override val type: TransportKind = TransportKind.LAN
        override val events: Flow<PeerEvent> = emptyFlow()
        val startFailure = IllegalStateException("synthetic feature start failure")
        val cleanupFailure = IllegalStateException("synthetic feature rollback failure")
        val startCalls = AtomicInteger()
        val stopCalls = AtomicInteger()
        var failStart = true
        var gateStart = false
        var gateSecondStop = false
        val startEntered = CompletableDeferred<Unit>()
        val releaseStart = CompletableDeferred<Unit>()
        val secondStopEntered = CompletableDeferred<Unit>()
        val releaseSecondStop = CompletableDeferred<Unit>()

        override suspend fun startAdvertising(localPeer: LocalPeerInfo) {
            if (advertising) start()
        }

        override suspend fun stopAdvertising() {
            if (advertising) stop()
        }

        override suspend fun startDiscovery() {
            if (!advertising) start()
        }

        override suspend fun stopDiscovery() {
            if (!advertising) stop()
        }

        private suspend fun start() {
            startCalls.incrementAndGet()
            startEntered.complete(Unit)
            if (gateStart) releaseStart.await()
            if (failStart) throw startFailure
        }

        private suspend fun stop() {
            val call = stopCalls.incrementAndGet()
            if (call in cleanupFailureCalls) throw cleanupFailure
            if (call == 2 && gateSecondStop) {
                secondStopEntered.complete(Unit)
                releaseSecondStop.await()
            }
        }
    }

    private class FailingFeatureFactory(private val transport: DiscoveryTransport) : TransportFactory {
        override val descriptor = TransportDescriptor(
            kind = transport.type,
            capabilities = setOf(TransportCapability.DATA, TransportCapability.DISCOVERY)
        )
        override fun build(context: TransportContext): TransportPair =
            TransportPair(data = FakeDataTransport(), discovery = transport)
    }
}
