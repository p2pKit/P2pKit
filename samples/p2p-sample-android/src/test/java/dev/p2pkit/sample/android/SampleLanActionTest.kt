package dev.p2pkit.sample.android

import dev.p2pkit.core.FeatureState
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.permission.P2pPermission
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Real VM actions with inert boundaries, not permission-dialog, radio, ART37 or authenticated-traffic evidence. */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], manifest = Config.NONE)
class SampleLanActionTest {
    @Test
    fun deniedRoomStartCleansItsKitAndGrantCallbackDoesNotReplayTheStart() = runTest {
        withSampleViewModel {
            room.permissions.missing = LOCAL_NETWORK
            vm.start()
            runCurrent()
            assertEquals(1, roomCreations)
            assertEquals(0, room.advertiseCalls)
            assertEquals(0, room.discoveryCalls)
            assertEquals(1, room.stopCalls)
            assertFalse(vm.isStarting.value)
            assertFalse(vm.isRunning.value)
            assertFalse(vm.cleanupPending.value)
            assertEquals(LOCAL_NETWORK, vm.lanPermissionState.value.missing)

            room.permissions.missing = emptyList()
            vm.onLanPermissionRequestResult()
            vm.onLanPermissionRequestResult()
            runCurrent()
            assertEquals(1, roomCreations)
            assertEquals(0, room.advertiseCalls)
            vm.start() // A fresh explicit action constructs/checks a room, not a retained callback.
            runCurrent()
            assertEquals(2, roomCreations)
            assertEquals(1, room.advertiseCalls)
            assertEquals(1, room.discoveryCalls)
            assertTrue(vm.isRunning.value)
        }
    }

    @Test
    fun requestLaunchFailureDuplicateResultsAndRevocationNeverInitiateAnAction() = runTest {
        withSampleViewModel {
            vm.start()
            runCurrent()
            room.permissions.missing = LOCAL_NETWORK
            vm.refreshLanPermissions()
            runCurrent()
            vm.requestLanAccess { throw IllegalStateException("synthetic launcher unavailable") }
            assertFalse(vm.lanPermissionState.value.requestInFlight)

            val requested = mutableListOf<String>()
            vm.requestLanAccess { requested += it }
            vm.requestLanAccess { requested += it }
            assertEquals(listOf(ACCESS_LOCAL_NETWORK_PERMISSION), requested)
            assertTrue(vm.lanPermissionState.value.requestInFlight)
            // Regardless of an OS callback's Boolean, a still-denied live reporter stays denied.
            vm.onLanPermissionRequestResult()
            runCurrent()
            assertEquals(LOCAL_NETWORK, vm.lanPermissionState.value.missing)
            room.permissions.missing = emptyList()
            vm.onLanPermissionRequestResult()
            vm.onLanPermissionRequestResult()
            runCurrent()
            assertTrue(vm.lanPermissionState.value.missing.isEmpty())
            assertFalse(vm.lanPermissionState.value.requestInFlight)
            assertEquals(1, room.advertiseCalls)
            assertEquals(1, room.discoveryCalls)
            assertEquals(0, room.connectCalls)

            room.permissions.missing = LOCAL_NETWORK
            vm.onLanPermissionRequestResult()
            runCurrent()
            assertEquals(LOCAL_NETWORK, vm.lanPermissionState.value.missing)
            vm.notifyBackgrounded()
            vm.requestLanAccess { requested += it }
            assertEquals(1, requested.size)
            vm.stop() // No permission grant is needed to retire the owned room.
            runCurrent()
            vm.onLanPermissionRequestResult() // A late result after Stop has no action to replay.
            runCurrent()
            assertEquals(1, roomCreations)
            assertEquals(1, room.stopCalls)
            assertEquals(0, smokeCreations)
        }
    }

