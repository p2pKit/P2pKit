package dev.p2pkit.transport.lan

import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import platform.Foundation.NSDate
import platform.Foundation.timeIntervalSince1970

/**
 * Process-wide diagnostic sink for the iOS LAN transport.
 *
 * Why this exists: `:p2p-core`'s `TransportContext` does NOT carry the
 * kit's `P2pLogger` down to transport implementations, so
 * [IosLanDiscoveryTransport] / [IosLanDataTransport] can't easily report
 * per-event detail back to the consuming Swift app. Adding a logger to
 * `TransportContext` is a larger SDK change; this singleton is the
 * minimum-impact path to surface what NWBrowser/NWListener/NWConnection
 * are doing at runtime.
 *
 * From Swift:
 *
 * ```swift
 * let collector = ... // your FlowCollector<String>
 * try await IosLanDebug.shared.events.collect(collector: collector)
 * ```
 *
 * Diagnostic UIs may opt into a 200-entry replay so a subscriber attached
 * shortly after startup still sees early browser-state events.
 */
@OptIn(ExperimentalCoroutinesApi::class)
public object IosLanDebug {

    private val _events = MutableSharedFlow<String>(
        replay = 200,
        extraBufferCapacity = 200,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )
    public val events: SharedFlow<String> = _events.asSharedFlow()

    /**
     * Push a single diagnostic line into the shared sink. Public so the
     * Swift sample can append UI-action lines (button taps, lifecycle
     * events, send results) to the same timeline that the LAN transport
     * emits its own events on — that way the on-screen log shows kit-side
     * events and UI-side events interleaved in time order, which is the
     * only way to tell whether a stuck button or a stuck send is the
     * upstream problem.
     *
     * Side effect: also `println`s the line with a `p2pkit:` prefix.
     * `println()` from Kotlin/Native on iOS goes through the unified
     * logging system, so the line appears in Xcode's debug console
     * (running from Xcode) and in Console.app (any device, filter on
     * "p2pkit"). That's the "logcat-like" surface for iOS — the
     * on-screen log inside the app is still the primary diagnostic, but
     * the stdout mirror means the same data is visible from the Mac
     * without screenshotting the phone.
     */
    public fun log(tag: String, message: String) {
        val ts = ((NSDate().timeIntervalSince1970 * 1000).toLong()) % 1_000_000
        val line = "[$ts][${sanitizeLanDiagnostic(tag)}] ${sanitizeLanDiagnostic(message)}"
        _events.tryEmit(line)
        if (!retainHistory) _events.resetReplayCache()
        if (mirrorToConsole) println("p2pkit: $line")
    }

    /**
     * Mirrors every line to `println` (unified logging / Console.app) when
     * true. Default OFF: the mirror ran unconditionally in release builds,
     * printing peer ids/device names/TXT contents to the device console and
     * adding a string-build + syscall per transport event — including one per
     * 64 KiB frame on the file-transfer hot path (AUDIT-2026-06 fix). The
     * sample app (and tests) can opt back in at startup.
     */
    @kotlin.concurrent.Volatile
    public var mirrorToConsole: Boolean = false

    /**
     * Retain up to 200 recent lines for late subscribers. Disabled by default
     * so a release process does not keep peer-controlled diagnostics merely
     * because console mirroring is off; diagnostic UIs may opt in explicitly.
     */
    @kotlin.concurrent.Volatile
    public var retainHistory: Boolean = false
}
