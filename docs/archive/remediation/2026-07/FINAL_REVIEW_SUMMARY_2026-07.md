# P2pKit — Final Review Summary (2026-07 review campaign)

## 1. Campaign header

- **Campaign:** P2pKit 2026-07 exhaustive internal code-review campaign (defensive quality assurance of our own SDK ahead of the RC tag).
- **Date closed:** 2026-07-04
- **Branch / HEAD:** `audit/exhaustive-review-2026-06` @ `870bf10`

This document closes the full-project review campaign over P2pKit, the Kotlin Multiplatform LAN SDK (mDNS discovery + TCP data; JVM desktop, Android minSdk 24, iOS). The campaign reviewed every repository file for correctness, error handling, cancellation handling, thread/coroutine safety, resource ownership and cleanup, lifecycle transitions, platform parity, input validation, resource-limit enforcement and bounded resource usage, documentation accuracy, and test coverage. Its outputs are a consolidated findings register, a prioritized test coverage plan, a per-file review tracker, and this summary; no repository code was changed.

## 2. Scope & method

- **Coverage:** 236/236 repository files reviewed (235 tracked + 1 untracked), organized into sections S1–S15 per `CODEBASE_REVIEW_MAP_2026-07.md`. File-count reconciliation in the tracker: 31+19+13+16+18+20+9+12+5+14+13+10+26+26+4 = 236.
- **Reports:** 18/18 section reports produced in 6 waves (`A01-arch` … `A16-samples`, including the split `A13a`/`A13b` documentation reviews and the cross-cutting `A14-robustness`, `A14-sec`, and `A15-perf` reviews, which own no tracker rows — their findings attach to the owning sections).
- **Model provenance:** every review, verification, and consolidation agent whose output was merged ran on Fable 5; no silent model fallback occurred in any merged wave.
- **Verification discipline:** every Critical and High finding was re-verified against the source tree at HEAD `870bf10` before acceptance into the register (register §2); the register is authoritative where an individual report disagrees.
- **Wording policy:** all campaign artifacts use neutral defensive-QA vocabulary (input validation, malformed/excessive peer input, resource-limit enforcement, bounded resource usage, admission control, crash prevention, defensive robustness), per hard rule 7 of `.review-2026-07/BRIEF.md`.
- **Read-only campaign:** no code changes, no build/test/git-mutating commands by reviewers, no push and no PR. Findings and tests are recorded for a post-approval remediation phase.

## 3. Results at a glance

Severity totals from `CODEBASE_FINDINGS_2026-07.md` (the authoritative register):

| Severity | Register rows |
|---|---|
| Critical | 1 |
| High | 16 |
| Medium | 47 |
| Low | 88 |
| Improvement | 96 |
| **Total** | **248** |

- **Raw finding IDs across the 18 reports:** 263. Duplicate findings (the same defect reported by more than one reviewer) were collapsed: **15 duplicate IDs → 13 canonical rows** (register §4); a canonical row keeps the highest severity assigned by any contributor.
- **Critical + High verification:** **17/17 Confirmed** against source at HEAD `870bf10` (register §2). Four Confirmed items carry a named runtime residual that would close a remaining sub-question (register §5): **RBS-1** (JVM/Android listener-thread disposition — either disposition already violates the typed-error invariant), **BLD-2** (one `publishToMavenLocal` listing closes the KGP auto-attach question), **DSC-1** (a two-CLI 20 s idle run remains the end-to-end demonstration), **ARCH-1** (the Android crash-escalation sub-claim needs a small repro).

## 4. Highlights — Critical and High findings

### The 1 Critical

**RBS-1** (`IosLanDiscoveryTransport.kt`, `JvmLanDiscoveryTransport.kt`, `AndroidLanDiscoveryTransport.kt`, `Identity.kt`) — A discovered peer-id taken from an mDNS TXT record reaches the throwing `PeerId()` constructor unguarded on all three platforms, so a blank or whitespace peer-id in discovery input throws inside the discovery callback: on iOS this is a process-crash path on malformed discovery input, and on JVM/Android it is an untyped failure on a listener thread — either disposition violates the typed-error invariant. The Lost path is additionally not appId-gated. By contrast, the wire-HELLO twin of this input path was hardened in the 2026-06 audit; the discovery/TXT path received neither the `isNotBlank` guard nor a `runCatching` wrapper. This is the top crash-prevention item for the RC.

