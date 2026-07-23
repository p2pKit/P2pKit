package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.ExplicitSecurityRisk
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.dsl.jvmSecureIdentityStore
import dev.p2pkit.core.transfer.FileTransferState
import dev.p2pkit.core.transfer.durableFileDestination
import dev.p2pkit.core.transfer.sendFile
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import java.io.File
import java.net.Inet4Address
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.NetworkInterface
import java.net.ServerSocket
import java.net.Socket
import java.nio.file.Files
import java.security.MessageDigest
import kotlin.test.AfterTest
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue
import org.junit.Assume

/**
 * Integration test: two [P2pKit] instances on `127.0.0.1`, both using the
 * `lan()` transport, discover each other via mDNS and exchange messages over
 * TCP.
 *
 * This test depends on multicast working on the test machine (UDP 5353 to
 * 224.0.0.251). Most desktops are fine; corporate or hardened networks may
 * block multicast even on loopback. Allow up to 30 s for discovery.
 */
@OptIn(ExplicitSecurityRisk::class)
@Suppress("DEPRECATION")
class JvmLanLoopbackTest {

    private val unique = "p2pkit-itest-${System.currentTimeMillis()}"
    private var globalStateLease: JvmGlobalStateTestGuard.Lease? = null

    /**
     * Pin JmDNS to a routable IPv4 interface for these tests. On macOS,
     * `InetAddress.getLocalHost()` resolves to 127.0.0.1 when the machine's
     * `.local` hostname isn't published on the LAN; JmDNS then binds to the
     * loopback interface and `selectRoutableHost` (in production code) drops
     * the resulting hints because they're loopback addresses. Pinning to a
     * non-loopback IPv4 sidesteps that and gives the test a deterministic
     * interface to discover on. Production callers don't set this property.
     */
    @BeforeTest
    fun setupBindAddress() {
        val routable = findRoutableIpv4()
        Assume.assumeTrue(
            "No routable IPv4 interface available for JmDNS loopback test",
            routable != null
        )
        globalStateLease = JvmGlobalStateTestGuard.acquire(JMDNS_BIND_PROPERTY, "user.home")
        globalStateLease?.set(JMDNS_BIND_PROPERTY, routable!!)
    }

    private fun newKit(name: String): P2pKit = P2pKit.create {
        appId = AppId(unique)
        deviceName = name
        jvmSecureIdentityStore(InMemoryTestJvmSecureIdentityStore())
        security {
            mode = SecurityMode.AuthenticatedV2(
                PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
            )
        }
        keepAlive {
            pingIntervalMillis = 60_000
            timeoutMillis = 120_000
        }
        transports {
            lan()
        }
    }

    private val toStop = mutableListOf<P2pKit>()
    private val tempHomes = mutableListOf<File>()

    @AfterTest
    fun teardown() {
        try {
            runBlocking {
                toStop.forEach { runCatching { it.stop() } }
                toStop.clear()
                tempHomes.forEach { runCatching { it.deleteRecursively() } }
                tempHomes.clear()
            }
        } finally {
            globalStateLease?.close()
            globalStateLease = null
        }
    }

    /**
     * Construct a [P2pKit] under a per-call temporary `user.home`. This forces
     * the default JVM [dev.p2pkit.core.internal.PeerIdStorage] to write under a
     * fresh directory, so two kits in the same JVM (sharing an `appId`) end up
     * with **different** `PeerId`s — otherwise each would filter the other
     * out of mDNS results as "self". The `user.home` swap is restored
     * synchronously after [P2pKit.create] returns; the kit captures its
     * `PeerId` at construction so later `user.home` changes don't affect it.
     */
    private suspend fun startAndAdvertise(name: String): P2pKit {
        val tempHome = Files.createTempDirectory("p2pkit-itest-${name}-").toFile()
        tempHomes.add(tempHome)
        val lease = checkNotNull(globalStateLease) { "global-state fixture was not acquired" }
        val kit = lease.withValue("user.home", tempHome.absolutePath) {
            newKit(name)
        }
        toStop.add(kit)
        kit.startAdvertising()
        kit.startDiscovery()
        return kit
    }

