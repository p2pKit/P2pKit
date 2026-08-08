# A16-SAMPLES — Samples & harnesses (S11) review

Scope: 13 files across `p2p-sample-desktop`, `p2p-sample-desktop-ui`, `p2p-sample-android`, `sample-kmp-shared`.
Branch `audit/exhaustive-review-2026-06`, HEAD `870bf10`. Review complete — all 13 files read in full; SDK contract surfaces cross-checked (`P2pSession.kt`, `P2pFileOffer.kt`, `FileTransferJvm.kt`, `FileTransferAndroid.kt`, `Identity.kt`, `AndroidP2pPermissionManager.kt`, `AndroidLanDiag.kt`, version catalog, README §permissions).

## 0. Section-wide contract checks (all four app samples)

- **sendFile source ownership** — no sample closes a source passed to `sendFile` (no IOSB-11 recurrence). CLI + desktop-ui use the `sendFile(File)` helper (`FileTransferJvm.kt:22` opens/owns the stream); Android uses `sendFile(ctx, uri)` (`FileTransferAndroid.kt:28`). Kit-owns-source per `P2pSession.kt:75-77`.
- **accept(sink) — caller must close** (`P2pFileOffer.kt:34-37`): CLI closes on terminal state (Main.kt:696-701); desktop-ui closes on terminal/cancel + `stop()` sweep (`watchTransfer` onFinally + `closeAllIncomingSinks`, ui/Main.kt:741,590); Android closes on terminal + `stop()`/`onCleared()` sweeps (VM:748-757, 963-977, 984-999). Correct everywhere.
- **No nested `collect { collect { } }`** in any sample — inner flows use `launchIn`/separate `launch` throughout. Verified by full read.
- **API-2 cross-check** (SDK `send()` can leak raw IOException/ISE): every sample wraps `send`/`connect`/`sendFile` in Throwable-catching helpers (`runCatching` / `runCatchingCancellable` / `runCatchingNonCancel`), so raw exceptions are caught and surfaced, not missed. No sample-side action needed for API-2. [LIKELY-DUP API-2 — SDK-side, not re-reported]
- **appId parity** — all four samples use `p2pkit-desktop-sample`: CLI default (desktop Main.kt:80), desktop-ui `DEFAULT_APP_ID` (ui/Main.kt:904), Android `APP_ID` (VM:1103), iOS `ContentView.swift:641`. Cross-platform discovery interop intact.
- **Trace layers per CLAUDE.md** — CLI: on by default with `trace=off|frames` arg (desktop Main.kt:88-94, matches CLAUDE.md). Desktop-ui: both on (ui/Main.kt:110-111). Android: `FrameTrace` → logcat at `start()` (VM:276-277); transport lifecycle trace is always-on `Log.d` `P2pKit*` tags in `androidMain` (byte-level `AndroidLanDiag.traceFrames` opt-in). Claim holds.
- **Permission model** — SDK never requests; Android sample requests via `rememberLauncherForActivityResult`, re-checks after grant/deny (`refreshMissingPermissions()`), resumes the operation on grant (MainActivity:872-884, 1095-1104), surfaces deny + "Don't ask again" hint (`notifyPermissionDenied`), and handles the OEM Location-mode quirk with a Settings deep-link. Standalone `AndroidP2pPermissionManager` at VM:431 confirmed the intended pattern. [LIKELY-DUP PRM-1 — sample deliberately does not builder-wire the sidecar manager; that is correct]
- **Manifest vs docs** — sample manifest declares exactly the README core set (INTERNET, ACCESS_NETWORK_STATE, ACCESS_WIFI_STATE, CHANGE_WIFI_MULTICAST_STATE; README.md:162-165) plus provisioning perms (CHANGE_WIFI_STATE; NEARBY_WIFI_DEVICES `neverForLocation` targetApi 33; ACCESS_FINE_LOCATION maxSdk 32). No missing/excess declarations. Only the launcher activity is exported, with the MAIN/LAUNCHER filter — required and hygienic.

## 1. Per-file verdicts

