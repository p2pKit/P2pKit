package dev.p2pkit.sample.android.rpclab

import android.content.Intent
import dev.p2pkit.sample.android.MainActivity
import dev.p2pkit.sample.android.SAMPLE_OPEN_RPC_ACTION
import dev.p2pkit.sample.android.withSampleViewModel
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertSame
import kotlin.test.assertTrue
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config

/** Process admission/shortcut controls with no network or native RPC creation. */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], manifest = Config.NONE)
class RpcLabRoomAdmissionTest {
    @Test fun oldProcessRuntimeBlocksFreshViewModelsUntilOriginalRetirement() = runTest {
        val owner = RpcLabProcessRuntime.owner
        assertFalse(owner.occupied)
        val creator = Job()
        val token = owner.beginCreation(creator)
        try {
            withSampleViewModel {
                vm.start()
                vm.runKmpConsumerSmoke()
                runCurrent()
                assertEquals(0, roomCreations)
                assertEquals(0, smokeCreations)
                assertTrue(vm.currentRunAdmission().rpcRuntimeOccupied)
                val entry = assertNotNull(vm.enterRpcSection()) // Cleanup recovery remains reachable, not a new role.
                assertTrue(vm.leaveRpcSection(entry))
            }
            assertTrue(owner.occupied) // Destroying the first VM is not RPC cleanup evidence.
            withSampleViewModel {
                vm.start()
                vm.runKmpConsumerSmoke()
                runCurrent()
                assertFalse(admission.canRunKmpSmoke)
                assertEquals(0, roomCreations)
                assertEquals(0, smokeCreations)
                creator.complete()
                owner.finishCreation(token) // The original creator's actual final boundary releases its reservation.
                runCurrent()
                assertFalse(owner.occupied)
                assertTrue(admission.canRunKmpSmoke)
                vm.start()
                runCurrent()
                assertEquals(1, roomCreations)
            }
        } finally {
            creator.complete()
            if (owner.snapshotFor(token) != null) owner.finishCreation(token)
        }
    }

    @Test fun legacyShortcutOnlyRoutesToCanonicalMainAndCannotCreateAnRpcOwner() {
        val before = RpcLabProcessRuntime.owner.snapshot()
        val controller = Robolectric.buildActivity(RpcLabActivity::class.java).create()
        try {
            val activity = controller.get()
            val destination = assertNotNull(shadowOf(activity).nextStartedActivity)
            assertEquals(MainActivity::class.java.name, destination.component?.className)
            assertEquals(SAMPLE_OPEN_RPC_ACTION, destination.action)
            assertTrue(destination.extras == null || destination.extras!!.isEmpty)
            assertTrue(destination.flags and Intent.FLAG_ACTIVITY_CLEAR_TOP != 0)
            assertTrue(destination.flags and Intent.FLAG_ACTIVITY_SINGLE_TOP != 0)
            assertTrue(activity.isFinishing)
            assertSame(before, RpcLabProcessRuntime.owner.snapshot())
        } finally { controller.destroy() }
    }
}
