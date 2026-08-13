package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.provisioning.ManualPeerRegistrar
import dev.p2pkit.core.provisioning.NetworkProvisioningConfig
import dev.p2pkit.core.provisioning.ProvisioningContext
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

@OptIn(ExperimentalP2pApi::class)
class AppleHostAddressSnapshotTest {

    @Test
    fun filtersUnsafeAddressesAndUnrelatedInterfaces() {
        val ordinary = ipv4(192, 168, 1, 20)
        val rejected = listOf(
            ordinary.copy(interfaceIsUp = false),
            ordinary.copy(interfaceIsRunning = false),
            ordinary.copy(interfaceIsLoopback = true),
            ordinary.copy(interfaceIsPointToPoint = true),
            ordinary.copy(interfaceSupportsMulticast = false),
            ordinary.copy(ipVersion = 5),
            ordinary.copy(addressBytes = byteArrayOf(1, 2, 3)),
            ipv4(0, 0, 0, 0),
            ipv4(0, 10, 20, 30),
            ipv4(127, 0, 0, 1),
            ipv4(224, 0, 0, 251),
            ipv4(239, 255, 255, 250),
            ipv4(255, 255, 255, 255),
            ordinary.copy(addressIsInterfaceBroadcast = true),
            ipv6(0, 0, 0, 0, 0, 0, 0, 0),
            ipv6(0, 0, 0, 0, 0, 0, 0, 1),
            ipv6(0xFF02, 0, 0, 0, 0, 0, 0, 0x00FB),
            ipv6(0xFEC0, 0, 0, 0, 0, 0, 0, 1),
            ipv6(0, 0, 0, 0, 0, 0xFFFF, 0xC0A8, 0x0114),
            ipv6(0x2001, 0x0DB8, 0, 0, 0, 0, 0, 1)
                .copy(interfaceIsPointToPoint = true)
        )

        assertEquals(emptyList(), selectAppleHostAddresses(rejected))
    }

    @Test
    fun ordersFamiliesAndPreservesOnlyValidatedIpv6LinkLocalScopes() {
        val candidates = listOf(
            ipv6(0xFE80, 0, 0, 0, 0, 0, 0, 1).copy(
                interfaceName = "en0",
                interfaceIndex = 14u,
                addressScopeId = 14u
            ),
            ipv6(0xFD00, 0, 0, 0, 0, 0, 0, 1),
            ipv4(169, 254, 10, 20),
            ipv4(192, 168, 1, 20),
            ipv6(0x2001, 0x0DB8, 1, 2, 0, 0, 0, 1).copy(
                interfaceIndex = 14u,
                addressScopeId = 14u
            ),
            ipv4(10, 0, 0, 7),
            ipv4(192, 168, 1, 20),
            ipv6(0xFE80, 0, 0, 0, 0, 0, 0, 2).copy(
                interfaceName = "en0",
                interfaceIndex = 14u,
                addressScopeId = 15u
            ),
            ipv6(0xFE80, 0, 0, 0, 0, 0, 0, 3).copy(
                interfaceName = "bad%scope",
                interfaceIndex = 14u
            ),
            ipv6(0xFE80, 0, 0, 0, 0, 0, 0, 4).copy(
                interfaceName = "interface-name-too-long",
                interfaceIndex = 14u
            ),
            ipv6(0xFE80, 0, 0, 0, 0, 0, 0, 5).copy(interfaceIndex = 0u),
            ipv6(0xFE80, 0, 0, 0, 0, 0, 0, 6).copy(
                interfaceName = "en0",
                interfaceIndex = 14u,
                addressScopeId = 0u
            )
        )

        assertEquals(
            listOf(
                "10.0.0.7",
                "192.168.1.20",
                "169.254.10.20",
                "2001:db8:1:2::1",
                "fd00::1",
                "fe80::1%en0",
                "fe80::6%en0"
            ),
            selectAppleHostAddresses(candidates)
        )
    }

