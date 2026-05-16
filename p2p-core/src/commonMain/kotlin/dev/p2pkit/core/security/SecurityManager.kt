package dev.p2pkit.core.security

import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerIdentity
import dev.p2pkit.core.transport.RawConnection

/**
 * Performs the handshake that turns a [RawConnection] into a [SecureConnection].
 *
 * In v0.1 the only implementation is [NoOpSecurityManager], which returns a
 * passthrough wrapper. The interface is the extension point for future
 * encryption modes (pairing code, QR code) without changing the public API.
 */
public interface SecurityManager {
    public suspend fun performHandshake(connection: RawConnection, peer: Peer): SecureConnection
}

/**
 * A [RawConnection] that has completed a security handshake.
 *
 * Public because [SecurityManager] is public and returns it. Application code
 * typically does not need to inspect this; the session machinery reads
 * [peerIdentity] internally.
 */
public interface SecureConnection : RawConnection {
    public val peerIdentity: PeerIdentity
}

/**
 * Default v0.1 security manager. Returns a passthrough wrapper around the
 * incoming raw connection with no encryption and a null public-key fingerprint.
 */
public class NoOpSecurityManager : SecurityManager {
    override suspend fun performHandshake(connection: RawConnection, peer: Peer): SecureConnection =
        PassthroughSecureConnection(connection, PeerIdentity(peer.id, publicKeyFingerprint = null))
}

internal class PassthroughSecureConnection(
    delegate: RawConnection,
    override val peerIdentity: PeerIdentity
) : SecureConnection, RawConnection by delegate
