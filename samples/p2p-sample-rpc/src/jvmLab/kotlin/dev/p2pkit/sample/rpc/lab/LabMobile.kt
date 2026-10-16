package dev.p2pkit.sample.rpc.lab

import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcDiagnostics
import dev.p2pkit.sample.rpc.RpcCapacityHostPlatform
import dev.p2pkit.sample.rpc.RpcCapacityHostSnapshot
import dev.p2pkit.sample.rpc.RpcCapacityHostTelemetry
import dev.p2pkit.sample.rpc.RpcMobileCapacityConfig
import dev.p2pkit.sample.rpc.RpcPhoneLab
import dev.p2pkit.sample.rpc.encodeMobileRecord
import dev.p2pkit.sample.rpc.mobileResources
import java.nio.file.Files
import java.nio.file.LinkOption

/** Explicit USB control integration. It never supplies or substitutes the RPC data transport. */
internal class LabMobile(private val config: LabConfig, internal val values: Map<String, String>) {
    private val binding = values - "hostInterface"
    val platform: RpcCapacityHostPlatform = RpcCapacityHostPlatform.valueOf(values.getValue("hostPlatform"))
    val artifactSha256: String = values.getValue("hostArtifactSha256")

    init {
        require(values.keys == RpcMobileCapacityConfig.BINDING_FIELDS + setOf("schema", "scope", "hostInterface"))
        require(platform in setOf(RpcCapacityHostPlatform.Android, RpcCapacityHostPlatform.Ios))
        require(values.getValue("runLabel") == config.runLabel && values.getValue("hostSourceSha") == config.sourceSha)
        require(config.sourceSha == RpcPhoneLab.compiledSource)
        require(values.getValue("runNonce").matches(Regex("[a-f0-9]{64}")))
        require(artifactSha256.matches(Regex("[a-f0-9]{64}")))
        require(values.getValue("schema") == "1" && values.getValue("scope") == "mobile-usb-capacity")
    }

    fun prepare(pins: List<PeerFingerprint>) {
        val fields = values + mapOf(
            "subnets" to config.values.getValue("subnets"), "hostAddress" to config.endpointAddress,
            "hostPort" to config.port.toString(), "clientPins" to pins.joinToString(",") { it.value },
        )
        val text = encodeMobileRecord(fields)
        // Apply the SAME phone parser and original OrganizationLan policy before asking the local UI to approve it.
        require(RpcMobileCapacityConfig.parse(text).pins == pins.toSet())
        LabFiles.write(config.directory.resolve("mobile-inbox.txt"), text.toByteArray(Charsets.US_ASCII))
    }

    fun ready(values: Map<String, String>) {
        require(values.keys == binding.keys + setOf(
            "fingerprint", "address", "port", "compiledSourceMatched", "artifactKind",
        ))
        require(values.filterKeys { it in binding } == binding && values.getValue("compiledSourceMatched") == "true")
        require(values.getValue("artifactKind") == if (platform == RpcCapacityHostPlatform.Android)
            "android-installed-base-apk" else "ios-installed-executable")
        require(values.getValue("address") == config.endpointAddress &&
            values.getValue("port") == config.port.toString())
        PeerFingerprint.parse(values.getValue("fingerprint"))
    }

    fun telemetry(values: Map<String, String>): RpcCapacityHostTelemetry {
        val resources = mobileResources(platform.name) + mapOf("clock" to "host-run-monotonic")
        require(values.keys == binding.keys + resources.keys + NUMBERS)
        require(values.filterKeys { it in binding } == binding && values.filterKeys { it in resources } == resources)
        fun long(name: String): Long = values.getValue(name).let {
            require(it.matches(Regex("0|[1-9][0-9]{0,18}")))
            it.toLong().also { number -> require(number >= 0) }
        }
        fun int(name: String): Int = long(name).also { require(it <= Int.MAX_VALUE) }.toInt()
        require(long("sequence") in 0..2_999 && int("connected") in 0..128 && int("running") in 0..128)
        require(int("queued") in 0..256 && int("records") in 0..131_072 && long("payloadBytes") <= 64L * 1_048_576)
        require(long("cpuNanos") % resources.getValue("cpuResolutionNanos").toLong() == 0L)
        return RpcCapacityHostTelemetry(
            RpcCapacityHostSnapshot(int("connected"), RpcDiagnostics(
                long("accepted"), long("completed"), long("refused"), long("duplicates"),
                long("droppedNotifications"), long("protocolFailures"), long("connectionFailures"),
                int("running"), int("queued"), int("records"), long("payloadBytes"),
            )), long("uptimeMillis"), long("cpuNanos"), long("residentBytes"), int("nativeThreads"),
        )
    }

    companion object {
        val NUMBERS = setOf("sequence", "uptimeMillis", "cpuNanos", "residentBytes", "nativeThreads", "connected",
            "accepted", "completed", "refused", "duplicates", "droppedNotifications", "protocolFailures",
            "connectionFailures", "running", "queued", "records", "payloadBytes")

        fun load(config: LabConfig): LabMobile? {
            val input = config.directory.resolve("mobile.txt")
            val authorization = System.getenv("RPC_CAPACITY_MOBILE_AUTHORIZED")
            if (authorization == null) {
                require(!Files.exists(input, LinkOption.NOFOLLOW_LINKS)) {
                    "Mobile control requires explicit authorization"
                }
                return null // Original JVM behavior, not an automatic phone or tunnel fallback.
            }
            require(authorization == "usb-provisioned-physical-phone-no-data-tunnel")
            return LabMobile(config, LabFiles.parse(LabFiles.read(input)))
        }
    }
}
