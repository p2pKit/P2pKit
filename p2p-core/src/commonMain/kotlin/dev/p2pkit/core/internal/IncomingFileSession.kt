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
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.io.RawSink

/**
 * Internal session that holds the state for one incoming file transfer. The
 * same instance is published to the app first as [P2pFileOffer] (before
 * `accept`) and then as [P2pFileTransfer] (after `accept`); the state flow
 * survives the transition so observers see one continuous lifecycle.
 *
 * `accept` returns `this` cast to [P2pFileTransfer]. A per-transfer mutex
 * serializes sink write/finalize/abort and the associated progress/state
 * commits. The dispatcher map lock is deliberately never held across these
 * operations because the sink is application-controlled I/O.
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

    private val operationLock = Mutex()

    @Volatile
    private var receiver: StreamingFileReceiver? = null

    override suspend fun accept(sink: RawSink): P2pFileTransfer = dispatcher.acceptOffer(this, sink)

    override suspend fun reject(reason: String?) {
        dispatcher.rejectOffer(this, reason)
    }

    override suspend fun cancel(reason: String?) {
        dispatcher.cancelIncoming(this, reason)
    }

    internal suspend fun installReceiver(sink: RawSink): Boolean = operationLock.withLock {
        if (_state.value.isTerminal()) return@withLock false
        check(receiver == null) { "Offer $id already owns a receiver" }
        receiver = StreamingFileReceiver(transferId, sizeBytes, sink)
        _state.value = FileTransferState.Accepted
        true
    }

    /** Returns null when a terminal transition already won the race. */
    internal suspend fun acceptData(frame: dev.p2pkit.core.protocol.Frame): Long? = operationLock.withLock {
        if (_state.value.isTerminal()) return@withLock null
        val ownedReceiver = receiver
            ?: throw P2pError.ProtocolError("FILE_DATA for $transferId arrived before acceptance committed")
        val total = ownedReceiver.acceptDataChunk(frame)
        _bytes.value = total
        if (sizeBytes > 0L) {
            val progress = (total.toDouble() / sizeBytes.toDouble()).coerceIn(0.0, 1.0).toFloat()
            _state.value = FileTransferState.Sending(progress)
        }
        total
    }

    /** Flush and complete under the same gate used by writes and abort. */
    internal suspend fun finishReceiver(): Boolean = operationLock.withLock {
        if (_state.value.isTerminal()) return@withLock false
        val ownedReceiver = receiver
            ?: throw P2pError.ProtocolError("FILE_DONE for $transferId arrived before acceptance committed")
        ownedReceiver.finish()
        receiver = null
        _state.value = FileTransferState.Completed
        true
    }

    internal suspend fun setState(newState: FileTransferState): Boolean = operationLock.withLock {
        if (_state.value.isTerminal()) return@withLock false
        _state.value = newState
        if (newState.isTerminal()) {
            receiver?.abort()
            receiver = null
        }
        true
    }

    internal suspend fun markFailed(error: P2pError): Boolean =
        setState(FileTransferState.Failed(error))

    internal fun retainsReceiver(): Boolean = receiver != null
}
