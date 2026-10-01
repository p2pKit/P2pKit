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
    strictJvmLanInterfaces(NetworkInterface.getNetworkInterfaces().toList())
}.getOrNull()

private fun strictJvmLanInterfaces(networks: List<NetworkInterface>): List<JvmLanInterfaceSnapshot> =
    networks.map { network ->
        JvmLanInterfaceSnapshot(
            network.name, network.isUp, network.isLoopback, network.isPointToPoint, network.isVirtual,
            network.supportsMulticast(), network.interfaceAddresses.map { address ->
                LanInterfaceAddress(checkNotNull(address.address), address.networkPrefixLength.toInt())
            }
        )
    }

/** One fresh OS enumeration, never retained between path checks or shared between connections. */
internal data class JvmLanSocketSnapshot(
    val interfaces: List<JvmLanInterfaceSnapshot>,
    // Null means address visibility could be filtered: preserve the native self-address lookup.
    val completeLocalAddresses: Set<InetAddress>?,
)

private fun readJvmLanSocketSnapshot(): JvmLanSocketSnapshot? = runCatching {
    val networks = NetworkInterface.getNetworkInterfaces().toList()
    JvmLanSocketSnapshot(strictJvmLanInterfaces(networks), unfilteredJvmLanAddresses(networks))
}.getOrNull()

@Suppress("DEPRECATION") // Java 17 still supports address-filtering SecurityManagers.
private fun unfilteredJvmLanAddresses(networks: List<NetworkInterface>): Set<InetAddress>? {
    if (System.getSecurityManager() != null) return null
    val addresses = buildSet<InetAddress> {
        fun collect(network: NetworkInterface) {
            // Use the full address inventory, NOT only eligible/up interfaces or prefix bindings.
            addAll(network.inetAddresses.toList())
            network.subInterfaces.toList().forEach(::collect)
        }
        networks.forEach(::collect)
    }
    return addresses.takeIf { System.getSecurityManager() == null }
}

internal fun OrganizationLan.jvmNumeric(address: String): InetAddress {
    if (!allows(address)) throw P2pError.ConnectionFailed("Organization LAN endpoint rejected")
    // getByAddress takes parsed bytes; unlike getByName/InetSocketAddress(String), it cannot query DNS.
    return InetAddress.getByAddress(checkNotNull(NumericAddress.parse(address)).bytes)
}

internal fun OrganizationLan.allowsJvmSocket(socket: Socket): Boolean = runCatching {
    allowsJvmSocketPath(socket.localAddress, socket.inetAddress)
}.getOrDefault(false)

/** Internal seam for deterministic topology/race controls; production always uses the fresh OS reader. */
internal fun OrganizationLan.allowsJvmSocketPath(
    local: InetAddress,
    remote: InetAddress,
    readSnapshot: () -> JvmLanSocketSnapshot? = ::readJvmLanSocketSnapshot,
    isAssignedLocally: (InetAddress) -> Boolean = { NetworkInterface.getByInetAddress(it) != null },
): Boolean = runCatching {
    val snapshot = readSnapshot() ?: return@runCatching false
    if (organizationJvmTarget(this, snapshot.interfaces) == null || !isLocal(local.hostAddress.orEmpty()) ||
        !allows(remote.hostAddress.orEmpty())
    ) return@runCatching false
    // getByInetAddress enumerates the OS interfaces again. Reuse the same complete, unfiltered
    // snapshot for self/hairpin rejection; retain the native lookup when completeness is unknown.
    // No cache, reduced revalidation frequency, interface exemption or authentication change.
    val localAddresses = snapshot.completeLocalAddresses
    if (localAddresses == null) !isAssignedLocally(remote) else remote !in localAddresses
}.getOrDefault(false)
