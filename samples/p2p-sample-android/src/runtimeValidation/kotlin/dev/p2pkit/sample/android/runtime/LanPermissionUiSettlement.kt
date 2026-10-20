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
