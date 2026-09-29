package dev.p2pkit.sample.rpc.lab

import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.security.JvmSecureIdentityStore
import dev.p2pkit.rpc.RpcClient
import dev.p2pkit.rpc.RpcEndpoint
import dev.p2pkit.rpc.RpcPlatform
import dev.p2pkit.rpc.RpcSelectedHost
import dev.p2pkit.rpc.RpcTrustPurpose
import dev.p2pkit.rpc.RpcTrustStore
import dev.p2pkit.rpc.jvm
import dev.p2pkit.sample.rpc.RpcCapacityContract
import dev.p2pkit.sample.rpc.RpcCapacityEnvironment
import dev.p2pkit.sample.rpc.RpcCapacityHostPlatform
import dev.p2pkit.sample.rpc.RpcCapacityHostTelemetry
import dev.p2pkit.sample.rpc.RpcCapacityManifest
import dev.p2pkit.transport.lan.OrganizationLan
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import java.nio.file.Files
import java.nio.file.LinkOption
import java.time.Instant

/** Loaded only by the separate lab compilation, with explicit owner-scoped configuration. */
public class LabEnvironment : RpcCapacityEnvironment {
    private val config = LabConfig.load("client")
    private val directory = config.directory
    private val identities = List(128) { index ->
        LabVault(LabFiles.newDirectory(directory, "client-$index"))
    }
    private val trusts = identities.map(::LabTrustStore)
    override val lan: OrganizationLan = config.lan
    override val selectedHost: RpcSelectedHost
    override val manifest: RpcCapacityManifest
    private var sequence = -1L
    private var closed = false

    init {
        try {
            val driverDigest = artifactDigest(directory)
            val preparedPins = runBlocking {
                val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
                try {
                    identities.mapIndexed { index, store ->
                        val client = RpcClient.create(RpcPlatform.jvm(store), scope) {
                            appId = RpcCapacityContract.appId
                            lan = this@LabEnvironment.lan
                            trustStore = trusts[index]
                        }
                        try { client.fingerprint } finally { client.close() }
                    }
                } finally { scope.cancel() }
            }
            require(preparedPins.toSet().size == 128)
            LabFiles.write(directory.resolve("client-pins.txt"), preparedPins.joinToString("\n", postfix = "\n") {
                it.value
            }.toByteArray())
            // The owner-scoped coordinator copies only these public synthetic pins through pinned SSH.
            // It must return the selected host's verified readiness file; no discovery or TOFU is used.
            val ready = runBlocking {
                withTimeout(120_000) {
                    val path = directory.resolve("host-ready.txt")
                    while (!Files.exists(path, LinkOption.NOFOLLOW_LINKS)) delay(100)
                    LabFiles.parse(LabFiles.read(path))
                }
            }
            require(ready.keys == setOf("schema", "runLabel", "sourceSha", "artifactSha256", "fingerprint", "address", "port"))
            require(ready.getValue("schema") == "1" && ready.getValue("runLabel") == config.runLabel)
            require(ready.getValue("sourceSha") == config.sourceSha)
            require(ready.getValue("address") == config.endpointAddress && ready.getValue("port").toInt() == config.port)
            selectedHost = RpcSelectedHost(
                PeerFingerprint.parse(ready.getValue("fingerprint")), RpcEndpoint(config.endpointAddress, config.port),
            )
            runBlocking {
                trusts.forEach { it.replace(RpcCapacityContract.appId, RpcTrustPurpose.SelectedHosts, setOf(selectedHost.fingerprint)) }
            }
            manifest = RpcCapacityManifest(
                config.runLabel, RpcCapacityHostPlatform.Jvm, config.sourceSha, ready.getValue("artifactSha256"), driverDigest,
            )
        } catch (failure: Exception) {
            identities.forEach(LabVault::close)
            throw failure
        }
    }

    override suspend fun identityStore(clientIndex: Int): JvmSecureIdentityStore = identities[clientIndex]
    override suspend fun trustStore(clientIndex: Int): RpcTrustStore = trusts[clientIndex]

    override suspend fun sampleHost(): RpcCapacityHostTelemetry {
        val file = directory.resolve("host-telemetry.txt")
        val values = LabFiles.parse(LabFiles.read(file))
        val next = values.getValue("sequence").toLong()
        // Local receipt mtime is set by the authenticated coordinator, not copied from a remote clock.
        val age = Instant.now().toEpochMilli() - Files.getLastModifiedTime(file, LinkOption.NOFOLLOW_LINKS).toMillis()
        require(age in 0..15_000 && next > sequence) { "Stale/replayed host telemetry" }
        val sample = LabTelemetry.decode(values, config.runLabel)
        sequence = next
        return sample
    }

    override suspend fun close() {
        if (!closed) {
            closed = true
            identities.forEach(LabVault::close)
            LabFiles.write(directory.resolve("clients-closed.txt"), "closed=true\n".toByteArray())
        }
    }
}
