# A9-PERMPROV — S9 Permissions + S10 Network provisioning review

Branch `audit/exhaustive-review-2026-06`, HEAD `870bf10`. Review complete (19/19 files read; call sites cross-checked in P2pKitImpl.kt, Builders.kt, PeerRegistry.kt, IosLanDataTransport.kt, sample ViewModel, commit `881fb31`).

## 1. Per-file verdicts

### S9 — Permissions (p2p-core)
| File | Lines | Verdict | Tests covering it | Test gaps (1 line) |
|---|---|---|---|---|
| p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PermissionManagerFactory.kt | 28 | clean | PermissionGateTest (default path) | none (expect + KDoc only) |
| p2p-core/src/androidMain/kotlin/dev/p2pkit/core/internal/PermissionManagerFactory.android.kt | 93 | findings: PRM-1 (systemic) | improvements: PRM-2 | none automated — manual recipe in PermissionGateTest KDoc | empty-report + manifest-warn need an Android host-test harness (p2p-core has none) |
| p2p-core/src/iosMain/kotlin/dev/p2pkit/core/internal/PermissionManagerFactory.ios.kt | 14 | clean | PermissionGateTest default path (runs on iOS targets) | none |
| p2p-core/src/jvmMain/kotlin/dev/p2pkit/core/internal/PermissionManagerFactory.jvm.kt | 9 | clean | PermissionGateTest default path (JVM) | none |
| p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/PermissionGateTest.kt | 155 | improvements: PRM-3 | n/a (is a test) | no pin that connect() bypasses the gate; Android manager only manually verified |

### S10 — Network provisioning
| File | Lines | Verdict | Tests covering it | Test gaps (1 line) |
|---|---|---|---|---|
| p2p-network-provisioning-android/src/androidMain/AndroidManifest.xml | 14 | clean (see PRM-20 note) | n/a | n/a — declares nothing by documented policy |
| p2p-network-provisioning-android/.../AndroidDsl.kt | 42 | improvements: PRM-20 | none (glue) | none needed |
| p2p-network-provisioning-android/.../AndroidNetworkProvisioningManager.kt | 425 | findings: PRM-5, PRM-7, PRM-8, PRM-9, PRM-10 | AndroidNetworkProvisioningManagerTest (12 tests, host JVM via fake wrapper) | timeout path, parentJob-cancel teardown, API-gate Unsupported, restartability after Failed |
| p2p-network-provisioning-android/.../AndroidP2pPermissionManager.kt | 70 | clean ([CATALOGUED] C:54 assessed sound) | none | targetSdk/API-level branching (audit fix) has zero automated coverage |
| p2p-network-provisioning-android/.../AndroidProvisioningFactory.kt | 28 | improvements: PRM-20 | none (glue) | none needed |
| p2p-network-provisioning-android/.../WifiManagerWrapper.kt | 129 | clean | exercised via fakes in manager test | interface contract asserted only through fakes (acceptable) |
| p2p-network-provisioning-android/.../WifiManagerWrapperImpl.kt | 335 | findings: PRM-4, PRM-11 | **none** (real WifiManager/ConnectivityManager; manual only) | the riskiest file in scope has no automated tests — device-manual recipes only |
| p2p-network-provisioning-android/src/androidHostTest/.../AndroidNetworkProvisioningManagerTest.kt | 478 | improvements: PRM-17 | n/a (is a test) | see §3 rows 1–5; fakes model pre-audit replay=0 flow semantics |
| p2p-network-provisioning-desktop/.../JvmDsl.kt | 31 | clean | ManualIpLoopbackTest (uses `jvm()`) | none |
| p2p-network-provisioning-desktop/.../JvmNetworkProvisioningManager.kt | 164 | findings: PRM-6 | improvements: PRM-15 | JvmNetworkProvisioningManagerTest, ManualIpLoopbackTest | networkState poll loop untested (no enumeration seam) |
| p2p-network-provisioning-desktop/.../JvmProvisioningFactory.kt | 14 | clean | ManualIpLoopbackTest | none |
| p2p-network-provisioning-desktop/src/test/.../JvmNetworkProvisioningManagerTest.kt | 139 | improvements: PRM-19 | n/a (is a test) | silent-pass guard when host has no non-loopback NIC |
| p2p-network-provisioning-desktop/src/test/.../ManualIpLoopbackTest.kt | 116 | improvements: PRM-18 | n/a (is a test) | dead 127.* branch; only one message direction asserted |
| p2p-transport-lan/src/appleMain/.../IosManualNetworkProvisioningManager.kt | 140 | findings: PRM-12, PRM-13 | improvements: PRM-14 | **none** (only the iosApp sample exercises it manually) | createManualPeer→dial path has no appleTest coverage |

## 2. Findings

### Verification of remediation #9 / C:54 (context for PRM-1)
Commit `881fb31` was verified at every gate call site: `ensurePermissions()` is called from exactly two places — `P2pKitImpl.kt:321` (startAdvertising) and `:358` (startDiscovery) — and defined at `:497-500`, gating on `missingPermissions()` only. `connect()` (`P2pKitImpl.kt:384`) is not gated, which matches the `P2pPermissionManager` KDoc (only the two entry points throw). All three platform defaults report empty (`PermissionManagerFactory.android.kt:89-93`, `.jvm.kt:8-9`, `.ios.kt:13-14`), so the default path can never regress into `PermissionMissing`. C:54 re-verified: `ChangeWifiState` now has exactly one Android mapping — `AndroidP2pPermissionManager.kt:67` → `CHANGE_WIFI_STATE`; no code maps it to `CHANGE_WIFI_MULTICAST_STATE` anymore (grep-confirmed; remaining hits are docs). **The deferral of a new enum constant is sound** — no current call path can confuse the two meanings.
Note: my task brief described the intended behavior as "operation-specific required permission sets (discovery requires CHANGE_WIFI_MULTICAST_STATE)". The implemented fix is *not* operation-specific — it reports **no** runtime permissions for core LAN and warns at construction for undeclared install-time perms. The commit message and REMEDIATION_2026-07.md #9 describe exactly what was implemented, and the deviation is deliberate and sound: `CHANGE_WIFI_MULTICAST_STATE` is a normal/install-time permission, so surfacing it through the runtime-request surface (even per-operation) would reintroduce the "app loops on an ungrantable prompt" category error the commit documents. The residual gap that IS worth fixing is PRM-1.

