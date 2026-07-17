@file:OptIn(
    kotlinx.cinterop.BetaInteropApi::class,
    kotlinx.cinterop.ExperimentalForeignApi::class
)

package dev.p2pkit.core.internal

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
import kotlinx.coroutines.CancellationException
import kotlinx.cinterop.CPointer
import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.cinterop.ObjCObjectVar
import kotlinx.cinterop.addressOf
import kotlinx.cinterop.alloc
import kotlinx.cinterop.memScoped
import kotlinx.cinterop.ptr
import kotlinx.cinterop.reinterpret
import kotlinx.cinterop.usePinned
import kotlinx.cinterop.value
import platform.CoreFoundation.CFDataCreate
import platform.CoreFoundation.CFDataGetBytes
import platform.CoreFoundation.CFDataGetLength
import platform.CoreFoundation.CFDataGetTypeID
import platform.CoreFoundation.CFDataRef
import platform.CoreFoundation.CFDictionaryCreateMutable
import platform.CoreFoundation.CFDictionaryRef
import platform.CoreFoundation.CFDictionarySetValue
import platform.CoreFoundation.CFGetTypeID
import platform.CoreFoundation.CFRangeMake
import platform.CoreFoundation.CFRelease
import platform.CoreFoundation.CFStringCreateWithCString
import platform.CoreFoundation.CFTypeRefVar
import platform.CoreFoundation.kCFAllocatorDefault
import platform.CoreFoundation.kCFBooleanFalse
import platform.CoreFoundation.kCFBooleanTrue
import platform.CoreFoundation.kCFStringEncodingUTF8
import platform.CoreFoundation.kCFTypeDictionaryKeyCallBacks
import platform.CoreFoundation.kCFTypeDictionaryValueCallBacks
import platform.Foundation.NSApplicationSupportDirectory
import platform.Foundation.NSData
import platform.Foundation.NSDataWritingAtomic
import platform.Foundation.NSError
import platform.Foundation.NSFileManager
import platform.Foundation.NSLock
import platform.Foundation.NSURL
import platform.Foundation.NSURLIsExcludedFromBackupKey
import platform.Foundation.NSUserDomainMask
import platform.Foundation.data
import platform.Foundation.dataWithBytes
import platform.Foundation.writeToFile
import platform.Security.SecItemAdd
import platform.Security.SecItemCopyMatching
import platform.Security.SecItemDelete
import platform.Security.errSecAuthFailed
import platform.Security.errSecDecode
import platform.Security.errSecDuplicateItem
import platform.Security.errSecInteractionNotAllowed
import platform.Security.errSecItemNotFound
import platform.Security.errSecMissingEntitlement
import platform.Security.errSecNotAvailable
import platform.Security.errSecSuccess
import platform.Security.kSecAttrAccessible
import platform.Security.kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
import platform.Security.kSecAttrAccount
import platform.Security.kSecAttrService
import platform.Security.kSecAttrSynchronizable
import platform.Security.kSecClass
import platform.Security.kSecClassGenericPassword
import platform.Security.kSecMatchLimit
import platform.Security.kSecMatchLimitOne
import platform.Security.kSecReturnData
import platform.Security.kSecValueData
import platform.posix.O_RDONLY
import platform.posix.close
import platform.posix.errno
import platform.posix.fsync
import platform.posix.memcpy
import platform.posix.open

