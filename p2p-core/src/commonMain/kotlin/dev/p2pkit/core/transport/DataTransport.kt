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

    /**
     * Bring the transport up: bind sockets / create listeners / acquire
     * resources. Called by [dev.p2pkit.core.P2pKit.start] (or implicitly on
     * the first call to [dev.p2pkit.core.P2pKit.startAdvertising] /
     * [dev.p2pkit.core.P2pKit.connect] if the host app skips the explicit
     * `start()`).
     *
     * Default impl is a no-op for transports that don't bind a server —
     * outbound-only transports stay quiet here. The contract is **must be
     * idempotent**: calling `start()` a second time after success must
     * return `Result.success(Unit)`.
     *
     * Returns:
     * - `Result.success(Unit)` once the transport is fully usable.
     * - `Result.failure(throwable)` if the underlying OS rejected the bind
     *   (e.g., port exhaustion, missing entitlement, multicast disabled).
     *   The kit wraps it in [dev.p2pkit.core.P2pError.TransportStartFailed]
     *   for the caller; transports do not throw.
     */
    public suspend fun start(): Result<Unit> = Result.success(Unit)

    public fun canConnect(peer: InternalPeer): Boolean

    public suspend fun connect(peer: InternalPeer): RawConnection

    /**
     * Emits a new [RawConnection] for every accepted inbound connection.
     * Single-collector contract: the engine collects this exactly once per
     * transport. Shipped implementations are channel-backed, so an
     * additional collector would steal accepted connections rather than
     * observe them.
     */
    public fun incomingConnections(): Flow<RawConnection>

    public suspend fun close()
}
