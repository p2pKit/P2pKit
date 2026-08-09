package dev.p2pkit.transport.lan

import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class AppleLifecycleRecoveryCoordinatorTest {

    @Test
    fun backgroundReturnSchedulesExactlyOneRecovery() {
        val coordinator = AppleLifecycleRecoveryCoordinator()

        assertFalse(coordinator.onSignal(AppleLifecycleSignal.WillResignActive))
        assertTrue(coordinator.onSignal(AppleLifecycleSignal.WillEnterForeground))
        assertFalse(coordinator.onSignal(AppleLifecycleSignal.DidBecomeActive))
        assertFalse(coordinator.onSignal(AppleLifecycleSignal.DidBecomeActive))
    }

    @Test
    fun inactiveForegroundDismissalStillSchedulesRecovery() {
        val coordinator = AppleLifecycleRecoveryCoordinator()

        assertFalse(coordinator.onSignal(AppleLifecycleSignal.WillResignActive))
        assertTrue(coordinator.onSignal(AppleLifecycleSignal.DidBecomeActive))
    }

    @Test
    fun successfulPathRebindWhileInactiveSuppressesForegroundRotation() {
        val coordinator = AppleLifecycleRecoveryCoordinator()

        assertFalse(coordinator.onSignal(AppleLifecycleSignal.WillResignActive))
        coordinator.onSuccessfulRebind()
        assertFalse(coordinator.onSignal(AppleLifecycleSignal.WillEnterForeground))
        assertFalse(coordinator.onSignal(AppleLifecycleSignal.DidBecomeActive))
    }

    @Test
    fun laterInactiveEpisodeCanRecoverIndependently() {
        val coordinator = AppleLifecycleRecoveryCoordinator()

        assertFalse(coordinator.onSignal(AppleLifecycleSignal.WillResignActive))
        assertTrue(coordinator.onSignal(AppleLifecycleSignal.DidBecomeActive))
        coordinator.onSuccessfulRebind()

        assertFalse(coordinator.onSignal(AppleLifecycleSignal.WillResignActive))
        assertTrue(coordinator.onSignal(AppleLifecycleSignal.WillEnterForeground))
    }
}
