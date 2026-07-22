package dev.p2pkit.core.internal

import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.P2pError
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
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.flow.update
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
 * @param clock Source of "now" in epoch milliseconds. Must be provided
 *   explicitly because `System.currentTimeMillis` is not available in
 *   commonMain. P2pKitImpl wires up the platform clock; tests inject a fake.
 */
@OptIn(ExperimentalP2pApi::class)
internal class PeerRegistry(
    private val discoveryTransports: List<DiscoveryTransport>,
    private val scope: CoroutineScope,
    private val clock: () -> Long,
    private val staleTimeoutMillis: Long = DEFAULT_STALE_TIMEOUT_MS,
    private val evictionPollMillis: Long = DEFAULT_EVICTION_POLL_MS,
    private val securityProfile: TransportSecurityProfile = TransportSecurityProfile.LegacyPlaintextV1,
    private val peerIdFromFingerprint: ((PeerFingerprint) -> PeerId)? = null
) : ManualPeerRegistrar {

    private val tracked: MutableStateFlow<Map<PeerId, TrackedPeer>> = MutableStateFlow(emptyMap())
    private val _peers: MutableStateFlow<List<Peer>> = MutableStateFlow(emptyList())

    /**
     * Public-facing peer list. Updated synchronously after every accepted
     * [PeerEvent]; emits a new value only when the visible peer set actually
     * changes (heartbeat-only updates to `lastSeen` do not churn this flow).
     */
    val peers: StateFlow<List<Peer>> = _peers.asStateFlow()

    fun lastSeen(peerId: PeerId): Long? = tracked.value[peerId]?.lastSeenAtMillis

    /**
     * Returns the [InternalPeer] (including transport hints) for [peerId] if
     * still tracked. Used by SessionManager to resolve a public [Peer] back to
     * its discovery-time reach information.
     */
    fun internalPeer(peerId: PeerId): InternalPeer? = tracked.value[peerId]?.internalPeer

    fun start() {
        discoveryTransports.forEachIndexed { sourceIndex, transport ->
            transport.events
                .onEach { event -> processEvent(DiscoverySource(sourceIndex), event) }
                .launchIn(scope)
        }
        scope.launch { evictLoop() }
    }

    internal fun processEvent(event: PeerEvent) = processEvent(DIRECT_SOURCE, event)

    private fun processEvent(source: DiscoverySource, event: PeerEvent) {
        tracked.update { current ->
            when (event) {
                is PeerEvent.Found -> current.upsertDiscoveredPeer(source, event.peer)
                is PeerEvent.Updated -> current.upsertDiscoveredPeer(source, event.peer)
                is PeerEvent.Lost -> current.removeDiscoveryContribution(source, event.peerId)
            }
        }
        publishPeers()
    }

    private fun publishPeers() {
        val newList = tracked.value.values.map { it.internalPeer.publicPeer }
        if (_peers.value != newList) _peers.value = newList
    }

    /** A discovery claim can refresh routing, but it can never erase an application-supplied manual pin. */
    private fun Map<PeerId, TrackedPeer>.upsertDiscoveredPeer(
        source: DiscoverySource,
        discovered: InternalPeer
    ): Map<PeerId, TrackedPeer> {
        val peerId = discovered.publicPeer.id
        val previous = this[peerId] ?: TrackedPeer()
        return this + (
            peerId to previous.copy(
                discoveredBy = previous.discoveredBy + (
                    source to DiscoveryContribution(discovered.snapshotForRegistry(), clock())
                )
            )
        )
    }

    private fun InternalPeer.snapshotForRegistry(): InternalPeer = copy(
        publicPeer = publicPeer.copy(supportedTransports = publicPeer.supportedTransports.toSet()),
        transportHints = transportHints.map { hint ->
            hint.copy(metadata = hint.metadata.toMap())
        }
    )

    private fun Map<PeerId, TrackedPeer>.removeDiscoveryContribution(
        source: DiscoverySource,
        peerId: PeerId
    ): Map<PeerId, TrackedPeer> {
        val previous = this[peerId] ?: return this
        val remaining = previous.copy(discoveredBy = previous.discoveredBy - source)
        return if (remaining.isEmpty) this - peerId else this + (peerId to remaining)
    }

    internal fun evictStalePeers() {
        val now = clock()
        tracked.update { current ->
            current.mapValues { (_, trackedPeer) ->
                trackedPeer.copy(
                    discoveredBy = trackedPeer.discoveredBy.filterValues { contribution ->
                        contribution.internalPeer.discoveryLifetime() == DiscoveryLifetime.TransportManaged ||
                            now - contribution.lastSeenAtMillis <= staleTimeoutMillis
                    }
                )
            }.filterValues { trackedPeer ->
                !trackedPeer.isEmpty
            }
        }
        publishPeers()
    }

    @OptIn(ExperimentalUuidApi::class)
    override fun registerManualPeer(
        host: String,
        port: Int,
        kind: TransportKind,
        deviceName: String?,
        expectedFingerprint: PeerFingerprint?
    ): Peer {
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
        val existing = tracked.value.values.firstOrNull { t ->
            t.manual?.internalPeer?.transportHints?.any {
                it.type == kind && it.host == normalizedHost && it.port == port
            } == true && (authenticatedPeerId == null || t.internalPeer.publicPeer.id == authenticatedPeerId)
        }
        if (existing != null) {
            val existingPeer = existing.internalPeer.publicPeer
            // AUDIT-2026-07 (IDN-7): a re-registration that supplies a new
            // non-blank display name refreshes the stored name instead of
            // silently dropping it — same endpoint keeps the same synthetic
            // id and single registry entry. Null/blank keeps the old name.
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
            tracked.update { current ->
                current + (existingPeer.id to existing.copy(manual = refreshedManual))
            }
            publishPeers()
            return checkNotNull(tracked.value[existingPeer.id]).internalPeer.publicPeer
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
        tracked.update { current ->
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
            withoutSupersededEndpoint + (
                peerId to previous.copy(manual = ManualContribution(internal, clock()))
            )
        }
        publishPeers()
        return publicPeer
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
                // No logger here by design; swallow and keep the loop alive.
            }
        }
    }

    companion object {
        const val DEFAULT_STALE_TIMEOUT_MS: Long = 15_000
        const val DEFAULT_EVICTION_POLL_MS: Long = 1_000
        private const val MAX_MANUAL_HOST_CHARS: Int = 253
        private val DIRECT_SOURCE = DiscoverySource(-1)
    }
}

@JvmInline
private value class DiscoverySource(val index: Int)

private data class DiscoveryContribution(
    val internalPeer: InternalPeer,
    val lastSeenAtMillis: Long
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
