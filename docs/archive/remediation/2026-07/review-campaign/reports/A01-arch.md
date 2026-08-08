# A1-ARCH — S2 kit wiring & platform services review (+ architecture/boundary pass)

Scope: 19 files under `p2p-core/src/` (17 sources, 2 tests) + cross-cutting
architecture validation (layering, transport SPI, TransportManager vs docs,
`CODEBASE_REVIEW_MAP_2026-07.md` accuracy). All paths below are relative to
`/Users/abdelrahman/Projects/P2pKit/`. Line numbers refer to the working tree
at HEAD `870bf10`.

## 1. Per-file verdicts

| File | Lines | Verdict | Tests covering it | Test gaps (1 line) |
|---|---|---|---|---|
| commonMain/…/internal/P2pKitImpl.kt | 559 | findings: ARCH-1, ARCH-2, ARCH-3, ARCH-4, ARCH-5, ARCH-10; improvements: ARCH-11, ARCH-12, ARCH-14 | KitLifecycleTest, NetworkPathRecoveryTest (observer wiring), PermissionGateTest (ensurePermissions), LocalIdentityTest (newP2pKit) | No P2pState-transition assertions anywhere; no start-cancellation, hung-observer, or stop-race tests |
| commonMain/…/internal/TransportManager.kt | 32 | findings: ARCH-8 (spec drift); improvements: ARCH-15 | TransportManagerTest | Tie-break determinism (equal priority → ordinal → registration order) unasserted |
| commonMain/…/internal/Platform.kt | 9 | clean | indirect (every clock-using test) | none needed (trivial expect) |
| commonMain/…/internal/NativeBuildLog.kt | 14 | findings: ARCH-7 | none | Contract untestable as stated (JVM actual violates it) |
| commonMain/…/internal/NetworkPathObserverFactory.kt | 16 | clean | indirect (kit tests construct defaults per target) | none |
| commonMain/…/internal/NoOpNetworkPathObserver.kt | 25 | clean | indirect (JVM/Android kit tests run on it) | none |
| androidMain/…/internal/Platform.android.kt | 7 | clean | none (no Android host tests in p2p-core) | none needed |
| androidMain/…/internal/NativeBuildLog.android.kt | 7 | clean | none | none needed |
| androidMain/…/internal/AndroidNetworkPathObserverFactory.kt | 19 | clean | none | none needed (returns shared NoOp; documented) |
| androidMain/…/AndroidNetworkPathObserver.kt | 119 | findings: ARCH-6; improvements: ARCH-13 | **none** (no instrumented/robolectric tests) | register/unregister symmetry, last-network-lost flip, close-reset all unverified by automation |
| jvmMain/…/internal/Platform.jvm.kt | 7 | clean | indirect (all jvmTest) | none needed |
| jvmMain/…/internal/NativeBuildLog.jvm.kt | 25 | findings: ARCH-7 (the violating side) | none | n/a (no-op) |
| jvmMain/…/internal/JvmNetworkPathObserverFactory.kt | 12 | clean | indirect (every JVM kit test uses it) | none needed |
| iosMain/…/internal/Platform.ios.kt | 10 | clean | indirect (iosSimulatorArm64Test) | none needed |
| iosMain/…/internal/NativeBuildLog.ios.kt | 8 | clean | none | none needed |
| iosMain/…/internal/IosNetworkPathObserver.kt | 110 | findings: ARCH-6 (shared); improvements: ARCH-16 | **none** (constructed implicitly by iOS kit tests, never asserted) | start/close/restart idempotence and mapping table unasserted on simulator |
| iosMain/…/internal/IosNetworkPathObserverFactory.kt | 8 | clean | indirect | none needed |
| commonTest/…/internal/KitLifecycleTest.kt | 239 | findings: ARCH-9; improvements: (gaps in §3) | n/a (is a test) | Misses failure-path variants of the stop-hang scenario (see §3 rows 1, 3, 4) |
| commonTest/…/internal/TransportManagerTest.kt | 84 | improvements: ARCH-15 | n/a (is a test) | Tie-break determinism untested |

## 2. Findings

