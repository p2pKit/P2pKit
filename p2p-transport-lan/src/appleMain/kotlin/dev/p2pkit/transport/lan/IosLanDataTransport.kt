package dev.p2pkit.transport.lan

import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.HasLocalTcpEndpoint
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import kotlinx.coroutines.flow.Flow

/**
 * iOS LAN [DataTransport].
 *
 * Implemented in Task 19 of v0.3.0-dev. Will hold an `NWListener` for inbound
 * connections (port chosen by the OS, surfaced via [tcpPort]) and build an
 * `NWConnection` per outbound [connect] using the endpoint resolved by
 * [IosLanDiscoveryTransport] and stashed in [IosEndpointRegistry].
 *
 * Stubbed in Task 18 so the iOS source set compiles; every method below
 * throws `NotImplementedError` until Task 19 lands.
 */
internal class IosLanDataTransport(
    @Suppress("unused") private val context: TransportContext,
    @Suppress("unused") private val endpointRegistry: IosEndpointRegistry
) : DataTransport, HasLocalTcpEndpoint {

    override val type: TransportKind = TransportKind.LAN

    /** LAN is the only v0.3 iOS transport; priority parity with JVM/Android. */
    override val priority: Int = 100

    override val tcpPort: Int
        get() = TODO("Task 19 of v0.3.0-dev — bind NWListener and expose its port")

    override fun canConnect(peer: InternalPeer): Boolean =
        TODO("Task 19 of v0.3.0-dev — true if endpointRegistry has an entry for peer")

    override suspend fun connect(peer: InternalPeer): RawConnection =
        TODO("Task 19 of v0.3.0-dev — NWConnection from endpoint registry → IosRawConnection")

    override fun incomingConnections(): Flow<RawConnection> =
        TODO("Task 19 of v0.3.0-dev — NWListener.newConnectionHandler → IosRawConnection flow")

    override suspend fun close(): Unit =
        TODO("Task 19 of v0.3.0-dev — cancel listener, close registry")
}
