package dev.p2pkit.core.transport

import dev.p2pkit.core.ConnectionState
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.StateFlow

/**
 * A bidirectional byte stream between two devices.
 *
 * Implemented by each [DataTransport]; the protocol layer frames bytes on top
 * of it. Internal — apps never see this type.
 */
public interface RawConnection {
    public val state: StateFlow<ConnectionState>

    public suspend fun write(bytes: ByteArray)

    /**
     * Stream of raw bytes from the peer. Single-collector contract: the
     * engine collects this exactly once per connection. Shipped
     * implementations read the underlying socket directly inside the flow,
     * so a second concurrent collector would steal bytes and corrupt
     * framing — implementations are not required to support multiple or
     * repeated collection.
     */
    public fun read(): Flow<ByteArray>

    /**
     * Permanently close the stream and release every owned native resource.
     * Must be idempotent and safe when cleanup races a failed read/write or a
     * second close attempt. No later callback may make the connection usable
     * again.
     */
    public suspend fun close()
}
