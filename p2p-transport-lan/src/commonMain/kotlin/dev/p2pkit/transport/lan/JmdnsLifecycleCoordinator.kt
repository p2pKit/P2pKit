package dev.p2pkit.transport.lan

import dev.p2pkit.core.transport.LocalPeerInfo
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlin.coroutines.CoroutineContext

/**
 * Platform operations behind [JmdnsLifecycleCoordinator] (2026-07 test seam,
 * P1-14). Implemented by both JmDNS transports (Android additionally supplies
 * `ConnectivityManager` and multicast-lock operations) and by fakes in
 * `JmdnsLifecycleCoordinatorTest` (`:p2p-transport-lan:jvmTest`). The fake
 * suite is also the automated contract for Android's rebind machinery, for
 * which this module has no instrumented test target.
 *
 * The `*Blocking` functions may block (JmDNS calls do); the coordinator hops
 * to its blocking-I/O context around every call, so implementations must NOT hop or
 * suspend themselves. Everything else must be cheap and non-blocking — it is
 * called inline under the coordinator lock.
 */
internal interface JmdnsLifecycleOps<N : Any, H : Any> {
    /**
     * Create the platform mDNS handle bound to [target]'s address (or the
     * platform default when no address can be resolved). [forRebind] only
     * selects the diagnostic-trail wording — the load-bearing log lines
     * (`rebindNow: rebinding onto …`, referenced from
     * `docs/LAN_DIAGNOSTICS_PROTOCOL.md`) must keep their original prefixes.
     */
    fun createHandleBlocking(target: N?, forRebind: Boolean): H

    fun closeHandleBlocking(handle: H)

    /**
     * Create the opaque service token before registration begins. Keeping the
     * token outside the blocking call lets the coordinator compensate an
     * ambiguous success when prompt cancellation wins the dispatcher return.
     */
    fun createServiceToken(localPeer: LocalPeerInfo): Any

    fun registerServiceBlocking(handle: H, token: Any)

    fun unregisterServiceBlocking(handle: H, token: Any)

    /** Create the listener token before the blocking add for the same ownership reason. */
    fun createListenerToken(handle: H): Any

    fun addListenerBlocking(handle: H, token: Any)

    /**
     * Prevent callbacks from [token] from publishing after its lifecycle
     * generation has been replaced. Must be idempotent and non-blocking.
     */
    fun deactivateListenerToken(token: Any)

    fun removeListenerBlocking(handle: H, token: Any)

    /**
     * AUDIT-2026-07 (DSC-1): one discovery-heartbeat tick — re-emit
     * `PeerEvent.Updated` for every appId-matching service already resolved
     * in [handle]'s in-process cache, so `PeerRegistry.lastSeen` keeps
     * refreshing and healthy idle peers survive the 15 s staleness eviction.
     * Must read the local cache only (no forced network re-query): a
     * genuinely departed peer, whose cache entry a goodbye or TTL expiry has
     * pruned, must stop being re-emitted so registry eviction still removes
     * it. Called by the coordinator's heartbeat loop on the blocking-I/O
     * context while discovery is intended and a handle is live.
     */
    fun reemitCachedPeersBlocking(handle: H)

    /** The platform's current active network (bind target for lazy starts). */
    fun currentNetwork(): N?

    /** Most recent network reported by the primary (WIFI|ETHERNET) watcher callback. */
    fun observedNetwork(): N?

    /** Most recent system-default network reported by the default watcher callback. */
    fun observedDefaultNetwork(): N?

    /** True while at least one network-watcher callback is registered. */
    fun isWatcherActive(): Boolean

    /** Idempotent acquire of the platform multicast lock (no-op where the platform has none). */
    fun acquireMulticastLock()

    /** Unconditional release of the multicast lock; the coordinator applies the intent-based idle guard. */
    fun releaseMulticastLock()

    /** Idempotent registration of the platform network-rotation watcher. */
    fun startNetworkWatcher()

    /** Unconditional watcher teardown (unregister callbacks, reset observed state); idle-guarded by the coordinator. */
    fun stopNetworkWatcher()

    fun logDebug(message: String)

    fun logWarn(message: String, error: Throwable? = null)
}

