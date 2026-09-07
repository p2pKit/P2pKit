package dev.p2pkit.sample.android

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.NetworkProvisioningError
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.provisioning.JoinNetworkResult
import dev.p2pkit.core.provisioning.LocalNetworkConfig
import dev.p2pkit.core.provisioning.LocalNetworkResult
import dev.p2pkit.core.provisioning.ManualConnectionInfo
import dev.p2pkit.core.provisioning.NetworkProvisioningEvent
import dev.p2pkit.core.provisioning.NetworkProvisioningManager
import dev.p2pkit.core.provisioning.NetworkProvisioningState
import dev.p2pkit.core.provisioning.NetworkState
import dev.p2pkit.core.provisioning.UnsupportedNetworkProvisioningManager
import dev.p2pkit.core.provisioning.WifiCredentials
import dev.p2pkit.core.provisioning.WifiPassword
import dev.p2pkit.core.provisioning.WifiSecurityType
import java.io.File
import java.util.concurrent.atomic.AtomicReference
import kotlin.concurrent.thread
import kotlin.coroutines.CoroutineContext
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancel
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** Tests the production consumer with real flows and an explicitly drained main-thread scheduler. */
class ProvisioningUiStateTest {
    @Test
    fun systemHotspotStopReplacesSuccessWithItsTypedFailure() = withHarness { h ->
        assertTrue(h.ui.startHotspot())
        h.drain()
        assertIs<LocalNetworkResult.Started>(h.ui.hotspotResult.value)

        h.manager.stopFromSystem()
        h.drain()

        val failure = assertIs<LocalNetworkResult.Failed>(h.ui.hotspotResult.value)
        assertIs<NetworkProvisioningError.HotspotStopped>(failure.error)
        assertFalse(h.ui.busy.value)
    }

    @Test
    fun systemJoinReleaseReplacesSuccessWithItsTypedFailure() = withHarness { h ->
        assertTrue(h.ui.joinHotspot(credentials))
        h.drain()
        assertIs<JoinNetworkResult.Joined>(h.ui.joinResult.value)

        h.manager.releaseFromSystem()
        h.drain()

        val failure = assertIs<JoinNetworkResult.Failed>(h.ui.joinResult.value)
        assertIs<NetworkProvisioningError.JoinFailed>(failure.error)
        assertFalse(h.ui.busy.value)
    }

    @Test
    fun repeatedHotspotStartPreservesSuccessWhenJoinedNetworkOwnsBothSnapshots() = withHarness { h ->
        h.startAndJoin()
        assertSame(NetworkProvisioningState.JoinedNetwork, h.manager.state.value)

        assertTrue(h.ui.startHotspot())
        h.drain()

        assertIs<LocalNetworkResult.Started>(h.ui.hotspotResult.value)
        assertIs<JoinNetworkResult.Joined>(h.ui.joinResult.value)
        assertEquals(2, h.manager.startCalls)
        assertFalse(h.ui.busy.value)
    }

    @Test
    fun systemStopDoesNotEraseAnIndependentJoin() = withHarness { h ->
        h.startAndJoin()
        h.manager.stopFromSystem()
        h.drain()

        assertIs<LocalNetworkResult.Failed>(h.ui.hotspotResult.value)
        assertIs<JoinNetworkResult.Joined>(h.ui.joinResult.value)
        assertSame(NetworkProvisioningState.JoinedNetwork, h.manager.state.value)
    }

    @Test
    fun systemReleaseDoesNotEraseAnIndependentHotspot() = withHarness { h ->
        assertTrue(h.ui.joinHotspot(credentials))
        h.drain()
        assertTrue(h.ui.startHotspot())
        h.drain()

        h.manager.releaseFromSystem()
        h.drain()

        assertIs<JoinNetworkResult.Failed>(h.ui.joinResult.value)
        assertIs<LocalNetworkResult.Started>(h.ui.hotspotResult.value)
        assertSame(NetworkProvisioningState.LocalNetworkRunning, h.manager.state.value)
    }

    @Test
    fun terminalHotspotSignalBeforeApiReturnCannotResurrectTheCard() = withHarness { h ->
        val release = CompletableDeferred<Unit>()
        h.manager.afterStart = { release.await() }
        assertTrue(h.ui.startHotspot())
        h.drain()
        h.manager.stopFromSystem()
        h.drain()

        release.complete(Unit)
        h.drain()

        assertIs<NetworkProvisioningError.HotspotStopped>(
            assertIs<LocalNetworkResult.Failed>(h.ui.hotspotResult.value).error
        )
        assertFalse(h.ui.busy.value)
    }

