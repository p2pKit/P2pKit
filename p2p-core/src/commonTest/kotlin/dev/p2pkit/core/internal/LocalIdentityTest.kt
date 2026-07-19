package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.PeerId
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
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = null)
}
