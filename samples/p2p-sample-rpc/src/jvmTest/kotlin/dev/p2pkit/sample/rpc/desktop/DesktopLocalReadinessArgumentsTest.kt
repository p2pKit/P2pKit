package dev.p2pkit.sample.rpc.desktop

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class DesktopLocalReadinessArgumentsTest {
    private fun args() = arrayOf("--approved-local-host", "en0", "192.168.14.2",
        "192.168.14.0/24", "48123", "/private-owned")

    @Test fun applicationCheckRequiresSeparateExplicitAuthorizationAndAnAbsoluteOwnedParent() {
        assertEquals("/private-owned", parseDesktopApplicationReadinessArguments(
            arrayOf("--approved-local-application", "/private-owned")).toString())
        for (arguments in listOf(emptyArray(), arrayOf("--approved-local-host", "/private-owned"),
                arrayOf("--approved-local-application", "relative"),
                arrayOf("--approved-local-application", "/tmp/../other"),
                arrayOf("--approved-local-application", "/private-owned", "extra"))) {
            assertFailsWith<IllegalArgumentException> { parseDesktopApplicationReadinessArguments(arguments) }
        }
    }

    @Test fun explicitApprovalAndAllNumericPolicyValuesAreRequiredBeforeAllocation() {
        val selected = parseDesktopLocalReadinessArguments(args())
        assertEquals("en0", selected.settings.interfaceName)
        assertEquals("192.168.14.2", selected.settings.localAddress)
        assertEquals(48123, selected.settings.port)
        assertFailsWith<IllegalArgumentException> { parseDesktopLocalReadinessArguments(args().drop(1).toTypedArray()) }
        assertFailsWith<IllegalArgumentException> {
            parseDesktopLocalReadinessArguments(args().also { it[0] = "--auto" })
        }
    }
    @Test fun prohibitedInterfaceAddressOrRelativeParentCannotSelectAnAlternatePath() {
        for ((index, value) in listOf(1 to "utun0", 2 to "example.local", 3 to "0.0.0.0/0", 4 to "0",
            5 to "relative", 5 to "/tmp/../other")) {
            assertFailsWith<IllegalArgumentException> {
                parseDesktopLocalReadinessArguments(args().also { it[index] = value })
            }
        }
    }
}
