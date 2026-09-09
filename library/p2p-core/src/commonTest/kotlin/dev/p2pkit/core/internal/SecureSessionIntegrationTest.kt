package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.ExplicitSecurityRisk
import dev.p2pkit.core.FileTransferFailureKind
import dev.p2pkit.core.FileTransferPhase
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.Retryability
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.internal.security.noise.NoiseTransportEofException
import dev.p2pkit.core.security.LocalSecureIdentity
import dev.p2pkit.core.security.SecureIdentityService
import dev.p2pkit.core.security.platformSecurityCryptography
import dev.p2pkit.core.internal.security.sha256
import dev.p2pkit.core.testfixtures.CopyingRawConnection
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.MemorySecureIdentityStorage
import dev.p2pkit.core.testfixtures.RecordingLogger
import dev.p2pkit.core.testfixtures.WireDelivery
import dev.p2pkit.core.testfixtures.createSecureTestKit
import dev.p2pkit.core.testfixtures.runWireBlocking
import dev.p2pkit.core.testfixtures.withTestKit
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.PeerAuthenticationHint
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import dev.p2pkit.core.transport.TransportSecurityProfile
import dev.p2pkit.core.transfer.FileTransferDestination
import dev.p2pkit.core.transfer.FileTransferState
import dev.p2pkit.core.transfer.PreparedFileSource
import dev.p2pkit.core.transfer.Sha256Digest
import kotlin.concurrent.atomics.AtomicInt
import kotlin.concurrent.atomics.ExperimentalAtomicApi
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertTrue
import kotlinx.coroutines.async
import kotlinx.coroutines.cancel
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.channels.ClosedReceiveChannelException
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.yield
import kotlinx.io.Buffer
import kotlinx.io.IOException
import kotlinx.io.RawSink
import kotlinx.io.RawSource
import kotlinx.io.readByteArray
import kotlinx.io.write

/** End-to-end proof that SessionManager never parses protocol v2 on the raw stream. */
@OptIn(ExplicitSecurityRisk::class, ExperimentalAtomicApi::class)
class SecureSessionIntegrationTest {
    @Test
    fun secureManualPeerRequiresPinAndUsesItsRealKeyDerivedIdentity() {
        val appId = AppId("secure.session.manual")
        val remote = previewIdentity(appId, MemorySecureIdentityStorage())
        val service = SecureIdentityService(platformSecurityCryptography(), MemorySecureIdentityStorage())
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
        val registry = PeerRegistry(
            discoveryTransports = emptyList(),
            scope = scope,
            clock = { 0L },
            securityProfile = TransportSecurityProfile.AuthenticatedV2,
            peerIdFromFingerprint = { service.peerId(appId, it) }
        )
        try {
            assertFailsWith<P2pError.SecurityConfigurationInvalid> {
                registry.registerManualPeer("192.0.2.10", 40404)
            }
            val peer = registry.registerManualPeer(
                host = "192.0.2.10",
                port = 40404,
                expectedFingerprint = remote.fingerprint
            )
            assertEquals(service.peerId(appId, remote.fingerprint), peer.id)
            val hint = assertNotNull(registry.internalPeer(peer.id)?.authenticationHint)
            assertEquals(
                PeerAuthenticationHint.TrustedApplicationPin(remote.fingerprint),
                hint
            )
        } finally {
            scope.cancel()
            remote.clearPrivate()
        }
    }

