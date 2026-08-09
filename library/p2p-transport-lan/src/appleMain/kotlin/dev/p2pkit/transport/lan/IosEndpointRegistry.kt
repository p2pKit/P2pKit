@file:OptIn(ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.core.PeerId
import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.update
import platform.Network.nw_endpoint_t

/**
 * Bridge from discovery to data transport on iOS.
 *
 * `NWBrowser` yields `NWBrowser.Result` values whose underlying
 * `nw_endpoint_t` is opaque — there's no public host/port to encode into a
 * [dev.p2pkit.core.transport.TransportHint] the way JmDNS does on JVM/Android.
 * Instead, the discovery transport stashes the endpoint here keyed by
 * [PeerId], and [IosLanDataTransport.connect] dials it directly via
 * `nw_connection_create(endpoint, parameters)`.
 *
 * Reads and writes are non-suspending so [IosLanDataTransport.canConnect]
 * — which the [dev.p2pkit.core.internal.TransportManager] calls synchronously
 * — can consult the registry without taking a lock.
 */
internal class IosEndpointRegistry {

    /**
     * Immutable ownership token for one endpoint published by one browser
     * generation. Data transport keeps the token (not just the opaque native
     * endpoint) so a failed dial can invalidate only the stale value it used;
     * a concurrent fresh browse result must never be deleted by that failure.
     */
    internal class Lease(
        val endpoint: nw_endpoint_t,
        val browserGeneration: Int
    )

    private val entries = MutableStateFlow<Map<PeerId, Lease>>(emptyMap())

    fun put(peerId: PeerId, endpoint: nw_endpoint_t, browserGeneration: Int): Lease {
        val lease = Lease(endpoint, browserGeneration)
        entries.update { it + (peerId to lease) }
        return lease
    }

    fun get(peerId: PeerId): nw_endpoint_t = entries.value[peerId]?.endpoint

    fun lease(peerId: PeerId): Lease? = entries.value[peerId]

    /**
     * Remove only when [expected] still owns the peer. A TXT update or a
     * replacement browser may already have installed a fresh endpoint while
     * the old connection attempt was failing.
     */
    fun removeIfCurrent(peerId: PeerId, expected: Lease): Boolean {
        while (true) {
            val current = entries.value
            if (current[peerId] !== expected) return false
            if (entries.compareAndSet(current, current - peerId)) return true
        }
    }

    fun remove(peerId: PeerId) {
        entries.update { it - peerId }
    }

    fun clear() {
        entries.value = emptyMap()
    }

    internal fun sizeForTest(): Int = entries.value.size
}
