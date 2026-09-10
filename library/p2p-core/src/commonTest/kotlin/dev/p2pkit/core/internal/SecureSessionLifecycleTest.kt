package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.NetworkPathStatus
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.P2pState
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.dsl.P2pKitBuilder
import dev.p2pkit.core.internal.security.noise.NoiseTransportEofException
import dev.p2pkit.core.security.SecureIdentityService
import dev.p2pkit.core.security.platformSecurityCryptography
import dev.p2pkit.core.testfixtures.CopyingRawConnection
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.FakeNetworkPathObserver
import dev.p2pkit.core.testfixtures.MemorySecureIdentityStorage
import dev.p2pkit.core.testfixtures.RecordingLogger
import dev.p2pkit.core.testfixtures.TrackedTransportKey
import dev.p2pkit.core.testfixtures.TrackingSecurityCryptography
import dev.p2pkit.core.testfixtures.createSecureTestKit
import dev.p2pkit.core.testfixtures.withTestKit
import dev.p2pkit.core.testfixtures.peerForSecureKit
import dev.p2pkit.core.testfixtures.runWireBlocking
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.RawConnection
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
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.runBlocking
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
            aliceConfigure = { lifecycle { reconnectPolicy = ReconnectPolicy.Enabled(3, 0) } },
            bobVerifyDiagnostics = { recorder ->
                val diagnostics = recorder.entries.filter {
                    it.level == RecordingLogger.Level.WARN || it.level == RecordingLogger.Level.ERROR
                }
                // The only retry's first write is parked before delivering its 16-byte preface.
                // Bob can observe that EOF or be structurally cancelled by stop first; no other
                // authentication, retry or cleanup diagnostic belongs to this controlled abort.
                assertTrue(diagnostics.size <= 1, "one aborted retry must not become a warning stream")
                diagnostics.forEach { entry ->
                    assertEquals(RecordingLogger.Level.WARN, entry.level)
                    assertEquals("Incoming session setup failed", entry.message)
                    val failure = assertIs<P2pError.AuthenticationFailed>(entry.throwable)
                    assertEquals("Authenticated protocol v2 setup failed", failure.reason)
                    assertTrue(failure.suppressedExceptions.isEmpty())
                    val eof = assertIs<NoiseTransportEofException>(failure.cause)
                    assertEquals("Raw connection ended before 16 bytes were available", eof.message)
                    assertTrue(eof.suppressedExceptions.isEmpty())
                }
            }
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

    @Test
    fun pathLossRetiresAuthenticatedTransportBeforeWakeAndKeepsReplacementPinned() = runBlocking {
        val initial = FakeConnectionPair()
        val retry = FakeConnectionPair()
        val path = FakeNetworkPathObserver(NetworkPathStatus.Satisfied)
        val holdClose = MutableStateFlow(false)
        val closeEntered = CompletableDeferred<Unit>()
        val releaseClose = CompletableDeferred<Unit>()
        val rawCloseCalls = AtomicInt(0)
        val firstRaw = object : RawConnection by CopyingRawConnection(initial.a) {
            override suspend fun close() {
                rawCloseCalls.addAndFetch(1)
                if (holdClose.value) {
                    closeEntered.complete(Unit)
                    releaseClose.await()
                }
                initial.a.close()
            }
        }
        val bobData = FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(initial.b)))
        val dials = AtomicInt(0)
        val aliceData = FakeDataTransport(outgoingConnection = {
            when (dials.addAndFetch(1)) {
                1 -> firstRaw
                2 -> {
                    assertEquals(ConnectionState.Closed, initial.a.state.value)
                    bobData.emitIncoming(CopyingRawConnection(retry.b))
                    CopyingRawConnection(retry.a)
                }
                else -> error("unexpected extra authenticated dial")
            }
        })
        try {
            withSecurePair(
                "path-retirement", aliceData, bobData,
                aliceConfigure = {
                    lifecycle {
                        reconnectPolicy = ReconnectPolicy.Enabled(3, 30_000)
                        networkPathObserver = path
                    }
                }
            ) { kits ->
                try {
                    val session = withTimeout(5_000) { kits.alice.connect(peerForSecureKit(kits.bob)) }
                    val oldBob = withTimeout(5_000) {
                        kits.bob.sessions.first { it.isNotEmpty() }.single()
                    }
                    kits.assertAuthenticated(session, oldBob)
                    holdClose.value = true
                    path.emit(NetworkPathStatus.Unsatisfied)
                    withTimeout(5_000) {
                        session.state.first { it == ConnectionState.Reconnecting }
                        closeEntered.await()
                    }
                    assertEquals(1, dials.load(), "retire before starting the replacement handshake")
                    assertEquals(ConnectionState.Connected, initial.a.state.value)
                    releaseClose.complete(Unit)
                    // The remote store must independently observe EOF; a local
                    // close alone cannot establish this cross-peer precondition.
                    withTimeout(5_000) { oldBob.state.first { it == ConnectionState.Failed } }
                    withTimeout(5_000) { kits.awaitKeyCounts(total = 2, cleared = 2) }
                    path.emit(NetworkPathStatus.Satisfied)
                    withTimeout(10_000) { session.state.first { it == ConnectionState.Connected } }
                    val newBob = withTimeout(5_000) {
                        kits.bob.sessions.first { sessions ->
                            sessions.singleOrNull()?.let {
                                it !== oldBob && it.state.value == ConnectionState.Connected
                            } == true
                        }.single()
                    }
                    kits.assertAuthenticated(session, newBob)
                    exchange(session, newBob, "recovered authenticated outbound")
                    exchange(newBob, session, "recovered authenticated inbound")
                    kits.assertKeyCounts(total = 4, cleared = 2)
                    assertEquals(2, dials.load())
                    assertEquals(1, rawCloseCalls.load(), "pump retirement and disposal share one raw-close owner")
                } finally {
                    releaseClose.complete(Unit)
                }
            }
        } finally {
            releaseClose.complete(Unit)
            initial.a.close()
            initial.b.close()
            retry.a.close()
            retry.b.close()
        }
    }

    private suspend fun withSecurePair(
        scenario: String,
        aliceTransport: DataTransport,
        bobTransport: DataTransport,
        aliceConfigure: P2pKitBuilder.() -> Unit = {},
        bobConfigure: P2pKitBuilder.() -> Unit = {},
        bobVerifyDiagnostics: (RecordingLogger) -> Unit = { it.assertNoUnexpectedWarnOrError() },
        test: suspend CoroutineScope.(SecureKitPair) -> Unit
    ) = coroutineScope {
        val appId = AppId("secure.lifecycle.$scenario")
        val aliceStore = MemorySecureIdentityStorage()
        val bobStore = MemorySecureIdentityStorage()
        val aliceCrypto = TrackingSecurityCryptography()
        val bobCrypto = TrackingSecurityCryptography()
        try {
            val aliceFingerprint = previewFingerprint(appId, aliceStore)
            val bobFingerprint = previewFingerprint(appId, bobStore)
            withTestKit(create = { recording ->
                createSecureTestKit(
                    appId, "Alice", aliceStore, aliceTransport,
                    PeerAuthorizationPolicy.PinnedOnly(setOf(bobFingerprint))
                ) {
                    logger = recording
                    securityCryptographyForTest = aliceCrypto
                    aliceConfigure()
                }
            }) { alice ->
                withTestKit(create = { recording ->
                    createSecureTestKit(
                        appId, "Bob", bobStore, bobTransport,
                        PeerAuthorizationPolicy.PinnedOnly(setOf(aliceFingerprint))
                    ) {
                        logger = recording
                        securityCryptographyForTest = bobCrypto
                        bobConfigure()
                    }
                }, verifyDiagnostics = bobVerifyDiagnostics) { bob ->
                    test(SecureKitPair(alice, bob, aliceCrypto, bobCrypto))
                }
            }
        } finally {
            // Attempt both kit shutdowns before clearing these in-memory stores; no platform I/O here.
            aliceStore.clear()
            bobStore.clear()
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
