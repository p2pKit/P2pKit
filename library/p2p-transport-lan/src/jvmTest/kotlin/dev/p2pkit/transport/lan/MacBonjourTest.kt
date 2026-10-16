package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.TransportSecurityProfile
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import java.io.IOException
import java.net.InetAddress
import java.nio.ByteBuffer
import kotlin.text.CharacterCodingException
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.ConcurrentLinkedQueue
import java.util.concurrent.atomic.AtomicLong
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Portable deterministic contracts; fake DNS-SD does not claim network or physical interoperability. */
class MacBonjourTest {
    private val policy = OrganizationLan(listOf("192.168.9.0/24"), "en0", "192.168.9.2")
    private val peer = LocalPeerInfo(PeerId("local"), "Local", Platform.JVM_DESKTOP, AppId("bonjour-test"),
        setOf(TransportKind.LAN))
    private val registration = LanServiceRegistration(peer.appId, peer.peerId, peer.deviceName, peer.platform,
        TransportSecurityProfile.AuthenticatedV2, PeerFingerprint("p2f1-" + "a".repeat(52)), 3456, policy.localAddress)
    private val network = JvmLanInterfaceSnapshot("en0", true, false, false, false, true,
        listOf(LanInterfaceAddress(InetAddress.getByAddress(byteArrayOf(192.toByte(), 168.toByte(), 9, 2)), 24)))
    private val snapshot = JvmLanSocketSnapshot(listOf(network), emptySet(), mapOf("en0" to 7))
    private fun frame(kind: Int, name: String = "remote", port: Int = 0, txt: ByteArray = byteArrayOf()): ByteArray {
        val bytes = name.encodeToByteArray()
        return ByteBuffer.allocate(2048).putInt(kind).putInt(0).putInt(7).putInt(port)
            .putInt(bytes.size).putInt(txt.size).put(bytes).put(txt).array()
    }
    private fun remote(address: String = "192.168.9.3", port: Int = 3456): MacBonjourEvent {
        val value = LanServiceRegistration(peer.appId, PeerId("remote"), "Remote", Platform.ANDROID,
            registration.securityProfile, registration.fingerprint, port, address)
        val info = buildJmdnsServiceInfo(value, peer)
        return MacBonjourEvent(3, 7, "remote", port, info.textBytes)
    }

    @Test fun explicitIndexSelectionDoesNotPretendPortableSourceBindingIsScoped() {
        val multihomed = snapshot.copy(
            interfaces = listOf(network, network.copy(name = "utun0", isPointToPoint = true)))
        assertNull(organizationJvmTarget(policy, multihomed.interfaces))
        assertEquals(7, assertNotNull(macBonjourTarget(policy, multihomed)).second)
        assertNull(macBonjourTarget(policy, null))
        assertNull(macBonjourTarget(policy, snapshot.copy(interfaceIndices = emptyMap())))
        assertNull(macBonjourTarget(policy, snapshot.copy(interfaceIndices = mapOf("en0" to 0))))
        for (bad in listOf(network.copy(isUp = false), network.copy(isPointToPoint = true),
            network.copy(isLoopback = true), network.copy(isVirtual = true), network.copy(supportsMulticast = false),
            network.copy(addresses = emptyList()))) {
            assertNull(macBonjourTarget(policy, snapshot.copy(interfaces = listOf(bad))))
        }
        assertNull(macBonjourTarget(policy, snapshot.copy(interfaces = listOf(network, network))))
        assertFalse(macBonjourTarget(policy, snapshot)!!.first ==
            macBonjourTarget(policy, snapshot.copy(interfaceIndices = mapOf("en0" to 8)))!!.first)
    }