    @Test
    fun twoKitsDiscoverEachOtherAndExchangeText() {
        runBlocking {
            val alice = startAndAdvertise("Alice")
            val bob = startAndAdvertise("Bob")

            val bobAsSeenByAlice = withTimeout(DISCOVERY_TIMEOUT_MS) {
                alice.peers.first { peers -> peers.any { it.name == "Bob" } }
                    .first { it.name == "Bob" }
            }

            val outgoingDeferred = async { alice.connect(bobAsSeenByAlice) }
            val incomingSession = withTimeout(HANDSHAKE_TIMEOUT_MS) { bob.incomingSessions.first() }
            val outgoing = withTimeout(HANDSHAKE_TIMEOUT_MS) { outgoingDeferred.await() }

            assertEquals("Alice", incomingSession.peer.name)
            assertEquals("Bob", outgoing.peer.name)

            // Alice → Bob text
            val ready = CompletableDeferred<Unit>()
            val received = async {
                incomingSession.incoming.onSubscription { ready.complete(Unit) }.first()
            }
            ready.await()
            outgoing.send(P2pMessage.Text("hi from Alice"))
            val msg = assertIs<P2pMessage.Text>(withTimeout(MESSAGE_TIMEOUT_MS) { received.await() })
            assertEquals("hi from Alice", msg.value)
        }
    }

    @Test
    fun largeBinaryPayloadRoundTripsOverTcp() {
        runBlocking {
            val alice = startAndAdvertise("Alice")
            val bob = startAndAdvertise("Bob")

            val bobAsSeenByAlice = withTimeout(DISCOVERY_TIMEOUT_MS) {
                alice.peers.first { peers -> peers.any { it.name == "Bob" } }
                    .first { it.name == "Bob" }
            }
            val outgoingDeferred = async { alice.connect(bobAsSeenByAlice) }
            val incomingSession = withTimeout(HANDSHAKE_TIMEOUT_MS) { bob.incomingSessions.first() }
            val outgoing = withTimeout(HANDSHAKE_TIMEOUT_MS) { outgoingDeferred.await() }

            // 200 KB — well over the default 64 KB chunk size, so this also
            // exercises chunking + reassembly over a real TCP socket.
            val payload = ByteArray(200 * 1024) { (it and 0xFF).toByte() }

            val ready = CompletableDeferred<Unit>()
            val received = async {
                outgoing.incoming.onSubscription { ready.complete(Unit) }.first()
            }
            ready.await()
            incomingSession.send(P2pMessage.Binary(payload))
            val bin = assertIs<P2pMessage.Binary>(withTimeout(MESSAGE_TIMEOUT_MS) { received.await() })
            assertContentEquals(payload, bin.bytes)
        }
    }

    @Test
    fun fileTransferRoundTripsOverTcpWithMatchingHash() {
        runBlocking {
            val alice = startAndAdvertise("Alice")
            val bob = startAndAdvertise("Bob")

            val bobAsSeenByAlice = withTimeout(DISCOVERY_TIMEOUT_MS) {
                alice.peers.first { peers -> peers.any { it.name == "Bob" } }
                    .first { it.name == "Bob" }
            }
            val outgoingDeferred = async { alice.connect(bobAsSeenByAlice) }
            val incomingSession = withTimeout(HANDSHAKE_TIMEOUT_MS) { bob.incomingSessions.first() }
            val outgoing = withTimeout(HANDSHAKE_TIMEOUT_MS) { outgoingDeferred.await() }

            // 5 MiB temp file with reproducible content so the receiver-side
            // hash check is deterministic.
            val srcFile = Files.createTempFile("p2pkit-itest-src-", ".bin").toFile()
            tempFiles.add(srcFile)
            val dstFile = Files.createTempFile("p2pkit-itest-dst-", ".bin").toFile()
            tempFiles.add(dstFile)

            val random = java.util.Random(20260516L)
            val totalBytes = 5L * 1024 * 1024
            val payloadHashHex = computeHash(srcFile.also { f ->
                f.outputStream().use { out ->
                    val buf = ByteArray(64 * 1024)
                    var written = 0L
                    while (written < totalBytes) {
                        val want = minOf(buf.size.toLong(), totalBytes - written).toInt()
                        random.nextBytes(buf)
                        out.write(buf, 0, want)
                        written += want
                    }
                }
            })

            // Subscribe to incomingFiles BEFORE the sender opens the offer.
            val offerReady = CompletableDeferred<Unit>()
            val offerDeferred = async {
                incomingSession.incomingFiles.onSubscription { offerReady.complete(Unit) }.first()
            }
            offerReady.await()

            val transfer = outgoing.sendFile(srcFile).also {
                val offer = withTimeout(MESSAGE_TIMEOUT_MS) { offerDeferred.await() }
                val incomingTransfer = offer.accept(durableFileDestination(dstFile))
                val senderFinal = withTimeout(FILE_TRANSFER_TIMEOUT_MS) {
                    it.state.first { s ->
                        s is FileTransferState.Completed || s is FileTransferState.Failed
                    }
                }
                val receiverFinal = withTimeout(FILE_TRANSFER_TIMEOUT_MS) {
                    incomingTransfer.state.first { s ->
                        s is FileTransferState.Completed || s is FileTransferState.Failed
                    }
                }
                assertIs<FileTransferState.Completed>(senderFinal)
                assertIs<FileTransferState.Completed>(receiverFinal)
            }
            assertEquals(srcFile.length(), transfer.bytesTransferred.value)
            assertEquals(srcFile.length(), dstFile.length())
            assertEquals(payloadHashHex, computeHash(dstFile))
        }
    }

