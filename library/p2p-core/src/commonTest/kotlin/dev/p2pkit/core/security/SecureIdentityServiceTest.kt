package dev.p2pkit.core.security

import dev.p2pkit.core.AppId
import dev.p2pkit.core.LocalIdentityFailureKind
import dev.p2pkit.core.LocalIdentityRecovery
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.internal.SecureIdentityStorage
import kotlinx.coroutines.CancellationException
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNotEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

class SecureIdentityServiceTest {
    @Test
    fun committedKeyDerivesStablePeerIdFingerprintAndQr() {
        val crypto = DeterministicTestIdentityCryptography()
        val storage = TestSecureIdentityStorage()
        val service = SecureIdentityService(crypto, storage)

        val first = service.loadOrCreate(AppId("exact.app/id"))
        val second = service.loadOrCreate(AppId("exact.app/id"))

        assertEquals(first.peerId, second.peerId)
        assertEquals(first.fingerprint, second.fingerprint)
        assertEquals(1, storage.generationCount)
        assertTrue(first.peerId.value.startsWith("p2id2-"))
        assertTrue(first.fingerprint.value.startsWith("p2f1-"))
        assertEquals(first.peerId, service.peerId(AppId("exact.app/id"), first.fingerprint))

        val qr = service.pairingQr(AppId("exact.app/id"), first.fingerprint)
        assertEquals(first.fingerprint, service.parsePairingQr(AppId("exact.app/id"), qr))
        assertNull(service.parsePairingQr(AppId("different-app"), qr))
    }

    @Test
    fun exactAppIdsThatOldSanitizerCollidedRemainIndependent() {
        val crypto = DeterministicTestIdentityCryptography()
        val storage = TestSecureIdentityStorage()
        val service = SecureIdentityService(crypto, storage)

        val punctuationA = service.loadOrCreate(AppId("app/a"))
        val punctuationB = service.loadOrCreate(AppId("app?a"))
        val longPrefix = "x".repeat(80)
        val longA = service.loadOrCreate(AppId(longPrefix + "a"))
        val longB = service.loadOrCreate(AppId(longPrefix + "b"))

        assertNotEquals(punctuationA.peerId, punctuationB.peerId)
        assertNotEquals(longA.peerId, longB.peerId)
        assertEquals(4, storage.generationCount)
    }

    @Test
    fun secureNamespaceRejectsUnpairedSurrogatesWithoutCollidingOrGenerating() {
        val storage = TestSecureIdentityStorage()
        val service = SecureIdentityService(DeterministicTestIdentityCryptography(), storage)

        val high = assertFailsWith<P2pError.SecurityConfigurationInvalid> {
            service.loadOrCreate(AppId("invalid-\ud800"))
        }
        val low = assertFailsWith<P2pError.SecurityConfigurationInvalid> {
            service.loadOrCreate(AppId("invalid-\udc00"))
        }

        assertTrue(high.reason.contains("well-formed Unicode"))
        assertTrue(low.reason.contains("well-formed Unicode"))
        assertEquals(0, storage.generationCount)

        val validSupplementary = service.loadOrCreate(AppId("valid-\ud83d\udd10"))
        assertTrue(validSupplementary.peerId.value.startsWith("p2id2-"))
    }

    @Test
    fun explicitResetRotatesOnlyTheSelectedAppIdentity() {
        val crypto = DeterministicTestIdentityCryptography()
        val storage = TestSecureIdentityStorage()
        val service = SecureIdentityService(crypto, storage)
        val selectedApp = AppId("reset-selected")
        val otherApp = AppId("reset-other")
        val selectedBefore = service.loadOrCreate(selectedApp)
        val otherBefore = service.loadOrCreate(otherApp)

        service.reset(selectedApp)

        val selectedAfter = service.loadOrCreate(selectedApp)
        val otherAfter = service.loadOrCreate(otherApp)
        assertNotEquals(selectedBefore.peerId, selectedAfter.peerId)
        assertNotEquals(selectedBefore.fingerprint, selectedAfter.fingerprint)
        assertEquals(otherBefore.peerId, otherAfter.peerId)
        assertEquals(otherBefore.fingerprint, otherAfter.fingerprint)
    }

