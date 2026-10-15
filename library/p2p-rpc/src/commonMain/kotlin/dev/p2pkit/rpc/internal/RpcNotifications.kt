package dev.p2pkit.rpc.internal

import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.core.PayloadLease
import dev.p2pkit.rpc.RpcNotification
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Semaphore
import kotlinx.serialization.KSerializer

internal class RpcNotifications(
    scope: CoroutineScope,
    private val descriptors: Map<String, RpcNotification<*>>,
    private val budget: PayloadBudget,
    private val onDrop: () -> Unit,
) {
    private class Queued(val message: WireMessage, val allowance: PayloadLease)
    private val entries = Semaphore(16) // includes the active slow subscriber, not just buffered entries
    private val bytes = PayloadBudget(128L * 1024)
    private val flows = descriptors.mapValues { MutableSharedFlow<Any?>(replay = 0) }
    private val queue = Channel<Queued>(16, onUndeliveredElement = {
        it.message.release(); it.allowance.release(); entries.release()
    })

    private val worker = scope.launch {
        try {
            for (item in queue) {
                try {
                    val descriptor = checkNotNull(descriptors[item.message.key])
                    @Suppress("UNCHECKED_CAST")
                    val decoded = RpcBodyCodec.decode(descriptor.payload as KSerializer<Any?>,
                        checkNotNull(item.message.body), descriptor.limitBytes, budget)
                    flows.getValue(item.message.key).emit(decoded)
                } catch (cancelled: CancellationException) {
                    throw cancelled
                } catch (_: Exception) { onDrop() } finally {
                    item.message.release()
                    item.allowance.release()
                    entries.release()
                }
            }
        } finally { queue.cancel() }
    }

    fun offer(message: WireMessage) {
        val descriptor = descriptors[message.key]
        if (descriptor == null || message.body == null || message.body.size > descriptor.limitBytes ||
            !entries.tryAcquire()
        ) { onDrop(); return }
        val allowance = bytes.tryReserve(message.body.size.toLong())
        if (allowance == null) { entries.release(); onDrop(); return }
        val queued = Queued(message.retained(), allowance)
        if (queue.trySend(queued).isFailure) {
            queued.message.release()
            allowance.release()
            entries.release()
            onDrop()
        }
    }

    fun <T> flow(descriptor: RpcNotification<T>): Flow<T> {
        require(descriptors[descriptor.key] === descriptor) { "Register and reuse this notification descriptor" }
        @Suppress("UNCHECKED_CAST")
        return flows.getValue(descriptor.key).map { it as T }
    }

    fun close() {
        queue.cancel()
        worker.cancel()
    }
}
