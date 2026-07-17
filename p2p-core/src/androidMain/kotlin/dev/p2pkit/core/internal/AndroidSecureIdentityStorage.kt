package dev.p2pkit.core.internal

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyPermanentlyInvalidatedException
import android.security.keystore.KeyProperties
import android.security.keystore.UserNotAuthenticatedException
import android.util.AtomicFile
import dev.p2pkit.core.LocalIdentityFailureKind
import dev.p2pkit.core.LocalIdentityRecovery
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.security.EncodedIdentityKeyPair
import dev.p2pkit.core.security.IdentityKeyRecordCodec
import dev.p2pkit.core.security.IdentityNamespace
import dev.p2pkit.core.security.IdentityRecordCorruptException
import dev.p2pkit.core.security.IdentityStateMarkerCodec
import dev.p2pkit.core.security.SHA256_SIZE_BYTES
import dev.p2pkit.core.security.constantTimeEquals
import dev.p2pkit.core.security.localIdentityError
import java.io.File
import java.io.FileNotFoundException
import java.io.FileOutputStream
import java.io.RandomAccessFile
import java.security.KeyStore
import java.security.UnrecoverableKeyException
import java.util.concurrent.atomic.AtomicBoolean
import javax.crypto.AEADBadTagException
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import kotlinx.coroutines.CancellationException

/**
 * Storage-A implementation for Android.
 *
 * The X25519 record is never written directly. A non-exportable Android
 * Keystore AES-256 key wraps the exact P2KI record, and the strict P2KB blob is
 * committed under no-backup storage while both an in-process lock and a
 * cross-process file lock are held.
 */
