package dev.p2pkit.core.transfer

import dev.p2pkit.core.P2pError
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.nio.channels.FileChannel
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.nio.file.StandardOpenOption
import java.nio.file.attribute.PosixFileAttributeView
import java.nio.file.attribute.PosixFilePermissions
import kotlinx.io.RawSink
import kotlinx.io.asSink

/**
 * Create a temporary-file, file-fsync, atomic-rename destination for [target].
 *
 * Construction creates no staging file; the single staging sink is acquired
 * only by [FileTransferDestination.openSink]. The target's parent directory
 * must already exist. On POSIX filesystems, commit also fsyncs that directory and fails if the durability barrier is
 * unavailable. The public JDK cannot open Windows directory handles with the
 * flags needed by `FlushFileBuffers`, so Windows commit guarantees synced file
 * content and atomic publication but cannot guarantee that the directory entry
 * survives sudden power loss. The standard receive path also retains 64 MiB
 * of usable space after the advertised file size fits; use the overload to
 * choose a different headroom.
 *
 * Staging is a randomly named `.p2pkit-*.part` sibling of [target], on the same
 * filesystem for atomic publication. POSIX staging is created with owner-only
 * read/write permissions (`0600`); other filesystems use the JDK's default
 * temporary-file permissions and the parent directory's access policy. Choose
 * a trusted, application-controlled directory with appropriate access controls.
 * Neither owner-only permissions nor a hidden name prevents same-user tools,
 * indexers, backup agents, or cloud-sync clients from reading unverified partial
 * content. Do not use a watched/synced directory when that exposure is unwanted.
 * A process crash after opening can leave staging content for the application
 * to reconcile; the SDK does not sweep files based only on their names.
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
): FileTransferDestination = JvmDurableFileDestination(target, minimumFreeSpaceBytes = minimumFreeSpaceBytes)

internal class JvmDurableFileDestination(
    target: File,
    private val closeSink: (RawSink) -> Unit = { it.close() },
    private val deleteTemp: (File) -> Boolean = { it.delete() },
    private val operatingSystemName: String = System.getProperty("os.name").orEmpty(),
    private val syncDirectory: (File) -> Unit = ::forceDirectory,
    private val usableSpace: (File) -> Long = { it.usableSpace },
    private val minimumFreeSpaceBytes: Long = DEFAULT_DURABLE_DESTINATION_MINIMUM_FREE_SPACE_BYTES,
    private val openStream: (File) -> FileOutputStream = { FileOutputStream(it, false) }
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
            val staging = createStagingFile(parent, target.name)
            temp = staging
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
            java.nio.file.Files.move(
                temp.toPath(),
                target.toPath(),
                StandardCopyOption.ATOMIC_MOVE,
                StandardCopyOption.REPLACE_EXISTING
            )
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
        if (isWindows(operatingSystemName)) return
        syncDirectory(parent)
    }
}

private fun createStagingFile(directory: File, targetName: String): File {
    val parent = directory.toPath()
    if (Files.getFileStore(parent).supportsFileAttributeView(PosixFileAttributeView::class.java)) {
        return Files.createTempFile(
            parent,
            tempPrefix(targetName),
            ".part",
            PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rw-------"))
        ).toFile()
    }
    // An explicitly non-POSIX filesystem uses its own temporary-file/ACL policy.
    // Do not fall back after a failed POSIX creation or permission check.
    return Files.createTempFile(parent, tempPrefix(targetName), ".part").toFile()
}

private fun forceDirectory(directory: File) {
    FileChannel.open(directory.toPath(), StandardOpenOption.READ).use { it.force(true) }
}

private fun isWindows(operatingSystemName: String): Boolean =
    operatingSystemName.startsWith("Windows", ignoreCase = true)

private enum class DestinationState {
    NEW,
    OPEN,
    PUBLISHED,
    COMMITTED,
    ABORTING,
    ABORTED
}

private fun tempPrefix(targetName: String): String = ".p2pkit-${targetName.take(48)}."

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