/** Storage-A implementation backed by a device-only Keychain item and P2KM marker. */
internal class IosSecureIdentityStorage(
    private val keychain: IosIdentityKeychain = SecurityFrameworkIdentityKeychain(),
    private val markerStore: IosIdentityMarkerStore = FoundationIdentityMarkerStore()
) : SecureIdentityStorage {

    override fun acquireUsage(namespace: IdentityNamespace): SecureIdentityUsage =
        IosSecureIdentityLiveGuard.acquire(namespace.storageKey)

    override fun loadOrCreate(
        namespace: IdentityNamespace,
        fingerprintDigest: (EncodedIdentityKeyPair) -> ByteArray,
        generate: () -> EncodedIdentityKeyPair
    ): EncodedIdentityKeyPair = withProcessLock {
        ensureNoResetPending(namespace)
        val account = namespace.storageKey
        val record = keychain.read(account)
        val marker = try {
            markerStore.readCommitted(namespace)
        } catch (error: Throwable) {
            record?.fill(0)
            throw error
        }

        try {
            when {
                record == null && marker != null -> throw localIdentityError(
                    kind = LocalIdentityFailureKind.KEY_MATERIAL_LOST,
                    recovery = LocalIdentityRecovery.EXPLICIT_RESET_REQUIRED,
                    reason = "The iOS identity marker exists but its Keychain item is missing"
                )

                record != null -> {
                    val winner = decodeIdentityRecord(namespace, record)
                    var success = false
                    try {
                        validateOrCommitMarker(namespace, winner, marker, fingerprintDigest)
                        success = true
                        winner
                    } finally {
                        if (!success) winner.clearPrivate()
                    }
                }

                else -> createAndCommit(namespace, fingerprintDigest, generate)
            }
        } finally {
            marker?.fill(0)
        }
    }

    override fun reset(namespace: IdentityNamespace): Unit =
        IosSecureIdentityLiveGuard.runReset(namespace.storageKey) {
            resetWhileExclusive(namespace)
        }

    private fun resetWhileExclusive(namespace: IdentityNamespace) {
        withProcessLock {
            val currentReset = markerStore.readResetPending(namespace)
            if (currentReset == null) {
                val encoded = IdentityStateMarkerCodec.encodeResetPending(namespace)
                try {
                    markerStore.writeResetPending(namespace, encoded)
                } finally {
                    encoded.fill(0)
                }
                val durable = markerStore.readResetPending(namespace) ?: throw localIdentityError(
                    kind = LocalIdentityFailureKind.PERSISTENCE_FAILED,
                    recovery = LocalIdentityRecovery.RETRY,
                    reason = "iOS reset-pending marker disappeared after atomic commit"
                )
                decodeResetMarker(namespace, durable)
            } else {
                decodeResetMarker(namespace, currentReset)
            }

            markerStore.deleteCommitted(namespace)
            markerStore.readCommitted(namespace)?.let { remaining ->
                remaining.fill(0)
                throw localIdentityError(
                    kind = LocalIdentityFailureKind.PERSISTENCE_FAILED,
                    recovery = LocalIdentityRecovery.RETRY,
                    reason = "iOS committed identity marker remained after explicit reset"
                )
            }

            keychain.delete(namespace.storageKey)
            keychain.read(namespace.storageKey)?.let { remaining ->
                remaining.fill(0)
                throw localIdentityError(
                    kind = LocalIdentityFailureKind.PERSISTENCE_FAILED,
                    recovery = LocalIdentityRecovery.RETRY,
                    reason = "iOS Keychain identity remained after explicit reset"
                )
            }
            markerStore.deleteResetPending(namespace)
            markerStore.readResetPending(namespace)?.let { remaining ->
                remaining.fill(0)
                throw localIdentityError(
                    kind = LocalIdentityFailureKind.PERSISTENCE_FAILED,
                    recovery = LocalIdentityRecovery.RETRY,
                    reason = "iOS reset-pending marker remained after reset completed"
                )
            }
        }
    }

    private fun createAndCommit(
        namespace: IdentityNamespace,
        fingerprintDigest: (EncodedIdentityKeyPair) -> ByteArray,
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
                reason = "Failed to generate the iOS secure identity",
                cause = error
            )
        }

        var record: ByteArray? = null
        try {
            record = IdentityKeyRecordCodec.encode(namespace, candidate)
            // A duplicate is a successful concurrent-create outcome. Never
            // return this candidate; reload the durable Keychain winner.
            keychain.add(namespace.storageKey, record)
        } finally {
            candidate.clearPrivate()
            record?.fill(0)
        }

        val durableRecord = keychain.read(namespace.storageKey) ?: throw localIdentityError(
            kind = LocalIdentityFailureKind.PERSISTENCE_FAILED,
            recovery = LocalIdentityRecovery.RETRY,
            reason = "iOS Keychain identity disappeared after add or duplicate resolution"
        )
        val winner = decodeIdentityRecord(namespace, durableRecord)
        var success = false
        try {
            // Re-read because a concurrent winner may have committed its marker
            // between our initial state snapshot and duplicate resolution.
            validateOrCommitMarker(
                namespace = namespace,
                keyPair = winner,
                existingMarker = markerStore.readCommitted(namespace),
                fingerprintDigest = fingerprintDigest
            )
            success = true
            return winner
        } finally {
            if (!success) winner.clearPrivate()
        }
    }

    private fun validateOrCommitMarker(
        namespace: IdentityNamespace,
        keyPair: EncodedIdentityKeyPair,
        existingMarker: ByteArray?,
        fingerprintDigest: (EncodedIdentityKeyPair) -> ByteArray
    ) {
        var digest: ByteArray? = null
        try {
            digest = try {
                fingerprintDigest(keyPair)
            } catch (error: P2pError.LocalIdentityUnavailable) {
                throw error
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                throw localIdentityError(
                    kind = LocalIdentityFailureKind.CRYPTO_PROVIDER_UNAVAILABLE,
                    recovery = LocalIdentityRecovery.FIX_PLATFORM_CONFIGURATION,
                    reason = "Failed to derive the iOS identity fingerprint marker",
                    cause = error
                )
            }
            if (digest.size != SHA256_SIZE_BYTES) {
                throw localIdentityError(
                    kind = LocalIdentityFailureKind.STORE_CONTRACT_VIOLATION,
                    recovery = LocalIdentityRecovery.FIX_PLATFORM_CONFIGURATION,
                    reason = "Identity fingerprint callback returned a non-32-byte digest"
                )
            }

            if (existingMarker != null) {
                validateCommittedMarker(namespace, existingMarker, digest)
                return
            }

            val encoded = IdentityStateMarkerCodec.encodeCommitted(namespace, digest)
            try {
                markerStore.writeCommitted(namespace, encoded)
            } finally {
                encoded.fill(0)
            }
            val durableMarker = markerStore.readCommitted(namespace) ?: throw localIdentityError(
                kind = LocalIdentityFailureKind.PERSISTENCE_FAILED,
                recovery = LocalIdentityRecovery.RETRY,
                reason = "iOS identity marker disappeared after atomic commit"
            )
            validateCommittedMarker(namespace, durableMarker, digest)
        } finally {
            digest?.fill(0)
            existingMarker?.fill(0)
        }
    }

    private fun validateCommittedMarker(
        namespace: IdentityNamespace,
        marker: ByteArray,
        expectedDigest: ByteArray
    ) {
        var storedDigest: ByteArray? = null
        try {
            storedDigest = IdentityStateMarkerCodec.decodeCommitted(namespace, marker)
            if (!constantTimeEquals(storedDigest, expectedDigest)) {
                throw corruptIdentity("iOS identity marker fingerprint does not match the Keychain item")
            }
        } catch (error: IdentityRecordCorruptException) {
            throw corruptIdentity("Malformed iOS committed identity marker", error)
        } finally {
            storedDigest?.fill(0)
            marker.fill(0)
        }
    }

    private fun decodeIdentityRecord(
        namespace: IdentityNamespace,
        record: ByteArray
    ): EncodedIdentityKeyPair = try {
        IdentityKeyRecordCodec.decode(namespace, record)
    } catch (error: IdentityRecordCorruptException) {
        throw corruptIdentity("Malformed iOS P2KI Keychain record", error)
    } finally {
        record.fill(0)
    }

    private fun ensureNoResetPending(namespace: IdentityNamespace) {
        val marker = markerStore.readResetPending(namespace) ?: return
        decodeResetMarker(namespace, marker)
        throw localIdentityError(
            kind = LocalIdentityFailureKind.RESET_PENDING,
            recovery = LocalIdentityRecovery.EXPLICIT_RESET_REQUIRED,
            reason = "An explicit iOS identity reset was interrupted"
        )
    }

    private fun decodeResetMarker(namespace: IdentityNamespace, marker: ByteArray) {
        try {
            IdentityStateMarkerCodec.decodeResetPending(namespace, marker)
        } catch (error: IdentityRecordCorruptException) {
            throw corruptIdentity("Malformed iOS reset-pending marker", error)
        } finally {
            marker.fill(0)
        }
    }

    private fun corruptIdentity(
        reason: String,
        cause: Throwable? = null
    ): P2pError.LocalIdentityUnavailable = localIdentityError(
        kind = LocalIdentityFailureKind.CORRUPT_RECORD,
        recovery = LocalIdentityRecovery.EXPLICIT_RESET_REQUIRED,
        reason = reason,
        cause = cause
    )

    private inline fun <T> withProcessLock(block: () -> T): T {
        processLock.lock()
        return try {
            block()
        } finally {
            processLock.unlock()
        }
    }

    private companion object {
        private val processLock = NSLock()
    }
}

