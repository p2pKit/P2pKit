package dev.p2pkit.transport.lan

import dev.p2pkit.core.P2pError
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import java.net.InetAddress
import java.net.NetworkInterface
import java.net.Socket

/** Elastic IO views do not share the blocking-read quota with writes/setup or change global IO settings. */
internal class JvmLanIo(restricted: Boolean) {
    val read: CoroutineDispatcher = if (restricted) Dispatchers.IO.limitedParallelism(164) else Dispatchers.IO
    val write: CoroutineDispatcher = if (restricted) Dispatchers.IO.limitedParallelism(16) else Dispatchers.IO
    val setup: CoroutineDispatcher = if (restricted) Dispatchers.IO.limitedParallelism(16) else Dispatchers.IO
    val accept: CoroutineDispatcher = if (restricted) Dispatchers.IO.limitedParallelism(1) else Dispatchers.IO
}

internal fun organizationJvmTarget(
    policy: OrganizationLan,
    snapshots: List<JvmLanInterfaceSnapshot>? = readStrictJvmLanInterfaces(),
): JvmLanBindTarget? {
    // Java 17 has no portable SO_BINDTODEVICE/route inspection. Multiple usable egress interfaces
    // make source binding insufficient. Refuse that topology rather than invent a permissive route.
    // A single physical interface still supports routed organization VLANs.
    if (snapshots == null || snapshots.any {
            it.isUp && !it.isLoopback && it.name != policy.interfaceName
        }
    ) return null
    val network = snapshots.singleOrNull { it.name == policy.interfaceName } ?: return null
    if (!network.isUp || network.isLoopback || network.isVirtual || network.isPointToPoint ||
        isForbiddenLanInterface(network.name)
    ) return null
    val address = network.addresses.firstOrNull { policy.isLocal(it.address.hostAddress.orEmpty()) }?.address
        ?: return null
    return JvmLanBindTarget(network.name, address, "${network.name}:${address.hostAddress}")
}

/** Unlike ordinary discovery, strict selection cannot discard an interface whose flags are unreadable. */
private fun readStrictJvmLanInterfaces(): List<JvmLanInterfaceSnapshot>? = runCatching {
    NetworkInterface.getNetworkInterfaces().toList().map { network ->
        JvmLanInterfaceSnapshot(
            network.name, network.isUp, network.isLoopback, network.isPointToPoint, network.isVirtual,
            network.supportsMulticast(), network.interfaceAddresses.map { address ->
                LanInterfaceAddress(checkNotNull(address.address), address.networkPrefixLength.toInt())
            }
        )
    }
}.getOrNull()

internal fun OrganizationLan.jvmNumeric(address: String): InetAddress {
    if (!allows(address)) throw P2pError.ConnectionFailed("Organization LAN endpoint rejected")
    // getByAddress takes parsed bytes; unlike getByName/InetSocketAddress(String), it cannot query DNS.
    return InetAddress.getByAddress(checkNotNull(NumericAddress.parse(address)).bytes)
}

internal fun OrganizationLan.allowsJvmSocket(socket: Socket): Boolean = runCatching {
    organizationJvmTarget(this) != null && isLocal(socket.localAddress.hostAddress.orEmpty()) &&
        allows(socket.inetAddress.hostAddress.orEmpty()) &&
        NetworkInterface.getByInetAddress(socket.inetAddress) == null
}.getOrDefault(false)
