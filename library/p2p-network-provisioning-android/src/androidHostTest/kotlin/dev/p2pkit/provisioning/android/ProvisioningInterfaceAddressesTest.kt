@file:OptIn(dev.p2pkit.core.ExperimentalP2pApi::class)

package dev.p2pkit.provisioning.android

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.permission.P2pPermission
import dev.p2pkit.core.provisioning.LocalNetworkConfig
import dev.p2pkit.core.provisioning.LocalNetworkResult
import dev.p2pkit.core.provisioning.ManualPeerRegistrar
import dev.p2pkit.core.provisioning.NetworkProvisioningConfig
import dev.p2pkit.core.provisioning.NetworkState
import dev.p2pkit.core.provisioning.ProvisioningContext
import dev.p2pkit.core.provisioning.WifiCredentials
import dev.p2pkit.core.provisioning.WifiSecurityType
import java.net.Inet6Address
import java.net.InetAddress
import java.net.SocketException
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.asCoroutineDispatcher
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class ProvisioningInterfaceAddressesTest {
    @Test
    fun dualStackSelectionDeduplicatesPortableAddressesAndExcludesUnusableIpv6() {
        val global = InetAddress.getByName("2001:db8::77")
        val scopedGlobal = Inet6Address.getByAddress(null, global.address, 7)
        val candidates = listOf(
            "192.0.2.77", "169.254.1.77", "2001:db8::77", "fd00::77", "192.0.2.77",
            "127.0.0.1", "0.0.0.0", "224.0.0.1", "::", "::1", "ff02::1", "fe80::77", "fec0::77"
        ).map(InetAddress::getByName) + scopedGlobal
        assertEquals(
            listOf("192.0.2.77", "169.254.1.77", "2001:db8:0:0:0:0:0:77", "fd00:0:0:0:0:0:0:77"),
            selectProvisioningInterfaceAddresses(candidates)
        )
    }

    @Test
    fun disappearingInterfaceDoesNotLoseHealthySiblingAndCancellationIsNotSwallowed() {
        assertEquals(
            listOf("2001:db8:0:0:0:0:0:77"),
            collectProvisioningInterfaceAddresses(
                interfaces = { sequenceOf("gone", "healthy") },
                addresses = { name ->
                    if (name == "gone") throw SocketException("synthetic vanished NIC")
                    listOf(InetAddress.getByName("2001:db8::77"))
                }
            )
        )
        assertTrue(collectProvisioningInterfaceAddresses<String>(
            interfaces = { throw SocketException("synthetic enumeration unavailable") },
            addresses = { error("not reached") }
        ).isEmpty())
        assertFailsWith<CancellationException> {
            collectProvisioningInterfaceAddresses(
                interfaces = { sequenceOf("cancelled") },
                addresses = { throw CancellationException("synthetic cancellation") }
            )
        }
        assertFailsWith<AssertionError> {
            collectProvisioningInterfaceAddresses<String>(
                interfaces = { throw AssertionError("fatal enumerator failure") },
                addresses = { error("not reached") }
            )
        }
    }

    @Test
    fun manualIpv6WithoutHotspotAndHostedSnapshotsUseTheSameOwnedIoScanner() = runBlocking<Unit> {
        lateinit var scannerThread: Thread
        val executor = Executors.newSingleThreadExecutor { operation ->
            Thread(operation, "provisioning-address-scan-test").also { scannerThread = it }
        }
        val dispatcher = executor.asCoroutineDispatcher()
        val threads = mutableListOf<Thread>()
        val expected = listOf("2001:db8:0:0:0:0:0:77")
        var hotspotStarts = 0
        var closes = 0
        val wifi = object : WifiManagerWrapper {
            override val isLocalOnlyHotspotSupported = true
            override val isSpecifierJoinSupported = true
            override fun requiredRuntimePermission() = P2pPermission.NearbyWifiDevices
            override fun scanInterfaceAddresses(): List<String> {
                threads += Thread.currentThread()
                return collectProvisioningInterfaceAddresses(
                    interfaces = { sequenceOf(Unit) },
                    addresses = { listOf(InetAddress.getByName("2001:db8::77")) }
                )
            }
            override suspend fun startLocalOnlyHotspot(): HotspotStartResult {
                hotspotStarts += 1
                return HotspotStartResult.Started(object : HotspotHandle {
                    override fun getCredentials() = WifiCredentials("synthetic", null, WifiSecurityType.OPEN)
                    override val stopped = MutableSharedFlow<HotspotStopReason>()
                    override fun close() { closes += 1 }
                })
            }
            override suspend fun joinWifiNetwork(credentials: WifiCredentials): JoinResult = error("not used")
        }
        val manager = AndroidNetworkProvisioningManager(
            ProvisioningContext(
                appId = AppId("android-ipv6-manual"),
                localPeerId = PeerId("local"),
                localDeviceName = "synthetic",
                config = NetworkProvisioningConfig(),
                logger = P2pLogger.NoOp,
                lanTcpPort = { 42000 },
                manualPeerRegistrar = object : ManualPeerRegistrar {
                    override fun registerManualPeer(
                        host: String,
                        port: Int,
                        kind: TransportKind,
                        deviceName: String?,
                        expectedFingerprint: PeerFingerprint?
                    ): Peer = error("not used")
                }
            ),
            wifi,
            addressScanDispatcher = dispatcher
        )
        try {
            assertEquals(expected, assertNotNull(manager.getManualConnectionInfo()).hostAddresses)
            assertEquals(0, hotspotStarts, "general IPv6 scanning must not require a hotspot")
            val started = assertIs<LocalNetworkResult.Started>(manager.startLocalNetwork(LocalNetworkConfig()))
            assertEquals(expected, assertNotNull(started.manualConnectionInfo).hostAddresses)
            assertEquals(
                expected,
                assertIs<NetworkState.LocalNetworkHosted>(manager.networkState.value).localIpAddresses
            )
            assertTrue(threads.size >= 2)
            assertEquals(setOf(scannerThread), threads.toSet())
        } finally {
            try {
                manager.close()
            } finally {
                dispatcher.close()
                assertTrue(executor.awaitTermination(2, TimeUnit.SECONDS), "owned scanner executor did not stop")
            }
        }
        assertEquals(1, closes)
    }
}
