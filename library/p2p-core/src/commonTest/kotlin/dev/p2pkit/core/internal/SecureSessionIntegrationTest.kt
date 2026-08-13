package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.ExplicitSecurityRisk
import dev.p2pkit.core.FileTransferFailureKind
import dev.p2pkit.core.FileTransferPhase
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.security.EncodedIdentityKeyPair
import dev.p2pkit.core.security.IdentityNamespace
import dev.p2pkit.core.security.LocalSecureIdentity
import dev.p2pkit.core.security.SecureIdentityService
import dev.p2pkit.core.security.platformSecurityCryptography
import dev.p2pkit.core.internal.security.sha256
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
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
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.yield
import kotlinx.io.Buffer
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
        val alice = secureKit(
            appId,
            "Alice",
            MemorySecureIdentityStorage(),
            FakeDataTransport(outgoingConnection = {
                if (dial++ == 0) blockedObserved
                else CopyingRawConnection(retryPair.a)
            }),
            PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
        )
        val bob = secureKit(
            appId,
            "Bob",
            MemorySecureIdentityStorage(),
            FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(retryPair.b))),
            PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
        )
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
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun secureSetupDeadlineIncludesInitialPrefaceWriteAndClosesRaw() = runBlocking {
        val appId = AppId("secure.session.full-setup-timeout")
        val blockedPair = FakeConnectionPair()
        blockedPair.a.writeLatencyMillis = 10_000
        val alice = secureKit(
            appId,
            "Alice",
            MemorySecureIdentityStorage(),
            FakeDataTransport(outgoingConnection = { blockedPair.a }),
            PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp,
            setupTimeoutMillis = 100
        )
        try {
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
        } finally {
            alice.stop()
        }
    }

    @Test
    fun callerDeadlineDuringSecureSetupRemainsCancellationAndClosesRaw() = runBlocking {
        val appId = AppId("secure.session.caller-timeout")
        val blockedPair = FakeConnectionPair()
        blockedPair.a.writeLatencyMillis = 10_000
        val alice = secureKit(
            appId,
            "Alice",
            MemorySecureIdentityStorage(),
            FakeDataTransport(outgoingConnection = { blockedPair.a }),
            PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp,
            setupTimeoutMillis = 5_000
        )
        try {
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
        } finally {
            alice.stop()
        }
    }

    @Test
    fun reconnectRemainsPinnedToTheInitiallyAuthenticatedIdentity() = runBlocking {
        val appId = AppId("secure.session.reconnect-pin")
        val firstPair = FakeConnectionPair()
        val attackerPair = FakeConnectionPair()
        var dial = 0
        val bob = secureKit(
            appId,
            "Bob",
            MemorySecureIdentityStorage(),
            FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(firstPair.b))),
            PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
        )
        val attacker = secureKit(
            appId,
            "Attacker",
            MemorySecureIdentityStorage(),
            FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(attackerPair.b))),
            PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
        )
        val alice = secureKit(
            appId,
            "Alice",
            MemorySecureIdentityStorage(),
            FakeDataTransport(outgoingConnection = {
                if (dial++ == 0) CopyingRawConnection(firstPair.a)
                else CopyingRawConnection(attackerPair.a)
            }),
            PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp,
            reconnect = ReconnectPolicy.Enabled(maxAttempts = 1, retryDelayMillis = 0)
        )
        try {
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
        } finally {
            alice.stop()
            bob.stop()
            attacker.stop()
        }
    }

    @Test
    fun pinnedSecureSessionsAuthenticateBeforeHelloAndExposeOnlyCiphertextOnRawWire() =
        runBlocking {
            val appId = AppId("secure.session.pinned")
            val aliceStore = MemorySecureIdentityStorage()
            val bobStore = MemorySecureIdentityStorage()
            val aliceIdentity = previewIdentity(appId, aliceStore)
            val bobIdentity = previewIdentity(appId, bobStore)
            val pair = FakeConnectionPair()
            val aliceRaw = ObservedRawConnection(pair.a)
            val bobRaw = ObservedRawConnection(pair.b)
            val alice = secureKit(
                appId = appId,
                name = "Alice secret hello name",
                store = aliceStore,
                transport = FakeDataTransport(outgoingConnection = { aliceRaw }),
                authorization = PeerAuthorizationPolicy.PinnedOnly(setOf(bobIdentity.fingerprint))
            )
            val bob = secureKit(
                appId = appId,
                name = "Bob secret hello name",
                store = bobStore,
                transport = FakeDataTransport(preStagedIncoming = listOf(bobRaw)),
                authorization = PeerAuthorizationPolicy.PinnedOnly(setOf(aliceIdentity.fingerprint))
            )
            try {
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

                val aliceWire = aliceRaw.writtenBytes()
                assertFalse(aliceWire.containsSubsequence(secret.encodeToByteArray()))
                assertFalse(aliceWire.containsSubsequence("Alice secret hello name".encodeToByteArray()))
                assertFalse(aliceWire.containsSubsequence(appId.value.encodeToByteArray()))
                assertTrue(aliceWire.isNotEmpty())
            } finally {
                alice.stop()
                bob.stop()
                aliceIdentity.clearPrivate()
                bobIdentity.clearPrivate()
            }
        }

    @Test
    fun securePreparedTransferCompletesAfterReceiverCommit() = runBlocking {
        val appId = AppId("secure.session.file-commit")
        val pair = FakeConnectionPair()
        val alice = secureKit(
            appId,
            "Alice",
            MemorySecureIdentityStorage(),
            FakeDataTransport(outgoingConnection = { CopyingRawConnection(pair.a) }),
            PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
        )
        val bob = secureKit(
            appId,
            "Bob",
            MemorySecureIdentityStorage(),
            FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(pair.b))),
            PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
        )
        try {
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
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun securePreparedSourceGrowthFailsBothPeersBeforeCommit() = runBlocking {
        val appId = AppId("secure.session.file-source-growth")
        val pair = FakeConnectionPair()
        val alice = secureKit(
            appId,
            "Alice",
            MemorySecureIdentityStorage(),
            FakeDataTransport(outgoingConnection = { CopyingRawConnection(pair.a) }),
            PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
        )
        val bob = secureKit(
            appId,
            "Bob",
            MemorySecureIdentityStorage(),
            FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(pair.b))),
            PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
        )
        try {
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
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun secureReceiverCommitFailureReachesSenderAsTypedTerminalResult() = runBlocking {
        val appId = AppId("secure.session.file-commit-failure")
        val pair = FakeConnectionPair()
        val alice = secureKit(
            appId,
            "Alice",
            MemorySecureIdentityStorage(),
            FakeDataTransport(outgoingConnection = { CopyingRawConnection(pair.a) }),
            PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
        )
        val bob = secureKit(
            appId,
            "Bob",
            MemorySecureIdentityStorage(),
            FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(pair.b))),
            PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
        )
        try {
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
        } finally {
            alice.stop()
            bob.stop()
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
        val alice = secureKit(
            appId,
            "Alice",
            aliceStore,
            FakeDataTransport(outgoingConnection = { CopyingRawConnection(pair.a) }),
            PeerAuthorizationPolicy.PinnedOnly(alicePins)
        )
        val bob = secureKit(
            appId,
            "Bob",
            bobStore,
            FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(pair.b))),
            PeerAuthorizationPolicy.PinnedOnly(bobPins)
        )

        // Mutation after construction must not alter the kit-owned policy.
        alicePins.clear()
        bobPins.clear()
        try {
            val incoming = async { withTimeout(5_000) { bob.incomingSessions.first() } }
            bob.start()
            val outgoing = withTimeout(5_000) { alice.connect(peerFor(bob)) }
            assertEquals(bobIdentity.fingerprint, outgoing.peerIdentity.fingerprint)
            assertEquals(aliceIdentity.fingerprint, incoming.await().peerIdentity.fingerprint)
        } finally {
            alice.stop()
            bob.stop()
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
        val alice = secureKit(
            appId,
            "Alice",
            aliceStore,
            FakeDataTransport(outgoingConnection = { CopyingRawConnection(pair.a) }),
            PeerAuthorizationPolicy.RejectUnknown
        )
        val bob = secureKit(
            appId,
            "Bob",
            bobStore,
            FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(pair.b))),
            PeerAuthorizationPolicy.PinnedOnly(setOf(aliceIdentity.fingerprint))
        )
        try {
            val incoming = async { withTimeout(5_000) { bob.incomingSessions.first() } }
            bob.start()
            val session = withTimeout(5_000) {
                alice.connect(peerFor(bob), bobIdentity.fingerprint)
            }
            assertEquals(bobIdentity.fingerprint, session.peerIdentity.fingerprint)
            assertEquals(aliceIdentity.fingerprint, incoming.await().peerIdentity.fingerprint)
        } finally {
            alice.stop()
            bob.stop()
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
        val alice = secureKit(
            appId,
            "Alice",
            aliceStore,
            FakeDataTransport(outgoingConnection = { CopyingRawConnection(pair.a) }),
            PeerAuthorizationPolicy.RejectUnknown
        )
        val bob = secureKit(
            appId,
            "Bob",
            bobStore,
            FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(pair.b))),
            PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
        )
        try {
            bob.start()
            assertFailsWith<P2pError.AuthorizationRejected> {
                withTimeout(5_000) { alice.connect(peerFor(bob)) }
            }
            assertTrue(alice.sessions.value.isEmpty())
            assertTrue(bob.sessions.value.isEmpty())
            assertEquals(ConnectionState.Closed, pair.a.state.value)
        } finally {
            alice.stop()
            bob.stop()
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
        val alice = secureKit(
            appId,
            "Alice",
            aliceStore,
            FakeDataTransport(outgoingConnection = { CopyingRawConnection(pair.a) }),
            PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
        )
        val attacker = secureKit(
            appId,
            "Attacker",
            attackerStore,
            FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(pair.b))),
            PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
        )
        val copiedClaim = Peer(
            id = victim.peerId,
            name = "Victim",
            platform = Platform.JVM_DESKTOP,
            supportedTransports = setOf(TransportKind.LAN)
        )
        try {
            attacker.start()
            assertFailsWith<P2pError.AuthenticatedIdentityMismatch> {
                withTimeout(5_000) { alice.connect(copiedClaim) }
            }
            assertTrue(alice.sessions.value.isEmpty())
            assertTrue(attacker.sessions.value.isEmpty())
        } finally {
            alice.stop()
            attacker.stop()
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
        val alice = secureKit(
            aliceAppId,
            "Alice",
            MemorySecureIdentityStorage(),
            FakeDataTransport(outgoingConnection = { CopyingRawConnection(pair.a) }),
            PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
        )
        val bob = if (bobLegacy) {
            legacyKit(
                bobAppId,
                FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(pair.b)))
            )
        } else {
            secureKit(
                bobAppId,
                "Bob",
                MemorySecureIdentityStorage(),
                FakeDataTransport(preStagedIncoming = listOf(CopyingRawConnection(pair.b))),
                PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
            )
        }
        try {
            bob.start()
            assertFailsWith<P2pError.AuthenticationFailed> {
                withTimeout(5_000) { alice.connect(peerFor(bob)) }
            }
            assertTrue(alice.sessions.value.isEmpty())
            assertTrue(bob.sessions.value.isEmpty())
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    private fun secureKit(
        appId: AppId,
        name: String,
        store: SecureIdentityStorage,
        transport: FakeDataTransport,
        authorization: PeerAuthorizationPolicy,
        reconnect: ReconnectPolicy = ReconnectPolicy.Disabled,
        setupTimeoutMillis: Long = DEFAULT_HANDSHAKE_TIMEOUT_MS
    ): P2pKit = P2pKit.create {
        this.appId = appId
        deviceName = name
        secureIdentityStorage = store
        sessionSetupTimeoutMillis = setupTimeoutMillis
        security { mode = SecurityMode.AuthenticatedV2(authorization) }
        lifecycle { reconnectPolicy = reconnect }
        keepAlive {
            pingIntervalMillis = 60_000
            timeoutMillis = 120_000
        }
        transports { register(SecureSessionFactory(transport)) }
    }

    @Suppress("DEPRECATION")
    private fun legacyKit(appId: AppId, transport: FakeDataTransport): P2pKit = P2pKit.create {
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

private class MemorySecureIdentityStorage : SecureIdentityStorage {
    private val records = mutableMapOf<String, EncodedIdentityKeyPair>()

    override fun loadOrCreate(
        namespace: IdentityNamespace,
        fingerprintDigest: (EncodedIdentityKeyPair) -> ByteArray,
        generate: () -> EncodedIdentityKeyPair
    ): EncodedIdentityKeyPair = run {
        records[namespace.storageKey]?.let(::copy)?.also {
            validateFingerprintCallback(it, fingerprintDigest)
        } ?: run {
            val generated = generate()
            try {
                validateFingerprintCallback(generated, fingerprintDigest)
                copy(generated).also { durable -> records[namespace.storageKey] = durable }
                copy(records.getValue(namespace.storageKey))
            } finally {
                generated.clearPrivate()
            }
        }
    }

    override fun reset(namespace: IdentityNamespace) {
        records.remove(namespace.storageKey)?.clearPrivate()
    }

    private fun validateFingerprintCallback(
        pair: EncodedIdentityKeyPair,
        callback: (EncodedIdentityKeyPair) -> ByteArray
    ) {
        val digest = callback(pair)
        try {
            require(digest.size == 32)
        } finally {
            digest.fill(0)
        }
    }

    private fun copy(pair: EncodedIdentityKeyPair): EncodedIdentityKeyPair {
        val privateKey = pair.privateKeyBytes()
        val publicKey = pair.publicKeyBytes()
        return try {
            EncodedIdentityKeyPair(privateKey, publicKey)
        } finally {
            privateKey.fill(0)
            publicKey.fill(0)
        }
    }
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

private class CopyingRawConnection(
    private val delegate: RawConnection
) : RawConnection {
    override val state: StateFlow<ConnectionState> get() = delegate.state

    override suspend fun write(bytes: ByteArray) = delegate.write(bytes.copyOf())

    override fun read(): Flow<ByteArray> = delegate.read()

    override suspend fun close() = delegate.close()
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
