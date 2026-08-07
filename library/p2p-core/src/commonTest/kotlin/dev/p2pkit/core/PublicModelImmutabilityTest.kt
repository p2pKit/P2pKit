package dev.p2pkit.core

import dev.p2pkit.core.permission.P2pPermission
import dev.p2pkit.core.provisioning.ManualConnectionInfo
import dev.p2pkit.core.provisioning.NetworkState
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.TransportHint
import dev.p2pkit.core.transport.TransportSecurityProfile
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

class PublicModelImmutabilityTest {

    @Test
    fun publicCollectionModelsOwnStableUnmodifiableSnapshots() {
        val transports = mutableSetOf(TransportKind.LAN)
        val metadata = mutableMapOf("scope" to "local")
        val hints = mutableListOf(
            TransportHint(TransportKind.LAN, "192.0.2.1", 4242, metadata)
        )
        val addresses = mutableListOf("192.0.2.10")
        val permissions = mutableListOf(P2pPermission.LocalNetwork)
        val fingerprints = mutableSetOf(PeerFingerprint("p2f1-${"a".repeat(52)}"))

        val peer = Peer(PeerId("peer"), "Peer", Platform.LINUX, transports)
        val hint = hints.single()
        val internal = InternalPeer(peer, hints)
        val local = LocalPeerInfo(
            PeerId("local"),
            "Local",
            Platform.LINUX,
            AppId("immutability.test"),
            transports,
            TransportSecurityProfile.AuthenticatedV2,
            fingerprints.single()
        )
        val policy = PeerAuthorizationPolicy.PinnedOnly(fingerprints)
        val text = P2pMessage.Text("hello", metadata)
        val binary = P2pMessage.Binary(byteArrayOf(1), metadata)
        val wifi = NetworkState.ConnectedToWifi("ssid", addresses)
        val ethernet = NetworkState.ConnectedToEthernet(addresses)
        val hosted = NetworkState.LocalNetworkHosted(null, addresses)
        val manual = ManualConnectionInfo(
            addresses,
            4242,
            AppId("immutability.test"),
            PeerId("local"),
            "Local"
        )
        val missing = P2pError.PermissionMissing(permissions)
        val featureMissing = FeatureState.PermissionRequired(permissions)
        val provisioningMissing =
            NetworkProvisioningError.PermissionMissingForProvisioning(permissions)

        transports += TransportKind.BLE
        metadata["mutated"] = "true"
        hints += TransportHint(TransportKind.BLE)
        addresses += "198.51.100.20"
        permissions += P2pPermission.Bluetooth
        fingerprints += PeerFingerprint("p2f1-b${"a".repeat(51)}")

        assertEquals(setOf(TransportKind.LAN), peer.supportedTransports)
        assertEquals(listOf(hint), internal.transportHints)
        assertEquals(mapOf("scope" to "local"), hint.metadata)
        assertEquals(setOf(TransportKind.LAN), local.supportedTransports)
        assertEquals(1, policy.fingerprints.size)
        assertEquals(mapOf("scope" to "local"), text.metadata)
        assertEquals(mapOf("scope" to "local"), binary.metadata)
        assertEquals(listOf("192.0.2.10"), wifi.localIpAddresses)
        assertEquals(listOf("192.0.2.10"), ethernet.localIpAddresses)
        assertEquals(listOf("192.0.2.10"), hosted.localIpAddresses)
        assertEquals(listOf("192.0.2.10"), manual.hostAddresses)
        assertEquals(listOf(P2pPermission.LocalNetwork), missing.permissions)
        assertEquals(listOf(P2pPermission.LocalNetwork), featureMissing.missing)
        assertEquals(
            listOf(P2pPermission.LocalNetwork),
            provisioningMissing.permissions
        )

        assertSame(peer.supportedTransports, peer.supportedTransports)
        assertSame(hint.metadata, hint.metadata)
        assertSame(text.metadata, text.metadata)
        assertSame(binary.metadata, binary.metadata)
        assertSame(manual.hostAddresses, manual.hostAddresses)

        assertCannotAdd(peer.supportedTransports, TransportKind.RELAY)
        assertCannotAdd(internal.transportHints, TransportHint(TransportKind.RELAY))
        assertCannotPut(hint.metadata, "injected", "value")
        assertCannotAdd(local.supportedTransports, TransportKind.RELAY)
        assertCannotAdd(policy.fingerprints, PeerFingerprint("p2f1-c${"a".repeat(51)}"))
        assertCannotPut(text.metadata, "injected", "value")
        assertCannotPut(binary.metadata, "injected", "value")
        assertCannotAdd(wifi.localIpAddresses, "203.0.113.1")
        assertCannotAdd(ethernet.localIpAddresses, "203.0.113.1")
        assertCannotAdd(hosted.localIpAddresses, "203.0.113.1")
        assertCannotAdd(manual.hostAddresses, "203.0.113.1")
        assertCannotAdd(missing.permissions, P2pPermission.Location)
        assertCannotAdd(featureMissing.missing, P2pPermission.Location)
        assertCannotAdd(provisioningMissing.permissions, P2pPermission.Location)
    }

    @Test
    fun handWrittenValuesPreserveDataClassStyleSemantics() {
        val peer = Peer(
            PeerId("peer"),
            "Peer",
            Platform.LINUX,
            setOf(TransportKind.LAN)
        )
        val (id, name, platform, transports) = peer

        assertEquals(peer.id, id)
        assertEquals(peer.name, name)
        assertEquals(peer.platform, platform)
        assertEquals(peer.supportedTransports, transports)
        assertEquals(peer, peer.copy())
        assertEquals(peer.hashCode(), peer.copy().hashCode())
        assertEquals(
            "Peer(id=${peer.id}, name=Peer, platform=LINUX, supportedTransports=[LAN])",
            peer.toString()
        )

        val text = P2pMessage.Text("hello", mapOf("key" to "value"))
        assertEquals(text, text.copy())
        assertFalse(text === text.copy())
        assertTrue(text.toString().startsWith("Text(value=hello, metadata="))
    }

    @Suppress("UNCHECKED_CAST")
    private fun <E> assertCannotAdd(collection: Collection<E>, value: E) {
        val outcome = runCatching {
            when (collection) {
                is Set<E> -> (collection as MutableSet<E>).add(value)
                else -> (collection as MutableList<E>).add(value)
            }
        }
        assertTrue(outcome.isFailure, "collection accepted mutation: $collection")
    }

    @Suppress("UNCHECKED_CAST")
    private fun <K, V> assertCannotPut(map: Map<K, V>, key: K, value: V) {
        val outcome = runCatching { (map as MutableMap<K, V>)[key] = value }
        assertTrue(outcome.isFailure, "map accepted mutation: $map")
    }
}
