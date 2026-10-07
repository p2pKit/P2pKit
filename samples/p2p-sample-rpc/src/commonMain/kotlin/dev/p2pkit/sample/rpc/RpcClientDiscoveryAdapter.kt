package dev.p2pkit.sample.rpc

import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcClient
import dev.p2pkit.rpc.RpcConnectionState
import dev.p2pkit.rpc.RpcDiscoveredHost
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcFailurePhase

/** Resolves the explicitly selected cryptographic identity from CURRENT records immediately before each operation. */
internal class RpcClientDiscoveryAdapter(private val client: RpcClient) : RpcDiscoveryClient {
    override fun nearby(): List<RpcNearbyHost> = client.discoveredHosts().map {
        RpcNearbyHost(it.fingerprint.value, it.peer.name, it.peer.platform.name, client.trust.isTrusted(it.fingerprint))
    }
    override fun trusted(pin: String): Boolean = client.trust.isTrusted(PeerFingerprint.parse(pin))
    override fun ready(): Boolean = client.state.value == RpcConnectionState.Ready
    override suspend fun discover() = client.startDiscovery()
    override suspend fun disconnect() = client.disconnect()
    override suspend fun connect(pin: String) = client.connect(current(pin))
    override suspend fun requestApproval(pin: String) = client.requestApproval(current(pin))
    override suspend fun revoke(pin: String) = client.trust.revoke(PeerFingerprint.parse(pin))

    private fun current(pin: String): RpcDiscoveredHost = client.discoveredHosts()
        .filter { it.fingerprint.value == pin }.singleOrNull()
        ?: throw RpcFailure(RpcFailureKind.NotConnected, RpcFailurePhase.Admission)
}
