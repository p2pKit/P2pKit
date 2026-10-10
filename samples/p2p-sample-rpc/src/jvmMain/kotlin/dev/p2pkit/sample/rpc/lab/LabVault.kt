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
internal class LabVault(private val directory: ProtectedProfileDirectory, key: ByteArray) : JvmSecureIdentityStore {
    constructor(directory: Path, key: ByteArray = randomKey()) : this(PosixProfileDirectory(directory), key)
    private val secret = key.copyOf().also { require(it.size == 32) }
    private val mutex = locks.computeIfAbsent(directory.mutexIdentity) { ReentrantLock() }
    private var closed = false
    private val ownedFiles = linkedMapOf<String, Any>()

    private fun <T> locked(block: () -> T): T = mutex.withLock {
        check(!closed)
        directory.verifyIdentity()
        val lockFile = "vault.lock"
        val createLock = !directory.exists(lockFile)
        directory.lock(lockFile).use {
            if (createLock) ownedFiles[lockFile] = directory.fileIdentity(lockFile)
            block()
        }
    }

    private fun file(namespace: String): String {
        require(namespace.isNotEmpty() && namespace.length <= 4096)
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
        require(value.size <= 262_100)
        val nonce = ByteArray(12).also(random::nextBytes)
        val record = byteArrayOf(1) + nonce + cipher(Cipher.ENCRYPT_MODE, nonce, namespace).doFinal(value)
        val path = file(namespace)
        directory.write(path, record, replace = true)
        ownedFiles[path] = directory.fileIdentity(path)
    }

    override fun read(namespace: String): ByteArray? = locked { readLocked(namespace) }

    override fun putIfAbsent(namespace: String, value: ByteArray): ByteArray = locked {
        readLocked(namespace) ?: value.copyOf().also { writeLocked(namespace, it) }
    }

    override fun delete(namespace: String): Boolean = locked {
        val path = file(namespace)
        directory.delete(path).also {
            ownedFiles.remove(path)
            if (it) directory.sync()
        }
    }

    fun replace(namespace: String, value: ByteArray) { locked { writeLocked(namespace, value.copyOf()) } }

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
        fun randomKey(): ByteArray = ByteArray(32).also(random::nextBytes)
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
        require(entries.size <= 128 && entries.size == entries.toSet().size)
        return entries.map(PeerFingerprint::parse).toSet()
    }

    override suspend fun replace(appId: AppId, purpose: RpcTrustPurpose, fingerprints: Set<PeerFingerprint>) {
        require(fingerprints.size <= 128)
        vault.replace(namespace(appId, purpose), fingerprints.map { it.value }.sorted()
            .joinToString("\n").toByteArray(Charsets.UTF_8))
    }
}
