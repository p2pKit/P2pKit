package dev.p2pkit.sample.rpc

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcFailurePhase
import dev.p2pkit.rpc.RpcTrustPurpose
import dev.p2pkit.rpc.RpcTrustStore
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

@OptIn(ExperimentalCoroutinesApi::class)
class RpcDiscoveryCoordinatorTest {
    private val a = "p2f1-" + "a".repeat(52)
    private val b = "p2f1-" + "b".repeat(51) + "a"

    private class Store : RpcTrustStore {
        var selected: Set<PeerFingerprint> = emptySet()
        var failure = false
        override suspend fun load(appId: AppId, purpose: RpcTrustPurpose): Set<PeerFingerprint> {
            check(purpose == RpcTrustPurpose.SelectedHostPreference)
            if (failure) error("private storage path")
            return selected
        }
        override suspend fun replace(appId: AppId, purpose: RpcTrustPurpose, fingerprints: Set<PeerFingerprint>) {
            check(purpose == RpcTrustPurpose.SelectedHostPreference)
            if (failure) error("private storage path")
            selected = fingerprints.toSet()
        }
    }

    private class Client : RpcDiscoveryClient {
        var hosts: List<RpcNearbyHost> = emptyList()
        val pins = mutableSetOf<String>()
        var connected = false
        var discoveryStarted = false
        val dials = mutableListOf<String>()
        var approvals = 0
        var onConnect: suspend (String) -> Unit = { connected = true }
        var onApproval: suspend (String) -> Unit = { pins += it }
        override fun nearby(): List<RpcNearbyHost> = hosts
        override fun trusted(pin: String): Boolean = pin in pins
        override fun ready(): Boolean = connected
        override suspend fun discover() { discoveryStarted = true }
        override suspend fun disconnect() { connected = false }
        override suspend fun connect(pin: String) { dials += pin; onConnect(pin) }
        override suspend fun requestApproval(pin: String) { approvals++; onApproval(pin) }
        override suspend fun revoke(pin: String) { pins -= pin; connected = false }
    }

    private fun host(pin: String) = RpcNearbyHost(pin, "Same untrusted name", "test", false)

    @Test
    fun discoveryAloneNeverChoosesOrPairsEvenWhenOtherHostIsTrusted() = runTest {
        val client = Client().apply { hosts = listOf(host(a), host(b)); pins += a }
        val coordinator = RpcDiscoveryCoordinator(backgroundScope, client, Store())
        coordinator.start(); runCurrent(); advanceTimeBy(60_000); runCurrent()
        assertTrue(client.discoveryStarted)
        assertTrue(client.dials.isEmpty())
        assertEquals(0, client.approvals)
        assertFailsWith<IllegalStateException> { coordinator.select(b, false) }
        assertTrue(client.dials.isEmpty())
        coordinator.close()
    }

    @Test
    fun storedSelectionReconnectsOnlyItsTrustedPinNotTheFirstNameOrAddress() = runTest {
        val client = Client().apply { hosts = listOf(host(b), host(a)); pins += setOf(a, b) }
        val store = Store().apply { selected = setOf(PeerFingerprint(a)) }
        val coordinator = RpcDiscoveryCoordinator(backgroundScope, client, store)
        coordinator.start(); runCurrent()
        assertEquals(listOf(a), client.dials)
        assertEquals(RpcDiscoveryConnectionState.Ready, coordinator.status.value.state)
        assertEquals(0, client.approvals)
        coordinator.close()
        assertEquals(setOf(PeerFingerprint(a)), store.selected)
    }

    @Test
    fun firstUseIsExplicitAndOnlyDurableApprovalBecomesAReconnectSelection() = runTest {
        val approval = CompletableDeferred<Unit>()
        val client = Client().apply {
            hosts = listOf(host(a))
            onApproval = { approval.await(); pins += it }
        }
        val store = Store()
        val coordinator = RpcDiscoveryCoordinator(backgroundScope, client, store)
        coordinator.start()
        coordinator.select(a, true); runCurrent()
        assertEquals(RpcDiscoveryConnectionState.AwaitingApproval, coordinator.status.value.state)
        assertEquals(1, client.approvals)
        assertTrue(store.selected.isEmpty())
        assertTrue(client.dials.isEmpty())
        approval.complete(Unit); runCurrent()
        assertEquals(setOf(PeerFingerprint(a)), store.selected)
        assertEquals(listOf(a), client.dials)
        coordinator.close()
    }

