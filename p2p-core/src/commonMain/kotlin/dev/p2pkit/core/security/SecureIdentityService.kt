package dev.p2pkit.core.security

import dev.p2pkit.core.AppId
import dev.p2pkit.core.LocalIdentityFailureKind
import dev.p2pkit.core.LocalIdentityRecovery
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.internal.SecureIdentityUsage
import dev.p2pkit.core.internal.SecureIdentityStorage
import kotlinx.coroutines.CancellationException

/** Loads, verifies, and derives the public values of one local secure identity. */
internal class SecureIdentityService(
    private val cryptography: IdentityCryptography,
    private val storage: SecureIdentityStorage
) {
    /**
     * Reserve this AppId against explicit reset before identity loading.
     * The kit owns the returned token until terminal teardown.
     */
    fun acquireUsage(appId: AppId): SecureIdentityUsage =
        storage.acquireUsage(IdentityDerivation.namespace(appId, cryptography))

    fun loadOrCreate(appId: AppId): LocalSecureIdentity {
        val namespace = IdentityDerivation.namespace(appId, cryptography)
        val keyPair = try {
            storage.loadOrCreate(
                namespace = namespace,
                fingerprintDigest = ::fingerprintDigest,
                generate = ::generateValidatedKeyPair
            )
        } catch (e: P2pError.LocalIdentityUnavailable) {
            throw e
        } catch (e: IdentityRecordCorruptException) {
            throw localIdentityError(
                kind = LocalIdentityFailureKind.CORRUPT_RECORD,
                recovery = LocalIdentityRecovery.EXPLICIT_RESET_REQUIRED,
                reason = e.message ?: "secure identity record is corrupt",
                cause = e
            )
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            throw localIdentityError(
                kind = LocalIdentityFailureKind.TEMPORARILY_UNAVAILABLE,
                recovery = LocalIdentityRecovery.RETRY,
                reason = "secure identity store failed",
                cause = e
            )
        }

        var success = false
        try {
            validateKeyPair(keyPair, LocalIdentityFailureKind.CORRUPT_RECORD)
            val publicKey = keyPair.publicKeyBytes()
            try {
                val fingerprintDigest = IdentityDerivation.fingerprintDigest(publicKey, cryptography)
                try {
                    val fingerprint = PeerFingerprint.fromDigest(fingerprintDigest)
                    val peerId = IdentityDerivation.peerId(namespace, fingerprintDigest, cryptography)
                    success = true
                    return LocalSecureIdentity(peerId, fingerprint, keyPair)
                } finally {
                    fingerprintDigest.fill(0)
                }
            } finally {
                publicKey.fill(0)
            }
        } finally {
            if (!success) keyPair.clearPrivate()
        }
    }

    fun pairingQr(appId: AppId, fingerprint: PeerFingerprint): String {
        val namespace = IdentityDerivation.namespace(appId, cryptography)
        return IdentityDerivation.pairingQr(namespace, fingerprint, cryptography).encode()
    }

    /** Derive the self-certifying PeerId represented by a full fingerprint. */
    fun peerId(appId: AppId, fingerprint: PeerFingerprint): PeerId {
        val namespace = IdentityDerivation.namespace(appId, cryptography)
        val digest = fingerprint.digestBytes()
        return try {
            IdentityDerivation.peerId(namespace, digest, cryptography)
        } finally {
            digest.fill(0)
        }
    }

    fun parsePairingQr(appId: AppId, value: String): PeerFingerprint? {
        val namespace = IdentityDerivation.namespace(appId, cryptography)
        return IdentityDerivation.parsePairingQr(value, namespace, cryptography)
    }

    fun reset(appId: AppId) {
        val namespace = IdentityDerivation.namespace(appId, cryptography)
        storage.reset(namespace)
    }

    private fun generateValidatedKeyPair(): EncodedIdentityKeyPair {
        val generated = try {
            cryptography.generateX25519KeyPair()
        } catch (e: P2pError.LocalIdentityUnavailable) {
            throw e
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            throw localIdentityError(
                kind = LocalIdentityFailureKind.KEY_GENERATION_FAILED,
                recovery = LocalIdentityRecovery.RETRY,
                reason = "X25519 key generation failed",
                cause = e
            )
        }
        var success = false
        try {
            validateKeyPair(generated, LocalIdentityFailureKind.KEY_GENERATION_FAILED)
            success = true
            return generated
        } finally {
            if (!success) generated.clearPrivate()
        }
    }

    private fun fingerprintDigest(keyPair: EncodedIdentityKeyPair): ByteArray {
        // Platform stores use this callback before committing any non-secret
        // marker. Validate key possession first so a malformed durable record
        // can never be memorialized as a committed identity.
        validateKeyPair(keyPair, LocalIdentityFailureKind.CORRUPT_RECORD)
        val publicKey = keyPair.publicKeyBytes()
        return try {
            IdentityDerivation.fingerprintDigest(publicKey, cryptography)
        } finally {
            publicKey.fill(0)
        }
    }

    private fun validateKeyPair(
        keyPair: EncodedIdentityKeyPair,
        mismatchKind: LocalIdentityFailureKind
    ) {
        val privateKey = keyPair.privateKeyBytes()
        val storedPublic = keyPair.publicKeyBytes()
        var derivedPublic: ByteArray? = null
        try {
            derivedPublic = try {
                cryptography.deriveX25519PublicKey(privateKey)
            } catch (e: P2pError.LocalIdentityUnavailable) {
                throw e
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                throw localIdentityError(
                    kind = LocalIdentityFailureKind.CRYPTO_PROVIDER_UNAVAILABLE,
                    recovery = LocalIdentityRecovery.FIX_PLATFORM_CONFIGURATION,
                    reason = "X25519 public-key derivation failed",
                    cause = e
                )
            }
            if (derivedPublic.size != X25519_KEY_SIZE_BYTES ||
                !constantTimeEquals(derivedPublic, storedPublic)
            ) {
                val recovery = if (mismatchKind == LocalIdentityFailureKind.CORRUPT_RECORD) {
                    LocalIdentityRecovery.EXPLICIT_RESET_REQUIRED
                } else {
                    LocalIdentityRecovery.FIX_PLATFORM_CONFIGURATION
                }
                throw localIdentityError(
                    kind = mismatchKind,
                    recovery = recovery,
                    reason = "stored X25519 public key does not match its private key"
                )
            }
        } finally {
            privateKey.fill(0)
            storedPublic.fill(0)
            derivedPublic?.fill(0)
        }
    }
}
