package dev.p2pkit.core.transfer

import android.system.Os
import android.system.OsConstants
import dev.p2pkit.core.P2pError
import java.io.File
import java.io.FileDescriptor
import java.io.FileOutputStream
import java.io.IOException
import kotlinx.io.RawSink
import kotlinx.io.asSink

/**
 * Create a checked sibling-temp, file-fsync, atomic-rename, directory-fsync
 * destination for [target].
 *
 * Construction creates no staging file; the single staging sink is acquired
 * only by [FileTransferDestination.openSink]. The target's parent directory
 * must already exist. Commit fails rather than silently weakening durability if Android cannot atomically replace the
 * target or cannot fsync its parent directory. The standard receive path also
 * retains 64 MiB of usable space after the advertised file size fits; use the
 * overload to choose a different headroom.
 *
 * Staging is a randomly named `.p2pkit-*.part` sibling of [target], on the same
 * filesystem for atomic publication. Before opening it for payload writes,
 * Android must accept owner-only read/write permissions (`0600`) or opening
 * fails. Choose a trusted, application-controlled directory whose filesystem
 * enforces those permissions, such as internal app storage. Neither owner-only
 * permissions nor a hidden name prevents same-user tools, indexers, backup
 * agents, or cloud-sync clients from reading unverified partial content. Do
 * not use a watched/synced directory when that exposure is unwanted. A process
 * crash after opening can leave staging content for the application to
 * reconcile; the SDK does not sweep files based only on their names.
 */
public fun durableFileDestination(target: File): FileTransferDestination =
    durableFileDestination(target, DEFAULT_DURABLE_DESTINATION_MINIMUM_FREE_SPACE_BYTES)

/**
 * Create a durable destination that retains at least [minimumFreeSpaceBytes]
 * after the offered file's declared size fits in the target volume.
 *
 * The standard receive path checks this before opening the staging sink. It
 * is a preflight rather than a reservation: other processes can still change
 * filesystem capacity while a transfer is running. The sibling-staging and
 * directory-access constraints of [durableFileDestination] also apply.
 */
public fun durableFileDestination(
    target: File,
    minimumFreeSpaceBytes: Long
): FileTransferDestination = AndroidDurableFileDestination(
    target,
    minimumFreeSpaceBytes = minimumFreeSpaceBytes
)

