package dev.p2pkit.transport.lan

import java.nio.ByteBuffer
import java.nio.channels.CancelledKeyException
import java.nio.channels.ClosedChannelException
import java.nio.channels.SelectionKey
import java.nio.channels.Selector
import java.nio.channels.SocketChannel

/** Java 17 / Android API24 public NIO, with bounded worker use even for idle or backpressured peers. */
internal object NioSocketIo {
    private val readiness = SocketReadiness("p2pkit-nio-readiness", create = ::NioSocketPoller)

    fun open(channel: SocketChannel): SuspendingSocketIo {
        channel.configureBlocking(false)
        val registration = readiness.register(channel)
        return ReadySocketIo(registration,
            readNow = { bytes -> channel.read(ByteBuffer.wrap(bytes)).takeIf { it != 0 } },
            writeNow = { bytes, offset, length ->
                channel.write(ByteBuffer.wrap(bytes, offset, length)).takeIf { it != 0 }
            },
        )
    }
}

private class NioSocketPoller : SocketPoller<SocketChannel> {
    private val selector = Selector.open()
    private class Slot(var index: Int, var epoch: Long)
    private var epoch = 0L

    override fun wakeup() { selector.wakeup() }
    override fun close() { selector.close() }

    override fun select(interests: List<SocketInterest<SocketChannel>>): IntArray {
        val result = IntArray(interests.size)
        val current = ++epoch
        var invalid = false
        interests.forEachIndexed { index, interest ->
            val ops = (if (interest.operations and READABLE != 0) SelectionKey.OP_READ else 0) or
                (if (interest.operations and WRITABLE != 0) SelectionKey.OP_WRITE else 0)
            try {
                val existing = interest.key.keyFor(selector)
                if (existing == null) interest.key.register(selector, ops, Slot(index, current)) else {
                    val slot = existing.attachment() as Slot
                    slot.index = index
                    slot.epoch = current
                    // A busy peer must not clear/re-register every OTHER idle peer's read interest.
                    // That caused O(n) selector update-queue churn and needless per-event allocations.
                    if (existing.interestOps() != ops) existing.interestOps(ops)
                }
            } catch (_: ClosedChannelException) {
                result[index] = interest.operations
                invalid = true
            } catch (_: CancelledKeyException) {
                result[index] = interest.operations
                invalid = true
            }
        }
        selector.keys().forEach { key ->
            try {
                if (key.isValid && (key.attachment() as Slot).epoch != current && key.interestOps() != 0) {
                    key.interestOps(0)
                }
            } catch (_: CancelledKeyException) { /* closing original owner */ }
        }
        // One backend-level safety ceiling, not one timer per connection. Even a failed wake must
        // let the engine observe its failure/stop flag and retire original owners deterministically.
        if (invalid) selector.selectNow() else selector.select(1_000)
        val iterator = selector.selectedKeys().iterator()
        while (iterator.hasNext()) {
            val key = iterator.next()
            iterator.remove()
            val slot = key.attachment() as Slot
            val index = slot.index
            // Attachment is refreshed for this snapshot; keys with no pending waiter have no interest.
            if (slot.epoch != current || index !in interests.indices || key.channel() !== interests[index].key) continue
            try {
                if (key.isReadable) result[index] = result[index] or READABLE
                if (key.isWritable) result[index] = result[index] or WRITABLE
            } catch (_: CancelledKeyException) { result[index] = interests[index].operations }
        }
        return result
    }
}
