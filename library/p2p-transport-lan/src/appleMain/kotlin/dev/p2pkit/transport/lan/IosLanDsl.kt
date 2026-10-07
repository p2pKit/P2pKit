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

/**
 * Explicit organization LAN. Secure peers can advertise policy-checked numeric TXT reachability hints.
 * Opaque-only Bonjour endpoints are never dialed under this policy; older peers need a numeric manual endpoint.
 */
public fun TransportsBuilder.lan(policy: OrganizationLan, role: LanRole) {
    register(IosOrganizationLanFactory(policy, role))
}

private class IosOrganizationLanFactory(
    private val policy: OrganizationLan,
    private val role: LanRole,
) : TransportFactory {
    override val descriptor: TransportDescriptor = TransportDescriptor.dataAndDiscovery(TransportKind.LAN)

    override fun build(context: TransportContext): TransportPair {
        val registry = IosEndpointRegistry()
        val data = IosLanDataTransport(context, registry, policy = policy, role = role)
        return TransportPair(data, IosLanDiscoveryTransport(context, registry, data, policy, role))
    }
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
