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

/** Reconcile proven abandoned sample-owned staging; never sweep received filenames. */
public fun cleanupStaleTransferPartsOnce(directory: File): Unit =
    cleanupStaleTransferPartsOnce(directory, ::isPlainJvmStagingPath)

/** Android supplies an API24-compatible no-follow inspector, not the JVM adapter. */
public fun cleanupStaleTransferPartsOnce(directory: File, isPlainPath: (File) -> Boolean) {
    val canonicalPath = directory.canonicalPath
    synchronized(cleanupMonitor) {
        if (!cleanedDirectories.add(canonicalPath)) return
        try {
            TransferStagingOwnership.reconcile(directory, isPlainPath)
        } catch (failure: Throwable) {
            cleanedDirectories.remove(canonicalPath)
            throw failure
        }
    }
}

/**
 * Owns a destination placeholder atomically claimed by [File.createNewFile].
 * Before commit starts, abort remains retryable until both the SDK partial and
 * the sample-owned reservation are gone. Once commit starts, the reservation
 * may already have become published data, so abort permanently relinquishes
 * authority to delete the target and cleans only delegate-owned staging state.
 */
public fun reservedFileDestination(target: File): FileTransferDestination =
    reservedFileDestination(target) { destination, staging ->
        durableFileDestination(destination, staging, 64L * 1024 * 1024)
    }

/**
 * Select the platform's durable destination without moving staging ownership to
 * that factory. Android supplies its own core facade rather than invoking the
 * JVM-only default above. The factory receives the already exclusively leased
 * staging directory and must use it until its writer closes on commit/abort.
 */
public fun reservedFileDestination(
    target: File,
    createDestination: (target: File, stagingDirectory: File) -> FileTransferDestination
): FileTransferDestination = reservedFileDestination(target, ::isPlainJvmStagingPath, createDestination)

/**
 * Select both platform adapters explicitly. [isPlainPath] must inspect every
 * original path component without following links, rejecting special entries
 * and non-directory ancestors. It is retained for terminal lease cleanup too.
 */
public fun reservedFileDestination(
    target: File,
    isPlainPath: (File) -> Boolean,
    createDestination: (target: File, stagingDirectory: File) -> FileTransferDestination
): FileTransferDestination {
    val lease = TransferStagingOwnership.claim(checkNotNull(target.absoluteFile.parentFile), isPlainPath)
    try {
        return RetainedReservedFileDestination(
            target,
            createDestination(target, lease.directory),
            lease
        )
    } catch (failure: Throwable) {
        try { lease.retire() } catch (cleanup: Throwable) { failure.addSuppressed(cleanup) }
        throw failure
    }
}

internal fun reservedFileDestination(
    target: File,
    delegate: FileTransferDestination
): FileTransferDestination = RetainedReservedFileDestination(target, delegate)

private class RetainedReservedFileDestination(
    private val target: File,
    private val delegate: FileTransferDestination,
    private val stagingLease: TransferStagingOwnership.Lease? = null
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
            check(state == State.ACTIVE || state == State.COMMITTING) {
                "Reserved destination is already aborted"
            }
            // The delegate may atomically replace the reservation and then
            // fail its durability barrier. From this point onward the target
            // may contain received data and must never be deleted by abort.
            state = State.COMMITTING
            delegate.commit()
            stagingLease?.retire()
            state = State.COMMITTED
        }
    }

    override suspend fun abort(cause: P2pError.FileTransferFailed?) {
        terminalLock.withLock {
            if (state == State.COMMITTED || state == State.ABORTED) return
            val removeReservation = when (state) {
                State.ACTIVE,
                State.ABORTING_RESERVATION -> true
                State.COMMITTING,
                State.ABORTING_AFTER_COMMIT -> false
                State.COMMITTED,
                State.ABORTED -> error("terminal destination state changed while locked")
            }
            state = if (removeReservation) State.ABORTING_RESERVATION else State.ABORTING_AFTER_COMMIT
            var failure: Throwable? = null
            try {
                delegate.abort(cause)
                stagingLease?.retire()
            } catch (error: Throwable) {
                failure = error
            }
            if (removeReservation && target.exists() && !target.delete()) {
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

    private enum class State {
        ACTIVE,
        COMMITTING,
        ABORTING_RESERVATION,
        ABORTING_AFTER_COMMIT,
        COMMITTED,
        ABORTED
    }
}
