package dev.p2pkit.transport.lan

import dev.p2pkit.core.dsl.TransportsBuilder
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair

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
 * `:p2p-transport-lan` androidMain — the `Context` supplies the Wi-Fi
 * multicast lock and `ConnectivityManager` hooks that the in-process
 * JmDNS discovery needs (Android discovery has used JmDNS, not
 * `NsdManager`, since v0.5).
 *
 * The actual `ServerSocket(0)` bind happens inside the transport's
 * `start()` (called by [dev.p2pkit.core.P2pKit.start], or lazily by the
 * first `startAdvertising` / `connect`). Factory construction has no
 * blocking I/O, so a bind failure (port exhaustion, permission denied)
 * surfaces as [dev.p2pkit.core.P2pError.TransportStartFailed] at start
 * time instead of throwing from the kit's `create` call.
 */
public fun TransportsBuilder.lan() {
    register(JvmLanTransportFactory)
}

internal object JvmLanTransportFactory : TransportFactory {
    override fun build(context: TransportContext): TransportPair {
        val registration = LanServiceRegistration(
            appId = context.appId,
            localPeerId = context.localPeerId,
            deviceName = context.deviceName,
            platform = context.platform
        )
        return TransportPair(
            data = JvmLanDataTransport(registration),
            discovery = JvmLanDiscoveryTransport(registration)
        )
    }
}
