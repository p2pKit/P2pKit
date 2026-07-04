package dev.p2pkit.core.internal

import dev.p2pkit.core.NetworkPathObserver
import dev.p2pkit.core.P2pLogger

/**
 * Android's default network path observer is deliberately no-op. A `Context`
 * could be obtained here via `androidApplicationContextOrNull()` once the
 * host app has called `P2pKitAndroid.initialize` (the peer-id and permission
 * factories in this source set do exactly that), but auto-wiring the real
 * observer would be a behavior change this factory has not adopted —
 * AUDIT-2026-06: the previous comment wrongly claimed a Context "cannot be
 * synthesised from :p2p-core alone". Host apps that want path-change
 * recovery construct [dev.p2pkit.core.AndroidNetworkPathObserver] and
 * register it via
 * `lifecycle { networkPathObserver = AndroidNetworkPathObserver(ctx) }`.
 */
internal actual fun defaultNetworkPathObserver(logger: P2pLogger): NetworkPathObserver =
    NoOpNetworkPathObserver