    @Test
    fun rejectionIsNotAutomaticallyRetriedAndNeverStoredAsTrust() = runTest {
        val client = Client().apply {
            hosts = listOf(host(a))
            onApproval = { throw RpcFailure(RpcFailureKind.Unauthorized, RpcFailurePhase.Trust) }
        }
        val store = Store()
        val coordinator = RpcDiscoveryCoordinator(backgroundScope, client, store)
        coordinator.start(); coordinator.select(a, true); runCurrent()
        advanceTimeBy(120_000); runCurrent()
        assertEquals(1, client.approvals)
        assertTrue(store.selected.isEmpty())
        assertTrue(client.pins.isEmpty())
        assertTrue(client.dials.isEmpty())
        assertEquals(RpcDiscoveryConnectionState.Failed, coordinator.status.value.state)
        coordinator.close()
    }

    @Test
    fun missingDuplicateAndRevokedSelectedIdentitiesNeverDialAnotherHost() = runTest {
        val client = Client().apply { hosts = listOf(host(b)); pins += a }
        val store = Store().apply { selected = setOf(PeerFingerprint(a)) }
        val coordinator = RpcDiscoveryCoordinator(backgroundScope, client, store)
        coordinator.start(); runCurrent()
        assertEquals(RpcDiscoveryConnectionState.Offline, coordinator.status.value.state)
        client.hosts = listOf(host(a), host(a))
        advanceTimeBy(1_000); runCurrent()
        assertEquals(RpcDiscoveryConnectionState.Ambiguous, coordinator.status.value.state)
        client.pins.clear()
        client.hosts = listOf(host(a))
        advanceTimeBy(1_000); runCurrent()
        assertEquals(RpcDiscoveryConnectionState.RequiresApproval, coordinator.status.value.state)
        assertTrue(client.dials.isEmpty())
        assertEquals(0, client.approvals)
        coordinator.close()
    }

    @Test
    fun reconnectBackoffIsBoundedAndCloseCancelsTheOnlyWorker() = runTest {
        val times = mutableListOf<Long>()
        val client = Client().apply {
            hosts = listOf(host(a)); pins += a
            onConnect = {
                times += testScheduler.currentTime
                throw RpcFailure(RpcFailureKind.NotConnected, RpcFailurePhase.Admission)
            }
        }
        val store = Store().apply { selected = setOf(PeerFingerprint(a)) }
        val coordinator = RpcDiscoveryCoordinator(backgroundScope, client, store)
        coordinator.start(); runCurrent()
        advanceTimeBy(91_001); runCurrent()
        assertEquals(listOf(0L, 1_000L, 3_000L, 7_000L, 15_000L, 31_000L, 61_000L, 91_000L), times)
        assertEquals(30_000L, coordinator.status.value.nextRetryMillis)
        coordinator.close()
        advanceTimeBy(120_000); runCurrent()
        assertEquals(8, client.dials.size)
        assertEquals(RpcDiscoveryConnectionState.Closed, coordinator.status.value.state)
    }

    @Test
    fun switchingSelectionJoinsOldApprovalBeforeStartingAnotherConnection() = runTest {
        var retired = false
        val client = Client().apply {
            hosts = listOf(host(a), host(b)); pins += b
            onApproval = { try { awaitCancellation() } finally { retired = true } }
            onConnect = { check(retired); connected = true }
        }
        val coordinator = RpcDiscoveryCoordinator(backgroundScope, client, Store())
        coordinator.start(); coordinator.select(a, true); runCurrent()
        coordinator.select(b, false); runCurrent()
        assertTrue(retired)
        assertEquals(listOf(b), client.dials)
        assertEquals(b, coordinator.status.value.selectedFingerprint)
        coordinator.close()
    }

    @Test
    fun forgettingSelectedHostClearsPreferenceAndNeverAutoPairsAgain() = runTest {
        val client = Client().apply { hosts = listOf(host(a)); pins += a }
        val store = Store().apply { selected = setOf(PeerFingerprint(a)) }
        val coordinator = RpcDiscoveryCoordinator(backgroundScope, client, store)
        coordinator.start(); runCurrent()
        coordinator.forget(a)
        assertFalse(client.trusted(a))
        assertTrue(store.selected.isEmpty())
        advanceTimeBy(60_000); runCurrent()
        assertEquals(1, client.dials.size)
        assertEquals(0, client.approvals)
        coordinator.close()
    }

    @Test
    fun corruptOrInaccessiblePreferenceNeverStartsDiscoveryOrChoosesAnotherIdentity() = runTest {
        for (store in listOf(Store().apply { failure = true }, Store().apply {
            selected = setOf(PeerFingerprint(a), PeerFingerprint(b))
        })) {
            val client = Client()
            val coordinator = RpcDiscoveryCoordinator(backgroundScope, client, store)
            val failure = assertFailsWith<RpcFailure> { coordinator.start() }
            assertEquals(RpcFailureKind.TrustStorage, failure.kind)
            assertFalse(failure.message.orEmpty().contains("private storage path"))
            assertFalse(client.discoveryStarted)
            coordinator.close()
        }
    }
}
