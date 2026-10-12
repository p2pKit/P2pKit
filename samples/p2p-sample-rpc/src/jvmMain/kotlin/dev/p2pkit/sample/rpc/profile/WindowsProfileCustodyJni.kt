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
    /** Explicit protected FILE_CREATE only; collision refusal, no rollback or durable namespace claim. */
    external fun createChildDirectory(directory: Long, name: String): Long
    external fun identity(handle: Long): LongArray
    external fun fileIdentity(directory: Long, name: String): LongArray
    external fun exists(directory: Long, name: String): Boolean
    external fun names(directory: Long): Array<String>
    external fun read(directory: Long, name: String, maximum: Int): ByteArray
    /** Existing protected lock file only; exclusive share-none open, never queued or created implicitly. */
    external fun lockExisting(directory: Long, name: String): Long
    /** Exact root/profile.lock FILE_CREATE; live exclusive handle, no fallback/replace/namespace durability. */
    external fun createProfileLock(root: Long): Long
    /** Disposable only: exact pwp-stage- plus 32 lowercase hex chars, <=256KiB ciphertext, no commit/rename. */
    external fun stageRecord(directory: Long, name: String, ciphertext: ByteArray): Long
    /** Retires only the original owned stage. Normal handle/session close also discards it. */
    external fun discardStage(stage: Long)
    /** Checked deletion intent + original handle retirement only; NOT name absence, sync or a transaction. */
    external fun requestExpectedFileDeletion(directory: Long, name: String, expected: LongArray)
    external fun close(handle: Long)
}
