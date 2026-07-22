package dev.p2pkit.core

import dev.p2pkit.core.permission.P2pPermission

/**
 * Provisioning-specific failures. Subtype of [P2pError] so callers can match
 * either generally (catch [P2pError]) or specifically (catch
 * [NetworkProvisioningError] or a particular variant).
 *
 * Declared in the same package as [P2pError] because Kotlin requires sealed
 * subclasses to share the parent's package in this compiler version.
 *
 * **Note on the `PlatformError` variant:** the spec named the wrapped throwable
 * `cause`, but that clashes with [Throwable.cause]. The field is named
 * `platformException` here and is also threaded into [Throwable.cause] for
 * stack-trace purposes.
 */
public sealed class NetworkProvisioningError(message: String?, cause: Throwable?) : P2pError(message, cause) {

    public data class PlatformError(val platformException: Throwable) : NetworkProvisioningError(
        "Platform error: ${platformException.message}",
        platformException
    )

    public data class PermissionMissingForProvisioning(val permissions: List<P2pPermission>) :
        NetworkProvisioningError("Missing permissions: $permissions", null)

    public data class HotspotStopped(val reason: String) : NetworkProvisioningError(reason, null)

    public data class JoinFailed(val reason: String) : NetworkProvisioningError(reason, null)

    /** The manager has begun terminal disposal and cannot accept new work. */
    public class ManagerClosed : NetworkProvisioningError("network provisioning manager is closed", null)

    /** One or more resources could not be released during terminal disposal. */
    public data class CleanupFailed(
        val reason: String,
        val cleanupCause: Throwable? = null
    ) : NetworkProvisioningError(reason, cleanupCause)
}
