package dev.p2pkit.transport.lan

import java.io.IOException
import java.net.InetAddress
import java.net.InetSocketAddress
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import kotlin.concurrent.thread
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class MacLanBindingTest {
    private val policy = OrganizationLan(listOf("10.0.0.0/8"), "en0", "10.1.2.3")
    private val local = InetAddress.getByAddress(byteArrayOf(10, 1, 2, 3))
    private val peer = InetAddress.getByAddress(byteArrayOf(10, 1, 2, 4))
    private val network = JvmLanInterfaceSnapshot("en0", true, false, false, false, true,
        listOf(LanInterfaceAddress(local, 24)))
    private fun snapshot() = JvmLanSocketSnapshot(listOf(network,
        network.copy(name = "utun0", isPointToPoint = true)), setOf(local), mapOf("en0" to 7, "utun0" to 9))

    @Test fun nativeScopeCanAdmitTcpWhilePortableMultihomingGuardStaysRejected() {
        val api = FakeMacLanCalls(); val state = snapshot()
        val binding = MacLanBinding(policy, api, fakeMacErrnos(), { state })
        assertNull(organizationJvmTarget(policy, state.interfaces)); assertNotNull(binding.target())
        binding.activate()
        val socket = binding.socket(); socket.bind(InetSocketAddress(local, 0))
        socket.connect(InetSocketAddress(peer, 4321), 1500)
        assertTrue(binding.allows(socket)); binding.retire(); assertTrue(socket.isClosed)
    }
    @Test fun indexAddressAndTopologyChangesInvalidateActualSocket() {
        var state: JvmLanSocketSnapshot? = snapshot()
        val binding = MacLanBinding(policy, FakeMacLanCalls(), fakeMacErrnos(), { state })
        binding.activate(); val socket = binding.socket(); socket.bind(InetSocketAddress(local, 0))
        socket.connect(InetSocketAddress(peer, 4321), 1500)
        for (invalid in listOf(null, snapshot().copy(interfaceIndices = mapOf("en0" to 8)),
            snapshot().copy(interfaces = listOf(network.copy(isUp = false))),
            snapshot().copy(interfaces = listOf(network.copy(addresses = emptyList()))))) {
            state = invalid; assertFalse(binding.allows(socket))
        }
        binding.retire()
    }
    @Test fun actualScopeMismatchIsRejectedDespiteSameInterfaceInventory() {
        val api = FakeMacLanCalls(); val binding = MacLanBinding(policy, api, fakeMacErrnos(), { snapshot() })
        binding.activate(); val socket = binding.socket(); socket.bind(InetSocketAddress(local, 0))
        socket.connect(InetSocketAddress(peer, 4321), 1500)
        api.scope = 9; assertFalse(binding.allows(socket)); binding.retire()
    }
    @Test fun selfAndOutOfPolicyDestinationsAreRejectedBeforeNativeConnect() {
        var connects = 0
        val api = object : FakeMacLanCalls() {
            override fun connect(handle: Long, address: ByteArray, port: Int): Int { connects++; return 0 }
        }
        val binding = MacLanBinding(policy, api, fakeMacErrnos(), { snapshot() })
        binding.activate()
        for (destination in listOf(local, InetAddress.getByAddress(byteArrayOf(192.toByte(), 168.toByte(), 1, 5)))) {
            val socket = binding.socket(); socket.bind(InetSocketAddress(local, 0))
            assertFailsWith<IOException> { socket.connect(InetSocketAddress(destination, 4321), 1500) }
            socket.close()
        }
        assertEquals(0, connects); binding.retire()
    }
    @Test fun retirementClosesHandedOffConnectionAndRejectsLateAllocationUntilRestart() {
        val api = FakeMacLanCalls(); val binding = MacLanBinding(policy, api, fakeMacErrnos(), { snapshot() })
        binding.activate(); val socket = binding.socket(); socket.bind(InetSocketAddress(local, 0))
        socket.connect(InetSocketAddress(peer, 4321), 1500)
        binding.retire(); binding.retire(); socket.close()
        assertEquals(listOf(10L), api.closed)
        assertFailsWith<IllegalStateException> { binding.socket() }
        binding.activate(); binding.socket().close(); binding.retire()
        assertEquals(listOf(10L), api.closed)
    }
    @Test fun discardedCloseFailureStillPreventsSuccessfulRetirementAndRestart() {
        val api = FakeMacLanCalls().apply { closeError = 5 }
        val binding = MacLanBinding(policy, api, fakeMacErrnos(), { snapshot() })
        binding.activate(); val socket = binding.socket(); socket.bind(InetSocketAddress(local, 0))
        runCatching { socket.close() }
        repeat(2) { assertFailsWith<IOException> { binding.retire() } }
        assertFailsWith<IOException> { binding.activate() }; assertEquals(listOf(10L), api.closed)
    }
    @Test fun retirementWaitsForInFlightCloseAndCannotReportBeforeItsQuarantinedResult() {
        val entered = CountDownLatch(1); val release = CountDownLatch(1)
        val api = object : FakeMacLanCalls() {
            override fun close(handle: Long): Int {
                entered.countDown(); check(release.await(5, TimeUnit.SECONDS)); super.close(handle); return 5
            }
        }
        val binding = MacLanBinding(policy, api, fakeMacErrnos(), { snapshot() })
        binding.activate(); val socket = binding.socket(); socket.bind(InetSocketAddress(local, 0))
        val closer = thread { runCatching { socket.close() } }
        assertTrue(entered.await(5, TimeUnit.SECONDS))
        val done = CountDownLatch(1); val result = AtomicReference<Throwable?>()
        val retire = thread { try { binding.retire() } catch (failure: Throwable) { result.set(failure) }
            finally { done.countDown() } }
        assertFalse(done.await(30, TimeUnit.MILLISECONDS)); release.countDown()
        retire.join(5000); closer.join(5000)
        assertFalse(retire.isAlive); assertFalse(closer.isAlive); assertTrue(result.get() is IOException)
        assertEquals(listOf(10L), api.closed)
    }
    @Test fun retirementOwnsInertCandidateBeforeOpenAndCannotBeRacedByLaterBind() {
        val api = FakeMacLanCalls(); val binding = MacLanBinding(policy, api, fakeMacErrnos(), { snapshot() })
        binding.activate(); val socket = binding.socket(); binding.retire()
        assertFailsWith<IOException> { socket.bind(InetSocketAddress(local, 0)) }
        assertTrue(api.closed.isEmpty()); assertEquals(10L, api.next)
    }
    @Test fun listenerAcceptedChildHandoffRemainsOwnedUntilVerifiedRetirement() {
        val api = FakeMacLanCalls().apply { accepted = 20 }
        val binding = MacLanBinding(policy, api, fakeMacErrnos(), { snapshot() })
        binding.activate(); val listener = binding.listener(); listener.bind(InetSocketAddress(local, 0))
        val child = listener.accept()
        assertTrue(binding.allows(child))
        binding.retire(); binding.retire()
        assertTrue(listener.isClosed); assertTrue(child.isClosed)
        assertEquals(setOf(10L, 20L), api.closed.toSet()); assertEquals(2, api.closed.size)
    }

    @Test fun retirementWaitsForPausedNativeOpenThenClosesItsReturnedHandle() {
        val entered = CountDownLatch(1); val release = CountDownLatch(1)
        val api = object : FakeMacLanCalls() {
            override fun open(index: Int, output: LongArray): Int {
                entered.countDown(); check(release.await(5, TimeUnit.SECONDS)); return super.open(index, output)
            }
        }
        val binding = MacLanBinding(policy, api, fakeMacErrnos(), { snapshot() })
        binding.activate(); val socket = binding.socket()
        val opener = thread { runCatching { socket.bind(InetSocketAddress(local, 0)) } }
        assertTrue(entered.await(5, TimeUnit.SECONDS))
        val done = CountDownLatch(1); val result = AtomicReference<Throwable?>()
        val retire = thread { try { binding.retire() } catch (failure: Throwable) { result.set(failure) }
            finally { done.countDown() } }
        assertFalse(done.await(30, TimeUnit.MILLISECONDS)); release.countDown()
        opener.join(5000); retire.join(5000)
        assertFalse(opener.isAlive); assertFalse(retire.isAlive); assertEquals(null, result.get())
        assertTrue(socket.isClosed); assertEquals(listOf(10L), api.closed)
        binding.activate(); binding.retire()
    }

    @Test fun sealingBeforeRetirementRefusesInertBindAndFurtherCandidates() {
        val api = FakeMacLanCalls(); val binding = MacLanBinding(policy, api, fakeMacErrnos(), { snapshot() })
        binding.activate(); val candidate = binding.socket(); binding.seal()
        assertFailsWith<IOException> { candidate.bind(InetSocketAddress(local, 0)) }
        assertFailsWith<IllegalStateException> { binding.socket() }
        assertTrue(api.closed.isEmpty()); assertEquals(10L, api.next)
        binding.retire(); assertTrue(candidate.isClosed)
    }

}
