package dev.p2pkit.core.internal

import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.permission.NoOpP2pPermissionManager
import dev.p2pkit.core.permission.P2pPermissionManager

/** JVM desktop needs no runtime permission grant for LAN/mDNS. */
internal actual fun defaultPlatformPermissionManager(logger: P2pLogger): P2pPermissionManager =
    NoOpP2pPermissionManager()
