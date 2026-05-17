@file:OptIn(ExperimentalForeignApi::class, BetaInteropApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.transport.RawConnection
import kotlin.concurrent.Volatile
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.cinterop.BetaInteropApi
import kotlinx.cinterop.COpaquePointerVar
import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.cinterop.addressOf
import kotlinx.cinterop.alloc
import kotlinx.cinterop.convert
import kotlinx.cinterop.get
import kotlinx.cinterop.memScoped
import kotlinx.cinterop.ptr
import kotlinx.cinterop.reinterpret
import kotlinx.cinterop.usePinned
import kotlinx.cinterop.value
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import platform.Network.NW_CONNECTION_DEFAULT_MESSAGE_CONTEXT
import platform.Network.nw_connection_cancel
import platform.Network.nw_connection_receive
import platform.Network.nw_connection_send
import platform.Network.nw_connection_set_queue
import platform.Network.nw_connection_set_state_changed_handler
import platform.Network.nw_connection_start
import platform.Network.nw_connection_state_cancelled
import platform.Network.nw_connection_state_failed
import platform.Network.nw_connection_state_ready
import platform.Network.nw_connection_t
import platform.darwin.dispatch_data_create
import platform.darwin.dispatch_data_get_size
import platform.darwin.dispatch_data_t
import platform.darwin.dispatch_queue_t
import platform.posix.size_tVar
import platform.posix.uint8_tVar

/**
 * iOS LAN [RawConnection] backed by Network.framework's `nw_connection_t`.
 *
 * Same contract as [JvmRawConnection]/[AndroidRawConnection] but built on the
 * Apple C API rather than POSIX sockets:
 *
 * - **State**: NWConnection's state-changed handler maps to [_state].
 *   `nw_connection_state_ready` → [ConnectionState.Connected]; `_failed` and
 *   `_cancelled` → [ConnectionState.Closed].
 * - **Write**: each `write(bytes)` pins the ByteArray, calls
 *   `dispatch_data_create` (which copies by default), and waits for the send
 *   completion handler before returning. Serialized through [writeLock]
 *   exactly like the JVM side.
 * - **Read**: each `nw_connection_receive` is awaited via
 *   `suspendCancellableCoroutine`, then yielded to the cold [Flow]. The
 *   downstream collector applies natural backpressure — no buffer between
 *   the dispatch queue and the consumer is needed.
 *
 * Construction does not call `nw_connection_start`. Use [outbound] for
 * dialer-side connections (we need to start them ourselves) and [inbound]
 * for connections handed in by the listener's new-connection handler
 * (the listener already configured them; we just attach the receive pump).
 */
internal class IosRawConnection private constructor(
    private val connection: nw_connection_t,
    private val queue: dispatch_queue_t
) : RawConnection {

    private val _state = MutableStateFlow(ConnectionState.Connecting)
    override val state: StateFlow<ConnectionState> = _state.asStateFlow()

    private val writeLock = Mutex()

    @Volatile
    private var closed: Boolean = false

    init {
        nw_connection_set_queue(connection, queue)
        nw_connection_set_state_changed_handler(connection) { st, _ ->
            when (st) {
                nw_connection_state_ready -> {
                    if (!closed) _state.value = ConnectionState.Connected
                }

                nw_connection_state_failed,
                nw_connection_state_cancelled -> {
                    closed = true
                    _state.value = ConnectionState.Closed
                }

                else -> {
                    // .invalid / .waiting / .preparing — keep as Connecting.
                }
            }
        }
        nw_connection_start(connection)
    }

    override suspend fun write(bytes: ByteArray) {
        if (closed) throw IllegalStateException("connection closed")
        if (_state.value == ConnectionState.Connecting) {
            // SessionManager normally only writes after Connected, but be defensive.
            _state.first { it != ConnectionState.Connecting }
        }
        if (closed) throw IllegalStateException("connection closed")
        if (bytes.isEmpty()) return
        writeLock.withLock {
            suspendCancellableCoroutine { cont ->
                val data: dispatch_data_t = bytes.usePinned { pinned ->
                    // DISPATCH_DATA_DESTRUCTOR_DEFAULT (null) makes an internal
                    // copy, so it's safe for usePinned to release the pin as
                    // soon as dispatch_data_create returns.
                    dispatch_data_create(
                        buffer = pinned.addressOf(0),
                        size = bytes.size.convert(),
                        queue = queue,
                        destructor = null
                    )
                }
                nw_connection_send(
                    connection = connection,
                    content = data,
                    context = NW_CONNECTION_DEFAULT_MESSAGE_CONTEXT,
                    is_complete = false,
                    completion = { error ->
                        if (error != null) {
                            cont.resumeWithException(
                                NetworkException("nw_connection_send failed")
                            )
                        } else {
                            cont.resume(Unit)
                        }
                    }
                )
            }
        }
    }

    override fun read(): Flow<ByteArray> = flow {
        while (!closed) {
            val chunk: ByteArray? = suspendCancellableCoroutine { cont ->
                nw_connection_receive(
                    connection = connection,
                    minimum_incomplete_length = 1u,
                    maximum_length = RECEIVE_MAX_LENGTH,
                    completion = { content, _, isComplete, error ->
                        val out = if (content != null) dispatchDataToByteArray(content) else null
                        if (error != null) {
                            closed = true
                            _state.value = ConnectionState.Closed
                            cont.resume(null)
                        } else if (isComplete && (out == null || out.isEmpty())) {
                            // Remote completed cleanly.
                            closed = true
                            _state.value = ConnectionState.Closed
                            cont.resume(null)
                        } else {
                            cont.resume(out ?: ByteArray(0))
                            if (isComplete) {
                                closed = true
                                _state.value = ConnectionState.Closed
                            }
                        }
                    }
                )
            }
            if (chunk == null) break
            if (chunk.isNotEmpty()) emit(chunk)
        }
    }

    override suspend fun close() {
        if (closed) return
        closed = true
        _state.value = ConnectionState.Closed
        nw_connection_cancel(connection)
    }

    internal class NetworkException(message: String) : RuntimeException(message)

    internal companion object {
        /** 64 KiB matches JvmRawConnection's BUFFER_SIZE. */
        private val RECEIVE_MAX_LENGTH: UInt = 64u * 1024u

        fun wrap(connection: nw_connection_t, queue: dispatch_queue_t): IosRawConnection =
            IosRawConnection(connection, queue)
    }
}

@OptIn(ExperimentalForeignApi::class, BetaInteropApi::class)
private fun dispatchDataToByteArray(data: dispatch_data_t): ByteArray {
    val totalSize = dispatch_data_get_size(data).toInt()
    if (totalSize == 0) return ByteArray(0)
    val result = ByteArray(totalSize)
    memScoped {
        val bufferPtr = alloc<COpaquePointerVar>()
        val mappedSize = alloc<size_tVar>()
        // dispatch_data_create_map returns a NEW dispatch_data_t that owns a
        // contiguous buffer covering all regions of `data`. The buffer pointer
        // is valid until the mapped reference is released; we copy out within
        // this memScoped block so the mapped object stays alive.
        @Suppress("UNUSED_VARIABLE")
        val mapped = platform.darwin.dispatch_data_create_map(data, bufferPtr.ptr, mappedSize.ptr)
        val src = bufferPtr.value!!.reinterpret<uint8_tVar>()
        for (i in 0 until totalSize) {
            result[i] = src[i].toByte()
        }
    }
    return result
}