### ARCH-1 — `ensureStarted` bind loop swallows `CancellationException` and latches `P2pState.Failed` on caller cancellation
- Severity: High | Confidence: Confirmed (code-path analysis); the Android crash-escalation sub-claim is Uncertain — a 20-line repro cancelling `kit.start()` mid-bind would settle it
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt:266-281; secondary site :301
- Category: bug
- Root cause: `runCatching { transport.start() }` catches everything, including the `CancellationException` raised at a suspension point inside `transport.start()` when the *caller's* coroutine (e.g. an Android `lifecycleScope` running `kit.start()`) is cancelled. The failure branch then treats cancellation as a transport failure.
- Evidence:
  ```kotlin
  val r = runCatching { transport.start() }.getOrElse { Result.failure(it) }
  if (r.isFailure) {
      val cause = r.exceptionOrNull()
      val failed = P2pError.TransportStartFailed(...)
      startResult = Result.failure(failed)
      ...
      if (!stopped) _state.value = P2pState.Failed(failed)
      throw failed
  }
  ```
  Note the SPI contract (transport/DataTransport.kt:35-36: "transports do not throw" — they return `Result`), so in practice the *most likely* throwable this `runCatching` ever captures is precisely `CancellationException`. Contrast `startAdvertising` (P2pKitImpl.kt:339-340), which correctly rethrows CE before wrapping — the pattern exists in the same file but not here. Secondary site: `runCatching { pathObserver.start() }` (:301) also swallows CE, letting a cancelled caller proceed to latch `Running`.
- Runtime impact: cancelling `kit.start()`/`startAdvertising()`/`startDiscovery()`/`connect()` mid-bind (screen rotation, nav-away during startup — routine on Android) (a) publishes a spurious terminal-looking `P2pState.Failed(TransportStartFailed)` to every state collector, (b) records `startResult = failure`, and (c) throws a non-CE (`TransportStartFailed`) out of a cancelled coroutine — kotlinx-coroutines reports a non-CE completion of a cancelled coroutine to the uncaught-exception machinery, which on Android default handlers can crash the host process (this last step is the uncertain part). Violates the brief invariant "CancellationException must never be swallowed."
- Platforms: all (window is widest on Android/JVM where LAN `start()` does real socket/JmDNS work) | User-visible: yes (Failed state in UI; possible crash)
- Failure class: crash (potential) / wrong error semantics
- Proposed fix (do NOT implement): in the bind loop, check `if (cause is CancellationException) throw cause` before constructing `TransportStartFailed` (and do not touch `startResult`/`_state`); same guard around the `pathObserver.start()` runCatching. Blame: line 266 predates the remediation (3970483, 2026-05-17) — this is an open defect, not one of the 21, and my grep of AUDIT_REPORT_2026-06.md / PROBLEMS_P2PKIT.md found no catalogue entry for it (only sample-app CE swallows are catalogued).
- Required tests: commonTest — cancel a `kit.start()` parked inside a `HungStartTransport`-style fake; assert state is NOT `Failed`, `CancellationException` (not `TransportStartFailed`) propagates, and a subsequent `start()` succeeds.

