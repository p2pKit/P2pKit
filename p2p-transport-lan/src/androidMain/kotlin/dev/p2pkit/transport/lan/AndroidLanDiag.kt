package dev.p2pkit.transport.lan

import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.util.Log as AndroidLog
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import java.net.NetworkInterface

/**
 * Android LAN diagnostic helpers — the Android companion to `JvmLanDiag` /
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
@OptIn(ExperimentalCoroutinesApi::class)
public object AndroidLanDiag {

    /** Enables bounded lifecycle/discovery/data debug diagnostics. */
    @Volatile
    public var enabled: Boolean = false

    /**
     * Per-frame byte-chunk logging gate (off by default — a single file
     * transfer is hundreds of chunks). Mirrors `JvmLanDiag.traceFrames`; set
     * `AndroidLanDiag.traceFrames = true` from the host app when the byte-level
     * trail is specifically needed.
     */
    @Volatile
    public var traceFrames: Boolean = false

    private val _events = MutableSharedFlow<String>(
        replay = 200,
        extraBufferCapacity = 200,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )

    /**
     * Bounded in-process diagnostic stream for explicit diagnostic/test UIs.
     * It contains the same sanitized lines as the `P2pKitLAN` logcat tag, so
     * physical-device evidence can be exported without requiring adb access.
     * No events are emitted unless [enabled] is true.
     */
    public val events: SharedFlow<String> = _events.asSharedFlow()

    /**
     * Retains the bounded replay window for a late in-app collector. Samples
     * opt in; production defaults to false and clears replay after each line.
     */
    @Volatile
    public var retainHistory: Boolean = false

    /** Per-frame line via logcat; no-op unless [enabled] and [traceFrames]. */
    public fun frame(tag: String, message: String) {
        if (traceFrames) d(tag, message)
    }

    internal fun d(tag: String, message: String) {
        if (!enabled) return
        val line = diagnosticLine(tag, message)
        emit(line)
        AndroidLog.d(LOGCAT_TAG, line)
    }

    internal fun w(tag: String, message: String, error: Throwable? = null) {
        val errorSummary = error?.let {
            val type = it::class.simpleName ?: "Throwable"
            " ($type: ${it.message.orEmpty()})"
        }.orEmpty()
        val line = diagnosticLine(tag, message + errorSummary)
        if (enabled) emit(line)
        AndroidLog.w(LOGCAT_TAG, line)
    }

    private fun emit(line: String) {
        _events.tryEmit(line)
        if (!retainHistory) _events.resetReplayCache()
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
