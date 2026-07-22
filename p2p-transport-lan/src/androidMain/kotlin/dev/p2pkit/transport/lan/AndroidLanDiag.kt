package dev.p2pkit.transport.lan

import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.util.Log as AndroidLog
import java.net.NetworkInterface

/**
 * Android LAN diagnostic helpers — the Android companion to [JvmLanDiag] /
 * appleMain's `IosLanDebug`.
 *
 * Android logs through `android.util.Log` (visible via `adb logcat`). Routine
 * lifecycle diagnostics are disabled by default and share one bounded,
 * sanitized `P2pKitLAN` logcat tag when [enabled]. Cleanup/resource warnings
 * remain visible even when routine diagnostics are disabled.
 *
 *  - [describeNetwork]: classifies a [Network] by transport (Wi-Fi / Cellular /
 *    Ethernet / VPN) + key addresses. This is the **Issue #2 smoking gun**: if
 *    JmDNS bound to a CELLULAR or VPN network, the LAN cannot carry our traffic
 *    and discovery / dials silently fail.
 *  - [describeInterfaces]: a full NIC dump (name, flags, MTU, addresses).
 *
 * Filter the unified tag with `adb logcat -s P2pKitLAN`.
 */
public object AndroidLanDiag {

    /** Enables bounded lifecycle/discovery/data debug diagnostics. */
    @Volatile
    public var enabled: Boolean = false

    /**
     * Per-frame byte-chunk logging gate (off by default — a single file
     * transfer is hundreds of chunks). Mirrors [JvmLanDiag.traceFrames]; set
     * `AndroidLanDiag.traceFrames = true` from the host app when the byte-level
     * trail is specifically needed.
     */
    @Volatile
    public var traceFrames: Boolean = false

    /** Per-frame line via logcat; no-op unless [enabled] and [traceFrames]. */
    public fun frame(tag: String, message: String) {
        if (traceFrames) d(tag, message)
    }

    internal fun d(tag: String, message: String) {
        if (!enabled) return
        AndroidLog.d(LOGCAT_TAG, diagnosticLine(tag, message))
    }

    internal fun w(tag: String, message: String, error: Throwable? = null) {
        val errorSummary = error?.let {
            val type = it::class.simpleName ?: "Throwable"
            " ($type: ${it.message.orEmpty()})"
        }.orEmpty()
        AndroidLog.w(LOGCAT_TAG, diagnosticLine(tag, message + errorSummary))
    }

    private fun diagnosticLine(tag: String, message: String): String =
        "[${sanitizeLanDiagnostic(tag)}] ${sanitizeLanDiagnostic(message)}"

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

    private const val LOGCAT_TAG: String = "P2pKitLAN"
}