    @Test
    fun terminalJoinSignalBeforeApiReturnCannotResurrectTheCard() = withHarness { h ->
        val release = CompletableDeferred<Unit>()
        h.manager.afterJoin = { release.await() }
        assertTrue(h.ui.joinHotspot(credentials))
        h.drain()
        h.manager.releaseFromSystem()
        h.drain()

        release.complete(Unit)
        h.drain()

        assertIs<NetworkProvisioningError.JoinFailed>(
            assertIs<JoinNetworkResult.Failed>(h.ui.joinResult.value).error
        )
        assertFalse(h.ui.busy.value)
    }

    @Test
    fun dismissingAnEstablishedJoinSurvivesItsLateApiResultWithoutReleasingIt() = withHarness { h ->
        val release = CompletableDeferred<Unit>()
        h.manager.afterJoin = { release.await() }
        assertTrue(h.ui.joinHotspot(credentials))
        h.drain()
        assertIs<JoinNetworkResult.Joined>(h.ui.joinResult.value)

        h.ui.dismissJoin()
        release.complete(Unit)
        h.drain()

        assertNull(h.ui.joinResult.value)
        assertTrue(h.manager.joinActive)
        assertEquals(0, h.manager.closeCalls)
    }

    @Test
    fun refusedRepeatJoinKeepsTheLiveCardButReportsTheActualFailedOperation() = withHarness { h ->
        h.startAndJoin()
        var reported: JoinNetworkResult? = null

        assertTrue(h.ui.joinHotspot(credentials) { reported = it })
        h.drain()

        assertIs<JoinNetworkResult.Joined>(h.ui.joinResult.value)
        assertIs<JoinNetworkResult.Failed>(reported)
        assertTrue(h.manager.joinActive)
    }

    @Test
    fun aCancelledOperationClearsBusyWithoutCancellingThePresentation() = withHarness { h ->
        h.manager.afterStart = {
            currentCoroutineContext().cancel(CancellationException("synthetic acquisition cancellation"))
            awaitCancellation()
        }

        assertTrue(h.ui.startHotspot())
        h.drain()

        assertFalse(h.ui.busy.value)
        assertTrue(h.job.isActive)
    }

    @Test
    fun cancellationIsNotConvertedToAResultEvenIfAnAcquisitionReturnsNormally() = withHarness { h ->
        var reported = false
        h.manager.afterStart = { currentCoroutineContext().cancel() }

        assertTrue(h.ui.startHotspot { reported = true })
        h.drain()

        assertFalse(reported)
        assertNull(h.ui.hotspotResult.value)
        assertFalse(h.ui.busy.value)
        assertTrue(h.job.isActive)
    }

    @Test
    fun localHotspotStopLeavesTheJoinedNetworkActive() = withHarness { h ->
        h.startAndJoin()
        assertTrue(h.ui.stopHotspot())
        h.drain()

        assertNull(h.ui.hotspotResult.value)
        assertIs<JoinNetworkResult.Joined>(h.ui.joinResult.value)
        assertTrue(h.manager.joinActive)
        assertEquals(1, h.manager.stopCalls)
        assertFalse(h.ui.busy.value)
    }

    @Test
    fun eventSubscriptionExistsBeforeTheFirstOperationCanPublish() = withHarness { h ->
        assertEquals(1, h.manager.events.subscriptionCount.value)
        assertTrue(h.ui.startHotspot())
        assertTrue(h.ui.busy.value)
        assertTrue(h.ui.joinBusy.value)
        assertEquals(0, h.manager.startCalls)
        h.drain()
        assertIs<LocalNetworkResult.Started>(h.ui.hotspotResult.value)
    }

    @Test
    fun cancellationBeforeFirstDispatchDoesNotCallTheManagerOrLeaveBusySet() = withHarness { h ->
        assertTrue(h.ui.startHotspot())
        h.job.cancel()
        h.drain()

        assertEquals(0, h.manager.startCalls)
        assertFalse(h.ui.busy.value)
        assertFalse(h.ui.joinBusy.value)
        assertNull(h.ui.hotspotResult.value)
        assertEquals(0, h.manager.events.subscriptionCount.value)
    }

    @Test
    fun parentCancellationRetiresBothCardsWithoutTakingNativeCleanupOwnership() = withHarness { h ->
        h.startAndJoin()
        h.job.cancel()
        h.drain()

        assertNull(h.ui.hotspotResult.value)
        assertNull(h.ui.joinResult.value)
        assertFalse(h.ui.busy.value)
        assertFalse(h.ui.startHotspot())
        assertFalse(h.ui.joinHotspot(credentials))
        assertEquals(0, h.manager.closeCalls)
        assertEquals(0, h.manager.stopCalls)
    }

