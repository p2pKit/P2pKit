# P2pKit — Exhaustive Audit Report (2026-06-12)

**Branch:** `audit/exhaustive-review-2026-06` (two commits on top of `main`: a baseline snapshot, then one fix commit so the whole audit is reviewable as a single diff).
**Method:** four phases — *understand* the SDK and its domain risk model, *find* (10 review dimensions × every one of the 211 source files, full coverage), *adversarially verify* every finding against the real code, then *fix* the safe ones.
**Verification:** `p2p-core:jvmTest`, `p2p-transport-lan:jvmTest`, `p2p-network-provisioning-android:testAndroidHostTest`, `p2p-network-provisioning-desktop:test`, `sample-kmp-shared:jvmTest` all pass; JVM, Android, and iOS-simulator targets all compile.

## Numbers

| | Critical | Major | Minor | Total |
|---|---|---|---|---|
| Verified (after dedup) | 7 | 71 | 290 | **368** |
| **Fixed in this commit** | **7** | **32** | **19** | **58** |
| Deferred to you | 0 | 39 | 271 | 310 |

Finders produced 677 raw reports; adversarial verification dropped 308 as duplicates of each other and 1 as refuted, leaving 368 real findings. Every finding was checked against the actual code — the one critical that was a *feature already broken in the repo* (manual-IP connect) was confirmed by running the existing test and watching it fail.

Severity rubric: **critical** = crash / process-kill / accumulating resource leak / silent data corruption / a whole feature dead / publish blocker. **major** = breaks a real production scenario or a documented promise under realistic conditions. **minor** = robustness gap, doc drift, dead code, test quality, polish.

---

## Critical findings — all 7 fixed

| # | Location | Problem | Fix applied |
|---|---|---|---|
| C1 | `SessionManager.kt:309` | **Manual-IP connect was completely broken.** The outgoing peerId anti-spoof check rejected every `registerManualPeer` connection, because a synthetic `manual-<uuid>` id can never equal the remote's real persisted id. The manual-IP fallback — the entire escape hatch for mDNS-blocked networks — failed 100% of the time. Confirmed by running `ManualIpLoopbackTest` (it threw `HandshakeRejected`). | Synthetic manual peers are now exempt from the equality check and adopt the remote's HELLO identity. The loopback test passes. |
| C2 | `SessionManager.kt:276` | **Remote-driven OOM.** The per-session reader used `Channel.UNLIMITED`; a peer flooding frames (or a slow local consumer) grew an unbounded in-memory queue with no TCP backpressure, and starved PONG handling into false keep-alive timeouts. | Bounded to 256; the reader now suspends and the kernel stops draining the socket (real backpressure). |
| C3 | `IosRawConnection.kt:221` | **fd + retain-cycle leak on every remote disconnect.** `nw_connection_cancel` was only reachable from a local `close()`; every remote-initiated end (EOF, read/write error, failed state) latched `closed=true` first, so `close()` early-returned and the connection was never cancelled. | CAS-guarded `cancelOnce` invoked on every terminal path. |
| C4 | `AndroidLanDiscoveryTransport.kt:781` | **Android host-app crash.** `JmDNS.create` ran unguarded inside a fire-and-forget rebind coroutine (no exception handler); an `IOException` during network churn became an uncaught exception that crashes the host process. | Wrapped; on failure the transport logs and degrades to the next rebind. |
| C5 | `IosLanDiscoveryTransport.kt:399` | **Accumulating NWBrowser leak.** The browser state handler nulled the shared `browser` field with no identity check; `refresh()` (fired ~every 3 s during reconnect) cancelled the old browser and installed a new one, then the old one's async cancelled-callback clobbered the field — orphaning a live browser each cycle. | Identity-checked: the handler only clears the field when it still points at *its* browser. |
| C6 | `AndroidNetworkProvisioningManager.kt:216` | **Process-wide socket blackhole + callback leak.** On network release, `handleJoinReleased` dropped the `JoinHandle` without `close()`. `JoinHandleImpl.close()` is the only code that clears `bindProcessToNetwork` and unregisters the callback, so all of the host process's sockets stayed bound to the dead network and one `NetworkCallback` leaked per join cycle. | `close()` the handle before nulling it (idempotent). |
| C7 | `FileTransferDispatcher.kt:80` | **File transfer permanently dead after the first reconnect.** `closeAll` (called on every reconnect rearm) latched a `closed` flag that nothing ever reset; afterwards `sendFile` threw and every inbound `FILE_OFFER` was silently dropped for the life of the session. | Added `reopen()`, called from `rearmWith` right after the in-flight transfers are failed. |

---

## Major findings (71) — 32 fixed, 39 deferred

### Fixed (32)