    @Test
    fun connectFeatureEnableAndAutoMeshUseLivePermissionsButDisableAndStopDoNot() = runTest {
        withSampleViewModel {
            vm.start()
            runCurrent()
            room.permissions.missing = LOCAL_NETWORK
            vm.toggleAdvertising()
            vm.toggleDiscovery()
            vm.connect(peer())
            vm.toggleAutoMesh()
            runCurrent()
            assertEquals(1, room.stopAdvertisingCalls)
            assertEquals(1, room.stopDiscoveryCalls)
            assertEquals(0, room.connectCalls)
            assertFalse(vm.autoMesh.value)
            vm.toggleAdvertising()
            vm.toggleDiscovery()
            runCurrent()
            assertEquals(1, room.advertiseCalls)
            assertEquals(1, room.discoveryCalls)
            assertFalse(vm.advertising.value)
            assertFalse(vm.discovering.value)

            room.permissions.missing = emptyList()
            vm.onLanPermissionRequestResult()
            runCurrent()
            assertEquals(1, room.advertiseCalls)
            assertEquals(1, room.discoveryCalls)
            vm.toggleAdvertising()
            vm.toggleDiscovery()
            vm.connect(peer())
            vm.toggleAutoMesh()
            runCurrent()
            assertEquals(2, room.advertiseCalls)
            assertEquals(2, room.discoveryCalls)
            assertEquals(1, room.connectCalls) // The inert dial deliberately fails after this boundary.
            assertTrue(vm.autoMesh.value)

            room.permissions.missing = LOCAL_NETWORK
            room.peers.value = listOf(peer())
            runCurrent()
            assertEquals(1, room.connectCalls)
            assertFalse(vm.autoMesh.value)
            room.permissions.missing = emptyList()
            vm.onLanPermissionRequestResult()
            room.peers.value = listOf(peer("z-second-peer"))
            runCurrent()
            assertEquals(1, room.connectCalls) // Grant plus peer churn cannot resume a denied mesh intent.
            vm.toggleAutoMesh()
            runCurrent()
            assertEquals(2, room.connectCalls)
            vm.stop()
            runCurrent()
            assertEquals(1, room.stopCalls)
        }
    }

    @Test
    fun stopWinsOverALateNonCooperativeConnectPermissionCheck() = runTest {
        withSampleViewModel {
            vm.start()
            runCurrent()
            val check = barrier()
            room.permissions.beforeCheck = { withContext(NonCancellable) { check.await() } }
            vm.connect(peer())
            runCurrent()
            assertEquals(listOf(peer().id.value), vm.pendingConnectPeerIds.toList())
            vm.stop()
            runCurrent()
            assertEquals(1, room.stopCalls)
            check.complete(Unit)
            runCurrent()
            assertEquals(0, room.connectCalls)
            assertTrue(vm.pendingConnectPeerIds.isEmpty())
            assertFalse(vm.isRunning.value)
        }
    }

    @Test
    fun deniedForegroundRestoreNeedsANewExplicitFeatureActionAfterGrant() = runTest {
        withSampleViewModel {
            vm.start()
            runCurrent()
            vm.notifyBackgrounded()
            room.advertisingState.value = FeatureState.Idle // Model the SDK's settled background stop.
            room.discoveryState.value = FeatureState.Idle
            room.permissions.missing = LOCAL_NETWORK
            vm.notifyForegrounded()
            runCurrent()
            assertEquals(1, room.advertiseCalls)
            assertEquals(1, room.discoveryCalls)
            assertFalse(vm.advertising.value)
            assertFalse(vm.discovering.value)
            room.permissions.missing = emptyList()
            vm.onLanPermissionRequestResult()
            runCurrent()
            assertEquals(1, room.advertiseCalls)
            assertEquals(1, room.discoveryCalls)
            vm.toggleAdvertising()
            vm.toggleDiscovery()
            runCurrent()
            assertEquals(2, room.advertiseCalls)
            assertEquals(2, room.discoveryCalls)
        }
    }

    @Test
    fun lateForegroundChecksCannotRestartOutsideTheirOriginalEpisode() = runTest {
        withSampleViewModel {
            vm.start()
            runCurrent()
            vm.notifyBackgrounded()
            room.advertisingState.value = FeatureState.Idle
            room.discoveryState.value = FeatureState.Idle
            val check = barrier()
            room.permissions.beforeCheck = { withContext(NonCancellable) { check.await() } }
            vm.notifyForegrounded()
            runCurrent()
            vm.notifyBackgrounded()
            check.complete(Unit)
            runCurrent()
            assertEquals(1, room.advertiseCalls)
            assertEquals(1, room.discoveryCalls)
            vm.notifyForegrounded() // A genuinely new episode may restore the still-requested features.
            runCurrent()
            assertEquals(2, room.advertiseCalls)
            assertEquals(2, room.discoveryCalls)
        }
    }

    @Test
    fun revocationWhileBackgroundStopIsSettlingCannotReplayRestoreAfterALaterGrant() = runTest {
        withSampleViewModel {
            vm.start()
            runCurrent()
            vm.notifyBackgrounded()
            // Keep both feature states Active to model an asynchronous background pause still in flight.
            vm.notifyForegrounded()
            runCurrent()
            room.permissions.missing = LOCAL_NETWORK
            vm.refreshLanPermissions()
            runCurrent()
            room.permissions.missing = emptyList()
            vm.onLanPermissionRequestResult()
            room.advertisingState.value = FeatureState.Idle
            room.discoveryState.value = FeatureState.Idle
            runCurrent()
            assertEquals(1, room.advertiseCalls)
            assertEquals(1, room.discoveryCalls)
            assertFalse(vm.advertising.value)
            assertFalse(vm.discovering.value)
            vm.toggleAdvertising()
            vm.toggleDiscovery()
            runCurrent()
            assertEquals(2, room.advertiseCalls)
            assertEquals(2, room.discoveryCalls)
        }
    }

