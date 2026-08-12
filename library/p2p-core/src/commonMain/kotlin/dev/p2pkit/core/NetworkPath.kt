package dev.p2pkit.core

import kotlinx.coroutines.flow.StateFlow

/**
 * Current reachability of the host device's default network path.
 *
 * Surfaced via [P2pKit.networkPathStatus] (and observed internally by
 * [SessionManager][dev.p2pkit.core.internal.SessionManager] when
 * [ReconnectPolicy.Enabled] is configured). Apps can also subscribe for
 * their own UI ("offline" banner, etc.).
 */
public sealed class NetworkPathStatus {
    /**
     * Initial value before [NetworkPathObserver.start] has reported anything,
     * or on a platform with no observer wired up (default JVM desktop). The
     * SDK does not act on this — it treats `Unknown` as "no information",
     * not "no network".
     */
    public data object Unknown : NetworkPathStatus()

    /**
     * The default network path is up and routable. On iOS this is
     * `nw_path_status_satisfied`; on Android it's the moment after
     * `NetworkCallback.onAvailable` fires for a Wi-Fi or Ethernet network
     * — upstream-internet status is irrelevant for LAN P2P, so hotspot
     * Wi-Fi without internet still counts as `Satisfied`.
     *
     * When the SDK observes a transition from `Unsatisfied` or `Unknown` to
     * `Satisfied`, sessions currently in `Reconnecting` get their pending
     * retry-loop delay woken so they attempt immediately instead of waiting
     * out the configured `retryDelayMillis`.
     */
    public data object Satisfied : NetworkPathStatus()

    /**
     * No usable default path. On iOS this is `nw_path_status_unsatisfied`
     * (typically Wi-Fi off, in-flight mode, or no carrier); on Android it's
     * after the last matching Wi-Fi/Ethernet network is lost (cellular
     * alone does not satisfy — see the Android network-path observer).
     *
     * When the SDK observes a transition into `Unsatisfied`, every session
     * in `Connected` is immediately routed to `onConnectionLost`. That
     * preserves the existing reconnect-vs-fail semantics:
     *   - [ReconnectPolicy.Enabled]: sessions go to `Reconnecting` and the
     *     retry loop kicks in.
     *   - [ReconnectPolicy.Disabled]: sessions go straight to `Failed`.
     */
    public data object Unsatisfied : NetworkPathStatus()
}

/**
 * Watches the host device's default network path and emits transitions to
 * [status]. Idempotent: implementations must be safe to [start] and [close]
 * multiple times. Calling `start()` while already attached is a no-op;
 * calling `start()` after [close] re-attaches the underlying OS monitor
 * (this is how the bundled iOS and Android implementations behave). Note
 * that [P2pKit.stop] closes the configured observer — including
 * host-provided instances — so an observer shared across kits will be
 * re-started by the next kit's lifecycle.
 *
 * **Platform impls:**
 *   - iOS: provided by default — uses `nw_path_monitor_t` on a serial
 *     dispatch queue. Wired automatically by [P2pKit.create]. Apps do not
 *     need to construct one unless they want to override.
 *   - Android: `P2pKitAndroid.initialize(context)` supplies the application
 *     context used to construct the Android network-path observer by default.
 *     Without initialization, Android falls back to
 *     the no-op network-path observer. Apps can still override either default via
 *     the lifecycle DSL.
 *   - JVM desktop: defaults to the no-op network-path observer. There is no
 *     reliable cross-platform JDK API for network-path change events; if a
 *     desktop app wants this behaviour it can supply a custom observer
 *     (e.g., polling `NetworkInterface.getNetworkInterfaces()`).
 */
public interface NetworkPathObserver {
    /** Current network path status. Cold reads return [NetworkPathStatus.Unknown] before [start]. */
    public val status: StateFlow<NetworkPathStatus>

    /**
     * Begin reporting path-change events to [status]. Idempotent.
     *
     * Implementations should not throw — failures to attach the underlying
     * OS monitor should be logged and left as a permanent [NetworkPathStatus.Unknown]
     * stream, so the kit degrades to "no path observer" rather than
     * propagating an error through the kit lifecycle. If a host implementation
     * nevertheless throws, P2pKit calls [close] to settle any partial
     * acquisition. A successful cleanup degrades to no observer for that kit
     * session; an unsuccessful cleanup fails startup closed so a retry cannot
     * attach a second monitor over uncertain ownership.
     */
    public suspend fun start()

    /**
     * Detach the underlying OS monitor. Idempotent. A failed native detach
     * must retain cleanup ownership for a later retry and must not allow
     * [start] to attach a second monitor over the first one.
     */
    public suspend fun close()
}
