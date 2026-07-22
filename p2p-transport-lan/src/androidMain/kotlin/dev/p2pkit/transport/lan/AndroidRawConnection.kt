package dev.p2pkit.transport.lan

import android.util.Log
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.transport.RawConnection
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.DelicateCoroutinesApi
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.IOException
import java.net.Socket
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger

/**
 * Android [RawConnection] over a [java.net.Socket]. Identical in shape to the
 * JVM version; duplicated here because :p2p-transport-lan does not share a
 * `jvmAndroidMain` source set in v0.1. Future refactor: introduce an
 * intermediate source set and merge the two implementations.
 */
internal class AndroidRawConnection(
    private val socket: Socket,
    /**
     * AUDIT-2026-07 (CON-14) test seam: the write-watchdog deadline,
     * injectable so the transport-level wedged-write teardown is testable
     * (pinned by `JvmRawConnectionWriteWatchdogTest` on the JVM twin — the
     * behavior-parity pair is changed in lockstep). Production call sites
     * (`AndroidLanDataTransport`) pass nothing and get [WRITE_TIMEOUT_MILLIS].
     */
    private val writeTimeoutMillis: Long = WRITE_TIMEOUT_MILLIS
) : RawConnection {

    private val _state = MutableStateFlow(ConnectionState.Connected)
    override val state: StateFlow<ConnectionState> = _state.asStateFlow()

    private val writeLock = Mutex()

    /**
     * CAS gate so the socket fd is released exactly once no matter which path
     * gets there first (user [close], read-loop EOF/error, write watchdog).
     * Every `socket.close()` in this class MUST go through [closeSocketOnce].
     */
    private val socketClosed = AtomicBoolean(false)

    /**
     * Connection-owned scope for the write watchdog (AUDIT-2026-06).
     * Deliberately NOT a child of the write's own `withContext` scope — an
     * enclosing cancellation of the caller must not kill the watchdog while
     * the un-interruptible `out.write()` is still parked (the watchdog's
     * `socket.close()` is the only thing that can unblock it). And
     * deliberately on [Dispatchers.Default], not the shared IO pool, so a
     * saturated IO pool cannot starve the very timeout that recovers it.
     * Cancelled in [close].
     */
    private val connScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    /** Stable label for the diagnostic trail; remoteSocketAddress goes null after close. */
    private val label: String =
        runCatching { "${socket.localSocketAddress}<->${socket.remoteSocketAddress}" }.getOrNull()
            ?: "socket"

    init {
        Log.d(TAG, "opened $label")
    }

    /** The single place the fd is released; idempotent and safe from any thread. */
    private fun closeSocketOnce() {
        if (socketClosed.compareAndSet(false, true)) {
            runCatching { socket.close() }
        }
    }

    override suspend fun write(bytes: ByteArray) {
        writeLock.withLock {
            // V0.6-WRITE-TIMEOUT (AUDIT-2026-06): mirrors JvmRawConnection.
            // java.net.Socket has no write deadline and its OutputStream
            // ignores thread interruption, so a peer that stops draining
            // wedges this write forever. A watchdog closes the socket once
            // the deadline passes, forcing the blocked write to throw and
            // tearing the dead connection down so keep-alive/reconnect
            // observe Closed. (A plain withTimeout can't help: structured
            // cancellation still waits for the un-interruptible write to
            // return, so the only abort lever is socket.close().)
            //
            // The watchdog runs on [connScope] and races the writer through
            // [writeState] (INFLIGHT → DONE | TIMED_OUT) so that:
            //   - caller cancellation cannot kill the watchdog before it
            //     fires (the wedged write still gets unblocked);
            //   - a watchdog that fires just as the write completes cannot
            //     close a healthy socket AND be reported as success — whoever
            //     wins the CAS decides the outcome.
            val writeState = AtomicInteger(WRITE_INFLIGHT)
            val watchdog = connScope.launch {
                delay(writeTimeoutMillis)
                if (writeState.compareAndSet(WRITE_INFLIGHT, WRITE_TIMED_OUT)) {
                    Log.d(
                        TAG,
                        "$label WRITE TIMEOUT after ${writeTimeoutMillis}ms (peer not draining) — closing socket"
                    )
                    closeSocketOnce()
                    _state.value = ConnectionState.Closed
                }
            }
            try {
                try {
                    withContext(Dispatchers.IO) {
                        AndroidLanDiag.frame(TAG, "$label write ${bytes.size}B")
                        val out = socket.getOutputStream()
                        out.write(bytes)
                        out.flush()
                    }
                } catch (e: IOException) {
                    if (!writeState.compareAndSet(WRITE_INFLIGHT, WRITE_DONE)) {
                        // The watchdog won: this IOException is its
                        // socket.close() surfacing inside the parked write.
                        // Report the timeout, not the raw close error.
                        _state.value = ConnectionState.Closed
                        throw IOException(
                            "socket write timed out after ${writeTimeoutMillis}ms (peer not reading)",
                            e
                        )
                    }
                    Log.d(TAG, "$label write error: ${e.message}")
                    closeSocketOnce()
                    _state.value = ConnectionState.Closed
                    throw e
                }
                if (!writeState.compareAndSet(WRITE_INFLIGHT, WRITE_DONE)) {
                    // The write call returned, but the watchdog had already
                    // fired and closed the socket under us — the bytes may
                    // never reach the peer. This must surface as a failure.
                    _state.value = ConnectionState.Closed
                    throw IOException(
                        "socket write timed out after ${writeTimeoutMillis}ms (peer not reading)"
                    )
                }
            } finally {
                // Normal/error path: stop the still-sleeping watchdog. If the
                // caller was cancelled while out.write() was parked, this line
                // is not reached until the write unblocks — which is exactly
                // why the watchdog lives on connScope and survives to fire.
                watchdog.cancel()
            }
        }
    }

    @OptIn(DelicateCoroutinesApi::class)
    override fun read(): Flow<ByteArray> = flow {
        // AUDIT-2026-07 (CON-1): the terminal cleanup below is in a `finally`
        // so it runs on EVERY exit from this flow — including a
        // CancellationException when the collector is cancelled, which
        // previously left the blocking read and fd alive until a remote close
        // or GC. The CE itself still propagates (never swallowed); every
        // production reader-cancellation site tears the connection down
        // anyway, so releasing here is the correct semantic.
        try {
            val input = socket.getInputStream()
            val buffer = ByteArray(BUFFER_SIZE)
            while (currentCoroutineContext().isActive) {
                val n = try {
                    suspendCancellableCoroutine<Int> { continuation ->
                        if (socketClosed.get()) {
                            continuation.resume(-1)
                            return@suspendCancellableCoroutine
                        }
                        val readJob = connScope.launch(
                            context = Dispatchers.IO,
                            start = CoroutineStart.ATOMIC
                        ) {
                            try {
                                val read = input.read(buffer)
                                if (continuation.isActive) continuation.resume(read)
                            } catch (error: Throwable) {
                                if (continuation.isActive) {
                                    continuation.resumeWithException(error)
                                } else if (error !is IOException) {
                                    throw error
                                }
                            }
                        }
                        continuation.invokeOnCancellation {
                            closeSocketOnce()
                            _state.value = ConnectionState.Closed
                            readJob.cancel()
                        }
                    }
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
        } finally {
            // AUDIT-2026-06 fd-leak fix: a remote-initiated disconnect (EOF or
            // read error) must release our fd, not just flip the state. Before
            // this, the loop set Closed without closing the socket and close()
            // early-returned on Closed — leaking the fd until GC.
            closeSocketOnce()
            _state.value = ConnectionState.Closed
            Log.d(TAG, "$label read loop ended -> Closed")
        }
    }

    override suspend fun close() {
        // No early-return on _state == Closed: the read loop flips state to
        // Closed on a remote disconnect, and close() must still be able to
        // release local resources afterwards (AUDIT-2026-06 fd-leak fix).
        // Idempotency comes from the closeSocketOnce CAS instead.
        _state.value = ConnectionState.Closed
        Log.d(TAG, "$label close()")
        // AUDIT-2026-07 (CON-1): this used to hop through
        // withContext(Dispatchers.IO) before releasing the socket, but
        // withContext on an already-cancelled caller throws CE on entry
        // WITHOUT running its block — session teardown closing connections
        // from a cancelling scope skipped both the fd release and the
        // watchdog-scope cancel. closeSocketOnce() is a plain CAS +
        // socket.close() that already runs on arbitrary threads (the write
        // watchdog calls it), so release inline with no suspension point:
        // close() can no longer be preempted by cancellation.
        closeSocketOnce()
        connScope.cancel()
    }

    private companion object {
        const val BUFFER_SIZE = 8 * 1024
        const val TAG = "P2pKitLanConn"

        /** [write] outcome markers raced between the writer and its watchdog. */
        const val WRITE_INFLIGHT = 0
        const val WRITE_DONE = 1
        const val WRITE_TIMED_OUT = 2

        /**
         * Upper bound for a single frame write. Mirrors JvmRawConnection: LAN
         * frames are ≤ 64 KiB chunks (8 MiB worst-case), which drain in well
         * under a second on any real Wi-Fi link; 30 s only elapses when the
         * peer's TCP receive window is genuinely wedged.
         */
        const val WRITE_TIMEOUT_MILLIS = 30_000L
    }
}
