package dev.p2pkit.transport.lan

import java.io.FileDescriptor
import java.io.IOException
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.Socket
import java.net.SocketException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Descriptor ownership/adapter controls only. They do not substitute for Android Network/kernel evidence. */
class AndroidNetworkServerSocketTest {
    private class Ops : AndroidSocketOps {
        val listener = FileDescriptor()
        val child = FileDescriptor()
        val events = mutableListOf<String>()
        val closes = mutableListOf<FileDescriptor>()
        val local = InetSocketAddress(InetAddress.getByAddress(byteArrayOf(192.toByte(), 168.toByte(), 1, 6)), 48123)
        val remote = InetSocketAddress(InetAddress.getByAddress(byteArrayOf(192.toByte(), 168.toByte(), 1, 7)), 49123)
        var pendingChild = true
        var failListen = false
        var failConfigure = false
        var failChildClose = false
        var readCount: Int? = 0
        var partialWrites = false
        val written = mutableListOf<Byte>()
        var polled: CountDownLatch? = null
        var configured: (() -> Unit)? = null

        override fun open(ipv6: Boolean): FileDescriptor { events += "open:$ipv6"; return listener }
        override fun configureAccepted(fd: FileDescriptor) {
            events += "configure-child"
            configured?.invoke()
            if (failConfigure) throw SocketException("synthetic configure failure")
        }
        override fun bind(fd: FileDescriptor, address: InetSocketAddress) { events += "bind" }
        override fun listen(fd: FileDescriptor, backlog: Int) {
            events += "listen"
            if (failListen) throw SocketException("synthetic listen failure")
        }
        override fun accept(fd: FileDescriptor): FileDescriptor? {
            if (!pendingChild) return null
            pendingChild = false
            return child
        }
        override fun local(fd: FileDescriptor): InetSocketAddress = local
        override fun remote(fd: FileDescriptor): InetSocketAddress = remote
        override fun reuse(fd: FileDescriptor, enabled: Boolean) { events += "reuse:$enabled" }
        override fun noDelay(fd: FileDescriptor, enabled: Boolean) { events += "noDelay:$enabled" }
        override fun read(fd: FileDescriptor, bytes: ByteArray, offset: Int, length: Int): Int? {
            val count = readCount?.coerceAtMost(length) ?: return null
            repeat(count) { bytes[offset + it] = 42 }
            return count
        }
        override fun write(fd: FileDescriptor, bytes: ByteArray, offset: Int, length: Int): Int? {
            if (readCount == null) return null
            val count = if (partialWrites) minOf(2, length) else length
            repeat(count) { written += bytes[offset + it] }
            return count
        }
        override fun poll(fd: FileDescriptor, writable: Boolean, timeoutMillis: Int) {
            assertEquals(100, timeoutMillis)
            polled?.countDown()
            Thread.sleep(10)
        }
        override fun close(fd: FileDescriptor) = synchronized(closes) {
            if (fd === child && failChildClose) throw SocketException("synthetic close failure")
            assertFalse(fd in closes, "Descriptor closed twice")
            closes += fd
        }
    }

    private fun listener(ops: Ops, networkBind: (FileDescriptor) -> Unit = { ops.events += "network-bind" }) =
        AndroidNetworkServerSocket(null, ops, networkBind).apply { reuseAddress = true; bind(ops.local) }

    @Test
    fun networkBindingPrecedesAddressBindAndListenAndWildcardIsRefused() {
        val ops = Ops()
        val server = listener(ops)
        try {
            assertEquals(listOf("open:false", "network-bind", "reuse:true", "bind", "listen"), ops.events)
            assertTrue(server.isBound)
            assertEquals(ops.local, server.localSocketAddress)
            assertNull(server.boundNetwork, "A host fixture is not a proven Android Network")
        } finally { server.close() }
        assertTrue(server.isClosed)
        server.close()
        assertEquals(listOf(ops.listener), ops.closes)
        val rejected = AndroidNetworkServerSocket(null, Ops()) { error("Must not bind an implicit route") }
        try { assertFailsWith<SocketException> { rejected.bind(InetSocketAddress(0)) } }
        finally { rejected.close() }
    }

    @Test
    fun failedNetworkBindingAndListenKeepTheDescriptorOwnedUntilClose() {
        for (failNetwork in listOf(true, false)) {
            val ops = Ops().apply { failListen = !failNetwork }
            val server = AndroidNetworkServerSocket(null, ops) {
                if (failNetwork) throw IOException("synthetic network binding failure")
            }
            try {
                assertFailsWith<IOException> { server.bind(ops.local) }
                assertFalse(server.isBound)
                assertTrue(ops.closes.isEmpty())
                server.close()
                assertEquals(listOf(ops.listener), ops.closes)
            } finally { server.close() }
        }
    }

    @Test
    fun acceptedConfigurationFailureRetainsFailedChildCleanupForListenerRetry() {
        val ops = Ops().apply { failConfigure = true; failChildClose = true }
        val server = listener(ops)
        try {
            val failure = assertFailsWith<SocketException> { server.accept() }
            assertEquals(1, failure.suppressed.size)
            assertFailsWith<SocketException> { server.close() }
            assertFalse(server.isClosed)
            assertEquals(listOf(ops.listener), ops.closes)
            ops.failChildClose = false
            server.close()
            assertTrue(server.isClosed)
            assertEquals(listOf(ops.listener, ops.child), ops.closes)
        } finally { ops.failChildClose = false; server.close() }
    }

