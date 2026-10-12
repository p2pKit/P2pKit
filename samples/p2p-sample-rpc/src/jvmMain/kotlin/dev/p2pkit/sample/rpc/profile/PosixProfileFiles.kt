package dev.p2pkit.sample.rpc.profile

import dev.p2pkit.sample.rpc.lab.LabFiles
import java.nio.file.Files
import java.nio.file.LinkOption.NOFOLLOW_LINKS
import java.nio.file.Path
import java.nio.file.attribute.BasicFileAttributes
import java.nio.file.attribute.PosixFilePermissions

/** Existing POSIX operations, modes, locking, publication and directory sync remain the implementation. */
internal class PosixProfileDirectory(
    private val path: Path,
    private val cleanupObservation: ProfileCleanupObservation? = null,
) : ProtectedProfileDirectory {
    override val mutexIdentity: Any = LabFiles.privateDirectory(path).toString()
    private fun file(name: String): Path = path.resolve(profileComponent(name))
    override fun verifyIdentity(): Any {
        LabFiles.privateDirectory(path)
        return checkNotNull(Files.readAttributes(path, BasicFileAttributes::class.java, NOFOLLOW_LINKS).fileKey())
    }
    override fun fileIdentity(name: String): Any = checkNotNull(
        Files.readAttributes(file(name), BasicFileAttributes::class.java, NOFOLLOW_LINKS).fileKey(),
    )
    override fun exists(name: String): Boolean = Files.exists(file(name), NOFOLLOW_LINKS)
    override fun names(): Set<String> = Files.list(path).use { entries ->
        entries.map { it.fileName.toString() }.toList().toSet()
    }
    override fun child(name: String, create: Boolean): ProtectedProfileDirectory = PosixProfileDirectory(
        if (create) LabFiles.newDirectory(path, profileComponent(name)) else file(name),
        cleanupObservation,
    )
    override fun read(name: String, maximum: Int): ByteArray = LabFiles.read(file(name), maximum)
    override fun write(name: String, bytes: ByteArray, replace: Boolean) = LabFiles.write(file(name), bytes, replace)
    override fun lock(name: String, nonBlocking: Boolean): ProtectedProfileLease {
        val channel = LabFiles.lockChannel(file(name))
        val lock = try {
            if (nonBlocking) checkNotNull(channel.tryLock()) { "Profile is already in use" } else channel.lock()
        } catch (failure: Throwable) {
            closeAfterProfileFailure(failure) { channel.close() }?.let { cleanupObservation?.record(it) }
            throw failure
        }
        return ProfileLeaseCloseOwner(lock::release, channel::close, cleanupObservation)
    }
    override fun delete(name: String, expectedIdentity: Any?): Boolean {
        if (expectedIdentity != null) check(fileIdentity(name) == expectedIdentity) {
            "Fixture file lifetime changed; retain for owner review"
        }
        // Preserve the POSIX pathname-delete contract; this extra readback is not an atomic native custody claim.
        return Files.deleteIfExists(file(name))
    }
    override fun sync() = LabFiles.syncDirectory(path)
    override fun deleteIfEmpty() {
        if (Files.list(path).use { it.findAny().isEmpty }) Files.delete(path)
    }
}

/** Two independently owned close boundaries; never mask the primary failure or repeat an uncertain release. */
internal class ProfileLeaseCloseOwner(
    private val releaseLock: () -> Unit,
    private val closeChannel: () -> Unit,
    private val cleanupObservation: ProfileCleanupObservation? = null,
) : ProtectedProfileLease {
    private var closed = false
    private var failure: Throwable? = null

    @Synchronized
    override fun close() {
        if (closed) return
        failure?.let { throw it }
        var primary: Throwable? = null
        try { releaseLock() } catch (caught: Throwable) { primary = caught; cleanupObservation?.record(caught) }
        if (primary == null) {
            try { closeChannel() } catch (caught: Throwable) { primary = caught; cleanupObservation?.record(caught) }
        } else closeAfterProfileFailure(primary, closeChannel)?.let { cleanupObservation?.record(it) }
        primary?.let { failure = it; throw it }
        closed = true
    }
}

internal fun closeAfterProfileFailure(primary: Throwable, close: () -> Unit): Throwable? {
    try { close() } catch (cleanup: Throwable) {
        if (cleanup !== primary) primary.addSuppressed(cleanup)
        return cleanup
    }
    return null
}

/** Local to one profile-open attempt; explicit same-exception cleanup evidence without mutating the exception. */
internal class ProfileCleanupObservation {
    private var first: Throwable? = null
    val failure: Throwable? get() = synchronized(this) { first }
    fun record(failure: Throwable) = synchronized(this) { if (first == null) first = failure }
}

internal object PosixProfileFiles {
    fun open(directory: Path, cleanupObservation: ProfileCleanupObservation? = null): ProtectedProfileSession {
        require(directory.isAbsolute && directory.normalize() == directory)
        if (!Files.exists(directory, NOFOLLOW_LINKS)) {
            Files.createDirectory(directory,
                PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rwx------")))
        }
        val root = PosixProfileDirectory(directory, cleanupObservation)
        return object : ProtectedProfileSession {
            override val root = root
            override fun close() = Unit // POSIX directory operations do not retain directory handles.
        }
    }
}