    @Test
    fun repeatedControlsCannotStartCompetingAcquisitions() = withHarness { h ->
        val release = h.barrier()
        h.manager.afterStart = { release.await() }
        assertTrue(h.ui.startHotspot())
        h.drain()

        assertFalse(h.ui.startHotspot())
        assertFalse(h.ui.stopHotspot())
        assertFalse(h.ui.joinHotspot(credentials))
        assertTrue(h.ui.busy.value)
        assertEquals(1, h.manager.startCalls)
        assertEquals(0, h.manager.joinCalls)
        assertEquals(0, h.manager.stopCalls)

        release.complete(Unit)
        h.drain()
        assertFalse(h.ui.busy.value)
        assertTrue(h.ui.stopHotspot())
        h.drain()
        assertTrue(h.ui.stopHotspot())
        h.drain()
        assertNull(h.ui.hotspotResult.value)
        assertEquals(2, h.manager.stopCalls)
    }

    @Test
    fun failedStopIsReportedTruthfullyAndCanBeRetriedWithoutReleasingTheJoin() = withHarness { h ->
        h.startAndJoin()
        val failure = NetworkProvisioningError.CleanupFailed("synthetic close failure")
        h.manager.stopFailure = failure
        var reported: Result<Unit>? = null

        assertTrue(h.ui.stopHotspot { reported = it })
        h.drain()

        assertSame(failure, reported?.exceptionOrNull())
        assertSame(failure, assertIs<LocalNetworkResult.Failed>(h.ui.hotspotResult.value).error)
        assertIs<JoinNetworkResult.Joined>(h.ui.joinResult.value)
        assertFalse(h.ui.busy.value)

        h.manager.stopFailure = null
        assertTrue(h.ui.stopHotspot())
        h.drain()
        assertNull(h.ui.hotspotResult.value)
        assertTrue(h.manager.joinActive)
    }

    @Test
    fun untaggedCleanupFailureAndUnknownSnapshotDoNotRevokeEitherLiveResource() = withHarness { h ->
        h.startAndJoin()
        val hotspot = h.ui.hotspotResult.value
        val joined = h.ui.joinResult.value
        val error = NetworkProvisioningError.CleanupFailed("synthetic retired resource")
        h.manager.state.value = NetworkProvisioningState.Failed(error)
        h.manager.networkState.value = NetworkState.Unknown
        h.manager.events.tryEmit(NetworkProvisioningEvent.Failed(error))
        h.drain()

        assertSame(hotspot, h.ui.hotspotResult.value)
        assertSame(joined, h.ui.joinResult.value)
    }

    @Test
    fun anAlreadyQueuedTerminalCannotKillTheNextSuccessfulHotspot() = withHarness { h ->
        h.startAndJoin()
        h.manager.stopFromSystem()
        // Do not drain the main queue before retrying. Its old collector resumes later.
        assertTrue(h.ui.startHotspot())
        h.drain()

        assertIs<LocalNetworkResult.Started>(h.ui.hotspotResult.value)
        assertIs<JoinNetworkResult.Joined>(h.ui.joinResult.value)
        assertFalse(h.ui.busy.value)
    }

    @Test
    fun anAlreadyQueuedTerminalCannotKillTheNextSuccessfulJoin() = withHarness { h ->
        h.startAndJoin()
        h.manager.releaseFromSystem()
        assertTrue(h.ui.joinHotspot(credentials))
        h.drain()

        assertIs<JoinNetworkResult.Joined>(h.ui.joinResult.value)
        assertIs<LocalNetworkResult.Started>(h.ui.hotspotResult.value)
        assertEquals(2L, h.ui.joinSuccessCount.value)
    }

    @Test
    fun busyMainThreadDoesNotLoseHotspotTerminationBehindUnrelatedEventBursts() = withHarness { h ->
        h.startAndJoin()
        h.onManagerThread {
            h.manager.stopFromSystem()
            h.manager.emitUnrelatedBurst()
        }
        assertSame(NetworkProvisioningState.JoinedNetwork, h.manager.state.value)
        h.drain()

        assertIs<NetworkProvisioningError.HotspotStopped>(
            assertIs<LocalNetworkResult.Failed>(h.ui.hotspotResult.value).error
        )
        assertIs<JoinNetworkResult.Joined>(h.ui.joinResult.value)
    }

    @Test
    fun busyMainThreadDoesNotLoseJoinReleaseBehindUnrelatedEventBursts() = withHarness { h ->
        assertTrue(h.ui.joinHotspot(credentials))
        h.drain()
        assertTrue(h.ui.startHotspot())
        h.drain()
        h.onManagerThread {
            h.manager.releaseFromSystem()
            h.manager.emitUnrelatedBurst()
        }
        assertSame(NetworkProvisioningState.LocalNetworkRunning, h.manager.state.value)
        h.drain()

        assertIs<NetworkProvisioningError.JoinFailed>(
            assertIs<JoinNetworkResult.Failed>(h.ui.joinResult.value).error
        )
        assertIs<LocalNetworkResult.Started>(h.ui.hotspotResult.value)
    }