    @Test
    fun acceptedStreamsPreserveEndpointsPartialWritesEofAndIndependentOwnership() {
        val ops = Ops().apply { partialWrites = true; readCount = 3 }
        val server = listener(ops)
        val socket = server.accept()
        try {
            assertEquals(ops.local, socket.localSocketAddress)
            assertEquals(ops.remote, socket.remoteSocketAddress)
            socket.tcpNoDelay = true
            assertTrue("configure-child" in ops.events && "noDelay:true" in ops.events)
            val bytes = byteArrayOf(1, 2, 3, 4, 5, 6, 7)
            socket.getOutputStream().write(bytes, 1, 5)
            assertContentEquals(bytes.copyOfRange(1, 6), ops.written.toByteArray())
            val input = ByteArray(5)
            assertEquals(3, socket.getInputStream().read(input, 1, 3))
            assertContentEquals(byteArrayOf(0, 42, 42, 42, 0), input)
            ops.readCount = 0
            assertEquals(-1, socket.getInputStream().read())
            assertEquals(0, socket.getInputStream().read(input, 0, 0))
            assertFailsWith<IndexOutOfBoundsException> { socket.getInputStream().read(input, -1, 1) }
            server.close()
            assertFalse(socket.isClosed, "A handed-off child is owned by the RawConnection, not the listener")
            socket.close()
            socket.close()
            assertEquals(listOf(ops.listener, ops.child), ops.closes)
        } finally { socket.close(); server.close() }
    }

    @Test
    fun closeDrainsAPendingAcceptWithoutReusingItsDescriptor() {
        val ops = Ops().apply { pendingChild = false; polled = CountDownLatch(1) }
        val server = listener(ops)
        val pool = Executors.newSingleThreadExecutor()
        try {
            val result = pool.submit<Boolean> {
                assertFailsWith<SocketException> { server.accept() }
                true
            }
            assertTrue(ops.polled!!.await(2, TimeUnit.SECONDS))
            server.close()
            assertTrue(result.get(2, TimeUnit.SECONDS))
            assertEquals(listOf(ops.listener), ops.closes)
        } finally {
            server.close()
            pool.shutdownNow()
            assertTrue(pool.awaitTermination(2, TimeUnit.SECONDS))
        }
    }

    @Test
    fun closeDrainsConcurrentReadAndWriteWaitersBeforeClosingTheChild() {
        val ops = Ops().apply { readCount = null; polled = CountDownLatch(2) }
        val server = listener(ops)
        val socket = server.accept()
        val pool = Executors.newFixedThreadPool(2)
        try {
            val read = pool.submit<Boolean> {
                assertFailsWith<SocketException> { socket.getInputStream().read() }
                true
            }
            val write = pool.submit<Boolean> {
                assertFailsWith<SocketException> { socket.getOutputStream().write(byteArrayOf(1)) }
                true
            }
            assertTrue(ops.polled!!.await(2, TimeUnit.SECONDS))
            socket.close()
            assertTrue(read.get(2, TimeUnit.SECONDS) && write.get(2, TimeUnit.SECONDS))
            assertEquals(listOf(ops.child), ops.closes)
            assertTrue(ops.written.isEmpty())
        } finally {
            socket.close()
            server.close()
            pool.shutdownNow()
            assertTrue(pool.awaitTermination(2, TimeUnit.SECONDS))
        }
    }

    @Test
    fun closeDuringAcceptedConfigurationPreventsPublicationAndClosesBothDescriptors() {
        val ops = Ops()
        val entered = CountDownLatch(1)
        val release = CountDownLatch(1)
        ops.configured = { entered.countDown(); check(release.await(2, TimeUnit.SECONDS)) }
        val server = listener(ops)
        val pool = Executors.newFixedThreadPool(2)
        try {
            val accepted = pool.submit<Boolean> { assertFailsWith<SocketException> { server.accept() }; true }
            assertTrue(entered.await(2, TimeUnit.SECONDS))
            val closed = pool.submit { server.close() }
            // The listener descriptor closes before the held child configuration can return.
            val end = System.nanoTime() + TimeUnit.SECONDS.toNanos(2)
            while (synchronized(ops.closes) { ops.listener !in ops.closes } && System.nanoTime() < end) Thread.yield()
            assertTrue(synchronized(ops.closes) { ops.listener in ops.closes })
            release.countDown()
            closed.get(2, TimeUnit.SECONDS)
            assertTrue(accepted.get(2, TimeUnit.SECONDS))
            assertEquals(setOf(ops.listener, ops.child), ops.closes.toSet())
        } finally {
            release.countDown()
            server.close()
            pool.shutdownNow()
            assertTrue(pool.awaitTermination(2, TimeUnit.SECONDS))
        }
    }

    @Test
    fun rawReaderCancellationAndWriteWatchdogCloseTheNewAdapter() = runBlocking {
        for (write in listOf(false, true)) {
            val ops = Ops().apply { readCount = null; polled = CountDownLatch(1) }
            val server = listener(ops)
            val socket: Socket = server.accept()
            val raw = AndroidRawConnection(socket, writeTimeoutMillis = 100)
            try {
                if (write) {
                    val outcome = async(Dispatchers.Default) { runCatching { raw.write(byteArrayOf(1)) } }
                    val failure = withTimeout(2_000) { outcome.await() }.exceptionOrNull()
                    assertTrue(failure is IOException)
                } else {
                    val reader = async(Dispatchers.Default) { raw.read().collect {} }
                    assertTrue(ops.polled!!.await(2, TimeUnit.SECONDS))
                    withTimeout(2_000) { reader.cancelAndJoin() }
                }
                assertTrue(socket.isClosed)
                assertEquals(listOf(ops.child), ops.closes)
            } finally { raw.close(); server.close() }
        }
    }
}
