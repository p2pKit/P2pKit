package dev.p2pkit.core.internal.security

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.ExplicitSecurityRisk
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.internal.security.noise.NoiseProtocolException
import dev.p2pkit.core.internal.security.noise.NoiseRole
import dev.p2pkit.core.internal.security.noise.SECURE_V2_PREFACE_SIZE_BYTES
import dev.p2pkit.core.internal.security.noise.wipe
import dev.p2pkit.core.security.IdentityDerivation
import dev.p2pkit.core.security.LocalSecureIdentity
import dev.p2pkit.core.security.PlatformSecurityCryptography
import dev.p2pkit.core.security.SecureConnection
import dev.p2pkit.core.security.platformSecurityCryptography
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeRawConnection
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.supervisorScope
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertNotEquals
import kotlin.test.assertNotNull

@OptIn(ExplicitSecurityRisk::class, ExperimentalCoroutinesApi::class)
class AuthenticatedV2SecurityEngineTest {
    private val cryptography: PlatformSecurityCryptography = platformSecurityCryptography()
    private val engine = AuthenticatedV2SecurityEngine(cryptography)

    @Test
    fun acceptAnyReturnsAppBoundImmutableAuthenticatedIdentities() = runTest {
        val appId = AppId("engine.accept-any")
        val initiatorIdentity = generateIdentity(appId)
        val responderIdentity = generateIdentity(appId)
        val pair = FakeConnectionPair()

        val (initiator, responder) = establishAcceptedPair(
            pair = pair,
            appId = appId,
            initiatorIdentity = initiatorIdentity,
            responderIdentity = responderIdentity,
            initiatorAuthorization = PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp,
            responderAuthorization = PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp,
        )
        try {
            assertEquals(responderIdentity.peerId, initiator.peerIdentity.peerId)
            assertEquals(responderIdentity.fingerprint, initiator.peerIdentity.fingerprint)
            assertEquals(initiatorIdentity.peerId, responder.peerIdentity.peerId)
            assertEquals(initiatorIdentity.fingerprint, responder.peerIdentity.fingerprint)

            val received = async { responder.read().first() }
            initiator.write("authenticated".encodeToByteArray())
            assertContentEquals("authenticated".encodeToByteArray(), received.await())

            // Clearing the persistent private key after establishment cannot
            // mutate the public identity already published by the connection.
            responderIdentity.clearPrivate()
            assertEquals(responderIdentity.peerId, initiator.peerIdentity.peerId)
            assertEquals(responderIdentity.fingerprint, initiator.peerIdentity.fingerprint)
        } finally {
            initiator.close()
            responder.close()
            initiatorIdentity.clearPrivate()
            responderIdentity.clearPrivate()
        }
    }

    @Test
    fun exactPerConnectionPinsAuthorizeUnderRejectUnknown() = runTest {
        val appId = AppId("engine.per-connect-pin")
        val initiatorIdentity = generateIdentity(appId)
        val responderIdentity = generateIdentity(appId)
        val pair = FakeConnectionPair()

        val (initiator, responder) = establishAcceptedPair(
            pair = pair,
            appId = appId,
            initiatorIdentity = initiatorIdentity,
            responderIdentity = responderIdentity,
            initiatorAuthorization = PeerAuthorizationPolicy.RejectUnknown,
            responderAuthorization = PeerAuthorizationPolicy.RejectUnknown,
            initiatorExpectedPeerId = responderIdentity.peerId,
            initiatorExpectedFingerprint = responderIdentity.fingerprint,
            responderExpectedPeerId = initiatorIdentity.peerId,
            responderExpectedFingerprint = initiatorIdentity.fingerprint,
        )
        try {
            assertEquals(responderIdentity.peerId, initiator.peerIdentity.peerId)
            assertEquals(initiatorIdentity.peerId, responder.peerIdentity.peerId)
        } finally {
            initiator.close()
            responder.close()
            initiatorIdentity.clearPrivate()
            responderIdentity.clearPrivate()
        }
    }

