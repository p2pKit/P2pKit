package dev.p2pkit.core

import dev.p2pkit.core.dsl.P2pKitBuilder
import dev.p2pkit.core.permission.P2pPermissionManager
import dev.p2pkit.core.provisioning.NetworkProvisioningManager
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * P2pKit's entry point. Created via [create].
 *
 * The application surface is intentionally small: discover, connect, send,
 * receive, close. Transport selection, framing, chunking, reconnection, and
 * platform differences are all hidden.
 *
 * ### Typical use
 *
 * ```kotlin
 * val p2p = P2pKit.create {
 *     appId = AppId("com.example.transfer")
 *     deviceName = "My Phone"
 *     transports { lan() }
 * }
 *
 * val scope = CoroutineScope(Dispatchers.Default + SupervisorJob())
 *
 * scope.launch { p2p.startAdvertising(); p2p.startDiscovery() }
 *
 * p2p.peers
 *     .onEach { peers -> println("Current peers: $peers") }
 *     .launchIn(scope)
 *
 * p2p.incomingSessions
 *     .onEach { session ->
 *         session.incoming
 *             .onEach { msg -> println(msg) }
 *             .launchIn(scope)
 *     }
 *     .launchIn(scope)
 * ```
 *
 * Never use nested `collect { collect { ... } }` — always use `launchIn(scope)`.
 */
public interface P2pKit {

    /**
     * The [AppId] this kit was constructed with. Apps already know this
     * because they passed it into [create]; exposed here so a single
     * [P2pKit] reference is enough to render diagnostics, support logs, or
     * room-member rows without threading the original config around.
     */
    public val appId: AppId

    /**
     * The local device name this kit was constructed with — same string
     * advertised over discovery and sent in the HELLO handshake.
     */
    public val localDeviceName: String

    /**
     * Stable identity of this device for the current [appId]. In authenticated
     * v2 it is derived from the persistent secure key held by the platform
     * secure identity store. JVM hosts must inject a
     * `JvmSecureIdentityStore`; Android uses Keystore-wrapped no-backup
     * storage, and Apple uses a device-only Keychain item. Explicit legacy
     * mode continues to use the pre-v2 UUID storage.
     *
     * The id is intentionally exposed read-only — apps should never construct
     * or override it directly. Test apps display this to verify persistence;
     * production apps may include it in support logs. Resetting or losing the
     * secure key produces a different id and requires remote peers to re-pin.
     */
    public val localPeerId: PeerId

    /** Canonical local X25519 fingerprint in secure v2; null only in explicit legacy mode. */
    public val localFingerprint: PeerFingerprint?

    /** AppId-bound canonical pairing QR text in secure v2; null in legacy mode. */
    public val localPairingQr: String?

    /**
     * Parse and validate a pairing QR against this kit's exact AppId.
     * Returns null for malformed, non-canonical, other-AppId, or legacy input.
     */
    public fun parsePeerPairingQr(value: String): PeerFingerprint?

    /** Global lifecycle of this P2pKit instance. */
    public val state: StateFlow<P2pState>

    /**
     * Retained advertising state, independent from [state] and
     * [discoveryState]. The default keeps third-party mocks source-compatible
     * for one migration release; production implementations override it. The
     * returned flow is read-only even at runtime and cannot be cast back to a
     * [MutableStateFlow].
     */
    public val advertisingState: StateFlow<FeatureState>
        get() = idleFeatureState

    /**
     * Retained discovery state, independent from [state] and
     * [advertisingState]. The default keeps third-party mocks
     * source-compatible for one migration release; production implementations
     * override it. The returned flow is read-only even at runtime.
     */
    public val discoveryState: StateFlow<FeatureState>
        get() = idleFeatureState

    /**
     * Currently-known peers. Updated as discovery transports report Found,
     * Updated, and Lost events. Heartbeats alone do not trigger emissions;
     * use [lastSeen] for freshness.
     */
    public val peers: StateFlow<List<Peer>>

