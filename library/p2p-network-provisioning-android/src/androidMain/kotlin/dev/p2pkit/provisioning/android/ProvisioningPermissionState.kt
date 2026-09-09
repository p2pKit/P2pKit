package dev.p2pkit.provisioning.android

/** Post-failure observations, not a preflight authorization guarantee. */
internal data class ProvisioningPermissionState(
    val runtimePermissionGranted: Boolean? = null,
    val locationEnabled: Boolean? = null
)

/** A bounded identity walk also terminates for a platform/OEM cause cycle. */
internal fun hasProvisioningSecurityCause(failure: Throwable): Boolean {
    val seen = ArrayList<Throwable>(8)
    var current: Throwable? = failure
    repeat(32) {
        val cause = current ?: return false
        if (cause is SecurityException) return true
        if (seen.any { it === cause }) return false
        seen += cause
        current = cause.cause
    }
    return false
}
