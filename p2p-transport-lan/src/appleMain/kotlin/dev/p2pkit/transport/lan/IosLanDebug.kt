package dev.p2pkit.transport.lan

import kotlinx.coroutines.channels.BufferOverflow
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
 * 200-entry replay so a UI that subscribes shortly after startup still
 * sees the early browser-state events.
 */
public object IosLanDebug {

    private val _events = MutableSharedFlow<String>(
        replay = 200,
        extraBufferCapacity = 200,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )
    public val events: SharedFlow<String> = _events.asSharedFlow()

    internal fun log(tag: String, message: String) {
        val ts = ((NSDate().timeIntervalSince1970 * 1000).toLong()) % 1_000_000
        _events.tryEmit("[$ts][$tag] $message")
    }
}