/** Process-local exclusion between live kits and explicit reset calls. */
private object IosSecureIdentityLiveGuard {
    private val lock = NSLock()
    private val states = mutableMapOf<String, State>()

    fun acquire(namespace: String): SecureIdentityUsage {
        withLock {
            val state = states.getOrPut(namespace) { State() }
            if (state.resetInProgress) {
                throw localIdentityError(
                    kind = LocalIdentityFailureKind.TEMPORARILY_UNAVAILABLE,
                    recovery = LocalIdentityRecovery.RETRY,
                    reason = "iOS secure identity reset is already in progress"
                )
            }
            state.liveUsages++
        }
        return IosSecureIdentityUsage(namespace)
    }

    fun <T> runReset(namespace: String, block: () -> T): T {
        withLock {
            val state = states.getOrPut(namespace) { State() }
            if (state.liveUsages != 0) {
                throw localIdentityError(
                    kind = LocalIdentityFailureKind.LIVE_IDENTITY_IN_USE,
                    recovery = LocalIdentityRecovery.RETRY,
                    reason = "A live iOS kit still owns this secure identity"
                )
            }
            if (state.resetInProgress) {
                throw localIdentityError(
                    kind = LocalIdentityFailureKind.TEMPORARILY_UNAVAILABLE,
                    recovery = LocalIdentityRecovery.RETRY,
                    reason = "Another iOS secure identity reset is already in progress"
                )
            }
            state.resetInProgress = true
        }

        return try {
            block()
        } finally {
            withLock {
                val state = checkNotNull(states[namespace]) {
                    "iOS secure identity reset state disappeared before completion"
                }
                state.resetInProgress = false
                if (state.liveUsages == 0) states.remove(namespace)
            }
        }
    }

