package dev.p2pkit.sample.rpc.lab

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.security.JvmSecureIdentityStore
import dev.p2pkit.rpc.RpcTrustPurpose
import dev.p2pkit.rpc.RpcTrustStore
import dev.p2pkit.sample.rpc.RpcCapacityContract
import java.nio.file.Files
import java.nio.file.LinkOption
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
 */
internal class LabVault(private val directory: Path, key: ByteArray = randomKey()) : JvmSecureIdentityStore {
    private val secret = key.copyOf().also { require(it.size == 32) }
    private val mutex = locks.computeIfAbsent(LabFiles.privateDirectory(directory).toString()) { ReentrantLock() }
    private var closed = false

    private fun <T> locked(block: () -> T): T = mutex.withLock {
        check(!closed)
        LabFiles.privateDirectory(directory)
        LabFiles.lockChannel(directory.resolve("vault.lock")).use { channel -> channel.lock().use { block() } }
    }

    private fun file(namespace: String): Path {
        require(namespace.isNotEmpty() && namespace.length <= 4096)
        return directory.resolve(LabFiles.sha256(namespace.toByteArray()) + ".aesgcm")
    }

    private fun readLocked(namespace: String): ByteArray? {
        val path = file(namespace)
        if (!Files.exists(path, LinkOption.NOFOLLOW_LINKS)) return null
        val record = LabFiles.read(path)
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
        LabFiles.write(file(namespace), record, replace = true)
    }

    override fun read(namespace: String): ByteArray? = locked { readLocked(namespace) }

    override fun putIfAbsent(namespace: String, value: ByteArray): ByteArray = locked {
        readLocked(namespace) ?: value.copyOf().also { writeLocked(namespace, it) }
    }

    override fun delete(namespace: String): Boolean = locked {
        Files.deleteIfExists(file(namespace)).also { if (it) LabFiles.syncDirectory(directory) }
    }

    fun replace(namespace: String, value: ByteArray) { locked { writeLocked(namespace, value.copyOf()) } }

    fun close() = mutex.withLock {
        if (!closed) { closed = true; secret.fill(0) }
        // JVM/provider copies cannot be promised physically erased. Do not advertise secure memory wiping.
    }

    companion object {
        private val random = SecureRandom()
        private val locks = ConcurrentHashMap<String, ReentrantLock>()
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
