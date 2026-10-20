package dev.p2pkit.sample.android.runtime

import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class LanPermissionUiSettlementTest {
    private val visible = LanPermissionUiSettlement(
        originalRequestObserved = true, ownedWindow = true, visibleAnchor = true, stateStable = true,
        liveGrant = true, requestInFlight = false, missingEmpty = true, checkFailed = false,
        card = LanPermissionUiSettlement.Card.AVAILABLE, waitingVisible = false, grantVisible = false,
        missingVisible = false, availableVisible = true, cardExplanationVisible = true,
        refreshVisible = true, refreshButtonReady = true
    )
    private val absent = visible.copy(
        card = LanPermissionUiSettlement.Card.ABSENT,
        availableVisible = false, cardExplanationVisible = false, refreshVisible = false, refreshButtonReady = false
    )

    @Test
    fun completedCallbackAllowsVisibleEnabledCardOrItsIntentionalRemoval() {
        assertTrue(visible.settled())
        assertTrue(absent.settled())
    }

    @Test
    fun neitherPresentationAdmitsAnOutstandingOrUnprovenRequest() {
        for (value in listOf(visible, absent)) {
            assertFalse(value.copy(originalRequestObserved = false).settled())
            assertFalse(value.copy(requestInFlight = true).settled())
            assertFalse(value.copy(liveGrant = false).settled())
            assertFalse(value.copy(missingEmpty = false).settled())
            assertFalse(value.copy(checkFailed = true).settled())
            assertFalse(value.copy(stateStable = false).settled())
        }
    }

    @Test
    fun stateAloneNeverAdmitsNullForeignBlankOrInactiveWindows() {
        for (value in listOf(visible, absent)) {
            assertFalse(value.copy(ownedWindow = false).settled())
            assertFalse(value.copy(visibleAnchor = false).settled())
            assertFalse(value.copy(waitingVisible = true).settled())
            assertFalse(value.copy(grantVisible = true).settled())
            assertFalse(value.copy(missingVisible = true).settled())
            assertFalse(value.copy(card = LanPermissionUiSettlement.Card.OTHER).settled())
        }
    }

    @Test
    fun visibleCardStillRequiresItsActualEnabledButton() {
        assertFalse(visible.copy(availableVisible = false).settled())
        assertFalse(visible.copy(refreshVisible = false).settled())
        assertFalse(visible.copy(refreshButtonReady = false).settled())
    }

    @Test
    fun intendedAbsenceDoesNotAdmitStaleVisibleStatusOrButton() {
        assertFalse(absent.copy(availableVisible = true).settled())
        assertFalse(absent.copy(refreshVisible = true).settled())
        assertFalse(absent.copy(refreshButtonReady = true).settled())
        assertFalse(absent.copy(cardExplanationVisible = true).settled())
    }
}
