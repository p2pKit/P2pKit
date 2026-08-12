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
import kotlinx.coroutines.NonCancellable
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
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.atomic.AtomicReference

/**
 * Android TCP data transport. Identical shape to `JvmLanDataTransport`;
 * duplicated for the same reason as [AndroidRawConnection].
 */
internal class AndroidLanDataTransport(
    private val registration: LanServiceRegistration,
    private val networkState: AndroidLanNetworkState? = null,
    private val socketFactory: (Network?) -> Socket = { network ->
        network?.socketFactory?.createSocket() ?: Socket()
    },
    private val serverSocketFactory: () -> ServerSocket = ::ServerSocket,
    private val beforeListenerResourceCheckForTest: (() -> Unit)? = null,
    private val beforeDialOwnershipHandoffForTest: (() -> Unit)? = null,
    private val afterListenerDetachForTest: (() -> Unit)? = null
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
    private val listenerStateLock = Any()
    private val dialStateLock = Any()
    private val serverSocket = AtomicReference<ServerSocket?>(null)
    private val retainedServerSocketCleanup = mutableSetOf<ServerSocket>()
    private val lifecycleGeneration = AtomicLong()
    private val pendingDialSockets = mutableSetOf<Socket>()
    private val retainedDialSocketCleanup = mutableSetOf<Socket>()
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
        beforeListenerResourceCheckForTest?.invoke()
        val hasUnreleasedResources = synchronized(listenerStateLock) {
            retainedServerSocketCleanup.isNotEmpty()
        } || synchronized(dialStateLock) {
            retainedDialSocketCleanup.isNotEmpty()
        }
        if (hasUnreleasedResources) {
            return Result.failure(
                IllegalStateException("LAN data transport has unreleased resources; retry stop()")
            )
        }
        if (serverSocket.get() != null) return Result.success(Unit)
        val callerJob = currentCoroutineContext()[Job]
        var boundCandidate: ServerSocket? = null
        var bindFailure: Throwable? = null
        try {
            withContext(Dispatchers.IO + NonCancellable) {
                try {
                    boundCandidate = bindServerSocket(restartPort)
                } catch (error: Throwable) {
                    bindFailure = error
                }
            }
        } catch (cancelled: CancellationException) {
            boundCandidate
                ?.let(::closeServerSocketRetainingFailure)
                ?.let(cancelled::addSuppressed)
            bindFailure?.let(cancelled::addSuppressed)
            throw cancelled
        }
        bindFailure?.let { error ->
            currentCoroutineContext().ensureActive()
            if (error !is Exception) throw error
            return Result.failure(error)
        }
        val sock = checkNotNull(boundCandidate) {
            "listener bind completed without a socket or failure"
        }
        try {
            currentCoroutineContext().ensureActive()
        } catch (cancelled: CancellationException) {
            closeServerSocketRetainingFailure(sock)?.let(cancelled::addSuppressed)
            throw cancelled
        }
        val publicationFailure = synchronized(listenerStateLock) {
            when {
                callerJob?.isActive == false -> CancellationException(
                    "LAN data transport start was cancelled before listener publication"
                )
                closed -> IllegalStateException("LAN data transport is closed")
                retainedServerSocketCleanup.isNotEmpty() -> IllegalStateException(
                    "LAN data transport has unreleased listener resources; retry stop()"
                )
                serverSocket.get() != null -> IllegalStateException(
                    "LAN data transport listener was concurrently published"
                )
                else -> {
                    serverSocket.set(sock)
                    restartPort = sock.localPort
                    hasStarted = true
                    registration.tcpPort = sock.localPort
                    _tcpPort.value = sock.localPort
                    serverSocketFlow.value = sock
                    null
                }
            }
        }
        if (publicationFailure != null) {
            closeServerSocketRetainingFailure(sock)?.let(publicationFailure::addSuppressed)
            if (publicationFailure is CancellationException) throw publicationFailure
            return Result.failure(publicationFailure)
        }
        Log.d(
            TAG,
            "server bound: ${sock.localSocketAddress} (wildcard 0.0.0.0, port=${sock.localPort})"
        )
        Result.success(Unit)
    }

    override fun canConnect(peer: InternalPeer): Boolean =
        peer.lanEndpoints().isNotEmpty()

    override suspend fun connect(peer: InternalPeer): RawConnection {
        val dialGeneration = lifecycleGeneration.get()
        ensureDialGeneration(dialGeneration)
        val endpoints = peer.lanEndpoints()
        if (endpoints.isEmpty()) throw P2pError.NoTransportAvailable(peer.publicPeer)
        val pid8 = peer.publicPeer.id.value.take(8)
        val selectedRoute = try {
            withContext(Dispatchers.IO) { networkState?.selectedRoute() }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Throwable) {
            if (error !is Exception) throw error
            throw P2pError.ConnectionFailed(
                "Android LAN route selection failed (${error::class.simpleName}: " +
                    error.message.orEmpty() + ")"
            ).also { failure -> failure.addSuppressed(error) }
        }
        if (networkState != null && selectedRoute == null) {
            throw P2pError.ConnectionFailed(
                "No Android LAN route is available; start LAN discovery/advertising and retry"
            )
        }
        val failures = mutableListOf<String>()
        val deadlineNanos = System.nanoTime() +
            LanConstants.TCP_CONNECT_TIMEOUT_MS * NANOS_PER_MILLISECOND
        endpoints.forEach { endpoint ->
            ensureDialGeneration(dialGeneration)
            val timeout = if (endpoints.size == 1) {
                LanConstants.TCP_CONNECT_TIMEOUT_MS
            } else {
                remainingCandidateTimeoutMillis(deadlineNanos)
            }
            if (timeout <= 0) return@forEach
            Log.d(
                TAG,
                "connect peer=$pid8 -> ${endpoint.host}:${endpoint.port} " +
                    "network=${selectedRoute?.network} local=${selectedRoute?.localAddress?.hostAddress} " +
                    "route=${selectedRoute?.fingerprint} " +
                    "(timeout=${timeout}ms)"
            )
            var createdSocket: Socket? = null
            val socket = try {
                socketFactory(selectedRoute?.network).also { candidate ->
                    createdSocket = candidate
                    // Hotspot/AP host mode is often absent from
                    // ConnectivityManager, so the discovery selector exposes
                    // an explicit Java-interface address with network=null.
                    // Binding that local address before connect is the only
                    // safe way to prevent the kernel from choosing cellular.
                    if (selectedRoute != null && selectedRoute.network == null) {
                        candidate.bind(InetSocketAddress(selectedRoute.localAddress, 0))
                    }
                }
            } catch (error: Throwable) {
                val cleanupFailure = createdSocket?.let(::closeDialSocket)
                if (error !is Exception) {
                    cleanupFailure?.let(error::addSuppressed)
                    throw error
                }
                val routeReason =
                    "route setup failed (${error::class.simpleName}: ${error.message.orEmpty()})"
                if (cleanupFailure != null) {
                    throw P2pError.ConnectionFailed(
                        "TCP route setup cleanup failed: ${endpoint.host}:${endpoint.port} $routeReason"
                    ).also { failure ->
                        failure.addSuppressed(error)
                        failure.addSuppressed(cleanupFailure)
                    }
                }
                failures += "${endpoint.host}:${endpoint.port} $routeReason"
                Log.d(TAG, "connect FAILED peer=$pid8 ${endpoint.host}:${endpoint.port} $routeReason")
                return@forEach
            }
            val admitted = synchronized(dialStateLock) {
                if (isDialGenerationActive(dialGeneration)) {
                    pendingDialSockets += socket
                    true
                } else {
                    false
                }
            }
            if (!admitted) {
                throw stoppedDialFailure().also { failure ->
                    closeDialSocket(socket)?.let(failure::addSuppressed)
                }
            }
            try {
                ensureDialGeneration(dialGeneration)
                withContext(Dispatchers.IO) {
                    socket.connect(InetSocketAddress(endpoint.host, endpoint.port), timeout)
                }
                currentCoroutineContext().ensureActive()
                ensureDialGeneration(dialGeneration)
                Log.d(TAG, "connect OK peer=$pid8 local=${socket.localSocketAddress} remote=${socket.remoteSocketAddress}")
                beforeDialOwnershipHandoffForTest?.invoke()
                val handedOff = synchronized(dialStateLock) {
                    if (isDialGenerationActive(dialGeneration)) {
                        pendingDialSockets.remove(socket)
                    } else {
                        false
                    }
                }
                if (!handedOff) throw stoppedDialFailure()
                return AndroidRawConnection(socket)
            } catch (cancelled: CancellationException) {
                closeDialSocket(socket)?.let(cancelled::addSuppressed)
                Log.d(TAG, "connect CANCELLED peer=$pid8 ${endpoint.host}:${endpoint.port} — socket closed")
                throw cancelled
            } catch (error: Throwable) {
                val cleanupFailure = closeDialSocket(socket)
                if (!isDialGenerationActive(dialGeneration)) {
                    throw stoppedDialFailure().also { stopped ->
                        stopped.addSuppressed(error)
                        cleanupFailure?.let(stopped::addSuppressed)
                    }
                }
                if (error !is Exception) {
                    cleanupFailure?.let(error::addSuppressed)
                    throw error
                }
                val reason = error.dialFailureReason(timeout)
                if (cleanupFailure != null) {
                    throw P2pError.ConnectionFailed(
                        "TCP connect candidate cleanup failed: ${endpoint.host}:${endpoint.port} $reason"
                    ).also { failure ->
                        failure.addSuppressed(error)
                        failure.addSuppressed(cleanupFailure)
                    }
                }
                failures += "${endpoint.host}:${endpoint.port} $reason"
                Log.d(TAG, "connect FAILED peer=$pid8 ${endpoint.host}:${endpoint.port} $reason")
            } finally {
                synchronized(dialStateLock) { pendingDialSockets -= socket }
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
                    val raw = AndroidRawConnection(socket)
                    val offered = trySend(raw)
                    if (offered.isFailure) {
                        Log.d(TAG, "DROPPED ${socket.remoteSocketAddress} (channel full) — closing")
                        runCatching { raw.close() }
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

    override suspend fun stop(): Unit = startMutex.withLock {
        if (closed) return@withLock
        stopLocked(preserveRestartPort = true)
    }

    override suspend fun close(): Unit = startMutex.withLock {
        if (!closed) closed = true
        stopLocked(preserveRestartPort = false)
        networkState?.clear()
    }

    private fun stopLocked(preserveRestartPort: Boolean) {
        val dialCleanup = synchronized(dialStateLock) {
            lifecycleGeneration.incrementAndGet()
            pendingDialSockets.toList() + retainedDialSocketCleanup.toList()
        }.distinct()
        val listenerCleanup = synchronized(listenerStateLock) {
            hasStarted = false
            val sock = serverSocket.getAndSet(null)
            if (preserveRestartPort && sock != null) restartPort = sock.localPort
            if (!preserveRestartPort) restartPort = 0
            serverSocketFlow.value = null
            registration.tcpPort = 0
            _tcpPort.value = null
            listOfNotNull(sock) + retainedServerSocketCleanup.toList()
        }.distinct()
        val failures = mutableListOf<Throwable>()
        dialCleanup.forEach { socket -> closeDialSocket(socket)?.let(failures::add) }
        listenerCleanup.firstOrNull()?.let {
            Log.d(
                TAG,
                "${if (closed) "close" else "stop"}: shutting down server socket ${it.localSocketAddress}"
            )
        }
        listenerCleanup.forEach { listener ->
            closeServerSocketRetainingFailure(listener)?.let(failures::add)
        }
        if (failures.isNotEmpty()) {
            throw IllegalStateException(
                "LAN data transport failed to release ${failures.size} resource(s)",
                failures.first()
            ).also { aggregate ->
                failures.drop(1).forEach(aggregate::addSuppressed)
            }
        }
    }

    private fun ensureDialGeneration(expected: Long) {
        if (!isDialGenerationActive(expected)) throw stoppedDialFailure()
    }

    private fun isDialGenerationActive(expected: Long): Boolean =
        !closed && lifecycleGeneration.get() == expected

    private fun stoppedDialFailure(): P2pError.ConnectionFailed =
        P2pError.ConnectionFailed("LAN data transport stopped during connect")

    private fun closeDialSocket(socket: Socket): Throwable? =
        synchronized(dialStateLock) {
            pendingDialSockets -= socket
            retainedDialSocketCleanup += socket
            runCatching { socket.close() }.exceptionOrNull().also { failure ->
                if (failure == null) retainedDialSocketCleanup -= socket
            }
        }

    private fun releaseServerSocket(expected: ServerSocket, preservePort: Boolean) {
        synchronized(listenerStateLock) {
            retainedServerSocketCleanup += expected
            if (serverSocket.compareAndSet(expected, null)) {
                afterListenerDetachForTest?.invoke()
                if (preservePort) restartPort = expected.localPort
                serverSocketFlow.compareAndSet(expected, null)
                registration.tcpPort = 0
                _tcpPort.value = null
            }
            if (runCatching { expected.close() }.isSuccess) {
                retainedServerSocketCleanup -= expected
            }
        }
    }

    private fun closeServerSocketRetainingFailure(socket: ServerSocket): Throwable? =
        synchronized(listenerStateLock) {
            retainedServerSocketCleanup += socket
            runCatching { socket.close() }.exceptionOrNull().also { failure ->
                if (failure == null) retainedServerSocketCleanup -= socket
            }
        }

    private fun bindServerSocket(port: Int): ServerSocket {
        val socket = serverSocketFactory()
        return try {
            socket.reuseAddress = true
            socket.bind(InetSocketAddress(port))
            socket
        } catch (error: Throwable) {
            closeServerSocketRetainingFailure(socket)?.let(error::addSuppressed)
            throw error
        }
    }

    private companion object {
        const val TAG = "P2pKitLanData"
        const val NANOS_PER_MILLISECOND: Long = 1_000_000
    }
}
