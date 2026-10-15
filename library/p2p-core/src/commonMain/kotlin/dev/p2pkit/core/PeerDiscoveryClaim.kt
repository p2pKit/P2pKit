package dev.p2pkit.core

/**
 * Advisory discovery snapshot, NOT authenticated identity or durable trust. A peer name and fingerprint
 * can be spoofed on the LAN. Only a pinned authenticated handshake proves possession of that key;
 * identifying its real-world owner additionally requires independent comparison or informed first-use trust.
 * No manual-registration pins are promoted into discovery claims. Re-read before selecting or reconnecting.
 */
public class PeerDiscoveryClaim internal constructor(
    public val peer: Peer,
    public val fingerprint: PeerFingerprint,
    public val lastSeenMillis: Long,
) {
    override fun toString(): String = "PeerDiscoveryClaim(untrusted, redacted)"
}