    /**
     * Inbound sessions accepted by data transports. Hot, buffered
     * `SharedFlow`; sessions are not silently dropped if subscribed
     * eagerly.
     */
    public val incomingSessions: SharedFlow<P2pSession>

    /** All currently active sessions, both outgoing and incoming. */
    public val sessions: StateFlow<List<P2pSession>>

    /** Reports required and missing runtime permissions. The library never requests permissions itself. */
    public val permissions: P2pPermissionManager

    /**
     * Optional sidecar for helping devices reach the same LAN. Returns the
     * `Unsupported` stub only when no provisioning factory is registered via
     * the `networkProvisioning { … }` DSL block. The optional platform
     * modules register real implementations: Android `LocalOnlyHotspot`
     * hosting + Wi-Fi join (`:p2p-network-provisioning-android`), JVM
     * manual-IP fallback (`:p2p-network-provisioning-desktop`), and iOS
     * manual-IP (`iosManualIp()` in `:p2p-transport-lan`). Hotspot hosting /
     * Wi-Fi join stay `Unsupported` on platforms whose OS forbids them (iOS).
     */
    public val networkProvisioning: NetworkProvisioningManager

    /**
     * Host device's default network path status. Driven by the configured
     * [NetworkPathObserver]:
     *   - iOS: real `nw_path_monitor` events (Wi-Fi / cellular / VPN
     *     transitions).
     *   - Android: `P2pKitAndroid.initialize(context)` installs the application
     *     context used by the default `AndroidNetworkPathObserver`; a lifecycle
     *     DSL override can supply one explicitly. Without either, the value
     *     stays [NetworkPathStatus.Unknown].
     *   - JVM desktop: defaults to [NetworkPathStatus.Unknown] unless the
     *     host app supplies a custom observer.
     *
     * Useful for the host app's UI ("offline" banner). Internally the SDK
     * uses the same flow to drive reconnect on path-recovered (see
     * [dev.p2pkit.core.internal.SessionManager.applyPathChange]).
     */
    public val networkPathStatus: StateFlow<NetworkPathStatus>

    /**
     * Bring up all registered data transports and the network-path observer.
     * The provisioning sidecar is constructed with the kit and has no separate
     * start phase. This is optional to call — if the host app skips it,
     * [startAdvertising], [startDiscovery],
     * and [connect] each lazily ensure the kit is started on their first
     * invocation. Calling `start()` explicitly is preferable because it
     * surfaces a typed [P2pError.TransportStartFailed] at a single,
     * predictable call site instead of inside the first lifecycle method.
     *
     * Idempotent: subsequent calls after a successful start return without
     * re-binding. After an ordinary failed start whose rollback completed, the
     * next call retries. If rollback itself fails or exceeds its deadline, the
     * instance fails closed: call [stop] and create a replacement instead of
     * risking a second listener over uncertain native ownership.
     *
     * @throws P2pError.TransportStartFailed if any registered transport's
     *   `start()` returned a failure (port exhaustion, missing entitlement,
     *   listener bind timeout, etc.).
     *
     * (The `@Throws(Exception::class)` annotation exists so Kotlin/Native
     * bridges thrown errors to a catchable Swift `NSError` instead of
     * terminating the process. Same reasoning applies to every other public
     * suspend method below.)
     */
    @Throws(Exception::class)
    public suspend fun start()

    /**
     * Start every declared advertising path. Concurrent calls coalesce and a
     * call while active is a no-op. Static absence publishes
     * [FeatureState.Unsupported] without starting the kit; missing runtime
     * permission publishes [FeatureState.PermissionRequired] and throws
     * [P2pError.PermissionMissing]. Other startup failures publish
     * [FeatureState.Failed] without changing [state].
     */
    @Throws(Exception::class)
    public suspend fun startAdvertising()

    /**
     * Stop every advertising path. A stop racing startup wins and rolls back
     * late resources. Successful and repeated stops reach
     * [FeatureState.Idle]; cleanup failures remain [FeatureState.Failed].
     */
    @Throws(Exception::class)
    public suspend fun stopAdvertising()

