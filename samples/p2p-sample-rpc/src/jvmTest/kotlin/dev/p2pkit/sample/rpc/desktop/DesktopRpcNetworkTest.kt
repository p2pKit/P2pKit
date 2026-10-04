package dev.p2pkit.sample.rpc.desktop

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class DesktopRpcNetworkTest {
    @Test
    fun observedIpv4PrefixProducesCanonicalNetworkNotHostBits() {
        assertEquals("192.168.14.0/24", desktopRpcSubnet("192.168.14.137", 24))
        assertEquals("172.16.0.0/12", desktopRpcSubnet("172.29.253.255", 12))
        assertEquals("10.128.0.0/9", desktopRpcSubnet("10.255.255.255", 9))
        assertEquals("10.1.2.3/32", desktopRpcSubnet("10.1.2.3", 32))
        assertEquals("0.0.0.0/0", desktopRpcSubnet("10.1.2.3", 0))
    }

    @Test
    fun observedAddressParsingRejectsDnsAmbiguousAndNonNumericSpellings() {
        for (address in listOf("example.local", "010.1.2.3", "10.1.2.256", "10.1.2", "10.1.2.3%en0", "10.1.2.-3")) {
            assertFailsWith<IllegalArgumentException> { desktopRpcSubnet(address, 24) }
        }
        assertFailsWith<IllegalArgumentException> { desktopRpcSubnet("10.1.2.3", -1) }
        assertFailsWith<IllegalArgumentException> { desktopRpcSubnet("10.1.2.3", 33) }
    }

    @Test
    fun settingsPreserveExplicitPolicyAndCanonicalPort() {
        val settings = desktopRpcSettings("192.168.14.0/24, 10.0.0.0/8", "en0", "192.168.14.2", "48123")
        assertEquals("en0", settings.interfaceName)
        assertEquals("192.168.14.2", settings.localAddress)
        assertEquals(48123, settings.port)
        assertEquals("192.168.14.0/24, 10.0.0.0/8", settings.subnets)
    }

    @Test
    fun settingsRejectUnsafeAddressesInterfacesAndSubnets() {
        for (name in listOf("lo0", "utun0", "bridge0", "awdl0", "vmnet0", "docker0", "en0;other")) {
            assertFailsWith<IllegalArgumentException> {
                desktopRpcSettings("192.168.14.0/24", name, "192.168.14.2", "48123")
            }
        }
        for (subnet in listOf("0.0.0.0/0", "8.8.8.0/24", "192.168.14.1/24", "", "192.168.14.0/24,")) {
            assertFailsWith<IllegalArgumentException> {
                desktopRpcSettings(subnet, "en0", "192.168.14.2", "48123")
            }
        }
        for (address in listOf("127.0.0.1", "8.8.8.8", "192.168.15.2", "desktop.local", "192.168.014.2")) {
            assertFailsWith<IllegalArgumentException> {
                desktopRpcSettings("192.168.14.0/24", "en0", address, "48123")
            }
        }
    }

    @Test
    fun settingsRejectOversizedOrAmbiguousInputRatherThanNormalizingIt() {
        for (port in listOf("0", "22", "1023", "65536", "048123", "+48123", " 48123", "48123\n")) {
            assertFailsWith<IllegalArgumentException> {
                desktopRpcSettings("192.168.14.0/24", "en0", "192.168.14.2", port)
            }
        }
        assertFailsWith<IllegalArgumentException> {
            desktopRpcSettings("a".repeat(513), "en0", "192.168.14.2", "48123")
        }
        assertFailsWith<IllegalArgumentException> {
            desktopRpcSettings("192.168.14.0/24", "e".repeat(33), "192.168.14.2", "48123")
        }
    }
}