**Core lifecycle & session (`p2p-core`)**
- `P2pKitImpl.stop()` is now cancellation-safe (`NonCancellable`) and holds `startMutex`, so a concurrent `ensureStarted` can no longer rebind transports after teardown or leave the kit permanently half-stopped; `closeAllSessions()` is `runCatching`-wrapped so one bad session can't abort teardown.
- `startAdvertising`/`startDiscovery` failure no longer latches `P2pState.Failed` forever — a later success restores `Running`; `startDiscovery` now wraps raw platform exceptions into typed `P2pError` like its sibling.
- Keep-alive checks PONG liveness **before** the (mutex-held) PING write, so a wedged writer (peer stopped reading) can no longer disable keep-alive and hang `close()`/`stop()` behind the same mutex; `close()`'s CLOSE frame is now time-bounded.
- File transfer: terminal-state CAS guards on both transfer state holders (no more "Completed → Sending" regressions), a cap on concurrently-pending inbound offers (FILE_OFFER-spam DoS), an accept/cancel race fix, and a leak fix on the cancel-before-offer path.
- Network-path recovery signal converted from a drop-prone `replay=0` SharedFlow to a generation counter, so a `Satisfied` transition that lands before a reconnect handler parks is no longer lost.
- Reason strings (`ERROR`/`FILE_REJECT`/`FILE_CANCEL`) capped on decode (were uncapped to the 8 MiB frame limit).

**Transport (`p2p-transport-lan`)**
- JVM **and** Android accept loops now close sockets dropped on `trySend` overflow (fd leak) and survive a poisoned first bind (one-shot deferred replaced with a nullable `StateFlow`, so a later `start()` retry serves the accept loop).
- `JvmLanDiscoveryTransport.refresh()` implemented (it was a no-op, so the documented ~3 s reconnect re-resolution did nothing on desktop); JmDNS `list()` calls during refresh now use a short timeout instead of blocking the lock up to 6 s; JVM stop paths are exception-wrapped.
- iOS: the documented 5 s peer re-announce loop now exists (peers no longer vanish from `kit.peers` after 15 s); null-listener guards in the rebind window (was an NPE-crash into a non-null `nw` parameter); `stopDiscovery` clears host intent before the browser null-check (browsing no longer resurrects); `close()` re-checks `closed` after the blocking rebuild (no orphaned bound listener); the `IosLanDebug` console mirror is now opt-in (was `println`-ing every frame, including peer ids, in release).
- cinterop: `dispatch_data` mapping pinned with `objc_precise_lifetime` (latent receive-buffer use-after-free under ARC).
- Dead `SERVICE_TYPE_NSD` constant removed.

**Provisioning (`p2p-network-provisioning-android`)**
- OS-callback waits (hotspot start, Wi-Fi-join approval) are now bounded by `withTimeoutOrNull` instead of holding `lifecycleLock` forever; API 26/29 calls are SDK-gated to return the contract's `Unsupported` instead of a linkage error on the minSdk-24 module; the `WifiManager` lookup is null-safe (ethernet-only devices no longer crash at `create{}`); system-stop/release handlers run under the lock with stale-handle guards; the `handle!!` TOCTOU is snapshotted; permission reporting is targetSdk-aware (was telling targetSdk≤32 apps to request the ungrantable `NEARBY_WIFI_DEVICES`); cancellation no longer leaks a hotspot reservation; one-shot signals use `replay=1`; interface scans run on `Dispatchers.IO` with per-NIC guards.

**Samples / build**
- KMP shared factory now calls `P2pKitAndroid.initialize` (PeerId was regenerating every launch); `sample-kmp-shared` pinned to `jvmToolchain(17)`; desktop CLI `reconnect=` arg no longer becomes the device name, nested `runBlocking` removed, incoming-file `outputStream()` guarded with reject-on-failure; desktop `start()` honors `isStopping`.

### Deferred (39) — need your decision

These are real but either behavior-changing, opinionated, or hardware/host-dependent. Grouped by theme:

**SDK behavior decisions**
- `SessionManager.kt:309` — **inbound HELLO peerId is never verified** (the anti-spoof check only runs on outgoing dials). On an untrusted LAN a rogue peer sharing the appId can claim any peerId and evict a genuine session. This is the documented `SecurityMode.NoneForMvp` trust boundary; the real fix is the encryption handshake. *Recommend:* reject inbound HELLOs claiming the local peerId, and document the trust model — full fix belongs to the security milestone.
- `NoOpP2pPermissionManager.kt:12` / `P2pKitImpl.kt:452` — the permission manager is hardcoded to NoOp with no builder knob, so `P2pKit.permissions.missingPermissions()` is inert and the documented Android wiring is impossible. *Recommend:* add a `lifecycle { permissionManager = … }` DSL knob (a public-API addition — your call).
- `PeerRegistry.kt:107` — `registerManualPeer` mints a fresh id per call with no dedup or unregister and is eviction-exempt, so repeated provisioning calls grow the registry unbounded. *Recommend:* dedup by `(host,port,kind)` and add an unregister API.
- `SessionManager.kt:171` — raw handshake-phase exceptions can still escape `connect()` as non-`P2pError` (only the transport-connect call is wrapped). *Recommend:* wrap the handshake path too.
- `JvmRawConnection.kt:34` — `write()` has no deadline and is cancellation-insensitive; this is the transport-layer root of the keep-alive wedge (the symptom is mitigated in core). *Recommend:* `runInterruptible` + a write timeout.

