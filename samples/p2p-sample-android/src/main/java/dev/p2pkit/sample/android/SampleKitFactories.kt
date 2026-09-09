package dev.p2pkit.sample.android

import dev.p2pkit.core.P2pKit

/** Internal creation seam for exercising real ViewModel actions without radios or persistent identity. */
internal interface SampleKitFactories {
    fun createRoomKit(): P2pKit
    fun createSmokeKit(): P2pKit
}
