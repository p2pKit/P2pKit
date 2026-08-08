# A10-IOSBUILD — S12 iOS/Xcode build integration review

Status: COMPLETE
Reviewer: A10-IOSBUILD | Branch: audit/exhaustive-review-2026-06 @ 870bf10
Scope: 10 files (iOS sample app, xcodegen/Xcode wiring, provenance scripts, cinterop shim). Static review only; no builds run.

## 1. Per-file verdicts
| File | Lines | Verdict | Tests covering it | Test gaps (1 line) |
|---|---|---|---|---|
| iosApp/ContentView.swift | 1534 | findings: IOSB-11 · improvements: IOSB-12 | none automated; manual smoke matrix A-rows + INTERNAL_TESTING.md §recipes | No automated exercise of the Swift bridge (collectors/sources/sinks) at all |
| iosApp/P2pKitSampleApp.swift | 10 | clean | n/a (trivial @main) | none |
| iosApp/Info.plist | 36 | findings: IOSB-9 | none (config) | No automated check that the built product keeps the two load-bearing network keys |
| iosApp/build.gradle.kts | 27 | improvements: IOSB-10 | none (manual harness task) | No CI exercise of :iosApp:runIosSimulator (macOS-only; acceptable) |
| iosApp/project.yml | 74 | clean | manual (every runIosSimulator regenerates from it) | Load-bearing keys unasserted post-build (see §3 row 1) |
| iosApp/scripts/README.md | 44 | findings: IOSB-6 | n/a (doc) | n/a |
| iosApp/scripts/check-xcframework.sh | 107 | findings: IOSB-4, IOSB-5 | manual recipe docs/STABILIZATION_AND_RELEASE.md:121-157 (matches new behavior) | Unresolvable-stamp path has no recipe step |
| scripts/run-ios-app.sh | 82 | findings: IOSB-1, IOSB-2, IOSB-3 | none (manual harness) | Failure paths themselves are broken — see findings |
| p2p-transport-lan/src/nativeInterop/cinterop/p2pkit_nw.def | 7 | improvements: IOSB-8 | indirect: all iosSimulatorArm64 tests link through it | Wrong-SDK/regression only surfaces via full iOS test run |
| p2p-transport-lan/src/nativeInterop/cinterop/p2pkit_nw.h | 99 | improvements: IOSB-7 | IosRawConnectionTest + IosLanLoopbackTest exercise all 3 helpers over real NWConnections | No leak assertion — a per-send/per-receive leak would pass all functional tests silently |

