package dev.p2pkit.core.internal

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.InternalPeer

/**
 * Picks the best registered [DataTransport] for a peer.
 *
 * Selection rule: filter to transports whose [DataTransport.canConnect] returns
 * true for the peer, then pick the one with the highest [DataTransport.priority].
 * Throws [P2pError.NoTransportAvailable] if none match.
 *
 * v0.1 only has LAN, so this is trivial in practice; the abstraction matters
 * for v0.2+ when BLE / Wi-Fi Direct / Multipeer / Relay are added.
 */
internal class TransportManager(
    private val transports: List<DataTransport>
) {

    fun selectBestTransport(peer: InternalPeer): DataTransport {
        return transports
            .filter { it.canConnect(peer) }
            .maxByOrNull { it.priority }
            ?: throw P2pError.NoTransportAvailable(peer.publicPeer)
    }
}
