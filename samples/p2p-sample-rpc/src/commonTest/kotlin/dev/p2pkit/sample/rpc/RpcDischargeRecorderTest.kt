package dev.p2pkit.sample.rpc

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

class RpcDischargeRecorderTest {
    private fun recorder() = RpcDischargeRecorder("discharge-" + "1".repeat(32), "Ios",
        "2".repeat(64), "3".repeat(40))

    private fun readings(state: String = "unplugged", thermal: String = "nominal") =
        RpcPhoneEnvironmentStats(70_000, null, null, state, "ios-uidevice", thermal, "ios-process-info")

    @Test
    fun fullRecordIsBoundedAndCarriesOnlyAvailableSensors() {
        val recorder = recorder()
        var last = ""
        repeat(1_801) { second -> recorder.observe(second * 1_000L, readings())?.let { last = it } }
        val fields = parseMobileRecord(last)
        assertFalse(recorder.active)
        assertEquals("complete", fields["status"])
        assertEquals("0,70000,unavailable,unavailable,unplugged,nominal", fields["sample000"])
        assertEquals("1800000,70000,unavailable,unavailable,unplugged,nominal", fields["sample180"])
        assertTrue(last.length <= 16_384)
        assertNull(recorder.interrupt())
    }

    @Test
    fun powerAndThermalChangesAreRetainedImmediatelyBetweenCheckpoints() {
        for ((sensor, expected) in listOf(
            readings(state = "full") to "power-changed",
            readings(thermal = "critical") to "thermal-stop",
        )) {
            val recorder = recorder()
            recorder.observe(0, readings())
            assertEquals(expected, parseMobileRecord(checkNotNull(recorder.observe(1_000, sensor)))["status"])
            assertFalse(recorder.active)
        }
    }

    @Test
    fun missingIntervalsAndInterruptedRunsCannotComplete() {
        val skipped = recorder()
        skipped.observe(0, readings())
        assertEquals("sample-gap", parseMobileRecord(checkNotNull(skipped.observe(3_001, readings())))["status"])
        val interrupted = recorder()
        interrupted.observe(0, readings())
        assertEquals("interrupted", parseMobileRecord(checkNotNull(interrupted.interrupt()))["status"])
        assertNull(interrupted.interrupt())
    }
}
