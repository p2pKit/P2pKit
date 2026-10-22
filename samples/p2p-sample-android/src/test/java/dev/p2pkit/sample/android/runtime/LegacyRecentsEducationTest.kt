package dev.p2pkit.sample.android.runtime

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Pure setup-selector/input-flow models only; not proprietary launcher or native privacy evidence. */
class LegacyRecentsEducationTest {
    private fun fixture(): List<LegacyEducationNode> = listOf(
        LegacyEducationNode(LegacyRecentsNode(null)),
        LegacyEducationNode(LegacyRecentsNode(0, bounds = listOf(10, 20, 50, 40)),
            kind = LegacyEducationClass.LINEAR_LAYOUT),
        LegacyEducationNode(LegacyRecentsNode(1, bounds = listOf(10, 20, 50, 35)),
            LegacyEducationResource.TEXT, LegacyEducationClass.TEXT_VIEW, exactText = true),
        // The actual layout can translate the decorative arrow outside the parent but inside the root.
        LegacyEducationNode(LegacyRecentsNode(1, bounds = listOf(60, 40, 65, 45)),
            LegacyEducationResource.ARROW, LegacyEducationClass.VIEW),
    )

    @Test
    fun exactStructuredPopupAllowsTranslatedArrowWithinRoot() {
        assertEquals(LegacyEducationPopup(1, 2, 3), findLegacyRecentsEducation(fixture()))
        assertEquals(LegacyEducationPresence.IDENTIFIED, selectLegacyRecentsEducation(fixture()).presence)
        assertEquals("Select text and images to copy, share, and more", LEGACY_RECENTS_EDUCATION_TEXT)
    }

    @Test
    fun wrongTextResourceOrClassCannotAdmitInput() {
        for (node in listOf(fixture()[2].copy(exactText = false),
            fixture()[2].copy(resource = LegacyEducationResource.OTHER),
            fixture()[2].copy(kind = LegacyEducationClass.OTHER))) {
            assertNull(findLegacyRecentsEducation(fixture().toMutableList().also { it[2] = node }))
        }
        assertNull(findLegacyRecentsEducation(fixture().toMutableList().also {
            it[1] = it[1].copy(kind = LegacyEducationClass.OTHER)
        }))
        assertNull(findLegacyRecentsEducation(fixture().toMutableList().also {
            it[3] = it[3].copy(kind = LegacyEducationClass.OTHER)
        }))
    }

    @Test
    fun foreignHiddenOrOffRootNodesNeverAdmitInput() {
        for (index in 0..3) {
            for (invalid in listOf(fixture()[index].observation.copy(owned = false),
                fixture()[index].observation.copy(visible = false),
                fixture()[index].observation.copy(bounds = listOf(0, 0, 0, 0)))) {
                assertNull(findLegacyRecentsEducation(fixture().toMutableList().also {
                    it[index] = it[index].copy(observation = invalid)
                }))
            }
        }
        for (index in listOf(2, 3)) {
            assertNull(findLegacyRecentsEducation(fixture().toMutableList().also {
                it[index] = it[index].copy(observation = it[index].observation.copy(bounds = listOf(90, 90, 110, 110)))
            }))
        }
    }

    @Test
    fun missingAmbiguousOrMalformedStructureNeverAdmitsInput() {
        assertNull(findLegacyRecentsEducation(fixture().dropLast(1)))
        assertNull(findLegacyRecentsEducation(fixture() + fixture()[3]))
        assertNull(findLegacyRecentsEducation(fixture() + fixture()[2]))
        assertNull(findLegacyRecentsEducation(fixture().toMutableList().also {
            it[3] = it[3].copy(observation = it[3].observation.copy(parent = 0))
        }))
        assertNull(findLegacyRecentsEducation(fixture().toMutableList().also {
            it[1] = it[1].copy(observation = it[1].observation.copy(parent = 2))
        }))
        assertNull(findLegacyRecentsEducation(List(257) { fixture()[0] }))
        assertNull(findLegacyRecentsEducation(emptyList()))
    }

