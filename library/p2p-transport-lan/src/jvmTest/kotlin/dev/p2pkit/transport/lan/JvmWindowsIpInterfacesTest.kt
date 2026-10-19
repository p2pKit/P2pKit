package dev.p2pkit.transport.lan

import java.net.InetAddress
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFails
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class JvmWindowsIpInterfacesTest {
    private val local = InetAddress.getByAddress(byteArrayOf(192.toByte(), 168.toByte(), 40, 2))
    private val peer = InetAddress.getByAddress(byteArrayOf(192.toByte(), 168.toByte(), 40, 3))
    private val policy = OrganizationLan(listOf("192.168.40.0/24"), "ethernet_1", "192.168.40.2")

    private fun row(name: String = "ethernet_1", index: Int = 7) = arrayOf<Any>(
        name, true, false, false, false, true, index, arrayOf(local), intArrayOf(24),
    )
    private fun snapshot(vararg rows: Array<Any>) = arrayOf<Any>(1, rows, arrayOf(local))

    @Test fun completeNativeSnapshotStillRequiresTheSelectedAddressAndRejectsLocalPeers() {
        val result = decodeWindowsIpSocketSnapshot(snapshot(row()))
        assertNotNull(organizationJvmTarget(policy, result.interfaces))
        assertTrue(policy.allowsJvmSocketPath(local, peer, { result }))
        assertFalse(policy.allowsJvmSocketPath(local, local, { result }))
        assertEquals(7, result.interfaceIndices["ethernet_1"])
    }

    @Test fun additionalIpInterfaceStillRefusesEvenWithNoAddresses() {
        val other = row("wan_2", 8).also { it[7] = emptyArray<InetAddress>(); it[8] = intArrayOf() }
        val result = decodeWindowsIpSocketSnapshot(snapshot(row(), other))
        assertEquals(JvmOrganizationLanProblem.CompetingActiveInterfaces,
            organizationJvmSelection(policy, result.interfaces).problem)
        assertFalse(policy.allowsJvmSocketPath(local, peer, { result }))
    }

    @Test fun malformedOrIncompleteSnapshotsCannotBecomeAnEmptyPermissiveTopology() {
        for (invalid in listOf(
            snapshot(), snapshot(row(), row()), snapshot(row(), row("ethernet_2")),
            snapshot(row().also { it[6] = 0 }), snapshot(row().also { it[1] = 1 }),
            snapshot(row().also { it[8] = intArrayOf(33) }),
            snapshot(row()).also { it[2] = emptyArray<InetAddress>() },
            snapshot(row()).also { it[0] = true },
        )) assertFails { decodeWindowsIpSocketSnapshot(invalid) }
    }
}
