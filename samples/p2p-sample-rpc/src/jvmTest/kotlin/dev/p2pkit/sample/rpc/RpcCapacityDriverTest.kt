package dev.p2pkit.sample.rpc

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.double
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
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
        histogram.record(Long.MAX_VALUE)
        assertEquals(2, histogram.percentile(50))
        assertEquals(30_001, histogram.percentile(100))
    }

    @Test
    fun machineReadableResultsPreserveMeasuredDurationAndNeverClaimQualification() {
        val histogram = CapacityLatencyHistogram().also { it.record(1) }
        val report = Json.parseToJsonElement(capacityResultJson(
            "steady", true, mapOf("completed" to 2_304_000L, "actualSchedulingNanos" to 1_800_000_000_000L),
            histogram, histogram,
        )).jsonObject
        assertEquals(false, report.getValue("capacityQualified").jsonPrimitive.boolean)
        assertEquals("PENDING_RESOURCE_AND_NETWORK_REVIEW", report.getValue("status").jsonPrimitive.content)
        assertEquals(1280.0, report.getValue("throughputResponsesPerSecond").jsonPrimitive.double)
        assertEquals("AWAIT_FINAL_RECORD", report.getValue("cleanup").jsonPrimitive.content)
        val failed = Json.parseToJsonElement(capacityResultJson("large", false, emptyMap(), histogram)).jsonObject
        assertEquals("FAIL", failed.getValue("status").jsonPrimitive.content)
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