    @Test
    fun rejectUnknownDoesNotTreatExpectedPeerIdAsAuthorization() = runTest {
        val appId = AppId("engine.reject-unknown")
        val initiatorIdentity = generateIdentity(appId)
        val responderIdentity = generateIdentity(appId)
        val pair = FakeConnectionPair()
        try {
            supervisorScope {
                val initiator = async {
                    establish(
                        raw = pair.a,
                        role = NoiseRole.Initiator,
                        appId = appId,
                        identity = initiatorIdentity,
                        authorization = PeerAuthorizationPolicy.RejectUnknown,
                        expectedPeerId = responderIdentity.peerId,
                    )
                }
                val responder = async {
                    establish(
                        raw = pair.b,
                        role = NoiseRole.Responder,
                        appId = appId,
                        identity = responderIdentity,
                        authorization = PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp,
                    )
                }
                assertFailsWith<P2pError.AuthorizationRejected> { initiator.await() }
                assertFailsWith<P2pError.AuthenticationFailed> { responder.await() }
            }
            assertEquals(ConnectionState.Closed, pair.a.state.value)
        } finally {
            initiatorIdentity.clearPrivate()
            responderIdentity.clearPrivate()
        }
    }

    @Test
    fun pinnedOnlyAcceptsAnExactConfiguredFingerprint() = runTest {
        val appId = AppId("engine.configured-pins")
        val initiatorIdentity = generateIdentity(appId)
        val responderIdentity = generateIdentity(appId)
        val pair = FakeConnectionPair()

        val (initiator, responder) = establishAcceptedPair(
            pair = pair,
            appId = appId,
            initiatorIdentity = initiatorIdentity,
            responderIdentity = responderIdentity,
            initiatorAuthorization = PeerAuthorizationPolicy.PinnedOnly(
                setOf(responderIdentity.fingerprint),
            ),
            responderAuthorization = PeerAuthorizationPolicy.PinnedOnly(
                setOf(initiatorIdentity.fingerprint),
            ),
        )
        try {
            assertEquals(responderIdentity.fingerprint, initiator.peerIdentity.fingerprint)
            assertEquals(initiatorIdentity.fingerprint, responder.peerIdentity.fingerprint)
        } finally {
            initiator.close()
            responder.close()
            initiatorIdentity.clearPrivate()
            responderIdentity.clearPrivate()
        }
    }

    @Test
    fun pinnedOnlyRejectsWhenNoConfiguredFingerprintMatches() = runTest {
        val appId = AppId("engine.wrong-configured-pin")
        val initiatorIdentity = generateIdentity(appId)
        val responderIdentity = generateIdentity(appId)
        val unrelatedIdentity = generateIdentity(appId)
        val pair = FakeConnectionPair()
        try {
            supervisorScope {
                val initiator = async {
                    establish(
                        raw = pair.a,
                        role = NoiseRole.Initiator,
                        appId = appId,
                        identity = initiatorIdentity,
                        authorization = PeerAuthorizationPolicy.PinnedOnly(
                            setOf(unrelatedIdentity.fingerprint),
                        ),
                    )
                }
                val responder = async {
                    establish(
                        raw = pair.b,
                        role = NoiseRole.Responder,
                        appId = appId,
                        identity = responderIdentity,
                        authorization = PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp,
                    )
                }
                assertFailsWith<P2pError.AuthorizationRejected> { initiator.await() }
                assertFailsWith<P2pError.AuthenticationFailed> { responder.await() }
            }
        } finally {
            initiatorIdentity.clearPrivate()
            responderIdentity.clearPrivate()
            unrelatedIdentity.clearPrivate()
        }
    }

    @Test
    fun mismatchedExpectedPeerIdFailsAsAuthenticatedIdentityMismatch() = runTest {
        assertTargetMismatch(expectedPeerId = PeerId("not-the-authenticated-peer"))
    }

    @Test
    fun mismatchedExpectedFingerprintFailsAsAuthenticatedIdentityMismatch() = runTest {
        val appId = AppId("engine.wrong-fingerprint")
        val unrelated = generateIdentity(appId)
        try {
            assertTargetMismatch(
                appId = appId,
                expectedFingerprint = unrelated.fingerprint,
            )
        } finally {
            unrelated.clearPrivate()
        }
    }

    @Test
    fun differentExactAppIdsCannotCompleteTheHandshake() = runTest {
        val initiatorAppId = AppId("engine.app.one")
        val responderAppId = AppId("engine.app.two")
        val initiatorIdentity = generateIdentity(initiatorAppId)
        val responderIdentity = generateIdentity(responderAppId)
        val pair = FakeConnectionPair()
        try {
            assertNotEquals(
                derivePeerId(initiatorAppId, responderIdentity),
                derivePeerId(responderAppId, responderIdentity),
            )
            supervisorScope {
                val initiator = async {
                    establish(
                        raw = pair.a,
                        role = NoiseRole.Initiator,
                        appId = initiatorAppId,
                        identity = initiatorIdentity,
                        authorization = PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp,
                    )
                }
                val responder = async {
                    establish(
                        raw = pair.b,
                        role = NoiseRole.Responder,
                        appId = responderAppId,
                        identity = responderIdentity,
                        authorization = PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp,
                    )
                }
                val failure = assertFailsWith<P2pError.AuthenticationFailed> { initiator.await() }
                assertNotNull(failure.cause)
                assertFailsWith<P2pError.AuthenticationFailed> { responder.await() }
            }
        } finally {
            initiatorIdentity.clearPrivate()
            responderIdentity.clearPrivate()
        }
    }