### The 16 Highs (one line each; full detail in the register §3.2)

- **ARCH-1** — `P2pKitImpl.kt` — the `ensureStarted` bind loop swallows `CancellationException` and latches `P2pState.Failed` when the caller is cancelled mid-start.
- **ARCH-2** — `P2pKitImpl.kt` (+ path observers) — the `stop()` tail runs `pathObserver.close()` outside `NonCancellable` and unbounded, allowing a hang on the observer's internal mutex or an observer leak on caller cancellation.
- **API-1** — `P2pMessage.kt` / `Chunker.kt` / `Reassembler.kt` — `P2pMessage.metadata` is accepted by the public API but silently dropped on the wire (open RC decision).
- **API-2** — `P2pSessionImpl.kt` / platform raw connections — `P2pSession.send()` leaks raw platform exceptions instead of the documented typed `P2pError.ConnectionFailed`.
- **SES-1** — `P2pSessionImpl.kt` / `SessionManager.kt` / `JvmRawConnection.kt` — terminal-outcome race on remote connection loss: reconnect is nondeterministically skipped and a clean close nondeterministically retried, because the transports collapse read-error and EOF into identical normal completion.
- **DSC-1** — `JvmLanDiscoveryTransport.kt` / `AndroidLanDiscoveryTransport.kt` / `PeerRegistry.kt` — JVM and Android discovered peers are evicted from `kit.peers` 15 s after resolution and never return in steady state (no re-announce heartbeat; only iOS has one).
- **CON-1** — `JvmRawConnection.kt` / `AndroidRawConnection.kt` — `close()` and the read loop skip file-descriptor release when the calling coroutine is already cancelled (`withContext` throws on entry without running the block).
- **CON-3** — `JvmLanDataTransport.kt` / `AndroidLanDataTransport.kt` / `SessionManager.kt` — an accept-loop failure propagates as an uncaught exception (Android host-app crash path) and permanently ends inbound connection acceptance.
- **FIL-1** — `FileTransferDispatcher.kt` / `P2pSessionImpl.kt` — the `sendFile` source-close watcher is cancelled by `close()` before it can close the source, a contract-violating RawSource/fd leak.
- **FIL-2** — `FileTransferDispatcher.kt` / `StreamingFileSender.kt` — a sender-side source read failure never notifies the receiver, so an accepted incoming transfer waits indefinitely.
- **IOSB-3** — `scripts/run-ios-app.sh` — the script installs the first `p2pkit-sample.app` found anywhere in global DerivedData and can silently install a stale bundle from another checkout or worktree.
- **BLD-2** — library `build.gradle.kts` files / `docs/STABILIZATION_AND_RELEASE.md` — the Maven-Central javadoc-jar requirement is satisfied on only 1 of 4 publishable modules while the release doc claims KMP modules "get theirs automatically" (release-readiness defect).
- **TST-1** — `FakeRawConnection.kt` — the fake models remote-initiated termination unlike any shipped transport, so the real clean-close-vs-reconnect race (SES-1) is structurally invisible to commonTest.
- **TST-9** — `SessionManager.kt` / `P2pKitImpl.kt` — the e91e094 `strictInvariants` safety net is inert in every kit-level suite: `P2pKitImpl` never passes it and SessionStore warnings go to NoOp loggers.
- **SEC-1** — `SessionManager.kt` / `Handshake.kt` / platform accept sources — no admission control on inbound connection setup: a non-conforming peer opening many connections drives unbounded concurrent pre-handshake work and unbounded total sessions (fd/coroutine/heap growth without a limit).
- **DOCB-1** — `AUDIT_REPORT_2026-06.md` — the "Deferred (39)" list is heavily stale (at least 10 of 16 deferred bullets were since implemented on this branch) while CLAUDE.md routes every future agent to it — a load-bearing maintenance-steering document.

## 5. Test coverage plan summary

`TEST_COVERAGE_PLAN_2026-07.md` consolidates every proposed test from all 18 reports into **155 items**: **32 P1** (must land before the RC tag), **70 P2** (strongly recommended for the RC line), **53 P3** (valuable hardening/pinning, schedule after P1–P2).