    @Test fun frameParserRejectsScopeShapeMalformedUtf8AndSystemErrors() {
        assertEquals("remote", decodeMacBonjourEvent(frame(1), 7).name)
        val valid = frame(3, port = 3456, txt = byteArrayOf(1, 'x'.code.toByte()))
        assertEquals(3456, decodeMacBonjourEvent(valid, 7).port)
        for ((offset, value) in listOf(0 to 0, 0 to 6, 4 to 5, 8 to 8, 12 to -1, 16 to 64, 20 to 1301)) {
            val invalid = valid.copyOf(); ByteBuffer.wrap(invalid).putInt(offset, value)
            assertFailsWith<IllegalStateException> { decodeMacBonjourEvent(invalid, 7) }
        }
        assertFailsWith<IllegalArgumentException> { decodeMacBonjourEvent(ByteArray(2), 7) }
        val invalid = frame(1); invalid[24] = 0xff.toByte()
        assertFailsWith<CharacterCodingException> { decodeMacBonjourEvent(invalid, 7) }
        val padding = frame(1); padding[2047] = 1
        assertFailsWith<IllegalStateException> { decodeMacBonjourEvent(padding, 7) }
        val error = ByteBuffer.allocate(2048).putInt(5).putInt(-65570).putInt(7).array()
        assertTrue(assertFailsWith<IOException> { decodeMacBonjourEvent(error, 7) }.message!!.contains("-65570"))
    }

    @Test fun numericTxtMustMatchIdentityProfileScopeAndSrvWithoutHostnameFallback() {
        assertNotNull(validateMacBonjourRecord(remote(), registration, policy))
        for (value in listOf(remote().copy(name = "other"), remote().copy(kind = 1), remote().copy(port = 4567),
            remote("192.168.10.3"), remote().copy(txt = byteArrayOf(255.toByte())))) {
            assertNull(validateMacBonjourRecord(value, registration, policy))
        }
        val legacy = LanServiceRegistration(peer.appId, PeerId("remote"), "Remote", Platform.ANDROID, tcpPort = 3456)
        val info = buildJmdnsServiceInfo(legacy, peer)
        assertNull(validateMacBonjourRecord(remote().copy(txt = info.textBytes), registration, policy))
        val noNumeric = LanServiceRegistration(peer.appId, PeerId("remote"), "Remote", Platform.ANDROID,
            registration.securityProfile, registration.fingerprint, 3456)
        assertNull(validateMacBonjourRecord(remote().copy(txt = buildJmdnsServiceInfo(noNumeric, peer).textBytes),
            registration, policy))
    }

    @Test fun partialOpenAlwaysHasAnOwnerAndFailedCloseRemainsQuarantined() {
        val api = Fake(); val owner = MacBonjourRef(api, 7)
        api.openError = 42
        assertFailsWith<IOException> { owner.open(1, 2) }
        owner.close(); owner.close()
        assertEquals(1, api.closed.size)
        assertFailsWith<IllegalStateException> { owner.open(1, 2) }
        val bad = Fake(); val ref = MacBonjourRef(bad, 7); ref.open(1, 2); bad.closeError = 9
        assertFailsWith<IOException> { ref.close() }
        assertFailsWith<IOException> { ref.close() }
        assertEquals(1, bad.closeAttempts)
    }

    @Test fun browserRevalidatesRemovesExpiresAndClosesEveryResolver() {
        val api = Fake(); val root = MacBonjourRef(api, 7); root.open(1, 2)
        api.events.values.single().add(frame(1))
        val changes = mutableListOf<Pair<String, MacBonjourEvent?>>()
        var now = 0L
        val browser = MacBonjourBrowser(registration, policy, 7, api, { name, event -> changes += name to event },
            clock = { now })
        var iteration = 0
        browser.run(root, {
            iteration++
            if (iteration == 2) {
                val event = remote()
                api.events[2L]!!.add(frame(3, port = event.port, txt = event.txt))
            }
            if (iteration == 3) now = 3_000_000_000
            if (iteration == 4) now = 5_000_000_000 // unresolved second query times out, withdrawing the old endpoint
            iteration < 5
        }, {})
        browser.verifyClosed(); root.close()
        assertEquals(1, changes.count { it.second != null })
        assertTrue(changes.any { it.second == null })
        assertEquals(api.created.get(), api.closed.size.toLong())
    }

