package dev.p2pkit.sample.rpc

import kotlinx.serialization.Serializable

/** Latest self-process sample; memory kinds and coarse battery/thermal sensors remain explicit. */
public data class RpcDeviceLiveResources(
    public val memoryBytes: Long,
    public val memoryKind: String,
    public val threads: Int,
    public val threadKind: String,
    public val cpuPercentOfOneCore: Double?,
    public val batteryPercentMilli: Int?,
    public val chargingState: String,
    public val thermalState: String,
    public val batteryTemperatureMilliC: Int?,
    public val batteryCurrentMicroamps: Long?,
) {
    public val title: String get() = "${memoryBytes / 1_048_576} MiB ($memoryKind) · " +
        "$threads threads ($threadKind) · " + (cpuPercentOfOneCore?.let {
            "${(it * 10).toLong() / 10.0}% of one CPU core"
        } ?: "CPU interval unavailable")
    public val environmentTitle: String get() = "Battery: " +
        (batteryPercentMilli?.let { "${it / 1_000}%" } ?: "unavailable") + " · $chargingState · " +
        "thermal category: $thermalState · battery temperature: " +
        (batteryTemperatureMilliC?.let { "${it / 1_000.0} °C" } ?: "unavailable") + " · battery current: " +
        (batteryCurrentMicroamps?.let { "$it µA" } ?: "unavailable")
}

/** Sampled self-process interval only; no battery-energy, CPU-temperature or post-Stop drain claim. */
@Serializable
public data class RpcDeviceTestResources(
    public val samples: Int,
    public val sampledMillis: Long,
    public val cpuDeltaNanos: Long,
    public val peakMemoryBytes: Long,
    public val memoryKind: String,
    public val peakThreads: Int,
    public val threadKind: String,
    public val firstBatteryPercentMilli: Int?,
    public val lastBatteryPercentMilli: Int?,
    public val batteryStates: List<String>,
    public val thermalStates: List<String>,
    public val peakBatteryTemperatureMilliC: Int?,
    public val minBatteryCurrentMicroamps: Long?,
    public val maxBatteryCurrentMicroamps: Long?,
) {
    public val cpuPercentOfOneCore: Double? get() = if (sampledMillis > 0)
        cpuDeltaNanos.toDouble() / (sampledMillis * 10_000.0) else null
    public val title: String get() = "Peak ${peakMemoryBytes / 1_048_576} MiB ($memoryKind) · " +
        "peak $peakThreads threads ($threadKind) · $samples samples · " +
        (cpuPercentOfOneCore?.let { "${(it * 10).toLong() / 10.0}% of one CPU core" } ?: "CPU interval unavailable")
    public val thermalStopped: Boolean get() = thermalStates.any { it == "serious" || it == "critical" }
    public val environmentTitle: String get() = "Battery " +
        (firstBatteryPercentMilli?.let { "${it / 1_000}%" } ?: "unavailable") + " → " +
        (lastBatteryPercentMilli?.let { "${it / 1_000}%" } ?: "unavailable") +
        " · ${batteryStates.joinToString()} · thermal categories: ${thermalStates.joinToString()} · " +
        "peak battery temperature: " +
        (peakBatteryTemperatureMilliC?.let { "${it / 1_000.0} °C" } ?: "unavailable") +
        " · current: ${minBatteryCurrentMicroamps ?: "unavailable"} / " +
        "${maxBatteryCurrentMicroamps ?: "unavailable"} µA"
}

internal data class DeviceResourceWindow(
    val runId: String, val firstMillis: Long? = null, val lastMillis: Long = 0,
    val firstCpu: Long = 0, val lastCpu: Long = 0, val summary: RpcDeviceTestResources? = null,
) {
    fun observe(millis: Long, cpu: Long, memory: Long, memoryKind: String, threads: Int, threadKind: String,
        environment: RpcPhoneEnvironmentStats?): DeviceResourceWindow {
        val old = summary
        if (old != null && millis - lastMillis < 1_000 && environment?.requiresThermalStop != true) return this
        require(firstMillis == null || (millis >= lastMillis && cpu >= lastCpu))
        require(old == null || (old.memoryKind == memoryKind && old.threadKind == threadKind))
        val now = RpcDeviceTestResources((old?.samples ?: 0) + 1, millis - (firstMillis ?: millis),
            cpu - if (old == null) cpu else firstCpu, maxOf(old?.peakMemoryBytes ?: 0, memory), memoryKind,
            maxOf(old?.peakThreads ?: 0, threads), threadKind,
            if (old == null) environment?.batteryPercentMilli else old.firstBatteryPercentMilli,
            environment?.batteryPercentMilli,
            ((old?.batteryStates ?: emptyList()) + (environment?.batteryState ?: "unavailable")).distinct(),
            ((old?.thermalStates ?: emptyList()) + (environment?.thermalState ?: "unavailable")).distinct(),
            listOfNotNull(old?.peakBatteryTemperatureMilliC, environment?.batteryTemperatureMilliC).maxOrNull(),
            listOfNotNull(old?.minBatteryCurrentMicroamps, environment?.batteryCurrentMicroamps).minOrNull(),
            listOfNotNull(old?.maxBatteryCurrentMicroamps, environment?.batteryCurrentMicroamps).maxOrNull())
        return copy(firstMillis = firstMillis ?: millis, lastMillis = millis,
            firstCpu = if (old == null) cpu else firstCpu, lastCpu = cpu, summary = now)
    }
}

internal fun validDeviceResources(value: RpcDeviceTestResources?, longObservation: Boolean = false): Boolean = value == null ||
    (value.samples in 1..(if (longObservation) 100_000 else 3_000) &&
        value.sampledMillis in 0..(if (longObservation) 86_400_000L else 1_850_000L) &&
        value.cpuDeltaNanos in 0..(if (longObservation) 11_059_200_000_000_000L else 100_000_000_000_000L) &&
        value.peakMemoryBytes in 1..68_719_476_736 && value.memoryKind in setOf("RESIDENT_BYTES", "JVM_HEAP_BYTES") &&
        value.peakThreads in 1..100_000 && value.threadKind in setOf("NATIVE_THREADS", "JVM_THREADS") &&
        (value.firstBatteryPercentMilli == null || value.firstBatteryPercentMilli in 0..100_000) &&
        (value.lastBatteryPercentMilli == null || value.lastBatteryPercentMilli in 0..100_000) &&
        value.batteryStates.size in 1..5 && value.batteryStates.all {
            it in setOf("unavailable", "unknown", "unplugged", "charging", "full")
        } && value.thermalStates.size in 1..5 && value.thermalStates.all {
            it in setOf("unavailable", "nominal", "fair", "serious", "critical")
        } && (value.peakBatteryTemperatureMilliC == null || value.peakBatteryTemperatureMilliC in -40_000..100_000) &&
        (value.minBatteryCurrentMicroamps == null || value.minBatteryCurrentMicroamps in -20_000_000L..20_000_000L) &&
        (value.maxBatteryCurrentMicroamps == null || value.maxBatteryCurrentMicroamps in -20_000_000L..20_000_000L))
