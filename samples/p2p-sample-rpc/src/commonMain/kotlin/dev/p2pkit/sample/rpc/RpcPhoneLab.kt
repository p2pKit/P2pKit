package dev.p2pkit.sample.rpc

import dev.p2pkit.core.FeatureState
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
public class RpcPhoneSettings private constructor(
    public val subnets: String,
    public val interfaceName: String,
    public val localAddress: String,
    public val port: Int,
    automatic: Boolean,
) {
    @Throws(Exception::class)
    public constructor(subnets: String, interfaceName: String, localAddress: String, port: Int) :
        this(subnets, interfaceName, localAddress, port, false)

    init { require((if (automatic) port == 0 else port in 1024..65535) && subnets.length in 1..512) }

    public companion object {
        /** Platform adapters supply the one eligible observed private LAN, never a guessed default interface. */
        @Throws(Exception::class)
        public fun automatic(subnet: String, interfaceName: String, localAddress: String): RpcPhoneSettings =
            RpcPhoneSettings(subnet, interfaceName, localAddress, 0, true)
    }
    internal fun policy(host: Boolean): OrganizationLan = OrganizationLan(
        subnets.split(',').map(String::trim), interfaceName, localAddress, if (host) port else 0,
    )
}

/** Local administrator UI only. Never include these pins/requests in exported diagnostics. */
public class RpcPhonePairing(
    public val requestId: String, public val fingerprint: String, public val origin: String,
) {
    public constructor(requestId: String, fingerprint: String) : this(requestId, fingerprint, "Invitation")
}

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

/** Completion is delivered even when cancellation wins before the coroutine's first dispatch. */
private class PhoneCompletion<T>(val value: T)

private class PhoneMobileRun(val config: RpcMobileCapacityConfig, val trust: RpcTrustStore) {
    val started = TimeSource.Monotonic.markNow()
    val sequence = MutableStateFlow(0L)
    val closed = MutableStateFlow(false)

    fun next(): Long {
        while (true) {
            val value = sequence.value
            check(value < 3_000) // Fixed outer run bound, not an unbounded diagnostic stream.
            if (sequence.compareAndSet(value, value + 1)) return value
        }
    }
}

/** Never erase unrelated or concurrently introduced approvals when retiring an explicit test import. */
internal suspend fun retireMobileCapacityPins(trust: RpcTrustStore, pins: Set<PeerFingerprint>) {
    val current = trust.load(RpcCapacityContract.appId, RpcTrustPurpose.HostClients)
    check(current.all { it in pins }) { "Unrelated approvals retained; no cleanup claim" }
    trust.replace(RpcCapacityContract.appId, RpcTrustPurpose.HostClients, emptySet())
    check(trust.load(RpcCapacityContract.appId, RpcTrustPurpose.HostClients).isEmpty())
}

/**
 * One facade's terminal ownership ledger, allocated before any operation is admitted. A native reporting
 * Error remains reachable here, never as public exception text or an unsafe permission to retry. This does
 * not promise recovery from real VM resource exhaustion; it preserves reportable late failures.
 */
internal class PhoneOperationFailureState {
    private val fatal = MutableStateFlow<Throwable?>(null)
    private val retirement = MutableStateFlow<Throwable?>(null)
    val originalFailure: Throwable? get() = fatal.value
    val retirementFailure: Throwable? get() = retirement.value
    val terminal = PhoneOperationTerminalFailure(this)

    fun requireHealthy() { if (originalFailure != null) throw terminal }
    fun retain(failure: Throwable) { fatal.compareAndSet(null, failure) }

    /** Direct and callback APIs share admission and the same sanitized cross-language failure boundary. */
    suspend fun <T> effect(action: suspend () -> T): T {
        requireHealthy()
        return try { action() }
        catch (cancelled: CancellationException) { throw cancelled }
        catch (failure: Exception) { throw failure }
        catch (failure: Throwable) { retain(failure); throw terminal }
    }

