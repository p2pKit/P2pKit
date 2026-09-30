package dev.p2pkit.sample.rpc

import dev.p2pkit.rpc.RpcDiagnostics
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.double
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.util.ServiceConfigurationError
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

class RpcCapacityDriverTest {
    @Test
    fun phaseSpacedClocksKeepEveryClientAtTenHertzForAllThirtyMinutes() {
        val origin = 456_000_000_000L
        val clients = RpcCapacityContract.CLIENTS
        val ticks = RpcCapacityContract.STEADY_SECONDS * RpcCapacityContract.CALLS_PER_SECOND_PER_CLIENT
        val phases = (0 until clients).map { capacityScheduledNanos(origin, 0, it, clients) }
        assertEquals(128, phases.toSet().size)
        assertEquals(phases.sorted(), phases)
        assertEquals(origin, phases.first())
        assertTrue(phases.last() < origin + 100_000_000)
        repeat(clients) { client ->
            for (tick in listOf(0, 500, ticks - 2)) {
                assertEquals(100_000_000L,
                    capacityScheduledNanos(origin, tick + 1, client, clients) -
                        capacityScheduledNanos(origin, tick, client, clients))
            }
            val last = capacityScheduledNanos(origin, ticks - 1, client, clients)
            assertTrue(last >= origin + 1_799_900_000_000 && last < origin + 1_800_000_000_000)
        }
        assertEquals(2_304_000, clients * ticks)
    }

    @Test
    fun invalidScheduleCannotShrinkTheClientOrDurationContractSilently() {
        for ((tick, client, count) in listOf(
            Triple(-1, 0, 128), Triple(18_000, 0, 128), Triple(0, -1, 128),
            Triple(0, 128, 128), Triple(0, 0, 0), Triple(0, 0, 129),
        )) assertFailsWith<IllegalArgumentException> { capacityScheduledNanos(0, tick, client, count) }
    }

    @Test
    fun finalTelemetryWaitsForActualCompletedCountersButRetainsItsDeadline() = runTest {
        fun sample(completed: Long) = RpcCapacityHostTelemetry(
            RpcCapacityHostSnapshot(128, RpcDiagnostics(completedCalls = completed)), 1, 1, 1, 1,
        )
        val fresh = sample(10)
        var reads = 0
        assertSame(fresh, withTimeout(5_000) {
            awaitCapacityCompletions(10) { if (reads++ < 2) sample(9) else fresh }
        })
        assertEquals(3, reads)
        assertFailsWith<TimeoutCancellationException> {
            withTimeout(5_000) { awaitCapacityCompletions(10) { sample(9) } }
        }
    }

    @Test
    fun absentOrAmbiguousProvidersNeverConstructResources() {
        var created = 0
        val factory = { created++; "owned" }
        assertFailsWith<IllegalArgumentException> { instantiateSingleCapacityProvider(emptySequence<() -> String>()) }
        assertFailsWith<IllegalArgumentException> { instantiateSingleCapacityProvider(sequenceOf(factory, factory)) }
        assertEquals(0, created)
        assertEquals("owned", instantiateSingleCapacityProvider(sequenceOf(factory)))
        assertEquals(1, created)
    }

    @Test
    fun failedProviderConstructionDoesNotExportItsRawServiceLoaderCause() {
        val failure = assertFailsWith<IllegalStateException> {
            instantiateSingleCapacityProvider(sequenceOf({
                throw ServiceConfigurationError("sensitive synthetic configuration", Exception("private cause"))
            }))
        }
        assertEquals("The reviewed local environment provider could not initialize", failure.message)
        assertNull(failure.cause)
    }

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