    @Test
    fun bothTerminalSignalsSurviveIndependentSnapshotOwnersAndUiConflation() = withHarness { h ->
        h.startAndJoin()
        h.manager.stopFromSystem()
        h.manager.releaseFromSystem()
        h.drain()

        assertIs<NetworkProvisioningError.HotspotStopped>(
            assertIs<LocalNetworkResult.Failed>(h.ui.hotspotResult.value).error
        )
        assertIs<NetworkProvisioningError.JoinFailed>(
            assertIs<JoinNetworkResult.Failed>(h.ui.joinResult.value).error
        )
    }

    @Test
    fun pendingJoinDisablesOnlyConflictingCallsAndDismissalDoesNotCancelIt() = withHarness { h ->
        h.manager.joinOverride = JoinNetworkResult.Pending
        assertTrue(h.ui.joinHotspot(credentials))
        h.drain()
        assertSame(JoinNetworkResult.Pending, h.ui.joinResult.value)
        assertFalse(h.ui.busy.value)
        assertTrue(h.ui.joinBusy.value)

        h.ui.dismissJoin()
        assertNull(h.ui.joinResult.value)
        assertFalse(h.ui.joinHotspot(credentials))
        assertTrue(h.ui.startHotspot())
        h.drain()
        assertIs<LocalNetworkResult.Started>(h.ui.hotspotResult.value)
        assertTrue(h.ui.stopHotspot())
        h.drain()
        assertTrue(h.ui.joinBusy.value)
        assertEquals(0, h.manager.closeCalls)

        h.manager.publishJoin()
        h.drain()
        assertIs<JoinNetworkResult.Joined>(h.ui.joinResult.value)
        assertEquals(1L, h.ui.joinSuccessCount.value)
        assertFalse(h.ui.joinBusy.value)
    }

    @Test
    fun pendingJoinFailureReleasesTheJoinControlForRetry() = withHarness { h ->
        h.manager.joinOverride = JoinNetworkResult.Pending
        assertTrue(h.ui.joinHotspot(credentials))
        h.drain()
        h.manager.releaseFromSystem()
        h.drain()

        assertIs<JoinNetworkResult.Failed>(h.ui.joinResult.value)
        assertFalse(h.ui.joinBusy.value)
        h.manager.joinOverride = null
        assertTrue(h.ui.joinHotspot(credentials))
        h.drain()
        assertIs<JoinNetworkResult.Joined>(h.ui.joinResult.value)
    }

    @Test
    fun pendingJoinCanFailWithAPlatformErrorButNotAnUnattributedCleanupWarning() = withHarness { h ->
        h.manager.joinOverride = JoinNetworkResult.Pending
        assertTrue(h.ui.joinHotspot(credentials))
        h.drain()
        h.manager.events.tryEmit(NetworkProvisioningEvent.Failed(
            NetworkProvisioningError.CleanupFailed("synthetic retired hotspot cleanup")
        ))
        h.drain()
        assertTrue(h.ui.joinBusy.value)
        assertSame(JoinNetworkResult.Pending, h.ui.joinResult.value)

        val failure = NetworkProvisioningError.PlatformError(IllegalStateException("synthetic pending join error"))
        h.manager.events.tryEmit(NetworkProvisioningEvent.Failed(failure))
        h.manager.emitUnrelatedBurst()
        h.drain()
        assertSame(failure, assertIs<JoinNetworkResult.Failed>(h.ui.joinResult.value).error)
        assertFalse(h.ui.joinBusy.value)
    }

    @Test
    fun joinedEventBeforePendingReturnIsNotOverwrittenByPending() = withHarness { h ->
        h.manager.joinOverride = JoinNetworkResult.Pending
        h.manager.afterJoin = { h.manager.publishJoin() }
        assertTrue(h.ui.joinHotspot(credentials))
        h.drain()

        assertIs<JoinNetworkResult.Joined>(h.ui.joinResult.value)
        assertFalse(h.ui.joinBusy.value)
        assertEquals(1L, h.ui.joinSuccessCount.value)
    }

    @Test
    fun failureEventBeforePendingReturnIsNotOverwrittenByPending() = withHarness { h ->
        h.manager.joinOverride = JoinNetworkResult.Pending
        h.manager.afterJoin = { h.manager.releaseFromSystem() }
        assertTrue(h.ui.joinHotspot(credentials))
        h.drain()

        assertIs<JoinNetworkResult.Failed>(h.ui.joinResult.value)
        assertFalse(h.ui.joinBusy.value)
    }

