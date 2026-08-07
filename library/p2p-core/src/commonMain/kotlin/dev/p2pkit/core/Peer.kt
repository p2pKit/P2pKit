package dev.p2pkit.core

import dev.p2pkit.core.internal.immutableSetSnapshot

/**
 * A discovered peer device.
 *
 * `Peer` is intentionally minimal and stable: it does **not** carry transport
 * details such as host or port — those are internal. Last-seen times are also
 * tracked separately so heartbeats do not churn the peers `StateFlow`.
 *
 * @property id Stable identifier for this peer (see [PeerId]).
 * @property name Human-readable device name set by the remote app.
 * @property platform The remote device's platform, or [Platform.UNKNOWN] if it
 *   was not advertised or could not be parsed.
 * @property supportedTransports Transports the remote claims to support; used
 *   by the local [P2pKit] to pick a compatible transport when connecting.
 */
public class Peer(
    public val id: PeerId,
    public val name: String,
    public val platform: Platform,
    supportedTransports: Set<TransportKind>
) {
    /** Stable, unmodifiable snapshot of the remote transport claims. */
    public val supportedTransports: Set<TransportKind> = immutableSetSnapshot(supportedTransports)

    public operator fun component1(): PeerId = id
    public operator fun component2(): String = name
    public operator fun component3(): Platform = platform
    public operator fun component4(): Set<TransportKind> = supportedTransports

    public fun copy(
        id: PeerId = this.id,
        name: String = this.name,
        platform: Platform = this.platform,
        supportedTransports: Set<TransportKind> = this.supportedTransports
    ): Peer = Peer(id, name, platform, supportedTransports)

    override fun equals(other: Any?): Boolean =
        this === other ||
            other is Peer &&
            id == other.id &&
            name == other.name &&
            platform == other.platform &&
            supportedTransports == other.supportedTransports

    override fun hashCode(): Int {
        var result = id.hashCode()
        result = 31 * result + name.hashCode()
        result = 31 * result + platform.hashCode()
        result = 31 * result + supportedTransports.hashCode()
        return result
    }

    override fun toString(): String =
        "Peer(id=$id, name=$name, platform=$platform, supportedTransports=$supportedTransports)"
}

/** Platform a peer device is running on. */
public enum class Platform {
    ANDROID,
    JVM_DESKTOP,
    IOS,
    MACOS,
    WINDOWS,
    LINUX,
    UNKNOWN
}

/**
 * A kind of transport that can carry P2pKit traffic.
 *
 * Used both as a peer capability (which transports a peer advertises) and as a
 * transport identifier (which transport carried a connection). Single source of
 * truth across the public API.
 */
public enum class TransportKind {
    LAN,
    BLE,
    WIFI_DIRECT,
    MULTIPEER,
    RELAY
}
