# A5-DISCOVERY — Discovery transports & LAN plumbing (S5) review

Reviewed at HEAD `870bf10`, branch `audit/exhaustive-review-2026-06`. All 18 assigned files opened in full; JmDNS 3.6.3 sources (the exact dependency, from the Gradle cache) were consulted to verify library-behavior claims; call sites in `:p2p-core` (`PeerRegistry`, `SessionManager`, `P2pKitImpl`) and `IosLanDataTransport` were cross-checked.

## 1. Per-file verdicts

| File | Lines | Verdict | Tests covering it | Test gaps (1 line) |
|---|---|---|---|---|
| jvmMain/JvmLanDiscoveryTransport.kt | 361 | findings: DSC-1, DSC-3, DSC-7, DSC-11, DSC-12, DSC-13; improvements: DSC-I1, DSC-I4, DSC-I5, DSC-I10 | JvmLanLoopbackTest (indirect), HostSelectorTest (selector only) | No steady-state (>15 s) peer-persistence test; refresh() rotation/CE paths untested |
| androidMain/AndroidLanDiscoveryTransport.kt | 1031 | findings: DSC-1, DSC-2, DSC-3, DSC-4, DSC-5, DSC-7, DSC-10, DSC-11, DSC-12, DSC-13; improvements: DSC-I3, DSC-I4, DSC-I5 | none (documented: zero Android automated tests) | Entire rebind/intent/retry machinery verified only by review + manual flap test |
| appleMain/IosLanDiscoveryTransport.kt | 782 | findings: DSC-6, DSC-8, DSC-9; improvements: DSC-I2, DSC-I6 | AnnounceCacheReconcileTest (pure helper), IosLanLifecycleTest, IosLanLoopbackTest (indirect) | Generation stamping under refresh churn and hook-vs-stopDiscovery races untested |
| appleMain/IosBonjour.kt | 97 | findings: DSC-12 (shared); improvements: — | IosBonjourTest | No oversize-value (>255 B) or duplicate-key malformed-input decode test |
| appleMain/IosEndpointRegistry.kt | 42 | improvements: DSC-I6 | indirect via lifecycle/loopback | No direct unit test (put/get/remove/clear trivial but unpinned) |
| commonMain/Lan.kt | 70 | improvements: DSC-I10 | indirect everywhere | `tcpPort == 0` precondition documented but never asserted |
| jvmMain/JvmLanDsl.kt | 47 | clean | JvmLanLoopbackTest (constructs via it) | — |
| androidMain/AndroidLanDsl.kt | 60 | clean | none | Factory wiring untested (low risk, mirrors JVM) |
| appleMain/IosLanDsl.kt | 37 | clean | iOS loopback/lifecycle construct via it | — |
| jvmMain/JvmLanDiag.kt | 100 | improvements: DSC-I1 | none | "zero allocation when disabled" KDoc claim is false at call sites (unpinned) |
| androidMain/AndroidLanDiag.kt | 80 | findings: DSC-2 (context); improvements: DSC-I1 | none | — |
| appleMain/IosLanDebug.kt | 75 | improvements: DSC-I1 | IosLanDiagnosticTest (@Ignore, diagnostic only) | Unconditional emit/retention behavior unpinned |
| appleMain/IosSwiftHelpers.kt | 50 | improvements: DSC-I8 | none (consumed by iosApp/ContentView.swift:745) | Snapshot helpers untested (trivial) |
| jvmTest/HostSelectorTest.kt | 132 | clean (good contract coverage) | n/a (is a test) | No IPv4-mapped-IPv6 case; pins only the JVM copy of a duplicated function |
| appleTest/AnnounceCacheReconcileTest.kt | 155 | clean (7 cases cover the decision table) | n/a | Does not (cannot, as a pure-fn test) cover the CAS/prune race in the caller — see DSC-8 |
| appleTest/IosBonjourTest.kt | 132 | clean | n/a | Missing >255 B value and duplicate-key cases (DSC-12) |
| appleTest/IosLanLifecycleTest.kt | 415 | improvements: DSC-I9 | n/a | 2 tests are the CATALOGUED simulator flakes; `repeatedKitLifecycle` asserts only "no exception" |
| appleTest/IosLanDiagnosticTest.kt | 65 | clean (@Ignore'd diagnostic, honestly documented) | n/a | — |

## 2. Findings

### DSC-1 — JVM and Android discovered peers are evicted from `kit.peers` 15 s after resolution and never come back in steady state (no heartbeat mechanism; only iOS got one)
- Severity: High (borders Critical for discovery UX) | Confidence: Confirmed by source-level analysis of both our code and the exact JmDNS 3.6.3 dependency; runtime confirmation would be: run two desktop CLIs idle for 20 s and watch the `[peers] 0:` line, or a JVM loopback test asserting peer presence at t > 15 s (expected to fail today).
- File(s): `p2p-transport-lan/src/jvmMain/kotlin/dev/p2pkit/transport/lan/JvmLanDiscoveryTransport.kt:123-188` (emits only `Found`/`Lost`, never periodic `Updated`); `p2p-transport-lan/src/androidMain/kotlin/dev/p2pkit/transport/lan/AndroidLanDiscoveryTransport.kt:514-584` (same); `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerRegistry.kt:95-106,168-171` (eviction: `now - lastSeenAtMillis <= 15_000` keeps, else evicts, polled every 1 s).
- Category: bug
- Root cause: `PeerRegistry` evicts any non-manual peer not re-seen within 15 s. The iOS transport was given a 5 s `PeerEvent.Updated` re-announce loop for exactly this reason (AUDIT-2026-06: "NWBrowser only fires result_added once per peer… peers would silently disappear from kit.peers after 15 s"). The same premise holds for JmDNS, but JVM/Android got no equivalent: JmDNS fires `serviceResolved` to a given listener **once per distinct resolved content** and nothing on renewals, so after the initial `Found` the registry entry's `lastSeen` is never refreshed.
- Evidence: JmDNS 3.6.3 `JmDNSImpl.handleRecord` — a renewal announcement with unchanged data takes the `else` branch and produces **no listener event**:
  ```java
  } else {
      cachedRecord.resetTTL(newRecord);
      newRecord = cachedRecord;      // cacheOperation stays Operation.Noop
  }
  ...
  if (cacheOperation != Operation.Noop) { this.updateRecord(now, newRecord, cacheOperation); }
  ```
  and `ListenerStatus.ServiceListenerStatus.serviceResolved` dedupes even re-deliveries: `if (!_sameInfo(info, previousServiceInfo)) { … listener.serviceResolved(event) } else { logger.debug("Service Resolved called for a service already resolved…") }`. Registered-service TTL is `DNSConstants.DNS_TTL = 60 * 60` (1 h), renewal at 50 % (`ANNOUNCED_RENEWAL_TTL_INTERVAL = DNS_TTL * 500` ms = 30 min) — and even those renewals are content-identical, i.e. silent. Our JVM/Android listeners therefore emit `PeerEvent.Found` exactly once per peer (grep confirms no `PeerEvent.Updated` emission exists in jvmMain/androidMain). `PeerRegistry.evictStalePeers` (PeerRegistry.kt:95-106) then drops the peer at ~15 s.
- Runtime impact: On JVM and Android, every discovered peer vanishes from the public `kit.peers` flow 15 s after its last resolution and does **not** reappear until (a) a `refresh()` listener rotation — which only runs while some session is in `Reconnecting` (SessionManager `launchPeriodicRefresh`, ~3 s cadence) and re-fires `serviceAdded` from the JmDNS cache-report path in `addServiceListener`, or (b) the remote's records actually change, or (c) discovery is stopped/restarted. `P2pKitImpl.connect` (P2pKitImpl.kt:404-412) for an evicted peer falls back to an `InternalPeer` with a host-less/port-less `TransportHint` → `NoTransportAvailable`/`ConnectionFailed` on JVM/Android (on iOS `IosEndpointRegistry` still holds the endpoint, masking the problem there — a parity asymmetry in itself). Established sessions are unaffected. | Platforms: JVM, Android | User-visible: yes (peer pickers empty out; connect-after-browse fails).
- Failure class: none of the listed catastrophics — functional regression of the primary discovery API (peer loss without network cause).
- Why I believe this is NOT already catalogued: both audit documents describe the 15 s eviction only as (i) the iOS bug that was fixed with the announce loop (AUDIT_REPORT_2026-06.md:50) and (ii) the intended *fallback* for JmDNS `serviceRemoved` events that carry no TXT (PROBLEMS_P2PKIT.md:858 — "PeerRegistry then falls back to staleness eviction"), which implicitly assumes JVM/Android entries otherwise stay fresh. No finding covers the missing JVM/Android heartbeat. Existing tests can't see it: `JvmLanLoopbackTest` discovers and connects within seconds; manual recipes check the peer list once, right after discovery.
- Proposed fix (do NOT implement): mirror the iOS mechanism on JVM/Android — keep a `Map<PeerId, InternalPeer>` of live resolutions (populated in `serviceResolved`, pruned in `serviceRemoved`) and re-emit `PeerEvent.Updated` every ~5 s while discovery is running; JmDNS's own cache reaper will fire `serviceRemoved` on genuine TTL expiry, bounding ghosts. Alternative (weaker): make the registry's stale timeout transport-configurable and set it above the mDNS renewal horizon for LAN — but that breaks Lost-fallback latency, so the announce loop is the right shape.
- Required tests: JVM loopback steady-state test — two kits, discover, then assert the peer is still present at t = 20 s and t = 35 s without any connect/reconnect activity; equivalent common-code test with `FakeDiscoveryTransport` documenting that a transport MUST re-emit within the stale timeout (contract test for future transports).

### DSC-2 — Android discovery transport logs unconditionally (44 `Log.*` sites), violating the documented default-off trace contract; JVM and iOS are gated
- Severity: Medium | Confidence: Confirmed
- File(s): `AndroidLanDiscoveryTransport.kt` throughout — e.g. 231-235, 272-276, 336-339, 385-393, 424-425, 682-699, 857-862, 884, 926-929 (44 call sites, TAG `P2pKitJmDNS`); contrast `JvmLanDiag.kt:58-63` (`if (!enabled) return`) and `IosLanDebug.kt:62,73-74` (console mirror opt-in).
- Category: bug (documented-contract violation / parity divergence), with an improvement component (DSC-I1)
- Root cause: the CLAUDE.md/docs contract says the transport byte/lifecycle trace is "default-off in the SDK but enabled in all samples". On Android the discovery lifecycle trace is raw `android.util.Log.d/w` with no gate at all — `AndroidLanDiag` only gates the per-frame trace (`traceFrames`, AndroidLanDiag.kt:34-40); there is no `enabled` master switch on Android.
- Evidence: `Log.d(TAG, "serviceResolved: pid=${pid.take(8)} candidates=[${candidates.joinToString(",") { it.hostAddress }}] selected=$host:$port — emitting PeerEvent.Found")` (AndroidLanDiscoveryTransport.kt:576-581) — runs for every resolution in every release app embedding the SDK. `Log.d(TAG, "ensureJmdns: NICs:${AndroidLanDiag.describeInterfaces()}")` (line 425) enumerates every NIC (syscalls + string building) on each bind/rebind regardless of any trace setting.
- Runtime impact: logcat spam in production apps (device IPs, truncated peer ids, network names — modest PII), string allocation per discovery event, NIC enumeration per rebind; diverges from JVM (`enabled` gate honored at JvmLanDiscoveryTransport call sites via `JvmLanDiag.log`) and iOS (no console output unless `mirrorToConsole`). | Platforms: Android | User-visible: to developers/inspection tools, yes.
- Failure class: none (diagnostics/contract).
- Proposed fix: add `AndroidLanDiag.enabled` (default false, mirroring `JvmLanDiag`), route the transport's lifecycle logs through a gated `AndroidLanDiag.log(tag, message)`; keep the Issue-#2 forensic lines available behind the flag; samples opt in. (A `Log.isLoggable(TAG, DEBUG)` gate is a weaker but zero-API alternative.)
- Required tests: none practical without Robolectric; a lint-style grep check ("no raw `Log.` in androidMain transport sources") would prevent regression.

### DSC-3 — Cancellation during `JmDNS.create` leaks a live JmDNS instance (open multicast socket + threads) that nothing can ever close
- Severity: Medium | Confidence: Confirmed (mechanism); the triggering races are plausible-but-unproven in the wild
- File(s): `AndroidLanDiscoveryTransport.kt:886-923` (rebindNow), `AndroidLanDiscoveryTransport.kt:426-428` (ensureJmdns), `JvmLanDiscoveryTransport.kt:290-293` (ensureJmdns)
- Category: bug
- Root cause: `withContext(Dispatchers.IO) { JmDNS.create(...) }` — if the calling coroutine is cancelled while the create runs, `withContext` completes the block on the IO thread, then **discards the result and throws `CancellationException`**. `JmDNS.create` returns an already-running instance (the `JmDNSImpl` constructor opens the multicast socket and starts the `SocketListener` thread and timers), so the discarded instance stays alive forever: its own threads keep it strongly reachable, it is never assigned to the `jmdns` field, and `stop()`/`closeJmdnsIfIdle()` cannot reach it. The rebindNow catch chain explicitly rethrows CE (line 890-891) without any compensation, unlike the listener-rotation CE handler in `refresh()` which does best-effort detach.
- Evidence:
  ```kotlin
  val fresh = try {
      withContext(Dispatchers.IO) {
          if (newBindAddr != null) JmDNS.create(newBindAddr) else JmDNS.create()
      }
  } catch (e: CancellationException) {
      throw e            // instance created on the IO thread is dropped un-closed
  ```
- Runtime impact: one leaked multicast socket + listener thread (+ JmDNS timers) per occurrence. Triggers: (a) Android — `scheduleRebind` cancels the pending job (`pendingRebindJob?.cancel()`, line 792) while the previous `rebindNow` is inside `JmDNS.create`; network-flap storms >800 ms apart are exactly the environment the #5 fix targets; (b) Android/JVM — the host cancels `startAdvertising`/`startDiscovery` mid-`ensureJmdns` (e.g. `lifecycleScope.launch { kit.startDiscovery() }` + screen rotation, or kit `stop()`'s bounded-mutex path racing a hung start). Leaked instances also keep responding to mDNS queries with stale data if registration got far enough (not the case for bare create, which only listens). | Platforms: JVM, Android | User-visible: no (resource creep; possible battery cost on Android).
- Failure class: leak.
- Proposed fix: make the create non-abandonable — e.g. run it in a `runCatching` that stores the instance into a local before any cancellation check, and in a `finally`/CE handler close it when the coroutine was cancelled (`withContext(NonCancellable + Dispatchers.IO) { runCatching { created.close() } }`), mirroring the fresh-listener detach pattern already used in `refresh()`.
- Required tests: JVM-side unit: cancel a coroutine parked in a fake slow factory and assert `close()` was invoked on the produced handle (requires seaming `JmDNS.create` behind an injectable factory — also what Android unit-testing needs, see §3).

### DSC-4 — Android rebind: failure to re-register/re-listen on the *fresh* handle is dropped with no retry; discovery/advertising stays dead until the next network change
- Severity: Medium | Confidence: Confirmed
- File(s): `AndroidLanDiscoveryTransport.kt:931-955` (post-create restore), `:332-338` (refresh early-return), `:900-921` (retry wired only to `JmDNS.create` failure)
- Category: bug
- Root cause: the AUDIT-#5 fix added a bounded self-retry for `JmDNS.create` failures, but the two follow-up steps on the fresh handle — `registerService` and `addServiceListener` — are each wrapped in `runCatching { … }.onFailure { Log.w(...) }` with no retry, no intent-flag change, and no self-scheduled repair. After such a failure: `jmdns != null` and `boundNetwork/boundDefaultNetwork` are updated (lines 957-958), so a later `rebindNow` skips via `noChangeSinceLastBind`; `refresh()` early-returns because `serviceListener == null` (line 335); nothing else calls back in.
- Evidence:
  ```kotlin
  if (hadDiscovery) {
      val l = buildServiceListener()
      runCatching {
          withContext(Dispatchers.IO) { fresh.addServiceListener(LanConstants.SERVICE_TYPE_JMDNS, l) }
          serviceListener = l
      }.onFailure { e -> Log.w(TAG, "rebindNow: addServiceListener failed", e) }
  }
  boundNetwork = target
  boundDefaultNetwork = defaultTarget
  ```
- Runtime impact: same failure class as the original #5 brick, narrower trigger: a transient `IOException` from JmDNS while re-registering right after a flap (send failure on a just-up interface is plausible) leaves that side (advertise and/or discovery) silently dead until the *next* network rotation or a host-driven `startDiscovery`/`startAdvertising` call (which does repair, since the guards check the handle fields). | Platforms: Android | User-visible: yes (peer invisible / cannot browse after a flap, no error surfaced).
- Failure class: none (silent functional loss; self-heals only on external events).
- Proposed fix: on restore failure, reuse the existing bounded-retry mechanism (schedule `rebindRetryJob` exactly as for create failure), or at minimum leave `boundNetwork/boundDefaultNetwork` un-updated so the next callback/rebind retries the whole cycle.
- Required tests: unit test with a seamed JmDNS factory whose `registerService` throws once — assert a retry restores advertising (same seam as DSC-3's test).

### DSC-5 — Android `start*` writes `boundNetwork`/`boundDefaultNetwork` without (re)binding, letting a pending rebind be wrongly skipped as "no change"
- Severity: Medium | Confidence: Confirmed (logic path); window is narrow in practice
- File(s): `AndroidLanDiscoveryTransport.kt:229-230` (startAdvertising), `:270-271` (startDiscovery), `:835-844` (noChangeSinceLastBind)
- Category: bug
- Root cause: the `bound*` markers are documented as "network present at the time of the most recent **successful JmDNS (re)bind**" (KDoc, lines 203-209), but `startAdvertising`/`startDiscovery` set them to `connectivity.activeNetwork` even when `ensureJmdns()` no-ops because a handle already exists (created earlier, bound to an older network).
- Evidence: sequence — `startDiscovery()` binds JmDNS on network A; the device rotates to network B (debounced rebind pending, 800 ms); `startAdvertising()` runs first: `ensureJmdns()` returns immediately (handle exists, still bound to A), then `boundNetwork = connectivity.activeNetwork` records **B**. The debounced `rebindNow` then evaluates `jmdns != null && target == boundNetwork && defaultTarget == boundDefaultNetwork` → true → skips. JmDNS's multicast socket stays bound to A's address until the *next* rotation.
- Runtime impact: transport silently advertising/browsing on a dead interface for an unbounded period after a specific interleaving (network flip between the two host `start*` calls, or between a host `start*` and the debounce firing). | Platforms: Android | User-visible: yes when hit (no discovery either direction).
- Failure class: none (silent functional loss).
- Proposed fix: set `bound*` only where a bind actually happens — inside `ensureJmdns` when it creates a handle, and in `rebindNow` after success (already done there); `start*` should not touch them.
- Required tests: unit test (seamed JmDNS + fake ConnectivityManager): create on A, flip active network to B, call startAdvertising, then run rebindNow — assert the handle was recreated.

### DSC-6 — iOS: `onAfterListenerRebind` recreates the browser from the stale `wasBrowsingBeforeRebind` flag without re-checking `discoveryStartedByHost` — a concurrent `stopDiscovery` is overridden
- Severity: Medium | Confidence: Confirmed (logic); needs the rebind window to overlap a host stop
- File(s): `IosLanDiscoveryTransport.kt:353-367` (before-hook captures flag), `:395-398` (after-hook uses it), `:283-298` (stopDiscovery clears intent)
- Category: bug
- Root cause: the data transport's `rebindNow` fires `beforeListenerRebind` (captures `wasBrowsingBeforeRebind = discoveryStartedByHost`, releases the discovery `lock`), rebuilds the listener (suspending, seconds), then fires `onAfterListenerRebind`. If the host calls `stopDiscovery()` in that gap (it acquires the discovery lock freely), intent is cleared and the browser/announce loop stopped — but the after-hook then runs `if (wasBrowsingBeforeRebind) { createBrowserLocked() }` from the stale capture and resurrects a live NWBrowser. The advertising side of the same hook is correct: it re-checks the *current* `advertising` flag under the lock. Note this is the exact bug class the AUDIT-2026-06 `stopDiscovery` fix addressed ("browsing no longer resurrects") — the fix covered the reap path but not the hook path.
- Evidence:
  ```kotlin
  if (wasBrowsingBeforeRebind) {
      createBrowserLocked()          // no discoveryStartedByHost check
      wasBrowsingBeforeRebind = false
  ```
- Runtime impact: a browser browses (and `emitPeer` emits `Found` — it has no intent check) against host intent until the next rebind or a `startDiscovery`/`stopDiscovery` cycle; `announceJob` is not running, so found peers churn in/out of the registry on the 15 s eviction; battery + ghost peers. Plausible window: iOS path-event rebinds coincide with app-background flows where hosts call `stopDiscovery`. | Platforms: iOS | User-visible: yes (peers appear while "stopped").
- Failure class: none (intent violation / battery).
- Proposed fix: `if (wasBrowsingBeforeRebind && discoveryStartedByHost) createBrowserLocked()` (both read under `lock`); also re-check in `onAfterListenerRebind`'s advertising branch is already correct — mirror it.
- Required tests: appleTest driving the two hooks directly with a `stopDiscovery()` interleaved between them; assert `browser == null` after the after-hook.

### DSC-7 — JVM/Android `refresh()`: cancellation on the remove-old-listener hop leaks the old listener permanently (duplicate event stream), accumulating across reconnect cycles
- Severity: Medium | Confidence: Confirmed (mechanism); per-cycle probability low but non-zero and unbounded cumulatively
- File(s): `JvmLanDiscoveryTransport.kt:240-243`, `AndroidLanDiscoveryTransport.kt:369-372`
- Category: bug (defect in the brand-new #7 fix)
- Root cause: the add-before-remove rotation is CE-safe on the add (fresh listener detached under `NonCancellable`), but the subsequent remove of the old listener is a plain `withContext(Dispatchers.IO) { runCatching { removeServiceListener(old) } }`. `refresh()` runs inside `SessionManager.launchPeriodicRefresh`, whose job is cancelled at every reconnect resolution (rearm/exhaustion — SessionManager.kt, `periodicRefreshJob.cancel()` in the `finally`). If that cancellation lands on the dispatch into this `withContext`, kotlinx-coroutines throws CE **without running the block**: `listener` already points at `fresh`, `old` stays registered in JmDNS forever (no field references it), and every subsequent event fires on both listeners.
- Evidence:
  ```kotlin
  listener = fresh
  withContext(Dispatchers.IO) {                       // ← CE here skips the block entirely
      runCatching { handle.removeServiceListener(LanConstants.SERVICE_TYPE_JMDNS, old) }
  }
  ```
- Runtime impact: each leaked listener duplicates `Found`/`Lost` emissions (registry converges, so correctness holds) and holds its closure alive; unbounded accumulation over many reconnect episodes in a long-lived process. | Platforms: JVM, Android | User-visible: no (CPU/memory creep, log noise).
- Failure class: leak.
- Proposed fix: perform the remove under `withContext(NonCancellable + Dispatchers.IO)` — the same pattern the CE handler five lines above already uses for the fresh listener.
- Required tests: with a seamed JmDNS: cancel refresh between add and remove; assert exactly one listener remains registered.

### DSC-8 — iOS announce-loop prune races the browse callback: a peer re-confirmed between the reconcile CAS and `emitLostById` is deleted and emitted Lost
- Severity: Low | Confidence: Confirmed (interleaving exists); microsecond window gated behind a ≥2-tick-stale entry
- File(s): `IosLanDiscoveryTransport.kt:259-278` (reconcile CAS then prune emissions), `:650` (emitPeer re-stamp), `:673-680` (emitLostById unconditionally removes)
- Category: bug
- Root cause: `reconcileAnnounceCache` commits a cache without the pruned pid; `emitLostById(pid)` then runs `announceCache.update { it - pid }` + `endpointRegistry.remove` + `Lost`. If the current browser's belated `result_added` lands in between (emitPeer commits `pid → AnnounceEntry(gen=current)`), `emitLostById` deletes that fresh entry and emits `Lost` for a live, just-confirmed peer. Because NWBrowser will not re-fire `result_added` for a result already in its set, the peer stays lost until the next browser generation (refresh/rebind).
- Evidence: `announceCache.update { it - pid }` in `emitLostById` has no generation guard; the KDoc (lines 666-672) calls the removal "idempotent", which is true only if no re-stamp interleaved.
- Runtime impact: rare wrong `Lost` + dropped endpoint for a live peer, persisting until the next generation. Most likely during reconnect churn (3 s browser recreates + slow simulator/congested delivery ≥10 s). | Platforms: iOS | User-visible: when hit, yes.
- Failure class: none (transient wrong state).
- Proposed fix: make the prune-side removal conditional — e.g. `emitLostById` for prunes should CAS-remove only if the entry is still absent/stale-generation (or have `reconcileAnnounceCache`'s caller emit Lost only for pids still absent from the committed map after a re-read); the browse-callback path keeps the unconditional removal.
- Required tests: unit test interleaving a re-stamp between reconcile and prune (extract the prune-emission into a testable helper).

### DSC-9 — iOS browse callbacks stamp entries with the *current* volatile `browserGeneration`, not the generation of the browser that delivered the result
- Severity: Low | Confidence: Confirmed (TOCTOU exists; self-heals within one generation + grace)
- File(s): `IosLanDiscoveryTransport.kt:537-539` (identity guard, not atomic with the body), `:650` (stamp reads the volatile), `:478` (increment under lock)
- Category: bug
- Root cause: the `if (browser === b)` guard (the #15 fix) is checked on the dispatch queue without the `lock`; `refresh()` can swap `browser` and increment `browserGeneration` while `handleBrowseResultChange`/`emitPeer` from the OLD browser is mid-flight. The stale result is then stamped `AnnounceEntry(peer, browserGeneration)` with the NEW generation (and its possibly-stale endpoint `put` into the registry), defeating the generation reconcile for that entry for one extra generation + grace (~one refresh cycle + 10 s).
- Evidence: `announceCache.update { it + (pid to AnnounceEntry(internalPeer, browserGeneration)) }` — `browserGeneration` is read at stamp time, not captured per browser.
- Runtime impact: a ghost can survive one extra generation window during refresh churn; endpoint registry may briefly hold a stale endpoint. Bounded and self-correcting. Generation wraparound is a non-issue (Int at one increment per browser creation; centuries at the 3 s cadence). | Platforms: iOS | User-visible: marginal (slightly delayed ghost pruning).
- Failure class: none.
- Proposed fix: capture `val gen = browserGeneration` inside `createBrowserLocked()` after the increment and close over `gen` in both handlers (`if (browser === b)` remains as the field guard; the stamp uses `gen`). This makes the stamp exact regardless of interleaving.
- Required tests: covered indirectly by AnnounceCacheReconcileTest once the stamp is exact; a wiring test needs a fake browser seam (P3).

### DSC-10 — Android `pendingRebindJob` is mutated from ConnectivityManager callback threads with no synchronization
- Severity: Low | Confidence: Confirmed (data race per JMM); consequences bounded by rebindNow's guards
- File(s): `AndroidLanDiscoveryTransport.kt:791-798` (scheduleRebind: unsynchronized read/cancel/write), `:766-767` (stopNetworkWatcherIfIdle mutates the same field under `lock`)
- Category: bug
- Root cause: `scheduleRebind` runs on binder threads (primary + default callbacks routinely fire near-simultaneously for one handover) and does `pendingRebindJob?.cancel(); pendingRebindJob = rebindScope.launch {…}` with no lock; two concurrent calls can both cancel the same old job and race the field write, losing one Job reference. The stop path mutates the field under the coroutine `lock`, so the accesses are mixed-discipline.
- Evidence: `private fun scheduleRebind(reason: String) { pendingRebindJob?.cancel() … pendingRebindJob = rebindScope.launch { … } }` — no `synchronized(networkLock)`/lock.
- Runtime impact: worst case a stray debounced job survives cancellation and runs `rebindNow` after the watcher stopped or redundantly — both are no-ops thanks to the watcher-null and `noChangeSinceLastBind` guards (verified). So: benign outcome, but a real unsynchronized shared field on multi-threaded paths (visibility not guaranteed). | Platforms: Android | User-visible: no.
- Failure class: none (latent race).
- Proposed fix: guard `pendingRebindJob` with the existing `networkLock` `synchronized` block (callbacks must stay non-suspending, so the coroutine `lock` is not an option there).
- Required tests: not practically testable; fix is mechanical.

### DSC-11 — `serviceRemoved`/`emitLost` emit `PeerEvent.Lost` with no appId filter, so any same-type advertiser can remove arbitrary pids from the registry
- Severity: Low | Confidence: Confirmed; malformed-input trigger only — largely inside the CATALOGUED unauthenticated-identity trust boundary
- File(s): `JvmLanDiscoveryTransport.kt:129-135`, `AndroidLanDiscoveryTransport.kt:519-525`, `IosLanDiscoveryTransport.kt:656-664`; consumer: `PeerRegistry.processEvent` (PeerRegistry.kt:84 — `Lost -> current - event.peerId`, applies to manual entries too)
- Category: bug (filter inconsistency); the spoofing dimension is [CATALOGUED] under the pre-encryption trust model
- Root cause: `Found` requires `pid` present, `app == local appId`, non-self; `Lost` requires only `pid` present and non-self. A `_p2pkit._tcp` advertisement from a *different* app (or a crafted one) that announces then goodbyes with `pid=<victim>` in TXT removes the victim from every JVM/Android/iOS registry on the LAN. Benign side of the asymmetry is safe — `Lost` for a never-Found pid is a no-op in the registry (verified) — but the removal side also deletes **manual** peers (eviction-exempt entries have no Lost protection) and, per DSC-1, JVM/Android victims do not re-appear.
- Evidence: `val pid = info.getPropertyString(LanConstants.TXT_PEER_ID) ?: return; if (pid == registration.localPeerId.value) return; _events.tryEmit(PeerEvent.Lost(PeerId(pid)))` — no `TXT_APP_ID` read.
- Runtime impact: peer-list eviction via a forged Lost record (affects discovery visibility, not sessions). | Platforms: all three | User-visible: under a forged-record scenario, yes.
- Failure class: resource-limit / discovery-visibility (malformed-input only).
- Proposed fix: read and require `TXT_APP_ID == local` in the removed path too (JmDNS removal events usually carry the cached TXT — where TXT is absent no Lost fires today anyway, PROBLEMS B:858); optionally have `PeerRegistry` ignore `Lost` for `origin == Manual` entries. Full identity protection remains the encryption milestone.
- Required tests: registry unit test: `Lost` for a manual peer id must not remove it (if that protection is adopted); transport-level filter test via seamed JmDNS (P3).

### DSC-12 — TXT edge-case parity divergences: empty value decodes as `"true"` on JmDNS vs `""` on iOS; oversized values silently dropped on both sides; no deviceName length validation anywhere
- Severity: Low | Confidence: Confirmed (JmDNS behavior verified in ByteWrangler/ServiceInfoImpl sources; nw set-key return ignored in our code)
- File(s): `IosBonjour.kt:44-58` (`nw_txt_record_set_key` boolean result ignored) and `:84-90` (empty/no-value → `""`); JmDNS 3.6.3 `ServiceInfoImpl.getPropertyString` (`if (data == ByteWrangler.NO_VALUE) return "true"`) + `ByteWrangler.readProperties` (`parts[1].isEmpty() → NO_VALUE`; malformed length → `properties.clear()` drops ALL keys; duplicate keys: last-wins `properties.put`); `ByteWrangler.isValueTooLarge` skips >255-byte values with only a warning; `Builders.kt:127` (deviceName only null-checked).
- Category: bug (parity divergence, degenerate inputs only)
- Root cause: three uncoordinated codecs. Concretely: a peer advertising `pid=` (empty) yields `PeerId("true")` on JVM/Android vs `PeerId("")` on iOS — same wire bytes, different identity. A deviceName over 255 UTF-8 bytes is silently dropped from TXT on every platform (JmDNS skips the entry; iOS's `nw_txt_record_set_key` failure is unchecked), so the remote falls back to pid-as-name with no warning to the app. A truncated final TXT entry makes JmDNS drop *all* keys (whole peer filtered) while iOS's nw parser keeps the valid prefix.
- Runtime impact: none for well-formed P2pKit peers; divergent behavior only for malformed records (and identity is unauthenticated pre-encryption anyway). | Platforms: all | User-visible: no in practice.
- Failure class: none.
- Proposed fix: treat empty/blank `pid` or `app` as missing (explicit `isNullOrEmpty()` filter at all three `serviceResolved`/`emitPeer` sites — this collapses the `"true"`/`""` divergence for the keys that matter); validate `deviceName` UTF-8 length (≤ ~200 bytes) in the builder with a clear error.
- Required tests: IosBonjourTest: >255-byte value case (assert observable behavior); JVM: serviceResolved with `pid=` filtered (seamed test or extracted parser).

### DSC-13 — Failed `start*` leaves the multicast lock held and the JmDNS handle open with both intent flags false, until `kit.stop()`
- Severity: Low | Confidence: Confirmed
- File(s): `AndroidLanDiscoveryTransport.kt:218-237` (acquire + ensureJmdns before registerService; no failure-path release), `:590-598` (acquire not exception-wrapped); `JvmLanDiscoveryTransport.kt:63-97` (same shape minus the lock)
- Category: bug (defensive gap)
- Root cause: `startAdvertising` acquires the multicast lock and creates JmDNS before `registerService`; if `registerService` throws (or `acquire()` itself throws `SecurityException` when `CHANGE_WIFI_MULTICAST_STATE` is missing — un-wrapped at line 594-596), the method throws with the lock held and the handle open, and `advertisingIntent`/`discoveryIntent` were never set, so nothing tracks the allocation. Cross-check: `P2pKitImpl.startAdvertising` wraps the throw into a typed `P2pError` and sets `P2pState.Failed` but performs no transport cleanup; `kit.stop()` → `teardownBoundResources` → `stopAdvertising`/`stopDiscovery` (both intents false → `releaseMulticastLockIfIdle`/`closeJmdnsIfIdle` run) does reclaim, and a host retry of `start*` reuses the handle/lock — so the design is retry-friendly, but an app that abandons the kit without `stop()` after a Failed start keeps a held multicast lock (measurable battery cost) and an open mDNS socket.
- Failure class: leak (bounded, reclaimable).
- Proposed fix: on the `start*` failure path (catch-rethrow), run the same `*IfIdle` trio as `stop*`; wrap `acquire()` in `runCatching` and degrade to lock-less operation with a warning (documented: some devices receive multicast fine without it).
- Required tests: JVM analog: `startAdvertising` with a registration that fails → assert `maybeCloseJmdns` ran (seamed factory).

## 3. Missing tests

| Invariant untested | Why it matters | Where it should live | Type | Priority |
|---|---|---|---|---|
| JVM/Android discovered peer remains in `kit.peers` at t > 15 s idle (DSC-1) | The primary discovery API silently empties in steady state; regression-proof for the fix | `p2p-transport-lan:jvmTest` loopback + commonTest contract test with `FakeDiscoveryTransport` | integration + unit | P1 |
| Android rebind machinery (intent flags vs handles, create-retry bounds, restore-failure repair — DSC-3/4/5) | The #5 fix shipped with "compile + review + manual" only; the module's riskiest state machine has zero automated coverage | seam `JmDNS.create`/handle behind an injectable factory → `androidHostTest` or jvm-style unit | unit | P1 |
| `refresh()` rotation leaves exactly one listener under cancellation at every suspension point (DSC-7) | New #7 code; leak accumulates invisibly | jvmTest with seamed JmDNS | unit | P2 |
| iOS after-rebind hook honors a concurrent `stopDiscovery` (DSC-6) | Browsing must never resurrect against host intent (already fixed once elsewhere) | appleTest driving the two hooks directly | unit | P2 |
| Announce prune cannot Lost a peer re-confirmed concurrently (DSC-8) | Wrong Lost persists a full browser generation | appleTest around an extracted prune-emission helper | unit | P2 |
| `Lost` for a manual peer / foreign-app pid does not evict tracked entries (DSC-11) | Manual peers are eviction-exempt but Lost-vulnerable | `p2p-core` commonTest `PeerRegistry` | unit | P2 |
| TXT malformed-input decode parity: >255 B values, duplicate keys, empty `pid=` (DSC-12) | Three codecs, no shared vectors | IosBonjourTest + a JVM-side ServiceInfo fixture test | unit | P3 |
| `selectRoutableHost` JVM/Android copies stay identical | Duplicated-verbatim pair, sync by convention only | a source-checksum guard test or extraction note | unit | P3 |
| `LanServiceRegistration.tcpPort != 0` at advertise time | Advertising SRV port 0 is undialable; only enforced by call-ordering convention | assertion + jvmTest | unit | P3 |

## 4. Improvements

- **DSC-I1 (diag gating/allocation):** `JvmLanDiag.log`'s KDoc claims "zero allocation when disabled" but every call site builds the message eagerly — including `JvmLanDiscoveryTransport.kt:289` which runs full NIC enumeration (`describeInterfaces()`) as an argument before the gate; `IosLanDebug.log` (IosLanDebug.kt:58-63) always allocates timestamp+line and retains the last ~400 lines in a release process with zero subscribers (and `emitPeer` logs full TXT maps, including foreign-app records, pre-filter — IosLanDiscoveryTransport.kt:600). Suggest lambda-message APIs (`log(tag) { … }`) and an `enabled` gate on iOS mirroring `JvmLanDiag`.
- **DSC-I2 (iOS announce-loop resilience):** the loop body (IosLanDiscoveryTransport.kt:251-280) has no per-tick try/catch; any unexpected throw kills re-announcing silently and the 15 s-evaporation bug returns until the host restarts discovery — `refresh()` never restarts the loop. Add CE-rethrowing isolation like `PeerRegistry.evictLoop`.
- **DSC-I3 (retry-budget episodes):** `rebindRetryAttempts` resets only on success or watcher stop (AndroidLanDiscoveryTransport.kt:900-921,925); after exhaustion, each *new* network episode gets a single un-retried create attempt. Consider resetting the counter in `scheduleRebind` (a genuine new signal starts a new episode).
- **DSC-I4 (constant drift):** JVM uses `JMDNS_LIST_SNAPSHOT_TIMEOUT_MS = 200` (JvmLanDiscoveryTransport.kt:361); Android inlines `200L` (AndroidLanDiscoveryTransport.kt:381) — the keep-in-sync pair deserves one named constant referenced by both comments.
- **DSC-I5 (refresh over-query):** both refresh() bodies force re-query every cached `_p2pkit._tcp` service regardless of appId (JVM 248-254, Android 385-400) — filterable by TXT app to cut multicast noise on shared-type networks.
- **DSC-I6 (endpoint registry hygiene):** `IosEndpointRegistry` is cleared only by `IosLanDataTransport.close()` (IosLanDataTransport.kt:510) and per-peer `Lost`; `stopDiscovery` leaves all entries behind (IosLanDiscoveryTransport.kt:283-298). Bounded but untidy — clear (or prune) on stopDiscovery.
- **DSC-I7 (dead `pv` key):** all three platforms advertise `TXT_PROTOCOL_VERSION` but no receive path reads it — version gating happens only at HELLO. Either read it as an early filter (skip incompatible peers pre-dial) or document it as reserved.
- **DSC-I8 (spec drift):** `peersSnapshot`/`sessionsSnapshot`/`stateName` (IosSwiftHelpers.kt:33-50) are public, exported in the XCFramework, and used by the iOS sample, but absent from `P2pKit-Spec.md` (the locked API surface doc). Document them (transport-module extension surface).
- **DSC-I9 (test-id collision):** `IosLanLifecycleTest.unique` uses second-resolution `timeIntervalSince1970.toLong()` (line 46-47); two test instances created in the same second share an appId and can see the previous test's not-yet-goodbyed advertisements (e.g. `threePeersMutuallyDiscover`'s `assertEquals(2, …)` could count a zombie). Use ms + random suffix.
- **DSC-I10 (Lan.kt precondition):** `LanServiceRegistration` documents "discovery transports should not call this with tcpPort == 0" (Lan.kt:16) but neither JVM nor Android asserts it before `ServiceInfo.create` — a one-line `check()` turns a silent port-0 SRV into a diagnosable failure.

## 5. Wire/TXT parity table (verified)

| Dimension | JVM | Android | iOS | Verdict |
|---|---|---|---|---|
| Service type | `_p2pkit._tcp.local.` (JmDNS form) | same | `_p2pkit._tcp` (canonical, no dot — correct for `nw_*`) | ✅ wire-identical |
| Instance name | `localPeerId.value` | same | same (`localPeer.peerId.value`) | ✅ |
| TXT keys | pid/app/name/plat/caps/pv | identical map | identical map | ✅ |
| Value formats | `Platform.name`, `TransportKind.name` CSV, `pv=1` (`ProtocolConstants.VERSION` = 1 ✓) | same | same | ✅ |
| Name-conflict handling | JmDNS auto-renames (`makeServiceNameUnique`) | same | `no_auto_rename=true` | ⚠️ nuance only — names are unique peer ids; same-host re-registration is not a conflict; no current symptom |
| Empty TXT value decode | `"true"` (JmDNS NO_VALUE) | same | `""` | ⚠️ DSC-12 |
| Oversize value (>255 B) | silently skipped (warn log) | same | silently dropped (`set_key` return ignored) | ⚠️ DSC-12 (consistent silence, no validation) |
| Duplicate TXT keys | last-wins (ByteWrangler `put`) | same | last-wins in our map (nw parser semantics unverified) | ✅-ish; malformed-input only |
| Endpoint transport | host/port in `TransportHint` via `selectRoutableHost` (copies verified byte-identical, jvm:341-354 ↔ android:1018-1031) | same | opaque `nw_endpoint_t` via `IosEndpointRegistry`, hint carries no host/port | ✅ by design (documented) |
| Steady-state registry heartbeat | **none** | **none** | 5 s Updated loop | ❌ DSC-1 |

## 6. Section summary

**What this section owns:** the three per-platform mDNS discovery implementations behind one `DiscoveryTransport` contract, the TXT codec and endpoint bridge on iOS, the `transports { lan() }` factories, and the three diagnostic sinks.

**Overall health:** the commit-25e501c fixes are genuinely good where they aimed — the JVM/Android refresh rotation is now CE-correct on the add side, the Android intent-flag decoupling closes the brick the audit found (my re-derivation confirms `stopAdvertising`/`stopDiscovery`/`closeJmdnsIfIdle`/`releaseMulticastLockIfIdle`/`stopNetworkWatcherIfIdle` are all consistently intent-based), and the iOS generation reconcile is a clean, well-tested pure function. But the section has one serious blind spot the fixes did not touch (DSC-1: JVM/Android have no registry heartbeat, so steady-state peers evaporate at 15 s — the identical iOS bug was fixed in 2026-06 while the JmDNS premise went unexamined), and the new rebind/refresh code has second-order gaps: restore-failure has no retry (DSC-4), stale bound-markers can suppress a needed rebind (DSC-5), and two cancellation windows leak live JmDNS resources (DSC-3, DSC-7). iOS's rebind hooks can resurrect browsing against a concurrent host stop (DSC-6). Android remains the highest-risk file: 1031 lines of lock/callback/coroutine machinery with zero automated tests.

**Top 3 risks:**
1. DSC-1 — steady-state discovery loss on the two JmDNS platforms (High; release-visible to any app that browses for >15 s before connecting).
2. The untested Android rebind state machine (DSC-3/4/5/10 all live there; a JmDNS factory seam would make all of them unit-testable and is the single highest-leverage test investment).
3. iOS hook/announce-loop concurrency (DSC-6/8/9 — individually narrow, but they share a root shape: browse-queue callbacks and lock-holding coroutines coordinating through volatile fields instead of captured state).

**CODEBASE_REVIEW_MAP_2026-07.md accuracy:** accurate for S5 — file list, ownership, dependency edges (S2/S3/S4 consumers verified at `P2pKitImpl.kt:169-183`, `SessionManager.launchPeriodicRefresh`, `PeerRegistry.start`), the "Android has zero automated tests" note, and the High risk rating all match what I found. One nit: it calls `Lan.kt` "common config" — it contains only wire constants and the mutable registration struct; there is no user-facing config in it (nothing to validate against DSL knobs, which take no LAN-specific options).

**Refresh-cadence cross-check (asked in scope):** `SessionManager` refires `refreshDiscovery()` every 3 s ± 0.4 s only while a session is `Reconnecting`, serialized per transport under each transport's lock. JVM/Android: each tick costs a listener rotation + 200 ms bounded `list()` — safe at that rate (lock held ≲300 ms; catalogued B:317 latency accepted). iOS: each tick cancels + recreates the NWBrowser (generation++); the reconcile grace (2 ticks ≈ 10 s) absorbs recreate latency, with the caveat that a browser slower than 10 s to re-deliver results causes transient Lost/Found churn (accepted trade-off per the #8 design notes; worth watching on real hardware in smoke A4).
