package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.LocalIdentityFailureKind
import dev.p2pkit.core.LocalIdentityRecovery
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.security.IdentityNamespace
import dev.p2pkit.core.security.IdentityRecordCorruptException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import kotlin.concurrent.thread
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** Host-executable proof of the frozen Android `P2KB` authenticated blob layout. */
class AndroidIdentityBlobCodecAndroidHostTest {
    private val namespace = namespace(seed = 0)
    private val iv = ByteArray(AndroidIdentityBlobCodec.IV_SIZE) { (it + 32).toByte() }
    private val ciphertext = ByteArray(120) { (it + 64).toByte() }

    @Test
    fun encodingIsExactlyTheFrozenAuthenticatedLayout() {
        val blob = AndroidIdentityBlobCodec.encode(namespace, iv, ciphertext)

        assertEquals(175, blob.size)
        assertContentEquals("P2KB".encodeToByteArray(), blob.copyOfRange(0, 4))
        assertEquals(1, blob[4].toInt())
        assertEquals(1, blob[5].toInt())
        assertEquals(0, blob[6].toInt())
        assertEquals(0, blob[7].toInt())
        assertContentEquals(namespace.hashBytes(), blob.copyOfRange(8, 40))
        assertEquals(AndroidIdentityBlobCodec.IV_SIZE, blob[40].toInt())
        assertEquals(0, blob[41].toInt())
        assertEquals(ciphertext.size, blob[42].toInt() and 0xff)
        assertContentEquals(iv, blob.copyOfRange(43, 55))
        assertContentEquals(ciphertext, blob.copyOfRange(55, blob.size))
    }

    @Test
    fun decodingReturnsDefensivePartsAndExactHeaderAsAad() {
        val blob = AndroidIdentityBlobCodec.encode(namespace, iv, ciphertext)
        val expectedHeader = blob.copyOfRange(0, 43)
        val parts = AndroidIdentityBlobCodec.decode(namespace, blob)
        blob.fill(0)

        assertContentEquals(expectedHeader, parts.aad)
        assertContentEquals(iv, parts.iv)
        assertContentEquals(ciphertext, parts.ciphertext)
        assertFalse(parts.aad.all { it == 0.toByte() })

        parts.clear()
        assertTrue(parts.aad.all { it == 0.toByte() })
        assertTrue(parts.iv.all { it == 0.toByte() })
        assertTrue(parts.ciphertext.all { it == 0.toByte() })
    }

    @Test
    fun encoderCopiesInputsAndRejectsEveryUnsupportedLength() {
        val mutableIv = iv.copyOf()
        val mutableCiphertext = ciphertext.copyOf()
        val blob = AndroidIdentityBlobCodec.encode(namespace, mutableIv, mutableCiphertext)
        mutableIv.fill(0)
        mutableCiphertext.fill(0)

        val decoded = AndroidIdentityBlobCodec.decode(namespace, blob)
        try {
            assertContentEquals(iv, decoded.iv)
            assertContentEquals(ciphertext, decoded.ciphertext)
        } finally {
            decoded.clear()
        }

        assertFailsWith<IllegalArgumentException> {
            AndroidIdentityBlobCodec.encode(namespace, ByteArray(11), ciphertext)
        }
        assertFailsWith<IllegalArgumentException> {
            AndroidIdentityBlobCodec.encode(namespace, iv, ByteArray(119))
        }
        assertFailsWith<IllegalArgumentException> {
            AndroidIdentityBlobCodec.encode(namespace, iv, ByteArray(121))
        }
    }

    @Test
    fun decoderRejectsEveryStructuralFieldLengthAndNamespaceMismatch() {
        val valid = AndroidIdentityBlobCodec.encode(namespace, iv, ciphertext)

        assertCorrupt(valid.copyOf(valid.size - 1))
        assertCorrupt(valid + 0)
        assertCorrupt(valid.copyOf().also { it[0] = 'X'.code.toByte() })
        assertCorrupt(valid.copyOf().also { it[4] = 2 })
        assertCorrupt(valid.copyOf().also { it[5] = 2 })
        assertCorrupt(valid.copyOf().also { it[6] = 1 })
        assertCorrupt(valid.copyOf().also { it[7] = 1 })
        assertCorrupt(valid.copyOf().also { it[40] = 11 })
        assertCorrupt(valid.copyOf().also { it[41] = 1 })
        assertCorrupt(valid.copyOf().also { it[42] = 119 })
        assertFailsWith<IdentityRecordCorruptException> {
            AndroidIdentityBlobCodec.decode(namespace(seed = 1), valid)
        }
    }

    @Test
    fun ciphertextAndIvRemainOpaqueWhileHeaderIsStrict() {
        val valid = AndroidIdentityBlobCodec.encode(namespace, iv, ciphertext)
        val changedIv = valid.copyOf().also { it[43] = (it[43].toInt() xor 1).toByte() }
        val changedCiphertext = valid.copyOf().also { it[55] = (it[55].toInt() xor 1).toByte() }

        AndroidIdentityBlobCodec.decode(namespace, changedIv).also { parts ->
            try {
                assertFalse(parts.iv.contentEquals(iv))
            } finally {
                parts.clear()
            }
        }
        AndroidIdentityBlobCodec.decode(namespace, changedCiphertext).also { parts ->
            try {
                assertFalse(parts.ciphertext.contentEquals(ciphertext))
            } finally {
                parts.clear()
            }
        }
    }

