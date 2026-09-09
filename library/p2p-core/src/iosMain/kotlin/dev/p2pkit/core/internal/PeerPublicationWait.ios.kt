package dev.p2pkit.core.internal

import platform.Foundation.NSThread

internal actual fun pausePeerPublication() {
    NSThread.sleepForTimeInterval(PEER_PUBLICATION_PAUSE_NANOS / 1_000_000_000.0)
}
