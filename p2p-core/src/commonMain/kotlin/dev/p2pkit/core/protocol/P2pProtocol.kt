package dev.p2pkit.core.protocol

import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.flow.Flow

/**
 * Encodes and decodes the wire protocol over a [RawConnection].
 *
 * The protocol carries both *data* (text/binary messages produced by the app)
 * and *control* frames (HELLO, ACK, PING/PONG, CLOSE, ERROR). The session
 * manager owns the connection and routes [ProtocolEvent]s emitted by
 * [events] to the right place.
 *
 * Send methods are not synchronized — the caller is expected to serialize
 * writes per connection (the session uses an internal Mutex for this).
 */
internal interface P2pProtocol {

    suspend fun sendMessage(connection: RawConnection, message: P2pMessage)

    suspend fun sendHello(connection: RawConnection, hello: HelloPayload)

    suspend fun sendPing(connection: RawConnection)

    suspend fun sendPong(connection: RawConnection)

    suspend fun sendClose(connection: RawConnection)

    suspend fun sendError(connection: RawConnection, reason: String)

    /**
     * Stream of decoded events read from [connection]. Completes when the
     * underlying read flow completes; throws on protocol or transport errors.
     */
    fun events(connection: RawConnection): Flow<ProtocolEvent>
}
