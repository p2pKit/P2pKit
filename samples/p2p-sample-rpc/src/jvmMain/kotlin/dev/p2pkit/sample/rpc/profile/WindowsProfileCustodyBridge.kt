package dev.p2pkit.sample.rpc.profile

import java.security.SecureRandom

/**
 * Real call mapping to the partial custody component, not a complete provider or a DLL loader.
 * Reports actual ABI/capabilities; WindowsProfileFiles therefore still refuses custody ABI 13 / mask 0x43.
 * The session and native ledger retain operation/handle ownership. This bridge never retries, rebinds a calls
 * object, repairs storage, or manufactures full-provider authority from the presence of JNI exports.
 */
internal class WindowsProfileCustodyBridge(
    private val calls: WindowsProfileCustodyCalls = WindowsProfileCustodyJni,
    private val random: SecureRandom = SecureRandom(),
) : WindowsProfileNativeApi {
    @Volatile private var everAdmitted = false
    @Volatile private var pinFailed = false

    override fun abi(): Int = calls.abi()
    override fun capabilities(): Long = calls.capabilities()

    private fun requireCustodyPin() {
        check(!pinFailed) { "Windows custody admission is sealed" }
        try {
            // The same export names also exist in older, weaker custody ABIs. Check numeric authority
            // before each storage entry, not only when the Java object or its PE exports are inspected.
            check(calls.abi() == WindowsProfilePeImage.ABI && calls.capabilities() == 0x43L) {
                "Unsupported Windows custody ABI or capabilities"
            }
            check(!pinFailed) { "Windows custody admission is sealed" }
            everAdmitted = true
        } catch (failure: Throwable) {
            pinFailed = true
            throw failure
        }
    }

    private inline fun <T> storage(action: () -> T): T {
        requireCustodyPin()
        return action()
    }

    override fun openRoot(): Long = storage { calls.openRoot() }
    override fun directoryIdentity(handle: Long): LongArray = storage { calls.identity(handle) }
    override fun fileIdentity(directory: Long, name: String): LongArray = storage {
        calls.fileIdentity(directory, name)
    }
    override fun exists(directory: Long, name: String): Boolean = storage { calls.exists(directory, name) }
    override fun names(directory: Long): Array<String> = storage { calls.names(directory) }
    override fun child(directory: Long, name: String, create: Boolean): Long = storage {
        if (create) calls.createChildDirectory(directory, name) else calls.child(directory, name)
    }
    override fun read(directory: Long, name: String, maximum: Int): ByteArray = storage {
        calls.read(directory, name, maximum)
    }

    override fun write(directory: Long, name: String, bytes: ByteArray, replace: Boolean) {
        require(bytes.size <= MAXIMUM_RECORD_BYTES) { "Windows profile record exceeds its bound" }
        require((name == "profile.header" && !replace) || (name.length == 71 && recordName.matches(name))) {
            "Invalid Windows profile publication target"
        }
        requireCustodyPin()
        val entropy = ByteArray(16)
        try {
            random.nextBytes(entropy)
            val pending = buildString(44) {
                append("pwp-pending-")
                for (byte in entropy) {
                    val value = byte.toInt() and 255
                    append(HEX[value ushr 4])
                    append(HEX[value and 15])
                }
            }
            // One name, one attempt. Creation collisions and ambiguous publication are not retry authority.
            storage { calls.writeRecord(directory, pending, name, bytes, replace) }
        } finally {
            entropy.fill(0)
        }
    }

    override fun lock(directory: Long, name: String, nonBlocking: Boolean): Long {
        require(nonBlocking) { "Windows profile leases require explicit nonBlocking=true" }
        require(name == "profile.lock" || name == "vault.lock") { "Unsupported Windows profile lease" }
        val present = storage { calls.exists(directory, name) }
        return storage {
            if (present) calls.lockExisting(directory, name)
            else if (name == "profile.lock") calls.createProfileLock(directory)
            else calls.createVaultLock(directory)
        }
    }

    override fun delete(directory: Long, name: String, expected: LongArray): Boolean = storage {
        calls.deleteRecord(directory, name, expected)
        true // Native completion includes expected-ID deletion, exact absence, retirement and parent sync.
    }
    override fun sync(directory: Long) = storage { calls.syncDirectory(directory) }
    override fun deleteIfEmpty(directory: Long): Unit =
        throw UnsupportedOperationException("Windows profile fixture-directory deletion is unsupported")

    override fun close(handle: Long) {
        // A never-admitted bridge cannot act on arbitrary native owners. Once compatible custody was
        // admitted, failed/changed introspection must not prevent the original calls object from draining.
        check(everAdmitted) { "Windows custody cleanup requires prior compatible admission" }
        calls.close(handle)
    }

    private companion object {
        const val MAXIMUM_RECORD_BYTES = 262_144
        const val HEX = "0123456789abcdef"
        val recordName = Regex("[0-9a-f]{64}\\.aesgcm")
    }
}
