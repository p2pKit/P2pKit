package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.LocalPeerInfo
import java.io.IOException
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.CountDownLatch
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.cancelChildren
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue
import kotlin.test.fail

/**
 * Automated contract for the shared JVM/Android JmDNS lifecycle machinery.
 * Android has no automated device target in this module, so its platform
 * operations compile against the same common state machine pinned here.
 *
 * Pinned here, per the coverage row:
 *   - intent flags vs live handles (AUDIT-2026-06 #5): a create failure mid
 *     rebind must not brick the transport; stop* during the failed-rebind
 *     window clears intent and halts the retry;
 *   - bounded create-retry (budget respected, re-attempt on the next change);
 *   - restoration is transactional: a dropped re-register never commits the
 *     new target and the bounded retry restores every intended resource;
 *   - cancelled create closes the produced handle (AUDIT-2026-07 DSC-3);
 *   - failed start* releases the handle + multicast lock, keeping both when
 *     the other side is still active (AUDIT-2026-07 DSC-13).
 *
 * Fakes drive real time with millisecond debounce/backoff; every wait is a
 * signal/poll with a hard timeout — no bare sleeps as assertions.
 */
class JmdnsLifecycleCoordinatorTest {

    private class FakeNet(private val name: String) {
        override fun toString(): String = name
    }

    private class FakeHandle(val id: Int) {
        @Volatile
        var closed = false
        override fun toString(): String = "handle#$id"
    }

    private class FakeListenerToken(val handle: FakeHandle) {
        @Volatile
        var active = true
    }

    private class FakeServiceToken(val localPeer: LocalPeerInfo)

    private class FakeOps : JmdnsLifecycleOps<FakeNet, FakeHandle> {
        val createCalls = AtomicInteger(0)
        val created = CopyOnWriteArrayList<FakeHandle>()
        val closed = CopyOnWriteArrayList<FakeHandle>()
        val registrations = CopyOnWriteArrayList<Pair<FakeHandle, LocalPeerInfo>>()
        val unregistrations = CopyOnWriteArrayList<Any>()
        val listenersAdded = CopyOnWriteArrayList<FakeListenerToken>()
        val listenersRemoved = CopyOnWriteArrayList<Any>()

        @Volatile
        var lockHeld = false

        @Volatile
        var watcherActive = false

        @Volatile
        var current: FakeNet? = null

        @Volatile
        var observed: FakeNet? = null

        @Volatile
        var observedDefault: FakeNet? = null

        /** While > 0, [createHandleBlocking] throws and decrements. */
        val createFailuresRemaining = AtomicInteger(0)

        /** When set, [createHandleBlocking] parks on this latch before producing. */
        @Volatile
        var createGate: CountDownLatch? = null

        @Volatile
        var registerGate: CountDownLatch? = null

        @Volatile
        var listenerGate: CountDownLatch? = null

        @Volatile
        var unregisterGate: CountDownLatch? = null

        @Volatile
        var removeListenerGate: CountDownLatch? = null

        /** One element offered per [createHandleBlocking] entry — a rendezvous for tests. */
        val createEntered = LinkedBlockingQueue<Unit>()
        val registerEntered = LinkedBlockingQueue<Unit>()
        val listenerEntered = LinkedBlockingQueue<Unit>()
        val unregisterEntered = LinkedBlockingQueue<Unit>()
        val removeListenerEntered = LinkedBlockingQueue<Unit>()

        @Volatile
        var failNextRegister = false

        @Volatile
        var failNextAddListener = false

        @Volatile
        var failNextUnregister = false

        @Volatile
        var failNextRemoveListener = false

        @Volatile
        var failNextWatcherStop = false

        @Volatile
        var failNextLockRelease = false

        val closeFailuresRemaining = AtomicInteger(0)

        /** Handle passed to each heartbeat tick (AUDIT-2026-07 DSC-1). */
        val reemitTicks = CopyOnWriteArrayList<FakeHandle>()

        @Volatile
        var failNextReemit = false

        private fun awaitNonCancellableGate(gate: CountDownLatch, label: String) {
            val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5)
            while (true) {
                val remaining = deadline - System.nanoTime()
                if (remaining <= 0) throw IOException("$label never released")
                try {
                    if (gate.await(remaining, TimeUnit.NANOSECONDS)) return
                } catch (_: InterruptedException) {
                    // JmDNS registration/listener creation is blocking work
                    // that does not honor coroutine cancellation. Ignore the
                    // worker-thread interrupt to reproduce prompt-cancellation
                    // after the side effect completes.
                }
            }
        }

        override fun createHandleBlocking(target: FakeNet?, forRebind: Boolean): FakeHandle {
            createCalls.incrementAndGet()
            createEntered.put(Unit)
            createGate?.let { awaitNonCancellableGate(it, "createGate") }
            if (createFailuresRemaining.get() > 0) {
                createFailuresRemaining.decrementAndGet()
                throw IOException("injected create failure")
            }
            val handle = FakeHandle(createCalls.get())
            created += handle
            return handle
        }

        override fun closeHandleBlocking(handle: FakeHandle) {
            if (closeFailuresRemaining.get() > 0) {
                closeFailuresRemaining.decrementAndGet()
                throw IOException("injected close failure")
            }
            handle.closed = true
            closed += handle
        }

