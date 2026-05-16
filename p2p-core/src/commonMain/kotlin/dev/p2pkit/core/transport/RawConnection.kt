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

    public fun read(): Flow<ByteArray>

    public suspend fun close()
}
