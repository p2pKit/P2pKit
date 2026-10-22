package dev.p2pkit.sample.android.runtime

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

/** Synthetic node graphs exercise the classifier, not actual Launcher/SystemUI identity or pixels. */
class LegacyRecentsCardTest {
    private fun nodes(api: Int): List<LegacyRecentsNode> = if (api == 24) listOf(
        LegacyRecentsNode(null),
        LegacyRecentsNode(0),
        LegacyRecentsNode(1, LegacyRecentsResource.HEADER, bounds = listOf(0, 0, 100, 20)),
        LegacyRecentsNode(2, LegacyRecentsResource.TITLE, bounds = listOf(1, 1, 99, 19), labelMatches = true),
        LegacyRecentsNode(1, LegacyRecentsResource.THUMBNAIL, bounds = listOf(0, 20, 100, 100)),
    ) else listOf(
        LegacyRecentsNode(null),
        LegacyRecentsNode(0, descriptionMatches = true, taskCollectionItem = true, closeAction = true),
        LegacyRecentsNode(1, LegacyRecentsResource.SNAPSHOT),
    )

    @Test
    fun exactClosedStructuresIdentifyOneBoundedCard() {
        assertEquals(LegacyRecentsCard(1, 3, 4), findLegacyRecentsCard(24, nodes(24)))
        assertEquals(LegacyRecentsCard(1, 1, 2), findLegacyRecentsCard(32, nodes(32)))
        assertNull(findLegacyRecentsCard(35, nodes(32)))
    }

    @Test
    fun homeLabelOrDescriptionWithoutTaskStructureDoesNotMatch() {
        assertNull(findLegacyRecentsCard(24, listOf(LegacyRecentsNode(null),
            LegacyRecentsNode(0, LegacyRecentsResource.TITLE, labelMatches = true))))
        for (replacement in listOf(nodes(32)[1].copy(taskCollectionItem = false),
                nodes(32)[1].copy(closeAction = false), nodes(32)[1].copy(descriptionMatches = false))) {
            assertNull(findLegacyRecentsCard(32, nodes(32).toMutableList().also { it[1] = replacement }))
        }
        assertNull(findLegacyRecentsCard(32, nodes(32).dropLast(1)))
    }

    @Test
    fun titleMustBeExactAndUnderItsOwnTaskHeaderWithThumbnailSibling() {
        for (replacement in listOf(nodes(24)[3].copy(labelMatches = false),
                nodes(24)[3].copy(parent = 1), nodes(24)[3].copy(resource = LegacyRecentsResource.OTHER))) {
            assertNull(findLegacyRecentsCard(24, nodes(24).toMutableList().also { it[3] = replacement }))
        }
        assertNull(findLegacyRecentsCard(24, nodes(24).toMutableList().also { it[4] = it[4].copy(parent = 2) }))
    }

    @Test
    fun hiddenForeignOrOutOfBoundsNodesAnywhereOnMatchedPathFail() {
        for (api in listOf(24, 32)) for (index in nodes(api).indices) {
            for (replacement in listOf(nodes(api)[index].copy(owned = false),
                    nodes(api)[index].copy(visible = false),
                    nodes(api)[index].copy(bounds = listOf(0, 0, 0, 0)))) {
                assertNull(findLegacyRecentsCard(api, nodes(api).toMutableList().also { it[index] = replacement }))
            }
        }
        assertNull(findLegacyRecentsCard(24, nodes(24).toMutableList().also {
            it[3] = it[3].copy(bounds = listOf(1, 1, 101, 19))
        }))
    }

    @Test
    fun duplicateLabelsCardsOrSnapshotsAreAmbiguousNotFirstMatchWins() {
        assertNull(findLegacyRecentsCard(24, nodes(24) + nodes(24)[3]))
        assertNull(findLegacyRecentsCard(32, nodes(32) + nodes(32)[2]))
        assertNull(findLegacyRecentsCard(32, nodes(32) + listOf(nodes(32)[1], nodes(32)[2].copy(parent = 3))))
    }

    @Test
    fun malformedOrOverLimitGraphCannotBePartiallyAccepted() {
        assertNull(findLegacyRecentsCard(24, emptyList()))
        assertNull(findLegacyRecentsCard(24, nodes(24).toMutableList().also { it[2] = it[2].copy(parent = 3) }))
        assertNull(findLegacyRecentsCard(24, nodes(24).toMutableList().also { it[2] = it[2].copy(parent = null) }))
        assertNull(findLegacyRecentsCard(32, nodes(32) + List(254) { LegacyRecentsNode(0) }))
    }
}
