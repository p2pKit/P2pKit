package dev.p2pkit.transport.lan

import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import java.net.NetworkInterface

/**
 * JVM/desktop diagnostic sink for the LAN transport — the JVM counterpart to
 * appleMain's `IosLanDebug` and androidMain's `android.util.Log` usage.
 *
 * Why this exists: `:p2p-core`'s `TransportContext` does NOT carry the kit's
 * `P2pLogger` down to transport implementations, so the JVM LAN transport had
 * no way to surface what JmDNS / the server socket / outbound dials are doing.
 * This singleton is the minimum-impact path to a forensic trace for the
 * interface-selection work (Issue #2).
 *
 * **Disabled by default.** Enable it one of two ways:
 *   - programmatically: `JvmLanDiag.enabled = true` (e.g. in the sample's main);
 *   - on the JVM command line: `-Ddev.p2pkit.lan.trace=true`.
 *
 * When enabled, every line is mirrored to **stdout** with a `P2pKitLAN` prefix
 * (so `... | grep P2pKitLAN` isolates the trail) AND emitted on [events] so a
 * Compose-desktop sample can show the same timeline in-app. 200-entry replay so
 * a late subscriber still sees the early bind/advertise events.
 */
public object JvmLanDiag {

    /**
     * Master switch. Defaults to the `dev.p2pkit.lan.trace` system property so a
     * release build is silent unless the operator explicitly opts in.
     */
    @Volatile
    public var enabled: Boolean =
        System.getProperty("dev.p2pkit.lan.trace")?.equals("true", ignoreCase = true) == true

    /**
     * Finer opt-in for **per-frame** byte-chunk logging on the data socket
     * (each `write`/`read`). Off even when [enabled] is true, because a single
     * file transfer is hundreds of chunks and would bury the interface /
     * discovery / connection-lifecycle lines that the two issues actually turn
     * on. Enable with `-Ddev.p2pkit.lan.traceFrames=true` (or set it directly)
     * when you specifically need the byte-level trail.
     */
    @Volatile
    public var traceFrames: Boolean =
        System.getProperty("dev.p2pkit.lan.traceFrames")?.equals("true", ignoreCase = true) == true

    private val _events = MutableSharedFlow<String>(
        replay = 200,
        extraBufferCapacity = 200,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )
    public val events: SharedFlow<String> = _events.asSharedFlow()

    /** Push one diagnostic line. No-op (and zero allocation) when [enabled] is false. */
    public fun log(tag: String, message: String) {
        if (!enabled) return
        val safeTag = sanitizeLanDiagnostic(tag)
        val safeMessage = sanitizeLanDiagnostic(message)
        val line = "P2pKitLAN [${System.currentTimeMillis() % 1_000_000}][$safeTag] $safeMessage"
        _events.tryEmit(line)
        println(line)
    }

    /** Per-frame byte-chunk line. No-op unless BOTH [enabled] and [traceFrames]. */
    public fun frame(tag: String, message: String) {
        if (!enabled || !traceFrames) return
        log(tag, message)
    }

    /**
     * Multi-line dump of every local network interface: name, flags
     * (up / loopback / point-to-point / virtual / multicast), MTU, and bound
     * addresses. Logged at JmDNS bind time so a wrong-interface bind (a VPN /
     * virtual / loopback NIC, or — on a tethered laptop — a cellular-backed
     * interface) is visible in the trail (Issue #2). Each accessor is wrapped
     * because `NetworkInterface` getters throw `SocketException`.
     */
    public fun describeInterfaces(): String = buildString {
        val ifaces = runCatching { NetworkInterface.getNetworkInterfaces()?.toList() }
            .getOrNull()
            .orEmpty()
        if (ifaces.isEmpty()) {
            append("(no interfaces enumerated)")
            return@buildString
        }
        for (ni in ifaces) {
            runCatching {
                val addrs = ni.inetAddresses.toList()
                    .joinToString(",") { it.hostAddress ?: it.toString() }
                append(
                    "\n  - ${ni.name} \"${ni.displayName}\" " +
                        "up=${ni.isUp} loopback=${ni.isLoopback} p2p=${ni.isPointToPoint} " +
                        "virtual=${ni.isVirtual} multicast=${ni.supportsMulticast()} mtu=${ni.mtu} " +
                        "addrs=[$addrs]"
                )
            }.onFailure { append("\n  - ${ni.name} (inspect failed: ${it.message})") }
        }
    }
}