### PRM-1 — Kit-wide permission gate re-creates LAN over-gating for apps that wire the provisioning sidecar's manager (as the docs recommend)
- Severity: Medium | Confidence: Confirmed (behavior); the *mechanism* is deliberate — PermissionGateTest pins it — but the granularity mismatch contradicts the stated goal of fix #9 ("stop hard-gating core LAN", "over-blocked advertise")
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt:321,358,497-500; p2p-core/src/androidMain/kotlin/dev/p2pkit/core/internal/PermissionManagerFactory.android.kt:82-88; p2p-network-provisioning-android/.../AndroidP2pPermissionManager.kt:37-47
- Category: bug (error semantics / design gap)
- Root cause: `ensurePermissions()` has no notion of which operation needs which permission — it throws if *any* permission the kit-wide manager reports is missing. The sidecar's `AndroidP2pPermissionManager` reports `NearbyWifiDevices`/`Location`, which are needed **only** for hotspot/Wi-Fi-join provisioning, never for LAN advertise/discovery. Yet `Builders.kt:77-79` and `PermissionManagerFactory.android.kt:85-87` explicitly tell provisioning apps to wire that manager into `P2pKitBuilder.permissionManager`.
- Evidence: `P2pKitImpl.kt:497-500` — `val missing = permissions.missingPermissions(); if (missing.isNotEmpty()) throw P2pError.PermissionMissing(missing)`; `PermissionManagerFactory.android.kt:85-88` — "wired in via `P2pKitBuilder.permissionManager` — **that path still gates startAdvertising/startDiscovery**". Meanwhile the Android sample deliberately does NOT wire it (p2p-sample-android/.../P2pKitViewModel.kt:431 constructs `AndroidP2pPermissionManager` standalone and checks `missingPermissions()` itself before provisioning ops) — the sample authors avoided the trap the SDK docs steer users into.
- Runtime impact: an app that follows the documented wiring and hasn't yet been granted `NEARBY_WIFI_DEVICES`/`ACCESS_FINE_LOCATION` gets `P2pError.PermissionMissing` from plain `startAdvertising()`/`startDiscovery()` — operations that need no runtime permission at all. This is exactly the over-gating class #9 removed, reintroduced for sidecar users. | Platforms: Android | User-visible: yes
- Failure class: none (wrong error semantics / functional blocking)
- Proposed fix (do NOT implement): documentation-level fix (no API change): change `Builders.kt` / `PermissionManagerFactory.android.kt` guidance to recommend the sample's pattern — keep the default (empty) manager on the kit and query `AndroidP2pPermissionManager` directly before provisioning calls. [API-CHANGE] alternative: give `P2pPermissionManager` per-operation sets (e.g. `missingPermissions(operation: P2pOperation)`) so the gate at each call site asks only for what that operation needs.
- Required tests: a PermissionGateTest case documenting the chosen contract (sidecar-managed kit + missing provisioning perm → advertise/discovery behavior asserted explicitly, whichever way the decision goes).

### PRM-2 — (Improvement) Construction-time manifest warn checks 2 of the 4 install-time permissions its own header lists
- Severity: Improvement | Confidence: Confirmed
- File(s): p2p-core/src/androidMain/kotlin/dev/p2pkit/core/internal/PermissionManagerFactory.android.kt:18-20 vs 54-58
- Category: improvement
- Root cause / evidence: the file header lists `INTERNET`, `ACCESS_NETWORK_STATE`, `ACCESS_WIFI_STATE`, `CHANGE_WIFI_MULTICAST_STATE` as the LAN install-time set, but `warnIfLanManifestPermissionsUndeclared` checks only the last two. Defensible (the first two fail loudly via `SecurityException`; the Wi-Fi pair fails *silently* as zero-discovery), but the asymmetry is undocumented and a missing `ACCESS_NETWORK_STATE` degrades `AndroidNetworkPathObserver` with only a generic "observer failed" warn.
- Proposed fix: either extend the checked list to all four, or add one sentence to the header stating why only the silent-failure pair is checked.
- Required tests: n/a (with a host-test harness, a Robolectric test could pin the warn text; see §3 row 7).

### PRM-3 — (Improvement) PermissionGateTest does not pin the full gate contract
- Severity: Improvement | Confidence: Confirmed
- File(s): p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/PermissionGateTest.kt:47-136
- Category: improvement
- Evidence: the 4 cases cover default-not-gated, missing-gates-both, granted-does-not-gate, and NoOp emptiness — good coverage of the 881fb31 regression pair. Not pinned: (a) `connect()` is intentionally un-gated (`P2pKitImpl.kt:384` — no `ensurePermissions()`), an invariant a future refactor could silently flip either way; (b) `P2pError.PermissionMissing.permissions` ordering/dedup with multiple missing entries; (c) `AndroidLanPermissionManager` itself (KDoc lines 38-45 honestly documents the manual recipe — but that leaves an audit-fix behavior verified by hand only).
- Proposed fix: add a `connectDoesNotConsultPermissionManager` case (FakePermissionManager counting calls) in commonTest; longer term add an androidHostTest source set to p2p-core (see §3).

