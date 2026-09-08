package dev.p2pkit.core.internal

import kotlin.test.Test

/** Android-compiled dispatcher on the host JVM; no framework stubs, ART or device storage. */
class FileDestinationAcceptanceAndroidHostTest {
    @Test
    fun destinationOpenAuthenticationFailureRetiresOffer() =
        FileTransferFlowTest().destinationOpenAuthenticationFailureIsTypedStorageFailure()

    @Test
    fun destinationPreflightAuthenticationFailureRetiresOffer() =
        FileTransferFlowTest().destinationPreflightAuthenticationFailureIsTypedStorageFailure()

    @Test
    fun destinationIoFailurePermitsRecovery() =
        FileTransferFlowTest().destinationOpenIoFailureRetiresOfferAndPermitsRecovery()

    @Test
    fun destinationCallbackCancellationPermitsRecovery() =
        FileTransferFlowTest().destinationOpenCallbackCancellationRetiresOfferAndPermitsRecovery()

    @Test
    fun typedDestinationFailureRetainsClassification() =
        FileTransferFlowTest().destinationOpenTypedFailurePreservesOriginalClassification()

    @Test
    fun secureWriterAuthenticationFailureIsNotAStorageFailure() =
        FileTransferFlowTest().secureAcceptWriterAuthenticationFailureIsNotReclassifiedAsStorage()

    @Test
    fun abortAndNotificationFailuresDoNotReplaceDestinationFailure() =
        FileTransferFlowTest().destinationAuthenticationFailureSurvivesAbortAndNotificationFailures()

    @Test
    fun callerCancellationWinsOverDestinationFailure() =
        FileTransferFlowTest().callerCancellationWinsOverDestinationAuthenticationFailure()
}
