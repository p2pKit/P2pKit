package dev.p2pkit.sample.desktop.ui

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs

class ManualEndpointTest {
    @Test
    fun parsesDnsAndIpv4Endpoints() {
        assertEquals(
            ManualEndpoint("peer.local", 9000),
            assertIs<ManualEndpointResult.Valid>(parseManualEndpoint("peer.local:9000")).endpoint
        )
        assertEquals(
            ManualEndpoint("192.168.1.23", 65535),
            assertIs<ManualEndpointResult.Valid>(parseManualEndpoint("192.168.1.23:65535")).endpoint
        )
    }

    @Test
    fun parsesBracketedAndUnbracketedIpv6EndpointsAtLastColon() {
        assertEquals(
            ManualEndpoint("fe80::1", 9000),
            assertIs<ManualEndpointResult.Valid>(parseManualEndpoint("[fe80::1]:9000")).endpoint
        )
        assertEquals(
            ManualEndpoint("fe80::abcd", 1234),
            assertIs<ManualEndpointResult.Valid>(parseManualEndpoint("fe80::abcd:1234")).endpoint
        )
        assertEquals(
            ManualEndpoint("fe80::1%en0", 9000),
            assertIs<ManualEndpointResult.Valid>(parseManualEndpoint("[fe80::1%en0]:9000")).endpoint
        )
    }

    @Test
    fun rejectsMissingOrOutOfRangePortsAndInvalidHosts() {
        assertIs<ManualEndpointResult.Invalid>(parseManualEndpoint("peer.local"))
        assertIs<ManualEndpointResult.Invalid>(parseManualEndpoint("peer.local:0"))
        assertIs<ManualEndpointResult.Invalid>(parseManualEndpoint("peer.local:65536"))
        assertIs<ManualEndpointResult.Invalid>(parseManualEndpoint("bad host:9000"))
    }
}
