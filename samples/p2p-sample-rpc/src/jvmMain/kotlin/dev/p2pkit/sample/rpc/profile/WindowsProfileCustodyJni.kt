package dev.p2pkit.sample.rpc.profile

/**
 * Actual JNI entry points for the incomplete Windows custody component, not a production profile provider.
 * No initializer loads a DLL. A future reviewed loader must establish DLL authority before invoking these methods.
 * Complete mutation, crash recovery and approved durability are absent; the required capability mask rejects it.
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
    /**
     * Private persistent candidate: <=256KiB, pending name, exact role grants; NOT a durable write/commit.
     * close(candidate) retains its file, including partial failure leftovers. No automatic promotion or recovery.
     */
    external fun prepareRecord(directory: Long, name: String, ciphertext: ByteArray): Long
    /**
     * Original-handle create-only same-directory rename; keeps the candidate/grants owned until close.
     * Only root profile.header or identity <64-lowercase-hex>.aesgcm. No replacement or namespace durability.
     * Post-attempt uncertainty seals native admission and survives even successful physical close.
     */
    external fun renameCandidate(candidate: Long, name: String)
    /**
     * Lease-serialized identity-record replacement using the original prepared candidate; never profile.header.
     * Supports first insertion. No automatic close, namespace sync, durable commit, recovery or expected-ID CAS.
     */
    external fun replaceCandidate(candidate: Long, name: String)
    /**
     * Original-handle NTFS directory flush under exact profile/vault grants; no record commit or recovery.
     * Uncertain completion seals native admission. This does not flush bootstrap ancestors or enable a provider.
     */
    external fun syncDirectory(directory: Long)
    /** Retires only the original owned stage. Normal handle/session close also discards it. */
    external fun discardStage(stage: Long)
    /** Role-bound expected-ID deletion intent + original handle retirement; NOT absence, sync or a transaction. */
    external fun requestExpectedFileDeletion(directory: Long, name: String, expected: LongArray)
    /** Lease close rejects live dependants; root close independently retires every original owner. */
    external fun close(handle: Long)
}
