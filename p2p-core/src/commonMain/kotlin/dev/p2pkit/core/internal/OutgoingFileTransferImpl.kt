package dev.p2pkit.core.internal

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.Peer
import dev.p2pkit.core.protocol.MessageId
import dev.p2pkit.core.transfer.PreparedFileSource
import dev.p2pkit.core.transfer.Sha256Digest
import dev.p2pkit.core.transfer.FileTransferState
import dev.p2pkit.core.transfer.P2pFileTransfer
import dev.p2pkit.core.transfer.isTerminal
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.io.RawSource

/**
 * Internal handle for an outgoing file transfer. Created by
 * [FileTransferDispatcher.sendFile]; mutated by the dispatcher as state
 * transitions happen. The public surface is the [P2pFileTransfer] interface.
 *
 * State/progress transitions use a per-transfer mutex. Source ownership is an
 * atomic nullable reference so terminal cleanup never needs the dispatcher's
 * global ownership lock and the terminal handle cannot retain the source.
 */
internal class OutgoingFileTransferImpl(
    override val peer: Peer,
    override val name: String,
    override val sizeBytes: Long,
    override val mimeType: String?,
    val transferId: MessageId,
    source: RawSource?,
    internal val preparedSource: PreparedFileSource? = null,
    internal val expectedDigest: Sha256Digest? = null,
    internal val offerHash: Sha256Digest? = null,
    private val dispatcher: FileTransferDispatcher
) : P2pFileTransfer {

    override val id: String = transferId.toString()

    private val _state = MutableStateFlow<FileTransferState>(FileTransferState.Offered)
    override val state: StateFlow<FileTransferState> = _state.asStateFlow()

    private val _bytes = MutableStateFlow(0L)
    override val bytesTransferred: StateFlow<Long> = _bytes.asStateFlow()

    private val lifecycleLock = Mutex()
    private val sourceRef = MutableStateFlow<RawSource?>(source)

    internal fun closeSourceOnce() {
        while (true) {
            val owned = sourceRef.value ?: return
            if (sourceRef.compareAndSet(owned, null)) {
                runCatching { owned.close() }
                return
            }
        }
    }

    internal fun sourceOrThrow(): RawSource =
        sourceRef.value ?: throw IllegalStateException("Transfer $id no longer owns its source")

    internal fun openPreparedSource(): RawSource {
        val prepared = checkNotNull(preparedSource) { "Transfer $id has no prepared source" }
        check(sourceRef.value == null) { "Transfer $id source is already open" }
        val opened = prepared.open()
        if (!sourceRef.compareAndSet(null, opened)) {
            runCatching { opened.close() }
            throw IllegalStateException("Transfer $id source was opened concurrently")
        }
        return opened
    }

    internal fun retainsSource(): Boolean = sourceRef.value != null

    override suspend fun cancel(reason: String?) {
        dispatcher.cancelOutgoing(this, reason)
    }

    internal suspend fun setState(newState: FileTransferState): Boolean {
        val changed = lifecycleLock.withLock {
            if (_state.value.isTerminal()) return@withLock false
            _state.value = newState
            true
        }
        if (changed && newState.isTerminal()) closeSourceOnce()
        return changed
    }

    internal suspend fun recordBytesSent(delta: Int): Boolean = lifecycleLock.withLock {
        if (_state.value.isTerminal()) return@withLock false
        val total = _bytes.value + delta.toLong()
        _bytes.value = total
        if (sizeBytes > 0L) {
            val progress = (total.toDouble() / sizeBytes.toDouble()).coerceIn(0.0, 1.0).toFloat()
            _state.value = FileTransferState.Sending(progress)
        }
        true
    }

    internal suspend fun markFailed(error: P2pError): Boolean =
        setState(FileTransferState.Failed(error))
}
