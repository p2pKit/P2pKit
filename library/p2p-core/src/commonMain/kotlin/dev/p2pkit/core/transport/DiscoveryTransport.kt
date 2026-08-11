package dev.p2pkit.core.transport

import dev.p2pkit.core.TransportKind
import kotlinx.coroutines.flow.Flow

/**
 * A transport that can discover and advertise peers on its medium.
 *
 * Discovery and data transport are separate concerns: a transport may
 * implement either, both, or neither. Internal contract — apps only see
 * the aggregated [dev.p2pkit.core.P2pKit.peers] flow. Events cross an
 * untrusted SPI boundary: the core validates and bounds retained fields,
 * treats every advertised fingerprint as an untrusted discovery claim, and
 * does not honor event-supplied manual/application-trust provenance.
 */
public interface DiscoveryTransport {
    public val type: TransportKind

    public val events: Flow<PeerEvent>

    public suspend fun startAdvertising(localPeer: LocalPeerInfo)
    public suspend fun stopAdvertising()
    public suspend fun startDiscovery()
    public suspend fun stopDiscovery()

    /**
     * V0.4-DISCOVERY-REFRESH: ask the transport to send a fresh round of
     * active discovery queries. Implementations should stop + restart their
     * underlying browser / `discoverServices` under their existing lock so a
     * fresh mDNS (or equivalent) query goes out on the wire.
     *
     * Called by [dev.p2pkit.core.internal.SessionManager] when an outgoing
     * session enters `Reconnecting`, to close the gap where the remote peer
     * has changed network state (rebound to a new port) but the local NSD
     * cache has not yet seen the re-announcement. A `refresh()` forces a
     * fresh active query → the remote responder answers with its current
     * port → `PeerRegistry` updates → next reconnect attempt dials the
     * fresh endpoint.
     *
     * No-op if discovery isn't currently running.
     *
     * Default implementation is a no-op so transports that don't have a
     * fresh-query primitive (e.g., a synthetic test transport) don't have
     * to implement it.
     */
    public suspend fun refresh() {}
}