**Transport robustness (mostly real-device / platform)**
- `IosLanDataTransport.kt:124` — `error()` in a property initializer can kill the iOS process at `create{}` (the sample even comments on it). *Recommend:* defer parameter creation into `start()` (returns `Result`).
- `IosLanDataTransport.kt:122` — `include_peer_to_peer` is set on the browser but not on the listener/connection params, so AWDL-discovered peers may be undialable. Needs device testing to confirm direction of fix.
- `AndroidLanDiscoveryTransport.kt:353,780` & `JvmLanDiscoveryTransport.kt:162,170` — bind-address selection can pick a cellular/loopback interface and the JVM transport has no network-rotation rebind; the macOS-loopback bind is only worked around in tests. These are interface-selection changes best validated on real multi-interface hardware.
- `IosNetworkPathObserver.kt:68` — counts cellular as `Satisfied`, diverging from the cellular-prohibited data transport; can drive reconnect storms. *Recommend:* treat cellular-only as not-satisfied for LAN.

**Samples & docs (not shipped to consumers, but they're the test harnesses)**
- `docs/ios-sample-app/KitController.swift` — the "ready to copy" template doesn't compile against the current exported API and never collects sessions/messages. *Recommend:* delete the directory and point at the maintained `iosApp/`.
- `iosApp/ContentView.swift` — no file-transfer UI (incoming offers time out invisibly), `attachMessageCollector` never returns (latches Connect/manual-dial UI), permission-denial banner never shows. iOS-UI work.
- `iosApp/project.yml` — xcodegen regeneration drops the local-network Info.plist keys and the provenance build phase (silent zero discovery on a fresh checkout). Build-tooling change.
- `P2pKit-Spec.md` / `README.md` — the spec omits `start()`, `networkPathStatus`, and the whole shipped file-transfer API, still says backgrounding sets `Stopped` (code deliberately doesn't), and both docs give the wrong JVM PeerId path (`~/.p2pkit` vs actual `~/p2pkit`). **The path discrepancy needs a decision:** fix the docs to `~/p2pkit`, or change the code to the dot-prefixed hidden dir (a migration). I left the code as-is.
- `build.gradle.kts:124` — the XCFramework `BUILD_COMMIT.txt` provenance stamp runs even on failed/up-to-date assemblies and stamps both configs, so the freshness guard can lie. Gradle-finalizer change.
- `provisioning .../build.gradle.kts` — `maven-publish` is on only two of four library modules; the provisioning sidecars are unpublishable.

**Test gaps (majors by impact, but they're missing tests, not broken code)**
- `HandshakeTest`, `KeepAliveTest` — the outgoing peerId anti-spoof check and the keep-alive positive path / PONG responder have no tests.

---

## Minor findings (290) — 19 fixed

Distribution: **docs-drift 95**, error-handling 47, logic 45, architecture 31, cleanup 21, performance 14, ux 14, ui-correctness 8, accessibility 6, security 5, design-consistency 4.

The dominant theme is **documentation drift** (stale `v0.2`/`v0.3` version strings in a v0.6 tree, NsdManager→JmDNS references that the v0.5 migration left behind, stale test counts, the `~/.p2pkit` path) and **swallowed `CancellationException`** across the sample apps. I fixed the safe code-side ones encountered alongside larger fixes (dead code, redundant imports, the `user.home`-restored-to-empty-string test bug, the macOS JmDNS loopback test seam) and left the ~95 doc edits and sample-UI polish as a mechanical follow-up batch — they don't affect the SDK's behavior and are lower risk applied as their own reviewable pass.

A notable cross-cutting one worth a decision: `PROBLEMS_P2PKIT.md` (the prior audit) has several findings whose IDs no longer match their rewritten descriptions, two duplicate slugs, a double-counted entry (its 238 total is off by one), and a rejected-findings appendix that ends mid-entry. Sampling its "fixes applied" claims, **21 of 21 production fixes I spot-checked genuinely held** — the prior audit's code fixes are real; only its bookkeeping drifted.

---

## What to do next

1. **Review this diff** (`git diff main...audit/exhaustive-review-2026-06`) — one commit, 33 files, all tests green.
2. **Decide the deferred SDK-behavior items** above — chiefly the inbound-peerId trust model, the permission-manager DSL knob, the `~/p2pkit` path, and the manual-peer registry lifecycle.
3. **The iOS sample + `docs/ios-sample-app`** need a real pass (or deletion of the stale docs copy) — most of the deferred majors live there and need Xcode to verify.
4. The ~95 doc-drift minors are a good mechanical follow-up commit.

The per-finding data (every id, file:line, verdict, and reason) is under `.audit/` — `phase3/verified-findings.json` is the full list, `report-data.json` the fixed/deferred split. `.audit/` is git-ignored so it doesn't pollute the diff.
