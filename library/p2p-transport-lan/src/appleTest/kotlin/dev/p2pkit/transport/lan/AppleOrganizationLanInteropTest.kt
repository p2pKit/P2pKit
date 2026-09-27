@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.transport.lan.interop.p2pkit_lan_numeric_equal
import dev.p2pkit.transport.lan.interop.p2pkit_nw_lan_path_is_allowed
import dev.p2pkit.transport.lan.interop.p2pkit_nw_restrict_lan_parameters
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
        assertFalse(p2pkit_lan_numeric_equal("host.local", "host.local"))
        assertFalse(p2pkit_lan_numeric_equal("fd12:3456::1%en0", "fd12:3456::1"))
        assertFalse(p2pkit_lan_numeric_equal(null, "192.168.20.1"))
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
