package dev.p2pkit.core.testfixtures

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.receiveAsFlow

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
}

/** A single side of a [FakeConnectionPair]. */
internal class FakeRawConnection(
    private val send: Channel<ByteArray>,
    private val receive: Channel<ByteArray>
) : RawConnection {

    private val _state = MutableStateFlow(ConnectionState.Connected)
    override val state: StateFlow<ConnectionState> = _state.asStateFlow()

    /** All chunks written on this side, in order. Tests inspect this. */
    val writtenChunks: MutableList<ByteArray> = mutableListOf()

    override suspend fun write(bytes: ByteArray) {
        writtenChunks.add(bytes)
        send.send(bytes)
    }

    override fun read(): Flow<ByteArray> = receive.receiveAsFlow()

    override suspend fun close() {
        if (_state.value == ConnectionState.Closed) return
        _state.value = ConnectionState.Closed
        send.close()
    }

    /**
     * Simulate an abrupt wire failure observable on this side.
     *
     * Closes the local receive channel with [cause] so the read flow throws
     * (driving the session's `routeEvents` into the failure branch) and
     * closes the local send channel so subsequent writes fail. The peer side
     * sees its read flow end normally (channel close without cause).
     */
    fun breakWith(cause: Throwable) {
        if (_state.value == ConnectionState.Closed) return
        _state.value = ConnectionState.Closed
        receive.close(cause)
        send.close()
    }
}
