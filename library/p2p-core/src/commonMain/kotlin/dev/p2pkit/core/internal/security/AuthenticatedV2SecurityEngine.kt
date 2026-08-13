package dev.p2pkit.core.internal.security

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ExplicitSecurityRisk
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.PeerIdentity
import dev.p2pkit.core.internal.captureCleanupIssue
import dev.p2pkit.core.internal.security.noise.NoiseKeyPair
import dev.p2pkit.core.internal.security.noise.NoiseRole
import dev.p2pkit.core.internal.security.noise.SecureV2HandshakeDriver
import dev.p2pkit.core.internal.security.noise.SecureV2HandshakeOutcome
import dev.p2pkit.core.internal.security.noise.SingleCollectorRawPump
import dev.p2pkit.core.internal.security.noise.wipe
import dev.p2pkit.core.security.IdentityDerivation
import dev.p2pkit.core.security.IdentityNamespace
import dev.p2pkit.core.security.LocalSecureIdentity
import dev.p2pkit.core.security.PlatformSecurityCryptography
import dev.p2pkit.core.security.SecureConnection
import dev.p2pkit.core.security.constantTimeEquals
import dev.p2pkit.core.security.platformSecurityCryptography
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout

/**
 * Establishes the built-in authenticated-v2 channel before any application
 * protocol reader is allowed to observe the raw connection.
 *
 * The persistent identity remains owned by the kit. Every handshake receives
 * only short-lived key copies, and those copies are cleared on every exit.
 */
