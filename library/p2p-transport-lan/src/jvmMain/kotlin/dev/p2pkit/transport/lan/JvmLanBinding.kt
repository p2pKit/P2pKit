package dev.p2pkit.transport.lan

import java.net.Inet4Address
import java.net.Inet6Address
import java.net.InetAddress
import java.net.NetworkInterface

/** Immutable interface snapshot used by deterministic JVM bind selection. */
internal data class JvmLanInterfaceSnapshot(
    val name: String,
    val isUp: Boolean,
    val isLoopback: Boolean,
    val isPointToPoint: Boolean,
    val isVirtual: Boolean,
    val supportsMulticast: Boolean,
    val addresses: List<LanInterfaceAddress>
)

/** One explicit JmDNS bind choice plus the topology that selected it. */
internal data class JvmLanBindTarget(
    val interfaceName: String,
    val address: InetAddress,
    val fingerprint: String
) {
    override fun toString(): String = "$interfaceName:${address.hostAddress} [$fingerprint]"
}

/**
 * Select one deterministic multicast-capable LAN address.
 *
 * Site-local IPv4 is preferred, then other non-link-local IPv4, IPv4
 * link-local, global IPv6, and finally scoped IPv6 link-local for
 * direct-cable/auto-configuration networks. OS tunnel,
 * peer-to-peer, virtualization, container, and Apple side-channel interfaces
 * are excluded because binding a single JmDNS instance to them makes its
 * announcement unreachable from the ordinary Wi-Fi/Ethernet LAN.
 */
internal fun selectJvmLanBindTarget(
    snapshots: List<JvmLanInterfaceSnapshot>
): JvmLanBindTarget? {
    val eligibleInterfaces = snapshots
        .filter(::isEligibleJvmLanInterface)
        .sortedBy { it.name.lowercase() }
    val fingerprint = eligibleInterfaces
        .flatMap { network ->
            network.addresses.map { entry ->
                "${network.name}:${entry.address.hostAddress}/${entry.prefixLength}"
            }
        }
        .sorted()
        .joinToString("|")
    val selected = eligibleInterfaces
        .flatMap { network ->
            network.addresses.map { entry -> network.name to entry.address }
        }
        .filter { (_, address) ->
            when (address) {
                is Inet4Address ->
                    !address.isLoopbackAddress && !address.isAnyLocalAddress
                is Inet6Address ->
                    !address.isLoopbackAddress &&
                        !address.isAnyLocalAddress &&
                        (!address.isLinkLocalAddress || address.scopeId != 0)
                else -> false
            }
        }
        .sortedWith(
            compareBy<Pair<String, InetAddress>>(
                { (_, address) -> bindRank(address) },
                { (name, _) -> name.lowercase() },
                { (_, address) -> address.hostAddress }
            )
        )
        .firstOrNull()
        ?: return null
    return JvmLanBindTarget(
        interfaceName = selected.first,
        address = selected.second,
        fingerprint = fingerprint
    )
}

internal fun readJvmLanInterfaceSnapshots(): List<JvmLanInterfaceSnapshot> = runCatching {
    NetworkInterface.getNetworkInterfaces().toList().mapNotNull { network ->
        runCatching {
            JvmLanInterfaceSnapshot(
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

internal fun currentJvmLanBindTarget(): JvmLanBindTarget? {
    val override = System.getProperty(TEST_JMDNS_BIND_PROPERTY)?.trim()
    if (!override.isNullOrEmpty()) {
        val address = InetAddress.getByName(override)
        return JvmLanBindTarget(
            interfaceName = "override",
            address = address,
            fingerprint = "override:${address.hostAddress}"
        )
    }
    return selectJvmLanBindTarget(readJvmLanInterfaceSnapshots())
}

internal fun localJvmLanInterfaceAddresses(): List<LanInterfaceAddress> =
    readJvmLanInterfaceSnapshots()
        .filter(::isEligibleJvmLanInterface)
        .flatMap { it.addresses }

private fun isEligibleJvmLanInterface(snapshot: JvmLanInterfaceSnapshot): Boolean =
    snapshot.isUp &&
        snapshot.supportsMulticast &&
        !snapshot.isLoopback &&
        !snapshot.isPointToPoint &&
        !snapshot.isVirtual &&
        !isJvmLanNoiseInterface(snapshot.name)

private fun isJvmLanNoiseInterface(name: String): Boolean {
    val normalized = name.lowercase()
    return JVM_LAN_NOISE_PREFIXES.any(normalized::startsWith)
}

private fun bindRank(address: InetAddress): Int = when (address) {
    is Inet4Address -> when {
        address.isSiteLocalAddress -> 0
        !address.isLinkLocalAddress -> 1
        else -> 2
    }
    is Inet6Address -> if (address.isLinkLocalAddress) 4 else 3
    else -> Int.MAX_VALUE
}

private val JVM_LAN_NOISE_PREFIXES: List<String> = listOf(
    "lo",
    "utun",
    "awdl",
    "llw",
    "bridge",
    "ap",
    "gif",
    "stf",
    "anpi",
    "vboxnet",
    "docker",
    "vmnet",
    "tun",
    "tap",
    "veth"
)
