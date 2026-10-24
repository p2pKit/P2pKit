package dev.p2pkit.transport.lan

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
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
        assertEquals(2, MacLanNative.abi())
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

    @Test fun realNativeAsyncBatchUsesOneWorkerAcross128And256Connections() = runBlocking(Dispatchers.Default) {
        val errors = load()
        val index = NetworkInterface.getByName("lo0").index
        val address = InetAddress.getByAddress(byteArrayOf(127, 0, 0, 1))
        for (count in listOf(128, 256)) {
            val listener = MacLanServerSocket(MacLanNative, errors, { index })
            val sockets = mutableListOf<MacLanSocket>()
            val connections = mutableListOf<JvmRawConnection>()
            val jobs = mutableListOf<kotlinx.coroutines.Job>()
            val clients = mutableListOf<Pair<JvmRawConnection, Channel<ByteArray>>>()
            try {
                withTimeout(20_000) {
                    listener.bind(InetSocketAddress(address, 0))
                    repeat(count) {
                        val socket = MacLanSocket(MacLanNative, errors, { index }).also { sockets += it }
                        socket.bind(InetSocketAddress(address, 0))
                        socket.connect(listener.localSocketAddress, 1500)
                        val child = (listener.accept() as MacLanSocket).also { sockets += it }
                        assertTrue(socket.verifyScope()); assertTrue(child.verifyScope())
                        socket.tcpNoDelay = true; child.tcpNoDelay = true
                        val host = JvmRawConnection(child, io = JvmLanIo(true)).also { connections += it }
                        val client = JvmRawConnection(socket, io = JvmLanIo(true)).also { connections += it }
                        val received = Channel<ByteArray>(1)
                        clients += client to received
                        jobs += launch { host.read().collect { host.write(it) } }
                        jobs += launch {
                            try { client.read().collect { received.send(it) } } finally { received.close() }
                        }
                    }
                    val payload = ByteArray(1024) { (it % 127).toByte() }
                    repeat(10) {
                        clients.map { (client, received) -> async {
                            client.write(payload)
                            var offset = 0
                            while (offset < payload.size) {
                                val bytes = received.receive()
                                assertTrue(bytes.isNotEmpty() && bytes.size <= payload.size - offset)
                                bytes.forEach { value -> assertEquals(payload[offset++], value) }
                            }
                        } }.awaitAll()
                    }
                    assertEquals(1, Thread.getAllStackTraces().keys.count { it.name == "p2pkit-macos-readiness" })
                    println("NATIVE_ASYNC clients=$count responses=${count * 10} readinessThreads=1")
                }
            } finally {
                withContext(NonCancellable) {
                    var failure: Throwable? = null
                    for (owned in connections) try { owned.close() } catch (error: Throwable) {
                        if (failure == null) failure = error else failure.addSuppressed(error)
                    }
                    for (socket in sockets) try { socket.close() } catch (error: Throwable) {
                        if (failure == null) failure = error else failure.addSuppressed(error)
                    }
                    try { listener.close() } catch (error: Throwable) {
                        if (failure == null) failure = error else failure.addSuppressed(error)
                    }
                    withTimeout(5_000) { jobs.forEach { it.cancelAndJoin() } }
                    assertEquals(0, Thread.getAllStackTraces().keys.count { it.name == "p2pkit-macos-readiness" })
                    failure?.let { throw it }
                }
            }
        }
    }
}