### Verified invariants and cross-checks (evidence)
- **Load-bearing plist keys:** `NSLocalNetworkUsageDescription` + `NSBonjourServices` present in `iosApp/project.yml:34-36` inside `info.properties` (the xcodegen-surviving location); service string `_p2pkit._tcp` exactly matches `LanConstants.SERVICE_TYPE_BONJOUR` (`p2p-transport-lan/src/commonMain/kotlin/dev/p2pkit/transport/lan/Lan.kt:42`).
- **Info.plist provenance:** `project.yml:22-24` (`info: path: Info.plist`) makes `iosApp/Info.plist` xcodegen-*generated* output; the tracked file is currently key-for-key consistent with the yml properties plus xcodegen's default CFBundle* keys (verified byte-level for the description string and service array). See IOSB-9.
- **Framework linkage:** XCFramework is dynamic (`isStatic = false`, p2p-transport-lan/build.gradle.kts:50) → `embed: true, codeSign: true` (project.yml:59-61) is required and correct. `FRAMEWORK_SEARCH_PATHS` (project.yml:46) targets `build/XCFrameworks/release` — same config the Gradle dependsOn builds (iosApp/build.gradle.kts:13) and the check script validates (check-xcframework.sh:34). Deployment target 15.0 everywhere (options + target + IPHONEOS_DEPLOYMENT_TARGET), above Network.framework's iOS 13 floor.
- **Provenance phase:** declared in `project.yml:62-74` with `basedOnDependencyAnalysis: false` (always runs) and an `sh "$SRCROOT/…"` trampoline (script edits apply without regeneration; no reliance on the exec bit, though both scripts are 755).
- **Stamp contract:** writer (p2p-transport-lan/build.gradle.kts:115-131, S13 scope) emits `<sha>\n` or `unknown`; script's `tr -d '[:space:]'` (:57) and `!= "unknown"` guard (:74) match. All git calls in the new stamp≠HEAD block sit in `if` conditions, so `set -e` semantics are correct as the comment claims; a stamp starting with `-` fails `git cat-file` and fails closed.
- **Exec wrapper:** `:iosApp` included (settings.gradle.kts:33); Exec declares no outputs → never UP-TO-DATE → cannot silently skip; default `isIgnoreExitValue=false` + `set -e`/`set -euo pipefail` in both scripts → failures propagate.
- **Cinterop call sites (all greps of all 3 helper symbols):** only `IosRawConnection.kt:235` (send), `IosRawConnection.kt:288` (receive), `IosLanDataTransport.kt:143` (params, null-checked), `IosRawConnectionTest.kt:38`. Send wraps the call in `bytes.usePinned` and pre-filters empty payloads (`IosRawConnection.kt:210-213`) — satisfies the header's "buffer valid until return" contract (dispatch_data_create with DEFAULT destructor copies synchronously). Receive copies via `readBytes` *inside* the completion (`IosRawConnection.kt:293-294`) — satisfies "valid only for the duration of the completion". `is_complete = false` on send (correct for stream TCP; never half-closes).
- **Swift bridge symbols:** `IosSwiftHelpersKt.peersSnapshot/sessionsSnapshot/stateName` exist as public extensions in `p2p-transport-lan/src/appleMain/.../IosSwiftHelpers.kt` (the Optional-erasure workaround the sample's comments describe); `BuildInfo.shared.describe()` resolves to the generated `public object BuildInfo` (`:p2p-core:generateBuildInfo`, p2p-core/build.gradle.kts:10-66).
- **Sample honors SDK contracts (section dimension):** sink ownership correct — `P2pFileOffer.accept` KDoc (P2pFileOffer.kt:34-37) says caller closes the sink, and the watcher does. Source ownership **violated** — see IOSB-11. No nested collects (poll loops + per-flow collector Tasks); collector Tasks are tracked and cancelled in stop() and on session removal (ContentView.swift:812-816, 1316-1321); `emit` adapters call `completionHandler` exactly once after the MainActor hop, so Kotlin-side backpressure serializes emissions (no reordering). `kit.connect(peer:)` staleness of the retained `row.peer` is harmless: `P2pKitImpl.connect` re-resolves `peerRegistry.internalPeer(peer.id)` (P2pKitImpl.kt:384-393).
- **appId parity across samples (discovery is filtered by appId):** iOS `"p2pkit-desktop-sample"` (ContentView.swift:641) == Android `APP_ID` (P2pKitViewModel.kt:1103) == desktop default — cross-platform samples discover each other.
- **ContentView is a struct** — Task closures capture a value copy; `[weak self]` is not applicable and no retain cycles are possible through `self`; all @State mutations happen on the MainActor (`MainActor.run` / `@MainActor` functions / `Task { @MainActor … }`). The one deliberate strong capture (`session` in collector closures) is bounded by tracked-task cancellation.

## 2. Findings

### IOSB-1 — run-ios-app.sh: UDID-resolution failure path is dead code under `set -e` (script dies silently instead of printing the FATAL hint)
- Severity: Medium | Confidence: Confirmed (bash semantics: the exit status of `VAR="$(pipeline)"` is the pipeline's; `set -e` aborts on it)
- File(s): scripts/run-ios-app.sh:58-67
- Category: bug
- Root cause: when no simulator matches, both `grep`s in the pipeline exit 1; with `set -euo pipefail` (line 19) the assignment fails and the script exits *at line 58*, so the guard that prints the actionable message can never run.
- Evidence:
  ```bash
  set -euo pipefail            # line 19
  UDID="$(xcrun simctl list devices available \
      | grep -E "^[[:space:]]+${SIM_NAME} \(" \
      | head -1 | grep -oE '[0-9A-F-]{36}' | head -1)"   # grep exit 1 → set -e aborts here
  if [[ -z "${UDID}" ]]; then                            # line 63 — unreachable in exactly the case it exists for
      echo "[ios-run] FATAL: no available simulator named '${SIM_NAME}'. Run:"
  ```
  Contrast line 47: `APP_PATH="$(find …)"` is fine — `find` exits 0 on no match, so that `-z` guard is reachable.
- Runtime impact: missing/renamed simulator (older Xcode without an "iPhone 17" runtime, SIM_NAME typo) → abort after "Resolving simulator UDID…" with no error text. Exit code is still non-zero (Gradle fails correctly); only the diagnostic is lost. | Platforms: macOS dev host | User-visible: yes (developer)
- Failure class: build failure (missing diagnostics)
- Proposed fix (do NOT implement): tolerate the empty result in the assignment (`… || true` inside the substitution, or `|| UDID=""`) and keep the explicit `-z` check as the single failure gate.
- Required tests: manual: `SIM_NAME=nonexistent bash scripts/run-ios-app.sh` must print the FATAL hint and exit 1.

### IOSB-2 — run-ios-app.sh: SIM_NAME is interpolated into an ERE unescaped — every parenthesized simulator name fails UDID resolution
- Severity: Medium | Confidence: Confirmed (regex mechanics; stock device names contain parens)
- File(s): scripts/run-ios-app.sh:59 (override documented at :14 and in CLAUDE.md)
- Category: bug
- Root cause: `grep -E "^[[:space:]]+${SIM_NAME} \("` treats the value as regex. "iPhone SE (3rd generation)" / "iPad (10th generation)" become ERE *groups* matching "iPhone SE 3rd generation (", which never matches the literal `simctl list` line.
- Evidence:
  ```bash
  | grep -E "^[[:space:]]+${SIM_NAME} \("     # line 59 — unescaped interpolation into the pattern
  ```
  xcodebuild's `-destination name=…` (line 39) is exact-string, so the *build succeeds* for these devices; the run then dies at UDID resolution — and via IOSB-1, with no message at all.
- Runtime impact: `SIM_NAME="iPhone SE (3rd generation)" ./gradlew :iosApp:runIosSimulator` burns a full build, then aborts silently. Default "iPhone 17" unaffected. | Platforms: macOS dev host | User-visible: yes
- Failure class: build failure
- Proposed fix (do NOT implement): stop regex-matching a display name — select by exact name from `xcrun simctl list devices available --json` (plutil/python3), or `grep -F` on a normalized line.
- Required tests: manual: run with a parenthesized SIM_NAME installed on the host; must resolve a UDID and launch.

### IOSB-3 — run-ios-app.sh: installs the first `p2pkit-sample.app` found anywhere in global DerivedData — can silently install a stale bundle from another checkout/worktree
- Severity: High | Confidence: Confirmed mechanism (`find -print -quit` returns the first hit in arbitrary directory order, not the newest); the ≥2-DerivedData precondition is realistic here (git worktrees under `.claude/worktrees/`, any second checkout, or a moved/renamed repo dir each mint a distinct `p2pkit-sample-<pathhash>` DerivedData directory that persists indefinitely)
- File(s): scripts/run-ios-app.sh:47-50; root cause enabled by the xcodebuild invocation at :35-40 lacking `-derivedDataPath`
- Category: bug
- Root cause: the build's output location is never pinned or queried; the script then searches *all* of `~/Library/Developer/Xcode/DerivedData`:
- Evidence:
  ```bash
  APP_PATH="$(find "$DERIVED_DATA_BASE" \
      -name 'p2pkit-sample.app' \
      -path '*Debug-iphonesimulator*' \
      -print -quit)"
  ```
- Runtime impact: with two or more matching DerivedData trees, the app xcodebuild just produced and the app simctl installs can differ — the simulator runs a *stale sample with a stale embedded P2pKitShared*, silently defeating the V0.4-PROVENANCE gate that the same build just enforced (the gate validates what xcodebuild links, not what this script installs). Classic symptom: a fix that "doesn't reproduce" on the simulator. | Platforms: macOS dev host | User-visible: yes
- Failure class: none directly (stale-artifact execution — the exact class the provenance guard exists to prevent)
- Proposed fix (do NOT implement): pass `-derivedDataPath "$PROJECT_DIR/build/DerivedData"` (already git-ignored via `iosApp/build/`) and derive `APP_PATH` deterministically beneath it; or parse `xcodebuild -showBuildSettings` for `TARGET_BUILD_DIR`/`CODESIGNING_FOLDER_PATH`.
- Required tests: manual: build from a worktree and from the main checkout, then `xcrun simctl get_app_container <udid> dev.p2pkit.sample` must resolve under the invoking checkout's DerivedData.

### IOSB-4 — check-xcframework.sh: residual hard-fail message repeats the audit #10 trap — the suggested fix is a no-op exactly when the failure state persists
- Severity: Low | Confidence: Confirmed (message text vs the UP-TO-DATE semantics documented in the same file and in p2p-transport-lan/build.gradle.kts:84-103)
- File(s): iosApp/scripts/check-xcframework.sh:83-89 (new adca586 code)
- Category: bug (misleading diagnostics)
- Root cause: the unresolvable-stamp branch (empty stamp, literal "unknown", commit absent locally — shallow clone or GC'd rewritten history) hard-fails with `Fix: sh ./gradlew :p2p-transport-lan:assembleP2pKitSharedReleaseXCFramework`. But the script *already ran that task* at lines 31-32 seconds earlier; the stale stamp survived precisely because the task was UP-TO-DATE, so re-running it changes nothing and the build stays bricked until the user knows to force re-execution. The original audit #10 called out this exact "suggested fix is a no-op" pattern (acknowledged in this script's own comment at lines 66-70).
- Evidence:
  ```sh
  echo "error: XCFramework identity mismatch — refusing to build against stale code:"
  …
  echo "  Fix: sh ./gradlew :p2p-transport-lan:assembleP2pKitSharedReleaseXCFramework"
  exit 1
  ```
- Runtime impact: shallow-clone / rewritten-history developers loop on a self-defeating instruction. Fail-closed behavior itself is correct (can't prove freshness → refuse). | Platforms: macOS dev host | User-visible: yes
- Failure class: build failure (self-defeating guidance)
- Proposed fix (do NOT implement): extend the message with the forcing variant (`--rerun-tasks`, or delete `p2p-transport-lan/build/XCFrameworks`) and distinguish "stamp commit not found locally (shallow clone?)" from "framework sources changed since stamp" — the operator response differs.
- Required tests: add the unresolvable-stamp case (`echo unknown > BUILD_COMMIT.txt`) to the docs/STABILIZATION_AND_RELEASE.md §provenance manual recipe.

### IOSB-5 — check-xcframework.sh: freshness pathspec omits build-config inputs that also shape the XCFramework (gradle.properties, root build.gradle.kts, settings.gradle.kts, wrapper)
- Severity: Low | Confidence: Confirmed omission; residual reachability is narrow (requires the Gradle layer-1 up-to-date check to also miss the change)
- File(s): iosApp/scripts/check-xcframework.sh:76-79; sync-contract comment p2p-transport-lan/build.gradle.kts:100-103 ("Keep the script's path list in sync with what actually feeds this framework")
- Category: bug (defensive gap in new adca586 code)
- Root cause: on stamp≠HEAD the gate passes iff the watched pathspec is diff-clean between stamp and HEAD. The set covers both modules' `src/` (including the cinterop `.def`/`.h`, which live under `src/nativeInterop/`), both module build scripts, and the version catalog — but not `gradle.properties` (today: `kotlin.mpp.enableCInteropCommonization=true`; any future `kotlin.native.binary.*` codegen flag; `VERSION_NAME`), the root `build.gradle.kts` (allprojects config that could gain compiler options), `settings.gradle.kts` (repositories/substitutions), or `gradle/wrapper/`.
- Evidence:
  ```sh
  if git diff --quiet "$XCF_COMMIT" HEAD -- \
      p2p-transport-lan/src p2p-core/src \
      p2p-transport-lan/build.gradle.kts p2p-core/build.gradle.kts \
      gradle/libs.versions.toml; then
  ```
- Runtime impact: mitigated in the common case by layer 1 — a change that alters tracked task inputs makes the assemble non-UP-TO-DATE, which re-stamps to HEAD before this comparison ever runs. Exposure is therefore limited to changes Gradle does not model as inputs of the cinterop/link/assemble chain — rare, but exactly the blind spot this second layer exists to cover; a silent pass here is invisible. | Platforms: macOS dev host | User-visible: no
- Failure class: none (weakened guard)
- Proposed fix (do NOT implement): append `gradle.properties build.gradle.kts settings.gradle.kts gradle/wrapper` to the pathspec (worst case a spurious hard-fail costs one forced rebuild — cheap relative to a silent stale pass) and update the build.gradle.kts:100 comment + docs/STABILIZATION_AND_RELEASE.md:127-129 list in the same change.
- Required tests: manual: commit touching only `gradle.properties` after an assemble; verify and document the intended gate outcome in the §provenance recipe.

### IOSB-6 — iosApp/scripts/README.md is stale twice over: obsolete manual Run-Script setup (following it double-wires the phase) and a pre-adca586 behavior description
- Severity: Low | Confidence: Confirmed (doc text vs project.yml:62-74 and check-xcframework.sh:60-90)
- File(s): iosApp/scripts/README.md:10-32 (setup), 34-44 (behavior); contradicted by iosApp/project.yml:62-74
- Category: bug (stale/contradictory instructions — brief §build/script/doc dimension)
- Root cause: (a) the "One-time setup (per-developer)" section instructs each developer to hand-add the Run Script phase to their git-ignored xcodeproj — but since the AUDIT-2026-06 fix (A-G9-samples-desktop-ios-11) `project.yml` declares the phase via `preBuildScripts` and xcodegen recreates it on every generation. A developer following the README ends up with a *duplicate* phase (the script, including its embedded `./gradlew` run, executes twice per build) and is taught precisely the hand-edit-the-generated-project antipattern the yml comment warns against. (b) "What the script does" still says "Fails the build if they differ … refusing to compile against stale framework code" — stale since adca586 (REMEDIATION #10): stamp≠HEAD now passes when no framework-relevant path changed.
- Evidence:
  ```markdown
  The Xcode project (`iosApp/p2pkit-sample.xcodeproj/`) is git-ignored, so
  each developer must wire this script as a Run Script build phase in
  their own copy of the project.
  ```
  vs project.yml:72-74:
  ```yaml
  - name: "Check P2pKitShared XCFramework provenance"
    script: sh "$SRCROOT/scripts/check-xcframework.sh"
    basedOnDependencyAnalysis: false
  ```
- Runtime impact: duplicated pre-build phase (two nested Gradle invocations per Xcode build) plus a doc a future agent cannot follow safely. | Platforms: macOS dev host | User-visible: yes (doc reader)
- Failure class: none
- Proposed fix (do NOT implement): rewrite: the phase is generated from project.yml — do NOT add it manually; describe the stamp-lag acceptance rule; link the docs/STABILIZATION_AND_RELEASE.md §provenance recipe; keep the "Based on dependency analysis" rationale as explanation of `basedOnDependencyAnalysis: false`.
- Required tests: n/a (doc).

### IOSB-9 — iosApp/Info.plist is generated xcodegen output tracked in git with no generated-file marker — direct edits are silently reverted
- Severity: Low | Confidence: Confirmed (project.yml:22-24 `info.path: Info.plist`; xcodegen rewrites that file on every `generate`, which runs on every runIosSimulator via scripts/run-ios-app.sh:31 and via :iosApp:regenerateXcodeProject)
- File(s): iosApp/Info.plist (whole file); iosApp/project.yml:22-24
- Category: bug (defensive gap / latent config-loss trap; content currently in sync, so no live defect)
- Root cause: the tracked plist looks like an editable source. Any key added or edited there (a new usage-description, ATS exception, orientation) is silently overwritten at the next regeneration — the same "silently dropped config" class as the documented NSBonjourServices invariant, but for *all other* keys, and the warning lives only in project.yml, which someone editing Info.plist is by definition not reading. XML comments cannot survive regeneration, so the file itself cannot carry the warning.
- Evidence: `project.yml:22-24` (`info: path: Info.plist / properties: …`); regeneration call sites scripts/run-ios-app.sh:31 and iosApp/build.gradle.kts:22-27.
- Runtime impact: a plist-only edit works until the next regen, then vanishes → intermittent, hard-to-diagnose config loss (the historically observed failure shape for this project's iOS discovery keys). | Platforms: iOS sample | User-visible: no (dev-facing)
- Failure class: none
- Proposed fix (do NOT implement): state in iosApp/scripts/README.md (or a short iosApp README) that Info.plist is generated from project.yml `info.properties` and must never be edited directly; optionally add a post-build grep asserting the two load-bearing keys exist in the *built product's* Info.plist (also closes §3 row 1).
- Required tests: §3 row 1.

### IOSB-11 — ContentView closes the `sendFile` source on the terminal path, violating the locked KDoc contract ("callers must not close it themselves"), and its comment documents the wrong ownership
- Severity: Low | Confidence: Confirmed (KDoc + kit-side close both verified)
- File(s): iosApp/ContentView.swift:995-997 (`watchTransfer(transfer, direction: .send, detail: nil) { source.close() }`), 1006-1008 (comment), contract at p2p-core/src/commonMain/kotlin/dev/p2pkit/core/P2pSession.kt:75-77, kit-side close at p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/FileTransferDispatcher.kt:137-143
- Category: bug (sample contradicts the spec-locked API contract; zero runtime harm with the in-tree source implementation)
- Root cause: `P2pSession.sendFile` KDoc: "The kit takes ownership of [source] and closes it automatically once the returned transfer reaches a terminal state — **callers must not close it themselves**" (this is the exact sentence REMEDIATION #21 used to close the ownership finding as a false positive). The dispatcher does close it (`runCatching { source.close() }` under a "Own the source's lifetime" comment). The sample's transfer watcher *also* closes the source at terminal state, and its doc comment asserts the opposite contract:
- Evidence:
  ```swift
  /// Track one transfer's StateFlows into a UI row until it reaches a
  /// terminal state, then run `onTerminal` (the SDK leaves closing the
  /// sink/source to the caller).                     // ContentView.swift:1006-1008
  …
  watchTransfer(transfer, direction: .send, detail: nil) {
      source.close()                                  // ContentView.swift:995-997
  }
  ```
  That parenthetical is true only for the **sink** (P2pFileOffer.kt:34-37: "the sink has been flushed but not closed — the caller is responsible for closing it"); the receive-side `sink.close()` at :957-959 is correct.
- Runtime impact: none in-tree — `DataRawSource.close()` is a no-op and the kit's close is `runCatching`-wrapped. But this is the maintained reference consumer of the iOS framework: it teaches double-close, and a copied pattern with a file-backed source races the kit's dispatcher-side close against the watcher's close. Note the error path at :999 (`source.close()` after `sendFile` **threw**) is correct and should stay — ownership only transfers when sendFile returns a transfer. | Platforms: iOS sample | User-visible: no
- Failure class: none
- Proposed fix (do NOT implement): drop `source.close()` from the send-side `onTerminal` (pass `{}` or make onTerminal optional), keep the catch-path close, and fix the :1007 comment to state the asymmetric ownership (kit closes the source; caller closes the sink).
- Required tests: none needed for the sample itself; the SDK-side ownership already has file-transfer tests (REMEDIATION #21).

## 2b. Improvements (Category: improvement — not defects)

### IOSB-7 — p2pkit_nw.h: make ownership explicit — annotate the create helper `NW_RETURNS_RETAINED` and fail compilation if the stubs are ever built without ARC
- Severity: Improvement | Confidence: current code Confirmed correct under ARC
- File(s): p2p-transport-lan/src/nativeInterop/cinterop/p2pkit_nw.h:25-30 (create), 46-55 (send), 67-97 (receive)
- Memory-ownership analysis (scope-mandated):
  - `p2pkit_nw_create_plain_tcp_parameters` returns the +1 result of `nw_parameters_create_secure_tcp` (SDK-annotated `NW_RETURNS_RETAINED`) from a helper carrying *no* retained-return annotation. Compiled as ARC ObjC (the `.def` sets `language = Objective-C`; the header's own AUDIT-2026-06 comment at :82-88 reasons in ARC terms, and REMEDIATION 20c's K/N-manages-OS-objects evidence corroborates), ARC balances this through the autorelease-return handshake and Kotlin/Native then owns the boxed reference — no leak, no over-release. The correctness is *implicit*, though: under MRC the same code hands a +1 object to a caller assuming +0.
  - `p2pkit_nw_connection_send_default`: `dispatch_data_create(buffer, size, NULL, NULL)` with the DEFAULT destructor copies the bytes synchronously (doc comment correct), so the Kotlin call site's `usePinned` scope suffices; the +1 `data` is released by ARC at scope end after `nw_connection_send` takes what it needs. Under MRC this would leak the entire payload copy on every send.
  - `p2pkit_nw_connection_receive_default`: the +1 `dispatch_data_create_map` result is pinned via `__attribute__((objc_precise_lifetime))` for the completion's duration — the AUDIT-2026-06 use-after-free fix, correct and well-commented; NULL/empty content falls through to `completion(NULL, 0, …)` with `buffer_size` initialized. Under MRC this would leak every mapped receive buffer.
  - All Kotlin call sites honor the documented buffer-lifetime contracts (see §1 cross-checks); no other consumers exist.
- Suggestion: add `NW_RETURNS_RETAINED` (or `__attribute__((ns_returns_retained))`) to the create helper, plus a guard such as `#if defined(__OBJC__) && !__has_feature(objc_arc)` / `#error "p2pkit_nw.h requires ARC"` — converting a hypothetical toolchain/def regression from three silent runtime leaks (one payload-sized per send) into a compile error. Zero behavior change today.

### IOSB-8 — p2pkit_nw.def: `-framework Network` in compilerOpts is link-only; the `-I` is cwd-relative
- Severity: Improvement | Confidence: Confirmed content; build demonstrably works today (REMEDIATION gate: all iOS targets assemble/link/test PASS)
- File(s): p2p-transport-lan/src/nativeInterop/cinterop/p2pkit_nw.def:6-7; Gradle wiring p2p-transport-lan/build.gradle.kts:36-38 (sets only `defFile`, no `includeDirs`)
- Analysis: `compilerOpts = -I./src/nativeInterop/cinterop -framework Network` — (a) `-framework` does nothing at compile time (`<Network/Network.h>` resolves through the per-target SDK's default framework search paths, which Kotlin/Native selects — nothing here can pin a wrong SDK); the load-bearing copy is in `linkerOpts`. (b) the relative `-I` is what lets `headers = p2pkit_nw.h` resolve, and it depends on the cinterop tool's working directory being the subproject dir — true under current KGP, but convention rather than contract; a KGP layout change would surface as a confusing "header not found".
- Suggestion: drop `-framework Network` from compilerOpts and replace the relative `-I` with `includeDirs(project.file("src/nativeInterop/cinterop"))` in the `cinterops.create("p2pkit_nw")` block (absolute at configuration time). `package`/`language`/`headerFilter` are correct as-is.

### IOSB-10 — iosApp/build.gradle.kts: undocumented environment assumptions; nested Gradle-in-Gradle chain deserves a comment
- Severity: Improvement | Confidence: Confirmed structure
- File(s): iosApp/build.gradle.kts:9-27; chain: scripts/run-ios-app.sh:31 → xcodebuild → project.yml pre-build phase → iosApp/scripts/check-xcframework.sh:31 (`sh ./gradlew …`)
- Analysis: `runIosSimulator` launches a build that, mid-Exec, launches another Gradle build of the same project (the provenance phase). It works — the outer dependsOn already produced the framework, so the inner run is UP-TO-DATE and cache-lock contention is brief — but it is the kind of chain that fails obscurely: a GUI-launched Xcode build gets a minimal PATH/JAVA_HOME (gradlew then needs a system-resolvable JDK), and `regenerateXcodeProject` needs `xcodegen` on the *daemon's* PATH (Exec surfaces a bare "Cannot run program \"xcodegen\""). Error propagation is otherwise correct and the task can never skip while stale (no declared outputs; dependsOn targets exactly the release config the app links).
- Suggestion: a short comment block listing prerequisites (xcodegen, Xcode CLT, JDK reachable from non-shell environments) and the intentional nested-Gradle design; optionally a `doFirst` existence probe for `xcodegen` with an actionable message.

### IOSB-12 — FileHandleRawSink swallows disk-write failures: a truncated file still reports "Completed" in the transfer row
- Severity: Improvement (deliberate, code-documented sample-grade tradeoff — reported here so it is a decision, not an accident) | Confidence: Confirmed
- File(s): iosApp/ContentView.swift:1489-1523 (`failed` flag, :1495 comment), watcher at :1032-1058
- Analysis: `RawSink.write` genuinely cannot throw across the bridge (kotlinx-io carries no `@Throws`), so the sink logs the failure and no-ops subsequent writes — but `failed` is private and never read outside `write`, so the SDK streams to completion, the state machine reaches `Completed`, and the UI shows a success row + saved path for a corrupt/truncated file. The only trace is one `[file] sink write FAILED` diagnostic line. In a harness used for the hardware smoke matrix, that combination can contribute to a false manual PASS unless the operator hash-verifies (the INTERNAL_TESTING recipes do — which is the current mitigation).
- Suggestion: surface the failure — e.g. expose `failed` and have `watchTransfer` poll it alongside the state, cancelling via `transfer.cancel(reason: "sink write failed")` so the row terminates as Cancelled/Failed instead of Completed. Also worth noting `describeTransferState`'s `default: ("…", false)` (ContentView.swift:1079-1080) polls forever if a future SDK adds an unmapped terminal state — all 7 current `FileTransferState` variants (FileTransferState.kt:17-39) are matched today.

## 3. Missing tests
| Invariant untested | Why it matters | Where it should live | Type | Priority |
|---|---|---|---|---|
| Built product's Info.plist contains `NSBonjourServices` `_p2pkit._tcp` + `NSLocalNetworkUsageDescription` | The documented "zero discovery" failure mode; today only a yml comment guards it — a bad xcodegen upgrade or refactor drops it silently | Post-build grep in check-xcframework.sh or scripts/run-ios-app.sh against the .app's Info.plist | manual/script | P1 |
| run-ios-app.sh installs the bundle produced by *this* build (not first-found in global DerivedData) | IOSB-3 — silent stale-app runs defeat the provenance gate | Manual `simctl get_app_container` verification after the fix; note in INTERNAL_TESTING.md | manual | P1 |
| check-xcframework.sh stamp-lag matrix incl. unresolvable stamp (`unknown`/shallow clone) | New adca586 logic; the existing recipe (docs/STABILIZATION_AND_RELEASE.md:131-157) covers only pass/pass/fail cases | Extend §provenance manual recipe | manual | P2 |
| SIM_NAME override with a parenthesized device name resolves and launches | IOSB-1/2 — the documented override is broken for a large class of stock devices and fails without diagnostics | Manual run matrix note in iosApp/scripts/README.md | manual | P2 |
| Cinterop helpers leak-free under sustained send/receive | A per-send/per-receive leak (IOSB-7's MRC scenario, or an ARC regression) passes every functional test silently | Instruments (Leaks) step in the smoke matrix, or an iosSimulatorArm64 test asserting stable memory across N transfers | manual | P3 |

## 4. Section summary
**What this section owns:** the maintained iOS sample (SwiftUI consumer of the exported XCFramework), the xcodegen/Xcode integration (project.yml as the single survivable source of Info.plist keys and the pre-build provenance phase), the run/provenance shell scripts, the `:iosApp` Exec wrapper, and the cinterop shim that keeps Kotlin/Native away from unboxable ObjC block macros.

**Overall health: good.** The AUDIT-2026-06 fixes hold up well under re-review: the provenance phase now survives regeneration, the collector-task tracking in ContentView is complete (attach/dedup/cancel on removal and stop), the log-replay epoch probe is correct, the cinterop shim's `objc_precise_lifetime` fix is the sanctioned pattern, and both plist network keys are in the yml and byte-consistent with the SDK's service type. The new adca586 stamp-lag logic is sound in its core (fail-closed on anything unprovable, `set -e`-correct, quoting safe) with two small gaps (IOSB-4/5). The weakest file is `scripts/run-ios-app.sh` (all three of the section's Medium/High findings), which predates the audit work and never got the same scrub.

**Top 3 risks:** (1) IOSB-3 — stale-app installs via the global DerivedData search silently defeat the provenance system this section otherwise builds carefully; (2) IOSB-1/2 — the run script's failure paths are broken exactly where the hardware smoke matrix will lean on them (device-name overrides, missing runtimes), wasting bench time with silent aborts; (3) doc drift (IOSB-6/9) — the scripts README teaches obsolete double-wiring and the tracked Info.plist invites edits that regeneration silently reverts.

**CODEBASE_REVIEW_MAP_2026-07.md accuracy:** the S12 entry is accurate — file list, dependency edges (transport-lan XCFramework task; xcodegen/xcodebuild/simctl), and both risk callouts (regenerated-project key-drop trap; #10 stamp logic is new) match what was found. One nuance, not an error: it lists Info.plist among "app sources", whereas it is xcodegen-generated output of project.yml (the substance of IOSB-9).

## Out-of-scope observations
- p2p-transport-lan/build.gradle.kts:100-103 (S13): the "keep the script's path list in sync" comment enumerates the same incomplete path set as IOSB-5; if IOSB-5 is accepted, that comment and docs/STABILIZATION_AND_RELEASE.md:127-129 need the same update.
- p2p-transport-lan/src/appleMain/.../IosSwiftHelpers.kt:24-26 (S5/S7 doc): the KDoc's Swift example shows member-style calls (`kit.peersSnapshot() as? [Peer] ?? []`) — Kotlin extension functions surface in Swift as static `IosSwiftHelpersKt.peersSnapshot(kit)` (what ContentView correctly uses), and the `as?` cast contradicts the preceding "without any cast gymnastics" sentence.
- ContentView.swift:635-639 documents that `P2pKitCompanion.create` is not `@Throws`, so a synchronous transport-init failure would crash the process; the comment says this SDK-side gap is "tracked separately" — orchestrator should confirm it is actually in the catalogue (I could not verify from my scope).
