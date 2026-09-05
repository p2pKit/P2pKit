package dev.p2pkit.sample.desktop

import dev.p2pkit.sample.diagnostics.SampleConsole
import dev.p2pkit.sample.diagnostics.SessionTransferKey

/** Opaque display selector; retain all matches rather than assuming hashes cannot collide. */
internal val SessionTransferKey.consoleSelector: String get() = SampleConsole.identifier(stableId)

/** Raw ID prefixes are usable only when unambiguous across all SDK sessions. */
internal fun matchingOfferKeys(
    keys: Collection<SessionTransferKey>,
    selector: String
): List<SessionTransferKey> = keys.filter {
    it.consoleSelector.startsWith(selector) || it.stableId == selector || it.transferId.startsWith(selector)
}.sortedBy { it.stableId }
