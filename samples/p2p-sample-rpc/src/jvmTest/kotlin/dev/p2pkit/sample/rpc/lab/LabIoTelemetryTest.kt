package dev.p2pkit.sample.rpc.lab

import dev.p2pkit.rpc.RpcDiagnostics
import dev.p2pkit.sample.rpc.RpcCapacityHostSnapshot
import dev.p2pkit.sample.rpc.RpcCapacityHostTelemetry
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertSame

class LabIoTelemetryTest {
    private fun sample(uptime: Long, completed: Long = 1024, cpu: Long = 123) = RpcCapacityHostTelemetry(
        RpcCapacityHostSnapshot(256, RpcDiagnostics(completedCalls = completed)), uptime, cpu, 1024, 32,
    )

    @Test fun waitsForFiveActualHostSecondsInsteadOfAcceptingAStaleTelemetryCopy() = runTest {
        val start = sample(20_000)
        val fresh = sample(25_001)
        var reads = 0
        assertSame(fresh, withTimeout(5_000) {
            awaitIoIdleTelemetry(start) { if (reads++ < 3) sample(24_024) else fresh }
        })
        assertEquals(4, reads)
    }

    @Test fun stalledHostIsNotSuccessfulAndCounterOrClockRegressionsAreRejected() = runTest {
        val start = sample(20_000)
        assertFailsWith<TimeoutCancellationException> {
            withTimeout(5_000) { awaitIoIdleTelemetry(start) { sample(24_999) } }
        }
        for (invalid in listOf(sample(19_999), sample(25_001, completed = 1025), sample(25_001, cpu = 122))) {
            assertFailsWith<IllegalStateException> { awaitIoIdleTelemetry(start) { invalid } }
        }
    }
}
