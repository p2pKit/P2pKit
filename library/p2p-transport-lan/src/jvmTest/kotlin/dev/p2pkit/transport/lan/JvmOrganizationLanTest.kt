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
}
