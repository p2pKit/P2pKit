package dev.p2pkit.core.testfixtures

import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.receiveAsFlow

/**
 * In-memory [DataTransport] used in unit tests.
 *
 * - Outgoing connections are produced by [outgoingConnection] (optional).
 * - Incoming connections are pre-staged via [preStagedIncoming] and surfaced
 *   on the [incomingConnections] flow as soon as a collector subscribes.
 * - Tests can also push more incoming connections later via [emitIncoming].
 */
internal class FakeDataTransport(
    override val type: TransportKind = TransportKind.LAN,
    override val priority: Int = 100,
    private val outgoingConnection: (() -> RawConnection)? = null,
    preStagedIncoming: List<RawConnection> = emptyList()
) : DataTransport {

    private val incoming = Channel<RawConnection>(Channel.UNLIMITED)
    private var canConnectResult: Boolean = true
    private var closed = false

    /**
     * Ordered list of every [InternalPeer] passed to [connect], oldest first.
     * Tests that exercise per-attempt re-resolution (V0.4-RECONNECT) read
     * this to assert which target each reconnect attempt actually dialed.
     */
    private val _connectCalls: MutableList<InternalPeer> = mutableListOf()
    val connectCalls: List<InternalPeer> get() = _connectCalls.toList()

    init {
        for (c in preStagedIncoming) incoming.trySend(c)
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

    fun emitIncoming(connection: RawConnection) {
        incoming.trySend(connection)
    }

    override suspend fun close() {
        closed = true
        incoming.close()
    }
}
