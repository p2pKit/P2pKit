package dev.p2pkit.core.internal

import kotlin.test.Test

/** The Android-host filter does not execute ordinary commonTest class names. */
class LegacyAppIdSanitizerAndroidHostTest {
    @Test
    fun androidUsesTheSameFrozenLegacyVectors() {
        LegacyAppIdSanitizerVectorTest().historicalMappingsAndIntentionalCollisionsRemainFrozen()
    }
}
