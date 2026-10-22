package dev.p2pkit.sample.android.runtime

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Pure control-flow/ownership models, not actual Android scene or privacy evidence. */
class LegacyFailureSceneTest {
    private val primary = LegacyCaptureFailure(LegacyCaptureFailureCode.RECENTS_ADMISSION_TIMEOUT)

    @Test
    fun onlyExactApi32RecentsFailureBeforeOriginalScreenshotIsEligible() {
        fun eligible(api: Int = 32, stage: String = "actual-recents-original", error: Throwable = primary,
            completed: List<String> = listOf("initial-secure-foreground"), requested: Boolean = false) =
            needsLegacyFailureScene(api, stage, error, completed, requested)
        assertTrue(eligible())
        assertFalse(eligible(api = 24))
        assertFalse(eligible(api = 35))
        assertFalse(eligible(stage = "same-task-reentry"))
        assertFalse(eligible(error = IllegalStateException()))
        assertFalse(eligible(error = LegacyCaptureFailure(LegacyCaptureFailureCode.CAPTURE_STATE_INVALID)))
        assertFalse(eligible(completed = emptyList()))
        assertFalse(eligible(completed = listOf("initial-secure-foreground", "actual-recents-original")))
        assertFalse(eligible(requested = true))
    }

    @Test
    fun oneCaptureHasTwoEqualStateObservationsAndExactlyOneRelease() {
        val bitmap = Any()
        val order = mutableListOf<String>()
        captureLegacyFailureScene(5, { 0 }, { order += "state"; "same" },
            { order += "capture"; bitmap }, { assertSame(bitmap, it); order += "retain" },
            { assertSame(bitmap, it); order += "release" })
        assertEquals(listOf("state", "capture", "state", "retain", "release"), order)
    }

    @Test
    fun exhaustedBudgetNeverReadsStateOrCaptures() {
        assertEquals(LegacyCaptureFailureCode.BODY_DEADLINE_EXCEEDED,
            assertFailsWith<LegacyCaptureFailure> {
                captureLegacyFailureScene<Any, Any>(5, { 5 }, { error("state must not execute") },
                    { error("capture must not execute") }, { error("retain") }, { error("release") })
            }.code)
    }

    @Test
    fun nullCaptureIsNotRetainedOrRecycledOrRetried() {
        var calls = 0
        assertEquals(LegacyCaptureFailureCode.SCREENSHOT_UNAVAILABLE,
            assertFailsWith<LegacyCaptureFailure> {
                captureLegacyFailureScene<String, Any>(5, { 0 }, { "same" }, { calls++; null },
                    { error("retain") }, { error("release") })
            }.code)
        assertEquals(1, calls)
    }

    @Test
    fun thrownScreenshotIsUnchangedAndNeverRetried() {
        val secondary = IllegalStateException("synthetic screenshot failure")
        var calls = 0
        assertSame(secondary, assertFailsWith<IllegalStateException> {
            captureLegacyFailureScene<String, Any>(5, { 0 }, { "same" }, { calls++; throw secondary },
                { error("retain") }, { error("release") })
        })
        assertEquals(1, calls)
    }

    @Test
    fun changedOrThrowingAfterStateReleasesWithoutRetention() {
        for (throws in listOf(false, true)) {
            var states = 0
            var releases = 0
            val secondary = IllegalStateException("synthetic after state")
            val result = assertFailsWith<IllegalStateException> {
                captureLegacyFailureScene(5, { 0 }, {
                    states++
                    if (throws && states == 2) throw secondary
                    states
                }, { Any() }, { error("retain") }, { releases++ })
            }
            if (throws) assertSame(secondary, result)
            else assertEquals(LegacyCaptureFailureCode.CAPTURE_STATE_INVALID, (result as LegacyCaptureFailure).code)
            assertEquals(2, states)
            assertEquals(1, releases)
        }
    }

    @Test
    fun lateScreenshotIsReleasedWithoutAfterQueryOrRetention() {
        var clock = 0L
        var states = 0
        var releases = 0
        assertFailsWith<LegacyCaptureFailure> {
            captureLegacyFailureScene(5, { clock }, { states++; "same" }, { clock = 5; Any() },
                { error("retain") }, { releases++ })
        }
        assertEquals(1, states)
        assertEquals(1, releases)
    }

    @Test
    fun failedOrLateRetentionReleasesAndCannotCompleteSuccessfully() {
        for (late in listOf(false, true)) {
            var clock = 0L
            var releases = 0
            val secondary = IllegalStateException("synthetic encoding")
            val result = assertFailsWith<IllegalStateException> {
                captureLegacyFailureScene(5, { clock }, { "same" }, { Any() },
                    { if (late) clock = 5 else throw secondary }, { releases++ })
            }
            if (late) assertEquals(LegacyCaptureFailureCode.BODY_DEADLINE_EXCEEDED,
                (result as LegacyCaptureFailure).code)
            else assertSame(secondary, result)
            assertEquals(1, releases)
        }
    }
}
