package dev.p2pkit.sample.rpc

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class RpcCapacityDriverTest {
    @Test
    fun histogramIsBoundedAndReportsUpperBucketsNotInventedPrecision() {
        val histogram = CapacityLatencyHistogram()
        assertEquals(-1, histogram.percentile(50))
        histogram.record(1)
        histogram.record(1_000_001)
        histogram.record(60_000_000_000)
        assertEquals(2, histogram.percentile(50))
        assertEquals(30_001, histogram.percentile(100))
    }

    @Test
    fun exportedManifestDoesNotAcceptFreeFormTextOrMissingArtifactHashes() {
        assertFailsWith<IllegalArgumentException> {
            RpcCapacityManifest(
                "user@private-host", RpcCapacityHostPlatform.Jvm, "a".repeat(40), "b".repeat(64), "c".repeat(64),
            )
        }
        assertFailsWith<IllegalArgumentException> {
            RpcCapacityManifest("local-run", RpcCapacityHostPlatform.Ios, "unknown", "b".repeat(64), "c".repeat(64))
        }
    }
}