internal class AndroidSecureIdentityStorage(
    context: Context
) : SecureIdentityStorage {
    private val noBackupRoot: File = try {
        context.applicationContext.noBackupFilesDir
    } catch (error: Exception) {
        throw localIdentityError(
            kind = LocalIdentityFailureKind.PERSISTENCE_FAILED,
            recovery = LocalIdentityRecovery.RETRY,
            reason = "Android no-backup storage is unavailable",
            cause = error
        )
    }

    override fun acquireUsage(namespace: IdentityNamespace): SecureIdentityUsage =
        AndroidSecureIdentityLiveGuard.acquire(namespace.storageKey)

    override fun loadOrCreate(
        namespace: IdentityNamespace,
        fingerprintDigest: (EncodedIdentityKeyPair) -> ByteArray,
        generate: () -> EncodedIdentityKeyPair
    ): EncodedIdentityKeyPair = withNamespaceLock(namespace) { paths ->
        ensureNoResetPending(namespace, paths)
        val storedBlob = readIdentityBlobOrNull(paths)
        val keyStore = openAndroidKeyStore()
        val alias = wrappingKeyAlias(namespace)
        val aliasExists = containsAlias(keyStore, alias)

        val winner = try {
            when {
                storedBlob != null && aliasExists -> decryptAndDecode(
                    namespace = namespace,
                    blob = storedBlob,
                    key = loadWrappingKey(keyStore, alias)
                )

                storedBlob != null -> throw localIdentityError(
                    kind = LocalIdentityFailureKind.KEY_MATERIAL_LOST,
                    recovery = LocalIdentityRecovery.EXPLICIT_RESET_REQUIRED,
                    reason = "The Android identity blob exists but its wrapping key is missing"
                )

                aliasExists -> throw localIdentityError(
                    kind = LocalIdentityFailureKind.INCOMPLETE_CREATION,
                    recovery = LocalIdentityRecovery.EXPLICIT_RESET_REQUIRED,
                    reason = "The Android wrapping key exists but the identity blob is missing"
                )

                else -> createAndCommit(namespace, paths, keyStore, alias, generate)
            }
        } finally {
            storedBlob?.fill(0)
        }
        validateFingerprintCallback(winner, fingerprintDigest)
    }

    override fun reset(namespace: IdentityNamespace): Unit =
        AndroidSecureIdentityLiveGuard.runReset(namespace.storageKey) {
            resetWhileExclusive(namespace)
        }

    private fun resetWhileExclusive(namespace: IdentityNamespace) {
        withNamespaceLock(namespace) { paths ->
            val existingReset = readResetMarkerOrNull(paths)
            if (existingReset == null) {
                val marker = IdentityStateMarkerCodec.encodeResetPending(namespace)
                try {
                    writeAtomic(paths.resetPending, marker)
                } finally {
                    marker.fill(0)
                }
                val durableReset = readResetMarkerOrNull(paths) ?: throw localIdentityError(
                    kind = LocalIdentityFailureKind.PERSISTENCE_FAILED,
                    recovery = LocalIdentityRecovery.RETRY,
                    reason = "Android reset-pending marker disappeared after atomic commit"
                )
                decodeResetMarker(namespace, durableReset)
            } else {
                decodeResetMarker(namespace, existingReset)
            }

            val keyStore = openAndroidKeyStore()
            val alias = wrappingKeyAlias(namespace)
            try {
                paths.identityBlob.delete()
                readIdentityBlobOrNull(paths)?.let { remaining ->
                    remaining.fill(0)
                    throw localIdentityError(
                        kind = LocalIdentityFailureKind.PERSISTENCE_FAILED,
                        recovery = LocalIdentityRecovery.RETRY,
                        reason = "Android identity blob remained after explicit reset"
                    )
                }
                deleteAliasIfPresent(keyStore, alias)
                paths.resetPending.delete()
                readResetMarkerOrNull(paths)?.let { remaining ->
                    remaining.fill(0)
                    throw localIdentityError(
                        kind = LocalIdentityFailureKind.PERSISTENCE_FAILED,
                        recovery = LocalIdentityRecovery.RETRY,
                        reason = "Android reset-pending marker remained after reset completed"
                    )
                }
            } catch (error: P2pError.LocalIdentityUnavailable) {
                throw error
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                throw localIdentityError(
                    kind = LocalIdentityFailureKind.PERSISTENCE_FAILED,
                    recovery = LocalIdentityRecovery.RETRY,
                    reason = "Failed to complete explicit Android identity reset",
                    cause = error
                )
            }
        }
    }

    private fun createAndCommit(
        namespace: IdentityNamespace,
        paths: NamespacePaths,
        keyStore: KeyStore,
        alias: String,
        generate: () -> EncodedIdentityKeyPair
    ): EncodedIdentityKeyPair {
        val candidate = try {
            generate()
        } catch (error: P2pError.LocalIdentityUnavailable) {
            throw error
        } catch (error: CancellationException) {
            throw error
        } catch (error: Exception) {
            throw localIdentityError(
                kind = LocalIdentityFailureKind.KEY_GENERATION_FAILED,
                recovery = LocalIdentityRecovery.RETRY,
                reason = "Failed to generate the Android secure identity",
                cause = error
            )
        }

        var blobCommitted = false
        var record: ByteArray? = null
        var wrappedBlob: ByteArray? = null
        try {
            record = IdentityKeyRecordCodec.encode(namespace, candidate)
            val wrappingKey = generateWrappingKey(alias)
            wrappedBlob = encryptRecord(namespace, record, wrappingKey)
            try {
                writeAtomic(paths.identityBlob, wrappedBlob)
                blobCommitted = true
            } catch (error: Exception) {
                paths.identityBlob.delete()
                throw error
            }

            // Never return the transient candidate. Re-read and validate the
            // durable winner while ownership is still serialized.
            val durableBlob = readIdentityBlobOrNull(paths) ?: throw localIdentityError(
                kind = LocalIdentityFailureKind.PERSISTENCE_FAILED,
                recovery = LocalIdentityRecovery.RETRY,
                reason = "Android identity blob disappeared after atomic commit"
            )
            return try {
                decryptAndDecode(
                    namespace = namespace,
                    blob = durableBlob,
                    key = loadWrappingKey(keyStore, alias)
                )
            } finally {
                durableBlob.fill(0)
            }
        } catch (error: P2pError.LocalIdentityUnavailable) {
            if (!blobCommitted) cleanupAliasFromFailedFirstCreation(keyStore, alias, error)
            throw error
        } catch (error: CancellationException) {
            if (!blobCommitted) cleanupAliasFromFailedFirstCreation(keyStore, alias, error)
            throw error
        } catch (error: Exception) {
            if (!blobCommitted) cleanupAliasFromFailedFirstCreation(keyStore, alias, error)
            throw localIdentityError(
                kind = LocalIdentityFailureKind.PERSISTENCE_FAILED,
                recovery = LocalIdentityRecovery.RETRY,
                reason = "Failed to commit the Android secure identity",
                cause = error
            )
        } finally {
            candidate.clearPrivate()
            record?.fill(0)
            wrappedBlob?.fill(0)
        }
    }

    private fun decryptAndDecode(
        namespace: IdentityNamespace,
        blob: ByteArray,
        key: SecretKey
    ): EncodedIdentityKeyPair {
        val parts = try {
            AndroidIdentityBlobCodec.decode(namespace, blob)
        } catch (error: IdentityRecordCorruptException) {
            throw corruptIdentity("Malformed Android P2KB identity blob", error)
        }

        var plaintext: ByteArray? = null
        try {
            val cipher = Cipher.getInstance(AES_GCM_TRANSFORMATION)
            cipher.init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(GCM_TAG_BITS, parts.iv))
            cipher.updateAAD(parts.aad)
            plaintext = cipher.doFinal(parts.ciphertext)
            return try {
                IdentityKeyRecordCodec.decode(namespace, plaintext)
            } catch (error: IdentityRecordCorruptException) {
                throw corruptIdentity("Malformed decrypted Android P2KI identity record", error)
            }
        } catch (error: P2pError.LocalIdentityUnavailable) {
            throw error
        } catch (error: AEADBadTagException) {
            throw corruptIdentity("Android identity authentication tag validation failed", error)
        } catch (error: KeyPermanentlyInvalidatedException) {
            throw invalidatedKey(error)
        } catch (error: UserNotAuthenticatedException) {
            throw deviceLocked(error)
        } catch (error: Exception) {
            throw localIdentityError(
                kind = LocalIdentityFailureKind.TEMPORARILY_UNAVAILABLE,
                recovery = LocalIdentityRecovery.RETRY,
                reason = "Failed to decrypt the Android secure identity",
                cause = error
            )
        } finally {
            plaintext?.fill(0)
            parts.clear()
        }
    }

    private fun encryptRecord(
        namespace: IdentityNamespace,
        record: ByteArray,
        key: SecretKey
    ): ByteArray {
        val aad = AndroidIdentityBlobCodec.header(namespace)
        var ciphertext: ByteArray? = null
        try {
            val cipher = Cipher.getInstance(AES_GCM_TRANSFORMATION)
            cipher.init(Cipher.ENCRYPT_MODE, key)
            val iv = cipher.iv ?: throw IllegalStateException("Android AES-GCM provider returned no IV")
            if (iv.size != AndroidIdentityBlobCodec.IV_SIZE) {
                throw IllegalStateException("Android AES-GCM provider returned a non-12-byte IV")
            }
            cipher.updateAAD(aad)
            ciphertext = cipher.doFinal(record)
            return AndroidIdentityBlobCodec.encode(namespace, iv, ciphertext)
        } catch (error: KeyPermanentlyInvalidatedException) {
            throw invalidatedKey(error)
        } catch (error: UserNotAuthenticatedException) {
            throw deviceLocked(error)
        } catch (error: Exception) {
            throw localIdentityError(
                kind = LocalIdentityFailureKind.CRYPTO_PROVIDER_UNAVAILABLE,
                recovery = LocalIdentityRecovery.FIX_PLATFORM_CONFIGURATION,
                reason = "Android AES-GCM wrapping failed",
                cause = error
            )
        } finally {
            aad.fill(0)
            ciphertext?.fill(0)
        }
    }

    private fun generateWrappingKey(alias: String): SecretKey = try {
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, ANDROID_KEYSTORE)
        generator.init(
            KeyGenParameterSpec.Builder(
                alias,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
            )
                .setKeySize(AES_KEY_SIZE_BITS)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true)
                .setUserAuthenticationRequired(false)
                .build()
        )
        generator.generateKey()
    } catch (error: Exception) {
        throw localIdentityError(
            kind = LocalIdentityFailureKind.KEY_GENERATION_FAILED,
            recovery = LocalIdentityRecovery.FIX_PLATFORM_CONFIGURATION,
            reason = "Android Keystore could not create the identity wrapping key",
            cause = error
        )
    }

    private fun openAndroidKeyStore(): KeyStore = try {
        KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
    } catch (error: Exception) {
        throw localIdentityError(
            kind = LocalIdentityFailureKind.TEMPORARILY_UNAVAILABLE,
            recovery = LocalIdentityRecovery.RETRY,
            reason = "Android Keystore is unavailable",
            cause = error
        )
    }

    private fun containsAlias(keyStore: KeyStore, alias: String): Boolean = try {
        keyStore.containsAlias(alias)
    } catch (error: Exception) {
        throw localIdentityError(
            kind = LocalIdentityFailureKind.TEMPORARILY_UNAVAILABLE,
            recovery = LocalIdentityRecovery.RETRY,
            reason = "Android Keystore could not inspect the identity wrapping key",
            cause = error
        )
    }

    private fun loadWrappingKey(keyStore: KeyStore, alias: String): SecretKey = try {
        val key = keyStore.getKey(alias, null)
        key as? SecretKey ?: throw localIdentityError(
            kind = LocalIdentityFailureKind.KEY_INVALIDATED,
            recovery = LocalIdentityRecovery.EXPLICIT_RESET_REQUIRED,
            reason = "Android identity wrapping key is unavailable or has the wrong type"
        )
    } catch (error: P2pError.LocalIdentityUnavailable) {
        throw error
    } catch (error: KeyPermanentlyInvalidatedException) {
        throw invalidatedKey(error)
    } catch (error: UnrecoverableKeyException) {
        throw invalidatedKey(error)
    } catch (error: UserNotAuthenticatedException) {
        throw deviceLocked(error)
    } catch (error: Exception) {
        throw localIdentityError(
            kind = LocalIdentityFailureKind.TEMPORARILY_UNAVAILABLE,
            recovery = LocalIdentityRecovery.RETRY,
            reason = "Android Keystore could not load the identity wrapping key",
            cause = error
        )
    }

    private fun deleteAliasIfPresent(keyStore: KeyStore, alias: String) {
        if (!containsAlias(keyStore, alias)) return
        try {
            keyStore.deleteEntry(alias)
            if (containsAlias(keyStore, alias)) {
                throw IllegalStateException("Android Keystore alias remained after deletion")
            }
        } catch (error: P2pError.LocalIdentityUnavailable) {
            throw error
        } catch (error: Exception) {
            throw localIdentityError(
                kind = LocalIdentityFailureKind.PERSISTENCE_FAILED,
                recovery = LocalIdentityRecovery.RETRY,
                reason = "Android Keystore could not delete the identity wrapping key",
                cause = error
            )
        }
    }

    private fun cleanupAliasFromFailedFirstCreation(
        keyStore: KeyStore,
        alias: String,
        primaryFailure: Throwable
    ) {
        try {
            // The state was checked as alias-absent while the cross-process
            // lock was held, so any alias now present belongs to this failed
            // first-creation transaction.
            deleteAliasIfPresent(keyStore, alias)
        } catch (cleanupFailure: Exception) {
            primaryFailure.addSuppressed(cleanupFailure)
        }
    }

    private fun ensureNoResetPending(namespace: IdentityNamespace, paths: NamespacePaths) {
        val reset = readResetMarkerOrNull(paths) ?: return
        decodeResetMarker(namespace, reset)
        throw localIdentityError(
            kind = LocalIdentityFailureKind.RESET_PENDING,
            recovery = LocalIdentityRecovery.EXPLICIT_RESET_REQUIRED,
            reason = "An explicit Android identity reset was interrupted"
        )
    }

    private fun validateFingerprintCallback(
        keyPair: EncodedIdentityKeyPair,
        fingerprintDigest: (EncodedIdentityKeyPair) -> ByteArray
    ): EncodedIdentityKeyPair {
        var digest: ByteArray? = null
        var success = false
        try {
            digest = fingerprintDigest(keyPair)
            if (digest.size != SHA256_SIZE_BYTES) {
                throw localIdentityError(
                    kind = LocalIdentityFailureKind.STORE_CONTRACT_VIOLATION,
                    recovery = LocalIdentityRecovery.FIX_PLATFORM_CONFIGURATION,
                    reason = "Identity fingerprint callback returned a non-32-byte digest"
                )
            }
            success = true
            return keyPair
        } finally {
            digest?.fill(0)
            if (!success) keyPair.clearPrivate()
        }
    }

    private fun decodeResetMarker(namespace: IdentityNamespace, marker: ByteArray) {
        try {
            IdentityStateMarkerCodec.decodeResetPending(namespace, marker)
        } catch (error: IdentityRecordCorruptException) {
            throw corruptIdentity("Malformed Android reset-pending marker", error)
        } finally {
            marker.fill(0)
        }
    }

    private fun readIdentityBlobOrNull(paths: NamespacePaths): ByteArray? =
        readAtomicOrNull(
            file = paths.identityBlob,
            expectedSize = AndroidIdentityBlobCodec.BLOB_SIZE,
            stateName = "Android P2KB identity blob"
        )

    private fun readResetMarkerOrNull(paths: NamespacePaths): ByteArray? =
        readAtomicOrNull(
            file = paths.resetPending,
            expectedSize = IdentityStateMarkerCodec.RESET_MARKER_SIZE,
            stateName = "Android P2KR reset marker"
        )

    private fun readAtomicOrNull(
        file: AtomicFile,
        expectedSize: Int,
        stateName: String
    ): ByteArray? = try {
        file.openRead().use { input ->
            if (input.channel.size() != expectedSize.toLong()) {
                throw corruptIdentity(
                    "$stateName has the wrong length",
                    IdentityRecordCorruptException("expected exactly $expectedSize bytes")
                )
            }
            val bytes = ByteArray(expectedSize)
            var offset = 0
            try {
                while (offset < bytes.size) {
                    val read = input.read(bytes, offset, bytes.size - offset)
                    if (read < 0) {
                        throw corruptIdentity(
                            "$stateName ended before its declared length",
                            IdentityRecordCorruptException("truncated secure identity state")
                        )
                    }
                    offset += read
                }
                if (input.read() != -1) {
                    throw corruptIdentity(
                        "$stateName contains trailing bytes",
                        IdentityRecordCorruptException("trailing secure identity state")
                    )
                }
                bytes
            } catch (error: Throwable) {
                bytes.fill(0)
                throw error
            }
        }
    } catch (_: FileNotFoundException) {
        null
    } catch (error: P2pError.LocalIdentityUnavailable) {
        throw error
    } catch (error: CancellationException) {
        throw error
    } catch (error: Exception) {
        throw localIdentityError(
            kind = LocalIdentityFailureKind.TEMPORARILY_UNAVAILABLE,
            recovery = LocalIdentityRecovery.RETRY,
            reason = "Failed to read Android secure identity state",
            cause = error
        )
    }

    private fun writeAtomic(file: AtomicFile, bytes: ByteArray) {
        var output: FileOutputStream? = null
        try {
            output = file.startWrite()
            output.write(bytes)
            file.finishWrite(output)
            output = null
        } catch (error: Exception) {
            output?.let {
                try {
                    file.failWrite(it)
                } catch (cleanupFailure: Exception) {
                    error.addSuppressed(cleanupFailure)
                }
            }
            throw localIdentityError(
                kind = LocalIdentityFailureKind.PERSISTENCE_FAILED,
                recovery = LocalIdentityRecovery.RETRY,
                reason = "Failed to atomically write Android secure identity state",
                cause = error
            )
        }
    }

    private inline fun <T> withNamespaceLock(
        namespace: IdentityNamespace,
        block: (NamespacePaths) -> T
    ): T = synchronized(processLock) {
        val paths = namespacePaths(namespace)
        try {
            if (!paths.directory.isDirectory) paths.directory.mkdirs()
            if (!paths.directory.isDirectory) {
                throw IllegalStateException("Could not create Android identity storage directory")
            }
            RandomAccessFile(paths.lockFile, "rw").use { randomAccess ->
                randomAccess.channel.use { channel ->
                    channel.lock().use {
                        block(paths)
                    }
                }
            }
        } catch (error: P2pError.LocalIdentityUnavailable) {
            throw error
        } catch (error: CancellationException) {
            throw error
        } catch (error: Exception) {
            throw localIdentityError(
                kind = LocalIdentityFailureKind.PERSISTENCE_FAILED,
                recovery = LocalIdentityRecovery.RETRY,
                reason = "Could not lock Android secure identity state",
                cause = error
            )
        }
    }

    private fun namespacePaths(namespace: IdentityNamespace): NamespacePaths {
        val directory = File(noBackupRoot, "p2pkit/identity-v2/${namespace.storageKey}")
        return NamespacePaths(
            directory = directory,
            lockFile = File(directory, "identity.lock"),
            identityBlob = AtomicFile(File(directory, "identity.blob")),
            resetPending = AtomicFile(File(directory, "reset.pending"))
        )
    }

    private fun wrappingKeyAlias(namespace: IdentityNamespace): String =
        "$WRAPPING_KEY_ALIAS_PREFIX${namespace.storageKey}"

    private fun corruptIdentity(reason: String, cause: Throwable): P2pError.LocalIdentityUnavailable =
        localIdentityError(
            kind = LocalIdentityFailureKind.CORRUPT_RECORD,
            recovery = LocalIdentityRecovery.EXPLICIT_RESET_REQUIRED,
            reason = reason,
            cause = cause
        )

    private fun invalidatedKey(cause: Throwable): P2pError.LocalIdentityUnavailable =
        localIdentityError(
            kind = LocalIdentityFailureKind.KEY_INVALIDATED,
            recovery = LocalIdentityRecovery.EXPLICIT_RESET_REQUIRED,
            reason = "Android invalidated the identity wrapping key",
            cause = cause
        )

    private fun deviceLocked(cause: Throwable): P2pError.LocalIdentityUnavailable =
        localIdentityError(
            kind = LocalIdentityFailureKind.DEVICE_LOCKED,
            recovery = LocalIdentityRecovery.RETRY_AFTER_DEVICE_UNLOCK,
            reason = "Android identity wrapping key is unavailable while the device is locked",
            cause = cause
        )

    private data class NamespacePaths(
        val directory: File,
        val lockFile: File,
        val identityBlob: AtomicFile,
        val resetPending: AtomicFile
    )

    private companion object {
        private const val ANDROID_KEYSTORE = "AndroidKeyStore"
        private const val WRAPPING_KEY_ALIAS_PREFIX = "dev.p2pkit.identity.v2."
        private const val AES_GCM_TRANSFORMATION = "AES/GCM/NoPadding"
        private const val AES_KEY_SIZE_BITS = 256
        private const val GCM_TAG_BITS = 128
        private val processLock = Any()
    }
}

