package dev.p2pkit.transport.lan

import android.net.Network
import dev.p2pkit.transport.lan.AndroidLanDiag as Log
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.HasLocalTcpEndpoint
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
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
import java.util.concurrent.atomic.AtomicReference

/**
 * Android TCP data transport. Identical shape to [JvmLanDataTransport];
 * duplicated for the same reason as [AndroidRawConnection].
 */
internal class AndroidLanDataTransport(
    private val registration: LanServiceRegistration,
    private val networkState: AndroidLanNetworkState? = null,
    private val socketFactory: (Network?) -> Socket = { network ->
        network?.socketFactory?.createSocket() ?: Socket()
    }
) : DataTransport, HasLocalTcpEndpoint {

    override val type: TransportKind = TransportKind.LAN
    override val priority: Int = 100

    private val _tcpPort = MutableStateFlow<Int?>(null)
    override val tcpPort: StateFlow<Int?> = _tcpPort.asStateFlow()

    // Nullable StateFlow (not a one-shot deferred) so a FAILED first bind does
    // not permanently poison the eagerly-collected incoming flow: a later
    // successful start() retry still serves the accept loop
    // (AUDIT-2026-06 fix). Keep in sync with JvmLanDataTransport.
    private val serverSocketFlow = MutableStateFlow<ServerSocket?>(null)
    private val startMutex = Mutex()
    private val serverSocket = AtomicReference<ServerSocket?>(null)
    @Volatile private var restartPort: Int = 0
    @Volatile private var hasStarted: Boolean = false

    @Volatile
    private var closed: Boolean = false

    override suspend fun start(): Result<Unit> = startMutex.withLock {
        if (closed) {
            // start() after close() previously reported success on a closed
            // socket (AUDIT-2026-06 fix).
            return Result.failure(IllegalStateException("LAN data transport is closed"))
        }
        if (serverSocket.get() != null) return Result.success(Unit)
        val sock = try {
            withContext(Dispatchers.IO) { bindServerSocket(restartPort) }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Throwable) {
            if (error !is Exception) throw error
            return Result.failure(error)
        }
        try {
            currentCoroutineContext().ensureActive()
        } catch (cancelled: CancellationException) {
            runCatching { sock.close() }
            throw cancelled
        }
        serverSocket.set(sock)
        restartPort = sock.localPort
        hasStarted = true
        registration.tcpPort = sock.localPort
        _tcpPort.value = sock.localPort
        serverSocketFlow.value = sock
        Log.d(
            TAG,
            "server bound: ${sock.localSocketAddress} (wildcard 0.0.0.0, port=${sock.localPort})"
        )
        Result.success(Unit)
    }

    override fun canConnect(peer: InternalPeer): Boolean =
        peer.lanEndpoints().isNotEmpty()

    override suspend fun connect(peer: InternalPeer): RawConnection {
        val endpoints = peer.lanEndpoints()
        if (endpoints.isEmpty()) throw P2pError.NoTransportAvailable(peer.publicPeer)
        val pid8 = peer.publicPeer.id.value.take(8)
        val selectedNetwork = networkState?.selectedNetwork()
        val failures = mutableListOf<String>()
        val deadlineNanos = System.nanoTime() +
            LanConstants.TCP_CONNECT_TIMEOUT_MS * NANOS_PER_MILLISECOND
        endpoints.forEach { endpoint ->
            val timeout = if (endpoints.size == 1) {
                LanConstants.TCP_CONNECT_TIMEOUT_MS
            } else {
                remainingCandidateTimeoutMillis(deadlineNanos)
            }
            if (timeout <= 0) return@forEach
            Log.d(TAG, "connect peer=$pid8 -> ${endpoint.host}:${endpoint.port} network=$selectedNetwork (timeout=${timeout}ms)")
            val socket = socketFactory(selectedNetwork)
            try {
                withContext(Dispatchers.IO) {
                    socket.connect(InetSocketAddress(endpoint.host, endpoint.port), timeout)
                }
                currentCoroutineContext().ensureActive()
                Log.d(TAG, "connect OK peer=$pid8 local=${socket.localSocketAddress} remote=${socket.remoteSocketAddress}")
                return AndroidRawConnection(socket)
            } catch (cancelled: CancellationException) {
                runCatching { socket.close() }
                Log.d(TAG, "connect CANCELLED peer=$pid8 ${endpoint.host}:${endpoint.port} — socket closed")
                throw cancelled
            } catch (error: Throwable) {
                runCatching { socket.close() }
                if (error !is Exception) throw error
                val reason = error.dialFailureReason(timeout)
                failures += "${endpoint.host}:${endpoint.port} $reason"
                Log.d(TAG, "connect FAILED peer=$pid8 ${endpoint.host}:${endpoint.port} $reason")
            }
        }
        throw P2pError.ConnectionFailed("TCP connect candidates failed: ${failures.joinToString("; ")}")
    }

    private fun Exception.dialFailureReason(timeoutMillis: Int): String = when (this) {
        is SocketTimeoutException -> "timed out after ${timeoutMillis}ms"
        is ConnectException -> "refused (${message ?: "ECONNREFUSED"})"
        is NoRouteToHostException -> "unreachable (${message ?: "EHOSTUNREACH"})"
        else -> "failed (${this::class.simpleName}: ${message ?: ""})"
    }

    private fun remainingCandidateTimeoutMillis(deadlineNanos: Long): Int {
        val remainingNanos = deadlineNanos - System.nanoTime()
        if (remainingNanos <= 0) return 0
        val roundedMillis = (remainingNanos + NANOS_PER_MILLISECOND - 1) / NANOS_PER_MILLISECOND
        return minOf(roundedMillis.toInt(), LanConstants.TCP_CANDIDATE_CONNECT_TIMEOUT_MS)
    }

    override fun incomingConnections(): Flow<RawConnection> = callbackFlow {
        if (hasStarted && serverSocket.get() == null && !closed) {
            start().getOrThrow()
        }
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
                        if (!closed) {
                            releaseServerSocket(sock, preservePort = true)
                            close(e)
                        }
                        break
                    }
                    // Close the socket when the channel refuses it (buffer full
                    // under an accept burst / stalled collector): silently
                    // dropping leaked the fd while the remote believed it had
                    // connected (AUDIT-2026-06 fix).
                    Log.d(TAG, "inbound from ${socket.remoteSocketAddress} -> local ${socket.localSocketAddress}")
                    val offered = trySend(AndroidRawConnection(socket))
                    if (offered.isFailure) {
                        Log.d(TAG, "DROPPED ${socket.remoteSocketAddress} (channel full) — closing")
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
            releaseServerSocket(sock, preservePort = !closed)
        }
    }

    override suspend fun close(): Unit = startMutex.withLock {
        if (closed) return@withLock
        closed = true
        hasStarted = false
        restartPort = 0
        val sock = serverSocket.getAndSet(null)
        serverSocketFlow.value = null
        registration.tcpPort = 0
        _tcpPort.value = null
        sock?.let {
            Log.d(TAG, "close: shutting down server socket ${it.localSocketAddress}")
            runCatching { it.close() }
        }
        Unit
    }

    private fun releaseServerSocket(expected: ServerSocket, preservePort: Boolean) {
        if (serverSocket.compareAndSet(expected, null)) {
            if (preservePort) restartPort = expected.localPort
            serverSocketFlow.compareAndSet(expected, null)
            registration.tcpPort = 0
            _tcpPort.value = null
        }
        runCatching { expected.close() }
    }

    private fun bindServerSocket(port: Int): ServerSocket {
        val socket = ServerSocket()
        return try {
            socket.reuseAddress = true
            socket.bind(InetSocketAddress(port))
            socket
        } catch (error: Throwable) {
            runCatching { socket.close() }
            throw error
        }
    }

    private companion object {
        const val TAG = "P2pKitLanData"
        const val NANOS_PER_MILLISECOND: Long = 1_000_000
    }
}
