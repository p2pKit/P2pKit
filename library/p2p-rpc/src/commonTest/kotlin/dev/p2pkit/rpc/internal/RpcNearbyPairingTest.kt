package dev.p2pkit.rpc.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.core.PeerAdmission
import dev.p2pkit.rpc.RpcEndpoint
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcPairing
import dev.p2pkit.rpc.RpcPairingOrigin
import dev.p2pkit.rpc.RpcTrust
import dev.p2pkit.rpc.RpcTrustPurpose
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

@OptIn(ExperimentalCoroutinesApi::class)
class RpcNearbyPairingTest {
    private class Fixture(val pairing: RpcPairing, val trust: RpcTrust, val gate: EnrollmentGate)

    private suspend fun TestScope.fixture(
        enabled: Boolean = true, store: LocalTestTrustStore = LocalTestTrustStore(),
    ): Fixture {
        val trust = RpcTrust.load(AppId("rpc.nearby.test"), RpcTrustPurpose.HostClients, store)
        val clock = RpcClock { testScheduler.currentTime }
        val gate = EnrollmentGate(clock)
        return Fixture(RpcPairing(backgroundScope, trust, clock, gate, TEST_INCARNATION,
            "p2pkit:v2:p2a1-" + "a".repeat(52) + ":" + testFingerprint().value,
            { RpcEndpoint("10.1.2.3", 5432) }, enabled), trust, gate)
    }

    private suspend fun RpcPairing.request(link: RpcTestLink, id: String = TEST_REQUEST) =
        onRequest(link, WireMessage(WireKind.RequestApproval, id, TEST_INCARNATION))

    @Test
    fun defaultRejectsNearbyWithoutOpeningAdmissionOrWritingTrust() = runTest {
        val f = fixture(enabled = false)
        val link = RpcTestLink(1, PeerAdmission.EnrollmentOnly)
        f.pairing.request(link)
        assertEquals(WireKind.PairDenied, link.sent.last().kind)
        assertEquals(ConnectionState.Closed, link.transportState.value)
        assertTrue(f.pairing.pending.value.isEmpty())
        assertFalse(f.trust.isTrusted(testFingerprint(1)))
        assertFalse(f.gate.isOpen)
        f.pairing.close(); link.clearSent()
    }

    @Test
    fun approvalIsDurableIdentityBoundAndCannotUpgradeTheEnrollmentLink() = runTest {
        val store = LocalTestTrustStore()
        val f = fixture(store = store)
        val link = RpcTestLink(1, PeerAdmission.EnrollmentOnly)
        f.pairing.request(link)
        val request = f.pairing.pending.value.single()
        assertEquals(RpcPairingOrigin.Nearby, request.origin)
        assertEquals(link.identity.fingerprint, request.peer.fingerprint)
        assertFalse(f.trust.isTrusted(testFingerprint(1)))
        f.pairing.approve(request.id)
        assertEquals(setOf(testFingerprint(1)), store.pins)
        assertEquals(WireKind.PairApproved, link.sent.last().kind)
        assertEquals(ConnectionState.Closed, link.transportState.value)
        assertEquals(PeerAdmission.EnrollmentOnly, link.admission)
        assertTrue(f.pairing.pending.value.isEmpty())
        f.pairing.close()
        assertFalse(f.gate.isOpen)
        link.clearSent()
    }

    @Test
    fun fourSlotsIncludeInvitationsAndRetriesCannotRenewExpiry() = runTest {
        val f = fixture()
        val invitation = f.pairing.createInvitation()
        val links = (1..4).map { RpcTestLink(it, PeerAdmission.EnrollmentOnly) }
        links.take(3).forEach { f.pairing.request(it) }
        f.pairing.request(links.last())
        assertEquals(3, f.pairing.pending.value.size)
        assertEquals(WireKind.PairDenied, links.last().sent.last().kind)
        advanceTimeBy(119_000); runCurrent()
        f.pairing.request(links.first())
        assertTrue(f.pairing.pending.value.all { it.remainingMillis <= 1_000 })
        advanceTimeBy(1_001); runCurrent()
        assertTrue(f.pairing.pending.value.isEmpty())
        assertTrue(links.all { it.transportState.value == ConnectionState.Closed })
        f.pairing.close(); invitation.clear(); links.forEach { it.clearSent() }
    }