    @Test
    fun malformedPrefaceIsTypedAndRetainsTheInternalCause() = runTest {
        val appId = AppId("engine.preface-failure")
        val identity = generateIdentity(appId)
        val pair = FakeConnectionPair()
        val peer = launch {
            pair.b.read().first()
            pair.b.write(ByteArray(SECURE_V2_PREFACE_SIZE_BYTES))
        }
        try {
            val failure = assertFailsWith<P2pError.AuthenticationFailed> {
                establish(
                    raw = pair.a,
                    role = NoiseRole.Initiator,
                    appId = appId,
                    identity = identity,
                    authorization = PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp,
                )
            }
            assertIs<NoiseProtocolException>(failure.cause)
            peer.join()
        } finally {
            identity.clearPrivate()
            pair.b.close()
        }
    }

    @Test
    fun cancellationPropagatesUnchangedAndClosesTheRawConnection() = runTest {
        val appId = AppId("engine.cancellation")
        val identity = generateIdentity(appId)
        val pair = FakeConnectionPair()
        try {
            val pending = async {
                establish(
                    raw = pair.a,
                    role = NoiseRole.Initiator,
                    appId = appId,
                    identity = identity,
                    authorization = PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp,
                )
            }
            runCurrent()
            pending.cancel(CancellationException("owner cancelled"))
            val failure = assertFailsWith<CancellationException> { pending.await() }
            assertEquals("owner cancelled", failure.message)
            assertEquals(ConnectionState.Closed, pair.a.state.value)
        } finally {
            identity.clearPrivate()
            pair.b.close()
        }
    }

    @Test
    fun invalidLocalMetadataFailsBeforeWireUseWithoutClearingPersistentKey() = runTest {
        val appId = AppId("engine.invalid-local")
        val valid = generateIdentity(appId)
        val invalid = LocalSecureIdentity(
            peerId = PeerId("invalid-local-peer-id"),
            fingerprint = valid.fingerprint,
            keyPair = valid.keyPair,
        )
        val originalPrivate = valid.keyPair.privateKeyBytes()
        val pair = FakeConnectionPair()
        try {
            assertFailsWith<P2pError.SecurityConfigurationInvalid> {
                establish(
                    raw = pair.a,
                    role = NoiseRole.Initiator,
                    appId = appId,
                    identity = invalid,
                    authorization = PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp,
                )
            }
            assertEquals(0, pair.a.writeAttempts)
            assertEquals(ConnectionState.Closed, pair.a.state.value)
            val afterFailure = valid.keyPair.privateKeyBytes()
            try {
                assertContentEquals(originalPrivate, afterFailure)
            } finally {
                afterFailure.wipe()
            }
        } finally {
            originalPrivate.wipe()
            valid.clearPrivate()
            pair.b.close()
        }
    }

    private suspend fun kotlinx.coroutines.CoroutineScope.assertTargetMismatch(
        appId: AppId = AppId("engine.target-mismatch"),
        expectedPeerId: PeerId? = null,
        expectedFingerprint: dev.p2pkit.core.PeerFingerprint? = null,
    ) {
        val initiatorIdentity = generateIdentity(appId)
        val responderIdentity = generateIdentity(appId)
        val pair = FakeConnectionPair()
        try {
            supervisorScope {
                val initiator = async {
                    establish(
                        raw = pair.a,
                        role = NoiseRole.Initiator,
                        appId = appId,
                        identity = initiatorIdentity,
                        authorization = PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp,
                        expectedPeerId = expectedPeerId,
                        expectedFingerprint = expectedFingerprint,
                    )
                }
                val responder = async {
                    establish(
                        raw = pair.b,
                        role = NoiseRole.Responder,
                        appId = appId,
                        identity = responderIdentity,
                        authorization = PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp,
                    )
                }
                val mismatch = assertFailsWith<P2pError.AuthenticatedIdentityMismatch> {
                    initiator.await()
                }
                assertEquals(
                    "Authenticated remote identity did not match the selected peer",
                    mismatch.reason,
                )
                assertFailsWith<P2pError.AuthenticationFailed> { responder.await() }
            }
        } finally {
            initiatorIdentity.clearPrivate()
            responderIdentity.clearPrivate()
        }
    }