    @Test
    fun kmpDenialBeforeAdvertisingAndRevocationBeforeDialBothCleanTheOwnedKit() = runTest {
        withSampleViewModel {
            smoke.permissions.missing = LOCAL_NETWORK
            vm.runKmpConsumerSmoke()
            runCurrent()
            assertEquals(1, smokeCreations)
            assertEquals(0, smoke.advertiseCalls)
            assertEquals(0, smoke.discoveryCalls)
            assertEquals(1, smoke.stopCalls)
            assertFalse(vm.kmpSmokeBusy.value)
            assertFalse(admission.smokeOwnsKit)

            smoke.permissions.missing = emptyList()
            vm.onLanPermissionRequestResult()
            runCurrent()
            assertEquals(1, smokeCreations)
            vm.runKmpConsumerSmoke()
            runCurrent()
            assertEquals(1, smoke.advertiseCalls)
            assertEquals(1, smoke.discoveryCalls)
            assertEquals(1, smoke.peers.subscriptionCount.value)
            smoke.permissions.missing = LOCAL_NETWORK
            smoke.peers.value = listOf(peer())
            runCurrent()
            assertEquals(0, smoke.connectCalls)
            assertEquals(2, smoke.stopCalls)
            assertFalse(vm.kmpSmokeBusy.value)
            assertFalse(admission.smokeOwnsKit)
            smoke.permissions.missing = emptyList()
            vm.runKmpConsumerSmoke()
            runCurrent()
            assertEquals(1, smoke.connectCalls)
            assertEquals(3, smoke.stopCalls)
        }
    }

    @Test
    fun kmpPermissionWaitCannotCrossAForegroundEpisodeOrReplayOnGrant() = runTest {
        withSampleViewModel {
            val check = barrier()
            smoke.permissions.beforeCheck = { withContext(NonCancellable) { check.await() } }
            vm.runKmpConsumerSmoke()
            runCurrent()
            assertEquals(1, smokeCreations)
            assertEquals(0, smoke.advertiseCalls)
            vm.notifyBackgrounded()
            vm.notifyForegrounded()
            check.complete(Unit)
            runCurrent()
            vm.onLanPermissionRequestResult()
            runCurrent()
            assertEquals(0, smoke.advertiseCalls)
            assertEquals(0, smoke.discoveryCalls)
            assertEquals(1, smoke.stopCalls)
            assertFalse(vm.kmpSmokeBusy.value)
            assertEquals(1, smokeCreations)
        }
    }

    @Test
    fun clearedViewModelWaitsForSmokeCleanupWithoutASecondStopOrLeakedBusyState() = runTest {
        withSampleViewModel {
            val check = barrier().also { smoke.permissions.beforeCheck = { it.await() } }
            val cleanup = barrier().also { smoke.beforeStop = { it.await() } }
            vm.runKmpConsumerSmoke()
            runCurrent()
            assertFalse(check.isCompleted)
            clearViewModel()
            runCurrent()
            assertEquals(0, smoke.advertiseCalls)
            assertEquals(1, smoke.stopCalls)
            assertTrue(vm.kmpSmokeBusy.value)
            vm.start()
            assertEquals(0, roomCreations)
            cleanup.complete(Unit)
            runCurrent()
            assertEquals(1, smoke.stopCalls)
            assertFalse(vm.kmpSmokeBusy.value)
            assertFalse(vm.currentRunAdmission().smokeOwnsKit)
        }
    }

    @Test
    fun permissionLookupErrorsFailClosedWithoutBlockingDisableOrCleanup() = runTest {
        withSampleViewModel {
            vm.start()
            runCurrent()
            room.permissions.failure = SecurityException("synthetic permission service failure")
            vm.toggleAdvertising()
            vm.toggleDiscovery()
            runCurrent()
            vm.toggleAdvertising()
            vm.toggleDiscovery()
            vm.connect(peer())
            vm.toggleAutoMesh()
            runCurrent()
            assertEquals(1, room.stopAdvertisingCalls)
            assertEquals(1, room.stopDiscoveryCalls)
            assertEquals(1, room.advertiseCalls)
            assertEquals(1, room.discoveryCalls)
            assertEquals(0, room.connectCalls)
            assertTrue(vm.lanPermissionState.value.checkFailed)
            assertFalse(vm.autoMesh.value)
            vm.stop()
            runCurrent()
            assertEquals(1, room.stopCalls)
        }
    }

    private fun peer(id: String = "z-synthetic-peer"): Peer = Peer(
        PeerId(id), "Synthetic peer", Platform.ANDROID, setOf(TransportKind.LAN)
    )

    private companion object {
        val LOCAL_NETWORK = listOf(P2pPermission.LocalNetwork)
    }
}
