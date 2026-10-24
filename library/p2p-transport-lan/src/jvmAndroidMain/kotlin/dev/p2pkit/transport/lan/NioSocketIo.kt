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

    override fun wakeup() { selector.wakeup() }
    override fun close() { selector.close() }

    override fun select(interests: List<SocketInterest<SocketChannel>>): IntArray {
        val result = IntArray(interests.size)
        selector.keys().forEach { key ->
            try { if (key.isValid) key.interestOps(0) } catch (_: CancelledKeyException) { /* closing owner */ }
        }
        var invalid = false
        interests.forEachIndexed { index, interest ->
            val ops = (if (interest.operations and READABLE != 0) SelectionKey.OP_READ else 0) or
                (if (interest.operations and WRITABLE != 0) SelectionKey.OP_WRITE else 0)
            try {
                interest.key.register(selector, ops, index)
            } catch (_: ClosedChannelException) {
                result[index] = interest.operations
                invalid = true
            } catch (_: CancelledKeyException) {
                result[index] = interest.operations
                invalid = true
            }
        }
        // One backend-level safety ceiling, not one timer per connection. Even a failed wake must
        // let the engine observe its failure/stop flag and retire original owners deterministically.
        if (invalid) selector.selectNow() else selector.select(1_000)
        val iterator = selector.selectedKeys().iterator()
        while (iterator.hasNext()) {
            val key = iterator.next()
            iterator.remove()
            val index = key.attachment() as Int
            // Attachment is refreshed for this snapshot; keys with no pending waiter have no interest.
            if (index !in interests.indices || key.channel() !== interests[index].key) continue
            try {
                if (key.isReadable) result[index] = result[index] or READABLE
                if (key.isWritable) result[index] = result[index] or WRITABLE
            } catch (_: CancelledKeyException) { result[index] = interests[index].operations }
        }
        return result
    }
}