    fun release(namespace: String) {
        withLock {
            val state = checkNotNull(states[namespace]) {
                "iOS secure identity usage state disappeared before release"
            }
            check(state.liveUsages > 0) { "iOS secure identity usage count underflow" }
            state.liveUsages--
            if (state.liveUsages == 0 && !state.resetInProgress) states.remove(namespace)
        }
    }

    private inline fun <T> withLock(block: () -> T): T {
        lock.lock()
        return try {
            block()
        } finally {
            lock.unlock()
        }
    }

    private class State(
        var liveUsages: Int = 0,
        var resetInProgress: Boolean = false
    )
}

private class IosSecureIdentityUsage(
    private val namespace: String
) : SecureIdentityUsage {
    private val lock = NSLock()
    private var released = false

    override fun release() {
        lock.lock()
        val shouldRelease = try {
            if (released) false else {
                released = true
                true
            }
        } finally {
            lock.unlock()
        }
        if (shouldRelease) IosSecureIdentityLiveGuard.release(namespace)
    }
}

/** Small boundary that makes the Keychain state machine deterministic in tests. */
internal interface IosIdentityKeychain {
    fun read(account: String): ByteArray?

    /** Returns `true` when added and `false` when another creator already won. */
    fun add(account: String, record: ByteArray): Boolean

    fun delete(account: String)
}

internal interface IosIdentityMarkerStore {
    fun readCommitted(namespace: IdentityNamespace): ByteArray?
    fun writeCommitted(namespace: IdentityNamespace, marker: ByteArray)
    fun deleteCommitted(namespace: IdentityNamespace)
    fun readResetPending(namespace: IdentityNamespace): ByteArray?
    fun writeResetPending(namespace: IdentityNamespace, marker: ByteArray)
    fun deleteResetPending(namespace: IdentityNamespace)
}

