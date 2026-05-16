package dev.p2pkit.sample.kmp

import kotlin.test.Test
import kotlin.test.assertNotNull

/**
 * Common-source smoke test: proves the shared [createP2pKit] expect resolves
 * and that the demo function compiles against the public API. We do *not*
 * actually start P2pKit here — that requires a platform actual to be wired
 * in by the host test run. The `jvmTest` JVM run will exercise this fully
 * because the JVM actual is in `jvmMain`.
 */
class KmpCallsiteSmokeTest {

    @Test
    fun factoryExpectIsResolvable() {
        // Just reference the factory; we don't invoke it because that would
        // bind ports and start network discovery in this unit test.
        val ref: (String, String) -> dev.p2pkit.core.P2pKit = ::createP2pKit
        assertNotNull(ref)
    }
}
