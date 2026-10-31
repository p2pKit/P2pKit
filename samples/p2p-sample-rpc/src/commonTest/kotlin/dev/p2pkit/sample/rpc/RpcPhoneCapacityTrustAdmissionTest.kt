package dev.p2pkit.sample.rpc

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcTrustPurpose
import dev.p2pkit.rpc.RpcTrustStore
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertSame

class RpcPhoneCapacityTrustAdmissionTest {
    @Test
    fun occupiedCapacityStoreRefusesBeforeAnyApprovalReplacementAndOmitsIdentities() = runTest {
        val pin = PeerFingerprint.parse("p2f1-" + "a".repeat(52))
        var replacements = 0
        val store = object : RpcTrustStore {
            override suspend fun load(appId: AppId, purpose: RpcTrustPurpose): Set<PeerFingerprint> {
                assertEquals(RpcCapacityContract.appId, appId)
                assertEquals(RpcTrustPurpose.HostClients, purpose)
                return setOf(pin)
            }
            override suspend fun replace(
                appId: AppId, purpose: RpcTrustPurpose, fingerprints: Set<PeerFingerprint>,
            ) { replacements++ }
        }
        val failure = assertFailsWith<RpcPhoneCapacityTrustOccupied> { requireEmptyMobileCapacityApprovals(store) }
        assertEquals(0, replacements)
        assertEquals(setOf(pin), store.load(RpcCapacityContract.appId, RpcTrustPurpose.HostClients))
        assertFalse(failure.toString().contains(pin.value))
    }

    @Test
    fun unavailableApprovalsArePropagatedWithoutImportOrRetirement() = runTest {
        val original = IllegalStateException("synthetic unavailable approvals")
        val store = object : RpcTrustStore {
            override suspend fun load(appId: AppId, purpose: RpcTrustPurpose): Set<PeerFingerprint> = throw original
            override suspend fun replace(
                appId: AppId, purpose: RpcTrustPurpose, fingerprints: Set<PeerFingerprint>,
            ) { throw AssertionError("Unavailable approvals must not be replaced") }
        }
        assertSame(original, assertFailsWith<IllegalStateException> { requireEmptyMobileCapacityApprovals(store) })
    }
}
