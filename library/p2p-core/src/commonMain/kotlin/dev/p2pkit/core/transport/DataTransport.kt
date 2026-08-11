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
    /** Stable kind for this instance. The getter must be side-effect free. */
    public val type: TransportKind

    /**
     * Higher = preferred. Used for transport selection when multiple match.
     * The getter must be stable and side-effect free for this instance.
     */
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

    /**
     * Release resources acquired by [start] while keeping this transport
     * instance restartable.
     *
     * The operation is idempotent: stopping an inactive transport succeeds.
     * Concurrent lifecycle calls must serialize so `start()` cannot publish a
     * listener after `stop()` has returned. A later [start] begins a fresh
     * lifecycle generation. Accepted [RawConnection]s whose ownership already
     * moved to a session are not transport-startup resources and are closed by
     * that session instead.
     *
     * This is the rollback primitive used when one transport in a
     * multi-transport startup fails. It must not perform terminal disposal;
     * [close] is the permanent operation.
     */
    public suspend fun stop()

    /**
     * Return whether this instance can reach [peer] using its current hints.
     * This check must be fast and resource-inert. A thrown provider exception
     * is surfaced to the application as [dev.p2pkit.core.P2pError.ConnectionFailed]
     * rather than causing an untyped platform-specific failure or an implicit
     * fallback to a lower-priority transport.
     */
    public fun canConnect(peer: InternalPeer): Boolean

    /**
     * Open a raw connection to [peer]. Cancellation must propagate unchanged;
     * any other unexpected provider exception is wrapped by the kit as
     * [dev.p2pkit.core.P2pError.ConnectionFailed].
     */
    public suspend fun connect(peer: InternalPeer): RawConnection

    /**
     * Emits a new [RawConnection] for every accepted inbound connection.
     * Single-active-collector contract: the engine never collects this flow
     * concurrently. If collection terminates unexpectedly, the engine may
     * call this method again after a bounded backoff. Implementations must
     * therefore return a flow that supports sequential recovery (typically a
     * fresh wrapper over a live channel); it must not permanently consume or
     * cancel the transport's acceptance source merely because one collector
     * ended.
     */
    public fun incomingConnections(): Flow<RawConnection>

    /**
     * Permanently dispose this transport. Idempotent. After `close()` begins,
     * every later [start] must fail and no native callback may republish a
     * listener or accepted connection.
     */
    public suspend fun close()
}