| File | Lines | Verdict | Tests covering it | Test gaps (1 line) |
|---|---|---|---|---|
| p2p-sample-desktop/src/main/kotlin/dev/p2pkit/sample/desktop/Main.kt | 774 | findings: SMP-2, SMP-3, SMP-4, SMP-5; improvements: SMP-13 | none (manual — INTERNAL_TESTING §A-§K) | No automated check of arg parsing (`reconnect=`, `trace=`) or `uniqueSaveFile` collision logic |
| p2p-sample-desktop-ui/src/main/kotlin/dev/p2pkit/sample/desktop/ui/Main.kt | 1752 | findings: SMP-1, SMP-6, SMP-7; improvements: SMP-9, SMP-10 | none (manual) | Incoming-file destination collision behavior untested (would have caught SMP-1) |
| p2p-sample-android/.../MainActivity.kt | 1354 | findings: SMP-6 (logcat leg); improvements: SMP-11, SMP-12 | none (no instrumented tests exist) | Permission-launcher grant→resume flow is manual-only |
| p2p-sample-android/.../P2pKitViewModel.kt | 1215 | findings: SMP-4, SMP-6; improvements: SMP-9, SMP-11 | none | stop()/onCleared teardown ordering (pendingStopJob join) is untested |
| p2p-sample-android/.../P2pKitSampleApplication.kt | 16 | clean | none | n/a (2 statements; `P2pKitAndroid.initialize` wired as documented) |
| p2p-sample-android/src/main/AndroidManifest.xml | 41 | clean | none | n/a — matches README-documented perm set; exported only for launcher |
| p2p-sample-android/src/main/res/values/themes.xml | 4 | clean | none | n/a (framework Material NoActionBar parent; referenced by manifest) |
| sample-kmp-shared/commonMain/Demo.kt | 35 | clean | KmpConsumerLoopbackTest (jvm) | Failure path (connect throws → advertising left on) is by-design/documented, untested |
| sample-kmp-shared/commonMain/P2pKitFactory.kt | 15 | clean | KmpCallsiteSmokeTest, KmpConsumerLoopbackTest | n/a |
| sample-kmp-shared/androidMain/P2pKitFactory.android.kt | 35 | clean | none (no android host test in this module) | `createP2pKit` before `initP2pKitAndroid` → error() path untested |
| sample-kmp-shared/jvmMain/P2pKitFactory.jvm.kt | 12 | clean | KmpConsumerLoopbackTest | n/a |
| sample-kmp-shared/commonTest/KmpCallsiteSmokeTest.kt | 22 | clean (merely-executes by design — compile-resolution smoke, honestly documented) | self | Asserts nothing at runtime beyond reference non-null; acceptable for its stated purpose |
| sample-kmp-shared/jvmTest/KmpConsumerLoopbackTest.kt | 130 | findings: SMP-8; improvements: SMP-14 | self (real mDNS+TCP loopback) | Happy-path only: no file transfer, no re-entrant stop, no reconnect through the consumer factory |

## 2. Findings

### SMP-1 — desktop-ui incoming file destination is not uniquified: same-named offers silently overwrite / can interleave-corrupt
- Severity: Medium | Confidence: Confirmed
- File(s): p2p-sample-desktop-ui/src/main/kotlin/dev/p2pkit/sample/desktop/ui/Main.kt:672-683, 810-813
- Category: bug
- Root cause: the audit fix applied to the CLI (`A-G9-samples-desktop-ios-19`, `uniqueSaveFile` with atomic `createNewFile`, desktop Main.kt:734-752) and to Android (`A-G8-samples-android-04`, `uniqueDestination`, VM:807-819) was never mirrored into desktop-ui, which still keys the destination by sanitized offer name alone.
- Evidence:
  ```kotlin
  val saveDir = File(baseDir, sanitize(session.peer.name)).also { it.mkdirs() }
  val saveFile = File(saveDir, sanitize(offer.name))          // ui/Main.kt:674
  ...
  val out = runCatching { saveFile.outputStream() }            // truncates existing file
  ```
