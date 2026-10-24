package dev.p2pkit.sample.rpc.lab

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.security.JvmSecureIdentityStore
import dev.p2pkit.rpc.RpcTrustPurpose
import dev.p2pkit.rpc.RpcTrustStore
import dev.p2pkit.sample.rpc.RpcCapacityContract
import dev.p2pkit.sample.rpc.profile.PosixProfileDirectory
import dev.p2pkit.sample.rpc.profile.ProtectedProfileDirectory
import java.nio.file.Path
import java.security.SecureRandom
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.locks.ReentrantLock
import javax.crypto.Cipher
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec
import kotlin.concurrent.withLock

/**
 * Synthetic-only encrypted file store. Each instance gets an independent 256-bit key.
 * The key is retained ONLY by the supervising JVM, never persisted beside ciphertext,
 * printed, exported or passed in argv. Data writes and trust replacements are atomic
 * and fsynced; a JVM restart deliberately destroys this fixture's recoverability.
 * This is not a production keystore, crash-surviving trust store or offline queue.
 * Callers reopening/sharing a store must supply the same key and coordinate its lifetime.
 * A provider session, if any, owns directory handles beyond close() so fixture destroy() can still verify custody.
 * DesktopRpcProfile closes that session only after vault users and its profile lock retire.
 */
