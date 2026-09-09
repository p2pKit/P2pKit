package dev.p2pkit.sample.android

import dev.p2pkit.core.permission.P2pPermission

/** Observed LAN access only: no queued room, peer, feature, or provisioning action. */
internal data class SampleLanPermissionState(
    val missing: List<P2pPermission> = emptyList(),
    val checkFailed: Boolean = false,
    val requestInFlight: Boolean = false,
    val message: String? = null
) {
    val canRequest: Boolean
        get() = P2pPermission.LocalNetwork in missing && !requestInFlight
}
