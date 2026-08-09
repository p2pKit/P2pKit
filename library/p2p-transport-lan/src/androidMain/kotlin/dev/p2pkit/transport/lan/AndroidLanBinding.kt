package dev.p2pkit.transport.lan

import android.net.Network
import java.net.Inet4Address
import java.net.InetAddress
import java.net.NetworkInterface

/** Immutable Java-interface snapshot for Android AP/tether fallback tests. */
internal data class AndroidLanInterfaceSnapshot(
    val name: String,
    val isUp: Boolean,
    val isLoopback: Boolean,
    val isPointToPoint: Boolean,
    val isVirtual: Boolean,
    val supportsMulticast: Boolean,
    val addresses: List<LanInterfaceAddress>
)

/** One explicit Android JmDNS bind choice. */
internal data class AndroidLanBindTarget(
    val network: Network?,
    val interfaceName: String,
    val address: InetAddress,
    val localAddresses: List<LanInterfaceAddress>,
    val fingerprint: String
) {
    override fun toString(): String =
        "$interfaceName:${address.hostAddress} network=${network ?: "none"} [$fingerprint]"
}

/**
 * Select a private IPv4 on a known Android Wi-Fi/AP/tether interface when
 * ConnectivityManager exposes no usable LAN Network (the hotspot-host case).
 */
internal fun selectAndroidFallbackBindTarget(
    snapshots: List<AndroidLanInterfaceSnapshot>
): AndroidLanBindTarget? {
    val candidates = snapshots
        .filter(::isEligibleAndroidFallbackInterface)
        .sortedWith(
            compareBy<AndroidLanInterfaceSnapshot>(
                { androidInterfaceRank(it.name) },
                { it.name.lowercase() }
            )
        )
    val fingerprint = candidates
        .flatMap { network ->
            network.addresses.map { entry ->
                "${network.name}:${entry.address.hostAddress}/${entry.prefixLength}"
            }
        }
        .sorted()
        .joinToString("|")
    val selected = candidates.firstNotNullOfOrNull { network ->
        network.addresses.firstOrNull { entry ->
            val address = entry.address
            address is Inet4Address &&
                address.isSiteLocalAddress &&
                !address.isLoopbackAddress &&
                !address.isAnyLocalAddress
        }?.let { network to it.address }
    } ?: return null
    return AndroidLanBindTarget(
        network = null,
        interfaceName = selected.first.name,
        address = selected.second,
        localAddresses = selected.first.addresses,
        fingerprint = fingerprint
    )
}

internal fun readAndroidLanInterfaceSnapshots(): List<AndroidLanInterfaceSnapshot> = runCatching {
    NetworkInterface.getNetworkInterfaces().toList().mapNotNull { network ->
        runCatching {
            AndroidLanInterfaceSnapshot(
                name = network.name.orEmpty(),
                isUp = network.isUp,
                isLoopback = network.isLoopback,
                isPointToPoint = network.isPointToPoint,
                isVirtual = network.isVirtual,
                supportsMulticast = network.supportsMulticast(),
                addresses = network.interfaceAddresses.mapNotNull { entry ->
                    val address = entry.address ?: return@mapNotNull null
                    LanInterfaceAddress(address, entry.networkPrefixLength.toInt())
                }
            )
        }.getOrNull()
    }
}.getOrDefault(emptyList())

internal fun currentAndroidFallbackBindTarget(): AndroidLanBindTarget? =
    selectAndroidFallbackBindTarget(readAndroidLanInterfaceSnapshots())

internal fun androidLanInterfaceFingerprint(): String =
    currentAndroidFallbackBindTarget()?.fingerprint.orEmpty()

private fun isEligibleAndroidFallbackInterface(
    snapshot: AndroidLanInterfaceSnapshot
): Boolean =
    snapshot.isUp &&
        snapshot.supportsMulticast &&
        !snapshot.isLoopback &&
        !snapshot.isPointToPoint &&
        !snapshot.isVirtual &&
        androidInterfaceRank(snapshot.name) < Int.MAX_VALUE

private fun androidInterfaceRank(name: String): Int {
    val normalized = name.lowercase()
    return when {
        ANDROID_AP_INTERFACE_PREFIXES.any(normalized::startsWith) -> 0
        normalized == "wlan1" -> 0
        ANDROID_WIFI_INTERFACE_PREFIXES.any(normalized::startsWith) -> 1
        else -> Int.MAX_VALUE
    }
}

private val ANDROID_AP_INTERFACE_PREFIXES: List<String> = listOf(
    "ap",
    "softap",
    "swlan",
    "tether"
)

private val ANDROID_WIFI_INTERFACE_PREFIXES: List<String> = listOf(
    "wlan",
    "wifi"
)
