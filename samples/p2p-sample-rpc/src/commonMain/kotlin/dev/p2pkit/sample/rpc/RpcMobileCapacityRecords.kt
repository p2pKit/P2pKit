package dev.p2pkit.sample.rpc

import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcDiagnostics
import dev.p2pkit.rpc.RpcLimits

/** Private USB control records for the foreground test apps, never an RPC protocol or a public report. */
public class RpcMobileCapacityConfig private constructor(internal val fields: Map<String, String>) {
    public val schema: String get() = fields.getValue("schema")
    public val clientCount: Int get() = fields["clientCount"]?.toInt() ?: RpcCapacityContract.CLIENTS
    public val runLabel: String get() = fields.getValue("runLabel")
    public val hostPlatform: String get() = fields.getValue("hostPlatform")
    public val hostSourceSha: String get() = fields.getValue("hostSourceSha")
    public val hostArtifactSha256: String get() = fields.getValue("hostArtifactSha256")
    public val settings: RpcPhoneSettings get() = RpcPhoneSettings(
        fields.getValue("subnets"), fields.getValue("hostInterface"), fields.getValue("hostAddress"),
        fields.getValue("hostPort").toInt(),
    )
    public val clientPins: String get() = fields.getValue("clientPins").replace(',', '\n')
    internal val pins: Set<PeerFingerprint> get() = RpcPhoneLab.parseCapacityPins(clientPins)

    internal val limits: RpcLimits = capacityProfileLimits(clientCount)

    internal fun binding(): Map<String, String> = fields.filterKeys { it in bindingFields(schema) } +
        mapOf("schema" to schema, "scope" to "mobile-usb-capacity")

    /** The platform may release its old control slot only after this exact run completed healthy retirement. */
    @Throws(Exception::class)
    public fun matchesHealthyClosed(record: String): Boolean = parseMobileRecord(record) == binding() + mapOf(
        "runtimeClosed" to "true", "clientPinsRemoved" to "true", "controlHealthy" to "true",
    )

    public companion object {
        internal val BINDING_FIELDS = setOf(
            "runLabel", "runNonce", "hostPlatform", "hostSourceSha", "hostArtifactSha256",
        )

        internal fun bindingFields(schema: String): Set<String> {
            require(schema in setOf("1", "2"))
            return BINDING_FIELDS + if (schema == "2") setOf("clientCount") else emptySet()
        }

        /** Parsing never authorizes an interface, host role, trust import or network operation. */
        @Throws(Exception::class)
        public fun parse(text: String): RpcMobileCapacityConfig {
            val fields = parseMobileRecord(text)
            val schema = requireNotNull(fields["schema"])
            require(fields.keys == bindingFields(schema) + setOf(
                "schema", "scope", "subnets", "hostInterface", "hostAddress", "hostPort", "clientPins",
            ))
            require(fields.getValue("scope") == "mobile-usb-capacity")
            if (schema == "2") require(fields.getValue("clientCount") in setOf("128", "256"))
            require(fields.getValue("runLabel").matches(Regex("[a-z0-9-]{1,64}")))
            require(fields.getValue("runNonce").matches(Regex("[a-f0-9]{64}")))
            require(fields.getValue("hostSourceSha").matches(Regex("[a-f0-9]{40}")))
            require(fields.getValue("hostArtifactSha256").matches(Regex("[a-f0-9]{64}")))
            require(fields.getValue("hostPlatform") in setOf("Android", "Ios"))
            require(fields.getValue("hostPort").matches(Regex("[1-9][0-9]{3,4}")))
            return RpcMobileCapacityConfig(fields).also {
                it.settings.policy(host = true) // The original organization policy, not a test whitelist.
                require(it.pins.size == it.clientCount)
            }
        }
    }
}

/** Actual self-process counters from the phone OS. CPU precision is recorded, not invented by unit conversion. */
public class RpcPhoneProcessStats @Throws(Exception::class) constructor(
    public val cpuNanos: Long,
    public val residentBytes: Long,
    public val nativeThreads: Int,
    public val environment: RpcPhoneEnvironmentStats? = null,
) {
    init { require(cpuNanos >= 0 && residentBytes > 0 && nativeThreads > 0) }
}

