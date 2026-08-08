package dev.p2pkit.core.security

import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerIdentity
import dev.p2pkit.core.transport.RawConnection

/**
 * Performs the handshake that turns a [RawConnection] into a [SecureConnection].
 *
 * Deprecated pre-v2 extension point. It cannot safely own the sole raw reader
 * because its contract requires an unauthenticated [Peer] up front. Built-in
 * secure v2 is established internally before protocol parsing and never calls
 * this interface.
 */
@Deprecated("Built-in authenticated v2 security is selected through SecurityMode")
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
 * Deprecated plaintext passthrough retained only for source migration of the
 * old extension point. It is not the kit default and is never selected by the
 * authenticated-v2 engine.
 */
@Deprecated("Plaintext passthrough is available only through SecurityMode.NoneForMvp")
@Suppress("DEPRECATION")
public class NoOpSecurityManager : SecurityManager {
    override suspend fun performHandshake(connection: RawConnection, peer: Peer): SecureConnection =
        PassthroughSecureConnection(connection, PeerIdentity(peer.id, fingerprint = null))
}

internal class PassthroughSecureConnection(
    delegate: RawConnection,
    override val peerIdentity: PeerIdentity
) : SecureConnection, RawConnection by delegate
