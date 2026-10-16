package dev.p2pkit.sample.rpc.lab

import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcPlatform
import dev.p2pkit.rpc.RpcTrustPurpose
import dev.p2pkit.rpc.jvm
import dev.p2pkit.sample.rpc.RpcCapacityContract
import dev.p2pkit.sample.rpc.RpcCapacityHost
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import java.nio.file.Files
import java.nio.file.LinkOption
import kotlin.system.exitProcess

/** Only the explicitly selected synthetic fixture procedures are exposed; never arbitrary remote code. */
public fun main(args: Array<String>) {
    val checks = args.contentEquals(arrayOf("--owner-authorized-correctness-host"))
    require(checks || args.contentEquals(arrayOf("--owner-authorized-capacity-host")))
    var phase = "configuration"
    try {
        runBlocking(Dispatchers.Default) {
            val config = LabConfig.load("host")
            val directory = config.directory
            val pinLines = LabFiles.read(directory.resolve("client-pins.txt")).toString(Charsets.US_ASCII)
                .split('\n').filter { it.isNotEmpty() }
            require(pinLines.size == 128 && pinLines.toSet().size == 128)
            val pins = pinLines.map(PeerFingerprint::parse).toSet()
            val digest = artifactDigest(directory)
            val vault = LabVault(LabFiles.newDirectory(directory, "host-vault"))
            val trust = LabTrustStore(vault)
            var host: LabRunningHost? = null
            var sequence = 0L
            try {
                phase = "trust-provisioning"
                trust.replace(RpcCapacityContract.appId, RpcTrustPurpose.HostClients, pins)
                phase = "host-creation"
                val running = if (checks) {
                    LabRpcChecks.host(RpcPlatform.jvm(vault), this, config.lan, trust, pins)
                } else {
                    LabRunningHost.capacity(
                        RpcCapacityHost.create(RpcPlatform.jvm(vault), this, config.lan, trust, pins),
                    )
                }
                host = running
                phase = "host-start"
                withTimeout(30_000) { running.start() }
                require(running.endpoint().port == config.port)
                fun sample() {
                    val values = LabTelemetry.sample(running.snapshot(), sequence++, config.runLabel)
                    val bytes = LabFiles.encode(values)
                    LabFiles.write(directory.resolve("host-telemetry.txt"), bytes, replace = true)
                    // Every actual host sample is retained independently from driver observations.
                    LabFiles.write(directory.resolve("sample-${sequence.toString().padStart(5, '0')}.txt"), bytes)
                }
                sample()
                LabFiles.write(directory.resolve("host-ready.txt"), LabFiles.encode(linkedMapOf(
                    "schema" to "1", "runLabel" to config.runLabel, "sourceSha" to config.sourceSha,
                    "artifactSha256" to digest, "fingerprint" to running.fingerprint.value,
                    "address" to config.endpointAddress, "port" to config.port.toString(),
                )))
                phase = "measurement"
                println("SYNTHETIC_HOST_READY: ${config.runLabel}; source=${config.sourceSha}; artifact=$digest")
                // Fixed outer lifespan includes setup, 30-minute workload, drain and retention review.
                withTimeout(2_400_000) {
                    while (!Files.exists(directory.resolve("stop.txt"), LinkOption.NOFOLLOW_LINKS)) {
                        delay(1_000)
                        sample()
                    }
                    require(LabFiles.parse(LabFiles.read(directory.resolve("stop.txt"))) == mapOf("stop" to "true"))
                }
                println("SYNTHETIC_HOST_STOP_REQUESTED")
            } finally {
                withContext(NonCancellable) {
                    try { host?.close() } finally { vault.destroy() }
                    LabFiles.write(
                        directory.resolve("host-closed.txt"), "closed=true\nfixturesRemoved=true\n".toByteArray(),
                    )
                }
            }
        }
    } catch (failure: RpcFailure) {
        System.err.println("SYNTHETIC_HOST_FAILED: $phase/${failure.kind}/${failure.phase}; no capacity pass")
        exitProcess(1)
    } catch (_: Exception) {
        System.err.println("SYNTHETIC_HOST_FAILED: $phase; setup, telemetry or cleanup failed; no capacity pass")
        exitProcess(1)
    }
}
