package dev.p2pkit.transport.lan

import java.io.IOException
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.NetworkInterface
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import kotlin.concurrent.thread
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

/** Selected only by macTcpNativeTest: real JNI loopback primitives, never a LAN/multicast qualification. */
class MacLanNativeIntegrationTest {
    private fun load(): MacLanErrnos {
        assertNotNull(MacLanNativeLoader.configuredBinding(OrganizationLan(listOf("10.0.0.0/8"), "en0", "10.1.2.3")))
        assertEquals(1, MacLanNative.abi())
        return MacLanErrnos(MacLanNative.constants())
    }
    @Test fun realNativeRoundTripReadsBackScopeEndpointsAndReleasesAllOwners() {
        val errors = load(); val index = NetworkInterface.getByName("lo0").index
        val address = InetAddress.getByAddress(byteArrayOf(127, 0, 0, 1))
        val listener = MacLanServerSocket(MacLanNative, errors, { index })
        val client = MacLanSocket(MacLanNative, errors, { index })
        var accepted: MacLanSocket? = null
        try {
            listener.bind(InetSocketAddress(address, 0))
            client.bind(InetSocketAddress(address, 0)); client.connect(listener.localSocketAddress, 1500)
            accepted = listener.accept() as MacLanSocket
            assertTrue(client.verifyScope()); assertTrue(accepted.verifyScope())
            assertEquals(listener.localPort, accepted.localPort); assertEquals(client.localPort, accepted.port)
            val payload = ByteArray(32768) { (it % 127).toByte() }
            client.getOutputStream().write(payload)
            val received = accepted.getInputStream().readNBytes(payload.size)
            assertTrue(payload.contentEquals(received))
            accepted.getOutputStream().write(byteArrayOf(3, 5, 7))
            assertTrue(client.getInputStream().readNBytes(3).contentEquals(byteArrayOf(3, 5, 7)))
        } finally { accepted?.close(); client.close(); listener.close() }
        client.requireReleased(); accepted.requireReleased(); listener.close()
        assertTrue(client.isClosed); assertTrue(listener.isClosed)
    }
    @Test fun realBlockedAcceptUnblocksOnOwnedCloseWithoutDescriptorRetry() {
        val errors = load(); val index = NetworkInterface.getByName("lo0").index
        val address = InetAddress.getByAddress(byteArrayOf(127, 0, 0, 1))
        val listener = MacLanServerSocket(MacLanNative, errors, { index })
        listener.bind(InetSocketAddress(address, 0))
        val entered = CountDownLatch(1); val failure = AtomicReference<Throwable?>()
        val worker = thread {
            entered.countDown()
            try { listener.accept(); error("Unexpected inbound connection") }
            catch (error: Throwable) { failure.set(error) }
        }
        assertTrue(entered.await(5, TimeUnit.SECONDS)); listener.close(); worker.join(5000)
        assertFalse(worker.isAlive); assertTrue(failure.get() is IOException); listener.close()
    }
    @Test fun realJniRejectsBadBoundsWithoutCreatingOwnership() {
        load()
        assertTrue(MacLanNative.open(0, LongArray(1)) != 0)
        assertTrue(MacLanNative.open(1, LongArray(2)) != 0)
        assertTrue(MacLanNative.read(0, ByteArray(2), -1, 1) < 0)
        assertTrue(MacLanNative.write(0, ByteArray(2), 1, Int.MAX_VALUE) < 0)
        assertTrue(MacLanNative.poll(0, 0, 101) < 0)
        assertTrue(MacLanNative.bind(0, ByteArray(3), 0) != 0)
    }
}
