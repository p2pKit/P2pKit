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
 * counters so the kit lifecycle can be asserted if needed. Events are
 * delivered via a [MutableSharedFlow] with `replay = 0` to match the
 * production semantics of [dev.p2pkit.core.transport.DiscoveryTransport].
 */
internal class FakeDiscoveryTransport(
    override val type: TransportKind = TransportKind.LAN
) : DiscoveryTransport {

    private val _events = MutableSharedFlow<PeerEvent>(
        replay = 0,
        extraBufferCapacity = 64,
        onBufferOverflow = BufferOverflow.SUSPEND
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

    /** Push a discovery event into the kit's `PeerRegistry`. */
    suspend fun emit(event: PeerEvent) {
        _events.emit(event)
    }
}
