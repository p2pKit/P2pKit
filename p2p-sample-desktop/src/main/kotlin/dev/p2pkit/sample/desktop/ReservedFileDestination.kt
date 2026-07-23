package dev.p2pkit.sample.desktop

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
internal fun cleanupStaleTransferPartsOnce(directory: File) {
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
 * The core helper preserves existing targets on abort; this wrapper removes
 * only the sample-owned reservation after the helper has cleaned its partial
 * file.
 */
internal fun reservedFileDestination(target: File): FileTransferDestination =
    ReservedFileDestination(target, durableFileDestination(target))

private class ReservedFileDestination(
    private val target: File,
    private val delegate: FileTransferDestination
) : FileTransferDestination {
    private val terminalLock = Mutex()
    private var state = State.ACTIVE

    override fun openSink(): RawSink = delegate.openSink()

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
            try {
                delegate.abort(cause)
            } finally {
                state = State.ABORTED
                if (target.exists() && !target.delete()) {
                    throw IOException("Could not remove aborted destination ${target.absolutePath}")
                }
            }
        }
    }

    private enum class State { ACTIVE, COMMITTED, ABORTED }
}
