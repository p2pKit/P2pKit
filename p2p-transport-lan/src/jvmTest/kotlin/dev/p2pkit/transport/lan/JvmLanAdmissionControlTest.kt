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
import java.net.Socket
import java.net.SocketTimeoutException
import java.nio.file.Files
import java.util.concurrent.CopyOnWriteArrayList
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * AUDIT-2026-07 (SEC-1, decision #9a) / coverage plan P1-26, integration
 * half: inbound admission control over a REAL `ServerSocket` + real loopback
 * TCP with full [P2pKit] instances. K raw sockets that connect and never
 * send HELLO must leave the kit responsive:
 *
 *  - connections past the pre-handshake bound are refused (closed by the
 *    kit with a warn diagnostic, no kit HELLO ever written on them);
 *  - the admitted setups hold bounded resources and an OUTBOUND connect
 *    from the kit still succeeds while inbound capacity is saturated;
 *  - once the non-conforming sockets go away, admission capacity recovers
 *    and a legitimate INBOUND connection produces a working session;
 *  - session count stays bounded and no uncaught exception reaches the kit
 *    scope (kit-scope escalations log at error level).
 *
 * No mDNS — endpoints travel through stub [DiscoveryTransport]s, keeping
 * the test deterministic (same harness as [JvmLanAcceptLoopResilienceTest]).
 */
class JvmLanAdmissionControlTest {

    private val unique = "p2pkit-itest-admission-${System.currentTimeMillis()}"

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
    fun neverHelloConnectionsAreBoundedAndKitStaysResponsive() {
        runBlocking {
            val bobLogger = AdmissionRecordingLogger()
            val bobTransport = newLanTransport("Bob")
            val bobStub = AdmissionStubDiscovery()
            val bob = newKit("Bob", bobLogger, AdmissionPairFactory(bobTransport, bobStub))
            bob.start()
            val bobPort = requireNotNull(bobTransport.tcpPort.value)

            // K raw connections that never send HELLO, all kept open.
            val sockets = List(NEVER_HELLO_COUNT) {
                Socket().also { s ->
                    s.connect(
                        InetSocketAddress(InetAddress.getLoopbackAddress(), bobPort),
                        CONNECT_TIMEOUT_MS.toInt()
                    )
                }
            }
            try {
                // Pre-handshake bound: the excess connections are refused with
                // a warn diagnostic (bound value mirrors the internal
                // MAX_CONCURRENT_PRE_HANDSHAKE_SETUPS policy constant).
                val expectedRefusals = NEVER_HELLO_COUNT - PRE_HANDSHAKE_BOUND
                awaitTrue("$expectedRefusals refusal diagnostics") {
                    bobLogger.warnings().count { it.contains(REFUSAL_FRAGMENT) } >= expectedRefusals
                }

                // fd evidence, per socket: a refused connection was closed by
                // the kit with NOTHING written on it (EOF, no bytes); an
                // admitted one received the kit's HELLO bytes.
                var refusedClosed = 0
                var admitted = 0
                for (s in sockets) {
                    s.soTimeout = SOCKET_PROBE_TIMEOUT_MS
                    val first = try {
                        s.getInputStream().read()
                    } catch (e: SocketTimeoutException) {
                        -2
                    }
                    when {
                        first == -1 -> refusedClosed++
                        first >= 0 -> admitted++
                    }
                }
                assertEquals(
                    expectedRefusals, refusedClosed,
                    "connections past the bound must be closed without any handshake bytes"
                )
                assertEquals(
                    PRE_HANDSHAKE_BOUND, admitted,
                    "connections within the bound must be admitted (kit HELLO sent)"
                )
                assertEquals(
                    expectedRefusals,
                    bobLogger.warnings().count { it.contains(REFUSAL_FRAGMENT) },
                    "exactly one refusal diagnostic per refused connection"
                )
                assertTrue(
                    bob.sessions.value.isEmpty(),
                    "never-HELLO connections must not produce sessions"
                )

                // Outbound stays available while inbound capacity is
                // saturated: Bob dials Alice and exchanges a message.
                val aliceTransport = newLanTransport("Alice")
                val alice = newKit(
                    "Alice",
                    AdmissionRecordingLogger(),
                    AdmissionPairFactory(aliceTransport)
                )
                alice.start()
                val alicePort = requireNotNull(aliceTransport.tcpPort.value)
                val (bobOutgoing, aliceIncoming) = establishSession(
                    dialer = bob, dialerStub = bobStub, acceptor = alice,
                    acceptorName = "Alice", acceptorPort = alicePort
                )
                val outboundMsg = exchangeMessage(
                    bobOutgoing, aliceIncoming, P2pMessage.Text("outbound while saturated")
                )
                assertEquals(
                    "outbound while saturated",
                    assertIs<P2pMessage.Text>(outboundMsg).value
                )
            } finally {
                // Release: the non-conforming sockets go away; every admitted
                // setup fails (EOF) and returns its admission permit.
                sockets.forEach { runCatching { it.close() } }
            }
            awaitTrue("all admitted never-HELLO setups surfaced as failures") {
                bobLogger.warnings().count { it.contains("Incoming session setup failed") } >=
                    PRE_HANDSHAKE_BOUND
            }

            // Inbound admission recovered: a legitimate peer (Carol) dials
            // Bob and gets a working session.
            val carolStub = AdmissionStubDiscovery()
            val carol = newKit(
                "Carol",
                AdmissionRecordingLogger(),
                AdmissionPairFactory(newLanTransport("Carol"), carolStub)
            )
            val (carolOutgoing, bobIncoming) = establishSession(
                dialer = carol, dialerStub = carolStub, acceptor = bob,
                acceptorName = "Bob", acceptorPort = requireNotNull(bobTransport.tcpPort.value)
            )
            val inboundMsg = exchangeMessage(
                carolOutgoing, bobIncoming, P2pMessage.Text("inbound after recovery")
            )
            assertEquals("inbound after recovery", assertIs<P2pMessage.Text>(inboundMsg).value)

            // Bounded session state + no kit-scope escalation.
            assertEquals(
                2, bob.sessions.value.size,
                "expected exactly the outgoing-to-Alice and incoming-from-Carol sessions"
            )
            assertTrue(
                bobLogger.warnings().none { it.contains("inbound acceptance ended") },
                "admission refusals must never terminate the accept loop"
            )
            assertTrue(
                bobLogger.errors().isEmpty(),
                "no uncaught kit-scope failure expected, got: ${bobLogger.errors()}"
            )
        }
    }

    // ---------------------------------------------------------------------
    // Harness (same shape as JvmLanAcceptLoopResilienceTest)
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
     * Announce [acceptor]'s endpoint on [dialerStub], dial from [dialer], and
     * return (outgoing session on the dialer, incoming session on the acceptor).
     */
    private suspend fun CoroutineScope.establishSession(
        dialer: P2pKit,
        dialerStub: AdmissionStubDiscovery,
        acceptor: P2pKit,
        acceptorName: String,
        acceptorPort: Int
    ): Pair<P2pSession, P2pSession> {
        val acceptorPeer = Peer(
            id = acceptor.localPeerId,
            name = acceptorName,
            platform = Platform.JVM_DESKTOP,
            supportedTransports = setOf(TransportKind.LAN)
        )
        dialerStub.announce(
            InternalPeer(
                publicPeer = acceptorPeer,
                transportHints = listOf(
                    TransportHint(type = TransportKind.LAN, host = "127.0.0.1", port = acceptorPort)
                )
            )
        )
        withTimeout(CONNECT_TIMEOUT_MS) {
            dialer.peers.first { peers -> peers.any { it.id == acceptorPeer.id } }
        }
        val ready = CompletableDeferred<Unit>()
        val incomingDeferred = async {
            acceptor.incomingSessions.onSubscription { ready.complete(Unit) }.first()
        }
        ready.await()
        val outgoing = withTimeout(CONNECT_TIMEOUT_MS) { dialer.connect(acceptorPeer) }
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
        /**
         * Mirrors the internal `MAX_CONCURRENT_PRE_HANDSHAKE_SETUPS` policy
         * constant in `dev.p2pkit.core.internal.SessionManager` (not visible
         * across the module boundary). If the policy value changes, update
         * this in the same commit.
         */
        const val PRE_HANDSHAKE_BOUND: Int = 16

        /** Raw connections opened that never send HELLO (> the bound). */
        const val NEVER_HELLO_COUNT: Int = 20

        /** Warn fragment logged on a pre-handshake admission refusal. */
        const val REFUSAL_FRAGMENT: String = "pre-handshake setups at capacity"

        const val CONNECT_TIMEOUT_MS: Long = 10_000
        const val MESSAGE_TIMEOUT_MS: Long = 10_000
        const val AWAIT_TIMEOUT_MS: Long = 10_000
        const val SOCKET_PROBE_TIMEOUT_MS: Int = 2_000
    }
}

/** Thread-safe recording [P2pLogger] (the commonTest fixture isn't published). */
private class AdmissionRecordingLogger : P2pLogger {
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
private class AdmissionStubDiscovery : DiscoveryTransport {
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

private class AdmissionPairFactory(
    private val data: JvmLanDataTransport,
    private val discovery: DiscoveryTransport? = null
) : TransportFactory {
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = data, discovery = discovery)
}
