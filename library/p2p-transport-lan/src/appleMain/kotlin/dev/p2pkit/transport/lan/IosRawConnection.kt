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
import platform.Network.nw_connection_copy_current_path
import platform.Network.nw_connection_set_queue
import platform.Network.nw_connection_set_state_changed_handler
import platform.Network.nw_connection_start
import platform.Network.nw_connection_state_cancelled
import platform.Network.nw_connection_state_failed
import platform.Network.nw_connection_state_preparing
import platform.Network.nw_connection_state_ready
import platform.Network.nw_connection_state_waiting
import platform.Network.nw_connection_t
import platform.Network.nw_error_get_error_code
import platform.Network.nw_interface_type_cellular
import platform.Network.nw_interface_type_loopback
import platform.Network.nw_interface_type_other
import platform.Network.nw_interface_type_wifi
import platform.Network.nw_interface_type_wired
import platform.Network.nw_path_uses_interface_type
import platform.darwin.dispatch_queue_t
import platform.posix.uint8_tVar

/** Non-suspending cancellation ownership required by Network.framework callbacks. */
internal interface IosConnectionHandle : RawConnection {
    fun cancelNow(reason: String)
}

/**
 * iOS LAN [RawConnection] backed by Network.framework's `nw_connection_t`.
 *
 * Same contract as `JvmRawConnection`/`AndroidRawConnection` but built on the
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
 * Construction attaches the state/receive handlers and immediately calls
 * `nw_connection_start` — both dialer-side connections and connections
 * handed in by the listener's new-connection handler (which Network.framework
 * delivers un-started) go through the single [wrap] factory.
 */
