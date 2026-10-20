package dev.p2pkit.sample.android.runtime

/** Pure admission for observations of the existing UI, never a permission or callback substitute. */
internal data class LanPermissionUiSettlement(
    val originalRequestObserved: Boolean,
    val ownedWindow: Boolean,
    val visibleAnchor: Boolean,
    val stateStable: Boolean,
    val liveGrant: Boolean,
    val requestInFlight: Boolean,
    val missingEmpty: Boolean,
    val checkFailed: Boolean,
    val card: Card,
    val waitingVisible: Boolean,
    val grantVisible: Boolean,
    val missingVisible: Boolean,
    val availableVisible: Boolean,
    val cardExplanationVisible: Boolean,
    val refreshVisible: Boolean,
    val refreshButtonReady: Boolean
) {
    enum class Card { AVAILABLE, ABSENT, OTHER }

    fun settled(): Boolean {
        if (!originalRequestObserved || !ownedWindow || !visibleAnchor || !stateStable || !liveGrant ||
            requestInFlight || !missingEmpty || checkFailed || waitingVisible || grantVisible || missingVisible
        ) return false
        return when (card) {
            Card.AVAILABLE -> availableVisible && refreshVisible && refreshButtonReady
            // MainActivity intentionally removes this card after a subsequent successful refresh.
            Card.ABSENT -> !availableVisible && !cardExplanationVisible && !refreshVisible && !refreshButtonReady
            Card.OTHER -> false
        }
    }
}

/** A disabled Compose click owner remains clickable but may omit ACTION_CLICK. */
internal data class LanPermissionActionNode(
    val owned: Boolean,
    val visible: Boolean,
    val enabled: Boolean,
    val clickable: Boolean,
    val clickAction: Boolean,
    val otherActivation: Boolean
) {
    fun ready(): Boolean = owned && visible && enabled && clickable && clickAction
}

/** Resolve structural ownership before checking readiness; never climb past a disabled owner. */
internal fun nearestLanPermissionActionOwner(chain: List<LanPermissionActionNode>): Int? {
    require(chain.size <= 6)
    for ((index, node) in chain.withIndex()) {
        if (!node.owned) return null
        if (node.clickable || node.clickAction || node.otherActivation) return index
    }
    return null
}