### ARCH-2 — `stop()` tail (`pathObserver.close()`) runs outside `NonCancellable` and unbounded: hang on the observer's internal mutex; observer leak on caller cancellation
- Severity: High | Confidence: Confirmed (code-path analysis; hang variant requires a hung/slow `pathObserver.start()`, stated below)
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt:435-472 (block boundary at :463); dev/p2pkit/core/AndroidNetworkPathObserver.kt:69-118; internal/IosNetworkPathObserver.kt:71-109
- Category: bug (defect in/adjacent to the new f4dd3a9 #17 fix — the fix bounded the *kit* mutex but left the observer teardown outside both `NonCancellable` and any bound)
- Root cause: the `withContext(NonCancellable)` block ends at :463; lines 469-471 execute on the caller's cancellable context:
  ```kotlin
  runCatching { pathObserver.close() }
  internalJob.cancel()
  _state.value = P2pState.Stopped
  ```
  Both bundled observers hold a private `startMutex` for the *entire* `start()` body (Android: across the `registerNetworkCallback` binder call, AndroidNetworkPathObserver.kt:69-111; iOS: across the nw calls, IosNetworkPathObserver.kt:71-103) and take the same mutex in `close()`.
- Runtime impact, two vectors. (a) **Hang:** if `pathObserver.start()` is hung (wedged binder / a host-supplied observer — the exact "hung start" class the #17 fix targets), `ensureStarted` holds the kit `startMutex` inside it, `stop()` correctly falls back after 5 s (:452-462) — and then parks *indefinitely* at :469 on the observer's contended internal mutex. `stop()` still never returns; the new bounded-stop guarantee is defeated. `KitLifecycleTest.stopCompletesWhenATransportStartHangs` doesn't catch this because it hangs the *transport* while the observer is the JVM NoOp. (b) **Leak:** if the coroutine calling `stop()` is itself cancelled (e.g. `onDestroy` scope teardown racing `stop()`), the first real suspension in `pathObserver.close()` (contended-mutex path) throws CE, `runCatching` swallows it, and the observer is never closed — a `ConnectivityManager.NetworkCallback` / `nw_path_monitor_t` leaks for process lifetime and accumulates across kit create/stop cycles (Android caps callbacks at 100 per process → `TooManyRequestsException` for the whole app). Lines 470-471 are non-suspending and still run, so the failure is silent: state reads `Stopped` while the OS callback survives. Uncontended close (`Mutex.lock` fast path does not suspend) usually completes even when cancelled, which is why this needs contention or a genuinely suspending custom observer — narrow but real, and 5 s of mutex-starved `stop()` is a long window.
- Platforms: Android + iOS (bundled observers), any host-supplied observer | User-visible: (a) app hangs in stop; (b) accumulating OS callbacks
- Failure class: hang / leak
- Proposed fix (do NOT implement): move :469-471 inside the `withContext(NonCancellable)` block and bound the observer close the same way the mutex acquisition is bounded, e.g. `withTimeoutOrNull(STOP_START_MUTEX_TIMEOUT_MS) { pathObserver.close() }` with a warn on timeout.
- Required tests: commonTest — (1) `stop()` completes within a bound when a fake observer's `start()` never returns and its `close()` blocks on the same mutex; (2) cancel the coroutine running `stop()` mid-teardown and assert the fake observer's `close()` was still invoked.

### ARCH-3 — Terminal `Stopped` state can be overwritten: `stopped` guard added at :280 is missing at the success latch and the advertise/discovery failure paths
- Severity: Medium | Confidence: Confirmed (interleaving analysis; each window stated)
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt:313-316, :341-348, :365-375
- Category: bug
- Root cause: the f4dd3a9 remediation added `if (!stopped)` before the `Failed` write in the bind-failure path (:280) but three other state writes remained unguarded.
- Evidence:
  - :313-316 — after the post-bind `stopped` re-check (:291), `ensureStarted` still suspends in `pathObserver.start()` (:301) before `startResult = Result.success(Unit)` / `_state.value = P2pState.Running`. If that observer start takes >5 s and a concurrent `stop()` completes via the lock-less fallback, the late resume latches `startResult=success` and overwrites `Stopped` with `Running` — permanently (all later lifecycle calls throw ISE on the `stopped` flag, so nothing ever corrects the state flow). The :436-438 comment claims the re-check makes a late Running latch impossible; that only holds for the bind loop, not for the observer-start suspension after the re-check.
  - :346 / :373 — `startAdvertising`/`startDiscovery` catch-alls write `_state.value = P2pState.Failed(err)` unguarded. Easy window, no slow observer needed: advertise loop in flight → concurrent `stop()` closes the transports and sets `Stopped` → `transport.startAdvertising()` throws *because* the transport was closed → catch writes `Failed` after `Stopped`. Kit terminally reports `Failed` on a stopped kit.
- Runtime impact: public `P2pKit.state` (the documented lifecycle contract) reports `Running`/`Failed` forever on a stopped kit; host UIs keyed on `Stopped` misbehave. | Platforms: all | User-visible: yes
- Failure class: none (wrong observable state; no resource impact)
- Proposed fix (do NOT implement): re-check `stopped` after `pathObserver.start()` (mirror :291-296, including not latching `startResult`), and gate the two catch-block `Failed` writes with `if (!stopped)` exactly like :280.
- Required tests: commonTest — (1) fake observer with a gated `start()`; call `stop()` while parked; release; assert state stays `Stopped` and a later `ensureStarted` throws ISE; (2) `startAdvertising` racing `stop()` (transport throws on stopped-advertise) → final state `Stopped`, not `Failed`.

### ARCH-4 — Kit scope has no `CoroutineExceptionHandler`; an uncaught throw in any internal collector crashes Android host apps
- Severity: Medium | Confidence: Confirmed (no CEH exists: `grep -rn CoroutineExceptionHandler p2p-core/src/` → 0 hits); crash consequence is standard kotlinx/Android behavior
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt:78-79; PeerRegistry.kt:72-78 (exposure example)
- Category: bug (library-hardening defect)
- Root cause: `scope = CoroutineScope(Dispatchers.Default + internalJob)` — `SupervisorJob` isolates siblings but unhandled child exceptions go to the platform handler (Android default: kill the process). Collectors launched on this scope process *externally supplied* code: `PeerRegistry.start()` runs `transport.events.onEach(::processEvent).launchIn(scope)` with no catch — `events` is implemented by out-of-module SPI transports (the SDK's own extension story), so a third-party transport flow that throws, or a future bug in `processEvent`, becomes an app crash rather than a typed `P2pError`/log line. Same for the path-status collector (P2pKitImpl.kt:308-312).
- Runtime impact: violates the SDK's stated failure contract ("surface failures as typed P2pError … rather than swallowing" — crashing is the opposite extreme). No in-tree throw site is currently proven, hence Medium not High.
- Platforms: Android (crash), JVM (stderr noise), iOS (termination) | User-visible: yes when triggered
- Failure class: crash
- Proposed fix (do NOT implement): add a `CoroutineExceptionHandler` to the kit context that logs via `logger.error` (and optionally transitions state to `Failed`); independently, wrap `processEvent` per-event in the collector.
- Required tests: commonTest — register a `FakeDiscoveryTransport` whose `events` flow throws after one emission; assert the kit survives, logs, and other transports' events still process.

### ARCH-5 — After a lock-less `stop()` fallback, the bind loop's *failure* path skips the close-if-stopped cleanup, leaking re-bound transports (multi-transport only)
- Severity: Low | Confidence: Confirmed (interleaving analysis; unreachable with the single shipped transport)
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt:265-282 vs :284-296
- Category: bug
- Root cause: the new (f4dd3a9) post-bind re-check closes every transport when `stopped` — but only on the success path (:291-296). The failure branch (:267-281) throws immediately without any close loop. Sequence with transports [A, B, C]: A hangs holding the mutex → `stop()` falls back at 5 s, closes A/B/C, sets `Stopped` → A's `start()` finally returns success (its bind may have completed after `close()`, so A is re-bound), loop proceeds, B (re-binds or) *fails* → throw at :281 → the `if (stopped) close` loop never runs → A stays bound on a stopped kit until process exit.
- Runtime impact: leaked listener socket(s) on a stopped kit. Requires ≥2 registered transports plus the hung-start-then-stop race — impossible today (only LAN ships), real once a second transport module exists (the SPI's declared roadmap).
- Platforms: all | User-visible: no (port stays bound)
- Failure class: leak
- Proposed fix (do NOT implement): in the failure branch, before `throw failed`, run the same `if (stopped) { close all; throw ISE }` cleanup (or restructure so the stopped re-check+close executes on every exit from the bind loop).
- Required tests: commonTest combination test with two fake transports (first hung-then-succeeds, second fails) + concurrent `stop()`; assert both transports end closed.

### ARCH-6 — Bundled path observers never reset `status` to `Unknown` on `close()`, breaking the documented cold-read contract for restarted/shared observers
- Severity: Low | Confidence: Confirmed
- File(s): p2p-core/src/androidMain/kotlin/dev/p2pkit/core/AndroidNetworkPathObserver.kt:113-118; iosMain/kotlin/dev/p2pkit/core/internal/IosNetworkPathObserver.kt:105-109; contract at commonMain/kotlin/dev/p2pkit/core/NetworkPath.kt:79 and :56-60
- Category: bug (contract mismatch)
- Root cause: `close()` unregisters/cancels the OS monitor but leaves `_status` at its last value. NetworkPath.kt:79 promises "Cold reads return [Unknown] before [start]", and :56-60 explicitly blesses reusing one observer across kits ("an observer shared across kits will be re-started by the next kit's lifecycle"). A second kit constructed around a previously-used observer starts with a stale `Satisfied`/`Unsatisfied` and `P2pKitImpl` immediately feeds it to `SessionManager.applyPathChange` (:308-312). Today's consequences are benign (a spurious generation bump or a no-op `notifyPathLost` on an empty store), but the contract and behavior disagree, and a stale `Unsatisfied` would suppress nothing while a stale `Satisfied` mislabels an offline device in `networkPathStatus` until the first real callback.
- Runtime impact: misleading `P2pKit.networkPathStatus` for the pre-first-event window on observer reuse | Platforms: Android, iOS | User-visible: yes (status API)
- Failure class: none (misleading diagnostics)
- Proposed fix (do NOT implement): set `_status.value = NetworkPathStatus.Unknown` inside both `close()` bodies (under the existing mutex); or amend the KDoc if stale-until-restart is intended.
- Required tests: platform tests (or a common test against the fakes' contract) asserting `close()` → `status.value == Unknown`.

### ARCH-7 — `nativeBuildInfoLog` common contract promises the line "ALWAYS appears," but the JVM actual is deliberately empty
- Severity: Low | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/NativeBuildLog.kt:7-13 vs jvmMain/kotlin/dev/p2pkit/core/internal/NativeBuildLog.jvm.kt:23-25
- Category: bug (doc mismatch)
- Root cause: the expect's KDoc: "the identity line ALWAYS appears in hardware-test logs, even when the host app uses the default P2pLogger.NoOp" and "The format is fixed (`p2pkit: [buildInfo] <describe>`) so log scans can rely on it." The JVM actual emits nothing (kdoc'd rationale: JVM hosts wire their own logger + a `println` broke `NetworkPathRecoveryTest` timing). A JVM app with the default NoOp logger produces no build-identity line anywhere, and `docs/LAN_DIAGNOSTICS_PROTOCOL.md`-style log scans keyed on the fixed signature find nothing on desktop. Also note the "fixed format" is only exact on iOS; Android renders as tag `p2pkit` + message `[buildInfo] …` (equivalent for grep, worth one clarifying word).
- Runtime impact: none functional; diagnostic-workflow gap on JVM. The "a println breaks a 2 s test budget" justification is itself a smell (prod behavior driven by a test's timing).
- Platforms: JVM | User-visible: no
- Failure class: none
- Proposed fix (do NOT implement): soften the expect KDoc to state the JVM exception (one line), or route the JVM emission through `System.err`/java.util.logging where Gradle's stdout capture doesn't sit on the hot path.
- Required tests: none (doc fix).

### ARCH-8 — P2pKit-Spec.md §8.3 embeds a stale `TransportManager` implementation (pre-tie-break `maxByOrNull`)
- Severity: Low | Confidence: Confirmed
- File(s): P2pKit-Spec.md:506-516 vs p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/TransportManager.kt:26-30
- Category: bug (doc mismatch; spec is the locked contract document)
- Root cause: spec shows `.maxByOrNull { it.priority }`; code now sorts `compareByDescending { priority }.thenBy { type.ordinal }` with stable-sort registration-order ties (the comment's claim is accurate — Kotlin `sortedWith` is stable). Behavior differs from the spec snippet exactly in the tie case (spec: first-listed max wins regardless of kind; code: kind-ordinal then registration order).
- Runtime impact: none today (single transport); spec/code divergence on the selection contract the multi-transport roadmap depends on. Spec prose at :759 ("filters by canConnect, picks highest priority") remains accurate; only the embedded snippet drifted. Owner is S14/A13a — cross-filed from here because TransportManager is mine.
- Platforms: n/a | User-visible: no
- Failure class: none
- Proposed fix (do NOT implement): update the spec snippet (or replace it with prose stating the deterministic tie-break so the spec stops embedding implementation).
- Required tests: see ARCH-15 / §3 row 7.

### ARCH-9 — Kit-level common tests persist real peer-id state on the host machine (no `peerIdStorage` override)
- Severity: Low | Confidence: Confirmed
- File(s): p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/KitLifecycleTest.kt:47-51, :70-76, :82-87, :111-115 (builders without `peerIdStorage`); jvmMain/kotlin/dev/p2pkit/core/internal/PeerIdStorageFactory.jvm.kt:7-11; jvmMain/kotlin/dev/p2pkit/core/internal/FilePeerIdStorage.kt:11
- Category: bug (test hygiene / isolation)
- Root cause: `P2pKit.create` without the internal `peerIdStorage` override calls `defaultPeerIdStorage`, which on JVM writes `~/.p2pkit/<appId>/peer-id` (with a legacy-migration read of `~/p2pkit/...`) and on the iOS simulator writes NSUserDefaults. Every `:p2p-core:jvmTest` run creates/reads `~/.p2pkit/lifecycle-test/…`, `~/.p2pkit/indep-test/…`, `~/.p2pkit/stop-hang-test/…` on the developer/CI machine.
- Runtime impact: cross-run shared state (a pre-existing corrupt file from an old run changes test conditions), pollution of real home dirs, and `freshKitAfterStopIsIndependent` (:68) unknowingly shares one peer-id file between its two kits (same appId "indep-test") — currently harmless to its assertions, but exactly the kind of hidden coupling the test's name promises to exclude. The suite is in commonTest so it runs on every target.
- Failure class: none (test-quality)
- Proposed fix (do NOT implement): set `peerIdStorage = InMemoryPeerIdStorage()` (internal, reachable from commonTest) in every kit builder in this file — no assertion or timeout changes involved.
- Required tests: n/a (fix is to the tests).

### ARCH-10 — [CATALOGUED] Blocking disk I/O at kit construction (`newP2pKit` → `loadOrGenerate()` on the caller's thread)
- Severity: Low here (catalogued elsewhere as B:201) | Confidence: Confirmed still current
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt:543 (`localPeerId = peerIdStorage.loadOrGenerate()`), non-suspend chain P2pKit.kt:190 → Builders.kt:131
- Category: bug — previously catalogued (PROBLEMS_P2PKIT.md:201-202: StrictMode disk-read/write, ANR risk when created on the Android main thread); not in the 21 remediated findings and no deferral note appears in AUDIT_REPORT_2026-06.md or REMEDIATION_2026-07.md.
- Assessment of the deferral: the code is unchanged and the hazard stands (the init block additionally does synchronous `logger.info` + `nativeBuildInfoLog` and builds all transports on the calling thread). Because fixing it cleanly needs a suspending or async construction path, it is `[API-CHANGE]`-adjacent; no-API-change mitigation: document "construct off the main thread" prominently and/or move only the file I/O behind a lazy first-use point. Flagging so the orchestrator records an explicit decision rather than silent drift.
- Required tests: none until a fix direction is chosen.

## Improvements

### ARCH-11 — `stop()` bounds mutex-acquisition *and* teardown together
- Severity: Improvement | File: P2pKitImpl.kt:452-455
- `withTimeoutOrNull(5 s) { startMutex.withLock { teardownBoundResources() }; true }` cancels a *healthy but slow* locked teardown mid-flight (e.g. many sessions writing time-bounded CLOSE frames), releases the mutex, and re-runs the whole teardown lock-lessly. Safe today only because (a) every step is runCatching-wrapped/idempotent and (b) a starter that grabs the freed mutex immediately hits the `stopped` throw (:256). Bounding only the acquisition (`withTimeoutOrNull { startMutex.lock() }` + try/finally) would make the timeout mean what the comment says ("waits to take startMutex") and avoid the cancel-and-redo pass. Also note `teardownBoundResources()`'s runCatching steps swallow the timeout CE by design — worth one comment line, since it looks like a CE-swallow violation but is load-bearing here.

### ARCH-12 — Second concurrent `stop()` returns before teardown completes
- Severity: Improvement | File: P2pKitImpl.kt:428
- `if (stopped) return` makes a racing second `stop()` return immediately while the first is still tearing down (state may read `Stopping` after "stop() returned"). Idempotent-stop callers usually expect completion. A `CompletableDeferred`/`Job` awaited by later callers would give join semantics without API change.

### ARCH-13 — AndroidNetworkPathObserver: make the NET_CAPABILITY_INTERNET reliance explicit
- Severity: Improvement | File: AndroidNetworkPathObserver.kt:98-104
- The comment says "Dropping NET_CAPABILITY_INTERNET is deliberate" but no `removeCapability` call exists — correctness rests on `NetworkRequest.Builder()` defaults *not* including INTERNET (defaults are NOT_RESTRICTED/TRUSTED/NOT_VPN; verified against [NetworkRequest.Builder](https://developer.android.com/reference/android/net/NetworkRequest.Builder) and [Read network state](https://developer.android.com/develop/connectivity/network-ops/reading-network-state)). Behavior is correct (internet-less hotspot Wi-Fi matches, per the class KDoc), but a future "add capabilities to be safe" edit would silently break the hotspot story. One comment line naming the default-set assumption removes the trap.

### ARCH-14 — Post-stop `stopAdvertising`/`stopDiscovery`/`notifyAppBackgrounded` silently no-op, contradicting the "every lifecycle entry point rejects further calls" comment
- Severity: Improvement | File: P2pKitImpl.kt:115-118 vs :351-355, :378-382, :398-415
- The stop-side entry points and `notifyAppBackgrounded` (whose `scope.launch` on the cancelled scope silently does nothing) don't reject on `stopped`. Harmless semantics, but the comment overclaims; align the comment (or add the checks) so the next reader doesn't rely on loud failure.

### ARCH-15 — TransportManagerTest: tie-break determinism unasserted
- Severity: Improvement | File: TransportManagerTest.kt
- The deterministic tie-break (priority tie → `type.ordinal` → registration order) is TransportManager's one non-trivial behavior and the code comment's headline claim; no test pins it. Two equal-priority transports of different kinds (+ same kind, order swapped) would lock it in and guard the multi-transport future the spec (:759) promises.

### ARCH-16 — IosNetworkPathObserver: no transition logging
- Severity: Improvement | File: IosNetworkPathObserver.kt:78-99
- The handler maps and publishes silently; the Android sibling is equally quiet but iOS is where path flaps are under active hardware investigation (issues #2/#3). A `logger.debug("path → $mapped …")` in the update handler would make the existing trace docs' capture protocols observe path transitions for free. (K/N block-capture usage is otherwise correct: explicit trailing `Unit` matches the documented libdispatch boxing hazard.)

## 3. Missing tests

| Invariant untested | Why it matters | Where it should live | Type | Priority |
|---|---|---|---|---|
| P2pState machine transitions: Idle→Starting→Running; bind failure→Failed; failed start doesn't latch (retry succeeds→Running); re-advertise clears Failed (:337-338 AUDIT fix) | Zero `P2pState.Failed/Starting/Running` assertions exist in all of commonTest (grep-verified) — the documented lifecycle contract and two AUDIT-2026-06 fixes have no regression net | commonTest KitLifecycleTest (new cases) | unit | P1 |
| Cancelling `kit.start()` mid-bind neither latches Failed nor swallows CE (ARCH-1) | Routine Android lifecycle event corrupts public state today | commonTest KitLifecycleTest | unit | P1 |
| `stop()` bounded and observer closed when `pathObserver.start()` hangs / when the stop caller is cancelled (ARCH-2) | The #17 fix's own scenario, shifted one resource over; current hang test only covers a hung *transport* with a NoOp observer | commonTest KitLifecycleTest (fake observer) | unit | P1 |
| `stop()` racing `startAdvertising`/`startDiscovery` failure → terminal state stays `Stopped` (ARCH-3) | Easy race window; terminal state lies to UIs | commonTest | combination | P2 |
| `ensureStarted` after `stop()` throws ISE (direct assertion; today only implicit via `runCatching` in the hang test) | Terminal-kit contract (:251) unpinned | commonTest KitLifecycleTest | unit | P2 |
| Hung transport `start()` returning *failure* after lock-less stop; two-transport variant closes re-bound transports (ARCH-5) | Failure-path counterpart of the new hang test; guards the multi-transport future | commonTest KitLifecycleTest | combination | P3 |
| TransportManager tie-break determinism (ARCH-15) | Comment/spec claim with no net | commonTest TransportManagerTest | unit | P3 |
| AndroidNetworkPathObserver register/unregister symmetry, last-network-lost flip, close-reset | 119 lines of OS-callback lifecycle with zero automation (repo has no instrumented tests — candidate for the manual recipes in INTERNAL_TESTING.md, or a robolectric-style host test like the provisioning module already has) | p2p-core android host test or INTERNAL_TESTING.md §-entry | integration/manual | P2 |
| IosNetworkPathObserver start/close/restart idempotence + status mapping | Real monitor is constructed implicitly by every iOS kit test but never asserted | p2p-core iosSimulatorArm64 test | integration | P3 |

## 4. Section summary

**What S2 owns.** The composition root (`P2pKitImpl` — builder wiring, kit
scope, start/stop lifecycle, the new bounded-stop machinery), transport
selection (`TransportManager`), and all six expect/actual platform seams plus
the three network-path observers.

**Overall health.** Architecturally sound: layering is clean (zero
transport-lan type references in p2p-core — only two prose comments mention
JmDNS; build deps are kotlinx-only), the transport SPI is coherent
(`PeerOrigin` set exactly once at PeerRegistry.kt:146, checked only via the
enum at SessionManager.kt:186/:555 and PeerRegistry.kt:185; `"manual-"`
appears only in comments), all 6 expects have exactly 3 actuals each with
consistent per-target behavior, and `TransportManager` matches the spec's
selection prose (one-shot best-pick, no dial-failure fallback — consistent
with what the spec promises for v0.1; the spec's embedded snippet drifted,
ARCH-8). The f4dd3a9 stop-hang fix's core mechanism (bounded mutex +
`stopped` latch + post-bind re-check) is correct for the scenario it tests,
but its edges are incomplete: the guard pattern wasn't applied to all state
writes (ARCH-3), the teardown tail sits outside `NonCancellable`/any bound
(ARCH-2), and the bind loop's CE handling predates and undermines it
(ARCH-1).

**Top 3 risks.** (1) ARCH-2 — `stop()` can still hang or leak the OS path
callback, defeating the just-shipped bounded-stop guarantee; (2) ARCH-1 —
caller cancellation during start corrupts public state and may crash Android
hosts; (3) ARCH-4 — the unfenced kit scope turns any SPI/internal collector
throw into a host-app crash.

**CODEBASE_REVIEW_MAP_2026-07.md accuracy.** Verified and accurate on: file
universe (235 tracked files / 38,077 lines — recounted exactly), S2 file
count (19) and ownership list, the 6-expect inventory ("all internal, p2p-core
commonMain" — grep-confirmed, no expects in transport-lan commonMain), the
Gradle module graph (all 8 dependency edges I checked match build files,
including provisioning-desktop → transport-lan), "platform observers have no
automated tests" (grep-confirmed), and the wave/roster tables. Discrepancies
to fix:
1. **Runtime mermaid edge `NPO -.->|rebind| DISC` is false** — no file in
   p2p-transport-lan references `NetworkPathObserver` (grep: 0 hits); iOS
   discovery/data rebind is driven by the transport's *own* internal path
   monitor, and the S2 observer feeds only `SessionManager.applyPathChange`
   (P2pKitImpl.kt:308-312). The `path change nudge → SM` edge is correct;
   the rebind edge should be deleted or re-sourced to the transport-internal
   monitors.
2. **S2 "Depends on" omits S6** — `P2pKitImpl` directly constructs
   `DefaultP2pProtocol` (P2pKitImpl.kt:21, :97); correspondingly S6's
   "Depended on by: S3, S8" omits S2.
3. **S2 teardown-order blurb imprecise** — actual order is
   advertising/discovery-stop → sessions → transports → path observer →
   scope cancel (P2pKitImpl.kt:481-488, :469-471); the map's
   "sessions → transports → observers" drops the first step.
4. **S2 test-coverage line undersells** — besides KitLifecycleTest/
   TransportManagerTest, `NetworkPathRecoveryTest` exercises P2pKitImpl's
   observer wiring end-to-end (via `lifecycle { networkPathObserver = fake }`),
   and PermissionGateTest/LocalIdentityTest cover `ensurePermissions`/
   `newP2pKit` — attribution matters for reviewers sizing S2's real net.
