package dev.p2pkit.provisioning.android

import dev.p2pkit.core.provisioning.NetworkState
import dev.p2pkit.core.provisioning.WifiCredentials
import dev.p2pkit.core.provisioning.WifiSecurityType

/** Normal manifest permissions consumed by the provisioning sidecar itself. */
internal val provisioningNormalManifestPermissions: List<String> = listOf(
    "android.permission.ACCESS_WIFI_STATE",
    "android.permission.CHANGE_WIFI_STATE",
    "android.permission.CHANGE_NETWORK_STATE"
)

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
    if (credentials.securityType == WifiSecurityType.OPEN &&
        !password.isNullOrEmpty()
    ) {
        return "OPEN Wi-Fi must not include a password"
    }
    if (credentials.securityType != WifiSecurityType.OPEN &&
        password != null && (password.length !in 8..63)
    ) {
        return "Wi-Fi password must be 8..63 characters"
    }
    return null
}

/** Builds a joined snapshot strictly from addresses of the joined Network. */
internal fun networkStateFromJoinedAddresses(addresses: List<String>): NetworkState =
    NetworkState.ConnectedToWifi(ssid = null, localIpAddresses = addresses.distinct())
