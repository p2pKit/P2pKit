package dev.p2pkit.transport.lan

import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.dsl.TransportsBuilder
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportDescriptor
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
 * Same public API as on JVM and Android. The selected whole-kit security
 * profile chooses the cross-platform namespace: `_p2pkit2._tcp` for
 * authenticated v2 or `_p2pkit._tcp` for explicit deprecated plaintext v1.
 * TXT records and protocol bytes remain identical across the iOS and
 * JVM/Android implementations of the selected profile.
 */
public fun TransportsBuilder.lan() {
    register(IosLanTransportFactory)
}

internal object IosLanTransportFactory : TransportFactory {
    override val descriptor: TransportDescriptor =
        TransportDescriptor.dataAndDiscovery(TransportKind.LAN)

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
