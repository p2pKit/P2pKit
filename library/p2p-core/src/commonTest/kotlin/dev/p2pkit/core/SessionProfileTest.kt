package dev.p2pkit.core

import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class SessionProfileTest {
    @Test
    fun reservationRefusalAndResizeConserveCapacity() {
        val budget = PayloadBudget(100)
        val first = assertNotNull(budget.tryReserve(80))
        assertNull(budget.tryReserve(21))
        assertEquals(80L, budget.retainedBytes.value)
        assertTrue(first.shrinkTo(20))
        val second = assertNotNull(budget.tryReserve(80))
        assertEquals(100L, budget.retainedBytes.value)
        first.release()
        first.release()
        assertFalse(first.shrinkTo(0))
        second.release()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun concurrentOwnersReleaseExactlyTheirReservations() = runTest {
        val budget = PayloadBudget(128)
        (0 until 128).map {
            async {
                val lease = assertNotNull(budget.tryReserve(1))
                lease.release()
                lease.release()
            }
        }.awaitAll()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun missingIdentityAndAdmissionExceptionsFailClosed() {
        val profile = P2pSessionProfile(
            admission = { error("application admission failed") },
            payloadBudget = PayloadBudget(1024),
            maxTrustedSessions = 1
        )
        assertEquals(PeerAdmission.Rejected, profile.decide(PeerIdentity(PeerId("unsigned"))))
        val identity = PeerIdentity(PeerId("signed"), PeerFingerprint.fromDigest(ByteArray(32)))
        assertEquals(PeerAdmission.Rejected, profile.decide(identity))
    }
}
