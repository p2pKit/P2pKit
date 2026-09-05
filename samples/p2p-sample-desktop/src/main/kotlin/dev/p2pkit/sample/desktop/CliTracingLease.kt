package dev.p2pkit.sample.desktop

import dev.p2pkit.core.protocol.FrameTrace
import dev.p2pkit.core.protocol.FrameTraceLease
import dev.p2pkit.transport.lan.JvmLanDiag

/** A sample opt-in, not permission to disable another owner's process-wide tracing. */
internal class CliTracingLease private constructor(
    private val token: Any,
    private val frames: FrameTraceLease?
) : AutoCloseable {
    override fun close() {
        frames?.release()
        CliLanTraceOwners.release(token)
    }

    companion object {
        fun acquire(mode: String?, onFrame: (String) -> Unit): CliTracingLease {
            require(mode == null || mode in setOf("off", "on", "frames")) { "Invalid CLI trace mode" }
            val enabled = mode == "on" || mode == "frames"
            val token = CliLanTraceOwners.acquire(enabled, mode == "frames")
            return try {
                // Off must not replace/disable an unrelated host's frame sink.
                val frames = if (enabled) {
                    FrameTrace.installSink(enabled = true) { line ->
                        println("P2pKitFRAME $line")
                        onFrame(line)
                    }
                } else null
                CliTracingLease(token, frames)
            } catch (failure: Throwable) {
                CliLanTraceOwners.release(token)
                throw failure
            }
        }
    }
}

private object CliLanTraceOwners {
    private data class Flags(val enabled: Boolean, val bytes: Boolean)

    private val requests = mutableMapOf<Any, Flags>()
    private var previous: Flags? = null

    @Synchronized
    fun acquire(enabled: Boolean, bytes: Boolean): Any {
        if (requests.isEmpty()) previous = Flags(JvmLanDiag.enabled, JvmLanDiag.traceFrames)
        val token = Any()
        requests[token] = Flags(enabled, bytes)
        applyRequests()
        return token
    }

    @Synchronized
    fun release(token: Any) {
        if (requests.remove(token) == null) return
        applyRequests()
        if (requests.isEmpty()) previous = null
    }

    private fun applyRequests() {
        val host = checkNotNull(previous)
        val enabled = host.enabled || requests.values.any { it.enabled }
        // A byte-trace request must not survive the owner that requested it.
        val bytes = host.bytes || requests.values.any { it.bytes }
        if (!enabled) JvmLanDiag.enabled = false
        JvmLanDiag.traceFrames = bytes
        JvmLanDiag.enabled = enabled
    }
}
