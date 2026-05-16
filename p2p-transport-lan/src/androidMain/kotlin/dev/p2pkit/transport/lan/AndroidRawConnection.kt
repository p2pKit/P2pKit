package dev.p2pkit.transport.lan

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.IOException
import java.net.Socket

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

    override suspend fun write(bytes: ByteArray) {
        writeLock.withLock {
            withContext(Dispatchers.IO) {
                val out = socket.getOutputStream()
                out.write(bytes)
                out.flush()
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
                break
            }
            if (n < 0) break
            if (n > 0) emit(buffer.copyOfRange(0, n))
        }
        _state.value = ConnectionState.Closed
    }

    override suspend fun close() {
        if (_state.value == ConnectionState.Closed) return
        _state.value = ConnectionState.Closed
        withContext(Dispatchers.IO) {
            runCatching { socket.close() }
        }
    }

    private companion object {
        const val BUFFER_SIZE = 8 * 1024
    }
}
