package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.RpcPhoneSettings
import dev.p2pkit.transport.lan.OrganizationLan
import java.net.Inet4Address
import java.net.InetAddress
import java.net.NetworkInterface

internal data class DesktopRpcNetwork(
    val interfaceName: String,
    val address: String,
    val subnet: String,
    val otherActiveInterfaces: Int = 0,
) {
    init { require(otherActiveInterfaces >= 0) }
    override fun toString(): String = "$interfaceName — $address ($subnet)"

    // This is feedback about the last read-only scan, never a replacement for the transport's fresh checks.
    val startProblem: String? get() = if (otherActiveInterfaces == 0) null else
        "Last scan: $otherActiveInterfaces other active non-loopback interface(s). " +
            "Portable Java cannot verify this topology. Explicit Start requires the verified macOS TCP adapter " +
            "to prove each socket; otherwise it will fail closed. This is not discovery/multicast proof. " +
            "Do not disable protections."
}

/** Suggestions only. Selecting a visible interface never changes its routes, flags or permissions. */
internal fun desktopRpcNetworks(): List<DesktopRpcNetwork> {
    // Read every interface's flags, including those which cannot supply a suggestion. An unreadable
    // competing interface must fail the scan, not disappear and make this topology appear usable.
    val interfaces = NetworkInterface.getNetworkInterfaces().toList()
    val active = interfaces.filter { it.isUp && !it.isLoopback }.map { it.name }
    return interfaces.flatMap { network ->
        if (!network.isUp || network.isLoopback || network.isVirtual || network.isPointToPoint) emptyList()
        else network.interfaceAddresses.mapNotNull { value ->
            val address = value.address as? Inet4Address ?: return@mapNotNull null
            runCatching {
                val text = checkNotNull(address.hostAddress)
                val subnet = desktopRpcSubnet(text, value.networkPrefixLength.toInt())
                OrganizationLan(listOf(subnet), network.name, text)
                DesktopRpcNetwork(network.name, text, subnet, active.count { it != network.name })
            }.getOrNull()
        }
    }.distinct().sortedWith(compareBy(DesktopRpcNetwork::interfaceName, DesktopRpcNetwork::address))
}

internal fun desktopRpcSubnet(address: String, prefix: Int): String {
    require(prefix in 0..32)
    val parts = address.split('.')
    require(parts.size == 4 && parts.all {
        it.matches(Regex("0|[1-9][0-9]{0,2}")) && it.toInt() in 0..255
    })
    val bytes = ByteArray(4) { index ->
        val bits = (prefix - index * 8).coerceIn(0, 8)
        (parts[index].toInt() and ((0xff shl (8 - bits)) and 0xff)).toByte()
    }
    return "${InetAddress.getByAddress(bytes).hostAddress}/$prefix"
}

internal fun desktopRpcSettings(
    subnets: String, interfaceName: String, address: String, port: String,
): RpcPhoneSettings {
    require(subnets.length in 1..512 && interfaceName.length in 1..32 && address.length in 1..39)
    require(port.matches(Regex("[1-9][0-9]{3,4}")) && port.toInt() in 1024..65535)
    OrganizationLan(subnets.split(',').map(String::trim), interfaceName, address, port.toInt())
    return RpcPhoneSettings(subnets, interfaceName, address, port.toInt())
}

/** Automatic application selection is fail-closed for no network or more than one eligible address/interface. */
internal fun desktopRpcAutomaticSettings(networks: List<DesktopRpcNetwork>): RpcPhoneSettings {
    val network = networks.singleOrNull()
        ?: throw IllegalStateException("No unique eligible private IPv4 LAN; check network availability")
    OrganizationLan(listOf(network.subnet), network.interfaceName, network.address)
    // This does not bypass the transport's fresh interface/route/native socket policy checks.
    return RpcPhoneSettings.automatic(network.subnet, network.interfaceName, network.address)
}
