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

    private fun candidateFixture(): List<LegacyEducationNode> = fixture().toMutableList().also {
        it[0] = it[0].copy(resource = LegacyEducationResource.DRAG_LAYER)
    }

    @Test
    fun positiveCandidateSelectorsRequireActualSharedDragLayerOrItsDirectLinearLayout() {
        val direct = selectLegacyRecentsEducationCandidates(candidateFixture())
        assertEquals(LegacyEducationPresence.IDENTIFIED, direct.presence)
        assertEquals(LegacyEducationPopup(1, 2, 3), direct.popup)
        val nodes = candidateFixture()
        val projected = listOf(nodes[0],
            nodes[2].copy(observation = nodes[2].observation.copy(parent = 0)),
            nodes[3].copy(observation = nodes[3].observation.copy(parent = 0)))
        val selection = selectLegacyRecentsEducationCandidates(projected)
        assertEquals(LegacyEducationPresence.IDENTIFIED, selection.presence)
        assertEquals(LegacyEducationPopup(0, 1, 2,
            LegacyEducationParentProjection.DRAG_LAYER_ACCESSIBILITY), selection.popup)
    }

    @Test
    fun noPositiveCandidatesNeverBecomeCompleteTreeAbsenceOrAuthorizeInput() {
        val dismissal = LegacyEducationDismissal()
        var actions = 0
        for (nodes in listOf(emptyList(), listOf(candidateFixture()[0]), candidateFixture().take(2))) {
            val selection = selectLegacyRecentsEducationCandidates(nodes)
            assertEquals(LegacyEducationPresence.NOT_ESTABLISHED_VISUAL_REVIEW_REQUIRED, selection.presence)
            assertNull(selection.popup)
            if (selection.presence == LegacyEducationPresence.IDENTIFIED) {
                dismissal.request(5, { 0 }) { actions++; true }
            }
        }
        assertEquals(0, actions)
        assertFalse(dismissal.requested)
        // Historical complete-tree model absence is deliberately not a candidate-query conclusion.
        assertEquals(LegacyEducationPresence.ABSENT,
            selectLegacyRecentsEducation(listOf(candidateFixture()[0])).presence)
    }

    @Test
    fun partialOrAmbiguousPositiveCandidatesNeverAuthorizeInputOrProveAbsence() {
        val nodes = candidateFixture()
        val invalid = listOf(
            nodes.dropLast(1),
            nodes.take(2) + nodes[3],
            nodes + nodes[2],
            nodes + nodes[3],
            nodes + LegacyEducationNode(LegacyRecentsNode(0), exactText = true),
            nodes + nodes[2].copy(kind = LegacyEducationClass.OTHER, exactText = false),
            nodes + nodes[3].copy(observation = nodes[3].observation.copy(owned = false)),
            nodes + nodes[0].copy(observation = nodes[0].observation.copy(parent = 0)),
            nodes + LegacyEducationNode(LegacyRecentsNode(0)),
        )
        val dismissal = LegacyEducationDismissal()
        var actions = 0
        for (candidate in invalid) {
            val selection = selectLegacyRecentsEducationCandidates(candidate)
            assertEquals(LegacyEducationPresence.REFUSED, selection.presence)
            assertNull(selection.popup)
            if (selection.presence == LegacyEducationPresence.IDENTIFIED) {
                dismissal.request(5, { 0 }) { actions++; true }
            }
        }
        assertEquals(0, actions)
        assertFalse(dismissal.requested)
    }

    @Test
    fun candidateParentProofCannotUseAnUnidentifiedDragLayerOrOnlyACommonAncestor() {
        val nodes = candidateFixture()
        val nested = listOf(nodes[0], LegacyEducationNode(LegacyRecentsNode(0)),
            nodes[1].copy(observation = nodes[1].observation.copy(parent = 1)),
            nodes[2].copy(observation = nodes[2].observation.copy(parent = 2)),
            nodes[3].copy(observation = nodes[3].observation.copy(parent = 2)))
        for (candidate in listOf(fixture(), nested, nodes.toMutableList().also {
            it[3] = it[3].copy(observation = it[3].observation.copy(parent = 0))
        }, nodes.toMutableList().also {
            it[1] = it[1].copy(kind = LegacyEducationClass.OTHER)
        })) {
            val selection = selectLegacyRecentsEducationCandidates(candidate)
            assertEquals(LegacyEducationPresence.REFUSED, selection.presence)
            assertNull(selection.popup)
        }
    }

    @Test
    fun candidateOwnershipVisibilityGeometryAndExactMarkersRemainMandatory() {
        val nodes = candidateFixture()
        for (index in nodes.indices) {
            for (invalid in listOf(nodes[index].observation.copy(owned = false),
                nodes[index].observation.copy(visible = false),
                nodes[index].observation.copy(bounds = listOf(0, 0, 0, 0)))) {
                val candidate = nodes.toMutableList().also { it[index] = it[index].copy(observation = invalid) }
                assertEquals(LegacyEducationPresence.REFUSED,
                    selectLegacyRecentsEducationCandidates(candidate).presence)
            }
        }
        for (invalid in listOf(nodes[2].copy(exactText = false),
            nodes[2].copy(kind = LegacyEducationClass.OTHER),
            nodes[2].copy(resource = LegacyEducationResource.OTHER),
            nodes[2].copy(observation = nodes[2].observation.copy(bounds = listOf(90, 90, 110, 110))))) {
            val candidate = nodes.toMutableList().also { it[2] = invalid }
            assertEquals(LegacyEducationPresence.REFUSED,
                selectLegacyRecentsEducationCandidates(candidate).presence)
        }
    }

    @Test
    fun malformedCandidateGraphsCannotEscapeTheFiniteParentBound() {
        val nodes = candidateFixture()
        val invalid = listOf(List(257) { nodes[0] }, listOf(nodes[0], nodes[0]),
            nodes.toMutableList().also { it[0] = it[0].copy(observation = it[0].observation.copy(parent = 1)) },
            nodes.toMutableList().also { it[1] = it[1].copy(observation = it[1].observation.copy(parent = 2)) },
            nodes.toMutableList().also { it[3] = it[3].copy(observation = it[3].observation.copy(parent = -1)) })
        for (candidate in invalid) {
            val selection = selectLegacyRecentsEducationCandidates(candidate)
            assertEquals(LegacyEducationPresence.REFUSED, selection.presence)
            assertNull(selection.popup)
        }
    }

    @Test
    fun repeatedPositiveCandidateObservationsNeverRearmTheSingleInput() {
        val dismissal = LegacyEducationDismissal()
        var actions = 0
        val nodes = candidateFixture()
        for (candidate in listOf(emptyList(), nodes.dropLast(1), nodes, nodes + nodes[2], nodes)) {
            val selection = selectLegacyRecentsEducationCandidates(candidate)
            assertTrue(selection.presence != LegacyEducationPresence.ABSENT)
            if (selection.presence == LegacyEducationPresence.IDENTIFIED && !dismissal.requested) {
                dismissal.request(5, { 0 }) { actions++; true }
            }
        }
        assertEquals(1, actions)
        assertTrue(dismissal.requested)
        assertFailsWith<IllegalStateException> { dismissal.request(5, { 0 }) { actions++; true } }
        assertEquals(1, actions)
    }

    @Test
    fun exactStructuredPopupAllowsTranslatedArrowWithinRoot() {
        assertEquals(LegacyEducationPopup(1, 2, 3), findLegacyRecentsEducation(fixture()))
        assertEquals(LegacyEducationPresence.IDENTIFIED, selectLegacyRecentsEducation(fixture()).presence)
        assertEquals("Select text and images to copy, share, and more", LEGACY_RECENTS_EDUCATION_TEXT)
    }

    @Test
    fun exactDragLayerProjectionWorksWithoutInventingLinearLayoutParent() {
        for (kind in listOf(LegacyEducationClass.OTHER, LegacyEducationClass.LINEAR_LAYOUT)) {
            val nodes = fixture().toMutableList().also {
                it[1] = it[1].copy(resource = LegacyEducationResource.DRAG_LAYER, kind = kind)
            }
            val selected = selectLegacyRecentsEducation(nodes)
            assertEquals(LegacyEducationPresence.IDENTIFIED, selected.presence)
            assertEquals(LegacyEducationPopup(1, 2, 3,
                LegacyEducationParentProjection.DRAG_LAYER_ACCESSIBILITY), selected.popup)
        }
    }

    @Test
    fun projectedPopupRequiresExactActualSharedOwnedParentNotCommonAncestor() {
        val projected = fixture().toMutableList().also {
            it[1] = it[1].copy(resource = LegacyEducationResource.DRAG_LAYER, kind = LegacyEducationClass.OTHER)
        }
        for (invalid in listOf(
            projected.toMutableList().also { it[1] = it[1].copy(resource = LegacyEducationResource.OTHER) },
            projected.toMutableList().also {
                it[3] = it[3].copy(observation = it[3].observation.copy(parent = 0))
            },
            projected.toMutableList().also {
                it[1] = it[1].copy(observation = it[1].observation.copy(owned = false))
            },
            projected.toMutableList().also {
                it[1] = it[1].copy(observation = it[1].observation.copy(visible = false))
            })) {
            assertEquals(LegacyEducationPresence.REFUSED, selectLegacyRecentsEducation(invalid).presence)
            assertNull(findLegacyRecentsEducation(invalid))
        }
    }

    @Test
    fun extraMalformedMarkersRefuseEvenWhenOneValidPairAndCardExist() {
        for (extra in listOf(
            fixture()[2].copy(kind = LegacyEducationClass.OTHER, exactText = false),
            fixture()[3].copy(observation = fixture()[3].observation.copy(parent = 0, owned = false)),
            fixture()[3].copy(observation = fixture()[3].observation.copy(visible = false)),
            LegacyEducationNode(LegacyRecentsNode(0), exactText = true))) {
            val nodes = fixture() + extra + listOf(
                LegacyEducationNode(LegacyRecentsNode(0, descriptionMatches = true,
                    taskCollectionItem = true, closeAction = true)),
                LegacyEducationNode(LegacyRecentsNode(5, LegacyRecentsResource.SNAPSHOT)))
            assertNotNull(findLegacyRecentsCard(32, nodes.map { it.observation }))
            assertNull(findLegacyRecentsEducation(nodes))
            assertEquals(LegacyEducationPresence.REFUSED, selectLegacyRecentsEducation(nodes).presence)
        }
    }

    @Test
    fun dragLayerIsOnlyAContainerAndNeverAnAbsenceBlockingMarker() {
        val nodes = listOf(fixture()[0], fixture()[1].copy(resource = LegacyEducationResource.DRAG_LAYER))
        assertEquals(LegacyEducationPresence.ABSENT, selectLegacyRecentsEducation(nodes).presence)
        for (marker in listOf(fixture()[2], fixture()[3],
            LegacyEducationNode(LegacyRecentsNode(1), exactText = true))) {
            assertEquals(LegacyEducationPresence.REFUSED, selectLegacyRecentsEducation(nodes + marker).presence)
        }
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
    fun observerRefreshRunsOnlyAfterTimelyTrueAcknowledgement() {
        for (mode in listOf("accepted", "rejected", "thrown", "late", "expired")) {
            val state = LegacyEducationDismissal()
            val calls = mutableListOf<String>()
            var clock = if (mode == "expired") 5L else 0L
            val original = IllegalStateException("synthetic action failure")
            fun request() = state.request(5, { clock }, afterAcknowledged = { calls += "refresh" }) {
                calls += "action"
                if (mode == "thrown") throw original
                if (mode == "late") clock = 5
                mode != "rejected"
            }
            if (mode == "accepted") {
                request()
                assertEquals(listOf("action", "refresh"), calls)
            } else {
                val failure = assertFailsWith<IllegalStateException> { request() }
                if (mode == "thrown") assertSame(original, failure)
                assertEquals(if (mode == "expired") emptyList() else listOf("action"), calls)
            }
        }
    }

    @Test
    fun observerRefreshFailureOrExpiryCannotRetryOrExtendTheOriginalDeadline() {
        for (mode in listOf("thrown", "late")) {
            val state = LegacyEducationDismissal()
            var clock = 0L
            val calls = mutableListOf<String>()
            val original = IllegalStateException("synthetic observer failure")
            val failure = assertFailsWith<IllegalStateException> {
                state.request(5, { clock }, afterAcknowledged = {
                    assertEquals(4L, clock)
                    calls += "refresh"
                    if (mode == "thrown") throw original
                    clock = 5
                }) { calls += "action"; clock = 4; true }
            }
            if (mode == "thrown") assertSame(original, failure)
            assertFailsWith<IllegalStateException> {
                state.request(5, { 0 }, afterAcknowledged = { calls += "retry-refresh" }) {
                    calls += "retry-action"; true
                }
            }
            assertEquals(listOf("action", "refresh"), calls)
        }
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
