package dev.p2pkit.core.internal

import dev.p2pkit.core.NetworkPathObserver
import dev.p2pkit.core.P2pLogger

/**
 * Platform default-observer factory. Each target picks the best-effort
 * observer it can build with no host-supplied configuration:
 *   - iOS: nw_path_monitor-backed observer
 *   - Android: NoOp (needs a Context — host supplies via DSL override)
 *   - JVM desktop: NoOp
 *
 * Host apps can override the default via
 * `lifecycle { networkPathObserver = … }` on [dev.p2pkit.core.dsl.P2pKitBuilder].
 */
internal expect fun defaultNetworkPathObserver(logger: P2pLogger): NetworkPathObserver
