package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.DiscoveryTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportHint
import dev.p2pkit.core.transport.TransportPair
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.async
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import java.io.File
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.nio.file.Files
import java.util.concurrent.CopyOnWriteArrayList
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * AUDIT-2026-07 (CON-3) / coverage plan P1-04, integration half: the inbound
 * accept path over a REAL `ServerSocket` + real loopback TCP, full [P2pKit]
 * instances on both sides. No mDNS — the dialing kit learns the accepting
 * kit's endpoint through a stub [DiscoveryTransport], keeping the test
 * deterministic.
 *
 *  1. A non-conforming inbound TCP connection (accepted, then immediately
 *     terminated by the remote) fails per-connection setup only: the accept
 *     loop stays live and a subsequent well-formed inbound connection still
 *     yields a working session.
 *  2. The real `ServerSocket` closed underneath the live accept loop (the
 *     accept-error signature, e.g. when the process fd limit is reached) is
 *     surfaced through the injectable logger; the kit survives — established
 *     sessions keep working — and shutdown still completes promptly.
 */
class JvmLanAcceptLoopResilienceTest {

    private val unique = "p2pkit-itest-accept-${System.currentTimeMillis()}"

    private val toStop = mutableListOf<P2pKit>()
    private val tempHomes = mutableListOf<File>()

    @AfterTest
    fun teardown() {
        runBlocking {
            toStop.forEach { runCatching { it.stop() } }
            toStop.clear()
            tempHomes.forEach { runCatching { it.deleteRecursively() } }
            tempHomes.clear()
        }
    }

    @Test
    fun perConnectionSetupFailureKeepsAcceptLoopLiveForSubsequentPeers() {
        runBlocking {
            val bobLogger = TestRecordingLogger()
            val bobTransport = newLanTransport("Bob")
            val bob = newKit("Bob", bobLogger, PairFactory(bobTransport))
            bob.start()
            val bobPort = requireNotNull(bobTransport.tcpPort.value)

            // Non-conforming inbound connection: accepted by the real accept
            // loop, then the remote end goes away before any HELLO. Setup for
            // this one connection must fail in isolation.
            Socket().use { s ->
                s.connect(
                    InetSocketAddress(InetAddress.getLoopbackAddress(), bobPort),
                    CONNECT_TIMEOUT_MS.toInt()
                )
            }
            awaitTrue("per-connection setup failure surfaced via logger") {
                bobLogger.warnings().any { it.contains("Incoming session setup failed") }
            }

            // The accept loop must still be live: a well-formed inbound
            // connection from a real peer kit still produces a session.
            val stub = StubDiscovery()
            val alice = newKit(
                "Alice",
                TestRecordingLogger(),
                PairFactory(newLanTransport("Alice"), stub)
            )
            val (outgoing, incoming) = establishSession(alice, bob, stub, bobPort)
            assertEquals("Alice", incoming.peer.name)
            assertEquals("Bob", outgoing.peer.name)
            val msg = exchangeMessage(outgoing, incoming, P2pMessage.Text("post-failure hello"))
            assertEquals("post-failure hello", assertIs<P2pMessage.Text>(msg).value)

            // The isolated failure never terminated the loop or escalated.
            assertTrue(
                bobLogger.warnings().none { it.contains("inbound acceptance ended") },
                "a per-connection setup failure must not end inbound acceptance"
            )
            assertTrue(
                bobLogger.errors().isEmpty(),
                "no kit-scope escalation expected, got: ${bobLogger.errors()}"
            )
        }
    }

    @Test
    fun serverSocketClosedUnderLoopIsSurfacedAndKitSurvives() {
        runBlocking {
            val bobLogger = TestRecordingLogger()
            val bobTransport = newLanTransport("Bob")
            val bob = newKit("Bob", bobLogger, PairFactory(bobTransport))
            bob.start()
            val bobPort = requireNotNull(bobTransport.tcpPort.value)

            val stub = StubDiscovery()
            val alice = newKit(
                "Alice",
                TestRecordingLogger(),
                PairFactory(newLanTransport("Alice"), stub)
            )
            val (outgoing, incoming) = establishSession(alice, bob, stub, bobPort)
            val sanity = exchangeMessage(outgoing, incoming, P2pMessage.Text("before"))
            assertEquals("before", assertIs<P2pMessage.Text>(sanity).value)

            // Close the REAL ServerSocket underneath the live accept loop —
            // accept() fails while the transport is not closed, terminating
            // the transport's incoming flow with a cause (P1-04 scenario).
            closeServerSocketUnderLoop(bobTransport)

            // The failure is surfaced through the injectable logger...
            awaitTrue("accept-loop failure surfaced via logger") {
                bobLogger.warnings().any { it.contains("inbound acceptance ended") }
            }

            // ...and the kit survives: the established session (its socket is
            // independent of the listener) still exchanges messages, and no
            // uncaught failure reached the kit scope.
            val after = exchangeMessage(outgoing, incoming, P2pMessage.Text("after accept-loop failure"))
            assertEquals("after accept-loop failure", assertIs<P2pMessage.Text>(after).value)
            assertTrue(
                bobLogger.errors().isEmpty(),
                "accept-loop failure must not escalate to the kit scope, got: ${bobLogger.errors()}"
            )

            // Shutdown still terminates promptly after the accept-loop failure.
            withTimeout(STOP_TIMEOUT_MS) { bob.stop() }
            withTimeout(STOP_TIMEOUT_MS) { alice.stop() }
        }
    }

    // ---------------------------------------------------------------------
    // Harness
    // ---------------------------------------------------------------------