### PRM-4 — WifiManagerWrapperImpl: cancellation racing the OS callback can leak the hotspot reservation and, worse, leave the whole process bound to a dead network
- Severity: Medium | Confidence: Confirmed (code inspection; the window is real but narrow — what would settle the join half empirically is a stress test cancelling `withTimeoutOrNull` in a tight loop around a fake ConnectivityManager, not possible against the real one)
- File(s): p2p-network-provisioning-android/.../WifiManagerWrapperImpl.kt:78-90, 109-111 (hotspot); 141-199, esp. 151-177 and 195-198 (join)
- Category: bug
- Root cause: both bridges use the `if (cont.isActive) cont.resume(v)` pattern instead of `cont.resume(v) { onCancellation }`. A cancellation (the manager's 60 s `withTimeoutOrNull`, or kit stop) that lands **between** the `isActive` check and the point where the handle becomes visible to `invokeOnCancellation` orphans the resource.
- Evidence (join, the severe half):
  ```kotlin
  if (terminated.compareAndSet(false, true)) {
      if (!cont.isActive) { ...unregister...; return }
      runCatching { connectivity.bindProcessToNetwork(network) }   // ← bind happens here
      val h = JoinHandleImpl(...)
      handle = h                                                    // ← plain captured var, no volatile
      if (cont.isActive) cont.resume(JoinResult.Joined(h))          // ← dropped if cancel won
  ```
  and the cancellation handler: `handle?.let { runCatching { it.close() } } ?: runCatching { connectivity.unregisterNetworkCallback(callback) }` (195-198). If cancellation wins after the bind but before the canceller observes `handle` (TOCTOU **plus** a data race: `handle` is a captured local with no happens-before edge between the ConnectivityManager thread and the cancelling thread), the `?:` branch unregisters the callback but leaves `bindProcessToNetwork(network)` set forever — every socket in the host process routes to a network nobody owns (the exact blackhole the in-code AUDIT-2026-06 comment at 155-161 describes for the pre-CAS case, unhandled for the post-bind case). Hotspot analog (78-90/109-111): cancel between `cont.isActive` and `handleHolder.handle = handle` → `invokeOnCancellation` reads null, `onStarted` completes, resume is silently dropped → reservation leaks until process death.
- Runtime impact: hotspot: leaked LOHS reservation (battery, hotspot stays up). Join: process-wide traffic blackhole until process restart. Trigger requires the 60 s timeout (or kit stop) to collide with the OS callback within a few instructions — rare, but the user-approval dialog sitting until exactly the deadline is the realistic collision scenario. | Platforms: Android | User-visible: yes (when hit)
- Failure class: leak (hotspot) / hang-equivalent connectivity loss (join)
- Proposed fix (do NOT implement): use the `resume(value, onCancellation)` overload — `cont.resume(JoinResult.Joined(h)) { h.close() }` and `cont.resume(HotspotStartResult.Started(handle)) { handle.close() }` — which atomically closes the resource when resume loses to cancellation; hold the join handle in an `AtomicReference`/`@Volatile` holder (like `AtomicHandleHolder`) so `invokeOnCancellation` reads a published value.
- Required tests: not unit-testable against real ConnectivityManager; add a code-review marker + cover the pattern in the manager-level fake by making the fake wrapper suspend until cancelled (asserts the manager path at least). Document the residual risk in INTERNAL_TESTING if untestable.

### PRM-5 — SecurityException mapping produces actionably-wrong error types (location toggle ≠ missing permission; join failures blamed on the wrong permission; original exception not chained)
- Severity: Medium | Confidence: Confirmed (behavior); the location-toggle mapping is deliberate per its own comment, but the rationale is self-contradictory
- File(s): p2p-network-provisioning-android/.../AndroidNetworkProvisioningManager.kt:366-391; p2p-core/.../NetworkProvisioningError.kt:25-26; manifest doc p2p-network-provisioning-android/src/androidMain/AndroidManifest.xml:9-12
- Category: bug (error semantics)
- Root cause: `mapStartException` collapses every `SecurityException` into `PermissionMissingForProvisioning(...)`. Three consequences:
  1. Device-wide Location toggle off (OEM message heuristic, 376-383) → `PermissionMissingForProvisioning([Location])`. The comment says this is "so callers can show the right remediation (open Location settings, not request a permission)" — but the error type carries only a permission list; a caller following the type's contract feeds it into a runtime-permission request, which instantly returns granted, and the hotspot still fails. The contract has `LocalNetworkResult.RequiresUserAction(instruction)` (NetworkProvisioningTypes.kt:85) built for exactly this case, and it is **never returned by the Android manager** for any path.
  2. `joinLocalNetwork`'s most plausible `SecurityException` is the *install-time* `CHANGE_NETWORK_STATE` missing from the host manifest (the module's own manifest comment, lines 10-12, calls it out as required by `requestNetwork`), yet the mapping names `NearbyWifiDevices`/`Location` (387) — the developer requests a runtime perm that was never the problem.
  3. `PermissionMissingForProvisioning` is constructed with `cause = null` (NetworkProvisioningError.kt:26 hardcodes null), so the original `SecurityException` text — the only disambiguator — survives only in `ctx.logger.warn` (default NoOp logger in production).