    @Test
    fun replacementLinkOrRequestIdCannotStealPendingApproval() = runTest {
        val f = fixture()
        val first = RpcTestLink(1, PeerAdmission.EnrollmentOnly)
        val replacement = RpcTestLink(1, PeerAdmission.EnrollmentOnly)
        f.pairing.request(first)
        val id = f.pairing.pending.value.single().id
        f.pairing.request(replacement)
        assertEquals(WireKind.PairDenied, replacement.sent.last().kind)
        assertEquals(id, f.pairing.pending.value.single().id)
        f.pairing.approve(id)
        assertEquals(WireKind.PairApproved, first.sent.last().kind)
        assertTrue(replacement.sent.none { it.kind == WireKind.PairApproved })
        f.pairing.close(); first.clearSent(); replacement.clearSent()
    }

    @Test
    fun rejectionHasBoundedCooldownAndDoesNotWriteTrust() = runTest {
        val f = fixture()
        val first = RpcTestLink(1, PeerAdmission.EnrollmentOnly)
        f.pairing.request(first)
        f.pairing.reject(f.pairing.pending.value.single().id)
        val replay = RpcTestLink(1, PeerAdmission.EnrollmentOnly)
        f.pairing.request(replay)
        assertEquals(WireKind.PairDenied, replay.sent.last().kind)
        assertTrue(f.pairing.pending.value.isEmpty())
        advanceTimeBy(30_000); runCurrent()
        val later = RpcTestLink(1, PeerAdmission.EnrollmentOnly)
        f.pairing.request(later)
        assertEquals(WireKind.PairPending, later.sent.last().kind)
        assertFalse(f.trust.isTrusted(testFingerprint(1)))
        f.pairing.close(); listOf(first, replay, later).forEach { it.clearSent() }
    }

    @Test
    fun storageFailureCannotSendApprovalOrLeaveAdmissionOpenAfterClose() = runTest {
        val store = LocalTestTrustStore()
        val f = fixture(store = store)
        val link = RpcTestLink(1, PeerAdmission.EnrollmentOnly)
        f.pairing.request(link)
        store.failWrites = true
        assertEquals(RpcFailureKind.TrustStorage,
            assertFailsWith<RpcFailure> { f.pairing.approve(f.pairing.pending.value.single().id) }.kind)
        assertFalse(f.trust.healthy)
        assertTrue(store.pins.isEmpty())
        assertTrue(link.sent.none { it.kind == WireKind.PairApproved })
        assertEquals(ConnectionState.Closed, link.transportState.value)
        f.pairing.close()
        assertFalse(f.gate.isOpen)
        link.clearSent()
    }

    @Test
    fun disconnectedNearbyRequestCannotBeApprovedOrResurrectedByAnOldCallback() = runTest {
        val f = fixture()
        val link = RpcTestLink(1, PeerAdmission.EnrollmentOnly)
        f.pairing.request(link)
        val id = f.pairing.pending.value.single().id
        link.close()
        f.pairing.onLinkClosed(link)
        assertTrue(f.pairing.pending.value.isEmpty())
        assertFailsWith<RpcFailure> { f.pairing.approve(id) }
        val retry = RpcTestLink(1, PeerAdmission.EnrollmentOnly)
        f.pairing.request(retry)
        assertEquals(WireKind.PairDenied, retry.sent.last().kind)
        assertFalse(f.trust.isTrusted(testFingerprint(1)))
        f.pairing.close(); link.clearSent(); retry.clearSent()
    }

    @Test
    fun newWireKindIsBodylessAndCannotMasqueradeAsInvitationProof() {
        val budget = PayloadBudget(4096)
        val message = WireMessage(WireKind.RequestApproval, TEST_REQUEST, TEST_INCARNATION)
        val packet = RpcWire.encode(message)
        assertEquals(56, packet.size)
        assertEquals(message, RpcWire.decode(packet, budget))
        for (invalid in listOf(
            packet.copyOf().also { it[5] = WireKind.PairRequest.code.toByte() },
            packet.copyOf().also { it[49] = 1 },
            packet.copyOf().also { it[44] = 1 },
            packet.copyOf().also { it[48] = 1 },
            packet + byteArrayOf(0),
        )) assertFailsWith<RpcFailure> { RpcWire.decode(invalid, budget) }
        val body = testBody("not-an-invitation", budget)
        assertFailsWith<RpcFailure> { RpcWire.encode(message.copy(body = body)) }
        body.release()
        assertEquals(0L, budget.retainedBytes.value)
    }
}
