package dev.p2pkit.transport.lan

import dev.p2pkit.core.PeerId
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.PeerEvent
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.update

/**
 * Non-blocking, state-backed bridge from platform discovery callbacks to the
 * core [PeerEvent] stream.
 *
 * Native/JmDNS callbacks cannot suspend. A bounded `MutableSharedFlow` with a
 * drop policy therefore loses lifecycle transitions when its collector is
 * briefly slower than discovery churn; a dropped [PeerEvent.Lost] can leave a
 * transport-managed peer in the core registry indefinitely. This relay stores
 * only the authoritative live-peer set instead of event history. Every
 * collector diffs successive snapshots, and a new collector receives the
 * complete current set as `Found`. `PeerRegistry` clears the old source
 * contribution before recollection, so the two sides converge even when a
 * removal happened during an event-stream outage.
 *
 * The private `lifecycleToken` distinguishes a peer that was removed and then
 * re-added from an in-place update. Even when `StateFlow` conflates the
 * intermediate empty snapshot, a collector that previously observed that
 * peer receives `Lost` followed by `Found`. Intermediate updates may be
 * coalesced to their latest value; that is intentional because this is a
 * current-state relay, not an unbounded discovery-history log.
 */
internal class ReliablePeerEventRelay(
    private val maxTrackedPeers: Int = MAX_TRACKED_LAN_PEERS,
    private val onCapacityRejected: (PeerId) -> Unit = {}
) {
    private data class RelayEntry(
        val peer: InternalPeer,
        /** Fresh identity for each absent -> present lifecycle. */
        val lifecycleToken: Any
    )

    private val state = MutableStateFlow<Map<PeerId, RelayEntry>>(emptyMap())
    private val capacityRejectionReported = MutableStateFlow(false)

    init {
        require(maxTrackedPeers > 0) { "maxTrackedPeers must be > 0" }
    }

    /** A per-collector lifecycle diff of the authoritative live-peer set. */
    val events: Flow<PeerEvent> = flow {
        var previous: Map<PeerId, RelayEntry> = emptyMap()
        state.collect { current ->
            previous.keys
                .asSequence()
                .filter { it !in current }
                .sortedBy { it.value }
                .forEach { emit(PeerEvent.Lost(it)) }

            current.keys
                .asSequence()
                .sortedBy { it.value }
                .forEach { peerId ->
                    val next = checkNotNull(current[peerId])
                    val prior = previous[peerId]
                    when {
                        prior == null -> emit(PeerEvent.Found(next.peer))
                        prior.lifecycleToken !== next.lifecycleToken -> {
                            emit(PeerEvent.Lost(peerId))
                            emit(PeerEvent.Found(next.peer))
                        }
                        prior.peer != next.peer -> emit(PeerEvent.Updated(next.peer))
                    }
                }

            previous = current
        }
    }

    /** Publish a new peer or the latest immutable value for an existing one. */
    fun upsert(peer: InternalPeer): Boolean {
        val peerId = peer.publicPeer.id
        while (true) {
            val current = state.value
            val prior = current[peerId]
            if (prior == null && current.size >= maxTrackedPeers) {
                if (capacityRejectionReported.compareAndSet(expect = false, update = true)) {
                    onCapacityRejected(peerId)
                }
                return false
            }
            val updated = when {
                prior == null -> current + (peerId to RelayEntry(peer, Any()))
                prior.peer == peer -> return true
                else -> current + (peerId to prior.copy(peer = peer))
            }
            if (state.compareAndSet(current, updated)) return true
        }
    }

    /** Withdraw one peer if this transport currently owns it. */
    fun remove(peerId: PeerId) {
        state.update { current ->
            if (peerId in current) current - peerId else current
        }
    }

    /** Withdraw every peer, for terminal discovery stop/rollback. */
    fun clear() {
        state.update { current ->
            if (current.isEmpty()) current else emptyMap()
        }
    }

    internal fun sizeForTest(): Int = state.value.size
}

/** Hard ceiling for unauthenticated discovery identities retained per transport. */
internal const val MAX_TRACKED_LAN_PEERS: Int = 256
