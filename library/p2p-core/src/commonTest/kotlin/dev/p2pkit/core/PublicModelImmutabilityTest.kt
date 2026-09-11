package dev.p2pkit.core

import dev.p2pkit.core.internal.InMemoryPeerIdStorage
import dev.p2pkit.core.permission.P2pPermission
import dev.p2pkit.core.provisioning.ManualConnectionInfo
import dev.p2pkit.core.provisioning.NetworkState
import dev.p2pkit.core.provisioning.WifiCredentials
import dev.p2pkit.core.provisioning.WifiPassword
import dev.p2pkit.core.provisioning.WifiSecurityType
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.assertCannotAdd
import dev.p2pkit.core.testfixtures.assertCannotPut
import dev.p2pkit.core.testfixtures.createTestKit
import dev.p2pkit.core.testfixtures.withTestKit
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.PeerAuthenticationHint
import dev.p2pkit.core.transport.PeerOrigin
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportDescriptor
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportHint
import dev.p2pkit.core.transport.TransportPair
import dev.p2pkit.core.transport.TransportSecurityProfile
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotEquals
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
        assertEqualCopies(
            peer,
            Peer(PeerId("peer"), "Peer", Platform.LINUX, setOf(TransportKind.LAN)),
            peer.copy()
        )
        assertFieldCopy(peer, PeerId("other"), Peer::id) { peer.copy(id = it) }
        assertFieldCopy(peer, "Renamed", Peer::name) { peer.copy(name = it) }
        assertFieldCopy(peer, Platform.IOS, Peer::platform) { peer.copy(platform = it) }
        assertFieldCopy(peer, setOf(TransportKind.BLE), Peer::supportedTransports) {
            peer.copy(supportedTransports = it)
        }
        assertEquals(
            "Peer(id=${peer.id}, name=Peer, platform=LINUX, supportedTransports=[LAN])",
            peer.toString()
        )

        val text = P2pMessage.Text("hello", mapOf("key" to "value"))
        assertEqualCopies(text, P2pMessage.Text("hello", mapOf("key" to "value")), text.copy())
        val (value, metadata) = text
        assertEquals("hello", value)
        assertEquals(mapOf("key" to "value"), metadata)
        assertFieldCopy(text, "goodbye", P2pMessage.Text::value) { text.copy(value = it) }
        assertFieldCopy(text, mapOf("key" to "other"), P2pMessage.Text::metadata) { text.copy(metadata = it) }
        assertFalse(text === text.copy())
        assertTrue(text.toString().startsWith("Text(value=hello, metadata="))
    }

    @Test
    fun permissionAndAuthorizationCopiesRetainTheirCollectionField() {
        val permissions = listOf(P2pPermission.LocalNetwork)
        val changed = listOf(P2pPermission.Bluetooth)
        val missing = P2pError.PermissionMissing(permissions)
        assertEqualCopies(missing, P2pError.PermissionMissing(permissions.toList()), missing.copy())
        assertEquals(permissions, missing.component1())
        assertFieldCopy(missing, changed, P2pError.PermissionMissing::permissions) { missing.copy(permissions = it) }

        val feature = FeatureState.PermissionRequired(permissions)
        assertEqualCopies(feature, FeatureState.PermissionRequired(permissions.toList()), feature.copy())
        assertEquals(permissions, feature.component1())
        assertFieldCopy(feature, changed, FeatureState.PermissionRequired::missing) { feature.copy(missing = it) }

        val provisioning = NetworkProvisioningError.PermissionMissingForProvisioning(permissions)
        assertEqualCopies(
            provisioning,
            NetworkProvisioningError.PermissionMissingForProvisioning(permissions.toList()),
            provisioning.copy()
        )
        assertEquals(permissions, provisioning.component1())
        assertFieldCopy(
            provisioning, changed, NetworkProvisioningError.PermissionMissingForProvisioning::permissions
        ) { provisioning.copy(permissions = it) }

        val fingerprint = PeerFingerprint("p2f1-${"a".repeat(52)}")
        val otherFingerprint = PeerFingerprint("p2f1-b${"a".repeat(51)}")
        val pinned = PeerAuthorizationPolicy.PinnedOnly(setOf(fingerprint))
        assertEqualCopies(pinned, PeerAuthorizationPolicy.PinnedOnly(setOf(fingerprint)), pinned.copy())
        assertEquals(setOf(fingerprint), pinned.component1())
        assertFieldCopy(pinned, setOf(otherFingerprint), PeerAuthorizationPolicy.PinnedOnly::fingerprints) {
            pinned.copy(fingerprints = it)
        }
    }

    @Test
    fun networkAndManualConnectionCopiesPreserveEveryAdvertisedField() {
        val addresses = listOf("192.0.2.10")
        val otherAddresses = listOf("198.51.100.20")
        val wifi = NetworkState.ConnectedToWifi("ssid", addresses)
        assertEqualCopies(wifi, NetworkState.ConnectedToWifi("ssid", addresses.toList()), wifi.copy())
        assertEquals(listOf("ssid", addresses), listOf(wifi.component1(), wifi.component2()))
        assertFieldCopy(wifi, null, NetworkState.ConnectedToWifi::ssid) { wifi.copy(ssid = it) }
        assertFieldCopy(wifi, otherAddresses, NetworkState.ConnectedToWifi::localIpAddresses) {
            wifi.copy(localIpAddresses = it)
        }

        val ethernet = NetworkState.ConnectedToEthernet(addresses)
        assertEqualCopies(ethernet, NetworkState.ConnectedToEthernet(addresses.toList()), ethernet.copy())
        assertEquals(addresses, ethernet.component1())
        assertFieldCopy(ethernet, otherAddresses, NetworkState.ConnectedToEthernet::localIpAddresses) {
            ethernet.copy(localIpAddresses = it)
        }

        val credentials = WifiCredentials("test-network", WifiPassword("synthetic-password"), WifiSecurityType.WPA2)
        val hosted = NetworkState.LocalNetworkHosted(credentials, addresses)
        assertEqualCopies(
            hosted, NetworkState.LocalNetworkHosted(credentials.copy(), addresses.toList()), hosted.copy()
        )
        assertEquals(listOf(credentials, addresses), listOf(hosted.component1(), hosted.component2()))
        assertFieldCopy(hosted, null, NetworkState.LocalNetworkHosted::credentials) { hosted.copy(credentials = it) }
        assertFieldCopy(hosted, otherAddresses, NetworkState.LocalNetworkHosted::localIpAddresses) {
            hosted.copy(localIpAddresses = it)
        }

        val appId = AppId("value-semantics.test")
        val peerId = PeerId("manual-peer")
        val fingerprint = PeerFingerprint("p2f1-${"a".repeat(52)}")
        fun info() = ManualConnectionInfo(addresses, 4242, appId, peerId, "Manual", fingerprint, "synthetic-qr")
        val manual = info()
        assertEqualCopies(manual, info(), manual.copy())
        assertEquals(
            listOf(addresses, 4242, appId, peerId, "Manual", fingerprint, "synthetic-qr"),
            listOf(
                manual.component1(), manual.component2(), manual.component3(), manual.component4(),
                manual.component5(), manual.component6(), manual.component7()
            )
        )
        assertFieldCopy(manual, otherAddresses, ManualConnectionInfo::hostAddresses) { manual.copy(hostAddresses = it) }
        assertFieldCopy(manual, 4243, ManualConnectionInfo::port) { manual.copy(port = it) }
        assertFieldCopy(manual, AppId("other.test"), ManualConnectionInfo::appId) { manual.copy(appId = it) }
        assertFieldCopy(manual, PeerId("other-peer"), ManualConnectionInfo::peerId) { manual.copy(peerId = it) }
        assertFieldCopy(manual, "Renamed", ManualConnectionInfo::deviceName) { manual.copy(deviceName = it) }
        assertFieldCopy(manual, null, ManualConnectionInfo::fingerprint) { manual.copy(fingerprint = it) }
        assertFieldCopy(manual, "other-qr", ManualConnectionInfo::pairingQr) { manual.copy(pairingQr = it) }
    }

    @Test
    fun transportPeerCopiesPreserveRoutingProvenanceAndIdentityFields() {
        val metadata = mapOf("scope" to "local")
        val hint = TransportHint(TransportKind.LAN, "192.0.2.10", 4242, metadata)
        assertEqualCopies(hint, TransportHint(TransportKind.LAN, "192.0.2.10", 4242, metadata.toMap()), hint.copy())
        assertEquals(
            listOf(TransportKind.LAN, "192.0.2.10", 4242, metadata),
            listOf(hint.component1(), hint.component2(), hint.component3(), hint.component4())
        )
        assertFieldCopy(hint, TransportKind.BLE, TransportHint::type) { hint.copy(type = it) }
        assertFieldCopy(hint, null, TransportHint::host) { hint.copy(host = it) }
        assertFieldCopy(hint, null, TransportHint::port) { hint.copy(port = it) }
        assertFieldCopy(hint, mapOf("scope" to "other"), TransportHint::metadata) { hint.copy(metadata = it) }

        val peer = Peer(PeerId("peer"), "Peer", Platform.LINUX, setOf(TransportKind.LAN))
        val fingerprint = PeerFingerprint("p2f1-${"a".repeat(52)}")
        val pin = PeerAuthenticationHint.TrustedApplicationPin(fingerprint)
        val internal = InternalPeer(peer, listOf(hint), PeerOrigin.Manual, pin)
        assertEqualCopies(
            internal, InternalPeer(peer.copy(), listOf(hint.copy()), PeerOrigin.Manual, pin), internal.copy()
        )
        assertEquals(
            listOf(peer, listOf(hint), PeerOrigin.Manual, pin),
            listOf(internal.component1(), internal.component2(), internal.component3(), internal.component4())
        )
        assertFieldCopy(internal, peer.copy(name = "Renamed"), InternalPeer::publicPeer) {
            internal.copy(publicPeer = it)
        }
        assertFieldCopy(internal, listOf(hint.copy(port = 4243)), InternalPeer::transportHints) {
            internal.copy(transportHints = it)
        }
        assertFieldCopy(internal, PeerOrigin.Discovered, InternalPeer::origin) { internal.copy(origin = it) }
        assertFieldCopy(
            internal, PeerAuthenticationHint.UntrustedDiscoveryClaim(fingerprint), InternalPeer::authenticationHint
        ) {
            internal.copy(authenticationHint = it)
        }

        val appId = AppId("value-semantics.test")
        fun info() = LocalPeerInfo(
            PeerId("local"), "Local", Platform.LINUX, appId, setOf(TransportKind.LAN),
            TransportSecurityProfile.AuthenticatedV2, fingerprint
        )
        val local = info()
        assertEqualCopies(local, info(), local.copy())
        assertEquals(
            listOf(
                PeerId("local"), "Local", Platform.LINUX, appId, setOf(TransportKind.LAN),
                TransportSecurityProfile.AuthenticatedV2, fingerprint
            ),
            listOf(
                local.component1(), local.component2(), local.component3(), local.component4(),
                local.component5(), local.component6(), local.component7()
            )
        )
        assertFieldCopy(local, PeerId("other"), LocalPeerInfo::peerId) { local.copy(peerId = it) }
        assertFieldCopy(local, "Renamed", LocalPeerInfo::deviceName) { local.copy(deviceName = it) }
        assertFieldCopy(local, Platform.IOS, LocalPeerInfo::platform) { local.copy(platform = it) }
        assertFieldCopy(local, AppId("other.test"), LocalPeerInfo::appId) { local.copy(appId = it) }
        assertFieldCopy(local, setOf(TransportKind.BLE), LocalPeerInfo::supportedTransports) {
            local.copy(supportedTransports = it)
        }
        assertFieldCopy(local, TransportSecurityProfile.LegacyPlaintextV1, LocalPeerInfo::securityProfile) {
            local.copy(securityProfile = it)
        }
        assertFieldCopy(local, null, LocalPeerInfo::fingerprint) { local.copy(fingerprint = it) }
    }

    // These assertions detect independently omitted copy/equals fields without assuming unique hashes.
    private fun <T> assertEqualCopies(original: T, independentlyEqual: T, copy: T) {
        assertEquals(original, independentlyEqual)
        assertEquals(original.hashCode(), independentlyEqual.hashCode())
        assertEquals(original, copy)
    }

    private fun <T, V> assertFieldCopy(original: T, expected: V, property: (T) -> V, copy: (V) -> T) {
        val changed = copy(expected)
        assertEquals(expected, property(changed))
        assertNotEquals(original, changed)
    }

    @Test
    fun defaultFeatureStatesAreRuntimeReadOnly() = runBlocking {
        withTestKit(create = { recorder ->
            createTestKit {
                logger = recorder
                peerIdStorage = InMemoryPeerIdStorage()
                appId = AppId("default-feature-state-test")
                deviceName = "Default state"
                transports { register(DefaultStateTransportFactory) }
            }
        }) { delegate ->
            val compatibilityImplementation = DefaultFeatureStateKit(delegate)
            val advertising = compatibilityImplementation.advertisingState
            val discovery = compatibilityImplementation.discoveryState

            assertSame(advertising, discovery)
            assertEquals(FeatureState.Idle, advertising.value)
            assertFalse(advertising is MutableStateFlow<*>)
        }
    }
}

private class DefaultFeatureStateKit(delegate: P2pKit) : P2pKit by delegate {
    override val advertisingState: StateFlow<FeatureState>
        get() = super<P2pKit>.advertisingState

    override val discoveryState: StateFlow<FeatureState>
        get() = super<P2pKit>.discoveryState
}

private object DefaultStateTransportFactory : TransportFactory {
    override val descriptor: TransportDescriptor =
        TransportDescriptor.dataOnly(TransportKind.LAN)

    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = FakeDataTransport())
}
