package dev.p2pkit.core.testfixtures

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.transport.RawConnection
import kotlin.concurrent.Volatile
import kotlin.concurrent.atomics.AtomicInt
import kotlin.concurrent.atomics.AtomicReference
import kotlin.concurrent.atomics.ExperimentalAtomicApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.withContext

/**
 * Pair of in-memory connections wired to each other. Bytes written to [a]
 * appear in [b]'s read flow, and vice versa. Used to test the protocol and
 * session layers without going over a real socket.
 */
internal class FakeConnectionPair {
    private val aToB = Channel<ByteArray>(Channel.UNLIMITED)
    private val bToA = Channel<ByteArray>(Channel.UNLIMITED)

    val a: FakeRawConnection = FakeRawConnection(send = aToB, receive = bToA)
    val b: FakeRawConnection = FakeRawConnection(send = bToA, receive = aToB)

    /**
     * Terminate the wire from [side]'s end without a protocol-level CLOSE
     * frame — the fixture equivalent of the remote process going away or the
     * OS dropping the socket (fixture change F1 / TST-1). From the partner's
     * perspective this looks exactly like a remote termination does on a
     * shipped transport: its read flow drains any already-buffered bytes,
     * completes normally (no exception), flips the partner's state to
     * `Closed`, and subsequent partner writes fail.
     */
    fun hangUp(side: FakeRawConnection) {
        require(side === a || side === b) { "hangUp side must be a member of this pair" }
        side.breakWith()
    }
}

/**
 * A single side of a [FakeConnectionPair].
 *
 * **Remote-termination fidelity contract (F1 / TST-1):** every shipped
 * transport collapses a read error and EOF into the same observable
 * signature — the read flow completes *normally* (never throws) and the
 * connection state flips to `Closed` (see `JvmRawConnection.read`; the
 * Android and iOS implementations mirror it). This fixture reproduces that
 * signature: [read] completes normally when the wire ends and flips [state]
 * to `Closed`, and a peer-side [close] / [breakWith] propagates to the
 * partner (partner read drains + completes, partner state flips once its
 * read flow finishes, partner writes then fail). Tests that deliberately
 * exercise the session layer's defensive throwing-read branch — a signature
 * no shipped transport produces — must opt in via [breakWithException].
 *
 * **Write-fault injection (F2 / TST-2, TST-5):** [writeFailure] (persistent),
 * [failNextWrite] (one-shot, connection stays open), [suspendWrites] /
 * [resumeWrites] (parks writers non-cancellably, like a blocking socket
 * write against a peer that stopped draining; a [close] while parked
 * releases the writer with a failure), and [writeLatencyMillis].
 */
@OptIn(ExperimentalAtomicApi::class)
internal class FakeRawConnection(
    private val send: Channel<ByteArray>,
    private val receive: Channel<ByteArray>
) : RawConnection {

    private val _state = MutableStateFlow(ConnectionState.Connected)
    override val state: StateFlow<ConnectionState> = _state.asStateFlow()

    private val _writtenChunks = SnapshotList<ByteArray>()

    /** All chunks accepted onto the wire by this side, in order. Tests inspect this. */
    val writtenChunks: List<ByteArray> get() = _writtenChunks.snapshot()

    private val _writeAttempts = AtomicInt(0)

    /** How many [write] calls were attempted on this side (including failed ones). */
    val writeAttempts: Int get() = _writeAttempts.load()

    /**
     * When non-null, every [write] throws it (until cleared). Set a
     * platform-shaped raw exception here to model a transport whose writes
     * fail while the connection object is still around.
     */
    @Volatile
    var writeFailure: Throwable? = null

    /** Artificial per-write latency (virtual under `runTest`). 0 = none. */
    @Volatile
    var writeLatencyMillis: Long = 0

    private val nextWriteFailure = AtomicReference<Throwable?>(null)

    private val writesSuspended = MutableStateFlow(false)

    /** Make only the next [write] throw [cause]; the connection stays open and later writes succeed. */
    fun failNextWrite(cause: Throwable) {
        nextWriteFailure.store(cause)
    }

    /**
     * Park subsequent [write] calls non-cancellably — like a blocking socket
     * write stalled in a full TCP send window — until [resumeWrites] or
     * [close]/[breakWith] (which releases the parked writer with a failure,
     * the same lever a real socket close uses to unblock a stalled write).
     */
    fun suspendWrites() {
        writesSuspended.value = true
    }

    /** Release writers parked by [suspendWrites]; they proceed normally. */
    fun resumeWrites() {
        writesSuspended.value = false
    }

    override suspend fun write(bytes: ByteArray) {
        _writeAttempts.addAndFetch(1)
        if (writeLatencyMillis > 0) delay(writeLatencyMillis)
        if (writesSuspended.value) {
            // Non-cancellable park, like the real blocking write: only
            // resumeWrites() or a connection close releases it.
            withContext(NonCancellable) {
                combine(writesSuspended, _state) { suspended, st ->
                    !suspended || st == ConnectionState.Closed
                }.first { it }
            }
            if (_state.value == ConnectionState.Closed) {
                throw IllegalStateException("connection closed while write was suspended")
            }
        }
        nextWriteFailure.exchange(null)?.let { throw it }
        writeFailure?.let { throw it }
        _writtenChunks.add(bytes)
        // Throws ClosedSendChannelException once either end terminated the
        // wire — the fixture's write-after-close failure.
        send.send(bytes)
    }

    override fun read(): Flow<ByteArray> = flow {
        for (bytes in receive) {
            emit(bytes)
        }
        // Channel closed without a cause = the wire ended (local close,
        // partner close, or hang-up). Match the shipped transports: the read
        // flow completes normally and the state flips to Closed
        // (JvmRawConnection.read collapses read error and EOF into exactly
        // this signature; iOS mirrors it). Fixture change F1 / TST-1.
        _state.value = ConnectionState.Closed
    }

    override suspend fun close() {
        _state.value = ConnectionState.Closed
        // Partner's read flow drains buffered bytes, then completes normally
        // (and flips the partner's state once collected to completion).
        send.close()
        // Partner writes now fail, as after a real socket close.
        receive.close()
    }

    /**
     * Simulate an abrupt wire termination observable on this side, with the
     * same signature every shipped transport produces: this side's read flow
     * drains and completes normally (no exception), [state] flips to
     * `Closed`, and writes on either side then fail. Byte-level equivalent
     * of the remote end disappearing without a protocol CLOSE frame.
     */
    fun breakWith() {
        if (_state.value == ConnectionState.Closed) return
        _state.value = ConnectionState.Closed
        receive.close()
        send.close()
    }

    /**
     * Opt-in defensive-path variant: closes the receive channel **with**
     * [cause] so this side's read flow throws — a failure signature no
     * shipped transport produces (they complete normally on both read error
     * and EOF). Use only for tests that deliberately exercise the session
     * layer's defensive failure branch, or that need a deterministic
     * connection-loss signal independent of the remote-termination
     * classification race (TST-1 / SES-1). New remote-termination tests
     * should prefer [breakWith] / [FakeConnectionPair.hangUp].
     */
    fun breakWithException(cause: Throwable) {
        if (_state.value == ConnectionState.Closed) return
        _state.value = ConnectionState.Closed
        receive.close(cause)
        send.close()
    }
}
