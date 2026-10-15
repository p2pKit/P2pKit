package dev.p2pkit.transport.lan

import java.net.InetAddress
import java.net.SocketException
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class JvmLanSocketAdmissionTest {
    private val local = address("10.1.2.3")
    private val peer = address("10.1.2.4")
    private val policy = OrganizationLan(listOf("10.1.2.0/24"), "eth0", "10.1.2.3")
    private val selected = JvmLanInterfaceSnapshot(
        "eth0", true, false, false, false, true, listOf(LanInterfaceAddress(local, 24)),
    )

    @Test
    fun eachValidationUsesOneFreshSnapshotWithoutASecondNativeEnumeration() {
        var reads = 0
        repeat(3) {
            assertTrue(policy.allowsJvmSocketPath(local, peer, readSnapshot = {
                reads++
                snapshot()
            }, isAssignedLocally = { error("Complete inventory must not enumerate again") }))
        }
        assertEquals(3, reads)
    }

    @Test
    fun previouslyAllowedPathDoesNotSurviveInterfaceOrAddressChanges() {
        val observations = ArrayDeque(
            listOf(
                snapshot(),
                snapshot(selected, selected.copy(name = "eth1")),
                snapshot(selected.copy(isUp = false)),
                snapshot(selected.copy(addresses = emptyList())),
                snapshot().copy(completeLocalAddresses = setOf(local, peer)),
                null,
                snapshot(),
            ),
        )
        val allowed = List(7) {
            policy.allowsJvmSocketPath(local, peer, readSnapshot = { observations.removeFirst() })
        }
        assertEquals(listOf(true, false, false, false, false, false, true), allowed)
        assertTrue(observations.isEmpty())
    }

    @Test
    fun selfAndHairpinRejectionIncludesSecondaryDownLoopbackAndAliasAddresses() {
        val secondary = address("10.1.2.5")
        val down = address("10.1.2.6")
        val loopbackAlias = address("10.1.2.7")
        val childAlias = address("10.1.2.8")
        val interfaces = listOf(
            selected.copy(addresses = selected.addresses + LanInterfaceAddress(secondary, 24)),
            selected.copy(name = "eth1", isUp = false, addresses = listOf(LanInterfaceAddress(down, 24))),
            selected.copy(
                name = "lo", isLoopback = true, addresses = listOf(LanInterfaceAddress(loopbackAlias, 32)),
            ),
        )
        // The inventory includes subinterfaces too, even if not a top-level bind candidate.
        val view = JvmLanSocketSnapshot(interfaces, setOf(local, secondary, down, loopbackAlias, childAlias))
        for (remote in view.completeLocalAddresses.orEmpty()) {
            assertFalse(policy.allowsJvmSocketPath(local, remote, readSnapshot = { view }))
        }
        assertTrue(policy.allowsJvmSocketPath(local, peer, readSnapshot = { view }))
    }

    @Test
    fun filteredAddressVisibilityRetainsNativeSelfLookupInsteadOfTrustingBindings() {
        val filtered = snapshot().copy(completeLocalAddresses = null)
        var lookups = 0
        for (assigned in listOf(true, false)) {
            assertEquals(!assigned, policy.allowsJvmSocketPath(local, peer, readSnapshot = { filtered },
                isAssignedLocally = { remote ->
                    assertEquals(peer, remote)
                    lookups++
                    assigned
                }))
        }
        assertEquals(2, lookups)
    }

    @Test
    fun filteredVisibilityAndNativeLookupFailureCannotFallBackToAllowingThePeer() {
        assertFalse(policy.allowsJvmSocketPath(local, peer,
            readSnapshot = { snapshot().copy(completeLocalAddresses = null) },
            isAssignedLocally = { throw SocketException("unreadable interface inventory") },
        ))
    }

    @Test
    fun unreadableInventoryOrFlagsFailClosedWithoutReusingEarlierObservations() {
        assertTrue(policy.allowsJvmSocketPath(local, peer, readSnapshot = { snapshot() }))
        assertFalse(policy.allowsJvmSocketPath(local, peer, readSnapshot = { null }))
        assertFalse(policy.allowsJvmSocketPath(local, peer,
            readSnapshot = { throw SocketException("unreadable interface flags") },
        ))
    }

    @Test
    fun explicitLocalBindingAndApprovedNumericRemoteAreStillRequired() {
        for (invalidLocal in listOf(peer, address("127.0.0.1"), address("0.0.0.0"))) {
            assertFalse(policy.allowsJvmSocketPath(invalidLocal, peer, readSnapshot = { snapshot() }))
        }
        for (invalidPeer in listOf("127.0.0.1", "0.0.0.0", "10.2.0.1", "192.0.2.1", "224.0.0.251")) {
            assertFalse(policy.allowsJvmSocketPath(local, address(invalidPeer), readSnapshot = { snapshot() }))
        }
    }

    @Test
    fun allFourActiveUtunsStillInvalidateThePathEvenWithOnlyLinkLocalAddresses() {
        val tunnels = List(4) { index ->
            selected.copy(
                name = "utun$index", isPointToPoint = true,
                addresses = listOf(LanInterfaceAddress(address("fe80::1"), 64)),
            )
        }
        assertFalse(policy.allowsJvmSocketPath(local, peer,
            readSnapshot = { snapshot(*(listOf(selected) + tunnels).toTypedArray()) },
        ))
        assertTrue(policy.allowsJvmSocketPath(local, peer,
            readSnapshot = { snapshot(*(listOf(selected) + tunnels.map { it.copy(isUp = false) }).toTypedArray()) },
        ))
    }

    @Test
    fun explicitSelectionStillRejectsVirtualPointToPointLoopbackAndMissingInterfaces() {
        val invalid = listOf(
            selected.copy(isVirtual = true), selected.copy(isPointToPoint = true),
            selected.copy(isLoopback = true), selected.copy(isUp = false), selected.copy(name = "eth1"),
        )
        invalid.forEach { network ->
            assertFalse(policy.allowsJvmSocketPath(local, peer, readSnapshot = { snapshot(network) }))
        }
        assertFalse(policy.allowsJvmSocketPath(local, peer,
            readSnapshot = { JvmLanSocketSnapshot(emptyList(), emptySet()) },
        ))
    }

    @Test
    fun ipv6LocalityUsesAddressIdentityNotTextualSpelling() {
        val source = address("fd00::3")
        val remote = address("fd00::4")
        val ipv6 = OrganizationLan(listOf("fd00::/64"), "eth0", "fd00::3")
        val network = selected.copy(addresses = listOf(LanInterfaceAddress(source, 64)))
        val view = JvmLanSocketSnapshot(listOf(network), setOf(address("fd00:0:0:0:0:0:0:3")))
        assertTrue(ipv6.allowsJvmSocketPath(source, remote, readSnapshot = { view }))
        assertFalse(ipv6.allowsJvmSocketPath(source, address("fd00::3"), readSnapshot = { view }))
        assertFalse(ipv6.allowsJvmSocketPath(source, remote,
            readSnapshot = { view.copy(completeLocalAddresses = view.completeLocalAddresses.orEmpty() + remote) },
        ))
    }

    @Test
    fun staticAdmissionMatchesThePreviousPredicateForCompleteAndFilteredSnapshots() {
        val topologies = listOf(
            listOf(selected), emptyList(), listOf(selected.copy(isUp = false)),
            listOf(selected.copy(isVirtual = true)), listOf(selected.copy(isPointToPoint = true)),
            listOf(selected.copy(isLoopback = true)), listOf(selected.copy(addresses = emptyList())),
            listOf(selected, selected.copy(name = "eth1")),
            listOf(selected, selected.copy(name = "utun0", isPointToPoint = true)),
            listOf(selected, selected.copy(name = "eth1", isUp = false)),
        )
        for (topology in topologies) for (source in listOf(local, peer)) {
            for (remote in listOf(local, peer, address("10.2.0.1"), address("192.0.2.1"))) {
                for (assigned in listOf(true, false)) for (filtered in listOf(true, false)) {
                    val previous = organizationJvmTarget(policy, topology) != null &&
                        policy.isLocal(source.hostAddress) && policy.allows(remote.hostAddress) && !assigned
                    val addresses = if (filtered) null else if (assigned) setOf(remote) else emptySet()
                    val view = JvmLanSocketSnapshot(topology, addresses)
                    assertEquals(previous, policy.allowsJvmSocketPath(source, remote,
                        readSnapshot = { view }, isAssignedLocally = { assigned },
                    ))
                }
            }
        }
    }

    private fun snapshot(vararg networks: JvmLanInterfaceSnapshot = arrayOf(selected)): JvmLanSocketSnapshot =
        JvmLanSocketSnapshot(networks.toList(), networks.flatMap { it.addresses }.map { it.address }.toSet())

    private fun address(numeric: String): InetAddress =
        InetAddress.getByAddress(checkNotNull(NumericAddress.parse(numeric)).bytes)
}
