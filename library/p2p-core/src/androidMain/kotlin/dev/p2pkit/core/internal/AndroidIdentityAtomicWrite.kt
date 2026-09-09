package dev.p2pkit.core.internal

import android.system.Os
import android.system.OsConstants
import dev.p2pkit.core.LocalIdentityFailureKind
import dev.p2pkit.core.LocalIdentityRecovery
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.security.localIdentityError
import java.io.File
import java.io.FileDescriptor
import java.io.FileOutputStream
import kotlinx.coroutines.CancellationException

/**
 * Check the content barrier before AtomicFile publication, then attempt the
 * directory barrier without undoing a published identity. AtomicFile's own
 * sync failures are not reliably propagated on every supported Android API.
 *
 * [onCommitted] transfers publication ownership before any directory work.
 * Its only production caller marks the blob committed so even cancellation
 * after publication cannot trigger first-creation blob/Keystore cleanup.
 * Best-effort directory sync is not a power-loss or Keystore transaction guarantee.
 */
internal fun writeAndroidIdentityAtomic(
    bytes: ByteArray,
    startWrite: () -> FileOutputStream,
    finishWrite: (FileOutputStream) -> Unit,
    failWrite: (FileOutputStream) -> Unit,
    syncDirectory: () -> Unit,
    logger: P2pLogger,
    onCommitted: () -> Unit = {},
    syncFile: (FileOutputStream) -> Unit = { it.fd.sync() }
) {
    var output: FileOutputStream? = null
    try {
        val stream = startWrite()
        output = stream
        stream.write(bytes)
        syncFile(stream)
        finishWrite(stream)
        output = null
    } catch (error: Throwable) {
        output?.let { stream ->
            try {
                failWrite(stream)
            } catch (cleanupFailure: Throwable) {
                if (cleanupFailure !== error) error.addSuppressed(cleanupFailure)
            }
        }
        if (error is CancellationException || error !is Exception) throw error
        throw localIdentityError(
            kind = LocalIdentityFailureKind.PERSISTENCE_FAILED,
            recovery = LocalIdentityRecovery.RETRY,
            reason = "Failed to atomically write Android secure identity state",
            cause = error
        )
    }

    onCommitted()
    try {
        syncDirectory()
    } catch (error: CancellationException) {
        throw error
    } catch (_: Exception) {
        // Raw syscall failures can contain private paths; do not pass them to
        // the host logger. Diagnostics must not turn publication into cleanup.
        logger.failureIsolated().warn(
            "Android secure identity state was published, but its directory durability barrier failed; " +
                "crash durability is reduced"
        )
    }
}

/** Syscall boundary kept separate so host tests exercise real failure ownership. */
internal fun syncAndroidIdentityParentDirectory(
    directory: File,
    openDirectory: (String) -> FileDescriptor = { Os.open(it, OsConstants.O_RDONLY, 0) },
    syncDirectory: (FileDescriptor) -> Unit = Os::fsync,
    closeDirectory: (FileDescriptor) -> Unit = Os::close
) {
    val descriptor = openDirectory(directory.absolutePath)
    var primary: Throwable? = null
    try {
        syncDirectory(descriptor)
    } catch (failure: Throwable) {
        primary = failure
        throw failure
    } finally {
        try {
            closeDirectory(descriptor)
        } catch (closeFailure: Throwable) {
            val failure = primary
            if (failure == null) throw closeFailure
            if (closeFailure !== failure) failure.addSuppressed(closeFailure)
        }
    }
}
