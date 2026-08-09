package dev.p2pkit.transport.lan

import java.net.InetAddress
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotEquals
import kotlin.test.assertNull

/** Deterministic AP/tether fallback selection tests; no Android runtime needed. */
class AndroidLanBindSelectorTest {
    @Test
    fun prefersExplicitApInterfaceOverOrdinaryWifiName() {
        val selected = selectAndroidFallbackBindTarget(
            listOf(
                snapshot("wlan0", "192.168.1.20"),
                snapshot("softap0", "192.168.43.1")
            )
        )

        assertEquals("softap0", selected?.interfaceName)
        assertEquals("192.168.43.1", selected?.address?.hostAddress)
        assertNull(selected?.network)
    }

    @Test
    fun supportsKnownOemApAndTetherNames() {
        listOf("ap0", "softap0", "swlan0", "tether0", "wlan1", "wifi0").forEach { name ->
            assertEquals(
                name,
                selectAndroidFallbackBindTarget(listOf(snapshot(name, "10.42.0.1")))?.interfaceName
            )
        }
    }

    @Test
    fun rejectsCellularVpnContainerPublicAndIneligibleInterfaces() {
        val selected = selectAndroidFallbackBindTarget(
            listOf(
                snapshot("rmnet_data0", "10.0.0.2"),
                snapshot("tun0", "10.8.0.2"),
                snapshot("docker0", "172.17.0.1"),
                snapshot("wlan0", "203.0.113.7"),
                snapshot("ap0", "192.168.43.1", isUp = false),
                snapshot("softap0", "192.168.44.1", supportsMulticast = false)
            )
        )

        assertNull(selected)
    }

    @Test
    fun addressReadinessAndRotationChangeFingerprint() {
        val first = selectAndroidFallbackBindTarget(
            listOf(snapshot("ap0", "192.168.43.1"))
        )
        val rotated = selectAndroidFallbackBindTarget(
            listOf(snapshot("ap0", "192.168.50.1"))
        )

        assertNotEquals(first?.fingerprint, rotated?.fingerprint)
    }

    private fun snapshot(
        name: String,
        address: String,
        isUp: Boolean = true,
        supportsMulticast: Boolean = true
    ): AndroidLanInterfaceSnapshot = AndroidLanInterfaceSnapshot(
        name = name,
        isUp = isUp,
        isLoopback = false,
        isPointToPoint = false,
        isVirtual = false,
        supportsMulticast = supportsMulticast,
        addresses = listOf(LanInterfaceAddress(InetAddress.getByName(address), 24))
    )
}
