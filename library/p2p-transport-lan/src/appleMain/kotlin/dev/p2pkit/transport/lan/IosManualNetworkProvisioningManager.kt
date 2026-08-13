package dev.p2pkit.transport.lan

import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.NetworkProvisioningError
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.dsl.NetworkProvisioningConfigBuilder
import dev.p2pkit.core.provisioning.JoinNetworkResult
import dev.p2pkit.core.provisioning.LocalNetworkConfig
import dev.p2pkit.core.provisioning.LocalNetworkResult
import dev.p2pkit.core.provisioning.ManualConnectionInfo
import dev.p2pkit.core.provisioning.NetworkProvisioningEvent
import dev.p2pkit.core.provisioning.NetworkProvisioningFactory
import dev.p2pkit.core.provisioning.NetworkProvisioningManager
import dev.p2pkit.core.provisioning.NetworkProvisioningState
import dev.p2pkit.core.provisioning.NetworkState
import dev.p2pkit.core.provisioning.ProvisioningContext
import dev.p2pkit.core.provisioning.WifiCredentials
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

/**
 * Minimum-viable iOS implementation of [NetworkProvisioningManager].
 *
 * Apple does not allow third-party iOS apps to host Wi-Fi hotspots or
 * silently join Wi-Fi networks, so [startLocalNetwork] and
 * [joinLocalNetwork] return [LocalNetworkResult.Unsupported] /
 * [JoinNetworkResult.Unsupported] respectively. Those are documented
 * limitations — they will never be implementable in this module.
 *
 * The single feature this manager DOES expose is **manual-IP fallback**:
 * - [getManualConnectionInfo] returns the local kit's port and authenticated
 *   identity plus a synchronous snapshot of safe LAN interface addresses for
 *   exchanging out-of-band.
 * - [createManualPeer] registers a synthetic peer keyed by
 *   `TransportHint(host, port)` so the iOS LAN data transport can dial
 *   it via `nw_endpoint_create_host` — see
 *   [IosLanDataTransport.connect]'s manual-IP fallback branch.
 *
 * Address enumeration is a moment-in-time `getifaddrs` snapshot rather than
 * a path subscription. It includes active Wi-Fi/wired/AWDL IPv4 and IPv6
 * unicast addresses, preserves a validated zone on IPv6 link-local values,
 * and excludes loopback, wildcard, multicast, broadcast, cellular, and VPN
 * tunnel candidates. The list can still be empty when no eligible interface
 * exists or enumeration fails. [networkState] and [events] remain static;
 * [state] changes only for terminal [close].
 */