- **Fixture-upgrade prerequisite:** 9 shared test-fixture changes (F1–F9, plan §2.1 — remote-termination fidelity and write-fault injection in `FakeRawConnection`, incoming-flow error termination in `FakeDataTransport`, production-shaped buffer semantics in `FakeDiscoveryTransport`, internal `strictInvariants` threading, a shared `RecordingLogger`, fixture-state synchronization, virtual-time migration) must land first: **14 plan rows are strictly blocked on them**, and several more are materially aided. A further ~10 rows need a product-side injection seam or extracted helper, and 5 rows need a new test source set (plan §2.2).
- **Manual/hardware rows:** 12 rows in the main plan are manual/hardware (2 × P1, 4 × P2, 6 × P3), plus 2 standing policy items in plan §5 — 14 manual/hardware rows total. The largest automated gains land in `p2p-core` commonTest (~89 rows, ~57% of the plan).
- **Policy notes (standing coverage, not gaps to automate):**
  - The two known-flaky iOS simulator churn tests (`IosLanLifecycleTest.peerLostEventFiresWhenPeerStops`, `advertiseStopRestartProducesObservablePeerChurn`) **stay active** in `iosSimulatorArm64Test`; the simulator's NWBrowser does not reliably deliver removed results, and the peer-Lost path is validated on real hardware via smoke-matrix row A4 in `docs/STABILIZATION_AND_RELEASE.md`. No widened timeouts, no `@Ignore`, no relaxed assertions.
  - There are no instrumented Android tests **by repository policy**; Android LAN transport paths, `WifiManagerWrapperImpl`, and the platform `NetworkPathObserver`s are covered by the manual recipes in `INTERNAL_TESTING.md` (§A–§K) and the device smoke matrix (A1–A12), represented in the plan as manual rows rather than automation gaps.

## 6. Open decisions for the user

Reproduced from register §6 (items the reports explicitly flagged as needing a user / RC decision; every `[API-CHANGE]`-tagged finding has a no-API-change alternative recorded in its source report):

| # | Finding(s) | Decision needed (compact) |
|---|---|---|
| 1 | DOCA-20 | Disposition of untracked `P2PKIT_GAP_ANALYSIS_2026-07.md` — report recommends KEEP and COMMIT with a status banner (untracked, it is one `git clean -fd` from loss). |
| 2 | DOCA-1 | Commit (or amend) the working-tree `CLAUDE.md`; the committed HEAD version contains a now-false publishing claim. |
| 3 | API-1, DOCA-15, DOCA-14 | `P2pMessage.metadata` never serialized: wire it, remove/deprecate it, or document "not transmitted in protocol v1"; add an explicit decision box to the C3 RC sign-off checklist. |
| 4 | C:54 (via A09) | Deferred `P2pPermission` enum disambiguation (`ChangeWifiState`): deferral re-assessed as sound — record the decision formally so it stops resurfacing. |
| 5 | ARCH-10 | [API-CHANGE-adjacent] Construction-time blocking disk I/O (`newP2pKit` → `loadOrGenerate()`): decide fix (suspending/async construction) vs documented deferral. |
| 6 | IDN-7 | [API-CHANGE] Add `unregisterManualPeer(peerId)` vs the no-API-change alternative (KDoc lifetime + registry-internal name refresh). |
| 7 | PRM-1 | Permission-gate granularity after fix #9: doc-level guidance vs [API-CHANGE] per-operation permission sets on `P2pPermissionManager`. |
| 8 | PRM-16 | [API-CHANGE] `leaveNetwork()` (or define `stopLocalNetwork` to also release a join); also reword the misleading "already in progress" rejection. |
| 9 | SEC-1 | Admission-control limits for inbound connection setup (max concurrent pre-handshake setups + max total sessions): internal caps need no API change; [API-CHANGE] only if surfaced as configuration. |
| 10 | DOCA-16 / SES-9 | `ConnectionState.Closing`: fix the spec/KDoc ("close() transitions directly to Closed") vs start emitting `Closing` (observable behavior change; reports disagree on its API-impact classification). |
| 11 | API-19 | Offer-timeout terminal-state asymmetry: document the per-side outcomes vs align the sender's local-timeout state to `Rejected("timeout")`. |
| 12 | API-2 (incl. SES-2) | Typed-error contract for `send()`: standing deferral assessed unsound for an RC — decide whether wrapping platform exceptions into `P2pError.ConnectionFailed` lands before the RC tag. |
| 13 | A16 (root of SMP-8) | Incoming-session receive contract: `incoming`/`incomingFiles` at replay=0 are inherently lossy between session emission and subscription — small replay buffer vs documented sender-side grace period. |
| 14 | DSC-1 | Steady-state discovery on JVM/Android needs a re-announce/heartbeat design (pick the mechanism before RC; it defines cross-platform `kit.peers` semantics). |
| 15 | TST-9 (incl. SES-8) | Approve the internal-only wiring so kit-level suites run `strictInvariants = true`; explicitly no public API change required. |

