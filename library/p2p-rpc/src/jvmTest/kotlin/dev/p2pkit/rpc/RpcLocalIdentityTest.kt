package dev.p2pkit.rpc

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerPairingQr
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.dsl.jvmSecureIdentityStore
import dev.p2pkit.core.security.JvmSecureIdentityStore
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportDescriptor
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import dev.p2pkit.transport.lan.OrganizationLan
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNotEquals
import kotlin.test.assertSame
import kotlin.test.assertTrue

class RpcLocalIdentityTest {
    // Synthetic policy only: the test transport refuses every networking operation.
    private val lan = OrganizationLan(listOf("10.0.0.0/24"), "identitytest", "10.0.0.1")
    private val appId = AppId("rpc-local-identity-test")

    @Test
    fun hostReadsActualKitBeforeStartingWithoutCreatingEnrollmentOrTrust() = runBlocking {
        val fixture = Fixture()
        lateinit var configuration: RpcHostConfiguration
        val host = RpcHost.create(fixture.platform, this) {
            configuration = this
            appId = this@RpcLocalIdentityTest.appId
            lan = this@RpcLocalIdentityTest.lan
            trustStore = fixture.trust
        }
        try {
            val identity = host.localIdentity
            fixture.assertIdentity(identity, "P2pKit RPC host")
            assertSame(identity, host.localIdentity)
            assertEquals(identity.fingerprint, host.fingerprint)
            assertEquals(RpcHostState.Idle, host.state.value)
            assertTrue(host.connections.value.isEmpty())
            assertTrue(host.pairing.pending.value.isEmpty())
            assertTrue(host.trust.fingerprints().isEmpty())
            configuration.appId = AppId("changed-after-create")
            configuration.deviceName = "changed after create"
            fixture.assertIdentity(identity, "P2pKit RPC host")
        } finally {
            host.close()
            fixture.clear()
        }
        assertEquals(RpcHostState.Closed, host.state.value)
        fixture.assertIdentity(host.localIdentity, "P2pKit RPC host")
        assertEquals(1, fixture.transport.closes)
        assertEquals(0, fixture.trust.replacements)
    }

    @Test
    fun clientReadsActualKitBeforeDiscoveryOrConnectionWithoutGrantingTrust() = runBlocking {
        val fixture = Fixture()
        val client = RpcClient.create(fixture.platform, this) {
            appId = this@RpcLocalIdentityTest.appId
            lan = this@RpcLocalIdentityTest.lan
            trustStore = fixture.trust
            deviceName = "Terminal café"
        }
        try {
            fixture.assertIdentity(client.localIdentity, "Terminal café")
            assertSame(client.localIdentity, client.localIdentity)
            assertEquals(client.localIdentity.fingerprint, client.fingerprint)
            assertTrue(client.discoveredPeers.value.isEmpty())
            assertTrue(client.trust.fingerprints().isEmpty())
        } finally {
            client.close()
            fixture.clear()
        }
        fixture.assertIdentity(client.localIdentity, "Terminal café")
        assertEquals(1, fixture.transport.closes)
        assertEquals(0, fixture.trust.replacements)
    }

    @Test
    fun retainedStoreAndNameReconstructIdentityAcrossRolesAndNamesAreSeparateFromKeyIdentity() = runBlocking {
        val store = TestIdentityStore()
        try {
            val hostFixture = Fixture(store)
            val host = RpcHost.create(hostFixture.platform, this) {
                appId = this@RpcLocalIdentityTest.appId
                lan = this@RpcLocalIdentityTest.lan
                trustStore = hostFixture.trust
                deviceName = "Retained terminal"
            }
            val original = try { host.localIdentity } finally { host.close() }
            val clientFixture = Fixture(store)
            val client = RpcClient.create(clientFixture.platform, this) {
                appId = original.appId
                lan = this@RpcLocalIdentityTest.lan
                trustStore = clientFixture.trust
                deviceName = original.deviceName
            }
            try {
                assertEquals(original.peerId, client.localIdentity.peerId)
                assertEquals(original.fingerprint, client.localIdentity.fingerprint)
                assertEquals(original.pairingQr, client.localIdentity.pairingQr)
                clientFixture.assertIdentity(client.localIdentity, original.deviceName)
            } finally { client.close() }
            val defaultFixture = Fixture(store)
            val defaultClient = RpcClient.create(defaultFixture.platform, this) {
                appId = original.appId
                lan = this@RpcLocalIdentityTest.lan
                trustStore = defaultFixture.trust
            }
            try {
                defaultFixture.assertIdentity(defaultClient.localIdentity, "P2pKit RPC client")
                assertNotEquals(original.deviceName, defaultClient.localIdentity.deviceName)
                assertEquals(original.peerId, defaultClient.localIdentity.peerId)
                assertEquals(original.fingerprint, defaultClient.localIdentity.fingerprint)
                assertEquals(original.pairingQr, defaultClient.localIdentity.pairingQr)
            } finally {
                defaultClient.close()
            }
        } finally { store.clear() }
    }

