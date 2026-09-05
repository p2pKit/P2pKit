package dev.p2pkit.sample.desktop

import dev.p2pkit.sample.diagnostics.SessionTransferKey

/** Raw ID prefixes are usable only when unambiguous across all SDK sessions. */
internal fun matchingOfferKeys(
    keys: Collection<SessionTransferKey>,
    selector: String
): List<SessionTransferKey> = keys.filter {
    it.stableId == selector || it.transferId.startsWith(selector)
}.sortedBy { it.stableId }
