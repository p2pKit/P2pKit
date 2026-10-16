package dev.p2pkit.transport.lan

import java.net.InetAddress
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class AndroidLanNetworkStateTest {
    @Test
    fun organizationRouteIsResolvedOnEveryLookupInsteadOfUsingDiscoverySnapshot() {
        val stale = target(1)
        val first = target(2)
        val second = target(3)
        var current = first
        var resolutions = 0
        val state = AndroidLanNetworkState(requireFresh = true) {
            resolutions++
            current
        }
        state.select(stale)

        assertEquals(first.address, state.selectedRoute()?.localAddress)
        current = second
        assertEquals(second.address, state.selectedRoute()?.localAddress)
        assertEquals(2, resolutions)
    }

    @Test
    fun unavailableOrganizationRouteNeverFallsBackToAnEarlierSelectedRoute() {
        var current: AndroidLanBindTarget? = target(2)
        val state = AndroidLanNetworkState(requireFresh = true) { current }
        state.select(target(1))
        assertEquals(current?.address, state.selectedRoute()?.localAddress)

        current = null
        assertNull(state.selectedRoute())
        state.select(target(3))
        assertNull(state.selectedRoute())
        state.clear()
        assertNull(state.selectedRoute())
    }

    private fun target(lastOctet: Int): AndroidLanBindTarget {
        val address = InetAddress.getByAddress(byteArrayOf(10, 0, 0, lastOctet.toByte()))
        return AndroidLanBindTarget(
            network = null,
            interfaceName = "synthetic-lan",
            address = address,
            localAddresses = emptyList(),
            fingerprint = "synthetic-route-$lastOctet",
        )
    }
}
