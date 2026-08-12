@file:OptIn(ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.core.PeerId
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.DiscoveryTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportHint
import kotlin.concurrent.Volatile
import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.cinterop.toKString
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import platform.Network.nw_advertise_descriptor_create_bonjour_service
import platform.Network.nw_advertise_descriptor_set_no_auto_rename
import platform.Network.nw_advertise_descriptor_set_txt_record_object
import platform.Network.nw_advertise_descriptor_t
import platform.Network.nw_browse_descriptor_create_bonjour_service
import platform.Network.nw_browse_descriptor_set_include_txt_record
import platform.Network.nw_browse_result_change_result_added
import platform.Network.nw_browse_result_change_result_removed
import platform.Network.nw_browse_result_change_txt_record_changed
import platform.Network.nw_browse_result_copy_endpoint
import platform.Network.nw_browse_result_copy_txt_record_object
import platform.Network.nw_browse_result_get_changes
import platform.Network.nw_browse_result_t
import platform.Network.nw_browser_cancel
import platform.Network.nw_browser_create
import platform.Network.nw_browser_set_browse_results_changed_handler
import platform.Network.nw_browser_set_queue
import platform.Network.nw_browser_set_state_changed_handler
import platform.Network.nw_browser_start
import platform.Network.nw_browser_state_cancelled
import platform.Network.nw_browser_state_failed
import platform.Network.nw_browser_state_ready
import platform.Network.nw_browser_state_waiting
import platform.Network.nw_browser_t
import platform.Network.nw_endpoint_get_bonjour_service_name
import platform.Network.nw_error_get_error_code
import platform.Network.nw_listener_set_advertise_descriptor
import platform.Network.nw_listener_t
import platform.Network.nw_parameters_create
import platform.Network.nw_parameters_get_include_peer_to_peer
import platform.Network.nw_parameters_iterate_prohibited_interface_types
import platform.Network.nw_parameters_prohibit_interface_type
import platform.Network.nw_parameters_set_include_peer_to_peer
import platform.Network.nw_parameters_t
import platform.Network.nw_interface_type_cellular
import platform.Foundation.NSLock

/** Build one browser policy symmetric with listener/outbound LAN policy. */
internal fun createAppleLanBrowserParameters(): nw_parameters_t {
    val parameters = nw_parameters_create()
    nw_parameters_prohibit_interface_type(parameters, nw_interface_type_cellular)
    nw_parameters_set_include_peer_to_peer(parameters, true)
    return parameters
}

internal fun appleLanBrowserIncludesPeerToPeerForTest(parameters: nw_parameters_t): Boolean =
    nw_parameters_get_include_peer_to_peer(parameters)

internal fun appleLanBrowserProhibitsCellularForTest(parameters: nw_parameters_t): Boolean {
    var prohibitsCellular = false
    nw_parameters_iterate_prohibited_interface_types(parameters) { type ->
        if (type == nw_interface_type_cellular) prohibitsCellular = true
        true
    }
    return prohibitsCellular
}

/**
 * iOS LAN [DiscoveryTransport].
 *
 * Browsing uses `nw_browser_t`; advertising rides on the listener inside
 * [IosLanDataTransport] via `nw_listener_set_advertise_descriptor`.
 *
 * NWBrowser owns DNS-SD TTL expiry: a result remains live until its matching
 * native removal callback. Core therefore does not require cache-derived
 * heartbeat events. A small reconciliation loop exists only to retire entries
 * owned by a replaced browser generation that can no longer send removals.
 *
 * **Diagnostics:** every browser state change, every result-change call,
 * every TXT decode, and every filter outcome is appended to
 * [IosLanDebug.events]. The iOS sample subscribes to that non-replaying flow
 * for an in-app log; release consumers can ignore it.
 */
internal class IosLanDiscoveryTransport(
    private val transportContext: TransportContext,
    private val endpointRegistry: IosEndpointRegistry,
    private val dataTransport: IosLanDataTransport
) : DiscoveryTransport {

    override val type: TransportKind = TransportKind.LAN

    private val peerEventRelay = ReliablePeerEventRelay()
    override val events: Flow<PeerEvent> = peerEventRelay.events

    private val lock = Mutex()

    @Volatile
    private var advertising: Boolean = false

    private class BrowserLease(
        val handle: nw_browser_t,
        val generation: Int,
        @Volatile var recoveryAttempt: Int
    )

    @Volatile
    private var browser: BrowserLease? = null

    @Volatile
    private var browserReady: Boolean = false

    /**
     * V0.4-IOS-FOREGROUND-REBIND follow-up: tracks whether the host app
     * asked us to be discovering (via [startDiscovery]), independent of
     * whether the current [browser] instance is alive. The two diverge
     * when iOS reaps DNS-SD subscriptions during app suspension — the
     * `nw_browser_t` transitions to `failed` and the state-changed
     * handler nulls [browser], but the host's intent (we should still
     * be browsing) is unchanged. [onBeforeListenerRebind] reads this
     * flag instead of `browser != null` so the post-rebind hook can
     * correctly recreate a fresh browser after a sleep/wake cycle.
     */
    @Volatile
    private var discoveryStartedByHost: Boolean = false

    /**
     * V0.4-IOS-LISTENER-REBIND: the most recent [LocalPeerInfo] passed to
     * [startAdvertising], retained so [onAfterListenerRebind] can rebuild
     * the advertise descriptor on the new listener. Cleared in
     * [stopAdvertising]. Bonjour identity stability across rebinds
     * depends on reusing this exact instance — the peerId / service name
     * / TXT contents are all derived from it.
     */
    @Volatile
    private var cachedLocalPeer: LocalPeerInfo? = null

    /**
     * V0.4-D-IOS-NUDGE: scope for the post-rebind Bonjour re-announce
     * nudge. SupervisorJob so a failed nudge doesn't poison the scope for
     * subsequent rebinds. Lives for the transport's lifetime.
     */
    private val nudgeScope: CoroutineScope =
        CoroutineScope(SupervisorJob() + Dispatchers.Default)

    private val browserScheduleMutex = Mutex()

    @Volatile
    private var pendingBrowserRecoveryJob: Job? = null

    /** Most recent pending nudge job; superseded on each new rebind. */
    @Volatile
    private var pendingNudgeJob: Job? = null

    /**
     * Peers seen by the current browse session. [announceCacheLock] serializes
     * cache, endpoint-registry, and event side effects across the native browse
     * callback queue and the stale-generation reconciliation coroutine.
     *
     * AUDIT-2026-06 (#8): each entry is stamped with the [browserGeneration]
     * that last CONFIRMED it via a browse result (added / TXT-changed).
     * `refresh()` and the rebind hooks cancel + recreate the NWBrowser
     * without any `result_removed` callbacks for peers that vanished while
     * the browser was being replaced, so an unconditional re-announce would
     * retain such ghosts after native ownership is gone. The reconciliation
     * loop prunes — via the shared lost-emission path — entries an older generation owns
     * once they stay unconfirmed for [ANNOUNCE_STALE_GRACE_TICKS] announce
     * cycles (~10 s grace for the replacement browser to re-add live peers).
     * See [reconcileAnnounceCache] for the pure decision logic.
     */
    private val announceCacheLock = NSLock()
    private var announceCache: Map<String, AnnounceEntry> = emptyMap()

    /**
     * AUDIT-2026-06 (#8): incremented (under [lock]) every time a new
     * NWBrowser instance is built in [createBrowserLocked] — initial
     * [startDiscovery], [refresh], and the listener-rebind recreate path all
     * funnel through there. Browse-result callbacks stamp [announceCache]
     * entries with this value; see the cache KDoc for the reconcile
     * contract. Volatile: written under [lock], read from the browse
     * callback queue and the announce coroutine.
     */
    @Volatile
    private var browserGeneration: Int = 0

    /** Re-announce loop for [announceCache]; runs while discovery is on. */
    @Volatile
    private var announceJob: Job? = null

    init {
        // Wire the listener-rebind hooks at factory construction time —
        // both transports are built together by `IosLanTransportFactory`,
        // so dataTransport is fully constructed and ready to accept hook
        // wiring before either transport is started.
        dataTransport.beforeListenerRebind = ::onBeforeListenerRebind
        dataTransport.afterListenerRebind = ::onAfterListenerRebind
    }

    override suspend fun startAdvertising(localPeer: LocalPeerInfo) = lock.withLock {
        if (advertising) return@withLock
        logAppleLanPackagingIssues(transportContext.lanServiceTypeBonjour, "startAdvertising")
        IosLanDebug.log(
            "advertise",
            "starting: peerId=${localPeer.peerId.value.take(8)} app=${localPeer.appId.value} name=${localPeer.deviceName}"
        )
        val descriptor = buildAdvertiseDescriptor(localPeer)
        // Listener may be null in the rebind rebuild window (or after a
        // failed rebind); passing null into the non-null nw parameter would
        // NPE-crash the process. Record intent — onAfterListenerRebind
        // re-applies the descriptor once a fresh listener exists
        // (AUDIT-2026-06 fix).
        val l = dataTransport.listener
        if (l != null) {
            nw_listener_set_advertise_descriptor(l, descriptor)
        } else {
            IosLanDebug.log("advertise", "listener null (rebind window?) — descriptor deferred to rebind hook")
        }
        advertising = true
        cachedLocalPeer = localPeer
        IosLanDebug.log("advertise", "started")
    }

    override suspend fun stopAdvertising() = lock.withLock {
        cancelPendingNudgeLocked()
        if (!advertising) return@withLock
        IosLanDebug.log("advertise", "stopping")
        val l = dataTransport.listener
        if (l != null) {
            nw_listener_set_advertise_descriptor(l, null)
        }
        advertising = false
        cachedLocalPeer = null
    }

    override suspend fun startDiscovery() = lock.withLock {
        if (browser != null) return@withLock
        logAppleLanPackagingIssues(transportContext.lanServiceTypeBonjour, "startDiscovery")
        IosLanDebug.log(
            "browse",
            "startDiscovery: type=${transportContext.lanServiceTypeBonjour} app=${transportContext.appId.value} localPid=${transportContext.localPeerId.value.take(8)}"
        )
        discoveryStartedByHost = true
        try {
            createBrowserLocked(recoveryAttempt = 0)
        } catch (cancelled: CancellationException) {
            discoveryStartedByHost = false
            throw cancelled
        } catch (error: Exception) {
            discoveryStartedByHost = false
            throw error
        }
        startAnnounceLoopLocked()
    }

    private inline fun <T> withAnnounceCacheLock(block: () -> T): T {
        announceCacheLock.lock()
        return try {
            block()
        } finally {
            announceCacheLock.unlock()
        }
    }

    /** Caller must hold [lock]. Idempotent. */
    private fun startAnnounceLoopLocked() {
        if (announceJob?.isActive == true) return
        announceJob = nudgeScope.launch {
            while (isActive) {
                delay(STALE_RECONCILE_INTERVAL_MS)
                if (!discoveryStartedByHost) continue
                // One native lock serializes reconcile/loss side effects with
                // browse re-adds. A fresh result either wins first and is
                // retained, or follows Lost and publishes a correctly ordered
                // Found; stale prune can no longer delete a fresh endpoint.
                val effectiveGeneration =
                    if (browserReady) browserGeneration else browserGeneration + 1
                reconcileAnnounceCacheAtomically(
                    currentGeneration = effectiveGeneration,
                    graceTicks = ANNOUNCE_STALE_GRACE_TICKS,
                    onLost = { pid ->
                        IosLanDebug.log(
                            "browse",
                            "announce loop: pruning ghost pid=${pid.take(8)} — not " +
                                "re-confirmed by browser generation $effectiveGeneration"
                        )
                        emitLostByIdLocked(pid, removeCacheEntry = false)
                    }
                )
            }
        }
    }

    /**
     * Commit reconcile, endpoint removal, and Lost/Updated publication as one
     * cache transaction. A concurrent fresh confirmation cannot be deleted by
     * a stale prune after the reconcile snapshot has been committed.
     */
    internal fun reconcileAnnounceCacheAtomically(
        currentGeneration: Int,
        graceTicks: Int,
        onLost: (String) -> Unit
    ) = withAnnounceCacheLock {
        val result = reconcileAnnounceCache(
            cache = announceCache,
            currentGeneration = currentGeneration,
            graceTicks = graceTicks
        )
        announceCache = result.updatedCache
        result.lostPeerIds.forEach(onLost)
    }

    internal fun confirmAnnounceEntryAtomically(
        pid: String,
        entry: AnnounceEntry,
        isCurrentGeneration: () -> Boolean = { true },
        onConfirmed: () -> Unit = {}
    ): Boolean = withAnnounceCacheLock {
        if (!isCurrentGeneration()) return@withAnnounceCacheLock false
        announceCache = announceCache + (pid to entry)
        onConfirmed()
        true
    }

    internal fun announceEntryForTest(pid: String): AnnounceEntry? =
        withAnnounceCacheLock { announceCache[pid] }

    override suspend fun stopDiscovery() = lock.withLock {
        // Clear host intent BEFORE the browser null-check: when iOS reaps the
        // browser during suspension the field is already null, and the old
        // early-return left discoveryStartedByHost=true — the next rebind
        // silently resurrected browsing the host had stopped
        // (AUDIT-2026-06 fix).
        discoveryStartedByHost = false
        cancelPendingBrowserRecoveryLocked()
        announceJob?.cancel()
        announceJob = null
        // Retire the native generation, opaque endpoint leases, announce
        // cache, and core-visible peer state as one ownership transaction.
        // A queued result callback either commits before this block and is
        // then withdrawn, or observes the retired generation/host intent and
        // cannot resurrect a peer after stop.
        val lease = withAnnounceCacheLock {
            val current = browser
            browser = null
            browserReady = false
            announceCache = emptyMap()
            endpointRegistry.clear()
            peerEventRelay.clear()
            current
        } ?: return@withLock
        IosLanDebug.log("browse", "stopDiscovery: cancelling browser")
        nw_browser_cancel(lease.handle)
    }

    /**
     * V0.4-DISCOVERY-REFRESH: cancel and immediately recreate the NWBrowser
     * so a fresh Bonjour query goes out on the wire. Called by
     * SessionManager when an outgoing session enters Reconnecting — closes
     * the gap where the remote peer rebound to a new port but we haven't
     * received the unsolicited announce yet.
     *
     * Reads [discoveryStartedByHost] (not the [browser] field) because iOS
     * may have transiently nulled the browser between the host's intent
     * and now — we want to honour the host's intent regardless.
     *
     * No-op if the host hasn't started discovery.
     */
    override suspend fun refresh() = lock.withLock {
        if (!discoveryStartedByHost) {
            IosLanDebug.log("browse", "refresh: host not discovering — skipping")
            return@withLock
        }
        IosLanDebug.log("browse", "refresh: cancel + recreate browser to flush Bonjour cache")
        val previous = withAnnounceCacheLock {
            val current = browser
            browser = null
            browserReady = false
            endpointRegistry.clear()
            current
        }
        previous?.handle?.let { nw_browser_cancel(it) }
        try {
            createBrowserLocked(recoveryAttempt = 0)
            IosLanDebug.log("browse", "refresh: fresh browser started")
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Exception) {
            IosLanDebug.log(
                "browse",
                "refresh: browser recreation failed; scheduling bounded recovery (${error.message})"
            )
            scheduleBrowserRecoveryLocked("refresh create failure", attempt = 1)
        }
    }

    // ──────────────────────────────────────────────────────────────────
    // V0.4-IOS-LISTENER-REBIND: listener-rebind hook handlers.
    //
    // These are invoked by IosLanDataTransport.rebindNow while it holds
    // its startMutex. Each handler acquires this transport's [lock]
    // independently — lock order is `data.startMutex -> discovery.lock`,
    // never the reverse (no discovery method calls into data methods
    // that acquire startMutex while holding discovery.lock).
    // ──────────────────────────────────────────────────────────────────

    /**
     * Pre-rebind: cancel the existing browser (if any). The data transport will
     * cancel the listener shortly after this returns, which implicitly
     * drops its attached advertise descriptor — we do NOT need to call
     * `nw_listener_set_advertise_descriptor(..., null)` here.
     *
     * `advertising` flag and [cachedLocalPeer] are intentionally NOT
     * cleared — they're how the after-hook knows to re-attach.
     *
     * Read host intent ([discoveryStartedByHost]) rather than current
     * browser-instance presence — iOS may have already reaped the
     * NWBrowser during app suspension, nulling [browser] before this
     * hook fires. The host's intent to be discovering is still valid;
     * the after-hook must recreate a fresh browser regardless of the
     * current [browser] field state.
     */
    private suspend fun onBeforeListenerRebind(): Unit = lock.withLock {
        // A nudge is scoped to the listener it captured. It must not issue a
        // delayed descriptor mutation after that native listener is retired.
        cancelPendingNudgeLocked()
        val previous = withAnnounceCacheLock {
            val current = browser
            browser = null
            browserReady = false
            // A queued result either commits before this transaction and is
            // cleared here, or observes the retired browser and cannot commit.
            endpointRegistry.clear()
            current
        }
        previous?.handle?.let { b ->
            IosLanDebug.log("browse", "rebind: cancelling old browser")
            nw_browser_cancel(b)
        }
        IosLanDebug.log(
            "browse",
            "rebind: pre-rebind state captured " +
                "(advertising=$advertising discoveryIntent=$discoveryStartedByHost " +
                "cachedPeer=${cachedLocalPeer?.peerId?.value?.take(8)})"
        )
    }

    /**
     * Post-rebind: re-attach the advertise descriptor on the new listener
     * (preserving Bonjour identity via [cachedLocalPeer] reuse), and
     * recreate the browser when the host still requests discovery and no
     * browser already exists. A start racing between the hooks may create the
     * browser first; the native-instance check prevents a duplicate. A stop
     * revokes intent, so current intent/state are the restoration sources.
     */
    private suspend fun onAfterListenerRebind(newListener: nw_listener_t): Unit = lock.withLock {
        if (advertising) {
            val cached = cachedLocalPeer
            if (cached != null) {
                val descriptor = buildAdvertiseDescriptor(cached)
                nw_listener_set_advertise_descriptor(newListener, descriptor)
                IosLanDebug.log(
                    "advertise",
                    "rebind: re-attached descriptor on new listener " +
                        "(peerId=${cached.peerId.value.take(8)} name=${cached.deviceName})"
                )
                scheduleBonjourReannounceNudge(newListener, cached)
            } else {
                IosLanDebug.log(
                    "advertise",
                    "rebind: advertising=true but cachedLocalPeer=null — advertise NOT restored"
                )
            }
        } else {
            IosLanDebug.log("advertise", "rebind: was not advertising; nothing to re-attach")
        }
        if (discoveryStartedByHost && browser == null) {
            try {
                createBrowserLocked(recoveryAttempt = 0)
                IosLanDebug.log("browse", "rebind: browser recreated on new listener queue")
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                IosLanDebug.log(
                    "browse",
                    "rebind: browser recreation failed; scheduling bounded recovery (${error.message})"
                )
                scheduleBrowserRecoveryLocked("listener rebind create failure", attempt = 1)
            }
        } else {
            IosLanDebug.log(
                "browse",
                "rebind: browser restore not required by current host intent/state"
            )
        }
    }

    /**
     * V0.4-D-IOS-NUDGE: force Apple's mDNSResponder to emit a fresh
     * goodbye + announce sequence on the new interface.
     *
     * Background: when the listener rebinds during a Wi-Fi flap, Apple's
     * mDNSResponder may have multicast its previous announcement on a
     * dying interface (Wi-Fi just went off) so the new-port announcement
     * never reaches peers. Re-attaching the same descriptor onto the new
     * listener is often treated as a no-op by mDNSResponder because the
     * service identity (name+type) is unchanged.
     *
     * The nudge: after a small delay (so the rebind's initial registration
     * settles), explicitly null the descriptor (mDNS goodbye), wait for the
     * goodbye to multicast, then re-attach (mDNS fresh announcement). This
     * gives any peer whose cache is holding the pre-flap port a clear
     * "service-removed then service-added" sequence to act on.
     *
     * Runs on a separate scope so the rebind path returns promptly. The
     * pending job is cancelled if a fresh rebind supersedes us — only the
     * latest rebind's nudge needs to fire. Each step re-acquires [lock]
     * and re-checks state, so a `stopAdvertising` (or another rebind)
     * mid-nudge aborts cleanly without leaving the listener mis-configured.
     */
    private fun scheduleBonjourReannounceNudge(
        listener: nw_listener_t,
        peer: LocalPeerInfo
    ) {
        pendingNudgeJob?.cancel()
        pendingNudgeJob = nudgeScope.launch {
            // Let the rebind's normal announcement complete first.
            delay(NUDGE_INITIAL_DELAY_MS)
            lock.withLock {
                if (!advertising || cachedLocalPeer?.peerId != peer.peerId) {
                    IosLanDebug.log(
                        "advertise",
                        "rebind: nudge skipped — advertise state changed before goodbye"
                    )
                    return@withLock
                }
                IosLanDebug.log(
                    "advertise",
                    "rebind: nudge — deregistering descriptor (mDNS goodbye)"
                )
                nw_listener_set_advertise_descriptor(listener, null)
            }
            // Wait for the goodbye to multicast before the fresh announce.
            delay(NUDGE_GAP_MS)
            lock.withLock {
                if (!advertising || cachedLocalPeer?.peerId != peer.peerId) {
                    IosLanDebug.log(
                        "advertise",
                        "rebind: nudge — skipping re-register (state changed mid-nudge)"
                    )
                    return@withLock
                }
                val freshDescriptor = buildAdvertiseDescriptor(peer)
                nw_listener_set_advertise_descriptor(listener, freshDescriptor)
                IosLanDebug.log(
                    "advertise",
                    "rebind: nudge — re-registered descriptor (mDNS fresh announce)"
                )
            }
        }
    }

    /** Caller holds [lock], so the nudge cannot concurrently own that lock. */
    private suspend fun cancelPendingNudgeLocked() {
        val pending = pendingNudgeJob
        pendingNudgeJob = null
        pending?.cancelAndJoin()
    }

    /**
     * Browser-creation body, extracted so [startDiscovery] and
     * [onAfterListenerRebind] share the same lifecycle code. Caller MUST
     * hold [lock] and MUST have checked that [browser] is null.
     */
    private fun createBrowserLocked(recoveryAttempt: Int) {
        // AUDIT-2026-06 (#8): every new browser instance opens a fresh
        // generation. Entries in [announceCache] confirmed by an older
        // generation are ghost candidates until this browser re-adds them.
        beginBrowserGeneration()
        val descriptor = nw_browse_descriptor_create_bonjour_service(
            type = transportContext.lanServiceTypeBonjour,
            domain = null
        )
        nw_browse_descriptor_set_include_txt_record(descriptor, true)

        val browserParams = createAppleLanBrowserParameters()
        IosLanDebug.log(
            "browse",
            "browser params: cellular=PROHIBITED, " +
                "include_peer_to_peer=true (AWDL discovery ENABLED)"
        )

        val b = nw_browser_create(descriptor, browserParams)
            ?: error("nw_browser_create returned null")
        val lease = BrowserLease(
            handle = b,
            generation = browserGeneration,
            recoveryAttempt = recoveryAttempt
        )
        withAnnounceCacheLock {
            browser = lease
            browserReady = false
        }

        nw_browser_set_queue(b, dataTransport.queue)
        nw_browser_set_state_changed_handler(b) browserStateHandler@ { state, error ->
            val label = when (state) {
                nw_browser_state_ready -> "ready"
                nw_browser_state_waiting -> "waiting"
                nw_browser_state_failed -> "failed"
                nw_browser_state_cancelled -> "cancelled"
                else -> "raw=$state"
            }
            val errorCode = error?.let { nw_error_get_error_code(it) }
            IosLanDebug.log(
                "browse",
                "state -> $label" + (errorCode?.let { " errCode=$it" } ?: "")
            )
            if (state == nw_browser_state_waiting || state == nw_browser_state_failed) {
                logAppleLanPackagingIssues(
                    transportContext.lanServiceTypeBonjour,
                    "browser state=$label errCode=${errorCode ?: 0}"
                )
            }
            when (state) {
                nw_browser_state_ready -> withAnnounceCacheLock {
                    if (browser === lease) {
                        browserReady = true
                        lease.recoveryAttempt = 0
                    }
                }
                nw_browser_state_failed, nw_browser_state_cancelled -> {
                    // Break the native callback-retention graph for both
                    // expected and unexpected terminal transitions.
                    nw_browser_set_browse_results_changed_handler(lease.handle, null)
                    nw_browser_set_state_changed_handler(lease.handle, null)
                    // Identity check: this handler belongs to `b`. refresh()
                    // cancels the old browser and installs a replacement; the
                    // old instance's async cancelled callback must not clobber
                    // the field, or the replacement is orphaned (still browsing,
                    // unreachable, re-created again on the next refresh — an
                    // accumulating leak during the ~3s Reconnecting refresh
                    // cadence). Only clear state for the CURRENT browser
                    // (AUDIT-2026-06 fix).
                    val shouldRecover = withAnnounceCacheLock {
                        if (browser === lease) {
                            browserReady = false
                            browser = null
                            endpointRegistry.clear()
                            true
                        } else {
                            false
                        }
                    }
                    if (shouldRecover) {
                        scheduleBrowserRecoveryFromCallback(
                            reason = "browser state=$label",
                            attempt = lease.recoveryAttempt + 1
                        )
                    }
                }
            }
            return@browserStateHandler
        }
        nw_browser_set_browse_results_changed_handler(b) browserResultsHandler@ { old, new, batchComplete ->
            // AUDIT-2026-06 (#15): same identity guard as the state handler
            // above — refresh()/rebind cancel this browser and install a
            // replacement, and a stale instance's queued result callbacks
            // (e.g. a result_removed for a peer the CURRENT browser still
            // sees) must not mutate the announce cache / endpoint registry
            // or emit Lost once a newer browser owns the field.
            if (browser === lease) {
                handleBrowseResultChange(
                    old = old,
                    new = new,
                    batchComplete = batchComplete,
                    generation = lease.generation
                )
            }
            return@browserResultsHandler
        }
        nw_browser_start(b)
        IosLanDebug.log("browse", "nw_browser_start invoked")
    }

    private fun beginBrowserGeneration() {
        browserGeneration++
        // Endpoints are opaque objects owned by the browser/path generation
        // that produced them. Never let a fresh browser inherit dialable
        // values from an older native owner.
        endpointRegistry.clear()
    }

    internal fun beginBrowserGenerationForTest() = beginBrowserGeneration()

    /** Deterministic rebind interleaving seams for Apple lifecycle tests. */
    internal suspend fun beforeListenerRebindForTest() = onBeforeListenerRebind()

    internal suspend fun afterListenerRebindForTest(newListener: nw_listener_t) =
        onAfterListenerRebind(newListener)

    private fun scheduleBrowserRecoveryFromCallback(reason: String, attempt: Int) {
        nudgeScope.launch {
            lock.withLock {
                if (!discoveryStartedByHost || browser != null) return@withLock
                scheduleBrowserRecoveryLocked(reason, attempt)
            }
        }
    }

    /** Caller holds [lock]. */
    private fun scheduleBrowserRecoveryLocked(reason: String, attempt: Int) {
        if (!discoveryStartedByHost || browser != null) return
        if (attempt > BROWSER_RECOVERY_MAX_ATTEMPTS) {
            IosLanDebug.log(
                "browse",
                "browser recovery budget exhausted after ${attempt - 1} attempt(s): $reason"
            )
            return
        }
        nudgeScope.launch(start = CoroutineStart.UNDISPATCHED) {
            browserScheduleMutex.withLock {
                pendingBrowserRecoveryJob?.cancel()
                pendingBrowserRecoveryJob = nudgeScope.launch {
                    delay(BROWSER_RECOVERY_BASE_DELAY_MS * attempt)
                    lock.withLock {
                        if (!discoveryStartedByHost || browser != null) return@withLock
                        try {
                            createBrowserLocked(recoveryAttempt = attempt)
                            IosLanDebug.log(
                                "browse",
                                "browser recovery $attempt/$BROWSER_RECOVERY_MAX_ATTEMPTS started"
                            )
                        } catch (cancelled: CancellationException) {
                            throw cancelled
                        } catch (error: Exception) {
                            IosLanDebug.log(
                                "browse",
                                "browser recovery attempt $attempt failed (${error.message})"
                            )
                            scheduleBrowserRecoveryLocked(reason, attempt + 1)
                        }
                    }
                }
            }
        }
    }

    /** Caller holds [lock]. */
    private suspend fun cancelPendingBrowserRecoveryLocked() {
        browserScheduleMutex.withLock {
            pendingBrowserRecoveryJob?.cancel()
            pendingBrowserRecoveryJob = null
        }
    }

    private fun buildAdvertiseDescriptor(localPeer: LocalPeerInfo): nw_advertise_descriptor_t {
        val descriptor = nw_advertise_descriptor_create_bonjour_service(
            name = localPeer.peerId.value,
            type = transportContext.lanServiceTypeBonjour,
            domain = null
        ) ?: error("nw_advertise_descriptor_create_bonjour_service returned null")
        nw_advertise_descriptor_set_no_auto_rename(descriptor, true)

        val properties = buildLanTxtProperties(
            peerId = localPeer.peerId,
            appId = localPeer.appId,
            deviceName = localPeer.deviceName,
            platform = localPeer.platform,
            supportedTransports = localPeer.supportedTransports,
            protocolVersion = transportContext.lanProtocolVersion,
            fingerprint = transportContext.localFingerprint
        )
        val txt = IosBonjour.mapToTxtRecord(
            properties
        )
        nw_advertise_descriptor_set_txt_record_object(descriptor, txt)
        return descriptor
    }

    private fun handleBrowseResultChange(
        old: nw_browse_result_t,
        new: nw_browse_result_t,
        batchComplete: Boolean,
        generation: Int
    ) {
        val changes = nw_browse_result_get_changes(old, new)
        val added = (changes and nw_browse_result_change_result_added.toULong()) != 0UL
        val removed = (changes and nw_browse_result_change_result_removed.toULong()) != 0UL
        val txtChanged = (changes and nw_browse_result_change_txt_record_changed.toULong()) != 0UL

        IosLanDebug.log(
            "browse",
            "result change: added=$added removed=$removed txtChanged=$txtChanged batchComplete=$batchComplete oldNull=${old == null} newNull=${new == null}"
        )

        if (added && new != null) {
            emitPeer(new, isUpdate = false, generation = generation)
        } else if (removed && old != null) {
            emitLost(old, generation)
        } else if (txtChanged && new != null) {
            emitPeer(new, isUpdate = true, generation = generation)
        }
    }

    private fun emitPeer(result: nw_browse_result_t, isUpdate: Boolean, generation: Int) {
        val endpoint = nw_browse_result_copy_endpoint(result)
        if (endpoint == null) {
            IosLanDebug.log("browse", "emitPeer: copy_endpoint returned null — skip")
            return
        }
        val txt = nw_browse_result_copy_txt_record_object(result)
        val decoded = IosBonjour.decodeTxtRecord(txt)
        if (decoded.malformed) {
            IosLanDebug.log("browse", "emitPeer: malformed TXT record — skip")
            return
        }
        val attrs = decoded.properties
        IosLanDebug.log("browse", "emitPeer: txt=$attrs (isUpdate=$isUpdate)")

        val record = validateLanDiscoveryRecord(
            properties = attrs,
            expectedAppId = transportContext.appId,
            localPeerId = transportContext.localPeerId,
            securityProfile = transportContext.securityProfile
        ) ?: run {
            IosLanDebug.log("browse", "emitPeer: filter — invalid/bounded TXT schema")
            return
        }
        val servicePid = validDiscoveryPeerIdOrNull(
            nw_endpoint_get_bonjour_service_name(endpoint)?.toKString()
        )
        if (servicePid != record.peerId.value) {
            IosLanDebug.log(
                "browse",
                "emitPeer: filter — Bonjour service identity does not match TXT peer id"
            )
            return
        }
        val peerId = record.peerId
        val internalPeer = record.toInternalPeer(TransportHint(type = TransportKind.LAN))
        // AUDIT-2026-06 (#8): stamp the entry with the generation that
        // confirmed it. A live peer re-added by a replacement browser gets
        // re-stamped here and keeps being announced; a ghost keeps its old
        // generation and is pruned by the announce loop.
        val committed = confirmAnnounceEntryAtomically(
            pid = peerId.value,
            entry = AnnounceEntry(internalPeer, lastConfirmedGeneration = generation),
            isCurrentGeneration = {
                // A generation can become stale between native callback entry
                // and parsing. Never let that queued result replace current
                // ownership.
                discoveryStartedByHost &&
                    generation == browserGeneration &&
                    browser?.generation == generation
            },
            onConfirmed = {
                endpointRegistry.put(peerId, endpoint, browserGeneration = generation)
                peerEventRelay.upsert(internalPeer)
            }
        )
        if (!committed) return
        IosLanDebug.log(
            "browse",
            "emitPeer: ACCEPTED ${if (isUpdate) "Updated" else "Found"} " +
                "${record.deviceName} pid=${peerId.value.take(8)}"
        )
    }

    private fun emitLost(result: nw_browse_result_t, generation: Int) {
        val txt = nw_browse_result_copy_txt_record_object(result)
        val decoded = IosBonjour.decodeTxtRecord(txt)
        if (decoded.malformed) {
            IosLanDebug.log("browse", "emitLost: malformed TXT record — skip")
            return
        }
        val attrs = decoded.properties
        val endpoint = nw_browse_result_copy_endpoint(result)
        val servicePid = endpoint?.let {
            validDiscoveryPeerIdOrNull(
                nw_endpoint_get_bonjour_service_name(it)?.toKString()
            )
        }
        if (servicePid == null) {
            IosLanDebug.log("browse", "emitLost: Bonjour service identity unavailable — skip")
            return
        }

        // Removed results may omit TXT entirely. Present fields must not
        // contradict the service identity/app, and the cache requirement in
        // emitLostById limits an incomplete removal to a peer whose complete
        // Found record already passed app, protocol, and fingerprint checks.
        if (LanConstants.TXT_PEER_ID in attrs) {
            val txtPid = validDiscoveryPeerIdOrNull(attrs[LanConstants.TXT_PEER_ID])
            if (txtPid == null || txtPid != servicePid) {
                IosLanDebug.log("browse", "emitLost: filter — invalid or mismatched TXT peer identity")
                return
            }
        }
        if (LanConstants.TXT_APP_ID in attrs) {
            val app = validLanTxtValueOrNull(
                LanConstants.TXT_APP_ID,
                attrs[LanConstants.TXT_APP_ID]
            )
            if (app == null || app != transportContext.appId.value) {
                IosLanDebug.log("browse", "emitLost: filter — invalid or mismatched appId")
                return
            }
        }
        val carriesSecurityMetadata =
            LanConstants.TXT_PROTOCOL_VERSION in attrs || LanConstants.TXT_FINGERPRINT in attrs
        if (
            carriesSecurityMetadata &&
            validateLanDiscoverySecurityMetadata(
                profile = transportContext.securityProfile,
                protocolVersion = attrs[LanConstants.TXT_PROTOCOL_VERSION],
                fingerprint = attrs[LanConstants.TXT_FINGERPRINT]
            ) == null
        ) {
            IosLanDebug.log("browse", "emitLost: filter — contradictory security metadata")
            return
        }
        emitLostById(
            pid = servicePid,
            expectedGeneration = generation,
            requireCachedPeer = true
        )
    }

    /** Real Network.framework failure seam used by the Apple lifecycle suite. */
    internal fun cancelCurrentBrowserForTest() {
        browser?.handle?.let { nw_browser_cancel(it) }
    }

    internal val browserGenerationForTest: Int
        get() = browserGeneration

    internal val hasBrowserForTest: Boolean
        get() = browser != null

    internal val hasPendingNudgeForTest: Boolean
        get() = pendingNudgeJob?.isActive == true

    /**
     * Shared lost-emission path: browse `result_removed` callbacks land here
     * via [emitLost], and the announce loop's generation prune
     * (AUDIT-2026-06 #8) calls it directly with the cached peer id. The
     * cache removal is idempotent — the prune path has already dropped the
     * entry via [reconcileAnnounceCache]'s updated map.
     */
    private fun emitLostById(
        pid: String,
        expectedGeneration: Int? = null,
        requireCachedPeer: Boolean = false
    ) {
        withAnnounceCacheLock {
            if (expectedGeneration != null && browser?.generation != expectedGeneration) {
                return@withAnnounceCacheLock
            }
            if (requireCachedPeer && pid !in announceCache) return@withAnnounceCacheLock
            emitLostByIdLocked(pid, removeCacheEntry = true)
        }
    }

    /** Caller holds [announceCacheLock]. */
    private fun emitLostByIdLocked(pid: String, removeCacheEntry: Boolean) {
        if (pid == transportContext.localPeerId.value) return
        // AUDIT-2026-07 (RBS-1): both callers validate their input (emitLost
        // from the raw TXT record, the announce-loop prune from entries that
        // were validated on insert), but a blank pid must never reach the
        // throwing PeerId constructor from this shared path.
        if (validDiscoveryPeerIdOrNull(pid) == null) return
        val peerId = PeerId(pid)
        if (removeCacheEntry) announceCache = announceCache - pid
        endpointRegistry.remove(peerId)
        peerEventRelay.remove(peerId)
        IosLanDebug.log("browse", "emitLost: $pid")
    }

    private companion object {
        /** Cadence for retiring entries owned by a replaced browser generation. */
        const val STALE_RECONCILE_INTERVAL_MS: Long = 5_000

        /**
         * V0.4-D-IOS-NUDGE: wait this long after a listener rebind before
         * deregistering the Bonjour descriptor. Gives mDNSResponder time
         * to finish the rebind's initial announcement.
         */
        const val NUDGE_INITIAL_DELAY_MS: Long = 150

        /**
         * V0.4-D-IOS-NUDGE: gap between mDNS goodbye (descriptor=null) and
         * fresh announce (descriptor re-set). Lets the goodbye packet
         * multicast before the re-announce overwrites the responder's
         * internal state.
         */
        const val NUDGE_GAP_MS: Long = 100

        /**
         * AUDIT-2026-06 (#8): consecutive announce ticks an [announceCache]
         * entry may stay unconfirmed by the current [browserGeneration]
         * before the announce loop prunes it and emits [PeerEvent.Lost].
         * 2 ticks × [STALE_RECONCILE_INTERVAL_MS] ≈ 10 s of grace for a
         * replacement browser to re-add a live peer — comfortably longer
         * than NWBrowser's typical sub-second result delivery, comfortably
         * shorter than retaining a native-ownership ghost indefinitely.
         */
        const val ANNOUNCE_STALE_GRACE_TICKS: Int = 2

        const val BROWSER_RECOVERY_BASE_DELAY_MS: Long = 250
        const val BROWSER_RECOVERY_MAX_ATTEMPTS: Int = 5
    }
}

/**
 * AUDIT-2026-06 (#8): one [IosLanDiscoveryTransport.announceCache] entry —
 * the peer to re-announce plus the [IosLanDiscoveryTransport.browserGeneration]
 * that last confirmed it via a browse result, and how many consecutive
 * announce ticks it has gone unconfirmed by the current generation.
 */
internal data class AnnounceEntry(
    val peer: InternalPeer,
    val lastConfirmedGeneration: Int,
    val staleTicks: Int = 0
)

/** Outcome of one [reconcileAnnounceCache] pass. */
internal data class AnnounceReconcileResult(
    /** The cache after this tick (stale counters advanced, ghosts dropped). */
    val updatedCache: Map<String, AnnounceEntry>,
    /** Ids pruned this tick — emit Lost for each. */
    val lostPeerIds: List<String>
)

/**
 * AUDIT-2026-06 (#8): pure per-tick reconciliation for the announce cache.
 *
 * A replaced NWBrowser (refresh / rebind / iOS reaping) never fires
 * `result_removed` for peers that vanished while it was down, so cache
 * entries cannot be trusted just because they exist — only entries the
 * CURRENT browser generation has confirmed are known-live. Per entry:
 *
 *   - `lastConfirmedGeneration == currentGeneration` → retain it and reset
 *     its stale counter; native ownership is the liveness signal.
 *   - stale generation, fewer than [graceTicks] consecutive stale ticks →
 *     keep it (silently — no announce, so PeerRegistry's lastSeen is NOT
 *     refreshed) and advance the counter, giving the new browser time to
 *     re-add a live peer.
 *   - stale generation, [graceTicks] reached → prune it and report it in
 *     [AnnounceReconcileResult.lostPeerIds] so the caller emits Lost.
 *
 * Pure function — no transport state, directly unit-tested in
 * `AnnounceCacheReconcileTest` (appleTest).
 */
internal fun reconcileAnnounceCache(
    cache: Map<String, AnnounceEntry>,
    currentGeneration: Int,
    graceTicks: Int
): AnnounceReconcileResult {
    val retained = mutableMapOf<String, AnnounceEntry>()
    val lost = mutableListOf<String>()
    for ((pid, entry) in cache) {
        if (entry.lastConfirmedGeneration == currentGeneration) {
            retained[pid] = if (entry.staleTicks == 0) entry else entry.copy(staleTicks = 0)
        } else {
            val ticks = entry.staleTicks + 1
            if (ticks >= graceTicks) {
                lost += pid
            } else {
                retained[pid] = entry.copy(staleTicks = ticks)
            }
        }
    }
    return AnnounceReconcileResult(retained, lost)
}
