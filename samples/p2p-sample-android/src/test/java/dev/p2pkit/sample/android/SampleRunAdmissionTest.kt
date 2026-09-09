package dev.p2pkit.sample.android

import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Real VM actions and shared Demo flow with inert kits; not Android radio or security evidence. */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], manifest = Config.NONE)
class SampleRunAdmissionTest {
    @Test
    fun smokeOwnsAdmissionThroughDiscoveryAndCleanupBeforeRoomMayStart() = runTest {
        withSampleViewModel {
            val discovery = barrier().also { smoke.beforeDiscovery = { it.await() } }
            val cleanup = barrier().also { smoke.beforeStop = { it.await() } }

            vm.runKmpConsumerSmoke()
            vm.start() // Before either launched coroutine has run.
            assertEquals(0, roomCreations)
            runCurrent()
            assertEquals(1, smokeCreations)
            assertEquals(1, smoke.advertiseCalls)
            assertEquals(1, smoke.discoveryCalls)
            assertFalse(admission.canStartOrRetryCleanup)

            vm.start()
            assertEquals(0, roomCreations)
            discovery.complete(Unit)
            runCurrent()
            advanceTimeBy(10_000)
            runCurrent()
            assertEquals(1, smoke.stopCalls)
            assertTrue(vm.kmpSmokeBusy.value)
            vm.start()
            assertEquals(0, roomCreations)

            cleanup.complete(Unit)
            runCurrent()
            assertFalse(vm.kmpSmokeBusy.value)
            assertTrue(admission.canStartOrRetryCleanup)
            vm.start()
            runCurrent()
            assertEquals(1, roomCreations)
            assertTrue(vm.isRunning.value)
        }
    }

    @Test
    fun roomStartingRunningAndStoppingEachRefuseAnotherSmokeOwner() = runTest {
        withSampleViewModel {
            val starting = barrier().also { room.beforeAdvertising = { it.await() } }
            val stopping = barrier().also { room.beforeStop = { it.await() } }
            vm.start()
            vm.runKmpConsumerSmoke()
            runCurrent()
            assertTrue(vm.isStarting.value)
            assertFalse(admission.canRunKmpSmoke)
            assertEquals(0, smokeCreations)

            starting.complete(Unit)
            runCurrent()
            assertTrue(vm.isRunning.value)
            vm.runKmpConsumerSmoke()
            assertEquals(0, smokeCreations)
            vm.stop()
            runCurrent()
            assertTrue(vm.isStopping.value)
            vm.runKmpConsumerSmoke()
            assertEquals(0, smokeCreations)

            stopping.complete(Unit)
            runCurrent()
            assertTrue(admission.canRunKmpSmoke)
            vm.runKmpConsumerSmoke()
            runCurrent()
            assertEquals(1, smokeCreations)
        }
    }

    @Test
    fun failedRoomStopRetainsOwnershipAndStartRetriesCleanupInsteadOfCreatingAKit() = runTest {
        withSampleViewModel {
            vm.start()
            runCurrent()
            room.stopFailure = IllegalStateException("synthetic unresolved cleanup")
            vm.stop()
            runCurrent()
            assertFalse(vm.isRunning.value)
            assertFalse(vm.isStopping.value)
            assertTrue(vm.cleanupPending.value)
            assertTrue(admission.canStartOrRetryCleanup)
            assertFalse(admission.canRunKmpSmoke)
            vm.runKmpConsumerSmoke()
            runCurrent()
            assertEquals(0, smokeCreations)

            // A successful fake retry tests the sample's retained-owner contract;
            // it does not assert that every real SDK stop failure is recoverable.
            room.stopFailure = null
            vm.start()
            runCurrent()
            assertEquals(1, roomCreations)
            assertEquals(2, room.stopCalls)
            assertFalse(vm.cleanupPending.value)
            assertTrue(admission.canRunKmpSmoke)
            vm.runKmpConsumerSmoke()
            runCurrent()
            assertEquals(1, smokeCreations)
        }
    }

    @Test
    fun failedStartupCleanupAlsoBlocksSmokeUntilItsOwnerIsRetired() = runTest {
        withSampleViewModel {
            room.advertisingFailure = IllegalStateException("synthetic startup failure")
            room.stopFailure = IllegalStateException("synthetic unresolved cleanup")
            vm.start()
            runCurrent()
            assertFalse(vm.isStarting.value)
            assertFalse(vm.isRunning.value)
            assertTrue(vm.cleanupPending.value)
            vm.runKmpConsumerSmoke()
            runCurrent()
            assertEquals(0, smokeCreations)

            room.stopFailure = null
            vm.start()
            runCurrent()
            assertEquals(1, roomCreations)
            assertEquals(2, room.stopCalls)
            assertFalse(vm.cleanupPending.value)
            assertTrue(admission.canRunKmpSmoke)
        }
    }

    @Test
    fun failedSmokeStopRetainsAdmissionEvenWhenRetryReturnsTheSameLatchedFailure() = runTest {
        withSampleViewModel {
            smoke.stopFailure = IllegalStateException("synthetic latched cleanup failure")
            vm.runKmpConsumerSmoke()
            runCurrent()
            advanceTimeBy(10_000)
            runCurrent()
            assertEquals(1, smoke.stopCalls)
            assertFalse(vm.kmpSmokeBusy.value)
            assertTrue(admission.canRetryKmpCleanup)
            assertFalse(admission.canStartOrRetryCleanup)
            assertFalse(admission.canRunKmpSmoke)
            vm.start()
            vm.runKmpConsumerSmoke() // Retry cleanup, never create another smoke kit.
            runCurrent()
            assertEquals(0, roomCreations)
            assertEquals(1, smokeCreations)
            assertEquals(2, smoke.stopCalls)
            assertFalse(admission.canStartOrRetryCleanup)
            assertTrue(vm.kmpSmokeResult.value.orEmpty().contains("restarting the app"))

            // An independently successful inert cleanup permits retirement. Real SDK stop can latch failure.
            smoke.stopFailure = null
            vm.runKmpConsumerSmoke()
            runCurrent()
            assertEquals(1, smokeCreations)
            assertEquals(3, smoke.stopCalls)
            assertTrue(admission.canStartOrRetryCleanup)
        }
    }

    @Test
    fun actualSetupButtonsConsumeTheSameObservedAdmissionAsTheViewModel() {
        val relative = "src/main/java/dev/p2pkit/sample/android/MainActivity.kt"
        val source = generateSequence(File(requireNotNull(System.getProperty("user.dir"))).absoluteFile) {
            it.parentFile
        }.flatMap { sequenceOf(File(it, relative), File(it, "samples/p2p-sample-android/$relative")) }
            .first(File::isFile).readText().substringAfter("private fun SetupScreen(")
            .substringBefore("private fun ReconnectChoicePicker(")
        assertTrue(source.contains("val admission by vm.runAdmission.collectAsState(vm.currentRunAdmission())"))
        assertTrue(source.contains("enabled = admission.canUseStartAction(vm.deviceName)"))
        assertTrue(source.contains("enabled = admission.canRunKmpSmoke || admission.canRetryKmpCleanup"))
        assertTrue(source.contains("onClick = vm::start"))
        assertTrue(source.contains("onClick = vm::runKmpConsumerSmoke"))
    }
}