    @Test
    fun storedPublicPrivateMismatchFailsClosedAndClearsOwnedPrivateKey() {
        val privateKey = ByteArray(32) { 7 }
        val mismatched = EncodedIdentityKeyPair(privateKey, ByteArray(32) { 9 })
        val storage = object : SecureIdentityStorage {
            override fun loadOrCreate(
                namespace: IdentityNamespace,
                fingerprintDigest: (EncodedIdentityKeyPair) -> ByteArray,
                generate: () -> EncodedIdentityKeyPair
            ): EncodedIdentityKeyPair = mismatched

            override fun reset(namespace: IdentityNamespace) = Unit
        }
        val error = assertFailsWith<P2pError.LocalIdentityUnavailable> {
            SecureIdentityService(DeterministicTestIdentityCryptography(), storage)
                .loadOrCreate(AppId("corrupt"))
        }

        assertEquals(LocalIdentityFailureKind.CORRUPT_RECORD, error.kind)
        assertEquals(LocalIdentityRecovery.EXPLICIT_RESET_REQUIRED, error.recovery)
        assertContentEquals(ByteArray(32), mismatched.privateKeyBytes())
    }

    @Test
    fun providerDerivationFailureRetainsCauseAndClearsEveryOwnedPrivateCopy() {
        val pair = validPair(12)
        var providerInput: ByteArray? = null
        val cause = IllegalStateException("provider unavailable")
        val crypto = object : IdentityCryptography {
            override fun sha256(bytes: ByteArray): ByteArray = ByteArray(32)
            override fun generateX25519KeyPair(): EncodedIdentityKeyPair = pair
            override fun deriveX25519PublicKey(privateKey: ByteArray): ByteArray {
                providerInput = privateKey
                throw cause
            }
        }
        val storage = TestSecureIdentityStorage()

        val error = assertFailsWith<P2pError.LocalIdentityUnavailable> {
            SecureIdentityService(crypto, storage).loadOrCreate(AppId("provider-failure"))
        }

        assertEquals(LocalIdentityFailureKind.CRYPTO_PROVIDER_UNAVAILABLE, error.kind)
        assertEquals(cause, error.cause)
        assertContentEquals(ByteArray(32), assertNotNull(providerInput))
        assertContentEquals(ByteArray(32), pair.privateKeyBytes())
    }

    @Test
    fun generationFailureIsTypedAndNoTransientIdentityIsCommitted() {
        val cause = IllegalStateException("rng failed")
        val crypto = object : IdentityCryptography {
            override fun sha256(bytes: ByteArray): ByteArray = ByteArray(32)
            override fun generateX25519KeyPair(): EncodedIdentityKeyPair = throw cause
            override fun deriveX25519PublicKey(privateKey: ByteArray): ByteArray = error("unused")
        }
        val storage = TestSecureIdentityStorage()

        val error = assertFailsWith<P2pError.LocalIdentityUnavailable> {
            SecureIdentityService(crypto, storage).loadOrCreate(AppId("generation-failure"))
        }

        assertEquals(LocalIdentityFailureKind.KEY_GENERATION_FAILED, error.kind)
        assertEquals(cause, error.cause)
        assertEquals(0, storage.committedCount)
    }

    @Test
    fun mismatchedDurableKeyFailsBeforePlatformCanCommitFingerprintMarker() {
        val mismatched = EncodedIdentityKeyPair(
            privateKey = ByteArray(32) { 4 },
            publicKey = ByteArray(32) { 99 }
        )
        var markerCommitted = false
        val storage = object : SecureIdentityStorage {
            override fun loadOrCreate(
                namespace: IdentityNamespace,
                fingerprintDigest: (EncodedIdentityKeyPair) -> ByteArray,
                generate: () -> EncodedIdentityKeyPair
            ): EncodedIdentityKeyPair = try {
                fingerprintDigest(mismatched)
                markerCommitted = true
                mismatched
            } finally {
                if (!markerCommitted) mismatched.clearPrivate()
            }

            override fun reset(namespace: IdentityNamespace) = Unit
        }

        val error = assertFailsWith<P2pError.LocalIdentityUnavailable> {
            SecureIdentityService(DeterministicTestIdentityCryptography(), storage)
                .loadOrCreate(AppId("marker-order"))
        }

        assertEquals(LocalIdentityFailureKind.CORRUPT_RECORD, error.kind)
        assertEquals(LocalIdentityRecovery.EXPLICIT_RESET_REQUIRED, error.recovery)
        assertEquals(false, markerCommitted)
    }

