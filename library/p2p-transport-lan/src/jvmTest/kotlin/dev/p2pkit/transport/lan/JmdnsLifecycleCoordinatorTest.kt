package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.LocalPeerInfo
import java.io.IOException
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import javax.jmdns.ServiceInfo
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.asCoroutineDispatcher
import kotlinx.coroutines.cancel
import kotlinx.coroutines.cancelChildren
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlin.coroutines.CoroutineContext
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
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
@OptIn(ExperimentalCoroutinesApi::class)
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
        var active = false
    }

    private class FakeServiceToken(val localPeer: LocalPeerInfo, val info: ServiceInfo?)

    private class FakeWatcherLease {
        @Volatile
        var active = true
    }

    private class FakeOps(
        private val serviceInfoFactory: ((LocalPeerInfo) -> ServiceInfo)? = null
    ) : JmdnsLifecycleOps<FakeNet, FakeHandle> {
        val createCalls = AtomicInteger(0)
        val created = CopyOnWriteArrayList<FakeHandle>()
        val createdTargets = CopyOnWriteArrayList<FakeNet?>()

        @Volatile
        var actualCreatedNetwork: FakeNet? = null
        val closeAttempts = AtomicInteger(0)
        val closed = CopyOnWriteArrayList<FakeHandle>()
        val registrations = CopyOnWriteArrayList<Pair<FakeHandle, LocalPeerInfo>>()
        val serviceInfos = CopyOnWriteArrayList<ServiceInfo>()
        val unregistrations = CopyOnWriteArrayList<Any>()
        val listenersAdded = CopyOnWriteArrayList<FakeListenerToken>()
        val listenersActivated = CopyOnWriteArrayList<FakeListenerToken>()
        val listenersRemoved = CopyOnWriteArrayList<Any>()
        val listenerTransitions = CopyOnWriteArrayList<Pair<String, FakeListenerToken>>()
        val multicastReleaseAttempts = AtomicInteger(0)
        val multicastReleases = AtomicInteger(0)
        val watcherStopAttempts = AtomicInteger(0)
        val watcherLeases = CopyOnWriteArrayList<FakeWatcherLease>()
        val warnings = CopyOnWriteArrayList<Pair<String, Throwable?>>()

        private var watcherLease: FakeWatcherLease? = null

        @Volatile
        var lockHeld = false

        @Volatile
        var watcherActive = false

        @Volatile
        var watcherBoundNetwork: FakeNet? = null

        @Volatile
        var current: FakeNet? = null

        @Volatile
        var observed: FakeNet? = null

        @Volatile
        var observedDefault: FakeNet? = null

        @Volatile
        var observedNetworkGate: CountDownLatch? = null

        val observedNetworkEntered = LinkedBlockingQueue<Unit>()

        @Volatile
        var currentNetworkThread: String? = null

        @Volatile
        var observedNetworkThread: String? = null

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

        @Volatile
        var closeGate: CountDownLatch? = null

        /** One element offered per [createHandleBlocking] entry — a rendezvous for tests. */
        val createEntered = LinkedBlockingQueue<Unit>()
        val registerEntered = LinkedBlockingQueue<Unit>()
        val listenerEntered = LinkedBlockingQueue<Unit>()
        val unregisterEntered = LinkedBlockingQueue<Unit>()
        val removeListenerEntered = LinkedBlockingQueue<Unit>()
        val closeEntered = LinkedBlockingQueue<Unit>()

        @Volatile
        var failNextRegister = false

        @Volatile
        var failNextServiceTokenCreation = false

        @Volatile
        var failNextAddListener = false

        @Volatile
        var failNextListenerTokenCreation = false

        @Volatile
        var failNextUnregister = false

        @Volatile
        var failNextRemoveListener = false

        @Volatile
        var failNextWatcherStop = false

        @Volatile
        var failNextLockRelease = false

        @Volatile
        var failNextLockAcquire = false

        @Volatile
        var failNextWatcherStart = false

        val closeFailuresRemaining = AtomicInteger(0)

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

        override fun createHandleBlocking(
            target: FakeNet?,
            forRebind: Boolean
        ): JmdnsHandleBinding<FakeNet, FakeHandle> {
            createCalls.incrementAndGet()
            createdTargets += target
            createEntered.put(Unit)
            createGate?.let { awaitNonCancellableGate(it, "createGate") }
            if (createFailuresRemaining.get() > 0) {
                createFailuresRemaining.decrementAndGet()
                throw IOException("injected create failure")
            }
            val handle = FakeHandle(createCalls.get())
            created += handle
            return JmdnsHandleBinding(actualCreatedNetwork ?: target, handle)
        }

        override fun closeHandleBlocking(handle: FakeHandle) {
            closeAttempts.incrementAndGet()
            closeEntered.put(Unit)
            closeGate?.let { awaitNonCancellableGate(it, "closeGate") }
            if (closeFailuresRemaining.get() > 0) {
                closeFailuresRemaining.decrementAndGet()
                throw IOException("injected close failure")
            }
            handle.closed = true
            closed += handle
        }

        override fun createServiceToken(localPeer: LocalPeerInfo): Any {
            if (failNextServiceTokenCreation) {
                failNextServiceTokenCreation = false
                throw IOException("injected service-token creation failure")
            }
            return FakeServiceToken(localPeer, serviceInfoFactory?.invoke(localPeer))
        }

        override fun registerServiceBlocking(handle: FakeHandle, token: Any) {
            registerEntered.put(Unit)
            registerGate?.let { awaitNonCancellableGate(it, "registerGate") }
            if (failNextRegister) {
                failNextRegister = false
                throw IOException("injected register failure")
            }
            val service = token as FakeServiceToken
            registrations += handle to service.localPeer
            service.info?.let(serviceInfos::add)
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

        override fun createListenerToken(handle: FakeHandle): Any {
            if (failNextListenerTokenCreation) {
                failNextListenerTokenCreation = false
                throw IOException("injected listener-token creation failure")
            }
            return FakeListenerToken(handle)
        }

        override fun addListenerBlocking(handle: FakeHandle, token: Any) {
            listenerEntered.put(Unit)
            listenerGate?.let { awaitNonCancellableGate(it, "listenerGate") }
            if (failNextAddListener) {
                failNextAddListener = false
                throw IOException("injected addListener failure")
            }
            val listener = token as FakeListenerToken
            listenersAdded += listener
            listenerTransitions += "add" to listener
        }

        override fun activateListenerBlocking(token: Any) {
            val listener = token as FakeListenerToken
            listener.active = true
            listenersActivated += listener
            listenerTransitions += "activate" to listener
        }

        override fun deactivateListenerToken(token: Any) {
            val listener = token as FakeListenerToken
            listener.active = false
            listenerTransitions += "deactivate" to listener
        }

        override fun removeListenerBlocking(handle: FakeHandle, token: Any) {
            removeListenerEntered.put(Unit)
            removeListenerGate?.let { awaitNonCancellableGate(it, "removeListenerGate") }
            if (failNextRemoveListener) {
                failNextRemoveListener = false
                throw IOException("injected listener removal failure")
            }
            val listener = token as FakeListenerToken
            listenersRemoved += listener
            listenerTransitions += "remove" to listener
        }

        override fun currentNetwork(): FakeNet? {
            currentNetworkThread = Thread.currentThread().name
            return current
        }

        override fun observedNetwork(): FakeNet? {
            observedNetworkThread = Thread.currentThread().name
            observedNetworkEntered.put(Unit)
            observedNetworkGate?.let { awaitNonCancellableGate(it, "observedNetworkGate") }
            return observed
        }

        override fun observedDefaultNetwork(): FakeNet? = observedDefault

        override fun isWatcherActive(): Boolean = watcherActive

        // Idempotence mirrors the transport-side acquireMulticastLockIfNeeded /
        // release helpers, which key on their own held-lock field.
        override fun acquireMulticastLock() {
            lockHeld = true
            if (failNextLockAcquire) {
                failNextLockAcquire = false
                throw IOException("injected multicast acquire failure")
            }
        }

        override fun releaseMulticastLock() {
            multicastReleaseAttempts.incrementAndGet()
            if (failNextLockRelease) {
                failNextLockRelease = false
                throw IOException("injected multicast release failure")
            }
            if (lockHeld) multicastReleases.incrementAndGet()
            lockHeld = false
        }

        override fun startNetworkWatcher(boundNetwork: FakeNet?) {
            // Mirror Android's distinction between retained native callback
            // ownership and retired publication rights after unregister failure.
            if (watcherLease?.active == false) stopNetworkWatcher()
            if (watcherLease == null) {
                watcherLease = FakeWatcherLease().also { watcherLeases += it }
            }
            watcherBoundNetwork = boundNetwork
            watcherActive = true
            if (failNextWatcherStart) {
                failNextWatcherStart = false
                throw IOException("injected watcher start failure")
            }
        }

        override fun stopNetworkWatcher() {
            watcherStopAttempts.incrementAndGet()
            watcherLease?.active = false
            if (failNextWatcherStop) {
                failNextWatcherStop = false
                throw IOException("injected watcher cleanup failure")
            }
            watcherActive = false
            watcherBoundNetwork = null
            watcherLease = null
        }

        override fun logDebug(message: String) = Unit

        override fun logWarn(message: String, error: Throwable?) {
            warnings += message to error
        }
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
        ioContext: CoroutineContext = Dispatchers.IO,
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
                ioContext = ioContext,
                rebindDebounceMillis = debounceMillis,
                rebindRetryBaseDelayMillis = retryBaseMillis,
                rebindRetryMaxAttempts = maxAttempts
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

    private fun TestScope.virtualCoordinator(ops: FakeOps) = JmdnsLifecycleCoordinator(
        ops = ops,
        rebindScope = backgroundScope,
        ioContext = UnconfinedTestDispatcher(testScheduler),
        rebindDebounceMillis = 10,
        rebindRetryBaseDelayMillis = 100,
        rebindRetryMaxAttempts = 2
    )

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
        val wifi = FakeNet("wifi0")
        val ops = FakeOps().apply { current = wifi }
        coordinatorTest(ops) { coordinator, _ ->
            coordinator.startAdvertising(localPeer)
            coordinator.startDiscovery()

            assertEquals(1, ops.createCalls.get(), "advertise + discover must share one handle")
            assertEquals(1, ops.registrations.size)
            assertEquals(1, ops.listenersAdded.size)
            val listener = ops.listenersAdded.single()
            assertTrue(ops.lockHeld)
            assertTrue(ops.watcherActive)
            assertSame(wifi, ops.watcherBoundNetwork)

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
            assertEquals(null, ops.watcherBoundNetwork)
        }
    }

    @Test
    fun watcherReceivesExactTargetResolvedByHandleCreation() {
        val resolved = FakeNet("wifi-resolved-during-create")
        val ops = FakeOps().apply {
            current = null
            actualCreatedNetwork = resolved
        }
        coordinatorTest(ops) { coordinator, _ ->
            coordinator.startAdvertising(localPeer)

            assertEquals(listOf<FakeNet?>(null), ops.createdTargets)
            assertSame(resolved, ops.watcherBoundNetwork)

            coordinator.stopAdvertising()
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
        for (advertising in listOf(true, false)) {
            val ops = FakeOps().apply { current = FakeNet("wifi0") }
            coordinatorTest(ops) { coordinator, _ ->
                if (advertising) coordinator.startAdvertising(localPeer) else coordinator.startDiscovery()
                suspend fun stop() {
                    if (advertising) coordinator.stopAdvertising() else coordinator.stopDiscovery()
                }
                val original = ops.created.single()
                ops.failNextUnregister = advertising
                ops.failNextRemoveListener = !advertising
                ops.closeFailuresRemaining.set(1)

                try {
                    assertFailsWith<IOException> { stop() }
                    assertFalse(original.closed)
                    assertEquals(1, ops.closeAttempts.get(), "do not repeat native close in one stop")
                    assertTrue(ops.lockHeld, "live handle keeps multicast ownership after failed close")
                    assertFalse(ops.watcherActive, "watcher retirement does not depend on native close")
                    assertFalse(ops.watcherLeases.single().active)
                    assertEquals(1, ops.watcherStopAttempts.get())
                    assertEquals(0, ops.multicastReleaseAttempts.get())

                    stop()
                    assertTrue(original.closed)
                    assertEquals(2, ops.closeAttempts.get())
                    assertEquals(1, ops.closed.size)
                    assertFalse(ops.lockHeld)
                    assertFalse(ops.watcherActive)
                    assertEquals(1, ops.watcherStopAttempts.get(), "retired watcher needs no second stop")
                    assertEquals(1, ops.multicastReleases.get())
                } finally {
                    stop()
                }
            }
        }
    }

    @Test
    fun watcherCleanupFailureStillReleasesMulticastOnEitherStop() {
        for (advertising in listOf(true, false)) {
            val ops = FakeOps().apply {
                current = FakeNet("wifi0")
                failNextWatcherStop = true
            }
            coordinatorTest(ops) { coordinator, _ ->
                if (advertising) coordinator.startAdvertising(localPeer) else coordinator.startDiscovery()
                suspend fun stop() {
                    if (advertising) coordinator.stopAdvertising() else coordinator.stopDiscovery()
                }
                try {
                    assertFailsWith<IOException> { stop() }
                    assertTrue(ops.watcherActive, "failed callback cleanup must remain owned")
                    assertFalse(ops.lockHeld, "a retired watcher must not retain the independent multicast lock")
                    assertEquals(1, ops.multicastReleaseAttempts.get())
                    assertEquals(1, ops.multicastReleases.get())

                    stop()
                    assertFalse(ops.watcherActive)
                    assertFalse(ops.lockHeld)
                    assertEquals(1, ops.multicastReleases.get(), "repeated stop must not release twice")
                } finally {
                    stop()
                }
            }
        }
    }

    @Test
    fun idleWatcherFailureCancelsPendingDebounce() = runTest {
        val ops = FakeOps().apply { current = FakeNet("wifi0") }
        val coordinator = virtualCoordinator(ops)
        try {
            coordinator.startAdvertising(localPeer)
            coordinator.scheduleRebind("pending rotation before watcher cleanup failure")
            runCurrent()
            val pending = backgroundScope.coroutineContext[Job]!!.children.single()
            assertTrue(pending.isActive)
            ops.failNextWatcherStop = true

            assertFailsWith<IOException> { coordinator.stopAdvertising() }
            assertTrue(pending.isCancelled, "watcher failure must not retain the debounced job")
            coordinator.awaitPendingRebindForTest()
            advanceTimeBy(1_000)
            runCurrent()
            assertTrue(ops.observedNetworkEntered.isEmpty(), "cancelled work must not probe the network")
            assertEquals(1, ops.createCalls.get())
            assertFalse(ops.lockHeld)
        } finally {
            coordinator.stopAdvertising()
        }
    }

    @Test
    fun idleWatcherFailureCancelsPendingRetry() = runTest {
        val ops = FakeOps().apply {
            current = FakeNet("wifi0")
            observed = FakeNet("wifi1")
        }
        val coordinator = virtualCoordinator(ops)
        try {
            coordinator.startDiscovery()
            ops.createFailuresRemaining.set(1)
            coordinator.scheduleRebind("rotation that needs a self-retry")
            runCurrent()
            advanceTimeBy(10)
            runCurrent()
            assertEquals(2, ops.createCalls.get())
            val retry = backgroundScope.coroutineContext[Job]!!.children.single()
            assertTrue(retry.isActive)
            ops.failNextWatcherStop = true

            assertFailsWith<IOException> { coordinator.stopDiscovery() }
            assertTrue(retry.isCancelled, "watcher failure must not retain the retry timer")
            val probes = ops.observedNetworkEntered.size
            advanceTimeBy(1_000)
            runCurrent()
            assertEquals(probes, ops.observedNetworkEntered.size)
            assertEquals(2, ops.createCalls.get())
            assertFalse(ops.lockHeld)
        } finally {
            coordinator.stopDiscovery()
        }
    }

    @Test
    fun absentWatcherStillCancelsPendingWorkAtIdle() = runTest {
        val ops = FakeOps().apply { current = FakeNet("wifi0") }
        val coordinator = virtualCoordinator(ops)
        try {
            coordinator.startDiscovery()
            coordinator.scheduleRebind("rotation queued before platform watcher disappeared")
            runCurrent()
            val pending = backgroundScope.coroutineContext[Job]!!.children.single()
            ops.watcherActive = false

            coordinator.stopDiscovery()
            assertTrue(pending.isCancelled, "no native watcher does not imply no coordinator work")
            advanceTimeBy(1_000)
            runCurrent()
            assertTrue(ops.observedNetworkEntered.isEmpty())
            assertFalse(ops.lockHeld)
        } finally {
            coordinator.stopDiscovery()
        }
    }

    @Test
    fun closeFailureRetiresIdleWatcherAndCancelsWorkWithoutReleasingLiveHandle() = runTest {
        for (advertising in listOf(true, false)) {
            val ops = FakeOps().apply { current = FakeNet("wifi0") }
            val coordinator = virtualCoordinator(ops)
            suspend fun stop() {
                if (advertising) coordinator.stopAdvertising() else coordinator.stopDiscovery()
            }
            try {
                if (advertising) coordinator.startAdvertising(localPeer) else coordinator.startDiscovery()
                val lease = ops.watcherLeases.single()
                coordinator.scheduleRebind("pending work before failed native close", admit = { lease.active })
                runCurrent()
                val pending = backgroundScope.coroutineContext[Job]!!.children.single()
                ops.closeFailuresRemaining.set(1)

                assertFailsWith<IOException> { stop() }
                assertTrue(pending.isCancelled, "close failure must not leave queued idle work")
                assertFalse(ops.created.single().closed)
                assertFalse(ops.watcherActive, "idle watchers must retire despite failed handle close")
                assertFalse(lease.active)
                assertEquals(1, ops.watcherStopAttempts.get())
                assertTrue(ops.lockHeld, "do not release multicast while a native handle is still owned")
                assertEquals(0, ops.multicastReleaseAttempts.get())

                coordinator.scheduleRebind("queued callback delivered after idle stop", admit = { lease.active })
                runCurrent()
                advanceTimeBy(1_000)
                runCurrent()
                assertTrue(ops.observedNetworkEntered.isEmpty(), "retired callbacks must not enqueue new probes")
                assertEquals(1, ops.createCalls.get())

                stop()
                assertTrue(ops.created.single().closed)
                assertFalse(ops.watcherActive)
                assertFalse(ops.lockHeld)
                assertEquals(2, ops.closeAttempts.get())
                assertEquals(1, ops.closed.size)
                assertEquals(1, ops.watcherStopAttempts.get())
                assertEquals(1, ops.multicastReleases.get())
                stop()
                assertEquals(2, ops.closeAttempts.get())
                assertEquals(1, ops.multicastReleases.get(), "repeated idle stop must not double-release")
            } finally {
                stop()
            }
        }
    }

    @Test
    fun closeAndWatcherFailuresRetirePublicationAndRetryOwnedResources() = runTest {
        for (advertising in listOf(true, false)) {
            val ops = FakeOps().apply { current = FakeNet("wifi0") }
            val coordinator = virtualCoordinator(ops)
            suspend fun start() {
                if (advertising) coordinator.startAdvertising(localPeer) else coordinator.startDiscovery()
            }
            suspend fun stop() {
                if (advertising) coordinator.stopAdvertising() else coordinator.stopDiscovery()
            }
            try {
                start()
                val retired = ops.watcherLeases.single()
                ops.closeFailuresRemaining.set(1)
                ops.failNextWatcherStop = true

                val failure = assertFailsWith<IOException> { stop() }
                assertEquals("injected close failure", failure.message)
                assertEquals(
                    listOf("injected watcher cleanup failure"), failure.suppressedExceptions.map { it.message }
                )
                assertTrue(ops.watcherActive, "failed native unregistration must remain owned")
                assertFalse(retired.active, "native ownership must not preserve callback publication rights")
                assertFalse(ops.created.single().closed)
                assertTrue(ops.lockHeld)
                assertEquals(1, ops.closeAttempts.get())
                assertEquals(1, ops.watcherStopAttempts.get())
                assertEquals(0, ops.multicastReleaseAttempts.get())
                coordinator.scheduleRebind(
                    "retired callback with native ownership retained", admit = { retired.active }
                )
                runCurrent()
                advanceTimeBy(1_000)
                runCurrent()
                assertTrue(ops.observedNetworkEntered.isEmpty())

                stop()
                assertTrue(ops.created.single().closed)
                assertFalse(ops.watcherActive)
                assertFalse(ops.lockHeld)
                assertEquals(2, ops.closeAttempts.get())
                assertEquals(2, ops.watcherStopAttempts.get())
                assertEquals(1, ops.multicastReleases.get())

                start()
                assertTrue(ops.watcherLeases.last().active)
                assertFalse(retired.active, "restart must never revive the retired lease")
                assertEquals(2, ops.watcherLeases.size)
                coordinator.scheduleRebind("old callback delivered after restart", admit = { retired.active })
                runCurrent()
                advanceTimeBy(1_000)
                runCurrent()
                assertTrue(ops.observedNetworkEntered.isEmpty())
                assertEquals(2, ops.createCalls.get(), "stale callback must not replace the new binding")
            } finally {
                ops.failNextWatcherStop = false
                stop()
            }
            assertEquals(2, ops.multicastReleases.get())
        }
    }

    @Test
    fun failedStartRetiresWatcherEvenWhenRollbackHandleCloseFails() = runTest {
        for (advertising in listOf(true, false)) {
            val ops = FakeOps().apply {
                current = FakeNet("wifi0")
                failNextWatcherStart = true
                closeFailuresRemaining.set(1)
            }
            val coordinator = virtualCoordinator(ops)
            suspend fun stop() {
                if (advertising) coordinator.stopAdvertising() else coordinator.stopDiscovery()
            }
            try {
                val failure = assertFailsWith<IOException> {
                    if (advertising) coordinator.startAdvertising(localPeer) else coordinator.startDiscovery()
                }
                assertEquals("injected watcher start failure", failure.message)
                assertEquals(listOf("injected close failure"), failure.suppressedExceptions.map { it.message })
                val lease = ops.watcherLeases.single()
                assertFalse(lease.active)
                assertFalse(ops.watcherActive)
                assertEquals(1, ops.watcherStopAttempts.get())
                assertFalse(ops.created.single().closed)
                assertTrue(ops.lockHeld)
                assertEquals(0, ops.multicastReleaseAttempts.get())
                coordinator.scheduleRebind("callback after failed start rollback", admit = { lease.active })
                runCurrent()
                advanceTimeBy(1_000)
                runCurrent()
                assertTrue(ops.observedNetworkEntered.isEmpty())

                stop()
                assertTrue(ops.created.single().closed)
                assertEquals(2, ops.closeAttempts.get())
                assertEquals(1, ops.watcherStopAttempts.get())
                assertEquals(1, ops.multicastReleases.get())
                assertFalse(ops.lockHeld)
            } finally {
                stop()
            }
        }
    }

    @Test
    fun idleCleanupAggregatesWatcherAndLockFailuresAndRetriesEachResource() {
        val ops = FakeOps().apply { current = FakeNet("wifi0") }
        coordinatorTest(ops) { coordinator, _ ->
            coordinator.startAdvertising(localPeer)
            ops.failNextWatcherStop = true
            ops.failNextLockRelease = true
            try {
                val failure = assertFailsWith<IOException> { coordinator.stopAdvertising() }
                assertEquals("injected watcher cleanup failure", failure.message)
                assertEquals(
                    listOf("injected multicast release failure"), failure.suppressedExceptions.map { it.message }
                )
                assertEquals(1, ops.multicastReleaseAttempts.get(), "independent release must be attempted")
                assertTrue(ops.watcherActive)
                assertTrue(ops.lockHeld)

                coordinator.stopAdvertising()
                assertEquals(2, ops.watcherStopAttempts.get())
                assertEquals(2, ops.multicastReleaseAttempts.get())
                assertEquals(1, ops.multicastReleases.get())
                assertFalse(ops.watcherActive)
                assertFalse(ops.lockHeld)
            } finally {
                ops.failNextLockRelease = false
                coordinator.stopAdvertising()
            }
        }
    }

    @Test
    fun failedStartCleanupAttemptsMulticastReleaseAfterWatcherFailure() {
        val ops = FakeOps().apply {
            current = FakeNet("wifi0")
            failNextWatcherStart = true
            failNextWatcherStop = true
        }
        coordinatorTest(ops) { coordinator, _ ->
            try {
                val failure = assertFailsWith<IOException> { coordinator.startDiscovery() }
                assertEquals("injected watcher start failure", failure.message)
                assertTrue(ops.created.single().closed)
                assertTrue(ops.watcherActive, "unreleased callback remains owned for retry")
                assertFalse(ops.lockHeld, "failed-start cleanup must also isolate the multicast release")
                assertEquals(
                    listOf("injected watcher cleanup failure"), failure.suppressedExceptions.map { it.message }
                )
                assertTrue(ops.warnings.any { it.second?.message == "injected watcher cleanup failure" })
            } finally {
                coordinator.stopDiscovery()
            }
        }
    }

    @Test
    fun cancelledStopPreservesCancellationAfterWatcherFailure() {
        val ops = FakeOps().apply { current = FakeNet("wifi0") }
        coordinatorTest(ops) { coordinator, scope ->
            coordinator.startAdvertising(localPeer)
            val gate = CountDownLatch(1)
            ops.unregisterGate = gate
            ops.failNextWatcherStop = true
            val outcome = CompletableDeferred<Throwable>()
            val stopper = scope.launch {
                try {
                    coordinator.stopAdvertising()
                    outcome.complete(AssertionError("cancelled stop unexpectedly succeeded"))
                } catch (failure: Throwable) {
                    outcome.complete(failure)
                }
            }
            try {
                awaitBlockingCall(ops.unregisterEntered, "unregisterServiceBlocking")
                stopper.cancel()
                gate.countDown()
                stopper.join()

                val failure = assertIs<CancellationException>(withTimeout(5_000) { outcome.await() })
                assertEquals(
                    listOf("injected watcher cleanup failure"), failure.suppressedExceptions.map { it.message }
                )
                assertTrue(ops.created.single().closed)
                assertTrue(ops.watcherActive)
                assertFalse(ops.lockHeld)
            } finally {
                gate.countDown()
                stopper.join()
                coordinator.stopAdvertising()
            }
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

    @Test
    fun serviceTokenCreationFailureClosesHandleAndReleasesLock() {
        val ops = FakeOps().apply {
            current = FakeNet("wifi0")
            failNextServiceTokenCreation = true
        }
        coordinatorTest(ops) { coordinator, _ ->
            assertFailsWith<IOException> { coordinator.startAdvertising(localPeer) }

            assertEquals(1, ops.created.size)
            assertTrue(ops.created.single().closed)
            assertFalse(ops.lockHeld)
            assertFalse(ops.watcherActive)

            coordinator.startAdvertising(localPeer)
            assertEquals(2, ops.created.size)
            assertEquals(1, ops.registrations.size)
        }
    }

    @Test
    fun listenerTokenCreationFailureRestoresExistingAdvertising() {
        val ops = FakeOps().apply { current = FakeNet("wifi0") }
        coordinatorTest(ops) { coordinator, _ ->
            coordinator.startAdvertising(localPeer)
            val original = ops.created.single()
            ops.failNextListenerTokenCreation = true

            assertFailsWith<IOException> { coordinator.startDiscovery() }

            assertTrue(original.closed)
            assertEquals(2, ops.created.size)
            assertEquals(2, ops.registrations.size, "advertising must be restored")
            assertTrue(ops.listenersAdded.isEmpty())
            assertTrue(ops.lockHeld)
            assertTrue(ops.watcherActive)
        }
    }

    @Test
    fun partialMulticastAcquireFailureIsRolledBack() {
        val ops = FakeOps().apply {
            current = FakeNet("wifi0")
            failNextLockAcquire = true
        }
        coordinatorTest(ops) { coordinator, _ ->
            assertFailsWith<IOException> { coordinator.startDiscovery() }

            assertFalse(ops.lockHeld)
            assertTrue(ops.created.isEmpty())
            assertFalse(ops.watcherActive)
        }
    }

    @Test
    fun partialWatcherStartFailureRollsBackRegisteredSide() {
        val ops = FakeOps().apply {
            current = FakeNet("wifi0")
            failNextWatcherStart = true
        }
        coordinatorTest(ops) { coordinator, _ ->
            assertFailsWith<IOException> { coordinator.startAdvertising(localPeer) }

            assertEquals(1, ops.registrations.size)
            assertTrue(ops.created.single().closed)
            assertFalse(ops.watcherActive)
            assertFalse(ops.lockHeld)
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
    fun cancelledRebindJobCompletesItsOwnershipTransaction() {
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

            // Cancel the pending rebind job mid-create (the shape of a
            // superseding schedule racing the active transaction). Once the
            // old handle has been closed, ownership restoration is
            // deliberately non-cancellable.
            rebindScope.coroutineContext.cancelChildren()
            gate.countDown()

            awaitCondition("cancelled rebind finishes replacement ownership") {
                ops.created.size == 2 && ops.listenersAdded.size == 2
            }
            assertTrue(ops.created[0].closed, "the replaced handle must close")
            assertFalse(ops.created[1].closed, "the installed replacement must remain live")
            assertSame(ops.created[1], ops.listenersAdded.last().handle)
            assertEquals(1, ops.closed.size)
            assertTrue(ops.lockHeld)
            assertTrue(ops.watcherActive)
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
    fun supersedingScheduleCannotCancelAnActiveRebindTransaction() {
        val wifi0 = FakeNet("wifi0")
        val wifi1 = FakeNet("wifi1")
        val wifi2 = FakeNet("wifi2")
        val ops = FakeOps().apply {
            current = wifi0
            observed = wifi0
        }
        coordinatorTest(ops, debounceMillis = 5) { coordinator, _ ->
            coordinator.startAdvertising(localPeer)
            val closeGate = CountDownLatch(1)
            ops.closeGate = closeGate

            ops.observed = wifi1
            coordinator.scheduleRebind("first rotation")
            awaitBlockingCall(ops.closeEntered, "first rebind closeHandleBlocking")

            // This cancels the first pending job after it has crossed the
            // debounce boundary. Its close+recreate transaction must still
            // complete before the second target is installed.
            ops.observed = wifi2
            coordinator.scheduleRebind("superseding rotation")
            closeGate.countDown()
            ops.closeGate = null

            awaitCondition("both serialized rebinds complete") {
                ops.createdTargets == listOf<FakeNet?>(wifi0, wifi1, wifi2) &&
                    ops.registrations.size == 3
            }
            assertEquals(2, ops.closed.size)
            assertSame(ops.created.last(), ops.registrations.last().first)
            assertTrue(ops.lockHeld)
            assertTrue(ops.watcherActive)
        }
    }

    @Test
    fun stopDuringAnActiveRebindWaitsForRestorationThenReleasesEverything() {
        val ops = FakeOps().apply {
            current = FakeNet("wifi0")
            observed = FakeNet("wifi0")
        }
        coordinatorTest(ops, debounceMillis = 5) { coordinator, scope ->
            coordinator.startDiscovery()
            val closeGate = CountDownLatch(1)
            ops.closeGate = closeGate
            ops.observed = FakeNet("wifi1")
            coordinator.scheduleRebind("rotation before stop")
            awaitBlockingCall(ops.closeEntered, "active rebind closeHandleBlocking")

            val stopper = scope.launch { coordinator.stopDiscovery() }
            closeGate.countDown()
            ops.closeGate = null
            stopper.join()

            assertEquals(2, ops.created.size)
            assertEquals(2, ops.closed.size)
            assertTrue(ops.created.all(FakeHandle::closed))
            assertFalse(ops.lockHeld)
            assertFalse(ops.watcherActive)
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
    fun detachedListenerPortRejectsTheRecordAndSelfRetryRestoresBothIntents() {
        val registration = LanServiceRegistration(
            localPeer.appId, localPeer.peerId, localPeer.deviceName, localPeer.platform
        )
        val data = JvmLanDataTransport(registration)
        val detachedAttempt = CompletableDeferred<Result<ServiceInfo>>()
        val retryGate = CountDownLatch(1)
        lateinit var ops: FakeOps
        ops = FakeOps { peer ->
            val result = runCatching { buildJmdnsServiceInfo(registration, peer) }
            if (registration.tcpPort == 0) {
                // Park the next handle creation before it consumes another
                // retry. The producer stays detached until the test restarts it.
                ops.createGate = retryGate
                detachedAttempt.complete(result)
            }
            result.getOrThrow()
        }.apply {
            current = FakeNet("wifi0")
            observed = current
        }
        coordinatorTest(ops) { coordinator, _ ->
            try {
                data.start().getOrThrow()
                val livePort = registration.tcpPort
                coordinator.startAdvertising(localPeer)
                coordinator.startDiscovery()
                assertEquals(listOf(livePort), ops.serviceInfos.map { it.port })

                data.stop()
                assertEquals(0, registration.tcpPort)
                ops.observed = FakeNet("wifi1")
                coordinator.scheduleRebind("listener detached during network rotation")
                val attempt = withTimeout(5_000) { detachedAttempt.await() }
                assertTrue(attempt.isFailure, "detached listener produced SRV port ${attempt.getOrNull()?.port}")
                assertIs<P2pError.TransportStartFailed>(attempt.exceptionOrNull())
                awaitCondition("self-scheduled retry reaches the gated creator") { ops.createCalls.get() == 3 }
                assertEquals(listOf(livePort), ops.serviceInfos.map { it.port }, "zero port must never register")
                assertTrue(ops.watcherActive)
                assertTrue(ops.lockHeld)

                data.start().getOrThrow()
                assertEquals(livePort, registration.tcpPort)
                retryGate.countDown()
                awaitCondition("retry restores the advertisement and independent discovery listener") {
                    ops.serviceInfos.size == 2 && ops.listenersActivated.size == 2
                }
                assertEquals(listOf(livePort, livePort), ops.serviceInfos.map { it.port })
                assertEquals(data.tcpPort.value, ops.serviceInfos.last().port)
                assertTrue(ops.listenersActivated.last().active)
                assertEquals(3, ops.createCalls.get(), "start + rejected record + successful retry")
                assertEquals(2, ops.closed.size, "old and rejected fresh handles are both released")
            } finally {
                retryGate.countDown()
                try {
                    coordinator.stopAdvertising()
                    coordinator.stopDiscovery()
                } finally {
                    data.close()
                }
            }
            assertFalse(ops.watcherActive)
            assertFalse(ops.lockHeld)
            assertTrue(ops.created.all { it.closed })
        }
    }

    @Test
    fun unboundAdvertisingFailurePreservesIndependentDiscoveryAndCanRetry() {
        val registration = LanServiceRegistration(
            localPeer.appId, localPeer.peerId, localPeer.deviceName, localPeer.platform
        )
        val data = JvmLanDataTransport(registration)
        val ops = FakeOps { peer -> buildJmdnsServiceInfo(registration, peer) }.apply {
            current = FakeNet("wifi0")
        }
        coordinatorTest(ops) { coordinator, _ ->
            try {
                coordinator.startDiscovery()
                assertFailsWith<P2pError.TransportStartFailed> { coordinator.startAdvertising(localPeer) }
                assertTrue(ops.serviceInfos.isEmpty())
                assertTrue(ops.listenersActivated.last().active, "failed advertising must restore discovery")
                assertTrue(ops.watcherActive)
                assertTrue(ops.lockHeld)

                data.start().getOrThrow()
                coordinator.startAdvertising(localPeer)
                assertEquals(data.tcpPort.value, ops.serviceInfos.single().port)
                coordinator.stopAdvertising()
                assertTrue(ops.listenersActivated.last().active, "stopping advertising must preserve discovery")
            } finally {
                try {
                    coordinator.stopAdvertising()
                    coordinator.stopDiscovery()
                } finally {
                    data.close()
                }
            }
            assertFalse(ops.watcherActive)
            assertFalse(ops.lockHeld)
            assertTrue(ops.created.all { it.closed })
        }
    }

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
    fun forcedSameNetworkAddressChangeSurvivesCallbackCoalescing() {
        val net = FakeNet("wifi0")
        val ops = FakeOps().apply {
            current = net
            observed = net
            observedDefault = net
        }
        coordinatorTest(ops, debounceMillis = 20) { coordinator, _ ->
            coordinator.startDiscovery()

            coordinator.scheduleRebind("link properties changed", force = true)
            coordinator.scheduleRebind("later capability callback")
            coordinator.awaitPendingRebindForTest()

            assertEquals(2, ops.createCalls.get())
            assertEquals(1, ops.closed.size)
            assertEquals(2, ops.listenersAdded.size)
        }
    }

    @Test
    fun defaultNetworkSignalTriggersRebindButNeverBecomesBindTarget() {
        val wifi = FakeNet("wifi0")
        val cellularA = FakeNet("cellular-a")
        val cellularB = FakeNet("cellular-b")
        val ops = FakeOps().apply {
            current = wifi
            observed = wifi
            observedDefault = cellularA
        }
        coordinatorTest(ops) { coordinator, _ ->
            coordinator.startAdvertising(localPeer)

            ops.observedDefault = cellularB
            coordinator.scheduleRebind("default cellular signal changed")
            awaitCondition("default-network signal causes a rebind") {
                ops.createCalls.get() == 2
            }

            assertEquals(
                listOf<FakeNet?>(wifi, wifi),
                ops.createdTargets,
                "the system default is a change signal, never a LAN bind fallback"
            )
        }
    }

    @Test
    fun rebindFallsBackToFreshSelectionWhenPrimaryObserverHasNoTarget() {
        val wifiA = FakeNet("wifi-a")
        val wifiB = FakeNet("wifi-b")
        val ops = FakeOps().apply {
            current = wifiA
            observed = wifiA
        }
        coordinatorTest(ops) { coordinator, _ ->
            coordinator.startDiscovery()

            ops.observed = null
            ops.current = wifiB
            coordinator.scheduleRebind("authoritative selection changed")
            awaitCondition("fresh selection is rebound") { ops.createCalls.get() == 2 }

            assertEquals(listOf<FakeNet?>(wifiA, wifiB), ops.createdTargets)
        }
    }

    @Test
    fun addingSecondIntentDoesNotRelabelExistingHandleBeforeRebind() {
        val wifiA = FakeNet("wifi-a")
        val wifiB = FakeNet("wifi-b")
        val ops = FakeOps().apply {
            current = wifiA
            observed = wifiA
        }
        coordinatorTest(ops) { coordinator, _ ->
            coordinator.startAdvertising(localPeer)

            // The topology rotates before discovery joins the shared handle.
            // Adding discovery must not claim that the wifi-a socket is
            // already bound to wifi-b and suppress the pending rebind.
            ops.current = wifiB
            ops.observed = wifiB
            coordinator.startDiscovery()
            assertEquals(1, ops.createCalls.get())

            coordinator.scheduleRebind("topology rotated while adding second intent")
            awaitCondition("existing handle is rebound to the new target") {
                ops.createCalls.get() == 2
            }

            assertEquals(listOf<FakeNet?>(wifiA, wifiB), ops.createdTargets)
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

    @Test
    fun retiredWatcherGenerationCannotScheduleAgainstTheLiveCoordinator() {
        val wifiA = FakeNet("wifi-a")
        val wifiB = FakeNet("wifi-b")
        val ops = FakeOps().apply {
            current = wifiA
            observed = wifiA
        }
        coordinatorTest(ops) { coordinator, _ ->
            coordinator.startAdvertising(localPeer)
            ops.current = wifiB
            ops.observed = wifiB

            coordinator.scheduleRebind(
                reason = "queued callback from retired watcher",
                admit = { false }
            )
            delay(25)

            assertEquals(1, ops.createCalls.get())
            assertTrue(ops.watcherActive)
            coordinator.stopAdvertising()
        }
    }

    // ── refresh rotation plumbing ───────────────────────────────────────

    @Test
    fun refreshRotationCommitsFreshListenerTokenUsedByLaterStop() {
        val ops = FakeOps().apply { current = FakeNet("wifi0") }
        coordinatorTest(ops) { coordinator, _ ->
            coordinator.startDiscovery()
            val original = ops.listenersAdded.single()
            ops.listenerTransitions.clear()

            coordinator.refreshDiscovery { handle ->
                assertSame(ops.created.single(), handle)
            }

            val replacement = ops.listenersAdded.last()
            assertEquals(2, ops.listenersAdded.size)
            assertSame(original, ops.listenersRemoved.single())
            assertFalse(original.active, "replaced listener generation must be deactivated")
            assertTrue(replacement.active)
            assertEquals(
                listOf(
                    "add" to replacement,
                    "deactivate" to original,
                    "remove" to original,
                    "activate" to replacement
                ),
                ops.listenerTransitions,
                "fresh callbacks must remain staged until the predecessor is retired"
            )

            ops.listenerTransitions.clear()
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
    fun cancellationDuringOldListenerRemovalStillCommitsFreshActivation() {
        val ops = FakeOps().apply { current = FakeNet("wifi0") }
        coordinatorTest(ops) { coordinator, scope ->
            coordinator.startDiscovery()
            val original = ops.listenersAdded.single()
            ops.listenerTransitions.clear()

            val gate = CountDownLatch(1)
            ops.removeListenerGate = gate
            var afterRotationInvoked = false
            val refresher = scope.launch {
                coordinator.refreshDiscovery { afterRotationInvoked = true }
            }
            awaitBlockingCall(ops.removeListenerEntered, "refresh removeListenerBlocking")
            val replacement = ops.listenersAdded.last()

            refresher.cancel()
            gate.countDown()
            refresher.join()

            assertTrue(refresher.isCancelled)
            assertFalse(afterRotationInvoked)
            assertFalse(original.active)
            assertTrue(replacement.active, "committed replacement must not remain staged")
            assertEquals(
                listOf(
                    "add" to replacement,
                    "deactivate" to original,
                    "remove" to original,
                    "activate" to replacement
                ),
                ops.listenerTransitions
            )

            ops.removeListenerGate = null
            coordinator.stopDiscovery()
            assertSame(replacement, ops.listenersRemoved.last())
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

    @Test
    fun blockedNetworkProbeDoesNotHoldLifecycleLock() {
        val wifi = FakeNet("wifi0")
        val ops = FakeOps().apply {
            current = wifi
            observed = wifi
        }
        coordinatorTest(ops) { coordinator, scope ->
            coordinator.startAdvertising(localPeer)

            val probeGate = CountDownLatch(1)
            ops.observedNetworkGate = probeGate
            coordinator.scheduleRebind("blocked network probe", force = true)
            awaitBlockingCall(ops.observedNetworkEntered, "observedNetwork")

            try {
                val stopped = CompletableDeferred<Unit>()
                scope.launch {
                    coordinator.stopAdvertising()
                    stopped.complete(Unit)
                }
                withTimeout(1_000) { stopped.await() }
                assertFalse(ops.watcherActive, "stop must not queue behind an IO-side network probe")
            } finally {
                probeGate.countDown()
            }
        }
    }

    @Test
    fun networkProbesUseTheInjectedIoContext() {
        val probeDispatcher = Executors.newSingleThreadExecutor { runnable ->
            Thread(runnable, "p2pkit-network-probe")
        }.asCoroutineDispatcher()
        try {
            val wifi = FakeNet("wifi0")
            val ops = FakeOps().apply {
                current = wifi
                observed = wifi
            }
            coordinatorTest(ops, ioContext = probeDispatcher) { coordinator, _ ->
                coordinator.startAdvertising(localPeer)
                assertTrue(ops.currentNetworkThread?.startsWith("p2pkit-network-probe") == true)

                coordinator.scheduleRebind("verify network probe dispatcher", force = true)
                coordinator.awaitPendingRebindForTest()
                assertTrue(ops.observedNetworkThread?.startsWith("p2pkit-network-probe") == true)
            }
        } finally {
            probeDispatcher.close()
        }
    }

}
