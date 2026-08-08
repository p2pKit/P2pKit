package dev.p2pkit.core.transport

import kotlinx.coroutines.flow.StateFlow

/**
 * Implemented by [DataTransport]s that bind a TCP server on the local host.
 *
 * Cross-module-internal contract: read by `P2pKitImpl` so the provisioning
 * sidecar can surface a host/port pair via
 * [dev.p2pkit.core.provisioning.NetworkProvisioningManager.getManualConnectionInfo].
 * Apps don't need to implement this — the LAN transport modules do.
 *
 * Since the v0.3 transport-lifecycle refactor the port is exposed as a
 * [StateFlow] of `Int?`. It is `null` before [DataTransport.start] succeeds
 * (the listener hasn't bound yet). The port is NOT guaranteed stable after
 * that: the iOS transport rebinds its listener on network changes, briefly
 * dropping the value back to `null` and then publishing the fresh —
 * typically different — port. (JVM/Android keep one bound port for the
 * transport's lifetime.) Consumers must re-read `.value` (or stay
 * subscribed) each time they need the current port rather than caching the
 * first non-null value; `.first { it != null }` is only a wait-until-bound
 * helper. AUDIT-2026-06: this doc previously promised "stable once
 * non-null", which the iOS rebind path violates.
 */
public interface HasLocalTcpEndpoint {
    public val tcpPort: StateFlow<Int?>
}