    private fun newLanTransport(name: String): JvmLanDataTransport =
        JvmLanDataTransport(
            LanServiceRegistration(
                appId = AppId(unique),
                localPeerId = PeerId("$name-registration"),
                deviceName = name,
                platform = Platform.JVM_DESKTOP
            )
        )

    /**
     * Build a kit under a per-call temporary `user.home` so two kits in one
     * JVM get distinct persisted PeerIds (same trick as [JvmLanLoopbackTest]).
     */
    private fun newKit(name: String, kitLogger: P2pLogger, factory: TransportFactory): P2pKit {
        val savedHome = System.getProperty("user.home")
        val tempHome = Files.createTempDirectory("p2pkit-itest-$name-").toFile()
        tempHomes.add(tempHome)
        System.setProperty("user.home", tempHome.absolutePath)
        val kit = try {
            P2pKit.create {
                appId = AppId(unique)
                deviceName = name
                logger = kitLogger
                keepAlive {
                    pingIntervalMillis = 60_000
                    timeoutMillis = 120_000
                }
                transports {
                    register(factory)
                }
            }
        } finally {
            System.setProperty("user.home", savedHome ?: "")
        }
        toStop.add(kit)
        return kit
    }

    /**
     * Announce Bob's endpoint to Alice through the stub discovery, then dial
     * and return (outgoing, incoming) sessions.
     */
    private suspend fun CoroutineScope.establishSession(
        alice: P2pKit,
        bob: P2pKit,
        stub: StubDiscovery,
        bobPort: Int
    ): Pair<P2pSession, P2pSession> {
        val bobPeer = Peer(
            id = bob.localPeerId,
            name = "Bob",
            platform = Platform.JVM_DESKTOP,
            supportedTransports = setOf(TransportKind.LAN)
        )
        stub.announce(
            InternalPeer(
                publicPeer = bobPeer,
                transportHints = listOf(
                    TransportHint(type = TransportKind.LAN, host = "127.0.0.1", port = bobPort)
                )
            )
        )
        // Wait until Alice's registry has processed the announcement so
        // connect() resolves real transport hints.
        withTimeout(CONNECT_TIMEOUT_MS) {
            alice.peers.first { peers -> peers.any { it.id == bobPeer.id } }
        }
        val ready = CompletableDeferred<Unit>()
        val incomingDeferred = async {
            bob.incomingSessions.onSubscription { ready.complete(Unit) }.first()
        }
        ready.await()
        val outgoing = withTimeout(CONNECT_TIMEOUT_MS) { alice.connect(bobPeer) }
        val incoming = withTimeout(CONNECT_TIMEOUT_MS) { incomingDeferred.await() }
        return outgoing to incoming
    }

    private suspend fun exchangeMessage(
        from: P2pSession,
        to: P2pSession,
        payload: P2pMessage
    ): P2pMessage = kotlinx.coroutines.coroutineScope {
        val ready = CompletableDeferred<Unit>()
        val received = async {
            to.incoming.onSubscription { ready.complete(Unit) }.first()
        }
        ready.await()
        from.send(payload)
        withTimeout(MESSAGE_TIMEOUT_MS) { received.await() }
    }

    /**
     * Reach the transport's live [ServerSocket] and close it while the accept
     * loop is blocked in `accept()`. Reflection because the field is
     * intentionally private in production code; the coverage plan's P1-04 row
     * explicitly calls for "a real ServerSocket closed under the loop".
     */
    private fun closeServerSocketUnderLoop(transport: JvmLanDataTransport) {
        val field = JvmLanDataTransport::class.java.getDeclaredField("serverSocket")
        field.isAccessible = true
        val sock = field.get(transport) as ServerSocket
        sock.close()
    }

    private suspend fun awaitTrue(what: String, condition: () -> Boolean) {
        try {
            withTimeout(AWAIT_TIMEOUT_MS) {
                while (!condition()) delay(20)
            }
        } catch (e: kotlinx.coroutines.TimeoutCancellationException) {
            throw AssertionError("Timed out after ${AWAIT_TIMEOUT_MS}ms waiting for: $what", e)
        }
    }

    private companion object {
        const val CONNECT_TIMEOUT_MS: Long = 10_000
        const val MESSAGE_TIMEOUT_MS: Long = 10_000
        const val AWAIT_TIMEOUT_MS: Long = 10_000
        const val STOP_TIMEOUT_MS: Long = 10_000
    }
}

/** Thread-safe recording [P2pLogger] (the commonTest fixture isn't published). */
private class TestRecordingLogger : P2pLogger {
    private val warnList = CopyOnWriteArrayList<String>()
    private val errorList = CopyOnWriteArrayList<String>()
    override fun debug(message: String) {}
    override fun info(message: String) {}
    override fun warn(message: String, throwable: Throwable?) {
        warnList.add(message)
    }

    override fun error(message: String, throwable: Throwable?) {
        errorList.add(message)
    }

    fun warnings(): List<String> = warnList.toList()
    fun errors(): List<String> = errorList.toList()
}

/** Emits scripted [PeerEvent]s; replay so an announce is never lost. */
private class StubDiscovery : DiscoveryTransport {
    override val type: TransportKind = TransportKind.LAN
    private val _events = MutableSharedFlow<PeerEvent>(replay = 8)
    override val events: Flow<PeerEvent> = _events
    fun announce(peer: InternalPeer) {
        check(_events.tryEmit(PeerEvent.Found(peer))) { "announce buffer full" }
    }

    override suspend fun startAdvertising(localPeer: LocalPeerInfo) {}
    override suspend fun stopAdvertising() {}
    override suspend fun startDiscovery() {}
    override suspend fun stopDiscovery() {}
}

private class PairFactory(
    private val data: JvmLanDataTransport,
    private val discovery: DiscoveryTransport? = null
) : TransportFactory {
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = data, discovery = discovery)
}
