package dev.p2pkit.sample.android.rpclab

import android.os.BatteryManager
import android.os.PowerManager
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Host normalization controls. These do not measure a battery, thermal service or physical phone. */
class AndroidRpcPhoneEnvironmentTest {
    @Test
    fun publicBatteryUnitsPreserveDischargingCurrentAndBatteryTemperatureResolution() {
        val sample = androidRpcEnvironmentStats(55, 100, BatteryManager.BATTERY_STATUS_DISCHARGING,
            0, -123_456L, 321, PowerManager.THERMAL_STATUS_NONE, true)
        assertEquals(55_000, sample.batteryPercentMilli)
        assertEquals(-123_456L, sample.batteryCurrentMicroamps)
        assertEquals(32_100, sample.batteryTemperatureMilliC)
        assertEquals("unplugged", sample.batteryState)
        assertEquals("android-battery-manager", sample.batterySource)
        assertEquals("nominal", sample.thermalState)
        assertFalse(sample.requiresThermalStop)
        val scaled = androidRpcEnvironmentStats(1, 3, null, 0, null, null, null, true)
        assertEquals(33_333, scaled.batteryPercentMilli)
    }

    @Test
    fun chargingAndFullReadingsAreNotReportedAsBatteryDischarge() {
        for ((status, expected) in listOf(BatteryManager.BATTERY_STATUS_CHARGING to "charging",
            BatteryManager.BATTERY_STATUS_FULL to "full", BatteryManager.BATTERY_STATUS_NOT_CHARGING to "unknown")) {
            val sample = androidRpcEnvironmentStats(100, 100, status, BatteryManager.BATTERY_PLUGGED_USB,
                200_000L, null, null, true)
            assertEquals(expected, sample.batteryState)
            assertEquals(200_000L, sample.batteryCurrentMicroamps)
        }
    }

    @Test
    fun unsupportedInvalidOrAbsentReadingsStayUnavailable() {
        val absent = androidRpcEnvironmentStats(null, null, null, null, Long.MIN_VALUE, null, null, false)
        assertNull(absent.batteryPercentMilli)
        assertNull(absent.batteryCurrentMicroamps)
        assertNull(absent.batteryTemperatureMilliC)
        assertEquals("unavailable", absent.batteryState)
        assertEquals("unavailable", absent.batterySource)
        assertEquals("unavailable", absent.thermalState)
        assertFalse(absent.requiresThermalStop)
        for ((level, scale) in listOf(-1 to 100, 101 to 100, 1 to 0, 0 to -1)) {
            val invalid = androidRpcEnvironmentStats(level, scale, null, null, 20_000_001L,
                Int.MIN_VALUE, 99, true)
            assertNull(invalid.batteryPercentMilli)
            assertNull(invalid.batteryCurrentMicroamps)
            assertNull(invalid.batteryTemperatureMilliC)
            assertEquals("unknown", invalid.batteryState)
            assertEquals("unavailable", invalid.thermalState)
        }
    }

    @Test
    fun severeAndHigherThermalStatesAbortWhileModerateDoesNot() {
        for ((status, state, abort) in listOf(
            Triple(PowerManager.THERMAL_STATUS_NONE, "nominal", false),
            Triple(PowerManager.THERMAL_STATUS_LIGHT, "fair", false),
            Triple(PowerManager.THERMAL_STATUS_MODERATE, "fair", false),
            Triple(PowerManager.THERMAL_STATUS_SEVERE, "serious", true),
            Triple(PowerManager.THERMAL_STATUS_CRITICAL, "critical", true),
            Triple(PowerManager.THERMAL_STATUS_EMERGENCY, "critical", true),
            Triple(PowerManager.THERMAL_STATUS_SHUTDOWN, "critical", true),
        )) {
            val sample = androidRpcEnvironmentStats(null, null, null, null, null, null, status, false)
            assertEquals(state, sample.thermalState)
            assertEquals("android-power-manager", sample.thermalSource)
            assertEquals(abort, sample.requiresThermalStop)
            if (abort) assertTrue(sample.requiresThermalStop)
        }
    }
}
