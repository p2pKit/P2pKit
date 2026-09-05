package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.P2pState
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.dsl.P2pKitBuilder
import dev.p2pkit.core.security.SecureIdentityService
import dev.p2pkit.core.security.platformSecurityCryptography
import dev.p2pkit.core.testfixtures.CopyingRawConnection
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.MemorySecureIdentityStorage
import dev.p2pkit.core.testfixtures.TrackedTransportKey
import dev.p2pkit.core.testfixtures.TrackingSecurityCryptography
import dev.p2pkit.core.testfixtures.createSecureTestKit
import dev.p2pkit.core.testfixtures.peerForSecureKit
import dev.p2pkit.core.testfixtures.runWireBlocking
import dev.p2pkit.core.transport.DataTransport
import kotlin.concurrent.atomics.AtomicInt
import kotlin.concurrent.atomics.ExperimentalAtomicApi
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNotSame
import kotlin.test.assertSame
import kotlin.test.assertTrue
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.yield

/** Real authenticated kits and cipher lifetimes over synthetic, explicitly shaped raw streams. */
@OptIn(ExperimentalAtomicApi::class)
class SecureSessionLifecycleTest {
    @Test
    fun simultaneousAuthenticatedOpenKeepsOneWireAndWipesOnlyLosingCipherKeys() = runWireBlocking { delivery ->
        val aliceOut = FakeConnectionPair(delivery)
        val bobOut = FakeConnectionPair(delivery)
        val aliceData = FakeDataTransport(
            outgoingConnection = { CopyingRawConnection(aliceOut.a) },
            preStagedIncoming = listOf(CopyingRawConnection(bobOut.b))
        )
        val bobData = FakeDataTransport(
            outgoingConnection = { CopyingRawConnection(bobOut.a) },
            preStagedIncoming = listOf(CopyingRawConnection(aliceOut.b))
        )
        val atCommit = AtomicInt(0)
        val allAuthenticated = CompletableDeferred<Unit>()
        val releaseCommit = CompletableDeferred<Unit>()
        val gate: suspend () -> Unit = {
            if (atCommit.addAndFetch(1) == 4) allAuthenticated.complete(Unit)
            releaseCommit.await()
        }
        withSecurePair(
            "simultaneous-open", aliceData, bobData,
            aliceConfigure = { beforeSessionCommitForTest = gate },
            bobConfigure = { beforeSessionCommitForTest = gate }
        ) { kits ->
            val aliceCall = async { kits.alice.connect(peerForSecureKit(kits.bob)) }
            val bobCall = async { kits.bob.connect(peerForSecureKit(kits.alice)) }
            try {
                // All four Noise + HELLO setups really overlap before any registration, not just two async calls.
                withTimeout(5_000) { allAuthenticated.await() }
                assertEquals(4, atCommit.load())
                assertTrue(kits.alice.sessions.value.isEmpty())
                assertTrue(kits.bob.sessions.value.isEmpty())
                kits.assertKeyCounts(total = 4, cleared = 0)
                releaseCommit.complete(Unit)
                withTimeout(5_000) { aliceCall.await(); bobCall.await() }

                val aliceKeepsOutgoing = kits.alice.localPeerId.value < kits.bob.localPeerId.value
                val winner = if (aliceKeepsOutgoing) aliceOut else bobOut
                val loser = if (aliceKeepsOutgoing) bobOut else aliceOut
                withTimeout(5_000) {
                    loser.a.state.first { it == ConnectionState.Closed }
                    loser.b.state.first { it == ConnectionState.Closed }
                    kits.awaitKeyCounts(total = 4, cleared = 2)
                }
                val aliceSession = kits.alice.sessions.value.single()
                val bobSession = kits.bob.sessions.value.single()
                kits.assertAuthenticated(aliceSession, bobSession)
                assertEquals(ConnectionState.Connected, winner.a.state.value)
                assertEquals(ConnectionState.Connected, winner.b.state.value)
                assertEquals(1, aliceData.connectCalls.size)
                assertEquals(1, bobData.connectCalls.size)
                // A stale loser must not remove the winner, close its keys, or leak back from a later connect.
                assertSame(aliceSession, kits.alice.connect(peerForSecureKit(kits.bob)))
                assertSame(bobSession, kits.bob.connect(peerForSecureKit(kits.alice)))
                exchange(aliceSession, bobSession, "surviving Alice to Bob")
                exchange(bobSession, aliceSession, "surviving Bob to Alice")
                kits.assertKeyCounts(total = 4, cleared = 2)

                kits.alice.stop()
                kits.bob.stop()
                kits.assertKeyCounts(total = 4, cleared = 4)
                assertTrue(kits.alice.sessions.value.isEmpty())
                assertTrue(kits.bob.sessions.value.isEmpty())
            } finally {
                releaseCommit.complete(Unit)
            }
        }
    }