    @Test
    fun untypedStoreFailureIsRetryableAndRetainsCause() {
        val cause = IllegalStateException("locked store")
        val storage = object : SecureIdentityStorage {
            override fun loadOrCreate(
                namespace: IdentityNamespace,
                fingerprintDigest: (EncodedIdentityKeyPair) -> ByteArray,
                generate: () -> EncodedIdentityKeyPair
            ): EncodedIdentityKeyPair = throw cause

            override fun reset(namespace: IdentityNamespace) = Unit
        }

        val error = assertFailsWith<P2pError.LocalIdentityUnavailable> {
            SecureIdentityService(DeterministicTestIdentityCryptography(), storage)
                .loadOrCreate(AppId("store-failure"))
        }

        assertEquals(LocalIdentityFailureKind.TEMPORARILY_UNAVAILABLE, error.kind)
        assertEquals(LocalIdentityRecovery.RETRY, error.recovery)
        assertEquals(cause, error.cause)
    }

    @Test
    fun cancellationFromStorePropagatesUnchanged() {
        val cancellation = CancellationException("cancel secure identity load")
        val storage = object : SecureIdentityStorage {
            override fun loadOrCreate(
                namespace: IdentityNamespace,
                fingerprintDigest: (EncodedIdentityKeyPair) -> ByteArray,
                generate: () -> EncodedIdentityKeyPair
            ): EncodedIdentityKeyPair = throw cancellation

            override fun reset(namespace: IdentityNamespace) = Unit
        }

        val thrown = assertFailsWith<CancellationException> {
            SecureIdentityService(DeterministicTestIdentityCryptography(), storage)
                .loadOrCreate(AppId("cancelled-store"))
        }

        assertSame(cancellation, thrown)
    }

    private fun validPair(seed: Int): EncodedIdentityKeyPair {
        val privateKey = ByteArray(32) { (seed + it).toByte() }
        val publicKey = privateKey.map { (it.toInt() xor 0x5a).toByte() }.toByteArray()
        return EncodedIdentityKeyPair(privateKey, publicKey)
    }

    private class TestSecureIdentityStorage : SecureIdentityStorage {
        private val committed = mutableMapOf<String, EncodedIdentityKeyPair>()
        var generationCount: Int = 0
            private set
        val committedCount: Int get() = committed.size

        override fun loadOrCreate(
            namespace: IdentityNamespace,
            fingerprintDigest: (EncodedIdentityKeyPair) -> ByteArray,
            generate: () -> EncodedIdentityKeyPair
        ): EncodedIdentityKeyPair {
            val existing = committed[namespace.storageKey]
            if (existing != null) return copy(existing).also { validateDigest(it, fingerprintDigest) }

            generationCount++
            val candidate = generate()
            return try {
                val durable = copy(candidate)
                validateDigest(durable, fingerprintDigest)
                committed[namespace.storageKey] = durable
                copy(durable)
            } finally {
                candidate.clearPrivate()
            }
        }

        override fun reset(namespace: IdentityNamespace) {
            committed.remove(namespace.storageKey)?.clearPrivate()
        }

        private fun copy(pair: EncodedIdentityKeyPair): EncodedIdentityKeyPair =
            EncodedIdentityKeyPair(pair.privateKeyBytes(), pair.publicKeyBytes())

        private fun validateDigest(
            pair: EncodedIdentityKeyPair,
            fingerprintDigest: (EncodedIdentityKeyPair) -> ByteArray
        ) {
            val digest = fingerprintDigest(pair)
            try {
                require(digest.size == 32)
            } finally {
                digest.fill(0)
            }
        }
    }

    private class DeterministicTestIdentityCryptography : IdentityCryptography {
        private var generation = 0

        override fun sha256(bytes: ByteArray): ByteArray {
            var accumulator = 0x13579bdf
            for (byte in bytes) accumulator = accumulator * 33 xor (byte.toInt() and 0xff)
            return ByteArray(32) { index ->
                (accumulator ushr ((index and 3) * 8) xor index * 29).toByte()
            }
        }

        override fun generateX25519KeyPair(): EncodedIdentityKeyPair {
            generation++
            val privateKey = ByteArray(32) { (generation + it).toByte() }
            return EncodedIdentityKeyPair(privateKey, deriveX25519PublicKey(privateKey))
        }

        override fun deriveX25519PublicKey(privateKey: ByteArray): ByteArray =
            privateKey.map { (it.toInt() xor 0x5a).toByte() }.toByteArray()
    }
}
