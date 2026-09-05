package dev.p2pkit.sample.desktop.ui

import dev.p2pkit.core.protocol.FrameTrace
import dev.p2pkit.core.protocol.FrameTraceLease

/** LAN already honors this explicit process-start property; use it for frame metadata too. */
internal fun installDesktopFrameTracing(onFrame: (String) -> Unit): FrameTraceLease? {
    if (!System.getProperty("dev.p2pkit.lan.trace").equals("true", ignoreCase = true)) return null
    // Opt-in topology/traffic-shape diagnostics are not safe production defaults.
    return FrameTrace.installSink(enabled = true) { line ->
        println("P2pKitFRAME $line")
        onFrame(line)
    }
}