## 7. Constraints honored

- **No code changes:** the campaign was read-only; the only files written are the campaign deliverables and reports.
- **No push, no PR:** all work stayed local on `audit/exhaustive-review-2026-06`; publication awaits explicit user approval.
- **The 9 remediation commits intact:** the 2026-06 audit-remediation commits ending at HEAD `870bf10` were reviewed as new code, not reverted or amended.
- **NsdManager not reintroduced:** Android discovery remains in-process JmDNS per the v0.5 migration; no proposal reverses it.
- **Known-flaky iOS churn tests not masked:** no `@Ignore`, widened timeout, or relaxed assertion was added or proposed for the two simulator churn tests (see §5).
- **PP2K wire protocol untouched:** magic "PP2K", version 1, the 36-byte header, frame types, and `ProtocolConstants` limits are unchanged and cross-platform identical.
- **Provisional draft quarantined:** the earlier Opus-produced consolidation draft remains at `.review-2026-07/CODEBASE_FINDINGS_2026-07.OPUS-PROVISIONAL.md` as a non-authoritative reference only, with **zero content reuse** — the authoritative register was produced by a fresh Fable 5 agent that never opened it, and this summary was likewise produced without opening it.

## 8. Recommended next steps (advisory — no action taken)

1. **Triage in severity order:** the 1 Critical (RBS-1 — discovery-callback crash prevention) first, then the 16 Highs, then the RC-decision items in §6 (several Highs — API-1, API-2, DSC-1, SEC-1, TST-9 — are themselves decision items, so triage and §6 converge quickly).
2. **Tests:** land the fixture upgrades F1–F9 and the §2.2 seams from the coverage plan, then the 32 P1 rows before the RC tag; P2 along the RC line; P3 afterwards.
3. **Release-gate documents:** with Critical/High remediation and P1 tests in hand, return to the user's own gate documents — `docs/STABILIZATION_AND_RELEASE.md` (smoke matrix A1–A12, publishing/signing recipe, C3 sign-off checklist, updated per DOCA-14) and `INTERNAL_TESTING.md` — and refresh the stale documentation of record flagged by the campaign (DOCB-1 and the A13a/A13b doc findings) so future agents are not mis-steered.

## 9. Deliverables index

| Deliverable | Path |
|---|---|
| Review map (sections S1–S15, owners, scope) | `/Users/abdelrahman/Projects/P2pKit/CODEBASE_REVIEW_MAP_2026-07.md` |
| Per-file review tracker (236/236 reviewed) | `/Users/abdelrahman/Projects/P2pKit/CODEBASE_REVIEW_TRACKER_2026-07.md` |
| Consolidated findings register (authoritative; 248 rows) | `/Users/abdelrahman/Projects/P2pKit/CODEBASE_FINDINGS_2026-07.md` |
| Test coverage plan (155 items) | `/Users/abdelrahman/Projects/P2pKit/TEST_COVERAGE_PLAN_2026-07.md` |
| Final review summary (this document) | `/Users/abdelrahman/Projects/P2pKit/FINAL_REVIEW_SUMMARY_2026-07.md` |
| The 18 section reports (A01–A16, incl. A13a/A13b, A14-robustness/A14-sec, A15-perf) | `/Users/abdelrahman/Projects/P2pKit/.review-2026-07/reports/` |

Campaign method/provenance records: `.review-2026-07/BRIEF.md` (standing rules) and `.review-2026-07/RESUME.md` (model/provenance history).
