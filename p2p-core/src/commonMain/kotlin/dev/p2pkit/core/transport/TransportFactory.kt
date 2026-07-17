package dev.p2pkit.core.transport

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.Platform

/** Immutable wire/discovery profile selected for the whole kit. */
public enum class TransportSecurityProfile {
    /** Authenticated Noise protocol v2 and the secure discovery namespace. */
    AuthenticatedV2,

    /** Explicit deprecated plaintext protocol v1 migration profile. */
    LegacyPlaintextV1
}

/**
 * Information P2pKit hands to a [TransportFactory] when constructing transports.
 *
 * Carries the local device identity so a transport can advertise itself.
 */
public data class TransportContext(
    val appId: AppId,
    val localPeerId: PeerId,
    val deviceName: String,
    val platform: Platform,
    val securityProfile: TransportSecurityProfile = TransportSecurityProfile.LegacyPlaintextV1,
    /** Full local fingerprint in secure mode; never an authorization decision. */
    val localFingerprint: PeerFingerprint? = null
)

/**
 * Builds a transport pair (data + optional discovery) for a single technology.
 *
 * Each transport module exposes an extension function on
 * [dev.p2pkit.core.dsl.TransportsBuilder] (e.g. `lan()`) that registers a
 * factory. P2pKit calls [build] once during instance construction.
 */
public interface TransportFactory {
    public fun build(context: TransportContext): TransportPair
}

/**
 * Output of a [TransportFactory]. A transport may provide a data path, a
 * discovery path, or both. Most transports provide both; relay-style
 * transports may provide only data.
 */
public data class TransportPair(
    val data: DataTransport,
    val discovery: DiscoveryTransport? = null
)