@OptIn(ExplicitSecurityRisk::class)
internal class AuthenticatedV2SecurityEngine(
    private val cryptography: PlatformSecurityCryptography = platformSecurityCryptography(),
    private val cleanupTimeoutMillis: Long = SECURE_ENGINE_CLEANUP_TIMEOUT_MILLIS,
    private val beforeHandshakeOutcomeClaimForTest: (suspend () -> Unit)? = null,
    private val onAbandonedHandshakeOutcomeDisposedForTest:
        (suspend (SecureV2HandshakeOutcome) -> Unit)? = null,
) {
    init {
        require(cleanupTimeoutMillis > 0L) { "cleanupTimeoutMillis must be positive" }
    }

    private val driver = SecureV2HandshakeDriver(cryptography)

    /**
     * @param expectedPeerId authenticated identity constraint for a selected
     * discovered/reconnecting peer; it never grants authorization by itself.
     * @param expectedFingerprint trusted per-connect/manual pin. An exact pin
     * grants authorization, but a mismatch remains terminal under every policy.
     */
    suspend fun establish(
        rawConnection: RawConnection,
        parentScope: CoroutineScope,
        role: NoiseRole,
        appId: AppId,
        localIdentity: LocalSecureIdentity,
        authorization: PeerAuthorizationPolicy,
        expectedPeerId: PeerId? = null,
        expectedFingerprint: PeerFingerprint? = null,
    ): SecureConnection {
        var localPrivate: ByteArray? = null
        var localPublic: ByteArray? = null
        var localStatic: NoiseKeyPair? = null
        var pump: SingleCollectorRawPump? = null
        var handshakeTask: Deferred<Result<SecureV2HandshakeOutcome>>? = null
        val outcomeLease = HandshakeOutcomeLease()
        var outcome: SecureV2HandshakeOutcome? = null
        var remoteIdentity: PeerIdentity? = null
        var returned = false

        try {
            val namespace = IdentityDerivation.namespace(appId, cryptography)
            localPrivate = localIdentity.keyPair.privateKeyBytes()
            localPublic = localIdentity.keyPair.publicKeyBytes()
            validateLocalIdentity(
                namespace = namespace,
                localIdentity = localIdentity,
                privateKey = localPrivate,
                publicKey = localPublic,
            )
            localStatic = NoiseKeyPair(localPrivate, localPublic)

            pump = SingleCollectorRawPump(rawConnection, parentScope)
            // A raw transport write may be implemented with blocking,
            // non-cancellable I/O. Run the exchange as a kit-owned sibling so
            // cancellation of this caller can close the sole pump immediately,
            // unblocking that I/O before waiting for the task to terminate.
            handshakeTask = parentScope.async {
                try {
                    val established = driver.establish(
                        pump = pump,
                        role = role,
                        appId = appId.value,
                        localStatic = localStatic,
                        authorizeRemoteStatic = { remoteStatic ->
                            deriveAndAuthorizeRemote(
                                namespace = namespace,
                                remoteStatic = remoteStatic,
                                authorization = authorization,
                                expectedPeerId = expectedPeerId,
                                expectedFingerprint = expectedFingerprint,
                            ).also { remoteIdentity = it }
                            true
                        },
                    )
                    val accepted = withContext(NonCancellable) {
                        outcomeLease.publish(established)
                    }
                    if (accepted) {
                        Result.success(established)
                    } else {
                        withContext(NonCancellable) {
                            val cleanupFailure = disposeAbandonedHandshakeOutcome(established)
                            outcomeLease.recordLateCleanupFailure(cleanupFailure)
                        }
                        Result.failure(
                            CancellationException("Authenticated v2 setup was abandoned"),
                        )
                    }
                } catch (cancelled: CancellationException) {
                    throw cancelled
                } catch (cause: Throwable) {
                    // The worker is deliberately owned by the kit rather than
                    // the connect caller. Return ordinary failures as data so
                    // they cannot cancel a non-supervisor owner before this
                    // boundary converts them to the stable public error model.
                    Result.failure(cause)
                }
            }
            val completedOutcome = handshakeTask.await().getOrThrow()
            beforeHandshakeOutcomeClaimForTest?.invoke()
            currentCoroutineContext().ensureActive()
            outcomeLease.claim(completedOutcome)
            outcome = completedOutcome

            val identity = remoteIdentity
                ?: throw P2pError.AuthenticationFailed(
                    "Authenticated protocol v2 completed without a remote identity",
                )
            val secureConnection = AuthenticatedSecureConnection(
                delegate = outcome.connection,
                peerIdentity = identity,
            )
            returned = true
            return secureConnection
        } catch (cause: Throwable) {
            val cleanupFailure = cleanupFailedConnection(
                rawConnection = rawConnection,
                pump = pump,
                handshakeTask = handshakeTask,
                outcome = outcome,
                outcomeLease = outcomeLease,
            )
            cleanupFailure?.let(cause::addSuppressed)
            when (cause) {
                is CancellationException -> throw cause
                is P2pError -> throw cause
                else -> throw P2pError.AuthenticationFailed(
                    "Authenticated protocol v2 setup failed",
                ).also { it.underlying = cause }
            }
        } finally {
            outcome?.clearMetadata()
            localStatic?.destroy()
            localPrivate?.wipe()
            localPublic?.wipe()
            if (!returned) remoteIdentity = null
        }
    }

    private fun validateLocalIdentity(
        namespace: IdentityNamespace,
        localIdentity: LocalSecureIdentity,
        privateKey: ByteArray,
        publicKey: ByteArray,
    ) {
        var derivedPublic: ByteArray? = null
        var fingerprintDigest: ByteArray? = null
        var storedFingerprintDigest: ByteArray? = null
        try {
            derivedPublic = cryptography.deriveX25519PublicKey(privateKey)
            if (!constantTimeEquals(derivedPublic, publicKey)) {
                throw P2pError.SecurityConfigurationInvalid(
                    "Local secure identity key material is inconsistent",
                )
            }

            fingerprintDigest = IdentityDerivation.fingerprintDigest(publicKey, cryptography)
            storedFingerprintDigest = localIdentity.fingerprint.digestBytes()
            val fingerprintMatches = constantTimeEquals(fingerprintDigest, storedFingerprintDigest)
            val derivedPeerId = IdentityDerivation.peerId(namespace, fingerprintDigest, cryptography)
            val peerIdMatches = constantTimePeerIdEquals(derivedPeerId, localIdentity.peerId)
            if (!fingerprintMatches || !peerIdMatches) {
                throw P2pError.SecurityConfigurationInvalid(
                    "Local secure identity does not match its AppId-bound key",
                )
            }
        } finally {
            derivedPublic?.wipe()
            fingerprintDigest?.wipe()
            storedFingerprintDigest?.wipe()
        }
    }

    private fun deriveAndAuthorizeRemote(
        namespace: IdentityNamespace,
        remoteStatic: ByteArray,
        authorization: PeerAuthorizationPolicy,
        expectedPeerId: PeerId?,
        expectedFingerprint: PeerFingerprint?,
    ): PeerIdentity {
        var fingerprintDigest: ByteArray? = null
        var expectedFingerprintDigest: ByteArray? = null
        try {
            fingerprintDigest = IdentityDerivation.fingerprintDigest(remoteStatic, cryptography)
            val fingerprint = PeerFingerprint.fromDigest(fingerprintDigest)
            val peerId = IdentityDerivation.peerId(namespace, fingerprintDigest, cryptography)

            val expectedPeerMatches = expectedPeerId == null ||
                constantTimePeerIdEquals(peerId, expectedPeerId)
            val expectedFingerprintMatches = if (expectedFingerprint == null) {
                true
            } else {
                expectedFingerprintDigest = expectedFingerprint.digestBytes()
                constantTimeEquals(fingerprintDigest, expectedFingerprintDigest)
            }

            // Evaluate configured pins even when a target constraint will fail,
            // avoiding an identity-dependent early exit through the policy path.
            val configuredPolicyAllows = when (authorization) {
                PeerAuthorizationPolicy.RejectUnknown -> false
                is PeerAuthorizationPolicy.PinnedOnly ->
                    matchesAnyFingerprint(fingerprintDigest, authorization.fingerprints)
                PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp -> true
            }

            if (!expectedPeerMatches || !expectedFingerprintMatches) {
                throw P2pError.AuthenticatedIdentityMismatch(
                    "Authenticated remote identity did not match the selected peer",
                )
            }

            val perConnectionPinAllows = expectedFingerprint != null
            if (!perConnectionPinAllows && !configuredPolicyAllows) {
                throw P2pError.AuthorizationRejected(
                    "Authenticated remote identity is not authorized",
                )
            }

            return PeerIdentity(peerId = peerId, fingerprint = fingerprint)
        } finally {
            fingerprintDigest?.wipe()
            expectedFingerprintDigest?.wipe()
        }
    }

    private fun matchesAnyFingerprint(
        remoteDigest: ByteArray,
        configured: Set<PeerFingerprint>,
    ): Boolean {
        var anyMatch = 0
        for (fingerprint in configured) {
            val candidate = fingerprint.digestBytes()
            try {
                anyMatch = anyMatch or if (constantTimeEquals(remoteDigest, candidate)) 1 else 0
            } finally {
                candidate.wipe()
            }
        }
        return anyMatch != 0
    }

    private fun constantTimePeerIdEquals(left: PeerId, right: PeerId): Boolean {
        val leftBytes = left.value.encodeToByteArray()
        val rightBytes = right.value.encodeToByteArray()
        return try {
            constantTimeEquals(leftBytes, rightBytes)
        } finally {
            leftBytes.wipe()
            rightBytes.wipe()
        }
    }

    private suspend fun cleanupFailedConnection(
        rawConnection: RawConnection,
        pump: SingleCollectorRawPump?,
        handshakeTask: Deferred<Result<SecureV2HandshakeOutcome>>?,
        outcome: SecureV2HandshakeOutcome?,
        outcomeLease: HandshakeOutcomeLease,
    ): Throwable? = withContext(NonCancellable) {
        var cleanupFailure: Throwable? = null
        val abandonedOutcome = outcomeLease.abandon()
        if (abandonedOutcome != null) {
            cleanupFailure = cleanupFailure.combineWith(
                disposeAbandonedHandshakeOutcome(abandonedOutcome),
            )
        } else {
            captureCleanupIssue(
                resource = "authenticated v2 failed connection",
                timeoutMillis = cleanupTimeoutMillis,
                preserveCancellation = false,
            ) {
                when {
                    outcome != null -> outcome.connection.close()
                    pump != null -> pump.close()
                    else -> rawConnection.close()
                }
            }?.let { cleanupFailure = cleanupFailure.combineWith(it.cause) }
        }
        handshakeTask?.cancel(CancellationException("Authenticated v2 setup aborted"))
        if (handshakeTask != null) {
            try {
                withContext(Dispatchers.Default) {
                    withTimeout(cleanupTimeoutMillis) {
                        handshakeTask.cancelAndJoin()
                    }
                }
            } catch (_: TimeoutCancellationException) {
                val timeout = IllegalStateException(
                    "Authenticated v2 handshake task did not stop within its cleanup deadline"
                )
                cleanupFailure = cleanupFailure.combineWith(timeout)
            } catch (cleanup: Throwable) {
                cleanupFailure = cleanupFailure.combineWith(cleanup)
            }
        }
        cleanupFailure = cleanupFailure.combineWith(outcomeLease.lateCleanupFailure())
        cleanupFailure
    }

    private suspend fun disposeAbandonedHandshakeOutcome(
        outcome: SecureV2HandshakeOutcome,
    ): Throwable? {
        var cleanupFailure: Throwable? = try {
            captureCleanupIssue(
                resource = "abandoned authenticated v2 handshake outcome",
                timeoutMillis = cleanupTimeoutMillis,
                preserveCancellation = false,
            ) {
                outcome.connection.close()
            }?.cause
        } finally {
            outcome.clearMetadata()
        }
        try {
            onAbandonedHandshakeOutcomeDisposedForTest?.invoke(outcome)
        } catch (callbackFailure: Throwable) {
            cleanupFailure = cleanupFailure.combineWith(callbackFailure)
        }
        return cleanupFailure
    }
}

