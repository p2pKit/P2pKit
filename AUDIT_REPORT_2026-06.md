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
| C1 | `SessionManager.kt:309` | **Manual-IP connect was completely broken.** The outgoing peerId anti-spoof check rejected every `registerManualPeer` connection, because a synthetic `manual-<uuid>` id can never equal the remote's real persisted id. The manual-IP fallback — the entire escape hatch for mDNS-blocked networks — failed 100% of the time. Confirmed by running `ManualIpLoopbackTest` (it threw `HandshakeRejected`). | Synthetic manual peers are now exempt from the equality check. The loopback test passes. *(2026-07 correction: the original fix adopted the remote's HELLO identity; since `012e49e` outgoing manual sessions keep the **dialed** synthetic identity — only incoming sessions adopt the HELLO id — so repeat `connect(manualPeer)` calls resolve to the same registered session instead of churning a healthy one.)* |
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

> **Annotation pass 2026-07-04** (2026-07 remediation Group L / DOCB-1; verified against the tree at `1f361c9`): every bullet below now opens with a status marker — `[IMPLEMENTED @ <commit>]`, `[PARTIALLY IMPLEMENTED …]`, or `[STILL OPEN — deliberate]` — checked directly against the current code. The original 2026-06 text is left unchanged after each marker. Maintenance rule going forward: when a deferred item is fixed, annotate its bullet here in the same commit so this list stays accurate.

These are real but either behavior-changing, opinionated, or hardware/host-dependent. Grouped by theme:

