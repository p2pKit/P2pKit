package dev.p2pkit.sample.android

import android.app.Application
import androidx.lifecycle.ViewModelStore
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Two real VMs share an isolated process broker and inert kits; no radio or native release qualification. */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], manifest = Config.NONE)
class SampleCrossViewModelAdmissionTest {
    private suspend fun TestScope.withSecondViewModel(
        original: SampleViewModelFixture,
        block: suspend (SampleViewModelFixture) -> Unit,
    ) {
        val second = SampleViewModelFixture(original.processOwner)
        val store = ViewModelStore()
        second.vm = P2pKitViewModel(original.vm.getApplication<Application>(), second,
            StandardTestDispatcher(testScheduler), second.processOwner)
        second.clearViewModel = store::clear
        store.put("second", second.vm)
        second.vm.notifyForegrounded()
        try { block(second) } finally {
            second.barriers.forEach { it.complete(Unit) }
            second.room.stopFailure = null
            second.smoke.stopFailure = null
            store.clear()
            runCurrent()
            assertEquals(0, second.room.peers.subscriptionCount.value)
            assertEquals(0, second.smoke.peers.subscriptionCount.value)
        }
    }

    @Test fun rpcEntryReservesProcessBeforeFactoryAndOldVmCannotReleaseReplacement() = runTest {
        withSampleViewModel {
            val original = this
            val first = assertNotNull(vm.enterRpcSection())
            withSecondViewModel(original) { second ->
                second.vm.start()
                second.vm.runKmpConsumerSmoke()
                assertNull(second.vm.enterRpcSection())
                runCurrent()
                assertEquals(0, second.roomCreations)
                assertEquals(0, second.smokeCreations)
                clearViewModel()
                runCurrent()
                val replacement = assertNotNull(second.vm.enterRpcSection())
                assertFalse(vm.leaveRpcSection(first))
                assertSame(replacement, processOwner.state.value)
                assertTrue(second.vm.leaveRpcSection(replacement))
            }
        }
    }

    @Test fun oldVmRoomCleanupBlocksNewRpcAndRoomUntilActualCloseCompletes() = runTest {
        withSampleViewModel {
            val original = this
            val closing = barrier().also { room.beforeStop = { it.await() } }
            vm.start()
            runCurrent()
            val lease = assertNotNull(processOwner.state.value)
            clearViewModel()
            runCurrent()
            assertEquals(1, room.stopCalls)
            withSecondViewModel(original) { second ->
                assertNull(second.vm.enterRpcSection())
                second.vm.start()
                runCurrent()
                assertEquals(0, second.roomCreations)
                assertSame(lease, processOwner.state.value)
                closing.complete(Unit)
                runCurrent()
                val entry = assertNotNull(second.vm.enterRpcSection())
                assertTrue(second.vm.leaveRpcSection(entry))
            }
        }
    }

    @Test fun roomStoppedBeforeStartupDispatchStillRetiresItsOriginalProcessLease() = runTest {
        withSampleViewModel {
            val original = this
            val closing = barrier().also { room.beforeStop = { it.await() } }
            vm.start()
            vm.stop() // Cancel startup before its coroutine body/finally can execute.
            runCurrent()
            withSecondViewModel(original) { second ->
                assertNull(second.vm.enterRpcSection())
                closing.complete(Unit)
                runCurrent()
                assertFalse(vm.isStarting.value)
                val entry = assertNotNull(second.vm.enterRpcSection())
                assertTrue(second.vm.leaveRpcSection(entry))
            }
        }
    }

