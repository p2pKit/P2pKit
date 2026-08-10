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
 * atomic three-state latch so terminal cleanup never needs the dispatcher's
 * global ownership lock. In particular, terminalization can win while a
 * caller-controlled [PreparedFileSource.open] is still running: the late
 * source is then closed instead of being installed into a terminal handle.
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
    private val sourceOwnership = MutableStateFlow<SourceOwnership>(
        source?.let(SourceOwnership::Owned) ?: SourceOwnership.Deferred
    )

    internal fun closeSourceOnce() {
        while (true) {
            when (val current = sourceOwnership.value) {
                SourceOwnership.Deferred -> {
                    if (sourceOwnership.compareAndSet(current, SourceOwnership.Released)) return
                }
                is SourceOwnership.Owned -> {
                    if (sourceOwnership.compareAndSet(current, SourceOwnership.Released)) {
                        runCatching { current.source.close() }
                        return
                    }
                }
                SourceOwnership.Released -> return
            }
        }
    }

    internal fun sourceOrThrow(): RawSource =
        (sourceOwnership.value as? SourceOwnership.Owned)?.source
            ?: throw IllegalStateException("Transfer $id no longer owns its source")

    internal fun openPreparedSource(): RawSource {
        val prepared = checkNotNull(preparedSource) { "Transfer $id has no prepared source" }
        check(sourceOwnership.value === SourceOwnership.Deferred) {
            "Transfer $id source is already open or released"
        }
        val opened = prepared.open()
        val owned = SourceOwnership.Owned(opened)
        if (!sourceOwnership.compareAndSet(SourceOwnership.Deferred, owned)) {
            val failure = IllegalStateException(
                "Transfer $id became terminal or opened concurrently while its prepared source was opening"
            )
            try {
                opened.close()
            } catch (cleanupFailure: Throwable) {
                failure.addSuppressed(cleanupFailure)
            }
            throw failure
        }
        return opened
    }

    internal fun retainsSource(): Boolean = sourceOwnership.value is SourceOwnership.Owned

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

    private sealed interface SourceOwnership {
        data object Deferred : SourceOwnership
        class Owned(val source: RawSource) : SourceOwnership
        data object Released : SourceOwnership
    }
}
