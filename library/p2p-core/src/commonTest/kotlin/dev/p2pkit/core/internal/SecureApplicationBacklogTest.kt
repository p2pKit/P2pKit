package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.KeepAliveConfig
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.internal.security.AuthenticatedV2SecurityEngine
import dev.p2pkit.core.permission.NoOpP2pPermissionManager
import dev.p2pkit.core.protocol.DefaultP2pProtocol
import dev.p2pkit.core.protocol.ProtocolConstants
import dev.p2pkit.core.security.LocalSecureIdentity
import dev.p2pkit.core.security.PlatformSecurityCryptography
import dev.p2pkit.core.security.SecureIdentityService
import dev.p2pkit.core.security.platformSecurityCryptography
import dev.p2pkit.core.testfixtures.CopyingRawConnection
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.MemorySecureIdentityStorage
import dev.p2pkit.core.testfixtures.RecordingLogger
import dev.p2pkit.core.testfixtures.createSecureTestKit
import dev.p2pkit.core.testfixtures.peerForSecureKit
import dev.p2pkit.core.testfixtures.runWireBlocking
import dev.p2pkit.core.transport.InternalPeer
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertSame
import kotlin.test.assertTrue
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.yield

/** Real pinned-v2 decode/router coverage over shaped in-memory wires, not independent interoperability. */
class SecureApplicationBacklogTest {
    @Test
    fun pinnedSecureReceiveChargesDecodedMetadataAndRecoversAfterSlowCollector() = runWireBlocking { delivery ->
        val appId = AppId("secure.application.backlog")
        val wire = FakeConnectionPair(delivery)
        val aliceStore = MemorySecureIdentityStorage()
        val bobStore = MemorySecureIdentityStorage()
        val logger = RecordingLogger()
        var alice: P2pKit? = null
        var bob: P2pKit? = null
        var setupWaiter: Job? = null
        val sessions = mutableListOf<P2pSessionImpl>()
        try {
            val aliceFingerprint = previewFingerprint(appId, aliceStore)
            val bobFingerprint = previewFingerprint(appId, bobStore)
            val senderKit = createSecureTestKit(
                appId = appId,
                name = "Alice",
                store = aliceStore,
                transport = FakeDataTransport(outgoingConnection = { CopyingRawConnection(wire.a) }),
                authorization = PeerAuthorizationPolicy.PinnedOnly(setOf(bobFingerprint))
            ) {
                this.logger = logger
                // Synthetic permission/path services; kit-only native build logging is not intercepted.
                permissionManager = NoOpP2pPermissionManager()
                lifecycle { networkPathObserver = NoOpNetworkPathObserver }
            }
            alice = senderKit
            val receiverKit = createSecureTestKit(
                appId = appId,
                name = "Bob",
                store = bobStore,
                transport = FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(wire.b))),
                authorization = PeerAuthorizationPolicy.PinnedOnly(setOf(aliceFingerprint))
            ) {
                this.logger = logger
                permissionManager = NoOpP2pPermissionManager()
                lifecycle { networkPathObserver = NoOpNetworkPathObserver }
            }
            bob = receiverKit
            val incomingCall = async(start = CoroutineStart.UNDISPATCHED) { receiverKit.incomingSessions.first() }
            setupWaiter = incomingCall
            val sender = assertIs<P2pSessionImpl>(
                withTimeout(5_000) { senderKit.connect(peerForSecureKit(receiverKit)) }
            )
            sessions += sender
            val receiver = assertIs<P2pSessionImpl>(withTimeout(5_000) { incomingCall.await() })
            sessions += receiver
            assertEquals(ConnectionState.Connected, sender.state.value)
            assertEquals(ConnectionState.Connected, receiver.state.value)
            assertEquals(bobFingerprint, sender.peerIdentity.fingerprint)
            assertEquals(aliceFingerprint, receiver.peerIdentity.fingerprint)
            assertEquals(receiverKit.localPeerId, sender.peerIdentity.peerId)
            assertEquals(senderKit.localPeerId, receiver.peerIdentity.peerId)