        override fun createServiceToken(localPeer: LocalPeerInfo): Any =
            FakeServiceToken(localPeer)

        override fun registerServiceBlocking(handle: FakeHandle, token: Any) {
            registerEntered.put(Unit)
            registerGate?.let { awaitNonCancellableGate(it, "registerGate") }
            if (failNextRegister) {
                failNextRegister = false
                throw IOException("injected register failure")
            }
            registrations += handle to (token as FakeServiceToken).localPeer
        }

        override fun unregisterServiceBlocking(handle: FakeHandle, token: Any) {
            unregisterEntered.put(Unit)
            unregisterGate?.let { awaitNonCancellableGate(it, "unregisterGate") }
            if (failNextUnregister) {
                failNextUnregister = false
                throw IOException("injected unregister failure")
            }
            unregistrations += token
        }

        override fun createListenerToken(handle: FakeHandle): Any =
            FakeListenerToken(handle)

        override fun addListenerBlocking(handle: FakeHandle, token: Any) {
            listenerEntered.put(Unit)
            listenerGate?.let { awaitNonCancellableGate(it, "listenerGate") }
            if (failNextAddListener) {
                failNextAddListener = false
                throw IOException("injected addListener failure")
            }
            listenersAdded += token as FakeListenerToken
        }

        override fun deactivateListenerToken(token: Any) {
            (token as FakeListenerToken).active = false
        }

        override fun removeListenerBlocking(handle: FakeHandle, token: Any) {
            removeListenerEntered.put(Unit)
            removeListenerGate?.let { awaitNonCancellableGate(it, "removeListenerGate") }
            if (failNextRemoveListener) {
                failNextRemoveListener = false
                throw IOException("injected listener removal failure")
            }
            listenersRemoved += token
        }

        override fun reemitCachedPeersBlocking(handle: FakeHandle) {
            if (failNextReemit) {
                failNextReemit = false
                throw IOException("injected reemit failure")
            }
            reemitTicks += handle
        }

        override fun currentNetwork(): FakeNet? = current

        override fun observedNetwork(): FakeNet? = observed

        override fun observedDefaultNetwork(): FakeNet? = observedDefault

        override fun isWatcherActive(): Boolean = watcherActive

        // Idempotence mirrors the transport-side acquireMulticastLockIfNeeded /
        // release helpers, which key on their own held-lock field.
        override fun acquireMulticastLock() {
            lockHeld = true
        }

        override fun releaseMulticastLock() {
            if (failNextLockRelease) {
                failNextLockRelease = false
                throw IOException("injected multicast release failure")
            }
            lockHeld = false
        }

        override fun startNetworkWatcher() {
            watcherActive = true
        }

        override fun stopNetworkWatcher() {
            if (failNextWatcherStop) {
                failNextWatcherStop = false
                throw IOException("injected watcher cleanup failure")
            }
            watcherActive = false
        }

        override fun logDebug(message: String) = Unit

