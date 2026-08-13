package dev.p2pkit.core.protocol

import kotlin.concurrent.atomics.AtomicReference
import kotlin.concurrent.atomics.ExperimentalAtomicApi

/**
 * Opt-in trace of every protocol frame (TX / RX) with its decoded command type
 * (HELLO / DATA / PING / PONG / ACK / CLOSE / ERROR / FILE_*) and byte size —
 * the session/protocol-level counterpart to the transport-level byte trace
 * (`JvmLanDiag` / `IosLanDebug` / Android logcat). Seeing the command name next
 * to the chunk size makes the trail actionable: you can tell a keep-alive PING
 * from a DATA chunk from a FILE_DATA chunk without decoding bytes by hand.
 *
 * **OFF by default** — a library consumer sees nothing and the trace line is
 * not constructed. A diagnostic build sets [enabled] = true; the P2pKit
 * samples do this alongside their transport trace. Lines go to [sink], which
 * defaults to **stdout**:
 *   - JVM/desktop: process stdout;
 *   - Android: logcat under the `System.out` tag;
 *   - iOS (Kotlin/Native): the unified log → Xcode console / Console.app.
 *
 * Use [installSink] to route frames into an in-app log, then release the
 * returned [FrameTraceLease] when its owner stops. The mutable [sink] property
 * remains available for source compatibility.
 */
@OptIn(ExperimentalAtomicApi::class)
public object FrameTrace {

    private val defaultSink: (String) -> Unit = { println("P2pKitFRAME $it") }
    private val state = AtomicReference(TraceState(false, defaultSink, null))

    /** Master switch. Library default is false; samples flip it on for tests. */
    public var enabled: Boolean
        get() = state.load().enabled
        set(value) {
            updateDirect { it.copy(enabled = value) }
        }

    /** Where each frame line goes. Defaults to a greppable stdout line. */
    public var sink: (String) -> Unit
        get() = state.load().sink
        set(value) {
            // Direct assignment is retained for source compatibility. It
            // deliberately revokes any lease so a later stale release cannot
            // overwrite the explicitly installed callback.
            updateDirect { it.copy(sink = value, owner = null) }
        }

    /**
     * Installs one owner-scoped diagnostic sink.
     *
     * The returned lease must be released when the diagnostic owner stops.
     * Releasing an older lease after a newer owner has installed its sink is
     * harmless: only the current owner can disable and detach its callback.
     * This keeps stopped samples/ViewModels out of the global callback while
     * preserving the legacy mutable [sink] property for existing consumers.
     */
    public fun installSink(
        enabled: Boolean,
        sink: (String) -> Unit
    ): FrameTraceLease {
        val lease = FrameTraceLease()
        while (true) {
            val current = state.load()
            if (state.compareAndSet(current, TraceState(enabled, sink, lease))) break
        }
        return lease
    }

    internal fun release(lease: FrameTraceLease) {
        while (true) {
            val current = state.load()
            if (current.owner !== lease) return
            if (state.compareAndSet(current, TraceState(false, defaultSink, null))) return
        }
    }

    /** Emit one frame line. The [line] lambda is built only when [enabled]. */
    internal fun emit(line: () -> String) {
        val current = state.load()
        if (!current.enabled) return
        try {
            current.sink(line())
        } catch (_: Throwable) {
            // Trace is diagnostic-only. Disable the failed sink so it cannot
            // fail a send, receive loop, or repeatedly consume exception work.
            state.compareAndSet(current, current.copy(enabled = false))
        }
    }

    private fun updateDirect(transform: (TraceState) -> TraceState) {
        while (true) {
            val current = state.load()
            if (state.compareAndSet(current, transform(current))) return
        }
    }

    private data class TraceState(
        val enabled: Boolean,
        val sink: (String) -> Unit,
        val owner: FrameTraceLease?
    )
}

/** Owner token returned by [FrameTrace.installSink]. */
public class FrameTraceLease internal constructor() {
    /** Idempotently detaches this sink if it is still the current owner. */
    public fun release() {
        FrameTrace.release(this)
    }
}
