package dev.p2pkit.sample.rpc.profile

/**
 * Proposed synchronous JNI contract, NOT a native implementation or loader. Windows x64/local fixed NTFS only.
 * All strings are validated single components; root comes from KnownFolder LocalAppData/P2pKit/RpcProfile.
 * Native operations must revalidate pinned handles, exact token-user+SYSTEM protected DACLs, file/volume IDs,
 * no reparse/ADS/hardlinks/aliases, exclusive locks, and transaction/durability semantics documented in docs/rpc.
 * A failed close is uncertain: the native handle must be quarantined and never reused or retried.
 */
internal interface WindowsProfileNativeApi {
    fun abi(): Int
    fun capabilities(): Long
    fun openRoot(): Long
    fun directoryIdentity(handle: Long): LongArray
    fun fileIdentity(directory: Long, name: String): LongArray
    fun exists(directory: Long, name: String): Boolean
    fun names(directory: Long): Array<String>
    fun child(directory: Long, name: String, create: Boolean): Long
    fun read(directory: Long, name: String, maximum: Int): ByteArray
    /** Return only after complete atomic publication and the approved durable transaction boundary. */
    fun write(directory: Long, name: String, bytes: ByteArray, replace: Boolean)
    fun lock(directory: Long, name: String, nonBlocking: Boolean): Long
    /** Validate expected file identity on the actual handle used for deletion, not a later pathname lookup. */
    fun delete(directory: Long, name: String, expected: LongArray): Boolean
    fun sync(directory: Long)
    fun deleteIfEmpty(directory: Long)
    fun close(handle: Long)
}

internal object WindowsProfileAvailability {
    const val IMPLEMENTED = false
    const val QUALIFIED = false
    fun requirePosixProductionHost(osName: String = System.getProperty("os.name")) {
        check(!osName.startsWith("Windows", ignoreCase = true)) {
            "Windows protected profile unavailable: native transactions, loader and qualification remain incomplete"
        }
    }
}

internal data class WindowsProfileIdentity(val volume: Long, val high: Long, val low: Long, val directory: Boolean) {
    fun encoded(): LongArray = longArrayOf(1, volume, high, low, if (directory) DIRECTORY_FLAGS else FILE_FLAGS, 1)
    companion object {
        // Native x64, fixed local NTFS, exact token owner, protected exact user+SYSTEM ACL,
        // no reparse/delete-pending, canonical pinned path, noninheritable; last flag distinguishes directory/file.
        const val DIRECTORY_FLAGS = 0x1ffL
        const val FILE_FLAGS = 0x2ffL
        fun decode(raw: LongArray, directory: Boolean): WindowsProfileIdentity {
            check(raw.size == 6 && raw[0] == 1L && (raw[2] != 0L || raw[3] != 0L) && raw[5] == 1L)
            check(raw[4] == if (directory) DIRECTORY_FLAGS else FILE_FLAGS) { "Native profile policy not proven" }
            return WindowsProfileIdentity(raw[1], raw[2], raw[3], directory)
        }
    }
}
