package dev.p2pkit.core.provisioning

import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.NetworkProvisioningError
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

/**
 * Fallback used when no provisioning factory is registered via the
 * `networkProvisioning { … }` DSL block (the optional platform modules
 * register real managers). Every method that has an `Unsupported` variant in
 * its return type returns it; `createManualPeer` throws because there is no
 * meaningful peer to fabricate without a real platform implementation.
 */
public class UnsupportedNetworkProvisioningManager : NetworkProvisioningManager {

    private val closeLock = Mutex()
    @kotlin.concurrent.Volatile
    private var closed: Boolean = false

    private val _state = MutableStateFlow<NetworkProvisioningState>(NetworkProvisioningState.Idle)
    override val state: StateFlow<NetworkProvisioningState> = _state.asStateFlow()

    private val _networkState = MutableStateFlow<NetworkState>(NetworkState.Unknown)
    override val networkState: StateFlow<NetworkState> = _networkState.asStateFlow()

    override val events: Flow<NetworkProvisioningEvent> = emptyFlow()

    override suspend fun startLocalNetwork(config: LocalNetworkConfig): LocalNetworkResult =
        if (closed) LocalNetworkResult.Failed(NetworkProvisioningError.ManagerClosed())
        else LocalNetworkResult.Unsupported(NOT_IN_V01)

    override suspend fun stopLocalNetwork() {
        // No-op: nothing was started.
    }

    override suspend fun joinLocalNetwork(credentials: WifiCredentials): JoinNetworkResult =
        if (closed) JoinNetworkResult.Failed(NetworkProvisioningError.ManagerClosed())
        else JoinNetworkResult.Unsupported(NOT_IN_V01)

    override suspend fun getManualConnectionInfo(): ManualConnectionInfo? {
        checkOpen()
        return null
    }

    @ExperimentalP2pApi
    @Deprecated(
        message = "Secure manual-IP connections require an expected fingerprint. Use the fingerprint overload.",
        replaceWith = ReplaceWith("createManualPeer(host, port, expectedFingerprint)")
    )
    override suspend fun createManualPeer(host: String, port: Int): Peer =
        if (closed) throw NetworkProvisioningError.ManagerClosed()
        else throw UnsupportedOperationException(NOT_IN_V01)

    @ExperimentalP2pApi
    override suspend fun createManualPeer(
        host: String,
        port: Int,
        expectedFingerprint: PeerFingerprint
    ): Peer = if (closed) throw NetworkProvisioningError.ManagerClosed()
    else throw UnsupportedOperationException(NOT_IN_V01)

    override suspend fun close(): Unit = withContext(NonCancellable) {
        closeLock.withLock {
            if (closed) return@withLock
            closed = true
            _state.value = NetworkProvisioningState.Closing
            _networkState.value = NetworkState.Unknown
            _state.value = NetworkProvisioningState.Closed
        }
    }

    private fun checkOpen() {
        if (closed) throw NetworkProvisioningError.ManagerClosed()
    }

    private companion object {
        // The compiler-generated field name is retained for RC2 JVM binary
        // compatibility even though its original v0.1-era wording is obsolete.
        const val NOT_IN_V01 =
            "No network provisioning implementation is registered. Add the platform module and configure " +
                "android(...), jvm(), or iosManualIp()."
    }
}
