package dev.p2pkit.sample.android.rpclab

import android.content.Context
import android.net.ConnectivityManager
import android.net.LinkProperties
import android.net.Network
import android.net.NetworkCapabilities
import android.os.Handler
import android.os.Looper
import android.system.OsConstants
import java.net.Inet4Address
import java.net.NetworkInterface

/** A default-path suggestion, never permission to use a network or trust a peer. */
internal data class RpcLabWifiNetwork(
    val networkHandle: Long,
    val interfaceName: String,
    val interfaceIndex: Int,
    val localAddress: String,
    val subnet: String,
)

internal data class RpcLabWifiAddress(val address: String, val prefix: Int, val usable: Boolean = true)

internal data class RpcLabWifiSnapshot(
    val networkHandle: Long?,
    val transports: Set<Int> = emptySet(),
    val interfaceName: String? = null,
    val interfaceIndex: Int = 0,
    val interfaceUp: Boolean = false,
    val loopback: Boolean = false,
    val pointToPoint: Boolean = false,
    val linkAddresses: List<RpcLabWifiAddress> = emptyList(),
    val interfaceAddresses: List<RpcLabWifiAddress> = emptyList(),
    val stable: Boolean = true,
    val capabilitiesAvailable: Boolean = true,
    val propertiesAvailable: Boolean = true,
)

/** Fixed English explanations for this debug test UI; never include raw OS exceptions or network identifiers. */
internal enum class RpcLabWifiIssue(val explanation: String) {
    NoDefaultNetwork("Android is not reporting a default network to this app. Join your authorized Wi-Fi."),
    MissingNetworkDetails("Android has not supplied the current network capabilities or link details. Check again."),
    NotWifi("The app's default network is not Wi-Fi, even if a Wi-Fi icon is visible."),
    MixedTransport("The default network also uses a VPN or another transport. Automatic setup will not guess."),
    PathChanged("The default network changed during the check. Check Wi-Fi again."),
    MissingInterface("Android did not report a usable interface for the default Wi-Fi network."),
    UnsafeInterface("The reported interface is not eligible for automatic private-LAN setup."),
    InactiveInterface("The Wi-Fi interface is not up, or is loopback or point-to-point."),
    NoIpv4("No IPv4 address was found on the default Wi-Fi network. Automatic setup needs private IPv4."),
    AmbiguousIpv4("More than one IPv4 address was reported. Automatic setup will not choose between aliases."),
    AddressMismatch("The default network and system interface disagree about their IPv4 address or prefix."),
    UnusableAddress("The Wi-Fi IPv4 address is tentative, deprecated or failed address validation."),
    InvalidAddress("The Wi-Fi address is not a valid numeric IPv4 address."),
    NonPrivateAddress("The Wi-Fi address is not in a supported private IPv4 range."),
    UnsupportedSubnet("The actual Wi-Fi prefix does not describe a wholly private subnet with a host range."),
    NonHostAddress("The reported IPv4 address is the subnet or broadcast address, not a host address."),
    ObservationFailed("This app could not read or observe the current network. Check Wi-Fi again."),
}

internal sealed class RpcLabWifiObservation {
    open val network: RpcLabWifiNetwork? get() = null
    abstract val explanation: String
    abstract val details: String

    data object Checking : RpcLabWifiObservation() {
        override val explanation = "Waiting for this app's Wi-Fi observation. " +
            "You can check again if it does not update."
        override val details = "Check: waiting. No current observation."
    }

    data class Available(override val network: RpcLabWifiNetwork, val summary: String) : RpcLabWifiObservation() {
        override val explanation = "Private Wi-Fi detected. Review it, then tap Use this Wi-Fi."
        override val details get() = "Check: available. $summary"
    }

    data class Unavailable(val issue: RpcLabWifiIssue, val summary: String = "") : RpcLabWifiObservation() {
        override val explanation get() = issue.explanation
        override val details get() = "Check: ${issue.name}. $summary"
    }
}