    private suspend fun kotlinx.coroutines.CoroutineScope.establishAcceptedPair(
        pair: FakeConnectionPair,
        appId: AppId,
        initiatorIdentity: LocalSecureIdentity,
        responderIdentity: LocalSecureIdentity,
        initiatorAuthorization: PeerAuthorizationPolicy,
        responderAuthorization: PeerAuthorizationPolicy,
        initiatorExpectedPeerId: PeerId? = null,
        initiatorExpectedFingerprint: dev.p2pkit.core.PeerFingerprint? = null,
        responderExpectedPeerId: PeerId? = null,
        responderExpectedFingerprint: dev.p2pkit.core.PeerFingerprint? = null,
    ): Pair<SecureConnection, SecureConnection> {
        // Launch into the caller's long-lived test scope. A secure connection's
        // sole-reader pump intentionally remains a child of that owner until
        // the returned connection is closed; nesting these launches inside a
        // temporary supervisorScope would wait for the pumps before it could
        // return the connections needed to close them.
        val connectionOwner = this
        val initiator = async {
            establish(
                raw = pair.a,
                role = NoiseRole.Initiator,
                appId = appId,
                identity = initiatorIdentity,
                authorization = initiatorAuthorization,
                expectedPeerId = initiatorExpectedPeerId,
                expectedFingerprint = initiatorExpectedFingerprint,
                parentScope = connectionOwner,
            )
        }
        val responder = async {
            establish(
                raw = pair.b,
                role = NoiseRole.Responder,
                appId = appId,
                identity = responderIdentity,
                authorization = responderAuthorization,
                expectedPeerId = responderExpectedPeerId,
                expectedFingerprint = responderExpectedFingerprint,
                parentScope = connectionOwner,
            )
        }
        return initiator.await() to responder.await()
    }

    private suspend fun kotlinx.coroutines.CoroutineScope.establish(
        raw: FakeRawConnection,
        role: NoiseRole,
        appId: AppId,
        identity: LocalSecureIdentity,
        authorization: PeerAuthorizationPolicy,
        expectedPeerId: PeerId? = null,
        expectedFingerprint: dev.p2pkit.core.PeerFingerprint? = null,
        parentScope: kotlinx.coroutines.CoroutineScope = this,
    ): SecureConnection = engine.establish(
        rawConnection = CopyingRawConnection(raw),
        parentScope = parentScope,
        role = role,
        appId = appId,
        localIdentity = identity,
        authorization = authorization,
        expectedPeerId = expectedPeerId,
        expectedFingerprint = expectedFingerprint,
    )

    private fun generateIdentity(appId: AppId): LocalSecureIdentity {
        val keyPair = cryptography.generateX25519KeyPair()
        val publicKey = keyPair.publicKeyBytes()
        var fingerprintDigest: ByteArray? = null
        return try {
            fingerprintDigest = IdentityDerivation.fingerprintDigest(publicKey, cryptography)
            val fingerprint = dev.p2pkit.core.PeerFingerprint.fromDigest(fingerprintDigest)
            val peerId = IdentityDerivation.peerId(
                IdentityDerivation.namespace(appId, cryptography),
                fingerprintDigest,
                cryptography,
            )
            LocalSecureIdentity(peerId, fingerprint, keyPair)
        } catch (cause: Throwable) {
            keyPair.clearPrivate()
            throw cause
        } finally {
            publicKey.wipe()
            fingerprintDigest?.wipe()
        }
    }

    private fun derivePeerId(appId: AppId, identity: LocalSecureIdentity): PeerId {
        val publicKey = identity.keyPair.publicKeyBytes()
        var digest: ByteArray? = null
        return try {
            digest = IdentityDerivation.fingerprintDigest(publicKey, cryptography)
            IdentityDerivation.peerId(
                IdentityDerivation.namespace(appId, cryptography),
                digest,
                cryptography,
            )
        } finally {
            publicKey.wipe()
            digest?.wipe()
        }
    }
}

private class CopyingRawConnection(
    private val delegate: FakeRawConnection,
) : RawConnection {
    override val state: StateFlow<ConnectionState> get() = delegate.state

    override suspend fun write(bytes: ByteArray) {
        delegate.write(bytes.copyOf())
    }

    override fun read(): Flow<ByteArray> = delegate.read()

    override suspend fun close() {
        delegate.close()
    }
}
