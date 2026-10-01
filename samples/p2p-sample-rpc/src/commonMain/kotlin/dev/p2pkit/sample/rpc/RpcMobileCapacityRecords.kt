package dev.p2pkit.sample.rpc

import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcDiagnostics

/** Private USB control records for the foreground test apps, never an RPC protocol or a public report. */
public class RpcMobileCapacityConfig private constructor(internal val fields: Map<String, String>) {
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

    internal fun binding(): Map<String, String> = fields.filterKeys { it in BINDING_FIELDS } +
        mapOf("schema" to "1", "scope" to "mobile-usb-capacity")

    public companion object {
        internal val BINDING_FIELDS = setOf(
            "runLabel", "runNonce", "hostPlatform", "hostSourceSha", "hostArtifactSha256",
        )

        /** Parsing never authorizes an interface, host role, trust import or network operation. */
        @Throws(Exception::class)
        public fun parse(text: String): RpcMobileCapacityConfig {
            val fields = parseMobileRecord(text)
            require(fields.keys == BINDING_FIELDS + setOf(
                "schema", "scope", "subnets", "hostInterface", "hostAddress", "hostPort", "clientPins",
            ))
            require(fields.getValue("schema") == "1" && fields.getValue("scope") == "mobile-usb-capacity")
            require(fields.getValue("runLabel").matches(Regex("[a-z0-9-]{1,64}")))
            require(fields.getValue("runNonce").matches(Regex("[a-f0-9]{64}")))
            require(fields.getValue("hostSourceSha").matches(Regex("[a-f0-9]{40}")))
            require(fields.getValue("hostArtifactSha256").matches(Regex("[a-f0-9]{64}")))
            require(fields.getValue("hostPlatform") in setOf("Android", "Ios"))
            require(fields.getValue("hostPort").matches(Regex("[1-9][0-9]{3,4}")))
            return RpcMobileCapacityConfig(fields).also {
                it.settings.policy(host = true) // The original organization policy, not a test whitelist.
                require(it.pins.size == RpcCapacityContract.CLIENTS)
            }
        }
    }
}

/** Actual self-process counters from the phone OS. CPU precision is recorded, not invented by unit conversion. */
public class RpcPhoneProcessStats @Throws(Exception::class) constructor(
    public val cpuNanos: Long,
    public val residentBytes: Long,
    public val nativeThreads: Int,
) {
    init { require(cpuNanos >= 0 && residentBytes > 0 && nativeThreads > 0) }
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
    require(sequence >= 0 && elapsedMillis >= 0 && connected in 0..128)
    require(diagnostics.runningCalls in 0..128 && diagnostics.queuedCalls in 0..256 &&
        diagnostics.retainedRecords in 0..131_072 && diagnostics.retainedPayloadBytes in 0..64L * 1_048_576)
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
    return encodeMobileRecord(config.binding() + mobileResources(config.hostPlatform) +
        mapOf("clock" to "host-run-monotonic") + values.mapValues { it.value.toString() })
}

internal fun mobileStopRequested(config: RpcMobileCapacityConfig, text: String): Boolean =
    parseMobileRecord(text) == config.binding() + mapOf("action" to "stop")

internal fun mobileClosedRecord(config: RpcMobileCapacityConfig, controlHealthy: Boolean): String =
    encodeMobileRecord(config.binding() + mapOf(
        "runtimeClosed" to "true", "clientPinsRemoved" to "true", "controlHealthy" to controlHealthy.toString(),
    ))
