package dev.p2pkit.core.transport

import dev.p2pkit.core.TransportKind
import kotlinx.coroutines.flow.Flow

/**
 * A transport that can discover and advertise peers on its medium.
 *
 * Discovery and data transport are separate concerns: a transport may
 * implement either, both, or neither. Internal contract — apps only see
 * the aggregated [dev.p2pkit.core.P2pKit.peers] flow.
 */
public interface DiscoveryTransport {
    public val type: TransportKind

    public val events: Flow<PeerEvent>

    public suspend fun startAdvertising(localPeer: LocalPeerInfo)
    public suspend fun stopAdvertising()
    public suspend fun startDiscovery()
    public suspend fun stopDiscovery()
}
