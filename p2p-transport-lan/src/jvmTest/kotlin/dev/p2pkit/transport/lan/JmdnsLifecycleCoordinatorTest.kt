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
 * 2026-07 P1-14: automated contract for the Android JmDNS rebind machinery —
 * the state machine extracted verbatim into [JmdnsLifecycleCoordinator]
 * (commonMain seam) precisely so this jvm-style unit suite can exist
 * (`androidMain` has no automated test path in this module; the
 * jvm-pins-the-shared-shape convention follows `HostSelectorTest`).
 *
 * Pinned here, per the coverage row:
 *   - intent flags vs live handles (AUDIT-2026-06 #5): a create failure mid
 *     rebind must not brick the transport; stop* during the failed-rebind
 *     window clears intent and halts the retry;
 *   - bounded create-retry (budget respected, re-attempt on the next change);
 *   - restore-failure repair: a dropped re-register is repaired by the next
 *     rebind (current no-immediate-retry disposition pinned as-is, DSC-4);
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

    private class FakeListenerToken(val handle: FakeHandle)

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

        /** One element offered per [createHandleBlocking] entry — a rendezvous for tests. */
        val createEntered = LinkedBlockingQueue<Unit>()

        @Volatile
        var failNextRegister = false

        @Volatile
        var failNextAddListener = false

        /** Handle passed to each heartbeat tick (AUDIT-2026-07 DSC-1). */
        val reemitTicks = CopyOnWriteArrayList<FakeHandle>()

        @Volatile
        var failNextReemit = false

        override fun createHandleBlocking(target: FakeNet?, forRebind: Boolean): FakeHandle {
            createCalls.incrementAndGet()
            createEntered.put(Unit)
            createGate?.let {
                if (!it.await(5, TimeUnit.SECONDS)) throw IOException("createGate never released")
            }
            if (createFailuresRemaining.get() > 0) {
                createFailuresRemaining.decrementAndGet()
                throw IOException("injected create failure")
            }
            val handle = FakeHandle(createCalls.get())
            created += handle
            return handle
        }

        override fun closeHandleBlocking(handle: FakeHandle) {
            handle.closed = true
            closed += handle
        }

        override fun registerServiceBlocking(handle: FakeHandle, localPeer: LocalPeerInfo): Any {
            if (failNextRegister) {
                failNextRegister = false
                throw IOException("injected register failure")
            }
            registrations += handle to localPeer
            return handle to localPeer
        }

        override fun unregisterServiceBlocking(handle: FakeHandle, token: Any) {
            unregistrations += token
        }

        override fun addListenerBlocking(handle: FakeHandle): Any {
            if (failNextAddListener) {
                failNextAddListener = false
                throw IOException("injected addListener failure")
            }
            val token = FakeListenerToken(handle)
            listenersAdded += token
            return token
        }

        override fun removeListenerBlocking(handle: FakeHandle, token: Any) {
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
            lockHeld = false
        }

        override fun startNetworkWatcher() {
            watcherActive = true
        }

        override fun stopNetworkWatcher() {
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
            assertEquals(1, ops.closed.size, "idle close must release the shared handle")
            assertFalse(ops.lockHeld)
            assertFalse(ops.watcherActive)
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
    fun failedStartDiscoveryKeepsSharedResourcesWhileAdvertisingActive() {
        val ops = FakeOps().apply { current = FakeNet("wifi0") }
        coordinatorTest(ops) { coordinator, _ ->
            coordinator.startAdvertising(localPeer)
            ops.failNextAddListener = true
            assertFailsWith<IOException> { coordinator.startDiscovery() }

            assertTrue(ops.lockHeld, "advertising still active — the lock must be kept (DSC-13 idle guard)")
            assertTrue(ops.closed.isEmpty(), "advertising still active — the shared handle must be kept")
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

    // ── AUDIT-2026-06 #5: intent flags vs handles + retry bounds ───────

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

    // ── restore-failure repair (DSC-4 disposition pinned) ──────────────

    @Test
    fun rebindRegisterFailureIsDroppedNowAndRepairedByNextRebind() {
        val ops = FakeOps().apply {
            current = FakeNet("wifi0")
            observed = FakeNet("wifi0")
        }
        coordinatorTest(ops) { coordinator, _ ->
            coordinator.startAdvertising(localPeer)

            ops.observed = FakeNet("wifi1")
            ops.failNextRegister = true
            coordinator.scheduleRebind("rotation with restore failure")
            awaitCondition("fresh handle created") { ops.createCalls.get() == 2 }
            delay(100)
            // Pinned current behavior (DSC-4 catalogued): the dropped
            // re-register is not retried by itself...
            assertEquals(1, ops.registrations.size, "restore failure is dropped without an immediate retry")

            // ...but intent survives, so the next rotation repairs it.
            ops.observed = FakeNet("wifi2")
            coordinator.scheduleRebind("repairing rotation")
            awaitCondition("advertising repaired on the next rebind") { ops.registrations.size == 2 }
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
            val replacement = FakeListenerToken(ops.created.single())

            coordinator.refreshDiscovery { handle, old, commit ->
                assertSame(ops.created.single(), handle)
                assertSame(original, old)
                commit(replacement)
            }

            coordinator.stopDiscovery()
            assertEquals(1, ops.listenersRemoved.size)
            assertSame(replacement, ops.listenersRemoved.single(), "stop must remove the committed token")
        }
    }

    @Test
    fun refreshSkipsWhenDiscoveryIsNotLiveIncludingFailedRebindWindow() {
        val ops = FakeOps().apply { current = FakeNet("wifi0") }
        coordinatorTest(ops) { coordinator, _ ->
            var invoked = false
            coordinator.refreshDiscovery { _, _, _ -> invoked = true }
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
            coordinator.refreshDiscovery { _, _, _ -> invokedInWindow = true }
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
