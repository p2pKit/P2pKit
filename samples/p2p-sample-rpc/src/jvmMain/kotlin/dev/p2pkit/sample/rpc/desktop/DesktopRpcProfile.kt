package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.lab.LabTrustStore
import dev.p2pkit.sample.rpc.lab.LabVault
import dev.p2pkit.sample.rpc.profile.PosixProfileFiles
import dev.p2pkit.sample.rpc.profile.ProfileCleanupObservation
import dev.p2pkit.sample.rpc.profile.ProtectedProfileLease
import dev.p2pkit.sample.rpc.profile.ProtectedProfileSession
import dev.p2pkit.sample.rpc.profile.WindowsProfileAvailability
import dev.p2pkit.sample.rpc.profile.WindowsProfileFiles
import dev.p2pkit.sample.rpc.profile.WindowsProfileInstalledProvider
import dev.p2pkit.sample.rpc.profile.WindowsProfileCustodyException
import dev.p2pkit.sample.rpc.profile.WindowsProfileCustodyFailure
import java.nio.file.Path
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
    private val files: ProtectedProfileSession,
    private val directoryKey: Any,
    private val lock: ProtectedProfileLease,
) {
    val trust = LabTrustStore(vault)
    private var closed = false
    private var closeFailure: Throwable? = null

    @Synchronized
    fun close() {
        if (closed) return
        closeFailure?.let { throw it }
        var failure: Throwable? = null
        fun attempt(action: () -> Unit) {
            try { action() } catch (caught: Throwable) {
                if (failure == null) failure = caught else if (failure !== caught) failure.addSuppressed(caught)
            }
        }
        attempt {
            check(files.root.verifyIdentity() == directoryKey) { "Profile directory changed; retain for owner review" }
        }
        attempt { vault.close() }
        attempt { lock.close() }
        attempt { files.close() }
        failure?.let { closeFailure = it; throw it }
        closed = true
    }

    companion object {
        private val magic = "P2PKIT-DESKTOP-PBKDF2-SHA256-V1\n".toByteArray(Charsets.US_ASCII)
        private val proof = "P2pKit RPC desktop profile v1".toByteArray(Charsets.US_ASCII)
        private const val PROOF_NAMESPACE = "desktop-profile-key-check-v1"
        private const val ITERATIONS = 600_000

        /** Caller transfers password ownership; every exit clears the array (provider copies are best effort). */
        fun open(directory: Path, password: CharArray): DesktopRpcProfile {
            try {
                require(password.size in 12..128) { "Use a profile passphrase of 12–128 characters" }
                WindowsProfileAvailability.requirePosixProductionHost()
                return open(PosixProfileFiles.open(directory), password)
            } finally { password.fill('\u0000') }
        }

        /**
         * Application entry: own the password before platform/default-path resolution. Windows must never
         * evaluate a POSIX home path; its fixed native root remains unavailable until trusted loading exists.
         * Pre-acquisition refusal is not uncertain provider cleanup and must not poison a later valid attempt.
         */
        internal fun openApplicationAttempt(password: CharArray): DesktopRpcProfileOpenAttempt {
            var acquisitionStarted = false
            try {
                require(password.size in 12..128) { "Use a profile passphrase of 12–128 characters" }
                if (System.getProperty("os.name").startsWith("Windows", ignoreCase = true)) {
                    acquisitionStarted = true
                    return openAttempt(password) { WindowsProfileFiles.openInstalled() }
                }
                val directory = Path.of(System.getProperty("user.home"), ".p2pkit-rpc-desktop")
                acquisitionStarted = true
                return openAttempt(directory, password)
            } catch (failure: Throwable) {
                return DesktopRpcProfileOpenAttempt(
                    Result.failure(failure), if (acquisitionStarted) failure else null,
                )
            } finally { password.fill('\u0000') }
        }

        /** Failed cleanup is explicit even when a provider rethrows the very same cached exception. */
        internal fun openAttempt(directory: Path, password: CharArray): DesktopRpcProfileOpenAttempt {
            try {
                require(password.size in 12..128) { "Use a profile passphrase of 12–128 characters" }
                WindowsProfileAvailability.requirePosixProductionHost()
                val cleanup = ProfileCleanupObservation()
                return openAttempt(password, cleanup) {
                    PosixProfileFiles.open(directory, cleanup)
                }
            } catch (failure: Throwable) {
                return DesktopRpcProfileOpenAttempt(Result.failure(failure), null)
            } finally { password.fill('\u0000') }
        }

        /**
         * Own password cleanup before acquiring a provider, including failed acquisition with unpublished
         * native resources. The factory must transfer an admitted session or report its retained owner;
         * this boundary neither authorizes loading nor retries failed native retirement.
         */
        internal fun openAttempt(
            password: CharArray,
            acquire: () -> ProtectedProfileSession,
        ): DesktopRpcProfileOpenAttempt = openAttempt(password, ProfileCleanupObservation(), acquire)

        private fun openAttempt(
            password: CharArray,
            cleanup: ProfileCleanupObservation,
            acquire: () -> ProtectedProfileSession,
        ): DesktopRpcProfileOpenAttempt {
            var acquired: ProtectedProfileSession? = null
            try {
                require(password.size in 12..128) { "Use a profile passphrase of 12–128 characters" }
                val files = try { acquire() } catch (failure: WindowsProfileInstalledProvider.Unavailable) {
                    return DesktopRpcProfileOpenAttempt(Result.failure(failure), null)
                } catch (failure: WindowsProfileFiles.AcquisitionFailure) {
                    return DesktopRpcProfileOpenAttempt(
                        Result.failure(failure), failure.cleanupFailure, failure.retainedSession,
                    )
                } catch (failure: Throwable) {
                    // Preserve the existing POSIX acquisition conservatism without inventing a session.
                    return DesktopRpcProfileOpenAttempt(Result.failure(failure), failure)
                }
                acquired = files
                return openAttempt(files, password, cleanup)
            } catch (failure: Throwable) {
                return DesktopRpcProfileOpenAttempt(
                    Result.failure(failure), if (acquired != null) failure else null, acquired,
                )
            } finally { password.fill('\u0000') }
        }

        internal fun openAttempt(files: ProtectedProfileSession, password: CharArray): DesktopRpcProfileOpenAttempt =
            openAttempt(files, password, ProfileCleanupObservation())

        private fun openAttempt(
            files: ProtectedProfileSession,
            password: CharArray,
            cleanup: ProfileCleanupObservation,
        ): DesktopRpcProfileOpenAttempt {
            val result = runCatching { open(files, password, cleanup) }
            // A provider can report failed cleanup before returning a lease. Preserve that existing uncertainty too.
            val failure = result.exceptionOrNull()
            val nativeUnknown = (failure as? WindowsProfileCustodyException)?.takeIf {
                it.failure in setOf(WindowsProfileCustodyFailure.CleanupUnknown, WindowsProfileCustodyFailure.Unknown)
            }
            val observed = cleanup.failure ?: failure?.suppressed?.firstOrNull() ?: nativeUnknown
            // The caller transferred this owner before admission. Retain it even if cleanup might have
            // physically succeeded: an error is not authority to discard its native ledger or retry retirement.
            val retained = files.takeIf { result.isFailure && observed != null }
            return DesktopRpcProfileOpenAttempt(result, observed, retained)
        }

        /** An admitted provider is transferred to this profile; tests supply inert native models, never a fallback. */
        internal fun open(files: ProtectedProfileSession, password: CharArray): DesktopRpcProfile =
            open(files, password, null)

        private fun open(
            files: ProtectedProfileSession,
            password: CharArray,
            cleanupObservation: ProfileCleanupObservation?,
        ): DesktopRpcProfile {
            var lock: ProtectedProfileLease? = null
            var vault: LabVault? = null
            try {
                require(password.size in 12..128) { "Use a profile passphrase of 12–128 characters" }
                val directory = files.root
                val directoryKey = directory.verifyIdentity()
                val lockPath = "profile.lock"
                if (directory.exists(lockPath)) directory.read(lockPath, 0)
                lock = directory.lock(lockPath, nonBlocking = true)
                check(directory.verifyIdentity() == directoryKey)
                if (files is WindowsProfileFiles) files.requireSettledProfileInventory()
                val headerPath = "profile.header"
                val fresh = !directory.exists(headerPath)
                // Missing metadata must never silently replace an existing encrypted identity.
                if (fresh) check(directory.names().all { it == lockPath }) {
                    "Incomplete profile: preserve its files; no identity reset was attempted"
                }
                val header = if (fresh) magic + ByteArray(16).also(SecureRandom()::nextBytes)
                    else directory.read(headerPath, magic.size + 16)
                require(header.size == magic.size + 16 && header.take(magic.size).toByteArray().contentEquals(magic))
                val specification = PBEKeySpec(password, header.copyOfRange(magic.size, header.size), ITERATIONS, 256)
                val key = try {
                    SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(specification).encoded
                }
                    finally { specification.clearPassword() }
                try {
                    if (fresh) {
                        directory.write(headerPath, header)
                        directory.child("identity", create = true)
                    }
                    vault = LabVault(
                        directory.child("identity"), key, nonBlockingLeases = files is WindowsProfileFiles,
                    )
                    if (fresh) vault.putIfAbsent(PROOF_NAMESPACE, proof)
                    check(MessageDigest.isEqual(checkNotNull(vault.read(PROOF_NAMESPACE)), proof)) {
                        "Profile key check failed"
                    }
                } finally { key.fill(0) }
                return DesktopRpcProfile(vault, files, directoryKey, lock)
            } catch (failure: Throwable) {
                try { vault?.close() } catch (cleanup: Throwable) {
                    cleanupObservation?.record(cleanup)
                    if (cleanup !== failure) failure.addSuppressed(cleanup)
                }
                try { lock?.close() } catch (cleanup: Throwable) {
                    cleanupObservation?.record(cleanup)
                    if (cleanup !== failure) failure.addSuppressed(cleanup)
                }
                try { files.close() } catch (cleanup: Throwable) {
                    cleanupObservation?.record(cleanup)
                    if (cleanup !== failure) failure.addSuppressed(cleanup)
                }
                // Wrong passwords/corruption do not delete, recreate or overwrite any profile record.
                throw failure
            } finally { password.fill('\u0000') }
        }
    }
}

/**
 * Original result and explicit cleanup observation, not inferred from null profile or exception suppression.
 * A failed transferred session stays owned by the attempt. This reference is not permission to retry close,
 * nor proof that every unpublished provider resource has a managed session owner.
 */
internal class DesktopRpcProfileOpenAttempt(
    val result: Result<DesktopRpcProfile>,
    val cleanupFailure: Throwable?,
    val retainedSession: ProtectedProfileSession? = null,
)
