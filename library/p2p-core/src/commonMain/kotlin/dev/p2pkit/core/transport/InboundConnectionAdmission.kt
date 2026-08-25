package dev.p2pkit.core.transport

/**
 * Optional cross-module lifecycle hook for an inbound connection that already
 * holds a transport admission slot.
 *
 * A transport may acquire a per-source slot before it buffers an accepted
 * connection, then implement this interface on the emitted [RawConnection].
 * The core calls [releasePreHandshakeAdmission] as soon as the handshake
 * succeeds, fails, or is refused by the global admission gate. Implementations
 * must make that operation non-throwing, thread-safe, and idempotent because a
 * concurrent connection close may release the same slot first.
 *
 * Public only because transport implementations live in separate modules;
 * application code does not need to implement or invoke this contract.
 */
public interface InboundConnectionAdmission {
    /** Stable, diagnostic-only source identifier; never an authentication identity. */
    public val admissionSource: String

    /** Release the transport-owned slot held only for the pre-handshake phase. */
    public fun releasePreHandshakeAdmission()
}