    @Test fun terminalStopPublicationRejectsReentryBeforeItsProcessLeaseIsReleased() = runTest {
        withSampleViewModel {
            vm.start()
            runCurrent()
            val originalLease = assertNotNull(processOwner.state.value)
            var observedStopping = false
            var checkedReentry = false
            // Resume directly inside the false publication, before cleanup releases the original lease.
            val collector = backgroundScope.launch(UnconfinedTestDispatcher(testScheduler)) {
                vm.isStopping.collect { stopping ->
                    if (stopping) observedStopping = true
                    if (observedStopping && !stopping && !checkedReentry) {
                        checkedReentry = true
                        assertSame(originalLease, processOwner.state.value)
                        assertTrue(vm.currentRunAdmission().canStartOrRetryCleanup)
                        vm.start()
                        vm.runKmpConsumerSmoke()
                        assertEquals(1, roomCreations)
                        assertEquals(0, smokeCreations)
                        assertSame(originalLease, processOwner.state.value)
                    }
                }
            }
            try {
                vm.stop()
                runCurrent()
                assertTrue(checkedReentry, "The terminal-publication race must actually be exercised")
                assertNull(processOwner.state.value)
                assertEquals(1, room.stopCalls)
                vm.start() // A fresh explicit action works after the actual release, without replaying rejected work.
                runCurrent()
                assertEquals(2, roomCreations)
                assertEquals(0, smokeCreations)
                assertTrue(vm.isRunning.value)
                assertFalse(originalLease === processOwner.state.value)
            } finally {
                collector.cancel()
            }
        }
    }

    @Test fun failedFinalRoomCleanupRetainsProcessAcrossVmDestruction() = runTest {
        withSampleViewModel {
            val original = this
            vm.start()
            runCurrent()
            room.stopFailure = IllegalStateException("synthetic final room failure")
            val lease = assertNotNull(processOwner.state.value)
            clearViewModel()
            runCurrent()
            assertTrue(vm.cleanupPending.value)
            withSecondViewModel(original) { second ->
                assertNull(second.vm.enterRpcSection())
                second.vm.start()
                second.vm.runKmpConsumerSmoke()
                runCurrent()
                assertEquals(0, second.roomCreations)
                assertEquals(0, second.smokeCreations)
                assertSame(lease, processOwner.state.value)
            }
            // This deliberately failed inert owner stays retained in this test's private broker, not the app singleton.
            assertSame(lease, processOwner.state.value)
        }
    }

    @Test fun smokeCanceledBeforeFirstDispatchReleasesOnlyItsNeverCreatedOwner() = runTest {
        withSampleViewModel {
            val original = this
            vm.runKmpConsumerSmoke()
            assertNotNull(processOwner.state.value)
            assertEquals(0, smokeCreations)
            clearViewModel()
            runCurrent()
            assertEquals(0, smokeCreations)
            assertNull(processOwner.state.value)
            withSecondViewModel(original) { second ->
                val entry = assertNotNull(second.vm.enterRpcSection())
                assertTrue(second.vm.leaveRpcSection(entry))
            }
        }
    }

    @Test fun smokeInFlightAndItsDelayedFinalCloseBlockNewVmRpc() = runTest {
        withSampleViewModel {
            val original = this
            val closing = barrier().also { smoke.beforeStop = { it.await() } }
            vm.runKmpConsumerSmoke()
            runCurrent()
            assertEquals(1, smokeCreations)
            val lease = assertNotNull(processOwner.state.value)
            clearViewModel()
            runCurrent()
            withSecondViewModel(original) { second ->
                assertNull(second.vm.enterRpcSection())
                second.vm.start()
                runCurrent()
                assertEquals(0, second.roomCreations)
                assertSame(lease, processOwner.state.value)
                closing.complete(Unit)
                runCurrent()
                val entry = assertNotNull(second.vm.enterRpcSection())
                assertTrue(second.vm.leaveRpcSection(entry))
            }
        }
    }

    @Test fun failedSmokeCleanupAfterOldVmClearsNeverAdmitsNewRpc() = runTest {
        withSampleViewModel {
            val original = this
            vm.runKmpConsumerSmoke()
            runCurrent()
            smoke.stopFailure = IllegalStateException("synthetic final smoke failure")
            val lease = assertNotNull(processOwner.state.value)
            clearViewModel()
            runCurrent()
            assertTrue(smoke.stopCalls >= 1)
            withSecondViewModel(original) { second ->
                assertNull(second.vm.enterRpcSection())
                second.vm.start()
                second.vm.runKmpConsumerSmoke()
                runCurrent()
                assertEquals(0, second.roomCreations)
                assertEquals(0, second.smokeCreations)
                assertSame(lease, processOwner.state.value)
            }
            assertSame(lease, processOwner.state.value)
        }
    }
}
