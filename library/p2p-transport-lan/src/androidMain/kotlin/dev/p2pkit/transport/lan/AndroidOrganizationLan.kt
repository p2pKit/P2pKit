package dev.p2pkit.transport.lan

import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import dev.p2pkit.core.P2pError
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import java.net.InetAddress
import java.net.NetworkInterface
import java.net.Socket

internal class AndroidLanIo(restricted: Boolean) {
    val read: CoroutineDispatcher = if (restricted) readers else Dispatchers.IO
    val write: CoroutineDispatcher = if (restricted) writers else Dispatchers.IO
    val setup: CoroutineDispatcher = if (restricted) setups else Dispatchers.IO
    // Accept remains one bounded blocking operation per listening transport (DialOnly creates none).
    val accept: CoroutineDispatcher = if (restricted) Dispatchers.IO.limitedParallelism(1) else Dispatchers.IO

    private companion object {
        // Shared across all kits, not an elastic view for every connected client. Data waits suspend on
        // readiness and consume no slot; these lanes only execute short syscalls / finite setup calls.
        val readers = Dispatchers.IO.limitedParallelism(16)
        val writers = Dispatchers.IO.limitedParallelism(16)
        val setups = Dispatchers.IO.limitedParallelism(16)
    }
}

/** No hotspot/null-Network or process-default fallback for the strict profile. */
@Suppress("DEPRECATION")
internal fun organizationAndroidTarget(
    policy: OrganizationLan,
    connectivity: ConnectivityManager,
): AndroidLanBindTarget? {
    return runCatching {
        if (connectivity.allNetworks.any {
                connectivity.getNetworkCapabilities(it)?.hasTransport(NetworkCapabilities.TRANSPORT_VPN) == true
            }
        ) return@runCatching null
        connectivity.allNetworks.firstNotNullOfOrNull { network ->
            val capabilities = connectivity.getNetworkCapabilities(network) ?: return@firstNotNullOfOrNull null
            if (!isSafeAndroidLanNetwork(connectivity, network) ||
                !capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_VPN)
            ) return@firstNotNullOfOrNull null
            val properties = connectivity.getLinkProperties(network) ?: return@firstNotNullOfOrNull null
            if (properties.interfaceName != policy.interfaceName) return@firstNotNullOfOrNull null
            val addresses = properties.linkAddresses.map { LanInterfaceAddress(it.address, it.prefixLength) }
            val address = addresses.firstOrNull { policy.isLocal(it.address.hostAddress.orEmpty()) }?.address
                ?: return@firstNotNullOfOrNull null
            AndroidLanBindTarget(network, policy.interfaceName, address, addresses, "$network:${address.hostAddress}")
        }
    }.getOrNull()
}

internal fun OrganizationLan.androidNumeric(address: String): InetAddress {
    if (!allows(address)) throw P2pError.ConnectionFailed("Organization LAN endpoint rejected")
    return InetAddress.getByAddress(checkNotNull(NumericAddress.parse(address)).bytes)
}

/** Unbound Java-socket fallback only. Strict production hosts use a Network-bound descriptor before listen. */
internal fun OrganizationLan.androidInboundRouteIsVerifiable(): Boolean = runCatching {
    val interfaces = NetworkInterface.getNetworkInterfaces().toList()
    interfaces.any { it.name == interfaceName && it.isUp && !it.isVirtual && !it.isPointToPoint } &&
        interfaces.none { it.isUp && !it.isLoopback && it.name != interfaceName }
}.getOrDefault(false)

internal fun OrganizationLan.allowsAndroidSocket(
    socket: Socket,
    route: AndroidLanDialRoute?,
    boundNetwork: Network? = null,
    isAssignedLocally: (InetAddress) -> Boolean = { NetworkInterface.getByInetAddress(it) != null },
): Boolean = runCatching {
    route?.network != null && (if (boundNetwork == null) androidInboundRouteIsVerifiable()
    else route.network == boundNetwork) && isLocal(route.localAddress.hostAddress.orEmpty()) &&
        isLocal(socket.localAddress.hostAddress.orEmpty()) && allows(socket.inetAddress.hostAddress.orEmpty()) &&
        !isAssignedLocally(socket.inetAddress)
}.getOrDefault(false)

/** Background pass only; no retained snapshot may authorize a later read/write or new connection. */
internal data class AndroidSocketPathSnapshot(
    val route: AndroidLanDialRoute?,
    val completeLocalAddresses: Set<InetAddress>?,
)

@Suppress("DEPRECATION") // Never treat a filtered address inventory as complete.
internal fun readAndroidSocketPathSnapshot(networkState: AndroidLanNetworkState?): AndroidSocketPathSnapshot {
    val route = networkState?.selectedRoute()
    val addresses = runCatching {
        if (System.getSecurityManager() != null) return@runCatching null
        val all = buildSet<InetAddress> {
            fun collect(network: NetworkInterface) {
                addAll(network.inetAddresses.toList())
                network.subInterfaces.toList().forEach(::collect)
            }
            NetworkInterface.getNetworkInterfaces().toList().forEach(::collect)
        }
        all.takeIf { System.getSecurityManager() == null }
    }.getOrNull()
    // On uncertain completeness preserve the original OS lookup, not an empty permissive set.
    return AndroidSocketPathSnapshot(route, addresses)
}
