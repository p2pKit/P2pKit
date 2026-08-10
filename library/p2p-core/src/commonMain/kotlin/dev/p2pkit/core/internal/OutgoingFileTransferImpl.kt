package dev.p2pkit.core.internal

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.Peer
import dev.p2pkit.core.protocol.MessageId
import dev.p2pkit.core.transfer.FileTransferState
import dev.p2pkit.core.transfer.P2pFileTransfer
import dev.p2pkit.core.transfer.PreparedFileSource
import dev.p2pkit.core.transfer.Sha256Digest
import dev.p2pkit.core.transfer.isTerminal
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.io.RawSource

/**
 * Internal handle for an outgoing file transfer. Created by
 * [FileTransferDispatcher.sendFile]; mutated by the dispatcher as state
 * transitions happen. The public surface is the [P2pFileTransfer] interface.
 *
 * State/progress transitions use a per-transfer mutex. Source ownership is an
 * atomic ownership latch so terminal cleanup never needs the dispatcher's
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
    preparedSource: PreparedFileSource? = null,
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
        source?.let(SourceOwnership::Owned)
            ?: preparedSource?.let(SourceOwnership::Deferred)
            ?: SourceOwnership.Released
    )

    private fun takeSourceForClose(): RawSource? {
        while (true) {
            when (val current = sourceOwnership.value) {
                is SourceOwnership.Deferred,
                SourceOwnership.Opening -> {
                    if (sourceOwnership.compareAndSet(current, SourceOwnership.Released)) return null
                }
                is SourceOwnership.Owned -> {
                    if (sourceOwnership.compareAndSet(current, SourceOwnership.Released)) {
                        return current.source
                    }
                }
                SourceOwnership.Released -> return null
            }
        }
    }

    /** Synchronous ownership-race hook used by the direct latch regression. */
    internal fun closeSourceOnce() {
        takeSourceForClose()?.let { runCatching { it.close() } }
    }

    internal fun sourceOrThrow(): RawSource =
        (sourceOwnership.value as? SourceOwnership.Owned)?.source
            ?: throw IllegalStateException("Transfer $id no longer owns its source")

    internal fun createPreparedSource(): RawSource {
        val deferred = sourceOwnership.value as? SourceOwnership.Deferred
            ?: throw IllegalStateException("Transfer $id has no deferred prepared source")
        check(sourceOwnership.compareAndSet(deferred, SourceOwnership.Opening)) {
            "Transfer $id source is already open or released"
        }
        return try {
            deferred.prepared.open()
        } catch (failure: Throwable) {
            sourceOwnership.compareAndSet(SourceOwnership.Opening, SourceOwnership.Released)
            throw failure
        }
    }

    internal suspend fun installPreparedSource(opened: RawSource): RawSource {
        val owned = SourceOwnership.Owned(opened)
        if (!sourceOwnership.compareAndSet(SourceOwnership.Opening, owned)) {
            val failure = IllegalStateException(
                "Transfer $id became terminal or opened concurrently while its prepared source was opening"
            )
            withContext(NonCancellable) {
                dispatcher.cleanupOutgoingSource(
                    opened,
                    "prepared source returned after terminal transfer $id"
                )
            }
            throw failure
        }
        return opened
    }

    internal suspend fun openPreparedSource(): RawSource =
        installPreparedSource(createPreparedSource())

    internal fun retainsSource(): Boolean = sourceOwnership.value is SourceOwnership.Owned

    internal fun retainsPreparedSource(): Boolean = sourceOwnership.value is SourceOwnership.Deferred

    internal fun detachSourceAfterStreaming(): RawSource? = takeSourceForClose()

    override suspend fun cancel(reason: String?) {
        dispatcher.cancelOutgoing(this, reason)
    }

    internal suspend fun setState(newState: FileTransferState): Boolean {
        if (newState.isTerminal()) {
            val resources = transitionTerminalWithoutCleanup(newState) ?: return false
            resources.source?.let { source ->
                withContext(NonCancellable) {
                    dispatcher.cleanupOutgoingSource(source, "terminal outgoing transfer $id")
                }
            }
            return true
        }
        val changed = lifecycleLock.withLock {
            if (_state.value.isTerminal()) return@withLock false
            _state.value = newState
            true
        }
        return changed
    }

    internal suspend fun transitionTerminalWithoutCleanup(
        newState: FileTransferState
    ): OutgoingTerminalResources? {
        check(newState.isTerminal()) { "transitionTerminalWithoutCleanup requires a terminal state" }
        val changed = lifecycleLock.withLock {
            if (_state.value.isTerminal()) return@withLock false
            _state.value = newState
            true
        }
        return if (changed) OutgoingTerminalResources(takeSourceForClose()) else null
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
        class Deferred(val prepared: PreparedFileSource) : SourceOwnership
        data object Opening : SourceOwnership
        class Owned(val source: RawSource) : SourceOwnership
        data object Released : SourceOwnership
    }
}

internal data class OutgoingTerminalResources(val source: RawSource?)
