package dev.p2pkit.sample.rpc

import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcClient
import dev.p2pkit.rpc.RpcDiagnostics
import dev.p2pkit.rpc.RpcEndpoint
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcHost
import dev.p2pkit.rpc.RpcInvitation
import dev.p2pkit.rpc.RpcLimits
import dev.p2pkit.rpc.RpcPlatform
import dev.p2pkit.rpc.RpcReply
import dev.p2pkit.rpc.RpcSelectedHost
import dev.p2pkit.rpc.RpcTrustPurpose
import dev.p2pkit.rpc.RpcTrustStore
import dev.p2pkit.transport.lan.OrganizationLan
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.supervisorScope
import kotlinx.coroutines.withContext
import kotlin.time.TimeSource

/** Explicit numeric organization policy. No automatic interface, peer, role or routing selection. */
public class RpcPhoneSettings(
    public val subnets: String,
    public val interfaceName: String,
    public val localAddress: String,
    public val port: Int,
) {
    init { require(port in 1024..65535 && subnets.length in 1..512) }
    internal fun policy(host: Boolean): OrganizationLan = OrganizationLan(
        subnets.split(',').map(String::trim), interfaceName, localAddress, if (host) port else 0,
    )
}

/** Local administrator UI only. Never include these pins/requests in exported diagnostics. */
public class RpcPhonePairing(public val requestId: String, public val fingerprint: String)

/** Synthetic measurements only; not a physical-host, load, throughput or release qualification. */
public class RpcPhoneCallResult(
    public val completed: Int,
    public val expected: Int,
    public val elapsedMillis: Long,
    public val failureKind: String?,
    public val executionEvidence: String?,
)

/** Explicit Kotlin cancellation bridge; cancelling a Swift Task alone is not this operation's cancellation. */
public class RpcPhoneOperation internal constructor(private val job: Job) {
    public fun cancel() { job.cancel() }
    public val active: Boolean get() = job.isActive
}

/**
 * Foreground-only phone test facade. Only fixed synthetic echo procedures are registered.
 * OS identity storage comes from RpcPlatform; the app supplies a local protected trust store.
 * Use a fresh controller after an explicit role change; close and await it before replacement.
 */
