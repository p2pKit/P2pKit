package dev.p2pkit.transport.lan

import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.PeerEvent
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** Real coordinator, platform listener/admissions and relay; no native JmDNS/network campaign. */
@OptIn(ExperimentalCoroutinesApi::class)
class AndroidWholeHandleRebindTest {
    @Test
    fun successfulWholeHandleReplacementWithdrawsAndRelearnsPeers() = rebindScenario("none")

    @Test
    fun failedCreationDoesNotReplayRetiredPeersAndNextRebindRecovers() = rebindScenario("create")

    @Test
    fun failedCloseRetainsNativeOwnerButNotPeerStateOrCallbackAuthority() = rebindScenario("close")

    private fun rebindScenario(failure: String) = runTest {
        val admissions = AndroidServiceAdmissions()
        val relay = ReliablePeerEventRelay()
        val ops = Ops(admissions, relay)
        val coordinator = JmdnsLifecycleCoordinator(
            ops, backgroundScope, StandardTestDispatcher(testScheduler),
            rebindDebounceMillis = 0,
            rebindRetryBaseDelayMillis = 10_000,
            onHandleRetiring = { admissions.drain(); relay.clear() }
        )
        val events = mutableListOf<PeerEvent>()
        backgroundScope.launch(UnconfinedTestDispatcher(testScheduler)) { relay.events.collect { events += it } }
        try {
            coordinator.startDiscovery()
            val handleA = ops.handles.single()
            val firstLease = ops.listeners.last()
            ops.resolve(firstLease, "absent-on-b")
            ops.resolve(firstLease, "present-on-b")
            assertEquals(2, admissions.sizeForTest())

            // Listener-only refresh must not withdraw a still-live handle's peers.
            coordinator.refreshDiscovery {}
            val refreshedLease = ops.listeners.last()
            assertFalse(firstLease.isActive())
            assertTrue(refreshedLease.isActive())
            assertEquals(2, relay.sizeForTest())
            assertEquals(0, events.count { it is PeerEvent.Lost })

            ops.target = "B"
            ops.failClose = failure == "close"
            ops.failCreate = failure == "create"
            ops.relearn = true
            coordinator.scheduleRebind("test whole-handle rotation")
            coordinator.awaitPendingRebindForTest()
            assertFalse(refreshedLease.isActive())
            assertTrue(events.any { it is PeerEvent.Lost && it.peerId == PeerId("absent-on-b") })
            assertTrue(events.any { it is PeerEvent.Lost && it.peerId == PeerId("present-on-b") })
            if (failure != "none") {
                assertEquals(0, admissions.sizeForTest())
                assertEquals(0, relay.sizeForTest(), "failed replacement must not replay stale Found")
                assertEquals(failure != "close", handleA.closed)
                ops.resolve(firstLease, "retired-callback")
                ops.resolve(refreshedLease, "retired-callback")
                assertEquals(0, relay.sizeForTest())
                coordinator.scheduleRebind("retry same target after injected failure")
                coordinator.awaitPendingRebindForTest()
            }
            assertTrue(handleA.closed)
            assertEquals("B", ops.handles.last().target)
            assertEquals(1, admissions.sizeForTest())
            assertEquals(1, relay.sizeForTest())
            assertEquals(PeerId("present-on-b"), (events.last() as PeerEvent.Found).peer.publicPeer.id)
            ops.resolve(refreshedLease, "retired-callback")
            assertEquals(1, relay.sizeForTest())
            coordinator.stopDiscovery()
            assertEquals(0, relay.sizeForTest())
            assertTrue(ops.handles.all { it.closed })
        } finally {
            ops.failClose = false
            ops.failCreate = false
            coordinator.stopDiscovery()
        }
    }

    private class Handle(val target: String) { var closed = false }

    private class Ops(
        private val admissions: AndroidServiceAdmissions,
        private val relay: ReliablePeerEventRelay
    ) : JmdnsLifecycleOps<String, Handle> {
        var target = "A"
        var failClose = false
        var failCreate = false
        var relearn = false
        private var watching = false
        val handles = mutableListOf<Handle>()
        val listeners = mutableListOf<AndroidListenerLease>()

        fun resolve(lease: AndroidListenerLease, name: String) {
            lease.publishIfActive(name) {
                val id = PeerId(name)
                admissions.admitAndPublish(name, id, lease) {
                    relay.upsert(InternalPeer(
                        publicPeer = Peer(id, name, Platform.JVM_DESKTOP, setOf(TransportKind.LAN)),
                        transportHints = emptyList()
                    ))
                }
            }
        }

        override fun createHandleBlocking(target: String?, forRebind: Boolean): JmdnsHandleBinding<String, Handle> {
            if (failCreate) { failCreate = false; error("injected create failure") }
            return Handle(checkNotNull(target)).also { handles += it }.let { JmdnsHandleBinding(target, it) }
        }
        override fun closeHandleBlocking(handle: Handle) {
            assertTrue(listeners.none { it.isActive() }, "fence callbacks before withdrawing peers")
            assertEquals(0, relay.sizeForTest(), "withdraw state even before a failing native close")
            assertEquals(0, admissions.sizeForTest())
            if (failClose) { failClose = false; error("injected close failure") }
            handle.closed = true
        }
        override fun createListenerToken(handle: Handle): Any = AndroidListenerLease().also { listeners += it }
        override fun addListenerBlocking(handle: Handle, token: Any) {
            // A native callback can arrive synchronously during add; activation must order it after reset.
            if (relearn) resolve(token as AndroidListenerLease, "present-on-b")
        }
        override fun activateListenerBlocking(token: Any) { (token as AndroidListenerLease).activate() }
        override fun deactivateListenerToken(token: Any) {
            val lease = token as AndroidListenerLease
            lease.deactivate()
            admissions.listenerDeactivated(lease)
        }
        override fun removeListenerBlocking(handle: Handle, token: Any) = Unit
        override fun createServiceToken(localPeer: LocalPeerInfo): Any = Any()
        override fun registerServiceBlocking(handle: Handle, token: Any) = Unit
        override fun unregisterServiceBlocking(handle: Handle, token: Any) = Unit
        override fun currentNetwork(): String = target
        override fun observedNetwork(): String = target
        override fun observedDefaultNetwork(): Any? = null
        override fun isWatcherActive(): Boolean = watching
        override fun startNetworkWatcher(boundNetwork: String?) { watching = true }
        override fun stopNetworkWatcher() { watching = false }
        override fun acquireMulticastLock() = Unit
        override fun releaseMulticastLock() = Unit
        override fun logDebug(message: String) = Unit
        override fun logWarn(message: String, error: Throwable?) = Unit
    }
}
