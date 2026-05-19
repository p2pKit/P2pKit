package dev.p2pkit.transport.lan

import dev.p2pkit.core.dsl.TransportsBuilder
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair

/**
 * Register the LAN transport (Bonjour discovery + TCP data via `Network.framework`)
 * on iOS.
 *
 * Usage inside a [dev.p2pkit.core.P2pKit.create] block:
 *
 * ```kotlin
 * transports { lan() }
 * ```
 *
 * Same public API as on JVM and Android — wire-compatible with the JmDNS /
 * `NsdManager` implementations (`_p2pkit._tcp` service type, identical TXT
 * record keys). See `IosLanDataTransport` / `IosLanDiscoveryTransport` for the
 * implementations.
 */
public fun TransportsBuilder.lan() {
    register(IosLanTransportFactory)
}

internal object IosLanTransportFactory : TransportFactory {
    override fun build(context: TransportContext): TransportPair {
        val endpointRegistry = IosEndpointRegistry()
        val dataTransport = IosLanDataTransport(context, endpointRegistry)
        val discoveryTransport = IosLanDiscoveryTransport(context, endpointRegistry, dataTransport)
        return TransportPair(
            data = dataTransport,
            discovery = discoveryTransport
        )
    }
}