public class IosManualNetworkProvisioningManager internal constructor(
    private val ctx: ProvisioningContext,
    private val lifecycleHooks: IosManualProvisioningLifecycleHooks =
        IosManualProvisioningLifecycleHooks(),
    private val addressScanner: AppleInterfaceAddressScanner =
        AppleInterfaceAddressScanner(::collectAppleInterfaceAddressSnapshot)
) : NetworkProvisioningManager {

    private val scopeJob = SupervisorJob(parent = ctx.parentJob)
    private val scope = CoroutineScope(Dispatchers.Default + scopeJob)
    private val closeLock = Mutex()
    @kotlin.concurrent.Volatile
    private var closed: Boolean = false

    private val _state = MutableStateFlow<NetworkProvisioningState>(NetworkProvisioningState.Idle)
    override val state: StateFlow<NetworkProvisioningState> = _state.asStateFlow()

    private val _networkState = MutableStateFlow<NetworkState>(NetworkState.Unknown)
    override val networkState: StateFlow<NetworkState> = _networkState.asStateFlow()

    private val _events = MutableSharedFlow<NetworkProvisioningEvent>(
        replay = 0,
        extraBufferCapacity = 16,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )
    override val events: Flow<NetworkProvisioningEvent> = _events.asSharedFlow()

    init {
        scopeJob.invokeOnCompletion {
            closed = true
            _networkState.value = NetworkState.Unknown
            _state.value = NetworkProvisioningState.Closed
        }
    }

    override suspend fun startLocalNetwork(config: LocalNetworkConfig): LocalNetworkResult =
        runManagerOperation(::closedLocalNetworkResult) {
            if (isClosingOrClosed()) closedLocalNetworkResult()
            else LocalNetworkResult.Unsupported(
                "iOS cannot host Wi-Fi hotspots — Apple does not expose this to third-party apps."
            )
        }

    override suspend fun stopLocalNetwork(): Unit = runManagerOperation({}) {
        // No-op — nothing to stop.
    }

    override suspend fun joinLocalNetwork(credentials: WifiCredentials): JoinNetworkResult =
        runManagerOperation(::closedJoinNetworkResult) {
            if (isClosingOrClosed()) closedJoinNetworkResult()
            else JoinNetworkResult.Unsupported(
                "iOS cannot programmatically join arbitrary Wi-Fi networks — the user must use the system Settings."
            )
        }

    override suspend fun getManualConnectionInfo(): ManualConnectionInfo? =
        runManagerOperation({ throw NetworkProvisioningError.ManagerClosed() }) {
            ensureOpen()
            // Read lazily — the LAN data transport's port isn't bound until
            // `kit.start()` (or the first lifecycle call) succeeds.
            val port = ctx.lanTcpPort() ?: return@runManagerOperation null
            lifecycleHooks.beforeManualInfoResult()
            val addressSnapshot = addressScanner.scan()
            addressSnapshot.enumerationErrorCode?.let { errorCode ->
                ctx.logger.warn(
                    "provisioning: Apple interface address snapshot failed with errno=$errorCode"
                )
            }
            ManualConnectionInfo(
                hostAddresses = selectAppleHostAddresses(addressSnapshot.candidates),
                port = port,
                appId = ctx.appId,
                peerId = ctx.localPeerId,
                deviceName = ctx.localDeviceName,
                fingerprint = ctx.localFingerprint,
                pairingQr = ctx.localPairingQr
            )
        }

    @OptIn(ExperimentalP2pApi::class)
    @Deprecated(
        message = "Secure manual-IP connections require an expected fingerprint. Use the fingerprint overload.",
        replaceWith = ReplaceWith("createManualPeer(host, port, expectedFingerprint)")
    )
    override suspend fun createManualPeer(host: String, port: Int): Peer =
        runManagerOperation({ throw NetworkProvisioningError.ManagerClosed() }) {
            ensureOpen()
            ctx.logger.info("provisioning: createManualPeer host=$host port=$port")
            IosLanDebug.log("provision", "createManualPeer host=$host port=$port")
            ctx.manualPeerRegistrar.registerManualPeer(host = host, port = port)
        }

    @ExperimentalP2pApi
    override suspend fun createManualPeer(
        host: String,
        port: Int,
        expectedFingerprint: PeerFingerprint
    ): Peer = runManagerOperation({ throw NetworkProvisioningError.ManagerClosed() }) {
        ensureOpen()
        ctx.logger.info("provisioning: createManualPeer host=$host port=$port with authenticated pin")
        IosLanDebug.log("provision", "createManualPeer host=$host port=$port with authenticated pin")
        ctx.manualPeerRegistrar.registerManualPeer(
            host = host,
            port = port,
            expectedFingerprint = expectedFingerprint
        )
    }

    override suspend fun close(): Unit = withContext(NonCancellable) {
        closeLock.withLock {
            if (!closed) {
                closed = true
                _state.value = NetworkProvisioningState.Closing
            }
            scopeJob.cancelAndJoin()
            _networkState.value = NetworkState.Unknown
            _state.value = NetworkProvisioningState.Closed
        }
    }

    private fun ensureOpen() {
        if (isClosingOrClosed()) throw NetworkProvisioningError.ManagerClosed()
    }

    private fun isClosingOrClosed(): Boolean = closed || !scopeJob.isActive

    private fun closedLocalNetworkResult(): LocalNetworkResult = LocalNetworkResult.Failed(
        NetworkProvisioningError.ManagerClosed()
    )

    private fun closedJoinNetworkResult(): JoinNetworkResult = JoinNetworkResult.Failed(
        NetworkProvisioningError.ManagerClosed()
    )

    private suspend fun <T> runManagerOperation(
        closedResult: () -> T,
        block: suspend () -> T
    ): T {
        val operation = scope.async { block() }
        return try {
            operation.await()
        } catch (e: CancellationException) {
            withContext(NonCancellable) { operation.cancelAndJoin() }
            if (isClosingOrClosed()) closedResult() else throw e
        }
    }
}

/** Deterministic suspension seam used only by Apple lifecycle tests. */
internal class IosManualProvisioningLifecycleHooks(
    val beforeManualInfoResult: suspend () -> Unit = {}
)

/**
 * Factory used by the DSL extension below.
 */
public object IosManualProvisioningFactory : NetworkProvisioningFactory {
    override fun build(context: ProvisioningContext): NetworkProvisioningManager =
        IosManualNetworkProvisioningManager(ctx = context)
}

/**
 * Register the iOS manual-IP-only provisioning module.
 *
 * Usage:
 *
 * ```kotlin
 * P2pKit.create {
 *     appId = AppId("…")
 *     deviceName = "…"
 *     transports { lan() }
 *     networkProvisioning { iosManualIp() }
 * }
 * ```
 *
 * After this is registered, Swift consumers can call
 * `kit.networkProvisioning.createManualPeer(host:port:expectedFingerprint:completionHandler:)`
 * to dial a peer directly by IP with its secure-v2 identity pinned — useful
 * when NWBrowser-based discovery isn't yielding results (corporate Wi-Fi
 * blocking multicast, iOS Simulator network sandbox, etc.). Hotspot host /
 * Wi-Fi join APIs remain `Unsupported`.
 */
public fun NetworkProvisioningConfigBuilder.iosManualIp() {
    register(IosManualProvisioningFactory)
}
