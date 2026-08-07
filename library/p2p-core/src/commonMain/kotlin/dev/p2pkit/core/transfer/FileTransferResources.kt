package dev.p2pkit.core.transfer

import dev.p2pkit.core.P2pError
import kotlinx.io.RawSink
import kotlinx.io.RawSource

/**
 * Repeatable, pre-hashed source for authenticated file transfer.
 *
 * [open] must return a new source positioned at byte zero on every call. The
 * SDK owns and closes the returned source. It reads exactly [sizeBytes] bytes
 * and verifies their SHA-256 against [sha256] while streaming, so mutation
 * after preparation fails with `SOURCE_CHANGED` instead of being committed.
 * The SDK snapshots [sizeBytes] and [sha256] while registering the offer and
 * does not call [open] unless the remote peer accepts.
 */
public interface PreparedFileSource {
    /** Exact number of bytes returned by every successful [open] call. */
    public val sizeBytes: Long

    /** SHA-256 of the exact [sizeBytes] bytes returned by [open]. */
    public val sha256: Sha256Digest

    /**
     * Open a new source positioned at byte zero.
     *
     * The SDK calls this at most once for a transfer attempt and closes the
     * returned source. Implementations retain ownership of any backing file
     * or provider and must remain reopenable while the offer is pending.
     */
    public fun open(): RawSource
}

/**
 * Transactional destination for authenticated file transfer.
 *
 * [openSink] is called once after the offer has been accepted. The SDK writes
 * and hashes the offered bytes, flushes its buffer, verifies the digest, and
 * then calls [commit]. A durable implementation closes/fsyncs its temporary
 * file and atomically publishes it before returning from [commit]. Only then
 * does the protocol acknowledge success to the sender.
 *
 * [commit] and [abort] are suspending and must not return until their resource
 * work is complete. [abort] is called when an accepted transfer fails or is
 * cancelled before commit. Implementations should close and remove partial
 * state. Both terminal methods must be idempotent because process/platform
 * cleanup can race a remote terminal event. Once publication begins,
 * cancellation must not leave an ambiguous half-published result: finish the
 * atomic publish and directory durability work or throw a storage failure.
 */
public interface FileTransferDestination {
    /**
     * Open the single staging sink owned by this destination.
     *
     * The SDK writes through the returned sink but never exposes it elsewhere.
     * The destination must close it during [commit] or [abort]. Repeated calls
     * must fail.
     */
    public fun openSink(): RawSink

    /**
     * Durably publish the verified staging content.
     *
     * Returning means the destination survived the implementation's promised
     * durability boundary. Repeated calls after success must be harmless.
     */
    public suspend fun commit()

    /**
     * Close and remove uncommitted staging state.
     *
     * [cause] is the typed terminal failure when one exists. Repeated calls,
     * including calls after a successful [commit], must be harmless.
     */
    public suspend fun abort(cause: P2pError.FileTransferFailed?)
}
