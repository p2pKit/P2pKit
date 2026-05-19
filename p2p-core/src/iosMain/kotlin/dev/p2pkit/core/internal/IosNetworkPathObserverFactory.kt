package dev.p2pkit.core.internal

import dev.p2pkit.core.NetworkPathObserver
import dev.p2pkit.core.P2pLogger

/** iOS default: an [IosNetworkPathObserver] over `nw_path_monitor_t`. */
internal actual fun defaultNetworkPathObserver(logger: P2pLogger): NetworkPathObserver =
    IosNetworkPathObserver(logger)
