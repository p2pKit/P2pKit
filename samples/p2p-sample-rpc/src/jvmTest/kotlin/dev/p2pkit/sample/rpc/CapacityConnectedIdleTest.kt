package dev.p2pkit.sample.rpc

import dev.p2pkit.rpc.RpcConnectionState
import dev.p2pkit.rpc.RpcDiagnostics
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Virtual-clock observer regressions, not evidence of physical resources, sockets or RPC capacity. */
@OptIn(ExperimentalCoroutinesApi::class)
class CapacityConnectedIdleTest {
    private fun TestScope.sample(
        clients: Int, uptime: Long = testScheduler.currentTime,
        cpu: Long = testScheduler.currentTime * 1_000, accepted: Long = clients * 600L,
        connected: Int = clients,
    ): RpcCapacityHostTelemetry = RpcCapacityHostTelemetry(
        RpcCapacityHostSnapshot(connected, RpcDiagnostics(acceptedCalls = accepted, completedCalls = accepted)),
        uptime, cpu, 32L * 1024 * 1024, 24,
    )

    private suspend fun TestScope.observe(
        states: List<MutableStateFlow<RpcConnectionState>>, sampleHost: suspend () -> RpcCapacityHostTelemetry = {
            sample(states.size, connected = states.count { it.value == RpcConnectionState.Ready })
        },
    ): CapacityConnectedIdleOutcome = observeCapacityConnectedIdle(states, sampleHost,
        driverCpuNanos = { testScheduler.currentTime * 500 },
        nowNanos = { testScheduler.currentTime * 1_000_000 })

    private fun states(clients: Int) = List(clients) { MutableStateFlow(RpcConnectionState.Ready) }

    @Test
    fun fullSelectedCohortGetsASeparateSettledThirtySecondHostClockObservation() = runTest {
        for (clients in listOf(128, 256)) {
            val states = states(clients)
            val outcome = observe(states)
            assertTrue(outcome.mechanical)
            assertNull(outcome.failureStage)
            assertEquals(40_000_000_000L, outcome.measurements.getValue("actualDurationNanos"))
            assertEquals(10_000_000_000L, outcome.measurements.getValue("actualSettleNanos"))
            assertEquals(30_000L, outcome.measurements.getValue("hostUptimeDeltaMillis"))
            assertEquals(30_000_000_000L, outcome.measurements.getValue("driverElapsedNanos"))
            assertEquals(30_000_000L, outcome.measurements.getValue("hostCpuDeltaNanos"))
            assertEquals(15_000_000L, outcome.measurements.getValue("driverCpuDeltaNanos"))
            assertEquals(0L, outcome.measurements.getValue("hostAcceptedDelta"))
            assertEquals(0L, outcome.measurements.getValue("hostCompletedDelta"))
            assertEquals(0L, outcome.measurements.getValue("connectionChanges"))
            assertEquals(7, outcome.samples.size)
            assertTrue(states.all { it.subscriptionCount.value == 0 })
            // Neither initialization nor the full steady-state schedule can be shortened by this observer.
            assertEquals(600, INITIALIZATION_CALLS_PER_CLIENT)
            assertEquals(1_800, RpcCapacityContract.STEADY_SECONDS)
        }
    }

    @Test
    fun intermediateDisconnectIsDetectedEvenWhenEverySampleAndFinalStateLookReady() = runTest {
        val states = states(256)
        launch {
            delay(12_500)
            states.first().value = RpcConnectionState.Closed
            delay(1)
            states.first().value = RpcConnectionState.Ready
        }
        val outcome = observe(states)
        assertFalse(outcome.mechanical)
        assertTrue(states.all { it.value == RpcConnectionState.Ready && it.subscriptionCount.value == 0 })
        assertEquals(1L, outcome.measurements.getValue("connectionChanges"))
        assertTrue(outcome.samples.all { it.getValue("connected") == 256L })
    }

    @Test
    fun missingClientOrInterveningRpcWorkCannotBeCalledConnectedIdle() = runTest {
        val incomplete = states(128).also { it.last().value = RpcConnectionState.Closed }
        val missing = observe(incomplete)
        assertFalse(missing.mechanical)
        assertEquals("baseline", missing.failureStage)
        assertEquals(127L, missing.measurements.getValue("hostConnectionsBefore"))
        assertTrue(incomplete.all { it.subscriptionCount.value == 0 })
        val states = states(256)
        var samples = 0
        val traffic = observe(states) { sample(256, accepted = 153_600L + if (samples++ == 0) 0 else 1) }
        assertFalse(traffic.mechanical)
        assertEquals(1L, traffic.measurements.getValue("hostAcceptedDelta"))
        assertEquals(1L, traffic.measurements.getValue("hostCompletedDelta"))
        assertEquals(1L, traffic.measurements.getValue("invalidHostSamples"))
        assertTrue(states.all { it.subscriptionCount.value == 0 })
    }

