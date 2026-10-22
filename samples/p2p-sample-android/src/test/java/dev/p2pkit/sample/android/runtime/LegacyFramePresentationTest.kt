package dev.p2pkit.sample.android.runtime

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNull
import kotlin.test.assertSame

/** Pure source-bound controls, never actual Android presentation or screenshot evidence. */
class LegacyFramePresentationTest {
    @Test
    fun actualPresentedTimeIsRequiredNotJustPostedOrReady() {
        for (time in listOf(-1L, 0L, 99L, 201L, Long.MAX_VALUE)) {
            assertNull(findLegacyPresentedFrame(listOf(LegacyPresentedFrame(0, 150, 160, time)), 100, 200))
        }
        assertNull(findLegacyPresentedFrame(emptyList(), 100, 200))
        val frame = LegacyPresentedFrame(0, 90, -1, 180)
        assertSame(frame, findLegacyPresentedFrame(listOf(frame), 100, 200))
    }

    @Test
    fun overflowAndWrongClockOrderingFailRatherThanPartialMatch() {
        val frame = LegacyPresentedFrame(0, 90, 160, 180)
        assertEquals(LegacyCaptureFailureCode.PRESENTATION_FRAME_LIMIT_EXCEEDED,
            assertFailsWith<LegacyCaptureFailure> {
                findLegacyPresentedFrame(List(1025) { frame }, 100, 200)
            }.code)
        assertFailsWith<LegacyCaptureFailure> { findLegacyPresentedFrame(listOf(frame), 200, 100) }
        assertFailsWith<LegacyCaptureFailure> { findLegacyPresentedFrame(listOf(frame), 0, 100) }
    }

    @Test
    fun clearAndRedrawAreEachOnceWhileOnlyObservationPolls() {
        var clock = 0L
        var clears = 0
        var draws = 0
        var reads = 0
        val original = Any()
        val result = awaitLegacyPresentation(5, { clock }, { clears++; true }, { draws++ },
            { if (++reads == 3) original else null }, { clock++ })
        assertSame(original, result)
        assertEquals(1, clears)
        assertEquals(1, draws)
        assertEquals(3, reads)
    }

    @Test
    fun falseClearNeverRedrawsAndOriginalPlatformExceptionPropagates() {
        var draws = 0
        assertEquals(LegacyCaptureFailureCode.PRESENTATION_STATS_UNAVAILABLE,
            assertFailsWith<LegacyCaptureFailure> {
                awaitLegacyPresentation<Any>(5, { 0 }, { false }, { draws++ }, { Any() }, {})
            }.code)
        assertEquals(0, draws)
        val original = IllegalStateException("synthetic platform exception")
        assertSame(original, assertFailsWith<IllegalStateException> {
            awaitLegacyPresentation<Any>(5, { 0 }, { throw original }, { draws++ }, { Any() }, {})
        })
        assertEquals(0, draws)
    }

    @Test
    fun lateReadyObservationCannotPassOrResetTheDeadline() {
        var clock = 0L
        var clears = 0
        assertEquals(LegacyCaptureFailureCode.PRESENTATION_ADMISSION_TIMEOUT,
            assertFailsWith<LegacyCaptureFailure> {
                awaitLegacyPresentation(5, { clock }, { clears++; true }, {}, { clock = 6; Any() }, {})
            }.code)
        assertEquals(1, clears)
        assertFailsWith<LegacyCaptureFailure> {
            awaitLegacyPresentation<Any>(5, { clock }, { clears++; true }, {}, { Any() }, {})
        }
        assertEquals(1, clears)
    }

    @Test
    fun changedOwnerOrMissingStatsExceptionsAreNotRetried() {
        var reads = 0
        val original = LegacyCaptureFailure(LegacyCaptureFailureCode.CAPTURE_STATE_INVALID)
        assertSame(original, assertFailsWith<LegacyCaptureFailure> {
            awaitLegacyPresentation<Any>(5, { 0 }, { true }, {}, { reads++; throw original }, {})
        })
        assertEquals(1, reads)
    }
}
