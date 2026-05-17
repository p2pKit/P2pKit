package dev.p2pkit.transport.lan

import dev.p2pkit.core.PeerId
import kotlinx.coroutines.sync.Mutex

/**
 * Bridge from discovery to data transport on iOS.
 *
 * `Network.framework`'s `NWBrowser` yields `NWBrowser.Result` values whose
 * underlying `NWEndpoint` is opaque — there's no public host/port to encode
 * into a [dev.p2pkit.core.transport.TransportHint] the way JmDNS/NsdManager
 * surface them. Instead, the discovery transport stashes the resolved
 * `NWEndpoint` (or its identifying tuple) here, keyed by [PeerId], so
 * `connect(peer)` on the data transport can open an `NWConnection` directly
 * to it.
 *
 * Populated in [IosLanDiscoveryTransport] on every `serviceResolved` event;
 * read in [IosLanDataTransport.connect]. Filled in by Tasks 19 and 20.
 */
internal class IosEndpointRegistry {
    private val lock = Mutex()
    private val entries: MutableMap<PeerId, Any> = mutableMapOf()

    @Suppress("unused")
    suspend fun put(peerId: PeerId, endpoint: Any) {
        TODO("Task 20 of v0.3.0-dev — populate from NWBrowser.Result")
    }

    @Suppress("unused")
    suspend fun get(peerId: PeerId): Any? {
        TODO("Task 20 of v0.3.0-dev — read by IosLanDataTransport.connect")
    }

    @Suppress("unused")
    suspend fun remove(peerId: PeerId) {
        TODO("Task 20 of v0.3.0-dev — clear on PeerEvent.Lost")
    }
}
