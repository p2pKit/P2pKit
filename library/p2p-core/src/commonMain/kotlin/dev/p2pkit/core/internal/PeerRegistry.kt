package dev.p2pkit.core.internal

import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.provisioning.ManualPeerRegistrar
import dev.p2pkit.core.protocol.HelloPayload
import dev.p2pkit.core.protocol.validateWireText
import dev.p2pkit.core.transport.DiscoveryTransport
import dev.p2pkit.core.transport.DiscoveryLifetime
import dev.p2pkit.core.transport.discoveryLifetime
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.PeerAuthenticationHint
import dev.p2pkit.core.transport.PeerOrigin
import dev.p2pkit.core.transport.TransportSecurityProfile
import dev.p2pkit.core.transport.TransportHint
import kotlin.uuid.ExperimentalUuidApi
import kotlin.uuid.Uuid
import kotlin.jvm.JvmInline
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.ExperimentalForInheritanceCoroutinesApi
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.FlowCollector
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.updateAndGet
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * Aggregates [PeerEvent]s from every registered [DiscoveryTransport] into a
 * single, deduplicated peers list.
 *
 * Public state surface is [peers] (the de-noised list) plus [lastSeen] (a
 * spot lookup that does not cause [peers] to re-emit on heartbeats).
 *
 * @param staleTimeoutMillis A peer not seen for this many milliseconds is
 *   evicted. Default 15 s.
 * @param evictionPollMillis How often the eviction loop wakes up. Smaller =
 *   more responsive, larger = cheaper. Default 1 s.
 * @param clock Source of epoch milliseconds for the public [lastSeen] value.
 * @param monotonicClock Monotonic elapsed-time source used for staleness. It
 *   must not jump when the wall clock is corrected. P2pKitImpl wires both
 *   platform clocks; tests inject fakes.
 * @param maxDiscoveredPeers Maximum number of distinct peer identifiers that
 *   discovery sources may retain at once. Manual registrations do not consume
 *   this budget, and updates for an already retained identifier remain valid
 *   while the budget is full.
 */