        override fun logWarn(message: String, error: Throwable?) = Unit
    }

    private val localPeer = LocalPeerInfo(
        peerId = PeerId("coordinator-test-peer"),
        deviceName = "unit",
        platform = Platform.JVM_DESKTOP,
        appId = AppId("dev.p2pkit.test"),
        supportedTransports = setOf(TransportKind.LAN)
    )

    /**
     * Runs [body] with a coordinator wired to [ops] and a dedicated rebind
     * scope (mirroring the transport's SupervisorJob scope), millisecond
     * debounce/backoff unless overridden, and guaranteed scope teardown.
     */
    private fun coordinatorTest(
        ops: FakeOps,
        debounceMillis: Long = 1,
        retryBaseMillis: Long = 1,
        maxAttempts: Int = 5,
        // Large default so the pre-existing tests never see heartbeat ticks;
        // the DSC-1 heartbeat tests inject a millisecond cadence explicitly.
        heartbeatMillis: Long = 60_000,
        body: suspend (
            coordinator: JmdnsLifecycleCoordinator<FakeNet, FakeHandle>,
            rebindScope: CoroutineScope
        ) -> Unit
    ) {
        runBlocking {
            val rebindScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
            val coordinator = JmdnsLifecycleCoordinator(
                ops = ops,
                rebindScope = rebindScope,
                ioContext = Dispatchers.IO,
                rebindDebounceMillis = debounceMillis,
                rebindRetryBaseDelayMillis = retryBaseMillis,
                rebindRetryMaxAttempts = maxAttempts,
                heartbeatIntervalMillis = heartbeatMillis
            )
            try {
                body(coordinator, rebindScope)
            } finally {
                rebindScope.cancel()
            }
        }
    }

    private suspend fun awaitCondition(
        what: String,
        timeoutMillis: Long = 5_000,
        condition: () -> Boolean
    ) {
        val deadline = System.currentTimeMillis() + timeoutMillis
        while (!condition()) {
            if (System.currentTimeMillis() > deadline) fail("timed out waiting for: $what")
            delay(5)
        }
    }

    private suspend fun awaitCreateEntered(ops: FakeOps) {
        withContext(Dispatchers.IO) { ops.createEntered.poll(5, TimeUnit.SECONDS) }
            ?: fail("createHandleBlocking was never entered")
    }

    private suspend fun awaitBlockingCall(queue: LinkedBlockingQueue<Unit>, what: String) {
        withContext(Dispatchers.IO) { queue.poll(5, TimeUnit.SECONDS) }
            ?: fail("$what was never entered")
    }

    // ── lifecycle / idle policy ─────────────────────────────────────────

    @Test
    fun startBothSidesSharesOneHandleAndStopBothReleasesEverything() {
        val ops = FakeOps().apply { current = FakeNet("wifi0") }
        coordinatorTest(ops) { coordinator, _ ->
            coordinator.startAdvertising(localPeer)
            coordinator.startDiscovery()

            assertEquals(1, ops.createCalls.get(), "advertise + discover must share one handle")
            assertEquals(1, ops.registrations.size)
            assertEquals(1, ops.listenersAdded.size)
            val listener = ops.listenersAdded.single()
            assertTrue(ops.lockHeld)
            assertTrue(ops.watcherActive)

            coordinator.stopAdvertising()
            // Discovery still intended: shared handle, lock, and watcher stay.
            assertEquals(1, ops.unregistrations.size)
            assertTrue(ops.closed.isEmpty(), "handle must survive while discovery is active")
            assertTrue(ops.lockHeld)
            assertTrue(ops.watcherActive)

            coordinator.stopDiscovery()
            assertEquals(1, ops.listenersRemoved.size)
            assertFalse(listener.active, "terminal cleanup must deactivate queued callbacks")
            assertEquals(1, ops.closed.size, "idle close must release the shared handle")
            assertFalse(ops.lockHeld)
            assertFalse(ops.watcherActive)
        }
    }

    @Test
    fun unregisterFailureClosesTheOwnerAndRestoresDiscoveryOnly() {
        val ops = FakeOps().apply { current = FakeNet("wifi0") }
        coordinatorTest(ops) { coordinator, _ ->
            coordinator.startAdvertising(localPeer)
            coordinator.startDiscovery()
            val original = ops.created.single()
            ops.failNextUnregister = true

            coordinator.stopAdvertising()

            assertTrue(original.closed, "failed targeted cleanup must close its owning handle")
            assertEquals(2, ops.created.size)
            assertEquals(2, ops.listenersAdded.size, "discovery must be restored")
            assertSame(ops.created.last(), ops.listenersAdded.last().handle)
            assertEquals(1, ops.registrations.size, "advertising must not be resurrected")
        }
    }

    @Test
    fun listenerRemovalFailureClosesTheOwnerAndRestoresAdvertisingOnly() {
        val ops = FakeOps().apply { current = FakeNet("wifi0") }
        coordinatorTest(ops) { coordinator, _ ->
            coordinator.startAdvertising(localPeer)
            coordinator.startDiscovery()
            val original = ops.created.single()
            ops.failNextRemoveListener = true

            coordinator.stopDiscovery()

            assertTrue(original.closed, "failed targeted cleanup must close its owning handle")
            assertEquals(2, ops.created.size)
            assertEquals(2, ops.registrations.size, "advertising must be restored")
            assertSame(ops.created.last(), ops.registrations.last().first)
            assertEquals(1, ops.listenersAdded.size, "discovery must not be resurrected")
        }
    }

    @Test
    fun failedFallbackCloseRetainsOwnershipAndARepeatedStopRetriesCleanup() {
        val ops = FakeOps().apply { current = FakeNet("wifi0") }
        coordinatorTest(ops) { coordinator, _ ->
            coordinator.startAdvertising(localPeer)
            val original = ops.created.single()
            ops.failNextUnregister = true
            ops.closeFailuresRemaining.set(1)

            assertFailsWith<IOException> { coordinator.stopAdvertising() }
            assertFalse(original.closed)
            assertTrue(ops.lockHeld, "live handle keeps multicast ownership after failed close")
            assertTrue(ops.watcherActive, "watcher ownership is retained for retry")

            coordinator.stopAdvertising()
            assertTrue(original.closed)
            assertFalse(ops.lockHeld)
            assertFalse(ops.watcherActive)
        }
    }

    @Test
    fun watcherCleanupFailureRetainsIdleOwnershipUntilRepeatedStopSucceeds() {
        val ops = FakeOps().apply {
            current = FakeNet("wifi0")
            failNextWatcherStop = true
        }
        coordinatorTest(ops) { coordinator, _ ->
            coordinator.startAdvertising(localPeer)

            assertFailsWith<IOException> { coordinator.stopAdvertising() }
            assertTrue(ops.watcherActive, "failed callback cleanup must remain owned")
            assertTrue(ops.lockHeld, "multicast lock stays owned until watcher cleanup completes")

            coordinator.stopAdvertising()
            assertFalse(ops.watcherActive)
            assertFalse(ops.lockHeld)
        }
    }

    @Test
    fun multicastReleaseFailureRetainsLockUntilRepeatedStopSucceeds() {
        val ops = FakeOps().apply {
            current = FakeNet("wifi0")
            failNextLockRelease = true
        }
        coordinatorTest(ops) { coordinator, _ ->
            coordinator.startAdvertising(localPeer)

            assertFailsWith<IOException> { coordinator.stopAdvertising() }
            assertFalse(ops.watcherActive)
            assertTrue(ops.lockHeld, "failed release must remain owned and retryable")

            coordinator.stopAdvertising()
            assertFalse(ops.lockHeld)
        }
    }

    @Test
    fun cancelledAdvertisingStopCompletesCleanupAndPreservesCancellation() {
        val ops = FakeOps().apply { current = FakeNet("wifi0") }
        coordinatorTest(ops) { coordinator, scope ->
            coordinator.startAdvertising(localPeer)
            val gate = CountDownLatch(1)
            ops.unregisterGate = gate

            val stopper = scope.launch { coordinator.stopAdvertising() }
            awaitBlockingCall(ops.unregisterEntered, "unregisterServiceBlocking")
            stopper.cancel()
            gate.countDown()
            stopper.join()

            assertTrue(stopper.isCancelled, "the caller's CancellationException must survive cleanup")
            assertEquals(1, ops.unregistrations.size)
            assertTrue(ops.created.single().closed)
            assertFalse(ops.lockHeld)
            assertFalse(ops.watcherActive)
        }
    }

    @Test
    fun cancelledDiscoveryStopRemovesListenerWithoutDisruptingAdvertising() {
        val ops = FakeOps().apply { current = FakeNet("wifi0") }
        coordinatorTest(ops) { coordinator, scope ->
            coordinator.startAdvertising(localPeer)
            coordinator.startDiscovery()
            val gate = CountDownLatch(1)
            ops.removeListenerGate = gate

            val stopper = scope.launch { coordinator.stopDiscovery() }
            awaitBlockingCall(ops.removeListenerEntered, "removeListenerBlocking")
            stopper.cancel()
            gate.countDown()
            stopper.join()

            assertTrue(stopper.isCancelled)
            assertEquals(1, ops.listenersRemoved.size)
            assertTrue(ops.closed.isEmpty(), "advertising still owns the shared handle")
            assertTrue(ops.lockHeld)
            assertTrue(ops.watcherActive)
        }
    }

    // ── DSC-13: failed start* cleanup ───────────────────────────────────

    @Test
    fun failedStartAdvertisingReleasesMulticastLockAndClosesHandle() {
        val ops = FakeOps().apply {
            current = FakeNet("wifi0")
            failNextRegister = true
        }
        coordinatorTest(ops) { coordinator, _ ->
            assertFailsWith<IOException> { coordinator.startAdvertising(localPeer) }

            assertFalse(ops.lockHeld, "failed start must not strand the multicast lock (DSC-13)")
            assertEquals(1, ops.created.size)
            assertEquals(1, ops.closed.size, "failed start must close the freshly created handle (DSC-13)")
            assertFalse(ops.watcherActive)

            // Not bricked: the next start succeeds on a fresh handle.
            coordinator.startAdvertising(localPeer)
            assertEquals(2, ops.created.size)
            assertEquals(1, ops.registrations.size)
            assertTrue(ops.lockHeld)
        }
    }

    @Test
    fun failedStartDiscoveryRebuildsTheStillIntendedAdvertisingSide() {
        val ops = FakeOps().apply { current = FakeNet("wifi0") }
        coordinatorTest(ops) { coordinator, _ ->
            coordinator.startAdvertising(localPeer)
            ops.failNextAddListener = true
            assertFailsWith<IOException> { coordinator.startDiscovery() }

            assertTrue(ops.lockHeld, "advertising still active — the lock must be kept")
            assertEquals(1, ops.closed.size, "ambiguous listener add must close its owning handle")
            assertEquals(2, ops.created.size, "advertising must be restored on a fresh handle")
            assertEquals(2, ops.registrations.size)
            assertSame(ops.created.last(), ops.registrations.last().first)
        }
    }

    // ── DSC-3: cancelled create closes the produced handle ─────────────

    @Test
    fun cancelledCreateDuringStartClosesProducedHandleAndReleasesLock() {
        val ops = FakeOps().apply { current = FakeNet("wifi0") }
        val gate = CountDownLatch(1)
        ops.createGate = gate
        coordinatorTest(ops) { coordinator, rebindScope ->
            val starter = rebindScope.launch { coordinator.startDiscovery() }
            awaitCreateEntered(ops)
            starter.cancel()
            gate.countDown()
            starter.join()

            awaitCondition("orphaned handle closed (DSC-3)") {
                ops.created.size == 1 && ops.created[0].closed
            }
            assertEquals(1, ops.closed.size)
            assertFalse(ops.lockHeld, "cancelled start must also release the lock (DSC-13 cleanup)")
        }
    }

    @Test
    fun cancelledRebindCreateClosesProducedHandle() {
        val ops = FakeOps().apply {
            current = FakeNet("wifi0")
            observed = FakeNet("wifi0")
        }
        coordinatorTest(ops) { coordinator, rebindScope ->
            coordinator.startDiscovery()
            awaitCreateEntered(ops) // drain the start-path rendezvous

            ops.observed = FakeNet("wifi1")
            val gate = CountDownLatch(1)
            ops.createGate = gate
            coordinator.scheduleRebind("rotation under cancellation")
            awaitCreateEntered(ops) // rebind create is parked on the gate

            // Cancel the pending rebind job mid-create (the shape of the
            // watcher stopping / a superseding schedule racing the create).
            rebindScope.coroutineContext.cancelChildren()
            gate.countDown()

            awaitCondition("rebind orphan closed (DSC-3)") {
                ops.created.size == 2 && ops.created[1].closed
            }
            // Old handle torn down by the rebind + the orphaned fresh one.
            assertEquals(2, ops.closed.size)
        }
    }

    @Test
    fun cancellationAfterAdvertisingRegistrationCompletesClosesTheOwningHandle() {
        val ops = FakeOps().apply { current = FakeNet("wifi0") }
        val gate = CountDownLatch(1)
        ops.registerGate = gate
        coordinatorTest(ops) { coordinator, scope ->
            val starter = scope.launch { coordinator.startAdvertising(localPeer) }
            awaitBlockingCall(ops.registerEntered, "registerServiceBlocking")

            starter.cancel()
            gate.countDown()
            starter.join()

            awaitCondition("ambiguously registered service handle closed") {
                ops.registrations.size == 1 && ops.created.single().closed
            }
            assertFalse(ops.lockHeld)
            assertFalse(ops.watcherActive)

            ops.registerGate = null
            coordinator.startAdvertising(localPeer)
            assertEquals(2, ops.created.size)
            assertEquals(2, ops.registrations.size)
        }
    }

    @Test
    fun cancellationAfterListenerAddCompletesRebuildsTheOtherLiveIntent() {
        val ops = FakeOps().apply { current = FakeNet("wifi0") }
        coordinatorTest(ops) { coordinator, scope ->
            coordinator.startAdvertising(localPeer)
            val original = ops.created.single()

            val gate = CountDownLatch(1)
            ops.listenerGate = gate
            val starter = scope.launch { coordinator.startDiscovery() }
            awaitBlockingCall(ops.listenerEntered, "addListenerBlocking")
            starter.cancel()
            gate.countDown()
            starter.join()

            awaitCondition("advertising restored after ambiguous listener add") {
                original.closed && ops.registrations.size == 2
            }
            assertEquals(2, ops.created.size)
            assertSame(ops.created.last(), ops.registrations.last().first)
            assertTrue(ops.lockHeld)
            assertTrue(ops.watcherActive)

            ops.listenerGate = null
            coordinator.startDiscovery()
            assertEquals(2, ops.listenersAdded.size)
            assertSame(ops.created.last(), ops.listenersAdded.last().handle)
        }
    }

    // ── AUDIT-2026-06 #5: intent flags vs handles + retry bounds ───────

    @Test
    fun repeatedDiscoveryStartRepairsFailedRebindWithoutDuplicatingListener() {
        val ops = FakeOps().apply {
            current = FakeNet("wifi0")
            observed = FakeNet("wifi0")
        }
        coordinatorTest(ops, retryBaseMillis = 10_000) { coordinator, _ ->
            coordinator.startDiscovery()
            ops.observed = FakeNet("wifi1")
            ops.createFailuresRemaining.set(1)

            coordinator.scheduleRebind("injected failed transaction")
            coordinator.awaitPendingRebindForTest()
            assertEquals(1, ops.listenersAdded.size)

            coordinator.startDiscovery()
            assertEquals(2, ops.listenersAdded.size, "repair must install exactly one fresh listener")
            assertSame(ops.created.last(), ops.listenersAdded.last().handle)
            coordinator.stopDiscovery()
        }
    }

    @Test
    fun repeatedAdvertisingStartRepairsFailedRebindWithoutDuplicateRegistration() {
        val ops = FakeOps().apply {
            current = FakeNet("wifi0")
            observed = FakeNet("wifi0")
        }
        coordinatorTest(ops, retryBaseMillis = 10_000) { coordinator, _ ->
            coordinator.startAdvertising(localPeer)
            ops.observed = FakeNet("wifi1")
            ops.createFailuresRemaining.set(1)

            coordinator.scheduleRebind("injected failed transaction")
            coordinator.awaitPendingRebindForTest()
            assertEquals(1, ops.registrations.size)

            coordinator.startAdvertising(localPeer)
            assertEquals(2, ops.registrations.size, "repair must register exactly one fresh service")
            assertSame(ops.created.last(), ops.registrations.last().first)
            coordinator.stopAdvertising()
        }
    }

    @Test
    fun rebindCreateFailureRetriesWithinBudgetThenRestores() {
        val ops = FakeOps().apply {
            current = FakeNet("wifi0")
            observed = FakeNet("wifi0")
        }
        coordinatorTest(ops) { coordinator, _ ->
            coordinator.startAdvertising(localPeer)
            coordinator.startDiscovery()

            ops.observed = FakeNet("wifi1")
            ops.createFailuresRemaining.set(2)
            coordinator.scheduleRebind("rotation with transient create failures")

            // Intent flags survive the failed-create window (handles null),
            // so the bounded retry restores BOTH sides on a fresh handle.
            awaitCondition("advertising restored after retries") { ops.registrations.size == 2 }
            awaitCondition("discovery restored after retries") { ops.listenersAdded.size == 2 }
            assertEquals(4, ops.createCalls.get(), "1 start + 2 failed rebind creates + 1 success")
            assertTrue(ops.lockHeld, "multicast lock is preserved across rebinds")
        }
    }

    @Test
    fun rebindCreateFailureStopsAtRetryBudgetAndReattemptsOnNextChange() {
        val ops = FakeOps().apply {
            current = FakeNet("wifi0")
            observed = FakeNet("wifi0")
        }
        coordinatorTest(ops, maxAttempts = 3) { coordinator, _ ->
            coordinator.startAdvertising(localPeer)

            ops.observed = FakeNet("wifi1")
            ops.createFailuresRemaining.set(Int.MAX_VALUE / 2)
            coordinator.scheduleRebind("rotation with persistent create failure")

            // Initial rebind create + 3 bounded retries, then the budget stops.
            awaitCondition("retry budget consumed") { ops.createCalls.get() == 5 }
            delay(100)
            assertEquals(5, ops.createCalls.get(), "no create attempts past the retry budget")

            // A genuine new network change re-attempts and succeeds.
            ops.createFailuresRemaining.set(0)
            ops.observed = FakeNet("wifi2")
            coordinator.scheduleRebind("next genuine rotation")
            awaitCondition("advertising restored on the next change") { ops.registrations.size == 2 }
        }
    }

    @Test
    fun exhaustedRetryBudgetIsResetForEveryGenuinelyNewTarget() {
        val ops = FakeOps().apply {
            current = FakeNet("wifi0")
            observed = FakeNet("wifi0")
        }
        coordinatorTest(ops, maxAttempts = 2) { coordinator, _ ->
            coordinator.startAdvertising(localPeer)

            ops.createFailuresRemaining.set(Int.MAX_VALUE / 2)
            ops.observed = FakeNet("wifi1")
            coordinator.scheduleRebind("first failed target")
            awaitCondition("first target consumes initial attempt plus two retries") {
                ops.createCalls.get() == 4
            }

            ops.observed = FakeNet("wifi2")
            coordinator.scheduleRebind("second failed target")
            awaitCondition("second target receives a fresh complete retry budget") {
                ops.createCalls.get() == 7
            }
        }
    }

    @Test
    fun concurrentScheduleRequestsCollapseToOneRebind() {
        val ops = FakeOps().apply {
            current = FakeNet("wifi0")
            observed = FakeNet("wifi0")
        }
        coordinatorTest(ops, debounceMillis = 25) { coordinator, _ ->
            coordinator.startAdvertising(localPeer)
            ops.observed = FakeNet("wifi1")

            coroutineScope {
                val callers = List(32) { index ->
                    launch(Dispatchers.Default) {
                        coordinator.scheduleRebind("concurrent callback $index")
                    }
                }
                callers.forEach { it.join() }
            }
            coordinator.awaitPendingRebindForTest()

            assertEquals(2, ops.createCalls.get(), "all concurrent callbacks must share one rebind")
            assertEquals(2, ops.registrations.size)
        }
    }

    @Test
    fun stopDuringFailedRebindWindowClearsIntentAndHaltsRetry() {
        val ops = FakeOps().apply {
            current = FakeNet("wifi0")
            observed = FakeNet("wifi0")
        }
        coordinatorTest(ops, retryBaseMillis = 400) { coordinator, _ ->
            coordinator.startAdvertising(localPeer)
            coordinator.startDiscovery()

            ops.observed = FakeNet("wifi1")
            ops.createFailuresRemaining.set(Int.MAX_VALUE / 2)
            coordinator.scheduleRebind("rotation entering the failed window")
            awaitCondition("failed rebind create happened") { ops.createCalls.get() == 2 }

            // AUDIT-2026-06 #5 stop semantics: intent cleared even though the
            // handles are already null; retry halted; resources released.
            coordinator.stopAdvertising()
            coordinator.stopDiscovery()
            assertFalse(ops.lockHeld)
            assertFalse(ops.watcherActive)

            delay(900) // well past the 400ms retry backoff
            assertEquals(2, ops.createCalls.get(), "halted retry must not resurrect the stopped transport")
        }
    }

    // ── transactional restoration ─────────────────────────────────────

    @Test
    fun rebindRegisterFailureDoesNotCommitAndSelfRetryRestoresAdvertising() {
        val ops = FakeOps().apply {
            current = FakeNet("wifi0")
            observed = FakeNet("wifi0")
        }
        coordinatorTest(ops) { coordinator, _ ->
            coordinator.startAdvertising(localPeer)

            ops.observed = FakeNet("wifi1")
            ops.failNextRegister = true
            coordinator.scheduleRebind("rotation with restore failure")
            awaitCondition("advertising restored by the transaction retry") {
                ops.registrations.size == 2
            }

            assertEquals(3, ops.createCalls.get(), "start + failed restore + successful retry")
            assertEquals(2, ops.closed.size, "old and partially restored handles must both close")
            assertSame(ops.created.last(), ops.registrations.last().first)
        }
    }

    // ── no-op guards ────────────────────────────────────────────────────

    @Test
    fun rebindSkipsWhenNothingChangedSinceLastBindAndRunsWhenItDid() {
        val net = FakeNet("wifi0")
        val ops = FakeOps().apply {
            current = net
            observed = net
            observedDefault = net
        }
        coordinatorTest(ops) { coordinator, _ ->
            coordinator.startAdvertising(localPeer)
            coordinator.startDiscovery()

            coordinator.scheduleRebind("capability tick — no rotation")
            delay(100)
            assertEquals(1, ops.createCalls.get(), "unchanged networks must skip the rebind")
            assertTrue(ops.closed.isEmpty(), "unchanged networks must not tear the handle down")

            ops.observed = FakeNet("wifi1")
            coordinator.scheduleRebind("genuine rotation")
            awaitCondition("genuine rotation rebinds") { ops.createCalls.get() == 2 }
        }
    }

    @Test
    fun rebindSkipsWhenWatcherIsNotActive() {
        val ops = FakeOps().apply {
            current = FakeNet("wifi0")
            observed = FakeNet("wifi1")
        }
        coordinatorTest(ops) { coordinator, _ ->
            coordinator.scheduleRebind("stray schedule before any start")
            delay(100)
            assertEquals(0, ops.createCalls.get())
            assertTrue(ops.closed.isEmpty())
        }
    }

    // ── refresh rotation plumbing ───────────────────────────────────────

    @Test
    fun refreshRotationCommitsFreshListenerTokenUsedByLaterStop() {
        val ops = FakeOps().apply { current = FakeNet("wifi0") }
        coordinatorTest(ops) { coordinator, _ ->
            coordinator.startDiscovery()
            val original = ops.listenersAdded.single()

            coordinator.refreshDiscovery { handle ->
                assertSame(ops.created.single(), handle)
            }

            val replacement = ops.listenersAdded.last()
            assertEquals(2, ops.listenersAdded.size)
            assertSame(original, ops.listenersRemoved.single())
            assertFalse(original.active, "replaced listener generation must be deactivated")
            assertTrue(replacement.active)

            coordinator.stopDiscovery()
            assertEquals(2, ops.listenersRemoved.size)
            assertSame(replacement, ops.listenersRemoved.last(), "stop must remove the committed token")
            assertFalse(replacement.active)
        }
    }

    @Test
    fun cancellationAfterRefreshListenerAddCompensatesTheFreshToken() {
        val ops = FakeOps().apply { current = FakeNet("wifi0") }
        coordinatorTest(ops) { coordinator, scope ->
            coordinator.startDiscovery()
            awaitBlockingCall(ops.listenerEntered, "initial addListenerBlocking")
            val original = ops.listenersAdded.single()

            val gate = CountDownLatch(1)
            ops.listenerGate = gate
            val refresher = scope.launch { coordinator.refreshDiscovery { } }
            awaitBlockingCall(ops.listenerEntered, "refresh addListenerBlocking")
            refresher.cancel()
            gate.countDown()
            refresher.join()

            assertEquals(
                2,
                ops.listenersAdded.size,
                "created=${ops.created} closed=${ops.closed} removed=${ops.listenersRemoved.size}"
            )
            val ambiguousFresh = ops.listenersAdded.last()
            assertSame(ambiguousFresh, ops.listenersRemoved.single())
            assertFalse(ambiguousFresh.active)
            assertTrue(original.active, "failed rotation must leave the original generation live")

            ops.listenerGate = null
            coordinator.stopDiscovery()
            assertSame(original, ops.listenersRemoved.last())
            assertFalse(original.active)
        }
    }

    @Test
    fun refreshOldListenerCleanupFailureRebuildsOneHealthyListener() {
        val ops = FakeOps().apply { current = FakeNet("wifi0") }
        coordinatorTest(ops) { coordinator, _ ->
            coordinator.startDiscovery()
            val originalHandle = ops.created.single()
            ops.failNextRemoveListener = true

            coordinator.refreshDiscovery { }

            assertTrue(originalHandle.closed)
            assertEquals(2, ops.created.size)
            assertEquals(3, ops.listenersAdded.size, "initial + ambiguous fresh + rebuilt listener")
            assertSame(ops.created.last(), ops.listenersAdded.last().handle)
            assertFalse(ops.listenersAdded[0].active)
            assertFalse(ops.listenersAdded[1].active)
            assertTrue(ops.listenersAdded.last().active)

            coordinator.stopDiscovery()
            assertSame(ops.listenersAdded.last(), ops.listenersRemoved.last())
        }
    }

    @Test
    fun refreshSkipsWhenDiscoveryIsNotLiveIncludingFailedRebindWindow() {
        val ops = FakeOps().apply { current = FakeNet("wifi0") }
        coordinatorTest(ops) { coordinator, _ ->
            var invoked = false
            coordinator.refreshDiscovery { invoked = true }
            assertFalse(invoked, "refresh must skip when no listener is live")

            // Failed-rebind window: listener token nulled → refresh skips too
            // (the refresh() null-handle early-return the AUDIT-2026-06 #5
            // retry exists to compensate for).
            coordinator.startDiscovery()
            ops.observed = FakeNet("wifi1")
            ops.createFailuresRemaining.set(Int.MAX_VALUE / 2)
            coordinator.scheduleRebind("rotation into the failed window")
            // >= 2: the 1ms retry backoff can push the count past 2 between
            // polls; any value >= 2 proves the failed-rebind window is open.
            awaitCondition("failed rebind create happened") { ops.createCalls.get() >= 2 }

            var invokedInWindow = false
            coordinator.refreshDiscovery { invokedInWindow = true }
            assertFalse(invokedInWindow, "refresh must skip in the failed-rebind window")
        }
    }

    // ── AUDIT-2026-07 DSC-1: discovery heartbeat lifecycle (P1-13) ──────

    @Test
    fun heartbeatStartsWithDiscoveryNotAdvertisingAndTicksOnLiveHandle() {
        val ops = FakeOps().apply { current = FakeNet("wifi0") }
        coordinatorTest(ops, heartbeatMillis = 20) { coordinator, _ ->
            coordinator.startAdvertising(localPeer)
            delay(150)
            assertTrue(ops.reemitTicks.isEmpty(), "advertising alone must not start the heartbeat")

            coordinator.startDiscovery()
            awaitCondition("heartbeat ticks while discovery is active") { ops.reemitTicks.size >= 2 }
            val live = ops.created.single()
            assertTrue(
                ops.reemitTicks.all { it === live },
                "every tick must re-emit from the live handle"
            )
        }
    }

    @Test
    fun heartbeatStopsOnStopDiscoveryAndRestartsWithNextStart() {
        val ops = FakeOps().apply { current = FakeNet("wifi0") }
        coordinatorTest(ops, heartbeatMillis = 20) { coordinator, _ ->
            coordinator.startDiscovery()
            awaitCondition("heartbeat is ticking") { ops.reemitTicks.size >= 2 }

            // stopDiscovery cancels the loop under the coordinator lock, so
            // once it returns no tick can be in flight — the count is stable.
            coordinator.stopDiscovery()
            val atStop = ops.reemitTicks.size
            delay(200) // ~10 intervals
            assertEquals(atStop, ops.reemitTicks.size, "no ticks may run after stopDiscovery")

            coordinator.startDiscovery()
            awaitCondition("heartbeat restarts with the next discovery") {
                ops.reemitTicks.size > atStop
            }
        }
    }

    @Test
    fun heartbeatSurvivesRebindMovesToFreshHandleAndSkipsFailedWindow() {
        val ops = FakeOps().apply {
            current = FakeNet("wifi0")
            observed = FakeNet("wifi0")
        }
        coordinatorTest(ops, heartbeatMillis = 20) { coordinator, _ ->
            coordinator.startDiscovery()
            awaitCondition("ticks on the original handle") { ops.reemitTicks.isNotEmpty() }

            // Genuine rotation: the loop survives the rebind and re-emits
            // from the FRESH handle without being restarted.
            ops.observed = FakeNet("wifi1")
            coordinator.scheduleRebind("rotation under heartbeat")
            awaitCondition("tick on the fresh handle after rebind") {
                ops.created.size == 2 && ops.reemitTicks.any { it === ops.created[1] }
            }

            // Failed-rebind window (handle null): ticks skip silently, the
            // loop stays alive.
            ops.observed = FakeNet("wifi2")
            ops.createFailuresRemaining.set(Int.MAX_VALUE / 2)
            coordinator.scheduleRebind("rotation into the failed window")
            awaitCondition("failed-rebind window open") { ops.createCalls.get() >= 3 }
            awaitCondition("retry budget consumed") {
                ops.createFailuresRemaining.get() < Int.MAX_VALUE / 2 - 5
            }
            val duringWindow = ops.reemitTicks.size
            delay(200)
            assertEquals(
                duringWindow,
                ops.reemitTicks.size,
                "ticks must skip while no handle is live"
            )

            // Recovery: the next genuine change restores the handle and the
            // same loop resumes ticking on it.
            ops.createFailuresRemaining.set(0)
            ops.observed = FakeNet("wifi3")
            coordinator.scheduleRebind("recovery rotation")
            awaitCondition("ticks resume on the recovered handle") {
                val last = ops.created.lastOrNull()
                last != null && !last.closed && ops.reemitTicks.any { it === last }
            }
        }
    }

    @Test
    fun heartbeatTickFailureKeepsLoopAliveAndNextTicksRun() {
        val ops = FakeOps().apply {
            current = FakeNet("wifi0")
            failNextReemit = true
        }
        coordinatorTest(ops, heartbeatMillis = 20) { coordinator, _ ->
            coordinator.startDiscovery()
            awaitCondition("ticks continue after an injected tick failure") {
                ops.reemitTicks.size >= 2
            }
            assertFalse(ops.failNextReemit, "the injected failure must have fired")
        }
    }

    /**
     * Pins the DSC-1 interval contract: the shared JVM/Android heartbeat
     * cadence matches the iOS re-announce interval (5 s) and stays comfortably
     * below PeerRegistry's staleness eviction horizon (15 s — the p2p-core
     * internal `DEFAULT_STALE_TIMEOUT_MS`, not referencable across modules,
     * hence the numeric pin).
     */
    @Test
    fun heartbeatIntervalStaysComfortablyBelowTheEvictionHorizon() {
        assertEquals(5_000L, LanConstants.PEER_REANNOUNCE_INTERVAL_MS)
        assertTrue(LanConstants.PEER_REANNOUNCE_INTERVAL_MS * 2 < 15_000L)
    }
}