    @Test
    fun coalescedJoinAndReleaseStillSignalCredentialClearingWithoutALiveCard() = withHarness { h ->
        h.manager.afterJoin = { h.manager.releaseFromSystem() }
        assertTrue(h.ui.joinHotspot(credentials))
        h.drain()

        assertIs<JoinNetworkResult.Failed>(h.ui.joinResult.value)
        assertEquals(1L, h.ui.joinSuccessCount.value)
    }

    @Test
    fun dismissedJoinDoesNotReappearOnUnrelatedSignalsOrRefusedRepeatCalls() = withHarness { h ->
        h.startAndJoin()
        h.ui.dismissJoin()
        h.manager.emitUnrelatedBurst()
        h.drain()
        assertNull(h.ui.joinResult.value)

        var reported: JoinNetworkResult? = null
        assertTrue(h.ui.joinHotspot(credentials) { reported = it })
        h.drain()
        assertIs<JoinNetworkResult.Failed>(reported)
        assertNull(h.ui.joinResult.value)
        assertTrue(h.manager.joinActive)

        // A genuine loss is a new outcome worth surfacing, not resurrection of success.
        h.manager.releaseFromSystem()
        h.drain()
        assertIs<JoinNetworkResult.Failed>(h.ui.joinResult.value)
    }

    @Test
    fun replacedRunIgnoresOldEventsResultsAndNonCancellableFinalizers() = withHarness { h ->
        val oldRelease = h.barrier()
        val newRelease = h.barrier()
        var oldReported = false
        h.manager.afterStart = { withContext(NonCancellable) { oldRelease.await() } }
        assertTrue(h.ui.startHotspot { oldReported = true })
        h.drain()
        val replacement = FakeManager().apply { afterJoin = { newRelease.await() } }
        h.ui.attach(replacement, h.scope)
        assertTrue(h.ui.joinHotspot(credentials))
        h.drain()

        oldRelease.complete(Unit)
        h.manager.stopFromSystem()
        h.manager.publishJoin()
        h.drain()

        assertFalse(oldReported)
        assertNull(h.ui.hotspotResult.value)
        assertIs<JoinNetworkResult.Joined>(h.ui.joinResult.value)
        assertTrue(h.ui.busy.value)
        assertTrue(h.ui.joinBusy.value)
        assertEquals(1L, h.ui.joinSuccessCount.value)
        assertEquals(0, h.manager.events.subscriptionCount.value)

        newRelease.complete(Unit)
        h.drain()
        assertFalse(h.ui.busy.value)
        assertFalse(h.ui.joinBusy.value)
        assertEquals(0, replacement.closeCalls)
    }

    @Test
    fun managerCloseRetiresBothCardsAndPermanentlyRefusesMoreCalls() = withHarness { h ->
        h.startAndJoin()
        h.manager.closeFromSystem()
        h.drain()

        assertIs<NetworkProvisioningError.ManagerClosed>(
            assertIs<LocalNetworkResult.Failed>(h.ui.hotspotResult.value).error
        )
        assertIs<NetworkProvisioningError.ManagerClosed>(
            assertIs<JoinNetworkResult.Failed>(h.ui.joinResult.value).error
        )
        assertFalse(h.ui.startHotspot())
        assertFalse(h.ui.joinHotspot(credentials))
        assertFalse(h.ui.stopHotspot())
        assertFalse(h.ui.busy.value)
        assertFalse(h.ui.joinBusy.value)
        assertEquals(0, h.manager.events.subscriptionCount.value)
    }

    @Test
    fun attachingAClosedManagerDoesNotStartWorkOrRetainCollectors() = withHarness { h ->
        val closed = FakeManager().apply { closeFromSystem() }
        h.ui.attach(closed, h.scope)
        h.drain()
        assertFalse(h.ui.startHotspot())
        assertFalse(h.ui.joinHotspot(credentials))
        assertFalse(h.ui.busy.value)
        assertEquals(0, closed.events.subscriptionCount.value)
    }

    @Test
    fun realUnsupportedManagerStillReturnsItsGuidanceAndObservesTerminalClose() = withHarness { h ->
        val unsupported = UnsupportedNetworkProvisioningManager()
        h.ui.attach(unsupported, h.scope)
        assertTrue(h.ui.startHotspot())
        h.drain()
        assertIs<LocalNetworkResult.Unsupported>(h.ui.hotspotResult.value)
        assertTrue(h.ui.joinHotspot(credentials))
        h.drain()
        assertIs<JoinNetworkResult.Unsupported>(h.ui.joinResult.value)

        h.scope.launch { unsupported.close() }
        h.drain()
        assertFalse(h.ui.startHotspot())
        assertFalse(h.ui.joinHotspot(credentials))
        assertFalse(h.ui.busy.value)
    }

