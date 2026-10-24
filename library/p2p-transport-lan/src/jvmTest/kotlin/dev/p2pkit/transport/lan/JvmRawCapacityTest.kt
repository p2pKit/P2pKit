package dev.p2pkit.transport.lan

import com.sun.management.OperatingSystemMXBean
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import java.lang.management.ManagementFactory
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.Socket
import java.nio.channels.ServerSocketChannel
import java.nio.channels.SocketChannel
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/** Actual transport byte I/O, not an RPC/authentication or physical-LAN capacity claim. */
class JvmRawCapacityTest {
    @Test fun clients128() = measure(128)

    @Test fun clients256() = measure(256)

    private fun measure(clients: Int) = runBlocking {
        val os = ManagementFactory.getOperatingSystemMXBean() as OperatingSystemMXBean
        val threads = ManagementFactory.getThreadMXBean()
        val connections = mutableListOf<JvmRawConnection>()
        val peers = mutableListOf<Socket>()
        val readers = mutableListOf<kotlinx.coroutines.Job>()
        val beforeThreads = threads.threadCount
        val baselineHeap = ManagementFactory.getMemoryMXBean().heapMemoryUsage.used
        val payload = ByteArray(1024) { (it % 127).toByte() }
        ServerSocketChannel.open().use { listener ->
            listener.bind(InetSocketAddress(InetAddress.getLoopbackAddress(), 0))
            try {
                repeat(clients) {
                    val peer = SocketChannel.open().socket()
                    peers += peer
                    peer.tcpNoDelay = true
                    peer.soTimeout = 10_000
                    peer.connect(listener.localAddress, 5_000)
                    val socket = listener.accept().socket().apply { tcpNoDelay = true }
                    val connection = JvmRawConnection(socket, io = JvmLanIo(true))
                    connections += connection
                    readers += launch(Dispatchers.Default) {
                        connection.read().collect { connection.write(it) }
                    }
                }
                // Every socket must deliver data before its idle measurement. Merely creating sockets is insufficient.
                fun exchange(peer: Socket) {
                    peer.getOutputStream().write(payload)
                    val returned = ByteArray(payload.size)
                    peer.getInputStream().readNBytes(returned, 0, returned.size).also {
                        assertEquals(payload.size, it)
                        assertTrue(payload.contentEquals(returned))
                    }
                }
                peers.forEach(::exchange)
                delay(3_000)
                val activeThreads = threads.threadCount
                assertTrue(activeThreads - beforeThreads < 80, "Idle clients must not reserve one thread per socket")
                assertEquals(1, Thread.getAllStackTraces().keys.count { it.name == "p2pkit-nio-readiness" })
                val heap = ManagementFactory.getMemoryMXBean().heapMemoryUsage.used
                val idleCpu = os.processCpuTime
                val idleStart = System.nanoTime()
                delay(2_000)
                val idleWall = System.nanoTime() - idleStart
                val cpu = os.processCpuTime - idleCpu
                val latencies = mutableListOf<Long>()
                val activeStart = System.nanoTime()
                repeat(4) {
                    peers.forEach { peer ->
                        val start = System.nanoTime()
                        exchange(peer)
                        latencies += System.nanoTime() - start
                    }
                }
                val activeWall = System.nanoTime() - activeStart
                latencies.sort()
                println("RAW_CAPACITY clients=$clients beforeThreads=$beforeThreads idleThreads=$activeThreads " +
                    "heapBefore=$baselineHeap heapIdle=$heap idleWallNs=$idleWall idleCpuNs=$cpu " +
                    "responses=${latencies.size} activeWallNs=$activeWall " +
                    "p95Ns=${latencies[(latencies.size * 95 / 100)]} p99Ns=${latencies[(latencies.size * 99 / 100)]}")
            } finally {
                connections.forEach { it.close() }
                peers.forEach { it.close() }
                withTimeout(10_000) { readers.forEach { it.cancelAndJoin() } }
                assertEquals(0, Thread.getAllStackTraces().keys.count { it.name == "p2pkit-nio-readiness" })
            }
        }
    }
}
