package dev.p2pkit.core

import dev.p2pkit.core.dsl.P2pKitBuilder
import dev.p2pkit.core.permission.P2pPermissionManager
import dev.p2pkit.core.provisioning.NetworkProvisioningManager
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow

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
     * Stable identity of this device for the current [appId]. Persists across
     * process restarts on platforms that ship a default [dev.p2pkit.core.internal.PeerIdStorage]
     * (JVM, Android with `P2pKitAndroid.initialize(context)`, iOS via
     * `NSUserDefaults`). Other peers will recognise the same device by this id.
     *
     * The id is intentionally exposed read-only — apps should never construct
     * or override it directly. Test apps display this to verify persistence;
     * production apps may include it in support logs.
     */
    public val localPeerId: PeerId

    /** Global lifecycle of this P2pKit instance. */
    public val state: StateFlow<P2pState>

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
     *   - Android: host-provided `AndroidNetworkPathObserver(ctx)`, which
     *     listens to `ConnectivityManager.NetworkCallback`. Without that
     *     override the value stays [NetworkPathStatus.Unknown].
     *   - JVM desktop: defaults to [NetworkPathStatus.Unknown] unless the
     *     host app supplies a custom observer.
     *
     * Useful for the host app's UI ("offline" banner). Internally the SDK
     * uses the same flow to drive reconnect on path-recovered (see
     * [dev.p2pkit.core.internal.SessionManager.applyPathChange]).
     */
    public val networkPathStatus: StateFlow<NetworkPathStatus>

    /**
     * Bring up all registered transports and provisioning sidecar. Optional
     * to call — if the host app skips it, [startAdvertising], [startDiscovery],
     * and [connect] each lazily ensure the kit is started on their first
     * invocation. Calling `start()` explicitly is preferable because it
     * surfaces a typed [P2pError.TransportStartFailed] at a single,
     * predictable call site instead of inside the first lifecycle method.
     *
     * Idempotent: subsequent calls after a successful start return without
     * re-binding. After a failed start, the next call retries.
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

    @Throws(Exception::class)
    public suspend fun startAdvertising()
    @Throws(Exception::class)
    public suspend fun stopAdvertising()

    @Throws(Exception::class)
    public suspend fun startDiscovery()
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
     * @throws P2pError.ConnectionFailed if the underlying connection fails
     */
    @Throws(Exception::class)
    public suspend fun connect(peer: Peer): P2pSession

    /** Last time the peer with [peerId] was observed by discovery, in epoch milliseconds. */
    public fun lastSeen(peerId: PeerId): Long?

    /** Notify the SDK that the host app moved to the background. Applies the configured policy. */
    public fun notifyAppBackgrounded()

    /** Notify the SDK that the host app returned to the foreground. */
    public fun notifyAppForegrounded()

    @Throws(Exception::class)
    public suspend fun stop()

    public companion object {
        /**
         * Build a P2pKit instance from a DSL block. See [P2pKitBuilder] for
         * the available configuration knobs.
         *
         * Construction performs a one-time, small-file identity read/write on
         * the calling thread (loading or generating the persistent
         * [localPeerId]) — construct off the main thread on Android to avoid
         * a first-launch stall (decision #5a, 2026-07-04; async/suspending
         * construction is a recorded backlog item in
         * `docs/production-readiness.md`).
         *
         * The implementation is provided by `dev.p2pkit.core.internal.P2pKitImpl`.
         */
        public fun create(block: P2pKitBuilder.() -> Unit): P2pKit {
            val builder = P2pKitBuilder().apply(block)
            return builder.build()
        }
    }
}
