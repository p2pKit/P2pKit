package dev.p2pkit.core.transport

/**
 * Implemented by [DataTransport]s that bind a TCP server on the local host.
 *
 * Cross-module-internal contract: read by `P2pKitImpl` so the provisioning
 * sidecar can surface a host/port pair via
 * [dev.p2pkit.core.provisioning.NetworkProvisioningManager.getManualConnectionInfo].
 * Apps don't need to implement this — the LAN transport modules do.
 */
public interface HasLocalTcpEndpoint {
    /** Port the TCP server is bound to on this host. Stable for the transport's lifetime. */
    public val tcpPort: Int
}
