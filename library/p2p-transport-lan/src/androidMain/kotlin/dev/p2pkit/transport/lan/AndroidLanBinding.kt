package dev.p2pkit.transport.lan

import android.net.ConnectivityManager
import android.net.LinkProperties
import android.net.Network
import android.net.NetworkCapabilities
import java.net.Inet4Address
import java.net.Inet6Address
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

/** Resolve one explicit Android [Network] into the immutable LAN bind target used by both planes. */
internal fun androidLanBindTargetForNetwork(
    connectivity: ConnectivityManager,
    network: Network
): AndroidLanBindTarget? {
    if (!isSafeAndroidLanNetwork(connectivity, network)) return null
    val properties = runCatching { connectivity.getLinkProperties(network) }.getOrNull()
        ?: return null
    val address = selectAndroidNetworkBindAddress(properties.linkAddresses.map { it.address })
        ?: return null
    val localAddresses = properties.toAndroidLanInterfaceAddresses()
    val fingerprint = localAddresses
        .map { "${properties.interfaceName}:${it.address.hostAddress}/${it.prefixLength}" }
        .sorted()
        .joinToString("|")
    return AndroidLanBindTarget(
        network = network,
        interfaceName = properties.interfaceName ?: "network-$network",
        address = address,
        localAddresses = localAddresses,
        fingerprint = "network=$network|$fingerprint"
    )
}

/**
 * Resolve a current route even when discovery is not running (for example a
 * manually registered peer). No cellular/VPN network is ever used as a
 * fallback; hotspot/AP Java interfaces are considered last.
 */
@Suppress("DEPRECATION")
internal fun currentAndroidLanBindTarget(
    connectivity: ConnectivityManager
): AndroidLanBindTarget? {
    val active = runCatching { connectivity.activeNetwork }.getOrNull()
    val candidates = buildList {
        active?.let(::add)
        runCatching { connectivity.allNetworks.toList() }
            .getOrDefault(emptyList())
            .filterNot { it == active }
            .sortedBy(Network::toString)
            .forEach(::add)
    }
    candidates.firstNotNullOfOrNull { network ->
        androidLanBindTargetForNetwork(connectivity, network)
    }?.let { return it }
    return currentAndroidFallbackBindTarget()
}

internal fun isSafeAndroidLanNetwork(
    connectivity: ConnectivityManager,
    network: Network
): Boolean {
    val capabilities = runCatching { connectivity.getNetworkCapabilities(network) }.getOrNull()
        ?: return false
    return isSafeAndroidLanTransport(
        hasWifi = capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI),
        hasEthernet = capabilities.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET),
        hasCellular = capabilities.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR),
        hasVpn = capabilities.hasTransport(NetworkCapabilities.TRANSPORT_VPN)
    )
}

/**
 * Select a deterministic JmDNS bind address from one Android [Network]'s
 * `LinkProperties`. The list is already scoped to that network; ordering is
 * only used within explicit address classes, never as a process-wide route
 * choice.
 */
internal fun selectAndroidNetworkBindAddress(addresses: List<InetAddress>): InetAddress? =
    addresses.firstOrNull { address ->
        address is Inet4Address &&
            !address.isLoopbackAddress &&
            !address.isAnyLocalAddress &&
            !address.isLinkLocalAddress
    } ?: addresses.firstOrNull { address ->
        address is Inet4Address &&
            !address.isLoopbackAddress &&
            !address.isAnyLocalAddress
    } ?: addresses.firstOrNull { address ->
        address is Inet6Address &&
            !address.isLoopbackAddress &&
            !address.isAnyLocalAddress &&
            (!address.isLinkLocalAddress || address.scopeId != 0)
    }

/** Reject VPN/cellular overlays even if Android also reports an underlying LAN transport. */
internal fun isSafeAndroidLanTransport(
    hasWifi: Boolean,
    hasEthernet: Boolean,
    hasCellular: Boolean,
    hasVpn: Boolean
): Boolean =
    (hasWifi || hasEthernet) && !hasCellular && !hasVpn

private fun LinkProperties.toAndroidLanInterfaceAddresses(): List<LanInterfaceAddress> =
    linkAddresses.map { LanInterfaceAddress(it.address, it.prefixLength) }

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
