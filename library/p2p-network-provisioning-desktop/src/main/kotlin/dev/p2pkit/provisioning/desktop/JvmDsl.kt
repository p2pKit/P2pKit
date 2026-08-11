package dev.p2pkit.provisioning.desktop

import dev.p2pkit.core.dsl.NetworkProvisioningConfigBuilder

/**
 * Register the JVM desktop provisioning module.
 *
 * Usage inside a [dev.p2pkit.core.P2pKit.create] block:
 *
 * ```kotlin
 * P2pKit.create {
 *     appId = AppId("…")
 *     deviceName = "…"
 *     transports { lan() }
 *     networkProvisioning {
 *         jvm()
 *         enableManualIpFallback = true   // default true; explicit for clarity
 *     }
 * }
 * ```
 *
 * On JVM the manager surfaces:
 *  - `getManualConnectionInfo()` with non-loopback host addresses + the LAN
 *    transport's TCP port.
 *  - `createManualPeer(host, port, expectedFingerprint)` to dial a peer by IP
 *    with its out-of-band secure-v2 identity pinned when mDNS is blocked.
 *
 * Hotspot hosting and Wi-Fi join return `Unsupported` (JVM cannot do either).
 */
public fun NetworkProvisioningConfigBuilder.jvm() {
    register(JvmProvisioningFactory)
}
