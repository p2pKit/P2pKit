package dev.p2pkit.sample.android.runtime

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class FrameCommitRetirementTest {
    @Test
    fun neverRegisteredNeedsNoFrameworkCall() {
        assertTrue(frameCommitRetired(false, { error("Not registered") }, { error("Not registered") }))
    }

    @Test
    fun alreadyCommittedNeedsNoUnregister() {
        assertTrue(frameCommitRetired(true, { true }, { error("Already committed") }))
    }

    @Test
    fun successfulUnregisterProvesCancellation() {
        assertTrue(frameCommitRetired(true, { false }, { true }))
    }

    @Test
    fun queuedOrRunningCallbackRemainsOwnedUntilItsCompletionIsObserved() {
        var completed = false
        var removals = 0
        val unregister = { removals++; false }
        assertFalse(frameCommitRetired(true, { completed }, unregister))
        assertFalse(frameCommitRetired(true, { completed }, unregister))
        assertEquals(2, removals)
        completed = true
        assertTrue(frameCommitRetired(true, { completed }, unregister))
        assertEquals(2, removals)
    }

    @Test
    fun callbackCompletionRacingFailedUnregisterIsObserved() {
        var completed = false
        assertTrue(frameCommitRetired(true, { completed }, { completed = true; false }))
    }

    @Test
    fun unknownRemovalNeverBecomesRetirement() {
        repeat(10) { assertFalse(frameCommitRetired(true, { false }, { false })) }
    }

    @Test
    fun deadObserverFailureIsNotConvertedIntoRetirement() {
        assertFailsWith<IllegalStateException> {
            frameCommitRetired(true, { false }, { error("Observer is dead") })
        }
    }
}
