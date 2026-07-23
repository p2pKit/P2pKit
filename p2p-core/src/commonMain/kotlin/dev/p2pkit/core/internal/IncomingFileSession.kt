package dev.p2pkit.core.internal

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.Peer
import dev.p2pkit.core.protocol.MessageId
import dev.p2pkit.core.protocol.SecureFileFinish
import dev.p2pkit.core.protocol.SecureFileOffer
import dev.p2pkit.core.protocol.StreamingFileReceiver
import dev.p2pkit.core.transfer.FileTransferDestination
import dev.p2pkit.core.transfer.FileTransferState
import dev.p2pkit.core.transfer.isTerminal
import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.core.transfer.P2pFileTransfer
import kotlin.concurrent.Volatile
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.CancellationException
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
    internal val secureOffer: SecureFileOffer? = null,
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

    @Volatile
    private var destination: FileTransferDestination? = null

    @Deprecated("Legacy flush-only transfer; use accept(FileTransferDestination)")
    override suspend fun accept(sink: RawSink): P2pFileTransfer = dispatcher.acceptOffer(this, sink)

    override suspend fun accept(destination: FileTransferDestination): P2pFileTransfer =
        dispatcher.acceptOffer(this, destination)

    override suspend fun reject(reason: String?) {
        dispatcher.rejectOffer(this, reason)
    }

    override suspend fun cancel(reason: String?) {
        dispatcher.cancelIncoming(this, reason)
    }

    internal suspend fun installReceiver(
        sink: RawSink,
        destination: FileTransferDestination? = null
    ): Boolean = operationLock.withLock {
        if (_state.value.isTerminal()) return@withLock false
        check(receiver == null) { "Offer $id already owns a receiver" }
        receiver = StreamingFileReceiver(transferId, sizeBytes, sink)
        this.destination = destination
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
    internal suspend fun finishLegacyReceiver(): Boolean = operationLock.withLock {
        if (_state.value.isTerminal()) return@withLock false
        val ownedReceiver = receiver
            ?: throw P2pError.ProtocolError("FILE_DONE for $transferId arrived before acceptance committed")
        ownedReceiver.finish()
        receiver = null
        _state.value = FileTransferState.Completed
        true
    }

    internal suspend fun verifyAndCommit(finish: SecureFileFinish): Boolean {
        operationLock.lock()
        try {
            if (_state.value.isTerminal()) return false
            val offer = secureOffer
                ?: throw P2pError.ProtocolError("FILE_FINISH received for a legacy offer")
            val ownedReceiver = receiver
                ?: throw P2pError.ProtocolError("FILE_FINISH for $transferId arrived before acceptance")
            if (finish.sizeBytes != sizeBytes || finish.contentDigest != offer.contentDigest ||
                finish.offerHash != offer.offerHash
            ) {
                throw P2pError.ProtocolError("FILE_FINISH does not match the authenticated offer")
            }
            val summary = ownedReceiver.prepareFinish()
            if (summary.sizeBytes != finish.sizeBytes || summary.chunkCount != finish.chunkCount) {
                throw P2pError.ProtocolError("FILE_FINISH byte/chunk totals do not match received data")
            }
            if (summary.contentDigest != finish.contentDigest) {
                throw P2pError.FileTransferFailed(
                    kind = dev.p2pkit.core.FileTransferFailureKind.INTEGRITY,
                    phase = dev.p2pkit.core.FileTransferPhase.VERIFY,
                    retryability = dev.p2pkit.core.Retryability.NOT_RETRYABLE,
                    transferId = id,
                    reason = "Received file SHA-256 does not match the authenticated offer"
                )
            }
            try {
                ownedReceiver.flushPrepared()
            } catch (e: CancellationException) {
                throw e
            } catch (e: Throwable) {
                throw P2pError.FileTransferFailed(
                    kind = dev.p2pkit.core.FileTransferFailureKind.STORAGE,
                    phase = dev.p2pkit.core.FileTransferPhase.FLUSH,
                    retryability = dev.p2pkit.core.Retryability.RETRY_AFTER_USER_ACTION,
                    transferId = id,
                    reason = "Receiver flush failed: ${e.message ?: e::class.simpleName}"
                ).also { it.underlying = e }
            }
            val ownedDestination = destination
                ?: throw P2pError.ProtocolError("Secure transfer has no transactional destination")
            try {
                ownedDestination.commit()
            } catch (e: CancellationException) {
                throw e
            } catch (e: Throwable) {
                throw P2pError.FileTransferFailed(
                    kind = dev.p2pkit.core.FileTransferFailureKind.STORAGE,
                    phase = dev.p2pkit.core.FileTransferPhase.DURABLE_COMMIT,
                    retryability = dev.p2pkit.core.Retryability.RETRY_AFTER_USER_ACTION,
                    transferId = id,
                    reason = "Receiver durable commit failed: ${e.message ?: e::class.simpleName}"
                ).also { it.underlying = e }
            }
            receiver = null
            destination = null
            _state.value = FileTransferState.Completed
            return true
        } finally {
            operationLock.unlock()
        }
    }

    internal suspend fun setState(newState: FileTransferState): Boolean {
        var destinationToAbort: FileTransferDestination? = null
        val changed = operationLock.withLock {
            if (_state.value.isTerminal()) return@withLock false
            _state.value = newState
            if (newState.isTerminal()) {
                receiver?.abort()
                receiver = null
                destinationToAbort = destination
                destination = null
            }
            true
        }
        if (changed) {
            try {
                destinationToAbort?.abort(
                    (newState as? FileTransferState.Failed)?.error as? P2pError.FileTransferFailed
                )
            } catch (e: CancellationException) {
                throw e
            } catch (_: Throwable) {
                // The transfer is already terminal and ownership was cleared.
                // Cleanup failure must not suppress the authenticated result.
            }
        }
        return changed
    }

    internal suspend fun markFailed(error: P2pError): Boolean =
        setState(FileTransferState.Failed(error))

    internal fun retainsReceiver(): Boolean = receiver != null
}