    @Test
    fun cancellationDuringBlockedNoiseWriteClosesRawRemovesPendingAndAllowsRetry() = runBlocking {
        val appId = AppId("secure.session.cancel-retry")
        val blockedPair = FakeConnectionPair()
        blockedPair.a.suspendWrites()
        val blockedObserved = ObservedRawConnection(blockedPair.a)
        val retryPair = FakeConnectionPair()
        var dial = 0
        withTestKit(
            create = { recorder ->
                createSecureTestKit(
                    appId,
                    "Alice",
                    MemorySecureIdentityStorage(),
                    FakeDataTransport(outgoingConnection = {
                        if (dial++ == 0) blockedObserved
                        else CopyingRawConnection(retryPair.a)
                    }),
                    PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
                ) {
                    logger = recorder
                }
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    createSecureTestKit(
                        appId,
                        "Bob",
                        MemorySecureIdentityStorage(),
                        FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(retryPair.b))),
                        PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
                    ) {
                        logger = recorder
                    }
                }
            ) { bob ->
                try {
                    val first = async { alice.connect(peerFor(bob)) }
                    withTimeout(2_000) {
                        while (blockedPair.a.writeAttempts == 0) yield()
                    }
                    first.cancel(CancellationException("cancel blocked secure setup"))
                    val cancellation = assertFailsWith<CancellationException> { first.await() }
                    assertEquals("cancel blocked secure setup", cancellation.message)
                    assertEquals(ConnectionState.Closed, blockedPair.a.state.value)
                    assertEquals(1, blockedObserved.closeCalls)
                    assertTrue(alice.sessions.value.isEmpty())

                    val incoming = async { withTimeout(5_000) { bob.incomingSessions.first() } }
                    bob.start()
                    val retried = withTimeout(5_000) { alice.connect(peerFor(bob)) }
                    assertEquals(bob.localFingerprint, retried.peerIdentity.fingerprint)
                    assertEquals(alice.localFingerprint, incoming.await().peerIdentity.fingerprint)
                    assertEquals(1, alice.sessions.value.size)
                } finally {
                    blockedPair.a.resumeWrites()
                }
            }
        }
    }

    @Test
    fun secureSetupDeadlineIncludesInitialPrefaceWriteAndClosesRaw() = runBlocking {
        val appId = AppId("secure.session.full-setup-timeout")
        val blockedPair = FakeConnectionPair()
        blockedPair.a.writeLatencyMillis = 10_000
        withTestKit(
            create = { recorder ->
                createSecureTestKit(
                    appId,
                    "Alice",
                    MemorySecureIdentityStorage(),
                    FakeDataTransport(outgoingConnection = { blockedPair.a }),
                    PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp,
                    setupTimeoutMillis = 100
                ) {
                    logger = recorder
                }
            }
        ) { alice ->
            val failure = assertFailsWith<P2pError.AuthenticationFailed> {
                withTimeout(5_000) {
                    alice.connect(
                        Peer(
                            id = PeerId("unresponsive-secure-peer"),
                            name = "Unresponsive peer",
                            platform = Platform.JVM_DESKTOP,
                            supportedTransports = setOf(TransportKind.LAN)
                        )
                    )
                }
            }
            assertTrue(failure.message.orEmpty().contains("timed out after 100 ms"))
            assertEquals(1, blockedPair.a.writeAttempts)
            assertEquals(ConnectionState.Closed, blockedPair.a.state.value)
            assertTrue(alice.sessions.value.isEmpty())
        }
    }

    @Test
    fun callerDeadlineDuringSecureSetupRemainsCancellationAndClosesRaw() = runBlocking {
        val appId = AppId("secure.session.caller-timeout")
        val blockedPair = FakeConnectionPair()
        blockedPair.a.writeLatencyMillis = 10_000
        withTestKit(
            create = { recorder ->
                createSecureTestKit(
                    appId,
                    "Alice",
                    MemorySecureIdentityStorage(),
                    FakeDataTransport(outgoingConnection = { blockedPair.a }),
                    PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp,
                    setupTimeoutMillis = 5_000
                ) {
                    logger = recorder
                }
            }
        ) { alice ->
            assertFailsWith<TimeoutCancellationException> {
                withTimeout(500) {
                    alice.connect(
                        Peer(
                            id = PeerId("caller-timeout-peer"),
                            name = "Unresponsive peer",
                            platform = Platform.JVM_DESKTOP,
                            supportedTransports = setOf(TransportKind.LAN)
                        )
                    )
                }
            }
            assertEquals(1, blockedPair.a.writeAttempts, "caller timeout must occur inside secure setup")
            assertEquals(ConnectionState.Closed, blockedPair.a.state.value)
            assertTrue(alice.sessions.value.isEmpty())
        }
    }

    @Test
    fun reconnectRemainsPinnedToTheInitiallyAuthenticatedIdentity() = runBlocking {
        val appId = AppId("secure.session.reconnect-pin")
        val firstPair = FakeConnectionPair()
        val attackerPair = FakeConnectionPair()
        var dial = 0
        withTestKit(
            create = { recorder ->
                createSecureTestKit(
                    appId,
                    "Bob",
                    MemorySecureIdentityStorage(),
                    FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(firstPair.b))),
                    PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
                ) {
                    logger = recorder
                }
            }
        ) { bob ->
            withTestKit(
                create = { recorder ->
                    createSecureTestKit(
                        appId,
                        "Attacker",
                        MemorySecureIdentityStorage(),
                        FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(attackerPair.b))),
                        PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
                    ) {
                        logger = recorder
                    }
                },
                verifyDiagnostics = ::assertInitiatorAbortedBeforeThirdFlight
            ) { attacker ->
                withTestKit(
                    create = { recorder ->
                        createSecureTestKit(
                            appId,
                            "Alice",
                            MemorySecureIdentityStorage(),
                            FakeDataTransport(outgoingConnection = {
                                if (dial++ == 0) CopyingRawConnection(firstPair.a)
                                else CopyingRawConnection(attackerPair.a)
                            }),
                            PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp,
                            reconnect = ReconnectPolicy.Enabled(maxAttempts = 1, retryDelayMillis = 0)
                        ) {
                            logger = recorder
                        }
                    },
                    verifyDiagnostics = { recorder ->
                        val expected = RecordingLogger.Entry(
                            RecordingLogger.Level.WARN,
                            "reconnect: attempt=1/1 peer=${bob.localPeerId.value.take(8)} " +
                                "name=Bob FAILED dialed=LAN:?:? source=FALLBACK " +
                                "reason=AuthenticatedIdentityMismatch: " +
                                "Authenticated remote identity did not match the selected peer"
                        )
                        recorder.assertNoUnexpectedWarnOrError { it == expected }
                        assertEquals(1, recorder.entries.count { it == expected })
                    }
                ) { alice ->
                    val bobIncoming = async { withTimeout(5_000) { bob.incomingSessions.first() } }
                    bob.start()
                    attacker.start()
                    val session = withTimeout(5_000) { alice.connect(peerFor(bob)) }
                    bobIncoming.await()
                    val originalIdentity = session.peerIdentity
                    assertEquals(bob.localFingerprint, originalIdentity.fingerprint)

                    firstPair.hangUp(firstPair.b)
                    withTimeout(5_000) {
                        session.state.first { it == ConnectionState.Failed }
                    }
                    assertEquals(originalIdentity, session.peerIdentity)
                    assertTrue(attacker.sessions.value.isEmpty())
                    assertEquals(2, dial)
                }
            }
        }
    }

    @Test
    fun pinnedSecureSessionsAuthenticateBeforeHelloAndExposeOnlyCiphertextOnRawWire() =
        runWireBlocking { delivery ->
            val appId = AppId("secure.session.pinned")
            val aliceStore = MemorySecureIdentityStorage()
            val bobStore = MemorySecureIdentityStorage()
            val aliceIdentity = previewIdentity(appId, aliceStore)
            val bobIdentity = previewIdentity(appId, bobStore)
            val pair = FakeConnectionPair(delivery)
            val aliceRaw = ObservedRawConnection(pair.a)
            val bobRaw = ObservedRawConnection(pair.b)
            try {
                withTestKit(
                    create = { recorder ->
                        createSecureTestKit(
                            appId = appId,
                            name = "Alice secret hello name",
                            store = aliceStore,
                            transport = FakeDataTransport(outgoingConnection = { aliceRaw }),
                            authorization = PeerAuthorizationPolicy.PinnedOnly(setOf(bobIdentity.fingerprint))
                        ) {
                            logger = recorder
                        }
                    }
                ) { alice ->
                    withTestKit(
                        create = { recorder ->
                            createSecureTestKit(
                                appId = appId,
                                name = "Bob secret hello name",
                                store = bobStore,
                                transport = FakeDataTransport(preStagedIncoming = listOf(bobRaw)),
                                authorization = PeerAuthorizationPolicy.PinnedOnly(setOf(aliceIdentity.fingerprint))
                            ) {
                                logger = recorder
                            }
                        }
                    ) { bob ->
                        val incomingSession = async { withTimeout(5_000) { bob.incomingSessions.first() } }
                        bob.start()
                        val outgoing = withTimeout(5_000) { alice.connect(peerFor(bob)) }
                        val incoming = incomingSession.await()

                        assertEquals(bobIdentity.peerId, outgoing.peerIdentity.peerId)
                        assertEquals(bobIdentity.fingerprint, outgoing.peerIdentity.fingerprint)
                        assertEquals(aliceIdentity.peerId, incoming.peerIdentity.peerId)
                        assertEquals(aliceIdentity.fingerprint, incoming.peerIdentity.fingerprint)
                        assertEquals(1, aliceRaw.readCalls)
                        assertEquals(1, bobRaw.readCalls)

                        val secret = "application plaintext must never reach raw TCP"
                        val subscribed = CompletableDeferred<Unit>()
                        val received = async {
                            withTimeout(5_000) {
                                incoming.incoming
                                    .onSubscription { subscribed.complete(Unit) }
                                    .first()
                            }
                        }
                        subscribed.await()
                        val metadata = mapOf("content-type" to "text/plain", "trace" to "secure-v2")
                        outgoing.send(P2pMessage.Text(secret, metadata))
                        assertEquals(P2pMessage.Text(secret, metadata), received.await())

                        val binary = ByteArray(34_000) { (it * 17).toByte() }
                        val binarySubscribed = CompletableDeferred<Unit>()
                        val binaryReceived = async {
                            withTimeout(5_000) {
                                outgoing.incoming.onSubscription { binarySubscribed.complete(Unit) }.first()
                            }
                        }
                        binarySubscribed.await()
                        incoming.send(P2pMessage.Binary(binary, mapOf("kind" to "reverse-binary")))
                        val binaryMessage = assertIs<P2pMessage.Binary>(binaryReceived.await())
                        assertContentEquals(binary, binaryMessage.bytes)
                        assertEquals(mapOf("kind" to "reverse-binary"), binaryMessage.metadata)

                        val aliceWire = aliceRaw.writtenBytes()
                        assertFalse(aliceWire.containsSubsequence(secret.encodeToByteArray()))
                        assertFalse(aliceWire.containsSubsequence("Alice secret hello name".encodeToByteArray()))
                        assertFalse(aliceWire.containsSubsequence(appId.value.encodeToByteArray()))
                        assertTrue(aliceWire.isNotEmpty())

                        outgoing.close()
                        assertEquals(ConnectionState.Closed, outgoing.state.value)
                        assertEquals(
                            ConnectionState.Closed,
                            withTimeout(5_000) { incoming.state.first { it != ConnectionState.Connected } }
                        )
                        withTimeout(5_000) { assertIs<P2pSessionImpl>(incoming).awaitRuntimeTermination() }
                    }
                }
            } finally {
                aliceIdentity.clearPrivate()
                bobIdentity.clearPrivate()
            }
        }

    @Test
    fun securePreparedTransferCompletesAfterReceiverCommit() = runWireBlocking { delivery ->
        val appId = AppId("secure.session.file-commit")
        val pair = FakeConnectionPair(delivery)
        withTestKit(
            create = { recorder ->
                createSecureTestKit(
                    appId,
                    "Alice",
                    MemorySecureIdentityStorage(),
                    FakeDataTransport(outgoingConnection = { CopyingRawConnection(pair.a) }),
                    PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
                ) {
                    logger = recorder
                }
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    createSecureTestKit(
                        appId,
                        "Bob",
                        MemorySecureIdentityStorage(),
                        FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(pair.b))),
                        PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
                    ) {
                        logger = recorder
                    }
                }
            ) { bob ->
                val incomingDeferred = async { withTimeout(5_000) { bob.incomingSessions.first() } }
                bob.start()
                val outgoing = withTimeout(5_000) { alice.connect(peerFor(bob)) }
                val incoming = incomingDeferred.await()
                val bytes = ByteArray(130_000) { (it and 0xff).toByte() }
                val sender = outgoing.sendFile("secure.bin", "application/octet-stream", TestPreparedSource(bytes))
                val offer = withTimeout(5_000) { incoming.pendingFileOffers.first { it.isNotEmpty() }.single() }
                val destination = TestCommitDestination()
                val receiver = offer.accept(destination)

                withTimeout(5_000) { sender.state.first { it is FileTransferState.Completed } }
                withTimeout(5_000) { receiver.state.first { it is FileTransferState.Completed } }
                assertTrue(destination.committed)
                assertContentEquals(bytes, destination.buffer.readByteArray())
            }
        }
    }

    @Test
    fun securePreparedSourceGrowthFailsBothPeersBeforeCommit() = runBlocking {
        val appId = AppId("secure.session.file-source-growth")
        val pair = FakeConnectionPair()
        withTestKit(
            create = { recorder ->
                createSecureTestKit(
                    appId,
                    "Alice",
                    MemorySecureIdentityStorage(),
                    FakeDataTransport(outgoingConnection = { CopyingRawConnection(pair.a) }),
                    PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
                ) {
                    logger = recorder
                }
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    createSecureTestKit(
                        appId,
                        "Bob",
                        MemorySecureIdentityStorage(),
                        FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(pair.b))),
                        PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
                    ) {
                        logger = recorder
                    }
                }
            ) { bob ->
                val incomingDeferred = async { withTimeout(5_000) { bob.incomingSessions.first() } }
                bob.start()
                val outgoing = withTimeout(5_000) { alice.connect(peerFor(bob)) }
                val incoming = incomingDeferred.await()
                val snapshot = ByteArray(4_096) { (it * 17).toByte() }
                val grown = snapshot + byteArrayOf(99)
                val sender = outgoing.sendFile(
                    "grown.bin",
                    "application/octet-stream",
                    TestPreparedSource(content = grown, snapshot = snapshot)
                )
                val offer = withTimeout(5_000) {
                    incoming.pendingFileOffers.first { it.isNotEmpty() }.single()
                }
                val destination = TestCommitDestination()
                val receiver = offer.accept(destination)

                val senderFailure = withTimeout(5_000) {
                    assertIs<FileTransferState.Failed>(
                        sender.state.first { it is FileTransferState.Failed }
                    )
                }
                val receiverFailure = withTimeout(5_000) {
                    assertIs<FileTransferState.Failed>(
                        receiver.state.first { it is FileTransferState.Failed }
                    )
                }
                val senderError = assertIs<P2pError.FileTransferFailed>(senderFailure.error)
                val receiverError = assertIs<P2pError.FileTransferFailed>(receiverFailure.error)
                assertEquals(FileTransferFailureKind.SOURCE_CHANGED, senderError.kind)
                assertEquals(FileTransferPhase.SOURCE_READ, senderError.phase)
                assertEquals(FileTransferFailureKind.SOURCE_CHANGED, receiverError.kind)
                assertEquals(FileTransferPhase.SOURCE_READ, receiverError.phase)
                assertFalse(destination.committed)
                assertEquals(0L, destination.buffer.size)
            }
        }
    }

    @Test
    fun secureReceiverCommitFailureReachesSenderAsTypedTerminalResult() = runWireBlocking { delivery ->
        val appId = AppId("secure.session.file-commit-failure")
        val pair = FakeConnectionPair(delivery)
        withTestKit(
            create = { recorder ->
                createSecureTestKit(
                    appId,
                    "Alice",
                    MemorySecureIdentityStorage(),
                    FakeDataTransport(outgoingConnection = { CopyingRawConnection(pair.a) }),
                    PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
                ) {
                    logger = recorder
                }
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    createSecureTestKit(
                        appId,
                        "Bob",
                        MemorySecureIdentityStorage(),
                        FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(pair.b))),
                        PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
                    ) {
                        logger = recorder
                    }
                }
            ) { bob ->
                val incomingDeferred = async { withTimeout(5_000) { bob.incomingSessions.first() } }
                bob.start()
                val outgoing = withTimeout(5_000) { alice.connect(peerFor(bob)) }
                val incoming = incomingDeferred.await()
                val bytes = ByteArray(4096) { (it * 31).toByte() }
                val sender = outgoing.sendFile("commit-fails.bin", null, TestPreparedSource(bytes))
                val offer = withTimeout(5_000) {
                    incoming.pendingFileOffers.first { it.isNotEmpty() }.single()
                }
                val receiver = offer.accept(
                    TestCommitDestination(commitFailure = IllegalStateException("fsync failed"))
                )

                val senderFailure = withTimeout(5_000) {
                    assertIs<FileTransferState.Failed>(
                        sender.state.first { it is FileTransferState.Failed }
                    )
                }
                val receiverFailure = withTimeout(5_000) {
                    assertIs<FileTransferState.Failed>(
                        receiver.state.first { it is FileTransferState.Failed }
                    )
                }
                val senderError = assertIs<P2pError.FileTransferFailed>(senderFailure.error)
                val receiverError = assertIs<P2pError.FileTransferFailed>(receiverFailure.error)
                assertEquals(FileTransferFailureKind.STORAGE, senderError.kind)
                assertEquals(FileTransferPhase.DURABLE_COMMIT, senderError.phase)
                assertEquals(FileTransferFailureKind.STORAGE, receiverError.kind)
                assertEquals(FileTransferPhase.DURABLE_COMMIT, receiverError.phase)
            }
        }
    }

    @Test
    fun destinationAuthenticationFailureIsIsolatedFromPinnedSecureSessions() = runWireBlocking { delivery ->
        assertDestinationFailureIsolatedFromPinnedSessions(delivery, cancelDuringAbort = false)
    }

    @Test
    fun cancelledDestinationFailureCleanupIsIsolatedFromPinnedSecureSessions() = runWireBlocking { delivery ->
        assertDestinationFailureIsolatedFromPinnedSessions(delivery, cancelDuringAbort = true)
    }

    private suspend fun CoroutineScope.assertDestinationFailureIsolatedFromPinnedSessions(
        delivery: WireDelivery,
        cancelDuringAbort: Boolean
    ) {
        val appId = AppId("secure.session.destination-auth-failure")
        val aliceStore = MemorySecureIdentityStorage()
        val bobStore = MemorySecureIdentityStorage()
        val pair = FakeConnectionPair(delivery)
        var aliceIdentity: LocalSecureIdentity? = null
        var bobIdentity: LocalSecureIdentity? = null
        val acceptingCaller = Job(coroutineContext[Job])
        val abortRelease = CompletableDeferred<Unit>()
        try {
            val aliceLocal = previewIdentity(appId, aliceStore).also { aliceIdentity = it }
            val bobLocal = previewIdentity(appId, bobStore).also { bobIdentity = it }
            withTestKit(
                create = { recorder ->
                    createSecureTestKit(
                        appId,
                        "Alice",
                        aliceStore,
                        FakeDataTransport(outgoingConnection = { CopyingRawConnection(pair.a) }),
                        PeerAuthorizationPolicy.PinnedOnly(setOf(bobLocal.fingerprint))
                    ) {
                        logger = recorder
                    }
                }
            ) { aliceKit ->
                withTestKit(
                    create = { recorder ->
                        createSecureTestKit(
                            appId,
                            "Bob",
                            bobStore,
                            FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(pair.b))),
                            PeerAuthorizationPolicy.PinnedOnly(setOf(aliceLocal.fingerprint))
                        ) {
                            logger = recorder
                        }
                    }
                ) { bobKit ->
                    try {
                        val incomingReady = CompletableDeferred<Unit>()
                        val incomingDeferred = async {
                            withTimeout(5_000) {
                                bobKit.incomingSessions.onSubscription { incomingReady.complete(Unit) }.first()
                            }
                        }
                        withTimeout(5_000) { incomingReady.await() }
                        bobKit.start()
                        val outgoing = withTimeout(5_000) { aliceKit.connect(peerFor(bobKit)) }
                        val incoming = incomingDeferred.await()
                        assertEquals(bobLocal.fingerprint, outgoing.peerIdentity.fingerprint)
                        assertEquals(aliceLocal.fingerprint, incoming.peerIdentity.fingerprint)

                        val bytes = ByteArray(4_096) { (it * 31).toByte() }
                        val sourceOpens = AtomicInt(0)
                        val failedSource = object : PreparedFileSource by TestPreparedSource(bytes) {
                            override fun open(): RawSource {
                                sourceOpens.addAndFetch(1)
                                return Buffer().apply { write(bytes) }
                            }
                        }
                        val failedSender = outgoing.sendFile("destination-fails.bin", null, failedSource)
                        val goodSender = outgoing.sendFile("unaffected.bin", null, TestPreparedSource(bytes))
                        val offers = withTimeout(5_000) { incoming.pendingFileOffers.first { it.size == 2 } }
                        val failedOffer = offers.single { it.id == failedSender.id }
                        val goodOffer = offers.single { it.id == goodSender.id }
                        val callbackFailure = if (cancelDuringAbort) {
                            IOException("synthetic local destination open failure")
                        } else {
                            P2pError.AuthenticationFailed("synthetic local destination credential failure")
                        }
                        val openCount = AtomicInt(0)
                        val commitCount = AtomicInt(0)
                        val abortCount = AtomicInt(0)
                        val aborted = CompletableDeferred<P2pError.FileTransferFailed?>()
                        val destination = object : FileTransferDestination {
                            override fun openSink(): RawSink {
                                openCount.addAndFetch(1)
                                throw callbackFailure
                            }

                            override suspend fun commit() {
                                commitCount.addAndFetch(1)
                            }

                            override suspend fun abort(cause: P2pError.FileTransferFailed?) {
                                abortCount.addAndFetch(1)
                                aborted.complete(cause)
                                if (cancelDuringAbort) abortRelease.await()
                            }
                        }
                        val error = if (cancelDuringAbort) {
                            val failureAtCallBoundary = CompletableDeferred<Throwable?>()
                            val accepting = CoroutineScope(coroutineContext + acceptingCaller).async {
                                runCatching { failedOffer.accept(destination) }.also {
                                    failureAtCallBoundary.complete(it.exceptionOrNull())
                                }
                            }
                            val abortCause = withTimeout(5_000) { aborted.await() }
                            acceptingCaller.cancel(
                                CancellationException("external cancellation during destination abort")
                            )
                            abortRelease.complete(Unit)
                            assertFailsWith<CancellationException> { withTimeout(5_000) { accepting.await() } }
                            assertIs<CancellationException>(withTimeout(5_000) { failureAtCallBoundary.await() })
                            assertNotNull(abortCause)
                        } else {
                            assertFailsWith<P2pError.FileTransferFailed> {
                                withTimeout(5_000) { failedOffer.accept(destination) }
                            }
                        }
                        assertEquals(FileTransferFailureKind.STORAGE, error.kind)
                        assertEquals(FileTransferPhase.ACCEPT, error.phase)
                        assertEquals(Retryability.RETRY_AFTER_USER_ACTION, error.retryability)
                        assertTrue(error.cause === callbackFailure)
                        assertTrue(withTimeout(5_000) { aborted.await() } === error)
                        val failedReceiver = assertIs<IncomingFileSession>(failedOffer)
                        assertTrue(assertIs<FileTransferState.Failed>(failedReceiver.state.value).error === error)
                        assertFalse(failedReceiver.retainsReceiver())
                        val remoteError = assertIs<P2pError.FileTransferFailed>(
                            assertIs<FileTransferState.Failed>(
                                withTimeout(5_000) { failedSender.state.first { it is FileTransferState.Failed } }
                            ).error
                        )
                        assertEquals(FileTransferFailureKind.STORAGE, remoteError.kind)
                        assertEquals(FileTransferPhase.ACCEPT, remoteError.phase)
                        assertEquals(Retryability.RETRY_AFTER_USER_ACTION, remoteError.retryability)
                        assertEquals("receiver storage failure", remoteError.reason)
                        assertEquals(0, sourceOpens.load(), "a failed destination must never accept the source")
                        assertEquals(1, openCount.load())
                        assertEquals(1, abortCount.load())
                        assertEquals(0, commitCount.load())
                        assertEquals(listOf(goodOffer.id), incoming.pendingFileOffers.value.map { it.id })

                        val goodDestination = TestCommitDestination()
                        val goodReceiver = withTimeout(5_000) { goodOffer.accept(goodDestination) }
                        withTimeout(5_000) { goodSender.state.first { it is FileTransferState.Completed } }
                        withTimeout(5_000) { goodReceiver.state.first { it is FileTransferState.Completed } }
                        assertTrue(goodDestination.committed)
                        assertContentEquals(bytes, goodDestination.buffer.readByteArray())
                        assertTrue(incoming.pendingFileOffers.value.isEmpty())
                        val messageReady = CompletableDeferred<Unit>()
                        val message = async {
                            withTimeout(5_000) {
                                incoming.incoming.onSubscription { messageReady.complete(Unit) }.first()
                            }
                        }
                        withTimeout(5_000) { messageReady.await() }
                        withTimeout(5_000) { outgoing.send(P2pMessage.Text("session survives local storage failure")) }
                        assertEquals(P2pMessage.Text("session survives local storage failure"), message.await())
                        assertEquals(ConnectionState.Connected, outgoing.state.value)
                        assertEquals(ConnectionState.Connected, incoming.state.value)
                    } finally {
                        withContext(NonCancellable) {
                            abortRelease.complete(Unit)
                            acceptingCaller.cancelAndJoin()
                        }
                    }
                }
            }
        } finally {
            withContext(NonCancellable) {
                abortRelease.complete(Unit)
                acceptingCaller.cancelAndJoin()
                try {
                    pair.a.close()
                } finally {
                    try {
                        pair.b.close()
                    } finally {
                        aliceIdentity?.clearPrivate()
                        bobIdentity?.clearPrivate()
                        aliceStore.clear()
                        bobStore.clear()
                    }
                }
            }
        }
    }

    @Test
    fun kitSnapshotsCallerOwnedPinnedAuthorizationSets() = runBlocking {
        val appId = AppId("secure.session.pin-snapshot")
        val aliceStore = MemorySecureIdentityStorage()
        val bobStore = MemorySecureIdentityStorage()
        val aliceIdentity = previewIdentity(appId, aliceStore)
        val bobIdentity = previewIdentity(appId, bobStore)
        val alicePins = mutableSetOf(bobIdentity.fingerprint)
        val bobPins = mutableSetOf(aliceIdentity.fingerprint)
        val pair = FakeConnectionPair()
        try {
            withTestKit(
                create = { recorder ->
                    createSecureTestKit(
                        appId,
                        "Alice",
                        aliceStore,
                        FakeDataTransport(outgoingConnection = { CopyingRawConnection(pair.a) }),
                        PeerAuthorizationPolicy.PinnedOnly(alicePins)
                    ) {
                        logger = recorder
                    }
                }
            ) { alice ->
                withTestKit(
                    create = { recorder ->
                        createSecureTestKit(
                            appId,
                            "Bob",
                            bobStore,
                            FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(pair.b))),
                            PeerAuthorizationPolicy.PinnedOnly(bobPins)
                        ) {
                            logger = recorder
                        }
                    }
                ) { bob ->
                    // Mutation after construction must not alter the kit-owned policy.
                    alicePins.clear()
                    bobPins.clear()
                    val incoming = async { withTimeout(5_000) { bob.incomingSessions.first() } }
                    bob.start()
                    val outgoing = withTimeout(5_000) { alice.connect(peerFor(bob)) }
                    assertEquals(bobIdentity.fingerprint, outgoing.peerIdentity.fingerprint)
                    assertEquals(aliceIdentity.fingerprint, incoming.await().peerIdentity.fingerprint)
                }
            }
        } finally {
            aliceIdentity.clearPrivate()
            bobIdentity.clearPrivate()
        }
    }

    @Test
    fun exactPerConnectPinAuthorizesRejectUnknownWithoutTrustingDiscoveryMetadata() = runBlocking {
        val appId = AppId("secure.session.per-connect")
        val aliceStore = MemorySecureIdentityStorage()
        val bobStore = MemorySecureIdentityStorage()
        val aliceIdentity = previewIdentity(appId, aliceStore)
        val bobIdentity = previewIdentity(appId, bobStore)
        val pair = FakeConnectionPair()
        try {
            withTestKit(
                create = { recorder ->
                    createSecureTestKit(
                        appId,
                        "Alice",
                        aliceStore,
                        FakeDataTransport(outgoingConnection = { CopyingRawConnection(pair.a) }),
                        PeerAuthorizationPolicy.RejectUnknown
                    ) {
                        logger = recorder
                    }
                }
            ) { alice ->
                withTestKit(
                    create = { recorder ->
                        createSecureTestKit(
                            appId,
                            "Bob",
                            bobStore,
                            FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(pair.b))),
                            PeerAuthorizationPolicy.PinnedOnly(setOf(aliceIdentity.fingerprint))
                        ) {
                            logger = recorder
                        }
                    }
                ) { bob ->
                    val incoming = async { withTimeout(5_000) { bob.incomingSessions.first() } }
                    bob.start()
                    val session = withTimeout(5_000) {
                        alice.connect(peerFor(bob), bobIdentity.fingerprint)
                    }
                    assertEquals(bobIdentity.fingerprint, session.peerIdentity.fingerprint)
                    assertEquals(aliceIdentity.fingerprint, incoming.await().peerIdentity.fingerprint)
                }
            }
        } finally {
            aliceIdentity.clearPrivate()
            bobIdentity.clearPrivate()
        }
    }

    @Test
    fun defaultRejectUnknownFailsClosedBeforePublishingEitherSession() = runBlocking {
        val appId = AppId("secure.session.reject-unknown")
        val aliceStore = MemorySecureIdentityStorage()
        val bobStore = MemorySecureIdentityStorage()
        val pair = FakeConnectionPair()
        withTestKit(
            create = { recorder ->
                createSecureTestKit(
                    appId,
                    "Alice",
                    aliceStore,
                    FakeDataTransport(outgoingConnection = { CopyingRawConnection(pair.a) }),
                    PeerAuthorizationPolicy.RejectUnknown
                ) {
                    logger = recorder
                }
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    createSecureTestKit(
                        appId,
                        "Bob",
                        bobStore,
                        FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(pair.b))),
                        PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
                    ) {
                        logger = recorder
                    }
                },
                verifyDiagnostics = ::assertInitiatorAbortedBeforeThirdFlight
            ) { bob ->
                bob.start()
                assertFailsWith<P2pError.AuthorizationRejected> {
                    withTimeout(5_000) { alice.connect(peerFor(bob)) }
                }
                assertTrue(alice.sessions.value.isEmpty())
                assertTrue(bob.sessions.value.isEmpty())
                assertEquals(ConnectionState.Closed, pair.a.state.value)
            }
        }
    }

    @Test
    fun copiedVictimPeerIdCannotBeClaimedByAnAttackersDifferentKey() = runBlocking {
        val appId = AppId("secure.session.identity-copy")
        val aliceStore = MemorySecureIdentityStorage()
        val victimStore = MemorySecureIdentityStorage()
        val attackerStore = MemorySecureIdentityStorage()
        val victim = previewIdentity(appId, victimStore)
        val pair = FakeConnectionPair()
        try {
            withTestKit(
                create = { recorder ->
                    createSecureTestKit(
                        appId,
                        "Alice",
                        aliceStore,
                        FakeDataTransport(outgoingConnection = { CopyingRawConnection(pair.a) }),
                        PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
                    ) {
                        logger = recorder
                    }
                }
            ) { alice ->
                withTestKit(
                    create = { recorder ->
                        createSecureTestKit(
                            appId,
                            "Attacker",
                            attackerStore,
                            FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(pair.b))),
                            PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
                        ) {
                            logger = recorder
                        }
                    },
                    verifyDiagnostics = ::assertInitiatorAbortedBeforeThirdFlight
                ) { attacker ->
                    val copiedClaim = Peer(
                        id = victim.peerId,
                        name = "Victim",
                        platform = Platform.JVM_DESKTOP,
                        supportedTransports = setOf(TransportKind.LAN)
                    )
                    attacker.start()
                    assertFailsWith<P2pError.AuthenticatedIdentityMismatch> {
                        withTimeout(5_000) { alice.connect(copiedClaim) }
                    }
                    assertTrue(alice.sessions.value.isEmpty())
                    assertTrue(attacker.sessions.value.isEmpty())
                }
            }
        } finally {
            victim.clearPrivate()
        }
    }

    @Test
    fun differentAppIdsAndExplicitLegacyNeverNegotiateOrFallBack() = runBlocking {
        assertProfileMismatch(
            aliceAppId = AppId("secure.session.app-a"),
            bobAppId = AppId("secure.session.app-b"),
            bobLegacy = false
        )
        assertProfileMismatch(
            aliceAppId = AppId("secure.session.no-fallback"),
            bobAppId = AppId("secure.session.no-fallback"),
            bobLegacy = true
        )
    }

    private suspend fun assertProfileMismatch(
        aliceAppId: AppId,
        bobAppId: AppId,
        bobLegacy: Boolean
    ) {
        val pair = FakeConnectionPair()
        withTestKit(
            create = { recorder ->
                createSecureTestKit(
                    aliceAppId,
                    "Alice",
                    MemorySecureIdentityStorage(),
                    FakeDataTransport(outgoingConnection = { CopyingRawConnection(pair.a) }),
                    PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
                ) {
                    logger = recorder
                }
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    if (bobLegacy) {
                        legacyKit(
                            bobAppId,
                            FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(pair.b))),
                            recording = recorder
                        )
                    } else {
                        createSecureTestKit(
                            bobAppId,
                            "Bob",
                            MemorySecureIdentityStorage(),
                            FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(pair.b))),
                            PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
                        ) {
                            logger = recorder
                        }
                    }
                },
                verifyDiagnostics = { recorder ->
                    if (bobLegacy) {
                        assertAtMostOneIncomingSetupFailure(recorder) { failure ->
                            val connection = assertIs<P2pError.ConnectionFailed>(failure)
                            val eof = assertIs<ClosedReceiveChannelException>(connection.cause)
                            assertTrue(eof.suppressedExceptions.isEmpty())
                        }
                    } else {
                        assertInitiatorAbortedBeforeThirdFlight(recorder)
                    }
                }
            ) { bob ->
                bob.start()
                assertFailsWith<P2pError.AuthenticationFailed> {
                    withTimeout(5_000) { alice.connect(peerFor(bob)) }
                }
                assertTrue(alice.sessions.value.isEmpty())
                assertTrue(bob.sessions.value.isEmpty())
            }
        }
    }

    @Suppress("DEPRECATION")
    private fun legacyKit(
        appId: AppId,
        transport: FakeDataTransport,
        recording: P2pLogger
    ): P2pKit = P2pKit.create {
        logger = recording
        this.appId = appId
        deviceName = "Legacy Bob"
        peerIdStorage = InMemoryPeerIdStorage(PeerId("legacy-bob"))
        security { mode = SecurityMode.NoneForMvp }
        keepAlive {
            pingIntervalMillis = 60_000
            timeoutMillis = 120_000
        }
        transports { register(SecureSessionFactory(transport)) }
    }

    // These tests abort the initiator after the responder's second Noise flight. A single
    // responder setup may report that EOF, or be cancelled by the test's terminal stop first.
    // The exact local rejection/state assertions in each test remain mandatory in either race.
    private fun assertInitiatorAbortedBeforeThirdFlight(recorder: RecordingLogger) {
        assertAtMostOneIncomingSetupFailure(recorder) { failure ->
            val authentication = assertIs<P2pError.AuthenticationFailed>(failure)
            assertEquals("Authenticated protocol v2 setup failed", authentication.reason)
            val eof = assertIs<NoiseTransportEofException>(authentication.cause)
            assertEquals("Raw connection ended before 2 bytes were available", eof.message)
            assertTrue(eof.suppressedExceptions.isEmpty())
        }
    }

    private fun assertAtMostOneIncomingSetupFailure(
        recorder: RecordingLogger,
        verifyFailure: (Throwable) -> Unit
    ) {
        val diagnostics = recorder.entries.filter {
            it.level == RecordingLogger.Level.WARN || it.level == RecordingLogger.Level.ERROR
        }
        // One controlled inbound attempt; not a count derived from however many failures occurred.
        assertTrue(diagnostics.size <= 1, "one rejected setup must not become a warning/retry stream")
        diagnostics.forEach { entry ->
            assertEquals(RecordingLogger.Level.WARN, entry.level)
            assertEquals("Incoming session setup failed", entry.message)
            val failure = assertNotNull(entry.throwable)
            assertTrue(failure.suppressedExceptions.isEmpty(), "cleanup failure is never an expected rejection")
            verifyFailure(failure)
        }
    }

    private fun previewIdentity(
        appId: AppId,
        store: SecureIdentityStorage
    ): LocalSecureIdentity = SecureIdentityService(platformSecurityCryptography(), store)
        .loadOrCreate(appId)

    private fun peerFor(kit: P2pKit): Peer = Peer(
        id = kit.localPeerId,
        name = kit.localDeviceName,
        platform = Platform.JVM_DESKTOP,
        supportedTransports = setOf(TransportKind.LAN)
    )

}

