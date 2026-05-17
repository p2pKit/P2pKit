package dev.p2pkit.transport.lan

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.HasLocalTcpEndpoint
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.net.ServerSocket
import java.net.Socket

/**
 * Android TCP data transport. Identical shape to [JvmLanDataTransport];
 * duplicated for the same reason as [AndroidRawConnection].
 */
internal class AndroidLanDataTransport(
    private val registration: LanServiceRegistration
) : DataTransport, HasLocalTcpEndpoint {

    override val type: TransportKind = TransportKind.LAN
    override val priority: Int = 100

    private val _tcpPort = MutableStateFlow<Int?>(null)
    override val tcpPort: StateFlow<Int?> = _tcpPort.asStateFlow()

    private val serverSocketReady = CompletableDeferred<ServerSocket>()
    private val startMutex = Mutex()
    @Volatile private var serverSocket: ServerSocket? = null

    @Volatile
    private var closed: Boolean = false

    override suspend fun start(): Result<Unit> = startMutex.withLock {
        if (serverSocket != null) return Result.success(Unit)
        val result = withContext(Dispatchers.IO) {
            runCatching {
                val sock = ServerSocket(0)
                serverSocket = sock
                registration.tcpPort = sock.localPort
                _tcpPort.value = sock.localPort
                serverSocketReady.complete(sock)
                Unit
            }
        }
        if (result.isFailure) {
            serverSocketReady.completeExceptionally(
                result.exceptionOrNull() ?: IllegalStateException("ServerSocket bind failed")
            )
        }
        result
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
            try {
                Socket(host, port)
            } catch (e: Throwable) {
                throw P2pError.ConnectionFailed("TCP connect $host:$port failed: ${e.message}")
            }
        }
        return AndroidRawConnection(socket)
    }

    override fun incomingConnections(): Flow<RawConnection> = callbackFlow {
        val sock = try {
            serverSocketReady.await()
        } catch (e: CancellationException) {
            throw e
        } catch (e: Throwable) {
            close(e)
            return@callbackFlow
        }
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
                    trySend(AndroidRawConnection(socket))
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
