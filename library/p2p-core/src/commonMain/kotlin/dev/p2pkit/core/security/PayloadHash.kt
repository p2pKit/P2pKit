package dev.p2pkit.core.security

import dev.p2pkit.core.internal.security.sha256

/**
 * Allocation-bounded SHA-256 over public protocol payloads. Reuses core's common implementation;
 * this unkeyed digest is NOT authentication, encryption, or application idempotency storage.
 */
public fun payloadSha256(bytes: ByteArray): ByteArray = sha256(bytes).bytes
