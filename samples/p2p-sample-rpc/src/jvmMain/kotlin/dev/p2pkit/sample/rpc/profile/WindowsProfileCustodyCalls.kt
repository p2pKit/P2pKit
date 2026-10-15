package dev.p2pkit.sample.rpc.profile

/**
 * The exact JNI subset used by the managed custody bridge. Implemented by the actual native entry-point object;
 * deterministic tests supply inert calls without loading a DLL. No provider selection or loading authority.
 */
internal interface WindowsProfileCustodyCalls {
    fun abi(): Int
    fun capabilities(): Long
    fun openRoot(): Long
    fun child(directory: Long, name: String): Long
    fun createChildDirectory(directory: Long, name: String): Long
    fun identity(handle: Long): LongArray
    fun fileIdentity(directory: Long, name: String): LongArray
    fun exists(directory: Long, name: String): Boolean
    fun names(directory: Long): Array<String>
    fun read(directory: Long, name: String, maximum: Int): ByteArray
    fun lockExisting(directory: Long, name: String): Long
    fun createProfileLock(root: Long): Long
    fun createVaultLock(identityDirectory: Long): Long
    fun writeRecord(directory: Long, pendingName: String, target: String, ciphertext: ByteArray, replace: Boolean)
    fun deleteRecord(directory: Long, name: String, expected: LongArray)
    fun syncDirectory(directory: Long)
    fun close(handle: Long)
}