/**
 * Owns a successful handshake outcome from creation until the connect caller
 * claims it. Cancellation can race both deferred completion and resumption;
 * abandoning this lease before publication makes the producer dispose a late
 * result, while abandoning it after publication returns the result to cleanup.
 */
private class HandshakeOutcomeLease {
    private val mutex = Mutex()
    private var state: State = State.Pending
    private var outcome: SecureV2HandshakeOutcome? = null
    private var lateCleanupFailure: Throwable? = null

    suspend fun publish(value: SecureV2HandshakeOutcome): Boolean = mutex.withLock {
        check(outcome == null) { "Authenticated v2 handshake outcome was published twice" }
        when (state) {
            State.Pending -> {
                outcome = value
                true
            }
            State.Abandoned -> false
            State.Claimed -> error("Authenticated v2 handshake outcome was claimed before publication")
        }
    }

    suspend fun claim(value: SecureV2HandshakeOutcome) {
        mutex.withLock {
            check(state == State.Pending && outcome === value) {
                "Authenticated v2 handshake outcome ownership was unavailable"
            }
            outcome = null
            state = State.Claimed
        }
    }

    suspend fun abandon(): SecureV2HandshakeOutcome? = mutex.withLock {
        if (state != State.Pending) return@withLock null
        state = State.Abandoned
        outcome.also { outcome = null }
    }

    suspend fun recordLateCleanupFailure(failure: Throwable?) {
        if (failure == null) return
        mutex.withLock {
            lateCleanupFailure = lateCleanupFailure.combineWith(failure)
        }
    }

    suspend fun lateCleanupFailure(): Throwable? = mutex.withLock { lateCleanupFailure }

    private enum class State { Pending, Claimed, Abandoned }
}

private fun Throwable?.combineWith(additional: Throwable?): Throwable? {
    if (additional == null) return this
    return this?.also { it.addSuppressed(additional) } ?: additional
}

private const val SECURE_ENGINE_CLEANUP_TIMEOUT_MILLIS: Long = 2_000

/** Immutable authenticated identity paired with the already-secured stream. */
private class AuthenticatedSecureConnection(
    private val delegate: RawConnection,
    override val peerIdentity: PeerIdentity,
) : SecureConnection, RawConnection by delegate, SecureTerminalFailureSource {
    private val secureDelegate: SecureTerminalFailureSource =
        delegate as? SecureTerminalFailureSource
            ?: error("Authenticated secure transport does not expose its failure source")

    override val terminalFailure = secureDelegate.terminalFailure
}