internal object RpcLabWifiSelection {
    fun observe(snapshot: RpcLabWifiSnapshot): RpcLabWifiObservation {
        val name = snapshot.interfaceName
        val safeName = name != null && name.length in 1..32 && name.all {
            it in 'a'..'z' || it in 'A'..'Z' || it in '0'..'9' || it in "_.-"
        }
        val transports = snapshot.transports.sorted().joinToString { type ->
            when (type) {
                NetworkCapabilities.TRANSPORT_WIFI -> "Wi-Fi"
                NetworkCapabilities.TRANSPORT_CELLULAR -> "cellular"
                NetworkCapabilities.TRANSPORT_VPN -> "VPN"
                NetworkCapabilities.TRANSPORT_ETHERNET -> "Ethernet"
                else -> "other($type)"
            }
        }.ifEmpty { "none" }
        val details = "Default network: ${if (snapshot.networkHandle != null) "present" else "none"}; " +
            "capabilities: ${snapshot.capabilitiesAvailable}; link details: ${snapshot.propertiesAvailable}; " +
            "transports: $transports; interface: ${if (safeName) name else "unavailable"}; " +
            "index: ${snapshot.interfaceIndex}; up: ${snapshot.interfaceUp}; " +
            "network IPv4 rows: ${snapshot.linkAddresses.size}; " +
            "interface IPv4 rows: ${snapshot.interfaceAddresses.size}; stable: ${snapshot.stable}."
        fun reject(issue: RpcLabWifiIssue) = RpcLabWifiObservation.Unavailable(issue, details)
        val handle = snapshot.networkHandle ?: return reject(RpcLabWifiIssue.NoDefaultNetwork)
        if (!snapshot.stable) return reject(RpcLabWifiIssue.PathChanged)
        if (!snapshot.capabilitiesAvailable || !snapshot.propertiesAvailable) {
            return reject(RpcLabWifiIssue.MissingNetworkDetails)
        }
        if (NetworkCapabilities.TRANSPORT_WIFI !in snapshot.transports) return reject(RpcLabWifiIssue.NotWifi)
        if (snapshot.transports != setOf(NetworkCapabilities.TRANSPORT_WIFI)) {
            return reject(RpcLabWifiIssue.MixedTransport)
        }
        if (name == null || snapshot.interfaceIndex <= 0 || handle == 0L) {
            return reject(RpcLabWifiIssue.MissingInterface)
        }
        val forbidden = listOf("lo", "utun", "tun", "tap", "wg", "ppp", "ipsec", "vpn", "awdl", "llw",
            "gif", "stf", "veth", "docker", "vbox", "vmnet", "bridge")
        if (!safeName || forbidden.any { name.lowercase().startsWith(it) }) {
            return reject(RpcLabWifiIssue.UnsafeInterface)
        }
        if (!snapshot.interfaceUp || snapshot.loopback || snapshot.pointToPoint) {
            return reject(RpcLabWifiIssue.InactiveInterface)
        }
        if (snapshot.linkAddresses.isEmpty() || snapshot.interfaceAddresses.isEmpty()) {
            return reject(RpcLabWifiIssue.NoIpv4)
        }
        if (snapshot.linkAddresses.size != 1 || snapshot.interfaceAddresses.size != 1) {
            return reject(RpcLabWifiIssue.AmbiguousIpv4)
        }
        val row = snapshot.linkAddresses.single()
        val system = snapshot.interfaceAddresses.single()
        if (row.address != system.address || row.prefix != system.prefix) {
            return reject(RpcLabWifiIssue.AddressMismatch)
        }
        if (!row.usable || !system.usable) return reject(RpcLabWifiIssue.UnusableAddress)
        val address = ipv4(row.address) ?: return reject(RpcLabWifiIssue.InvalidAddress)
        val minimum = when {
            address ushr 24 == 10L -> 8
            address ushr 20 == 0xac1L -> 12
            address ushr 16 == 0xc0a8L -> 16
            else -> return reject(RpcLabWifiIssue.NonPrivateAddress)
        }
        if (row.prefix !in minimum..30) return reject(RpcLabWifiIssue.UnsupportedSubnet)
        val hostMask = (1L shl (32 - row.prefix)) - 1
        val host = address and hostMask
        if (host == 0L || host == hostMask) return reject(RpcLabWifiIssue.NonHostAddress)
        val subnet = address and (0xffffffffL xor hostMask)
        val text = (3 downTo 0).joinToString(".") { ((subnet ushr (it * 8)) and 255).toString() }
        return RpcLabWifiObservation.Available(
            RpcLabWifiNetwork(handle, name, snapshot.interfaceIndex, row.address, "$text/${row.prefix}"), details,
        )
    }

