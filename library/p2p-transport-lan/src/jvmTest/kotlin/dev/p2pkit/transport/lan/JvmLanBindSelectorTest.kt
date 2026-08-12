package dev.p2pkit.transport.lan

import java.net.InetAddress
import java.net.Inet6Address
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotEquals
import kotlin.test.assertNull

/** Deterministic interface-selection contract for JVM/macOS JmDNS binding. */
class JvmLanBindSelectorTest {
    @Test
    fun excludesTunnelAppleSideChannelContainerAndIneligibleInterfaces() {
        val selected = selectJvmLanBindTarget(
            listOf(
                snapshot("lo0", "192.168.1.9", isLoopback = true),
                snapshot("utun4", "10.8.0.2"),
                snapshot("awdl0", "169.254.2.2"),
                snapshot("docker0", "172.17.0.1"),
                snapshot("en9", "192.168.50.9", isUp = false),
                snapshot("en8", "192.168.50.8", supportsMulticast = false),
                snapshot("en0", "192.168.50.2")
            )
        )

        assertEquals("en0", selected?.interfaceName)
        assertEquals("192.168.50.2", selected?.address?.hostAddress)
    }

    @Test
    fun siteLocalIpv4WinsDeterministicallyOverPublicAndLinkLocalAddresses() {
        val selected = selectJvmLanBindTarget(
            listOf(
                snapshot("en2", "169.254.20.2"),
                snapshot("en1", "203.0.113.7"),
                snapshot("en0", "192.168.1.20"),
                snapshot("en3", "10.0.0.4")
            )
        )

        assertEquals("en0", selected?.interfaceName)
        assertEquals("192.168.1.20", selected?.address?.hostAddress)
    }

    @Test
    fun ipv4LinkLocalOnlyDirectCableInterfaceIsSelected() {
        val selected = selectJvmLanBindTarget(
            listOf(snapshot("en7", "169.254.20.2"))
        )

        assertEquals("en7", selected?.interfaceName)
        assertEquals("169.254.20.2", selected?.address?.hostAddress)
    }

    @Test
    fun completeEligibleTopologyParticipatesInFingerprint() {
        val first = selectJvmLanBindTarget(
            listOf(
                snapshot("en0", "192.168.1.20"),
                snapshot("en1", "10.0.0.4")
            )
        )
        val changedSecondary = selectJvmLanBindTarget(
            listOf(
                snapshot("en0", "192.168.1.20"),
                snapshot("en1", "10.0.0.5")
            )
        )

        assertEquals(first?.address, changedSecondary?.address)
        assertNotEquals(first?.fingerprint, changedSecondary?.fingerprint)
    }

    @Test
    fun safeIpv6IsUsedOnlyWhenNoIpv4Exists() {
        val global = InetAddress.getByName("2001:db8::1")
        val scoped = Inet6Address.getByAddress(
            null,
            InetAddress.getByName("fe80::1").address,
            5
        )

        assertEquals(
            global,
            selectJvmLanBindTarget(
                listOf(
                    snapshot("en0", scoped),
                    snapshot("en1", global)
                )
            )?.address
        )
    }

    @Test
    fun scopedIpv6LinkLocalOnlyInterfaceIsSelectedWithScopeIntact() {
        val scoped = Inet6Address.getByAddress(
            null,
            InetAddress.getByName("fe80::2").address,
            7
        )

        val selected = selectJvmLanBindTarget(listOf(snapshot("en7", scoped)))

        assertEquals("en7", selected?.interfaceName)
        assertEquals(scoped, selected?.address)
        assertEquals(scoped.hostAddress, selected?.address?.hostAddress)
    }

    @Test
    fun returnsNullInsteadOfFallingBackToJdkHostnameSelection() {
        assertNull(
            selectJvmLanBindTarget(
                listOf(
                    snapshot("utun0", "10.0.0.2"),
                    snapshot("en0", "127.0.0.1")
                )
            )
        )
    }

    private fun snapshot(
        name: String,
        address: String,
        isUp: Boolean = true,
        isLoopback: Boolean = false,
        supportsMulticast: Boolean = true
    ): JvmLanInterfaceSnapshot = JvmLanInterfaceSnapshot(
        name = name,
        isUp = isUp,
        isLoopback = isLoopback,
        isPointToPoint = false,
        isVirtual = false,
        supportsMulticast = supportsMulticast,
        addresses = listOf(LanInterfaceAddress(InetAddress.getByName(address), 24))
    )

    private fun snapshot(
        name: String,
        address: InetAddress
    ): JvmLanInterfaceSnapshot = JvmLanInterfaceSnapshot(
        name = name,
        isUp = true,
        isLoopback = false,
        isPointToPoint = false,
        isVirtual = false,
        supportsMulticast = true,
        addresses = listOf(LanInterfaceAddress(address, 64))
    )
}
