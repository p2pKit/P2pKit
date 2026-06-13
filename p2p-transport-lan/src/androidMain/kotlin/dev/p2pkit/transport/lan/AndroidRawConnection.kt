package dev.p2pkit.transport.lan

import android.util.Log
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.IOException
import java.net.Socket
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Android [RawConnection] over a [java.net.Socket]. Identical in shape to the
 * JVM version; duplicated here because :p2p-transport-lan does not share a
 * `jvmAndroidMain` source set in v0.1. Future refactor: introduce an
 * intermediate source set and merge the two implementations.
 */
internal class AndroidRawConnection(
    private val socket: Socket
) : RawConnection {

    private val _state = MutableStateFlow(ConnectionState.Connected)
    override val state: StateFlow<ConnectionState> = _state.asStateFlow()

    private val writeLock = Mutex()

    /** Stable label for the diagnostic trail; remoteSocketAddress goes null after close. */
    private val label: String =
        runCatching { "${socket.localSocketAddress}<->${socket.remoteSocketAddress}" }.getOrNull()
            ?: "socket"

    init {
        Log.d(TAG, "opened $label")
    }

    override suspend fun write(bytes: ByteArray) {
        writeLock.withLock {
            withContext(Dispatchers.IO) {
                // V0.6-WRITE-TIMEOUT (AUDIT-2026-06): mirrors JvmRawConnection.
                // java.net.Socket has no write deadline and its OutputStream
                // ignores thread interruption, so a peer that stops draining
                // wedges this write forever. A watchdog closes the socket once
                // the deadline passes, forcing the blocked write to throw and
                // tearing the dead connection down so keep-alive/reconnect
                // observe Closed. (A plain withTimeout can't help: structured
                // cancellation still waits for the un-interruptible write to
                // return, so the only abort lever is socket.close().)
                val timedOut = AtomicBoolean(false)
                val watchdog = launch {
                    delay(WRITE_TIMEOUT_MILLIS)
                    timedOut.set(true)
                    Log.d(
                        TAG,
                        "$label WRITE TIMEOUT after ${WRITE_TIMEOUT_MILLIS}ms (peer not draining) — closing socket"
                    )
                    runCatching { socket.close() }
                }
                AndroidLanDiag.frame(TAG, "$label write ${bytes.size}B")
                try {
                    val out = socket.getOutputStream()
                    out.write(bytes)
                    out.flush()
                } catch (e: IOException) {
                    if (timedOut.get()) {
                        _state.value = ConnectionState.Closed
                        throw IOException(
                            "socket write timed out after ${WRITE_TIMEOUT_MILLIS}ms (peer not reading)",
                            e
                        )
                    }
                    Log.d(TAG, "$label write error: ${e.message}")
                    throw e
                } finally {
                    watchdog.cancel()
                }
            }
        }
    }

    override fun read(): Flow<ByteArray> = flow {
        val input = withContext(Dispatchers.IO) { socket.getInputStream() }
        val buffer = ByteArray(BUFFER_SIZE)
        while (currentCoroutineContext().isActive) {
            val n = try {
                withContext(Dispatchers.IO) { input.read(buffer) }
            } catch (e: IOException) {
                Log.d(TAG, "$label read error (socket dropped): ${e.message}")
                break
            }
            if (n < 0) {
                Log.d(TAG, "$label EOF (remote half-closed)")
                break
            }
            if (n > 0) {
                AndroidLanDiag.frame(TAG, "$label read ${n}B")
                emit(buffer.copyOfRange(0, n))
            }
        }
        _state.value = ConnectionState.Closed
        Log.d(TAG, "$label read loop ended -> Closed")
    }

    override suspend fun close() {
        if (_state.value == ConnectionState.Closed) return
        _state.value = ConnectionState.Closed
        Log.d(TAG, "$label close()")
        withContext(Dispatchers.IO) {
            runCatching { socket.close() }
        }
    }

    private companion object {
        const val BUFFER_SIZE = 8 * 1024
        const val TAG = "P2pKitLanConn"

        /**
         * Upper bound for a single frame write. Mirrors JvmRawConnection: LAN
         * frames are ≤ 64 KiB chunks (8 MiB worst-case), which drain in well
         * under a second on any real Wi-Fi link; 30 s only elapses when the
         * peer's TCP receive window is genuinely wedged.
         */
        const val WRITE_TIMEOUT_MILLIS = 30_000L
    }
}
