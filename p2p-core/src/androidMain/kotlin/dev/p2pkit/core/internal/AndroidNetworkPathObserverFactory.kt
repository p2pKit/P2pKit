package dev.p2pkit.core.internal

import dev.p2pkit.core.AndroidNetworkPathObserver
import dev.p2pkit.core.NetworkPathObserver
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.android.androidApplicationContextOrNull

/**
 * Uses the application context registered through `P2pKitAndroid.initialize`
 * to provide Android path recovery by default. Initialization-free hosts keep
 * the compatibility fallback to a permanent `Unknown` stream.
 */
internal actual fun defaultNetworkPathObserver(logger: P2pLogger): NetworkPathObserver =
    selectAndroidDefaultPathObserver(
        context = androidApplicationContextOrNull(),
        fallback = NoOpNetworkPathObserver
    ) { context -> AndroidNetworkPathObserver(context, logger) }
