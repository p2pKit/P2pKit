package dev.p2pkit.transport.lan

import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.util.Log
import java.net.NetworkInterface

/**
 * Android LAN diagnostic helpers — the Android companion to [JvmLanDiag] /
 * appleMain's `IosLanDebug`.
 *
 * Android already logs through `android.util.Log` (visible via `adb logcat`),
 * so this object only adds the two things a plain `Log.d` line can't express
 * compactly — and a frame-trace gate:
 *
 *  - [describeNetwork]: classifies a [Network] by transport (Wi-Fi / Cellular /
 *    Ethernet / VPN) + key addresses. This is the **Issue #2 smoking gun**: if
 *    JmDNS bound to a CELLULAR or VPN network, the LAN cannot carry our traffic
 *    and discovery / dials silently fail.
 *  - [describeInterfaces]: a full NIC dump (name, flags, MTU, addresses).
 *
 * Every P2pKit LAN logcat tag starts with `P2pKit` — filter with
 * `adb logcat | grep P2pKit`.
 */
public object AndroidLanDiag {

    /**
     * Per-frame byte-chunk logging gate (off by default — a single file
     * transfer is hundreds of chunks). Mirrors [JvmLanDiag.traceFrames]; set
     * `AndroidLanDiag.traceFrames = true` from the host app when the byte-level
     * trail is specifically needed.
     */
    @Volatile
    public var traceFrames: Boolean = false

    /** Per-frame line via `Log.d`; no-op unless [traceFrames]. */
    public fun frame(tag: String, message: String) {
        if (traceFrames) {
            Log.d(sanitizeLanDiagnostic(tag), sanitizeLanDiagnostic(message))
        }
    }

    internal fun describeNetwork(cm: ConnectivityManager, network: Network?): String {
        if (network == null) return "network=null"
        val caps = runCatching { cm.getNetworkCapabilities(network) }.getOrNull()
            ?: return "network=$network caps=unavailable"
        val transports = buildList {
            if (caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) add("WIFI")
            if (caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)) add("CELLULAR")
            if (caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)) add("ETHERNET")
            if (caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN)) add("VPN")
            if (caps.hasTransport(NetworkCapabilities.TRANSPORT_BLUETOOTH)) add("BLUETOOTH")
        }.ifEmpty { listOf("UNKNOWN") }
        val link = runCatching { cm.getLinkProperties(network) }.getOrNull()
        val addrs = link?.linkAddresses
            ?.joinToString(",") { it.address.hostAddress ?: it.address.toString() }
            ?: "?"
        return "network=$network transports=$transports iface=${link?.interfaceName ?: "?"} addrs=[$addrs]"
    }

    internal fun describeInterfaces(): String = buildString {
        val ifaces = runCatching { NetworkInterface.getNetworkInterfaces()?.toList() }
            .getOrNull()
            .orEmpty()
        if (ifaces.isEmpty()) {
            append("(none)")
            return@buildString
        }
        for (ni in ifaces) {
            runCatching {
                val a = ni.inetAddresses.toList()
                    .joinToString(",") { it.hostAddress ?: it.toString() }
                append(
                    "\n  - ${ni.name} up=${ni.isUp} loopback=${ni.isLoopback} " +
                        "p2p=${ni.isPointToPoint} virtual=${ni.isVirtual} " +
                        "multicast=${ni.supportsMulticast()} mtu=${ni.mtu} addrs=[$a]"
                )
            }.onFailure { append("\n  - ${ni.name} (inspect failed: ${it.message})") }
        }
    }
}
