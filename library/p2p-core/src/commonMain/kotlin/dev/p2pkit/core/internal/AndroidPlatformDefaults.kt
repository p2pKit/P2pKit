package dev.p2pkit.core.internal

import dev.p2pkit.core.NetworkPathObserver

/** Install-time Android permissions required by LAN sockets and path observation. */
internal val androidLanManifestPermissions: List<String> = listOf(
    "android.permission.INTERNET",
    "android.permission.ACCESS_NETWORK_STATE",
    "android.permission.ACCESS_WIFI_STATE",
    "android.permission.CHANGE_WIFI_MULTICAST_STATE"
)

/** Pure selection seam for the registered-context Android path default. */
internal fun <ContextT> selectAndroidDefaultPathObserver(
    context: ContextT?,
    fallback: NetworkPathObserver,
    create: (ContextT) -> NetworkPathObserver
): NetworkPathObserver = context?.let(create) ?: fallback
