package dev.p2pkit.transport.lan

import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertNotEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class ApplePathMonitorCallbackStateTest {

    @Test
    fun retiredCallbackCannotOverwriteRestartedMonitorFingerprints() {
        val state = ApplePathMonitorCallbackState()
        val retired = state.begin()
        assertNotNull(
            state.publish(
                owner = retired,
                isSatisfied = true,
                interfaceFingerprint = 1,
                addressFingerprint = 11uL
            )
        )
        assertTrue(state.detach(retired))

        val current = state.begin()
        assertNotEquals(retired.generation, current.generation)
        val initial = assertNotNull(
            state.publish(
                owner = current,
                isSatisfied = true,
                interfaceFingerprint = 4,
                addressFingerprint = 44uL
            )
        )
        assertTrue(initial.isFirstSatisfied)
        assertFalse(initial.needsRebind)

        assertNull(
            state.publish(
                owner = retired,
                isSatisfied = true,
                interfaceFingerprint = 8,
                addressFingerprint = 88uL
            )
        )
        val stableCurrent = assertNotNull(
            state.publish(
                owner = current,
                isSatisfied = true,
                interfaceFingerprint = 4,
                addressFingerprint = 44uL
            )
        )
        assertFalse(stableCurrent.interfaceChanged)
        assertFalse(stableCurrent.addressChanged)
        assertFalse(stableCurrent.needsRebind)
        assertFalse(retired.isActive())
        assertTrue(current.isActive())
    }

    @Test
    fun currentCallbackPublishesTopologyChangeAndRetirementRevokesDelayedAdmission() {
        val state = ApplePathMonitorCallbackState()
        val current = state.begin()
        assertNotNull(
            state.publish(
                owner = current,
                isSatisfied = true,
                interfaceFingerprint = 1,
                addressFingerprint = 11uL
            )
        )

        val changed = assertNotNull(
            state.publish(
                owner = current,
                isSatisfied = true,
                interfaceFingerprint = 9,
                addressFingerprint = 99uL
            )
        )
        assertTrue(changed.interfaceChanged)
        assertTrue(changed.addressChanged)
        assertTrue(changed.needsRebind)
        assertTrue(current.isActive())

        assertTrue(state.detach(current))
        assertFalse(current.isActive())
    }
}
