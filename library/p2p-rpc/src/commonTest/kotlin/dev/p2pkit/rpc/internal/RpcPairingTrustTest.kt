package dev.p2pkit.rpc.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.core.PeerAdmission
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcEndpoint
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcInvitation
import dev.p2pkit.rpc.RpcPairing
import dev.p2pkit.rpc.RpcTrust
import dev.p2pkit.rpc.RpcTrustPurpose
import dev.p2pkit.rpc.RpcTrustStore
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.async
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

internal class LocalTestTrustStore : RpcTrustStore {
    var pins: Set<PeerFingerprint> = emptySet()
    var failWrites = false
    var writeGate: CompletableDeferred<Unit>? = null
    override suspend fun load(appId: AppId, purpose: RpcTrustPurpose): Set<PeerFingerprint> = pins.toSet()
    override suspend fun replace(appId: AppId, purpose: RpcTrustPurpose, fingerprints: Set<PeerFingerprint>) {
        writeGate?.await()
        if (failWrites) error("test storage failure must never escape as infrastructure text")
        pins = fingerprints.toSet()
    }
}

@OptIn(ExperimentalCoroutinesApi::class)
class RpcPairingTrustTest {
    private val hostQr = "p2pkit:v2:p2a1-" + "a".repeat(52) + ":" + testFingerprint().value

