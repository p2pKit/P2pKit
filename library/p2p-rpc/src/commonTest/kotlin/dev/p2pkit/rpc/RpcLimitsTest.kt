package dev.p2pkit.rpc

import dev.p2pkit.core.P2pSessionProfile
import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.core.PeerAdmission
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class RpcLimitsTest {
    @Test fun defaultAndHost128KeepTheirOriginalCapacity() {
        for (limits in listOf(RpcLimits(), RpcLimits.host128())) {
            assertEquals(128, limits.trustedClients)
            assertEquals(128, limits.runningCalls)
            assertEquals(256, limits.queuedCalls)
            assertEquals(64L * 1_048_576, limits.payloadBytes)
            assertEquals(32L * 1_048_576, limits.resultCacheBytes)
            assertEquals(131_072, limits.totalRecords)
        }
    }

    @Test fun host256OnlyRaisesHostWideCapacityAndStillFitsTheCoreProfile() {
        val limits = RpcLimits.host256()
        assertEquals(256, limits.trustedClients)
        assertEquals(256, limits.runningCalls)
        assertEquals(512, limits.queuedCalls)
        assertEquals(128L * 1_048_576, limits.payloadBytes)
        assertEquals(64L * 1_048_576, limits.resultCacheBytes)
        assertEquals(262_144, limits.totalRecords)
        assertEquals(8, limits.callsPerClient)
        assertEquals(1_024, limits.recordsPerClient)
        val profile = P2pSessionProfile({ PeerAdmission.Rejected }, PayloadBudget(limits.payloadBytes),
            limits.trustedClients)
        assertEquals(256, profile.maxTrustedSessions)
        assertEquals(4, profile.maxEnrollmentSessions)
        assertEquals(16, profile.maxInboundHandshakes)
        assertEquals(16, profile.maxQueuedMessagesPerSession)
        assertEquals(4L * 1_048_576, profile.maxQueuedBytesPerSession)
    }

    @Test fun host256IsAnUpperBoundNotPermissionFor512OrLargerPerClientExposure() {
        assertFailsWith<IllegalArgumentException> { RpcLimits(trustedClients = 257) }
        assertFailsWith<IllegalArgumentException> { RpcLimits(runningCalls = 257) }
        assertFailsWith<IllegalArgumentException> { RpcLimits(queuedCalls = 513) }
        assertFailsWith<IllegalArgumentException> { RpcLimits(callsPerClient = 9) }
        assertFailsWith<IllegalArgumentException> { RpcLimits(recordsPerClient = 1_025) }
        assertFailsWith<IllegalArgumentException> { RpcLimits(totalRecords = 262_145) }
        assertFailsWith<IllegalArgumentException> { RpcLimits(payloadBytes = 128L * 1_048_576 + 1) }
        assertFailsWith<IllegalArgumentException> { RpcLimits(resultCacheBytes = 64L * 1_048_576 + 1) }
        assertFailsWith<IllegalArgumentException> { RpcLimits(payloadBytes = 100, resultCacheBytes = 101) }
        assertFailsWith<IllegalArgumentException> {
            P2pSessionProfile({ PeerAdmission.Trusted }, PayloadBudget(1024), 257)
        }
    }
}
