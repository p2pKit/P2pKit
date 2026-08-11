package dev.p2pkit.core.dsl

import dev.p2pkit.core.AppId
import dev.p2pkit.core.AppKilledPolicy
import dev.p2pkit.core.BackgroundPolicy
import dev.p2pkit.core.KeepAliveConfig
import dev.p2pkit.core.NetworkPathObserver
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.internal.PeerIdStorage
import dev.p2pkit.core.internal.SecureIdentityStorage
import dev.p2pkit.core.internal.DEFAULT_DISCOVERY_REFRESH_TIMEOUT_MS
import dev.p2pkit.core.internal.DEFAULT_FEATURE_OPERATION_SETTLE_TIMEOUT_MS
import dev.p2pkit.core.internal.DEFAULT_HANDSHAKE_TIMEOUT_MS
import dev.p2pkit.core.internal.newP2pKit
import dev.p2pkit.core.permission.P2pPermissionManager
import dev.p2pkit.core.protocol.HelloPayload
import dev.p2pkit.core.protocol.validateWireText
import dev.p2pkit.core.provisioning.NetworkProvisioningConfig
import dev.p2pkit.core.provisioning.NetworkProvisioningFactory
import dev.p2pkit.core.transfer.FileTransferConfig
import dev.p2pkit.core.transport.RegisteredTransportFactory
import dev.p2pkit.core.transport.TransportFactory

/**
 * DSL marker for the P2pKit builder family. Prevents accidentally referencing
 * the outer builder from within nested blocks.
 */
@DslMarker
public annotation class P2pKitDsl

/**
 * Top-level builder for a P2pKit instance. Use via [P2pKit.create].
 *
 * Required fields are [appId] and [deviceName] and at least one entry in
 * [transports]. Configuration not explicitly set falls back to documented
 * defaults.
 */
@P2pKitDsl
public class P2pKitBuilder internal constructor() {

    /** Identifier shared by all devices of the same product. Required. */
    public var appId: AppId? = null

    /** Human-readable name advertised to peers. Required. */
    public var deviceName: String? = null

    /** Sink for diagnostic logs. Defaults to no-op. */
    public var logger: P2pLogger = P2pLogger.NoOp

    internal val transportsBuilder: TransportsBuilder = TransportsBuilder()
    internal var keepAlive: KeepAliveConfig = KeepAliveConfig()
    internal var reconnectPolicy: ReconnectPolicy = ReconnectPolicy.Disabled
    internal var backgroundPolicy: BackgroundPolicy = BackgroundPolicy.CloseActiveSessions
    internal var appKilledPolicy: AppKilledPolicy = AppKilledPolicy.NoPersistenceForMvp
    internal var securityMode: SecurityMode = SecurityMode.AuthenticatedV2()
    internal var networkProvisioning: NetworkProvisioningConfig = NetworkProvisioningConfig()
    internal var networkProvisioningFactory: NetworkProvisioningFactory? = null
    internal var fileTransfer: FileTransferConfig = FileTransferConfig()
    /**
     * Optional host-provided network path observer. When `null`, the kit
     * uses the platform default (iOS: real `nw_path_monitor`; JVM and
     * Android: no-op). Host apps that want path-change recovery on
     * Android construct `AndroidNetworkPathObserver(applicationContext)`
     * inside `lifecycle { … }`.
     */
    internal var networkPathObserver: NetworkPathObserver? = null

    /**
     * Override the [PeerIdStorage] the kit uses. **Internal** — set from
     * tests or from advanced internal code only. When `null`, the kit calls
     * [dev.p2pkit.core.internal.defaultPeerIdStorage] which selects a
     * platform-appropriate file-based store (or in-memory on Android if
     * `P2pKitAndroid.initialize(context)` wasn't called).
     */
    internal var peerIdStorage: PeerIdStorage? = null

    /** Platform-protected secure-v2 identity store selected by platform DSL. */
    internal var secureIdentityStorage: SecureIdentityStorage? = null

    /**
     * Optional host-provided [P2pPermissionManager]. When `null`, the kit uses
     * the platform default ([dev.p2pkit.core.internal.defaultPlatformPermissionManager]):
     * a real manifest-permission checker on Android (once
     * `P2pKitAndroid.initialize(context)` has run), no-op on JVM/iOS.
     *
     * Recommended wiring (decision #7a, 2026-07-04): keep this default even
     * when the app uses hotspot/Wi-Fi-join provisioning — core LAN
     * discovery/advertising needs no runtime permissions, and a kit-wide
     * sidecar manager (e.g. `AndroidP2pPermissionManager`) gates
     * `startAdvertising`/`startDiscovery` on provisioning-only permissions,
     * re-creating the install-time over-gating the AUDIT-2026-06
     * permission-gate fix removed. Query the sidecar's manager immediately
     * before provisioning calls instead.
     */
    public var permissionManager: P2pPermissionManager? = null

