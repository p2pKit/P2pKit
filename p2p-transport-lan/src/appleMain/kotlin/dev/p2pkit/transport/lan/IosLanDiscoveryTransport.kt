package dev.p2pkit.transport.lan

import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.DiscoveryTransport
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.TransportContext
import kotlinx.coroutines.flow.Flow

/**
 * iOS LAN [DiscoveryTransport].
 *
 * Implemented in Task 20 of v0.3.0-dev. Will use `NWBrowser` for browsing
 * `_p2pkit._tcp` services and `NWListener.service` (TXT-record-carrying) to
 * advertise. TXT round-trip helpers live in `IosBonjour.kt`. On every
 * `NWBrowser.Result` change, the resolved `NWEndpoint` is stashed in
 * [IosEndpointRegistry] keyed by the remote peer id so
 * [IosLanDataTransport.connect] can dial it without re-resolving.
 *
 * Stubbed in Task 18 so the iOS source set compiles.
 */
internal class IosLanDiscoveryTransport(
    @Suppress("unused") private val context: TransportContext,
    @Suppress("unused") private val endpointRegistry: IosEndpointRegistry,
    @Suppress("unused") private val dataTransport: IosLanDataTransport
) : DiscoveryTransport {

    override val type: TransportKind = TransportKind.LAN

    override val events: Flow<PeerEvent>
        get() = TODO("Task 20 of v0.3.0-dev — NWBrowser.browseResultsChangedHandler → PeerEvent")

    override suspend fun startAdvertising(localPeer: LocalPeerInfo): Unit =
        TODO("Task 20 of v0.3.0-dev — NWListener.service with NWTXTRecord")

    override suspend fun stopAdvertising(): Unit =
        TODO("Task 20 of v0.3.0-dev — cancel NWListener.service")

    override suspend fun startDiscovery(): Unit =
        TODO("Task 20 of v0.3.0-dev — start NWBrowser on _p2pkit._tcp")

    override suspend fun stopDiscovery(): Unit =
        TODO("Task 20 of v0.3.0-dev — cancel NWBrowser")
}