/** Optional OS observations. Missing measurements stay unavailable; charging is never treated as discharge. */
public class RpcPhoneEnvironmentStats @Throws(Exception::class) constructor(
    public val batteryPercentMilli: Int?,
    public val batteryCurrentMicroamps: Long?,
    public val batteryTemperatureMilliC: Int?,
    public val batteryState: String,
    public val batterySource: String,
    public val thermalState: String,
    public val thermalSource: String,
) {
    init {
        require(batteryPercentMilli == null || batteryPercentMilli in 0..100_000)
        require(batteryCurrentMicroamps == null || batteryCurrentMicroamps in -20_000_000L..20_000_000L)
        require(batteryTemperatureMilliC == null || batteryTemperatureMilliC in -40_000..100_000)
        require(batteryState in setOf("unavailable", "unknown", "unplugged", "charging", "full"))
        require(batterySource in setOf("unavailable", "android-battery-manager", "ios-uidevice"))
        require(thermalState in setOf("unavailable", "nominal", "fair", "serious", "critical"))
        require(thermalSource in setOf("unavailable", "android-power-manager", "ios-process-info"))
        if (batterySource == "unavailable") require(batteryPercentMilli == null &&
            batteryCurrentMicroamps == null && batteryTemperatureMilliC == null && batteryState == "unavailable")
        if (batterySource == "ios-uidevice") require(batteryCurrentMicroamps == null &&
            batteryTemperatureMilliC == null)
        require((thermalState == "unavailable") == (thermalSource == "unavailable"))
    }

    public val requiresThermalStop: Boolean get() = thermalState == "serious" || thermalState == "critical"

    internal fun record(platform: String): Map<String, String> {
        require(platform in setOf("Android", "Ios"))
        require(batterySource == "unavailable" || batterySource == if (platform == "Android")
            "android-battery-manager" else "ios-uidevice")
        require(thermalSource == "unavailable" || thermalSource == if (platform == "Android")
            "android-power-manager" else "ios-process-info")
        return linkedMapOf(
            "batteryPercentMilli" to (batteryPercentMilli?.toString() ?: "unavailable"),
            "batteryCurrentMicroamps" to (batteryCurrentMicroamps?.toString() ?: "unavailable"),
            "batteryTemperatureMilliC" to (batteryTemperatureMilliC?.toString() ?: "unavailable"),
            "batteryState" to batteryState, "batterySource" to batterySource,
            "thermalState" to thermalState, "thermalSource" to thermalSource,
        )
    }

    internal companion object {
        val FIELDS = setOf("batteryPercentMilli", "batteryCurrentMicroamps", "batteryTemperatureMilliC",
            "batteryState", "batterySource", "thermalState", "thermalSource")
        val UNAVAILABLE = RpcPhoneEnvironmentStats(null, null, null,
            "unavailable", "unavailable", "unavailable", "unavailable")

        fun parse(values: Map<String, String>, platform: String): RpcPhoneEnvironmentStats {
            require(values.keys == FIELDS)
            fun measured(name: String): Long? = values.getValue(name).let {
                if (it == "unavailable") null else {
                    require(it.matches(Regex("0|-?[1-9][0-9]{0,8}")))
                    it.toLong()
                }
            }
            fun measuredInt(name: String): Int? = measured(name)?.also {
                require(it in Int.MIN_VALUE.toLong()..Int.MAX_VALUE.toLong())
            }?.toInt()
            return RpcPhoneEnvironmentStats(measuredInt("batteryPercentMilli"),
                measured("batteryCurrentMicroamps"), measuredInt("batteryTemperatureMilliC"),
                values.getValue("batteryState"), values.getValue("batterySource"),
                values.getValue("thermalState"), values.getValue("thermalSource")).also { it.record(platform) }
        }
    }
}

