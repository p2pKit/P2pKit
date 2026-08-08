# A11-BUILD — S13 build, Gradle, publishing & release review

Branch `audit/exhaustive-review-2026-06`, HEAD `870bf10`. Static review only (no gradle executed). All 26 assigned files opened and read; wrapper jar verified by presence/type only per instructions.

## 1. Per-file verdicts

| File | Lines | Verdict | Tests covering it | Test gaps (1 line) |
|---|---|---|---|---|
| build.gradle.kts (root) | 62 | clean | Exercised by REMEDIATION gate builds (publishToMavenLocal dry-run per docs Part B) | No automated check that Sign tasks skip keyless / run+attach .asc with a key |
| settings.gradle.kts | 33 | improvements: BLD-5, BLD-10 | Implicit in every gate build | No fresh-machine bootstrap check (JDK-17 provisioning) |
| gradle.properties | 16 | clean | Implicit in every gate build | org.gradle.caching=true benefit is silently defeated by BLD-1 — no build-avoidance regression check |
| gradle/gradle-daemon-jvm.properties | 12 | clean | Implicit (daemon boot) | none needed |
| gradle/libs.versions.toml | 41 | clean (all 13 libraries + 7 plugins + 3 SDK versions used; no unused aliases) | Implicit in every gate build | none needed |
| gradle/wrapper/gradle-wrapper.jar | binary | clean (present, valid zip, 45,457 B, dated May 17 with properties — consistent pair) | Implicit (every ./gradlew run) | none needed |
| gradle/wrapper/gradle-wrapper.properties | 7 | improvements: BLD-6 | Implicit | none needed |
| gradlew | 248 | clean (stock Gradle 9 POSIX template incl. SPDX header, CDPATH fix, `command -v` checks — no local edits) | Implicit | none needed |
| gradlew.bat | 93 | clean (stock template incl. JAVA_HOME quote-strip, stderr redirects — no local edits) | none (no Windows CI) | none needed |
| .editorconfig | 20 | improvements: BLD-10 | none | none needed |
| .gitignore | 34 | findings: BLD-3; improvements: BLD-10 | none | none needed |
| .run/Build iOS Framework (Device).run.xml | 30 | clean (`:p2p-transport-lan:linkReleaseFrameworkIosArm64` exists — framework binary declared per iOS target, both build types) | none | none needed |
| .run/Build iOS Framework (Simulator).run.xml | 30 | clean (`linkDebugFrameworkIosSimulatorArm64` exists) | none | none needed |
| .run/Compose Desktop UI.run.xml | 30 | clean (`:p2p-sample-desktop-ui:run` provided by jetbrains-compose desktop.application) | none | none needed |
| .run/JVM CLI Alice.run.xml | 30 | clean (`:p2p-sample-desktop:run` + `--args="Alice"`; stdin forwarding wired in module build) | none | none needed |
| .run/JVM CLI Bob.run.xml | 30 | clean (same as Alice) | none | none needed |
| .run/iOS Sample (Simulator).run.xml | 30 | clean (`:iosApp:runIosSimulator` registered at iosApp/build.gradle.kts:9; no SIM_NAME env set → script default "iPhone 17" per scripts/run-ios-app.sh:14,21 — consistent with CLAUDE.md "SIM_NAME=… overrides") | none | none needed |
| .run/iOS Simulator Tests.run.xml | 30 | clean (`:p2p-transport-lan:iosSimulatorArm64Test` is a standard KMP task; RunAsTest=true correctly set only here) | REMEDIATION gate (29 tests) | none needed |
| p2p-core/build.gradle.kts | 143 | findings: BLD-1, BLD-2; improvements: BLD-4, BLD-7 | Gate builds (`:p2p-core:assemble`, `allTests`) | No regression check that a no-change rebuild leaves BuildInfo.kt untouched (BLD-1) |
| p2p-transport-lan/build.gradle.kts | 164 | findings: BLD-2; improvements: BLD-4, BLD-7, BLD-9 | Gate builds incl. XCFramework assembly; stamp has a manual recipe in docs (not unit-testable) | Stamp semantics (up-to-date skip / failure skip / per-config XOR) only manually verified |
| p2p-network-provisioning-android/build.gradle.kts | 62 | findings: BLD-2; improvements: BLD-7 | `testAndroidHostTest` gate (task name matches `withHostTest{}` wiring) | Publish-artifact completeness never asserted |
| p2p-network-provisioning-desktop/build.gradle.kts | 63 | improvements: BLD-10 | `:p2p-network-provisioning-desktop:test` gate | none beyond publish-set check |
| p2p-sample-android/build.gradle.kts | 48 | improvements: BLD-10 | `assembleDebug` documented; no instrumented tests (known) | none needed (sample) |
| p2p-sample-desktop/build.gradle.kts | 30 | improvements: BLD-8 | installDist/run used in manual recipes | none needed (sample) |
| p2p-sample-desktop-ui/build.gradle.kts | 41 | clean (mainClass `dev.p2pkit.sample.desktop.ui.MainKt` verified against src/main/kotlin/dev/p2pkit/sample/desktop/ui/Main.kt; packageVersion 1.0.0 comment correct — jpackage requires MAJOR>0; description derives from project.version) | manual UI runs | none needed (sample) |
| sample-kmp-shared/build.gradle.kts | 27 | clean (jvm+android only — the no-iOS framing issue is catalogued/closed in PROBLEMS; consumed by its own jvmTest per INTERNAL_TESTING.md:36-45) | `:sample-kmp-shared:jvmTest` | none needed (sample) |

