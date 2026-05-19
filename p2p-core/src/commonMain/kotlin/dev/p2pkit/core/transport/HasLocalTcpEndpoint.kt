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
 * (the listener hasn't bound yet) and stable for the transport's lifetime
 * once non-null. Consumers that need the current port should read `.value`;
 * consumers that want to wait for binding can `.first { it != null }`.
 */
public interface HasLocalTcpEndpoint {
    public val tcpPort: StateFlow<Int?>
}
