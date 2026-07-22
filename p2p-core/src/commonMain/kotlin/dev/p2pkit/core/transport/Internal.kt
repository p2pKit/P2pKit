package dev.p2pkit.core.transport

import dev.p2pkit.core.AppId
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind

/**
 * Provenance of an [InternalPeer] — how the kit learned about this peer.
 *
 * Public for the same reason as [InternalPeer]. Behavioral decisions that
 * depend on provenance (e.g. the HELLO identity-mismatch exemption for
 * manual-IP peers in `SessionManager`) key off this field — never off the
 * shape of the peer-id string, which a remote could mimic.
 */
public enum class PeerOrigin {
    /** Learned from a [DiscoveryTransport] announcement (mDNS etc.). */
    Discovered,

    /**
     * Minted locally by `ManualPeerRegistrar.registerManualPeer` from a
     * user-supplied host:port; carries a synthetic placeholder [PeerId].
     */
    Manual
}

/**
 * Internal view of a peer that includes transport-specific reach information.
 *
 * Public only because [DataTransport] and [DiscoveryTransport] are implemented
 * in separate Gradle modules. Application code should not use this type;
 * use [Peer] instead.
 */
public data class InternalPeer(
    val publicPeer: Peer,
    val transportHints: List<TransportHint>,
    /** How this entry entered the registry. Defaults to [PeerOrigin.Discovered]. */
    val origin: PeerOrigin = PeerOrigin.Discovered,
    /** Authentication information with explicit provenance. */
    val authenticationHint: PeerAuthenticationHint? = null
)

/**
 * Lifetime contract between a [DiscoveryTransport] and the core peer registry.
 *
 * Most transports emit periodic observations and use [CoreStaleTimeout]. A
 * transport backed by a resolver/browser that already enforces protocol TTLs
 * uses [TransportManaged]: the contribution remains until that exact transport
 * emits [PeerEvent.Lost] or stops. This avoids turning a local resolver-cache
 * read into false evidence that a remote peer is still alive.
 */
public enum class DiscoveryLifetime {
    CoreStaleTimeout,
    TransportManaged
}

private const val DISCOVERY_LIFETIME_METADATA_KEY = "dev.p2pkit.discovery-lifetime"
private const val TRANSPORT_MANAGED_LIFETIME_VALUE = "transport-managed"

/** Attach a transport-owned expiry contract without changing the SPI data-class ABI. */
public fun TransportHint.withDiscoveryLifetime(lifetime: DiscoveryLifetime): TransportHint =
    when (lifetime) {
        DiscoveryLifetime.CoreStaleTimeout -> copy(
            metadata = metadata - DISCOVERY_LIFETIME_METADATA_KEY
        )
        DiscoveryLifetime.TransportManaged -> copy(
            metadata = metadata +
                (DISCOVERY_LIFETIME_METADATA_KEY to TRANSPORT_MANAGED_LIFETIME_VALUE)
        )
    }

/** Resolve the lifetime attached to this transport contribution. */
public fun InternalPeer.discoveryLifetime(): DiscoveryLifetime =
    if (transportHints.any {
            it.metadata[DISCOVERY_LIFETIME_METADATA_KEY] == TRANSPORT_MANAGED_LIFETIME_VALUE
        }
    ) {
        DiscoveryLifetime.TransportManaged
    } else {
        DiscoveryLifetime.CoreStaleTimeout
    }

/**
 * A fingerprint associated with a routing candidate. Discovery claims remain
 * untrusted; only an application/manual pin may authorize a key.
 */
public sealed interface PeerAuthenticationHint {
    public val fingerprint: PeerFingerprint

    public data class UntrustedDiscoveryClaim(
        override val fingerprint: PeerFingerprint
    ) : PeerAuthenticationHint

    public data class TrustedApplicationPin(
        override val fingerprint: PeerFingerprint
    ) : PeerAuthenticationHint
}

/**
 * Reach information for a single transport.
 *
 * Public for the same reason as [InternalPeer]. Application code should not
 * depend on host or port — those are transport implementation details.
 */
public data class TransportHint(
    val type: TransportKind,
    val host: String? = null,
    val port: Int? = null,
    val metadata: Map<String, String> = emptyMap()
)

/**
 * Local device's advertising payload, passed to every [DiscoveryTransport]
 * when advertising starts.
 */
public data class LocalPeerInfo(
    val peerId: PeerId,
    val deviceName: String,
    val platform: Platform,
    val appId: AppId,
    val supportedTransports: Set<TransportKind>,
    val securityProfile: TransportSecurityProfile = TransportSecurityProfile.LegacyPlaintextV1,
    val fingerprint: PeerFingerprint? = null
)

/** Discovery events emitted by a [DiscoveryTransport]; aggregated by `PeerRegistry`. */
public sealed class PeerEvent {
    public data class Found(val peer: InternalPeer) : PeerEvent()
    public data class Updated(val peer: InternalPeer) : PeerEvent()
    public data class Lost(val peerId: PeerId) : PeerEvent()
}
