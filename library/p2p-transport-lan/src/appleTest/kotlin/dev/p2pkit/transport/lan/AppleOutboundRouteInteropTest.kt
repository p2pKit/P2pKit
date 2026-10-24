@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.transport.lan.interop.p2pkit_nw_create_plain_tcp_parameters
import kotlinx.cinterop.ByteVar
import kotlinx.cinterop.UByteVar
import kotlinx.cinterop.alloc
import kotlinx.cinterop.convert
import kotlinx.cinterop.memScoped
import kotlinx.cinterop.pointed
import kotlinx.cinterop.ptr
import kotlinx.cinterop.readBytes
import kotlinx.cinterop.reinterpret
import kotlinx.cinterop.set
import kotlinx.cinterop.sizeOf
import platform.Network.nw_connection_cancel
import platform.Network.nw_connection_copy_endpoint
import platform.Network.nw_endpoint_create_address
import platform.Network.nw_endpoint_create_bonjour_service
import platform.Network.nw_endpoint_create_host
import platform.Network.nw_endpoint_get_address
import platform.Network.nw_endpoint_get_port
import platform.darwin.NXSwapHostShortToBig
import platform.posix.AF_INET6
import platform.posix.memset
import platform.posix.sockaddr_in6
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull

class AppleOutboundRouteInteropTest {
    @Test
    fun connectionHelperRetainsItsNumericConfigurationAfterTemporaryEndpointRetirement() {
        val value = LanTcpEndpoint(assertNotNull(LanNumericAddress.copyOf(byteArrayOf(127, 0, 0, 1))), 40_123)
        assertNull(value.appleConnection(null))
        val connection = assertNotNull(value.appleConnection(p2pkit_nw_create_plain_tcp_parameters()))
        try {
            // Configured endpoint readback is appropriate only for this constructor/ownership control.
            // It must NEVER be used as evidence that this unstarted connection reached a destination.
            assertEquals(value, appleNumericEndpoint(nw_connection_copy_endpoint(connection)))
            assertNull(appleConnectedEndpoint(connection))
        } finally {
            nw_connection_cancel(connection)
        }
    }

    @Test
    fun ipv4RoundTripUsesNumericSockaddrAndExactPort() {
        val bytes = byteArrayOf(127, 0, 0, 1)
        val value = LanTcpEndpoint(assertNotNull(LanNumericAddress.copyOf(bytes)), 40_123)
        val endpoint = assertNotNull(value.appleEndpoint())
        assertEquals(40_123, nw_endpoint_get_port(endpoint).toInt())
        val copied = assertNotNull(appleNumericEndpoint(endpoint))
        assertEquals(value, copied)
        assertContentEquals(bytes, copied.address.copyBytes())
        assertEquals(0, copied.address.scopeId)
    }

    @Test
    fun effectiveSockaddrIpv6ScopeAndPortSurviveCopyAndReconstruction() = memScoped {
        val native = alloc<sockaddr_in6>()
        memset(native.ptr, 0, sizeOf<sockaddr_in6>().convert())
        native.sin6_len = sizeOf<sockaddr_in6>().convert()
        native.sin6_family = AF_INET6.convert()
        native.sin6_port = NXSwapHostShortToBig(54_321u)
        native.sin6_scope_id = 17u
        val bytes = native.sin6_addr.ptr.reinterpret<UByteVar>()
        bytes[0] = 0xfeu
        bytes[1] = 0x80u
        bytes[15] = 9u
        val endpoint = assertNotNull(nw_endpoint_create_address(native.ptr.reinterpret()))
        val copied = assertNotNull(appleNumericEndpoint(endpoint))
        assertEquals(54_321, copied.port)
        assertEquals(17, copied.address.scopeId)
        val rebuilt = assertNotNull(copied.appleEndpoint())
        val rebuiltAddress = assertNotNull(nw_endpoint_get_address(rebuilt)).reinterpret<sockaddr_in6>().pointed
        assertEquals(17u, rebuiltAddress.sin6_scope_id)
        assertEquals(54_321, nw_endpoint_get_port(rebuilt).toInt())
        assertContentEquals(
            native.sin6_addr.ptr.reinterpret<ByteVar>().readBytes(16),
            rebuiltAddress.sin6_addr.ptr.reinterpret<ByteVar>().readBytes(16)
        )
        assertEquals(copied, appleNumericEndpoint(rebuilt))
    }

    @Test
    fun hostnameBonjourMissingPortAndUnscopedLinkLocalAreNotRoutingEvidence() {
        assertNull(appleNumericEndpoint(nw_endpoint_create_host("peer.local", "1234")))
        assertNull(appleNumericEndpoint(nw_endpoint_create_bonjour_service("peer", "_p2pkit2._tcp", "local.")))
        assertNull(appleNumericEndpoint(nw_endpoint_create_host("127.0.0.1", "0")))
        assertNull(appleNumericEndpoint(nw_endpoint_create_host("fe80::1", "1234")))
        assertNull(appleNumericEndpoint(null))
        assertNull(appleConnectedEndpoint(null))
        val scoped = assertNotNull(appleNumericEndpoint(nw_endpoint_create_host("fe80::1%17", "1234")))
        assertEquals(17, scoped.address.scopeId)
        assertEquals(1234, scoped.port)
    }
}
