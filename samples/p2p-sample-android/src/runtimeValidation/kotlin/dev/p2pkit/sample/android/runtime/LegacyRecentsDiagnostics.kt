package dev.p2pkit.sample.android.runtime

/** Diagnostic history only. Beginning a later query never erases or relabels a completed query. */
internal class LegacyRecentsProgress {
    var attempt = 0
        private set
    var lastCompletedAttempt = 0
        private set
    var lastCompletedGuard: LegacyRecentsGuard? = null
        private set
    val guardCounts = mutableMapOf<LegacyRecentsGuard, Int>()

    fun begin() { attempt++ }

    fun completed(guard: LegacyRecentsGuard) {
        check(attempt > lastCompletedAttempt)
        lastCompletedAttempt = attempt
        lastCompletedGuard = guard
        guardCounts[guard] = (guardCounts[guard] ?: 0) + 1
    }
}

internal data class LegacyRecentsDiagnosticSummary(
    val counts: Map<String, Int>, val candidates: List<Int>, val candidateCount: Int,
)

/** Already-queried closed predicates only. Diagnostic truncation is NEVER a classifier input. */
internal fun summarizeLegacyRecentsNodes(nodes: List<LegacyRecentsNode>): LegacyRecentsDiagnosticSummary {
    check(nodes.size <= 256)
    val counts = linkedMapOf(
        "visited" to nodes.size, "owned" to nodes.count { it.owned }, "visible" to nodes.count { it.visible },
        "labelMatches" to nodes.count { it.labelMatches },
        "descriptionMatches" to nodes.count { it.descriptionMatches },
        "closeAction" to nodes.count { it.closeAction }, "taskCollectionItem" to nodes.count { it.taskCollectionItem },
    )
    LegacyRecentsResource.entries.forEach { resource ->
        counts[resource.name] = nodes.count { it.resource == resource }
    }
    val candidates = nodes.indices.filter { index ->
        val node = nodes[index]
        node.resource != LegacyRecentsResource.OTHER || node.labelMatches || node.descriptionMatches ||
            node.closeAction || node.taskCollectionItem
    }
    return LegacyRecentsDiagnosticSummary(counts, candidates.take(16), candidates.size)
}
