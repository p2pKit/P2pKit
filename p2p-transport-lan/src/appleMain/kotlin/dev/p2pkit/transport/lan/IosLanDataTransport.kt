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
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.consumeAsFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
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
 * Owns one `nw_listener_t` bound to an OS-chosen ephemeral TCP port for
 * inbound connections. Outbound `connect(peer)` looks the peer's resolved
 * `nw_endpoint_t` up in [IosEndpointRegistry] (populated by
 * [IosLanDiscoveryTransport]) and builds an `nw_connection_t` to it.
 *
 * **Lifecycle (v0.3 refactor).** The listener bind no longer happens in
 * `init` — instead [start] is a `suspend` method that runs the
 * `nw_listener_start` + 5-second semaphore wait. A bind failure surfaces
 * as `Result.failure(IllegalStateException)`, which the kit wraps in
 * `P2pError.TransportStartFailed`. This replaces the v0.2 behaviour where
 * a port=0 outcome would `throw IllegalStateException` from `init` and
 * tear down the entire kit-construction call site (which, on iOS, was a
 * runtime panic because Kotlin/Native doesn't bridge un-`@Throws` exceptions
 * to ObjC).
 *
 * [start] is idempotent: after the first success subsequent calls return
 * `Result.success(Unit)` immediately. After a failure they retry — a port
 * that was unavailable a moment ago might be free now.
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
     * connections. Constructed entirely in ObjC via the
     * [p2pkit_nw_create_plain_tcp_parameters] cinterop helper.
     */
    internal val parameters: nw_parameters_t =
        p2pkit_nw_create_plain_tcp_parameters()
            ?: error("p2pkit_nw_create_plain_tcp_parameters returned null")

    private val _tcpPort = MutableStateFlow<Int?>(null)
    override val tcpPort: StateFlow<Int?> = _tcpPort.asStateFlow()

    /**
     * Exposed for the discovery transport to attach an advertise descriptor.
     * Null until [start] succeeds. Reading from `nw_listener_set_advertise_descriptor`
     * before start would silently no-op, so [IosLanDiscoveryTransport]'s
     * `startAdvertising` is sequenced after `data.start()` via
     * `P2pKitImpl.ensureStarted`.
     */
    @Volatile
    internal var listener: nw_listener_t = null
        private set

    private val incomingChannel = Channel<RawConnection>(Channel.UNLIMITED)
    private val startMutex = Mutex()

    @Volatile
    private var closed: Boolean = false

    override suspend fun start(): Result<Unit> = startMutex.withLock {
        if (listener != null) return Result.success(Unit)
        if (closed) return Result.failure(IllegalStateException("transport already closed"))

        val l = nw_listener_create(parameters)
            ?: return Result.failure(
                IllegalStateException("nw_listener_create returned null")
            )

        nw_listener_set_queue(l, queue)

        nw_listener_set_new_connection_handler(l) { conn ->
            if (conn != null && !closed) {
                val raw = IosRawConnection.wrap(conn, queue)
                incomingChannel.trySend(raw)
            }
            // Force Unit return — without this, Kotlin/Native infers the
            // lambda type from trySend()'s ChannelResult and bridges it to
            // an id-returning ObjC block, which libdispatch crashes on.
            Unit
        }

        val ready = dispatch_semaphore_create(0)
        nw_listener_set_state_changed_handler(l) { state, _ ->
            when (state) {
                nw_listener_state_ready,
                nw_listener_state_failed,
                nw_listener_state_cancelled -> {
                    dispatch_semaphore_signal(ready)
                }
            }
            Unit
        }

        nw_listener_start(l)
        val deadline = dispatch_time(DISPATCH_TIME_NOW, (5L * NSEC_PER_SEC.toLong()))
        dispatch_semaphore_wait(ready, deadline)
        val port = nw_listener_get_port(l).toInt()
        if (port == 0) {
            // .failed / .cancelled or the 5 s timeout expired — surface as
            // a typed Result.failure. The kit converts to TransportStartFailed.
            nw_listener_cancel(l)
            return Result.failure(
                IllegalStateException(
                    "iOS LAN listener failed to bind a TCP port within 5 s " +
                        "(tcpPort=0 after nw_listener_start)"
                )
            )
        }
        listener = l
        _tcpPort.value = port
        return Result.success(Unit)
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
                IosLanDebug.log("connect", "manual-IP fallback for ${peer.publicPeer.id.value}: host=${hint.host} port=${hint.port}")
                nw_endpoint_create_host(hint.host!!, hint.port!!.toString())
            }
            ?: throw P2pError.NoTransportAvailable(peer.publicPeer)
        val conn = nw_connection_create(endpoint, parameters)
            ?: throw P2pError.ConnectionFailed("nw_connection_create returned null")
        val raw = IosRawConnection.wrap(conn, queue)
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
        listener?.let { nw_listener_cancel(it) }
        incomingChannel.close()
        endpointRegistry.clear()
    }

    internal companion object {
        /** Bounded outbound connect; LAN should resolve + handshake in << 10 s. */
        const val CONNECT_TIMEOUT_MILLIS: Long = 10_000
    }
}