    @Test fun registrationBrowseRefreshAndIndependentStopsLeaveNoWorkerOrReference() = runBlocking {
        val api = Fake()
        api.onOpen = { handle, operation, name ->
            if (operation == 2) api.events[handle]!!.add(frame(4, name))
        }
        val transport = MacBonjourDiscoveryTransport(registration, policy, LanRole.Host, api, { snapshot })
        try {
            transport.startAdvertising(peer)
            transport.startDiscovery()
            transport.refresh()
            transport.stopAdvertising()
            assertTrue(api.closed.size < api.created.get())
            transport.stopDiscovery()
            assertEquals(api.created.get(), api.closed.size.toLong())
            transport.startDiscovery()
            transport.stopDiscovery()
            assertEquals(api.created.get(), api.closed.size.toLong())
        } finally { transport.stopDiscovery(); transport.stopAdvertising() }
    }

    @Test fun dialOnlyAndUnboundRegistrationRejectBeforeNativeAllocation() = runBlocking {
        val api = Fake()
        val dial = MacBonjourDiscoveryTransport(registration, policy, LanRole.DialOnly, api, { snapshot })
        assertFailsWith<IllegalStateException> { dial.startAdvertising(peer) }
        registration.tcpPort = 0
        val host = MacBonjourDiscoveryTransport(registration, policy, LanRole.Host, api, { snapshot })
        assertFailsWith<dev.p2pkit.core.P2pError.TransportStartFailed> { host.startAdvertising(peer) }
        host.stopAdvertising(); host.stopDiscovery()
        assertEquals(0, api.created.get())
    }

    @Test fun freshBrowserWithdrawsOldPeersEvenWithoutARemovalCallback() = runBlocking {
        val api = Fake()
        var browsers = 0
        api.onOpen = { handle, operation, _ ->
            if (operation == 1 && ++browsers == 1) api.events[handle]!!.add(frame(1))
            if (operation == 3) {
                val event = remote()
                api.events[handle]!!.add(frame(3, port = event.port, txt = event.txt))
            }
        }
        val transport = MacBonjourDiscoveryTransport(registration, policy, LanRole.DialOnly, api, { snapshot })
        val events = Channel<PeerEvent>(16)
        val observer = launch { transport.events.collect { events.send(it) } }
        try {
            transport.startDiscovery()
            assertTrue(withTimeout(2000) { events.receive() } is PeerEvent.Found)
            transport.refresh()
            assertEquals(PeerEvent.Lost(PeerId("remote")), withTimeout(2000) { events.receive() })
        } finally {
            transport.stopDiscovery()
            observer.cancelAndJoin()
            events.close()
        }
        assertEquals(api.created.get(), api.closed.size.toLong())
    }

    @Test fun repeatedCallbackFailureBackoffIsBoundedAndDoesNotResetAtEverySuccessfulOpen() {
        var time = 0L
        val backoff = MacBonjourFailureBackoff { time }
        val actual = List(8) { time += 1_000_000_000L; backoff.nextDelay() }
        assertEquals(listOf(1000L, 2000L, 4000L, 8000L, 16000L, 30000L, 30000L, 30000L), actual)
        time += 60_000_000_000L
        assertEquals(1000L, backoff.nextDelay())
    }

    private class Fake : MacBonjourCalls {
        val created = AtomicLong()
        val events = ConcurrentHashMap<Long, ConcurrentLinkedQueue<ByteArray>>()
        val closed = ConcurrentHashMap.newKeySet<Long>()
        var openError = 0
        var closeError = 0
        var closeAttempts = 0
        var onOpen: (Long, Int, String) -> Unit = { _, _, _ -> }
        override fun open(index: Int, operation: Int, profile: Int, name: ByteArray, port: Int,
            txt: ByteArray, output: LongArray): Int {
            assertEquals(7, index)
            val id = created.incrementAndGet(); output[0] = id
            events[id] = ConcurrentLinkedQueue()
            onOpen(id, operation, name.decodeToString())
            return openError
        }
        override fun poll(handle: Long, timeout: Int, output: ByteArray): Int {
            check(handle !in closed)
            val event = events[handle]!!.poll()
            if (event == null) { if (timeout > 0) Thread.sleep(1); return 0 }
            event.copyInto(output); return 1
        }
        @Synchronized override fun close(handle: Long): Int {
            closeAttempts++
            check(closed.add(handle))
            return closeError
        }
    }
}
