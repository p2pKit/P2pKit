package dev.p2pkit.core

/**
 * A discovered peer device.
 *
 * `Peer` is intentionally minimal and stable: it does **not** carry transport
 * details such as host or port — those are internal. Last-seen times are also
 * tracked separately so heartbeats do not churn the peers [StateFlow].
 *
 * @property id Stable identifier for this peer (see [PeerId]).
 * @property name Human-readable device name set by the remote app.
 * @property platform The remote device's platform, or [Platform.UNKNOWN] if it
 *   was not advertised or could not be parsed.
 * @property supportedTransports Transports the remote claims to support; used
 *   by the local [P2pKit] to pick a compatible transport when connecting.
 */
public data class Peer(
    val id: PeerId,
    val name: String,
    val platform: Platform,
    val supportedTransports: Set<TransportKind>
)

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
