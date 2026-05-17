@file:OptIn(ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.HasLocalTcpEndpoint
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import kotlin.concurrent.Volatile
import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.consumeAsFlow
import kotlinx.coroutines.flow.first
import platform.Network.NW_PARAMETERS_DEFAULT_CONFIGURATION
import platform.Network.NW_PARAMETERS_DISABLE_PROTOCOL
import platform.Network.nw_connection_create
import platform.Network.nw_listener_cancel
import platform.Network.nw_listener_create
import platform.Network.nw_listener_get_port
import platform.Network.nw_listener_set_new_connection_handler
import platform.Network.nw_listener_set_queue
import platform.Network.nw_listener_set_state_changed_handler
import platform.Network.nw_listener_start
import platform.Network.nw_listener_state_cancelled
import platform.Network.nw_listener_state_failed
import platform.Network.nw_listener_state_ready
import platform.Network.nw_listener_t
import platform.Network.nw_parameters_create_secure_tcp
import platform.Network.nw_parameters_t
import platform.darwin.DISPATCH_TIME_NOW
import platform.darwin.NSEC_PER_SEC
import platform.darwin.dispatch_queue_create
import platform.darwin.dispatch_queue_t
import platform.darwin.dispatch_semaphore_create
import platform.darwin.dispatch_semaphore_signal
import platform.darwin.dispatch_semaphore_wait
import platform.darwin.dispatch_time

/**
 * iOS LAN [DataTransport].
 *
 * Holds one `nw_listener_t` bound to an OS-chosen ephemeral TCP port for
 * inbound connections. Outbound `connect(peer)` looks the peer's resolved
 * `nw_endpoint_t` up in [IosEndpointRegistry] (populated by
 * [IosLanDiscoveryTransport]) and builds an `nw_connection_t` to it.
 *
 * Construction blocks for up to 5 s until the listener reaches
 * `nw_listener_state_ready`. This mirrors the JVM/Android factories binding
 * `ServerSocket(0)` synchronously so [tcpPort] is stable from the moment the
 * `TransportFactory.build` call returns.
 */
internal class IosLanDataTransport(
    @Suppress("unused") private val transportContext: TransportContext,
    private val endpointRegistry: IosEndpointRegistry
) : DataTransport, HasLocalTcpEndpoint {

    override val type: TransportKind = TransportKind.LAN
    override val priority: Int = 100

    /** Serial queue for the listener and all connections it owns. */
    internal val queue: dispatch_queue_t =
        dispatch_queue_create("dev.p2pkit.lan.ios", null)

    /**
     * Non-TLS TCP parameters, matching the JVM/Android `Socket` wire format.
     * `SecurityMode.NoneForMvp` parity. Shared between listener and outbound
     * connections.
     */
    internal val parameters: nw_parameters_t =
        nw_parameters_create_secure_tcp(
            configure_tls = NW_PARAMETERS_DISABLE_PROTOCOL,
            configure_tcp = NW_PARAMETERS_DEFAULT_CONFIGURATION
        )

    private val listener: nw_listener_t
    private val incomingChannel = Channel<RawConnection>(Channel.UNLIMITED)

    @Volatile
    private var closed: Boolean = false

    override val tcpPort: Int

    init {
        val l = nw_listener_create(parameters)
            ?: error("nw_listener_create returned null")
        listener = l

        nw_listener_set_queue(listener, queue)

        nw_listener_set_new_connection_handler(listener) { conn ->
            if (conn != null && !closed) {
                val raw = IosRawConnection.wrap(conn, queue)
                incomingChannel.trySend(raw)
            }
        }

        val ready = dispatch_semaphore_create(0)
        nw_listener_set_state_changed_handler(listener) { state, _ ->
            when (state) {
                nw_listener_state_ready,
                nw_listener_state_failed,
                nw_listener_state_cancelled -> {
                    dispatch_semaphore_signal(ready)
                }
            }
        }

        nw_listener_start(listener)
        val deadline = dispatch_time(DISPATCH_TIME_NOW, (5L * NSEC_PER_SEC.toLong()))
        dispatch_semaphore_wait(ready, deadline)
        // Even on failure path, nw_listener_get_port returns 0; downstream
        // callers (Bonjour advertise on the discovery side) will then surface
        // a clean error. We don't throw from init so the kit can still load.
        tcpPort = nw_listener_get_port(listener).toInt()
    }

    override fun canConnect(peer: InternalPeer): Boolean =
        endpointRegistry.get(peer.publicPeer.id) != null

    override suspend fun connect(peer: InternalPeer): RawConnection {
        val endpoint = endpointRegistry.get(peer.publicPeer.id)
            ?: throw P2pError.NoTransportAvailable(peer.publicPeer)
        val conn = nw_connection_create(endpoint, parameters)
            ?: throw P2pError.ConnectionFailed("nw_connection_create returned null")
        val raw = IosRawConnection.wrap(conn, queue)
        // Wait until it transitions out of Connecting. IosRawConnection's
        // state-changed handler flips Connected on .ready or Closed on .failed
        // / .cancelled, mirroring how JvmRawConnection's Socket constructor
        // throws on connect failure.
        val terminal = raw.state.first { it != ConnectionState.Connecting }
        if (terminal != ConnectionState.Connected) {
            throw P2pError.ConnectionFailed("iOS LAN connect failed (state=$terminal)")
        }
        return raw
    }

    override fun incomingConnections(): Flow<RawConnection> = incomingChannel.consumeAsFlow()

    override suspend fun close() {
        if (closed) return
        closed = true
        nw_listener_cancel(listener)
        incomingChannel.close()
        endpointRegistry.clear()
    }
}