- Runtime impact: with auto-accepted offers, (a) a re-sent same-named file truncates the previously received copy; (b) two peers in a room sending the same common filename (e.g. `IMG_0001.jpg`) → the second silently destroys the first; (c) two *concurrent* same-named offers open two streams onto one path → interleaved, corrupted output. Both sibling samples were judged worth an A-class fix for the identical defect. | Platforms: JVM desktop | User-visible: yes
- Failure class: data loss
- Proposed fix (do NOT implement): port the CLI's `uniqueSaveFile` (atomic `createNewFile` claim, " (n)" suffix) into `wireIncomingFiles`; also strip ISO control chars in `sanitize` for parity with the CLI's `sanitizeName`.
- Required tests: sample-level unit test of the uniquifier (two claims same name → distinct paths); manual two-offer re-send check per INTERNAL_TESTING.

### SMP-2 — CLI `close` command evicts sessions by key without identity check, violating its own replacement-safety rule
- Severity: Low | Confidence: Confirmed
- File(s): p2p-sample-desktop/src/main/kotlin/dev/p2pkit/sample/desktop/Main.kt:476 (vs. the documented intent at 622-627 and the correct two-arg remove at 641)
- Category: bug
- Root cause: `registerSession`'s state watcher uses `sessions.remove(session.peer.id.value, session)` precisely so "a newer session already stored for the same peer is never evicted" (comment at 624-626), but the user `close` command path uses the one-arg remove.
- Evidence:
  ```kotlin
  runCatching { session.close() }.onFailure { ... }
  sessions.remove(session.peer.id.value)   // Main.kt:476 — not identity-checked
  ```
- Runtime impact: if a replacement session for the same peer (e.g. an incoming redial) is registered between `close()` completing and the remove, the *live* new session is dropped from the CLI map: `sessions`/`send`/`to` no longer see it while its collectors keep printing; auto-mesh only self-heals when the local id is the smaller one. Narrow race window; harness-only confusion. | Platforms: JVM desktop | User-visible: yes (stale `sessions` output)
- Failure class: none (state desync in harness)
- Proposed fix: use the two-arg `sessions.remove(session.peer.id.value, session)` (the terminal-state watcher already prunes it anyway; the explicit remove could even be dropped).
- Required tests: none realistic at sample level; code-review invariant.

### SMP-3 — CLI swallows CancellationException around suspend SDK calls (fix applied to the other two samples, not the CLI)
- Severity: Low | Confidence: Confirmed
- File(s): p2p-sample-desktop/src/main/kotlin/dev/p2pkit/sample/desktop/Main.kt:161-168 (auto-mesh), 303-314 (`manual`), 335-342/351-358 (`adv`/`disc`), 394 (`catch (e: Throwable)` in `connect`), 426-429, 456-459, 473-475, 517-528, 678-688
- Category: bug
- Root cause: the CE-rethrowing helper was introduced in desktop-ui (`runCatchingCancellable`, ui/Main.kt:954-960, audit A-G9-samples-desktop-ios-29) and Android (`runCatchingNonCancel`, VM:1119-1126, audit C-G8-samples-android-18) but the CLI still uses plain `runCatching`/`catch (e: Throwable)` around suspend SDK calls, which catches `CancellationException`.
- Evidence:
  ```kotlin
  } catch (e: Throwable) {                       // Main.kt:394 — catches CE
      System.err.println("connect failed: ${e.message}")
  ```
- Runtime impact: on `quit`/EOF teardown (`scope.cancel()` at 193), in-flight sends/connects report spurious `send … failed:`/`connect failed:` lines instead of cancelling silently, and the cancelled coroutines run their follow-up statements. Violates the stated repo invariant ("CancellationException must never be swallowed") in the reference consumer that teaches adopters. | Platforms: JVM desktop | User-visible: yes (misleading shutdown output)
- Failure class: none (misleading diagnostics / contract violation)
- Proposed fix: copy `runCatchingCancellable` into the CLI and replace the plain `runCatching`/`catch(Throwable)` wrappers around suspend calls.
- Required tests: none at sample level; grep-check in review.

