package dev.p2pkit.core.internal

import kotlin.test.Test

/** Android-compiled dispatcher on the host JVM; no framework stubs, ART or device storage. */
class FileDestinationCleanupCancellationAndroidHostTest {
    @Test
    fun ioFailureCleanupSurvivesCallerCancellation() =
        FileTransferFlowTest().callerCancellationDuringIoFailureAbortStillTerminalizesTransfer()

    @Test
    fun authenticationFailureCleanupSurvivesCallerCancellation() =
        FileTransferFlowTest().callerCancellationDuringAuthenticationFailureAbortStillTerminalizesTransfer()

    @Test
    fun abortCallbackCancellationDoesNotCancelCleanup() =
        FileTransferFlowTest().destinationAbortCallbackCancellationDoesNotCancelAcceptanceCleanup()

    @Test
    fun cancelledFailureSurvivesAbortAndNotificationErrors() =
        FileTransferFlowTest().cancelledDestinationFailureSurvivesAbortAndNotificationErrors()

    @Test
    fun preflightFailureCleanupSurvivesCallerCancellation() =
        FileTransferFlowTest().destinationPreflightFailureCleanupSurvivesCallerCancellation()

    @Test
    fun externalCancellationDuringSuspendedAbortStillSettlesFailure() =
        FileTransferFlowTest().externalCancellationDuringSuspendedDestinationAbortStillSettlesFailure()

    @Test
    fun cancelledFailureCleanupBoundsNonCooperativeAbort() =
        FileTransferFlowTest().cancelledDestinationFailureCleanupBoundsNonCooperativeAbort()

    @Test
    fun cancelledFailureCleanupCannotWriteIntoReopenedEpoch() =
        FileTransferFlowTest().cancelledDestinationFailureCleanupCannotWriteIntoReopenedEpoch()
}