- Runtime impact: apps show the wrong remediation UI; with the default NoOp logger there is no way to distinguish the three cases programmatically. | Platforms: Android | User-visible: yes
- Failure class: none (wrong error semantics)
- Proposed fix (do NOT implement): map the location-toggle heuristic to `LocalNetworkResult.RequiresUserAction("Enable Location…")` / `JoinNetworkResult.RequiresUserAction(...)`; for the join path, include the exception message in the `JoinFailed`/permission error; thread the original throwable through (add a nullable cause parameter — additive, or wrap in `PlatformError` with a permissions hint in the message; avoid changing the sealed shape).
- Required tests: androidHostTest cases asserting `RequiresUserAction` for the location-mode message (replacing `locationModeOff…MapsToLocationPermissionMissing` which currently pins the wrong-type behavior — update, don't mask), and one asserting the join SecurityException surfaces the exception text.

### PRM-6 — JVM manager lacks the per-NIC SocketException guard that the same audit fix added on Android — `getManualConnectionInfo()` can throw a raw SocketException
- Severity: Medium | Confidence: Confirmed
- File(s): p2p-network-provisioning-desktop/.../JvmNetworkProvisioningManager.kt:137-159 (esp. 144-146) vs p2p-network-provisioning-android/.../AndroidNetworkProvisioningManager.kt:406-424 and WifiManagerWrapperImpl.kt:287-304
- Category: bug (platform parity + untyped exception from public API)
- Root cause: Android's `collectInterfaceIPs` wraps each NIC in `runCatching` with the explicit comment "isUp/inetAddresses throw SocketException when an interface vanishes mid-scan (AUDIT-2026-06 fix)". The JVM sidecar — the intentionally-parallel implementation — guards only `getNetworkInterfaces()` itself:
  ```kotlin
  for (nif in interfaces) {
      if (!nif.isUp || nif.isLoopback) continue      // ← can throw SocketException, unguarded
  ```
- Runtime impact: in `pollNetworkLoop` the outer `runCatching` absorbs it (networkState → Unknown, fine). But `getManualConnectionInfo()` (94-105) calls `collectNonLoopbackAddresses()` with no catch — a NIC vanishing mid-enumeration (VPN toggle, dock/undock, Wi-Fi off — routine on desktops, and precisely the moment users reach for manual-IP) throws a raw `SocketException` out of the public API instead of a typed error or a degraded list. | Platforms: JVM | User-visible: yes (exception surfaces to app code)
- Failure class: crash (uncaught platform exception in app code)
- Proposed fix (do NOT implement): mirror the Android per-NIC `runCatching` guard in `collectNonLoopbackAddresses`.
- Required tests: unit test with a throwing NIC is not feasible against real `NetworkInterface`; extract an enumeration seam (also unlocks §3 row 10) or accept a code-review marker.

### PRM-7 — Manager's system-initiated teardown paths orphan their watcher coroutines and (hotspot) skip closing the fired handle
- Severity: Low | Confidence: Confirmed
- File(s): p2p-network-provisioning-android/.../AndroidNetworkProvisioningManager.kt:355-364 (handleSystemStop), 249-271 (handleJoinReleased), 155-159 / 236-238 (watcher launches)
- Category: bug (bounded leak, asymmetric cleanup)
- Root cause / evidence: `handleSystemStop` does `handle = null; stopWatch = null` — it neither calls `firing.close()` (contrast `handleJoinReleased:263`, whose comment explains why close-before-drop is critical, and `stopLocalNetwork:173-175`, which both cancels the watcher and closes) nor cancels the `stopWatch` job. The watcher is `scope.launch { h.stopped.collect { … } }` — `collect` on a SharedFlow never completes, so after the one-shot terminal emission the coroutine stays suspended forever, pinning the fired `HotspotHandle` (and its `LocalOnlyHotspotReservation`, never `close()`d → CloseGuard warning, skipped release binder call). `handleJoinReleased` closes the handle but likewise leaves its own collector suspended forever (`joinReleaseWatch = null` without cancel — it cannot cancel itself mid-body, which is the design smell).
- Runtime impact: one suspended coroutine + retained handle per system-stop / join-release cycle, freed only at manager scope cancellation (kit stop). Bounded, slow. | Platforms: Android | User-visible: no
- Failure class: leak
- Proposed fix (do NOT implement): replace open-ended `collect` with a one-shot await — `scope.launch { handleSystemStop(h, h.stopped.first()) }` — so the watcher completes naturally; add `runCatching { firing.close() }` to `handleSystemStop` (idempotent; symmetric with the join path).
- Required tests: androidHostTest: after `simulateSystemStop`, assert `lastHandle.isClosed == true` and that a subsequent `startLocalNetwork` succeeds (also covers §3 row 5).

### PRM-8 — Hotspot-start timeout is reported as reason "STOPPED_BEFORE_START", masking the hang it actually is
- Severity: Low (misleading diagnostics; scale places this at Medium but the blast radius is one error/log string) | Confidence: Confirmed
- File(s): p2p-network-provisioning-android/.../AndroidNetworkProvisioningManager.kt:127-129, 397-404; WifiManagerWrapperImpl.kt:202-205
- Category: bug (diagnostics)
- Root cause: the manager reuses the wrapper's sentinel `-1` (defined as "onStopped fired without onStarted") for a completely different condition — `withTimeoutOrNull` expiring because the OS callback never arrived: `?: HotspotStartResult.Failed(reasonCode = -1)`. `reasonCodeName(-1)` then labels the resulting error "reason code -1: STOPPED_BEFORE_START".
- Runtime impact: a developer debugging the documented OEM never-calls-back hang (the very case the bounded wait was added for) is pointed at a phantom stop event. | Platforms: Android | User-visible: yes (error message)
- Failure class: none
- Proposed fix (do NOT implement): distinct sentinel (e.g. `-2` → "TIMED_OUT_WAITING_FOR_OS_CALLBACK") or a dedicated `HotspotStopped("timed out after …s")` message on the timeout branch.
- Required tests: androidHostTest with a suspending fake wrapper + injectable timeout asserting the timeout error text (see §3 row 1).

### PRM-9 — startLocalNetwork can return `Failed` while state says `LocalNetworkRunning` (and the reservation keeps running)
- Severity: Low | Confidence: Confirmed
- File(s): p2p-network-provisioning-android/.../AndroidNetworkProvisioningManager.kt:152-165 (ordering), 314-332 (buildStartedResult), 117-121 (already-running fast path)
- Category: bug (state/result divergence, narrow trigger)
- Root cause: on the success branch, `publishStartedNetworkState` + `_state.value = LocalNetworkRunning` + `LocalNetworkStarted` event all fire **before** `buildStartedResult` decides; if credentials are null (OEM redaction) *and* manual info is null (`ctx.lanTcpPort()` null — provisioning invoked before `kit.start()`, a legal call order), the caller receives `LocalNetworkResult.Failed("Hotspot started but neither credentials nor manualConnectionInfo are available.")` while `state`/`events` say running and the reservation stays up. The already-running fast path (117-121) can return the same `Failed` for an active hotspot.
- Runtime impact: app UIs keyed on the result show failure for a hotspot that is up (and consuming battery); no code path reconciles the divergence. | Platforms: Android | User-visible: yes (edge)
- Failure class: none (inconsistent state)
- Proposed fix (do NOT implement): decide the result *before* publishing state/events, and on the no-creds-no-info outcome either close the reservation before returning `Failed`, or return `StartedWithoutCredentials` with a best-effort info… the honest minimal fix is: compute result first; if `Failed`, close + reset to `Idle`.
- Required tests: androidHostTest: `ctx(lanTcpPort = null)` + `Behavior.Start(credentials = null, …)` → assert result/state agree and `lastHandle.isClosed` matches the chosen semantics.

### PRM-10 — Provisioning entry points still "work" after kit.stop(), but against a dead scope: a hotspot started post-stop is never auto-released
- Severity: Low | Confidence: Confirmed (code inspection)
- File(s): p2p-network-provisioning-android/.../AndroidNetworkProvisioningManager.kt:64-65, 88-100, 155-159; cross-check P2pKitImpl.kt:465-471
- Category: bug (defensive gap)
- Root cause: `scopeJob = SupervisorJob(parent = ctx.parentJob)` completes when `P2pKitImpl.stop()` cancels `internalJob`, and the `init` `invokeOnCompletion` fires (with `handle == null` if nothing was running). Nothing latches "closed": a later `startLocalNetwork()` call proceeds normally (lifecycleLock is a plain Mutex; `wifi.startLocalOnlyHotspot()` runs), but `scope.launch { h.stopped.collect … }` on the completed scope is dead-on-arrival and the completion hook has already fired — so the new reservation has no system-stop watcher and no automatic release; only an explicit `stopLocalNetwork()` frees it.
- Runtime impact: misuse-shaped (calling provisioning after stop), but nothing throws or warns — silent watcherless hotspot. `kit.networkProvisioning` remains reachable after `stop()` (no guard in P2pKitImpl). | Platforms: Android (JVM analog is benign — only the poll loop dies) | User-visible: no (until battery drain)
- Failure class: leak
- Proposed fix (do NOT implement): check `scopeJob.isActive` (or a `closed` flag set in the completion hook) at the top of `startLocalNetwork`/`joinLocalNetwork` and return `LocalNetworkResult.Failed(PlatformError(IllegalStateException("provisioning manager is closed")))` — mirrors the kit's own post-stop `IllegalStateException` convention.
- Required tests: androidHostTest: `ctx(parentJob = Job())`, cancel the job, call `startLocalNetwork`, assert it refuses (and, regression for the audit leak fix: with the job cancelled *after* a successful start, assert `lastHandle.isClosed` — §3 row 2).

### PRM-11 — WifiManagerWrapperImpl KDoc still carries the "targetSdk 26..28: ACCESS_COARSE_LOCATION" row the audit fix deleted as never-implemented
- Severity: Low | Confidence: Confirmed
- File(s): p2p-network-provisioning-android/.../WifiManagerWrapperImpl.kt:32-39 vs 63-70; contrast AndroidP2pPermissionManager.kt:21-25
- Category: bug (doc mismatch)
- Evidence: header says "targetSdk 26..28: `ACCESS_COARSE_LOCATION`", but `requiredRuntimePermission()` returns `P2pPermission.Location` (→ `ACCESS_FINE_LOCATION`) for everything below 33, and `AndroidP2pPermissionManager`'s AUDIT-2026-06 comment explicitly records that "the table promised a COARSE row the implementation never had". The stale copy survives in the wrapper — the intentionally-paired file.
- Runtime impact: doc-only; a maintainer following the wrapper's table would tell targetSdk-28 apps to request COARSE, diverging from the shipped reporter. | Platforms: Android | User-visible: no
- Failure class: none
- Proposed fix: replace the three-row table with the same two-row (device+targetSdk ≥33 → NEARBY, else FINE) table used in AndroidP2pPermissionManager.
- Required tests: n/a (doc).

### PRM-12 — "iOS network provisioning is permanently Unsupported" (CLAUDE.md / brief catalogue) contradicts the shipped `iosManualIp()` manual-IP manager
- Severity: Low | Confidence: Confirmed | [CATALOGUED-adjacent: the catalogued statement itself is the imprecise artifact]
- File(s): p2p-transport-lan/src/appleMain/.../IosManualNetworkProvisioningManager.kt:26-49, 82-106, 138-140 (in-scope anchor — code is the correct side); CLAUDE.md ("iOS provisioning is permanently `Unsupported` (Apple policy)"); .review-2026-07/BRIEF.md:50
- Category: bug (doc mismatch)
- Evidence: the class implements a real manual-IP path — `createManualPeer` registers via `ctx.manualPeerRegistrar` (105) and `IosLanDataTransport.connect` has the matching manual-IP dial branch (`IosLanDataTransport.kt:449-457`, `nw_endpoint_create_host(hint.host!!, …)`) — while only hotspot host (68-71) and Wi-Fi join (77-80) are `Unsupported`. `NetworkProvisioningTypes.kt:19-22` states this correctly ("iOS manual-IP (`iosManualIp()` in `:p2p-transport-lan`)").
- Runtime impact: a maintainer or reviewer trusting the blanket claim would skip reviewing/testing a shipped, reachable feature (this review's own scope notes nearly framed the file as Unsupported-only). | User-visible: no
- Failure class: none
- Proposed fix: reword CLAUDE.md / catalogue line to "iOS hotspot hosting and programmatic Wi-Fi join are permanently Unsupported (Apple policy); manual-IP fallback ships via `iosManualIp()`".
- Required tests: n/a (doc) — but see §3 row 11 for the missing appleTest.

### PRM-13 — iOS `getManualConnectionInfo` returns empty `hostAddresses` on a false premise ("Apple offers no synchronous non-loopback IP enumeration")
- Severity: Low | Confidence: Confirmed for the API claim (`getifaddrs` is plain POSIX, available to iOS apps and exposed to Kotlin/Native via `platform.posix`); the *feature gap* itself is documented behavior
- File(s): p2p-transport-lan/src/appleMain/.../IosManualNetworkProvisioningManager.kt:43-49, 86-93
- Category: bug (doc misstatement) + improvement (see PRM-14)
- Evidence: "Apple does not give us a non-loopback IP list synchronously without a path monitor subscription" — inaccurate: `getifaddrs()`/`freeifaddrs()` enumerate interface addresses synchronously on iOS with no entitlement, and are the standard way apps display their own LAN IP.
- Runtime impact: an iOS device cannot hand its own dial-in info to a peer through the SDK — `ManualConnectionInfo.hostAddresses` is always empty, pushing every Swift consumer to reimplement enumeration (the KDoc even instructs them to). The *capability* exists to close this gap in-SDK. | Platforms: iOS | User-visible: yes (feature gap)
- Failure class: none
- Proposed fix (do NOT implement): correct the KDoc; separately (PRM-14) populate `hostAddresses` via `getifaddrs` filtering `AF_INET`/non-loopback, mirroring the JVM/Android collectors.
- Required tests: appleTest asserting non-empty `hostAddresses` on the simulator once implemented.

### PRM-14 — (Improvement) Implement iOS `hostAddresses` via `getifaddrs` (companion to PRM-13)
- Severity: Improvement | File(s): IosManualNetworkProvisioningManager.kt:82-99 | Category: improvement
- Brings iOS to parity with JVM/Android `getManualConnectionInfo` so the manual-IP flow works iOS→X, not only X→iOS. Straightforward `platform.posix` walk; no new cinterop needed.

### PRM-15 — (Improvement) Address-collection semantics drift across the three managers
- Severity: Improvement | Confidence: Confirmed
- File(s): JvmNetworkProvisioningManager.kt:148-155 (IPv4 + non-link-local IPv6) vs AndroidNetworkProvisioningManager.kt:419 and WifiManagerWrapperImpl.kt:299 (IPv4 only) vs iOS (empty); JvmNetworkProvisioningManager.kt:139-143 (enumeration failure → emptyList → poll reports `NoNetwork` where the outer handler would say `Unknown`); WifiManagerWrapperImpl.kt:218-230 (`snapshotNetworkState` scans all NICs and hardcodes `ssid = null` although the joined network's `LinkProperties` — and the requested SSID from `credentials` — are both available)
- Category: improvement
- Impact: JVM may advertise IPv6 addresses Android/iOS never would; JVM misreports enumeration failure as NoNetwork; Android's joined-state IP list can include unrelated NICs. None currently breaks a flow (dialing any reported address works), but the divergence is exactly the class the parity invariant warns about.
- Proposed fix: shared address-filter policy (document "IPv4 + global IPv6" or "IPv4 only" and apply everywhere); use `ConnectivityManager.getLinkProperties(network)` + the requested SSID in `snapshotNetworkState`.

### PRM-16 — (Improvement) Join-rejection message says "already in progress" when the state is *already joined*, and there is no way to leave a joined network
- Severity: Improvement | Confidence: Confirmed
- File(s): AndroidNetworkProvisioningManager.kt:190-196; NetworkProvisioningTypes.kt:24-43 (no leave/unjoin API); test pins the wording (AndroidNetworkProvisioningManagerTest.kt:279-298)
- Category: improvement
- Evidence: `joinHandle` is only ever non-null **after** a successful join (in-progress joins are serialized out by `lifecycleLock`), so the guard fires for the joined state; the message "a join is already in progress; close the kit before retrying" misdescribes both the state and the remedy (the impl's `close()` isn't on the interface; apps can't call it without casting). Contract gap: `stopLocalNetwork` releases only the hotspot; a joined network can be left only via kit stop or system release.
- Proposed fix: reword the message; consider (spec discussion, [API-CHANGE]) a `leaveNetwork()` or defining `stopLocalNetwork` to also release a join.

### PRM-17 — (Improvement) Android host test fidelity: fakes model the pre-audit replay=0 flow semantics; "…AndClearsHandle" names assert neither
- Severity: Improvement | Confidence: Confirmed
- File(s): AndroidNetworkProvisioningManagerTest.kt:417-421, 442-446 (fakes: `replay = 0`) vs WifiManagerWrapperImpl.kt:146-150, 246-250 (production: `replay = 1`, with AUDIT-2026-06 comments explaining why replay=0 silently dropped pre-subscription one-shots); 172-195 & 301-324 (tests named `…AndClearsHandle` assert only the event — not `state == Failed`, not handle cleared, and crucially not `lastJoinHandle.isClosed` — the audit's close-before-drop blackhole fix has **no** regression assertion); 188, 215, 316 (`delay(50)` real-time subscription windows — withTimeout(2s) bounds the flake, but a loaded CI can still lose the pre-subscription emission *because* the fakes lack replay=1)
- Category: improvement (test-strengthening)
- Proposed fix: switch fakes to `replay = 1` (models production and removes the delay(50) sensitivity); add `assertTrue(wifi.lastJoinHandle!!.isClosed)` after `simulateRelease` and `assertEquals(Failed, mgr.state.value)` + restart-succeeds after `simulateSystemStop`.

### PRM-18 — (Improvement) ManualIpLoopbackTest: dead loopback-preference branch, one-directional "round-trip", environment couplings
- Severity: Improvement | Confidence: Confirmed
- File(s): ManualIpLoopbackTest.kt:85-87, 107-114, 47-65
- Category: improvement
- Evidence: (a) `hostAddresses.firstOrNull { it.startsWith("127.") }` can never match — `collectNonLoopbackAddresses` excludes loopback by construction, so the test always dials the machine's real NIC IP (works, but the loopback intent is dead code and the dial crosses the macOS local-network firewall surface — a latent CI/dev flake source); (b) comment says "Round-trip a Text message in each direction" but only Bob→Alice is sent/asserted; (c) `System.setProperty("user.home", …)` around create is a process-global mutation — safe under sequential execution, a race if test parallelism is ever enabled.
- Proposed fix: drop the 127.* branch (or bind-and-report loopback explicitly for tests); send+assert the Alice→Bob direction too; note the user.home constraint in the class KDoc.

### PRM-19 — (Improvement) JvmNetworkProvisioningManagerTest: conditional assertion silently passes; poll loop and timeout knobs untested
- Severity: Improvement | Confidence: Confirmed
- File(s): JvmNetworkProvisioningManagerTest.kt:82-100 (`if (info != null) { …asserts… }` — on a NIC-less host the test passes having asserted nothing; honest comment, but an assumption-violation should be visible, e.g. `assumeTrue`/skip rather than silent green); no test drives `pollNetworkLoop`/`networkState` (needs an enumeration seam — same seam PRM-6's fix wants); `pollIntervalMillis` is injectable but unused by tests
- Category: improvement (test-strengthening)

### PRM-20 — (Improvement) Sidecar KDoc/manifest nits
- Severity: Improvement | Confidence: Confirmed
- File(s)/evidence: AndroidNetworkProvisioningManager.kt:293-302 — the KDoc "Cancels the background scope and releases any active hotspot…" is attached to `private companion object`, not to `close()` below it (misplaced doc; `close()` is undocumented); AndroidDsl.kt:37 and AndroidProvisioningFactory.kt:15 — `[P2pKit.permissions]` KDoc links don't resolve (no import/FQN); AndroidDsl.kt:33-35 — the permission table omits that NEARBY also requires **device** API ≥33 (targetSdk ≥33 app on a 12L device needs FINE — `AndroidP2pPermissionManager` gets this right); AndroidManifest.xml — declaring no `uses-permission` is a documented policy (host app declares); fine as-is, but consider whether the *install-time* trio (`ACCESS_WIFI_STATE`, `CHANGE_WIFI_STATE`, `CHANGE_NETWORK_STATE`) should be library-declared for manifest-merger safety, since forgetting them fails only at runtime (PRM-5.2).
- Category: improvement

## 3. Missing tests

| Invariant untested | Why it matters | Where it should live | Type | Priority |
|---|---|---|---|---|
| 1. OS-callback timeout → typed Failed (hotspot + join) with truthful message | The audit's bounded-wait hang fix has zero coverage; `OS_CALLBACK_TIMEOUT_MS` is a hardcoded 60 s so the branch is untestable as written — needs an injectable timeout + a suspending fake behavior | androidHostTest AndroidNetworkProvisioningManagerTest | unit | P2 |
| 2. parentJob cancellation closes hotspot reservation + join binding (init `invokeOnCompletion`) | The audit's "reservation leaked for process lifetime" fix — currently only `close()` is exercised, never the kit-stop path that production uses | androidHostTest (ctx with `parentJob = Job()`, cancel, assert `isClosed`) | unit | P1 |
| 3. Join release closes the JoinHandle (`lastJoinHandle.isClosed`) | The close-before-drop blackhole fix (manager 254-263) is unasserted — a regression would silently reintroduce process-wide traffic blackholing | androidHostTest, extend `systemInitiatedJoinReleaseEmitsFailedEventAndClearsHandle` | unit | P1 |
| 4. `isLocalOnlyHotspotSupported=false` / `isSpecifierJoinSupported=false` → contract `Unsupported` | The audit's API-26/29 linkage-error fix; fakes hardcode `true` so the gates are never exercised | androidHostTest | unit | P2 |
| 5. After system stop, `state == Failed` and a new `startLocalNetwork` succeeds (restartability) | Pins handle-cleared semantics the current test names claim but don't assert | androidHostTest | unit | P2 |
| 6. `connect()` never consults the permission manager | Gate-scope invariant; a refactor adding `ensurePermissions()` to connect (or removing it from start*) would pass today's suite | p2p-core commonTest PermissionGateTest | unit | P3 |
| 7. `AndroidLanPermissionManager` reports empty + manifest warn fires/silences correctly | The 881fb31 Android-side behavior is verified only by a manual recipe; p2p-core has no Android host-test source set | new p2p-core androidHostTest (or Robolectric) | unit | P2 |
| 8. `AndroidP2pPermissionManager` / `requiredRuntimePermission` targetSdk×API matrix | The audit's targetSdk-keying fix (ungrantable-NEARBY bug) has no automated coverage | Robolectric (`@Config(sdk=…)`) or a Build-version seam | unit | P2 |
| 9. `createManualPeer` with blank host / out-of-range port → `IllegalArgumentException` from `PeerRegistry.registerManualPeer:115-116` surfaces to the caller | Validation exists only in core; managers pass through — pin that the sidecars don't swallow/wrap it inconsistently | JvmNetworkProvisioningManagerTest (real registrar or asserting fake) | unit | P3 |
| 10. JVM `networkState` poll transitions (NoNetwork/ConnectedToWifi/Unknown-on-failure) | Whole poll loop unexecuted by tests; PRM-6/PRM-15 fixes need the same enumeration seam | JvmNetworkProvisioningManagerTest | unit | P3 |
| 11. iOS manual-IP end-to-end (`iosManualIp()` → createManualPeer → dial via `nw_endpoint_create_host`) | The only iOS-reachable provisioning feature has no appleTest; only the sample exercises it by hand | p2p-transport-lan appleTest (loopback, mirrors ManualIpLoopbackTest) | integration | P2 |
| 12. WifiManagerWrapperImpl against real OS (hotspot start/stop, join approve/decline, cancellation) | Inherently device-bound; ensure INTERNAL_TESTING/smoke matrix has explicit rows for decline + timeout + location-off | manual (INTERNAL_TESTING / smoke matrix) | manual | P2 |

## 4. Section summary

**What this section owns:** the permission-reporting seam (`defaultPlatformPermissionManager` expect/actual + the gate contract test) and the three provisioning sidecars (Android LocalOnlyHotspot/Wi-Fi-join, JVM manual-IP, iOS manual-IP) plus their DSLs, factories, manifest, and tests.

**Overall health:** good. Remediation #9 is correctly implemented and consistent at both `ensurePermissions` call sites; C:54's single-mapping resolution is verified and its enum-constant deferral is sound; the Android manager's locking/stale-guard architecture (post-audit) is solid, and the wrapper's cancellation handling covers the *common* windows. The weak spots are the residual narrow races in the callback→coroutine bridges (PRM-4), error-type semantics that steer apps to wrong remediations (PRM-5, PRM-1), one missing parity guard on JVM (PRM-6) — and the fact that the single most OS-entangled file (WifiManagerWrapperImpl) plus the iOS manual path have no automated coverage at all.

**Top 3 risks:**
1. PRM-4 — join-cancellation race can leave the whole process bound to a dead network (severe consequence, narrow window, untestable today).
2. PRM-1 + PRM-5 — permission/error semantics: docs steer provisioning apps into over-gating core LAN, and SecurityException mapping sends apps to request permissions that aren't the problem (location toggle, CHANGE_NETWORK_STATE).
3. Coverage asymmetry — audit-critical behaviors (reservation release on kit stop, join-handle close on release, bounded OS waits) are implemented but unasserted (§3 rows 1–3), so regressions would be silent.

**CODEBASE_REVIEW_MAP_2026-07.md accuracy:** accurate for S9 and S10 (S9 "Android: no runtime perms + warnIfLanManifestPermissionsUndeclared; iOS/JVM: none" matches the code; S10's file inventory matches the 14 files reviewed; dependency edges `PROV → API` and `PROV -.-> registerManualPeer → REG` are correct). One nuance worth adding to the map: S10 also includes an *appleMain* manager inside `:p2p-transport-lan` (the map does note it, but the CLAUDE.md-level "iOS provisioning permanently Unsupported" framing contradicts it — PRM-12).

## Out-of-scope observations

- `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/dsl/Builders.kt:73-80` — `permissionManager` KDoc still calls the Android default "a real manifest-permission checker", stale after 881fb31 (it reports nothing; checking is a one-time construction warn), and recommends the sidecar wiring without mentioning it gates LAN start (feeds PRM-1). 881fb31 updated only 3 files; this doc was missed.
- `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/provisioning/UnsupportedNetworkProvisioningManager.kt:48` — fallback message "Network provisioning is planned for v0.2 and not implemented in v0.1." is stale at v0.6 and wrong in kind: the feature ships in sidecar modules; the message should say "no provisioning module registered — add `jvm()`/`android(ctx)`/`iosManualIp()`".
- `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/permission/P2pPermissionManager.kt:6-8` — KDoc's install-time examples omit the Wi-Fi pair that 881fb31 made the canonical example; minor.
- `REMEDIATION_2026-07.md:63` — manual-peer `(host,port)` dedupe listed as deferred though implemented at `PeerRegistry.kt:118-131` (known — catalogued as IDN-5 per the brief; confirming the code side is the dedupe, keyed (host, port, kind), with `require`-based host/port validation at :115-116).
- `p2p-sample-android/.../P2pKitViewModel.kt:431` — the sample's standalone-`AndroidP2pPermissionManager` pattern (not wired into the builder) is the better pattern and contradicts the SDK docs' recommendation; whichever way PRM-1 is resolved, sample and docs should agree.
