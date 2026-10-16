package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.KeepAliveConfig
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSessionProfile
import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerAdmission
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.SessionFailureKind
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.internal.security.AuthenticatedV2SecurityEngine
import dev.p2pkit.core.protocol.DefaultP2pProtocol
import dev.p2pkit.core.protocol.HelloPayload
import dev.p2pkit.core.protocol.P2pProtocol
import dev.p2pkit.core.protocol.ProtocolConstants
import dev.p2pkit.core.protocol.ProtocolEvent
import dev.p2pkit.core.protocol.ProtocolSessionState
import dev.p2pkit.core.security.LocalSecureIdentity
import dev.p2pkit.core.security.PlatformSecurityCryptography
import dev.p2pkit.core.security.SecureIdentityService
import dev.p2pkit.core.security.platformSecurityCryptography
import dev.p2pkit.core.testfixtures.CopyingRawConnection
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.MemorySecureIdentityStorage
import dev.p2pkit.core.testfixtures.RecordingLogger
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Real authenticated managers over in-memory wires; no sockets or physical-device claim. */
class RestrictedReconnectAdmissionTest {
    @Test
    fun approvalCannotStartAReplacementReaderOnTheOldEnrollmentSession() = runBlocking {
        reconnect(PeerAdmission.EnrollmentOnly, PeerAdmission.Trusted)
    }

    @Test
    fun downgradeCannotStartAReplacementReaderOnTheOldTrustedSession() = runBlocking {
        reconnect(PeerAdmission.Trusted, PeerAdmission.EnrollmentOnly)
    }

    @Test
    fun liveRevocationCannotBeBypassedByTheReconnectFingerprintPin() = runBlocking {
        reconnect(PeerAdmission.Trusted, PeerAdmission.Rejected)
    }

    @Test
    fun bothUnchangedAdmissionClassesCanReconnectWithTheirOriginalLimits() = runBlocking {
        reconnect(PeerAdmission.EnrollmentOnly, PeerAdmission.EnrollmentOnly)
        reconnect(PeerAdmission.Trusted, PeerAdmission.Trusted)
    }