internal fun parseMobileRecord(text: String): Map<String, String> {
    require(text.length in 1..16_384 && text.all { it == '\n' || it.code in 32..126 })
    val result = linkedMapOf<String, String>()
    for (line in text.lineSequence().filter(String::isNotEmpty)) {
        val pair = line.split('=', limit = 2)
        require(pair.size == 2 && pair[0].matches(Regex("[A-Za-z][A-Za-z0-9]{0,63}")) && pair[1].isNotEmpty())
        require(result.put(pair[0], pair[1]) == null)
    }
    return result
}

internal fun encodeMobileRecord(fields: Map<String, String>): String = fields.entries.joinToString(
    "\n", postfix = "\n",
) {
    "${it.key}=${it.value}"
}.also { require(parseMobileRecord(it) == fields) }

/** The fixed values identify actual platform collectors. There is deliberately no `jvmThreads` on a phone. */
internal fun mobileResources(platform: String): Map<String, String> = when (platform) {
    "Android" -> mapOf("cpuSource" to "android-process-elapsed-cpu", "cpuResolutionNanos" to "1000000",
        "residentSource" to "proc-self-status", "threadSource" to "proc-self-status")
    "Ios" -> mapOf("cpuSource" to "getrusage-self", "cpuResolutionNanos" to "1000",
        "residentSource" to "mach-task-basic-info", "threadSource" to "mach-task-threads-retired-rights")
    else -> error("Unknown mobile resource collector")
}

internal fun mobileTelemetryRecord(
    config: RpcMobileCapacityConfig, sequence: Long, elapsedMillis: Long, connected: Int,
    diagnostics: RpcDiagnostics, resources: RpcPhoneProcessStats,
): String {
    val limits = config.limits
    require(sequence >= 0 && elapsedMillis >= 0 && connected in 0..config.clientCount)
    require(diagnostics.runningCalls in 0..limits.runningCalls && diagnostics.queuedCalls in 0..limits.queuedCalls &&
        diagnostics.retainedRecords in 0..limits.totalRecords &&
        diagnostics.retainedPayloadBytes in 0..limits.payloadBytes)
    val values = linkedMapOf(
        "sequence" to sequence, "uptimeMillis" to elapsedMillis, "cpuNanos" to resources.cpuNanos,
        "residentBytes" to resources.residentBytes, "nativeThreads" to resources.nativeThreads.toLong(),
        "connected" to connected.toLong(), "accepted" to diagnostics.acceptedCalls,
        "completed" to diagnostics.completedCalls, "refused" to diagnostics.refusedCalls,
        "duplicates" to diagnostics.duplicateRequests, "droppedNotifications" to diagnostics.droppedNotifications,
        "protocolFailures" to diagnostics.protocolFailures, "connectionFailures" to diagnostics.connectionFailures,
        "running" to diagnostics.runningCalls.toLong(), "queued" to diagnostics.queuedCalls.toLong(),
        "records" to diagnostics.retainedRecords.toLong(), "payloadBytes" to diagnostics.retainedPayloadBytes,
    )
    require(values.values.all { it >= 0 })
    val environment = if (config.schema == "2") {
        (resources.environment ?: RpcPhoneEnvironmentStats.UNAVAILABLE).record(config.hostPlatform)
    } else emptyMap()
    return encodeMobileRecord(config.binding() + mobileResources(config.hostPlatform) + environment +
        mapOf("clock" to "host-run-monotonic") + values.mapValues { it.value.toString() })
}

internal fun mobileStopRequested(config: RpcMobileCapacityConfig, text: String): Boolean =
    parseMobileRecord(text) == config.binding() + mapOf("action" to "stop")

internal fun mobileClosedRecord(config: RpcMobileCapacityConfig, controlHealthy: Boolean): String =
    encodeMobileRecord(config.binding() + mapOf(
        "runtimeClosed" to "true", "clientPinsRemoved" to "true", "controlHealthy" to controlHealthy.toString(),
    ))
