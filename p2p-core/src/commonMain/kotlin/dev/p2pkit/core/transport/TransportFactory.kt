package dev.p2pkit.core.transport

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform

/**
 * Information P2pKit hands to a [TransportFactory] when constructing transports.
 *
 * Carries the local device identity so a transport can advertise itself.
 */
public data class TransportContext(
    val appId: AppId,
    val localPeerId: PeerId,
    val deviceName: String,
    val platform: Platform
)

/**
 * Builds a transport pair (data + optional discovery) for a single technology.
 *
 * Each transport module exposes an extension function on
 * [dev.p2pkit.core.dsl.TransportsBuilder] (e.g. `lan()`) that registers a
 * factory. P2pKit calls [build] once during instance construction.
 */
public interface TransportFactory {
    public fun build(context: TransportContext): TransportPair
}

/**
 * Output of a [TransportFactory]. A transport may provide a data path, a
 * discovery path, or both. Most transports provide both; relay-style
 * transports may provide only data.
 */
public data class TransportPair(
    val data: DataTransport,
    val discovery: DiscoveryTransport? = null
)