    private suspend fun CoroutineScope.reconnect(initial: PeerAdmission, next: PeerAdmission) {
        val appId = AppId("restricted.reconnect.${initial.name}.${next.name}")
        val wires = listOf(FakeConnectionPair(), FakeConnectionPair())
        val aliceStore = MemorySecureIdentityStorage()
        val bobStore = MemorySecureIdentityStorage()
        val aliceJob = SupervisorJob(coroutineContext[Job])
        val bobJob = SupervisorJob(coroutineContext[Job])
        val aliceLogger = RecordingLogger()
        val bobLogger = RecordingLogger()
        val decision = MutableStateFlow(initial)
        val aliceBudget = PayloadBudget(2L * 1_048_576)
        val bobBudget = PayloadBudget(2L * 1_048_576)
        val aliceProfile = P2pSessionProfile({ decision.value }, aliceBudget, 1, maxApplicationBytes = 8192)
        val bobProfile = P2pSessionProfile({ PeerAdmission.Trusted }, bobBudget, 1, maxApplicationBytes = 8192)
        val observedProtocol = ObservedRestrictedProtocol(
            DefaultP2pProtocol(
                clock = ::systemTimeMillis, version = ProtocolConstants.SECURE_VERSION,
                sessionProfile = aliceProfile,
            )
        )
        var nextWire = 0
        val aliceTransport = FakeDataTransport(outgoingConnection = {
            check(nextWire < wires.size) { "Unexpected additional reconnect attempt" }
            CopyingRawConnection(wires[nextWire++].a)
        })
        val reconnectTransport = SecondConnectGate(aliceTransport)
        val bobTransport = FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(wires[0].b)))
        var aliceIdentity: LocalSecureIdentity? = null
        var bobIdentity: LocalSecureIdentity? = null
        var aliceManager: SessionManager? = null
        var bobManager: SessionManager? = null
        val waiters = mutableListOf<Job>()
        val sessions = mutableListOf<P2pSessionImpl>()
        var bodyFailure: Throwable? = null
        try {
            val cryptography = platformSecurityCryptography()
            val localAlice = SecureIdentityService(cryptography, aliceStore).loadOrCreate(appId)
            aliceIdentity = localAlice
            val localBob = SecureIdentityService(cryptography, bobStore).loadOrCreate(appId)
            bobIdentity = localBob
            val senderManager = manager(
                CoroutineScope(Dispatchers.Default + aliceJob), reconnectTransport, observedProtocol,
                appId, localAlice, localBob.fingerprint, cryptography, aliceProfile, aliceLogger,
                ReconnectPolicy.Enabled(maxAttempts = 1, retryDelayMillis = 0),
            )
            aliceManager = senderManager
            val receiverManager = manager(
                CoroutineScope(Dispatchers.Default + bobJob), bobTransport,
                DefaultP2pProtocol(
                    clock = ::systemTimeMillis, version = ProtocolConstants.SECURE_VERSION,
                    sessionProfile = bobProfile,
                ),
                appId, localBob, localAlice.fingerprint, cryptography, bobProfile, bobLogger,
                ReconnectPolicy.Disabled,
            )
            bobManager = receiverManager
            aliceTransport.start().getOrThrow()
            bobTransport.start().getOrThrow()
            receiverManager.startAcceptingIncoming(listOf(bobTransport))
            val firstIncoming = async(start = CoroutineStart.UNDISPATCHED) {
                receiverManager.incomingSessions.first()
            }.also(waiters::add)
            val peer = Peer(localBob.peerId, "Bob", currentPlatform(), setOf(TransportKind.LAN))
            val session = assertIs<P2pSessionImpl>(withTimeout(5_000) {
                senderManager.connect(peer, InternalPeer(peer, emptyList()), lifecycleGeneration = 1L)
            })
            sessions += session
            val firstReceiver = assertIs<P2pSessionImpl>(withTimeout(5_000) { firstIncoming.await() })
            sessions += firstReceiver
            val originalIdentity = session.peerIdentity
            val limit = if (initial == PeerAdmission.EnrollmentOnly) 4096 else aliceProfile.maxApplicationBytes
            assertEquals(initial, session.admission)
            assertEquals(listOf(limit), observedProtocol.readerLimits.value)
            assertEquals(1, observedProtocol.helloAttempts.value)

            decision.value = next
            wires[0].hangUp(wires[0].b)
            withTimeout(5_000) {
                reconnectTransport.entered.await()
                firstReceiver.state.first { it == ConnectionState.Closed || it == ConnectionState.Failed }
                receiverManager.sessions.first { it.isEmpty() }
            }
            val secondIncoming = async(start = CoroutineStart.UNDISPATCHED) {
                receiverManager.incomingSessions.first()
            }.also(waiters::add)
            bobTransport.emitIncoming(CopyingRawConnection(wires[1].b))
            reconnectTransport.release.complete(Unit)
            withTimeout(5_000) {
                combine(session.state, session.connectionInfo) { state, info ->
                    state == ConnectionState.Failed || (state == ConnectionState.Connected && info.generation > 1)
                }.first { it }
            }

            assertEquals(originalIdentity, session.peerIdentity)
            assertEquals(initial, session.admission)
            assertEquals(2, aliceTransport.connectCalls.size)
            if (initial != next) {
                assertEquals(ConnectionState.Failed, session.state.value)
                assertEquals(SessionFailureKind.Authorization, session.connectionInfo.value.lastFailure?.kind)
                assertEquals(1L, session.connectionInfo.value.generation)
                assertEquals(listOf(limit), observedProtocol.readerLimits.value, "No rejected-epoch protocol reader")
                assertEquals(1, observedProtocol.helloAttempts.value, "No rejected-epoch HELLO attempt")
                withTimeout(5_000) { session.awaitRuntimeTermination() }
                assertEquals(ConnectionState.Closed, wires[1].a.state.value)
                assertEquals(0 to 0L, session.applicationBacklogForTest())
                assertEquals(0L, aliceBudget.retainedBytes.value)
            } else {
                assertEquals(ConnectionState.Connected, session.state.value)
                assertEquals(2L, session.connectionInfo.value.generation)
                assertSame(session, senderManager.sessions.value.single())
                assertEquals(listOf(limit, limit), observedProtocol.readerLimits.value)
                assertEquals(2, observedProtocol.helloAttempts.value)
                val receiver = assertIs<P2pSessionImpl>(withTimeout(5_000) { secondIncoming.await() })
                sessions += receiver
                val received = async(start = CoroutineStart.UNDISPATCHED) { receiver.incoming.first() }
                    .also(waiters::add)
                val boundary = P2pMessage.Binary(ByteArray(limit) { it.toByte() })
                session.send(boundary)
                assertEquals(boundary, withTimeout(5_000) { received.await() })
                val writes = wires[1].a.writeAttempts
                assertFailsWith<P2pError.ProtocolError> {
                    session.send(P2pMessage.Binary(ByteArray(limit + 1)))
                }
                assertEquals(writes, wires[1].a.writeAttempts)
            }
        } catch (failure: Throwable) {
            bodyFailure = failure
            throw failure
        } finally {
            try {
                withContext(NonCancellable) {
                    reconnectTransport.release.complete(Unit)
                    cleanupAll(
                        { waiters.forEach { it.cancelAndJoin() } },
                        { aliceManager?.let { assertTrue(it.shutdownAllSessions().isEmpty()) } },
                        { bobManager?.let { assertTrue(it.shutdownAllSessions().isEmpty()) } },
                        { sessions.forEach { withTimeout(5_000) { it.awaitRuntimeTermination() } } },
                        { withTimeout(5_000) { aliceJob.cancelAndJoin() } },
                        { withTimeout(5_000) { bobJob.cancelAndJoin() } },
                        { aliceTransport.close() },
                        { bobTransport.close() },
                        { wires.forEach { pair -> try { pair.a.close() } finally { pair.b.close() } } },
                        { aliceIdentity?.clearPrivate() },
                        { bobIdentity?.clearPrivate() },
                        { aliceStore.clear() },
                        { bobStore.clear() },
                        { assertEquals(0L, aliceBudget.retainedBytes.value) },
                        { assertEquals(0L, bobBudget.retainedBytes.value) },
                    )
                }
            } catch (cleanupFailure: Throwable) {
                val original = bodyFailure
                if (original == null) throw cleanupFailure else original.addSuppressed(cleanupFailure)
            }
        }
        aliceLogger.assertNoUnexpectedWarnOrError()
        bobLogger.assertNoUnexpectedWarnOrError { entry ->
            initial != next && entry.level == RecordingLogger.Level.WARN &&
                entry.message == "Incoming session setup failed" && entry.throwable is P2pError.AuthenticationFailed
        }
        assertTrue(bobLogger.warnings.size <= if (initial == next) 0 else 1)
    }

    private fun manager(
        scope: CoroutineScope,
        transport: DataTransport,
        protocol: P2pProtocol,
        appId: AppId,
        identity: LocalSecureIdentity,
        remoteFingerprint: PeerFingerprint,
        cryptography: PlatformSecurityCryptography,
        profile: P2pSessionProfile,
        logger: RecordingLogger,
        reconnect: ReconnectPolicy,
    ): SessionManager = SessionManager(
        scope = scope, transportManager = TransportManager(listOf(transport)), protocol = protocol,
        securityMode = SecurityMode.AuthenticatedV2(PeerAuthorizationPolicy.PinnedOnly(setOf(remoteFingerprint))),
        localSecureIdentity = identity, authenticatedSecurity = AuthenticatedV2SecurityEngine(cryptography),
        keepAlive = KeepAliveConfig(60_000, 120_000), reconnectPolicy = reconnect,
        localAppId = appId, localPeerId = identity.peerId, localDeviceName = "Restricted reconnect peer",
        localPlatform = currentPlatform(), localTransports = setOf(TransportKind.LAN),
        clock = ::systemTimeMillis, monotonicClock = ::monotonicTimeMillis, logger = logger,
        lifecycleGate = RestrictedReconnectActiveGate, strictInvariants = true, sessionProfile = profile,
    )

    private suspend fun cleanupAll(vararg actions: suspend () -> Unit) {
        var first: Throwable? = null
        for (action in actions) {
            try {
                action()
            } catch (failure: Throwable) {
                val previous = first
                if (previous == null) first = failure else previous.addSuppressed(failure)
            }
        }
        first?.let { throw it }
    }
}