            assertSlowCollectorAccounting(sender, receiver, logger)
        } finally {
            withContext(NonCancellable) {
                try {
                    try {
                        setupWaiter?.cancelAndJoin()
                    } finally {
                        try {
                            alice?.stop()
                        } finally {
                            bob?.stop()
                        }
                    }
                } finally {
                    try {
                        for (session in sessions) {
                            withTimeout(5_000) { session.awaitRuntimeTermination() }
                            assertEquals(0 to 0L, session.applicationBacklogForTest())
                        }
                    } finally {
                        try {
                            wire.a.close()
                        } finally {
                            wire.b.close()
                            aliceStore.clear()
                            bobStore.clear()
                        }
                    }
                }
            }
        }
        logger.assertNoUnexpectedWarnOrError()
    }

    /**
     * Android host runs the real secure manager/reader/session without kit-only native build logging.
     * This does not simulate android.util.Log, Android initialization, or physical transport services.
     * The separate kit test above remains enabled on the common JVM/Native test surfaces.
     */
    @Test
    fun pinnedSecureManagerReceiveChargesDecodedMetadataAndRecoversAfterSlowCollector() = runWireBlocking { delivery ->
        val appId = AppId("secure.manager.application.backlog")
        val wire = FakeConnectionPair(delivery)
        val aliceTransport = FakeDataTransport(outgoingConnection = { CopyingRawConnection(wire.a) })
        val bobTransport = FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(wire.b)))
        val aliceStore = MemorySecureIdentityStorage()
        val bobStore = MemorySecureIdentityStorage()
        val aliceJob = SupervisorJob(coroutineContext[Job])
        val bobJob = SupervisorJob(coroutineContext[Job])
        val logger = RecordingLogger()
        var aliceIdentity: LocalSecureIdentity? = null
        var bobIdentity: LocalSecureIdentity? = null
        var aliceManager: SessionManager? = null
        var bobManager: SessionManager? = null
        var setupWaiter: Job? = null
        val sessions = mutableListOf<P2pSessionImpl>()
        try {
            val cryptography = platformSecurityCryptography()
            val localAlice = SecureIdentityService(cryptography, aliceStore).loadOrCreate(appId)
            aliceIdentity = localAlice
            val localBob = SecureIdentityService(cryptography, bobStore).loadOrCreate(appId)
            bobIdentity = localBob
            val senderManager = secureManager(
                CoroutineScope(Dispatchers.Default + aliceJob), aliceTransport, appId,
                localAlice, localBob.fingerprint, cryptography, logger
            )
            aliceManager = senderManager
            val receiverManager = secureManager(
                CoroutineScope(Dispatchers.Default + bobJob), bobTransport, appId,
                localBob, localAlice.fingerprint, cryptography, logger
            )
            bobManager = receiverManager
            aliceTransport.start().getOrThrow()
            bobTransport.start().getOrThrow()
            receiverManager.startAcceptingIncoming(listOf(bobTransport))
            val incomingCall = async(start = CoroutineStart.UNDISPATCHED) { receiverManager.incomingSessions.first() }
            setupWaiter = incomingCall
            val peer = Peer(localBob.peerId, "Bob", currentPlatform(), setOf(TransportKind.LAN))
            val sender = assertIs<P2pSessionImpl>(
                withTimeout(5_000) {
                    senderManager.connect(peer, InternalPeer(peer, emptyList()), lifecycleGeneration = 1L)
                }
            )
            sessions += sender
            val receiver = assertIs<P2pSessionImpl>(withTimeout(5_000) { incomingCall.await() })
            sessions += receiver
            assertEquals(ConnectionState.Connected, sender.state.value)
            assertEquals(ConnectionState.Connected, receiver.state.value)
            assertEquals(localBob.fingerprint, sender.peerIdentity.fingerprint)
            assertEquals(localAlice.fingerprint, receiver.peerIdentity.fingerprint)
            assertEquals(localBob.peerId, sender.peerIdentity.peerId)
            assertEquals(localAlice.peerId, receiver.peerIdentity.peerId)
            assertSame(sender, senderManager.sessions.value.single())
            assertSame(receiver, receiverManager.sessions.value.single())
            assertSlowCollectorAccounting(sender, receiver, logger)
        } finally {
            withContext(NonCancellable) {
                cleanupEveryResource(
                    { setupWaiter?.cancelAndJoin() },
                    { aliceManager?.let { assertTrue(it.shutdownAllSessions().isEmpty()) } },
                    { bobManager?.let { assertTrue(it.shutdownAllSessions().isEmpty()) } },
                    {
                        for (session in sessions) {
                            withTimeout(5_000) { session.awaitRuntimeTermination() }
                            assertEquals(0 to 0L, session.applicationBacklogForTest())
                        }
                    },
                    { withTimeout(5_000) { aliceJob.cancelAndJoin() } },
                    { withTimeout(5_000) { bobJob.cancelAndJoin() } },
                    { aliceTransport.close() },
                    { bobTransport.close() },
                    { wire.a.close() },
                    { wire.b.close() },
                    { aliceIdentity?.clearPrivate() },
                    { bobIdentity?.clearPrivate() },
                    { aliceStore.clear() },
                    { bobStore.clear() }
                )
            }
        }
        logger.assertNoUnexpectedWarnOrError()
    }

    private fun secureManager(
        scope: CoroutineScope,
        transport: FakeDataTransport,
        appId: AppId,
        identity: LocalSecureIdentity,
        remoteFingerprint: PeerFingerprint,
        cryptography: PlatformSecurityCryptography,
        logger: RecordingLogger
    ): SessionManager = SessionManager(
        scope = scope,
        transportManager = TransportManager(listOf(transport)),
        protocol = DefaultP2pProtocol(
            clock = ::systemTimeMillis,
            logger = logger,
            version = ProtocolConstants.SECURE_VERSION
        ),
        securityMode = SecurityMode.AuthenticatedV2(PeerAuthorizationPolicy.PinnedOnly(setOf(remoteFingerprint))),
        localSecureIdentity = identity,
        authenticatedSecurity = AuthenticatedV2SecurityEngine(cryptography),
        keepAlive = KeepAliveConfig(60_000, 120_000),
        reconnectPolicy = ReconnectPolicy.Disabled,
        localAppId = appId,
        localPeerId = identity.peerId,
        localDeviceName = "Secure backlog peer",
        localPlatform = currentPlatform(),
        localTransports = setOf(TransportKind.LAN),
        clock = ::systemTimeMillis,
        monotonicClock = ::monotonicTimeMillis,
        logger = logger,
        lifecycleGate = BacklogAlwaysActiveLifecycleGate,
        strictInvariants = true
    )

    private suspend fun CoroutineScope.assertSlowCollectorAccounting(
        sender: P2pSessionImpl,
        receiver: P2pSessionImpl,
        logger: RecordingLogger
    ) {
        val subscribed = CompletableDeferred<Unit>()
        val sentinelReceived = CompletableDeferred<Unit>()
        val releaseCollector = CompletableDeferred<Unit>()
        val received = Channel<P2pMessage>(Channel.UNLIMITED)
        val sentinel = P2pMessage.Text("hold the collector")
        val collector = launch(start = CoroutineStart.UNDISPATCHED) {
            receiver.incoming.onSubscription { subscribed.complete(Unit) }.collect { message ->
                if (message == sentinel) {
                    sentinelReceived.complete(Unit)
                    releaseCollector.await()
                } else {
                    received.send(message)
                }
            }
        }
        try {
            withTimeout(5_000) { subscribed.await() }
            sender.send(sentinel)
            withTimeout(5_000) { sentinelReceived.await() }
            awaitBacklogCount(receiver, 0)

            val metadata = mutableMapOf("ascii" to "value", "unicode" to "中\uD83D\uDE00")
            val message = P2pMessage.Text("a".repeat(64 * 1_024), metadata)
            metadata.clear()
            sender.send(message)
            awaitBacklogCount(receiver, 1)
            // 512 + 2 * 65_536 + 2 * 256 + 2 * (5 + 5 + 7 + 3).
            assertEquals(1 to 132_136L, receiver.applicationBacklogForTest())

            releaseCollector.complete(Unit)
            assertEquals(message, withTimeout(5_000) { received.receive() })
            awaitBacklogCount(receiver, 0)
            assertEquals(0 to 0L, receiver.applicationBacklogForTest())

            val followup = P2pMessage.Binary(byteArrayOf(1, 2, 3), mapOf("type" to "binary"))
            sender.send(followup)
            assertEquals(followup, withTimeout(5_000) { received.receive() })
            awaitBacklogCount(receiver, 0)
            assertEquals(0 to 0L, receiver.applicationBacklogForTest())
            assertEquals(ConnectionState.Connected, sender.state.value)
            assertEquals(ConnectionState.Connected, receiver.state.value)
            logger.assertNoUnexpectedWarnOrError()
        } finally {
            withContext(NonCancellable) {
                releaseCollector.complete(Unit)
                collector.cancelAndJoin()
                received.cancel()
            }
        }
    }

    /** Attempt every owned cleanup and propagate, rather than suppress, every observed failure. */
    private suspend fun cleanupEveryResource(vararg actions: suspend () -> Unit) {
        var firstFailure: Throwable? = null
        for (action in actions) {
            try {
                action()
            } catch (failure: Throwable) {
                val first = firstFailure
                if (first == null) firstFailure = failure else first.addSuppressed(failure)
            }
        }
        firstFailure?.let { throw it }
    }

    private fun previewFingerprint(appId: AppId, store: MemorySecureIdentityStorage): PeerFingerprint {
        val identity = SecureIdentityService(platformSecurityCryptography(), store).loadOrCreate(appId)
        return try {
            identity.fingerprint
        } finally {
            identity.clearPrivate()
        }
    }

    private suspend fun awaitBacklogCount(session: P2pSessionImpl, count: Int) {
        withTimeout(5_000) {
            // The collector barrier fixes ownership; only production worker visibility is awaited here.
            while (session.applicationBacklogForTest().first != count) yield()
        }
    }
}

/** This fixture has no concurrent kit lifecycle transition; manager/session invariants stay strict. */
private object BacklogAlwaysActiveLifecycleGate : SessionLifecycleGate {
    override suspend fun isActive(expectedGeneration: Long?): Boolean = true

    override suspend fun <T : Any> commit(expectedGeneration: Long?, block: suspend () -> T): T = block()
}
