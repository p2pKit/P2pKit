package dev.p2pkit.provisioning.android

import dev.p2pkit.core.permission.P2pPermission
import dev.p2pkit.core.provisioning.NetworkState
import dev.p2pkit.core.provisioning.WifiCredentials
import dev.p2pkit.core.provisioning.WifiSecurityType

/** Normal manifest permissions consumed by the provisioning sidecar itself. */
internal val provisioningNormalManifestPermissions: List<String> = listOf(
    "android.permission.ACCESS_WIFI_STATE",
    "android.permission.CHANGE_WIFI_STATE",
    "android.permission.CHANGE_NETWORK_STATE"
)

/** Target-aware Android runtime permission policy shared by both entry points. */
internal fun requiredProvisioningRuntimePermission(
    deviceSdk: Int,
    targetSdk: Int
): P2pPermission =
    if (deviceSdk >= 33 && targetSdk >= 33) {
        P2pPermission.NearbyWifiDevices
    } else {
        P2pPermission.Location
    }

/**
 * Validates values before they reach `WifiNetworkSpecifier.Builder`, whose
 * platform exceptions otherwise surface as an opaque PlatformError.
 */
internal fun validateWifiCredentials(credentials: WifiCredentials): String? {
    val ssid = credentials.ssid?.takeIf { it.isNotBlank() }
        ?: return "SSID must not be blank"
    if (ssid.toByteArray(Charsets.UTF_8).size > 32) {
        return "SSID must be at most 32 UTF-8 bytes"
    }
    val password = credentials.password?.reveal()
    if (credentials.securityType == WifiSecurityType.OPEN && password != null) {
        return "OPEN Wi-Fi must not include a password"
    }
    if (credentials.securityType == WifiSecurityType.WPA2 ||
        credentials.securityType == WifiSecurityType.WPA3
    ) {
        if (password.isNullOrEmpty()) {
            return "${credentials.securityType} Wi-Fi requires a password"
        }
    }
    if (password != null) {
        if (password.any { it.code > 0x7f }) {
            return "Wi-Fi password must contain only ASCII characters"
        }
        if (password.length !in 8..63) {
            return "Wi-Fi password must be 8..63 characters"
        }
    }
    return null
}

/** Builds a joined snapshot strictly from addresses of the joined Network. */
internal fun networkStateFromJoinedAddresses(addresses: List<String>): NetworkState =
    NetworkState.ConnectedToWifi(ssid = null, localIpAddresses = addresses.distinct())