    private fun assertCorrupt(blob: ByteArray) {
        assertFailsWith<IdentityRecordCorruptException> {
            AndroidIdentityBlobCodec.decode(namespace, blob)
        }
    }

    private fun namespace(seed: Int): IdentityNamespace {
        val appId = AppId("android-blob-codec-$seed")
        return IdentityNamespace(
            appId = appId,
            appIdBytes = appId.value.encodeToByteArray(),
            hash = ByteArray(32) { (seed + it).toByte() }
        )
    }
}

/** Host-executable proof of Android's live-kit/reset ownership state machine. */
class AndroidSecureIdentityLiveGuardAndroidHostTest {
    @Test
    fun everyLiveOwnerBlocksResetUntilEveryIdempotentReleaseCompletes() {
        val namespace = "android-live-guard-multiple-owners"
        val first = AndroidSecureIdentityLiveGuard.acquire(namespace)
        val second = AndroidSecureIdentityLiveGuard.acquire(namespace)

        try {
            assertResetBlockedByLiveUsage(namespace)
            first.release()
            first.release()
            assertResetBlockedByLiveUsage(namespace)
            second.release()
            second.release()
            AndroidSecureIdentityLiveGuard.runReset(namespace) { Unit }
        } finally {
            first.release()
            second.release()
        }
    }

    @Test
    fun activeResetRejectsUsageAndAnotherResetThenReleasesStateAfterFailure() {
        val namespace = "android-live-guard-active-reset"
        val entered = CountDownLatch(1)
        val proceed = CountDownLatch(1)
        val finished = CountDownLatch(1)
        val injected = IllegalStateException("injected reset failure")
        val resetFailure = AtomicReference<Throwable?>(null)

        thread(name = "android-secure-identity-reset") {
            try {
                AndroidSecureIdentityLiveGuard.runReset(namespace) {
                    entered.countDown()
                    check(proceed.await(5, TimeUnit.SECONDS)) {
                        "timed out waiting to complete reset"
                    }
                    throw injected
                }
            } catch (failure: Throwable) {
                resetFailure.set(failure)
            } finally {
                finished.countDown()
            }
        }

        assertTrue(entered.await(5, TimeUnit.SECONDS), "reset did not enter its exclusive block")
        try {
            val usageError = assertFailsWith<P2pError.LocalIdentityUnavailable> {
                AndroidSecureIdentityLiveGuard.acquire(namespace)
            }
            assertEquals(LocalIdentityFailureKind.TEMPORARILY_UNAVAILABLE, usageError.kind)
            assertEquals(LocalIdentityRecovery.RETRY, usageError.recovery)

            val resetError = assertFailsWith<P2pError.LocalIdentityUnavailable> {
                AndroidSecureIdentityLiveGuard.runReset(namespace) { Unit }
            }
            assertEquals(LocalIdentityFailureKind.TEMPORARILY_UNAVAILABLE, resetError.kind)
            assertEquals(LocalIdentityRecovery.RETRY, resetError.recovery)
        } finally {
            proceed.countDown()
        }

        assertTrue(finished.await(5, TimeUnit.SECONDS), "reset did not release its guard")
        assertTrue(resetFailure.get() === injected, "reset did not preserve the original failure")

        AndroidSecureIdentityLiveGuard.acquire(namespace).also { usage ->
            usage.release()
            usage.release()
        }
        AndroidSecureIdentityLiveGuard.runReset(namespace) { Unit }
    }

    private fun assertResetBlockedByLiveUsage(namespace: String) {
        val error = assertFailsWith<P2pError.LocalIdentityUnavailable> {
            AndroidSecureIdentityLiveGuard.runReset(namespace) { Unit }
        }
        assertEquals(LocalIdentityFailureKind.LIVE_IDENTITY_IN_USE, error.kind)
        assertEquals(LocalIdentityRecovery.RETRY, error.recovery)
    }
}

/** Host proof that every early Android Keystore path releases blob bytes. */
class AndroidIdentityBlobOwnershipAndroidHostTest {
    @Test
    fun blobIsClearedAfterSuccessAndAfterEarlyFailure() {
        val successful = ByteArray(175) { 1 }
        val result = withClearedAndroidIdentityBlob(successful) { "loaded" }
        assertEquals("loaded", result)
        assertContentEquals(ByteArray(successful.size), successful)

        val failed = ByteArray(175) { 2 }
        val injected = IllegalStateException("Keystore unavailable")
        val thrown = assertFailsWith<IllegalStateException> {
            withClearedAndroidIdentityBlob(failed) { throw injected }
        }
        assertTrue(thrown === injected)
        assertContentEquals(ByteArray(failed.size), failed)
    }