@OptIn(ExperimentalP2pApi::class)
internal class PeerRegistry(
    private val discoveryTransports: List<DiscoveryTransport>,
    private val scope: CoroutineScope,
    private val clock: () -> Long,
    private val monotonicClock: () -> Long = clock,
    private val staleTimeoutMillis: Long = DEFAULT_STALE_TIMEOUT_MS,
    private val evictionPollMillis: Long = DEFAULT_EVICTION_POLL_MS,
    private val logger: P2pLogger = P2pLogger.NoOp,
    private val securityProfile: TransportSecurityProfile = TransportSecurityProfile.LegacyPlaintextV1,
    private val peerIdFromFingerprint: ((PeerFingerprint) -> PeerId)? = null,
    private val maxDiscoveredPeers: Int = MAX_DISCOVERED_PEERS,
    private val beforeManualPeerCompareAndSetForTest: (() -> Unit)? = null,
    private val beforePeerPublicationForTest: ((Long) -> Unit)? = null
) : ManualPeerRegistrar {

    init {
        require(maxDiscoveredPeers > 0) { "maxDiscoveredPeers must be positive" }
    }

    /**
     * The terminal seal and tracked entries share one compare-and-set record.
     * A callback that captured the pre-close map therefore cannot commit after
     * [close], even when the old and cleared maps are both empty/equal.
     */
    private val registryState: MutableStateFlow<PeerRegistryState> =
        MutableStateFlow(PeerRegistryState())
    private val peerPublication: MutableStateFlow<PeerPublication> =
        MutableStateFlow(PeerPublication(0L, immutableListSnapshot(emptyList())))
    private val loggedDiscoveryRejections: MutableStateFlow<Set<DiscoveryRejection>> =
        MutableStateFlow(emptySet())

    /**
     * Public-facing peer list. Updated synchronously after every accepted
     * [PeerEvent]; emits a new value only when the visible peer set actually
     * changes (heartbeat-only updates to `lastSeen` do not churn this flow).
     */
    val peers: StateFlow<List<Peer>> = PeerListStateFlow(peerPublication)

    fun lastSeen(peerId: PeerId): Long? =
        registryState.value.tracked[peerId]?.lastSeenAtMillis

    /**
     * Returns the [InternalPeer] (including transport hints) for [peerId] if
     * still tracked. Used by SessionManager to resolve a public [Peer] back to
     * its discovery-time reach information.
     */
    fun internalPeer(peerId: PeerId): InternalPeer? =
        registryState.value.tracked[peerId]?.internalPeer

    fun start() {
        discoveryTransports.forEachIndexed { sourceIndex, transport ->
            scope.launch {
                collectEventsWithRecovery(DiscoverySource(sourceIndex), transport)
            }
        }
        scope.launch { evictLoop() }
    }

    /**
     * A third-party discovery flow is an SPI boundary, not a lifetime fuse.
     * An ordinary failure or unexpected completion invalidates that source's
     * liveness ownership before bounded-backoff recollection. A state-backed
     * transport replays its complete current set into the fresh collector;
     * clearing first also prevents a peer removed while the stream was down
     * from remaining forever under [DiscoveryLifetime.TransportManaged].
     * Structural cancellation still terminates the collector.
     */
    private suspend fun collectEventsWithRecovery(
        source: DiscoverySource,
        transport: DiscoveryTransport
    ) {
        var consecutiveEmptyFailures = 0
        while (currentCoroutineContext().isActive) {
            var observedEvent = false
            var collectionFailure: Throwable? = null
            try {
                transport.events.collect { event ->
                    if (processEvent(source, event)) {
                        observedEvent = true
                        consecutiveEmptyFailures = 0
                    }
                }
                currentCoroutineContext().ensureActive()
            } catch (cancelled: CancellationException) {
                // A third-party flow can throw a CancellationException while
                // this collector's Job remains active. That is an SPI failure,
                // not structural cancellation. Genuine scope cancellation is
                // rethrown by ensureActive().
                currentCoroutineContext().ensureActive()
                collectionFailure = cancelled
            } catch (failure: Throwable) {
                collectionFailure = failure
            }
            removeDiscoverySource(source)
            if (!observedEvent) consecutiveEmptyFailures += 1
            val exponent = minOf(
                (consecutiveEmptyFailures - 1).coerceAtLeast(0),
                MAX_EVENT_RECOLLECT_EXPONENT
            )
            val retryDelayMillis = minOf(
                EVENT_RECOLLECT_INITIAL_DELAY_MS shl exponent,
                EVENT_RECOLLECT_MAX_DELAY_MS
            )
            logger.warn(
                "Discovery event stream ${transport.type} " +
                    if (collectionFailure == null) {
                        "completed unexpectedly; retrying in ${retryDelayMillis}ms"
                    } else {
                        "failed; retrying in ${retryDelayMillis}ms"
                    },
                collectionFailure
            )
            delay(retryDelayMillis)
        }
    }

    internal fun processEvent(event: PeerEvent) {
        processEvent(DIRECT_SOURCE, event)
    }

    /** Return true only when a valid event reached the registry boundary. */
    private fun processEvent(source: DiscoverySource, event: PeerEvent): Boolean {
        if (registryState.value.closed) return false
        val admitted = admitDiscoveryEvent(event) ?: run {
            warnDiscoveryRejectionOnce(DiscoveryRejection.InvalidEvent)
            return false
        }
        val observation = if (admitted is AdmittedDiscoveryEvent.Upsert) {
            DiscoveryObservation(clock(), monotonicClock())
        } else {
            null
        }
        while (true) {
            val current = registryState.value
            if (current.closed) return false
            val next = when (admitted) {
                is AdmittedDiscoveryEvent.Upsert -> {
                    val previous = current.tracked[admitted.peer.publicPeer.id]
                    val addsDistinctPeer = previous?.discoveredBy.isNullOrEmpty()
                    if (addsDistinctPeer && current.discoveredPeerCount >= maxDiscoveredPeers) {
                        // Verify the capacity decision against the exact state
                        // snapshot. The generation prevents an ABA-equivalent
                        // map from making this check accidentally succeed.
                        if (registryState.compareAndSet(current, current)) {
                            warnDiscoveryRejectionOnce(DiscoveryRejection.CapacityExhausted)
                            return false
                        }
                        continue
                    }
                    current.withTracked(
                        tracked = current.tracked.upsertDiscoveredPeer(
                            source = source,
                            discovered = admitted.peer,
                            lastSeenAtMillis = checkNotNull(observation).epochMillis,
                            observedAtMonotonicMillis = observation.monotonicMillis
                        ),
                        discoveredPeerCount = current.discoveredPeerCount +
                            if (addsDistinctPeer) 1 else 0
                    )
                }
                is AdmittedDiscoveryEvent.Lost -> {
                    val previous = current.tracked[admitted.peerId]
                    val removesDistinctPeer = previous?.discoveredBy?.let { discoveredBy ->
                        source in discoveredBy && discoveredBy.size == 1
                    } == true
                    current.withTracked(
                        tracked = current.tracked.removeDiscoveryContribution(source, admitted.peerId),
                        discoveredPeerCount = current.discoveredPeerCount -
                            if (removesDistinctPeer) 1 else 0
                    )
                }
            }
            if (next === current) return true
            if (registryState.compareAndSet(current, next)) {
                publishPeers(next)
                return true
            }
        }
    }

    /** Publish only if [snapshot] is newer than every state already exposed. */
    private fun publishPeers(snapshot: PeerRegistryState) {
        if (peerPublication.value.generation >= snapshot.generation) return
        val newList = if (snapshot.closed) {
            emptyList()
        } else {
            snapshot.tracked.values.map { it.internalPeer.publicPeer }
        }
        val candidate = PeerPublication(snapshot.generation, immutableListSnapshot(newList))
        beforePeerPublicationForTest?.invoke(snapshot.generation)
        while (true) {
            val published = peerPublication.value
            if (published.generation >= candidate.generation) return
            if (peerPublication.compareAndSet(published, candidate)) return
        }
    }

    /**
     * Validate the public discovery SPI before retaining any caller-controlled
     * data. Every fingerprint arriving here remains a discovery claim even if
     * a custom transport incorrectly labels it as an application pin.
     */
    private fun admitDiscoveryEvent(event: PeerEvent): AdmittedDiscoveryEvent? = try {
        when (event) {
            is PeerEvent.Found -> AdmittedDiscoveryEvent.Upsert(event.peer.validatedDiscoverySnapshot())
            is PeerEvent.Updated -> AdmittedDiscoveryEvent.Upsert(event.peer.validatedDiscoverySnapshot())
            is PeerEvent.Lost -> {
                validateDiscoveryPeerId(event.peerId)
                AdmittedDiscoveryEvent.Lost(event.peerId)
            }
        }
    } catch (_: IllegalArgumentException) {
        null
    }

    private fun InternalPeer.validatedDiscoverySnapshot(): InternalPeer {
        validateDiscoveryPeerId(publicPeer.id)
        validateWireText(
            publicPeer.name,
            "discovery peer name",
            HelloPayload.MAX_FIELD_LEN,
            HelloPayload.MAX_FIELD_UTF8_BYTES,
            requireNonBlank = true
        )
        require(publicPeer.supportedTransports.size <= HelloPayload.MAX_TRANSPORTS) {
            "discovery peer advertised too many transports"
        }
        require(transportHints.size <= MAX_DISCOVERY_HINTS) {
            "discovery peer supplied too many transport hints"
        }
        transportHints.forEach { hint ->
            hint.host?.let(::validateDiscoveryHost)
            hint.port?.let { port ->
                require(port in 1..65_535) { "discovery transport port is out of range" }
            }
            require(hint.metadata.size <= MAX_DISCOVERY_METADATA_ENTRIES) {
                "discovery transport hint supplied too much metadata"
            }
            hint.metadata.forEach { (key, value) ->
                validateWireText(
                    key,
                    "discovery metadata key",
                    MAX_DISCOVERY_METADATA_KEY_CHARS,
                    MAX_DISCOVERY_METADATA_KEY_UTF8_BYTES,
                    requireNonBlank = true
                )
                validateWireText(
                    value,
                    "discovery metadata value",
                    MAX_DISCOVERY_METADATA_VALUE_CHARS,
                    MAX_DISCOVERY_METADATA_VALUE_UTF8_BYTES
                )
            }
        }
        val untrustedAuthenticationHint = authenticationHint?.let { hint ->
            PeerAuthenticationHint.UntrustedDiscoveryClaim(hint.fingerprint)
        }
        return copy(
            publicPeer = publicPeer.copy(supportedTransports = publicPeer.supportedTransports.toSet()),
            transportHints = transportHints.map { hint -> hint.copy(metadata = hint.metadata.toMap()) },
            origin = PeerOrigin.Discovered,
            authenticationHint = untrustedAuthenticationHint
        )
    }

    private fun validateDiscoveryPeerId(peerId: PeerId) {
        validateWireText(
            peerId.value,
            "discovery peer id",
            HelloPayload.MAX_FIELD_LEN,
            HelloPayload.MAX_FIELD_UTF8_BYTES,
            requireNonBlank = true
        )
    }

    private fun validateDiscoveryHost(host: String) {
        validateWireText(
            host,
            "discovery transport host",
            MAX_DISCOVERY_HOST_CHARS,
            MAX_DISCOVERY_HOST_UTF8_BYTES,
            requireNonBlank = true
        )
        require(host.none(Char::isWhitespace)) {
            "discovery transport host must not contain whitespace"
        }
    }

    private fun warnDiscoveryRejectionOnce(rejection: DiscoveryRejection) {
        while (true) {
            val logged = loggedDiscoveryRejections.value
            if (rejection in logged) return
            if (loggedDiscoveryRejections.compareAndSet(logged, logged + rejection)) {
                logger.warn(rejection.message)
                return
            }
        }
    }

    /** A discovery claim can refresh routing, but it can never erase an application-supplied manual pin. */
    private fun Map<PeerId, TrackedPeer>.upsertDiscoveredPeer(
        source: DiscoverySource,
        discovered: InternalPeer,
        lastSeenAtMillis: Long,
        observedAtMonotonicMillis: Long
    ): Map<PeerId, TrackedPeer> {
        val peerId = discovered.publicPeer.id
        val previous = this[peerId] ?: TrackedPeer()
        return this + (
            peerId to previous.copy(
                discoveredBy = previous.discoveredBy + (
                    source to DiscoveryContribution(
                        internalPeer = discovered,
                        lastSeenAtMillis = lastSeenAtMillis,
                        observedAtMonotonicMillis = observedAtMonotonicMillis
                    )
                )
            )
        )
    }

    private fun Map<PeerId, TrackedPeer>.removeDiscoveryContribution(
        source: DiscoverySource,
        peerId: PeerId
    ): Map<PeerId, TrackedPeer> {
        val previous = this[peerId] ?: return this
        val remaining = previous.copy(discoveredBy = previous.discoveredBy - source)
        return if (remaining.isEmpty) this - peerId else this + (peerId to remaining)
    }

    /** Withdraw every contribution owned by one failed/completed stream. */
    private fun removeDiscoverySource(source: DiscoverySource) {
        val committed = registryState.updateAndGet { current ->
            if (current.closed) return@updateAndGet current
            val tracked = current.tracked.mapValues { (_, trackedPeer) ->
                trackedPeer.copy(discoveredBy = trackedPeer.discoveredBy - source)
            }.filterValues { trackedPeer ->
                !trackedPeer.isEmpty
            }
            current.withTracked(
                tracked = tracked,
                discoveredPeerCount = tracked.values.count { it.discoveredBy.isNotEmpty() }
            )
        }
        publishPeers(committed)
    }

    internal fun evictStalePeers() {
        val now = monotonicClock()
        val committed = registryState.updateAndGet { current ->
            if (current.closed) return@updateAndGet current
            val tracked = current.tracked.mapValues { (_, trackedPeer) ->
                trackedPeer.copy(
                    discoveredBy = trackedPeer.discoveredBy.filterValues { contribution ->
                        contribution.internalPeer.discoveryLifetime() ==
                            DiscoveryLifetime.TransportManaged ||
                            now - contribution.observedAtMonotonicMillis <= staleTimeoutMillis
                    }
                )
            }.filterValues { trackedPeer ->
                !trackedPeer.isEmpty
            }
            current.withTracked(
                tracked = tracked,
                discoveredPeerCount = tracked.values.count { it.discoveredBy.isNotEmpty() }
            )
        }
        publishPeers(committed)
    }

    private fun currentOpenRegistryState(): PeerRegistryState {
        return registryState.value.also { state ->
            check(!state.closed) {
                "P2pKit has been stopped; manual peers cannot be registered"
            }
        }
    }

    @OptIn(ExperimentalUuidApi::class)
    override fun registerManualPeer(
        host: String,
        port: Int,
        kind: TransportKind,
        deviceName: String?,
        expectedFingerprint: PeerFingerprint?
    ): Peer {
        currentOpenRegistryState()
        val normalizedHost = normalizeManualHost(host)
        require(port in 1..65_535) { "port out of range: $port" }
        deviceName?.takeIf { it.isNotBlank() }?.let { name ->
            validateWireText(
                name,
                "manual peer deviceName",
                HelloPayload.MAX_FIELD_LEN,
                HelloPayload.MAX_FIELD_UTF8_BYTES,
                requireNonBlank = true
            )
        }
        val authenticatedPeerId = when (securityProfile) {
            TransportSecurityProfile.AuthenticatedV2 -> {
                val fingerprint = expectedFingerprint
                    ?: throw P2pError.SecurityConfigurationInvalid(
                        "Secure manual peer registration requires an out-of-band fingerprint"
                    )
                val derivePeerId = peerIdFromFingerprint
                    ?: throw P2pError.SecurityConfigurationInvalid(
                        "Secure manual peer identity derivation is unavailable"
                    )
                derivePeerId(fingerprint)
            }
            TransportSecurityProfile.LegacyPlaintextV1 -> {
                if (expectedFingerprint != null) {
                    throw P2pError.SecurityConfigurationInvalid(
                        "Legacy plaintext manual peers cannot authenticate a fingerprint"
                    )
                }
                null
            }
        }

        // Dedup by (host, port, kind): repeated registrations of the same
        // endpoint reuse the existing synthetic peer instead of minting a
        // fresh "manual-<uuid>" each time. Without this, a provisioning
        // manager calling createManualPeer once per connect attempt grew the
        // registry unbounded (manual entries are eviction-exempt).
        // Manual peers are session-scoped: they live only in this in-memory
        // map, so they are forgotten on kit.stop() / process exit and a stale
        // IP is never silently redialed in a later session (AUDIT-2026-06).
        while (true) {
            val currentState = currentOpenRegistryState()
            val current = currentState.tracked
            val existingEntry = current.entries.firstOrNull { (_, trackedPeer) ->
                trackedPeer.manual?.internalPeer?.transportHints?.any {
                    it.type == kind && it.host == normalizedHost && it.port == port
                } == true && (
                    authenticatedPeerId == null ||
                        trackedPeer.internalPeer.publicPeer.id == authenticatedPeerId
                    )
            }
            if (existingEntry != null) {
                val (existingId, existing) = existingEntry
                val existingPeer = existing.internalPeer.publicPeer
                val refreshedName = deviceName?.takeIf { it.isNotBlank() }
                if (refreshedName == null || refreshedName == existingPeer.name) {
                    return existingPeer
                }
                val refreshedManual = checkNotNull(existing.manual).copy(
                    internalPeer = existing.manual.internalPeer.copy(
                        publicPeer = existing.manual.internalPeer.publicPeer.copy(name = refreshedName)
                    ),
                    registeredAtMillis = clock()
                )
                val updated = current + (existingId to existing.copy(manual = refreshedManual))
                beforeManualPeerCompareAndSetForTest?.invoke()
                val updatedState = currentState.withTracked(
                    tracked = updated,
                    discoveredPeerCount = currentState.discoveredPeerCount
                )
                if (registryState.compareAndSet(currentState, updatedState)) {
                    publishPeers(updatedState)
                    return checkNotNull(updated[existingId]).internalPeer.publicPeer
                }
                continue
            }

            val peerId = authenticatedPeerId ?: PeerId("manual-${Uuid.random()}")
            val displayName = deviceName?.takeIf { it.isNotBlank() } ?: "manual:$normalizedHost:$port"
            val publicPeer = Peer(
                id = peerId,
                name = displayName,
                platform = Platform.UNKNOWN,
                supportedTransports = setOf(kind)
            )
            val internal = InternalPeer(
                publicPeer = publicPeer,
                transportHints = listOf(TransportHint(type = kind, host = normalizedHost, port = port)),
                // Explicit provenance: SessionManager keys its manual-peer HELLO
                // handling off this flag, never off the "manual-" id prefix.
                origin = PeerOrigin.Manual,
                authenticationHint = expectedFingerprint?.let(PeerAuthenticationHint::TrustedApplicationPin)
            )
            val withoutSupersededEndpoint = if (authenticatedPeerId == null) {
                current
            } else {
                current.mapValues { (_, trackedPeer) ->
                    val manual = trackedPeer.manual
                    if (manual != null && manual.internalPeer.transportHints.any {
                            it.type == kind && it.host == normalizedHost && it.port == port
                        }
                    ) {
                        trackedPeer.copy(manual = null)
                    } else {
                        trackedPeer
                    }
                }.filterValues { !it.isEmpty }
            }
            val previous = withoutSupersededEndpoint[peerId] ?: TrackedPeer()
            val updated = withoutSupersededEndpoint + (
                peerId to previous.copy(manual = ManualContribution(internal, clock()))
            )
            beforeManualPeerCompareAndSetForTest?.invoke()
            val updatedState = currentState.withTracked(
                tracked = updated,
                discoveredPeerCount = currentState.discoveredPeerCount
            )
            if (registryState.compareAndSet(currentState, updatedState)) {
                publishPeers(updatedState)
                return publicPeer
            }
        }
    }

    /** Seal the process-local registry and publish an empty terminal snapshot. */
    fun close() {
        val committed = registryState.updateAndGet { current ->
            if (current.closed && current.tracked.isEmpty()) {
                current
            } else {
                current.copy(
                    closed = true,
                    tracked = emptyMap(),
                    discoveredPeerCount = 0,
                    generation = current.generation + 1
                )
            }
        }
        publishPeers(committed)
    }

    private fun normalizeManualHost(host: String): String {
        val trimmed = host.trim()
        val unwrapped = if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
            trimmed.substring(1, trimmed.lastIndex)
        } else {
            trimmed
        }
        require(unwrapped.isNotBlank()) { "host must not be blank" }
        require(unwrapped.length <= MAX_MANUAL_HOST_CHARS) { "host is too long" }
        require(unwrapped.none { it.isWhitespace() || it.code < 0x20 || it.code in 0x7F..0x9F }) {
            "host must not contain whitespace or control characters"
        }
        require(unwrapped.none { it == '/' || it == '?' || it == '#' || it == '@' }) {
            "host must not contain URI path, query, fragment, or user-info delimiters"
        }
        return unwrapped.lowercase()
    }

    private suspend fun evictLoop() {
        while (scope.isActive) {
            delay(evictionPollMillis)
            // Isolate per-iteration failures so one throw can't kill peer
            // eviction for the kit's lifetime (rethrow cancellation).
            try {
                evictStalePeers()
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Throwable) {
                logger.warn("Peer eviction iteration failed; retrying on the next poll", e)
            }
        }
    }

    companion object {
        const val DEFAULT_STALE_TIMEOUT_MS: Long = 15_000
        const val DEFAULT_EVICTION_POLL_MS: Long = 1_000
        internal const val MAX_DISCOVERED_PEERS: Int = 1_024
        private const val EVENT_RECOLLECT_INITIAL_DELAY_MS: Long = 100
        private const val EVENT_RECOLLECT_MAX_DELAY_MS: Long = 5_000
        private const val MAX_EVENT_RECOLLECT_EXPONENT: Int = 6
        private const val MAX_MANUAL_HOST_CHARS: Int = 253
        private const val MAX_DISCOVERY_HOST_CHARS: Int = 253
        private const val MAX_DISCOVERY_HOST_UTF8_BYTES: Int = MAX_DISCOVERY_HOST_CHARS * 4
        private const val MAX_DISCOVERY_HINTS: Int = 32
        private const val MAX_DISCOVERY_METADATA_ENTRIES: Int = 16
        private const val MAX_DISCOVERY_METADATA_KEY_CHARS: Int = 64
        private const val MAX_DISCOVERY_METADATA_KEY_UTF8_BYTES: Int =
            MAX_DISCOVERY_METADATA_KEY_CHARS * 4
        private const val MAX_DISCOVERY_METADATA_VALUE_CHARS: Int = 256
        private const val MAX_DISCOVERY_METADATA_VALUE_UTF8_BYTES: Int =
            MAX_DISCOVERY_METADATA_VALUE_CHARS * 4
        private val DIRECT_SOURCE = DiscoverySource(-1)
    }
}