/** Process-local exclusion between live kits and explicit reset calls. */
private object AndroidSecureIdentityLiveGuard {
    private val lock = Any()
    private val states = mutableMapOf<String, State>()

    fun acquire(namespace: String): SecureIdentityUsage {
        synchronized(lock) {
            val state = states.getOrPut(namespace) { State() }
            if (state.resetInProgress) {
                throw localIdentityError(
                    kind = LocalIdentityFailureKind.TEMPORARILY_UNAVAILABLE,
                    recovery = LocalIdentityRecovery.RETRY,
                    reason = "Android secure identity reset is already in progress"
                )
            }
            state.liveUsages++
        }

        val released = AtomicBoolean(false)
        return SecureIdentityUsage {
            if (!released.compareAndSet(false, true)) return@SecureIdentityUsage
            synchronized(lock) {
                val state = checkNotNull(states[namespace]) {
                    "Android secure identity usage state disappeared before release"
                }
                check(state.liveUsages > 0) { "Android secure identity usage count underflow" }
                state.liveUsages--
                if (state.liveUsages == 0 && !state.resetInProgress) states.remove(namespace)
            }
        }
    }

    fun <T> runReset(namespace: String, block: () -> T): T {
        synchronized(lock) {
            val state = states.getOrPut(namespace) { State() }
            if (state.liveUsages != 0) {
                throw localIdentityError(
                    kind = LocalIdentityFailureKind.LIVE_IDENTITY_IN_USE,
                    recovery = LocalIdentityRecovery.RETRY,
                    reason = "A live Android kit still owns this secure identity"
                )
            }
            if (state.resetInProgress) {
                throw localIdentityError(
                    kind = LocalIdentityFailureKind.TEMPORARILY_UNAVAILABLE,
                    recovery = LocalIdentityRecovery.RETRY,
                    reason = "Another Android secure identity reset is already in progress"
                )
            }
            state.resetInProgress = true
        }

        return try {
            block()
        } finally {
            synchronized(lock) {
                val state = checkNotNull(states[namespace]) {
                    "Android secure identity reset state disappeared before completion"
                }
                state.resetInProgress = false
                if (state.liveUsages == 0) states.remove(namespace)
            }
        }
    }

