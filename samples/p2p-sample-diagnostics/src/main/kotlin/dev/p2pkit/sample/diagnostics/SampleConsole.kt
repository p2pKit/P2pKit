package dev.p2pkit.sample.diagnostics

import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.Peer
import dev.p2pkit.core.transfer.FileTransferState

/** Opaque display/selection alias only; never use it for identity authorization. */
public val Peer.consoleId: String get() = SampleConsole.identifier(id.value)

/**
 * Data-minimized sample console fields, not a sanitizer for arbitrary text.
 * Compose these with fixed labels, enums and counts only. Names, payloads,
 * paths, addresses, rejection reasons and exception messages do not belong here.
 * Hashes permit correlation; they are not a promise of unlinkability.
 */
public object SampleConsole {
    public fun identifier(value: String): String = anonymizeIdentifier(value)

    public fun received(peerId: String, isText: Boolean, sizeBytes: Long): String =
        "incoming from ${identifier(peerId)}: <${if (isText) "text" else "binary"} ${sizeBytes}B>"

    public fun sendingText(recipients: Int, sizeBytes: Long): String =
        "sending <text ${sizeBytes}B> to $recipients peer(s) (local send, not remote processing)"

    /** A diagnostic summary can contain an arbitrary Failed/Rejected reason after its state name. */
    public fun stateLabel(value: String?): String = listOf(
        "Offered", "Accepted", "Sending", "Completed", "Rejected", "Cancelled", "Failed",
        "Connecting", "Handshaking", "Connected", "Reconnecting", "Closing", "Closed"
    ).firstOrNull { value == it || value?.startsWith("$it(") == true || value?.startsWith("$it:") == true }
        ?: "Unknown"

    /** Never call Throwable.toString(), message, cause or stackTrace at a console boundary. */
    public fun failure(error: Throwable): String = error.javaClass.simpleName.ifEmpty { "Throwable" }

    public fun transferState(state: FileTransferState): String = when (state) {
        FileTransferState.Offered -> "Offered"
        FileTransferState.Accepted -> "Accepted"
        is FileTransferState.Sending -> "Sending(progress=${state.progress})"
        FileTransferState.Completed -> "Completed"
        is FileTransferState.Rejected -> "Rejected"
        is FileTransferState.Cancelled -> "Cancelled"
        is FileTransferState.Failed -> "Failed(${failure(state.error)})"
    }
}

/**
 * SDK log strings are free-form and may embed peer data or platform paths.
 * Do not attempt to make them private with a regex: emit severity/type only.
 * The structured diagnostic recorder remains a separate, test-only channel.
 */
public class SampleConsoleLogger(private val write: (level: String, line: String) -> Unit) : P2pLogger {
    override fun debug(message: String): Unit = write("D", "SDK event (details omitted)")

    override fun info(message: String): Unit = write("I", "SDK event (details omitted)")

    override fun warn(message: String, throwable: Throwable?): Unit = emit("W", throwable)

    override fun error(message: String, throwable: Throwable?): Unit = emit("E", throwable)

    private fun emit(level: String, error: Throwable?) {
        val kind = error?.let { "; errorType=${SampleConsole.failure(it)}" }.orEmpty()
        write(level, "SDK event (details omitted)$kind")
    }
}
