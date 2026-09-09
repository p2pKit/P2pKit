package dev.p2pkit.core.testfixtures

import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.DiscoveryTransport
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.PeerEvent
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.first

/**
 * Test-controllable [DiscoveryTransport]. Tests push [PeerEvent]s through
 * [emit] to drive `PeerRegistry` updates deterministically — used by
 * scenarios that need to simulate address rotation (V0.4-RECONNECT).
 *
 * No actual discovery work is performed; `start*` / `stop*` are recorded as
 * counters so the kit lifecycle can be asserted if needed.
 *
 * This is a synthetic replay-zero event source, not the shipped LAN relay.
 * Both modes discard events emitted without a subscriber. Default mode uses
 * a 256-event buffer and drops the oldest events under backlog. With
 * [strictDelivery], emission suspends only when an active subscriber's buffer
 * is full; completion means buffer acceptance, not consumer processing.
 *
 * The production LAN relay instead retains current peers and replays them to
 * new collectors, while allowing intermediate updates to conflate. Tests using
 * this fake must [awaitSubscriber] before emitting, then await the registry's
 * observable postcondition when they need proof that an event was processed.
 */
internal class FakeDiscoveryTransport(
    override val type: TransportKind = TransportKind.LAN,
    private val strictDelivery: Boolean = false
) : DiscoveryTransport {

    private val _events = MutableSharedFlow<PeerEvent>(
        replay = 0,
        extraBufferCapacity = 256,
        onBufferOverflow = if (strictDelivery) BufferOverflow.SUSPEND else BufferOverflow.DROP_OLDEST
    )
    override val events: Flow<PeerEvent> = _events.asSharedFlow()

    var startAdvertisingCalls: Int = 0
        private set
    var stopAdvertisingCalls: Int = 0
        private set
    var startDiscoveryCalls: Int = 0
        private set
    var stopDiscoveryCalls: Int = 0
        private set
    var refreshCalls: Int = 0
        private set

    override suspend fun startAdvertising(localPeer: LocalPeerInfo) {
        startAdvertisingCalls++
    }

    override suspend fun stopAdvertising() {
        stopAdvertisingCalls++
    }

    override suspend fun startDiscovery() {
        startDiscoveryCalls++
    }

    override suspend fun stopDiscovery() {
        stopDiscoveryCalls++
    }

    override suspend fun refresh() {
        refreshCalls++
    }

    /** Wait for an active subscriber; this does not acknowledge registry processing. */
    suspend fun awaitSubscriber() {
        _events.subscriptionCount.first { it > 0 }
    }

    /**
     * Enqueue a synthetic event. With no subscriber, both modes discard it.
     * Default mode never suspends and drops oldest entries under backlog;
     * [strictDelivery] suspends at buffer saturation, not until processing.
     */
    suspend fun emit(event: PeerEvent) {
        if (strictDelivery) {
            _events.emit(event)
        } else {
            _events.tryEmit(event)
        }
    }
}
