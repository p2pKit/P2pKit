@file:OptIn(ExperimentalForeignApi::class, BetaInteropApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.transport.lan.interop.p2pkit_nw_connection_receive_default
import dev.p2pkit.transport.lan.interop.p2pkit_nw_connection_send_default
import kotlin.concurrent.Volatile
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.cinterop.BetaInteropApi
import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.cinterop.addressOf
import kotlinx.cinterop.convert
import kotlinx.cinterop.readBytes
import kotlinx.cinterop.reinterpret
import kotlinx.cinterop.usePinned
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeout
import platform.Network.nw_connection_cancel
import platform.Network.nw_connection_set_queue
import platform.Network.nw_connection_set_state_changed_handler
import platform.Network.nw_connection_start
import platform.Network.nw_connection_state_cancelled
import platform.Network.nw_connection_state_failed
import platform.Network.nw_connection_state_ready
import platform.Network.nw_connection_t
import platform.darwin.dispatch_queue_t
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
            Unit
        }
        nw_connection_start(connection)
    }

    override suspend fun write(bytes: ByteArray) {
        if (closed) throw IllegalStateException("connection closed")
        if (_state.value == ConnectionState.Connecting) {
            // SessionManager normally only writes after Connected, but be
            // defensive. Bounded so a wedged Connecting state doesn't hang the
            // sender forever — the keep-alive would eventually notice, but
            // that takes a full pingInterval round-trip; surfacing fast is
            // better. 10 s matches IosLanDataTransport.CONNECT_TIMEOUT_MILLIS.
            try {
                withTimeout(WRITE_READY_TIMEOUT_MILLIS) {
                    _state.first { it != ConnectionState.Connecting }
                }
            } catch (e: TimeoutCancellationException) {
                throw IllegalStateException(
                    "write timed out waiting for connection to leave Connecting state " +
                        "after ${WRITE_READY_TIMEOUT_MILLIS}ms"
                )
            }
        }
        if (closed) throw IllegalStateException("connection closed")
        if (bytes.isEmpty()) return
        writeLock.withLock {
            suspendCancellableCoroutine { cont ->
                bytes.usePinned { pinned ->
                    // C helper performs dispatch_data_create (which copies)
                    // and nw_connection_send with the default-message context
                    // entirely on the ObjC side, so Kotlin never has to box
                    // dispatch_data_t or nw_content_context_t.
                    p2pkit_nw_connection_send_default(
                        connection = connection,
                        buffer = pinned.addressOf(0),
                        size = bytes.size.convert(),
                        is_complete = false,
                        completion = { error ->
                            if (error != null) {
                                cont.resumeWithException(
                                    NetworkException("nw_connection_send failed")
                                )
                            } else {
                                cont.resume(Unit)
                            }
                            Unit
                        }
                    )
                }
            }
        }
    }

    override fun read(): Flow<ByteArray> = flow {
        while (!closed) {
            val chunk: ByteArray? = suspendCancellableCoroutine { cont ->
                // C helper wraps nw_connection_receive and maps the resulting
                // dispatch_data_t to a contiguous (buffer, size) pair before
                // calling our completion. Keeps dispatch_data_t off the
                // Kotlin side entirely.
                p2pkit_nw_connection_receive_default(
                    connection = connection,
                    min_incomplete_length = 1u,
                    max_length = RECEIVE_MAX_LENGTH,
                    completion = { buffer, size, isComplete, error ->
                        val out: ByteArray? = if (buffer != null && size.toInt() > 0) {
                            buffer.reinterpret<uint8_tVar>().readBytes(size.toInt())
                        } else {
                            null
                        }
                        if (error != null) {
                            closed = true
                            _state.value = ConnectionState.Closed
                            cont.resume(null)
                        } else if (isComplete && (out == null || out.isEmpty())) {
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
                        Unit
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

        /** Bounded wait for a wedged Connecting state on write entry. */
        const val WRITE_READY_TIMEOUT_MILLIS: Long = 10_000

        fun wrap(connection: nw_connection_t, queue: dispatch_queue_t): IosRawConnection =
            IosRawConnection(connection, queue)
    }
}

