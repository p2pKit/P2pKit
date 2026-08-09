package dev.p2pkit.transport.lan

import java.net.Inet6Address
import java.net.InetAddress
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Pins the Android copy of the JVM/Android discovery-host contract. */
class HostSelectorTest {
    private fun ipv4(value: String): InetAddress = InetAddress.getByName(value)
    private fun ipv6(value: String): InetAddress = InetAddress.getByName(value)

    private fun scopedIpv6(literal: String, scopeId: Int): Inet6Address =
        Inet6Address.getByAddress(null, InetAddress.getByName(literal).address, scopeId)

    @Test
    fun emptyCandidatesReturnsNull() {
        assertNull(selectRoutableHost(emptyList()))
    }

    @Test
    fun routableIpv4IsPreferredOverIpv6AndResolverOrderIsStable() {
        assertEquals(
            "10.0.0.5",
            selectRoutableHost(
                listOf(ipv6("2001:db8::1"), ipv4("10.0.0.5"), ipv4("192.168.1.20"))
            )
        )
    }

    @Test
    fun nonLinkLocalIpv6IsAcceptedWhenNoIpv4() {
        val address = ipv6("2001:db8::1")
        assertEquals(address.hostAddress, selectRoutableHost(listOf(address)))
    }

    @Test
    fun unscopedIpv6LinkLocalIsRejected() {
        assertNull(selectRoutableHost(listOf(ipv6("fe80::1"))))
    }

    @Test
    fun scopedIpv6LinkLocalIsAcceptedAndScopePreserved() {
        val address = scopedIpv6("fe80::1", 5)
        val selected = selectRoutableHost(listOf(address))
        assertNotNull(selected)
        assertEquals(address.hostAddress, selected)
        assertTrue("%" in selected)
    }

    @Test
    fun mixedUnscopedLinkLocalAndGlobalIpv6PicksGlobal() {
        val global = ipv6("2001:db8::42")
        assertEquals(
            global.hostAddress,
            selectRoutableHost(listOf(ipv6("fe80::1"), global))
        )
    }

    @Test
    fun ipv4LinkLocalIsAccepted() {
        assertEquals("169.254.10.20", selectRoutableHost(listOf(ipv4("169.254.10.20"))))
    }

    @Test
    fun loopbackAndWildcardAddressesAreRejected() {
        assertNull(
            selectRoutableHost(
                listOf(ipv4("127.0.0.1"), ipv6("::1"), ipv4("0.0.0.0"), ipv6("::"))
            )
        )
    }

    @Test
    fun loopbackPlusIpv4PicksIpv4() {
        assertEquals(
            "192.168.1.20",
            selectRoutableHost(listOf(ipv4("127.0.0.1"), ipv4("192.168.1.20")))
        )
    }

    @Test
    fun ipv4IsPreferredOverScopedIpv6() {
        assertEquals(
            "10.0.0.5",
            selectRoutableHost(listOf(scopedIpv6("fe80::1", 5), ipv4("10.0.0.5")))
        )
    }

    @Test
    fun interfaceAwareSelectionRejectsOffSubnetAndRetainsLocalCandidates() {
        val selected = selectRoutableHosts(
            candidates = listOf(
                ipv4("203.0.113.7"),
                ipv4("192.168.50.20"),
                ipv4("192.168.50.21")
            ),
            localAddresses = listOf(LanInterfaceAddress(ipv4("192.168.50.2"), 24))
        )

        assertEquals(listOf("192.168.50.20", "192.168.50.21"), selected)
    }

    @Test
    fun interfaceAwareSelectionReturnsEmptyWhenAllClaimsAreOffSubnet() {
        assertTrue(
            selectRoutableHosts(
                candidates = listOf(ipv4("10.0.0.8"), ipv4("203.0.113.9")),
                localAddresses = listOf(LanInterfaceAddress(ipv4("192.168.1.5"), 24))
            ).isEmpty()
        )
    }

    @Test
    fun unusableInterfacePrefixesDoNotRejectEveryCandidate() {
        assertEquals(
            listOf("10.0.0.8"),
            selectRoutableHosts(
                candidates = listOf(ipv4("10.0.0.8")),
                localAddresses = listOf(LanInterfaceAddress(ipv4("192.168.1.5"), 0))
            )
        )
    }

    @Test
    fun candidateFanOutIsBoundedAndDeduplicated() {
        val candidates = buildList {
            add(ipv4("10.0.0.10"))
            add(ipv4("10.0.0.10"))
            repeat(20) { add(ipv4("10.0.0.${it + 20}")) }
        }

        val selected = selectRoutableHosts(candidates)
        assertEquals(LanConstants.MAX_DIAL_CANDIDATES, selected.size)
        assertEquals(selected.distinct(), selected)
    }
}
