@file:OptIn(ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.core.PeerId
import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.update
import platform.Network.nw_endpoint_t

/**
 * Bridge from discovery to data transport on iOS.
 *
 * `NWBrowser` yields `NWBrowser.Result` values whose underlying
 * `nw_endpoint_t` is opaque — there's no public host/port to encode into a
 * [dev.p2pkit.core.transport.TransportHint] the way JmDNS does on JVM/Android.
 * Instead, the discovery transport stashes the endpoint here keyed by
 * [PeerId], and [IosLanDataTransport.connect] dials it directly via
 * `nw_connection_create(endpoint, parameters)`.
 *
 * Reads and writes are non-suspending so [IosLanDataTransport.canConnect]
 * — which the [dev.p2pkit.core.internal.TransportManager] calls synchronously
 * — can consult the registry without taking a lock.
 */
internal class IosEndpointRegistry {

    private val entries = MutableStateFlow<Map<PeerId, nw_endpoint_t>>(emptyMap())

    fun put(peerId: PeerId, endpoint: nw_endpoint_t) {
        entries.update { it + (peerId to endpoint) }
    }

    fun get(peerId: PeerId): nw_endpoint_t = entries.value[peerId]

    fun remove(peerId: PeerId) {
        entries.update { it - peerId }
    }

    fun clear() {
        entries.value = emptyMap()
    }
}