    @Test
    fun absentBlobDoesNotChangeTheOperationResult() {
        assertEquals(42, withClearedAndroidIdentityBlob(null) { 42 })
    }
}

/** Host proof that explicit reset can replace a corrupted pending marker. */
class AndroidIdentityResetMarkerAndroidHostTest {
    private val namespace = namespace(seed = 80)

    @Test
    fun explicitResetReplacesMalformedMarkerWithCanonicalDurableState() {
        var durable: ByteArray? = ByteArray(40)
        var replacementInput: ByteArray? = null

        AndroidIdentityResetMarker.replaceAndVerify(
            namespace = namespace,
            replace = { marker ->
                replacementInput = marker
                durable = marker.copyOf()
            },
            reread = { durable?.copyOf() }
        )

        assertTrue(checkNotNull(replacementInput).all { it == 0.toByte() })
        val committed = checkNotNull(durable)
        dev.p2pkit.core.security.IdentityStateMarkerCodec.decodeResetPending(namespace, committed)
    }

    @Test
    fun missingOrMalformedReplacementFailsClosedAndClearsReturnedBytes() {
        val missing = assertFailsWith<P2pError.LocalIdentityUnavailable> {
            AndroidIdentityResetMarker.replaceAndVerify(namespace, replace = { }, reread = { null })
        }
        assertEquals(LocalIdentityFailureKind.PERSISTENCE_FAILED, missing.kind)
        assertEquals(LocalIdentityRecovery.RETRY, missing.recovery)

        val malformed = ByteArray(40)
        val corrupt = assertFailsWith<P2pError.LocalIdentityUnavailable> {
            AndroidIdentityResetMarker.replaceAndVerify(
                namespace,
                replace = { },
                reread = { malformed }
            )
        }
        assertEquals(LocalIdentityFailureKind.CORRUPT_RECORD, corrupt.kind)
        assertEquals(LocalIdentityRecovery.EXPLICIT_RESET_REQUIRED, corrupt.recovery)
        assertContentEquals(ByteArray(malformed.size), malformed)
    }

    private fun namespace(seed: Int): IdentityNamespace {
        val appId = AppId("android-reset-marker-$seed")
        return IdentityNamespace(
            appId = appId,
            appIdBytes = appId.value.encodeToByteArray(),
            hash = ByteArray(32) { (seed + it).toByte() }
        )
    }
}

/** Host proof of first-creation blob/wrapping-key cleanup ordering. */
class AndroidIdentityFirstCreationCleanupAndroidHostTest {
    @Test
    fun aliasIsDeletedOnlyAfterBlobAbsenceIsProven() {
        val primary = IllegalStateException("atomic write failed")
        var blobDeletes = 0
        var aliasDeletes = 0

        cleanupFailedAndroidIdentityBlobWrite(
            primaryFailure = primary,
            deleteBlob = { blobDeletes += 1 },
            rereadBlob = { null },
            deleteAlias = { aliasDeletes += 1 }
        )

        assertEquals(1, blobDeletes)
        assertEquals(1, aliasDeletes)
        assertTrue(primary.suppressedExceptions.isEmpty())
    }

    @Test
    fun remainingBlobIsClearedAndKeepsAliasForFailClosedRecovery() {
        val primary = IllegalStateException("atomic write failed")
        val remaining = ByteArray(175) { 7 }
        var aliasDeletes = 0

        cleanupFailedAndroidIdentityBlobWrite(
            primaryFailure = primary,
            deleteBlob = { },
            rereadBlob = { remaining },
            deleteAlias = { aliasDeletes += 1 }
        )

        assertEquals(0, aliasDeletes)
        assertContentEquals(ByteArray(remaining.size), remaining)
        assertTrue(primary.suppressedExceptions.any {
            it is P2pError.LocalIdentityUnavailable &&
                it.kind == LocalIdentityFailureKind.PERSISTENCE_FAILED
        })
    }

    @Test
    fun uncertainBlobStateKeepsAliasAndRetainsCleanupFailure() {
        val primary = IllegalStateException("atomic write failed")
        val inspectionFailure = IllegalStateException("blob reread failed")
        var aliasDeletes = 0

        cleanupFailedAndroidIdentityBlobWrite(
            primaryFailure = primary,
            deleteBlob = { },
            rereadBlob = { throw inspectionFailure },
            deleteAlias = { aliasDeletes += 1 }
        )

        assertEquals(0, aliasDeletes)
        assertTrue(primary.suppressedExceptions.any { it === inspectionFailure })
    }

    @Test
    fun aliasCleanupFailureIsRetainedAfterBlobAbsence() {
        val primary = IllegalStateException("atomic write failed")
        val aliasFailure = IllegalStateException("alias delete failed")

        cleanupFailedAndroidIdentityBlobWrite(
            primaryFailure = primary,
            deleteBlob = { },
            rereadBlob = { null },
            deleteAlias = { throw aliasFailure }
        )

        assertTrue(primary.suppressedExceptions.any { it === aliasFailure })
    }
}