    /** Advertising-equivalent lifecycle contract for discovery paths. */
    @Throws(Exception::class)
    public suspend fun startDiscovery()

    /** Discovery-equivalent stop and rollback contract. */
    @Throws(Exception::class)
    public suspend fun stopDiscovery()

    /**
     * Open a session to [peer], or return the existing session if one is
     * already in `Connecting`, `Handshaking`, `Connected`, or `Reconnecting`.
     *
     * Note: `connect()` performs no permission check itself — runtime
     * permissions are verified by [startAdvertising] / [startDiscovery],
     * which surface [P2pError.PermissionMissing].
     *
     * @throws P2pError.NoTransportAvailable if no registered transport can reach [peer]
     * @throws P2pError.TransportStartFailed if lazy transport startup fails.
     * @throws P2pError.ConnectionFailed if the underlying connection fails
     *   or a transport provider fails while evaluating reachability.
     * @throws P2pError.SecurityConfigurationInvalid if the requested peer/pin
     *   cannot be authenticated under the configured security mode.
     * @throws P2pError.HandshakeRejected if the peer rejects the HELLO exchange.
     * @throws P2pError.AuthenticationFailed if secure-v2 authentication fails.
     * @throws P2pError.AuthorizationRejected if the authenticated key is not admitted.
     * @throws P2pError.AuthenticatedIdentityMismatch if the proved identity
     *   conflicts with the selected peer or expected fingerprint.
     * @throws P2pError.VersionMismatch if the peer uses an incompatible protocol major.
     * @throws IllegalStateException if [stop] has begun.
     */
    @Throws(Exception::class)
    public suspend fun connect(peer: Peer): P2pSession

    /**
     * Connect while requiring this exact out-of-band authenticated fingerprint.
     * Uses the same lifecycle and error contract as [connect].
     */
    @Throws(Exception::class)
    public suspend fun connect(
        peer: Peer,
        expectedFingerprint: PeerFingerprint
    ): P2pSession

    /** Last time the peer with [peerId] was observed by discovery, in epoch milliseconds. */
    public fun lastSeen(peerId: PeerId): Long?

    /** Notify the SDK that the host app moved to the background. Applies the configured policy. */
    public fun notifyAppBackgrounded()

    /** Notify the SDK that the host app returned to the foreground. */
    public fun notifyAppForegrounded()

    /**
     * Terminally stop the kit. Every resource receives a bounded cleanup
     * attempt and [state] reaches [P2pState.Stopped] even if cleanup fails.
     * Concurrent and later callers observe the same teardown result.
     *
     * @throws P2pError.ConnectionFailed after teardown when one or more
     *   resources failed or exceeded their close deadline.
     */
    @Throws(Exception::class)
    public suspend fun stop()

    public companion object {
        /**
         * Build a P2pKit instance from a DSL block. See [P2pKitBuilder] for
         * the available configuration knobs.
         *
         * Construction synchronously performs persistent identity storage and
         * cryptographic-provider work on the calling thread (including
         * Android Keystore or Apple Keychain access in secure mode). Construct
         * off the main/UI thread to avoid a first-launch or locked-store stall.
         *
         * The implementation is provided by `dev.p2pkit.core.internal.P2pKitImpl`.
         *
         * @throws IllegalStateException when a required builder field or
         *   transport registration is missing.
         * @throws IllegalArgumentException when configuration or advertised
         *   identity text violates its documented bounds.
         * @throws P2pError.LocalIdentityUnavailable when secure identity
         *   storage cannot safely load or create the local identity.
         * @throws P2pError.SecurityConfigurationInvalid when secure-v2
         *   configuration cannot be represented safely.
         * @throws P2pError.TransportInitializationFailed when a transport
         *   factory throws or contradicts its declared descriptor.
         */
        @Throws(Exception::class)
        public fun create(block: P2pKitBuilder.() -> Unit): P2pKit {
            val builder = P2pKitBuilder().apply(block)
            return builder.build()
        }
    }
}

private val idleFeatureState: StateFlow<FeatureState> =
    MutableStateFlow(FeatureState.Idle).asStateFlow()
