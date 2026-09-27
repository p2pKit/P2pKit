package dev.p2pkit.core.internal

import dev.p2pkit.core.KeepAliveConfig
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSessionProfile
import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerAdmission
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.PeerIdentity
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.protocol.DefaultP2pProtocol
import dev.p2pkit.core.protocol.ProtocolConstants
import dev.p2pkit.core.protocol.ProtocolEvent
import dev.p2pkit.core.protocol.ProtocolSessionState
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs

/** In-memory admission/accounting tests, not a claim about 128 real LAN connections. */
@OptIn(ExperimentalCoroutinesApi::class)
class RestrictedSessionTest {
    private class Fixture(val session: P2pSessionImpl, val pair: FakeConnectionPair) {
        suspend fun close() {
            try { session.close() } finally { pair.b.close() }
        }
    }

    private fun TestScope.session(
        index: Int, profile: P2pSessionProfile, admission: PeerAdmission,
    ): Fixture {
        val peer = Peer(PeerId("restricted-$index"), "Test", Platform.JVM_DESKTOP, setOf(TransportKind.LAN))
        val fingerprint = PeerFingerprint.fromDigest(ByteArray(32).also {
            it[0] = index.toByte()
            it[1] = (index ushr 8).toByte()
        })
        val pair = FakeConnectionPair()
        val session = P2pSessionImpl(
            id = "session-$index", peer = peer, peerIdentity = PeerIdentity(peer.id, fingerprint),
            initialConnection = pair.a,
            initialEvents = Channel(Channel.UNLIMITED, onUndeliveredElement = ProtocolEvent::release),
            initialProtocolState = ProtocolSessionState(
                "local", secure = true, restrictedApplicationBytes =
                    if (admission == PeerAdmission.EnrollmentOnly) 4096 else profile.maxApplicationBytes,
            ),
            protocol = DefaultP2pProtocol(
                clock = { testScheduler.currentTime }, sessionProfile = profile,
                version = ProtocolConstants.SECURE_VERSION,
            ),
            parentScope = backgroundScope, keepAlive = KeepAliveConfig(60_000, 120_000),
            clock = { testScheduler.currentTime }, logger = P2pLogger.NoOp,
            cleanupClock = { testScheduler.currentTime },
            cleanupOperationDispatcher = StandardTestDispatcher(testScheduler),
            cleanupDeadlineDispatcher = StandardTestDispatcher(testScheduler),
            sessionProfile = profile, admittedAs = admission,
        )
        return Fixture(session, pair)
    }

    @Test
    fun exactly128TrustedAndFourQuarantinedSessionsCountBothDirections() = runTest {
        val budget = PayloadBudget(64L * 1_048_576)
        val admissions = mutableMapOf<PeerFingerprint, PeerAdmission>()
        val profile = P2pSessionProfile(
            { admissions[it.fingerprint] ?: PeerAdmission.Rejected }, budget, maxTrustedSessions = 128,
        )
        val store = SessionStore(P2pLogger.NoOp, strictInvariants = true, profile = profile)
        val owned = mutableListOf<Fixture>()
        suspend fun register(index: Int, admission: PeerAdmission, incoming: Boolean): RegisterOutcome {
            val fixture = session(index, profile, admission)
            owned += fixture
            admissions[checkNotNull(fixture.session.peerIdentity.fingerprint)] = admission
            return store.tryRegister(fixture.session.peer.id, fixture.session, incoming, "local")
        }
        try {
            repeat(128) { assertIs<RegisterOutcome.Accepted>(register(it, PeerAdmission.Trusted, it % 2 == 0)) }
            assertIs<RegisterOutcome.RefusedAtCapacity>(register(128, PeerAdmission.Trusted, incoming = false))
            assertIs<RegisterOutcome.RefusedAtCapacity>(register(129, PeerAdmission.Trusted, incoming = true))
            repeat(4) {
                assertIs<RegisterOutcome.Accepted>(register(130 + it, PeerAdmission.EnrollmentOnly, incoming = true))
            }
            assertIs<RegisterOutcome.RefusedAtCapacity>(register(134, PeerAdmission.EnrollmentOnly, incoming = false))
            assertEquals(132, store.sessions.value.size)
            assertEquals(132, store.drainForShutdown().sessions.size)
            assertEquals(0, store.sessions.value.size)
        } finally { owned.forEach { it.close() } }
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun liveRevocationAndQuarantineLimitsCannotBeBypassedByAnExistingSession() = runTest {
        val decision = MutableStateFlow(PeerAdmission.EnrollmentOnly)
        val budget = PayloadBudget(2L * 1_048_576)
        val profile = P2pSessionProfile({ decision.value }, budget, maxTrustedSessions = 1)
        val fixture = session(1, profile, PeerAdmission.EnrollmentOnly)
        try {
            fixture.session.send(P2pMessage.Binary(byteArrayOf(1)))
            decision.value = PeerAdmission.Trusted
            // The approval notice may traverse quarantine, but its captured class/limit never upgrades.
            assertEquals(PeerAdmission.EnrollmentOnly, fixture.session.admission)
            assertFailsWith<P2pError.ProtocolError> { fixture.session.send(P2pMessage.Binary(ByteArray(4097))) }
            assertFailsWith<P2pError.ProtocolError> { fixture.session.send(P2pMessage.Text("not RPC")) }
            assertFailsWith<P2pError.ProtocolError> {
                fixture.session.send(P2pMessage.Binary(byteArrayOf(1), mapOf("extra" to "not allowed")))
            }
            decision.value = PeerAdmission.Rejected
            val writes = fixture.pair.a.writeAttempts
            assertFailsWith<P2pError.AuthorizationRejected> { fixture.session.send(P2pMessage.Binary(byteArrayOf(1))) }
            assertEquals(writes, fixture.pair.a.writeAttempts)
        } finally { fixture.close() }
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun generationBoundSendRejectsAStaleOrUnsupportedGenerationBeforeWriting() = runTest {
        val budget = PayloadBudget(2L * 1_048_576)
        val profile = P2pSessionProfile({ PeerAdmission.Trusted }, budget, maxTrustedSessions = 1)
        val fixture = session(1, profile, PeerAdmission.Trusted)
        try {
            assertEquals(1L, fixture.session.connectionInfo.value.generation)
            val before = fixture.pair.a.writeAttempts
            assertFailsWith<P2pError.ConnectionFailed> {
                fixture.session.sendAtGeneration(P2pMessage.Binary(byteArrayOf(1)), generation = 0)
            }
            assertFailsWith<P2pError.ConnectionFailed> {
                fixture.session.sendAtGeneration(P2pMessage.Binary(byteArrayOf(1)), generation = 2)
            }
            assertEquals(before, fixture.pair.a.writeAttempts)
            fixture.session.sendAtGeneration(P2pMessage.Binary(byteArrayOf(1)), generation = 1)
            assertEquals(before + 1, fixture.pair.a.writeAttempts)
        } finally { fixture.close() }
        assertEquals(0L, budget.retainedBytes.value)
    }
}
