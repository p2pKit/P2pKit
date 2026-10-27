package dev.p2pkit.sample.android.rpclab

import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.Build
import android.os.PowerManager
import dev.p2pkit.sample.rpc.RpcPhoneEnvironmentStats

/** Optional, self-device measurements for the foreground USB campaign. No listener or wake lock is acquired. */
internal class AndroidRpcPhoneEnvironment(context: Context) {
    private val application = context.applicationContext
    private val batteryManager = application.getSystemService(BatteryManager::class.java)
    private val powerManager = application.getSystemService(PowerManager::class.java)

    fun sample(): RpcPhoneEnvironmentStats {
        // A null receiver reads the current sticky record; it does not register a callback that needs retirement.
        val battery = optionalObservation {
            application.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        }
        val current = optionalObservation {
            batteryManager?.getLongProperty(BatteryManager.BATTERY_PROPERTY_CURRENT_NOW)
        }
        val thermal = if (Build.VERSION.SDK_INT >= 29) optionalObservation { powerManager?.currentThermalStatus }
            else null
        return androidRpcEnvironmentStats(
            level = battery?.takeIf { it.hasExtra(BatteryManager.EXTRA_LEVEL) }
                ?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1),
            scale = battery?.takeIf { it.hasExtra(BatteryManager.EXTRA_SCALE) }
                ?.getIntExtra(BatteryManager.EXTRA_SCALE, -1),
            status = battery?.takeIf { it.hasExtra(BatteryManager.EXTRA_STATUS) }
                ?.getIntExtra(BatteryManager.EXTRA_STATUS, -1),
            plugged = battery?.takeIf { it.hasExtra(BatteryManager.EXTRA_PLUGGED) }
                ?.getIntExtra(BatteryManager.EXTRA_PLUGGED, -1),
            currentMicroamps = current,
            temperatureDeciC = battery?.takeIf { it.hasExtra(BatteryManager.EXTRA_TEMPERATURE) }
                ?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, Int.MIN_VALUE),
            thermalStatus = thermal,
            batteryObserved = battery != null || current?.let { it != Long.MIN_VALUE } == true,
        )
    }
}

private inline fun <T> optionalObservation(read: () -> T?): T? = try { read() } catch (_: Exception) { null }

/** Separately testable normalization of public Android readings; unavailable values are never synthetic zeroes. */
internal fun androidRpcEnvironmentStats(
    level: Int?, scale: Int?, status: Int?, plugged: Int?, currentMicroamps: Long?,
    temperatureDeciC: Int?, thermalStatus: Int?, batteryObserved: Boolean,
): RpcPhoneEnvironmentStats {
    val percent = if (level != null && scale != null && scale > 0 && level in 0..scale)
        (level.toLong() * 100_000 / scale).toInt() else null
    val current = currentMicroamps?.takeIf { it in -20_000_000L..20_000_000L }
    // ACTION_BATTERY_CHANGED reports battery temperature in tenths of a degree C, not CPU/ambient temperature.
    val temperature = temperatureDeciC?.takeIf { it in -400..1_000 }?.times(100)
    val batteryState = when {
        !batteryObserved -> "unavailable"
        status == BatteryManager.BATTERY_STATUS_FULL -> "full"
        status == BatteryManager.BATTERY_STATUS_CHARGING -> "charging"
        plugged == 0 -> "unplugged"
        else -> "unknown"
    }
    val thermal = when (thermalStatus) {
        PowerManager.THERMAL_STATUS_NONE -> "nominal"
        PowerManager.THERMAL_STATUS_LIGHT, PowerManager.THERMAL_STATUS_MODERATE -> "fair"
        PowerManager.THERMAL_STATUS_SEVERE -> "serious"
        PowerManager.THERMAL_STATUS_CRITICAL, PowerManager.THERMAL_STATUS_EMERGENCY,
        PowerManager.THERMAL_STATUS_SHUTDOWN -> "critical"
        else -> "unavailable"
    }
    return RpcPhoneEnvironmentStats(
        batteryPercentMilli = percent,
        batteryCurrentMicroamps = current,
        batteryTemperatureMilliC = temperature,
        batteryState = batteryState,
        batterySource = if (batteryObserved) "android-battery-manager" else "unavailable",
        thermalState = thermal,
        thermalSource = if (thermal == "unavailable") "unavailable" else "android-power-manager",
    )
}
