package dev.p2pkit.sample.android

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** #376 is the cleanup/name predicate, not #374's distinct room/KMP ownership guard. */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], manifest = Config.NONE)
class SampleCleanupNameAdmissionTest {
    @Test
    fun blankNameBlocksNewRoomButNotTheActualRetainedCleanupAction() = runTest {
        withSampleViewModel {
            vm.updateDeviceName("  ")
            assertFalse(admission.canUseStartAction(vm.deviceName))
            vm.start()
            runCurrent()
            assertEquals(0, roomCreations)

            vm.updateDeviceName("Synthetic room")
            vm.start()
            runCurrent()
            room.stopFailure = IllegalStateException("synthetic unresolved cleanup")
            vm.stop()
            runCurrent()
            vm.updateDeviceName("")
            assertTrue(admission.canUseStartAction(vm.deviceName))
            vm.start()
            runCurrent()
            assertEquals(1, roomCreations)
            assertEquals(2, room.stopCalls)
            assertTrue(vm.cleanupPending.value)
            assertTrue(admission.canUseStartAction(vm.deviceName))

            room.stopFailure = null // Inert successful cleanup, not a promise of real SDK retryability.
            vm.start()
            runCurrent()
            assertEquals(1, roomCreations)
            assertEquals(3, room.stopCalls)
            assertFalse(vm.cleanupPending.value)
            assertFalse(admission.canUseStartAction(vm.deviceName))
            vm.start()
            runCurrent()
            assertEquals(1, roomCreations)
        }
    }
}
