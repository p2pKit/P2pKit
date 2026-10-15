package dev.p2pkit.sample.android.rpclab

import android.net.NetworkCapabilities
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNotEquals
import kotlin.test.assertNull

/** Deterministic admission controls; not device Wi-Fi, permission or multicast qualification. */
class RpcLabWifiTest {
    private val wifi = NetworkCapabilities.TRANSPORT_WIFI

    private fun snapshot(address: String = "192.168.7.26", prefix: Int = 24) = RpcLabWifiSnapshot(
        networkHandle = 101, transports = setOf(wifi), interfaceName = "wlan0", interfaceIndex = 9,
        interfaceUp = true, linkAddresses = listOf(RpcLabWifiAddress(address, prefix)),
        interfaceAddresses = listOf(RpcLabWifiAddress(address, prefix)),
    )

    private fun rejected(value: RpcLabWifiSnapshot, issue: RpcLabWifiIssue) {
        val observed = assertIs<RpcLabWifiObservation.Unavailable>(RpcLabWifiSelection.observe(value))
        assertEquals(issue, observed.issue)
        assertNull(observed.network)
        assertEquals(issue.explanation, observed.explanation)
    }

    @Test
    fun privateNetworkUsesActualInterfaceIdentityAndPrefixRatherThanAssumingWlan0Or24() {
        for ((address, prefix, subnet) in listOf(
            Triple("192.168.7.26", 24, "192.168.7.0/24"),
            Triple("192.168.7.26", 23, "192.168.6.0/23"),
            Triple("172.21.12.18", 27, "172.21.12.0/27"),
            Triple("10.23.45.67", 8, "10.0.0.0/8"),
        )) {
            val result = assertIs<RpcLabWifiObservation.Available>(RpcLabWifiSelection.observe(
                snapshot(address, prefix).copy(interfaceName = "wlan2", interfaceIndex = 17)))
            assertEquals(RpcLabWifiNetwork(101, "wlan2", 17, address, subnet), result.network)
        }
    }

    @Test
    fun absentChangedNonWifiAndMixedDefaultPathsFailClosed() {
        rejected(snapshot().copy(networkHandle = null), RpcLabWifiIssue.NoDefaultNetwork)
        rejected(snapshot().copy(stable = false), RpcLabWifiIssue.PathChanged)
        rejected(snapshot().copy(capabilitiesAvailable = false), RpcLabWifiIssue.MissingNetworkDetails)
        rejected(snapshot().copy(propertiesAvailable = false), RpcLabWifiIssue.MissingNetworkDetails)
        for (transports in listOf(emptySet(), setOf(NetworkCapabilities.TRANSPORT_CELLULAR),
            setOf(NetworkCapabilities.TRANSPORT_ETHERNET), setOf(NetworkCapabilities.TRANSPORT_VPN))) {
            rejected(snapshot().copy(transports = transports), RpcLabWifiIssue.NotWifi)
        }
        for (other in listOf(NetworkCapabilities.TRANSPORT_VPN, NetworkCapabilities.TRANSPORT_CELLULAR,
            NetworkCapabilities.TRANSPORT_ETHERNET, 15)) {
            rejected(snapshot().copy(transports = setOf(wifi, other)), RpcLabWifiIssue.MixedTransport)
        }
    }

    @Test
    fun missingUnsafeAndNonLanInterfacesCannotBeAutoSelected() {
        rejected(snapshot().copy(interfaceName = null), RpcLabWifiIssue.MissingInterface)
        rejected(snapshot().copy(interfaceIndex = 0), RpcLabWifiIssue.MissingInterface)
        rejected(snapshot().copy(networkHandle = 0), RpcLabWifiIssue.MissingInterface)
        for (name in listOf("", "wlan0\n", "../wlan0", "vpn0", "tun0", "bridge0", "awdl0", "x".repeat(33))) {
            rejected(snapshot().copy(interfaceName = name), RpcLabWifiIssue.UnsafeInterface)
        }
        rejected(snapshot().copy(interfaceUp = false), RpcLabWifiIssue.InactiveInterface)
        rejected(snapshot().copy(loopback = true), RpcLabWifiIssue.InactiveInterface)
        rejected(snapshot().copy(pointToPoint = true), RpcLabWifiIssue.InactiveInterface)
    }

