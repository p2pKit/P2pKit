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
    /** Fixed root/identity FILE_CREATE under a verified profile lease; no fallback or namespace durability. */
    external fun createChildDirectory(directory: Long, name: String): Long
    external fun identity(handle: Long): LongArray
    external fun fileIdentity(directory: Long, name: String): LongArray
    external fun exists(directory: Long, name: String): Boolean
    external fun names(directory: Long): Array<String>
    external fun read(directory: Long, name: String, maximum: Int): ByteArray
    /** Only empty profile.lock/vault.lock in their bound scopes; vault requires a verified profile lease. */
    external fun lockExisting(directory: Long, name: String): Long
    /** Exact root/profile.lock FILE_CREATE; live exclusive handle, no fallback/replace/namespace durability. */
    external fun createProfileLock(root: Long): Long
    /** Exact root/identity/vault.lock FILE_CREATE under a verified profile lease; never an existing-file fallback. */
    external fun createVaultLock(identityDirectory: Long): Long
    /** Disposable <=256KiB stage: fixed random name, root/profile or identity/profile+vault leases; no commit. */
    external fun stageRecord(directory: Long, name: String, ciphertext: ByteArray): Long
    /** Retires only the original owned stage. Normal handle/session close also discards it. */
    external fun discardStage(stage: Long)
    /** Role-bound expected-ID deletion intent + original handle retirement; NOT absence, sync or a transaction. */
    external fun requestExpectedFileDeletion(directory: Long, name: String, expected: LongArray)
    /** Lease close rejects live dependants; root close independently retires every original owner. */
    external fun close(handle: Long)
}
