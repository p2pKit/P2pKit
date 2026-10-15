package dev.p2pkit.rpc

import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint

/** Unauthenticated discovery claim. Selecting a name or seeing this object does not establish trust. */
public class RpcDiscoveredHost internal constructor(
    public val peer: Peer,
    public val fingerprint: PeerFingerprint,
) {
    override fun toString(): String = "RpcDiscoveredHost(untrusted discovery, redacted)"
}
