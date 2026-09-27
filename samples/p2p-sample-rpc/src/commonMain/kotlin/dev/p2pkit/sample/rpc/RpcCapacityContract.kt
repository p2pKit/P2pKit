package dev.p2pkit.sample.rpc

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.PeerAdmission
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcDiagnostics
import dev.p2pkit.rpc.RpcEndpoint
import dev.p2pkit.rpc.RpcHost
import dev.p2pkit.rpc.RpcLimits
import dev.p2pkit.rpc.RpcPlatform
import dev.p2pkit.rpc.RpcProcedure
import dev.p2pkit.rpc.RpcReply
import dev.p2pkit.rpc.RpcTrustStore
import dev.p2pkit.transport.lan.OrganizationLan
import kotlinx.coroutines.CoroutineScope
import kotlinx.serialization.builtins.serializer

/** Requirements for future measurement, NOT capabilities demonstrated by this source. */
public object RpcCapacityContract {
    public const val CLIENTS: Int = 128
    public const val CALLS_PER_SECOND_PER_CLIENT: Int = 10
    public const val STEADY_SECONDS: Int = 30 * 60
    public const val ENCODED_BYTES: Int = 1024
    public const val MAXIMUM_BODY_BYTES: Int = 1_048_576
    public val appId: AppId = AppId("dev.p2pkit.rpc.qualification.v1")
    public val payload: String = "a".repeat(ENCODED_BYTES - 2)
    public val echo: RpcProcedure<String, String, String> = RpcProcedure(
        "qualification.echo", 1, String.serializer(), String.serializer(), String.serializer(),
        requestLimitBytes = ENCODED_BYTES, responseLimitBytes = ENCODED_BYTES, errorLimitBytes = 256,
    )
    public val largeEcho: RpcProcedure<String, String, String> = RpcProcedure(
        "qualification.large-echo", 1, String.serializer(), String.serializer(), String.serializer(),
        requestLimitBytes = MAXIMUM_BODY_BYTES, responseLimitBytes = MAXIMUM_BODY_BYTES, errorLimitBytes = 256,
    )
}

public class RpcCapacityHostSnapshot internal constructor(
    public val distinctAuthenticatedClients: Int,
    public val diagnostics: RpcDiagnostics,
)

/** Thin shared-Kotlin host facade usable from JVM, Android and an iOS foreground test UI. */
public class RpcCapacityHost private constructor(private val host: RpcHost) {
    public val fingerprint: PeerFingerprint get() = host.fingerprint

    @Throws(Exception::class)
    public suspend fun start() { host.start() }

    @Throws(Exception::class)
    public suspend fun endpoint(): RpcEndpoint = host.endpoint()

    public fun snapshot(): RpcCapacityHostSnapshot = RpcCapacityHostSnapshot(
        host.connections.value.filter {
            it.admission == PeerAdmission.Trusted && it.state == ConnectionState.Connected
        }.mapNotNull { it.peer.fingerprint }.toSet().size,
        host.diagnostics.value,
    )

    @Throws(Exception::class)
    public suspend fun close() { host.close() }

    public companion object {
        @Throws(Exception::class)
        public suspend fun create(
            platform: RpcPlatform, scope: CoroutineScope, lan: OrganizationLan,
            localDurableTrustStore: RpcTrustStore, approvedClients: Set<PeerFingerprint>,
        ): RpcCapacityHost {
            require(approvedClients.size == RpcCapacityContract.CLIENTS)
            val pins = approvedClients.toSet()
            val host = RpcHost.create(platform, scope) {
                appId = RpcCapacityContract.appId
                this.lan = lan
                trustStore = localDurableTrustStore
                limits = RpcLimits.host128()
                advertise = false // Numeric pinned fallback; no discovery dependency in the load experiment.
                register(RpcCapacityContract.echo, authorize = { it.fingerprint in pins }) { _, value ->
                    if (value == RpcCapacityContract.payload) RpcReply.Success(value)
                    else RpcReply.ApplicationError("unexpected synthetic size")
                }
                register(RpcCapacityContract.largeEcho, authorize = { it.fingerprint in pins }) { _, value ->
                    RpcReply.Success(value)
                }
            }
            if (host.trust.fingerprints().toSet() != pins) {
                host.close()
                error("Qualification host requires exactly the 128 durably approved fixture identities")
            }
            return RpcCapacityHost(host)
        }
    }
}
