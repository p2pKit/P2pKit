package dev.p2pkit.core.transfer

import dev.p2pkit.core.P2pError
import kotlinx.io.RawSink
import kotlinx.io.RawSource

/**
 * Repeatable, pre-hashed source for authenticated file transfer.
 *
 * [open] must return a new source positioned at byte zero on every call. The
 * SDK owns and closes the returned source. It requires the source to end
 * immediately after exactly [sizeBytes] bytes and verifies their SHA-256
 * against [sha256] while streaming. Early EOF, trailing bytes, or a digest
 * change after preparation therefore fails with `SOURCE_CHANGED` instead of
 * being committed.
 * The SDK snapshots [sizeBytes] and [sha256] while registering the offer and
 * does not call [open] unless the remote peer accepts. Both snapshot getters
 * must be immutable and return promptly; the SDK reads them together on an
 * independently owned worker bounded by `offerTimeoutMillis`.
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
     * This non-suspending callback should return promptly. The SDK invokes it
     * on an independently owned worker and enforces `offerTimeoutMillis`; a
     * source returned after that deadline is closed and is never streamed.
     * The returned source's `close()` should also return promptly. Terminal
     * close is independently bounded; a broken close that ignores interruption
     * can finish after the public transfer is already terminal, but the SDK
     * detaches the source from the handle and closes it at most once.
     */
    public fun open(): RawSource
}

/**
 * Transactional destination for authenticated file transfer.
 *
 * [openSink] is called once after the offer has been accepted. The SDK writes
 * and hashes the offered bytes, flushes its buffer, verifies the digest, and
 * then calls [commit]. A durable implementation closes/fsyncs its temporary
 * file and atomically publishes it before returning from [commit], applying
 * any additional durability barrier its platform exposes. Only then does the
 * protocol acknowledge success to the sender. Platform factories document
 * limitations where an operating-system barrier is unavailable.
 *
 * [commit] and [abort] are suspending and must not return until their resource
 * work is complete. [abort] is called when an accepted transfer fails or is
 * cancelled before commit. Implementations should close and remove partial
 * state. Both terminal methods must be idempotent and safe when they race,
 * because a deadline, remote terminal event, and an already-running commit
 * can overlap. Once publication begins, cancellation must not leave an
 * ambiguous half-published result: finish the atomic publish and the
 * platform-supported durability work or throw a storage failure.
 *
 * The SDK bounds open/commit/abort waits on independently owned workers. A
 * callback that ignores cancellation therefore cannot freeze the protocol or
 * session lifecycle, but its platform work can finish after the transfer is
 * already `Failed`. `abort` can begin while a non-cooperative `openSink` or
 * `commit` invocation is still unwinding, so implementations must serialize
 * all three methods around one coherent ownership state. In particular, an
 * atomic publish that crossed its point of no return can leave a fully durable
 * target after a reported commit timeout; it must never leave a partially
 * published target. Applications should use transfer-unique destinations and
 * retain timeout diagnostics when reconciling such a late durable result.
 */
public interface FileTransferDestination {
    /**
     * Open the single staging sink owned by this destination.
     *
     * The SDK writes through the returned sink but never exposes it elsewhere.
     * The destination must close it during [commit] or [abort]. Repeated calls
     * must fail. This non-suspending callback should return promptly. If it
     * returns after the acceptance deadline, the SDK aborts the destination
     * and never installs the sink.
     */
    public fun openSink(): RawSink

    /**
     * Durably publish the verified staging content.
     *
     * Returning means the destination survived the implementation's promised
     * durability boundary. Repeated calls after success must be harmless.
     * Cooperate with cancellation before publication starts; after the atomic
     * publish point, complete durability or report a storage failure.
     */
    public suspend fun commit()

    /**
     * Close and remove uncommitted staging state.
     *
     * [cause] is the typed terminal failure when one exists. Repeated calls,
     * including calls after a successful [commit], must be harmless. If
     * resource cleanup fails, the implementation must propagate that failure
     * and retain ownership of only the work that did not complete. A later
     * call retries the incomplete cleanup; [openSink] and [commit] must remain
     * terminally unavailable once abort has begun.
     */
    public suspend fun abort(cause: P2pError.FileTransferFailed?)
}

/**
 * Internal capability implemented by the built-in durable destinations.
 *
 * A [FileTransferDestination] cannot generally identify its backing storage,
 * so application-defined destinations retain responsibility for their own
 * quota policy. The dispatcher invokes this capability, when present, before
 * it opens the staging sink for the offered byte count.
 */
internal interface StorageCapacityCheckingFileTransferDestination {
    /** Fail before opening the staging sink when [expectedSizeBytes] cannot fit safely. */
    fun requireAvailableStorage(expectedSizeBytes: Long)
}

internal const val DEFAULT_DURABLE_DESTINATION_MINIMUM_FREE_SPACE_BYTES: Long = 64L * 1024 * 1024

internal fun hasRequiredStorageCapacity(
    availableBytes: Long,
    expectedSizeBytes: Long,
    minimumFreeSpaceBytes: Long
): Boolean {
    require(expectedSizeBytes >= 0) { "expectedSizeBytes must be non-negative" }
    require(minimumFreeSpaceBytes >= 0) { "minimumFreeSpaceBytes must be non-negative" }
    if (availableBytes < 0) return false
    if (expectedSizeBytes > Long.MAX_VALUE - minimumFreeSpaceBytes) return false
    return availableBytes >= expectedSizeBytes + minimumFreeSpaceBytes
}