    @Test
    fun requestBitIsSetBeforeExactlyOnePublicAction() {
        val state = LegacyEducationDismissal()
        var actions = 0
        assertFalse(state.requested)
        state.request(5, { 0 }) { assertTrue(state.requested); actions++; true }
        assertFailsWith<IllegalStateException> { state.request(5, { 0 }) { actions++; true } }
        assertEquals(1, actions)
    }

    @Test
    fun rejectedThrownOrLateRequestIsNeverRetried() {
        for (mode in listOf("rejected", "thrown", "late")) {
            val state = LegacyEducationDismissal()
            var actions = 0
            var now = 0L
            val original = IllegalStateException("synthetic public action error")
            val failure = assertFailsWith<IllegalStateException> {
                state.request(5, { now }) {
                    actions++
                    if (mode == "thrown") throw original
                    if (mode == "late") now = 5
                    mode != "rejected"
                }
            }
            if (mode == "thrown") assertSame(original, failure)
            assertTrue(state.requested)
            assertFailsWith<IllegalStateException> { state.request(5, { 0 }) { actions++; true } }
            assertEquals(1, actions)
        }
    }

    @Test
    fun expiredBudgetDoesNotIssueAnAction() {
        val state = LegacyEducationDismissal()
        assertFailsWith<LegacyCaptureFailure> { state.request(5, { 5 }) { error("must not execute") } }
        assertFalse(state.requested)
    }

    @Test
    fun acknowledgementOrPersistentPopupAloneCannotCompleteAdmission() {
        val dismissal = LegacyEducationDismissal()
        var clock = 0L
        var actions = 0
        assertFailsWith<LegacyCaptureFailure> {
            awaitLegacyRecentsState<Any>(5, { clock }, { clock++ }) {
                assertNotNull(findLegacyRecentsEducation(fixture()))
                if (!dismissal.requested) dismissal.request(5, { clock }) { actions++; true }
                null // Still-present popup or missing real card never becomes a successful observation.
            }
        }
        assertEquals(1, actions)
    }

    @Test
    fun noKnownPopupIssuesNoInputAndOnlySubsequentRealCardCanComplete() {
        val dismissal = LegacyEducationDismissal()
        var clock = 0L
        val realCard = Any()
        val result = awaitLegacyRecentsState(5, { clock }, { clock++ }) {
            assertEquals(LegacyEducationPresence.ABSENT,
                selectLegacyRecentsEducation(listOf(fixture()[0])).presence)
            if (clock == 2L) realCard else null
        }
        assertSame(realCard, result)
        assertFalse(dismissal.requested)
    }

    @Test
    fun refusedOrAmbiguousPopupCannotBecomeAbsenceEvenWithRealCard() {
        val refused = listOf(fixture().dropLast(1), fixture() + fixture()[2],
            fixture().toMutableList().also { it[2] = it[2].copy(kind = LegacyEducationClass.OTHER) },
            fixture().toMutableList().also {
                it[2] = it[2].copy(observation = it[2].observation.copy(visible = false))
            })
        for (popup in refused) {
            val withCard = popup + listOf(
                LegacyEducationNode(LegacyRecentsNode(0, descriptionMatches = true,
                    taskCollectionItem = true, closeAction = true)),
                LegacyEducationNode(LegacyRecentsNode(popup.size, LegacyRecentsResource.SNAPSHOT)))
            val realCard = assertNotNull(findLegacyRecentsCard(32, withCard.map { it.observation }))
            var clock = 0L
            assertFailsWith<LegacyCaptureFailure> {
                awaitLegacyRecentsState(5, { clock }, { clock++ }) {
                    val selection = selectLegacyRecentsEducation(withCard)
                    assertEquals(LegacyEducationPresence.REFUSED, selection.presence)
                    assertNull(selection.popup) // No input can be admitted either.
                    if (selection.presence == LegacyEducationPresence.ABSENT) realCard else null
                }
            }
        }
        for (invalid in listOf(emptyList(), List(257) { fixture()[0] },
            listOf(fixture()[0], fixture()[0]))) {
            assertEquals(LegacyEducationPresence.REFUSED, selectLegacyRecentsEducation(invalid).presence)
        }
    }
}
