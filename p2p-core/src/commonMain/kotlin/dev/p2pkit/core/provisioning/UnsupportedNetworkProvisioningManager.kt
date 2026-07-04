package dev.p2pkit.core.provisioning

import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.Peer
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.emptyFlow

/**
 * Fallback used when no provisioning factory is registered via the
 * `networkProvisioning { … }` DSL block (the optional platform modules
 * register real managers). Every method that has an `Unsupported` variant in
 * its return type returns it; `createManualPeer` throws because there is no
 * meaningful peer to fabricate without a real platform implementation.
 */
public class UnsupportedNetworkProvisioningManager : NetworkProvisioningManager {

    private val _state = MutableStateFlow<NetworkProvisioningState>(NetworkProvisioningState.Idle)
    override val state: StateFlow<NetworkProvisioningState> = _state.asStateFlow()

    private val _networkState = MutableStateFlow<NetworkState>(NetworkState.Unknown)
    override val networkState: StateFlow<NetworkState> = _networkState.asStateFlow()

    override val events: Flow<NetworkProvisioningEvent> = emptyFlow()

    override suspend fun startLocalNetwork(config: LocalNetworkConfig): LocalNetworkResult =
        LocalNetworkResult.Unsupported(NOT_IN_V01)

    override suspend fun stopLocalNetwork() {
        // No-op: nothing was started.
    }

    override suspend fun joinLocalNetwork(credentials: WifiCredentials): JoinNetworkResult =
        JoinNetworkResult.Unsupported(NOT_IN_V01)

    override suspend fun getManualConnectionInfo(): ManualConnectionInfo? = null

    @ExperimentalP2pApi
    override suspend fun createManualPeer(host: String, port: Int): Peer =
        throw UnsupportedOperationException(NOT_IN_V01)

    private companion object {
        const val NOT_IN_V01 = "Network provisioning is planned for v0.2 and not implemented in v0.1."
    }
}
