package dev.p2pkit.core.internal

import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.provisioning.ManualPeerRegistrar
import dev.p2pkit.core.transport.DiscoveryTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.TransportHint
import kotlin.uuid.ExperimentalUuidApi
import kotlin.uuid.Uuid
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
    private val evictionPollMillis: Long = DEFAULT_EVICTION_POLL_MS
) : ManualPeerRegistrar {

    /**
     * Peer ids whose [TrackedPeer] entry was created by
     * [registerManualPeer], not by a discovery `Found` event. These are
     * skipped by the staleness sweeper since no transport sends heartbeats
     * for them.
     */
    private val manualPeerIds: MutableSet<PeerId> = mutableSetOf()

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
        discoveryTransports.forEach { transport ->
            transport.events
                .onEach(::processEvent)
                .launchIn(scope)
        }
        scope.launch { evictLoop() }
    }

    internal fun processEvent(event: PeerEvent) {
        tracked.update { current ->
            when (event) {
                is PeerEvent.Found -> current + (event.peer.publicPeer.id to TrackedPeer(event.peer, clock()))
                is PeerEvent.Updated -> current + (event.peer.publicPeer.id to TrackedPeer(event.peer, clock()))
                is PeerEvent.Lost -> current - event.peerId
            }
        }
        publishPeers()
    }

    private fun publishPeers() {
        val newList = tracked.value.values.map { it.internalPeer.publicPeer }
        if (_peers.value != newList) _peers.value = newList
    }

    internal fun evictStalePeers() {
        val now = clock()
        tracked.update { current ->
            current.filterValues { tracked ->
                tracked.internalPeer.publicPeer.id in manualPeerIds ||
                    now - tracked.lastSeenAtMillis <= staleTimeoutMillis
            }
        }
        publishPeers()
    }

    @OptIn(ExperimentalUuidApi::class)
    override fun registerManualPeer(
        host: String,
        port: Int,
        kind: TransportKind,
        deviceName: String?
    ): Peer {
        require(host.isNotBlank()) { "host must not be blank" }
        require(port in 1..65_535) { "port out of range: $port" }
        val syntheticId = PeerId("manual-${Uuid.random()}")
        val displayName = deviceName?.takeIf { it.isNotBlank() } ?: "manual:$host:$port"
        val publicPeer = Peer(
            id = syntheticId,
            name = displayName,
            platform = Platform.UNKNOWN,
            supportedTransports = setOf(kind)
        )
        val internal = InternalPeer(
            publicPeer = publicPeer,
            transportHints = listOf(TransportHint(type = kind, host = host, port = port))
        )
        tracked.update { current -> current + (syntheticId to TrackedPeer(internal, clock())) }
        manualPeerIds.add(syntheticId)
        publishPeers()
        return publicPeer
    }

    private suspend fun evictLoop() {
        while (scope.isActive) {
            delay(evictionPollMillis)
            evictStalePeers()
        }
    }

    companion object {
        const val DEFAULT_STALE_TIMEOUT_MS: Long = 15_000
        const val DEFAULT_EVICTION_POLL_MS: Long = 1_000
    }
}

internal data class TrackedPeer(
    val internalPeer: InternalPeer,
    val lastSeenAtMillis: Long
) {
    val peer: Peer get() = internalPeer.publicPeer
}