    @Test
    fun cpuCounterRegressionIsPreservedAsFailedEvidenceRatherThanClampedToZero() = runTest {
        val states = states(128)
        var samples = 0
        val outcome = observe(states) { sample(128, cpu = if (samples++ == 0) 1_000 else 900) }
        assertFalse(outcome.mechanical)
        assertEquals(-100L, outcome.measurements.getValue("hostCpuDeltaNanos"))
        assertEquals(1L, outcome.measurements.getValue("invalidHostSamples"))
        assertTrue(states.all { it.subscriptionCount.value == 0 })
    }

    @Test
    fun driverClockCannotSubstituteForTheActualHostIdleDuration() = runTest {
        val states = states(256)
        val outcome = observe(states) { sample(256, uptime = testScheduler.currentTime / 2) }
        assertFalse(outcome.mechanical)
        assertEquals("observe", outcome.failureStage)
        assertEquals(CAPACITY_IDLE_TIMEOUT_MILLIS, testScheduler.currentTime)
        assertTrue(outcome.measurements.getValue("hostUptimeDeltaMillis") < CAPACITY_IDLE_REQUIRED_MILLIS)
        assertTrue(states.all { it.subscriptionCount.value == 0 })
    }

    @Test
    fun aCachedFirstHostSampleCannotShortenTheRegisteredObserverWindowToTwentyFiveSeconds() = runTest {
        val states = states(256)
        var samples = 0
        val outcome = observe(states) {
            sample(256, uptime = if (samples++ == 0) 10_000 else testScheduler.currentTime + 5_000)
        }
        assertTrue(outcome.mechanical)
        assertEquals(30_000_000_000L, outcome.measurements.getValue("driverElapsedNanos"))
        assertEquals(35_000L, outcome.measurements.getValue("hostUptimeDeltaMillis"))
        assertEquals(40_000L, testScheduler.currentTime)
        assertEquals(7, outcome.samples.size)
        assertTrue(states.all { it.subscriptionCount.value == 0 })
    }

    @Test
    fun aHostClockJumpCannotQualifyAShorterObservedInterval() = runTest {
        val states = states(128)
        var samples = 0
        val outcome = observe(states) {
            sample(128, uptime = if (samples++ == 0) 10_000 else testScheduler.currentTime + 25_000)
        }
        assertFalse(outcome.mechanical)
        assertEquals("validation", outcome.failureStage)
        assertEquals(55_000L, outcome.measurements.getValue("hostUptimeDeltaMillis"))
        assertEquals(30_000_000_000L, outcome.measurements.getValue("driverElapsedNanos"))
        assertTrue(states.all { it.subscriptionCount.value == 0 })
    }

    @Test
    fun unavailableTelemetryFailsWithinItsBoundAndRetiresAllStateCollectors() = runTest {
        val states = states(256)
        val outcome = observe(states) { awaitCancellation() }
        assertFalse(outcome.mechanical)
        assertEquals("baseline", outcome.failureStage)
        assertEquals(15_000L, testScheduler.currentTime)
        assertTrue(outcome.samples.isEmpty())
        assertEquals(0L, outcome.measurements.getValue("sampleCount"))
        assertTrue(states.all { it.subscriptionCount.value == 0 })
    }

    @Test
    fun externalCancellationDoesNotProduceAPassOrRetainObservers() = runTest {
        val states = states(128)
        val program = async { observe(states) }
        delay(12_000)
        assertTrue(states.all { it.subscriptionCount.value == 1 })
        program.cancelAndJoin()
        assertTrue(program.isCancelled)
        assertTrue(states.all { it.subscriptionCount.value == 0 })
    }

    @Test
    fun schemaTwoJsonBindsActualArtifactsAndNeverClaimsCapacityQualification() = runTest {
        val outcome = observe(states(256))
        val manifest = RpcCapacityManifest("idle-fixture", RpcCapacityHostPlatform.Ios,
            "a".repeat(40), "b".repeat(64), "c".repeat(64))
        val record = Json.parseToJsonElement(outcome.json(manifest)).jsonObject
        assertEquals(2, record.getValue("schema").jsonPrimitive.int)
        assertEquals(256, record.getValue("clientCount").jsonPrimitive.int)
        assertEquals(manifest.hostSourceSha, record.getValue("sourceSha").jsonPrimitive.content)
        assertEquals(manifest.hostArtifactSha256, record.getValue("hostArtifactSha256").jsonPrimitive.content)
        assertEquals(manifest.driverArtifactSha256, record.getValue("driverArtifactSha256").jsonPrimitive.content)
        assertEquals("Ios", record.getValue("hostPlatform").jsonPrimitive.content)
        assertFalse(record.getValue("capacityQualified").jsonPrimitive.boolean)
        assertEquals("OBSERVED_CONNECTED_IDLE_NOT_CAPACITY", record.getValue("status").jsonPrimitive.content)
    }
}
