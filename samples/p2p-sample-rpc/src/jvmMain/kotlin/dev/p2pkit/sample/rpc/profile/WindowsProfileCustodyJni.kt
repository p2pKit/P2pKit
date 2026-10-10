package dev.p2pkit.sample.rpc.profile

/**
 * Actual JNI entry points for the incomplete Windows custody component, not a production profile provider.
 * No initializer loads a DLL. A future reviewed loader must establish DLL authority before invoking these methods.
 * Atomic mutation, crash recovery and approved durability are absent; the required profile capability mask rejects it.
 */
internal object WindowsProfileCustodyJni {
    external fun abi(): Int
    external fun capabilities(): Long
    external fun openRoot(): Long
    external fun child(directory: Long, name: String): Long
    external fun identity(handle: Long): LongArray
    external fun read(directory: Long, name: String, maximum: Int): ByteArray
    /** Existing protected lock file only; exclusive share-none open, never queued or created implicitly. */
    external fun lockExisting(directory: Long, name: String): Long
    external fun close(handle: Long)
}
