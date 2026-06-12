package dev.p2pkit.core.internal

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.Peer
import dev.p2pkit.core.protocol.MessageId
import dev.p2pkit.core.protocol.StreamingFileReceiver
import dev.p2pkit.core.transfer.FileTransferState
import dev.p2pkit.core.transfer.isTerminal
import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.core.transfer.P2pFileTransfer
import kotlin.concurrent.Volatile
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.io.RawSink

/**
 * Internal session that holds the state for one incoming file transfer. The
 * same instance is published to the app first as [P2pFileOffer] (before
 * `accept`) and then as [P2pFileTransfer] (after `accept`); the state flow
 * survives the transition so observers see one continuous lifecycle.
 *
 * `accept` returns `this` cast to [P2pFileTransfer]. The dispatcher's lock
 * serializes [setReceiver] / [setState] / [recordBytesReceived] calls.
 */
internal class IncomingFileSession(
    override val peer: Peer,
    override val name: String,
    override val sizeBytes: Long,
    override val mimeType: String?,
    val transferId: MessageId,
    private val dispatcher: FileTransferDispatcher
) : P2pFileOffer, P2pFileTransfer {

    override val id: String = transferId.toString()

    private val _state = MutableStateFlow<FileTransferState>(FileTransferState.Offered)
    override val state: StateFlow<FileTransferState> = _state.asStateFlow()

    private val _bytes = MutableStateFlow(0L)
    override val bytesTransferred: StateFlow<Long> = _bytes.asStateFlow()

    @Volatile
    internal var receiver: StreamingFileReceiver? = null
        private set

    override suspend fun accept(sink: RawSink): P2pFileTransfer = dispatcher.acceptOffer(this, sink)

    override suspend fun reject(reason: String?) {
        dispatcher.rejectOffer(this, reason)
    }

    override suspend fun cancel(reason: String?) {
        dispatcher.cancelIncoming(this, reason)
    }

    internal fun setReceiver(r: StreamingFileReceiver) {
        receiver = r
    }

    internal fun setState(newState: FileTransferState) {
        // Terminal states are final — see OutgoingFileTransferImpl
        // (AUDIT-2026-06 fix).
        updateUnlessTerminal { newState }
    }

    internal fun recordBytesReceived(total: Long) {
        _bytes.value = total
        if (sizeBytes > 0) {
            val progress = (total.toDouble() / sizeBytes.toDouble()).coerceIn(0.0, 1.0).toFloat()
            updateUnlessTerminal { FileTransferState.Sending(progress) }
        }
    }

    internal fun markFailed(error: P2pError) {
        updateUnlessTerminal { FileTransferState.Failed(error) }
    }

    private inline fun updateUnlessTerminal(next: () -> FileTransferState) {
        while (true) {
            val cur = _state.value
            if (cur.isTerminal()) return
            if (_state.compareAndSet(cur, next())) return
        }
    }
}