private class SecureSessionFactory(
    private val transport: FakeDataTransport
) : TransportFactory {
    override val descriptor =
        dev.p2pkit.core.transport.TransportDescriptor.dataOnly(transport.type)
    override fun build(context: TransportContext): TransportPair = TransportPair(transport)
}

@OptIn(ExperimentalAtomicApi::class)
private class ObservedRawConnection(
    private val delegate: RawConnection
) : RawConnection {
    private val readCounter = AtomicInt(0)
    private val closeCounter = AtomicInt(0)
    private val writes = mutableListOf<ByteArray>()

    val readCalls: Int get() = readCounter.load()
    val closeCalls: Int get() = closeCounter.load()
    override val state: StateFlow<ConnectionState> get() = delegate.state

    override suspend fun write(bytes: ByteArray) {
        val retained = bytes.copyOf()
        writes += retained
        delegate.write(bytes.copyOf())
    }

    override fun read(): Flow<ByteArray> {
        readCounter.addAndFetch(1)
        return delegate.read()
    }

    override suspend fun close() {
        closeCounter.addAndFetch(1)
        delegate.close()
    }

    fun writtenBytes(): ByteArray {
        val result = ByteArray(writes.sumOf(ByteArray::size))
        var offset = 0
        for (write in writes) {
            write.copyInto(result, offset)
            offset += write.size
        }
        return result
    }
}

private class TestPreparedSource(
    private val content: ByteArray,
    snapshot: ByteArray = content
) : PreparedFileSource {
    override val sizeBytes: Long = snapshot.size.toLong()
    override val sha256: Sha256Digest = sha256(snapshot)
    override fun open(): RawSource = Buffer().apply { write(content) }
}

private class TestCommitDestination(
    private val commitFailure: Throwable? = null
) : FileTransferDestination {
    val buffer = Buffer()
    var committed: Boolean = false

    override fun openSink(): RawSink = buffer

    override suspend fun commit() {
        commitFailure?.let { throw it }
        committed = true
    }

    override suspend fun abort(cause: P2pError.FileTransferFailed?) {
        buffer.clear()
    }
}

private fun ByteArray.containsSubsequence(needle: ByteArray): Boolean {
    if (needle.isEmpty()) return true
    if (needle.size > size) return false
    for (start in 0..size - needle.size) {
        var matches = true
        for (offset in needle.indices) {
            if (this[start + offset] != needle[offset]) {
                matches = false
                break
            }
        }
        if (matches) return true
    }
    return false
}