    @Test
    fun managerCloseBeforeResultAndParentCancellationClearPendingWork() = withHarness { h ->
        val release = h.barrier()
        h.manager.afterStart = { release.await() }
        var reported = false
        assertTrue(h.ui.startHotspot { reported = true })
        h.drain()
        h.manager.closeFromSystem()
        release.complete(Unit)
        h.drain()

        assertFalse(reported)
        assertFalse(h.ui.busy.value)
        assertIs<NetworkProvisioningError.ManagerClosed>(
            assertIs<LocalNetworkResult.Failed>(h.ui.hotspotResult.value).error
        )
    }

    @Test
    fun noCredentialsHotspotStillTracksItsOwnLifetime() = withHarness { h ->
        h.manager.withoutHotspotCredentials = true
        assertTrue(h.ui.startHotspot())
        h.drain()
        assertIs<LocalNetworkResult.StartedWithoutCredentials>(h.ui.hotspotResult.value)
        h.manager.stopFromSystem()
        h.drain()
        assertIs<LocalNetworkResult.Failed>(h.ui.hotspotResult.value)
    }

    @Test
    fun unsupportedAndUserActionResultsReleaseBusyAndRemainVisible() = withHarness { h ->
        for (result in listOf(
            LocalNetworkResult.Unsupported("synthetic unsupported API"),
            LocalNetworkResult.RequiresUserAction("synthetic settings action"),
            LocalNetworkResult.Failed(NetworkProvisioningError.HotspotStopped("synthetic start failure"))
        )) {
            h.manager.startOverride = result
            assertTrue(h.ui.startHotspot())
            h.drain()
            assertSame(result, h.ui.hotspotResult.value)
            assertFalse(h.ui.busy.value)
        }
        for (result in listOf(
            JoinNetworkResult.Unsupported("synthetic unsupported API"),
            JoinNetworkResult.RequiresUserAction("synthetic settings action"),
            JoinNetworkResult.Failed(NetworkProvisioningError.JoinFailed("synthetic join failure"))
        )) {
            h.manager.joinOverride = result
            assertTrue(h.ui.joinHotspot(credentials))
            h.drain()
            assertSame(result, h.ui.joinResult.value)
            assertFalse(h.ui.joinBusy.value)
        }
    }

    @Test
    fun acquisitionExceptionsAreTypedAndDoNotPreventRecovery() = withHarness { h ->
        h.manager.startFailure = IllegalStateException("synthetic start error")
        assertTrue(h.ui.startHotspot())
        h.drain()
        assertIs<NetworkProvisioningError.PlatformError>(
            assertIs<LocalNetworkResult.Failed>(h.ui.hotspotResult.value).error
        )
        assertFalse(h.ui.busy.value)
        h.manager.startFailure = null
        assertTrue(h.ui.startHotspot())
        h.drain()
        assertIs<LocalNetworkResult.Started>(h.ui.hotspotResult.value)
    }

    @Test
    fun aClosedOperationResultRetiresTheManagerEvenBeforeItsStateFlowCatchesUp() = withHarness { h ->
        h.startAndJoin()
        h.manager.startOverride = LocalNetworkResult.Failed(NetworkProvisioningError.ManagerClosed())
        assertTrue(h.ui.startHotspot())
        h.drain()

        assertIs<NetworkProvisioningError.ManagerClosed>(
            assertIs<JoinNetworkResult.Failed>(h.ui.joinResult.value).error
        )
        assertFalse(h.ui.joinHotspot(credentials))
        assertFalse(h.ui.busy.value)
    }

    @Test
    fun brokenEventObservationFailsClosedWithoutExposingExceptionDetails() = withHarness { h ->
        val throwing = object : NetworkProvisioningManager by h.manager {
            override val events = flow {
                h.manager.events.collect {
                    emit(it)
                    error("synthetic-private-detail-must-not-escape")
                }
            }
        }
        h.ui.attach(throwing, h.scope)
        assertTrue(h.ui.startHotspot())
        h.drain()

        val failure = assertIs<LocalNetworkResult.Failed>(h.ui.hotspotResult.value)
        assertIs<NetworkProvisioningError.PlatformError>(failure.error)
        assertFalse(failure.error.message.orEmpty().contains("synthetic-private-detail"))
        assertFalse(h.ui.startHotspot())
        assertFalse(h.ui.busy.value)
        assertEquals(0, h.manager.events.subscriptionCount.value)
    }