Publishing scope verified by grep: `maven-publish` appears in exactly the four library modules plus the root wiring — no sample module publishes (root build.gradle.kts:41; p2p-core:7; p2p-transport-lan:6; p2p-network-provisioning-android:4; p2p-network-provisioning-desktop:3). The XCFramework export pair is present on both sides: `export(project(":p2p-core"))` (p2p-transport-lan/build.gradle.kts:51) and `api(project(":p2p-core"))` (:64). cinterop def and header both exist at p2p-transport-lan/src/nativeInterop/cinterop/ (p2pkit_nw.def + p2pkit_nw.h). iOS target triple (iosX64/iosArm64/iosSimulatorArm64) identical between core (:91-93) and transport-lan (:29). jvmToolchain(17) set in all 7 Kotlin modules; sample-android uses compileOptions 17 (AGP 9 built-in Kotlin) — consistent. minSdk 24 flows from the catalog everywhere it is used.

## 2. Findings

### BLD-1 — BuildInfo BUILD_TIME defeats its own "only write when changed" guard: every build rewrites the file, invalidating incremental compile, build cache, and reproducibility
- Severity: Medium | Confidence: Confirmed (static logic; deterministic)
- File(s): p2p-core/build.gradle.kts:15-19, 42, 62-63, 71-75; interacts with gradle.properties:13 (`org.gradle.caching=true`)
- Category: bug (code contradicts its stated and comment-documented behavior)
- Root cause: `newContent` embeds `val buildTime = Instant.now().toString()` (line 42 → line 63 `BUILD_TIME`). Two invocations always produce different content, so the guard at lines 72-75 (`if (oldContent != newContent) outFile.writeText(...)`) always fires. The comment (lines 16-19) claims "only rewrites BuildInfo.kt when the content actually differs … downstream recompilation only happens when the commit / dirty flag / branch changes" — false as long as BUILD_TIME is in the content.
- Evidence:
  ```kotlin
  // Up-to-date semantics: … only rewrites BuildInfo.kt when the content actually
  // differs. That preserves Kotlin compile's incremental cache — downstream
  // recompilation only happens when the commit / dirty flag / branch changes.
  ...
  val buildTime = Instant.now().toString()
  ...
  appendLine("    public const val BUILD_TIME: String = \"$buildTime\"")
  ...
  val oldContent = if (outFile.exists()) outFile.readText() else ""
  if (oldContent != newContent) { outFile.writeText(newContent) }
  ```
  BuildInfo.kt is wired into commonMain (`kotlin.srcDir(generateBuildInfo)`, line 97) and consumed at p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt:128, so every target's compile (JVM/Android/all iOS + metadata) sees a changed source on every build; with `org.gradle.caching=true` those compile tasks also miss the build cache every time. Two builds of the same commit produce different binaries (non-reproducible), which matters once artifacts are signed for release.
