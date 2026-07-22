@file:OptIn(ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.HasLocalTcpEndpoint
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import kotlin.concurrent.Volatile
import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.cancelChildren
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeout
import dev.p2pkit.transport.lan.interop.p2pkit_nw_create_plain_tcp_parameters
import platform.Foundation.NSNotification
import platform.Foundation.NSNotificationCenter
import platform.Network.nw_connection_create
import platform.Network.nw_endpoint_create_host
import platform.Network.nw_endpoint_t
import platform.Network.nw_listener_cancel
import platform.Network.nw_listener_create
import platform.Network.nw_listener_get_port
import platform.Network.nw_listener_set_new_connection_handler
import platform.Network.nw_listener_set_queue
import platform.Network.nw_listener_set_state_changed_handler
import platform.Network.nw_listener_start
import platform.Network.nw_listener_state_cancelled
import platform.Network.nw_listener_state_failed
import platform.Network.nw_listener_state_ready
import platform.Network.nw_listener_t
import platform.Network.nw_parameters_prohibit_interface_type
import platform.Network.nw_parameters_t
import platform.Network.nw_interface_type_cellular
import platform.Network.nw_interface_type_wifi
import platform.Network.nw_interface_type_wired
import platform.Network.nw_path_get_status
import platform.Network.nw_path_monitor_cancel
import platform.Network.nw_path_monitor_create
import platform.Network.nw_path_monitor_set_queue
import platform.Network.nw_path_monitor_set_update_handler
import platform.Network.nw_path_monitor_start
import platform.Network.nw_path_monitor_t
import platform.Network.nw_path_status_satisfied
import platform.Network.nw_path_uses_interface_type
import platform.UIKit.UIApplicationWillEnterForegroundNotification
import platform.darwin.DISPATCH_TIME_NOW
import platform.darwin.NSObjectProtocol
import platform.darwin.NSEC_PER_SEC
import platform.darwin.dispatch_queue_create
import platform.darwin.dispatch_queue_t
import platform.darwin.dispatch_semaphore_create
import platform.darwin.dispatch_semaphore_signal
import platform.darwin.dispatch_semaphore_wait
import platform.darwin.dispatch_time

/**
 * iOS LAN [DataTransport].
 *
 * Owns one `nw_listener_t` bound to an OS-chosen ephemeral TCP port for
 * inbound connections. Outbound `connect(peer)` looks the peer's resolved
 * `nw_endpoint_t` up in [IosEndpointRegistry] (populated by
 * [IosLanDiscoveryTransport]) and builds an `nw_connection_t` to it.
 *
 * **Lifecycle (v0.3 refactor).** The listener bind no longer happens in
 * `init` — instead [start] is a `suspend` method that runs the
 * `nw_listener_start` + 5-second semaphore wait. A bind failure surfaces
 * as `Result.failure(IllegalStateException)`, which the kit wraps in
 * `P2pError.TransportStartFailed`. This replaces the v0.2 behaviour where
 * a port=0 outcome would `throw IllegalStateException` from `init` and
 * tear down the entire kit-construction call site (which, on iOS, was a
 * runtime panic because Kotlin/Native doesn't bridge un-`@Throws` exceptions
 * to ObjC).
 *
 * [start] is idempotent: after the first success subsequent calls return
 * `Result.success(Unit)` immediately. After a failure they retry — a port
 * that was unavailable a moment ago might be free now.
 */
internal class IosLanDataTransport(
    @Suppress("unused") private val transportContext: TransportContext,
    private val endpointRegistry: IosEndpointRegistry
) : DataTransport, HasLocalTcpEndpoint {

    override val type: TransportKind = TransportKind.LAN
    override val priority: Int = 100

    /** Serial queue for the listener and all connections it owns. */
    internal val queue: dispatch_queue_t =
        dispatch_queue_create("dev.p2pkit.lan.ios", null)

    /**
     * Non-TLS TCP parameters, matching the JVM/Android `Socket` wire format.
     * `SecurityMode.NoneForMvp` parity. Shared between listener and outbound
     * connections. Built lazily via [ensureParameters] in ObjC through the
     * [p2pkit_nw_create_plain_tcp_parameters] cinterop helper.
     *
     * Cellular is prohibited so the LAN listener never binds on a cellular-only
     * interface (which would advertise an Android-unreachable Bonjour port
     * during a Wi-Fi gap) and outbound dials never route over cellular. Closes
     * the v0.5 residual edge case where an iPhone with cellular ENABLED would
     * rotate its listener through an intermediate cellular-only port during a
     * Wi-Fi flap. Wired Ethernet remains permitted.
     *
     * AUDIT-2026-06: construction was previously an eager property initializer
     * that called `error()` when the cinterop helper returned null. A throw out
     * of a constructor crosses into ObjC at `P2pKit.create { }`, and because
     * Kotlin/Native cannot bridge an un-`@Throws` exception it panics the host
     * process. It is now created lazily so the failure surfaces as a typed
     * `Result.failure` / `P2pError` through [start] / [connect] instead.
     */
    private val _parameters = kotlin.concurrent.AtomicReference<nw_parameters_t>(null)

    /**
     * Lazily create (and cache) the shared TCP parameters. Returns `null` if the
     * cinterop helper fails — callers map that to a typed failure rather than a
     * process-killing throw. Normally created by [start] under [startMutex]
     * before any [connect]; a [connect] racing the very first [start] is
     * resolved by the compareAndSet below (AUDIT-2026-06 #20a) — exactly one
     * creation wins, so every listener and outbound connection shares ONE
     * params object. A losing racer's extra object is never assigned; it is a
     * K/N-managed ObjC reference the GC releases once it goes out of scope.
     */
    private fun ensureParameters(): nw_parameters_t {
        _parameters.value?.let { return it }
        val p = p2pkit_nw_create_plain_tcp_parameters() ?: run {
            IosLanDebug.log(
                "data",
                "ensureParameters: p2pkit_nw_create_plain_tcp_parameters returned NULL"
            )
            return null
        }
        nw_parameters_prohibit_interface_type(p, nw_interface_type_cellular)
        if (!_parameters.compareAndSet(null, p)) {
            IosLanDebug.log(
                "data",
                "ensureParameters: lost create race — dropping duplicate, using winner's params"
            )
            return _parameters.value
        }
        // Issue #3: these params back BOTH the listener and every outbound
        // connection, and they do NOT call nw_parameters_set_include_peer_to_peer.
        // The browser (IosLanDiscoveryTransport) DOES, so an AWDL-discovered peer
        // may be undialable with these params. Logged once (only the CAS winner
        // reaches this line) so the asymmetry is explicit in the trail.
        IosLanDebug.log(
            "data",
            "TCP params built: cellular=PROHIBITED, include_peer_to_peer=NOT_SET " +
                "(listener + outbound) — AWDL asymmetry vs browser (issue #3)"
        )
        return p
    }

    private val _tcpPort = MutableStateFlow<Int?>(null)
    override val tcpPort: StateFlow<Int?> = _tcpPort.asStateFlow()

    /**
     * Exposed for the discovery transport to attach an advertise descriptor.
     * Null until [start] succeeds. Reading from `nw_listener_set_advertise_descriptor`
     * before start would silently no-op, so [IosLanDiscoveryTransport]'s
     * `startAdvertising` is sequenced after `data.start()` via
     * `P2pKitImpl.ensureStarted`.
     */
    @Volatile
    internal var listener: nw_listener_t = null
        private set

    private val incomingChannel = Channel<RawConnection>(Channel.UNLIMITED)
    private val startMutex = Mutex()

    @Volatile
    private var closed: Boolean = false

    // ──────────────────────────────────────────────────────────────────
    // V0.4-IOS-LISTENER-REBIND: path-monitor state + rebind hooks.
    //
    // Apple's mDNSResponder reaps DNS-SD subscriptions tied to a dead
    // network interface after ~90s (`dnssd_clientstub DEFUNCT`), which
    // kills the NWBrowser and the listener's attached Bonjour advertise.
    // To prevent that, watch the network path with a dedicated
    // `nw_path_monitor_t` and, on a satisfied-after-change transition,
    // cancel-and-recreate the listener before the daemon subscriptions
    // expire. Discovery is notified via two suspend hooks to tear down
    // and rebuild its NWBrowser + re-attach its advertise descriptor.
    //
    // Lock ordering: rebindNow holds `startMutex`, then the hooks acquire
    // IosLanDiscoveryTransport.lock. Discovery never holds its own lock
    // while calling into data transport methods that acquire startMutex,
    // so no inversion is possible.
    // ──────────────────────────────────────────────────────────────────

    /** Serial queue dedicated to the rebind path monitor. */
    private val pathQueue: dispatch_queue_t =
        dispatch_queue_create("dev.p2pkit.lan.ios.path", null)

    @Volatile
    private var pathMonitor: nw_path_monitor_t = null

    /**
     * V0.4-IOS-FOREGROUND-REBIND: token returned by NSNotificationCenter
     * when we subscribe to `UIApplicationWillEnterForegroundNotification`.
     * Held so we can unregister cleanly in [close]. Non-null iff observer
     * is registered.
     *
     * Lifecycle-driven rebind is needed because the path-monitor signal
     * is insufficient on its own — iOS may invalidate `nw_listener_t` /
     * `nw_browser_t` during prolonged app suspension while the network
     * path itself remains "satisfied". No `becameSatisfied=true` event
     * fires on wake; our V0.4-IOS-LISTENER-REBIND trigger stays silent.
     * Subscribing to `WillEnterForeground` gives us the missing trigger.
     */
    @Volatile
    private var foregroundObserver: NSObjectProtocol? = null

    /**
     * Whether the most recent path observation was `satisfied`.
     * Read & written ONLY from the path-monitor update handler, which is
     * invoked serially on [pathQueue] (created with `null` attributes →
     * serial dispatch queue). The only cross-context write is
     * [stopPathMonitor]'s reset, sequenced AFTER `nw_path_monitor_cancel`
     * which prevents further handler invocations. `@Volatile` guarantees
     * memory visibility across that boundary; `synchronized` is not
     * available in Kotlin/Native.
     */
    @Volatile
    private var lastWasSatisfied: Boolean = false

    /** Has any path observation reported `satisfied` yet — used to skip first-signal rebind. */
    @Volatile
    private var hasEverObservedSatisfied: Boolean = false

    /**
     * V0.4-IOS-PATH-INTERFACE-CHANGE: 3-bit fingerprint of which
     * interface types are currently part of the satisfied path:
     *
     *   bit 0 = Wi-Fi   (nw_interface_type_wifi)
     *   bit 1 = cellular (nw_interface_type_cellular)
     *   bit 2 = wired   (nw_interface_type_wired)
     *
     * Sentinel `-1` = never observed (used to skip first-signal rebind,
     * paralleling [hasEverObservedSatisfied]). Required because Apple's
     * `nw_path_status` stays `satisfied` when Wi-Fi flaps with cellular
     * fallback available — the satisfaction bit doesn't change but the
     * interface set does, and our LAN listener/browser are bound to
     * whatever interface was active at registration. When the active
     * interface set changes, the SDK must re-register on the new one.
     *
     * Read/written only from the path-monitor update handler (serial on
     * [pathQueue]). The only cross-context write is [stopPathMonitor]'s
     * reset, sequenced after `nw_path_monitor_cancel`; `@Volatile`
     * guarantees visibility across that boundary.
     */
    @Volatile
    private var lastInterfaceFingerprint: Int = -1

    /**
     * Scope for the debounced rebind coroutine. SupervisorJob so one
     * failed rebind cycle does not poison the scope for future rebinds.
     */
    private val rebindScope: CoroutineScope =
        CoroutineScope(SupervisorJob() + Dispatchers.Default)

    /** Most recent debounced rebind job; cancelled when superseded. */
    private var pendingRebindJob: Job? = null

    /**
     * Hook fired by [rebindNow] BEFORE the old listener is cancelled.
     * The discovery transport uses this to cancel its NWBrowser and
     * capture state (was-browsing flag) that the after-hook needs.
     * Wired by [IosLanDiscoveryTransport]'s `init` block.
     */
    internal var beforeListenerRebind: (suspend () -> Unit)? = null

    /**
     * Hook fired by [rebindNow] AFTER a fresh listener has reached
     * `ready` and [listener] has been re-assigned. Receives the new
     * listener so discovery can re-attach its advertise descriptor and
     * recreate its NWBrowser on top of it. Wired by
     * [IosLanDiscoveryTransport]'s `init` block.
     *
     * Not invoked when listener rebuild fails — discovery has nothing to
     * attach to in that case and we leave the transport in a degraded
     * state (listener=null) until the next path event or explicit retry.
     */
    internal var afterListenerRebind: (suspend (newListener: nw_listener_t) -> Unit)? = null

    override suspend fun start(): Result<Unit> = startMutex.withLock {
        if (listener != null) {
            IosLanDebug.log("data", "start: already started (port=${_tcpPort.value})")
            return Result.success(Unit)
        }
        if (closed) {
            IosLanDebug.log("data", "start: refused (transport already closed)")
            return Result.failure(IllegalStateException("transport already closed"))
        }
        if (ensureParameters() == null) {
            IosLanDebug.log("data", "start: refused (TCP parameters unavailable)")
            return Result.failure(
                IllegalStateException(
                    "iOS LAN TCP parameters unavailable " +
                        "(p2pkit_nw_create_plain_tcp_parameters returned null)"
                )
            )
        }
        val l = buildListener() ?: return Result.failure(
            IllegalStateException(
                "iOS LAN listener failed to bind a TCP port within 5 s " +
                    "(tcpPort=0 after nw_listener_start)"
            )
        )
        listener = l
        IosLanDebug.log("data", "start: SUCCESS port=${_tcpPort.value}")
        startPathMonitor()
        startForegroundObserver()
        return Result.success(Unit)
    }

    /**
     * Create and bind a fresh `nw_listener_t`. Sets [_tcpPort] as a side
     * effect on success and returns the listener in `ready` state. Returns
     * `null` if the bind fails (semaphore timeout or `.failed` state) —
     * caller decides whether to surface that as a fatal error
     * ([start]) or a degraded state ([rebindNow]).
     *
     * Caller is responsible for assigning the result to [listener].
     */
    private fun buildListener(): nw_listener_t {
        IosLanDebug.log("data", "buildListener: nw_listener_create")
        val params = ensureParameters() ?: run {
            IosLanDebug.log(
                "data",
                "buildListener: TCP parameters unavailable (cinterop helper returned null)"
            )
            return null
        }
        val l = nw_listener_create(params)
            ?: run {
                IosLanDebug.log("data", "buildListener: nw_listener_create returned NULL")
                return null
            }

        nw_listener_set_queue(l, queue)
        IosLanDebug.log("data", "buildListener: queue attached, wiring handlers")

        nw_listener_set_new_connection_handler(l) { conn ->
            if (conn != null && !closed) {
                IosLanDebug.log("data", "listener: accepted inbound nw_connection")
                val raw = IosRawConnection.wrap(conn, queue)
                val sent = incomingChannel.trySend(raw).isSuccess
                if (!sent) {
                    // AUDIT-2026-06 (#20b): wrap() already STARTED the
                    // connection; the only way the UNLIMITED channel refuses
                    // it is a concurrent close() having closed the channel
                    // after the `closed` check above. Dropping the wrapper
                    // without cancelling would leak the started nw_connection.
                    // cancelNow is the non-suspend close — this handler runs
                    // on the libdispatch queue and must return quickly
                    // without suspending.
                    raw.cancelNow("inbound dropped (incoming channel refused)")
                }
                IosLanDebug.log(
                    "data",
                    "listener: handed connection to incoming channel (queued=$sent)"
                )
            } else {
                IosLanDebug.log(
                    "data",
                    "listener: ignored inbound nw_connection (conn=${conn != null} closed=$closed)"
                )
            }
            // Force Unit return — without this, Kotlin/Native infers the
            // lambda type from trySend()'s ChannelResult and bridges it to
            // an id-returning ObjC block, which libdispatch crashes on.
            Unit
        }

        val ready = dispatch_semaphore_create(0)
        nw_listener_set_state_changed_handler(l) { state, _ ->
            val label = when (state) {
                nw_listener_state_ready -> "ready"
                nw_listener_state_failed -> "failed"
                nw_listener_state_cancelled -> "cancelled"
                else -> "raw=$state"
            }
            IosLanDebug.log("data", "listener state -> $label")
            when (state) {
                nw_listener_state_ready,
                nw_listener_state_failed,
                nw_listener_state_cancelled -> {
                    dispatch_semaphore_signal(ready)
                }
            }
            Unit
        }

        IosLanDebug.log("data", "buildListener: nw_listener_start (waiting up to 5s for .ready)")
        nw_listener_start(l)
        val deadline = dispatch_time(DISPATCH_TIME_NOW, (5L * NSEC_PER_SEC.toLong()))
        dispatch_semaphore_wait(ready, deadline)
        val port = nw_listener_get_port(l).toInt()
        if (port == 0) {
            IosLanDebug.log("data", "buildListener: port=0 (semaphore timeout or .failed) — cancelling listener")
            nw_listener_cancel(l)
            _tcpPort.value = null
            return null
        }
        _tcpPort.value = port
        IosLanDebug.log("data", "buildListener: SUCCESS port=$port")
        return l
    }

    override fun canConnect(peer: InternalPeer): Boolean {
        if (endpointRegistry.get(peer.publicPeer.id) != null) return true
        // Manual-IP fallback: peers registered via ManualPeerRegistrar
        // carry a TransportHint(LAN, host, port) that we can dial directly,
        // mirroring how JvmLanDataTransport handles them.
        return peer.transportHints.any {
            it.type == TransportKind.LAN && !it.host.isNullOrBlank() && (it.port ?: 0) > 0
        }
    }

    override suspend fun connect(peer: InternalPeer): RawConnection {
        val pid8 = peer.publicPeer.id.value.take(8)
        val cached = endpointRegistry.get(peer.publicPeer.id)
        IosLanDebug.log(
            "connect",
            "begin peer=$pid8 name=${peer.publicPeer.name} cachedEndpoint=${cached != null}"
        )
        val endpoint: nw_endpoint_t = cached
            ?: peer.transportHints.firstOrNull {
                it.type == TransportKind.LAN && !it.host.isNullOrBlank() && (it.port ?: 0) > 0
            }?.let { hint ->
                IosLanDebug.log(
                    "connect",
                    "manual-IP fallback peer=$pid8 host=${hint.host} port=${hint.port}"
                )
                nw_endpoint_create_host(hint.host!!, hint.port!!.toString())
            }
            ?: run {
                IosLanDebug.log("connect", "ABORT peer=$pid8 — no transport available (no cached endpoint, no manual-IP hint)")
                throw P2pError.NoTransportAvailable(peer.publicPeer)
            }
        val params = ensureParameters() ?: run {
            IosLanDebug.log(
                "connect",
                "ABORT peer=$pid8 — TCP parameters unavailable (cinterop helper returned null)"
            )
            throw P2pError.ConnectionFailed("iOS LAN TCP parameters unavailable")
        }
        // Issue #3: a `browse(AWDL-capable)` endpoint source + a dial that then
        // sits in `waiting` (see IosRawConnection conn-path lines) is the
        // signature of the AWDL asymmetry — the peer was found over peer-to-peer
        // but these connection params can't route there.
        IosLanDebug.log(
            "connect",
            "peer=$pid8 endpointSource=${if (cached != null) "browse(AWDL-capable)" else "manual-IP-hint"} " +
                "connParams.include_peer_to_peer=NOT_SET"
        )
        val conn = nw_connection_create(endpoint, params) ?: run {
            IosLanDebug.log("connect", "ABORT peer=$pid8 — nw_connection_create returned null")
            throw P2pError.ConnectionFailed("nw_connection_create returned null")
        }
        IosLanDebug.log("connect", "peer=$pid8 nw_connection_create OK, wrapping + awaiting Connected (<=${CONNECT_TIMEOUT_MILLIS}ms)")
        val raw = IosRawConnection.wrap(conn, queue)
        val terminal = try {
            withTimeout(CONNECT_TIMEOUT_MILLIS) {
                raw.state.first { it != ConnectionState.Connecting }
            }
        } catch (e: TimeoutCancellationException) {
            IosLanDebug.log("connect", "TIMEOUT peer=$pid8 after ${CONNECT_TIMEOUT_MILLIS}ms — closing wrapper")
            runCatching { raw.close() }
            throw P2pError.ConnectionFailed("iOS LAN connect timed out after ${CONNECT_TIMEOUT_MILLIS}ms")
        }
        if (terminal != ConnectionState.Connected) {
            IosLanDebug.log("connect", "FAILED peer=$pid8 terminal=$terminal (expected Connected)")
            throw P2pError.ConnectionFailed("iOS LAN connect failed (state=$terminal)")
        }
        IosLanDebug.log("connect", "SUCCESS peer=$pid8 raw connection in Connected state")
        return raw
    }

    override fun incomingConnections(): Flow<RawConnection> = incomingChannel.receiveAsFlow()

    override suspend fun close() {
        if (closed) return
        IosLanDebug.log("data", "close: cancelling path monitor, foreground observer, listener, and incoming channel")
        closed = true
        stopPathMonitor()
        stopForegroundObserver()
        rebindScope.coroutineContext.cancelChildren()
        listener?.let { nw_listener_cancel(it) }
        incomingChannel.close()
        endpointRegistry.clear()
    }

    // ──────────────────────────────────────────────────────────────────
    // V0.4-IOS-LISTENER-REBIND: path monitor + rebind cycle.
    // ──────────────────────────────────────────────────────────────────

    /**
     * Start an `nw_path_monitor_t` dedicated to driving the rebind cycle.
     * Idempotent. Called from [start] after the initial listener is bound.
     *
     * Update handler treats only a "satisfied AFTER a transition" as a
     * rebind trigger — the initial satisfied observation right after
     * startup is skipped because the listener was just bound against the
     * current path. Subsequent unsatisfied → satisfied transitions
     * (typical of Wi-Fi rotation / hotspot join) trigger a debounced rebind.
     */
    private fun startPathMonitor() {
        if (pathMonitor != null) return
        val m = nw_path_monitor_create() ?: run {
            IosLanDebug.log(
                "data",
                "startPathMonitor: nw_path_monitor_create returned NULL — no rebind on path changes"
            )
            return
        }
        nw_path_monitor_set_queue(m, pathQueue)
        nw_path_monitor_set_update_handler(m) { path ->
            // All invocations of this handler are serialized on pathQueue
            // (created as a serial dispatch queue). State reads/writes
            // below are safe without explicit synchronization; the
            // @Volatile annotations guarantee visibility against the
            // stopPathMonitor reset path which runs after
            // nw_path_monitor_cancel and therefore after the last handler
            // invocation.
            val status = nw_path_get_status(path)
            val isSatisfied = (status == nw_path_status_satisfied)
            val prevWasSatisfied = lastWasSatisfied
            val isFirstEver = !hasEverObservedSatisfied
            lastWasSatisfied = isSatisfied
            if (isSatisfied) hasEverObservedSatisfied = true
            val becameSatisfied = isSatisfied && !prevWasSatisfied

            // V0.4-IOS-PATH-INTERFACE-CHANGE: complementary trigger that
            // fires when the satisfied path's interface set changes
            // (Wi-Fi flap masked by cellular fallback — the satisfaction
            // bit never flips, but the LAN listener needs rebinding
            // because the underlying interface has changed).
            val usesWifi = nw_path_uses_interface_type(path, nw_interface_type_wifi)
            val usesCellular = nw_path_uses_interface_type(path, nw_interface_type_cellular)
            val usesWired = nw_path_uses_interface_type(path, nw_interface_type_wired)
            val fingerprint = (if (usesWifi) 1 else 0) or
                (if (usesCellular) 2 else 0) or
                (if (usesWired) 4 else 0)
            val prevFingerprint = lastInterfaceFingerprint
            val isFirstFingerprint = prevFingerprint == -1
            // Only update fingerprint while satisfied — if we're transiently
            // unsatisfied, we want to retain the last-known-good interface
            // set so the next "back to satisfied" comparison sees the real
            // pre-flap baseline, not a transient null state.
            if (isSatisfied) lastInterfaceFingerprint = fingerprint
            val interfaceChanged = isSatisfied &&
                !isFirstFingerprint &&
                prevFingerprint != fingerprint

            IosLanDebug.log(
                "data",
                "path-monitor: status=$status isSatisfied=$isSatisfied " +
                    "becameSatisfied=$becameSatisfied isFirst=$isFirstEver " +
                    "usesWifi=$usesWifi usesCellular=$usesCellular usesWired=$usesWired " +
                    "fingerprint=$fingerprint prev=$prevFingerprint " +
                    "interfaceChanged=$interfaceChanged"
            )

            when {
                becameSatisfied && !isFirstEver -> {
                    scheduleRebind("path satisfied after change (status=$status)")
                }
                interfaceChanged -> {
                    scheduleRebind(
                        "active interface set changed: $prevFingerprint -> $fingerprint " +
                            "(usesWifi=$usesWifi usesCellular=$usesCellular usesWired=$usesWired)"
                    )
                }
            }
            Unit
        }
        nw_path_monitor_start(m)
        pathMonitor = m
        IosLanDebug.log("data", "startPathMonitor: monitor started")
    }

    private fun stopPathMonitor() {
        val m = pathMonitor ?: return
        pathMonitor = null
        nw_path_monitor_cancel(m)
        pendingRebindJob?.cancel()
        pendingRebindJob = null
        // Safe to reset directly: nw_path_monitor_cancel above prevents
        // further handler invocations, and @Volatile guarantees visibility.
        lastWasSatisfied = false
        hasEverObservedSatisfied = false
        lastInterfaceFingerprint = -1
        IosLanDebug.log("data", "stopPathMonitor: monitor cancelled, pending rebind cleared")
    }

    /**
     * V0.4-IOS-FOREGROUND-REBIND: subscribe to
     * `UIApplicationWillEnterForegroundNotification`. On wake, schedule
     * a rebind via the existing [scheduleRebind] machinery — same
     * 800ms debounce, same cancel-and-recreate cycle as path-driven
     * rebinds.
     *
     * Idempotent: a second call while already subscribed is a no-op.
     * Notifications fire on the posting thread (main thread for UIKit
     * notifications); the callback only schedules — it does no I/O.
     */
    private fun startForegroundObserver() {
        if (foregroundObserver != null) return
        val token = NSNotificationCenter.defaultCenter.addObserverForName(
            name = UIApplicationWillEnterForegroundNotification,
            `object` = null,
            queue = null
        ) { _: NSNotification? ->
            IosLanDebug.log(
                "data",
                "foreground notification observed (UIApplicationWillEnterForeground)"
            )
            scheduleRebind("returning to foreground")
            Unit
        }
        foregroundObserver = token
        IosLanDebug.log(
            "data",
            "startForegroundObserver: registered for UIApplicationWillEnterForegroundNotification"
        )
    }

    private fun stopForegroundObserver() {
        val token = foregroundObserver ?: return
        foregroundObserver = null
        NSNotificationCenter.defaultCenter.removeObserver(token)
        IosLanDebug.log("data", "stopForegroundObserver: unregistered")
    }

    /**
     * Debounce-schedule a rebind. Each call cancels any pending job and
     * launches a fresh delay; back-to-back path callbacks during a single
     * physical rotation collapse into one actual rebind. Callbacks must
     * remain cheap and non-blocking — the lock + NSD/NWListener work all
     * happens inside [rebindNow].
     */
    private fun scheduleRebind(reason: String) {
        pendingRebindJob?.cancel()
        IosLanDebug.log(
            "data",
            "scheduleRebind: $reason (debounce=${REBIND_DEBOUNCE_MILLIS}ms)"
        )
        pendingRebindJob = rebindScope.launch {
            delay(REBIND_DEBOUNCE_MILLIS)
            rebindNow(reason)
        }
    }

    /**
     * Cancel-and-recreate cycle for the listener. Runs under [startMutex]
     * so it cannot race with [start] / [close]. Coordinates with
     * [IosLanDiscoveryTransport] via the two suspend hooks so the browser
     * is torn down before and the advertise descriptor is re-attached
     * after the listener is rebuilt.
     *
     * On rebuild failure: leaves [listener] = null and does NOT invoke
     * [afterListenerRebind] — discovery has nothing to attach to in that
     * case. The transport is in a degraded state recoverable on the next
     * path event or explicit [start] retry. The failure is logged with
     * a distinct signature so it is easy to distinguish from "rebuild
     * succeeded but discovery hook failed".
     */
    private suspend fun rebindNow(reason: String): Unit = startMutex.withLock {
        if (closed) {
            IosLanDebug.log("data", "rebindNow: transport closed; skipping ($reason)")
            return@withLock
        }
        val old = listener ?: run {
            IosLanDebug.log("data", "rebindNow: no listener to rebind; skipping ($reason)")
            return@withLock
        }
        val oldPort = _tcpPort.value
        IosLanDebug.log("data", "rebindNow: starting ($reason) oldPort=$oldPort")

        runCatching { beforeListenerRebind?.invoke() }
            .onSuccess {
                IosLanDebug.log("data", "rebindNow: beforeListenerRebind hook complete")
            }
            .onFailure { e ->
                IosLanDebug.log(
                    "data",
                    "rebindNow: beforeListenerRebind hook FAILED: ${e.message ?: e::class.simpleName}"
                )
            }

        nw_listener_cancel(old)
        listener = null
        _tcpPort.value = null
        IosLanDebug.log("data", "rebindNow: old listener cancelled (oldPort=$oldPort)")

        val fresh = buildListener()
        if (fresh == null) {
            IosLanDebug.log(
                "data",
                "rebindNow: REBUILD FAILED — listener stays null, afterListenerRebind NOT invoked ($reason)"
            )
            return@withLock
        }
        // close() does not take startMutex (it must stay non-blocking even
        // while a rebind is mid-flight), so re-check after the blocking
        // rebuild: without this a close() racing the 5s bind window left the
        // fresh listener bound and orphaned forever (AUDIT-2026-06 fix).
        if (closed) {
            IosLanDebug.log("data", "rebindNow: closed during rebuild — cancelling fresh listener ($reason)")
            nw_listener_cancel(fresh)
            return@withLock
        }
        listener = fresh
        val newPort = _tcpPort.value
        IosLanDebug.log("data", "rebindNow: new listener ready newPort=$newPort")

        runCatching { afterListenerRebind?.invoke(fresh) }
            .onSuccess {
                IosLanDebug.log(
                    "data",
                    "rebindNow: complete (port rotated: $oldPort -> $newPort)"
                )
            }
            .onFailure { e ->
                IosLanDebug.log(
                    "data",
                    "rebindNow: REBUILD OK but afterListenerRebind hook FAILED: " +
                        "${e.message ?: e::class.simpleName} (listener=$newPort, discovery degraded)"
                )
            }
    }

    internal companion object {
        /** Bounded outbound connect; LAN should resolve + handshake in << 10 s. */
        const val CONNECT_TIMEOUT_MILLIS: Long = 10_000

        /**
         * Debounce window for back-to-back path callbacks. Matches the
         * V0.4-NSD/V0.4-AP value for cross-platform symmetry — a single
         * Wi-Fi → hotspot transition typically emits multiple path events
         * within a few hundred ms; 800ms catches the burst while keeping
         * recovery latency bounded.
         */
        const val REBIND_DEBOUNCE_MILLIS: Long = 800
    }
}