    private class State(
        var liveUsages: Int = 0,
        var resetInProgress: Boolean = false
    )
}

/** Strict codec for the frozen Android P2KB outer blob. */
internal object AndroidIdentityBlobCodec {
    const val IV_SIZE: Int = 12
    private const val CIPHERTEXT_SIZE = IdentityKeyRecordCodec.RECORD_SIZE + 16
    private const val HEADER_SIZE = 43
    const val BLOB_SIZE: Int = HEADER_SIZE + IV_SIZE + CIPHERTEXT_SIZE
    private const val SCHEMA = 0x01
    private const val AES_GCM_ALGORITHM = 0x01
    private val magic = byteArrayOf(
        'P'.code.toByte(),
        '2'.code.toByte(),
        'K'.code.toByte(),
        'B'.code.toByte()
    )

    fun header(namespace: IdentityNamespace): ByteArray = ByteArray(HEADER_SIZE).also { header ->
        magic.copyInto(header, 0)
        header[4] = SCHEMA.toByte()
        header[5] = AES_GCM_ALGORITHM.toByte()
        // 6..7 flags remain zero.
        namespace.hashBytes().copyInto(header, 8)
        header[40] = IV_SIZE.toByte()
        writeU16be(header, 41, CIPHERTEXT_SIZE)
    }

