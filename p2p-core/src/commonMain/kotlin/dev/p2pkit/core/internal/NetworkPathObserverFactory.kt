package dev.p2pkit.core.internal

import dev.p2pkit.core.NetworkPathObserver
import dev.p2pkit.core.P2pLogger

/**
 * Platform default-observer factory. Each target picks the best-effort
 * observer it can build with no host-supplied configuration:
 *   - iOS: nw_path_monitor-backed observer
 *   - Android: ConnectivityManager-backed observer when the application
 *     context was registered, otherwise NoOp
 *   - JVM desktop: NoOp
 *
 * Host apps can override the default via
 * `lifecycle { networkPathObserver = … }` on [dev.p2pkit.core.dsl.P2pKitBuilder].
 */
internal expect fun defaultNetworkPathObserver(logger: P2pLogger): NetworkPathObserver