    @Test
    fun invitationIsSingleUseIdentityBoundAndNeverAuthorizesBeforeDurableApproval() = runTest {
        val store = LocalTestTrustStore()
        val trust = RpcTrust.load(AppId("rpc.test"), RpcTrustPurpose.HostClients, store)
        val clock = RpcClock { testScheduler.currentTime }
        val budget = PayloadBudget(4096)
        val gate = EnrollmentGate(clock)
        val pairing = RpcPairing(backgroundScope, trust, clock, gate, TEST_INCARNATION, hostQr,
            { RpcEndpoint("10.1.2.3", 5432) })
        val invitation = pairing.createInvitation()
        assertFalse(invitation.toString().contains(invitation.qr))
        val client = RpcTestLink(1, PeerAdmission.EnrollmentOnly)
        val competing = RpcTestLink(2, PeerAdmission.EnrollmentOnly)
        suspend fun request(link: RpcTestLink, invitation: RpcInvitation) {
            val message = WireMessage(WireKind.PairRequest, TEST_REQUEST, TEST_INCARNATION,
                body = OwnedBytes.copy(invitation.proof(), budget))
            try { pairing.onRequest(link, message) } finally { message.release() }
        }
        request(client, invitation)
        assertFalse(trust.isTrusted(testFingerprint(1)))
        request(competing, invitation)
        assertEquals(WireKind.PairDenied, competing.sent.last().kind)
        pairing.approve(pairing.pending.value.single().id)
        assertTrue(trust.isTrusted(testFingerprint(1)))
        assertEquals(setOf(testFingerprint(1)), store.pins)
        assertEquals(WireKind.PairApproved, client.sent.last().kind)
        assertFalse(gate.isOpen)
        assertTrue(pairing.pending.value.isEmpty())
        assertFailsWith<RpcFailure> { pairing.approve(invitation.id) }
        pairing.close(); client.clearSent(); competing.clearSent(); invitation.clear()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun storageFailureCannotReportApprovalAndRevocationDeniesBeforePersistenceCompletes() = runTest {
        val store = LocalTestTrustStore()
        val trust = RpcTrust.load(AppId("rpc.test"), RpcTrustPurpose.HostClients, store)
        trust.approve(testFingerprint())
        val gate = CompletableDeferred<Unit>()
        store.writeGate = gate
        var cancellationRequested = false
        trust.onRevoke = { cancellationRequested = true }
        val revoke = async { runCatching { trust.revoke(testFingerprint()) } }
        runCurrent()
        assertFalse(trust.isTrusted(testFingerprint()))
        assertTrue(cancellationRequested)
        store.failWrites = true
        gate.complete(Unit)
        assertFailsWith<RpcFailure> { revoke.await().getOrThrow() }
        assertFalse(trust.healthy)
        assertFailsWith<RpcFailure> { trust.approve(testFingerprint(1)) }
    }

    @Test
    fun expiredInvitationIsRejectedAndSecretTextMustBeCanonical() = runTest {
        val trust = RpcTrust.load(AppId("rpc.test"), RpcTrustPurpose.HostClients, LocalTestTrustStore())
        val clock = RpcClock { testScheduler.currentTime }
        val pairing = RpcPairing(backgroundScope, trust, clock, EnrollmentGate(clock), TEST_INCARNATION,
            hostQr, { RpcEndpoint("10.1.2.3", 5432) })
        val invitation = pairing.createInvitation()
        assertEquals(invitation.qr, RpcInvitation.parse(invitation.qr).qr)
        assertFailsWith<IllegalArgumentException> { RpcInvitation.parse(invitation.qr + "|extra") }
        val budget = PayloadBudget(4096)
        val client = RpcTestLink(1, PeerAdmission.EnrollmentOnly)
        advanceTimeBy(120_001); runCurrent()
        val request = WireMessage(WireKind.PairRequest, TEST_REQUEST, TEST_INCARNATION,
            body = OwnedBytes.copy(invitation.proof(), budget))
        try { pairing.onRequest(client, request) } finally { request.release() }
        assertEquals(WireKind.PairDenied, client.sent.last().kind)
        assertFalse(trust.isTrusted(testFingerprint(1)))
        pairing.close(); invitation.clear(); client.clearSent()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun failedDurableApprovalSealsAdmissionWithoutSendingAnApprovalNotice() = runTest {
        val store = LocalTestTrustStore()
        val trust = RpcTrust.load(AppId("rpc.test"), RpcTrustPurpose.HostClients, store)
        val clock = RpcClock { testScheduler.currentTime }
        val gate = EnrollmentGate(clock)
        val pairing = RpcPairing(
            backgroundScope, trust, clock, gate, TEST_INCARNATION, hostQr, { RpcEndpoint("10.1.2.3", 5432) },
        )
        val invitation = pairing.createInvitation()
        val link = RpcTestLink(1, PeerAdmission.EnrollmentOnly)
        val budget = PayloadBudget(4096)
        val request = WireMessage(
            WireKind.PairRequest, TEST_REQUEST, TEST_INCARNATION, body = OwnedBytes.copy(invitation.proof(), budget),
        )
        try { pairing.onRequest(link, request) } finally { request.release() }
        var sealed = false
        trust.onStorageFailure = { sealed = true }
        store.failWrites = true
        link.closeFailure = IllegalStateException("private cleanup detail must not replace storage failure")
        val failure = assertFailsWith<RpcFailure> { pairing.approve(pairing.pending.value.single().id) }
        assertEquals(RpcFailureKind.TrustStorage, failure.kind)
        assertTrue(sealed)
        assertFalse(trust.healthy)
        assertFalse(trust.isTrusted(testFingerprint(1)))
        assertTrue(link.sent.none { it.kind == WireKind.PairApproved })
        assertTrue(store.pins.isEmpty())
        assertFalse(gate.isOpen)
        pairing.close()
        invitation.clear()
        link.clearSent()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun failedTransportCleanupDoesNotSkipDurableRevocation() = runTest {
        val store = LocalTestTrustStore()
        val trust = RpcTrust.load(AppId("rpc.test"), RpcTrustPurpose.HostClients, store)
        trust.approve(testFingerprint())
        trust.onRevoke = { error("retained cleanup failure") }
        assertFailsWith<RpcFailure> { trust.revoke(testFingerprint()) }
        assertTrue(store.pins.isEmpty())
        assertFalse(trust.healthy)
        assertFalse(trust.isTrusted(testFingerprint()))
    }

    @Test
    fun rejectingAPendingRequestAlwaysClosesEvenWhenTheDenialNoticeFails() = runTest {
        val trust = RpcTrust.load(AppId("rpc.test"), RpcTrustPurpose.HostClients, LocalTestTrustStore())
        val clock = RpcClock { testScheduler.currentTime }
        val gate = EnrollmentGate(clock)
        val pairing = RpcPairing(
            backgroundScope, trust, clock, gate, TEST_INCARNATION, hostQr, { RpcEndpoint("10.1.2.3", 5432) },
        )
        val invitation = pairing.createInvitation()
        val link = RpcTestLink(1, PeerAdmission.EnrollmentOnly)
        val budget = PayloadBudget(4096)
        val request = WireMessage(
            WireKind.PairRequest, TEST_REQUEST, TEST_INCARNATION, body = OwnedBytes.copy(invitation.proof(), budget),
        )
        try { pairing.onRequest(link, request) } finally { request.release() }
        link.onSend = { error("private transport detail") }
        val failure = assertFailsWith<RpcFailure> { pairing.reject(invitation.id) }
        assertEquals(RpcFailureKind.NotConnected, failure.kind)
        assertEquals(dev.p2pkit.core.ConnectionState.Closed, link.transportState.value)
        assertTrue(pairing.pending.value.isEmpty())
        assertFalse(gate.isOpen)
        assertFalse(trust.isTrusted(testFingerprint(1)))
        pairing.close()
        invitation.clear()
        link.clearSent()
        assertEquals(0L, budget.retainedBytes.value)
    }
}