    @Test
    fun viewModelWiresRunOwnedStateAndUiClearsCredentialsIndependentOfVisibleResult() {
        val vm = sampleSource("P2pKitViewModel.kt")
        val ui = sampleSource("MainActivity.kt")
        assertTrue(vm.contains("val hotspotResult: StateFlow<LocalNetworkResult?> = provisioningUi.hotspotResult"))
        assertTrue(vm.contains("val joinResult: StateFlow<JoinNetworkResult?> = provisioningUi.joinResult"))
        assertTrue(vm.contains("val joinProvisioningBusy: StateFlow<Boolean> = provisioningUi.joinBusy"))
        assertTrue(vm.contains("val joinSuccessCount: StateFlow<Long> = provisioningUi.joinSuccessCount"))
        val attachment = vm.indexOf("provisioningUi.attach(newKit.networkProvisioning, scope)")
        assertTrue(attachment > vm.indexOf("runScope = scope"))
        assertTrue(attachment < vm.indexOf("newKit.startAdvertising()"))
        assertTrue(vm.contains("catch (t: Throwable) {\n                provisioningUi.detach()"))
        val stop = vm.substringAfter("fun stop() {").substringBefore("override fun onCleared()")
        assertTrue(stop.contains("provisioningUi.detach()"))
        assertTrue(stop.indexOf("provisioningUi.detach()") < stop.indexOf("runScope?.cancel()"))
        assertTrue(vm.contains("override fun onCleared() {\n        provisioningUi.detach()"))
        assertFalse(vm.contains("_hotspotResult.value ="))
        assertFalse(vm.contains("_joinResult.value ="))
        assertTrue(ui.contains("val busy by vm.joinProvisioningBusy.collectAsState()"))
        assertTrue(ui.contains("LaunchedEffect(joinSuccessCount)"))
        assertTrue(ui.contains("if (joinSuccessCount > 0) credentialInput.onJoinSucceeded()"))
    }

    private fun sampleSource(name: String): String {
        val relative = "src/main/java/dev/p2pkit/sample/android/$name"
        return generateSequence(File(requireNotNull(System.getProperty("user.dir"))).absoluteFile) { it.parentFile }
            .flatMap { sequenceOf(File(it, relative), File(it, "samples/p2p-sample-android/$relative")) }
            .first(File::isFile).readText()
    }

    private fun withHarness(block: (Harness) -> Unit) {
        val harness = Harness()
        try {
            block(harness)
        } finally {
            harness.ui.detach()
            harness.job.cancel()
            harness.barriers.forEach { it.complete(Unit) }
            harness.drain()
            assertTrue(harness.job.isCompleted, "test must not retain presentation coroutines")
            assertEquals(0, harness.manager.events.subscriptionCount.value)
        }
    }

    private class Harness {
        val dispatcher = MainQueue()
        val job = Job()
        val scope = CoroutineScope(dispatcher + job)
        val manager = FakeManager()
        val ui = ProvisioningUiState(dispatcher).apply { attach(manager, scope) }
        val barriers = mutableListOf<CompletableDeferred<Unit>>()
        fun barrier() = CompletableDeferred<Unit>().also { barriers += it }
        fun drain() = dispatcher.drain()
        fun onManagerThread(action: () -> Unit) {
            val failure = AtomicReference<Throwable>()
            val producer = thread(name = "synthetic-provisioning-producer") {
                try {
                    action()
                } catch (error: Throwable) {
                    failure.set(error)
                }
            }
            try {
                producer.join(2_000)
                assertFalse(producer.isAlive, "event recording must not wait for the main queue")
                assertNull(failure.get())
            } finally {
                if (producer.isAlive) {
                    producer.interrupt()
                    producer.join(2_000)
                }
                check(!producer.isAlive) { "test must not retain a producer thread" }
            }
        }
        fun startAndJoin() {
            assertTrue(ui.startHotspot())
            drain()
            assertTrue(ui.joinHotspot(credentials))
            drain()
            assertIs<LocalNetworkResult.Started>(ui.hotspotResult.value)
            assertIs<JoinNetworkResult.Joined>(ui.joinResult.value)
        }
    }

    private class MainQueue : CoroutineDispatcher() {
        private val queue = ArrayDeque<Runnable>()
        override fun dispatch(context: CoroutineContext, block: Runnable) {
            synchronized(queue) { queue.addLast(block) }
        }

        fun drain() {
            var steps = 0
            while (true) {
                val next = synchronized(queue) { queue.removeFirstOrNull() } ?: break
                check(++steps < 10_000) { "presentation scheduler did not become idle" }
                next.run()
            }
        }
    }

    @OptIn(ExperimentalP2pApi::class)
    private class FakeManager : NetworkProvisioningManager {
        override val state = MutableStateFlow<NetworkProvisioningState>(NetworkProvisioningState.Idle)
        override val networkState = MutableStateFlow<NetworkState>(NetworkState.Unknown)
        override val events = MutableSharedFlow<NetworkProvisioningEvent>(
            replay = 0,
            extraBufferCapacity = 16,
            onBufferOverflow = BufferOverflow.DROP_OLDEST
        )
        var startCalls = 0
        var joinCalls = 0
        var stopCalls = 0
        var closeCalls = 0
        var joinActive = false
        private var hotspotActive = false
        private var stateOwner: Owner? = null
        private var networkOwner: Owner? = null
        var afterStart: suspend () -> Unit = {}
        var afterJoin: suspend () -> Unit = {}
        var startOverride: LocalNetworkResult? = null
        var joinOverride: JoinNetworkResult? = null
        var startFailure: Throwable? = null
        var stopFailure: Throwable? = null
        var withoutHotspotCredentials = false