internal class LabVault private constructor(
    private val directory: ProtectedProfileDirectory,
    key: ByteArray?,
    private val copyBytes: (ByteArray) -> ByteArray,
    private val nonBlockingLeases: Boolean = false,
) : JvmSecureIdentityStore {
    constructor(directory: ProtectedProfileDirectory, key: ByteArray, nonBlockingLeases: Boolean = false) :
        this(directory, key, { it.copyOf() }, nonBlockingLeases)
    constructor(directory: Path) : this(PosixProfileDirectory(directory), null, { it.copyOf() })
    constructor(directory: Path, key: ByteArray) : this(admitDirectory(directory, key), key)
    private var closed = false
    private val ownedFiles = linkedMapOf<String, Any>()
    // Directory admission and ordinary field initialization precede key allocation. A generated key is
    // owned directly here, not passed through a default argument then copied into a second live array.
    private val secret = if (key == null) randomKey() else run { requireKey(key); checkedCopy(key) }
    private val mutex = try { locks.computeIfAbsent(directory.mutexIdentity) { ReentrantLock() } }
        catch (failure: Throwable) { secret.fill(0); throw failure }

    private fun checkedCopy(input: ByteArray, excluded: ByteArray? = null): ByteArray {
        val copy = copyBytes(input)
        val independent = copy !== input && copy !== excluded
        try {
            check(independent && copy.size == input.size && copy.contentEquals(input)) { "Invalid vault copy" }
            return copy
        } catch (failure: Throwable) {
            // A faulty validation copier must not clear caller-owned input or the live vault key.
            if (independent) copy.fill(0)
            throw failure
        }
    }

    private fun <T> locked(block: () -> T): T = mutex.withLock {
        check(!closed)
        directory.verifyIdentity()
        val lockFile = "vault.lock"
        val createLock = !directory.exists(lockFile)
        var pending: Any? = null
        try {
            // Windows explicitly requests one lease attempt. Existing POSIX/fixture callers retain waiting;
            // no retry, provider fallback or claim that the underlying native syscall cannot block is implied.
            directory.lock(lockFile, nonBlocking = nonBlockingLeases).use {
                if (createLock) ownedFiles[lockFile] = directory.fileIdentity(lockFile)
                block().also { pending = it }
            }
        } catch (failure: Throwable) {
            // A plaintext result is caller-owned only after the lease really closes. A close failure
            // can occur after a successful read/write; do not leave the unreturned winner uncleared.
            (pending as? ByteArray)?.fill(0)
            throw failure
        }
    }

    private fun file(namespace: String): String {
        requireNamespace(namespace)
        return LabFiles.sha256(namespace.toByteArray()) + ".aesgcm"
    }

    private fun readLocked(namespace: String): ByteArray? {
        val path = file(namespace)
        if (!directory.exists(path)) return null
        val record = directory.read(path)
        require(record.size in 29..262_144 && record[0] == 1.toByte())
        return cipher(Cipher.DECRYPT_MODE, record.copyOfRange(1, 13), namespace)
            .doFinal(record, 13, record.size - 13)
    }

    private fun cipher(mode: Int, nonce: ByteArray, namespace: String): Cipher = Cipher.getInstance("AES/GCM/NoPadding")
        .also {
            it.init(mode, SecretKeySpec(secret, "AES"), GCMParameterSpec(128, nonce))
            it.updateAAD(("p2pkit-synthetic-lab-v1:" + namespace).toByteArray())
        }

    private fun writeLocked(namespace: String, value: ByteArray) {
        requireValue(value)
        val path = file(namespace)
        val nonce = ByteArray(12).also(random::nextBytes)
        val record = byteArrayOf(1) + nonce + cipher(Cipher.ENCRYPT_MODE, nonce, namespace).doFinal(value)
        directory.write(path, record, replace = true)
        ownedFiles[path] = directory.fileIdentity(path)
    }

    override fun read(namespace: String): ByteArray? {
        requireNamespace(namespace)
        return locked { readLocked(namespace) }
    }

    override fun putIfAbsent(namespace: String, value: ByteArray): ByteArray {
        requireNamespace(namespace)
        // Reject invalid input even when an existing winner would otherwise bypass the size check.
        requireValue(value)
        return locked {
            readLocked(namespace) ?: checkedCopy(value, secret).let { candidate ->
                try { writeLocked(namespace, candidate); candidate }
                catch (failure: Throwable) { candidate.fill(0); throw failure }
            }
        }
    }

    override fun delete(namespace: String): Boolean {
        requireNamespace(namespace)
        return locked {
            val path = file(namespace)
            directory.delete(path).also {
                ownedFiles.remove(path)
                if (it) directory.sync()
            }
        }
    }

    fun replace(namespace: String, value: ByteArray) {
        requireNamespace(namespace)
        requireValue(value)
        locked {
            val copy = checkedCopy(value, secret)
            try { writeLocked(namespace, copy) } finally { copy.fill(0) }
        }
    }

    fun close() = mutex.withLock {
        if (!closed) { closed = true; secret.fill(0) }
        // JVM/provider copies cannot be promised physically erased. Do not advertise secure memory wiping.
    }

    /** Call only after all users have closed. Remove exact fixture-owned inodes, never a directory tree. */
    fun destroy() = mutex.withLock {
        close()
        directory.verifyIdentity()
        // Refuse a replaced/symlinked/foreign file before removing any remaining fixture.
        ownedFiles.forEach { (path, expected) ->
            directory.read(path)
            check(directory.fileIdentity(path) == expected) { "Fixture file lifetime changed; retain for owner review" }
        }
        ownedFiles.keys.toList().forEach { path ->
            check(directory.delete(path, ownedFiles.getValue(path)))
            ownedFiles.remove(path)
        }
        directory.sync()
        // Unexpected files belong to neither cleanup nor an inferred wildcard. Preserve them.
        directory.deleteIfEmpty()
    }

    companion object {
        private val random = SecureRandom()
        private val locks = ConcurrentHashMap<Any, ReentrantLock>()
        private fun requireKey(key: ByteArray) { require(key.size == 32) }
        private fun requireValue(value: ByteArray) { require(value.size <= 262_100) }
        private fun requireNamespace(namespace: String) {
            require(namespace.isNotEmpty() && namespace.length <= 4096)
        }
        private fun admitDirectory(directory: Path, key: ByteArray): ProtectedProfileDirectory {
            requireKey(key) // Reject before Path inspection as well as before copying key bytes.
            return PosixProfileDirectory(directory)
        }

        /**
         * Inert test seam only; ordinary key/value copies always use ByteArray.copyOf. The supplied copier must
         * allocate fresh independent storage and must not mutate its input or alias any previously returned
         * array. Input/live-key aliases and changed length/content fail closed. No global hook is installed,
         * and no production instance's key, buffers or storage provider can be obtained through this factory.
         */
        internal fun forCopyValidation(
            directory: ProtectedProfileDirectory,
            key: ByteArray,
            copier: (ByteArray) -> ByteArray,
        ): LabVault = LabVault(directory, key, copier)

        fun randomKey(): ByteArray {
            val key = ByteArray(32)
            return try { random.nextBytes(key); key }
                catch (failure: Throwable) { key.fill(0); throw failure }
        }
    }
}

internal class LabTrustStore(private val vault: LabVault) : RpcTrustStore {
    private fun namespace(appId: AppId, purpose: RpcTrustPurpose): String {
        require(appId == RpcCapacityContract.appId) { "Synthetic AppId only" }
        return "rpc-trust:${appId.value}:${purpose.name}"
    }

    override suspend fun load(appId: AppId, purpose: RpcTrustPurpose): Set<PeerFingerprint> {
        val bytes = vault.read(namespace(appId, purpose)) ?: return emptySet()
        val entries = bytes.toString(Charsets.UTF_8).split('\n').filter { it.isNotEmpty() }
        require(entries.size <= 256 && entries.size == entries.toSet().size)
        return entries.map(PeerFingerprint::parse).toSet()
    }

    override suspend fun replace(appId: AppId, purpose: RpcTrustPurpose, fingerprints: Set<PeerFingerprint>) {
        require(fingerprints.size <= 256)
        vault.replace(namespace(appId, purpose), fingerprints.map { it.value }.sorted()
            .joinToString("\n").toByteArray(Charsets.UTF_8))
    }
}
