package dev.p2pkit.core.testfixtures

import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.RawConnection
import kotlin.concurrent.Volatile
import kotlin.concurrent.atomics.AtomicInt
import kotlin.concurrent.atomics.ExperimentalAtomicApi
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.receiveAsFlow

/**
 * In-memory [DataTransport] used in unit tests.
 *
 * - Outgoing connections are produced by [outgoingConnection] (optional).
 * - Incoming connections are pre-staged via [preStagedIncoming] and surfaced
 *   on the [incomingConnections] flow as soon as a collector subscribes.
 * - Tests can also push more incoming connections later via [emitIncoming],
 *   or terminate the incoming flow with an error via [failIncoming] — the
 *   signature the real accept loop produces when `accept()` fails while the
 *   transport is not closed (fixture change F3 / TST-3).
 * - [start] follows the shipped contract (fixture change F5 / TST-6): it
 *   records calls in [startCalls], succeeds by default, reports
 *   `Result.failure` after [close] (matching `JvmLanDataTransport`), and can
 *   be made to fail on demand via [startFailure].
 */
@OptIn(ExperimentalAtomicApi::class)
internal class FakeDataTransport(
    override val type: TransportKind = TransportKind.LAN,
    override val priority: Int = 100,
    private val outgoingConnection: (() -> RawConnection)? = null,
    preStagedIncoming: List<RawConnection> = emptyList()
) : DataTransport {

    private val incoming = Channel<RawConnection>(Channel.UNLIMITED)
    private var canConnectResult: Boolean = true

    @Volatile
    private var closed = false

    /** Whether [close] has been called. */
    val isClosed: Boolean get() = closed

    private val _startCalls = AtomicInt(0)

    /** How many times [start] was called. */
    val startCalls: Int get() = _startCalls.load()

    /**
     * Fail-on-demand knob for [start]: while non-null, `start()` returns
     * `Result.failure(startFailure)` — modeling an OS-level bind refusal per
     * the [DataTransport.start] contract (transports report, never throw).
     */
    @Volatile
    var startFailure: Throwable? = null

    /**
     * Ordered list of every [InternalPeer] passed to [connect], oldest first.
     * Tests that exercise per-attempt re-resolution (V0.4-RECONNECT) read
     * this to assert which target each reconnect attempt actually dialed.
     */
    private val _connectCalls = SnapshotList<InternalPeer>()
    val connectCalls: List<InternalPeer> get() = _connectCalls.snapshot()

    init {
        for (c in preStagedIncoming) incoming.trySend(c)
    }

    override suspend fun start(): Result<Unit> {
        _startCalls.addAndFetch(1)
        if (closed) {
            // Shipped contract: start() after close() reports failure
            // (JvmLanDataTransport.start).
            return Result.failure(IllegalStateException("FakeDataTransport is closed"))
        }
        startFailure?.let { return Result.failure(it) }
        return Result.success(Unit)
    }

    override fun canConnect(peer: InternalPeer): Boolean = canConnectResult

    fun setCanConnect(value: Boolean) {
        canConnectResult = value
    }

    override suspend fun connect(peer: InternalPeer): RawConnection {
        check(!closed) { "Transport closed" }
        _connectCalls.add(peer)
        val factory = outgoingConnection ?: error("FakeDataTransport has no outgoing connection")
        return factory()
    }

    override fun incomingConnections(): Flow<RawConnection> = incoming.receiveAsFlow()

    /**
     * Push an incoming connection to the collector. Fails loudly if the
     * incoming flow can no longer accept it (e.g. after [close] /
     * [failIncoming]) instead of dropping it silently.
     */
    fun emitIncoming(connection: RawConnection) {
        val result = incoming.trySend(connection)
        check(result.isSuccess) {
            "emitIncoming could not deliver the connection " +
                "(closed=$closed, result=$result)"
        }
    }

    /**
     * Terminate the [incomingConnections] flow with [cause], exactly like
     * the real accept loop's `close(e)` when `accept()` fails while the
     * transport is still open (fixture change F3 / TST-3). The collector
     * observes the flow completing exceptionally with [cause].
     */
    fun failIncoming(cause: Throwable) {
        incoming.close(cause)
    }

    override suspend fun close() {
        closed = true
        incoming.close()
    }
}
