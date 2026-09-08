package dev.p2pkit.core.internal

import kotlin.test.Test

/**
 * Android-compiled session/accounting and pinned secure managers with real JDK crypto.
 * No kit-only android.util.Log calls, framework mocks, ART, or physical-device claims.
 */
class ApplicationBacklogAccountingAndroidHostTest {
    @Test
    fun textCodeUnitsAndMessageAllowance() =
        ApplicationBacklogAccountingTest().textUsesUtf16CodeUnitsAndFixedAllowanceRatherThanUtf8Encoding()

    @Test
    fun metadataCodeUnitsAndPerEntryAllowance() =
        ApplicationBacklogAccountingTest().textAndBinaryIncludeMetadataCodeUnitsAndEachEntryAllowance()

    @Test
    fun immutableBinaryAndMetadataOwnership() =
        ApplicationBacklogAccountingTest().callerMutationAndBinaryCopiesCannotChangeRecordedOwnershipOrDelivery()

    @Test
    fun exactMessageCountBoundaryIncludesInFlight() =
        ApplicationBacklogAccountingTest().exactly64MessagesIncludingInFlightAreAdmittedAnd65thFails()

    @Test
    fun exactByteBoundary() =
        ApplicationBacklogAccountingTest().exactly8MiBIsAdmittedAndAnotherMessageFails()

    @Test
    fun oneByteOverflowRollback() =
        ApplicationBacklogAccountingTest().oneByteBeyond8MiBIsRejectedWithoutChargingTheRejectedMessage()

    @Test
    fun exactByteBoundaryIncludesMetadata() =
        ApplicationBacklogAccountingTest().exactly8MiBIncludingMetadataIsAdmitted()

    @Test
    fun metadataControlsOneByteOverflow() =
        ApplicationBacklogAccountingTest().metadataChargeParticipatesInTheOneByteOverflowBoundary()

    @Test
    fun successfulReleaseAndReadmission() =
        ApplicationBacklogAccountingTest().successfulEmissionReleasesOnlyItsChargeAndPermitsReadmission()

    @Test
    fun failedChannelSendPreservesExistingOwnership() =
        ApplicationBacklogAccountingTest().failedChannelSendRollsBackItsChargeWithoutErasingExistingOwnership()

    @Test
    fun nonCooperativeDeliveryReleasesAfterTerminalDrain() =
        ApplicationBacklogAccountingTest().terminalDrainLeavesNonCooperativeInFlightChargeUntilItsLateFinally()

    @Test
    fun reconnectPreservesSessionOwnedBacklog() =
        ApplicationBacklogAccountingTest().rearmPreservesChargesOwnedByTheSessionRatherThanTheOldEpoch()

    @Test
    fun asciiAtExactBudget() =
        ApplicationBacklogAccountingTest().asciiAtExactlyTheRetentionBudgetIsAdmitted()

    @Test
    fun asciiOneCodeUnitOverBudget() =
        ApplicationBacklogAccountingTest().asciiOneCodeUnitAboveTheRetentionBudgetIsRejected()

    @Test
    fun maximumWireAsciiExceedsRetentionBudget() =
        ApplicationBacklogAccountingTest().maximumWireSizedAsciiIsRejectedEvenWhenTheBacklogWasEmpty()

    @Test
    fun pinnedSecureWireReachabilityAndRecovery() =
        SecureApplicationBacklogTest().pinnedSecureManagerReceiveChargesDecodedMetadataAndRecoversAfterSlowCollector()
}