/** Exact non-synchronizable generic-password Keychain adapter. */
internal class SecurityFrameworkIdentityKeychain(
    private val service: String = KEYCHAIN_SERVICE
) : IosIdentityKeychain {

    override fun read(account: String): ByteArray? = withQuery(
        account = account,
        returnData = true
    ) { query ->
        memScoped {
            val result = alloc<CFTypeRefVar>()
            result.value = null
            val status = SecItemCopyMatching(query, result.ptr)
            val value = result.value
            try {
                when (status) {
                    errSecItemNotFound -> null
                    errSecSuccess -> {
                        val returned = value ?: throw keychainContractError(
                            "Keychain read succeeded without returning identity data"
                        )
                        if (CFGetTypeID(returned) != CFDataGetTypeID()) {
                            throw corruptKeychain("Keychain identity item is not data")
                        }
                        copyCfData(returned.reinterpret())
                    }
                    else -> throw keychainStatusError("read", status)
                }
            } finally {
                value?.let(::CFRelease)
            }
        }
    }

    override fun add(account: String, record: ByteArray): Boolean = withQuery(
        account = account,
        valueData = record
    ) { query ->
        when (val status = SecItemAdd(query, null)) {
            errSecSuccess -> true
            errSecDuplicateItem -> false
            else -> throw keychainStatusError("add", status)
        }
    }

    override fun delete(account: String) {
        withQuery(account = account) { query ->
            when (val status = SecItemDelete(query)) {
                errSecSuccess, errSecItemNotFound -> Unit
                else -> throw keychainStatusError("delete", status)
            }
        }
    }

    private inline fun <T> withQuery(
        account: String,
        valueData: ByteArray? = null,
        returnData: Boolean = false,
        block: (CFDictionaryRef) -> T
    ): T {
        val dictionary = CFDictionaryCreateMutable(
            allocator = kCFAllocatorDefault,
            capacity = 0,
            keyCallBacks = kCFTypeDictionaryKeyCallBacks.ptr,
            valueCallBacks = kCFTypeDictionaryValueCallBacks.ptr
        ) ?: throw keychainContractError("Could not allocate a Keychain query")
        val serviceRef = CFStringCreateWithCString(
            alloc = kCFAllocatorDefault,
            cStr = service,
            encoding = kCFStringEncodingUTF8
        ) ?: run {
            CFRelease(dictionary)
            throw keychainContractError("Could not encode the Keychain service")
        }
        val accountRef = CFStringCreateWithCString(
            alloc = kCFAllocatorDefault,
            cStr = account,
            encoding = kCFStringEncodingUTF8
        ) ?: run {
            CFRelease(serviceRef)
            CFRelease(dictionary)
            throw keychainContractError("Could not encode the Keychain account")
        }
        var dataRef: CFDataRef? = null
        try {
            CFDictionarySetValue(dictionary, kSecClass, kSecClassGenericPassword)
            CFDictionarySetValue(dictionary, kSecAttrService, serviceRef)
            CFDictionarySetValue(dictionary, kSecAttrAccount, accountRef)
            CFDictionarySetValue(dictionary, kSecAttrSynchronizable, kCFBooleanFalse)
            if (returnData) {
                CFDictionarySetValue(dictionary, kSecReturnData, kCFBooleanTrue)
                CFDictionarySetValue(dictionary, kSecMatchLimit, kSecMatchLimitOne)
            }
            if (valueData != null) {
                dataRef = createCfData(valueData)
                CFDictionarySetValue(dictionary, kSecValueData, dataRef)
                CFDictionarySetValue(
                    dictionary,
                    kSecAttrAccessible,
                    kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
                )
            }
            return block(dictionary)
        } finally {
            dataRef?.let(::CFRelease)
            CFRelease(accountRef)
            CFRelease(serviceRef)
            CFRelease(dictionary)
        }
    }

    private fun createCfData(bytes: ByteArray): CFDataRef {
        if (bytes.isEmpty()) {
            return CFDataCreate(kCFAllocatorDefault, null, 0)
                ?: throw keychainContractError("Could not allocate empty Keychain data")
        }
        return bytes.usePinned { pinned ->
            CFDataCreate(
                allocator = kCFAllocatorDefault,
                bytes = pinned.addressOf(0).reinterpret(),
                length = bytes.size.toLong()
            )
        } ?: throw keychainContractError("Could not allocate Keychain identity data")
    }

    private fun copyCfData(data: CFDataRef): ByteArray {
        val size = CFDataGetLength(data)
        if (size != IdentityKeyRecordCodec.RECORD_SIZE.toLong()) {
            throw corruptKeychain("Keychain identity record must be exactly 104 bytes")
        }
        return ByteArray(size.toInt()).also { result ->
            if (result.isNotEmpty()) {
                result.usePinned { pinned ->
                    CFDataGetBytes(data, CFRangeMake(0, size), pinned.addressOf(0).reinterpret())
                }
            }
        }
    }

    private fun keychainStatusError(
        operation: String,
        status: Int
    ): P2pError.LocalIdentityUnavailable {
        val cause = IosKeychainOperationException(operation, status)
        return when (status) {
            errSecInteractionNotAllowed -> localIdentityError(
                kind = LocalIdentityFailureKind.DEVICE_LOCKED,
                recovery = LocalIdentityRecovery.RETRY_AFTER_DEVICE_UNLOCK,
                reason = "The iOS secure identity is unavailable before first device unlock",
                cause = cause
            )
            errSecMissingEntitlement, errSecAuthFailed -> localIdentityError(
                kind = LocalIdentityFailureKind.PERMISSION_OR_ENTITLEMENT_DENIED,
                recovery = LocalIdentityRecovery.FIX_PLATFORM_CONFIGURATION,
                reason = "iOS denied access to the secure identity Keychain item",
                cause = cause
            )
            errSecDecode -> corruptKeychain("iOS could not decode the secure identity Keychain item", cause)
            errSecNotAvailable -> localIdentityError(
                kind = LocalIdentityFailureKind.TEMPORARILY_UNAVAILABLE,
                recovery = LocalIdentityRecovery.RETRY,
                reason = "The iOS Keychain is temporarily unavailable",
                cause = cause
            )
            else -> localIdentityError(
                kind = LocalIdentityFailureKind.TEMPORARILY_UNAVAILABLE,
                recovery = LocalIdentityRecovery.RETRY,
                reason = "The iOS Keychain operation failed",
                cause = cause
            )
        }
    }

    private fun corruptKeychain(
        reason: String,
        cause: Throwable? = null
    ): P2pError.LocalIdentityUnavailable = localIdentityError(
        kind = LocalIdentityFailureKind.CORRUPT_RECORD,
        recovery = LocalIdentityRecovery.EXPLICIT_RESET_REQUIRED,
        reason = reason,
        cause = cause
    )

    private fun keychainContractError(reason: String): P2pError.LocalIdentityUnavailable =
        localIdentityError(
            kind = LocalIdentityFailureKind.STORE_CONTRACT_VIOLATION,
            recovery = LocalIdentityRecovery.FIX_PLATFORM_CONFIGURATION,
            reason = reason
        )

    private companion object {
        private const val KEYCHAIN_SERVICE = "dev.p2pkit.identity.v2"
    }
}

