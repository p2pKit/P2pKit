package dev.p2pkit.transport.lan

import kotlin.test.Test
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class OrganizationLanTest {
    private val policy = OrganizationLan(listOf("10.0.0.0/8", "fd12:3456::/32"), "en0", "10.1.2.3")

    @Test
    fun routedPrivateVlansAndCanonicalIpv6AreAllowed() {
        assertTrue(policy.allows("10.9.8.7"))
        assertTrue(policy.allows("fd12:3456::abcd"))
        assertTrue(policy.allows("fd12:3456:0:0:0:0:0:abcd"))
    }

    @Test
    fun ambiguousPublicTunnelAndHostnameDestinationsFailClosed() {
        listOf("127.0.0.1", "8.8.8.8", "192.168.1.1", "10.01.2.3", "10.1", "example.org",
            "::ffff:10.1.2.3", "fd12:3456::1%en0", "[fd12:3456::1]", "10.1.2.3 ", "10.1.2.3:7",
            "fc00::1", "fd12:3456:::1").forEach { assertFalse(policy.allows(it), it) }
        assertFailsWith<IllegalArgumentException> {
            OrganizationLan(listOf("10.0.0.0/8"), "utun0", "10.1.2.3")
        }
    }

    @Test
    fun nonCanonicalOrNonPrivateSubnetsCannotWidenPolicy() {
        for (cidr in listOf("0.0.0.0/0", "10.0.0.0/7", "10.1.0.1/16", "172.16.0.0/11", "::/0")) {
            assertFailsWith<IllegalArgumentException> { OrganizationLan(listOf(cidr), "en0", "10.1.2.3") }
        }
    }
}
