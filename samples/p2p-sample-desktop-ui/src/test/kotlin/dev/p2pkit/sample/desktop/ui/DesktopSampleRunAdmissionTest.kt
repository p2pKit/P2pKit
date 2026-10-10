package dev.p2pkit.sample.desktop.ui

import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class DesktopSampleRunAdmissionTest {
    @Test fun rpcReservesAdmissionSynchronouslyAndAnUnretiredRoomCannotBeReplaced() {
        val admission = DesktopSampleRunAdmission()
        assertNull(admission.reserveRpc(ordinaryIdle = false))
        assertTrue(admission.ordinaryAllowed)
        val entry = assertNotNull(admission.reserveRpc(ordinaryIdle = true))
        assertFalse(admission.ordinaryAllowed)
        assertNull(admission.reserveRpc(ordinaryIdle = true))
        assertFalse(admission.releaseRpc(Any()))
        assertFalse(admission.ordinaryAllowed)
        assertTrue(admission.releaseRpc(entry))
        assertTrue(admission.ordinaryAllowed)
    }

    @Test fun staleCloseCannotReleaseAReplacementRpcSection() {
        val admission = DesktopSampleRunAdmission()
        val first = assertNotNull(admission.reserveRpc(true))
        assertTrue(admission.releaseRpc(first))
        val second = assertNotNull(admission.reserveRpc(true))
        assertFalse(admission.releaseRpc(first))
        assertFalse(admission.ordinaryAllowed)
        assertTrue(admission.releaseRpc(second))
    }
}
