@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.transport.lan.interop.p2pkit_lan_endpoint_numeric_equal
import dev.p2pkit.transport.lan.interop.p2pkit_lan_numeric_equal
import dev.p2pkit.transport.lan.interop.p2pkit_nw_lan_path_is_allowed
import dev.p2pkit.transport.lan.interop.p2pkit_nw_restrict_lan_parameters
import kotlinx.cinterop.UByteVar
import kotlinx.cinterop.alloc
import kotlinx.cinterop.convert
import kotlinx.cinterop.memScoped
import kotlinx.cinterop.ptr
import kotlinx.cinterop.reinterpret
import kotlinx.cinterop.set
import kotlinx.cinterop.sizeOf
import platform.Network.nw_endpoint_create_address
import platform.Network.nw_endpoint_create_bonjour_service
import platform.Network.nw_endpoint_create_host
import platform.posix.AF_INET
import platform.posix.AF_INET6
import platform.posix.memset
import platform.posix.sockaddr_in
import platform.posix.sockaddr_in6
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** Native helper contracts only; real interface binding/path changes require separate platform qualification. */
class AppleOrganizationLanInteropTest {
    @Test
    fun numericComparisonAcceptsEquivalentIpv6ButNeverHostnamesOrAmbiguousIpv4() {
        assertTrue(p2pkit_lan_numeric_equal("fd12:3456::1", "fd12:3456:0:0:0:0:0:1"))
        assertTrue(p2pkit_lan_numeric_equal("192.168.20.1", "192.168.20.1"))
        assertFalse(p2pkit_lan_numeric_equal("192.168.20.1", "192.168.20.2"))
        assertFalse(p2pkit_lan_numeric_equal("0192.168.20.1", "192.168.20.1"))
        assertFalse(p2pkit_lan_numeric_equal("192.168.020.1", "192.168.20.1"))
        assertFalse(p2pkit_lan_numeric_equal("127.1", "127.0.0.1"))
        assertFalse(p2pkit_lan_numeric_equal("192.168.20.1 ", "192.168.20.1"))
        assertFalse(p2pkit_lan_numeric_equal("fd12::192.168.020.1", "fd12::c0a8:1401"))
        assertFalse(p2pkit_lan_numeric_equal("host.local", "host.local"))
        assertFalse(p2pkit_lan_numeric_equal("fd12:3456::1%en0", "fd12:3456::1"))
        assertFalse(p2pkit_lan_numeric_equal(null, "192.168.20.1"))
    }

    @Test
    fun numericEndpointHandlingAcceptsBothHostAndSockaddrRepresentationsWithoutDns() = memScoped {
        val ipv4 = alloc<sockaddr_in>()
        memset(ipv4.ptr, 0, sizeOf<sockaddr_in>().convert())
        ipv4.sin_len = sizeOf<sockaddr_in>().convert()
        ipv4.sin_family = AF_INET.convert()
        ipv4.sin_port = 0u
        // Populate network-order bytes independently of the parser under test.
        val bytes4 = ipv4.sin_addr.ptr.reinterpret<UByteVar>()
        listOf<UByte>(192u, 168u, 20u, 1u).forEachIndexed { index, octet -> bytes4[index] = octet }
        val address4 = nw_endpoint_create_address(ipv4.ptr.reinterpret())
        assertTrue(p2pkit_lan_endpoint_numeric_equal(address4, "192.168.20.1"))
        assertFalse(p2pkit_lan_endpoint_numeric_equal(address4, "192.168.20.2"))

        val ipv6 = alloc<sockaddr_in6>()
        memset(ipv6.ptr, 0, sizeOf<sockaddr_in6>().convert())
        ipv6.sin6_len = sizeOf<sockaddr_in6>().convert()
        ipv6.sin6_family = AF_INET6.convert()
        ipv6.sin6_port = 0u
        ipv6.sin6_flowinfo = 0u
        ipv6.sin6_scope_id = 0u
        val bytes6 = ipv6.sin6_addr.ptr.reinterpret<UByteVar>()
        bytes6[0] = 0xfdu
        bytes6[1] = 0x12u
        bytes6[2] = 0x34u
        bytes6[3] = 0x56u
        bytes6[15] = 1u
        val address6 = nw_endpoint_create_address(ipv6.ptr.reinterpret())
        assertTrue(p2pkit_lan_endpoint_numeric_equal(address6, "fd12:3456:0:0:0:0:0:1"))
        bytes6[0] = 0xfeu
        bytes6[1] = 0x80u
        bytes6[2] = 0u
        bytes6[3] = 0u
        ipv6.sin6_scope_id = 1u
        val scoped = nw_endpoint_create_address(ipv6.ptr.reinterpret())
        assertFalse(p2pkit_lan_endpoint_numeric_equal(scoped, "fe80::1"))

        val numeric4 = nw_endpoint_create_host("192.168.20.1", "1234")
        val numeric6 = nw_endpoint_create_host("fd12:3456::1", "1234")
        val hostname = nw_endpoint_create_host("host.local", "1234")
        assertTrue(p2pkit_lan_endpoint_numeric_equal(numeric4, "192.168.20.1"))
        assertTrue(p2pkit_lan_endpoint_numeric_equal(numeric6, "fd12:3456::1"))
        assertFalse(p2pkit_lan_endpoint_numeric_equal(hostname, "192.168.20.1"))
        val service = nw_endpoint_create_bonjour_service("rpc-fixture", "_p2pkit2._tcp", "local.")
        assertFalse(p2pkit_lan_endpoint_numeric_equal(service, "192.168.20.1"))
        assertFalse(p2pkit_lan_endpoint_numeric_equal(null, "192.168.20.1"))
    }

    @Test
    fun missingNativeConnectionOrPathFailsClosedBeforeAnyEndpointApproval() {
        var endpointChecks = 0
        assertFalse(p2pkit_nw_lan_path_is_allowed(null, "en0", "192.168.20.1") {
            endpointChecks++
            true
        })
        assertEquals(0, endpointChecks)
        assertFalse(p2pkit_nw_restrict_lan_parameters(null, null, "en0", "192.168.20.1", "0"))
    }
}
