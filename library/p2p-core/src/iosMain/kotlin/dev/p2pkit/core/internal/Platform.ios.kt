package dev.p2pkit.core.internal

import dev.p2pkit.core.Platform
import platform.Foundation.NSDate
import platform.Foundation.NSProcessInfo
import platform.Foundation.timeIntervalSince1970

internal actual fun systemTimeMillis(): Long =
    (NSDate().timeIntervalSince1970 * 1_000.0).toLong()

internal actual fun monotonicTimeMillis(): Long =
    (NSProcessInfo.processInfo.systemUptime * 1_000.0).toLong()

internal actual fun currentPlatform(): Platform = Platform.IOS