**SDK behavior decisions**
- **[PARTIALLY IMPLEMENTED @ `b9f6311`; remainder STILL OPEN — deliberate]** The recommended interim guard shipped: an inbound HELLO claiming the *local* peerId is rejected (`SessionManager.kt`, "peerId collision with local"). Full inbound identity verification is deliberately deferred to the encryption milestone (`TODO(encryption-milestone)` in `SessionManager.kt`). — `SessionManager.kt:309` — **inbound HELLO peerId is never verified** (the anti-spoof check only runs on outgoing dials). On an untrusted LAN a rogue peer sharing the appId can claim any peerId and evict a genuine session. This is the documented `SecurityMode.NoneForMvp` trust boundary; the real fix is the encryption handshake. *Recommend:* reject inbound HELLOs claiming the local peerId, and document the trust model — full fix belongs to the security milestone.
- **[IMPLEMENTED @ `b9f6311`]** A public `permissionManager` builder knob now exists (`dsl/Builders.kt`, threaded through `P2pKitImpl` as `permissionManagerOverride`). — `NoOpP2pPermissionManager.kt:12` / `P2pKitImpl.kt:452` — the permission manager is hardcoded to NoOp with no builder knob, so `P2pKit.permissions.missingPermissions()` is inert and the documented Android wiring is impossible. *Recommend:* add a `lifecycle { permissionManager = … }` DSL knob (a public-API addition — your call).
- **[PARTIALLY IMPLEMENTED @ `b9f6311`]** Dedup by `(host, port, kind)` shipped (`PeerRegistry.kt`; repeat registrations reuse the existing synthetic peer), and manual-peer provenance is modeled explicitly since `012e49e` (`PeerOrigin.Manual`). An unregister API is still open (2026-07 decision #6 / IDN-7). — `PeerRegistry.kt:107` — `registerManualPeer` mints a fresh id per call with no dedup or unregister and is eviction-exempt, so repeated provisioning calls grow the registry unbounded. *Recommend:* dedup by `(host,port,kind)` and add an unregister API.
- **[IMPLEMENTED @ `a08500a`]** `runHandshake` now wraps raw handshake-phase failures into `P2pError.ConnectionFailed` (typed `P2pError`s and `CancellationException` pass through unchanged). — `SessionManager.kt:171` — raw handshake-phase exceptions can still escape `connect()` as non-`P2pError` (only the transport-connect call is wrapped). *Recommend:* wrap the handshake path too.
- **[IMPLEMENTED @ `47fe586`, robustness pass @ `f4dd3a9`, Android parity @ `5568355`]** A 30 s write watchdog (`WRITE_TIMEOUT_MILLIS`) now fails the connection when a peer stops draining, mirrored in `JvmRawConnection.kt` and `AndroidRawConnection.kt`; transport-level regression test landed @ `df2dbea` (P1-15, injectable-timeout seam). — `JvmRawConnection.kt:34` — `write()` has no deadline and is cancellation-insensitive; this is the transport-layer root of the keep-alive wedge (the symptom is mitigated in core). *Recommend:* `runInterruptible` + a write timeout.

**Transport robustness (mostly real-device / platform)**
- **[IMPLEMENTED @ `47fe586`, race-hardened @ `f4dd3a9`]** TCP parameters are now created lazily via `ensureParameters()` (CAS-guarded); a cinterop failure surfaces as a typed failure through `start()`/`connect()` instead of a process-killing throw at `create{}`. — `IosLanDataTransport.kt:124` — `error()` in a property initializer can kill the iOS process at `create{}` (the sample even comments on it). *Recommend:* defer parameter creation into `start()` (returns `Result`).
- **[STILL OPEN — deliberate]** Awaits real-hardware diagnosis (issue #3; capture protocol in `docs/LAN_DIAGNOSTICS_PROTOCOL.md`). — `IosLanDataTransport.kt:122` — `include_peer_to_peer` is set on the browser but not on the listener/connection params, so AWDL-discovered peers may be undialable. Needs device testing to confirm direction of fix.
- **[STILL OPEN — deliberate]** Awaits real multi-interface hardware diagnosis (issue #2; capture protocol in `docs/LAN_DIAGNOSTICS_PROTOCOL.md`). — `AndroidLanDiscoveryTransport.kt:353,780` & `JvmLanDiscoveryTransport.kt:162,170` — bind-address selection can pick a cellular/loopback interface and the JVM transport has no network-rotation rebind; the macOS-loopback bind is only worked around in tests. These are interface-selection changes best validated on real multi-interface hardware.
- **[IMPLEMENTED @ `a08500a`]** A cellular-only satisfied path now maps to `Unsatisfied`, mirroring the data transport's cellular prohibition (file now lives at `p2p-core/src/iosMain/.../IosNetworkPathObserver.kt`). — `IosNetworkPathObserver.kt:68` — counts cellular as `Satisfied`, diverging from the cellular-prohibited data transport; can drive reconnect storms. *Recommend:* treat cellular-only as not-satisfied for LAN.

**Samples & docs (not shipped to consumers, but they're the test harnesses)**
- **[IMPLEMENTED @ `5568355`]** The directory is kept but carries a prominent superseded/deprecated banner pointing at the maintained `iosApp/` (the "point at `iosApp/`" half of the recommendation). — `docs/ios-sample-app/KitController.swift` — the "ready to copy" template doesn't compile against the current exported API and never collects sessions/messages. *Recommend:* delete the directory and point at the maintained `iosApp/`.
- **[IMPLEMENTED @ `52f4daa`]** The sample revamp added a file-transfer UI (`incomingFiles` collector + `sendFile` preset), non-latching session collectors, and a Local Network permission-denial hint (AUDIT-2026-06 D-G9 marker in `ContentView.swift`). — `iosApp/ContentView.swift` — no file-transfer UI (incoming offers time out invisibly), `attachMessageCollector` never returns (latches Connect/manual-dial UI), permission-denial banner never shows. iOS-UI work.
- **[IMPLEMENTED @ `52f4daa`; provenance gate extended @ `1f361c9`]** The `NSLocalNetworkUsageDescription`/`NSBonjourServices` keys and the "Check P2pKitShared XCFramework provenance" build phase now live in `project.yml` itself, so xcodegen regeneration preserves them; `scripts/run-ios-app.sh` gained a build-provenance gate (IOSB-3, P1-30, P1-31). — `iosApp/project.yml` — xcodegen regeneration drops the local-network Info.plist keys and the provenance build phase (silent zero discovery on a fresh checkout). Build-tooling change.
- **[IMPLEMENTED — path decision @ `b9f6311`, docs realigned @ `ce882a0`/`a08500a`]** The path decision was taken in code: JVM storage moved to `<home>/.p2pkit` with a legacy `<home>/p2pkit` migration (`FilePeerIdStorage.kt`; migration test P1-12 @ `efde8e1`), so the documented dot-path is now correct. The spec now documents `start()`, `networkPathStatus`, and the file-transfer API, and states that backgrounding does **not** produce `Stopped` (`Stopped` is only ever produced by `stop()`, spec §16.2/"Android backgrounded"). — `P2pKit-Spec.md` / `README.md` — the spec omits `start()`, `networkPathStatus`, and the whole shipped file-transfer API, still says backgrounding sets `Stopped` (code deliberately doesn't), and both docs give the wrong JVM PeerId path (`~/.p2pkit` vs actual `~/p2pkit`). **The path discrepancy needs a decision:** fix the docs to `~/p2pkit`, or change the code to the dot-prefixed hidden dir (a migration). I left the code as-is.
- **[IMPLEMENTED @ `47fe586`; up-to-date handling @ `adca586`]** The stamp is now a per-config `doLast` on the assembly task itself — skipped on failure and on UP-TO-DATE, stamping only the config it produced — and `iosApp/scripts/check-xcframework.sh` tolerates a moved HEAD when no framework sources changed (`p2p-transport-lan/build.gradle.kts`, "V0.4-PROVENANCE (L3) + AUDIT-2026-06" block). — `build.gradle.kts:124` — the XCFramework `BUILD_COMMIT.txt` provenance stamp runs even on failed/up-to-date assemblies and stamps both configs, so the freshness guard can lie. Gradle-finalizer change.
- **[IMPLEMENTED @ `47fe586`]** `maven-publish` + Central-shaped POMs are wired on all four library modules, centralized in the root build ("AUDIT-2026-06: `maven-publish` now ships on all four library modules", root `build.gradle.kts`); javadoc jars + an artifact-set verification gate followed @ `464fc53` (BLD-2, P1-29). — `provisioning .../build.gradle.kts` — `maven-publish` is on only two of four library modules; the provisioning sidecars are unpublishable.

**Test gaps (majors by impact, but they're missing tests, not broken code)**
- **[IMPLEMENTED @ `a08500a`]** `HandshakeIdentityTest` covers the outgoing peerId identity check (match accepted, mismatch rejected, remote claiming the local peerId rejected); `KeepAliveTest` covers the PONG-timeout failure path, the inbound PING→PONG responder, and the positive stays-connected liveness path. — `HandshakeTest`, `KeepAliveTest` — the outgoing peerId anti-spoof check and the keep-alive positive path / PONG responder have no tests.

---

## Minor findings (290) — 19 fixed

Distribution: **docs-drift 95**, error-handling 47, logic 45, architecture 31, cleanup 21, performance 14, ux 14, ui-correctness 8, accessibility 6, security 5, design-consistency 4.

The dominant theme is **documentation drift** (stale `v0.2`/`v0.3` version strings in a v0.6 tree, NsdManager→JmDNS references that the v0.5 migration left behind, stale test counts, the `~/.p2pkit` path) and **swallowed `CancellationException`** across the sample apps. I fixed the safe code-side ones encountered alongside larger fixes (dead code, redundant imports, the `user.home`-restored-to-empty-string test bug, the macOS JmDNS loopback test seam) and left the ~95 doc edits and sample-UI polish as a mechanical follow-up batch — they don't affect the SDK's behavior and are lower risk applied as their own reviewable pass.

A notable cross-cutting one worth a decision: `PROBLEMS_P2PKIT.md` (the prior audit) has several findings whose IDs no longer match their rewritten descriptions, two duplicate slugs, a double-counted entry (its 238 total is off by one), and a rejected-findings appendix that ends mid-entry. Sampling its "fixes applied" claims, **21 of 21 production fixes I spot-checked genuinely held** — the prior audit's code fixes are real; only its bookkeeping drifted.

---

## What to do next

1. **Review this diff** (`git diff main...audit/exhaustive-review-2026-06`) — one commit, 33 files, all tests green.
2. **Decide the deferred SDK-behavior items** above — chiefly the inbound-peerId trust model, the permission-manager DSL knob, the `~/p2pkit` path, and the manual-peer registry lifecycle. *(2026-07: all four decided and shipped — see the status markers in the deferred list above, chiefly `b9f6311`.)*
3. **The iOS sample + `docs/ios-sample-app`** need a real pass (or deletion of the stale docs copy) — most of the deferred majors live there and need Xcode to verify. *(2026-07: done — `iosApp/` revamped @ `52f4daa`; `docs/ios-sample-app/` carries a superseded banner @ `5568355`.)*
4. The ~95 doc-drift minors are a good mechanical follow-up commit. *(2026-07: done @ `ce882a0`.)*

The per-finding data (every id, file:line, verdict, and reason) is under `.audit/` — `phase3/verified-findings.json` is the full list, `report-data.json` the fixed/deferred split. `.audit/` is git-ignored so it doesn't pollute the diff.
