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

    /**
     * nw_connection_cancel must be issued for EVERY terminal path, not just
     * local close(): remote-initiated ends (failed state, read error/EOF,
     * write error) previously latched [closed] without cancelling, so close()
     * early-returned and the underlying nw_connection (fd + ObjC<->Kotlin
     * reference cycle) leaked once per remote disconnect (AUDIT-2026-06 fix).
     * AtomicInt CAS makes the cancel exactly-once across queues.
     */
    private val cancelIssued = kotlin.concurrent.AtomicInt(0)

    private fun cancelOnce(reason: String) {
        if (cancelIssued.compareAndSet(0, 1)) {
            IosLanDebug.log("conn", "nw_connection_cancel ($reason)")
            nw_connection_cancel(connection)
        }
    }

    init {
        nw_connection_set_queue(connection, queue)
        nw_connection_set_state_changed_handler(connection) { st, _ ->
            val label = when (st) {
                nw_connection_state_ready -> "ready"
                nw_connection_state_failed -> "failed"
                nw_connection_state_cancelled -> "cancelled"
                else -> "raw=$st"
            }
            IosLanDebug.log("conn", "state-changed -> $label")
            when (st) {
                nw_connection_state_ready -> {
                    if (!closed) _state.value = ConnectionState.Connected
                }

                nw_connection_state_failed -> {
                    closed = true
                    _state.value = ConnectionState.Closed
                    cancelOnce("state=failed")
                }

                nw_connection_state_cancelled -> {
                    closed = true
                    _state.value = ConnectionState.Closed
                    // Already cancelled by the framework; just latch the flag.
                    cancelIssued.value = 1
                }

                else -> {
                    // .invalid / .waiting / .preparing — keep as Connecting.
                }
            }
            Unit
        }
        nw_connection_start(connection)
        IosLanDebug.log("conn", "wrapped + nw_connection_start invoked")
    }

    override suspend fun write(bytes: ByteArray) {
        if (closed) {
            IosLanDebug.log("conn", "write(${bytes.size}): REFUSED (already closed)")
            throw IllegalStateException("connection closed")
        }
        if (_state.value == ConnectionState.Connecting) {
            IosLanDebug.log("conn", "write(${bytes.size}): state=Connecting, awaiting transition (<=${WRITE_READY_TIMEOUT_MILLIS}ms)")
            try {
                withTimeout(WRITE_READY_TIMEOUT_MILLIS) {
                    _state.first { it != ConnectionState.Connecting }
                }
            } catch (e: TimeoutCancellationException) {
                IosLanDebug.log("conn", "write(${bytes.size}): TIMEOUT — connection wedged in Connecting")
                throw IllegalStateException(
                    "write timed out waiting for connection to leave Connecting state " +
                        "after ${WRITE_READY_TIMEOUT_MILLIS}ms"
                )
            }
        }
        if (closed) {
            IosLanDebug.log("conn", "write(${bytes.size}): REFUSED (closed during await)")
            throw IllegalStateException("connection closed")
        }
        if (bytes.isEmpty()) {
            IosLanDebug.log("conn", "write(0): empty payload — no-op")
            return
        }
        writeLock.withLock {
            // Log the attempt up-front so the timeline shows the send was
            // dispatched; we only log the completion on error (a noisy
            // "completion OK" per packet would drown out the lines that
            // matter when something goes wrong).
            IosLanDebug.log("conn", "write(${bytes.size}): nw_connection_send")
            suspendCancellableCoroutine { cont ->
                bytes.usePinned { pinned ->
                    p2pkit_nw_connection_send_default(
                        connection = connection,
                        buffer = pinned.addressOf(0),
                        size = bytes.size.convert(),
                        is_complete = false,
                        completion = { error ->
                            if (error != null) {
                                IosLanDebug.log("conn", "write(${bytes.size}): completion ERROR — flipping state to Closed")
                                // Flip state to Closed AND latch closed=true
                                // before resuming with the exception. Without
                                // this the session-level keep-alive only learns
                                // the connection is dead one ping interval
                                // later. Symptom: messages silently stop being
                                // delivered while session.state stays Connected.
                                closed = true
                                _state.value = ConnectionState.Closed
                                cancelOnce("write error")
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
        IosLanDebug.log("conn", "read: flow collector started")
        while (!closed) {
            val chunk: ByteArray? = suspendCancellableCoroutine { cont ->
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
                            IosLanDebug.log("conn", "read: completion ERROR — closing")
                            closed = true
                            _state.value = ConnectionState.Closed
                            cancelOnce("read error")
                            cont.resume(null)
                        } else if (isComplete && (out == null || out.isEmpty())) {
                            IosLanDebug.log("conn", "read: EOF (isComplete + empty) — closing")
                            closed = true
                            _state.value = ConnectionState.Closed
                            cancelOnce("read EOF")
                            cont.resume(null)
                        } else {
                            // Successful chunk — intentionally silent. With
                            // a chatty session every receive would spam the
                            // log; we only surface anomalies (error, EOF, or
                            // a half-close via isComplete on a non-empty
                            // chunk, logged below).
                            cont.resume(out ?: ByteArray(0))
                            if (isComplete) {
                                IosLanDebug.log("conn", "read: half-close (isComplete on non-empty chunk) — closing")
                                closed = true
                                _state.value = ConnectionState.Closed
                                cancelOnce("read half-close")
                            }
                        }
                        Unit
                    }
                )
            }
            if (chunk == null) break
            if (chunk.isNotEmpty()) emit(chunk)
        }
        IosLanDebug.log("conn", "read: flow collector ending (closed=$closed)")
    }

    override suspend fun close() {
        closed = true
        _state.value = ConnectionState.Closed
        // Safe after remote termination too: cancelOnce is CAS-guarded, so
        // this is the single place that guarantees the cancel for locally
        // closed connections without double-cancelling remotely-ended ones.
        cancelOnce("close()")
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

