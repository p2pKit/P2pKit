package dev.p2pkit.sample.rpc.profile

/**
 * Actual JNI entry points for the incomplete Windows custody component, not a production profile provider.
 * No initializer loads a DLL. A future reviewed loader must establish DLL authority before invoking these methods.
 * Full adapter/loading, crash recovery and runtime qualification are absent; the capability mask rejects it.
 */
internal object WindowsProfileCustodyJni {
    external fun abi(): Int
    external fun capabilities(): Long
    /** Fixed KnownFolder bootstrap; acknowledge original RpcProfile, P2pKit and LocalAppData before publication. */
    external fun openRoot(): Long
    external fun child(directory: Long, name: String): Long
    /** Fixed identity FILE_CREATE; sync original child then root under the retained profile lease before return. */
    external fun createChildDirectory(directory: Long, name: String): Long
    external fun identity(handle: Long): LongArray
    external fun fileIdentity(directory: Long, name: String): LongArray
    external fun exists(directory: Long, name: String): Boolean
    external fun names(directory: Long): Array<String>
    external fun read(directory: Long, name: String, maximum: Int): ByteArray
    /** Only empty profile.lock/vault.lock in their bound scopes; vault requires a verified profile lease. */
    external fun lockExisting(directory: Long, name: String): Long
    /** Exact profile.lock FILE_CREATE; file and original-parent sync before returning the held exclusive lease. */
    external fun createProfileLock(root: Long): Long
    /** Fixed vault.lock FILE_CREATE and file/parent sync under the original profile lease; no open fallback. */
    external fun createVaultLock(identityDirectory: Long): Long
    /** Disposable <=256KiB stage: fixed random name, root/profile or identity/profile+vault leases; no commit. */
    external fun stageRecord(directory: Long, name: String, ciphertext: ByteArray): Long
    /**
     * Private persistent candidate: <=256KiB, pending name, exact role grants; NOT a durable write/commit.
     * close(candidate) retains its file, including partial failure leftovers. No automatic promotion or recovery.
     */
    external fun prepareRecord(directory: Long, name: String, ciphertext: ByteArray): Long
    /**
     * Single-admission record publication, original-directory NTFS sync and exact candidate retirement.
     * pendingName must be fresh pwp-pending- plus 32 lowercase hex from 128 random bits; no collision retry.
     * replace is identity-record-only; headers stay create-only. Failure retains incomplete/ambiguous files.
     * Does not establish durable bootstrap ancestors, crash recovery, a loader or full-provider availability.
     */
    external fun writeRecord(
        directory: Long, pendingName: String, target: String, ciphertext: ByteArray, replace: Boolean,
    )
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
    /**
     * One admitted expected-ID deletion, exact final name-absence observation and original-parent NTFS sync.
     * Initial missing is an error; post-intent failures are uncertain, never false/harmless absence.
     * Retains original grants through completion. No retry, bootstrap, recovery or full-provider availability.
     */
    external fun deleteRecord(directory: Long, name: String, expected: LongArray)
    /** Lease close rejects live dependants; root close independently retires every original owner. */
    external fun close(handle: Long)
}
