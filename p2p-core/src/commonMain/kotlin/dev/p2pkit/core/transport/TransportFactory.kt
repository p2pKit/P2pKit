package dev.p2pkit.core.transport

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.internal.immutableSetSnapshot

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
 * factory. P2pKit snapshots [descriptor] during DSL registration and calls
 * [build] once during instance construction. `build` and returned transport
 * constructors must remain resource-inert; listeners, sockets, native handles,
 * and callbacks are acquired only by the transport start methods. This lets
 * descriptor/pair contract violations fail without leaking resources.
 */
public interface TransportFactory {
    /** Static kind/capabilities available before [build] allocates resources. */
    public val descriptor: TransportDescriptor

    public fun build(context: TransportContext): TransportPair
}

/** A static operation a transport provider can implement. */
public enum class TransportCapability {
    DATA,
    DISCOVERY
}

/**
 * Immutable pre-build declaration used for configuration validation and
 * capability queries. Dynamic permission/radio/network failures belong to
 * feature state or transport startup, not this descriptor.
 */
public class TransportDescriptor(
    public val kind: TransportKind,
    capabilities: Set<TransportCapability>
) {
    /** Non-empty, stable snapshot of declared provider capabilities. */
    public val capabilities: Set<TransportCapability> = immutableSetSnapshot(capabilities)

    init {
        require(this.capabilities.isNotEmpty()) {
            "TransportDescriptor.capabilities must contain DATA, DISCOVERY, or both"
        }
    }

    public operator fun component1(): TransportKind = kind
    public operator fun component2(): Set<TransportCapability> = capabilities

    public fun copy(
        kind: TransportKind = this.kind,
        capabilities: Set<TransportCapability> = this.capabilities
    ): TransportDescriptor = TransportDescriptor(kind, capabilities)

    override fun equals(other: Any?): Boolean =
        this === other ||
            other is TransportDescriptor &&
            kind == other.kind &&
            capabilities == other.capabilities

    override fun hashCode(): Int = 31 * kind.hashCode() + capabilities.hashCode()

    override fun toString(): String =
        "TransportDescriptor(kind=$kind, capabilities=$capabilities)"

    public companion object {
        public fun dataOnly(kind: TransportKind): TransportDescriptor =
            TransportDescriptor(kind, setOf(TransportCapability.DATA))

        public fun discoveryOnly(kind: TransportKind): TransportDescriptor =
            TransportDescriptor(kind, setOf(TransportCapability.DISCOVERY))

        public fun dataAndDiscovery(kind: TransportKind): TransportDescriptor =
            TransportDescriptor(
                kind,
                setOf(TransportCapability.DATA, TransportCapability.DISCOVERY)
            )
    }
}

/**
 * Output of a [TransportFactory]. A transport may provide a data path, a
 * discovery path, or both. Most transports provide both; relay-style
 * transports may provide only data.
 */
public data class TransportPair(
    val data: DataTransport? = null,
    val discovery: DiscoveryTransport? = null
) {
    init {
        require(data != null || discovery != null) {
            "TransportPair must provide a data path, a discovery path, or both"
        }
    }
}

/** Descriptor snapshotted by the DSL before any provider resources exist. */
internal data class RegisteredTransportFactory(
    val factory: TransportFactory,
    val descriptor: TransportDescriptor
)
