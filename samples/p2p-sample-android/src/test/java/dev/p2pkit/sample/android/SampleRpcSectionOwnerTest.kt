package dev.p2pkit.sample.android

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Real sample VM admission with inert kit factories: no RPC sockets, permissions, or device claims. */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], manifest = Config.NONE)
class SampleRpcSectionOwnerTest {
    @Test fun queuedRoomAndSmokeActionsAreRejectedBeforeNavigationRecomposes() = runTest {
        withSampleViewModel {
            val queuedRoomStart = vm::start
            val queuedSmokeStart = vm::runKmpConsumerSmoke
            val entry = assertNotNull(vm.enterRpcSection())
            assertSame(entry, vm.rpcSection.value)
            // Deliberately dispatch stale handlers before the StateFlow collector or any launched work runs.
            queuedRoomStart()
            queuedSmokeStart()
            assertNull(vm.enterRpcSection())
            runCurrent()
            assertEquals(0, roomCreations)
            assertEquals(0, smokeCreations)
            assertFalse(admission.canStartOrRetryCleanup)
            assertFalse(admission.canRunKmpSmoke)
            assertTrue(vm.leaveRpcSection(entry))
            queuedRoomStart()
            runCurrent()
            assertEquals(1, roomCreations)
            assertTrue(vm.isRunning.value)
        }
    }

    @Test fun staleAndDuplicateExitCallbacksCannotReleaseReplacementEntry() = runTest {
        withSampleViewModel {
            val first = assertNotNull(vm.enterRpcSection())
            assertTrue(vm.leaveRpcSection(first))
            assertFalse(vm.leaveRpcSection(first))
            val replacement = assertNotNull(vm.enterRpcSection())
            assertFalse(vm.leaveRpcSection(first))
            assertSame(replacement, vm.rpcSection.value)
            vm.start()
            vm.runKmpConsumerSmoke()
            runCurrent()
            assertEquals(0, roomCreations)
            assertEquals(0, smokeCreations)
            assertTrue(vm.leaveRpcSection(replacement))
            assertNull(vm.rpcSection.value)
        }
    }

    @Test fun roomStartAndCleanupEachBlockRpcReservationUntilActuallyIdle() = runTest {
        withSampleViewModel {
            val cleanup = barrier().also { room.beforeStop = { it.await() } }
            vm.start()
            assertNull(vm.enterRpcSection())
            runCurrent()
            assertNull(vm.enterRpcSection())
            vm.stop()
            assertNull(vm.enterRpcSection())
            runCurrent()
            assertNull(vm.enterRpcSection())
            cleanup.complete(Unit)
            runCurrent()
            val entry = assertNotNull(vm.enterRpcSection())
            assertTrue(vm.leaveRpcSection(entry))
            assertEquals(1, roomCreations)
        }
    }

    @Test fun refusedShortcutRequestDoesNotInterruptRoomOrAutoOpenAfterStop() = runTest {
        withSampleViewModel {
            vm.start()
            runCurrent()
            vm.openRpcFromNavigation()
            assertNull(vm.rpcSection.value)
            assertTrue(vm.isRunning.value)
            assertEquals(0, room.stopCalls)
            assertNotNull(vm.rpcNavigationMessage.value)
            vm.stop()
            runCurrent()
            assertNull(vm.rpcSection.value)
            vm.openRpcFromNavigation() // A new, explicit request is required after cleanup.
            val entry = assertNotNull(vm.rpcSection.value)
            assertNull(vm.rpcNavigationMessage.value)
            assertTrue(vm.leaveRpcSection(entry))
        }
    }

    @Test fun backgroundAndClearedOwnersCannotAcquireOrReplaySectionExit() = runTest {
        withSampleViewModel {
            vm.notifyBackgrounded()
            assertNull(vm.enterRpcSection())
            vm.notifyForegrounded()
            val entry = assertNotNull(vm.enterRpcSection())
            vm.notifyBackgrounded()
            assertFalse(vm.leaveRpcSection(entry))
            assertSame(entry, vm.rpcSection.value)
            vm.notifyForegrounded()
            assertSame(entry, vm.rpcSection.value)
            assertTrue(vm.leaveRpcSection(entry))
            clearViewModel()
            assertNull(vm.enterRpcSection())
            assertFalse(vm.leaveRpcSection(entry))
        }
    }
}
