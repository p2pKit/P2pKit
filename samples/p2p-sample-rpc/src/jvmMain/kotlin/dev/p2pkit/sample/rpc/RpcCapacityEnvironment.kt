package dev.p2pkit.sample.rpc

import dev.p2pkit.core.security.JvmSecureIdentityStore
import dev.p2pkit.rpc.RpcSelectedHost
import dev.p2pkit.rpc.RpcTrustStore
import dev.p2pkit.transport.lan.OrganizationLan

public enum class RpcCapacityHostPlatform { Jvm, Android, Ios }

/** Non-secret artifact labels only; never include hardware identifiers, user names, endpoints or pins. */
public class RpcCapacityManifest(
    public val runLabel: String,
    public val hostPlatform: RpcCapacityHostPlatform,
    public val hostSourceSha: String,
    public val hostArtifactSha256: String,
    public val driverArtifactSha256: String,
) {
    init {
        require(runLabel.matches(Regex("[a-z0-9-]{1,64}")))
        require(hostSourceSha.matches(Regex("[a-f0-9]{40}")))
        require(listOf(hostArtifactSha256, driverArtifactSha256).all { it.matches(Regex("[a-f0-9]{64}")) })
    }
}

/** Must describe the actual HOST process, not the JVM driving its clients. No sentinel/estimated values. */
public class RpcCapacityHostTelemetry(
    public val host: RpcCapacityHostSnapshot,
    public val uptimeMillis: Long,
    public val processCpuNanos: Long,
    public val residentBytes: Long,
    public val liveThreads: Int,
) {
    init {
        require(uptimeMillis >= 0 && processCpuNanos >= 0 && residentBytes > 0 && liveThreads > 0)
    }
}

/**
 * Test-driver integration, not an injectable RPC transport. Supply exactly one reviewed local
 * ServiceLoader provider on the driver's classpath. There is deliberately no provider, key material,
 * in-memory trust fallback, secret CLI argument, hosted executor, or automatic pairing in this sample.
 * Provision 128 different protected identities and durably approve them on the selected host first.
 */
public interface RpcCapacityEnvironment {
    public val manifest: RpcCapacityManifest
    public val lan: OrganizationLan
    public val selectedHost: RpcSelectedHost

    /** Each index must have independent, durable, protected identity storage. */
    public suspend fun identityStore(clientIndex: Int): JvmSecureIdentityStore

    /** Local durable trust for that client; must already contain selectedHost's full AppId-bound pin. */
    public suspend fun trustStore(clientIndex: Int): RpcTrustStore

    /**
     * Obtain a recent snapshot from the real foreground host using an owner-approved local test
     * integration. Collection must cooperate with cancellation and must not export application data.
     * Capture CPU/RSS/thread values with platform-local facilities, not guessed SDK counters.
     */
    public suspend fun sampleHost(): RpcCapacityHostTelemetry

    /** Release provider-owned resources. Never delete/reorganize someone else's evidence or identities. */
    public suspend fun close()
}