private object RestrictedReconnectActiveGate : SessionLifecycleGate {
    override suspend fun isActive(expectedGeneration: Long?): Boolean = true
    override suspend fun <T : Any> commit(expectedGeneration: Long?, block: suspend () -> T): T = block()
}

private class ObservedRestrictedProtocol(private val delegate: P2pProtocol) : P2pProtocol by delegate {
    val readerLimits = MutableStateFlow<List<Int?>>(emptyList())
    val helloAttempts = MutableStateFlow(0)

    override fun events(connection: RawConnection, sessionState: ProtocolSessionState): Flow<ProtocolEvent> {
        readerLimits.update { it + sessionState.restrictedApplicationBytes }
        return delegate.events(connection, sessionState)
    }

    override suspend fun sendHello(connection: RawConnection, hello: HelloPayload) {
        helloAttempts.update { it + 1 }
        delegate.sendHello(connection, hello)
    }
}

private class SecondConnectGate(private val delegate: FakeDataTransport) : DataTransport by delegate {
    val entered = CompletableDeferred<Unit>()
    val release = CompletableDeferred<Unit>()

    override suspend fun connect(peer: InternalPeer): RawConnection {
        if (delegate.connectCalls.isNotEmpty()) {
            entered.complete(Unit)
            release.await()
        }
        return delegate.connect(peer)
    }
}
