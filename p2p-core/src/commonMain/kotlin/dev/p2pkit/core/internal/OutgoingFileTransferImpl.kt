package dev.p2pkit.core.internal

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.Peer
import dev.p2pkit.core.protocol.MessageId
import dev.p2pkit.core.transfer.FileTransferState
import dev.p2pkit.core.transfer.P2pFileTransfer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.io.RawSource

/**
 * Internal handle for an outgoing file transfer. Created by
 * [FileTransferDispatcher.sendFile]; mutated by the dispatcher as state
 * transitions happen. The public surface is the [P2pFileTransfer] interface.
 *
 * State transitions are guarded by the dispatcher's lock — direct callers of
 * [setState] / [recordBytesSent] are expected to hold it.
 */
internal class OutgoingFileTransferImpl(
    override val peer: Peer,
    override val name: String,
    override val sizeBytes: Long,
    override val mimeType: String?,
    val transferId: MessageId,
    val source: RawSource,
    private val dispatcher: FileTransferDispatcher
) : P2pFileTransfer {

    override val id: String = transferId.toString()

    private val _state = MutableStateFlow<FileTransferState>(FileTransferState.Offered)
    override val state: StateFlow<FileTransferState> = _state.asStateFlow()

    private val _bytes = MutableStateFlow(0L)
    override val bytesTransferred: StateFlow<Long> = _bytes.asStateFlow()

    override suspend fun cancel(reason: String?) {
        dispatcher.cancelOutgoing(this, reason)
    }

    internal fun setState(newState: FileTransferState) {
        _state.value = newState
    }

    internal fun recordBytesSent(delta: Int) {
        val total = _bytes.updateAndGet { it + delta }
        if (sizeBytes > 0) {
            val progress = (total.toDouble() / sizeBytes.toDouble()).coerceIn(0.0, 1.0).toFloat()
            _state.value = FileTransferState.Sending(progress)
        }
    }

    internal fun markFailed(error: P2pError) {
        _state.value = FileTransferState.Failed(error)
    }
}

private inline fun MutableStateFlow<Long>.updateAndGet(transform: (Long) -> Long): Long {
    while (true) {
        val current = value
        val next = transform(current)
        if (compareAndSet(current, next)) return next
    }
}
