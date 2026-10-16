package dev.p2pkit.transport.lan

import java.io.IOException
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.SocketException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import kotlin.concurrent.thread
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

internal open class FakeMacLanCalls : MacLanCalls {
    val closed = mutableListOf<Long>()
    var openError = 0
    var closeError = 0
    var scope = 7
    var childScope = 7
    var next = 10L
    var accepted = 0L
    var acceptError = 0
    var writeLimit = 65536
    val written = mutableListOf<Byte>()
    var localIp = byteArrayOf(10, 1, 2, 3)
    var remoteIp = byteArrayOf(10, 1, 2, 4)
    override fun open(index: Int, output: LongArray): Int { output[0] = next++; return openError }
    override fun bind(handle: Long, address: ByteArray, port: Int): Int = 0
    override fun listen(handle: Long, backlog: Int): Int = 0
    override fun accept(handle: Long, output: LongArray): Int { output[0] = accepted; return acceptError }
    override fun connect(handle: Long, address: ByteArray, port: Int): Int = 0
    override fun connected(handle: Long): Int = 0
    override fun endpoint(handle: Long, remote: Int, address: ByteArray, port: IntArray): Int {
        (if (remote == 0) localIp else remoteIp).copyInto(address)
        port[0] = if (remote == 0) 3456 else 4321
        return 0
    }
    override fun boundInterface(handle: Long, output: IntArray): Int {
        output[0] = if (handle == accepted && accepted != 0L) childScope else scope
        return 0
    }
    override fun option(handle: Long, option: Int, enabled: Int): Int = 0
    override fun read(handle: Long, bytes: ByteArray, offset: Int, length: Int): Int = 0
    override fun write(handle: Long, bytes: ByteArray, offset: Int, length: Int): Int {
        val count = minOf(length, writeLimit)
        written.addAll(bytes.copyOfRange(offset, offset + count).toList())
        return count
    }
    override fun poll(handle: Long, writable: Int, timeout: Int): Int = 1
    override fun close(handle: Long): Int { synchronized(closed) { closed += handle }; return closeError }
}
internal fun fakeMacErrnos(): MacLanErrnos = MacLanErrnos(intArrayOf(35, 35, 4, 36, 37, 57, 22, 9))
internal fun fakeMacSocket(api: FakeMacLanCalls): MacLanSocket =
    MacLanSocket(api, fakeMacErrnos(), { 7 }).apply {
        bind(InetSocketAddress(InetAddress.getByAddress(api.localIp), 0))
        connect(InetSocketAddress(InetAddress.getByAddress(api.remoteIp), 4321), 1500)
    }