internal class AndroidDurableFileDestination(
    target: File,
    private val closeSink: (RawSink) -> Unit = { it.close() },
    private val deleteTemp: (File) -> Boolean = { it.delete() },
    private val usableSpace: (File) -> Long = { it.usableSpace },
    private val minimumFreeSpaceBytes: Long = DEFAULT_DURABLE_DESTINATION_MINIMUM_FREE_SPACE_BYTES,
    private val openStream: (File) -> FileOutputStream = { FileOutputStream(it, false) },
    private val chmod: (String, Int) -> Unit = Os::chmod,
    private val rename: (String, String) -> Unit = Os::rename,
    private val openDirectory: (String) -> FileDescriptor = { Os.open(it, OsConstants.O_RDONLY, 0) },
    private val fsyncDirectory: (FileDescriptor) -> Unit = Os::fsync,
    private val closeDirectory: (FileDescriptor) -> Unit = Os::close
) : FileTransferDestination, StorageCapacityCheckingFileTransferDestination {
    private val target = target.absoluteFile
    private val parent = checkNotNull(this.target.parentFile) { "Target must have a parent directory" }
        .also { require(it.isDirectory) { "Target parent is not a directory: ${it.absolutePath}" } }

    init {
        require(minimumFreeSpaceBytes >= 0) { "minimumFreeSpaceBytes must be non-negative" }
    }

    private var temp: File? = null
    private var stream: FileOutputStream? = null
    private var sink: RawSink? = null
    private var state = DestinationState.NEW

    override fun requireAvailableStorage(expectedSizeBytes: Long) = synchronized(this) {
        if (!hasRequiredStorageCapacity(
                availableBytes = usableSpace(parent),
                expectedSizeBytes = expectedSizeBytes,
                minimumFreeSpaceBytes = minimumFreeSpaceBytes
            )
        ) {
            throw IOException(
                "Insufficient usable space for $expectedSizeBytes-byte transfer while retaining " +
                    "$minimumFreeSpaceBytes bytes"
            )
        }
    }

    override fun openSink(): RawSink = synchronized(this) {
        check(state == DestinationState.NEW) { "Destination was already opened or terminal" }
        try {
            val staging = File.createTempFile(tempPrefix(target.name), ".part", parent)
            temp = staging
            chmod(staging.absolutePath, 0x180) // 0600: owner read/write, no group/other access.
            val opened = openStream(staging)
            stream = opened
            opened.asSink().also {
                sink = it
                state = DestinationState.OPEN
            }
        } catch (failure: Throwable) {
            // A failed one-shot open still owns any staging file/stream it acquired.
            // The caller or the dispatcher's acceptance cleanup must abort it.
            state = DestinationState.ABORTING
            throw failure
        }
    }

    override suspend fun commit() {
        synchronized(this) {
            when (state) {
                DestinationState.COMMITTED -> return
                DestinationState.ABORTING,
                DestinationState.ABORTED -> error("Destination is already aborted")
                DestinationState.NEW -> error("Destination was not opened")
                DestinationState.PUBLISHED -> {
                    syncParentDirectory()
                    state = DestinationState.COMMITTED
                    return
                }
                DestinationState.OPEN -> Unit
            }
            val temp = checkNotNull(temp) { "Destination has no staging file" }
            val opened = checkNotNull(stream) { "Destination was not opened" }
            sink?.flush()
            opened.fd.sync()
            sink?.close()
            sink = null
            stream = null
            rename(temp.absolutePath, target.absolutePath)
            state = DestinationState.PUBLISHED
            syncParentDirectory()
            state = DestinationState.COMMITTED
        }
    }

    override suspend fun abort(cause: P2pError.FileTransferFailed?) {
        synchronized(this) {
            if (state == DestinationState.COMMITTED || state == DestinationState.ABORTED) return
            if (state == DestinationState.PUBLISHED) {
                state = DestinationState.ABORTED
                return
            }
            state = DestinationState.ABORTING

            val failures = mutableListOf<AbortFailure>()
            val openedSink = sink
            if (openedSink != null || stream != null) {
                try {
                    if (openedSink != null) closeSink(openedSink) else stream?.close()
                    sink = null
                    stream = null
                } catch (failure: Throwable) {
                    failures += AbortFailure("staging sink close", failure)
                }
            }
            val temp = temp
            if (temp != null && temp.exists()) {
                try {
                    deleteTemp(temp)
                    if (temp.exists()) {
                        failures += AbortFailure(
                            "staging file deletion",
                            IOException("Staging file still exists after deletion")
                        )
                    }
                } catch (failure: Throwable) {
                    failures += AbortFailure("staging file deletion", failure)
                }
            }

            if (sink == null && stream == null && temp?.exists() != true && failures.isEmpty()) {
                this.temp = null
                state = DestinationState.ABORTED
                return
            }
            throw abortFailure(failures)
        }
    }

    private fun syncParentDirectory() {
        val descriptor = openDirectory(parent.absolutePath)
        var primary: Throwable? = null
        try {
            fsyncDirectory(descriptor)
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
}

private enum class DestinationState {
    NEW,
    OPEN,
    PUBLISHED,
    COMMITTED,
    ABORTING,
    ABORTED
}

/**
 * Limit the target-derived staging prefix to 48 UTF-16 units, leaving room for
 * the 8-character marker, separator, platform-generated infix and `.part`.
 * This is not a universal 255-byte filesystem guarantee: encoding/component
 * rules differ, and it does not validate or shorten the final target name.
 */
private const val MAX_TEMP_PREFIX_NAME_CHARS: Int = 48

private fun tempPrefix(targetName: String): String = ".p2pkit-${targetName.take(MAX_TEMP_PREFIX_NAME_CHARS)}."

private data class AbortFailure(val resource: String, val cause: Throwable)

private fun abortFailure(failures: List<AbortFailure>): IOException {
    val effective = failures.ifEmpty {
        listOf(AbortFailure("staging cleanup", IOException("Staging cleanup did not complete")))
    }
    return IOException(
        "Durable destination abort failed for " +
            effective.joinToString { it.resource },
        effective.first().cause
    ).also { aggregate ->
        effective.drop(1).forEach { aggregate.addSuppressed(it.cause) }
    }
}