    private fun ipv4(text: String): Long? {
        val parts = text.split('.')
        if (parts.size != 4) return null
        var result = 0L
        for (part in parts) {
            if (part.length !in 1..3 || part.any { it !in '0'..'9' } ||
                (part.length > 1 && part[0] == '0')) return null
            val octet = part.toIntOrNull()?.takeIf { it in 0..255 } ?: return null
            result = (result shl 8) or octet.toLong()
        }
        return result
    }
}

internal interface RpcLabWifiObserving {
    fun start(changed: (RpcLabWifiObservation) -> Unit)
    fun currentObservation(): RpcLabWifiObservation
    fun stop()
}

/** Passive default-network reads: no Wi-Fi scan, SSID/location access, requestNetwork or process/socket binding. */
internal class AndroidRpcLabWifiObserver(context: Context) : RpcLabWifiObserving {
    private val connectivity = context.applicationContext.getSystemService(ConnectivityManager::class.java)
    private val handler = Handler(Looper.getMainLooper())
    private var generation: Any? = null
    private var callback: ConnectivityManager.NetworkCallback? = null

    override fun start(changed: (RpcLabWifiObservation) -> Unit) {
        stop()
        val token = Any()
        generation = token
        val observer = object : ConnectivityManager.NetworkCallback() {
            private fun update() {
                handler.post { if (generation === token) changed(currentObservation()) }
            }
            override fun onAvailable(network: Network) = update()
            override fun onLost(network: Network) = update()
            override fun onCapabilitiesChanged(network: Network, capabilities: NetworkCapabilities) = update()
            override fun onLinkPropertiesChanged(network: Network, properties: LinkProperties) = update()
        }
        connectivity.registerDefaultNetworkCallback(observer)
        callback = observer
        changed(currentObservation())
    }

    override fun stop() {
        generation = null
        handler.removeCallbacksAndMessages(null)
        // Keep an unsuccessfully unregistered callback reachable for the next cleanup attempt.
        callback?.let { connectivity.unregisterNetworkCallback(it) }
        callback = null
    }

    override fun currentObservation(): RpcLabWifiObservation = try {
        val network = connectivity.activeNetwork
        val capabilities = network?.let(connectivity::getNetworkCapabilities)
        val properties = network?.let(connectivity::getLinkProperties)
        val name = properties?.interfaceName
        val iface = name?.let(NetworkInterface::getByName)
        val forbiddenFlags = OsConstants.IFA_F_TENTATIVE or OsConstants.IFA_F_DADFAILED or OsConstants.IFA_F_DEPRECATED
        val rows = properties?.linkAddresses.orEmpty().filter { it.address is Inet4Address }.map {
            RpcLabWifiAddress(checkNotNull(it.address.hostAddress), it.prefixLength, it.flags and forbiddenFlags == 0)
        }
        val systemRows = iface?.interfaceAddresses.orEmpty().filter { it.address is Inet4Address }.map {
            RpcLabWifiAddress(checkNotNull(it.address.hostAddress), it.networkPrefixLength.toInt())
        }
        RpcLabWifiSelection.observe(RpcLabWifiSnapshot(
            networkHandle = network?.networkHandle,
            transports = (0..15).filter { capabilities?.hasTransport(it) == true }.toSet(),
            interfaceName = name, interfaceIndex = iface?.index ?: 0, interfaceUp = iface?.isUp == true,
            loopback = iface?.isLoopback == true, pointToPoint = iface?.isPointToPoint == true,
            linkAddresses = rows, interfaceAddresses = systemRows, stable = network == connectivity.activeNetwork,
            capabilitiesAvailable = capabilities != null, propertiesAvailable = properties != null,
        ))
    } catch (_: Exception) {
        RpcLabWifiObservation.Unavailable(RpcLabWifiIssue.ObservationFailed)
    }
}