    @Test
    fun differentAppIdUsesItsActualNamespaceAndIndependentIdentity() = runBlocking {
        val fixture = Fixture()
        val host = RpcHost.create(fixture.platform, this) {
            appId = AppId("other-rpc-local-identity-test")
            lan = this@RpcLocalIdentityTest.lan
            trustStore = fixture.trust
        }
        try {
            assertNotEquals(appId, host.localIdentity.appId)
            fixture.assertIdentity(host.localIdentity, "P2pKit RPC host")
        } finally {
            host.close()
            fixture.clear()
        }
    }

    @Test
    fun explicitInvalidNameIsRejectedByCoreBeforeTransportConstruction() = runBlocking {
        for (name in listOf("", " ", "bad\u0000name", "x".repeat(1025))) {
            val fixture = Fixture()
            try {
                assertFailsWith<RpcFailure> {
                    RpcClient.create(fixture.platform, this) {
                        appId = this@RpcLocalIdentityTest.appId
                        lan = this@RpcLocalIdentityTest.lan
                        trustStore = fixture.trust
                        deviceName = name
                    }
                }
                assertEquals(0, fixture.builds)
                assertEquals(0, fixture.trust.replacements)
            } finally { fixture.clear() }
        }
    }

    private class Fixture(private val store: TestIdentityStore = TestIdentityStore()) {
        val transport = InertTransport()
        val trust = TestTrustStore()
        lateinit var kit: P2pKit
        lateinit var context: TransportContext
        var builds = 0
        val platform = RpcPlatform { settings ->
            P2pKit.create {
                settings.configure(this)
                jvmSecureIdentityStore(store)
                transports {
                    register(object : TransportFactory {
                        override val descriptor = TransportDescriptor.dataOnly(TransportKind.LAN)
                        override fun build(context: TransportContext): TransportPair {
                            this@Fixture.context = context
                            builds++
                            return TransportPair(data = transport)
                        }
                    })
                }
            }.also { kit = it }
        }

        fun assertIdentity(identity: RpcLocalIdentity, name: String) {
            assertEquals(kit.appId, identity.appId)
            assertEquals(kit.localPeerId, identity.peerId)
            assertEquals(kit.localFingerprint, identity.fingerprint)
            assertEquals(kit.localPairingQr, identity.pairingQr)
            assertEquals(kit.localDeviceName, identity.deviceName)
            assertEquals(context.appId, identity.appId)
            assertEquals(context.localPeerId, identity.peerId)
            assertEquals(context.localFingerprint, identity.fingerprint)
            assertEquals(context.deviceName, identity.deviceName)
            assertEquals(name, identity.deviceName)
            assertTrue(identity.peerId.value.startsWith("p2id2-"))
            assertEquals(identity.fingerprint, PeerPairingQr.parse(identity.pairingQr).fingerprint)
            assertEquals(identity.fingerprint, kit.parsePeerPairingQr(identity.pairingQr))
        }

        fun clear() = store.clear()
    }

    private class InertTransport : DataTransport {
        override val type = TransportKind.LAN
        override val priority = 1
        var closes = 0
        override suspend fun start(): Result<Unit> = error("Identity readback must not start networking")
        override suspend fun stop() = Unit
        override fun canConnect(peer: InternalPeer): Boolean = error("Unexpected peer selection")
        override suspend fun connect(peer: InternalPeer): RawConnection = error("Unexpected connection")
        override fun incomingConnections(): Flow<RawConnection> = error("Unexpected transport collection")
        override suspend fun close() { closes++ }
    }

    // Test-only process storage; these fixtures do not qualify durable/protected platform storage.
    private class TestIdentityStore : JvmSecureIdentityStore {
        private val entries = mutableMapOf<String, ByteArray>()
        @Synchronized
        override fun read(namespace: String): ByteArray? = entries[namespace]?.copyOf()
        @Synchronized
        override fun putIfAbsent(namespace: String, value: ByteArray): ByteArray =
            entries.getOrPut(namespace) { value.copyOf() }.copyOf()
        @Synchronized
        override fun delete(namespace: String): Boolean = entries.remove(namespace)?.let { it.fill(0); true } ?: false
        @Synchronized
        fun clear() { entries.values.forEach { it.fill(0) }; entries.clear() }
    }

    private class TestTrustStore : RpcTrustStore {
        var replacements = 0
        override suspend fun load(appId: AppId, purpose: RpcTrustPurpose): Set<PeerFingerprint> = emptySet()
        override suspend fun replace(appId: AppId, purpose: RpcTrustPurpose, fingerprints: Set<PeerFingerprint>) {
            replacements++
            error("Identity readback must not grant trust")
        }
    }
}
