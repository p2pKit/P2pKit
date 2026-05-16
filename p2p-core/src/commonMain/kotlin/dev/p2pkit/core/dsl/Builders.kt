package dev.p2pkit.core.dsl

import dev.p2pkit.core.AppId
import dev.p2pkit.core.AppKilledPolicy
import dev.p2pkit.core.BackgroundPolicy
import dev.p2pkit.core.KeepAliveConfig
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.internal.PeerIdStorage
import dev.p2pkit.core.internal.newP2pKit
import dev.p2pkit.core.provisioning.NetworkProvisioningConfig
import dev.p2pkit.core.provisioning.NetworkProvisioningFactory
import dev.p2pkit.core.transfer.FileTransferConfig
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
    internal var securityMode: SecurityMode = SecurityMode.NoneForMvp
    internal var networkProvisioning: NetworkProvisioningConfig = NetworkProvisioningConfig()
    internal var networkProvisioningFactory: NetworkProvisioningFactory? = null
    internal var fileTransfer: FileTransferConfig = FileTransferConfig()

    /**
     * Override the [PeerIdStorage] the kit uses. **Internal** — set from
     * tests or from advanced internal code only. When `null`, the kit calls
     * [dev.p2pkit.core.internal.defaultPeerIdStorage] which selects a
     * platform-appropriate file-based store (or in-memory on Android if
     * `P2pKitAndroid.initialize(context)` wasn't called).
     */
    internal var peerIdStorage: PeerIdStorage? = null

    public fun transports(block: TransportsBuilder.() -> Unit) {
        transportsBuilder.apply(block)
    }

    public fun keepAlive(block: KeepAliveConfigBuilder.() -> Unit) {
        val b = KeepAliveConfigBuilder(keepAlive).apply(block)
        keepAlive = b.toConfig()
    }

    public fun lifecycle(block: LifecycleConfigBuilder.() -> Unit) {
        val b = LifecycleConfigBuilder(reconnectPolicy, backgroundPolicy, appKilledPolicy).apply(block)
        reconnectPolicy = b.reconnectPolicy
        backgroundPolicy = b.onBackground
        appKilledPolicy = b.onAppKilled
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
        check(transportsBuilder.factories.isNotEmpty()) {
            "At least one transport must be registered (e.g. transports { lan() })"
        }
        return newP2pKit(
            appId = resolvedAppId,
            deviceName = resolvedName,
            transportFactories = transportsBuilder.factories.toList(),
            keepAlive = keepAlive,
            reconnectPolicy = reconnectPolicy,
            backgroundPolicy = backgroundPolicy,
            appKilledPolicy = appKilledPolicy,
            securityMode = securityMode,
            provisioningConfig = networkProvisioning,
            provisioningFactory = networkProvisioningFactory,
            fileTransferConfig = fileTransfer,
            logger = logger,
            peerIdStorageOverride = peerIdStorage
        )
    }
}

@P2pKitDsl
public class TransportsBuilder internal constructor() {

    internal val factories: MutableList<TransportFactory> = mutableListOf()

    /** Register a transport. Transport modules expose extension helpers (e.g. `lan()`). */
    public fun register(factory: TransportFactory) {
        factories.add(factory)
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
    public var onAppKilled: AppKilledPolicy
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