    @Test
    fun aliasesPublicAlternativesAndIncompleteCrossChecksAreNotDiscarded() {
        val row = RpcLabWifiAddress("192.168.7.26", 24)
        rejected(snapshot().copy(linkAddresses = emptyList()), RpcLabWifiIssue.NoIpv4)
        rejected(snapshot().copy(interfaceAddresses = emptyList()), RpcLabWifiIssue.NoIpv4)
        for (extra in listOf(row, RpcLabWifiAddress("192.168.7.27", 24), RpcLabWifiAddress("203.0.113.5", 24))) {
            rejected(snapshot().copy(linkAddresses = listOf(row, extra)), RpcLabWifiIssue.AmbiguousIpv4)
            rejected(snapshot().copy(interfaceAddresses = listOf(row, extra)), RpcLabWifiIssue.AmbiguousIpv4)
        }
        rejected(snapshot().copy(interfaceAddresses = listOf(row.copy(prefix = 23))), RpcLabWifiIssue.AddressMismatch)
        rejected(snapshot().copy(interfaceAddresses = listOf(row.copy(address = "192.168.7.27"))),
            RpcLabWifiIssue.AddressMismatch)
        rejected(snapshot().copy(linkAddresses = listOf(row.copy(usable = false))), RpcLabWifiIssue.UnusableAddress)
    }

    @Test
    fun addressesAreStrictNumericIpv4AndPrivateWithoutDnsOrNormalization() {
        for (address in listOf("localhost", "192.168.7.026", "192.168.7.256", "192.168.7.26\n",
            "192.168.7.26 ", "+192.168.7.26", "192.168.7", "192.168..26", "fd00::1", "::ffff:192.168.7.26")) {
            rejected(snapshot(address), RpcLabWifiIssue.InvalidAddress)
        }
        for (address in listOf("127.0.0.1", "169.254.7.26", "172.32.7.26", "192.169.7.26", "203.0.113.5")) {
            rejected(snapshot(address), RpcLabWifiIssue.NonPrivateAddress)
        }
    }

    @Test
    fun privateMasksMustHaveARealHostRangeWhollyInsideThePrivateAllocation() {
        for ((address, prefixes) in listOf("192.168.7.26" to listOf(-1, 0, 15, 31, 32, 33),
            "172.21.7.26" to listOf(0, 11), "10.7.26.5" to listOf(0, 7))) {
            for (prefix in prefixes) rejected(snapshot(address, prefix), RpcLabWifiIssue.UnsupportedSubnet)
        }
        for (address in listOf("192.168.7.0", "192.168.7.255")) {
            rejected(snapshot(address), RpcLabWifiIssue.NonHostAddress)
        }
    }

    @Test
    fun networkAndInterfaceIdentityArePartOfConfirmationEvenWhenTheAddressIsUnchanged() {
        val baseline = RpcLabWifiSelection.observe(snapshot()).network
        assertNotEquals(baseline, RpcLabWifiSelection.observe(snapshot().copy(networkHandle = 102)).network)
        assertNotEquals(baseline, RpcLabWifiSelection.observe(snapshot().copy(interfaceIndex = 10)).network)
    }

    @Test
    fun diagnosticDetailsDoNotExposeNetworkAddressesOrUntrustedInterfaceText() {
        val accepted = RpcLabWifiSelection.observe(snapshot())
        assertFalse(accepted.details.contains("192.168.7.26"))
        assertFalse(accepted.details.contains("192.168.7.0/24"))
        val unsafe = RpcLabWifiSelection.observe(snapshot().copy(interfaceName = "untrusted\ntext"))
        assertFalse(unsafe.details.contains("untrusted"))
    }
}