### SMP-4 — per-transfer StateFlow collectors never terminate (CLI sender+receiver, Android VM both directions) — coroutine pile-up over long runs
- Severity: Low | Confidence: Confirmed
- File(s): p2p-sample-desktop/src/main/kotlin/dev/p2pkit/sample/desktop/Main.kt:519-526 (sender), 690-703 (receiver); p2p-sample-android/src/main/java/dev/p2pkit/sample/android/P2pKitViewModel.kt:716-721 (outgoing state+bytes), 748-760 (incoming state+bytes)
- Category: bug
- Root cause: `transfer.state` / `transfer.bytesTransferred` are `StateFlow`s (never complete). Desktop-ui was given `watchTransfer` which ends collection at the first terminal state precisely "so per-transfer collectors don't pile up over long runs" (ui/Main.kt:744-770); the CLI and the Android VM never got that fix — their collectors update rows/print lines and, on the receive side, close the sink on terminal state, but keep collecting forever.
- Evidence (Android VM:716-721; CLI receiver analogous):
  ```kotlin
  scope.launch { transfer.state.collect { st -> updateRowState(transfer.id, st) } }
  scope.launch { transfer.bytesTransferred.collect { b -> updateRowBytes(transfer.id, b) } }
  ```
- Runtime impact: 1-2 suspended coroutines (holding the transfer object) leak per transfer for the life of the run scope (Android: until Stop/onCleared; CLI: until process exit — and the CLI is documented for unattended auto-accept use). They are not in `sessionJobs`, so session removal does not cancel them. Slow, bounded-by-run leak; no functional error. | Platforms: JVM desktop CLI, Android | User-visible: no
- Failure class: leak
- Proposed fix: mirror desktop-ui's `watchTransfer` (collect until `first { it.isTerminal() }`, cancel the bytes job in `finally`) in both files.
- Required tests: none automated at sample level; note in INTERNAL_TESTING long-run soak.

### SMP-5 — CLI has no SIGINT/shutdown hook: Ctrl-C skips `p2p.stop()`, leaving the mDNS advertisement to go stale with no goodbye
- Severity: Low | Confidence: Confirmed (no `addShutdownHook` anywhere in repo Kotlin — repo-wide grep)
- File(s): p2p-sample-desktop/src/main/kotlin/dev/p2pkit/sample/desktop/Main.kt:175-194 (clean path only)
- Category: bug
- Root cause: teardown (`p2p.stop()` + `scope.cancel()`) runs only when `repl` returns (`quit`/`exit`/EOF). SIGINT — the default way to kill a CLI — terminates the JVM without running it; no `Runtime.getRuntime().addShutdownHook` exists.
- Evidence: Main.kt:189-193 is the only stop path; grep for `addShutdownHook` across `--include=*.kt` returns nothing.
- Runtime impact: OS closes the sockets (peers see abrupt `Failed`, which is handled), but the JmDNS service is never unregistered gracefully — no mDNS goodbye packets — so other devices keep a ghost peer entry until their cache/lastSeen eviction. In manual smoke runs (this CLI is a primary harness, incl. the CLI↔iOS pairing recipe) ghost peers can mislead the operator between runs. Desktop-ui's window-close equivalent is already documented as best-effort in-code (ui/Main.kt:129-134, catalogued under B-G9-samples-desktop-ios-20). | Platforms: JVM desktop | User-visible: yes (ghost peer on other devices)
- Failure class: none (transient stale advertisement; self-corrects)
- Proposed fix: register a shutdown hook that runs `runBlocking { withTimeout(3s) { p2p.stop() } }` best-effort; keep the clean path as-is.
- Required tests: manual (Ctrl-C, observe peer-Lost latency on second device).

