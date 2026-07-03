@file:OptIn(ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.DiscoveryTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportHint
import kotlin.concurrent.Volatile
import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.flow.asSharedFlow
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
import platform.Network.nw_listener_set_advertise_descriptor
import platform.Network.nw_listener_t
import platform.Network.nw_parameters_create
import platform.Network.nw_parameters_set_include_peer_to_peer

/**
 * iOS LAN [DiscoveryTransport].
 *
 * Browsing uses `nw_browser_t`; advertising rides on the listener inside
 * [IosLanDataTransport] via `nw_listener_set_advertise_descriptor`.
 *
 * **Refresh loop:** `PeerRegistry` in :p2p-core evicts a peer 15 s after its
 * last `PeerEvent.Found`/`Updated`. NWBrowser only fires "result_added" once
 * per peer (and "result_removed" when a peer leaves), so without a periodic
 * heartbeat the iOS discovery transport's peers would silently disappear
 * from `kit.peers` after 15 s even while NWBrowser still sees them. The
 * refresh loop here re-emits `PeerEvent.Updated` for every cached peer
 * every 5 s as long as discovery is running.
 *
 * **Diagnostics:** every browser state change, every result-change call,
 * every TXT decode, and every filter outcome is appended to
 * [IosLanDebug.events]. The iOS sample subscribes to that flow for an
 * in-app log; from a release consumer's view it's a 200-entry replayable
 * SharedFlow they can ignore.
 */
internal class IosLanDiscoveryTransport(
    private val transportContext: TransportContext,
    private val endpointRegistry: IosEndpointRegistry,
    private val dataTransport: IosLanDataTransport
) : DiscoveryTransport {

    override val type: TransportKind = TransportKind.LAN

    private val _events = MutableSharedFlow<PeerEvent>(
        replay = 0,
        extraBufferCapacity = 256,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )
    override val events: Flow<PeerEvent> = _events.asSharedFlow()

    private val lock = Mutex()

    @Volatile
    private var advertising: Boolean = false

    @Volatile
    private var browser: nw_browser_t = null

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
     * V0.4-IOS-LISTENER-REBIND: captured by [onBeforeListenerRebind] so
     * [onAfterListenerRebind] knows whether to recreate the browser. We
     * cannot infer this from `browser != null` after the before-hook
     * because the before-hook is the one that nulls it.
     */
    @Volatile
    private var wasBrowsingBeforeRebind: Boolean = false

    /**
     * V0.4-D-IOS-NUDGE: scope for the post-rebind Bonjour re-announce
     * nudge. SupervisorJob so a failed nudge doesn't poison the scope for
     * subsequent rebinds. Lives for the transport's lifetime.
     */
    private val nudgeScope: CoroutineScope =
        CoroutineScope(SupervisorJob() + Dispatchers.Default)

    /** Most recent pending nudge job; superseded on each new rebind. */
    @Volatile
    private var pendingNudgeJob: Job? = null

    /**
     * Peers seen by the current browse session, re-announced as
     * [PeerEvent.Updated] every [PEER_REANNOUNCE_INTERVAL_MS] while discovery
     * is running. NWBrowser fires result_added exactly once per stable result
     * set, but PeerRegistry evicts peers ~15 s after the last event — the
     * class KDoc always documented this loop, the implementation was missing,
     * so iOS-discovered peers vanished from kit.peers after 15 s of browse
     * quiet (AUDIT-2026-06 fix). StateFlow CAS keeps it thread-safe between
     * the browse callback queue and the announce coroutine without a lock.
     *
     * AUDIT-2026-06 (#8): each entry is stamped with the [browserGeneration]
     * that last CONFIRMED it via a browse result (added / TXT-changed).
     * `refresh()` and the rebind hooks cancel + recreate the NWBrowser
     * without any `result_removed` callbacks for peers that vanished while
     * the browser was being replaced, so an unconditional re-announce would
     * pin such ghosts alive forever (their PeerRegistry lastSeen kept
     * refreshing, defeating staleness eviction). The announce loop therefore
     * only re-emits entries confirmed by the CURRENT generation and prunes —
     * via the shared lost-emission path — entries an older generation owns
     * once they stay unconfirmed for [ANNOUNCE_STALE_GRACE_TICKS] announce
     * cycles (~10 s grace for the replacement browser to re-add live peers).
     * See [reconcileAnnounceCache] for the pure decision logic.
     */
    private val announceCache = MutableStateFlow<Map<String, AnnounceEntry>>(emptyMap())

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
        IosLanDebug.log(
            "browse",
            "startDiscovery: type=${LanConstants.SERVICE_TYPE_BONJOUR} app=${transportContext.appId.value} localPid=${transportContext.localPeerId.value.take(8)}"
        )
        discoveryStartedByHost = true
        createBrowserLocked()
        startAnnounceLoopLocked()
    }

    /** Caller must hold [lock]. Idempotent. */
    private fun startAnnounceLoopLocked() {
        if (announceJob?.isActive == true) return
        announceJob = nudgeScope.launch {
            while (isActive) {
                delay(PEER_REANNOUNCE_INTERVAL_MS)
                if (!discoveryStartedByHost) continue
                // AUDIT-2026-06 (#8): reconcile inside update {} so the CAS
                // retries against concurrent browse-callback stamps instead
                // of clobbering them; `applied` captures the result of the
                // lambda execution that actually committed.
                var applied: AnnounceReconcileResult? = null
                announceCache.update { current ->
                    reconcileAnnounceCache(
                        cache = current,
                        currentGeneration = browserGeneration,
                        graceTicks = ANNOUNCE_STALE_GRACE_TICKS
                    ).also { applied = it }.updatedCache
                }
                val result = applied ?: continue
                result.announce.forEach { peer ->
                    _events.tryEmit(PeerEvent.Updated(peer))
                }
                result.lostPeerIds.forEach { pid ->
                    IosLanDebug.log(
                        "browse",
                        "announce loop: pruning ghost pid=${pid.take(8)} — not " +
                            "re-confirmed by browser generation $browserGeneration"
                    )
                    emitLostById(pid)
                }
            }
        }
    }

    override suspend fun stopDiscovery() = lock.withLock {
        // Clear host intent BEFORE the browser null-check: when iOS reaps the
        // browser during suspension the field is already null, and the old
        // early-return left discoveryStartedByHost=true — the next rebind
        // silently resurrected browsing the host had stopped
        // (AUDIT-2026-06 fix).
        discoveryStartedByHost = false
        announceJob?.cancel()
        announceJob = null
        announceCache.value = emptyMap()
        val b = browser ?: return@withLock
        IosLanDebug.log("browse", "stopDiscovery: cancelling browser")
        browser = null
        browserReady = false
        nw_browser_cancel(b)
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
        browser?.let { nw_browser_cancel(it) }
        browser = null
        browserReady = false
        createBrowserLocked()
        IosLanDebug.log("browse", "refresh: fresh browser started")
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
     * Pre-rebind: cancel the existing browser (if any) and capture the
     * was-browsing flag for the after-hook. The data transport will
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
        wasBrowsingBeforeRebind = discoveryStartedByHost
        browser?.let { b ->
            IosLanDebug.log("browse", "rebind: cancelling old browser")
            nw_browser_cancel(b)
        }
        browser = null
        browserReady = false
        IosLanDebug.log(
            "browse",
            "rebind: pre-rebind state captured " +
                "(advertising=$advertising wasBrowsing=$wasBrowsingBeforeRebind " +
                "cachedPeer=${cachedLocalPeer?.peerId?.value?.take(8)})"
        )
    }

    /**
     * Post-rebind: re-attach the advertise descriptor on the new listener
     * (preserving Bonjour identity via [cachedLocalPeer] reuse), and
     * recreate the browser if we had one before the rebind.
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
        if (wasBrowsingBeforeRebind) {
            createBrowserLocked()
            wasBrowsingBeforeRebind = false
            IosLanDebug.log("browse", "rebind: browser recreated on new listener queue")
        } else {
            IosLanDebug.log("browse", "rebind: was not browsing; nothing to recreate")
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

    /**
     * Browser-creation body, extracted so [startDiscovery] and
     * [onAfterListenerRebind] share the same lifecycle code. Caller MUST
     * hold [lock] and MUST have checked that [browser] is null.
     */
    private fun createBrowserLocked() {
        // AUDIT-2026-06 (#8): every new browser instance opens a fresh
        // generation. Entries in [announceCache] confirmed by an older
        // generation are ghost candidates until this browser re-adds them.
        browserGeneration++
        val descriptor = nw_browse_descriptor_create_bonjour_service(
            type = LanConstants.SERVICE_TYPE_BONJOUR,
            domain = null
        )
        nw_browse_descriptor_set_include_txt_record(descriptor, true)

        val browserParams = nw_parameters_create()
        nw_parameters_set_include_peer_to_peer(browserParams, true)
        // Issue #3 (AWDL asymmetry): the BROWSER opts into peer-to-peer (AWDL),
        // so it can DISCOVER peers reachable only over awdl0. The data
        // transport's listener/connection params do NOT set this, so a peer
        // found here over AWDL may be UNDIALABLE — watch the conn-path lines in
        // IosRawConnection on the subsequent dial.
        IosLanDebug.log(
            "browse",
            "browser params: include_peer_to_peer=true (AWDL discovery ENABLED)"
        )

        val b = nw_browser_create(descriptor, browserParams)
            ?: error("nw_browser_create returned null")
        browser = b

        nw_browser_set_queue(b, dataTransport.queue)
        nw_browser_set_state_changed_handler(b) { state, _ ->
            val label = when (state) {
                nw_browser_state_ready -> "ready"
                nw_browser_state_waiting -> "waiting"
                nw_browser_state_failed -> "failed"
                nw_browser_state_cancelled -> "cancelled"
                else -> "raw=$state"
            }
            IosLanDebug.log("browse", "state -> $label")
            when (state) {
                nw_browser_state_ready -> if (browser === b) browserReady = true
                nw_browser_state_failed, nw_browser_state_cancelled -> {
                    // Identity check: this handler belongs to `b`. refresh()
                    // cancels the old browser and installs a replacement; the
                    // old instance's async cancelled callback must not clobber
                    // the field, or the replacement is orphaned (still browsing,
                    // unreachable, re-created again on the next refresh — an
                    // accumulating leak during the ~3s Reconnecting refresh
                    // cadence). Only clear state for the CURRENT browser
                    // (AUDIT-2026-06 fix).
                    if (browser === b) {
                        browserReady = false
                        browser = null
                    }
                }
            }
            Unit
        }
        nw_browser_set_browse_results_changed_handler(b) { old, new, batchComplete ->
            // AUDIT-2026-06 (#15): same identity guard as the state handler
            // above — refresh()/rebind cancel this browser and install a
            // replacement, and a stale instance's queued result callbacks
            // (e.g. a result_removed for a peer the CURRENT browser still
            // sees) must not mutate the announce cache / endpoint registry
            // or emit Lost once a newer browser owns the field.
            if (browser === b) {
                handleBrowseResultChange(old, new, batchComplete)
            }
            Unit
        }
        nw_browser_start(b)
        IosLanDebug.log("browse", "nw_browser_start invoked")
    }

    private fun buildAdvertiseDescriptor(localPeer: LocalPeerInfo): nw_advertise_descriptor_t {
        val descriptor = nw_advertise_descriptor_create_bonjour_service(
            name = localPeer.peerId.value,
            type = LanConstants.SERVICE_TYPE_BONJOUR,
            domain = null
        ) ?: error("nw_advertise_descriptor_create_bonjour_service returned null")
        nw_advertise_descriptor_set_no_auto_rename(descriptor, true)

        val txt = IosBonjour.mapToTxtRecord(
            mapOf(
                LanConstants.TXT_PEER_ID to localPeer.peerId.value,
                LanConstants.TXT_APP_ID to localPeer.appId.value,
                LanConstants.TXT_DEVICE_NAME to localPeer.deviceName,
                LanConstants.TXT_PLATFORM to localPeer.platform.name,
                LanConstants.TXT_CAPABILITIES to localPeer.supportedTransports.joinToString(",") { it.name },
                LanConstants.TXT_PROTOCOL_VERSION to LanConstants.PROTOCOL_VERSION.toString()
            )
        )
        nw_advertise_descriptor_set_txt_record_object(descriptor, txt)
        return descriptor
    }

    private fun handleBrowseResultChange(
        old: nw_browse_result_t,
        new: nw_browse_result_t,
        batchComplete: Boolean
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
            emitPeer(new, isUpdate = false)
        } else if (removed && old != null) {
            emitLost(old)
        } else if (txtChanged && new != null) {
            emitPeer(new, isUpdate = true)
        }
    }

    private fun emitPeer(result: nw_browse_result_t, isUpdate: Boolean) {
        val endpoint = nw_browse_result_copy_endpoint(result)
        if (endpoint == null) {
            IosLanDebug.log("browse", "emitPeer: copy_endpoint returned null — skip")
            return
        }
        val txt = nw_browse_result_copy_txt_record_object(result)
        val attrs = IosBonjour.txtRecordToMap(txt)
        IosLanDebug.log("browse", "emitPeer: txt=$attrs (isUpdate=$isUpdate)")

        val pid = attrs[LanConstants.TXT_PEER_ID]
        val app = attrs[LanConstants.TXT_APP_ID]
        if (pid == null) {
            IosLanDebug.log("browse", "emitPeer: filter — missing TXT_PEER_ID")
            return
        }
        if (app == null) {
            IosLanDebug.log("browse", "emitPeer: filter — missing TXT_APP_ID")
            return
        }
        if (pid == transportContext.localPeerId.value) {
            IosLanDebug.log("browse", "emitPeer: filter — self (pid matches local)")
            return
        }
        if (app != transportContext.appId.value) {
            IosLanDebug.log(
                "browse",
                "emitPeer: filter — appId mismatch (peer=$app local=${transportContext.appId.value})"
            )
            return
        }

        val name = attrs[LanConstants.TXT_DEVICE_NAME] ?: pid
        val platform = attrs[LanConstants.TXT_PLATFORM]
            ?.let { runCatching { Platform.valueOf(it) }.getOrNull() }
            ?: Platform.UNKNOWN
        val capabilities = attrs[LanConstants.TXT_CAPABILITIES]
            ?.split(",")
            ?.mapNotNull { tag -> runCatching { TransportKind.valueOf(tag.trim()) }.getOrNull() }
            ?.toSet()
            ?: setOf(TransportKind.LAN)

        val peerId = PeerId(pid)
        endpointRegistry.put(peerId, endpoint)

        val internalPeer = InternalPeer(
            publicPeer = Peer(
                id = peerId,
                name = name,
                platform = platform,
                supportedTransports = capabilities
            ),
            transportHints = listOf(TransportHint(type = TransportKind.LAN))
        )
        // AUDIT-2026-06 (#8): stamp the entry with the generation that
        // confirmed it. A live peer re-added by a replacement browser gets
        // re-stamped here and keeps being announced; a ghost keeps its old
        // generation and is pruned by the announce loop.
        announceCache.update { it + (pid to AnnounceEntry(internalPeer, browserGeneration)) }
        val event = if (isUpdate) PeerEvent.Updated(internalPeer) else PeerEvent.Found(internalPeer)
        _events.tryEmit(event)
        IosLanDebug.log("browse", "emitPeer: ACCEPTED ${if (isUpdate) "Updated" else "Found"} $name pid=${pid.take(8)}")
    }

    private fun emitLost(result: nw_browse_result_t) {
        val txt = nw_browse_result_copy_txt_record_object(result)
        val pid = IosBonjour.txtRecordToMap(txt)[LanConstants.TXT_PEER_ID]
        if (pid == null) {
            IosLanDebug.log("browse", "emitLost: TXT had no peer id — skip")
            return
        }
        emitLostById(pid)
    }

    /**
     * Shared lost-emission path: browse `result_removed` callbacks land here
     * via [emitLost], and the announce loop's generation prune
     * (AUDIT-2026-06 #8) calls it directly with the cached peer id. The
     * cache removal is idempotent — the prune path has already dropped the
     * entry via [reconcileAnnounceCache]'s updated map.
     */
    private fun emitLostById(pid: String) {
        if (pid == transportContext.localPeerId.value) return
        val peerId = PeerId(pid)
        announceCache.update { it - pid }
        endpointRegistry.remove(peerId)
        _events.tryEmit(PeerEvent.Lost(peerId))
        IosLanDebug.log("browse", "emitLost: $pid")
    }

    private companion object {
        /**
         * Cadence for re-emitting [PeerEvent.Updated] for cached browse
         * results — must stay comfortably below PeerRegistry's 15 s
         * staleness eviction.
         */
        const val PEER_REANNOUNCE_INTERVAL_MS: Long = 5_000

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
         * 2 ticks × [PEER_REANNOUNCE_INTERVAL_MS] ≈ 10 s of grace for a
         * replacement browser to re-add a live peer — comfortably longer
         * than NWBrowser's typical sub-second result delivery, comfortably
         * shorter than letting a ghost pin PeerRegistry forever.
         */
        const val ANNOUNCE_STALE_GRACE_TICKS: Int = 2
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
    /** Peers confirmed by the current generation — re-announce as Updated. */
    val announce: List<InternalPeer>,
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
 *   - `lastConfirmedGeneration == currentGeneration` → announce it; reset
 *     its stale counter.
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
    val announce = mutableListOf<InternalPeer>()
    val retained = mutableMapOf<String, AnnounceEntry>()
    val lost = mutableListOf<String>()
    for ((pid, entry) in cache) {
        if (entry.lastConfirmedGeneration == currentGeneration) {
            announce += entry.peer
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
    return AnnounceReconcileResult(announce, retained, lost)
}
