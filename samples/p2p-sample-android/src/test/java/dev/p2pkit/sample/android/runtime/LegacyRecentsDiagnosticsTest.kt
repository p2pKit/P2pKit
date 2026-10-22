package dev.p2pkit.sample.android.runtime

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNull

/** Pure diagnostic models, never native task-card or provider qualification. */
class LegacyRecentsDiagnosticsTest {
    @Test
    fun interruptedLaterQueryPreservesAndIdentifiesPreviousCompletedReason() {
        val progress = LegacyRecentsProgress()
        progress.begin()
        progress.completed(LegacyRecentsGuard.CARD_NOT_IDENTIFIED)
        progress.begin() // The next native tree could now time out without calling completed.
        assertEquals(2, progress.attempt)
        assertEquals(1, progress.lastCompletedAttempt)
        assertEquals(LegacyRecentsGuard.CARD_NOT_IDENTIFIED, progress.lastCompletedGuard)
        assertEquals(mapOf(LegacyRecentsGuard.CARD_NOT_IDENTIFIED to 1), progress.guardCounts)
    }

    @Test
    fun completedCountsAreExactAndDuplicateCompletionIsRejected() {
        val progress = LegacyRecentsProgress()
        assertNull(progress.lastCompletedGuard)
        assertFailsWith<IllegalStateException> { progress.completed(LegacyRecentsGuard.READY) }
        progress.begin()
        progress.completed(LegacyRecentsGuard.ROOT_MISSING)
        progress.begin()
        progress.completed(LegacyRecentsGuard.READY)
        assertEquals(2, progress.lastCompletedAttempt)
        assertEquals(mapOf(LegacyRecentsGuard.ROOT_MISSING to 1, LegacyRecentsGuard.READY to 1), progress.guardCounts)
        assertFailsWith<IllegalStateException> { progress.completed(LegacyRecentsGuard.READY) }
    }

    @Test
    fun summaryUsesOnlyExistingClosedPredicatesAndDoesNotMutateInput() {
        val nodes = listOf(LegacyRecentsNode(null), LegacyRecentsNode(0, labelMatches = true),
            LegacyRecentsNode(0, descriptionMatches = true, closeAction = true, taskCollectionItem = true),
            LegacyRecentsNode(2, resource = LegacyRecentsResource.SNAPSHOT, visible = false))
        val copy = nodes.toList()
        val summary = summarizeLegacyRecentsNodes(nodes)
        assertEquals(listOf(1, 2, 3), summary.candidates)
        assertEquals(1, summary.counts["labelMatches"])
        assertEquals(1, summary.counts["SNAPSHOT"])
        assertEquals(3, summary.counts["visible"])
        assertEquals(copy, nodes)
    }

    @Test
    fun candidateTruncationIsExplicitAndNeverChangesClassifierInput() {
        val nodes = List(20) { LegacyRecentsNode(if (it == 0) null else 0, labelMatches = true) }
        val before = findLegacyRecentsCard(24, nodes)
        val summary = summarizeLegacyRecentsNodes(nodes)
        assertEquals(20, summary.candidateCount)
        assertEquals((0 until 16).toList(), summary.candidates)
        assertEquals(before, findLegacyRecentsCard(24, nodes))
        assertEquals(20, nodes.size)
    }

    @Test
    fun diagnosticOverflowCannotSilentlyClaimCompleteSummary() {
        assertFailsWith<IllegalStateException> { summarizeLegacyRecentsNodes(List(257) { LegacyRecentsNode(null) }) }
    }
}
