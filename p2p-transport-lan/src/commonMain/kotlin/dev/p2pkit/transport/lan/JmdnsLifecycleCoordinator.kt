package dev.p2pkit.transport.lan

import dev.p2pkit.core.transport.LocalPeerInfo
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlin.coroutines.CoroutineContext

/**
 * Platform operations behind [JmdnsLifecycleCoordinator] (2026-07 test seam,
 * P1-14). Implemented by `AndroidLanDiscoveryTransport` over JmDNS +
 * `ConnectivityManager`; implemented by fakes in
 * `JmdnsLifecycleCoordinatorTest` (`:p2p-transport-lan:jvmTest`), which is the
 * automated contract for the Android rebind machinery (the same
 * jvm-pins-the-shared-shape convention as `HostSelectorTest` /
 * `JvmRawConnectionCancellationTest`; there are no instrumented Android
 * tests).
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

    /** Register the advertised service on [handle]; returns an opaque token for [unregisterServiceBlocking]. */
    fun registerServiceBlocking(handle: H, localPeer: LocalPeerInfo): Any

    fun unregisterServiceBlocking(handle: H, token: Any)

    /** Add a fresh browse listener on [handle]; returns an opaque token for [removeListenerBlocking]. */
    fun addListenerBlocking(handle: H): Any

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
 * Platform-neutral JmDNS-style lifecycle state machine, extracted verbatim
 * from `AndroidLanDiscoveryTransport` (2026-07, P1-14 seam) so the module's
 * riskiest state machine is unit-testable from `jvmTest` with fake ops —
 * `androidMain` cannot be driven by an automated test in this module (no
 * instrumented tests by repo policy), so the extraction IS the seam.
 * Behavior-preserving: every guard, log line, and ordering below is ported
 * from the audited Android implementation; the AUDIT-2026-06 (#5) marker
 * comments moved here with the code they describe.
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

    /** The live platform handle; null before first start, after idle close, and in the failed-rebind window. */
    private var handle: H? = null

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
     * AUDIT-2026-06 (#5): consecutive create failures in [rebindNow]. Bounds
     * the self-scheduled retry; reset to 0 on the next successful bind and
     * when the watcher stops. Guarded by [lock].
     */
    private var rebindRetryAttempts = 0

    /**
     * AUDIT-2026-06 (#5): pending self-scheduled retry after a create failure
     * in [rebindNow]. Nothing else is guaranteed to call back in after that
     * failure (`refresh()` early-returns on a null handle), so the transport
     * must re-attempt on its own. Cancelled when the watcher stops. Guarded
     * by [lock].
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
        if (advertisedToken != null) return@withLock

        ops.acquireMulticastLock()
        val h = try {
            ensureHandle()
        } catch (e: Throwable) {
            failedStartCleanup()
            throw e
        }
        val token = try {
            withContext(ioContext) { ops.registerServiceBlocking(h, localPeer) }
        } catch (e: Throwable) {
            failedStartCleanup()
            throw e
        }
        advertisedToken = token
        advertisingIntent = true
        cachedLocalPeer = localPeer
        boundNetwork = ops.currentNetwork()
        boundDefaultNetwork = ops.currentNetwork()
        ops.logDebug(
            "startAdvertising: registered, " +
                "boundNetwork=$boundNetwork boundDefaultNetwork=$boundDefaultNetwork"
        )
        ops.startNetworkWatcher()
    }

    suspend fun stopAdvertising(): Unit = lock.withLock {
        // AUDIT-2026-06 (#5): clear intent BEFORE the null-handle check —
        // after a failed rebind the advertised token is null while the host
        // still counts as advertising, and the old `?: return` shape would
        // have skipped the clear, letting the rebind retry resurrect
        // advertising the host just stopped.
        advertisingIntent = false
        val token = advertisedToken
        if (token != null) {
            withContext(ioContext) {
                runCatching { handle?.let { ops.unregisterServiceBlocking(it, token) } }
            }
            advertisedToken = null
            ops.logDebug("stopAdvertising: unregistered")
        }
        cachedLocalPeer = null
        stopNetworkWatcherIfIdle()
        releaseMulticastLockIfIdle()
        closeHandleIfIdle()
    }

    suspend fun startDiscovery(): Unit = lock.withLock {
        if (listenerToken != null) return@withLock

        ops.acquireMulticastLock()
        val h = try {
            ensureHandle()
        } catch (e: Throwable) {
            failedStartCleanup()
            throw e
        }
        val token = try {
            withContext(ioContext) { ops.addListenerBlocking(h) }
        } catch (e: Throwable) {
            failedStartCleanup()
            throw e
        }
        listenerToken = token
        discoveryIntent = true
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
        // AUDIT-2026-06 (#5): mirror stopAdvertising — clear intent before
        // the null-handle check so a failed-rebind window (listener handle
        // null, host still discovering) cannot strand the intent flag true.
        discoveryIntent = false
        // AUDIT-2026-07 (DSC-1): halt the heartbeat — we hold [lock], so an
        // in-flight tick is either parked on the lock (cancelled here) or
        // already finished; no tick can re-emit after the intent flips.
        heartbeatJob?.cancel()
        heartbeatJob = null
        val token = listenerToken
        if (token != null) {
            withContext(ioContext) {
                runCatching { handle?.let { ops.removeListenerBlocking(it, token) } }
            }
            listenerToken = null
            ops.logDebug("stopDiscovery: listener removed")
        }
        stopNetworkWatcherIfIdle()
        releaseMulticastLockIfIdle()
        closeHandleIfIdle()
    }

    /**
     * Serialized access for `refresh()`'s listener rotation: runs [rotate]
     * under [lock] with the live handle and current listener token, skipping
     * (with the original diagnostic) when discovery is not live. [rotate]
     * must call `commitListener(fresh)` as soon as the fresh listener is
     * attached — before removing the old one — so a failure later in the
     * rotation cannot leave the committed token out of sync with what is
     * actually registered (the AUDIT-2026-06 #7 add-first ordering).
     */
    suspend fun refreshDiscovery(
        rotate: suspend (handle: H, oldListenerToken: Any, commitListener: (Any) -> Unit) -> Unit
    ): Unit = lock.withLock {
        val h = handle
        val old = listenerToken
        if (h == null || old == null) {
            ops.logDebug("refresh: no listener active — skipping")
            return@withLock
        }
        rotate(h, old) { fresh -> listenerToken = fresh }
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
                } catch (e: Throwable) {
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
        pendingRebindJob?.cancel()
        ops.logDebug("scheduleRebind: $reason (debounce=${rebindDebounceMillis}ms)")
        pendingRebindJob = rebindScope.launch {
            delay(rebindDebounceMillis)
            rebindNow(reason)
        }
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

        // AUDIT-2026-06 (#5): `handle != null` term — the bound* markers are
        // only updated on a SUCCESSFUL bind, so after a failed rebind (handle
        // torn down, create failed) they still describe the pre-teardown
        // bind. A retry arriving after the network flipped back to the
        // previously-bound one must not be skipped as "no change" while
        // there is no live handle at all.
        val noChangeSinceLastBind =
            handle != null && target == boundNetwork && defaultTarget == boundDefaultNetwork
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

        // Close the old handle — on JmDNS this also flushes its in-process
        // mDNS cache, so resolved peer addresses bound to the old interface
        // don't leak forward into the next round.
        val cached = cachedLocalPeer
        withContext(ioContext) {
            runCatching { handle?.let { ops.closeHandleBlocking(it) } }
        }
        handle = null
        advertisedToken = null
        listenerToken = null

        // Recreate the handle on the new interface. MUST NOT throw out of
        // this coroutine (except cancellation): rebindNow runs fire-and-forget
        // on [rebindScope] (no CoroutineExceptionHandler), so an uncaught
        // IOException here would crash an Android host process. On failure we
        // log, leave the handle null, and self-schedule a bounded retry —
        // nothing external is guaranteed to call back in (refresh()
        // early-returns on a null handle), so relying on "the next callback"
        // bricked the transport on a transient create failure (AUDIT-2026-06
        // #5 fix).
        val rebindTarget = target ?: defaultTarget
        val fresh = try {
            createHandleClosingOrphanOnCancel(rebindTarget, forRebind = true)
        } catch (e: CancellationException) {
            throw e
        } catch (e: Throwable) {
            // Bounded linear backoff (base, 2×base, …), reset on the next
            // successful bind; a genuine network callback still supersedes
            // via scheduleRebind, and rebindNow's own guards stop the retry
            // once the watcher is gone (intent cleared on both sides) or an
            // interleaved rebind restored the handle with no network change.
            val attempt = ++rebindRetryAttempts
            if (attempt <= rebindRetryMaxAttempts) {
                val backoffMs = rebindRetryBaseDelayMillis * attempt
                ops.logWarn(
                    "rebindNow: JmDNS.create failed; retry $attempt/$rebindRetryMaxAttempts " +
                        "in ${backoffMs}ms",
                    e
                )
                rebindRetryJob?.cancel()
                rebindRetryJob = rebindScope.launch {
                    delay(backoffMs)
                    rebindNow("JmDNS.create retry $attempt/$rebindRetryMaxAttempts")
                }
            } else {
                ops.logWarn(
                    "rebindNow: JmDNS.create failed; retry budget exhausted — " +
                        "will re-attempt on the next network change",
                    e
                )
            }
            return@withLock
        }
        handle = fresh
        rebindRetryAttempts = 0

        if (hadAdvertising && cached != null) {
            runCatching {
                val token = withContext(ioContext) { ops.registerServiceBlocking(fresh, cached) }
                advertisedToken = token
                ops.logDebug("rebindNow: registerService completed on fresh JmDNS")
            }.onFailure { e ->
                ops.logWarn("rebindNow: registerService failed", e)
            }
        } else if (hadAdvertising) {
            ops.logWarn("rebindNow: cachedLocalPeer was null; advertising not restored")
        }

        if (hadDiscovery) {
            runCatching {
                val token = withContext(ioContext) { ops.addListenerBlocking(fresh) }
                listenerToken = token
                ops.logDebug("rebindNow: addServiceListener completed on fresh JmDNS")
            }.onFailure { e ->
                ops.logWarn("rebindNow: addServiceListener failed", e)
            }
        }

        boundNetwork = target
        boundDefaultNetwork = defaultTarget
        ops.logDebug(
            "rebindNow: complete; boundNetwork=$target boundDefaultNetwork=$defaultTarget"
        )
    }

    /** Lazily creates the handle bound to the current active network. Called under [lock]. */
    private suspend fun ensureHandle(): H {
        handle?.let { return it }
        val fresh = createHandleClosingOrphanOnCancel(ops.currentNetwork(), forRebind = false)
        handle = fresh
        return fresh
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
                withContext(NonCancellable + ioContext) {
                    runCatching { ops.closeHandleBlocking(orphan) }
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
            releaseMulticastLockIfIdle()
            closeHandleIfIdle()
        }
    }

    private suspend fun closeHandleIfIdle() {
        // AUDIT-2026-06 (#5): idle == host intent cleared on both sides. The
        // old handle-based check misread the failed-rebind window (handles
        // null, host still active) as idle — see the intent-flag KDoc.
        if (advertisingIntent || discoveryIntent) return
        val h = handle ?: return
        handle = null
        withContext(ioContext) { runCatching { ops.closeHandleBlocking(h) } }
        ops.logDebug("closeJmdnsIfIdle: closed handle")
    }

    private fun releaseMulticastLockIfIdle() {
        // AUDIT-2026-06 (#5): intent-based idle check — a failed rebind nulls
        // the handles while the host is still active, and the rebind retry
        // needs the multicast lock kept alive to be useful.
        if (advertisingIntent || discoveryIntent) return
        ops.releaseMulticastLock()
    }

    /**
     * Tears down the platform watcher and cancels any pending debounced
     * rebind/retry — only when **both** advertising and discovery intents
     * have been cleared (AUDIT-2026-06 #5 intent-based idle check).
     */
    private fun stopNetworkWatcherIfIdle() {
        if (advertisingIntent || discoveryIntent) return
        if (!ops.isWatcherActive()) return

        ops.stopNetworkWatcher()
        pendingRebindJob?.cancel()
        pendingRebindJob = null
        rebindRetryJob?.cancel()
        rebindRetryJob = null
        rebindRetryAttempts = 0
        boundNetwork = null
        boundDefaultNetwork = null
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
         * create failure in [rebindNow]; attempt N waits N * base (2s, 4s, …
         * 10s) — bounded backoff, never a tight loop.
         */
        const val REBIND_RETRY_BASE_DELAY_MILLIS = 2_000L

        /**
         * AUDIT-2026-06 (#5): max consecutive create-failure retries before
         * giving up and waiting for the next genuine network change (which
         * schedules a fresh rebind and, on success, resets the counter).
         */
        const val REBIND_RETRY_MAX_ATTEMPTS = 5
    }
}
