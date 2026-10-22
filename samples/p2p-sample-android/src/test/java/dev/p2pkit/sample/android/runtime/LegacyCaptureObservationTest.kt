package dev.p2pkit.sample.android.runtime

import kotlin.test.Test
import kotlin.test.assertFailsWith

/** Pure policy controls only. No Android compositor, task-card or screenshot-privacy claim. */
class LegacyCaptureObservationTest {
    private fun state(secure: Boolean) = LegacyCaptureState(1, 2, 3, 7, 16, 16,
        listOf(2 to 4, 6 to 4, 10 to 4, 14 to 4), true, true, true, secure, 1)

    private fun observation(secure: Boolean, unavailable: Boolean = false): LegacyCaptureObservation {
        val state = state(secure)
        return LegacyCaptureObservation(state, state, if (unavailable) null else 16 to 16,
            if (unavailable) null else List(4) { !secure })
    }

    @Test
    fun completeBracketAllowsOnlyProvisionalUnavailableOrActualRedactedPixels() {
        for (unavailable in listOf(false, true)) {
            checkLegacyCaptureBracket(observation(false), observation(true, unavailable), observation(false))
        }
    }

    @Test
    fun unavailablePositiveAndInventedProtectedPixelsCannotPass() {
        assertFailsWith<LegacyCaptureFailure> {
            checkLegacyCaptureBracket(observation(false, true), observation(true, true), observation(false))
        }
        assertFailsWith<LegacyCaptureFailure> {
            checkLegacyCaptureBracket(observation(false), observation(true, true), observation(false, true))
        }
        assertFailsWith<LegacyCaptureFailure> {
            checkLegacyCaptureObservation(observation(true, true).copy(matches = List(4) { false }), false)
        }
    }

    @Test
    fun bothSidesRequireStableOwnedFocusedProtectedWindowAndGeometry() {
        val original = observation(true, true)
        val changes = listOf<(LegacyCaptureState) -> LegacyCaptureState>(
            { it.copy(owned = false) }, { it.copy(attached = false) }, { it.copy(focused = false) },
            { it.copy(secure = false) }, { it.copy(draws = 0) }, { it.copy(activity = 8) },
            { it.copy(window = 8) }, { it.copy(view = 8) }, { it.copy(taskId = 8) },
            { it.copy(width = 17) }, { it.copy(height = 17) }, { it.copy(points = it.points.reversed()) },
        )
        for (change in changes) {
            assertFailsWith<LegacyCaptureFailure> {
                checkLegacyCaptureObservation(original.copy(before = change(original.before)), false)
            }
            assertFailsWith<LegacyCaptureFailure> {
                checkLegacyCaptureObservation(original.copy(after = change(original.after)), false)
            }
        }
    }

    @Test
    fun bracketRejectsNewWindowViewTaskGeometryAndChangedCaptureDimensions() {
        val positive = observation(false)
        val changes = listOf<(LegacyCaptureState) -> LegacyCaptureState>(
            { it.copy(activity = 9) }, { it.copy(window = 9) }, { it.copy(view = 9) },
            { it.copy(taskId = 9) }, { it.copy(width = 17) }, { it.copy(points = it.points.reversed()) },
        )
        for (change in changes) {
            assertFailsWith<LegacyCaptureFailure> {
                checkLegacyCaptureBracket(positive, observation(true, true),
                    positive.copy(before = change(positive.before), after = change(positive.after)))
            }
        }
        assertFailsWith<LegacyCaptureFailure> {
            checkLegacyCaptureBracket(positive, observation(true, true), positive.copy(bitmapSize = 17 to 16))
        }
    }

    @Test
    fun leakedPatternMissingPositivePixelsAndInvalidCoordinatesFail() {
        for (secure in listOf(false, true)) {
            assertFailsWith<LegacyCaptureFailure> {
                checkLegacyCaptureObservation(observation(secure).copy(matches = List(4) { secure }), !secure)
            }
        }
        assertFailsWith<LegacyCaptureFailure> {
            checkLegacyCaptureObservation(observation(false).copy(bitmapSize = 8 to 8), true)
        }
        assertFailsWith<LegacyCaptureFailure> {
            checkLegacyCaptureObservation(observation(false).copy(matches = listOf(true)), true)
        }
    }
}