    /** Failure never skips physical cleanup. Keep its separate original outcome without suppression allocation. */
    suspend fun retire(cleanup: suspend () -> Unit) {
        var caught: Throwable? = null
        try { cleanup() } catch (failure: Throwable) { caught = failure }
        if (originalFailure != null) {
            caught?.let { retirement.compareAndSet(null, it) }
            throw terminal
        }
        caught?.let { throw it }
    }
}

/** Sanitized @Throws(Exception) boundary; its private owner retains the original Error, not its cause/message. */
internal class PhoneOperationTerminalFailure(private val owner: PhoneOperationFailureState) :
    Exception("RPC operation ownership failed; cleanup is required") {
    val originalFailure: Throwable? get() = owner.originalFailure
    val retirementFailure: Throwable? get() = owner.retirementFailure
}

/**
 * Owns only the scope and resource actually returned to this factory. A null resource does not prove that
 * the underlying library factory retired every unpublished owner. Allocate the fatal carrier before effects.
 */
internal class PhoneFactoryOwner<R : Any>(private val closeResource: suspend (R) -> Unit) {
    val failure = PhoneFactoryOwnershipError(this)
    val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    var resource: R? = null
    var initialFailure: Throwable? = null
        private set
    var resourceCloseFailure: Throwable? = null
        private set
    var scopeCloseFailure: Throwable? = null
        private set

    suspend fun failed(original: Throwable): Nothing {
        initialFailure = original
        withContext(NonCancellable) {
            try { resource?.let { closeResource(it) } } catch (cleanup: Throwable) {
                resourceCloseFailure = cleanup
            } finally {
                // A reporting Error from resource.close must not skip the independent owned job-tree drain.
                try { checkNotNull(scope.coroutineContext[Job]).cancelAndJoin() } catch (cleanup: Throwable) {
                    scopeCloseFailure = cleanup
                }
            }
        }
        // Keep the library's established ordinary creation-refusal contract, including refusals before
        // a resource is returned. This wrapper does not newly prove custody of unpublished library owners.
        if (original is Exception && original !is PhoneOperationTerminalFailure &&
            resourceCloseFailure == null && scopeCloseFailure == null
        ) throw original
        // Preserve existing fatal Android/iOS behavior: their ordinary Exception paths assume factory
        // cleanup succeeded. Never translate retained ownership into that retryable success assumption.
        throw failure
    }
}

/** No raw cause/message or new @Throws contract; retains actual owners even after a failed factory returns. */
internal class PhoneFactoryOwnershipError(private val owner: PhoneFactoryOwner<*>) :
    Error("RPC factory ownership is unproven; retained owner review is required") {
    val initialFailure: Throwable? get() = owner.initialFailure
    val resourceCloseFailure: Throwable? get() = owner.resourceCloseFailure
    val scopeCloseFailure: Throwable? get() = owner.scopeCloseFailure
    val retainedResource: Any? get() = owner.resource
    val retainedScope: CoroutineScope get() = owner.scope
}

internal fun <T> startPhoneOperation(
    scope: CoroutineScope,
    busy: MutableStateFlow<Boolean>,
    cancelled: () -> T,
    failed: (Exception) -> T,
    onComplete: (T) -> Unit,
    failures: PhoneOperationFailureState = PhoneOperationFailureState(),
    action: suspend () -> T,
): RpcPhoneOperation {
    failures.requireHealthy()
    check(scope.coroutineContext[Job]?.isActive == true && busy.compareAndSet(false, true))
    val completion = MutableStateFlow<PhoneCompletion<T>?>(null)
    val job = scope.launch {
        val result = try { failures.effect(action) }
        catch (cancellation: CancellationException) { throw cancellation }
        catch (failure: Exception) { failed(failure) }
        completion.value = PhoneCompletion(result)
    }
    job.invokeOnCompletion { cause ->
        busy.value = false
        // Terminal notification follows admission release; nullable success is not "no outcome".
        if (cause is CancellationException) onComplete(cancelled())
        else completion.value?.let { onComplete(it.value) }
    }
    return RpcPhoneOperation(job)
}

