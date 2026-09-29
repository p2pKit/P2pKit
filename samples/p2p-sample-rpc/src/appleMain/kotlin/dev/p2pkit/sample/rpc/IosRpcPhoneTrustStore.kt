@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)

package dev.p2pkit.sample.rpc

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcTrustPurpose
import dev.p2pkit.rpc.RpcTrustStore
import kotlinx.cinterop.addressOf
import kotlinx.cinterop.alloc
import kotlinx.cinterop.memScoped
import kotlinx.cinterop.ptr
import kotlinx.cinterop.reinterpret
import kotlinx.cinterop.usePinned
import kotlinx.cinterop.value
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
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
import platform.Security.SecItemAdd
import platform.Security.SecItemCopyMatching
import platform.Security.SecItemDelete
import platform.Security.SecItemUpdate
import platform.Security.errSecDuplicateItem
import platform.Security.errSecItemNotFound
import platform.Security.errSecSuccess
import platform.Security.kSecAttrAccessible
import platform.Security.kSecAttrAccessibleWhenUnlockedThisDeviceOnly
import platform.Security.kSecAttrAccount
import platform.Security.kSecAttrService
import platform.Security.kSecAttrSynchronizable
import platform.Security.kSecClass
import platform.Security.kSecClassGenericPassword
import platform.Security.kSecMatchLimit
import platform.Security.kSecMatchLimitOne
import platform.Security.kSecReturnData
import platform.Security.kSecValueData

/** Test-app approval storage only; atomic device-only Keychain replacement, no preferences or cloud sync. */
internal class IosRpcPhoneTrustStore(private val fixtureId: String? = null) : RpcTrustStore {
    private val service = "dev.p2pkit.rpc.phone-lab.trust.v1" + fixtureId?.also {
        require(it.matches(Regex("[A-Fa-f0-9-]{36}")))
    }?.let { "-$it" }.orEmpty()

    private fun account(appId: AppId, purpose: RpcTrustPurpose): String {
        require(appId == RpcCapacityContract.appId)
        return "${appId.value}:${purpose.name}"
    }

    override suspend fun load(appId: AppId, purpose: RpcTrustPurpose): Set<PeerFingerprint> = mutex.withLock {
        decode(read(account(appId, purpose)))
    }

    override suspend fun replace(appId: AppId, purpose: RpcTrustPurpose, fingerprints: Set<PeerFingerprint>) {
        mutex.withLock {
            val account = account(appId, purpose)
            require(fingerprints.size <= 128)
            decode(read(account)) // A corrupt/inaccessible record must not be silently erased.
            val bytes = fingerprints.map { it.value }.sorted().joinToString("\n").encodeToByteArray()
            withData(bytes) { data ->
                query(account) { query ->
                    dictionary { attributes ->
                        CFDictionarySetValue(attributes, kSecValueData, data)
                        CFDictionarySetValue(attributes, kSecAttrAccessible,
                            kSecAttrAccessibleWhenUnlockedThisDeviceOnly)
                        var status = SecItemUpdate(query, attributes)
                        if (status == errSecItemNotFound) {
                            CFDictionarySetValue(query, kSecValueData, data)
                            CFDictionarySetValue(query, kSecAttrAccessible,
                                kSecAttrAccessibleWhenUnlockedThisDeviceOnly)
                            status = SecItemAdd(query, null)
                            if (status == errSecDuplicateItem) {
                                // A separate process won creation. Atomic replacement, never delete-then-add.
                                status = this.query(account) { SecItemUpdate(it, attributes) }
                            }
                        }
                        check(status == errSecSuccess) { "Local test approval replacement failed" }
                    }
                }
            }
            check(decode(read(account)) == fingerprints)
        }
    }

    private fun decode(bytes: ByteArray?): Set<PeerFingerprint> {
        if (bytes == null) return emptySet()
        require(bytes.size <= 8192 && bytes.all { it == 10.toByte() || it.toInt() in 32..126 })
        val pins = bytes.decodeToString().split('\n').filter(String::isNotEmpty)
        require(pins.size <= 128 && pins.toSet().size == pins.size)
        return pins.map(PeerFingerprint::parse).toSet()
    }

    private fun read(account: String): ByteArray? = query(account) { query ->
        CFDictionarySetValue(query, kSecReturnData, kCFBooleanTrue)
        CFDictionarySetValue(query, kSecMatchLimit, kSecMatchLimitOne)
        memScoped {
            val returned = alloc<CFTypeRefVar>()
            returned.value = null
            val status = SecItemCopyMatching(query, returned.ptr)
            val value = returned.value
            try {
                if (status == errSecItemNotFound) null
                else {
                    check(status == errSecSuccess && value != null) { "Local test approvals unavailable" }
                    check(CFGetTypeID(value) == CFDataGetTypeID())
                    val data: CFDataRef = value.reinterpret()
                    val size = CFDataGetLength(data)
                    check(size in 0L..8192L)
                    ByteArray(size.toInt()).also { bytes ->
                        if (bytes.isNotEmpty()) bytes.usePinned {
                            CFDataGetBytes(data, CFRangeMake(0, size), it.addressOf(0).reinterpret())
                        }
                    }
                }
            } finally { value?.let(::CFRelease) }
        }
    }

    private inline fun <T> dictionary(block: (CFDictionaryRef) -> T): T {
        val value = checkNotNull(CFDictionaryCreateMutable(kCFAllocatorDefault, 0,
            kCFTypeDictionaryKeyCallBacks.ptr, kCFTypeDictionaryValueCallBacks.ptr))
        try { return block(value) } finally { CFRelease(value) }
    }

    private inline fun <T> query(account: String, block: (CFDictionaryRef) -> T): T = dictionary { dictionary ->
        val serviceRef = checkNotNull(CFStringCreateWithCString(kCFAllocatorDefault, service, kCFStringEncodingUTF8))
        try {
            val accountRef = checkNotNull(CFStringCreateWithCString(
                kCFAllocatorDefault, account, kCFStringEncodingUTF8))
            try {
                CFDictionarySetValue(dictionary, kSecClass, kSecClassGenericPassword)
                CFDictionarySetValue(dictionary, kSecAttrService, serviceRef)
                CFDictionarySetValue(dictionary, kSecAttrAccount, accountRef)
                CFDictionarySetValue(dictionary, kSecAttrSynchronizable, kCFBooleanFalse)
                block(dictionary)
            } finally { CFRelease(accountRef) }
        } finally { CFRelease(serviceRef) }
    }

    private inline fun <T> withData(bytes: ByteArray, block: (CFDataRef) -> T): T {
        val data = checkNotNull(if (bytes.isEmpty()) CFDataCreate(kCFAllocatorDefault, null, 0)
            else bytes.usePinned {
                CFDataCreate(kCFAllocatorDefault, it.addressOf(0).reinterpret(), bytes.size.toLong())
            })
        try { return block(data) } finally { CFRelease(data) }
    }

    /** Never callable for the real UI's stable store; only newly created nonce-scoped test records are removed. */
    suspend fun deleteSyntheticFixture() {
        checkNotNull(fixtureId)
        mutex.withLock {
            RpcTrustPurpose.entries.forEach { purpose ->
                query(account(RpcCapacityContract.appId, purpose)) {
                    val status = SecItemDelete(it)
                    check(status == errSecSuccess || status == errSecItemNotFound)
                }
            }
        }
    }

    private companion object { val mutex = Mutex() }
}
