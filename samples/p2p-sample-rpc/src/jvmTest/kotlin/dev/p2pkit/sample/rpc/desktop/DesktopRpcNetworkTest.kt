package dev.p2pkit.sample.rpc.desktop

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNull
import kotlin.test.assertTrue

class DesktopRpcNetworkTest {
    @Test
    fun competingInterfacesExplainTheExistingTransportBlockWithoutSuggestingABypass() {
        for (count in listOf(1, 6)) {
            val network = DesktopRpcNetwork("en0", "192.168.14.2", "192.168.14.0/24", count)
            val problem = checkNotNull(network.startProblem)
            assertTrue(problem.contains("$count other active non-loopback"))
            assertTrue(problem.contains("Last scan"))
            assertTrue(problem.contains("verified macOS TCP adapter"))
            assertTrue(problem.contains("Do not disable protections"))
            assertTrue(problem.contains("otherwise it will fail closed"))
            assertTrue(problem.contains("not discovery/multicast proof"))
        }
    }

    @Test
    fun singleInterfaceSuggestionIsNotAConnectivityPassAndInvalidCountsAreRejected() {
        val network = DesktopRpcNetwork("en0", "192.168.14.2", "192.168.14.0/24")
        assertNull(network.startProblem)
        assertEquals("en0 — 192.168.14.2 (192.168.14.0/24)", network.toString())
        assertFailsWith<IllegalArgumentException> {
            DesktopRpcNetwork("en0", "192.168.14.2", "192.168.14.0/24", -1)
        }
    }

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
    @Test
    fun automaticSelectionRequiresExactlyOneEligibleObservationAndUsesAnOsAssignedPort() {
        val network = DesktopRpcNetwork("en0", "192.168.14.2", "192.168.14.0/24", 6)
        val settings = desktopRpcAutomaticSettings(listOf(network))
        assertEquals(network.interfaceName, settings.interfaceName)
        assertEquals(network.subnet, settings.subnets)
        assertEquals(network.address, settings.localAddress)
        assertEquals(0, settings.port)
        val missing = assertFailsWith<DesktopRpcNetworkUnavailable> { desktopRpcAutomaticSettings(emptyList()) }
        assertEquals("No eligible private IPv4 LAN was found. Check network availability; no role started.",
            desktopRpcFailureText(missing))
        val ambiguous = assertFailsWith<DesktopRpcNetworkUnavailable> {
            desktopRpcAutomaticSettings(listOf(network, network))
        }
        assertEquals("More than one eligible private IPv4 LAN was found; automatic selection is ambiguous. " +
            "No role started.", desktopRpcFailureText(ambiguous))
        assertFailsWith<IllegalStateException> { desktopRpcAutomaticSettings(listOf(network, network)) }
        assertFailsWith<IllegalStateException> {
            desktopRpcAutomaticSettings(listOf(network, network.copy(address = "192.168.14.3")))
        }
        assertFailsWith<IllegalArgumentException> {
            desktopRpcAutomaticSettings(listOf(network.copy(interfaceName = "utun0")))
        }
    }

    @Test
    fun discoveryPreflightDoesNotTreatNativeTcpOrASingleSuggestionAsMulticastScope() {
        val network = DesktopRpcNetwork("en0", "192.168.14.2", "192.168.14.0/24")
        assertEquals(0, desktopRpcDiscoverySettings(listOf(network)).port)
        assertTrue(desktopRpcDiscoveryNetworkSummary(listOf(network)).contains("not yet verified"))
        for (count in listOf(1, 6)) {
            val blocked = listOf(network.copy(otherActiveInterfaces = count))
            // The address remains eligible, but that is not sufficient to start this discovery adapter.
            assertEquals(network.address, desktopRpcAutomaticSettings(blocked).localAddress)
            val failure = assertFailsWith<DesktopRpcDiscoveryUnavailable> { desktopRpcDiscoverySettings(blocked) }
            assertEquals(count, failure.competingInterfaces)
            val message = desktopRpcFailureText(failure)
            assertTrue(message.contains("$count other active"))
            assertTrue(message.contains("source binding is not multicast scope"))
            assertTrue(message.contains("Keep network and security protections enabled"))
            assertTrue(message.contains("verified scoped Bonjour build is required"))
            assertEquals("Last read-only scan: $message", desktopRpcDiscoveryNetworkSummary(blocked))
        }
        assertFailsWith<DesktopRpcNetworkUnavailable> { desktopRpcDiscoverySettings(emptyList()) }
        assertFailsWith<DesktopRpcNetworkUnavailable> { desktopRpcDiscoverySettings(listOf(network, network)) }
        assertFailsWith<IllegalArgumentException> { DesktopRpcDiscoveryUnavailable(0) }
    }
    @Test
    fun configuredBonjourAllowsOnlyAnAttemptNotAClaimOfVerifiedNetworking() {
        val network = DesktopRpcNetwork("en0", "192.168.14.2", "192.168.14.0/24", otherActiveInterfaces = 6)
        assertEquals(network.address, desktopRpcDiscoverySettings(listOf(network), scopedBonjour = true).localAddress)
        assertTrue(desktopRpcDiscoveryNetworkSummary(listOf(network), scopedBonjour = true)
            .contains("not yet verified"))
        assertFailsWith<DesktopRpcDiscoveryUnavailable> {
            desktopRpcDiscoverySettings(listOf(network), scopedBonjour = false)
        }
        assertFailsWith<DesktopRpcNetworkUnavailable> { desktopRpcDiscoverySettings(emptyList(), scopedBonjour = true) }
        assertFailsWith<DesktopRpcNetworkUnavailable> {
            desktopRpcDiscoverySettings(listOf(network, network), scopedBonjour = true)
        }
    }

}
