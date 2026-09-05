package dev.p2pkit.sample.diagnostics

import dev.p2pkit.core.P2pKit

/** Public identity for an explicit pairing UI, never an automatic log or diagnostic record. */
class LocalPairingInfo private constructor(
    val fingerprint: String,
    val qr: String
) {
    // Do not accidentally disclose the full identity through interpolation in a diagnostic line.
    override fun toString(): String = "LocalPairingInfo(<display only>)"

    companion object {
        fun from(kit: P2pKit): LocalPairingInfo? {
            val fingerprint = kit.localFingerprint ?: return null
            val qr = kit.localPairingQr ?: return null
            check(kit.parsePeerPairingQr(qr) == fingerprint) { "Local pairing identity is inconsistent" }
            return LocalPairingInfo(fingerprint.value, qr)
        }
    }
}