    /**
     * **Internal, test-only** (#19 / 2026-07 TST-9, decision #15a) — never set
     * from production code. When `true`, the kit's `SessionStore` throws
     * [IllegalStateException] on a detected bookkeeping-invariant violation
     * instead of `logger.warn`ing, so a store regression fails the suite
     * loudly rather than vanishing into a NoOp logger. Threaded via
     * [dev.p2pkit.core.internal.newP2pKit] →
     * `P2pKitImpl` → `SessionManager` → `SessionStore`. The production
     * default stays `false` (log-don't-crash); kit-level behavioral suites
     * opt in through the commonTest `createTestKit` fixture. Not public API.
     */
    internal var strictSessionInvariants: Boolean = false

    /** Internal test seam; production always keeps the protocol setup deadline. */
    internal var sessionSetupTimeoutMillis: Long = DEFAULT_HANDSHAKE_TIMEOUT_MS

    /** Internal deterministic cancellation seam immediately before session commit. */
    internal var beforeSessionCommitForTest: (suspend () -> Unit)? = null

    /** Internal deterministic cancellation seam after dial ownership transfers. */
    internal var afterOutgoingConnectForTest: (suspend () -> Unit)? = null

    /** Internal deterministic cancellation seam after setup produced a committed result. */
    internal var afterSessionSetupResultForTest: (suspend () -> Unit)? = null

    /** Internal deadline override for deterministic reconnect-refresh tests. */
    internal var discoveryRefreshTimeoutMillisForTest: Long = DEFAULT_DISCOVERY_REFRESH_TIMEOUT_MS

    /** Internal deadline override for a startup operation that prevents explicit feature stop. */
    internal var featureOperationSettleTimeoutMillisForTest: Long =
        DEFAULT_FEATURE_OPERATION_SETTLE_TIMEOUT_MS

    /** Internal seam used to prove shutdown does not depend on watcher scheduling. */
    internal var beforeTerminalWatcherRemovalForTest: (suspend () -> Unit)? = null

    public fun transports(block: TransportsBuilder.() -> Unit) {
        transportsBuilder.apply(block)
    }

    public fun keepAlive(block: KeepAliveConfigBuilder.() -> Unit) {
        val b = KeepAliveConfigBuilder(keepAlive).apply(block)
        keepAlive = b.toConfig()
    }

    public fun lifecycle(block: LifecycleConfigBuilder.() -> Unit) {
        val b = LifecycleConfigBuilder(
            reconnectPolicy,
            backgroundPolicy,
            appKilledPolicy,
            networkPathObserver
        ).apply(block)
        reconnectPolicy = b.reconnectPolicy
        backgroundPolicy = b.onBackground
        appKilledPolicy = b.onAppKilled
        networkPathObserver = b.networkPathObserver
    }

    public fun security(block: SecurityConfigBuilder.() -> Unit) {
        val b = SecurityConfigBuilder(securityMode).apply(block)
        securityMode = b.mode
    }

    public fun networkProvisioning(block: NetworkProvisioningConfigBuilder.() -> Unit) {
        val b = NetworkProvisioningConfigBuilder(networkProvisioning).apply(block)
        networkProvisioning = b.toConfig()
        networkProvisioningFactory = b.factory
    }

    /**
     * Configure the file-transfer subsystem. See [FileTransferConfig] for
     * available knobs (max file size, chunk size, offer timeout).
     */
    public fun fileTransfer(block: FileTransferConfigBuilder.() -> Unit) {
        val b = FileTransferConfigBuilder(fileTransfer).apply(block)
        fileTransfer = b.toConfig()
    }

