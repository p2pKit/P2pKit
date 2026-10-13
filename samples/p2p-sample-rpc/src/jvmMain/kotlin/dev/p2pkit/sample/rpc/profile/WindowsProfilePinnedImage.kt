package dev.p2pkit.sample.rpc.profile

import com.sun.nio.file.ExtendedOpenOption.NOSHARE_DELETE
import com.sun.nio.file.ExtendedOpenOption.NOSHARE_WRITE
import java.io.IOException
import java.nio.ByteBuffer
import java.nio.channels.FileChannel
import java.nio.file.FileSystems
import java.nio.file.LinkOption.NOFOLLOW_LINKS
import java.nio.file.Path
import java.nio.file.StandardOpenOption.READ

/**
 * A retained, read-only final-file share pin, not a DLL loader or executable-path authority.
 * Windows opens deny ordinary concurrent write/delete opens; reads use that original channel.
 * No ancestor/ACL/reparse metadata, Authenticode, preexisting writable mapping or load identity is proven.
 * The existing installed-ancestor/launcher authority must still be supplied before any future native load.
 * Blocking I/O retains this owner until actual return; coroutine interruption is not native cancellation.
 */
internal class WindowsProfilePinnedImage private constructor(
    private val manifest: ByteArray,
    private val authority: WindowsProfileByteManifest.Authority,
    val scope: Scope,
) : AutoCloseable {
    enum class Scope { WINDOWS_FINAL_FILE_BYTES_AND_SHARING_ONLY, INERT_VALIDATION_ONLY }

    /** Only an actual FileChannel.open I/O failure, not a later read/verification/cleanup failure. */
    class OpenFailure internal constructor(cause: IOException) :
        IOException("Windows profile image channel could not be acquired", cause)

    /** Retains the original sealed owner after failed initialization AND uncertain actual cleanup. */
    class AcquisitionFailure internal constructor(
        val retainedPin: WindowsProfilePinnedImage,
    ) : IOException("Windows profile image admission failed with retained cleanup ownership") {
        lateinit var cleanupFailure: Throwable
            private set

        internal fun attach(cause: Throwable, cleanup: Throwable): AcquisitionFailure {
            initCause(cause)
            cleanupFailure = cleanup
            return this
        }
    }

    /** Inert-test seam only. Production construction always owns a real Windows FileChannel. */
    internal interface Owner {
        fun size(): Long
        fun read(destination: ByteBuffer, position: Long): Int
        fun close()
    }

    private lateinit var owner: Owner

    private var closeAttempted = false
    private var closeFailure: Throwable? = null
    private var verificationFailure: Throwable? = null
    private lateinit var observation: WindowsProfileByteManifest.ByteAuthorization

    /** Re-read the held channel, not its pathname. Failure seals reads but preserves original cleanup ownership. */
    @Synchronized
    fun verify(): WindowsProfileByteManifest.ByteAuthorization {
        check(!closeAttempted) { "Windows profile image pin is retired" }
        verificationFailure?.let { throw it }
        try {
            return readAuthorization().also {
                check(it == observation) { "Windows profile image changed while pinned" }
            }
        } catch (failure: Throwable) {
            verificationFailure = failure
            throw failure
        }
    }

    private fun readAuthorization(): WindowsProfileByteManifest.ByteAuthorization {
        val length = owner.size()
        require(length in 512L..WindowsProfilePeImage.MAXIMUM_BYTES.toLong()) {
            "Windows profile image exceeds its bounded format"
        }
        val bytes = ByteArray(length.toInt())
        try {
            var position = 0
            while (position < bytes.size) {
                val target = ByteBuffer.wrap(bytes, position, minOf(READ_BLOCK_BYTES, bytes.size - position))
                val count = owner.read(target, position.toLong())
                check(count > 0 && count == target.position() - position) {
                    "Windows profile image read made no valid progress"
                }
                position += count
            }
            val end = ByteBuffer.allocate(1)
            check(owner.read(end, length) == -1 && end.position() == 0 && owner.size() == length) {
                "Windows profile image size changed during read"
            }
            return WindowsProfileByteManifest.authorize(manifest, bytes, authority)
        } finally {
            bytes.fill(0)
        }
    }

    /** Exactly one physical close attempt. A thrown close remains uncertain and is never retried. */
    @Synchronized
    override fun close() {
        if (closeAttempted) {
            closeFailure?.let { throw it }
            return
        }
        closeAttempted = true
        try {
            owner.close()
        } catch (failure: Throwable) {
            closeFailure = failure
            throw failure
        } finally {
            manifest.fill(0)
        }
    }

    companion object {
        const val FILE_NAME = "p2pkit-windows-profile.dll"
        private const val READ_BLOCK_BYTES = 65_536

        /**
         * Ordinary file opening only: no native execution, profile access, extraction, signature or ancestor claim.
         * The external Authority must not be derived from an adjacent candidate manifest.
         */
        fun open(
            path: Path,
            manifest: ByteArray,
            authority: WindowsProfileByteManifest.Authority,
        ): WindowsProfilePinnedImage {
            check(System.getProperty("os.name").startsWith("Windows", ignoreCase = true)) {
                "Windows profile image share pin requires Windows"
            }
            require(path.fileSystem === FileSystems.getDefault() && path.isAbsolute && path.normalize() == path &&
                path.fileName?.toString() == FILE_NAME && path.root.toString().matches(Regex("[A-Za-z]:\\\\"))) {
                "Windows profile image requires a normalized local-drive path and exact filename"
            }
            return acquire(manifest, authority, Scope.WINDOWS_FINAL_FILE_BYTES_AND_SHARING_ONLY) {
                // Allocate the retaining wrapper before acquiring the actual channel.
                val retained = object : Owner {
                    lateinit var channel: FileChannel
                    fun open() {
                        channel = try {
                            FileChannel.open(path, READ, NOFOLLOW_LINKS, NOSHARE_WRITE, NOSHARE_DELETE)
                        } catch (failure: IOException) { throw OpenFailure(failure) }
                    }
                    override fun size(): Long = channel.size()
                    override fun read(destination: ByteBuffer, position: Long): Int =
                        channel.read(destination, position)
                    override fun close() = channel.close()
                }
                retained.open()
                retained
            }
        }

        /** Does not claim Windows sharing or accept a filesystem pathname; for deterministic inert controls only. */
        internal fun openForValidation(
            manifest: ByteArray,
            authority: WindowsProfileByteManifest.Authority,
            acquireOwner: () -> Owner,
        ): WindowsProfilePinnedImage = acquire(manifest, authority, Scope.INERT_VALIDATION_ONLY, acquireOwner)

        private fun acquire(
            manifest: ByteArray,
            authority: WindowsProfileByteManifest.Authority,
            scope: Scope,
            acquireOwner: () -> Owner,
        ): WindowsProfilePinnedImage {
            require(manifest.size in 1..WindowsProfileByteManifest.MAXIMUM_MANIFEST_BYTES) {
                "Windows profile image manifest exceeds its bound"
            }
            val snapshot = manifest.copyOf()
            // Reserve the outer owner before any channel acquisition; no post-open wrapper allocation can lose it.
            val pin = WindowsProfilePinnedImage(snapshot, authority, scope)
            // Reserve its failure carrier before acquiring a channel, not while reporting an I/O/VM Error.
            // This avoids that post-acquisition allocation; it does not promise recovery from heap exhaustion.
            val retained = AcquisitionFailure(pin)
            try { pin.owner = acquireOwner() } catch (failure: Throwable) {
                snapshot.fill(0)
                throw failure
            }
            try {
                pin.observation = pin.readAuthorization()
                pin.verify() // Independent held-channel readback before publishing this byte-only owner.
                return pin
            } catch (failure: Throwable) {
                try { pin.close() } catch (cleanup: Throwable) {
                    retained.attach(failure, cleanup)
                    if (cleanup !== failure && failure !is Error && cleanup !is Error)
                        retained.addSuppressed(cleanup)
                    throw retained
                }
                throw failure
            }
        }
    }
}
