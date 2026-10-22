package dev.p2pkit.sample.android.runtime

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertSame

/** Pure timing/return ownership checks, not native window readiness. */
class LegacyRecentsAdmissionTest {
    @Test
    fun firstReadyStateIsReturnedWithoutAnotherAcquisitionOrPause() {
        val original = Any()
        var observations = 0
        var pauses = 0
        assertSame(original, awaitLegacyRecentsState(5, { 0 }, { pauses++ }) { observations++; original })
        assertEquals(1, observations)
        assertEquals(0, pauses)
    }

    @Test
    fun pendingThenReadyReturnsTheExactCompleteState() {
        var time = 0L
        var observations = 0
        val original = Any()
        assertSame(original, awaitLegacyRecentsState(5, { time }, { time++ }) {
            observations++
            if (time == 0L) null else original
        })
        assertEquals(2, observations)
        assertEquals(1L, time)
    }

    @Test
    fun expiredAndPersistentlyPendingObservationsFailWithoutLateQueries() {
        var calls = 0
        val expired = assertFailsWith<LegacyCaptureFailure> {
            awaitLegacyRecentsState(5, { 6 }, { error("no pause") }) { calls++; Any() }
        }
        assertEquals(LegacyCaptureFailureCode.RECENTS_ADMISSION_TIMEOUT, expired.code)
        assertEquals(0, calls)
        var time = 0L
        val pending = assertFailsWith<LegacyCaptureFailure> {
            awaitLegacyRecentsState<Any>(1, { time }, { time++ }) { calls++; null }
        }
        assertEquals(LegacyCaptureFailureCode.RECENTS_ADMISSION_TIMEOUT, pending.code)
        assertEquals(2, calls)
    }

    @Test
    fun aReadyObservationThatFinishesAfterDeadlineCannotPass() {
        var time = 0L
        var calls = 0
        val failure = assertFailsWith<LegacyCaptureFailure> {
            awaitLegacyRecentsState(5, { time }, { error("no retry") }) { calls++; time = 6; Any() }
        }
        assertEquals(LegacyCaptureFailureCode.RECENTS_ADMISSION_TIMEOUT, failure.code)
        assertEquals(1, calls)
    }

    @Test
    fun ownerOrPlatformFailurePropagatesWithoutPendingConversionOrRetry() {
        for (original in listOf(IllegalStateException("synthetic owner"), SecurityException("synthetic platform"))) {
            var calls = 0
            val actual = assertFailsWith<RuntimeException> {
                awaitLegacyRecentsState<Any>(5, { 0 }, { error("no retry") }) { calls++; throw original }
            }
            assertSame(original, actual)
            assertEquals(1, calls)
        }
    }
}
