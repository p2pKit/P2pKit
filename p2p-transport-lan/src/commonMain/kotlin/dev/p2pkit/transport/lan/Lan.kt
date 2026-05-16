package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform

/**
 * Identity advertised over mDNS and used by the data transport to label
 * accepted sockets. Created by each platform's factory when the TCP server
 * binds to its ephemeral port.
 */
internal data class LanServiceRegistration(
    val appId: AppId,
    val localPeerId: PeerId,
    val deviceName: String,
    val platform: Platform,
    val tcpPort: Int
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
