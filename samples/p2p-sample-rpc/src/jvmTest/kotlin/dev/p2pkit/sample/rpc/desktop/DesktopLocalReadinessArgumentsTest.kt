package dev.p2pkit.sample.rpc.desktop

import java.nio.file.Path
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNotEquals
import kotlin.test.assertTrue

class DesktopLocalReadinessArgumentsTest {
    // Lexical fixture only: no directory is created or inspected.
    private val ownedParent = Path.of("rpc-readiness-fixture").toAbsolutePath().normalize()

    private fun nonNormalizedParent(): String {
        val path = ownedParent.resolve("child").resolve("..").resolve("other")
        assertTrue(path.isAbsolute)
        assertNotEquals(path.normalize(), path)
        return path.toString()
    }

    private fun args() = arrayOf("--approved-local-host", "en0", "192.168.14.2",
        "192.168.14.0/24", "48123", ownedParent.toString())

    @Test fun advertisingCheckRequiresSeparateExplicitAuthorizationAndAnAbsoluteOwnedParent() {
        assertEquals(ownedParent.toString(), parseDesktopAdvertisingReadinessArguments(
            arrayOf("--approved-local-advertising", ownedParent.toString())).toString())
        for (arguments in listOf(emptyArray(), arrayOf("--approved-local-host", ownedParent.toString()),
                arrayOf("--approved-local-application", ownedParent.toString()),
                arrayOf("--approved-local-advertising", "relative"),
                arrayOf("--approved-local-advertising", nonNormalizedParent()),
                arrayOf("--approved-local-advertising", ownedParent.toString(), "extra"))) {
            assertFailsWith<IllegalArgumentException> { parseDesktopAdvertisingReadinessArguments(arguments) }
        }
    }

    @Test fun explicitApprovalAndAllNumericPolicyValuesAreRequiredBeforeAllocation() {
        val selected = parseDesktopLocalReadinessArguments(args())
        assertEquals("en0", selected.settings.interfaceName)
        assertEquals("192.168.14.2", selected.settings.localAddress)
        assertEquals(48123, selected.settings.port)
        assertEquals(ownedParent, selected.ownedParent)
        assertFailsWith<IllegalArgumentException> { parseDesktopLocalReadinessArguments(args().drop(1).toTypedArray()) }
        assertFailsWith<IllegalArgumentException> {
            parseDesktopLocalReadinessArguments(args().also { it[0] = "--auto" })
        }
    }
    @Test fun prohibitedInterfaceAddressOrRelativeParentCannotSelectAnAlternatePath() {
        for ((index, value) in listOf(1 to "utun0", 2 to "example.local", 3 to "0.0.0.0/0", 4 to "0",
            5 to "relative", 5 to nonNormalizedParent())) {
            assertFailsWith<IllegalArgumentException> {
                parseDesktopLocalReadinessArguments(args().also { it[index] = value })
            }
        }
    }
}
