package dev.p2pkit.sample.desktop

import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.sample.diagnostics.LocalPairingInfo

internal const val PINNED_CONNECT_USAGE: String = "usage: connect-pinned <peer-alias> <full-pairing-QR>"

internal class PinnedConnectRequest(val selector: String, val fingerprint: PeerFingerprint)

/** Require the complete AppId-bound QR; never accept discovery metadata as approval. */
internal fun parsePinnedConnect(kit: P2pKit, input: String): PinnedConnectRequest? {
    val parts = input.trim().split(Regex("\\s+"))
    if (parts.size != 2 || parts[0].isBlank()) return null
    val fingerprint = kit.parsePeerPairingQr(parts[1]) ?: return null
    return PinnedConnectRequest(parts[0], fingerprint)
}

internal suspend fun connectPinnedPeer(
    kit: P2pKit,
    peer: Peer,
    request: PinnedConnectRequest
): P2pSession = kit.connect(peer, request.fingerprint)

/** Only the operator's `info`/`pairing` command calls this; it is not a logger sink. */
internal fun printPairingInfo(kit: P2pKit, output: (String) -> Unit = ::println) {
    val info = LocalPairingInfo.from(kit)
    if (info == null) {
        output("pairing          unavailable (legacy plaintext has no authenticated identity)")
        return
    }
    output("Share only with the intended peer over a trusted channel; not in diagnostic exports.")
    output("fingerprint      ${info.fingerprint}")
    output("pairing QR       ${info.qr}")
    output("JVM sample identity changes after restart. Incoming peers still use the development policy.")
}
