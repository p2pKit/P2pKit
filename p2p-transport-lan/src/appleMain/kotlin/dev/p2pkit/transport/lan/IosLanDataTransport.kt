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
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.consumeAsFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.withTimeout
import dev.p2pkit.transport.lan.interop.p2pkit_nw_create_plain_tcp_parameters
import platform.Network.nw_connection_create
import platform.Network.nw_endpoint_create_host
import platform.Network.nw_endpoint_t
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
     *
     * Constructed entirely in ObjC via the
     * [p2pkit_nw_create_plain_tcp_parameters] cinterop helper — see
     * `src/nativeInterop/cinterop/p2pkit_nw.h` for why we can't call the
     * `nw_parameters_create_secure_tcp` macro pair from Kotlin directly.
     */
    internal val parameters: nw_parameters_t =
        p2pkit_nw_create_plain_tcp_parameters()
            ?: error("p2pkit_nw_create_plain_tcp_parameters returned null")

    internal val listener: nw_listener_t
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
            // Force Unit return — without this, Kotlin/Native infers the
            // lambda type from trySend()'s ChannelResult and bridges it to an
            // id-returning ObjC block, which libdispatch then crashes on.
            Unit
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
            Unit
        }

        nw_listener_start(listener)
        val deadline = dispatch_time(DISPATCH_TIME_NOW, (5L * NSEC_PER_SEC.toLong()))
        dispatch_semaphore_wait(ready, deadline)
        val port = nw_listener_get_port(listener).toInt()
        if (port == 0) {
            // Either the listener never reached .ready within the timeout
            // window, or it transitioned to .failed / .cancelled. Either way,
            // returning a "transport" with port 0 silently breaks Bonjour
            // advertise + every later connect attempt. Surface the failure
            // loudly so the kit factory throws — matches how ServerSocket(0)
            // throws on the JVM/Android side when bind fails.
            nw_listener_cancel(listener)
            throw IllegalStateException(
                "iOS LAN listener failed to bind a TCP port within 5 s " +
                    "(tcpPort=0 after nw_listener_start)"
            )
        }
        tcpPort = port
    }

    override fun canConnect(peer: InternalPeer): Boolean {
        if (endpointRegistry.get(peer.publicPeer.id) != null) return true
        // Manual-IP fallback: peers registered via ManualPeerRegistrar
        // carry a TransportHint(LAN, host, port) that we can dial directly,
        // mirroring how JvmLanDataTransport handles them.
        return peer.transportHints.any {
            it.type == TransportKind.LAN && !it.host.isNullOrBlank() && (it.port ?: 0) > 0
        }
    }

    override suspend fun connect(peer: InternalPeer): RawConnection {
        val endpoint: nw_endpoint_t = endpointRegistry.get(peer.publicPeer.id)
            ?: peer.transportHints.firstOrNull {
                it.type == TransportKind.LAN && !it.host.isNullOrBlank() && (it.port ?: 0) > 0
            }?.let { hint ->
                // Manual-IP dial: build an `nw_endpoint_t` from the host/port
                // pair the consumer supplied (typed in via the sample UI, or
                // injected through NetworkProvisioningManager.createManualPeer).
                // Apple's API takes the port as a C string.
                IosLanDebug.log("connect", "manual-IP fallback for ${peer.publicPeer.id.value}: host=${hint.host} port=${hint.port}")
                nw_endpoint_create_host(hint.host!!, hint.port!!.toString())
            }
            ?: throw P2pError.NoTransportAvailable(peer.publicPeer)
        val conn = nw_connection_create(endpoint, parameters)
            ?: throw P2pError.ConnectionFailed("nw_connection_create returned null")
        val raw = IosRawConnection.wrap(conn, queue)
        // Wait until it transitions out of Connecting. IosRawConnection's
        // state-changed handler flips Connected on .ready or Closed on .failed
        // / .cancelled, mirroring how JvmRawConnection's Socket constructor
        // throws on connect failure. Bounded so a stale endpoint (peer
        // disappeared between discovery and dial) doesn't hang the caller —
        // 10 s comfortably exceeds NW's typical Bonjour resolve + TCP SYN
        // window on a LAN.
        val terminal = try {
            withTimeout(CONNECT_TIMEOUT_MILLIS) {
                raw.state.first { it != ConnectionState.Connecting }
            }
        } catch (e: TimeoutCancellationException) {
            runCatching { raw.close() }
            throw P2pError.ConnectionFailed("iOS LAN connect timed out after ${CONNECT_TIMEOUT_MILLIS}ms")
        }
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

    internal companion object {
        /** Bounded outbound connect; LAN should resolve + handshake in << 10 s. */
        const val CONNECT_TIMEOUT_MILLIS: Long = 10_000
    }
}