    @Test
    fun formatsIpv6WithCanonicalZeroCompression() {
        val cases = listOf(
            ipv6(0x2001, 0x0DB8, 1, 2, 3, 4, 5, 6) to "2001:db8:1:2:3:4:5:6",
            ipv6(0, 0, 1, 2, 3, 4, 5, 6) to "::1:2:3:4:5:6",
            ipv6(0x2001, 0x0DB8, 1, 2, 0, 0, 0, 0) to "2001:db8:1:2::",
            ipv6(0x2001, 0, 0, 1, 0, 0, 1, 1) to "2001::1:0:0:1:1"
        )

        cases.forEach { (candidate, expected) ->
            assertEquals(listOf(expected), selectAppleHostAddresses(listOf(candidate)))
        }
    }

    @Test
    fun managerTakesFreshStableAddressSnapshotForEachManualInfoCall() = runBlocking<Unit> {
        val mutableAddress = byteArrayOf(192.toByte(), 168.toByte(), 1, 20)
        val candidate = eligibleCandidate(addressBytes = mutableAddress, ipVersion = 4)
        var scans = 0
        val manager = IosManualNetworkProvisioningManager(
            ctx = provisioningContext(),
            addressScanner = AppleInterfaceAddressScanner {
                scans++
                AppleInterfaceAddressSnapshot(listOf(candidate))
            }
        )

        try {
            val first = manager.getManualConnectionInfo()
            mutableAddress[3] = 99
            val second = manager.getManualConnectionInfo()

            assertEquals(listOf("192.168.1.20"), first?.hostAddresses)
            assertEquals(listOf("192.168.1.99"), second?.hostAddresses)
            assertEquals(2, scans)
            assertEquals(42_000, first?.port)
            assertEquals(AppId("apple-address-snapshot"), first?.appId)
        } finally {
            manager.close()
        }
    }

    @Test
    fun nativeSnapshotOwnsItsValuesAndSelectionIsOrderIndependent() {
        val snapshot = collectAppleInterfaceAddressSnapshot()

        assertNull(snapshot.enumerationErrorCode)
        snapshot.candidates.forEach { candidate ->
            assertTrue(candidate.ipVersion == 4 || candidate.ipVersion == 6)
            assertEquals(if (candidate.ipVersion == 4) 4 else 16, candidate.addressBytes.size)
        }
        assertEquals(
            selectAppleHostAddresses(snapshot.candidates),
            selectAppleHostAddresses(snapshot.candidates.reversed())
        )
    }
}

private fun ipv4(a: Int, b: Int, c: Int, d: Int): AppleInterfaceAddressCandidate =
    eligibleCandidate(
        addressBytes = byteArrayOf(a.toByte(), b.toByte(), c.toByte(), d.toByte()),
        ipVersion = 4
    )

private fun ipv6(vararg groups: Int): AppleInterfaceAddressCandidate {
    require(groups.size == 8)
    val bytes = ByteArray(16)
    groups.forEachIndexed { index, group ->
        require(group in 0..0xFFFF)
        bytes[index * 2] = (group ushr 8).toByte()
        bytes[index * 2 + 1] = group.toByte()
    }
    return eligibleCandidate(addressBytes = bytes, ipVersion = 6)
}

private fun eligibleCandidate(
    addressBytes: ByteArray,
    ipVersion: Int
): AppleInterfaceAddressCandidate = AppleInterfaceAddressCandidate(
    addressBytes = addressBytes,
    ipVersion = ipVersion,
    interfaceName = "en0",
    interfaceIndex = 14u,
    addressScopeId = 0u,
    interfaceIsUp = true,
    interfaceIsRunning = true,
    interfaceIsLoopback = false,
    interfaceIsPointToPoint = false,
    interfaceSupportsMulticast = true,
    addressIsInterfaceBroadcast = false
)

@OptIn(ExperimentalP2pApi::class)
private fun provisioningContext(): ProvisioningContext = ProvisioningContext(
    appId = AppId("apple-address-snapshot"),
    localPeerId = PeerId("local"),
    localDeviceName = "iPhone",
    config = NetworkProvisioningConfig(),
    logger = P2pLogger.NoOp,
    lanTcpPort = { 42_000 },
    manualPeerRegistrar = SnapshotRejectingRegistrar
)

@OptIn(ExperimentalP2pApi::class)
private object SnapshotRejectingRegistrar : ManualPeerRegistrar {
    override fun registerManualPeer(
        host: String,
        port: Int,
        kind: TransportKind,
        deviceName: String?,
        expectedFingerprint: PeerFingerprint?
    ): Peer = error("not used")
}
