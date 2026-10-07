package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.lab.LabFiles
import dev.p2pkit.sample.rpc.lab.LabTrustStore
import dev.p2pkit.sample.rpc.lab.LabVault
import java.nio.channels.FileChannel
import java.nio.channels.FileLock
import java.nio.file.Files
import java.nio.file.LinkOption
import java.nio.file.Path
import java.nio.file.attribute.BasicFileAttributes
import java.nio.file.attribute.PosixFilePermissions
import java.security.MessageDigest
import java.security.SecureRandom
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.PBEKeySpec

/**
 * Persistent POSIX sample profile: a user-supplied passphrase unlocks an AES-GCM identity/trust vault.
 * Not an OS keystore or password-recovery mechanism. No passphrase/key is saved, logged or put in argv.
 * One process holds the profile lock until all roles close; Stop does not erase identity or trust.
 */
internal class DesktopRpcProfile private constructor(
    val vault: LabVault,
    private val directory: Path,
    private val directoryKey: Any,
    private val channel: FileChannel,
    private val lock: FileLock,
) {
    val trust = LabTrustStore(vault)
    private var closed = false

    @Synchronized
    fun close() {
        if (closed) return
        check(identity(directory) == directoryKey) { "Profile directory changed; retain for owner review" }
        vault.close()
        lock.release()
        channel.close()
        closed = true
    }

    companion object {
        private val magic = "P2PKIT-DESKTOP-PBKDF2-SHA256-V1\n".toByteArray(Charsets.US_ASCII)
        private val proof = "P2pKit RPC desktop profile v1".toByteArray(Charsets.US_ASCII)
        private const val PROOF_NAMESPACE = "desktop-profile-key-check-v1"
        private const val ITERATIONS = 600_000

        /** Caller transfers password ownership; every exit clears the array (provider copies are best effort). */
        fun open(directory: Path, password: CharArray): DesktopRpcProfile {
            var channel: FileChannel? = null
            var lock: FileLock? = null
            var vault: LabVault? = null
            try {
                require(password.size in 12..128) { "Use a profile passphrase of 12–128 characters" }
                require(directory.isAbsolute && directory.normalize() == directory)
                if (!Files.exists(directory, LinkOption.NOFOLLOW_LINKS)) {
                    Files.createDirectory(directory,
                        PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rwx------")))
                }
                val directoryKey = identity(directory)
                val lockPath = directory.resolve("profile.lock")
                if (Files.exists(lockPath, LinkOption.NOFOLLOW_LINKS)) LabFiles.read(lockPath, 0)
                channel = LabFiles.lockChannel(lockPath)
                lock = checkNotNull(channel.tryLock()) { "Profile is already in use" }
                check(identity(directory) == directoryKey)
                val headerPath = directory.resolve("profile.header")
                val fresh = !Files.exists(headerPath, LinkOption.NOFOLLOW_LINKS)
                // Missing metadata must never silently replace an existing encrypted identity.
                if (fresh) check(Files.list(directory).use { paths ->
                    paths.allMatch { it == lockPath }
                }) { "Incomplete profile: preserve its files; no identity reset was attempted" }
                val header = if (fresh) magic + ByteArray(16).also(SecureRandom()::nextBytes)
                    else LabFiles.read(headerPath, magic.size + 16)
                require(header.size == magic.size + 16 && header.take(magic.size).toByteArray().contentEquals(magic))
                val specification = PBEKeySpec(password, header.copyOfRange(magic.size, header.size), ITERATIONS, 256)
                val key = try {
                    SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(specification).encoded
                }
                    finally { specification.clearPassword() }
                try {
                    if (fresh) {
                        LabFiles.write(headerPath, header)
                        LabFiles.newDirectory(directory, "identity")
                    }
                    vault = LabVault(directory.resolve("identity"), key)
                    if (fresh) vault.putIfAbsent(PROOF_NAMESPACE, proof)
                    check(MessageDigest.isEqual(checkNotNull(vault.read(PROOF_NAMESPACE)), proof)) {
                        "Profile key check failed"
                    }
                } finally { key.fill(0) }
                return DesktopRpcProfile(vault, directory, directoryKey, channel, lock)
            } catch (failure: Throwable) {
                try { vault?.close() } catch (cleanup: Throwable) { failure.addSuppressed(cleanup) }
                try { lock?.release() } catch (cleanup: Throwable) { failure.addSuppressed(cleanup) }
                try { channel?.close() } catch (cleanup: Throwable) { failure.addSuppressed(cleanup) }
                // Wrong passwords/corruption do not delete, recreate or overwrite any profile record.
                throw failure
            } finally { password.fill('\u0000') }
        }

        private fun identity(path: Path): Any {
            LabFiles.privateDirectory(path)
            return checkNotNull(Files.readAttributes(path, BasicFileAttributes::class.java,
                LinkOption.NOFOLLOW_LINKS).fileKey())
        }
    }
}