/**
 * Platform-neutral JmDNS-style lifecycle state machine shared by the JVM and
 * Android transports. It owns the transactional resource rules once duplicated
 * in both platform implementations and is directly exercised from `jvmTest`
 * with fake blocking operations.
 *
 * Owns: the shared advertise/discover handle, the host-intent flags, the
 * multicast-lock + watcher idle policy, and the debounced network-rotation
 * rebind with bounded create-retry (AUDIT-2026-06 #5). Platform specifics
 * (JmDNS calls, `ConnectivityManager` callbacks, `WifiManager` lock, logcat)
 * stay behind [JmdnsLifecycleOps].
 */
internal class JmdnsLifecycleCoordinator<N : Any, H : Any>(
    private val ops: JmdnsLifecycleOps<N, H>,
    /**
     * Scope for the debounced rebind + retry coroutines. The owning transport
     * passes its `SupervisorJob`-backed rebind scope so a single failed rebind
     * does not poison future rebinds; tests pass their own scope.
     */
    private val rebindScope: CoroutineScope,
    /**
     * Context for the blocking [JmdnsLifecycleOps] `*Blocking` calls — the
     * platform transport passes `Dispatchers.IO` (the exact hop the
     * pre-extraction code performed inline; `Dispatchers.IO` is not part of
     * the coroutines common API, hence the injection).
     */
    private val ioContext: CoroutineContext,
    private val rebindDebounceMillis: Long = REBIND_DEBOUNCE_MILLIS,
    private val rebindRetryBaseDelayMillis: Long = REBIND_RETRY_BASE_DELAY_MILLIS,
    private val rebindRetryMaxAttempts: Int = REBIND_RETRY_MAX_ATTEMPTS,
    /**
     * AUDIT-2026-07 (DSC-1): cadence of the discovery heartbeat (see
     * [JmdnsLifecycleOps.reemitCachedPeersBlocking]). Injectable for tests;
     * production uses the shared JVM/Android constant, which matches the iOS
     * re-announce interval and stays comfortably below PeerRegistry's 15 s
     * staleness eviction horizon.
     */
    private val heartbeatIntervalMillis: Long = LanConstants.PEER_REANNOUNCE_INTERVAL_MS
) {

    private val lock = Mutex()

    /** Serializes debounce-job replacement across concurrent platform callbacks. */
    private val scheduleLock = Mutex()

    /** The live platform handle; null before first start, after idle close, and in the failed-rebind window. */
    private var handle: H? = null

    /** True only when the live handle and tokens exactly match both intent flags. */
    private var bindingHealthy = true

    /** Token returned by [JmdnsLifecycleOps.registerServiceBlocking] while advertising is live. */
    private var advertisedToken: Any? = null

    /** Token returned by [JmdnsLifecycleOps.addListenerBlocking] while discovery is live. */
    private var listenerToken: Any? = null

    /**
     * AUDIT-2026-06 (#5): host INTENT flags, independent of the live handles
     * above. [rebindNow] nulls the advertised/listener tokens mid-rebind, so a
     * transient create failure used to leave both handles null while the host
     * still wanted advertising/discovery — the next rebind's "neither active"
     * guard (previously computed from the handles) then skipped forever and
     * `refresh()` early-returned on the null handle: the transport was bricked
     * until process restart. These flags capture what the host asked for; the
     * handles capture what is currently live. Set on successful start*,
     * cleared in stop*; guarded by [lock] like the handles.
     */
    private var advertisingIntent = false
    private var discoveryIntent = false

    /**
     * Cached `LocalPeerInfo` from the most recent `startAdvertising` call.
     * Used by [rebindNow] to re-register after a fresh handle is constructed
     * on the new interface. Cleared in `stopAdvertising` so a subsequent
     * rebind cannot inadvertently re-advertise after the host app stopped.
     */
    private var cachedLocalPeer: LocalPeerInfo? = null

    /**
     * Network present at the time of the most recent successful (re)bind.
     * Used by [rebindNow] to skip no-op rebinds when neither observed signal
     * has changed since we last bound. Guarded by [lock].
     */
    private var boundNetwork: N? = null

    /** Default network present at the time of the most recent successful bind. */
    private var boundDefaultNetwork: N? = null

    /**
     * Consecutive failed binding transactions in [rebindNow]. The budget is
     * reset on a successful bind, watcher stop, or genuinely new target pair.
     * Guarded by [lock].
     */
    private var rebindRetryAttempts = 0

    /** Retry budgets are scoped to one observed target pair, including null targets. */
    private var retryTargetInitialized = false
    private var retryTarget: N? = null
    private var retryDefaultTarget: N? = null

    /**
     * Pending self-scheduled retry after a failed binding transaction in
     * [rebindNow]. Nothing else is guaranteed to call back in after failure,
     * so the transport must re-attempt on its own. Cancelled when the watcher
     * stops. Guarded by [lock].
     */
    private var rebindRetryJob: Job? = null

    /** The most recent debounced rebind job; cancelled when superseded. */
    private var pendingRebindJob: Job? = null

    /**
     * AUDIT-2026-07 (DSC-1): discovery heartbeat loop; non-null while
     * discovery is intended. Started on successful [startDiscovery],
     * cancelled in [stopDiscovery]. Deliberately NOT touched by [rebindNow]:
     * the loop keys each tick off the CURRENT [handle] and [discoveryIntent],
     * so it survives refresh/rebind and simply skips ticks in the
     * failed-rebind window (handle null). Guarded by [lock].
     */
    private var heartbeatJob: Job? = null

    suspend fun startAdvertising(localPeer: LocalPeerInfo): Unit = lock.withLock {
        if (advertisingIntent && advertisedToken != null && bindingHealthy) return@withLock

        repairUnhealthyBindingBeforeStart()
        // Repair may have restored this same intent after a failed rebind or
        // cleanup. Do not register a second service on the repaired handle.
        if (advertisingIntent && advertisedToken != null && bindingHealthy) return@withLock

        ops.acquireMulticastLock()
        val h = try {
            ensureHandle()
        } catch (e: Throwable) {
            failedStartCleanup()
            throw e
        }
        val token = ops.createServiceToken(localPeer)
        advertisedToken = token
        bindingHealthy = false
        try {
            withContext(ioContext) { ops.registerServiceBlocking(h, token) }
        } catch (e: Throwable) {
            failedStartCleanup()
            throw e
        }
        advertisingIntent = true
        cachedLocalPeer = localPeer
        bindingHealthy = bindingMatchesIntents()
        boundNetwork = ops.currentNetwork()
        boundDefaultNetwork = ops.currentNetwork()
        ops.logDebug(
            "startAdvertising: registered, " +
                "boundNetwork=$boundNetwork boundDefaultNetwork=$boundDefaultNetwork"
        )
        ops.startNetworkWatcher()
    }

    suspend fun stopAdvertising(): Unit = lock.withLock {
        withContext(NonCancellable) {
            // Clear intent before cleanup so fallback restoration cannot
            // resurrect the side the host just stopped.
            advertisingIntent = false
            cachedLocalPeer = null
            bindingHealthy = false
            val token = advertisedToken
            if (token != null) {
                val cleanupFailure = removeAdvertisingToken(token)
                if (cleanupFailure != null) {
                    recoverOtherIntentsAfterCleanupFailure("stopAdvertising", cleanupFailure)
                }
            }
            bindingHealthy = bindingMatchesIntents()
            closeHandleIfIdle()
            stopNetworkWatcherIfIdle()
            releaseMulticastLockIfIdle()
        }
        currentCoroutineContext().ensureActive()
    }

    suspend fun startDiscovery(): Unit = lock.withLock {
        if (discoveryIntent && listenerToken != null && bindingHealthy) return@withLock

        repairUnhealthyBindingBeforeStart()
        // As above, repair can satisfy the requested intent itself.
        if (discoveryIntent && listenerToken != null && bindingHealthy) return@withLock

        ops.acquireMulticastLock()
        val h = try {
            ensureHandle()
        } catch (e: Throwable) {
            failedStartCleanup()
            throw e
        }
        val token = ops.createListenerToken(h)
        listenerToken = token
        bindingHealthy = false
        try {
            withContext(ioContext) { ops.addListenerBlocking(h, token) }
        } catch (e: Throwable) {
            failedStartCleanup()
            throw e
        }
        discoveryIntent = true
        bindingHealthy = bindingMatchesIntents()
        boundNetwork = ops.currentNetwork()
        boundDefaultNetwork = ops.currentNetwork()
        ops.logDebug(
            "startDiscovery: listener added, " +
                "boundNetwork=$boundNetwork boundDefaultNetwork=$boundDefaultNetwork"
        )
        ops.startNetworkWatcher()
        startHeartbeatLocked()
    }

    suspend fun stopDiscovery(): Unit = lock.withLock {
        withContext(NonCancellable) {
            discoveryIntent = false
            bindingHealthy = false
            // Halt heartbeat before listener cleanup; no later tick may use a
            // binding after discovery intent is cleared.
            heartbeatJob?.cancel()
            heartbeatJob = null
            val token = listenerToken
            if (token != null) {
                val cleanupFailure = removeListenerToken(token)
                if (cleanupFailure != null) {
                    recoverOtherIntentsAfterCleanupFailure("stopDiscovery", cleanupFailure)
                }
            }
            bindingHealthy = bindingMatchesIntents()
            closeHandleIfIdle()
            stopNetworkWatcherIfIdle()
            releaseMulticastLockIfIdle()
        }
        currentCoroutineContext().ensureActive()
    }

    /**
     * Rotate discovery add-first under coordinator ownership, then run the
     * platform-specific cache refresh on the resulting live handle. Failed
     * detach uses the same close-and-rebuild fallback as stop cleanup, so a
     * duplicate listener can never become unowned.
     */
    suspend fun refreshDiscovery(
        afterRotation: suspend (handle: H) -> Unit
    ): Unit = lock.withLock {
        val h = handle
        val old = listenerToken
        if (h == null || old == null) {
            ops.logDebug("refresh: no listener active — skipping")
            return@withLock
        }
        val fresh = ops.createListenerToken(h)
        try {
            withContext(ioContext) { ops.addListenerBlocking(h, fresh) }
        } catch (error: Throwable) {
            ops.deactivateListenerToken(fresh)
            var cleanupFailure: Throwable? = null
            try {
                withContext(NonCancellable) {
                    withContext(ioContext) { ops.removeListenerBlocking(h, fresh) }
                }
            } catch (cleanupError: Throwable) {
                if (cleanupError !is Exception) throw cleanupError
                cleanupFailure = cleanupError
            }
            if (cleanupFailure != null) {
                bindingHealthy = false
                recoverOtherIntentsAfterCleanupFailure("refresh add compensation", cleanupFailure)
            }
            if (error is CancellationException) throw error
            if (error !is Exception) throw error
            ops.logWarn("refresh: addServiceListener failed; keeping active binding", error)
            return@withLock
        }

        listenerToken = fresh
        bindingHealthy = false
        // The new generation owns delivery before the old listener is
        // detached; any queued callback from the old generation is ignored.
        ops.deactivateListenerToken(old)
        val removalFailure = try {
            withContext(NonCancellable) {
                withContext(ioContext) { ops.removeListenerBlocking(h, old) }
            }
            null
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Throwable) {
            if (error !is Exception) throw error
            error
        }
        if (removalFailure != null) {
            recoverOtherIntentsAfterCleanupFailure("refresh old-listener removal", removalFailure)
        }
        bindingHealthy = bindingMatchesIntents()
        val live = handle ?: return@withLock
        afterRotation(live)
    }

    /**
     * AUDIT-2026-07 (DSC-1): the discovery heartbeat. While discovery is
     * intended, ask the platform every [heartbeatIntervalMillis] to re-emit
     * `PeerEvent.Updated` for every service already resolved in the live
     * handle's in-process cache (see
     * [JmdnsLifecycleOps.reemitCachedPeersBlocking]) so healthy idle peers
     * survive PeerRegistry's 15 s staleness eviction — previously only iOS
     * had this loop and `kit.peers` silently emptied on JVM/Android in steady
     * state. Runs on [rebindScope] like the rebind machinery; each tick takes
     * [lock] and re-checks intent + handle, so the loop survives
     * refresh/rebind and skips the failed-rebind window. Cancellation is
     * rethrown, never swallowed; any other tick failure is logged and the
     * loop stays alive. Caller must hold [lock]. Idempotent.
     */
    private fun startHeartbeatLocked() {
        if (heartbeatJob?.isActive == true) return
        heartbeatJob = rebindScope.launch {
            while (isActive) {
                delay(heartbeatIntervalMillis)
                try {
                    heartbeatTick()
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Exception) {
                    ops.logWarn("discovery heartbeat: tick failed — keeping loop alive", e)
                }
            }
        }
    }

    /** One heartbeat tick under [lock]; skips when discovery is not live. */
    private suspend fun heartbeatTick(): Unit = lock.withLock {
        if (!discoveryIntent) return@withLock
        val h = handle ?: return@withLock
        withContext(ioContext) { ops.reemitCachedPeersBlocking(h) }
    }

    /**
     * Debounces rebind requests. Each call cancels the previous pending job
     * and launches a fresh one after [rebindDebounceMillis]. Multiple
     * back-to-back rotation events (typical of Android's
     * `onAvailable`/`onLost`/`onCapabilitiesChanged` storms on a single
     * physical handover) collapse into one actual rebind.
     *
     * No [lock] is taken here — that happens inside [rebindNow]. Platform
     * watcher callbacks must remain cheap and non-blocking.
     */
    fun scheduleRebind(reason: String) {
        rebindScope.launch(start = CoroutineStart.UNDISPATCHED) {
            scheduleLock.withLock {
                pendingRebindJob?.cancel()
                ops.logDebug("scheduleRebind: $reason (debounce=${rebindDebounceMillis}ms)")
                pendingRebindJob = rebindScope.launch {
                    delay(rebindDebounceMillis)
                    rebindNow(reason)
                }
            }
        }
    }

    /** Deterministic synchronization seam for the coordinator regression suite. */
    internal suspend fun awaitPendingRebindForTest() {
        val pending = scheduleLock.withLock { pendingRebindJob }
        pending?.join()
    }

    /**
     * Performs the actual teardown + recreate cycle for whichever of
     * advertising / discovery is currently intended. Runs under [lock] so it
     * cannot race with the start / stop entry points.
     *
     * Idempotency (two-target check, preserved from V0.4-AP):
     *   - If the watcher is no longer active (stopped after schedule), no-op.
     *   - If BOTH the primary observation AND the default-network observation
     *     are unchanged since the last successful bind, no-op. A `null`
     *     observed network is a legitimate steady state in the hotspot-host
     *     case, and we still want to re-bind so the handle picks up whatever
     *     multicast carrier is alive.
     */
    private suspend fun rebindNow(reason: String): Unit = lock.withLock {
        if (!ops.isWatcherActive()) {
            ops.logDebug("rebindNow: watcher already stopped; skipping ($reason)")
            return@withLock
        }
        val target = ops.observedNetwork()
        val defaultTarget = ops.observedDefaultNetwork()

        if (!retryTargetInitialized || target != retryTarget || defaultTarget != retryDefaultTarget) {
            rebindRetryJob?.cancel()
            rebindRetryJob = null
            rebindRetryAttempts = 0
            retryTarget = target
            retryDefaultTarget = defaultTarget
            retryTargetInitialized = true
        }

        // AUDIT-2026-06 (#5): `handle != null` term — the bound* markers are
        // only updated on a SUCCESSFUL bind, so after a failed rebind (handle
        // torn down, create failed) they still describe the pre-teardown
        // bind. A retry arriving after the network flipped back to the
        // previously-bound one must not be skipped as "no change" while
        // there is no live handle at all.
        val noChangeSinceLastBind =
            bindingHealthy &&
                handle != null &&
                target == boundNetwork &&
                defaultTarget == boundDefaultNetwork
        if (noChangeSinceLastBind) {
            ops.logDebug(
                "rebindNow: no changes since last bind; skipping ($reason) " +
                    "transport=$boundNetwork default=$boundDefaultNetwork"
            )
            return@withLock
        }

        // AUDIT-2026-06 (#5): computed from host INTENT, not from the live
        // handles — this method nulls the advertised/listener tokens below,
        // so after a create failure the handle-based check read "neither
        // active" and skipped every subsequent rebind forever.
        val hadAdvertising = advertisingIntent
        val hadDiscovery = discoveryIntent
        if (!hadAdvertising && !hadDiscovery) {
            ops.logDebug("rebindNow: neither advertising nor discovery active; skipping ($reason)")
            return@withLock
        }

        ops.logDebug(
            "rebindNow: starting; reason=$reason " +
                "transport: $boundNetwork -> $target  default: $boundDefaultNetwork -> $defaultTarget " +
                "advertising=$hadAdvertising discovery=$hadDiscovery"
        )

        // Closing and restoring form one transaction. Ownership is never
        // cleared until close succeeds, and the binding is not marked healthy
        // until every intended service/listener has been attached.
        bindingHealthy = false
        try {
            closeCurrentHandle()
            installCurrentIntents(
                target = target,
                defaultTarget = defaultTarget,
                forRebind = true
            )
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Throwable) {
            if (error !is Exception) throw error
            scheduleRebindRetry(error)
            return@withLock
        }

        rebindRetryJob?.cancel()
        rebindRetryJob = null
        rebindRetryAttempts = 0
        retryTargetInitialized = false
        ops.logDebug(
            "rebindNow: complete; boundNetwork=$target boundDefaultNetwork=$defaultTarget"
        )
    }

    /** Lazily creates the handle bound to the current active network. Called under [lock]. */
    private suspend fun ensureHandle(): H {
        handle?.let { return it }
        val fresh = createHandleClosingOrphanOnCancel(ops.currentNetwork(), forRebind = false)
        handle = fresh
        bindingHealthy = bindingMatchesIntents()
        return fresh
    }

    private fun bindingMatchesIntents(): Boolean =
        advertisingIntent == (advertisedToken != null) &&
            discoveryIntent == (listenerToken != null)

    /**
     * Install every currently intended resource on one new handle. Tokens are
     * stored before their blocking side effects begin, so ambiguous completion
     * remains owned and can be rolled back by closing the handle.
     */
    private suspend fun installCurrentIntents(
        target: N?,
        defaultTarget: N?,
        forRebind: Boolean
    ) {
        check(handle == null) { "cannot install a binding while another handle is owned" }
        val fresh = createHandleClosingOrphanOnCancel(target ?: defaultTarget, forRebind)
        handle = fresh
        bindingHealthy = false
        try {
            if (advertisingIntent) {
                val localPeer = cachedLocalPeer
                    ?: error("advertising intent has no cached LocalPeerInfo")
                val token = ops.createServiceToken(localPeer)
                advertisedToken = token
                withContext(ioContext) { ops.registerServiceBlocking(fresh, token) }
                ops.logDebug("rebindNow: registerService completed on fresh JmDNS")
            }
            if (discoveryIntent) {
                val token = ops.createListenerToken(fresh)
                listenerToken = token
                withContext(ioContext) { ops.addListenerBlocking(fresh, token) }
                ops.logDebug("rebindNow: addServiceListener completed on fresh JmDNS")
            }
        } catch (error: Throwable) {
            withContext(NonCancellable) {
                try {
                    closeCurrentHandle()
                } catch (cleanupError: Throwable) {
                    if (cleanupError !is Exception) throw cleanupError
                    ops.logWarn(
                        "binding rollback: close failed; retaining handle/token ownership",
                        cleanupError
                    )
                }
            }
            throw error
        }
        bindingHealthy = bindingMatchesIntents()
        check(bindingHealthy) { "installed JmDNS resources do not match lifecycle intent" }
        boundNetwork = target
        boundDefaultNetwork = defaultTarget
    }

    /** Clear ownership only after the platform handle actually closes. */
    private suspend fun closeCurrentHandle() {
        val current = handle ?: run {
            advertisedToken = null
            listenerToken = null
            bindingHealthy = bindingMatchesIntents()
            return
        }
        listenerToken?.let(ops::deactivateListenerToken)
        withContext(ioContext) { ops.closeHandleBlocking(current) }
        handle = null
        advertisedToken = null
        listenerToken = null
        bindingHealthy = bindingMatchesIntents()
    }

    private suspend fun removeAdvertisingToken(token: Any): Throwable? {
        val current = handle
            ?: return IllegalStateException("advertised token exists without an owning handle")
        return try {
            withContext(NonCancellable) {
                withContext(ioContext) { ops.unregisterServiceBlocking(current, token) }
            }
            advertisedToken = null
            ops.logDebug("stopAdvertising: unregistered")
            null
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Throwable) {
            if (error !is Exception) throw error
            ops.logWarn("stopAdvertising: unregister failed; retaining ownership", error)
            error
        }
    }

    private suspend fun removeListenerToken(token: Any): Throwable? {
        val current = handle
            ?: return IllegalStateException("listener token exists without an owning handle")
        ops.deactivateListenerToken(token)
        return try {
            withContext(NonCancellable) {
                withContext(ioContext) { ops.removeListenerBlocking(current, token) }
            }
            listenerToken = null
            ops.logDebug("stopDiscovery: listener removed")
            null
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Throwable) {
            if (error !is Exception) throw error
            ops.logWarn("stopDiscovery: listener removal failed; retaining ownership", error)
            error
        }
    }

    private suspend fun recoverOtherIntentsAfterCleanupFailure(
        operation: String,
        cleanupFailure: Throwable
    ) {
        ops.logWarn("$operation: targeted cleanup failed; rebuilding shared handle", cleanupFailure)
        try {
            withContext(NonCancellable) {
                closeCurrentHandle()
                if (advertisingIntent || discoveryIntent) {
                    val target = ops.currentNetwork()
                    installCurrentIntents(
                        target = target,
                        defaultTarget = ops.observedDefaultNetwork(),
                        forRebind = true
                    )
                }
            }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (recoveryFailure: Throwable) {
            if (recoveryFailure !is Exception) throw recoveryFailure
            ops.logWarn(
                "$operation: fallback rebuild failed; ownership retained for retry",
                recoveryFailure
            )
            throw recoveryFailure
        }
    }

    private suspend fun repairUnhealthyBindingBeforeStart() {
        if (bindingHealthy && bindingMatchesIntents()) return
        closeCurrentHandle()
        if (advertisingIntent || discoveryIntent) {
            val target = ops.currentNetwork()
            installCurrentIntents(
                target = target,
                defaultTarget = ops.observedDefaultNetwork(),
                forRebind = true
            )
        }
    }

    /**
     * AUDIT-2026-07 (DSC-3): the blocking create is non-cancellable work — a
     * caller cancelled mid-create still gets a live handle produced on the IO
     * thread, and the plain `withContext` shape then threw the cancellation
     * and dropped that handle on the floor: an open multicast socket plus
     * listener threads that nothing could ever close. Capture the produced
     * handle and close it before rethrowing the cancellation. (withContext
     * always waits for its block, so the catch below cannot race the
     * assignment.)
     */
    private suspend fun createHandleClosingOrphanOnCancel(target: N?, forRebind: Boolean): H {
        var produced: H? = null
        try {
            withContext(ioContext) {
                produced = ops.createHandleBlocking(target, forRebind)
            }
        } catch (e: CancellationException) {
            produced?.let { orphan ->
                handle = orphan
                bindingHealthy = false
                withContext(NonCancellable) {
                    try {
                        closeCurrentHandle()
                    } catch (cleanupError: Throwable) {
                        if (cleanupError !is Exception) throw cleanupError
                        ops.logWarn(
                            "cancelled handle creation: close failed; retaining ownership",
                            cleanupError
                        )
                    }
                }
            }
            throw e
        }
        return produced ?: error("createHandleBlocking returned without producing a handle")
    }

    /**
     * AUDIT-2026-07 (DSC-13): a failed start* used to return with the
     * multicast lock held and the handle open while both intent flags were
     * still false — nothing would release either until the other side's stop
     * or `kit.stop()`. Run the intent-guarded idle cleanup (which correctly
     * keeps both when the OTHER side is active) before the failure is
     * rethrown; NonCancellable so a cancelled start cleans up too.
     */
    private suspend fun failedStartCleanup() {
        withContext(NonCancellable) {
            try {
                closeCurrentHandle()
                if (advertisingIntent || discoveryIntent) {
                    val target = ops.currentNetwork()
                    installCurrentIntents(
                        target = target,
                        defaultTarget = ops.observedDefaultNetwork(),
                        forRebind = true
                    )
                }
            } catch (cleanupError: Throwable) {
                if (cleanupError !is Exception) throw cleanupError
                ops.logWarn(
                    "failed start cleanup: ownership retained for a later retry",
                    cleanupError
                )
            }
            if (handle == null) releaseMulticastLockIfIdle()
        }
    }

    private suspend fun closeHandleIfIdle() {
        // AUDIT-2026-06 (#5): idle == host intent cleared on both sides. The
        // old handle-based check misread the failed-rebind window (handles
        // null, host still active) as idle — see the intent-flag KDoc.
        if (advertisingIntent || discoveryIntent) return
        if (handle == null) return
        closeCurrentHandle()
        ops.logDebug("closeJmdnsIfIdle: closed handle")
    }

    private fun releaseMulticastLockIfIdle() {
        // AUDIT-2026-06 (#5): intent-based idle check — a failed rebind nulls
        // the handles while the host is still active, and the rebind retry
        // needs the multicast lock kept alive to be useful.
        if (advertisingIntent || discoveryIntent) return
        if (handle != null) return
        ops.releaseMulticastLock()
    }

    /**
     * Tears down the platform watcher and cancels any pending debounced
     * rebind/retry — only when **both** advertising and discovery intents
     * have been cleared (AUDIT-2026-06 #5 intent-based idle check).
     */
    private suspend fun stopNetworkWatcherIfIdle() {
        if (advertisingIntent || discoveryIntent) return
        if (handle != null) return
        if (!ops.isWatcherActive()) return

        ops.stopNetworkWatcher()
        scheduleLock.withLock {
            pendingRebindJob?.cancel()
            pendingRebindJob = null
        }
        rebindRetryJob?.cancel()
        rebindRetryJob = null
        rebindRetryAttempts = 0
        retryTargetInitialized = false
        retryTarget = null
        retryDefaultTarget = null
        boundNetwork = null
        boundDefaultNetwork = null
    }

    private fun scheduleRebindRetry(error: Throwable) {
        val attempt = ++rebindRetryAttempts
        if (attempt <= rebindRetryMaxAttempts) {
            val backoffMs = rebindRetryBaseDelayMillis * attempt
            ops.logWarn(
                "rebindNow: binding transaction failed; retry " +
                    "$attempt/$rebindRetryMaxAttempts in ${backoffMs}ms",
                error
            )
            rebindRetryJob?.cancel()
            rebindRetryJob = rebindScope.launch {
                delay(backoffMs)
                rebindNow("binding retry $attempt/$rebindRetryMaxAttempts")
            }
        } else {
            ops.logWarn(
                "rebindNow: binding transaction failed; retry budget exhausted — " +
                    "will re-attempt with a fresh budget on the next network target",
                error
            )
        }
    }

    internal companion object {
        /**
         * Debounce window for back-to-back rotation signals. Android emits
         * multiple `onAvailable` / `onCapabilitiesChanged` ticks per single
         * physical handover (typically 100-400ms apart on Pixel devices);
         * 800ms catches a comfortable majority while keeping perceived
         * recovery latency bounded.
         */
        const val REBIND_DEBOUNCE_MILLIS = 800L

        /**
         * AUDIT-2026-06 (#5): base delay for the self-scheduled retry after a
         * binding-transaction failure in [rebindNow]; attempt N waits N *
         * base (2s, 4s, …
         * 10s) — bounded backoff, never a tight loop.
         */
        const val REBIND_RETRY_BASE_DELAY_MILLIS = 2_000L

        /**
         * AUDIT-2026-06 (#5): max consecutive binding-transaction retries before
         * giving up and waiting for the next genuine network change (which
         * schedules a fresh rebind and, on success, resets the counter).
         */
        const val REBIND_RETRY_MAX_ATTEMPTS = 5
    }
}
