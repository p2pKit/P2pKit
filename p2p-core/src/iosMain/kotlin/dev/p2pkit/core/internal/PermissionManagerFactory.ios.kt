package dev.p2pkit.core.internal

import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.permission.NoOpP2pPermissionManager
import dev.p2pkit.core.permission.P2pPermissionManager

/**
 * iOS Local Network access is gated by the OS at first `NWBrowser`/`NWListener`
 * use (the system shows the permission prompt), and there is no synchronous
 * pre-check API to surface here — so the default manager is a no-op. The iOS
 * sample detects a denial behaviourally (browser never reaches `ready`).
 */
internal actual fun defaultPlatformPermissionManager(logger: P2pLogger): P2pPermissionManager =
    NoOpP2pPermissionManager()
