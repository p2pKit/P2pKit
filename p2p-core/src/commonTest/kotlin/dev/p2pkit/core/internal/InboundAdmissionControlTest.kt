package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.protocol.DefaultP2pProtocol
import dev.p2pkit.core.protocol.HelloPayload
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.RecordingLogger
import dev.p2pkit.core.testfixtures.createTestKit
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * AUDIT-2026-07 (SEC-1, decision #9a) / coverage plan P1-26, commonTest
 * half: inbound admission control end to end through a real kit
 * ([SessionManager] + [SessionStore]) over fake connections.
 *
 *  1. Pre-handshake bound ([MAX_CONCURRENT_PRE_HANDSHAKE_SETUPS]): exactly
 *     that many concurrent inbound setups are admitted (boundary: at-cap
 *     load is unaffected); the next connection is refused — closed, warned,
 *     no session, and the kit never even sends its HELLO on it (nothing was
 *     allocated for it).
 *  2. Permit recovery — the no-leak proof: settling in-flight handshakes on
 *     BOTH outcomes (success via a valid remote HELLO, failure via remote
 *     hang-up) frees admission capacity, and a subsequent connection is
 *     admitted and completes normally.
 *  3. Total-session bound ([MAX_TOTAL_ACTIVE_SESSIONS]): that many inbound
 *     sessions with distinct peerIds register; the next net-new inbound
 *     session is refused post-handshake — closed cleanly, warned, never
 *     surfaced on [P2pKit.incomingSessions], session list stays at the
 *     bound.
 *
 * Kits are built with `strictInvariants = true` (via [createTestKit]), so
 * any refusal path that corrupted store bookkeeping would fail loudly.
 */
class InboundAdmissionControlTest {

    /** Warn fragment logged by [SessionManager.handleIncoming] on a pre-handshake refusal. */
    private val preHandshakeRefusalFragment = "pre-handshake setups at capacity"

    /** Warn fragment logged by [SessionManager.registerSession] on a total-session refusal. */
    private val totalSessionRefusalFragment = "total active sessions at capacity"

    /** Warn fragment logged by [SessionManager.handleIncoming] on a per-connection setup failure. */
    private val setupFailedFragment = "Incoming session setup failed"

    private val appIdValue = "com.example.test"

    /** Protocol instance playing the remote peers' side of each fake wire. */
    private val remoteProtocol = DefaultP2pProtocol(clock = { 0L })

    private fun incomingKit(
        transport: FakeDataTransport,
        recordingLogger: RecordingLogger
    ): P2pKit = createTestKit {
        appId = AppId(appIdValue)
        deviceName = "Bob"
        logger = recordingLogger
        peerIdStorage = InMemoryPeerIdStorage(seed = PeerId("bob-id"))
        keepAlive {
            pingIntervalMillis = 60_000
            timeoutMillis = 120_000
        }
        transports {
            register(AdmissionFactory(transport))
        }
    }

    private fun remoteHello(peerId: String) = HelloPayload(
        appId = appIdValue,
        peerId = peerId,
        deviceName = "Remote $peerId",
        platform = "JVM_DESKTOP",
        supportedTransports = listOf("LAN")
    )

    @Test
    fun preHandshakeBoundRefusesExcessAndPermitsRecoverOnBothOutcomes() = runBlocking {
        val logger = RecordingLogger()
        val transport = FakeDataTransport()
        val bob = incomingKit(transport, logger)
        try {
            // Fill the pre-handshake bound with connections that never send
            // HELLO. All of them must be ADMITTED (at-cap conforming load is
            // unaffected): each setup sends the kit's HELLO on its wire.
            val stalled = List(MAX_CONCURRENT_PRE_HANDSHAKE_SETUPS) { FakeConnectionPair() }
            stalled.forEach { transport.emitIncoming(it.b) }
            awaitTrue("all $MAX_CONCURRENT_PRE_HANDSHAKE_SETUPS at-bound setups admitted (kit HELLO sent)") {
                stalled.all { it.b.writeAttempts > 0 }
            }

            // One connection past the bound: refused before any allocation —
            // closed, warned, no kit HELLO ever written on it, no session.
            val excess = FakeConnectionPair()
            transport.emitIncoming(excess.b)
            awaitTrue("refusal diagnostic for the connection past the bound") {
                logger.warnings.any { it.contains(preHandshakeRefusalFragment) }
            }
            awaitTrue("refused connection closed") {
                excess.b.state.value == ConnectionState.Closed
            }
            assertEquals(
                0, excess.b.writeAttempts,
                "the kit must not allocate handshake work for a refused connection"
            )
            assertTrue(bob.sessions.value.isEmpty(), "no session may exist for refused/stalled setups")

            // Permit recovery, success path: half of the stalled setups
            // complete their handshake with a valid remote HELLO.
            val successCount = MAX_CONCURRENT_PRE_HANDSHAKE_SETUPS / 2
            stalled.take(successCount).forEachIndexed { i, pair ->
                remoteProtocol.sendHello(pair.a, remoteHello("peer-success-$i"))
            }
            withTimeout(AWAIT_TIMEOUT_MS) {
                // >= not ==: StateFlow conflation may skip intermediate sizes
                // when several handshakes complete close together.
                bob.sessions.first { it.size >= successCount }
            }

            // Permit recovery, failure path: the other half hang up without
            // ever sending HELLO — each setup fails, is logged, and releases
            // its permit.
            stalled.drop(successCount).forEach { it.hangUp(it.a) }
            awaitTrue("every hung-up setup surfaced as a per-connection failure") {
                logger.warnings.count { it.contains(setupFailedFragment) } >=
                    MAX_CONCURRENT_PRE_HANDSHAKE_SETUPS - successCount
            }

            // With every permit returned (both outcomes), a fresh inbound
            // connection is admitted and completes normally.
            val late = FakeConnectionPair()
            transport.emitIncoming(late.b)
            awaitTrue("post-recovery connection admitted (kit HELLO sent)") {
                late.b.writeAttempts > 0
            }
            remoteProtocol.sendHello(late.a, remoteHello("peer-late"))
            withTimeout(AWAIT_TIMEOUT_MS) {
                bob.sessions.first { sessions ->
                    sessions.any { it.peer.id.value == "peer-late" }
                }
            }

            // Exactly one connection was ever refused at the pre-handshake
            // bound; refusal never recurred once capacity was free.
            assertEquals(
                1,
                logger.warnings.count { it.contains(preHandshakeRefusalFragment) },
                "expected exactly one pre-handshake refusal"
            )
        } finally {
            bob.stop()
        }
    }

    @Test
    fun totalSessionBoundRefusesNetNewInboundSessions() = runBlocking {
        val logger = RecordingLogger()
        val transport = FakeDataTransport()
        val bob = incomingKit(transport, logger)
        val surfaced = mutableListOf<String>()
        var collector: Job? = null
        try {
            // Record everything the kit surfaces on the public incoming flow.
            // Subscription is awaited before any connection is emitted:
            // incomingSessions is replay=0, so an emission before the
            // collector registers would be invisible to it.
            val subscribed = CompletableDeferred<Unit>()
            collector = launch {
                bob.incomingSessions
                    .onSubscription { subscribed.complete(Unit) }
                    .collect { surfaced.add(it.peer.id.value) }
            }
            subscribed.await()

            // Register sessions with distinct peerIds up to the bound, one at
            // a time (each handshake completes before the next connection, so
            // the pre-handshake gate never interferes).
            for (i in 1..MAX_TOTAL_ACTIVE_SESSIONS) {
                val pair = FakeConnectionPair()
                transport.emitIncoming(pair.b)
                remoteProtocol.sendHello(pair.a, remoteHello("peer-$i"))
                withTimeout(AWAIT_TIMEOUT_MS) { bob.sessions.first { it.size == i } }
            }
            assertEquals(MAX_TOTAL_ACTIVE_SESSIONS, bob.sessions.value.size)

            // The next net-new inbound session passes the handshake but is
            // refused at registration: warned, closed cleanly, never listed,
            // never surfaced on incomingSessions.
            val overflow = FakeConnectionPair()
            transport.emitIncoming(overflow.b)
            remoteProtocol.sendHello(overflow.a, remoteHello("peer-overflow"))
            awaitTrue("total-session refusal diagnostic") {
                logger.warnings.any { it.contains(totalSessionRefusalFragment) }
            }
            awaitTrue("refused session's connection closed") {
                overflow.b.state.value == ConnectionState.Closed
            }
            assertEquals(
                MAX_TOTAL_ACTIVE_SESSIONS, bob.sessions.value.size,
                "the session list must stay at the bound"
            )
            assertTrue(
                bob.sessions.value.none { it.peer.id.value == "peer-overflow" },
                "a refused session must never appear in the public session list"
            )
            awaitTrue("all admitted sessions surfaced on incomingSessions") {
                surfaced.size == MAX_TOTAL_ACTIVE_SESSIONS
            }
            assertTrue(
                surfaced.none { it == "peer-overflow" },
                "a refused session must never surface on incomingSessions"
            )
        } finally {
            collector?.cancel()
            bob.stop()
        }
    }

    private suspend fun awaitTrue(what: String, condition: () -> Boolean) {
        try {
            withTimeout(AWAIT_TIMEOUT_MS) {
                while (!condition()) delay(10)
            }
        } catch (e: kotlinx.coroutines.TimeoutCancellationException) {
            throw AssertionError("Timed out after ${AWAIT_TIMEOUT_MS}ms waiting for: $what", e)
        }
    }

    private companion object {
        const val AWAIT_TIMEOUT_MS: Long = 5_000
    }
}

private class AdmissionFactory(private val transport: FakeDataTransport) : TransportFactory {
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = null)
}
