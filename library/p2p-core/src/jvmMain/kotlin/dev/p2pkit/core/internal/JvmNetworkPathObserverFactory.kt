package dev.p2pkit.core.internal

import dev.p2pkit.core.NetworkPathObserver
import dev.p2pkit.core.P2pLogger

/**
 * JVM desktop has no reliable cross-OS API for path-change events.
 * The host app can supply a custom observer via DSL if it wants the
 * behaviour. Default is no-op.
 */
internal actual fun defaultNetworkPathObserver(logger: P2pLogger): NetworkPathObserver =
    NoOpNetworkPathObserver
