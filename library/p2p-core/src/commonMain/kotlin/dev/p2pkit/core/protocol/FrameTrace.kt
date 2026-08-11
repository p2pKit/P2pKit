package dev.p2pkit.core.protocol

import kotlin.concurrent.Volatile

/**
 * Opt-in trace of every protocol frame (TX / RX) with its decoded command type
 * (HELLO / DATA / PING / PONG / ACK / CLOSE / ERROR / FILE_*) and byte size —
 * the session/protocol-level counterpart to the transport-level byte trace
 * (`JvmLanDiag` / `IosLanDebug` / Android logcat). Seeing the command name next
 * to the chunk size makes the trail actionable: you can tell a keep-alive PING
 * from a DATA chunk from a FILE_DATA chunk without decoding bytes by hand.
 *
 * **OFF by default** — a library consumer sees nothing and pays nothing (the
 * line lambda is not even evaluated). A diagnostic build sets [enabled] = true;
 * the P2pKit samples do this alongside their transport trace. Lines go to
 * [sink], which defaults to **stdout**:
 *   - JVM/desktop: process stdout;
 *   - Android: logcat under the `System.out` tag;
 *   - iOS (Kotlin/Native): the unified log → Xcode console / Console.app.
 *
 * Override [sink] to route frames into an existing in-app log instead, e.g.
 * `FrameTrace.sink = { IosLanDebug.shared.log(tag: "frame", message: $0) }`.
 */
public object FrameTrace {

    /** Master switch. Library default is false; samples flip it on for tests. */
    @Volatile
    public var enabled: Boolean = false

    /** Where each frame line goes. Defaults to a greppable stdout line. */
    @Volatile
    public var sink: (String) -> Unit = { println("P2pKitFRAME $it") }

    /** Emit one frame line. The [line] lambda is built only when [enabled]. */
    internal inline fun emit(line: () -> String) {
        if (!enabled) return
        try {
            sink(line())
        } catch (_: Throwable) {
            // Trace is diagnostic-only. Disable the failed sink so it cannot
            // fail a send, receive loop, or repeatedly consume exception work.
            enabled = false
        }
    }
}
