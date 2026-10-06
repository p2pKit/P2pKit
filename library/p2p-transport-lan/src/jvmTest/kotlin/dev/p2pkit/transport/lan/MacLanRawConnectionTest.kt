package dev.p2pkit.transport.lan

import dev.p2pkit.core.ConnectionState
import java.io.IOException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class MacLanRawConnectionTest {
    @Test fun nativeAdapterWriteWatchdogClosesTheExactOwnedHandle() = runBlocking {
        val released = CountDownLatch(1)
        val api = object : FakeMacLanCalls() {
            override fun write(handle: Long, bytes: ByteArray, offset: Int, length: Int): Int = -35
            override fun poll(handle: Long, writable: Int, timeout: Int): Int {
                released.await(timeout.toLong(), TimeUnit.MILLISECONDS); return 0
            }
            override fun close(handle: Long): Int { released.countDown(); return super.close(handle) }
        }
        val socket = fakeMacSocket(api)
        val raw = JvmRawConnection(socket, writeTimeoutMillis = 100)
        try {
            assertFailsWith<IOException> { withTimeout(5000) { raw.write(byteArrayOf(1, 2, 3)) } }
            assertEquals(ConnectionState.Closed, raw.state.value)
            assertTrue(socket.isClosed); assertEquals(listOf(10L), api.closed)
        } finally { raw.close() }
        assertEquals(listOf(10L), api.closed)
    }
    @Test fun blockedNativeReadCancellationClosesAndDrainsWithoutAnExtraDescriptorClose() = runBlocking {
        val entered = CountDownLatch(1); val released = CountDownLatch(1)
        val api = object : FakeMacLanCalls() {
            override fun read(handle: Long, bytes: ByteArray, offset: Int, length: Int): Int = -35
            override fun poll(handle: Long, writable: Int, timeout: Int): Int {
                entered.countDown(); released.await(timeout.toLong(), TimeUnit.MILLISECONDS); return 0
            }
            override fun close(handle: Long): Int { released.countDown(); return super.close(handle) }
        }
        val socket = fakeMacSocket(api); val raw = JvmRawConnection(socket)
        val reader = launch(Dispatchers.Default) { raw.read().collect { error("No payload expected") } }
        try {
            assertTrue(withContext(Dispatchers.IO) { entered.await(5, TimeUnit.SECONDS) })
            withTimeout(5000) { reader.cancelAndJoin() }
            assertTrue(socket.isClosed); assertEquals(listOf(10L), api.closed)
        } finally { raw.close(); reader.cancelAndJoin() }
    }
    @Test fun nativeCleanupQuarantineCannotBeHiddenByRawCloseIdempotency() = runBlocking {
        val api = FakeMacLanCalls().apply { closeError = 5 }
        val socket = fakeMacSocket(api); val raw = JvmRawConnection(socket)
        repeat(2) { assertFailsWith<IOException> { raw.close() } }
        assertEquals(listOf(10L), api.closed)
    }
}