### SMP-6 — remote-controlled strings printed unsanitized to terminal-bound streams in desktop-ui (stderr) and Android (logcat) — terminal-escape-injection fix applied only to the CLI
- Severity: Low | Confidence: Confirmed
- File(s): p2p-sample-desktop-ui/src/main/kotlin/dev/p2pkit/sample/desktop/ui/Main.kt:373, 675-677, 687, 834-835, 843, 847, 869 (peer names / offer names to `System.err`); p2p-sample-android/src/main/java/dev/p2pkit/sample/android/P2pKitViewModel.kt:387, 674, 677, 1021, 1030, 1033, 1049 (peer names / offer names to `Log.*`)
- Category: bug
- Root cause: the CLI strips ISO control characters from every remote-controlled string before it reaches the terminal (`sanitizedForTerminal`, desktop Main.kt:721-727, audit B-G9-samples-desktop-ios-11: peer-supplied names/file names from mDNS TXT / HELLO / FILE_OFFER can embed ANSI/OSC sequences that rewrite or spoof operator-terminal lines). Desktop-ui prints the same fields raw to `System.err` (which lands in the launching terminal under `./gradlew :p2p-sample-desktop-ui:run`), and Android logs them raw to logcat (rendered by `adb logcat` in the operator's terminal). The Compose in-app rendering is inert; only the terminal-bound legs are affected.
- Evidence (ui/Main.kt:675-677):
  ```kotlin
  System.err.println(
      "[p2pkit] incoming file ${offer.name} (${offer.sizeBytes}B) → ${saveFile.absolutePath}"
  )
  ```
- Runtime impact: a non-conforming LAN peer can inject escape sequences into the tester's terminal during trace capture (the exact scenario the CLI fix describes, e.g. a spoofed "Completed" line). | Platforms: JVM desktop (stderr), Android (adb logcat) | User-visible: yes (operator terminal)
- Failure class: spoofing (operator-facing)
- Proposed fix: port `sanitizedForTerminal()` and apply to peer/file-name/message interpolations on the stderr/logcat legs (in the Android `TailLogger`/`Log` call sites and desktop-ui `System.err` call sites); also strip ISO controls in both `sanitize()` filename helpers.
- Required tests: none automated; manual with a crafted peer name.

### SMP-7 — desktop-ui renders unbounded remote-supplied reject/cancel reasons (Android's bounding fix not mirrored)
- Severity: Low | Confidence: Confirmed
- File(s): p2p-sample-desktop-ui/src/main/kotlin/dev/p2pkit/sample/desktop/ui/Main.kt:1611-1615 (state label `Text` with no `maxLines`), 1636-1644 (`label()` with no truncation)
- Category: bug
- Root cause: Android bounds untrusted remote reasons with `.take(200)` + `maxLines = 2` (MainActivity:773-780, 805-813, audit B-G8-samples-android-07: a peer can ship a reason bounded only by the 8 MiB frame limit); desktop-ui's `FileTransferRowView` renders `state.label()` with unbounded `reason`/`error.message` and no `maxLines`.
- Evidence (ui/Main.kt:1641-1643):
  ```kotlin
  is FileTransferState.Rejected -> "rejected" + (reason?.let { " — $it" } ?: "")
  is FileTransferState.Cancelled -> "cancelled" + (reason?.let { " — $it" } ?: "")
  ```
- Runtime impact: a multi-megabyte reject reason from a non-conforming peer produces a massive single-line `Text` layout in the transfer row — UI jank/possible freeze of the harness window. | Platforms: JVM desktop | User-visible: yes
- Failure class: resource-limit (UI-level, harness)
- Proposed fix: `.take(200)` in `label()` and `maxLines`/`overflow` on the row's state `Text`, mirroring the Android sample.
- Required tests: none automated; manual with an oversized reject reason via a patched peer.

### SMP-8 — KmpConsumerLoopbackTest: receiver subscribes to `session.incoming` only after the session is emitted — scheduling race can drop the greeting (latent flake)
- Severity: Low | Confidence: Uncertain (mechanism confirmed by SharedFlow semantics — `P2pSession.kt:24-27`: replay=0, "messages emitted before any subscriber attaches are not buffered"; frequency unproven. Settling evidence: insert an artificial delay between `incomingSessions.first()` and the inner `first()` — the message should be reliably lost — or add a CI soak count.)
- File(s): sample-kmp-shared/src/jvmTest/kotlin/dev/p2pkit/sample/kmp/KmpConsumerLoopbackTest.kt:100-109; interacts with sample-kmp-shared/src/commonMain/kotlin/dev/p2pkit/sample/kmp/Demo.kt:31-32
- Category: bug (test flakiness)
- Root cause: `runDiscoverAndGreet` sends immediately after `connect()` returns. On the responder, the test's collector must resume from `incomingSessions.first()`, then start collecting `session.incoming` — at least one dispatch hop after the session is emitted — while the in-process loopback read loop can deliver the DATA frame in the same window. With zero subscribers and replay=0, the emitted message is dropped, and `firstMessage.await()` then times out (10 s) → test failure. The `onSubscription` eager-ready trick is applied only to the *outer* `incomingSessions` flow (line 102); the inner `onSubscription { /* eager subscribe */ }` (line 106) does not close the emission→subscription gap.
- Evidence:
  ```kotlin
  responder.incomingSessions
      .onSubscription { incomingReady.complete(Unit) }
      .first()
      .let { session ->
          session.incoming
              .onSubscription { /* eager subscribe */ }   // subscribes AFTER the session exists
              .first()
      }
  ```
- Runtime impact: intermittent 10 s-timeout failure of the KMP consumer gate test under CI load/thread starvation; no product impact. Also documents a real consumer-facing sharp edge of the SDK receive contract (see Out-of-scope). | Platforms: JVM (test) | User-visible: no
- Failure class: none (flaky test)
- Proposed fix (no masking): restructure the responder to subscribe to `session.incoming` from *inside* a `flatMapLatest`-style chain is still post-emission; the robust arrangement is to have the greeter wait to send until the responder signals readiness — e.g. split `runDiscoverAndGreet`'s connect and send steps in the test (connect, await a `CompletableDeferred` completed by the responder after its inner subscription registers via `onSubscription`, then send). Do not widen the 10 s timeout.
- Required tests: this is the test; fix is structural.

## 3. Missing tests

| Invariant untested | Why it matters | Where it should live | Type | Priority |
|---|---|---|---|---|
| Incoming-file destination uniquification (no overwrite on same-named offers) | SMP-1 shipped in desktop-ui because nothing checks it; CLI/Android logic is also test-free | small JVM unit for the shared helper (or per-sample) | unit | P1 |
| `createP2pKit` on Android before `initP2pKitAndroid` fails with the documented error | KMP consumers copy this factory; silent context-null would be a runtime crash pattern | sample-kmp-shared androidHostTest (module currently has none) | unit | P2 |
| Message emitted between incoming-session emission and consumer subscription is (by contract) lost — pin the contract or the fix | SMP-8's root cause; the SDK KDoc warns but nothing pins behavior; any future buffering change should be deliberate | p2p-core commonTest (fakes) | combination | P2 |
| Consumer-path file transfer + `stop()` idempotence through `createP2pKit` | Loopback gate covers text-greeting only; file transfer through the consumer factory is untested | KmpConsumerLoopbackTest sibling case | integration | P3 |
| CLI arg parsing (`reconnect=`, `trace=`, name/appId filtering) | Regression-prone hand parser guarding harness identity (already had one audit fix) | p2p-sample-desktop test source set (none exists) | unit | P3 |

## 4. Section summary

**What this section owns:** the four maintained reference consumers (JVM CLI, Compose Desktop UI, Android Compose app, KMP-shared factory/demo) plus their tests — simultaneously the manual verification path for the RC smoke matrix (no instrumented Android tests exist).

**Overall health: good.** The heavy 2026-06 audit remediation clearly landed here — lifecycle ownership (kit vs run scope vs cleanup scope), session-collector reconciliation, sink ownership, permission flow, and Compose state discipline are all solid, and the Android permission flow around the standalone `AndroidP2pPermissionManager` is a genuinely good reference implementation. The dominant defect pattern is **incomplete propagation of audit fixes across the three sibling samples**: each of uniquify-destination (Android+CLI only), CE-safe runCatching (UI+Android only), terminal-sanitization (CLI only), reason-bounding (Android only), and terminal-transfer-collector cleanup (UI only) exists in some samples but not all. None is individually severe; together they mean the "samples teach the right pattern" guarantee currently depends on *which* sample an adopter reads.

**Top 3 risks:**
1. SMP-1 — desktop-ui silently overwriting received files (data loss in the harness used for file-transfer smoke rows).
2. SMP-8 — latent flake in the only automated KMP-consumer gate, rooted in a real consumer-facing receive-contract sharp edge.
3. The fix-propagation gap itself — future single-sample fixes will keep drifting unless parity is checked as a review gate (the wire-protocol parity rule exists for transports; the samples have no equivalent).

**Map accuracy:** CODEBASE_REVIEW_MAP_2026-07.md §S11 (lines 261-275) is accurate — file inventory, line counts, dependency edges (CLI/UI → provisioning-desktop, Android → provisioning-android, kmp-shared → core+lan only) and "kmp-shared smoke/loopback only; apps manual" test-coverage note all match the tree. No discrepancies found.

## 5. Improvements (not defects)

### SMP-9 — `start()` has no failure guard; a throwing `P2pKit.create` wedges the UI in "Starting…" forever
- Files: ui/Main.kt:289-315 (`_isStarting.value = true` at 289, no try/catch), P2pKitViewModel.kt:270-315 (same shape)
- `AppId` only rejects blank (Identity.kt:15) and both samples pre-trim, so today's realistic throw paths are exotic (builder validation, storage init). Still: wrap create in try/catch, reset `_isStarting`, surface a system message. Cheap insurance in reference code.

### SMP-10 — desktop-ui `pickFile()` shows a modal AWT `FileDialog` from the Compose UI thread
- Files: ui/Main.kt:927-933, call site 1346-1350. Works in practice (AWT modal dialogs pump a nested event loop on the EDT), but the idiomatic Compose Desktop pattern is `AwtWindow`/a dedicated dialog scope; as written, anything scheduled behind the click handler waits for dialog dismissal. Improvement only — no observed hang.

### SMP-11 — Android harness has no keep-alive against cached-app freezing during manual tests
- Files: MainActivity.kt (no `FLAG_KEEP_SCREEN_ON`/foreground affordance), VM KDoc scopes out process death (VM:71-72). On Android 12+ a backgrounded harness gets frozen → keep-alive PINGs stop → remote peers see timeouts mid-smoke-run. A `FLAG_KEEP_SCREEN_ON` toggle or an INTERNAL_TESTING note ("keep the sample foregrounded") would prevent misleading manual results.

### SMP-12 — MainActivity re-derives the OS permission string from device SDK only
- Files: MainActivity.kt:867-871, 1090-1094 vs AndroidP2pPermissionManager.kt:49-58 (keys on device SDK **and** targetSdk). Correct today (targetSdk=36 per libs.versions.toml:11); would silently diverge if targetSdk were ever ≤32. Mapping the *reported* `P2pPermission` to its manifest string would remove the duplicated policy.

### SMP-13 — CLI `printInfo` calls a suspend provisioning API unguarded inside the REPL
- Files: desktop Main.kt:559. If `getManualConnectionInfo()` ever throws, the exception exits `repl()` and skips the `p2p.stop()` teardown at 189-193. Wrap in `runCatching` (CE-safe variant per SMP-3).

### SMP-14 — KmpConsumerLoopbackTest `finally` stops kits without guarding the first `stop()`
- Files: KmpConsumerLoopbackTest.kt:124-127. If `greeter.stop()` throws, `responder.stop()` never runs and the kit leaks until JVM exit (can bleed mDNS state into subsequent suites in the same worker). Wrap each in `runCatching`.

## Out-of-scope observations

- **SDK receive contract (p2p-core):** `P2pSession.incoming`/`incomingFiles` with replay=0 make an *incoming*-session receiver inherently lossy between session emission and subscription (KDoc warns, P2pSession.kt:24-27, but no consumer can fully close the gap — root cause of SMP-8). Worth an explicit SDK-side decision (small replay buffer or documented sender-side grace) — likely already known to the S1/S3 reviewers.
- **README.md:275:** provisioning manifest guidance omits `CHANGE_WIFI_STATE`, which `startLocalOnlyHotspot` requires and the sample manifest correctly declares (AndroidManifest.xml:11) — doc gap.
- **iosApp/ContentView.swift:641:** appId `p2pkit-desktop-sample` — matches all Kotlin samples (recorded here as the parity evidence; file belongs to S12).
