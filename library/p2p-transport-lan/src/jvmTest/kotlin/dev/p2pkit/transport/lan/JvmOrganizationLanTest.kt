package dev.p2pkit.transport.lan

import java.net.InetAddress
import kotlin.test.Test
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
}
