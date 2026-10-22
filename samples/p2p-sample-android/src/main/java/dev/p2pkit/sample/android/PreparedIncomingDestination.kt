package dev.p2pkit.sample.android

import dev.p2pkit.core.transfer.FileTransferDestination
import dev.p2pkit.core.transfer.durableFileDestination
import dev.p2pkit.sample.diagnostics.reservedFileDestination
import java.io.File
import java.io.IOException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.withContext

internal data class PreparedIncomingDestination(
    val location: IncomingFileLocation,
    val destination: FileTransferDestination,
)

/** Retain an unpublished reservation even when prompt cancellation drops the IO block's return. */
internal suspend fun prepareIncomingDestination(
    wrap: (File) -> FileTransferDestination = ::androidReservedFileDestination,
    allocate: () -> IncomingFileLocation,
): PreparedIncomingDestination {
    var location: IncomingFileLocation? = null
    var destination: FileTransferDestination? = null
    try {
        withContext(Dispatchers.IO) {
            // Assign before the next cancellable boundary; never return an unowned file from IO.
            val reserved = allocate()
            location = reserved
            destination = wrap(reserved.file)
        }
        return PreparedIncomingDestination(checkNotNull(location), checkNotNull(destination))
    } catch (failure: Throwable) {
        // Keep the return from IO inside NonCancellable as well: otherwise prompt cancellation
        // can replace the primary failure (and its suppressed cleanup error) on that return.
        withContext(NonCancellable) {
            withContext(Dispatchers.IO) {
                try {
                    val owned = destination
                    if (owned != null) {
                        owned.abort(null)
                    } else {
                        // No wrapper/offer can have published this exact claim yet.
                        location?.file?.let { file ->
                            if (file.exists() && !file.delete()) {
                                throw IOException("Could not remove unclaimed destination")
                            }
                        }
                    }
                } catch (cleanupFailure: Throwable) {
                    if (cleanupFailure !== failure) failure.addSuppressed(cleanupFailure)
                }
            }
        }
        throw failure
    }
}

/** The shared diagnostics JAR's default is JVM-only; bind Android's facade here. */
private fun androidReservedFileDestination(target: File): FileTransferDestination =
    reservedFileDestination(target) { destination, staging ->
        durableFileDestination(destination, staging, 64L * 1024 * 1024)
    }
