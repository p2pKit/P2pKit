package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform

/**
 * Identity advertised over mDNS plus the bound TCP port, shared between each
 * platform's data and discovery transports (created once per kit by the
 * platform's [dev.p2pkit.core.transport.TransportFactory]).
 *
 * The port is mutable since the v0.3 transport-lifecycle refactor: the data
 * transport binds its server socket lazily in `start()`, then writes the
 * chosen port back into this struct before the discovery transport begins
 * advertising. A zero value means "not bound yet" — discovery transports
 * should not call this with [tcpPort] == 0.
 *
 * The platform `@Volatile` annotations differ between JVM and Kotlin/Native,
 * so we just rely on the SPI call ordering guaranteed by core's start path
 * (it holds a mutex and runs `DataTransport.start()` strictly before
 * `DiscoveryTransport.startAdvertising()`). No cross-thread reads of
 * [tcpPort] happen outside that ordering.
 */
internal class LanServiceRegistration(
    val appId: AppId,
    val localPeerId: PeerId,
    val deviceName: String,
    val platform: Platform,
    var tcpPort: Int = 0
)

/** Wire-level constants shared by the JVM and Android implementations. */
internal object LanConstants {
    /** JmDNS-style service type. Used by [JvmLanDiscoveryTransport]. */
    const val SERVICE_TYPE_JMDNS: String = "_p2pkit._tcp.local."

    /**
     * Bonjour service type for iOS `nw_advertise_descriptor` and
     * `nw_browse_descriptor`. No trailing dot — Apple's API expects the
     * canonical form. Wire-identical to the JmDNS string above.
     */
    const val SERVICE_TYPE_BONJOUR: String = "_p2pkit._tcp"

    // TXT record keys. Both platforms must use the same keys.
    const val TXT_PEER_ID: String = "pid"
    const val TXT_APP_ID: String = "app"
    const val TXT_DEVICE_NAME: String = "name"
    const val TXT_PLATFORM: String = "plat"
    const val TXT_CAPABILITIES: String = "caps"
    const val TXT_PROTOCOL_VERSION: String = "pv"

    /** Wire protocol version. Must match `ProtocolConstants.VERSION` in :p2p-core. */
    const val PROTOCOL_VERSION: Int = 1

    /**
     * Per-attempt TCP connect timeout used by the JVM and Android data
     * transports when dialing a discovered peer. v0.5 real-device traces
     * showed the kernel's default `Socket(host, port)` blocking ~17 s
     * before ECONNREFUSED on a stale port — that whole window is wasted
     * dead time during reconnect because the next attempt would have
     * picked up the fresh port from the JmDNS cache. 5 s comfortably
     * exceeds typical LAN RTT plus TCP SYN retries while still keeping
     * three full retries inside the sample's
     * `ReconnectPolicy.Enabled(maxAttempts=10, retryDelayMillis=1500)`
     * budget. iOS-side `NWConnection` already times out on a shorter
     * horizon via `Network.framework`, so no equivalent knob is needed
     * on the appleMain path.
     */
    const val TCP_CONNECT_TIMEOUT_MS: Int = 5_000
}