/** Atomic Application Support marker files, excluded from device backup. */
internal class FoundationIdentityMarkerStore(
    private val applicationSupportRootOverride: String? = null,
    private val fileManager: NSFileManager = NSFileManager.defaultManager
) : IosIdentityMarkerStore {

    override fun readCommitted(namespace: IdentityNamespace): ByteArray? =
        readMarker(namespace, COMMITTED_MARKER_FILE)

    override fun writeCommitted(namespace: IdentityNamespace, marker: ByteArray) {
        writeMarker(namespace, COMMITTED_MARKER_FILE, marker)
    }

    override fun deleteCommitted(namespace: IdentityNamespace) {
        deleteMarker(namespace, COMMITTED_MARKER_FILE)
    }

    override fun readResetPending(namespace: IdentityNamespace): ByteArray? =
        readMarker(namespace, RESET_PENDING_FILE)

    override fun writeResetPending(namespace: IdentityNamespace, marker: ByteArray) {
        writeMarker(namespace, RESET_PENDING_FILE, marker)
    }

    override fun deleteResetPending(namespace: IdentityNamespace) {
        deleteMarker(namespace, RESET_PENDING_FILE)
    }

    private fun readMarker(namespace: IdentityNamespace, fileName: String): ByteArray? {
        val directory = ensureNamespaceDirectory(namespace)
        val path = "$directory/$fileName"
        if (!fileManager.fileExistsAtPath(path)) return null
        val data = fileManager.contentsAtPath(path) ?: throw fileFailure(
            operation = "read",
            reason = "iOS identity marker exists but could not be read"
        )
        val expectedSize = expectedMarkerSize(fileName)
        if (data.length != expectedSize.toULong()) {
            throw localIdentityError(
                kind = LocalIdentityFailureKind.CORRUPT_RECORD,
                recovery = LocalIdentityRecovery.EXPLICIT_RESET_REQUIRED,
                reason = "iOS identity marker has the wrong length"
            )
        }
        ensureExcludedFromBackup(NSURL.fileURLWithPath(path))
        return data.toByteArrayCopy()
    }

    private fun writeMarker(namespace: IdentityNamespace, fileName: String, marker: ByteArray) {
        val directory = ensureNamespaceDirectory(namespace)
        val path = "$directory/$fileName"
        val data = marker.toNSDataCopy()
        memScoped {
            val error = alloc<ObjCObjectVar<NSError?>>()
            error.value = null
            if (!data.writeToFile(path, NSDataWritingAtomic, error.ptr)) {
                throw fileFailure("write", "Failed to atomically write iOS identity marker", error.value)
            }
        }
        val url = NSURL.fileURLWithPath(path)
        ensureExcludedFromBackup(url)
        synchronizePath(path, "fsync-marker")
        synchronizePath(directory, "fsync-marker-directory")
        val durable = fileManager.contentsAtPath(path) ?: throw fileFailure(
            operation = "read-after-write",
            reason = "iOS identity marker disappeared after atomic write"
        )
        if (durable.length != marker.size.toULong()) {
            throw fileFailure(
                operation = "read-after-write",
                reason = "iOS identity marker length changed during atomic commit"
            )
        }
        val durableBytes = durable.toByteArrayCopy()
        try {
            if (!constantTimeEquals(durableBytes, marker)) {
                throw fileFailure(
                    operation = "read-after-write",
                    reason = "iOS identity marker changed during atomic commit"
                )
            }
        } finally {
            durableBytes.fill(0)
        }
    }

    private fun deleteMarker(namespace: IdentityNamespace, fileName: String) {
        val directory = ensureNamespaceDirectory(namespace)
        val path = "$directory/$fileName"
        if (!fileManager.fileExistsAtPath(path)) return
        memScoped {
            val error = alloc<ObjCObjectVar<NSError?>>()
            error.value = null
            if (!fileManager.removeItemAtPath(path, error.ptr)) {
                throw fileFailure("delete", "Failed to delete iOS identity marker", error.value)
            }
        }
        if (fileManager.fileExistsAtPath(path)) {
            throw fileFailure("delete", "iOS identity marker remained after deletion")
        }
        synchronizePath(directory, "fsync-marker-delete-directory")
    }

    private fun ensureNamespaceDirectory(namespace: IdentityNamespace): String {
        val root = applicationSupportRootOverride ?: applicationSupportRoot()
        val directory = "$root/p2pkit/identity-v2/${namespace.storageKey}"
        memScoped {
            val error = alloc<ObjCObjectVar<NSError?>>()
            error.value = null
            if (!fileManager.createDirectoryAtPath(
                    path = directory,
                    withIntermediateDirectories = true,
                    attributes = null,
                    error = error.ptr
                )
            ) {
                throw fileFailure("mkdir", "Failed to create iOS identity marker directory", error.value)
            }
        }
        ensureExcludedFromBackup(NSURL.fileURLWithPath(directory, isDirectory = true))
        return directory
    }

    private fun applicationSupportRoot(): String = memScoped {
        val error = alloc<ObjCObjectVar<NSError?>>()
        error.value = null
        val url = fileManager.URLForDirectory(
            directory = NSApplicationSupportDirectory,
            inDomain = NSUserDomainMask,
            appropriateForURL = null,
            create = true,
            error = error.ptr
        ) ?: throw fileFailure(
            "application-support",
            "iOS Application Support directory is unavailable",
            error.value
        )
        url.path ?: throw fileFailure(
            "application-support",
            "iOS Application Support directory has no filesystem path"
        )
    }

    private fun ensureExcludedFromBackup(url: NSURL) {
        val key = NSURLIsExcludedFromBackupKey ?: throw fileFailure(
            "exclude-backup",
            "iOS backup-exclusion resource key is unavailable"
        )
        memScoped {
            val error = alloc<ObjCObjectVar<NSError?>>()
            error.value = null
            if (!url.setResourceValue(true, forKey = key, error = error.ptr)) {
                throw fileFailure(
                    "exclude-backup",
                    "Failed to exclude iOS identity state from backup",
                    error.value
                )
            }
        }
    }

    private fun synchronizePath(path: String, operation: String) {
        val descriptor = open(path, O_RDONLY)
        if (descriptor < 0) {
            throw posixFailure(operation, "Failed to open iOS identity state for synchronization", errno)
        }
        var primaryFailure: Throwable? = null
        try {
            if (fsync(descriptor) != 0) {
                throw posixFailure(operation, "Failed to durably synchronize iOS identity state", errno)
            }
        } catch (error: Throwable) {
            primaryFailure = error
            throw error
        } finally {
            if (close(descriptor) != 0) {
                val closeFailure = posixFailure(
                    "$operation-close",
                    "Failed to close synchronized iOS identity state",
                    errno
                )
                if (primaryFailure != null) {
                    primaryFailure.addSuppressed(closeFailure)
                } else {
                    throw closeFailure
                }
            }
        }
    }

    private fun fileFailure(
        operation: String,
        reason: String,
        error: NSError? = null
    ): P2pError.LocalIdentityUnavailable = localIdentityError(
        kind = if (operation == "exclude-backup") {
            LocalIdentityFailureKind.PERMISSION_OR_ENTITLEMENT_DENIED
        } else {
            LocalIdentityFailureKind.PERSISTENCE_FAILED
        },
        recovery = if (operation == "exclude-backup") {
            LocalIdentityRecovery.FIX_PLATFORM_CONFIGURATION
        } else {
            LocalIdentityRecovery.RETRY
        },
        reason = reason,
        cause = IosFoundationOperationException(operation, error)
    )

    private fun posixFailure(
        operation: String,
        reason: String,
        errorNumber: Int
    ): P2pError.LocalIdentityUnavailable = localIdentityError(
        kind = LocalIdentityFailureKind.PERSISTENCE_FAILED,
        recovery = LocalIdentityRecovery.RETRY,
        reason = reason,
        cause = IosPosixOperationException(operation, errorNumber)
    )

    private fun expectedMarkerSize(fileName: String): Int = when (fileName) {
        COMMITTED_MARKER_FILE -> IdentityStateMarkerCodec.COMMITTED_MARKER_SIZE
        RESET_PENDING_FILE -> IdentityStateMarkerCodec.RESET_MARKER_SIZE
        else -> error("unknown identity marker file")
    }

    private companion object {
        private const val COMMITTED_MARKER_FILE = "identity.marker"
        private const val RESET_PENDING_FILE = "reset.pending"
    }
}

private class IosKeychainOperationException(
    operation: String,
    status: Int
) : Exception("iOS Keychain $operation failed with OSStatus $status")

private class IosFoundationOperationException(
    operation: String,
    error: NSError?
) : Exception(
    buildString {
        append("iOS identity storage ")
        append(operation)
        append(" failed")
        if (error != null) {
            append(": ")
            append(error.domain)
            append('/')
            append(error.code)
            append(" (")
            append(error.localizedDescription)
            append(')')
        }
    }
)

private class IosPosixOperationException(
    operation: String,
    errorNumber: Int
) : Exception("iOS identity storage $operation failed with errno $errorNumber")

private fun ByteArray.toNSDataCopy(): NSData {
    if (isEmpty()) return NSData.data()
    return usePinned { pinned ->
        NSData.dataWithBytes(pinned.addressOf(0), size.toULong())
    }
}

private fun NSData.toByteArrayCopy(): ByteArray {
    val size = length.toInt()
    return ByteArray(size).also { result ->
        if (size != 0) {
            result.usePinned { pinned ->
                memcpy(pinned.addressOf(0), bytes, length)
            }
        }
    }
}
