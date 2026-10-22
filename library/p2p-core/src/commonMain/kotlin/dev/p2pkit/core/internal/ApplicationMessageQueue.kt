package dev.p2pkit.core.internal

import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.PayloadLease
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.channels.ChannelIterator
import kotlinx.coroutines.flow.MutableStateFlow

/** Session-owned charges include queued messages and the message being emitted to the application. */
internal class ApplicationMessageQueue(
    private val maxMessages: Int,
    private val maxBytes: Long
) {
    private data class Backlog(val messages: Int = 0, val bytes: Long = 0L)

    private val retained = MutableStateFlow(Backlog())
    private val channel = Channel<Entry>(
        capacity = Channel.UNLIMITED,
        // A matched receive can be cancelled before the delivery loop enters its finally block.
        // This owner must be synchronous: no cancelled scope, dispatch or suspending mutex is needed.
        onUndeliveredElement = Entry::release
    )

    val backlog: Pair<Int, Long>
        get() = retained.value.let { it.messages to it.bytes }

    /** On failure the caller still owns [lease], just as with Channel.trySend. */
    fun trySend(message: P2pMessage, retainedBytes: Long, lease: PayloadLease?): Boolean {
        require(retainedBytes >= 0L)
        while (true) {
            val current = retained.value
            if (current.messages >= maxMessages || retainedBytes > maxBytes - current.bytes) return false
            if (retained.compareAndSet(current, Backlog(current.messages + 1, current.bytes + retainedBytes))) break
        }
        val entry = Entry(message, lease) { releaseCharge(retainedBytes) }
        val sent = channel.trySend(entry)
        if (sent.isFailure) {
            // trySend neither delivers the value nor invokes onUndeliveredElement on failure.
            entry.reject()
        }
        return sent.isSuccess
    }

    operator fun iterator(): ChannelIterator<Entry> = channel.iterator()

    fun close() {
        channel.close()
    }

    /** Do not reset the counters: a non-cooperative in-flight emitter still owns its own charge. */
    fun drain() {
        while (true) {
            val entry = channel.tryReceive().getOrNull() ?: return
            entry.release()
        }
    }

    private fun releaseCharge(bytes: Long) {
        while (true) {
            val current = retained.value
            check(current.messages > 0 && current.bytes >= bytes) { "Application backlog ownership underflow" }
            if (retained.compareAndSet(current, Backlog(current.messages - 1, current.bytes - bytes))) return
        }
    }

    internal class Entry(
        val message: P2pMessage,
        private val lease: PayloadLease?,
        private val releaseCharge: () -> Unit
    ) {
        private val released = MutableStateFlow(false)

        fun release() {
            if (!released.compareAndSet(false, true)) return
            try {
                lease?.release()
            } finally {
                releaseCharge()
            }
        }

        /** Roll back only our charge; an unsuccessful send never takes the caller's payload lease. */
        fun reject() {
            if (released.compareAndSet(false, true)) releaseCharge()
        }
    }
}