    internal fun build(): P2pKit {
        val resolvedAppId = appId ?: error("appId must be set on the P2pKit builder")
        val resolvedName = deviceName ?: error("deviceName must be set on the P2pKit builder")
        validateWireText(
            resolvedName,
            "deviceName",
            HelloPayload.MAX_FIELD_LEN,
            HelloPayload.MAX_FIELD_UTF8_BYTES,
            requireNonBlank = true
        )
        check(transportsBuilder.registrations.isNotEmpty()) {
            "At least one transport must be registered (e.g. transports { lan() })"
        }
        return newP2pKit(
            appId = resolvedAppId,
            deviceName = resolvedName,
            transportFactories = transportsBuilder.registrations.toList(),
            keepAlive = keepAlive,
            reconnectPolicy = reconnectPolicy,
            backgroundPolicy = backgroundPolicy,
            appKilledPolicy = appKilledPolicy,
            securityMode = securityMode,
            provisioningConfig = networkProvisioning,
            provisioningFactory = networkProvisioningFactory,
            fileTransferConfig = fileTransfer,
            logger = logger,
            peerIdStorageOverride = peerIdStorage,
            secureIdentityStorageOverride = secureIdentityStorage,
            networkPathObserverOverride = networkPathObserver,
            permissionManagerOverride = permissionManager,
            strictSessionInvariants = strictSessionInvariants,
            sessionSetupTimeoutMillis = sessionSetupTimeoutMillis,
            beforeSessionCommitForTest = beforeSessionCommitForTest,
            afterOutgoingConnectForTest = afterOutgoingConnectForTest,
            afterSessionSetupResultForTest = afterSessionSetupResultForTest,
            discoveryRefreshTimeoutMillis = discoveryRefreshTimeoutMillisForTest,
            featureOperationSettleTimeoutMillis = featureOperationSettleTimeoutMillisForTest,
            beforeTerminalWatcherRemovalForTest = beforeTerminalWatcherRemovalForTest
        )
    }
}

@P2pKitDsl
public class TransportsBuilder internal constructor() {

    internal val registrations: MutableList<RegisteredTransportFactory> = mutableListOf()

    /**
     * Register a transport after validating its static descriptor. Duplicate
     * kinds are rejected before any factory can allocate a resource.
     */
    public fun register(factory: TransportFactory) {
        require(registrations.none { it.factory === factory }) {
            "The same TransportFactory instance cannot be registered more than once"
        }
        val descriptor = factory.descriptor
        require(registrations.none { it.descriptor.kind == descriptor.kind }) {
            "Transport kind ${descriptor.kind} is already registered"
        }
        registrations += RegisteredTransportFactory(factory, descriptor)
    }
}

@P2pKitDsl
public class KeepAliveConfigBuilder internal constructor(initial: KeepAliveConfig) {
    public var pingIntervalMillis: Long = initial.pingIntervalMillis
    public var timeoutMillis: Long = initial.timeoutMillis

    internal fun toConfig(): KeepAliveConfig = KeepAliveConfig(pingIntervalMillis, timeoutMillis)
}

@P2pKitDsl
public class LifecycleConfigBuilder internal constructor(
    public var reconnectPolicy: ReconnectPolicy,
    public var onBackground: BackgroundPolicy,
    public var onAppKilled: AppKilledPolicy,
    /**
     * Host-provided override for the network path observer. When `null`,
     * the kit uses the platform default — iOS gets a real `nw_path_monitor`
     * observer; JVM and Android default to no-op.
     *
     * On Android, host apps that want network-recovery behavior construct
     * `AndroidNetworkPathObserver(applicationContext)` here:
     *
     * ```kotlin
     * lifecycle {
     *     reconnectPolicy = ReconnectPolicy.Enabled(maxAttempts = 8, retryDelayMillis = 500)
     *     networkPathObserver = AndroidNetworkPathObserver(applicationContext)
     * }
     * ```
     */
    public var networkPathObserver: NetworkPathObserver?
)

@P2pKitDsl
public class SecurityConfigBuilder internal constructor(public var mode: SecurityMode)

@P2pKitDsl
public class FileTransferConfigBuilder internal constructor(initial: FileTransferConfig) {
    public var maxFileSizeBytes: Long = initial.maxFileSizeBytes
    public var chunkSizeBytes: Int = initial.chunkSizeBytes
    public var offerTimeoutMillis: Long = initial.offerTimeoutMillis

    internal fun toConfig(): FileTransferConfig =
        FileTransferConfig(maxFileSizeBytes, chunkSizeBytes, offerTimeoutMillis)
}

@P2pKitDsl
public class NetworkProvisioningConfigBuilder internal constructor(initial: NetworkProvisioningConfig) {
    public var enableLocalHotspot: Boolean = initial.enableLocalHotspot
    public var enableWifiJoin: Boolean = initial.enableWifiJoin
    public var enableManualIpFallback: Boolean = initial.enableManualIpFallback

    /**
     * Platform-module hook. Provisioning modules expose extension helpers
     * (e.g. `jvm()`, `android(context)`) that call this. When no factory is
     * registered, the kit uses
     * [dev.p2pkit.core.provisioning.UnsupportedNetworkProvisioningManager].
     */
    public fun register(factory: NetworkProvisioningFactory) {
        this.factory = factory
    }

    internal var factory: NetworkProvisioningFactory? = null

    internal fun toConfig(): NetworkProvisioningConfig =
        NetworkProvisioningConfig(enableLocalHotspot, enableWifiJoin, enableManualIpFallback)
}
