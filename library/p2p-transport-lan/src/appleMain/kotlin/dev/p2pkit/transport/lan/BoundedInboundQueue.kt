package dev.p2pkit.transport.lan

import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.receiveAsFlow

/**
 * Bounded hand-off for already-started inbound resources. Ownership moves to
 * the consumer only after a successful receive; overflow and terminal drain
 * synchronously release resources through [onDrop].
 */
internal class BoundedInboundQueue<T : Any>(
    capacity: Int,
    private val onDrop: (T) -> Unit
) {
    private val channel = Channel(
        capacity = capacity,
        onUndeliveredElement = onDrop
    )

    fun offer(value: T): Boolean {
        if (channel.trySend(value).isSuccess) return true
        onDrop(value)
        return false
    }

    fun asFlow(): Flow<T> = channel.receiveAsFlow()

    /** Release queued ownership without terminally closing the reusable channel. */
    fun drain() {
        while (true) {
            val value = channel.tryReceive().getOrNull() ?: return
            onDrop(value)
        }
    }

    fun closeAndDrain() {
        channel.close()
        drain()
    }
}
