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
import kotlin.coroutines.resume
import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelChildren
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import dev.p2pkit.transport.lan.interop.p2pkit_nw_create_plain_tcp_parameters
import dev.p2pkit.transport.lan.interop.p2pkit_lan_interface_fingerprint
import platform.Foundation.NSNotification
import platform.Foundation.NSNotificationCenter
import platform.Foundation.NSLock
import platform.Network.nw_connection_create
import platform.Network.nw_connection_cancel
import platform.Network.nw_connection_t
import platform.Network.nw_endpoint_create_host
import platform.Network.nw_error_get_error_code
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
import platform.Network.nw_parameters_get_include_peer_to_peer
import platform.Network.nw_parameters_set_include_peer_to_peer
import platform.Network.nw_parameters_t
import platform.Network.nw_interface_type_cellular
import platform.Network.nw_interface_type_other
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
import platform.UIKit.UIApplicationDidBecomeActiveNotification
import platform.UIKit.UIApplicationWillEnterForegroundNotification
import platform.UIKit.UIApplicationWillResignActiveNotification
import platform.darwin.NSObjectProtocol
import platform.darwin.dispatch_queue_create
import platform.darwin.dispatch_queue_t

/**
 * iOS LAN [DataTransport].
 *
 * Owns one `nw_listener_t` bound to an OS-chosen ephemeral TCP port for
 * inbound connections. Outbound `connect(peer)` looks the peer's resolved
 * `nw_endpoint_t` up in [IosEndpointRegistry] (populated by
 * [IosLanDiscoveryTransport]) and builds an `nw_connection_t` to it.
 *
 * **Lifecycle (v0.3 refactor).** The listener bind no longer happens in
 * `init` — instead [start] is a `suspend` method that starts the listener
 * and cancellably awaits its ready callback. A bind failure surfaces
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
    private val endpointRegistry: IosEndpointRegistry,
    /** Test-only suspension point after native readiness but before ownership is committed. */
    private val listenerReadyBarrierForTest: suspend () -> Unit = {},
    /** Test seam for proving rejected, unstarted native connections are cancelled. */
    private val connectionRejector: (nw_connection_t) -> Unit = ::nw_connection_cancel,
    /** Test-only synchronization point inside the inbound admission transaction. */
    private val beforeInboundOfferForTest: (() -> Unit)? = null,
    /** Test-only signal immediately before stop/rebind acquires inbound ownership. */
    private val beforeInboundRetireForTest: (() -> Unit)? = null,
    /** Test-only synchronization point before a connected dial transfers ownership. */
    private val beforeDialOwnershipHandoffForTest: (() -> Unit)? = null,
    private val connectionFactory: (nw_connection_t, dispatch_queue_t) -> IosConnectionHandle =
        { connection, connectionQueue -> IosRawConnection.wrap(connection, connectionQueue) }
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
        nw_parameters_set_include_peer_to_peer(p, true)
        if (!_parameters.compareAndSet(null, p)) {
            IosLanDebug.log(
                "data",
                "ensureParameters: lost create race — dropping duplicate, using winner's params"
            )
            return _parameters.value
        }
        IosLanDebug.log(
            "data",
            "TCP params built: cellular=PROHIBITED, include_peer_to_peer=true " +
                "(listener + outbound)"
        )
        return p
    }

    internal fun parametersIncludePeerToPeerForTest(): Boolean =
        ensureParameters()?.let(::nw_parameters_get_include_peer_to_peer) == true

    private val _tcpPort = MutableStateFlow<Int?>(null)
    override val tcpPort: StateFlow<Int?> = _tcpPort.asStateFlow()

    /**
     * Exposed for the discovery transport to attach an advertise descriptor.
     * Null until [start] succeeds. Reading from `nw_listener_set_advertise_descriptor`
     * before start would silently no-op, so [IosLanDiscoveryTransport]'s
     * `startAdvertising` is sequenced after `data.start()` via
     * `P2pKitImpl.ensureStarted`.
     */
    /**
     * Owns both the native handle and its terminal acknowledgement. Merely
     * calling `nw_listener_cancel` does not release the descriptor
     * synchronously; close/rebind must wait for `.cancelled`/`.failed` before
     * considering ownership released.
     */
    private class ListenerLease(
        val handle: nw_listener_t,
        val terminated: CompletableDeferred<Unit> = CompletableDeferred()
    )

    @Volatile
    private var listenerLease: ListenerLease? = null

    /** Leases whose cancellation has not yet received a native terminal callback. */
    private val pendingListenerCleanups = mutableListOf<ListenerLease>()

    internal val listener: nw_listener_t
        get() = listenerLease?.handle

    private val incomingQueue = BoundedInboundQueue<IosConnectionHandle>(
        capacity = MAX_BUFFERED_INBOUND_CONNECTIONS,
        onDrop = { it.cancelNow("inbound admission rejected") }
    )
    private val inboundOwnershipLock = NSLock()
    private var inboundListenerOwner: nw_listener_t = null
    private val startMutex = Mutex()
    private val dialMutex = Mutex()
    private val pendingDials = mutableSetOf<IosConnectionHandle>()
    private var dialGeneration: Long = 0

    @Volatile
    private var closed: Boolean = false

    /** Host start intent, independent of whether a live listener is currently available. */
    @Volatile
    private var startedByHost: Boolean = false

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

    /** Callback authority for [pathMonitor], retired before native cancellation. */
    @Volatile
    private var pathMonitorOwner: ApplePathMonitorOwner? = null

    private val pathMonitorCallbackState = ApplePathMonitorCallbackState()

    /**
     * Tokens returned by NSNotificationCenter for the three UIKit lifecycle
     * signals coordinated by the current [AppleLifecycleRecoveryCoordinator].
     * Held so stop and close can unregister every callback deterministically.
     *
     * Lifecycle-driven rebind is needed because the path-monitor signal
     * is insufficient on its own — iOS may invalidate `nw_listener_t` /
     * `nw_browser_t` during prolonged app suspension while the network
     * path itself remains "satisfied". No `becameSatisfied=true` event
     * fires on wake; our V0.4-IOS-LISTENER-REBIND trigger stays silent.
     * `WillEnterForeground` covers background return; `DidBecomeActive`
     * covers inactive-foreground recovery after Control Center or a system
     * interruption. `WillResignActive` opens the episode that coalesces them.
     */
    @Volatile
    private var lifecycleObservers: List<NSObjectProtocol> = emptyList()

    /** A fresh coalescing owner is installed for every successful start. */
    @Volatile
    private var lifecycleRecoveryCoordinator: AppleLifecycleRecoveryCoordinator? = null

    /**
     * Scope for the debounced rebind coroutine. SupervisorJob so one
     * failed rebind cycle does not poison the scope for future rebinds.
     */
    private val rebindScope: CoroutineScope =
        CoroutineScope(SupervisorJob() + Dispatchers.Default)

    /** Most recent debounced rebind job; cancelled when superseded. */
    @Volatile
    private var pendingRebindJob: Job? = null

    /** Serializes job replacement across path, foreground, and listener callbacks. */
    private val rebindScheduleMutex = Mutex()

    /**
     * Hook fired by [rebindNow] BEFORE the old listener is cancelled.
     * The discovery transport uses this to cancel resources owned by the
     * retiring listener/path generation. Current host intent remains the
     * source of truth for the after-hook.
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
     * attach to in that case. A bounded self-retry continues while host
     * start intent remains active.
     */
    internal var afterListenerRebind: (suspend (newListener: nw_listener_t) -> Unit)? = null

    override suspend fun start(): Result<Unit> = startMutex.withLock {
        if (closed) {
            IosLanDebug.log("data", "start: refused (transport already closed)")
            return Result.failure(IllegalStateException("transport already closed"))
        }
        if (listener != null && startedByHost) {
            IosLanDebug.log("data", "start: already started (port=${_tcpPort.value})")
            return Result.success(Unit)
        }
        if (!releasePendingListeners("listener start retry")) {
            return Result.failure(
                IllegalStateException(
                    "previous iOS LAN listener ownership is still awaiting native cleanup"
                )
            )
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
                "iOS LAN listener failed to become ready within " +
                    "${LISTENER_READY_TIMEOUT_MILLIS}ms"
            )
        )
        listenerLease = l
        startedByHost = true
        publishInboundListener(l.handle)
        val lifecycleOwner = lifecycleRecoveryCoordinator
            ?: AppleLifecycleRecoveryCoordinator().also {
                lifecycleRecoveryCoordinator = it
            }
        lifecycleOwner.onSuccessfulRebind()
        IosLanDebug.log("data", "start: SUCCESS port=${_tcpPort.value}")
        startPathMonitor()
        startForegroundObserver(lifecycleOwner)
        return Result.success(Unit)
    }

    /**
     * Create and bind a fresh `nw_listener_t`. Sets [_tcpPort] as a side
     * effect on success and returns the listener in `ready` state. Returns
     * `null` if the bind fails (deadline or `.failed` state) —
     * caller decides whether to surface that as a fatal error
     * ([start]) or a degraded state ([rebindNow]).
     *
     * Caller is responsible for assigning the result to [listener].
     */
    private suspend fun buildListener(): ListenerLease? {
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
        val lease = ListenerLease(l)

        nw_listener_set_queue(l, queue)
        IosLanDebug.log("data", "buildListener: queue attached, wiring handlers")

        nw_listener_set_new_connection_handler(l) connectionHandler@ { conn ->
            handleInboundConnection(owner = l, connection = conn)
            return@connectionHandler
        }

        val readyListener = try {
            val candidate = withTimeoutOrNull(LISTENER_READY_TIMEOUT_MILLIS) {
                suspendCancellableCoroutine<ListenerLease?> { continuation ->
                    val readinessResolved = kotlin.concurrent.AtomicInt(0)
                    continuation.invokeOnCancellation {
                        readinessResolved.compareAndSet(0, 1)
                        _tcpPort.value = null
                        nw_listener_cancel(l)
                    }
                    nw_listener_set_state_changed_handler(l) listenerStateHandler@ { state, error ->
                        val label = when (state) {
                            nw_listener_state_ready -> "ready"
                            nw_listener_state_failed -> "failed"
                            nw_listener_state_cancelled -> "cancelled"
                            else -> "raw=$state"
                        }
                        val errorCode = error?.let { nw_error_get_error_code(it) }
                        IosLanDebug.log(
                            "data",
                            "listener state -> $label" +
                                (errorCode?.let { " errCode=$it" } ?: "")
                        )
                        when (state) {
                            nw_listener_state_ready -> {
                                val port = nw_listener_get_port(l).toInt()
                                if (port > 0 && readinessResolved.compareAndSet(0, 1)) {
                                    _tcpPort.value = port
                                    continuation.resume(lease)
                                } else if (port <= 0 && readinessResolved.compareAndSet(0, 1)) {
                                    continuation.resume(null)
                                }
                            }
                            nw_listener_state_failed,
                            nw_listener_state_cancelled -> {
                                lease.terminated.complete(Unit)
                                if (readinessResolved.compareAndSet(0, 1)) {
                                    continuation.resume(null)
                                }
                                nw_listener_set_new_connection_handler(lease.handle, null)
                                nw_listener_set_state_changed_handler(lease.handle, null)
                                onNativeListenerTerminated(lease, label)
                            }
                        }
                        return@listenerStateHandler
                    }
                    IosLanDebug.log(
                        "data",
                        "buildListener: nw_listener_start (awaiting ready <=${LISTENER_READY_TIMEOUT_MILLIS}ms)"
                    )
                    nw_listener_start(l)
                }
            }
            if (candidate != null) listenerReadyBarrierForTest()
            candidate
        } catch (cancelled: CancellationException) {
            _tcpPort.value = null
            releaseOrRetainListener(lease, "cancelled listener start")
            throw cancelled
        }
        if (readyListener == null) {
            IosLanDebug.log(
                "data",
                "buildListener: listener did not become ready — cancelling candidate"
            )
            releaseOrRetainListener(lease, "listener did not become ready")
            _tcpPort.value = null
            return null
        }
        if (lease.terminated.isCompleted) {
            IosLanDebug.log("data", "buildListener: listener terminated before ownership commit")
            _tcpPort.value = null
            return null
        }
        IosLanDebug.log("data", "buildListener: SUCCESS port=${_tcpPort.value}")
        return readyListener
    }

    /**
     * Admit or reject one callback under the same lock used by stop/rebind
     * queue draining. Apple requires cancelling an inbound connection that is
     * not accepted. Native owner identity prevents a queued callback from a
     * retired listener entering the replacement generation.
     */
    private fun handleInboundConnection(
        owner: nw_listener_t,
        connection: nw_connection_t
    ): Boolean {
        if (connection == null) {
            IosLanDebug.log("data", "listener: ignored null inbound nw_connection")
            return false
        }
        return withInboundOwnershipLock {
            if (inboundListenerOwner !== owner) {
                IosLanDebug.log(
                    "data",
                    "listener: rejected inbound nw_connection from stale/inactive listener"
                )
                rejectNativeConnection(connection, "stale/inactive listener")
                return@withInboundOwnershipLock false
            }
            val raw = try {
                connectionFactory(connection, queue)
            } catch (error: Throwable) {
                // Do not throw across the native callback boundary. The
                // connection was not accepted and remains ours to cancel.
                rejectNativeConnection(connection, "connection wrapper failure")
                IosLanDebug.log(
                    "data",
                    "listener: connection wrapper failed (${error::class.simpleName})"
                )
                return@withInboundOwnershipLock false
            }
            try {
                beforeInboundOfferForTest?.invoke()
                val sent = incomingQueue.offer(raw)
                IosLanDebug.log(
                    "data",
                    "listener: handed connection to incoming channel (queued=$sent)"
                )
                sent
            } catch (error: Throwable) {
                raw.cancelNow("inbound admission failed")
                IosLanDebug.log(
                    "data",
                    "listener: inbound admission failed (${error::class.simpleName})"
                )
                false
            }
        }
    }

    private inline fun <T> withInboundOwnershipLock(block: () -> T): T {
        inboundOwnershipLock.lock()
        return try {
            block()
        } finally {
            inboundOwnershipLock.unlock()
        }
    }

    private fun publishInboundListener(owner: nw_listener_t) = withInboundOwnershipLock {
        inboundListenerOwner = owner
    }

    private fun rejectNativeConnection(connection: nw_connection_t, reason: String) {
        try {
            connectionRejector(connection)
        } catch (error: Throwable) {
            // A test seam or future wrapper must never throw through an Apple
            // native callback. There is no safer fallback after cancellation
            // itself fails, so retain a sanitized diagnostic and return.
            IosLanDebug.log(
                "data",
                "native connection cancellation failed for $reason (${error::class.simpleName})"
            )
        }
    }

    private fun retireInboundListener(closeQueue: Boolean) {
        beforeInboundRetireForTest?.invoke()
        withInboundOwnershipLock {
            inboundListenerOwner = null
            if (closeQueue) incomingQueue.closeAndDrain() else incomingQueue.drain()
        }
    }

    /** Deterministic native callback seam used by Apple ownership tests. */
    internal fun handleInboundConnectionForTest(
        owner: nw_listener_t,
        connection: nw_connection_t
    ): Boolean = handleInboundConnection(owner, connection)

    /**
     * A listener can fail long after its initial ready callback. Serialize
     * that terminal callback with start/rebind/close, depublish the stale
     * port, stop Bonjour resources through the pre-hook, and start a fresh
     * bounded recovery generation. Intentional cancellation first clears
     * [listener], so its later callback is ignored by the identity guard.
     */
    private fun onNativeListenerTerminated(terminated: ListenerLease, state: String) {
        rebindScope.launch {
            val recover = startMutex.withLock {
                if (closed || !startedByHost || listenerLease !== terminated) return@withLock false
                listenerLease = null
                _tcpPort.value = null
                IosLanDebug.log(
                    "data",
                    "listener terminal state=$state for current owner — port depublished"
                )
                retireInboundListener(closeQueue = false)
                // Fence and cancel old-path dials before the suspendable
                // discovery hook so none can hand off while browser cleanup
                // is waiting on native/coroutine work.
                stopPendingDials("listener terminal state=$state")
                invokeBeforeRebindHook("listener terminal state=$state")
                // The discovery pre-hook retires the browser callback owner.
                // Clear once more afterwards so a callback that committed
                // immediately before retirement cannot republish a stale
                // endpoint after the earlier listener-terminal transition.
                endpointRegistry.clear()
                true
            }
            if (recover) scheduleRebind("listener terminal state=$state")
        }
    }

    /**
     * Retain ownership until Network.framework confirms the handle is terminal.
     * Access is serialized by [startMutex].
     */
    private fun retainListenerForCleanup(lease: ListenerLease) {
        if (pendingListenerCleanups.none { it === lease }) {
            pendingListenerCleanups += lease
        }
    }

    private suspend fun releaseOrRetainListener(
        lease: ListenerLease,
        reason: String
    ): Boolean = withContext(NonCancellable) {
        nw_listener_cancel(lease.handle)
        val released = withTimeoutOrNull(LISTENER_CANCEL_TIMEOUT_MILLIS) {
            lease.terminated.await()
            true
        } ?: false
        if (released) {
            // Break Network.framework's retained callback graph before dropping
            // the final lease. The state callback captures [lease]; leaving it
            // installed creates a native -> Kotlin block -> lease -> native
            // ownership cycle and can keep the bound descriptor alive.
            nw_listener_set_new_connection_handler(lease.handle, null)
            nw_listener_set_state_changed_handler(lease.handle, null)
            pendingListenerCleanups.removeAll { it === lease }
        } else {
            retainListenerForCleanup(lease)
            IosLanDebug.log(
                "data",
                "listener cancellation acknowledgement timed out ($reason); ownership retained"
            )
        }
        released
    }

    private suspend fun releasePendingListeners(reason: String): Boolean {
        val snapshot = pendingListenerCleanups.toList()
        var allReleased = true
        for (lease in snapshot) {
            if (!releaseOrRetainListener(lease, reason)) allReleased = false
        }
        return allReleased
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
        val expectedGeneration = dialMutex.withLock {
            if (closed) throw stoppedDialFailure()
            dialGeneration
        }
        val pid8 = peer.publicPeer.id.value.take(8)
        val cachedLease = endpointRegistry.lease(peer.publicPeer.id)
        IosLanDebug.log(
            "connect",
            "begin peer=$pid8 name=${peer.publicPeer.name} " +
                "cachedEndpoint=${cachedLease != null} " +
                "browserGeneration=${cachedLease?.browserGeneration ?: -1}"
        )
        val endpoint: nw_endpoint_t = cachedLease?.endpoint
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
        IosLanDebug.log(
            "connect",
            "peer=$pid8 endpointSource=${if (cachedLease != null) "browse(AWDL-capable)" else "manual-IP-hint"} " +
                "connParams.include_peer_to_peer=true"
        )
        val conn = nw_connection_create(endpoint, params) ?: run {
            invalidateFailedEndpoint(peer, cachedLease, "nw_connection_create returned null")
            IosLanDebug.log("connect", "ABORT peer=$pid8 — nw_connection_create returned null")
            throw P2pError.ConnectionFailed("nw_connection_create returned null")
        }
        IosLanDebug.log("connect", "peer=$pid8 nw_connection_create OK, wrapping + awaiting Connected (<=${CONNECT_TIMEOUT_MILLIS}ms)")
        val raw = try {
            connectionFactory(conn, queue)
        } catch (error: Throwable) {
            // Ownership has not transferred to a wrapper or session yet.
            rejectNativeConnection(conn, "outbound connection wrapper failure")
            throw error
        }
        val registered = dialMutex.withLock {
            if (closed || dialGeneration != expectedGeneration) false else pendingDials.add(raw)
        }
        if (!registered) {
            raw.cancelNow("transport stopped before outbound ownership commit")
            throw stoppedDialFailure()
        }
        try {
            val terminal = try {
                withTimeoutOrNull(CONNECT_TIMEOUT_MILLIS) {
                    raw.state.first { it != ConnectionState.Connecting }
                } ?: run {
                    IosLanDebug.log("connect", "TIMEOUT peer=$pid8 after ${CONNECT_TIMEOUT_MILLIS}ms — closing wrapper")
                    raw.cancelNow("outbound connect timeout")
                    invalidateFailedEndpoint(peer, cachedLease, "connect timeout")
                    throw P2pError.ConnectionFailed(
                        "iOS LAN connect timed out after ${CONNECT_TIMEOUT_MILLIS}ms"
                    )
                }
            } catch (cancelled: CancellationException) {
                // withTimeoutOrNull consumes only its own deadline. An outer
                // caller deadline/cancellation reaches this branch unchanged.
                IosLanDebug.log("connect", "CANCELLED peer=$pid8 — closing wrapper")
                raw.cancelNow("outbound connect cancelled")
                throw cancelled
            }
            val generationStillActive = dialMutex.withLock {
                !closed && dialGeneration == expectedGeneration
            }
            if (!generationStillActive) {
                raw.cancelNow("transport stopped during outbound connect")
                throw stoppedDialFailure()
            }
            if (terminal != ConnectionState.Connected) {
                raw.cancelNow("outbound connect terminal state=$terminal")
                invalidateFailedEndpoint(peer, cachedLease, "terminal state=$terminal")
                IosLanDebug.log("connect", "FAILED peer=$pid8 terminal=$terminal (expected Connected)")
                throw P2pError.ConnectionFailed("iOS LAN connect failed (state=$terminal)")
            }
            beforeDialOwnershipHandoffForTest?.invoke()
            val handedOff = dialMutex.withLock {
                if (!closed && dialGeneration == expectedGeneration) {
                    pendingDials.remove(raw)
                } else {
                    false
                }
            }
            if (!handedOff) {
                raw.cancelNow("transport stopped before outbound ownership handoff")
                throw stoppedDialFailure()
            }
            IosLanDebug.log("connect", "SUCCESS peer=$pid8 raw connection in Connected state")
            return raw
        } finally {
            dialMutex.withLock { pendingDials.remove(raw) }
        }
    }

    private fun invalidateFailedEndpoint(
        peer: InternalPeer,
        cachedLease: IosEndpointRegistry.Lease?,
        reason: String
    ) {
        if (cachedLease == null) return
        val removed = endpointRegistry.removeIfCurrent(peer.publicPeer.id, cachedLease)
        IosLanDebug.log(
            "connect",
            "cached endpoint invalidation peer=${peer.publicPeer.id.value.take(8)} " +
                "generation=${cachedLease.browserGeneration} removed=$removed reason=$reason"
        )
    }

    override fun incomingConnections(): Flow<RawConnection> = incomingQueue.asFlow()

    override suspend fun stop(): Unit = withContext(NonCancellable) {
        startMutex.withLock {
            if (closed) return@withLock
            stopStartedResources(closeQueue = false, clearEndpoints = false)
            if (!releasePendingListeners("transport stop")) {
                throw IllegalStateException(
                    "iOS LAN listener did not acknowledge cancellation within " +
                        "${LISTENER_CANCEL_TIMEOUT_MILLIS}ms"
                )
            }
        }
    }

    override suspend fun close(): Unit = withContext(NonCancellable) {
        startMutex.withLock {
            val firstClose = !closed
            if (firstClose) {
                IosLanDebug.log("data", "close: cancelling path monitor, foreground observer, listener, and incoming channel")
                closed = true
                stopStartedResources(closeQueue = true, clearEndpoints = true)
            }

            if (!releasePendingListeners("transport close")) {
                throw IllegalStateException(
                    "iOS LAN listener did not acknowledge cancellation within " +
                        "${LISTENER_CANCEL_TIMEOUT_MILLIS}ms"
                )
            }
        }
    }

    /** Caller holds [startMutex]. */
    private suspend fun stopStartedResources(closeQueue: Boolean, clearEndpoints: Boolean) {
        startedByHost = false
        val retiredLifecycleOwner = lifecycleRecoveryCoordinator
        lifecycleRecoveryCoordinator = null
        retiredLifecycleOwner?.retire()
        retireInboundListener(closeQueue = closeQueue)
        stopPendingDials("transport lifecycle stopped")
        stopPathMonitor()
        stopForegroundObserver()
        cancelPendingRebind()
        rebindScope.coroutineContext.cancelChildren()
        listenerLease?.let(::retainListenerForCleanup)
        listenerLease = null
        _tcpPort.value = null
        if (clearEndpoints) endpointRegistry.clear()
    }

    private suspend fun stopPendingDials(reason: String) {
        val pending = dialMutex.withLock {
            dialGeneration += 1
            pendingDials.toList().also { pendingDials.clear() }
        }
        pending.forEach { it.cancelNow(reason) }
    }

    private fun stoppedDialFailure(): P2pError.ConnectionFailed =
        P2pError.ConnectionFailed("iOS LAN data transport stopped during connect")

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
        val owner = pathMonitorCallbackState.begin()
        pathMonitorOwner = owner
        nw_path_monitor_set_queue(m, pathQueue)
        nw_path_monitor_set_update_handler(m) pathHandler@ { path ->
            // Cancellation can leave an update queued on pathQueue. The
            // owner check is a cheap early exit; publish below performs the
            // authoritative generation check under the callback-state lock.
            if (!owner.isActive()) return@pathHandler
            val status = nw_path_get_status(path)
            val isSatisfied = (status == nw_path_status_satisfied)

            // V0.4-IOS-PATH-INTERFACE-CHANGE: complementary trigger that
            // fires when the satisfied path's interface set changes
            // (Wi-Fi flap masked by cellular fallback — the satisfaction
            // bit never flips, but the LAN listener needs rebinding
            // because the underlying interface has changed).
            val usesWifi = nw_path_uses_interface_type(path, nw_interface_type_wifi)
            val usesCellular = nw_path_uses_interface_type(path, nw_interface_type_cellular)
            val usesWired = nw_path_uses_interface_type(path, nw_interface_type_wired)
            val usesOther = nw_path_uses_interface_type(path, nw_interface_type_other)
            val fingerprint = appleInterfaceFingerprint(
                usesWifi = usesWifi,
                usesCellular = usesCellular,
                usesWired = usesWired,
                usesOther = usesOther
            )
            val addressFingerprint = p2pkit_lan_interface_fingerprint()
            val update = pathMonitorCallbackState.publish(
                owner = owner,
                isSatisfied = isSatisfied,
                interfaceFingerprint = fingerprint,
                addressFingerprint = addressFingerprint
            ) ?: return@pathHandler

            IosLanDebug.log(
                "data",
                "path-monitor: status=$status isSatisfied=$isSatisfied " +
                    "becameSatisfied=${update.becameSatisfied} " +
                    "isFirst=${update.isFirstSatisfied} " +
                    "usesWifi=$usesWifi usesCellular=$usesCellular usesWired=$usesWired " +
                    "usesOther=$usesOther " +
                    "fingerprint=$fingerprint prev=${update.previousInterfaceFingerprint} " +
                    "interfaceChanged=${update.interfaceChanged} " +
                    "addressFingerprint=$addressFingerprint " +
                    "previousAddressFingerprint=${update.previousAddressFingerprint} " +
                    "addressChanged=${update.addressChanged}"
            )

            if (!update.needsRebind) return@pathHandler
            when {
                update.becameSatisfied && !update.isFirstSatisfied -> {
                    scheduleRebind(
                        reason = "path satisfied after change (status=$status)",
                        admit = owner::isActive
                    )
                }
                update.interfaceChanged || update.addressChanged -> {
                    scheduleRebind(
                        reason = "active LAN path changed: " +
                            "interface=${update.previousInterfaceFingerprint}->$fingerprint " +
                            "addresses=${update.previousAddressFingerprint}->$addressFingerprint " +
                            "(usesWifi=$usesWifi usesCellular=$usesCellular " +
                            "usesWired=$usesWired usesOther=$usesOther)",
                        admit = owner::isActive
                    )
                }
            }
            return@pathHandler
        }
        pathMonitor = m
        nw_path_monitor_start(m)
        IosLanDebug.log("data", "startPathMonitor: monitor started")
    }

    private fun stopPathMonitor() {
        val owner = pathMonitorOwner
        pathMonitorOwner = null
        owner?.let(pathMonitorCallbackState::detach)
        val m = pathMonitor
        pathMonitor = null
        if (m == null) return
        // Native cancellation does not drain callbacks already queued on
        // pathQueue; the owner was retired before this call so they no-op.
        nw_path_monitor_cancel(m)
        IosLanDebug.log("data", "stopPathMonitor: monitor cancelled, pending rebind cleared")
    }

    /**
     * Observe the complete UIKit inactive/background return sequence. The
     * coordinator emits at most one rebind request per inactive episode and
     * treats a successful path-driven rebind while inactive as satisfying the
     * later foreground signal. This prevents back-to-back listener rotations
     * while retaining recovery after Control Center/system-dialog dismissal.
     *
     * Idempotent: a second call while already subscribed is a no-op.
     * Notifications fire on the posting thread (main thread for UIKit
     * notifications); the callback only schedules — it does no I/O.
     */
    private fun startForegroundObserver(owner: AppleLifecycleRecoveryCoordinator) {
        if (lifecycleObservers.isNotEmpty()) return

        fun observe(
            name: platform.Foundation.NSNotificationName,
            signal: AppleLifecycleSignal
        ): NSObjectProtocol = NSNotificationCenter.defaultCenter.addObserverForName(
            name = name,
            `object` = null,
            queue = null
        ) lifecycleHandler@ { _: NSNotification? ->
            handleLifecycleSignal(owner, signal)
            return@lifecycleHandler
        }

        lifecycleObservers = listOf(
            observe(
                UIApplicationWillResignActiveNotification,
                AppleLifecycleSignal.WillResignActive
            ),
            observe(
                UIApplicationWillEnterForegroundNotification,
                AppleLifecycleSignal.WillEnterForeground
            ),
            observe(
                UIApplicationDidBecomeActiveNotification,
                AppleLifecycleSignal.DidBecomeActive
            )
        )
        IosLanDebug.log(
            "data",
            "startForegroundObserver: registered WillResignActive, " +
                "WillEnterForeground, and DidBecomeActive"
        )
    }

    private fun handleLifecycleSignal(
        owner: AppleLifecycleRecoveryCoordinator,
        signal: AppleLifecycleSignal
    ): Boolean {
        val shouldRecover =
            lifecycleRecoveryCoordinator === owner && owner.onSignal(signal)
        IosLanDebug.log(
            "data",
            "lifecycle notification observed signal=$signal " +
                "rebindScheduled=$shouldRecover"
        )
        if (shouldRecover) {
            scheduleRebind(
                reason = "lifecycle recovery signal=$signal",
                admit = {
                    lifecycleRecoveryCoordinator === owner && owner.isAcceptingSignals()
                }
            )
        }
        return shouldRecover
    }

    private fun stopForegroundObserver() {
        val tokens = lifecycleObservers
        if (tokens.isEmpty()) return
        lifecycleObservers = emptyList()
        tokens.forEach(NSNotificationCenter.defaultCenter::removeObserver)
        IosLanDebug.log("data", "stopForegroundObserver: unregistered all lifecycle observers")
    }

    internal val lifecycleObserverCountForTest: Int
        get() = lifecycleObservers.size

    /** Deterministic signal seam; follows the exact observer admission path. */
    internal fun handleLifecycleSignalForTest(signal: AppleLifecycleSignal): Boolean =
        lifecycleRecoveryCoordinator?.let { handleLifecycleSignal(it, signal) } ?: false

    /**
     * Debounce-schedule a rebind. Each call cancels any pending job and
     * launches a fresh delay; back-to-back path callbacks during a single
     * physical rotation collapse into one actual rebind. Callbacks must
     * remain cheap and non-blocking — the lock + NSD/NWListener work all
     * happens inside [rebindNow].
     */
    private fun scheduleRebind(
        reason: String,
        attempt: Int = 0,
        delayMillis: Long = REBIND_DEBOUNCE_MILLIS,
        admit: () -> Boolean = { true }
    ) {
        if (!admit() || closed || !startedByHost) return
        rebindScope.launch(start = CoroutineStart.UNDISPATCHED) {
            rebindScheduleMutex.withLock {
                if (!admit() || closed || !startedByHost) return@withLock
                pendingRebindJob?.cancel()
                IosLanDebug.log(
                    "data",
                    "scheduleRebind: $reason (attempt=$attempt delay=${delayMillis}ms)"
                )
                pendingRebindJob = rebindScope.launch {
                    delay(delayMillis)
                    if (!admit()) {
                        IosLanDebug.log(
                            "data",
                            "scheduleRebind: retired callback owner ignored ($reason)"
                        )
                        return@launch
                    }
                    rebindNow(reason, attempt, admit)
                }
            }
        }
    }

    private suspend fun cancelPendingRebind() = rebindScheduleMutex.withLock {
        pendingRebindJob?.cancel()
        pendingRebindJob = null
    }

    private fun scheduleRebindRetry(
        reason: String,
        failedAttempt: Int,
        admit: () -> Boolean
    ) {
        val nextAttempt = failedAttempt + 1
        if (nextAttempt > REBIND_RETRY_MAX_ATTEMPTS) {
            IosLanDebug.log(
                "data",
                "rebindNow: retry budget exhausted after $failedAttempt attempt(s) ($reason)"
            )
            return
        }
        scheduleRebind(
            reason = "retry $nextAttempt/$REBIND_RETRY_MAX_ATTEMPTS after $reason",
            attempt = nextAttempt,
            delayMillis = REBIND_RETRY_BASE_DELAY_MILLIS * nextAttempt,
            admit = admit
        )
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
     * case. The bounded retry generation continues without requiring an
     * external path event.
     */
    private suspend fun rebindNow(
        reason: String,
        attempt: Int,
        admit: () -> Boolean
    ): Unit = startMutex.withLock {
        if (!admit()) {
            IosLanDebug.log("data", "rebindNow: callback owner retired; skipping ($reason)")
            return@withLock
        }
        if (closed) {
            IosLanDebug.log("data", "rebindNow: transport closed; skipping ($reason)")
            return@withLock
        }
        if (!startedByHost) {
            IosLanDebug.log("data", "rebindNow: host no longer started; skipping ($reason)")
            return@withLock
        }
        // Fence inbound and outbound handoffs immediately, then retire the
        // browser callback owner before the final endpoint clear. This avoids
        // both late dial success and stale endpoint republication.
        retireInboundListener(closeQueue = false)
        stopPendingDials("listener/path rebind")
        invokeBeforeRebindHook(reason)
        // Retire the browser owner before the final clear. Otherwise a queued
        // old-generation result can refill the registry after the clear and
        // after the dial generation has already advanced.
        endpointRegistry.clear()
        val old = listenerLease
        val oldPort = _tcpPort.value
        IosLanDebug.log("data", "rebindNow: starting ($reason) oldPort=$oldPort")

        listenerLease = null
        _tcpPort.value = null
        val oldReleased = old?.let {
            releaseOrRetainListener(it, "listener rebind")
        } ?: releasePendingListeners("listener rebind")
        IosLanDebug.log(
            "data",
            if (old != null) "rebindNow: old listener cancelled (oldPort=$oldPort)"
            else "rebindNow: rebuilding from missing-listener state"
        )
        if (!oldReleased || !releasePendingListeners("listener rebind")) {
            IosLanDebug.log(
                "data",
                "rebindNow: old listener release is still pending; rebuild deferred ($reason)"
            )
            scheduleRebindRetry("listener cleanup pending", attempt, admit)
            return@withLock
        }

        val fresh = buildListener()
        if (fresh == null) {
            IosLanDebug.log(
                "data",
                "rebindNow: REBUILD FAILED — listener stays null ($reason)"
            )
            scheduleRebindRetry(reason, attempt, admit)
            return@withLock
        }
        // Keep the defensive re-check even though close() is now serialized
        // by startMutex: it protects against future lifecycle call sites that
        // may latch terminal state before acquiring this lock.
        if (closed) {
            IosLanDebug.log("data", "rebindNow: closed during rebuild — cancelling fresh listener ($reason)")
            releaseOrRetainListener(fresh, "closed during listener rebuild")
            return@withLock
        }
        listenerLease = fresh
        publishInboundListener(fresh.handle)
        val newPort = _tcpPort.value
        IosLanDebug.log("data", "rebindNow: new listener ready newPort=$newPort")

        try {
            afterListenerRebind?.invoke(fresh.handle)
            lifecycleRecoveryCoordinator?.onSuccessfulRebind()
            IosLanDebug.log(
                "data",
                "rebindNow: complete (port rotated: $oldPort -> $newPort)"
            )
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Exception) {
            IosLanDebug.log(
                "data",
                "rebindNow: listener ready but discovery restore failed: " +
                    "${error.message ?: error::class.simpleName} (listener=$newPort)"
            )
            scheduleRebindRetry("discovery restore failure", attempt, admit)
        }
    }

    private suspend fun invokeBeforeRebindHook(reason: String) {
        try {
            beforeListenerRebind?.invoke()
            IosLanDebug.log("data", "rebindNow: beforeListenerRebind hook complete")
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Exception) {
            IosLanDebug.log(
                "data",
                "rebindNow: beforeListenerRebind hook failed during $reason: " +
                    (error.message ?: error::class.simpleName.orEmpty())
            )
        }
    }

    /** Real Network.framework failure seam used by the Apple lifecycle suite. */
    internal fun cancelCurrentListenerForTest() {
        listenerLease?.handle?.let { nw_listener_cancel(it) }
    }

    internal companion object {
        /** Matches core's maximum number of concurrently admitted inbound setups. */
        const val MAX_BUFFERED_INBOUND_CONNECTIONS: Int = 16

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

        const val LISTENER_READY_TIMEOUT_MILLIS: Long = 5_000
        const val LISTENER_CANCEL_TIMEOUT_MILLIS: Long = 2_000
        const val REBIND_RETRY_BASE_DELAY_MILLIS: Long = 250
        const val REBIND_RETRY_MAX_ATTEMPTS: Int = 5
    }
}

internal fun applePathNeedsRebind(
    becameSatisfied: Boolean,
    isFirstEver: Boolean,
    interfaceChanged: Boolean,
    addressChanged: Boolean
): Boolean = (becameSatisfied && !isFirstEver) || interfaceChanged || addressChanged

internal fun appleInterfaceFingerprint(
    usesWifi: Boolean,
    usesCellular: Boolean,
    usesWired: Boolean,
    usesOther: Boolean
): Int = (if (usesWifi) 1 else 0) or
    (if (usesCellular) 2 else 0) or
    (if (usesWired) 4 else 0) or
    (if (usesOther) 8 else 0)
