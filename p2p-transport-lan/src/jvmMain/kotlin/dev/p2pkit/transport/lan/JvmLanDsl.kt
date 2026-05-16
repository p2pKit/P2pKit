package dev.p2pkit.transport.lan

import dev.p2pkit.core.dsl.TransportsBuilder
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import java.net.ServerSocket

/**
 * Register the LAN transport (JmDNS discovery + TCP data) on JVM desktop.
 *
 * Usage inside a [dev.p2pkit.core.P2pKit.create] block:
 *
 * ```kotlin
 * transports { lan() }
 * ```
 *
 * For Android, use the `lan(applicationContext)` overload from
 * `:p2p-transport-lan` androidMain — `NsdManager` needs a `Context`.
 */
public fun TransportsBuilder.lan() {
    register(JvmLanTransportFactory)
}

internal object JvmLanTransportFactory : TransportFactory {
    override fun build(context: TransportContext): TransportPair {
        // Bind the TCP server first so we know which port to advertise over mDNS.
        val serverSocket = ServerSocket(0)
        val tcpPort = serverSocket.localPort

        val registration = LanServiceRegistration(
            appId = context.appId,
            localPeerId = context.localPeerId,
            deviceName = context.deviceName,
            platform = context.platform,
            tcpPort = tcpPort
        )

        return TransportPair(
            data = JvmLanDataTransport(registration, serverSocket),
            discovery = JvmLanDiscoveryTransport(registration)
        )
    }
}
