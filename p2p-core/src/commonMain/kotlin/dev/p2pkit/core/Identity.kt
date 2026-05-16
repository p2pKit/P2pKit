package dev.p2pkit.core

import kotlin.jvm.JvmInline

/**
 * Identifier of the application that this P2pKit instance belongs to.
 *
 * Discovery is scoped by [AppId]: peers advertising a different value are
 * filtered out before they reach [P2pKit.peers]. Use the same [AppId] on every
 * device of the same product.
 */
@JvmInline
public value class AppId(public val value: String) {
    init {
        require(value.isNotBlank()) { "AppId must not be blank" }
    }
}

/**
 * Stable identifier of a peer device.
 *
 * On each device, the SDK generates and persists a UUID on first run; it
 * survives app restarts but may be lost on uninstall. Use [PeerId] to recognize
 * a known peer across sessions.
 */
@JvmInline
public value class PeerId(public val value: String) {
    init {
        require(value.isNotBlank()) { "PeerId must not be blank" }
    }
}

/**
 * Optional cryptographic identity of a peer after a security handshake.
 *
 * Under [SecurityMode.NoneForMvp] in v0.1, [publicKeyFingerprint] is always `null`.
 */
public data class PeerIdentity(
    val peerId: PeerId,
    val publicKeyFingerprint: String? = null
)
