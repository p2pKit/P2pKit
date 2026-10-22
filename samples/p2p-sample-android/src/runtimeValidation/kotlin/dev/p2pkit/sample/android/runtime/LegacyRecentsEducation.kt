package dev.p2pkit.sample.android.runtime

/** Exact controlled-image fixture, not a substring/locale fallback or task authentication. */
internal const val LEGACY_RECENTS_EDUCATION_TEXT = "Select text and images to copy, share, and more"

internal enum class LegacyEducationResource { OTHER, TEXT, ARROW }
internal enum class LegacyEducationClass { OTHER, TEXT_VIEW, VIEW, LINEAR_LAYOUT }
internal data class LegacyEducationNode(
    val observation: LegacyRecentsNode,
    val resource: LegacyEducationResource = LegacyEducationResource.OTHER,
    val kind: LegacyEducationClass = LegacyEducationClass.OTHER,
    val exactText: Boolean = false,
)
internal data class LegacyEducationPopup(val parent: Int, val text: Int, val arrow: Int)

/** Only a complete owned structured popup permits an input; never changes the real TaskView matcher. */
internal fun findLegacyRecentsEducation(nodes: List<LegacyEducationNode>): LegacyEducationPopup? {
    if (nodes.isEmpty() || nodes.size > 256 || nodes[0].observation.parent != null) return null
    if (nodes.indices.drop(1).any { index ->
        val parent = nodes[index].observation.parent
        parent == null || parent !in 0 until index
    }) return null
    fun positive(bounds: List<Int>) = bounds.size == 4 && bounds[0] < bounds[2] && bounds[1] < bounds[3]
    fun valid(index: Int): Boolean {
        var current: Int? = index
        while (current != null) {
            val node = nodes[current].observation
            if (!node.owned || !node.visible || !positive(node.bounds)) return false
            current = node.parent
        }
        return true
    }
    val root = nodes[0].observation.bounds
    if (!positive(root)) return null
    fun inRoot(index: Int): Boolean {
        val bounds = nodes[index].observation.bounds
        return positive(bounds) && root[0] <= bounds[0] && root[1] <= bounds[1] &&
            bounds[2] <= root[2] && bounds[3] <= root[3]
    }
    return nodes.indices.mapNotNull { index ->
        val text = nodes[index]
        if (text.resource != LegacyEducationResource.TEXT || text.kind != LegacyEducationClass.TEXT_VIEW ||
            !text.exactText) return@mapNotNull null
        val parent = text.observation.parent ?: return@mapNotNull null
        if (nodes[parent].kind != LegacyEducationClass.LINEAR_LAYOUT) return@mapNotNull null
        val arrow = nodes.indices.singleOrNull { nodes[it].observation.parent == parent &&
            nodes[it].resource == LegacyEducationResource.ARROW && nodes[it].kind == LegacyEducationClass.VIEW }
            ?: return@mapNotNull null
        if (!valid(index) || !valid(arrow) || !inRoot(index) || !inRoot(arrow)) return@mapNotNull null
        // The decorative arrow may be translated outside its parent's box, but never outside this root.
        LegacyEducationPopup(parent, index, arrow)
    }.singleOrNull()
}

/** The bit is set before the public request, so even a thrown or rejected request can never be retried. */
internal class LegacyEducationDismissal {
    var requested = false
        private set

    fun request(until: Long, now: () -> Long, perform: () -> Boolean) {
        check(!requested)
        checkLegacyCapture(now() < until, LegacyCaptureFailureCode.RECENTS_ADMISSION_TIMEOUT)
        requested = true
        val accepted = perform()
        checkLegacyCapture(now() < until, LegacyCaptureFailureCode.RECENTS_ADMISSION_TIMEOUT)
        checkLegacyCapture(accepted, LegacyCaptureFailureCode.NAVIGATION_ACTION_REJECTED)
    }
}
