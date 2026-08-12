package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.protocol.HelloPayload
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.createTestKit
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlinx.coroutines.runBlocking
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNotEquals

/**
 * Pins the v0.2 local-identity accessors on [P2pKit]: [P2pKit.appId],
 * [P2pKit.localDeviceName], [P2pKit.localPeerId]. Read-only, set at
 * construction, identical across reads on the same kit.
 */
class LocalIdentityTest {

    private val kits = mutableListOf<P2pKit>()

    @AfterTest
    fun teardown() = runBlocking {
        for (kit in kits) runCatching { kit.stop() }
        kits.clear()
    }

    private fun newKit(deviceName: String, peerIdOverride: PeerId): P2pKit {
        val kit = createTestKit {
            appId = AppId("com.example.identity-test")
            this.deviceName = deviceName
            peerIdStorage = InMemoryPeerIdStorage(seed = peerIdOverride)
            transports {
                register(IdentityTestFactory(FakeDataTransport()))
            }
        }
        kits.add(kit)
        return kit
    }

    @Test
    fun localIdentityIsExposedAndStable() {
        val kit = newKit(deviceName = "Alice", peerIdOverride = PeerId("alice-id"))

        assertEquals(AppId("com.example.identity-test"), kit.appId)
        assertEquals("Alice", kit.localDeviceName)
        assertEquals(PeerId("alice-id"), kit.localPeerId)

        // Repeated reads return equal values — these accessors are pure
        // exposure of constructor state, not lazy/recomputed.
        assertEquals(kit.appId, kit.appId)
        assertEquals(kit.localPeerId, kit.localPeerId)
        assertEquals(kit.localDeviceName, kit.localDeviceName)
    }

    @Test
    fun twoKitsInSameProcessHaveTheirOwnIdentity() {
        val a = newKit(deviceName = "Alice", peerIdOverride = PeerId("alice-id"))
        val b = newKit(deviceName = "Bob", peerIdOverride = PeerId("bob-id"))

        assertEquals("Alice", a.localDeviceName)
        assertEquals("Bob", b.localDeviceName)
        assertNotEquals(a.localPeerId, b.localPeerId)
    }

    @Test
    fun invalidDeviceNamesAreRejectedBeforeTransportConstruction() {
        listOf("   ", "a".repeat(513), "unsafe\u202Ename").forEach { invalidName ->
            assertFailsWith<IllegalArgumentException> {
                createTestKit {
                    appId = AppId("com.example.invalid-name")
                    deviceName = invalidName
                    transports { register(IdentityTestFactory(FakeDataTransport())) }
                }
            }
        }
    }

    @Test
    fun invalidAppIdsAreRejectedBeforeIdentityStorageOrTransportConstruction() {
        val invalidAppIds = listOf(
            "a".repeat(HelloPayload.MAX_FIELD_LEN + 1),
            "unsafe\u202Eapp-id",
            "malformed-\uD800"
        )
        invalidAppIds.forEach { invalidAppId ->
            val storage = TrackingPeerIdStorage(PeerId("valid-local-id"))
            val factory = IdentityTestFactory(FakeDataTransport())

            assertFailsWith<IllegalArgumentException> {
                createTestKit {
                    appId = AppId(invalidAppId)
                    deviceName = "Test"
                    peerIdStorage = storage
                    transports { register(factory) }
                }
            }

            assertEquals(0, storage.loadCalls, "invalid AppId must fail before identity I/O")
            assertEquals(0, factory.buildCalls, "invalid AppId must fail before transport construction")
        }
    }

    @Test
    fun invalidStoredLocalPeerIdsAreRejectedBeforeTransportConstruction() {
        val invalidPeerIds = listOf(
            PeerId("x".repeat(HelloPayload.MAX_FIELD_LEN + 1)),
            PeerId("unsafe\u202Epeer-id"),
            PeerId("malformed-\uD800")
        )
        invalidPeerIds.forEach { invalidPeerId ->
            val storage = TrackingPeerIdStorage(invalidPeerId)
            val factory = IdentityTestFactory(FakeDataTransport())

            assertFailsWith<IllegalArgumentException> {
                createTestKit {
                    appId = AppId("com.example.invalid-persisted-peer")
                    deviceName = "Test"
                    peerIdStorage = storage
                    transports { register(factory) }
                }
            }

            assertEquals(1, storage.loadCalls)
            assertEquals(0, factory.buildCalls, "invalid local identity must not reach a transport")
        }
    }

    @Test
    fun duplicateFactoryInstanceIsRejectedBeforeConstruction() {
        val factory = IdentityTestFactory(FakeDataTransport())
        assertFailsWith<IllegalArgumentException> {
            createTestKit {
                appId = AppId("com.example.duplicate-instance")
                deviceName = "Duplicate"
                transports {
                    register(factory)
                    register(factory)
                }
            }
        }
    }
}

private class IdentityTestFactory(private val transport: FakeDataTransport) : TransportFactory {
    var buildCalls: Int = 0
        private set

    override val descriptor =
        dev.p2pkit.core.transport.TransportDescriptor.dataOnly(transport.type)
    override fun build(context: TransportContext): TransportPair {
        buildCalls += 1
        return TransportPair(data = transport, discovery = null)
    }
}

private class TrackingPeerIdStorage(private val peerId: PeerId) : PeerIdStorage {
    var loadCalls: Int = 0
        private set

    override fun loadOrGenerate(): PeerId {
        loadCalls += 1
        return peerId
    }
}
