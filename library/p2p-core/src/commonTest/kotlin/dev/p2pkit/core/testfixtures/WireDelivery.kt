package dev.p2pkit.core.testfixtures

import kotlin.random.Random
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.channels.ReceiveChannel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.runTest

/** Opt-in read shapes; write logging, ordering and the default wire stay unchanged. */
internal sealed interface WireDelivery {
    data object Exact : WireDelivery

    data class Fragmented(val seed: Int, val maxFragmentBytes: Int = 97) : WireDelivery {
        init {
            require(maxFragmentBytes in 1..8_192)
        }
    }

    /**
     * Merge only already-queued writes, never wait for another write (which
     * would deadlock request/response handshakes). Both bytes and drain work
     * per emission are bounded. A large write can span several emissions.
     */
    data class Coalesced(val maxReadBytes: Int = 8_192, val maxWritesPerRead: Int = 16) : WireDelivery {
        init {
            require(maxReadBytes in 1..8_192)
            require(maxWritesPerRead in 1..1_024)
        }
    }
}

/** Small high-value matrix; the printed seed identifies a reproducible fragment shape. */
internal suspend fun forEachWireDelivery(block: suspend (WireDelivery) -> Unit) {
    for (delivery in listOf(WireDelivery.Exact, WireDelivery.Fragmented(seed = 138), WireDelivery.Coalesced())) {
        println("Wire delivery: $delivery")
        block(delivery)
    }
}

internal fun runWireTest(block: suspend TestScope.(WireDelivery) -> Unit) = runTest {
    forEachWireDelivery { block(it) }
}

internal fun runWireBlocking(block: suspend CoroutineScope.(WireDelivery) -> Unit) = runBlocking {
    forEachWireDelivery { block(it) }
}

internal fun deliverRawBytes(receive: ReceiveChannel<ByteArray>, delivery: WireDelivery): Flow<ByteArray> = flow {
    when (delivery) {
        WireDelivery.Exact -> for (bytes in receive) emit(bytes)
        is WireDelivery.Fragmented -> {
            val random = Random(delivery.seed)
            for (bytes in receive) {
                if (bytes.isEmpty()) emit(bytes)
                var offset = 0
                while (offset < bytes.size) {
                    val count = random.nextInt(1, minOf(delivery.maxFragmentBytes, bytes.size - offset) + 1)
                    emit(bytes.copyOfRange(offset, offset + count))
                    offset += count
                }
            }
        }
        is WireDelivery.Coalesced -> {
            var pending: ByteArray? = null
            var pendingOffset = 0
            while (true) {
                var bytes = pending ?: receive.receiveCatching().let { result ->
                    result.exceptionOrNull()?.let { throw it }
                    result.getOrNull()
                } ?: break
                var offset = pendingOffset
                pending = null
                pendingOffset = 0
                val batch = ByteArray(delivery.maxReadBytes)
                var size = 0
                var writes = 0
                while (true) {
                    val count = minOf(bytes.size - offset, batch.size - size)
                    bytes.copyInto(batch, size, offset, offset + count)
                    size += count
                    offset += count
                    if (offset < bytes.size) {
                        pending = bytes
                        pendingOffset = offset
                        break
                    }
                    writes += 1
                    if (size == batch.size || writes == delivery.maxWritesPerRead) break
                    bytes = receive.tryReceive().getOrNull() ?: break
                    offset = 0
                }
                emit(if (size == batch.size) batch else batch.copyOf(size))
            }
        }
    }
}