        private enum class Owner { HOTSPOT, JOIN }

        override suspend fun startLocalNetwork(config: LocalNetworkConfig): LocalNetworkResult {
            startCalls++
            startFailure?.let { throw it }
            startOverride?.let { return it }
            if (hotspotActive) return startedResult()
            hotspotActive = true
            stateOwner = Owner.HOTSPOT
            networkOwner = Owner.HOTSPOT
            networkState.value = NetworkState.LocalNetworkHosted(credentials, listOf("192.0.2.1"))
            state.value = NetworkProvisioningState.LocalNetworkRunning
            events.tryEmit(NetworkProvisioningEvent.LocalNetworkStarted(credentials))
            afterStart()
            return startedResult()
        }

        private fun startedResult(): LocalNetworkResult = if (withoutHotspotCredentials) {
            LocalNetworkResult.StartedWithoutCredentials(
                ManualConnectionInfo(listOf("192.0.2.1"), 12345, AppId("synthetic.app"), PeerId("synthetic-id"), "test")
            )
        } else LocalNetworkResult.Started(credentials, null)

        override suspend fun joinLocalNetwork(credentials: WifiCredentials): JoinNetworkResult {
            joinCalls++
            joinOverride?.let { afterJoin(); return it }
            if (joinActive) {
                return JoinNetworkResult.Failed(
                    NetworkProvisioningError.JoinFailed("a joined network is already active")
                )
            }
            val joined = publishJoin()
            afterJoin()
            return JoinNetworkResult.Joined(joined)
        }

        fun publishJoin(): NetworkState {
            joinActive = true
            stateOwner = Owner.JOIN
            networkOwner = Owner.JOIN
            val joined = NetworkState.ConnectedToWifi(credentials.ssid, listOf("192.0.2.2"))
            networkState.value = joined
            state.value = NetworkProvisioningState.JoinedNetwork
            events.tryEmit(NetworkProvisioningEvent.NetworkJoined(joined))
            return joined
        }

        fun emitUnrelatedBurst() {
            repeat(40) {
                events.tryEmit(NetworkProvisioningEvent.UserActionRequired("synthetic unrelated notice"))
            }
            events.tryEmit(NetworkProvisioningEvent.Failed(
                NetworkProvisioningError.CleanupFailed("synthetic retired resource cleanup")
            ))
        }

        fun closeFromSystem() {
            state.value = NetworkProvisioningState.Closing
            hotspotActive = false
            joinActive = false
            networkState.value = NetworkState.Unknown
            state.value = NetworkProvisioningState.Closed
        }

        fun stopFromSystem() {
            val error = NetworkProvisioningError.HotspotStopped("synthetic OS stop")
            hotspotActive = false
            if (stateOwner == Owner.HOTSPOT) state.value = NetworkProvisioningState.Failed(error)
            if (networkOwner == Owner.HOTSPOT) networkState.value = NetworkState.Unknown
            events.tryEmit(NetworkProvisioningEvent.Failed(error))
        }

        fun releaseFromSystem() {
            val error = NetworkProvisioningError.JoinFailed("synthetic OS release")
            joinActive = false
            if (stateOwner == Owner.JOIN) state.value = NetworkProvisioningState.Failed(error)
            if (networkOwner == Owner.JOIN) networkState.value = NetworkState.Unknown
            events.tryEmit(NetworkProvisioningEvent.Failed(error))
        }

        override suspend fun stopLocalNetwork() {
            stopCalls++
            stopFailure?.let { throw it }
            hotspotActive = false
            if (stateOwner == Owner.HOTSPOT) state.value = NetworkProvisioningState.Idle
            if (networkOwner == Owner.HOTSPOT) networkState.value = NetworkState.Unknown
            events.tryEmit(NetworkProvisioningEvent.LocalNetworkStopped)
        }
        override suspend fun getManualConnectionInfo(): ManualConnectionInfo? = error("unused")
        @Deprecated("Test stub for the deprecated API")
        override suspend fun createManualPeer(host: String, port: Int): Peer = error("unused")
        override suspend fun createManualPeer(host: String, port: Int, expectedFingerprint: PeerFingerprint): Peer =
            error("unused")
        override suspend fun close() {
            closeCalls++
            error("presentation must not own native cleanup")
        }
    }

    private companion object {
        val credentials = WifiCredentials("synthetic-hotspot", WifiPassword("test-only-pass"), WifiSecurityType.WPA2)
    }
}