@JvmInline
private value class DiscoverySource(val index: Int)

private data class PeerRegistryState(
    val closed: Boolean = false,
    val tracked: Map<PeerId, TrackedPeer> = emptyMap(),
    val discoveredPeerCount: Int = 0,
    val generation: Long = 0L
) {
    fun withTracked(
        tracked: Map<PeerId, TrackedPeer>,
        discoveredPeerCount: Int
    ): PeerRegistryState {
        if (this.tracked == tracked && this.discoveredPeerCount == discoveredPeerCount) return this
        check(discoveredPeerCount >= 0) { "discovered peer count underflow" }
        return copy(
            tracked = tracked,
            discoveredPeerCount = discoveredPeerCount,
            generation = generation + 1
        )
    }
}

private sealed interface AdmittedDiscoveryEvent {
    data class Upsert(val peer: InternalPeer) : AdmittedDiscoveryEvent
    data class Lost(val peerId: PeerId) : AdmittedDiscoveryEvent
}

private data class DiscoveryObservation(
    val epochMillis: Long,
    val monotonicMillis: Long
)

private enum class DiscoveryRejection(val message: String) {
    InvalidEvent("Rejected an invalid discovery event"),
    CapacityExhausted("Rejected a discovery event because peer capacity is exhausted")
}

