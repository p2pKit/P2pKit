package dev.p2pkit.core.security

/**
 * JVM host-provided protected storage for P2pKit's opaque local-identity state.
 *
 * The implementation must provide confidentiality and integrity at rest. It
 * must be safe across every thread and process sharing its backing store. Core
 * deliberately supplies no passwordless/plain-file default and never calls
 * this interface from a security-engine extension point.
 *
 * Core stores both the identity record and a reset-transaction marker under
 * distinct namespace strings. Values are opaque: implementations must not
 * parse, normalize, truncate, or assume one fixed value length.
 */
public interface JvmSecureIdentityStore {
    /** Return a defensive copy of the durable value, or `null` only when absent. */
    public fun read(namespace: String): ByteArray?

    /**
     * Durably store [value] only if absent and return a defensive copy of the
     * durable winner. The absence check and commit must be cross-process atomic.
     * This method must not return before a subsequent [read] can observe the
     * same bytes. Copy [value] during the call; core clears its array as soon
     * as this method returns.
     */
    public fun putIfAbsent(namespace: String, value: ByteArray): ByteArray

    /**
     * Durably and idempotently delete [namespace]. Returns `true` if an entry
     * was removed and `false` when it was already absent.
     */
    public fun delete(namespace: String): Boolean
}
