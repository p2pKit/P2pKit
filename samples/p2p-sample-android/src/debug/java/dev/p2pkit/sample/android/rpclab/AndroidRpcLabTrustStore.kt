package dev.p2pkit.sample.android.rpclab

import android.content.Context
import android.os.Process
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.system.ErrnoException
import android.system.Os
import android.system.OsConstants
import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcTrustPurpose
import dev.p2pkit.rpc.RpcTrustStore
import dev.p2pkit.sample.rpc.RpcCapacityContract
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.security.KeyStore
import java.util.UUID
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Debug phone app only. Non-exportable Keystore key; atomic, fsynced no-backup trust, never cloud preferences. */
internal class AndroidRpcLabTrustStore(context: Context, fixtureId: String? = null) : RpcTrustStore {
    // Only instrumentation supplies a fresh synthetic namespace; the actual UI always uses the stable default.
    private val suffix = fixtureId?.also { require(it.matches(Regex("[a-f0-9]{32}"))) }?.let { "-$it" }.orEmpty()
    private val alias = "dev.p2pkit.rpc.phone-lab.trust.v1$suffix"
    private val root = File(context.applicationContext.noBackupFilesDir.canonicalFile, "rpc-phone-lab-trust$suffix")

    init {
        synchronized(mutex) {
            if (!root.exists()) check(root.mkdir())
            val info = Os.lstat(root.path)
            check(OsConstants.S_ISDIR(info.st_mode) && info.st_uid == Process.myUid())
            Os.chmod(root.path, 0b111000000)
        }
    }

    private fun <T> locked(block: () -> T): T = synchronized(mutex) {
        val fd = Os.open(File(root, "trust.lock").path,
            OsConstants.O_RDWR or OsConstants.O_CREAT or OsConstants.O_NOFOLLOW, 0b110000000)
        FileOutputStream(fd).use { stream -> stream.channel.lock().use { block() } }
    }

    private fun namespace(appId: AppId, purpose: RpcTrustPurpose): String {
        require(appId == RpcCapacityContract.appId)
        return "${appId.value}:${purpose.name}"
    }

    private fun target(purpose: RpcTrustPurpose): File = File(root, "${purpose.name}.aesgcm")

    private fun read(file: File): ByteArray? {
        val metadata = try { Os.lstat(file.path) } catch (missing: ErrnoException) {
            if (missing.errno == OsConstants.ENOENT) return null
            throw missing
        }
        check(OsConstants.S_ISREG(metadata.st_mode) && metadata.st_uid == Process.myUid())
        val fd = Os.open(file.path, OsConstants.O_RDONLY or OsConstants.O_NOFOLLOW, 0)
        return FileInputStream(fd).use { stream ->
            val info = Os.fstat(fd)
            check(OsConstants.S_ISREG(info.st_mode) && info.st_uid == Process.myUid() && info.st_size <= 16_384)
            val buffer = ByteArray(16_385)
            var size = 0
            while (size < buffer.size) {
                val count = stream.read(buffer, size, buffer.size - size)
                if (count < 0) break
                size += count
            }
            check(size <= 16_384)
            buffer.copyOf(size)
        }
    }

    private fun key(allowCreation: Boolean): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        if (store.containsAlias(alias)) return checkNotNull(store.getKey(alias, null) as? SecretKey)
        check(allowCreation && RpcTrustPurpose.entries.all { read(target(it)) == null }) {
            "Trust key unavailable; never silently recreate existing trust"
        }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").run {
            init(KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setKeySize(256).setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
            generateKey()
        }
    }

    private fun decrypt(bytes: ByteArray, namespace: String): ByteArray {
        check(bytes.size in 29..16_384 && bytes[0] == 1.toByte())
        return Cipher.getInstance("AES/GCM/NoPadding").run {
            init(Cipher.DECRYPT_MODE, key(false), GCMParameterSpec(128, bytes.copyOfRange(1, 13)))
            updateAAD(namespace.toByteArray(Charsets.UTF_8))
            doFinal(bytes, 13, bytes.size - 13)
        }
    }

    override suspend fun load(appId: AppId, purpose: RpcTrustPurpose): Set<PeerFingerprint> = locked {
        val name = namespace(appId, purpose)
        val bytes = read(target(purpose)) ?: return@locked emptySet()
        val text = decrypt(bytes, name).toString(Charsets.US_ASCII)
        val values = text.split('\n').filter(String::isNotEmpty)
        require(values.size <= 128 && values.toSet().size == values.size)
        values.map(PeerFingerprint::parse).toSet()
    }

    override suspend fun replace(appId: AppId, purpose: RpcTrustPurpose, fingerprints: Set<PeerFingerprint>) {
        locked {
            val name = namespace(appId, purpose)
            require(fingerprints.size <= 128)
            val file = target(purpose)
            // A missing wrapping key must never erase an older authenticated approval set.
            val existing = read(file)
            if (existing != null) decrypt(existing, name)
            val clear = fingerprints.map { it.value }.sorted().joinToString("\n").toByteArray(Charsets.US_ASCII)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply {
                init(Cipher.ENCRYPT_MODE, key(existing == null))
                updateAAD(name.toByteArray(Charsets.UTF_8))
            }
            check(cipher.iv.size == 12)
            val bytes = byteArrayOf(1) + cipher.iv + cipher.doFinal(clear)
            val temporary = File(root, ".trust-${UUID.randomUUID()}")
            try {
                val fd = Os.open(temporary.path, OsConstants.O_WRONLY or OsConstants.O_CREAT or
                    OsConstants.O_EXCL or OsConstants.O_NOFOLLOW, 0b110000000)
                FileOutputStream(fd).use { stream -> stream.write(bytes); stream.fd.sync() }
                Os.rename(temporary.path, file.path)
                val directory = Os.open(root.path, OsConstants.O_RDONLY or OsConstants.O_DIRECTORY, 0)
                try { Os.fsync(directory) } finally { Os.close(directory) }
                check(decrypt(checkNotNull(read(file)), name).contentEquals(clear))
            } finally {
                if (temporary.exists()) check(temporary.delete())
                clear.fill(0)
            }
        }
    }

    private companion object {
        val mutex = Any()
    }
}
