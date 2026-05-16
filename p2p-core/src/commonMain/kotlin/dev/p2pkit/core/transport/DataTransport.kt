package dev.p2pkit.core.transport

import dev.p2pkit.core.TransportKind
import kotlinx.coroutines.flow.Flow

/**
 * A transport that can open and accept raw byte streams to peers.
 *
 * Each transport advertises a [type] (LAN, BLE, ...) and a [priority]. The
 * [dev.p2pkit.core.internal.TransportManager] picks the highest-priority
 * transport that reports [canConnect] for the target peer. Internal contract.
 */
public interface DataTransport {
    public val type: TransportKind

    /** Higher = preferred. Used for transport selection when multiple match. */
    public val priority: Int

    public fun canConnect(peer: InternalPeer): Boolean

    public suspend fun connect(peer: InternalPeer): RawConnection

    /** Emits a new [RawConnection] for every accepted inbound connection. */
    public fun incomingConnections(): Flow<RawConnection>

    public suspend fun close()
}
