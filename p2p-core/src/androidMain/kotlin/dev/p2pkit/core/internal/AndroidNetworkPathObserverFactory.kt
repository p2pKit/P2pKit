package dev.p2pkit.core.internal

import dev.p2pkit.core.NetworkPathObserver
import dev.p2pkit.core.P2pLogger

/**
 * Android's `ConnectivityManager.NetworkCallback` requires a `Context` we
 * cannot synthesise from `:p2p-core` alone. The default is no-op; host
 * apps that want path-change recovery construct
 * [dev.p2pkit.core.AndroidNetworkPathObserver] in `androidMain` and register
 * it via `lifecycle { networkPathObserver = AndroidNetworkPathObserver(ctx) }`.
 */
internal actual fun defaultNetworkPathObserver(logger: P2pLogger): NetworkPathObserver =
    NoOpNetworkPathObserver
