package dev.p2pkit.transport.lan

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.HasLocalTcpEndpoint
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.net.ConnectException
import java.net.InetSocketAddress
import java.net.NoRouteToHostException
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketTimeoutException

internal class JvmLanDataTransport(
    private val registration: LanServiceRegistration
) : DataTransport, HasLocalTcpEndpoint {

    override val type: TransportKind = TransportKind.LAN

    /** LAN is the only v0.1 transport; priority just needs to be positive. */
    override val priority: Int = 100

    private val _tcpPort = MutableStateFlow<Int?>(null)
    override val tcpPort: StateFlow<Int?> = _tcpPort.asStateFlow()

    /**
     * Set by [start] with the bound server socket. [incomingConnections]
     * parks on this nullable StateFlow until `start()` succeeds. A nullable
     * StateFlow (not a one-shot deferred) so a FAILED first bind does not
     * permanently poison the eagerly-collected incoming flow: a later
     * successful `start()` retry still serves the accept loop
     * (AUDIT-2026-06 fix). Bind failures surface through start()'s Result
     * (-> P2pError.TransportStartFailed), not through this flow.
     */
    private val serverSocketFlow = MutableStateFlow<ServerSocket?>(null)

    private val startMutex = Mutex()
    @Volatile private var serverSocket: ServerSocket? = null

    @Volatile
    private var closed: Boolean = false

    override suspend fun start(): Result<Unit> = startMutex.withLock {
        if (closed) {
            // start() after close() previously reported success on a closed
            // socket (AUDIT-2026-06 fix).
            return Result.failure(IllegalStateException("LAN data transport is closed"))
        }
        if (serverSocket != null) return Result.success(Unit)
        withContext(Dispatchers.IO) {
            runCatching {
                val sock = ServerSocket(0)
                serverSocket = sock
                registration.tcpPort = sock.localPort
                _tcpPort.value = sock.localPort
                serverSocketFlow.value = sock
                Unit
            }
        }
    }

    override fun canConnect(peer: InternalPeer): Boolean =
        peer.transportHints.any {
            it.type == TransportKind.LAN && !it.host.isNullOrBlank() && (it.port ?: 0) > 0
        }

    override suspend fun connect(peer: InternalPeer): RawConnection {
        val hint = peer.transportHints.firstOrNull {
            it.type == TransportKind.LAN && !it.host.isNullOrBlank() && (it.port ?: 0) > 0
        } ?: throw P2pError.NoTransportAvailable(peer.publicPeer)
        val host = hint.host!!
        val port = hint.port!!
        val socket = withContext(Dispatchers.IO) {
            val s = Socket()
            try {
                // V0.5.1-TCP-TIMEOUT (issue #9): bounded connect so a stale
                // SRV record doesn't burn ~17 s of the reconnect budget on
                // the OS-default `Socket(host, port)` blocking wait. The
                // failure classification below feeds the `reason` field that
                // `SessionReconnectHandler` already logs per attempt.
                s.connect(InetSocketAddress(host, port), LanConstants.TCP_CONNECT_TIMEOUT_MS)
                s
            } catch (e: Throwable) {
                runCatching { s.close() }
                val reason = when (e) {
                    is SocketTimeoutException ->
                        "timed out after ${LanConstants.TCP_CONNECT_TIMEOUT_MS}ms"
                    is ConnectException -> "refused (${e.message ?: "ECONNREFUSED"})"
                    is NoRouteToHostException -> "unreachable (${e.message ?: "EHOSTUNREACH"})"
                    else -> "failed (${e::class.simpleName}: ${e.message ?: ""})"
                }
                throw P2pError.ConnectionFailed("TCP connect $host:$port $reason")
            }
        }
        return JvmRawConnection(socket)
    }

    override fun incomingConnections(): Flow<RawConnection> = callbackFlow {
        // Park until start() binds a server socket; a later successful retry
        // after a failed first bind still serves this collector (see
        // serverSocketFlow KDoc).
        val sock = serverSocketFlow.filterNotNull().first()
        val accepterJob: Job = launch(Dispatchers.IO) {
            try {
                while (!closed) {
                    val socket = try {
                        sock.accept()
                    } catch (e: CancellationException) {
                        throw e
                    } catch (e: Throwable) {
                        if (!closed) close(e)
                        break
                    }
                    // Close the socket when the channel refuses it (buffer full
                    // under an accept burst / stalled collector): silently
                    // dropping leaked the fd while the remote believed it had
                    // connected (AUDIT-2026-06 fix).
                    val offered = trySend(JvmRawConnection(socket))
                    if (offered.isFailure) {
                        runCatching { socket.close() }
                    }
                }
                close()
            } catch (e: CancellationException) {
                // Normal shutdown.
            }
        }
        awaitClose {
            accepterJob.cancel()
            runCatching { sock.close() }
        }
    }

    override suspend fun close() {
        if (closed) return
        closed = true
        val sock = serverSocket ?: return
        withContext(Dispatchers.IO) {
            runCatching { sock.close() }
        }
    }
}