internal class IosRawConnection private constructor(
    private val connection: nw_connection_t,
    private val queue: dispatch_queue_t,
    private val sendOverride: (suspend (ByteArray) -> Unit)? = null,
    startNativeConnection: Boolean = true
) : IosConnectionHandle {

    private val _state = MutableStateFlow(
        if (startNativeConnection) ConnectionState.Connecting else ConnectionState.Connected
    )
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

    /**
     * Log which interface type(s) the connection's current path is using.
     * Issue #3 forensic signal: a connection that reached `ready` over AWDL
     * shows up as `wifi=true` or `other=true`; a dial that never leaves
     * `waiting`/`preparing` has no usable path. `nw_path_uses_interface_type`
     * is the same primitive [IosLanDataTransport]'s path monitor already uses.
     */
    private fun logConnectionPath(reason: String) {
        val path = nw_connection_copy_current_path(connection)
        if (path == null) {
            IosLanDebug.log("conn", "$reason: current path = null")
            return
        }
        val wifi = nw_path_uses_interface_type(path, nw_interface_type_wifi)
        val cell = nw_path_uses_interface_type(path, nw_interface_type_cellular)
        val wired = nw_path_uses_interface_type(path, nw_interface_type_wired)
        val loop = nw_path_uses_interface_type(path, nw_interface_type_loopback)
        val other = nw_path_uses_interface_type(path, nw_interface_type_other)
        IosLanDebug.log(
            "conn",
            "$reason path interfaces: wifi=$wifi cellular=$cell wired=$wired loopback=$loop other=$other " +
                "(AWDL usually reports wifi=true or other=true)"
        )
    }

    init {
        nw_connection_set_queue(connection, queue)
        nw_connection_set_state_changed_handler(connection) connectionStateHandler@ { st, err ->
            val label = when (st) {
                nw_connection_state_ready -> "ready"
                nw_connection_state_preparing -> "preparing"
                nw_connection_state_waiting -> "waiting"
                nw_connection_state_failed -> "failed"
                nw_connection_state_cancelled -> "cancelled"
                else -> "raw=$st"
            }
            // nw_error carries the POSIX errno (e.g. 65 EHOSTUNREACH, 61
            // ECONNREFUSED, 60 ETIMEDOUT) — the why behind a stuck/failed dial.
            val errCode = err?.let { nw_error_get_error_code(it) }
            IosLanDebug.log("conn", "state-changed -> $label" + (errCode?.let { " errCode=$it" } ?: ""))
            when (st) {
                nw_connection_state_ready -> {
                    if (!closed) _state.value = ConnectionState.Connected
                    // Issue #3: log which interface the established connection
                    // actually uses — reveals whether the dial routed over
                    // Wi-Fi/wired vs. AWDL/peer-to-peer ("other").
                    logConnectionPath("ready")
                }

                nw_connection_state_waiting -> {
                    IosLanDebug.log(
                        "conn",
                        "WAITING errCode=${errCode ?: 0} — endpoint not yet routable " +
                            "(peer-to-peer routing is enabled; inspect path/packaging state)"
                    )
                }

                nw_connection_state_failed -> {
                    closed = true
                    _state.value = ConnectionState.Closed
                    cancelOnce("state=failed errCode=${errCode ?: 0}")
                }

                nw_connection_state_cancelled -> {
                    closed = true
                    _state.value = ConnectionState.Closed
                    // Already cancelled by the framework; just latch the flag.
                    cancelIssued.value = 1
                }

                else -> {
                    // .invalid / .preparing — keep as Connecting.
                }
            }
            return@connectionStateHandler
        }
        if (startNativeConnection) {
            nw_connection_start(connection)
            IosLanDebug.log("conn", "wrapped + nw_connection_start invoked")
        }
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
            // A writer may have queued behind another send while close()
            // cancelled the connection. Recheck after acquiring ownership so
            // no queued write is dispatched on a terminal connection.
            if (closed) {
                IosLanDebug.log("conn", "write(${bytes.size}): REFUSED (closed while queued)")
                throw IllegalStateException("connection closed")
            }
            sendOverride?.let { send ->
                withTimeout(WRITE_TIMEOUT_MILLIS) { send(bytes) }
                return@withLock
            }
            // Log the attempt up-front so the timeline shows the send was
            // dispatched; we only log the completion on error (a noisy
            // "completion OK" per packet would drown out the lines that
            // matter when something goes wrong).
            IosLanDebug.log("conn", "write(${bytes.size}): nw_connection_send")
            try {
                // V0.6-WRITE-TIMEOUT (AUDIT-2026-06): bound the wait for the
                // send-completion handler — parity with the JVM/Android 30 s
                // write watchdog. A peer that stops draining (TCP receive
                // window wedged) never fires the completion, which used to
                // suspend this write forever while holding [writeLock]:
                // messages silently stopped while session.state stayed
                // Connected. Unlike the JVM's un-interruptible blocking
                // OutputStream write, this suspension is genuinely
                // cancellable, so a withTimeout around ONLY the send await
                // is the whole fix. A late completion after the timeout
                // resumes a cancelled continuation, which is a no-op.
                withTimeout(WRITE_TIMEOUT_MILLIS) {
                    suspendCancellableCoroutine<Unit> { cont ->
                        bytes.usePinned { pinned ->
                            p2pkit_nw_connection_send_default(
                                connection = connection,
                                buffer = pinned.addressOf(0),
                                size = bytes.size.convert(),
                                is_complete = false,
                                completion = sendCompletion@ { error ->
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
                                    return@sendCompletion
                                }
                            )
                        }
                    }
                }
            } catch (e: TimeoutCancellationException) {
                // Catch ONLY the timeout: TimeoutCancellationException is a
                // CancellationException subtype, but a parent cancellation
                // arrives as a plain CancellationException and must keep
                // propagating untouched.
                IosLanDebug.log(
                    "conn",
                    "write(${bytes.size}): SEND TIMEOUT after ${WRITE_TIMEOUT_MILLIS}ms (peer not draining) — cancelling connection"
                )
                closed = true
                _state.value = ConnectionState.Closed
                cancelOnce("write timeout")
                throw IllegalStateException(
                    "nw_connection_send completion did not fire within " +
                        "${WRITE_TIMEOUT_MILLIS}ms (peer not reading)"
                )
            }
        }
    }

    override fun read(): Flow<ByteArray> = flow {
        IosLanDebug.log("conn", "read: flow collector started")
        while (!closed) {
            val chunk: ByteArray? = suspendCancellableCoroutine { cont ->
                cont.invokeOnCancellation {
                    // Cancelling only the Kotlin continuation does not cancel
                    // Network.framework's outstanding receive operation.
                    cancelNow("read collector cancelled")
                }
                p2pkit_nw_connection_receive_default(
                    connection = connection,
                    min_incomplete_length = 1u,
                    max_length = RECEIVE_MAX_LENGTH,
                    completion = receiveCompletion@ { buffer, size, isComplete, error ->
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
                        return@receiveCompletion
                    }
                )
            }
            if (chunk == null) break
            if (chunk.isNotEmpty()) emit(chunk)
        }
        IosLanDebug.log("conn", "read: flow collector ending (closed=$closed)")
    }

    override suspend fun close() {
        cancelNow("close()")
    }

    /**
     * Non-suspend body of [close], also callable directly from libdispatch
     * callbacks that must not suspend — [IosLanDataTransport]'s
     * new-connection handler uses it to release a just-started inbound
     * connection whose channel hand-off was refused (AUDIT-2026-06 #20b).
     * Safe after remote termination too: cancelOnce is CAS-guarded, so
     * this is the single place that guarantees the cancel for locally
     * closed connections without double-cancelling remotely-ended ones.
     */
    override fun cancelNow(reason: String) {
        closed = true
        _state.value = ConnectionState.Closed
        cancelOnce(reason)
    }

    internal class NetworkException(message: String) : RuntimeException(message)

    internal companion object {
        /**
         * Max bytes requested per `nw_connection_receive` call. Independent
         * of JvmRawConnection's 8 KiB read buffer — per-read chunk size is a
         * platform implementation detail; framing happens above the byte
         * stream, so the sizes need not match.
         */
        private val RECEIVE_MAX_LENGTH: UInt = 64u * 1024u

        /** Bounded wait for a wedged Connecting state on write entry. */
        const val WRITE_READY_TIMEOUT_MILLIS: Long = 10_000

        /**
         * Upper bound for a single nw_connection_send completion — parity
         * with the JVM/Android 30 s write watchdog (V0.6-WRITE-TIMEOUT).
         * LAN frames are ≤ 64 KiB chunks (8 MiB worst-case max frame),
         * which drain in well under a second on any real link; 30 s only
         * elapses when the peer's TCP receive window is genuinely wedged,
         * at which point the connection is dead and must be torn down.
         * Distinct from [WRITE_READY_TIMEOUT_MILLIS], which bounds only
         * the wait to LEAVE Connecting before the send is attempted.
         */
        const val WRITE_TIMEOUT_MILLIS: Long = 30_000

        fun wrap(connection: nw_connection_t, queue: dispatch_queue_t): IosRawConnection =
            IosRawConnection(connection, queue)

        /** Deterministic send seam for the write/close ownership tests. */
        internal fun wrapForWriteTest(
            connection: nw_connection_t,
            queue: dispatch_queue_t,
            send: suspend (ByteArray) -> Unit
        ): IosRawConnection = IosRawConnection(
            connection = connection,
            queue = queue,
            sendOverride = send,
            startNativeConnection = false
        )
    }
}
