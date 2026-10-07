package dev.p2pkit.transport.lan

import java.net.InetAddress
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull

class JvmOrganizationLanTest {
    private val policy = OrganizationLan(listOf("10.0.0.0/8"), "eth0", "10.1.2.3")
    private fun network(name: String, up: Boolean = true): JvmLanInterfaceSnapshot = JvmLanInterfaceSnapshot(
        name, up, false, false, false, true,
        listOf(LanInterfaceAddress(InetAddress.getByAddress(byteArrayOf(10, 1, 2, 3)), 24))
    )

    @Test
    fun singlePhysicalInterfaceWorksWithoutHostnameResolution() {
        assertNotNull(organizationJvmTarget(policy, listOf(network("eth0"))))
    }

    @Test
    fun multihomingTunnelsUnreadableSnapshotsAndStaleInterfacesFailClosed() {
        assertNull(organizationJvmTarget(policy, listOf(network("eth0"), network("eth1"))))
        assertNull(organizationJvmTarget(policy, listOf(network("eth0"), network("tun0"))))
        assertNull(organizationJvmTarget(policy, listOf(network("eth0", false))))
        assertNull(organizationJvmTarget(policy, null))
    }

    @Test
    fun fourActiveLinkLocalOnlyUtunsAreNotSilentlyIgnoredForIpv4Selection() {
        val linkLocal = InetAddress.getByAddress(
            byteArrayOf(0xfe.toByte(), 0x80.toByte(), 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1),
        )
        val systemInterfaces = List(4) { index ->
            network("utun$index").copy(
                isPointToPoint = true,
                addresses = listOf(LanInterfaceAddress(linkLocal, 64)),
            )
        }
        // This is route uncertainty in Java 17, not a claim about the owning Apple service's trust.
        assertNull(organizationJvmTarget(policy, listOf(network("eth0")) + systemInterfaces))
        assertNotNull(
            organizationJvmTarget(policy, listOf(network("eth0")) + systemInterfaces.map { it.copy(isUp = false) }),
        )
    }

    @Test
    fun explicitNameCannotOverrideVirtualPointToPointLoopbackOrMissingAddress() {
        val selected = network("eth0")
        for (invalid in listOf(
            selected.copy(isVirtual = true), selected.copy(isPointToPoint = true),
            selected.copy(isLoopback = true), selected.copy(addresses = emptyList()),
        )) {
            assertNull(organizationJvmTarget(policy, listOf(invalid)))
        }
    }

    @Test
    fun rejectionExplainsTheExactSnapshotWithoutAddressesOrAnAlternateTarget() {
        val selected = network("eth0")
        val cases = listOf(
            null to JvmOrganizationLanProblem.SnapshotUnavailable,
            emptyList<JvmLanInterfaceSnapshot>() to JvmOrganizationLanProblem.SelectedInterfaceNotUnique,
            listOf(selected, selected) to JvmOrganizationLanProblem.SelectedInterfaceNotUnique,
            listOf(selected.copy(isUp = false)) to JvmOrganizationLanProblem.SelectedInterfaceUnsafeOrDown,
            listOf(selected.copy(isVirtual = true)) to JvmOrganizationLanProblem.SelectedInterfaceUnsafeOrDown,
            listOf(selected.copy(isPointToPoint = true)) to JvmOrganizationLanProblem.SelectedInterfaceUnsafeOrDown,
            listOf(selected.copy(isLoopback = true)) to JvmOrganizationLanProblem.SelectedInterfaceUnsafeOrDown,
            listOf(selected.copy(addresses = emptyList())) to JvmOrganizationLanProblem.SelectedAddressUnavailable,
        )
        for ((snapshot, problem) in cases) {
            val result = organizationJvmSelection(policy, snapshot)
            assertNull(result.target)
            assertNull(organizationJvmTarget(policy, snapshot))
            assertEquals(problem, result.problem)
            assertEquals(problem.name, result.failureCode)
            assertEquals(0, result.competingInterfaces)
        }
        val tunnels = List(4) { network("utun$it").copy(isPointToPoint = true, addresses = emptyList()) }
        val result = organizationJvmSelection(policy, listOf(selected) + tunnels)
        assertNull(result.target)
        assertEquals(JvmOrganizationLanProblem.CompetingActiveInterfaces, result.problem)
        assertEquals("CompetingActiveInterfaces:4", result.failureCode)
        assertEquals(4, result.competingInterfaces)
        val allowed = organizationJvmSelection(policy, listOf(selected) + tunnels.map { it.copy(isUp = false) })
        assertNull(allowed.problem)
        assertEquals("eth0", checkNotNull(allowed.target).interfaceName)
        assertEquals(organizationJvmTarget(policy, listOf(selected)), allowed.target)
    }
}