    /**
     * AUDIT-2026-06 fd-leak fix: a remote-initiated disconnect must close the
     * LOCAL socket fd, not just flip the connection state to Closed.
     *
     * The public P2pKit harness cannot reach the underlying [java.net.Socket]
     * (sessions wrap the raw connection privately), so this test drives
     * [JvmRawConnection] directly over a real loopback TCP pair — that is the
     * exact object the fix lives in, and `socket.isClosed` is the direct
     * observable. Pre-fix, the read loop set state to Closed without closing
     * the socket, and close() early-returned on Closed, leaking the fd.
     */
    @Test
    fun remoteDisconnectClosesLocalSocketFd() {
        runBlocking {
            val server = ServerSocket(0, 1, InetAddress.getLoopbackAddress())
            try {
                val localSocket = Socket()
                localSocket.connect(
                    InetSocketAddress(InetAddress.getLoopbackAddress(), server.localPort),
                    5_000
                )
                val remoteSide = server.accept()
                val connection = JvmRawConnection(localSocket)

                // Consume the read flow the way the protocol reader does; the
                // EOF from the remote close ends the loop.
                val reader = launch { connection.read().collect { } }

                remoteSide.close()

                withTimeout(MESSAGE_TIMEOUT_MS) {
                    connection.state.first { it == ConnectionState.Closed }
                }
                withTimeout(MESSAGE_TIMEOUT_MS) { reader.join() }

                assertTrue(
                    localSocket.isClosed,
                    "remote disconnect must close the local socket fd (not just state)"
                )

                // close() after a remote-initiated close stays a safe no-op.
                connection.close()
                assertEquals(ConnectionState.Closed, connection.state.value)
                assertTrue(localSocket.isClosed)
            } finally {
                runCatching { server.close() }
            }
        }
    }

    private fun computeHash(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { stream ->
            val buf = ByteArray(64 * 1024)
            while (true) {
                val n = stream.read(buf)
                if (n <= 0) break
                digest.update(buf, 0, n)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    private val tempFiles: MutableList<File> = mutableListOf()

    @AfterTest
    fun cleanupTempFiles() {
        tempFiles.forEach { runCatching { it.delete() } }
        tempFiles.clear()
    }

    private companion object {
        const val DISCOVERY_TIMEOUT_MS: Long = 30_000
        const val HANDSHAKE_TIMEOUT_MS: Long = 10_000
        const val MESSAGE_TIMEOUT_MS: Long = 10_000
        const val FILE_TRANSFER_TIMEOUT_MS: Long = 60_000
        const val JMDNS_BIND_PROPERTY: String = "dev.p2pkit.test.jmdnsBindAddress"

        /**
         * First IPv4 address on an up, non-loopback interface, excluding
         * link-local (169.254/16) which JmDNS multicast doesn't reliably
         * traverse on macOS. Returns `null` when no such interface exists
         * (CI sandboxes with only loopback, network-off laptops); the
         * caller skips the test in that case.
         */
        fun findRoutableIpv4(): String? {
            val interfaces = NetworkInterface.getNetworkInterfaces() ?: return null
            for (iface in interfaces) {
                if (!iface.isUp || iface.isLoopback) continue
                for (addr in iface.inetAddresses) {
                    if (addr !is Inet4Address) continue
                    if (addr.isLoopbackAddress || addr.isLinkLocalAddress) continue
                    return addr.hostAddress
                }
            }
            return null
        }
    }
}
