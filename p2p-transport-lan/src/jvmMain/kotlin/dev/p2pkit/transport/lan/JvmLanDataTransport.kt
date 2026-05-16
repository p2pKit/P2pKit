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
import kotlinx.coroutines.cancel
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.net.ServerSocket
import java.net.Socket

internal class JvmLanDataTransport(
    private val registration: LanServiceRegistration,
    private val serverSocket: ServerSocket
) : DataTransport, HasLocalTcpEndpoint {

    override val type: TransportKind = TransportKind.LAN

    /** LAN is the only v0.1 transport; priority just needs to be positive. */
    override val priority: Int = 100

    override val tcpPort: Int get() = registration.tcpPort

    @Volatile
    private var closed: Boolean = false

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
        return JvmRawConnection(socket)
    }

    override fun incomingConnections(): Flow<RawConnection> = callbackFlow {
        val accepterJob: Job = launch(Dispatchers.IO) {
            try {
                while (!closed) {
                    val socket = try {
                        serverSocket.accept()
                    } catch (e: CancellationException) {
                        throw e
                    } catch (e: Throwable) {
                        if (!closed) close(e)
                        break
                    }
                    trySend(JvmRawConnection(socket))
                }
                close()
            } catch (e: CancellationException) {
                // Normal shutdown.
            }
        }
        awaitClose {
            accepterJob.cancel()
            runCatching { serverSocket.close() }
        }
    }

    override suspend fun close() {
        if (closed) return
        closed = true
        withContext(Dispatchers.IO) {
            runCatching { serverSocket.close() }
        }
    }
}