    @Test
    fun cancelledAuthenticatedResultOwnerRollsBackKeysAndPermitsFreshSession() = runWireBlocking { delivery ->
        val first = FakeConnectionPair(delivery)
        val retry = FakeConnectionPair(delivery)
        val dial = AtomicInt(0)
        val resultCount = AtomicInt(0)
        val resultReady = CompletableDeferred<Unit>()
        val bobData = FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(first.b)))
        val aliceData = FakeDataTransport(outgoingConnection = {
            if (dial.addAndFetch(1) == 1) CopyingRawConnection(first.a) else {
                bobData.emitIncoming(CopyingRawConnection(retry.b))
                CopyingRawConnection(retry.a)
            }
        })
        withSecurePair(
            "result-owner", aliceData, bobData,
            aliceConfigure = {
                afterSessionSetupResultForTest = {
                    if (resultCount.addAndFetch(1) == 1) {
                        resultReady.complete(Unit)
                        awaitCancellation()
                    }
                }
            },
            bobConfigure = { lifecycle { reconnectPolicy = ReconnectPolicy.Enabled(1, 0) } }
        ) { kits ->
            val incomingCall = async(start = CoroutineStart.UNDISPATCHED) { kits.bob.incomingSessions.first() }
            val owner = async { kits.alice.connect(peerForSecureKit(kits.bob)) }
            withTimeout(5_000) { resultReady.await() }
            val abandoned = kits.alice.sessions.value.single()
            val incoming = withTimeout(5_000) { incomingCall.await() }
            kits.assertAuthenticated(abandoned, incoming)
            kits.assertKeyCounts(total = 2, cleared = 0)

            owner.cancel(CancellationException("cancel authenticated result owner"))
            val cancelled = assertFailsWith<CancellationException> { withTimeout(5_000) { owner.await() } }
            assertEquals("cancel authenticated result owner", cancelled.message)
            assertEquals(ConnectionState.Closed, abandoned.state.value)
            withTimeout(5_000) {
                incoming.state.first { it == ConnectionState.Closed }
                assertIs<P2pSessionImpl>(incoming).awaitRuntimeTermination()
                kits.bob.sessions.first { it.isEmpty() }
            }
            assertTrue(kits.alice.sessions.value.isEmpty())
            kits.assertKeyCounts(total = 2, cleared = 2)
            assertEquals(0, bobData.connectCalls.size, "the incoming side must not reconnect")

            val replacementIncoming = async(start = CoroutineStart.UNDISPATCHED) {
                kits.bob.incomingSessions.first()
            }
            val replacement = withTimeout(5_000) { kits.alice.connect(peerForSecureKit(kits.bob)) }
            val replacementRemote = withTimeout(5_000) { replacementIncoming.await() }
            assertNotSame(abandoned, replacement)
            kits.assertAuthenticated(replacement, replacementRemote)
            assertSame(replacement, kits.alice.connect(peerForSecureKit(kits.bob)))
            assertEquals(2, aliceData.connectCalls.size)
            exchange(replacement, replacementRemote, "after cancelled authenticated ownership")
            kits.assertKeyCounts(total = 4, cleared = 2)
            assertFailsWith<P2pError.ConnectionFailed> { abandoned.send(P2pMessage.Text("must not escape")) }
        }
    }

    @Test
    fun authenticatedReconnectRearmsSameOutgoingOwnerWithFreshKeysAndNoIncomingDial() = runWireBlocking { delivery ->
        val first = FakeConnectionPair(delivery)
        val retry = FakeConnectionPair(delivery)
        retry.a.suspendWrites()
        val dial = AtomicInt(0)
        val bobData = FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(first.b)))
        val aliceData = FakeDataTransport(outgoingConnection = {
            if (dial.addAndFetch(1) == 1) CopyingRawConnection(first.a) else {
                bobData.emitIncoming(CopyingRawConnection(retry.b))
                CopyingRawConnection(retry.a)
            }
        })
        withSecurePair(
            "reconnect-owner", aliceData, bobData,
            aliceConfigure = { lifecycle { reconnectPolicy = ReconnectPolicy.Enabled(1, 0) } },
            bobConfigure = { lifecycle { reconnectPolicy = ReconnectPolicy.Enabled(1, 0) } }
        ) { kits ->
            try {
                val incomingCall = async(start = CoroutineStart.UNDISPATCHED) { kits.bob.incomingSessions.first() }
                val outgoing = withTimeout(5_000) { kits.alice.connect(peerForSecureKit(kits.bob)) }
                val oldIncoming = withTimeout(5_000) { incomingCall.await() }
                kits.assertAuthenticated(outgoing, oldIncoming)
                val originalId = outgoing.id
                val originalIdentity = outgoing.peerIdentity
                kits.assertKeyCounts(total = 2, cleared = 0)

                first.hangUp(first.b)
                withTimeout(5_000) {
                    while (retry.a.writeAttempts == 0) yield()
                    oldIncoming.state.first { it == ConnectionState.Failed }
                    assertIs<P2pSessionImpl>(oldIncoming).awaitRuntimeTermination()
                    kits.bob.sessions.first { it.isEmpty() }
                    kits.awaitKeyCounts(total = 2, cleared = 2)
                }
                assertEquals(ConnectionState.Reconnecting, outgoing.state.value)
                assertEquals(0, bobData.connectCalls.size)
                val newIncomingCall = async(start = CoroutineStart.UNDISPATCHED) {
                    kits.bob.incomingSessions.first()
                }
                retry.a.resumeWrites()
                val newIncoming = withTimeout(5_000) { newIncomingCall.await() }
                withTimeout(5_000) { outgoing.state.first { it == ConnectionState.Connected } }
                kits.assertAuthenticated(outgoing, newIncoming)
                assertEquals(originalId, outgoing.id)
                assertEquals(originalIdentity, outgoing.peerIdentity)
                assertSame(outgoing, kits.alice.sessions.value.single())
                assertSame(outgoing, kits.alice.connect(peerForSecureKit(kits.bob)))
                assertNotSame(oldIncoming, newIncoming)
                assertEquals(2, aliceData.connectCalls.size)
                assertEquals(0, bobData.connectCalls.size)
                exchange(outgoing, newIncoming, "fresh epoch forward")
                exchange(newIncoming, outgoing, "fresh epoch reverse")
                kits.assertKeyCounts(total = 4, cleared = 2)
            } finally {
                retry.a.resumeWrites()
            }
        }
    }

    @Test
    fun defaultSecureFixtureDoesNotReconnectAfterUnexpectedEof() = runWireBlocking { delivery ->
        val wire = FakeConnectionPair(delivery)
        val aliceData = FakeDataTransport(outgoingConnection = { CopyingRawConnection(wire.a) })
        val bobData = FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(wire.b)))
        withSecurePair("default-no-reconnect", aliceData, bobData) { kits ->
            val incomingCall = async(start = CoroutineStart.UNDISPATCHED) { kits.bob.incomingSessions.first() }
            val outgoing = withTimeout(5_000) { kits.alice.connect(peerForSecureKit(kits.bob)) }
            val incoming = withTimeout(5_000) { incomingCall.await() }
            kits.assertAuthenticated(outgoing, incoming)
            wire.hangUp(wire.b)
            for (session in listOf(outgoing, incoming)) {
                withTimeout(5_000) {
                    session.state.first { it == ConnectionState.Failed }
                    assertIs<P2pSessionImpl>(session).awaitRuntimeTermination()
                }
                assertFalse(assertIs<P2pSessionImpl>(session).runtimeJobIsActiveForTest)
            }
            withTimeout(5_000) {
                kits.alice.sessions.first { it.isEmpty() }
                kits.bob.sessions.first { it.isEmpty() }
            }
            assertEquals(1, aliceData.connectCalls.size)
            assertEquals(0, bobData.connectCalls.size)
            kits.assertKeyCounts(total = 2, cleared = 2)
        }
    }

    @Test
    fun terminalStopCancelsBlockedSecureReconnectAndCannotRestartItsOwner() = runWireBlocking { delivery ->
        val first = FakeConnectionPair(delivery)
        val retry = FakeConnectionPair(delivery)
        retry.a.suspendWrites()
        val dial = AtomicInt(0)
        val bobData = FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(first.b)))
        val aliceData = FakeDataTransport(outgoingConnection = {
            if (dial.addAndFetch(1) == 1) CopyingRawConnection(first.a) else {
                bobData.emitIncoming(CopyingRawConnection(retry.b))
                CopyingRawConnection(retry.a)
            }
        })
        withSecurePair(
            "stop-reconnect", aliceData, bobData,
            aliceConfigure = { lifecycle { reconnectPolicy = ReconnectPolicy.Enabled(3, 0) } }
        ) { kits ->
            try {
                val incomingCall = async(start = CoroutineStart.UNDISPATCHED) { kits.bob.incomingSessions.first() }
                val outgoing = withTimeout(5_000) { kits.alice.connect(peerForSecureKit(kits.bob)) }
                withTimeout(5_000) { incomingCall.await() }
                first.hangUp(first.b)
                withTimeout(5_000) { while (retry.a.writeAttempts == 0) yield() }
                assertEquals(ConnectionState.Reconnecting, outgoing.state.value)

                withTimeout(5_000) { kits.alice.stop() }
                assertEquals(P2pState.Stopped, kits.alice.state.value)
                assertEquals(ConnectionState.Closed, outgoing.state.value)
                withTimeout(5_000) { assertIs<P2pSessionImpl>(outgoing).awaitRuntimeTermination() }
                assertFalse(assertIs<P2pSessionImpl>(outgoing).runtimeJobIsActiveForTest)
                assertEquals(ConnectionState.Closed, retry.a.state.value)
                assertTrue(kits.alice.sessions.value.isEmpty())
                assertTrue(aliceData.isClosed)
                assertFailsWith<IllegalStateException> { kits.alice.start() }
                assertFailsWith<IllegalStateException> { kits.alice.connect(peerForSecureKit(kits.bob)) }
                kits.alice.stop()
                assertEquals(2, aliceData.connectCalls.size, "stopped reconnect cannot use remaining retry budget")
                kits.bob.stop()
                assertEquals(ConnectionState.Closed, retry.b.state.value)
                kits.assertKeyCounts(total = 2, cleared = 2)
            } finally {
                retry.a.resumeWrites()
            }
        }
    }

    private suspend fun withSecurePair(
        scenario: String,
        aliceTransport: DataTransport,
        bobTransport: DataTransport,
        aliceConfigure: P2pKitBuilder.() -> Unit = {},
        bobConfigure: P2pKitBuilder.() -> Unit = {},
        test: suspend CoroutineScope.(SecureKitPair) -> Unit
    ) = coroutineScope {
        val appId = AppId("secure.lifecycle.$scenario")
        val aliceStore = MemorySecureIdentityStorage()
        val bobStore = MemorySecureIdentityStorage()
        val aliceCrypto = TrackingSecurityCryptography()
        val bobCrypto = TrackingSecurityCryptography()
        var alice: P2pKit? = null
        var bob: P2pKit? = null
        try {
            val aliceFingerprint = previewFingerprint(appId, aliceStore)
            val bobFingerprint = previewFingerprint(appId, bobStore)
            val createdAlice = createSecureTestKit(
                appId, "Alice", aliceStore, aliceTransport,
                PeerAuthorizationPolicy.PinnedOnly(setOf(bobFingerprint))
            ) {
                securityCryptographyForTest = aliceCrypto
                aliceConfigure()
            }
            alice = createdAlice
            val createdBob = createSecureTestKit(
                appId, "Bob", bobStore, bobTransport,
                PeerAuthorizationPolicy.PinnedOnly(setOf(aliceFingerprint))
            ) {
                securityCryptographyForTest = bobCrypto
                bobConfigure()
            }
            bob = createdBob
            test(SecureKitPair(createdAlice, createdBob, aliceCrypto, bobCrypto))
        } finally {
            try {
                alice?.stop()
            } finally {
                try {
                    bob?.stop()
                } finally {
                    aliceStore.clear()
                    bobStore.clear()
                }
            }
        }
    }

    private fun previewFingerprint(appId: AppId, store: MemorySecureIdentityStorage): PeerFingerprint {
        val identity = SecureIdentityService(platformSecurityCryptography(), store).loadOrCreate(appId)
        return try {
            identity.fingerprint
        } finally {
            identity.clearPrivate()
        }
    }

    private suspend fun exchange(sender: P2pSession, receiver: P2pSession, text: String) = coroutineScope {
        val subscribed = CompletableDeferred<Unit>()
        val received = async(start = CoroutineStart.UNDISPATCHED) {
            withTimeout(5_000) {
                receiver.incoming.onSubscription { subscribed.complete(Unit) }.first()
            }
        }
        subscribed.await()
        val message = P2pMessage.Text(text, mapOf("test" to "authenticated-lifecycle"))
        sender.send(message)
        assertEquals(message, received.await())
    }

    private class SecureKitPair(
        val alice: P2pKit,
        val bob: P2pKit,
        private val aliceCrypto: TrackingSecurityCryptography,
        private val bobCrypto: TrackingSecurityCryptography
    ) {
        fun assertAuthenticated(aliceSession: P2pSession, bobSession: P2pSession) {
            assertEquals(ConnectionState.Connected, aliceSession.state.value)
            assertEquals(ConnectionState.Connected, bobSession.state.value)
            assertEquals(bob.localFingerprint, aliceSession.peerIdentity.fingerprint)
            assertEquals(alice.localFingerprint, bobSession.peerIdentity.fingerprint)
            assertEquals(bob.localPeerId, aliceSession.peerIdentity.peerId)
            assertEquals(alice.localPeerId, bobSession.peerIdentity.peerId)
        }

        fun assertKeyCounts(total: Int, cleared: Int) {
            for (crypto in listOf(aliceCrypto, bobCrypto)) {
                val keys = crypto.transportKeys()
                assertEquals(total, keys.size, "must observe real send/receive key arrays for each secure epoch")
                assertTrue(keys.all(TrackedTransportKey::wasLiveWhenObserved))
                assertEquals(cleared, keys.count(TrackedTransportKey::isCleared), "actual cipher-array wipes")
            }
        }

        suspend fun awaitKeyCounts(total: Int, cleared: Int) {
            try {
                while (listOf(aliceCrypto, bobCrypto).any { crypto ->
                    val keys = crypto.transportKeys()
                    keys.size != total || keys.count(TrackedTransportKey::isCleared) != cleared
                }) yield()
                assertKeyCounts(total, cleared)
            } finally {
                // Counts only, never key bytes; a failed deadline must identify which cleanup condition stalled.
                val counts = listOf(aliceCrypto, bobCrypto).map { crypto ->
                    val keys = crypto.transportKeys()
                    "total=${keys.size}, cleared=${keys.count(TrackedTransportKey::isCleared)}"
                }
                println("Secure fixture key counts: $counts; expected total=$total, cleared=$cleared")
            }
        }
    }
}
