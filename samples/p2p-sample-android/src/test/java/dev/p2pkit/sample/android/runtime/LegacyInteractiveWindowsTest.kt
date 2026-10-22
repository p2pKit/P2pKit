package dev.p2pkit.sample.android.runtime

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNull
import kotlin.test.assertSame

/** Pure ownership/selection controls, not actual Android service or window inventory execution. */
class LegacyInteractiveWindowsTest {
    @Test
    fun flagsPreserveAllExistingBitsAndRestoreTheExactOriginal() {
        for (original in listOf(18, 82, 274)) {
            var actual = original
            val writes = mutableListOf<Int>()
            val owner = LegacyInteractiveWindowFlags({ actual }, { actual = it; writes += it }, 64)
            assertEquals(emptyList(), writes)
            assertEquals(original or 64, owner.enable())
            assertEquals(original, owner.restore())
            assertEquals(listOf(original or 64, original), writes)
        }
    }

    @Test
    fun absorbedSetFailureIsRejectedByReadbackAndStillRestorable() {
        var actual = 18
        val owner = LegacyInteractiveWindowFlags({ actual }, { if (it == 18) actual = it }, 64)
        assertEquals(LegacyCaptureFailureCode.OBSERVER_FLAGS_INVALID,
            assertFailsWith<LegacyCaptureFailure> { owner.enable() }.code)
        assertEquals(18, owner.restore())
    }

    @Test
    fun originalIsOwnedBeforeThrowingPartialMutationAndRestoredIndependently() {
        var actual = 18
        val originalError = IllegalStateException("synthetic")
        val owner = LegacyInteractiveWindowFlags({ actual }, { actual = it; if (it == 82) throw originalError }, 64)
        assertSame(originalError, assertFailsWith<IllegalStateException> { owner.enable() })
        assertEquals(82, actual)
        assertEquals(18, owner.restore())
    }

    @Test
    fun wrongRestorationReadbackNeverBecomesSuccessfulCleanup() {
        var actual = 18
        val owner = LegacyInteractiveWindowFlags({ actual }, { if (it == 82) actual = it }, 64)
        owner.enable()
        assertEquals(LegacyCaptureFailureCode.OBSERVER_FLAGS_INVALID,
            assertFailsWith<LegacyCaptureFailure> { owner.restore() }.code)
    }

    @Test
    fun failedInitialReadDoesNotMutateAnyFlags() {
        var writes = 0
        val originalError = IllegalStateException("synthetic")
        assertSame(originalError, assertFailsWith<IllegalStateException> {
            LegacyInteractiveWindowFlags({ throw originalError }, { writes++ }, 64)
        })
        assertEquals(0, writes)
    }

    private val view = listOf(0, 30, 100, 200)
    private val points = listOf(10 to 50, 30 to 50, 50 to 50, 70 to 50)
    private val target = LegacyInteractiveWindow(7, 1, active = true, focused = true, bounds = view)
    private fun find(windows: List<LegacyInteractiveWindow>) = findLegacyInteractiveWindow(windows, 7, 1, view, points)

    @Test
    fun actualIdIsSelectedNotFirstWindowAndInsetsAreAllowed() {
        assertSame(target, find(listOf(target.copy(id = 3), target)))
        assertSame(target, find(listOf(target)))
        assertNull(find(listOf(target.copy(id = 3))))
        assertNull(find(emptyList()))
    }

    @Test
    fun duplicateTargetOrOverflowNeverUsesPartialMatch() {
        assertEquals(LegacyCaptureFailureCode.CAPTURE_STATE_INVALID,
            assertFailsWith<LegacyCaptureFailure> { find(listOf(target, target.copy(active = false))) }.code)
        assertEquals(LegacyCaptureFailureCode.INTERACTIVE_WINDOW_LIMIT_EXCEEDED,
            assertFailsWith<LegacyCaptureFailure> { find(List(257) { target.copy(id = it) }) }.code)
    }

    @Test
    fun wrongTypeInactiveOrUnfocusedTargetCannotAdmit() {
        for (invalid in listOf(target.copy(type = 2), target.copy(active = false), target.copy(focused = false))) {
            assertNull(find(listOf(invalid)))
        }
    }

    @Test
    fun clippedOrMalformedWindowAndOutsideSampleCannotAdmit() {
        for (invalid in listOf(emptyList(), listOf(0, 31, 100, 200), listOf(0, 30, 99, 200), listOf(0, 0, 0, 0))) {
            assertNull(find(listOf(target.copy(bounds = invalid))))
        }
        assertNull(findLegacyInteractiveWindow(listOf(target), 7, 1, view, listOf(100 to 50)))
    }
}
