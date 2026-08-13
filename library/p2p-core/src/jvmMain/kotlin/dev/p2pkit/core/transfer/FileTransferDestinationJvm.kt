package dev.p2pkit.core.transfer

import dev.p2pkit.core.P2pError
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.nio.channels.FileChannel
import java.nio.file.StandardCopyOption
import java.nio.file.StandardOpenOption
import kotlinx.io.RawSink
import kotlinx.io.asSink

/**
 * Create a temporary-file, fsync, atomic-rename destination for [target].
 *
 * The target's parent directory must already exist. Commit fails rather than
 * silently weakening durability if the filesystem cannot atomically replace
 * the target or cannot fsync its parent directory.
 */
public fun durableFileDestination(target: File): FileTransferDestination =
    JvmDurableFileDestination(target)

internal class JvmDurableFileDestination(
    target: File,
    private val closeSink: (RawSink) -> Unit = { it.close() },
    private val deleteTemp: (File) -> Boolean = { it.delete() }
) : FileTransferDestination {
    private val target = target.absoluteFile
    private val parent = checkNotNull(this.target.parentFile) { "Target must have a parent directory" }
        .also { require(it.isDirectory) { "Target parent is not a directory: ${it.absolutePath}" } }
    private val temp = File.createTempFile(tempPrefix(this.target.name), ".part", parent)
    private var stream: FileOutputStream? = null
    private var sink: RawSink? = null
    private var state = DestinationState.NEW

    override fun openSink(): RawSink = synchronized(this) {
        check(state == DestinationState.NEW) { "Destination was already opened or terminal" }
        val opened = FileOutputStream(temp, false)
        stream = opened
        state = DestinationState.OPEN
        opened.asSink().also { sink = it }
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
            sink?.let { openedSink ->
                try {
                    closeSink(openedSink)
                    sink = null
                    stream = null
                } catch (failure: Throwable) {
                    failures += AbortFailure("staging sink close", failure)
                }
            }
            if (temp.exists()) {
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

            if (sink == null && !temp.exists() && failures.isEmpty()) {
                state = DestinationState.ABORTED
                return
            }
            throw abortFailure(failures)
        }
    }

    private fun syncParentDirectory() {
        FileChannel.open(parent.toPath(), StandardOpenOption.READ).use { it.force(true) }
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
