package dev.p2pkit.sample.diagnostics

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.transfer.FileTransferDestination
import dev.p2pkit.core.transfer.durableFileDestination
import java.io.File
import java.io.IOException
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.io.RawSink

private val cleanupMonitor = Any()
private val cleanedDirectories: MutableSet<String> = mutableSetOf()

/** Remove crash-left SDK part files before this process starts a transfer in [directory]. */
public fun cleanupStaleTransferPartsOnce(directory: File) {
    val canonicalPath = directory.canonicalPath
    synchronized(cleanupMonitor) {
        if (!cleanedDirectories.add(canonicalPath)) return
        try {
            directory.listFiles()
                .orEmpty()
                .filter { it.isFile && it.name.startsWith(".p2pkit-") && it.name.endsWith(".part") }
                .forEach { part ->
                    if (!part.delete()) {
                        throw IOException("Could not remove stale transfer part ${part.absolutePath}")
                    }
                }
        } catch (failure: Throwable) {
            cleanedDirectories.remove(canonicalPath)
            throw failure
        }
    }
}

/**
 * Owns a destination placeholder atomically claimed by [File.createNewFile].
 * Abort remains retryable until both the SDK partial and the sample-owned
 * reservation are gone; a cleanup error is never converted into false
 * terminal success.
 */
public fun reservedFileDestination(target: File): FileTransferDestination =
    RetainedReservedFileDestination(target, durableFileDestination(target))

internal fun reservedFileDestination(
    target: File,
    delegate: FileTransferDestination
): FileTransferDestination = RetainedReservedFileDestination(target, delegate)

private class RetainedReservedFileDestination(
    private val target: File,
    private val delegate: FileTransferDestination
) : FileTransferDestination {
    private val terminalLock = Mutex()
    @Volatile
    private var state = State.ACTIVE

    override fun openSink(): RawSink {
        check(state == State.ACTIVE) { "Reserved destination is no longer writable" }
        return delegate.openSink()
    }

    override suspend fun commit() {
        terminalLock.withLock {
            if (state == State.COMMITTED) return
            check(state == State.ACTIVE) { "Reserved destination is already aborted" }
            delegate.commit()
            state = State.COMMITTED
        }
    }

    override suspend fun abort(cause: P2pError.FileTransferFailed?) {
        terminalLock.withLock {
            if (state == State.COMMITTED || state == State.ABORTED) return
            check(state == State.ACTIVE || state == State.ABORTING)
            state = State.ABORTING
            var failure: Throwable? = null
            try {
                delegate.abort(cause)
            } catch (error: Throwable) {
                failure = error
            }
            if (target.exists() && !target.delete()) {
                val deletion = IOException("Could not remove aborted destination ${target.absolutePath}")
                if (failure == null) failure = deletion else failure.addSuppressed(deletion)
            }
            if (failure == null) {
                state = State.ABORTED
            } else {
                // The delegate's abort contract is retryable after incomplete
                // cleanup. Keep this wrapper active for the same reason.
                throw failure
            }
        }
    }

    private enum class State { ACTIVE, ABORTING, COMMITTED, ABORTED }
}
