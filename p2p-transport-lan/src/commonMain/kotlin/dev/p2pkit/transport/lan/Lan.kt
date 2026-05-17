package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform

/**
 * Identity advertised over mDNS and used by the data transport to label
 * accepted sockets. Created by each platform's factory when the TCP server
 * binds to its ephemeral port.
 */
/**
 * Identity advertised over mDNS plus the bound TCP port.
 *
 * The port is mutable since the v0.3 transport-lifecycle refactor: the data
 * transport binds its server socket lazily in `start()`, then writes the
 * chosen port back into this struct before the discovery transport begins
 * advertising. A zero value means "not bound yet" — discovery transports
 * should not call this with [tcpPort] == 0.
 *
 * The platform `@Volatile` annotations differ between JVM and Kotlin/Native,
 * so we just rely on the call-ordering guarantee from [P2pKitImpl.ensureStarted]
 * (which acquires a [Mutex] and runs `data.start()` strictly before
 * `discovery.startAdvertising()`). No cross-thread reads of [tcpPort]
 * happen outside that ordering.
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
     * Android `NsdManager`-style service type. Same wire protocol as
     * [SERVICE_TYPE_JMDNS]; the string format just differs.
     */
    const val SERVICE_TYPE_NSD: String = "_p2pkit._tcp."

    /**
     * Bonjour service type for iOS `nw_advertise_descriptor` and
     * `nw_browse_descriptor`. No trailing dot — Apple's API expects the
     * canonical form. Wire-identical to the JMDNS/NSD strings above.
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
}
