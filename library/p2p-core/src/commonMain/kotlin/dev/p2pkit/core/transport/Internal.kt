package dev.p2pkit.core.transport

import dev.p2pkit.core.AppId
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.internal.immutableListSnapshot
import dev.p2pkit.core.internal.immutableMapSnapshot
import dev.p2pkit.core.internal.immutableSetSnapshot

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
public class InternalPeer(
    public val publicPeer: Peer,
    transportHints: List<TransportHint>,
    /** How this entry entered the registry. Defaults to [PeerOrigin.Discovered]. */
    public val origin: PeerOrigin = PeerOrigin.Discovered,
    /** Authentication information with explicit provenance. */
    public val authenticationHint: PeerAuthenticationHint? = null
) {
    /** Stable, unmodifiable snapshot of transport-specific reach information. */
    public val transportHints: List<TransportHint> = immutableListSnapshot(transportHints)

    public operator fun component1(): Peer = publicPeer
    public operator fun component2(): List<TransportHint> = transportHints
    public operator fun component3(): PeerOrigin = origin
    public operator fun component4(): PeerAuthenticationHint? = authenticationHint

    public fun copy(
        publicPeer: Peer = this.publicPeer,
        transportHints: List<TransportHint> = this.transportHints,
        origin: PeerOrigin = this.origin,
        authenticationHint: PeerAuthenticationHint? = this.authenticationHint
    ): InternalPeer = InternalPeer(publicPeer, transportHints, origin, authenticationHint)

    override fun equals(other: Any?): Boolean =
        this === other ||
            other is InternalPeer &&
            publicPeer == other.publicPeer &&
            transportHints == other.transportHints &&
            origin == other.origin &&
            authenticationHint == other.authenticationHint

    override fun hashCode(): Int {
        var result = publicPeer.hashCode()
        result = 31 * result + transportHints.hashCode()
        result = 31 * result + origin.hashCode()
        result = 31 * result + (authenticationHint?.hashCode() ?: 0)
        return result
    }

    override fun toString(): String =
        "InternalPeer(publicPeer=$publicPeer, transportHints=$transportHints, " +
            "origin=$origin, authenticationHint=$authenticationHint)"
}

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
public class TransportHint(
    public val type: TransportKind,
    public val host: String? = null,
    public val port: Int? = null,
    metadata: Map<String, String> = emptyMap()
) {
    /** Stable, unmodifiable snapshot of transport-defined attributes. */
    public val metadata: Map<String, String> = immutableMapSnapshot(metadata)

    public operator fun component1(): TransportKind = type
    public operator fun component2(): String? = host
    public operator fun component3(): Int? = port
    public operator fun component4(): Map<String, String> = metadata

    public fun copy(
        type: TransportKind = this.type,
        host: String? = this.host,
        port: Int? = this.port,
        metadata: Map<String, String> = this.metadata
    ): TransportHint = TransportHint(type, host, port, metadata)

    override fun equals(other: Any?): Boolean =
        this === other ||
            other is TransportHint &&
            type == other.type &&
            host == other.host &&
            port == other.port &&
            metadata == other.metadata

    override fun hashCode(): Int {
        var result = type.hashCode()
        result = 31 * result + (host?.hashCode() ?: 0)
        result = 31 * result + (port ?: 0)
        result = 31 * result + metadata.hashCode()
        return result
    }

    override fun toString(): String =
        "TransportHint(type=$type, host=$host, port=$port, metadata=$metadata)"
}

/**
 * Local device's advertising payload, passed to every [DiscoveryTransport]
 * when advertising starts.
 */
public class LocalPeerInfo(
    public val peerId: PeerId,
    public val deviceName: String,
    public val platform: Platform,
    public val appId: AppId,
    supportedTransports: Set<TransportKind>,
    public val securityProfile: TransportSecurityProfile = TransportSecurityProfile.LegacyPlaintextV1,
    public val fingerprint: PeerFingerprint? = null
) {
    /** Stable, unmodifiable snapshot of locally advertised transport support. */
    public val supportedTransports: Set<TransportKind> = immutableSetSnapshot(supportedTransports)

    public operator fun component1(): PeerId = peerId
    public operator fun component2(): String = deviceName
    public operator fun component3(): Platform = platform
    public operator fun component4(): AppId = appId
    public operator fun component5(): Set<TransportKind> = supportedTransports
    public operator fun component6(): TransportSecurityProfile = securityProfile
    public operator fun component7(): PeerFingerprint? = fingerprint

    public fun copy(
        peerId: PeerId = this.peerId,
        deviceName: String = this.deviceName,
        platform: Platform = this.platform,
        appId: AppId = this.appId,
        supportedTransports: Set<TransportKind> = this.supportedTransports,
        securityProfile: TransportSecurityProfile = this.securityProfile,
        fingerprint: PeerFingerprint? = this.fingerprint
    ): LocalPeerInfo = LocalPeerInfo(
        peerId,
        deviceName,
        platform,
        appId,
        supportedTransports,
        securityProfile,
        fingerprint
    )

    override fun equals(other: Any?): Boolean =
        this === other ||
            other is LocalPeerInfo &&
            peerId == other.peerId &&
            deviceName == other.deviceName &&
            platform == other.platform &&
            appId == other.appId &&
            supportedTransports == other.supportedTransports &&
            securityProfile == other.securityProfile &&
            fingerprint == other.fingerprint

    override fun hashCode(): Int {
        var result = peerId.hashCode()
        result = 31 * result + deviceName.hashCode()
        result = 31 * result + platform.hashCode()
        result = 31 * result + appId.hashCode()
        result = 31 * result + supportedTransports.hashCode()
        result = 31 * result + securityProfile.hashCode()
        result = 31 * result + (fingerprint?.hashCode() ?: 0)
        return result
    }

    override fun toString(): String =
        "LocalPeerInfo(peerId=$peerId, deviceName=$deviceName, platform=$platform, appId=$appId, " +
            "supportedTransports=$supportedTransports, securityProfile=$securityProfile, " +
            "fingerprint=$fingerprint)"
}

/** Discovery events emitted by a [DiscoveryTransport]; aggregated by `PeerRegistry`. */
public sealed class PeerEvent {
    public data class Found(val peer: InternalPeer) : PeerEvent()
    public data class Updated(val peer: InternalPeer) : PeerEvent()
    public data class Lost(val peerId: PeerId) : PeerEvent()
}
