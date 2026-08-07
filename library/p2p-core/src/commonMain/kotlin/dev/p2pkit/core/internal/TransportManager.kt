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
 * LAN is the only shipped transport today, so this is trivial in practice;
 * the abstraction matters once additional transports (BLE / Wi-Fi Direct /
 * Multipeer / Relay) are added.
 */
internal class TransportManager(
    private val transports: List<DataTransport>
) {

    fun selectBestTransport(peer: InternalPeer): DataTransport {
        // Highest priority wins; ties broken deterministically by transport
        // kind ordinal (then registration order) so selection is stable and
        // reproducible rather than dependent on `maxByOrNull`'s first-max bias.
        return transports
            .filter { it.canConnect(peer) }
            .sortedWith(compareByDescending<DataTransport> { it.priority }.thenBy { it.type.ordinal })
            .firstOrNull()
            ?: throw P2pError.NoTransportAvailable(peer.publicPeer)
    }
}