    fun encode(namespace: IdentityNamespace, iv: ByteArray, ciphertext: ByteArray): ByteArray {
        require(iv.size == IV_SIZE) { "P2KB IV must be 12 bytes" }
        require(ciphertext.size == CIPHERTEXT_SIZE) { "P2KB ciphertext must be 120 bytes" }
        val header = header(namespace)
        return try {
            ByteArray(BLOB_SIZE).also { blob ->
                header.copyInto(blob, 0)
                iv.copyInto(blob, HEADER_SIZE)
                ciphertext.copyInto(blob, HEADER_SIZE + IV_SIZE)
            }
        } finally {
            header.fill(0)
        }
    }

    fun decode(namespace: IdentityNamespace, blob: ByteArray): Parts {
        if (blob.size != BLOB_SIZE) corrupt("P2KB blob must be exactly 175 bytes")
        if (!constantTimeRegionEquals(blob, 0, magic)) corrupt("P2KB magic mismatch")
        if (blob[4].toInt() and 0xff != SCHEMA) corrupt("unsupported P2KB schema")
        if (blob[5].toInt() and 0xff != AES_GCM_ALGORITHM) corrupt("unsupported P2KB algorithm")
        if (blob[6].toInt() != 0 || blob[7].toInt() != 0) corrupt("P2KB flags must be zero")
        val storedNamespace = blob.copyOfRange(8, 40)
        val expectedNamespace = namespace.hashBytes()
        try {
            if (!constantTimeEquals(storedNamespace, expectedNamespace)) {
                corrupt("P2KB namespace mismatch")
            }
        } finally {
            storedNamespace.fill(0)
            expectedNamespace.fill(0)
        }
        if (blob[40].toInt() and 0xff != IV_SIZE) corrupt("P2KB IV length must be 12")
        if (readU16be(blob, 41) != CIPHERTEXT_SIZE) corrupt("P2KB ciphertext length must be 120")
        return Parts(
            aad = blob.copyOfRange(0, HEADER_SIZE),
            iv = blob.copyOfRange(HEADER_SIZE, HEADER_SIZE + IV_SIZE),
            ciphertext = blob.copyOfRange(HEADER_SIZE + IV_SIZE, BLOB_SIZE)
        )
    }

    internal class Parts(
        val aad: ByteArray,
        val iv: ByteArray,
        val ciphertext: ByteArray
    ) {
        fun clear() {
            aad.fill(0)
            iv.fill(0)
            ciphertext.fill(0)
        }
    }

    private fun writeU16be(target: ByteArray, offset: Int, value: Int) {
        target[offset] = (value ushr 8).toByte()
        target[offset + 1] = value.toByte()
    }

    private fun readU16be(source: ByteArray, offset: Int): Int =
        ((source[offset].toInt() and 0xff) shl 8) or (source[offset + 1].toInt() and 0xff)

    private fun constantTimeRegionEquals(
        source: ByteArray,
        offset: Int,
        expected: ByteArray
    ): Boolean {
        if (offset < 0 || source.size - offset < expected.size) return false
        var difference = 0
        for (index in expected.indices) {
            difference = difference or (source[offset + index].toInt() xor expected[index].toInt())
        }
        return difference == 0
    }

    private fun corrupt(reason: String): Nothing = throw IdentityRecordCorruptException(reason)
}
