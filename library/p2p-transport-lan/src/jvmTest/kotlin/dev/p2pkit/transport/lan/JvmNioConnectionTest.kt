package dev.p2pkit.transport.lan

import dev.p2pkit.core.ConnectionState
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.supervisorScope
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import java.io.IOException
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.Socket
import java.nio.ByteBuffer
import java.nio.channels.ServerSocketChannel
import java.nio.channels.SocketChannel
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** Exercise the production channel adapter, not the intentionally retained fake blocking-Socket seam. */
class JvmNioConnectionTest {
    private class Pair : AutoCloseable {
        private val listener = ServerSocketChannel.open()
        val local: Socket
        val remote: Socket

        init {
            listener.socket().receiveBufferSize = 1024
            listener.bind(InetSocketAddress(InetAddress.getLoopbackAddress(), 0))
            local = SocketChannel.open().socket()
            local.sendBufferSize = 1024
            local.tcpNoDelay = true
            local.connect(listener.localAddress, 5_000)
            remote = listener.accept().socket()
            remote.soTimeout = 5_000
        }

        /** Prove the kernel actually reached would-block before a cancellation/watchdog assertion. */
        fun fillSendBuffer() {
            val channel = checkNotNull(local.channel)
            channel.configureBlocking(false)
            val bytes = ByteBuffer.wrap(ByteArray(8192))
            var sent = 0
            while (true) {
                bytes.clear()
                val count = channel.write(bytes)
                if (count == 0) break
                sent += count
                check(sent <= 8 * 1_048_576) { "Fixture failed to backpressure the real socket" }
            }
            check(sent > 0)
        }

        override fun close() {
            try { local.close() } finally { try { remote.close() } finally { listener.close() } }
        }
    }

    @Test fun cancellingSuspendedReadRetiresChannelWithoutAnyRemoteClose() = runBlocking {
        Pair().use { pair ->
            val raw = JvmRawConnection(pair.local, io = JvmLanIo(true))
            val delivered = CompletableDeferred<Unit>()
            val reader = launch(Dispatchers.Default) {
                raw.read().collect { assertContentEquals(byteArrayOf(42), it); delivered.complete(Unit) }
            }
            try {
                pair.remote.getOutputStream().write(byteArrayOf(42))
                withTimeout(5_000) { delivered.await(); reader.cancelAndJoin() }
                assertTrue(pair.local.isClosed)
                assertFalse(pair.local.channel.isOpen)
                assertFalse(pair.remote.isClosed)
                assertEquals(ConnectionState.Closed, raw.state.value)
            } finally { raw.close(); reader.cancelAndJoin() }
        }
    }

    @Test fun halfCloseEndsNioReadAndReleasesOriginalDescriptor() = runBlocking {
        Pair().use { pair ->
            val raw = JvmRawConnection(pair.local)
            val reader = async(start = CoroutineStart.UNDISPATCHED) {
                raw.read().collect { error("The fixture sends FIN only") }
            }
            try {
                pair.remote.shutdownOutput()
                withTimeout(5_000) { reader.await() }
                assertTrue(pair.local.isClosed)
                assertFalse(pair.remote.isClosed)
                assertEquals(ConnectionState.Closed, raw.state.value)
            } finally { raw.close(); reader.cancelAndJoin() }
        }
    }

    @Test fun stalledNonblockingWriteTimesOutAndCannotReportSuccess() = runBlocking { supervisorScope {
        Pair().use { pair ->
            pair.fillSendBuffer()
            val raw = JvmRawConnection(pair.local, writeTimeoutMillis = 100, io = JvmLanIo(true))
            try {
                withTimeout(5_000) {
                    val error = assertFailsWith<IOException> { raw.write(ByteArray(8 * 1_048_576)) }
                    assertTrue(error.message.orEmpty().contains("timed out"))
                }
                assertTrue(pair.local.isClosed)
                assertFalse(pair.local.channel.isOpen)
                assertEquals(ConnectionState.Closed, raw.state.value)
            } finally { raw.close() }
        }
    } }

    @Test fun cancellingBackpressuredWriteClosesPartialStreamWithoutWaitingForWatchdog() = runBlocking {
        Pair().use { pair ->
            pair.fillSendBuffer()
            val raw = JvmRawConnection(pair.local, writeTimeoutMillis = 30_000, io = JvmLanIo(true))
            val writer = launch(start = CoroutineStart.UNDISPATCHED) { raw.write(ByteArray(8 * 1_048_576)) }
            try {
                delay(50)
                assertFalse(writer.isCompleted, "The proved full send window must not finish a large write")
                withTimeout(5_000) { writer.cancelAndJoin() }
                assertTrue(pair.local.isClosed)
                assertFalse(pair.local.channel.isOpen)
                assertEquals(ConnectionState.Closed, raw.state.value)
            } finally { raw.close(); writer.cancelAndJoin() }
        }
    }

    @Test fun partialWritesPreserveWholeWriteOrderingWhileAnotherConnectionProgresses() = runBlocking {
        Pair().use { busy -> Pair().use { other ->
            val raw = JvmRawConnection(busy.local, io = JvmLanIo(true))
            val independent = JvmRawConnection(other.local, io = JvmLanIo(true))
            val first = ByteArray(131_072) { (it % 127).toByte() }
            val second = ByteArray(16_384) { (255 - it % 127).toByte() }
            val startedReading = CompletableDeferred<Unit>()
            val reader = async(Dispatchers.IO) {
                val actual = ByteArray(first.size + second.size)
                val input = busy.remote.getInputStream()
                val firstCount = input.read(actual, 0, 1024)
                check(firstCount > 0)
                startedReading.complete(Unit)
                input.readNBytes(actual, firstCount, actual.size - firstCount).also {
                    assertEquals(actual.size - firstCount, it)
                }
                actual
            }
            val writer = launch { raw.write(first) }
            try {
                withTimeout(10_000) {
                    startedReading.await() // Establish which call owns the write mutex before the second.
                    val next = launch { raw.write(second) }
                    independent.write(byteArrayOf(7, 8, 9))
                    assertContentEquals(byteArrayOf(7, 8, 9), withContext(Dispatchers.IO) {
                        other.remote.getInputStream().readNBytes(3)
                    })
                    writer.join(); next.join()
                    assertContentEquals(first + second, reader.await())
                }
            } finally {
                raw.close(); independent.close()
                writer.cancelAndJoin(); reader.cancelAndJoin()
            }
        } }
    }
}