public class RpcPhoneLab private constructor(
    private val scope: CoroutineScope,
    private val host: RpcHost?,
    private val client: RpcClient?,
) {
    private val callBusy = MutableStateFlow(false)
    public val fingerprint: String get() = (host?.fingerprint ?: checkNotNull(client).fingerprint).value
    public val state: String get() = host?.state?.value?.name ?: checkNotNull(client).state.value.name
    public val diagnostics: RpcDiagnostics get() = host?.diagnostics?.value ?: checkNotNull(client).diagnostics.value
    public val connectedClients: Int get() = host?.connections?.value?.filter {
        it.state == dev.p2pkit.core.ConnectionState.Connected &&
            it.admission == dev.p2pkit.core.PeerAdmission.Trusted
    }?.mapNotNull { it.peer.fingerprint }?.toSet()?.size ?: 0

    @Throws(Exception::class)
    public suspend fun invitation(): String {
        val invitation = checkNotNull(host).pairing.createInvitation()
        return try { invitation.qr } finally { invitation.clear() }
    }

    public fun pending(): List<RpcPhonePairing> = checkNotNull(host).pairing.pending.value.map {
        RpcPhonePairing(it.id, checkNotNull(it.peer.fingerprint).value)
    }

    @Throws(Exception::class)
    public suspend fun approve(requestId: String) { checkNotNull(host).pairing.approve(requestId) }

    @Throws(Exception::class)
    public suspend fun revoke(fingerprint: String) {
        (host?.trust ?: checkNotNull(client).trust).revoke(PeerFingerprint.parse(fingerprint))
    }

    /** The invitation must be obtained from the explicitly selected host's trusted LOCAL UI. */
    @Throws(Exception::class)
    public suspend fun pairAndConnect(qr: String) {
        val invitation = RpcInvitation.parse(qr)
        val selected = try { checkNotNull(client).pair(invitation) } finally { invitation.clear() }
        checkNotNull(client).connect(selected)
    }

    /** Existing durable approval is still required; changing the address cannot change the trusted pin. */
    @Throws(Exception::class)
    public suspend fun connect(fingerprint: String, address: String, port: Int) {
        checkNotNull(client).connect(RpcSelectedHost(PeerFingerprint.parse(fingerprint), RpcEndpoint(address, port)))
    }

    /** Callback is NOT a UI-thread callback. The native UI must marshal it to its own main actor. */
    public fun echo(large: Boolean, onComplete: (RpcPhoneCallResult) -> Unit): RpcPhoneOperation {
        val peer = checkNotNull(client)
        check(scope.coroutineContext[Job]?.isActive == true && callBusy.compareAndSet(false, true))
        val job = scope.launch {
            val started = TimeSource.Monotonic.markNow()
            val expected = if (large) 20 else 1
            var completed = 0
            var failureKind: String? = null
            var evidence: String? = null
            try {
                val payload = if (large) "a".repeat(RpcCapacityContract.MAXIMUM_BODY_BYTES - 2)
                    else RpcCapacityContract.payload
                val procedure = if (large) RpcCapacityContract.largeEcho else RpcCapacityContract.echo
                repeat(if (large) 10 else 1) {
                    val outcomes = supervisorScope {
                        List(if (large) 2 else 1) { async { peer.call(procedure, payload) } }.awaitAll()
                    }
                    for (reply in outcomes) {
                        check(reply is RpcReply.Success && reply.value == payload) { "Synthetic echo mismatch" }
                        completed++
                    }
                }
            } catch (cancelled: CancellationException) {
                onComplete(RpcPhoneCallResult(
                    completed, expected, started.elapsedNow().inWholeMilliseconds, "Cancelled", "MayHaveExecuted",
                ))
                throw cancelled
            } catch (failure: RpcFailure) {
                failureKind = failure.kind.name
                evidence = failure.executionEvidence.name
            } catch (_: Exception) {
                failureKind = "LocalOrProtocolFailure"
                evidence = "MayHaveExecuted"
            }
            onComplete(RpcPhoneCallResult(
                completed, expected, started.elapsedNow().inWholeMilliseconds, failureKind, evidence,
            ))
        }
        job.invokeOnCompletion { callBusy.value = false }
        return RpcPhoneOperation(job)
    }

    /** Foreground loss cancels owned calls and closes the runtime; it does not undo remote side effects. */
    @Throws(Exception::class)
    public suspend fun close() {
        withContext(NonCancellable) {
            try {
                host?.close()
                client?.close()
            } finally {
                scope.coroutineContext[Job]?.cancelAndJoin()
            }
        }
    }

    public companion object {
        /** Import is an explicit local administrator action for exactly 128 synthetic test clients. */
        public fun parseCapacityPins(text: String): Set<PeerFingerprint> {
            require(text.length <= 8192)
            val lines = text.lineSequence().filter(String::isNotEmpty).toList()
            require(lines.size == 128 && lines.toSet().size == 128)
            return lines.map(PeerFingerprint::parse).toSet().also { require(it.size == 128) }
        }

        @Throws(Exception::class)
        public suspend fun createHost(
            platform: RpcPlatform, settings: RpcPhoneSettings, trustStore: RpcTrustStore,
            explicitlyApprovedCapacityPins: String,
        ): RpcPhoneLab {
            val policy = settings.policy(host = true)
            if (explicitlyApprovedCapacityPins.isNotEmpty()) {
                trustStore.replace(RpcCapacityContract.appId, RpcTrustPurpose.HostClients,
                    parseCapacityPins(explicitlyApprovedCapacityPins))
            }
            val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
            var host: RpcHost? = null
            try {
                host = RpcHost.create(platform, scope) {
                    appId = RpcCapacityContract.appId
                    lan = policy
                    this.trustStore = trustStore
                    limits = RpcLimits.host128()
                    advertise = false
                    // Engine admission still requires durable trust; enrollment-only peers cannot invoke these.
                    register(RpcCapacityContract.echo, authorize = { it.fingerprint != null }) { _, value ->
                        if (value == RpcCapacityContract.payload) RpcReply.Success(value)
                        else RpcReply.ApplicationError("unexpected synthetic body")
                    }
                    register(RpcCapacityContract.largeEcho, authorize = { it.fingerprint != null }) { _, value ->
                        RpcReply.Success(value)
                    }
                }
                host.start()
                return RpcPhoneLab(scope, host, null)
            } catch (failure: Exception) {
                withContext(NonCancellable) {
                    try { host?.close() } catch (cleanup: Exception) { failure.addSuppressed(cleanup) }
                    scope.coroutineContext[Job]?.cancelAndJoin()
                }
                throw failure
            }
        }

        @Throws(Exception::class)
        public suspend fun createClient(
            platform: RpcPlatform, settings: RpcPhoneSettings, trustStore: RpcTrustStore,
        ): RpcPhoneLab {
            val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
            try {
                val client = RpcClient.create(platform, scope) {
                    appId = RpcCapacityContract.appId
                    lan = settings.policy(host = false)
                    this.trustStore = trustStore
                }
                return RpcPhoneLab(scope, null, client)
            } catch (failure: Exception) {
                withContext(NonCancellable) { scope.coroutineContext[Job]?.cancelAndJoin() }
                throw failure
            }
        }
    }
}
