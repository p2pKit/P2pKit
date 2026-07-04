package dev.p2pkit.core.testfixtures

import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.DiscoveryTransport
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.PeerEvent
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow

/**
 * Test-controllable [DiscoveryTransport]. Tests push [PeerEvent]s through
 * [emit] to drive `PeerRegistry` updates deterministically — used by
 * scenarios that need to simulate address rotation (V0.4-RECONNECT).
 *
 * No actual discovery work is performed; `start*` / `stop*` are recorded as
 * counters so the kit lifecycle can be asserted if needed.
 *
 * Delivery semantics (fixture change F4 / TST-4): by default the event flow
 * is **production-shaped**, matching all three shipped LAN discovery
 * transports — `MutableSharedFlow(replay = 0, extraBufferCapacity = 256,
 * onBufferOverflow = DROP_OLDEST)` fed via `tryEmit`. That means events
 * emitted while no collector is subscribed are not delivered, and a
 * collector lagging more than 256 events behind loses the oldest ones —
 * exactly like production. Construct with [strictDelivery] = true for tests
 * that must not lose events under backlog: the flow then uses
 * `BufferOverflow.SUSPEND` and [emit] suspends until delivered.
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

    /**
     * Push a discovery event into the kit's `PeerRegistry`. Default mode is
     * `tryEmit`-shaped like production (never suspends; DROP_OLDEST under
     * backlog); with [strictDelivery] it suspends until delivered.
     */
    suspend fun emit(event: PeerEvent) {
        if (strictDelivery) {
            _events.emit(event)
        } else {
            _events.tryEmit(event)
        }
    }
}