- Runtime impact: none at app runtime; build-time cost on every compile across the whole repo (everything depends on :p2p-core), plus non-reproducible RC artifacts. | Platforms: all | User-visible: no
- Failure class: none (build efficiency/reproducibility)
- Proposed fix (do NOT implement): drop BUILD_TIME from the generated constants, or derive it from the commit (`git show -s --format=%cI HEAD`) so content is stable per commit/dirty-state; keep `upToDateWhen { false }` so git state is still re-checked each run.
- Required tests: a scripted check (or TestKit test) that a second build with unchanged git state leaves BuildInfo.kt byte-identical and `compileKotlinJvm` UP-TO-DATE.
- Note: [CATALOGUED] — this is PROBLEMS_P2PKIT.md:356-361 `buildinfo-not-reproducible`, marked 🟡 (open), and it is NOT among the 21 remediated findings in REMEDIATION_2026-07.md nor mentioned in AUDIT_REPORT_2026-06.md. Re-verified true in the current tree; reported here because the newer audit dropped it and the RC lens (signed, reproducible artifacts) raises its relevance.

### BLD-2 — Maven-Central javadoc-jar requirement is satisfied on only 1 of 4 publishable modules; the release doc claims the KMP modules "get theirs automatically"
- Severity: High (release-readiness defect: the repo's own RC sign-off checklist item can never pass as written) | Confidence: Confirmed that no javadoc wiring exists in the build files for the 3 KMP modules; Uncertain only whether KGP 2.3.21 / AGP-KMP 9.1.1 auto-attach a javadoc jar (nothing through KGP 2.x historically does). One `./gradlew publishToMavenLocal && ls ~/.m2/repository/dev/p2pkit/*/0.6.0/` settles it.
- File(s): p2p-core/build.gradle.kts:118-143; p2p-transport-lan/build.gradle.kts:139-164; p2p-network-provisioning-android/build.gradle.kts:34-62 (none of the three contains any javadoc-jar wiring); contrast p2p-network-provisioning-desktop/build.gradle.kts:10-15; contradicted docs: docs/STABILIZATION_AND_RELEASE.md:76-77, :99, :102-104, :212
- Category: bug (release infrastructure gap + wrong build-fact in the release doc)
- Root cause: only the plain-JVM sidecar opts in:
  ```kotlin
  // Sources + (empty, Kotlin) Javadoc jars so the published artifact satisfies
  // Maven Central's required-artifacts rule.
  java {
      withSourcesJar()
      withJavadocJar()
  }
  ```
  (p2p-network-provisioning-desktop/build.gradle.kts:10-15). The three KMP modules rely on KMP defaults, which publish per-target `-sources.jar` but no `-javadoc.jar`; there is no central wiring in the root build either (root build.gradle.kts:39-62 handles signing only). Yet docs/STABILIZATION_AND_RELEASE.md:76-77 states "The desktop sidecar publishes `-sources.jar` + `-javadoc.jar` (Central requires both); KMP modules get theirs automatically", the dry-run listing at :99 annotates `# jars, -sources, -javadoc, .pom, .module` for all modules, :102-104 claims verified `-javadoc.jar` output for BOTH sidecars (provisioning-android is KMP — doubtful), and the sign-off checklist :212 requires "`publishToMavenLocal` produces jars + sources + javadoc + pom".
- Runtime impact: none today (publishing is local-only). The day a Central Portal/Sonatype repo is wired (the doc's own "remaining release-infra step", :114-119), validation rejects at minimum the JVM-target jars of :p2p-core and :p2p-transport-lan (and typically all publications) for missing javadoc. | Platforms: n/a | User-visible: no (release pipeline)
- Failure class: build failure (future Central upload validation) / doc-vs-build mismatch (now)
- Proposed fix (do NOT implement): attach an empty javadoc jar to every publication of the three KMP modules (small shared snippet in the root `plugins.withId("maven-publish")` block, mirroring the desktop sidecar's comment), or adopt `com.vanniktech.maven.publish` when the Central repo is wired; fix docs/STABILIZATION_AND_RELEASE.md:76-77/:99 to state what is actually produced today.
- Required tests: scripted artifact-set assertion after `publishToMavenLocal` (per module: jar/klib/aar + -sources + -javadoc + .pom + .module), runnable as part of the RC checklist.

### BLD-3 — `.gitignore` ignores `*.log` globally while the repo's documented practice tracks evidence logs under `docs/audit-evidence/`
- Severity: Low | Confidence: Confirmed
- File(s): .gitignore:25 (`*.log`); tracked files `docs/audit-evidence/dns-sd-browse.log`, `docs/audit-evidence/jvm-cli.log` (via `git ls-files`); docs/LAN_DIAGNOSTICS_PROTOCOL.md:27-28, 73-75, 95, 106, 166-167 instruct producing `*.log` capture files
- Category: bug (repo hygiene contradiction)
- Root cause: the blanket `*.log` rule predates/conflicts with committing audit-evidence logs. The two existing logs stay tracked (ignore rules don't affect tracked files), but every NEW evidence log a contributor produces per the diagnostics protocol is silently invisible to `git status`/`git add` unless force-added — the exact failure mode for the pending Issue #2/#3 hardware-evidence captures.
- Evidence: `.gitignore:25` is `*.log`; `git ls-files | grep '\.log$'` returns the two docs/audit-evidence files.
- Runtime impact: evidence files silently dropped from commits. | Platforms: n/a | User-visible: no
- Failure class: none (process/data-capture gap)
- Proposed fix (do NOT implement): add `!docs/audit-evidence/*.log` after the `*.log` rule (or scope the rule to repo root / sample output dirs).
- Required tests: none (one-line ignore-rule change; verify with `git check-ignore`).

## 2b. Improvements (not defects)

### BLD-4 — Validate git subprocess output in both provenance writers
- Severity: Improvement | Confidence: Confirmed pattern, edge-case trigger
- File(s): p2p-core/build.gradle.kts:27-38; p2p-transport-lan/build.gradle.kts:116-126
- Both `git()` helpers use `redirectErrorStream(true)` and treat merged stdout+stderr as the value when exit code is 0. A git advisory printed to stderr with rc 0 (e.g. config/ownership warnings) would pollute `BUILD_COMMIT.txt` and the string constants baked into BuildInfo.kt. Validate `^[0-9a-f]{40}$` for `rev-parse HEAD` (fall back to "unknown") or stop merging stderr.

### BLD-5 — `jvmToolchain(17)` has no auto-provisioning while the daemon JVM (21) auto-downloads
- Severity: Improvement (fresh-machine DX) | Confidence: Confirmed statically
- File(s): settings.gradle.kts:1-21 (no `org.gradle.toolchains.foojay-resolver-convention` / `toolchainManagement`); gradle/gradle-daemon-jvm.properties:2-12 (`toolchainVersion=21` with download URLs); all modules pin `jvmToolchain(17)`
- On a machine with no local JDK 17, `./gradlew` bootstraps a JDK 21 daemon via the foojay URLs, then fails at the first compile with "no matching toolchain (17)". CLAUDE.md says "Java 17 required" so this is a documented prerequisite, not a defect — but adding the foojay resolver convention plugin (or a doc note that TWO JDK arrangements are in play: daemon 21, toolchain 17) would remove the asymmetry.

### BLD-6 — No `distributionSha256Sum` pin in gradle-wrapper.properties
- Severity: Improvement (supply-chain hardening) | Confidence: Confirmed
- File(s): gradle/wrapper/gradle-wrapper.properties:1-7
- `distributionUrl` is https and `validateDistributionUrl=true`, but the distribution content itself is unpinned. For an SDK heading to a public release, add the official `gradle-9.3.1-bin.zip` sha256.

### BLD-7 — `explicitApi()` not enabled on any published module
- Severity: Improvement | Confidence: Confirmed (grep across all .kts: no `explicitApi`)
- File(s): p2p-core/build.gradle.kts:79-109; p2p-transport-lan/build.gradle.kts:9-82; p2p-network-provisioning-android/build.gradle.kts:7-27; p2p-network-provisioning-desktop/build.gradle.kts:6-8
- The generated BuildInfo.kt even uses explicit `public` + `@file:Suppress("RedundantVisibilityModifier")` (p2p-core/build.gradle.kts:49, 58-68), signalling intent that is never enforced. For a locked public API (P2pKit-Spec.md), explicit API mode is the standard guard against accidental surface growth. [CATALOGUED] — PROBLEMS_P2PKIT.md:363-366, 🟡 open; not in the 21 remediated findings; still true.

### BLD-8 — `standardInput = System.in` on the sample-desktop run task is configuration-cache-incompatible
- Severity: Improvement (latent; CC is not enabled in gradle.properties) | Confidence: Confirmed pattern
- File(s): p2p-sample-desktop/build.gradle.kts:13-15
- The stdin forwarding is correct and load-bearing for IDE runs (comment explains why), but this exact idiom is a known configuration-cache blocker. If CC is ever enabled repo-wide, gate it (`if (System.console() != null)`) or accept the task being CC-excluded. No action needed today.

### BLD-9 — cinterop def uses a cwd-relative include path
- Severity: Improvement | Confidence: Uncertain whether the `-I` is even effective (build passes per REMEDIATION gates, so either the cinterop tool resolves it against the module dir or the def-file's own directory already satisfies `headers=`); an intentionally broken-path experiment would settle it
- File(s): p2p-transport-lan/src/nativeInterop/cinterop/p2pkit_nw.def:6 (`compilerOpts = -I./src/nativeInterop/cinterop`), referenced from p2p-transport-lan/build.gradle.kts:36-38
- Relative `-I` in a .def depends on the cinterop invocation's working directory. More robust: drop it or add `includeDirs(project.file("src/nativeInterop/cinterop"))` in the build script where the path is anchored to the project.

### BLD-10 — Hygiene batch (each one line)
- Severity: Improvement | Confidence: Confirmed
- settings.gradle.kts:17-20: `dependencyResolutionManagement`'s `google()` lacks the content filter that `pluginManagement`'s has (:3-8) — minor resolution-speed/consistency nit.
- p2p-network-provisioning-desktop/build.gradle.kts:24: `testImplementation(libs.kotlinx.coroutines.core)` is redundant (testImplementation already extends implementation, :20).
- .gitignore:4: `!gradle/wrapper/gradle-wrapper.jar` negates nothing (no rule ignores it — there is no `*.jar` rule); .gitignore:34 `iosApp/build/` is redundant with the global `build/` (:3). Harmless dead rules.
- .editorconfig:12-13: ktlint knobs (`ktlint_standard_no-wildcard-imports`, `ktlint_standard_filename`) with no ktlint plugin/task wired anywhere (grep confirms; CLAUDE.md correctly says no lint task) — IDE-only effect; either wire ktlint or accept as advisory.
- p2p-sample-android/build.gradle.kts:15: `versionName = "0.1.0"` literal while project.version is 0.6.0 (desktop-ui already derives its description from `project.version`, p2p-sample-desktop-ui/build.gradle.kts:38) — sample-only, cosmetic.
- gradle/libs.versions.toml:12-15: the androidx set (activity-compose 1.9.3, core-ktx 1.15.0, lifecycle 2.8.7, compose-bom 2024.12.01) is a coherent but ~18-month-old pin set next to compileSdk 36 — samples only, works, worth a refresh pass before public release.

## 3. Missing tests

| Invariant untested | Why it matters | Where it should live | Type | Priority |
|---|---|---|---|---|
| `publishToMavenLocal` produces the full Central artifact set per module (jar/klib/aar, -sources, -javadoc, .pom, .module) | RC checklist item docs/STABILIZATION_AND_RELEASE.md:212 is currently manual and (per BLD-2) cannot pass for 3 modules | scripts/ verification script invoked by the release recipe | integration (script) | P1 |
| Keyed signing path: with a throwaway key, Sign tasks run and every publication gains .asc; keyless run reports SKIPPED | Central-blocking if the central wiring regresses; only prose-verified today (docs :102-111) | same script, optional key branch | integration (script) | P2 |
| Second no-change build leaves BuildInfo.kt byte-identical and compile tasks UP-TO-DATE | Guards the BLD-1 fix; protects build-cache economics repo-wide | Gradle TestKit test or CI script step | integration | P2 |
| BUILD_COMMIT stamp semantics: stamped only on executed+successful per-config assembly; not re-stamped on UP-TO-DATE; debug/release XOR | The Xcode freshness guard's trust anchor (adca586); manual recipe only (REMEDIATION #10 notes "shell not unit-testable" — the *writer* is testable via TestKit even if the shell check isn't) | TestKit test on :p2p-transport-lan | integration | P3 |
| Exactly 4 modules publish; samples never acquire maven-publish | Accidental sample publication would ship test harnesses under dev.p2pkit | root build verification task or script (`assert publishing only on the 4`) | unit (build logic) | P3 |

## 4. Section summary

**What this section owns:** the whole build/release surface — root coordination (coordinates, central signing), settings/repos, version catalog, wrapper (jar + scripts, both verified stock for Gradle 9.3.1), daemon-JVM pinning, IDE run configs, and the 8 module build scripts including the XCFramework/cinterop wiring and the BUILD_COMMIT provenance stamp.

**Overall health: good.** Publishing is correctly scoped (exactly the 4 library modules; samples and iosApp cannot publish), the POMs carry every Central-required metadata field (name/description/url/licenses/developers/scm — verified in all four modules; scm/url match the actual `origin` remote), GROUP/VERSION_NAME propagate from gradle.properties via `allprojects`, and the conditional signing block behaves exactly as CLAUDE.md and the release doc describe (keyless → `isRequired=false`, no signatory → SKIPPED; `ORG_GRADLE_PROJECT_signingInMemoryKey[Password]` names match `findProperty` keys at root build.gradle.kts:45-46; the publish→sign `dependsOn` closes the known ordering error). All version-catalog aliases are used; toolchain 17 is consistent across all modules; iOS target triples match between core and transport-lan; export/api pairing for the XCFramework is present on both sides.

**The adca586 stamp writer (reviewed as new code) is sound.** doLast-on-the-assembly-task gives exactly the three properties the comment claims: no stamp on failure, no re-stamp on UP-TO-DATE, per-config XOR (umbrella task correctly falls out via the `null` config). Captures are CC-safe (File/Provider/String only; process exec at execution time); `tasks.matching{}.configureEach{}` stays lazy; writer path `p2p-transport-lan/build/XCFrameworks/<config>/BUILD_COMMIT.txt` exactly matches the consumer (iosApp/scripts/check-xcframework.sh:34-35) and iosApp/project.yml:46,59; a missing stamp hard-fails the consumer (safe). Dirty-tree state is deliberately handled consumer-side (soft warn, check-xcframework.sh:92-94), so the writer omitting a dirty marker is coherent. Residual nits: unvalidated git output (BLD-4) and, if the XCFramework task ever became build-cacheable, a FROM-CACHE restore would skip doLast — analysis shows the consumer's path-diff logic fails safe (spurious rebuild) rather than passing a wrong artifact, so no finding.

**What breaks the day a real Central repo is added:** (1) missing javadoc jars on the 3 KMP modules — BLD-2, the one real gap; (2) the acknowledged missing `repositories{}` target (docs :114-119 — accurately documented, not a finding); (3) nothing else found — signing, POMs, coordinates, and non-SNAPSHOT version are ready.

**Cross-doc build-fact verification (for the doc reviewers).** Verified TRUE against build files: every command in CLAUDE.md "Commands" (assemble pair, allTests/jvmTest/iosSimulatorArm64Test/testAndroidHostTest/test, --tests filters, installDist + binary path, desktop-ui run, assembleDebug + APK path, assembleP2pKitSharedXCFramework, :iosApp:runIosSimulator + SIM_NAME override, publishToMavenLocal → four modules, keyless publish needs no secrets, ORG_GRADLE_PROJECT_… env names, "no lint/format task", GROUP/VERSION_NAME from gradle.properties, minSdk 24, Java 17 toolchain); docs/STABILIZATION_AND_RELEASE.md Part B's signing table, SKIPPED semantics, and "no remote repository yet" caveat. Verified FALSE/overclaiming: STABILIZATION :76-77 "KMP modules get theirs automatically" (javadoc), :99 ls annotation listing `-javadoc` for all modules, :102-104 "verified … -javadoc.jar" for the KMP android sidecar, and checklist :212 as written — all BLD-2. Also note the p2p-core build comment (lines 16-19) is itself a false claim about incremental behavior — BLD-1.

**Top 3 risks:** (1) BLD-2 Central javadoc gap + release-doc overclaim (the sign-off checklist contains an unpassable item); (2) BLD-1 every-build recompile/cache-miss + non-reproducible artifacts from BUILD_TIME; (3) zero automated verification of the publish artifact set (all release assurance is manual prose).

**CODEBASE_REVIEW_MAP_2026-07.md accuracy for S13:** accurate. "9 modules" in settings ✓ (counted); "8 module build.gradle.kts (core, transport-lan incl. XCFramework + cinterop + BUILD_COMMIT stamp, 2 provisioning, 4 samples)" ✓; module dependency graph (map :373-384) matches the actual `project(...)` edges in every build file I read, including provD→lan and kmp→core+lan; risk rating "Medium — release gate correctness … no automated verification" matches my conclusions. No discrepancies found.
