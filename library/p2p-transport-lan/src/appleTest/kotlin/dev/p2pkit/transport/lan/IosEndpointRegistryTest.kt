@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.core.PeerId
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertSame
import kotlin.test.assertTrue
import platform.Network.nw_endpoint_create_host

class IosEndpointRegistryTest {

    @Test
    fun failedOldDialCannotDeleteConcurrentFreshEndpoint() {
        val registry = IosEndpointRegistry()
        val peerId = PeerId("endpoint-generation-peer")
        val oldEndpoint = assertNotNull(nw_endpoint_create_host("127.0.0.1", "41001"))
        val freshEndpoint = assertNotNull(nw_endpoint_create_host("127.0.0.1", "41002"))

        val oldLease = registry.put(peerId, oldEndpoint, browserGeneration = 1)
        val freshLease = registry.put(peerId, freshEndpoint, browserGeneration = 2)

        assertFalse(registry.removeIfCurrent(peerId, oldLease))
        assertSame(freshLease, registry.lease(peerId))
        assertEquals(2, registry.lease(peerId)?.browserGeneration)
        assertTrue(registry.removeIfCurrent(peerId, freshLease))
        assertEquals(0, registry.sizeForTest())
    }

    @Test
    fun browserGenerationClearRemovesEveryOpaqueEndpoint() {
        val registry = IosEndpointRegistry()
        registry.put(
            PeerId("endpoint-clear-peer-a"),
            assertNotNull(nw_endpoint_create_host("127.0.0.1", "42001")),
            browserGeneration = 4
        )
        registry.put(
            PeerId("endpoint-clear-peer-b"),
            assertNotNull(nw_endpoint_create_host("127.0.0.1", "42002")),
            browserGeneration = 4
        )

        assertEquals(2, registry.sizeForTest())
        registry.clear()
        assertEquals(0, registry.sizeForTest())
    }
}
