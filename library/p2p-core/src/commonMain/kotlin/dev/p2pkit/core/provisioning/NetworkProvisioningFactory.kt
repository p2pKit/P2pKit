package dev.p2pkit.core.provisioning

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import kotlinx.coroutines.Job

/**
 * Constructs a platform-specific [NetworkProvisioningManager] when the
 * `P2pKit.create { networkProvisioning { … } }` DSL block registers one.
 *
 * Platform modules (`:p2p-network-provisioning-desktop`,
 * `:p2p-network-provisioning-android`) provide a `NetworkProvisioningFactory`
 * and a DSL helper that registers it; the kit dispatches to that factory
 * during construction.
 *
 * When no factory is registered, the kit falls back to
 * [UnsupportedNetworkProvisioningManager].
 */
public interface NetworkProvisioningFactory {
    public fun build(context: ProvisioningContext): NetworkProvisioningManager
}

/**
 * Context handed to [NetworkProvisioningFactory.build] so a platform manager
 * can be built without inspecting the kit's internals.
 *
 * - [appId], [localPeerId], [localDeviceName] mirror the kit's identity.
 * - [config] passes advisory capability hints to the factory. Bundled
 *   managers do not enforce these flags; custom factories must document
 *   any effect they give them. See [NetworkProvisioningConfig].
 * - [logger] is the kit's logger; managers should route their own diagnostics
 *   through it.
 * - [lanTcpPort] is a provider lambda that returns the **current** bound
 *   TCP port of the LAN data transport, or `null` when the transport hasn't
 *   bound yet (before [dev.p2pkit.core.P2pKit.start]) or no LAN transport
 *   is registered. Implementations should call it each time they need the
 *   port, not capture the value at construction — since the v0.3 transport
 *   lifecycle refactor the bind happens lazily, so the captured value at
 *   factory-build time would be `null` even when the bind succeeds later.
 * - [manualPeerRegistrar] is the hook a manager uses inside
 *   [NetworkProvisioningManager.createManualPeer] to inject a synthetic
 *   peer into the kit's `PeerRegistry`.
 *
 * Constructor is `public` so factories and tests in other Gradle modules
 * can construct one directly; production callers should not — `P2pKitImpl`
 * builds these for registered factories.
 */
@OptIn(ExperimentalP2pApi::class)
public class ProvisioningContext public constructor(
    public val appId: AppId,
    public val localPeerId: PeerId,
    public val localDeviceName: String,
    public val config: NetworkProvisioningConfig,
    public val logger: P2pLogger,
    public val lanTcpPort: () -> Int?,
    public val manualPeerRegistrar: ManualPeerRegistrar,
    /** Local v2 fingerprint, or `null` for explicit legacy plaintext mode. */
    public val localFingerprint: PeerFingerprint? = null,
    /**
     * Canonical local [dev.p2pkit.core.PeerPairingQr] text bound to [appId],
     * or `null` in legacy mode when populated by the kit. Direct constructor
     * calls carry this text unchanged and do not validate it.
     */
    public val localPairingQr: String? = null,
    /**
     * Parent [Job] the manager should attach its scope to so the kit's
     * `stop()` automatically tears the manager down (cancels callbacks,
     * releases hotspot reservations, unbinds
     * `android.net.ConnectivityManager.bindProcessToNetwork`
     * on Android, etc.). `null` if no parent is available — managers fall
     * back to a free-standing scope, in which case the host is responsible
     * for explicit cleanup.
     */
    public val parentJob: Job? = null
)