class MacLanSocketTest {
    @Test fun inertConstructionAndEmptyCloseNeverOpenANativeHandle() {
        val api = FakeMacLanCalls()
        val socket = MacLanSocket(api, fakeMacErrnos(), { error("No preparation") })
        socket.close(); socket.close(); socket.requireReleased()
        assertTrue(api.closed.isEmpty()); assertEquals(10L, api.next)
    }
    @Test fun failedOpenRetainsReturnedHandleAndCloseIsExactlyOnce() {
        val api = FakeMacLanCalls().apply { openError = 22 }
        val owner = MacLanHandle(api)
        assertFailsWith<IOException> { owner.open(7) }
        owner.close(); owner.close()
        assertEquals(listOf(10L), api.closed)
    }
    @Test fun closeFailureStaysQuarantinedAndNeverRetriesDescriptor() {
        val api = FakeMacLanCalls().apply { closeError = 5 }
        val failures = mutableListOf<Throwable>()
        val owner = MacLanHandle(api, retainFailure = failures::add)
        owner.open(7)
        repeat(3) { assertFailsWith<IOException> { owner.close() } }
        assertFailsWith<IOException> { owner.requireReleased() }
        assertEquals(1, failures.size); assertEquals(listOf(10L), api.closed)
    }
    @Test fun concurrentCloseWaitsForActualReleaseAndRepeatsNoNativeCall() {
        val entered = CountDownLatch(1); val release = CountDownLatch(1)
        val api = object : FakeMacLanCalls() {
            override fun close(handle: Long): Int {
                entered.countDown(); check(release.await(5, TimeUnit.SECONDS)); return super.close(handle)
            }
        }
        val owner = MacLanHandle(api); owner.open(7)
        val error = AtomicReference<Throwable?>()
        val first = thread { try { owner.close() } catch (failure: Throwable) { error.set(failure) } }
        assertTrue(entered.await(5, TimeUnit.SECONDS))
        val secondDone = CountDownLatch(1)
        val second = thread { try { owner.close() } finally { secondDone.countDown() } }
        assertFalse(secondDone.await(30, TimeUnit.MILLISECONDS))
        release.countDown(); first.join(5000); second.join(5000)
        assertFalse(first.isAlive); assertFalse(second.isAlive); assertEquals(null, error.get())
        assertEquals(listOf(10L), api.closed)
    }
    @Test fun sourceScopeMismatchFailsBeforeConnectAndRetainsOwnership() {
        val api = FakeMacLanCalls().apply { scope = 9 }
        val socket = MacLanSocket(api, fakeMacErrnos(), { 7 })
        assertFailsWith<SocketException> {
            socket.bind(InetSocketAddress(InetAddress.getByAddress(api.localIp), 0))
        }
        socket.close(); assertEquals(listOf(10L), api.closed)
    }
    @Test fun partialWritesAreCompleteAndBoundedWithoutExtraPayload() {
        val api = FakeMacLanCalls().apply { writeLimit = 7 }
        val socket = fakeMacSocket(api)
        val bytes = ByteArray(131073) { (it % 97).toByte() }
        try { socket.getOutputStream().write(bytes); assertEquals(bytes.toList(), api.written) }
        finally { socket.close() }
    }
    @Test fun streamBoundsZeroLengthAndEofAreExact() {
        val api = FakeMacLanCalls(); val socket = fakeMacSocket(api)
        try {
            assertEquals(0, socket.getInputStream().read(ByteArray(0), 0, 0))
            assertEquals(-1, socket.getInputStream().read())
            assertFailsWith<IndexOutOfBoundsException> { socket.getInputStream().read(ByteArray(2), 2, 1) }
            assertFailsWith<IndexOutOfBoundsException> { socket.getOutputStream().write(ByteArray(2), -1, 1) }
        } finally { socket.close() }
    }
    @Test fun failedAcceptedSetupRetainsAndClosesChildBeforePropagating() {
        val api = FakeMacLanCalls().apply { accepted = 20; acceptError = 22 }
        val listener = MacLanServerSocket(api, fakeMacErrnos(), { 7 })
        listener.bind(InetSocketAddress(InetAddress.getByAddress(api.localIp), 0))
        assertFailsWith<IOException> { listener.accept() }
        listener.close(); assertEquals(listOf(20L, 10L), api.closed)
    }
    @Test fun inheritedScopeMismatchIsRejectedNotRepaired() {
        val api = FakeMacLanCalls().apply { accepted = 20; childScope = 9 }
        val listener = MacLanServerSocket(api, fakeMacErrnos(), { 7 })
        listener.bind(InetSocketAddress(InetAddress.getByAddress(api.localIp), 0))
        assertFailsWith<IOException> { listener.accept() }
        listener.close(); assertEquals(listOf(20L, 10L), api.closed)
    }
    @Test fun failedChildCloseMakesListenerRetirementFailWithoutNativeRetry() {
        val api = FakeMacLanCalls().apply { accepted = 20; acceptError = 22; closeError = 5 }
        val listener = MacLanServerSocket(api, fakeMacErrnos(), { 7 })
        listener.bind(InetSocketAddress(InetAddress.getByAddress(api.localIp), 0))
        assertFailsWith<IOException> { listener.accept() }
        repeat(2) { assertFailsWith<IOException> { listener.close() } }
        assertEquals(listOf(20L, 10L), api.closed)
    }
    @Test fun acceptingChildCannotEscapeConcurrentListenerClose() {
        val entered = CountDownLatch(1); val release = CountDownLatch(1)
        val api = object : FakeMacLanCalls() {
            override fun accept(handle: Long, output: LongArray): Int {
                entered.countDown(); check(release.await(5, TimeUnit.SECONDS)); output[0] = 20; return 0
            }
            override fun close(handle: Long): Int { if (handle == 10L) release.countDown(); return super.close(handle) }
        }.apply { accepted = 20 }
        val listener = MacLanServerSocket(api, fakeMacErrnos(), { 7 })
        listener.bind(InetSocketAddress(InetAddress.getByAddress(api.localIp), 0))
        val outcome = AtomicReference<Throwable?>()
        val worker = thread { try { listener.accept(); error("Retired child escaped") }
            catch (failure: Throwable) { outcome.set(failure) } }
        assertTrue(entered.await(5, TimeUnit.SECONDS)); listener.close(); worker.join(5000)
        assertFalse(worker.isAlive); assertTrue(outcome.get() is IOException)
        assertEquals(setOf(10L, 20L), api.closed.toSet()); assertEquals(2, api.closed.size)
    }
}