/**
 * Foreground-owned facade. Qualification factories register only synthetic echo; application factories
 * additionally register the same typed application examples on all platforms.
 * OS identity storage comes from RpcPlatform; the app supplies a local protected trust store.
 * Use a fresh controller after an explicit role change; close and await it before replacement.
 */
public class RpcPhoneLab private constructor(
    private val scope: CoroutineScope,
    private val host: RpcHost?,
    private val client: RpcClient?,
    private val application: RpcApplicationSession? = null,
) {
    private val callBusy = MutableStateFlow(false)
    private val operationFailures = PhoneOperationFailureState()
    private val controlBusy = MutableStateFlow(false)
    private var mobileRun: PhoneMobileRun? = null
    private var discovery: RpcDiscoveryCoordinator? = null
    public val nearbyMode: Boolean get() = discovery != null || nearbyHost
    private var nearbyHost = false
    public val discoveryConnection: RpcDiscoveryConnectionStatus? get() = discovery?.status?.value
    public val networkActivity: String get() = when (host?.advertisingState?.value ?: client?.discoveryState?.value) {
        FeatureState.Idle, null -> "Idle"
        FeatureState.Starting -> "Starting"
        FeatureState.Active -> "Active"
        FeatureState.Stopping -> "Stopping"
        is FeatureState.PermissionRequired -> "Local network permission required"
        is FeatureState.Failed -> "Network discovery/advertising failed"
        is FeatureState.Unsupported -> "Network discovery/advertising unsupported"
    }

    public fun nearbyHosts(): List<RpcNearbyHost> = client?.let { RpcClientDiscoveryAdapter(it).nearby() }.orEmpty()

    /** Hosts report authenticated connections; clients report unverified discovery presence, not proof of identity. */
    public fun trustedDevices(): List<RpcKnownDevice> {
        val trust = host?.trust ?: checkNotNull(client).trust
        val discovered = nearbyHosts()
        return trust.fingerprints().map { pin ->
            val found = discovered.singleOrNull { it.fingerprint == pin.value }
            val connected = host?.connections?.value?.any {
                it.peer.fingerprint == pin && it.state == dev.p2pkit.core.ConnectionState.Connected
            } == true || (discoveryConnection?.selectedFingerprint == pin.value &&
                client?.state?.value == dev.p2pkit.rpc.RpcConnectionState.Ready)
            RpcKnownDevice(pin.value, found?.name ?: "Known device", if (connected) "Connected"
                else if (found != null) "Discovered (unverified presence)" else "Offline")
        }
    }

    @Throws(Exception::class)
    public fun beginSelectNearby(
        fingerprint: String, firstUseConfirmed: Boolean, onComplete: (String?) -> Unit,
    ): RpcPhoneOperation = controlOperation(onComplete) {
        checkNotNull(discovery).select(fingerprint, firstUseConfirmed)
    }

    @Throws(Exception::class)
    public suspend fun reject(requestId: String) = operationFailures.effect {
        check(mobileRun == null)
        checkNotNull(host).pairing.reject(requestId)
    }

    public val applicationAvailable: Boolean get() = application != null
    public val fingerprint: String get() = (host?.fingerprint ?: checkNotNull(client).fingerprint).value
    public val state: String get() = host?.state?.value?.name ?: checkNotNull(client).state.value.name
    public val diagnostics: RpcDiagnostics get() {
        host?.let { application?.history?.observeHost(it.requests.value) }
        return host?.diagnostics?.value ?: checkNotNull(client).diagnostics.value
    }
    public val requestMetrics: List<RpcMetricCard> get() {
        val requests = host?.requests?.value
        return rpcRequestMetrics(requests?.totals ?: checkNotNull(client).requestTotals.value,
            diagnostics, requests?.droppedCaptures ?: 0, client = host == null)
    }
    public val connectedClients: Int get() = host?.connections?.value?.filter {
        it.state == dev.p2pkit.core.ConnectionState.Connected &&
            it.admission == dev.p2pkit.core.PeerAdmission.Trusted
    }?.mapNotNull { it.peer.fingerprint }?.toSet()?.size ?: 0

    @Throws(Exception::class)
    public suspend fun invitation(): String = operationFailures.effect {
        check(mobileRun == null) { "Manual pairing is unavailable during a capacity session" }
        val invitation = checkNotNull(host).pairing.createInvitation()
        return@effect try { invitation.qr } finally { invitation.clear() }
    }

    @Throws(Exception::class)
    public fun pending(): List<RpcPhonePairing> {
        check(mobileRun == null) { "Manual pairing is unavailable during a capacity session" }
        return checkNotNull(host).pairing.pending.value.map {
            RpcPhonePairing(it.id, checkNotNull(it.peer.fingerprint).value, it.origin.name)
        }
    }

    @Throws(Exception::class)
    public suspend fun approve(requestId: String) = operationFailures.effect {
        check(mobileRun == null) { "Manual pairing is unavailable during a capacity session" }
        checkNotNull(host).pairing.approve(requestId)
    }

    @Throws(Exception::class)
    public suspend fun revoke(fingerprint: String) = operationFailures.effect {
        check(mobileRun == null) { "Stop the capacity session before changing its approvals" }
        val nearby = discovery
        if (nearby != null) nearby.forget(fingerprint)
        else (host?.trust ?: checkNotNull(client).trust).revoke(PeerFingerprint.parse(fingerprint))
    }

    /** Only the private, owner-approved USB coordinator consumes this identity-bearing record. */
    @Throws(Exception::class)
    public suspend fun mobileReadyRecord(observedArtifactSha256: String): String = operationFailures.effect {
        val run = checkNotNull(mobileRun)
        check(!run.closed.value)
        check(observedArtifactSha256 == run.config.hostArtifactSha256)
        val endpoint = checkNotNull(host).endpoint()
        check(endpoint.address == run.config.settings.localAddress && endpoint.port == run.config.settings.port)
        return@effect encodeMobileRecord(run.config.binding() + mapOf(
            "fingerprint" to fingerprint, "address" to endpoint.address, "port" to endpoint.port.toString(),
            "compiledSourceMatched" to "true",
            "artifactKind" to if (run.config.hostPlatform == "Android") "android-installed-base-apk"
                else "ios-installed-executable",
        ))
    }

    /** OS counters must be collected on this foreground PHONE, never substituted with generator measurements. */
    @Throws(Exception::class)
    public fun mobileTelemetry(resources: RpcPhoneProcessStats): String {
        val run = checkNotNull(mobileRun)
        check(!run.closed.value)
        return mobileTelemetryRecord(run.config, run.next(), run.started.elapsedNow().inWholeMilliseconds,
            connectedClients, diagnostics, resources)
    }

    @Throws(Exception::class)
    public fun mobileStopMatches(record: String): Boolean = mobileStopRequested(checkNotNull(mobileRun).config, record)

    /** Successful close AND exact synthetic pin retirement are necessary, not sufficient, qualification evidence. */
    @Throws(Exception::class)
    public fun mobileClosedRecord(controlHealthy: Boolean): String {
        operationFailures.requireHealthy()
        val run = checkNotNull(mobileRun)
        check(run.closed.value)
        return mobileClosedRecord(run.config, controlHealthy)
    }

    /** The invitation must be obtained from the explicitly selected host's trusted LOCAL UI. */
    @Throws(Exception::class)
    public suspend fun pairAndConnect(qr: String) = operationFailures.effect {
        check(discovery == null) { "Nearby mode owns connection selection" }
        val invitation = RpcInvitation.parse(qr)
        val selected = try { checkNotNull(client).pair(invitation) } finally { invitation.clear() }
        checkNotNull(client).connect(selected)
    }

    /** Existing durable approval is still required; changing the address cannot change the trusted pin. */
    @Throws(Exception::class)
    public suspend fun connect(fingerprint: String, address: String, port: Int) = operationFailures.effect {
        check(discovery == null) { "Nearby mode owns connection selection" }
        checkNotNull(client).connect(RpcSelectedHost(PeerFingerprint.parse(fingerprint), RpcEndpoint(address, port)))
    }

    /** Swift/native callers retain this Kotlin handle; cancelling a Swift Task is not enough. */
    @Throws(Exception::class)
    public fun beginPairAndConnect(qr: String, onComplete: (String?) -> Unit): RpcPhoneOperation =
        controlOperation(onComplete) { pairAndConnect(qr) }

    @Throws(Exception::class)
    public fun beginConnect(
        fingerprint: String, address: String, port: Int, onComplete: (String?) -> Unit,
    ): RpcPhoneOperation = controlOperation(onComplete) { connect(fingerprint, address, port) }

    private fun controlOperation(onComplete: (String?) -> Unit, action: suspend () -> Unit): RpcPhoneOperation =
        startPhoneOperation(scope, controlBusy, { "Cancelled" }, { failure ->
            if (failure is RpcFailure) "${failure.kind}/${failure.phase}/${failure.executionEvidence}"
            else "LocalOrProtocolFailure"
        }, onComplete, operationFailures) { action(); null }

    /** Fixed shared example inputs; typed callers may also use RpcApplicationSession directly. */
    @Throws(Exception::class)
    public fun beginExample(example: RpcApplicationExample, onComplete: (String?) -> Unit): RpcPhoneOperation {
        operationFailures.requireHealthy()
        val app = checkNotNull(application)
        val peer = checkNotNull(client)
        check(mobileRun == null)
        return startPhoneOperation(scope, callBusy, { "Cancelled" }, { failure ->
            if (failure is RpcFailure) "${failure.kind}/${failure.phase}/${failure.executionEvidence}"
            else "LocalOrProtocolFailure"
        }, onComplete, operationFailures) {
            when (example) {
                RpcApplicationExample.GetUser -> app.getUser(peer, 123)
                RpcApplicationExample.ListItems -> app.listItems(peer, 0, 20)
                RpcApplicationExample.SendMessage -> app.sendMessage(peer, 123, "Hello from the RPC sample")
                RpcApplicationExample.BusinessError -> app.getUser(peer, 999)
                RpcApplicationExample.ValidationError -> app.getUser(peer, -1)
            }
            null
        }
    }

    /** Editable typed requests use the same bounded call slot, codecs, procedure policy and history as presets. */
    @Throws(Exception::class)
    public fun beginRequest(input: RpcApplicationInput, onComplete: (String?) -> Unit): RpcPhoneOperation {
        operationFailures.requireHealthy()
        val app = checkNotNull(application)
        val peer = checkNotNull(client)
        check(mobileRun == null)
        return startPhoneOperation(scope, callBusy, { "Cancelled" }, { failure ->
            if (failure is RpcFailure) "${failure.kind}/${failure.phase}/${failure.executionEvidence}"
            else "LocalOrProtocolFailure"
        }, onComplete, operationFailures) {
            when (input.procedure) {
                RpcApplicationProcedure.GetUser -> app.getUser(peer, input.userId)
                RpcApplicationProcedure.ListItems -> app.listItems(peer, input.offset, input.limit)
                RpcApplicationProcedure.SendMessage -> app.sendMessage(peer, input.userId, input.message)
            }
            null
        }
    }

    /** Callback is NOT a UI-thread callback. The native UI must marshal it to its own main actor. */
    @Throws(Exception::class)
    public fun echo(large: Boolean, onComplete: (RpcPhoneCallResult) -> Unit): RpcPhoneOperation {
        operationFailures.requireHealthy()
        val peer = checkNotNull(client)
        val started = TimeSource.Monotonic.markNow()
        val expected = if (large) 20 else 1
        var completed = 0
        var entered = false
        fun result(kind: String?, evidence: String?) = RpcPhoneCallResult(
            completed, expected, started.elapsedNow().inWholeMilliseconds, kind, evidence,
        )
        return startPhoneOperation(scope, callBusy, {
            result("Cancelled", if (entered) "MayHaveExecuted" else "NotSent")
        }, { failure ->
            if (failure is RpcFailure) result(failure.kind.name, failure.executionEvidence.name)
            else result("LocalOrProtocolFailure", if (entered) "MayHaveExecuted" else "NotSent")
        }, onComplete, operationFailures) {
            entered = true
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
            result(null, null)
        }
    }

    /** Foreground loss cancels owned calls and closes the runtime; it does not undo remote side effects. */
    @Throws(Exception::class)
    public suspend fun close() {
        withContext(NonCancellable) {
            operationFailures.retire {
                host?.let { application?.history?.observeHost(it.requests.value) }
                try {
                    try { discovery?.close() } finally {
                        host?.close()
                        client?.close()
                    }
                } finally {
                    scope.coroutineContext[Job]?.cancelAndJoin()
                    host?.let { application?.history?.retireHost(it.requests.value.hostIncarnation) }
                }
                mobileRun?.let { run ->
                    if (!run.closed.value) {
                        retireMobileCapacityPins(run.trust, run.config.pins)
                        run.closed.value = true
                    }
                }
            }
        }
    }

    public companion object {
        public val compiledSource: String get() = RpcPhoneBuildStamp.SOURCE_COMMIT

        /**
         * The platform UI calls this ONLY after explicit approval of the USB run and its exact network/pins.
         * An empty host-approval namespace is required; no older approval set is overwritten or restored.
         */
        @Throws(Exception::class)
        public suspend fun createMobileCapacityHost(
            platform: RpcPlatform, trustStore: RpcTrustStore, config: RpcMobileCapacityConfig, actualPlatform: String,
        ): RpcPhoneLab {
            require(RpcPhoneBuildStamp.SOURCE_CLEAN && config.hostSourceSha == compiledSource)
            require(actualPlatform in setOf("Android", "Ios") && config.hostPlatform == actualPlatform)
            require(trustStore.load(RpcCapacityContract.appId, RpcTrustPurpose.HostClients).isEmpty())
            try {
                val lab = createHostInternal(platform, config.settings, trustStore, config.clientPins, null,
                    capacityExercises = config.schema == "2")
                lab.mobileRun = PhoneMobileRun(config, trustStore)
                // Return the owned runtime before performing fallible USB publication.
                // mobileReadyRecord subsequently verifies its actual bound endpoint.
                return lab
            } catch (failure: Exception) {
                withContext(NonCancellable) {
                    try { retireMobileCapacityPins(trustStore, config.pins) }
                    catch (cleanup: Exception) { failure.addSuppressed(cleanup) }
                }
                throw failure
            }
        }

        /** Import is an explicit local administrator action for exactly 128 or 256 synthetic test clients. */
        @Throws(Exception::class)
        public fun parseCapacityPins(text: String): Set<PeerFingerprint> {
            require(text.length <= 16384)
            val lines = text.lineSequence().filter(String::isNotEmpty).toList()
            require(lines.size in setOf(128, 256) && lines.toSet().size == lines.size)
            return lines.map(PeerFingerprint::parse).toSet().also { require(it.size == lines.size) }
        }

        @Throws(Exception::class)
        public suspend fun createHost(
            platform: RpcPlatform, settings: RpcPhoneSettings, trustStore: RpcTrustStore,
            explicitlyApprovedCapacityPins: String,
        ): RpcPhoneLab = createHostInternal(platform, settings, trustStore, explicitlyApprovedCapacityPins, null)

        /** Interactive application mode is separate from the unchanged explicit capacity host. */
        @Throws(Exception::class)
        public suspend fun createApplicationHost(
            platform: RpcPlatform, settings: RpcPhoneSettings, trustStore: RpcTrustStore,
            application: RpcApplicationSession,
        ): RpcPhoneLab = createHostInternal(platform, settings, trustStore, "", application)

        /** Application workflow opt-in; legacy invitation/capacity factories retain their original behavior. */
        @Throws(Exception::class)
        public suspend fun createNearbyApplicationHost(
            platform: RpcPlatform, settings: RpcPhoneSettings, trustStore: RpcTrustStore,
            application: RpcApplicationSession,
        ): RpcPhoneLab = createHostInternal(platform, settings, trustStore, "", application, nearby = true)

        private suspend fun createHostInternal(
            platform: RpcPlatform, settings: RpcPhoneSettings, trustStore: RpcTrustStore,
            explicitlyApprovedCapacityPins: String, application: RpcApplicationSession?, nearby: Boolean = false,
            capacityExercises: Boolean = false,
        ): RpcPhoneLab {
            val policy = settings.policy(host = true)
            val capacityPins = explicitlyApprovedCapacityPins.takeIf(String::isNotEmpty)?.let(::parseCapacityPins)
            if (capacityPins != null) {
                trustStore.replace(RpcCapacityContract.appId, RpcTrustPurpose.HostClients, capacityPins)
            }
            val owner = PhoneFactoryOwner<RpcHost>(RpcHost::close)
            val scope = owner.scope
            try {
                val host = RpcHost.create(platform, scope) {
                    appId = RpcCapacityContract.appId
                    lan = policy
                    this.trustStore = trustStore
                    limits = if (capacityPins?.size == 256) RpcLimits.host256() else RpcLimits.host128()
                    advertise = nearby
                    allowNearbyPairing = nearby
                    application?.register(this, authorize = { it.fingerprint != null })
                    // Engine admission still requires durable trust; enrollment-only peers cannot invoke these.
                    register(RpcCapacityContract.echo, authorize = { it.fingerprint != null }) { _, value ->
                        if (value == RpcCapacityContract.payload) RpcReply.Success(value)
                        else RpcReply.ApplicationError("unexpected synthetic body")
                    }
                    register(RpcCapacityContract.largeEcho, authorize = { it.fingerprint != null }) { _, value ->
                        RpcReply.Success(value)
                    }
                    if (capacityExercises) registerCapacityExercises(checkNotNull(capacityPins))
                }.also { owner.resource = it }
                host.start()
                return RpcPhoneLab(scope, host, null, application).also { it.nearbyHost = nearby }
            } catch (failure: Exception) {
                owner.failed(failure)
            } catch (failure: Error) {
                owner.failed(failure)
            }
        }

        @Throws(Exception::class)
        public suspend fun createClient(
            platform: RpcPlatform, settings: RpcPhoneSettings, trustStore: RpcTrustStore,
        ): RpcPhoneLab = createClientInternal(platform, settings, trustStore, null)

        @Throws(Exception::class)
        public suspend fun createApplicationClient(
            platform: RpcPlatform, settings: RpcPhoneSettings, trustStore: RpcTrustStore,
            application: RpcApplicationSession,
        ): RpcPhoneLab = createClientInternal(platform, settings, trustStore, application)

        @Throws(Exception::class)
        public suspend fun createNearbyApplicationClient(
            platform: RpcPlatform, settings: RpcPhoneSettings, trustStore: RpcTrustStore,
            application: RpcApplicationSession,
        ): RpcPhoneLab = createClientInternal(platform, settings, trustStore, application, nearby = true)

        private suspend fun createClientInternal(
            platform: RpcPlatform, settings: RpcPhoneSettings, trustStore: RpcTrustStore,
            application: RpcApplicationSession?, nearby: Boolean = false,
        ): RpcPhoneLab {
            val owner = PhoneFactoryOwner<RpcClient>(RpcClient::close)
            val scope = owner.scope
            try {
                val client = RpcClient.create(platform, scope) {
                    appId = RpcCapacityContract.appId
                    lan = settings.policy(host = false)
                    transportReconnect = !nearby
                    this.trustStore = trustStore
                }.also { owner.resource = it }
                val lab = RpcPhoneLab(scope, null, client, application)
                if (nearby) {
                    lab.discovery = RpcDiscoveryCoordinator(scope, RpcClientDiscoveryAdapter(client), trustStore,
                        lab.operationFailures)
                    checkNotNull(lab.discovery).start()
                }
                return lab
            } catch (failure: Exception) {
                owner.failed(failure)
            } catch (failure: Error) {
                owner.failed(failure)
            }
        }
    }
}
