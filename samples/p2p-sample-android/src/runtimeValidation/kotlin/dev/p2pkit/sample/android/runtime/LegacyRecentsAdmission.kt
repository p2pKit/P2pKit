package dev.p2pkit.sample.android.runtime

internal enum class LegacyRecentsGuard {
    ROOT_MISSING, ROOT_REFRESH_FAILED, ROOT_NOT_VISIBLE, ROOT_PACKAGE_INVALID, ROOT_GEOMETRY_INVALID,
    TREE_INCOMPLETE, CARD_NOT_IDENTIFIED, READY,
}

/** A bounded observation only: never retries navigation or screenshots, and never catches owner failures. */
internal fun <T : Any> awaitLegacyRecentsState(
    deadline: Long,
    now: () -> Long,
    pause: () -> Unit,
    observe: () -> T?,
): T {
    while (true) {
        checkLegacyCapture(now() <= deadline, LegacyCaptureFailureCode.RECENTS_ADMISSION_TIMEOUT)
        val state = observe()
        checkLegacyCapture(now() <= deadline, LegacyCaptureFailureCode.RECENTS_ADMISSION_TIMEOUT)
        if (state != null) return state
        pause()
    }
}

internal enum class LegacyRecentsResource { OTHER, TITLE, HEADER, THUMBNAIL, SNAPSHOT }

/** No arbitrary system UI strings retained: labels are exact matches against our own public app label. */
internal data class LegacyRecentsNode(
    val parent: Int?,
    val resource: LegacyRecentsResource = LegacyRecentsResource.OTHER,
    val owned: Boolean = true,
    val visible: Boolean = true,
    val bounds: List<Int> = listOf(0, 0, 100, 100),
    val labelMatches: Boolean = false,
    val descriptionMatches: Boolean = false,
    val taskCollectionItem: Boolean = false,
    val closeAction: Boolean = false,
)

internal data class LegacyRecentsCard(val card: Int, val label: Int, val snapshot: Int)

/** These closed image-specific structures correlate a task card, not authenticate arbitrary app labels. */
internal fun findLegacyRecentsCard(api: Int, nodes: List<LegacyRecentsNode>): LegacyRecentsCard? {
    if (nodes.isEmpty() || nodes.size > 256 || nodes[0].parent != null) return null
    if (nodes.indices.drop(1).any { index ->
        val parent = nodes[index].parent
        parent == null || parent !in 0 until index
    }) return null
    fun contained(child: List<Int>, parent: List<Int>): Boolean = child.size == 4 && parent.size == 4 &&
        child[2] > child[0] && child[3] > child[1] && child[0] >= parent[0] && child[1] >= parent[1] &&
        child[2] <= parent[2] && child[3] <= parent[3]
    fun validPath(index: Int): Boolean {
        var current: Int? = index
        while (current != null) {
            val node = nodes[current]
            if (!node.owned || !node.visible || !contained(node.bounds, nodes[0].bounds)) return false
            current = node.parent
        }
        return true
    }
    val matches = nodes.indices.mapNotNull { index ->
        val node = nodes[index]
        val card = when (api) {
            24 -> {
                if (node.resource != LegacyRecentsResource.TITLE || !node.labelMatches) return@mapNotNull null
                val header = node.parent ?: return@mapNotNull null
                if (nodes[header].resource != LegacyRecentsResource.HEADER) return@mapNotNull null
                nodes[header].parent ?: return@mapNotNull null
            }
            32 -> {
                if (!node.descriptionMatches || !node.taskCollectionItem || !node.closeAction) return@mapNotNull null
                index
            }
            else -> return@mapNotNull null
        }
        val snapshotKind = if (api == 24) LegacyRecentsResource.THUMBNAIL else LegacyRecentsResource.SNAPSHOT
        val snapshot = nodes.indices.singleOrNull {
            nodes[it].parent == card && nodes[it].resource == snapshotKind
        } ?: return@mapNotNull null
        if (!validPath(index) || !validPath(card) || !validPath(snapshot) ||
            !contained(node.bounds, nodes[card].bounds) || !contained(nodes[snapshot].bounds, nodes[card].bounds)) {
            return@mapNotNull null
        }
        LegacyRecentsCard(card, index, snapshot)
    }
    return matches.singleOrNull()
}
