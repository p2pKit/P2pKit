package dev.p2pkit.core.internal

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.Peer
import dev.p2pkit.core.protocol.MessageId
import dev.p2pkit.core.transfer.FileTransferState
import dev.p2pkit.core.transfer.P2pFileTransfer
import dev.p2pkit.core.transfer.isTerminal
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

    // AUDIT-2026-07 (FIL-1): close-once latch for [source]. The kit owns the
    // caller's RawSource (sendFile KDoc contract); the close used to be done
    // only by a watcher coroutine on the session scope, which session teardown
    // cancels before it can observe the terminal state — leaking the source.
    // The guaranteed close now runs synchronously at the transition INTO a
    // terminal state (every terminal path funnels through
    // [updateUnlessTerminal]); the watcher remains only as a backstop, and
    // both paths go through this idempotent guard.
    private val sourceClosed = MutableStateFlow(false)

    internal fun closeSourceOnce() {
        if (sourceClosed.compareAndSet(expect = false, update = true)) {
            runCatching { source.close() }
        }
    }

    override suspend fun cancel(reason: String?) {
        dispatcher.cancelOutgoing(this, reason)
    }

    internal fun setState(newState: FileTransferState) {
        // Terminal states are final: contending paths (offer timeout vs
        // FILE_ACCEPT, remote FILE_CANCEL vs streamer completion) must not
        // overwrite them — the KDoc'd lock discipline was never actually
        // applied by all callers (AUDIT-2026-06 fix).
        updateUnlessTerminal { newState }
    }

    internal fun recordBytesSent(delta: Int) {
        val total = _bytes.updateAndGet { it + delta }
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
            val candidate = next()
            if (_state.compareAndSet(cur, candidate)) {
                // AUDIT-2026-07 (FIL-1): the winning transition into a terminal
                // state is the one guaranteed-to-run cleanup point for the
                // source — it covers every terminal path (Completed / Rejected
                // / Cancelled / Failed, including closeAll's markFailed during
                // session teardown) and, unlike the watcher coroutine, cannot
                // be cancelled out from under the transfer.
                if (candidate.isTerminal()) closeSourceOnce()
                return
            }
        }
    }
}

private inline fun MutableStateFlow<Long>.updateAndGet(transform: (Long) -> Long): Long {
    while (true) {
        val current = value
        val next = transform(current)
        if (compareAndSet(current, next)) return next
    }
}