private data class PeerPublication(
    val generation: Long,
    val peers: List<Peer>
)

/**
 * Projects generation-bearing publications onto the established public state
 * type while retaining StateFlow's equality de-noising for heartbeat updates.
 */
@OptIn(ExperimentalForInheritanceCoroutinesApi::class)
private class PeerListStateFlow(
    private val source: StateFlow<PeerPublication>
) : StateFlow<List<Peer>> {
    override val value: List<Peer> get() = source.value.peers

    override val replayCache: List<List<Peer>> get() = listOf(value)

    override suspend fun collect(collector: FlowCollector<List<Peer>>): Nothing {
        var initialized = false
        var previous: List<Peer> = emptyList()
        source.collect { publication ->
            val next = publication.peers
            if (!initialized || previous != next) {
                initialized = true
                previous = next
                collector.emit(next)
            }
        }
    }
}

private data class DiscoveryContribution(
    val internalPeer: InternalPeer,
    val lastSeenAtMillis: Long,
    val observedAtMonotonicMillis: Long
)

private data class ManualContribution(
    val internalPeer: InternalPeer,
    val registeredAtMillis: Long
)

private data class TrackedPeer(
    val manual: ManualContribution? = null,
    val discoveredBy: Map<DiscoverySource, DiscoveryContribution> = emptyMap()
) {
    val internalPeer: InternalPeer
        get() {
            val discovered = discoveredBy.entries
                .sortedBy { it.key.index }
                .map { it.value.internalPeer }
            val primary = discovered.firstOrNull() ?: checkNotNull(manual).internalPeer
            val allClaims = buildList {
                manual?.let { add(it.internalPeer) }
                addAll(discovered)
            }
            val retainedPin = manual?.internalPeer?.authenticationHint as?
                PeerAuthenticationHint.TrustedApplicationPin
            return primary.copy(
                publicPeer = primary.publicPeer.copy(
                    supportedTransports = allClaims
                        .flatMap { it.publicPeer.supportedTransports }
                        .toSet()
                ),
                transportHints = allClaims.flatMap { it.transportHints }.distinct(),
                origin = if (manual != null) PeerOrigin.Manual else PeerOrigin.Discovered,
                authenticationHint = retainedPin ?: primary.authenticationHint
            )
        }

    val lastSeenAtMillis: Long
        get() = maxOf(
            manual?.registeredAtMillis ?: Long.MIN_VALUE,
            discoveredBy.values.maxOfOrNull { it.lastSeenAtMillis } ?: Long.MIN_VALUE
        )

    val isEmpty: Boolean get() = manual == null && discoveredBy.isEmpty()

    /**
     * True for entries created by [PeerRegistry.registerManualPeer]; exempt
     * from staleness eviction. Derived from [InternalPeer.origin] so there is
     * a single source of provenance truth (no second flag that could drift).
     */
    val isManual: Boolean get() = manual != null
}
