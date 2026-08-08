# P2pKit — Deferred-Items Register (2026-07)

- **Date:** 2026-07-05
- **Tree:** `main` @ `6a05ccd` (2026-07 remediation campaign fully merged; PR #48)
- **Purpose:** the complete owner-facing register of everything intentionally postponed across the 2026-06 audit, the 2026-07 review campaign, the remediation groups A–N/M1–M5, and the release-planning documents — grouped for the first-RC decision pass. Every item cites where it is recorded, why it waits, its honest residual risk, and one exact next step.
- **Status:** review document — nothing implemented. This file is the only artifact produced; no code, test, build file, or other doc was changed.
- **Wording:** neutral defensive-QA vocabulary throughout, per the campaign brief (rule 7).
- **Verdict key:** Blocks RC / Waive explicitly at RC / Safe post-RC.

## 1. Metadata transmission (the `metadata-wire` milestone, decomposed)

Decision #3(c) (recorded 2026-07-04) ships the RC with metadata documented as **not transmitted in protocol v1**; transmission is the named post-RC milestone. The milestone decomposes into five deferred items.

- **Item:** Metadata DATA-payload envelope (the milestone core)
- **Source:** `docs/STABILIZATION_AND_RELEASE.md` §C4; `OPEN_DECISIONS_2026-07.md` #3; `.review-2026-07/IMPLEMENTATION_NOTES.md` Group M5
- **Why deferred:** Decision #3(c) scoped the RC to a documented local-only contract; the envelope is a DATA-payload-encoding change (commonMain codec in `Chunker`/`Reassembler`), wrong scope for a stabilization RC.
- **Risk if left deferred through RC:** None for the RC — KDoc, spec §9.4, and the C3 decision box state the contract; the field stays a documented no-op until wired.
- **RC verdict:** Safe post-RC
- **Owner & timing:** assistant-able once prerequisites are decided; owner wants it soon after the RC line
- **Next step:** Schedule `metadata-wire` as the first post-RC feature batch, opening with the two prerequisite decisions below.

- **Item:** Cross-version interop stance
- **Source:** `docs/STABILIZATION_AND_RELEASE.md` §C4 prerequisite 1
- **Why deferred:** The mechanism (HELLO-negotiated capability vs a reserved DATA flag bit vs a protocol version bump) needs a deliberate compatibility matrix before any bytes change.
- **Risk if left deferred through RC:** None at RC; mandatory before the envelope — a v1 receiver must never misparse an envelope as payload bytes.
- **RC verdict:** Safe post-RC
- **Owner & timing:** maintainer decision, first item of the milestone
- **Next step:** Pick one of the three mechanisms and write the sender/receiver compatibility matrix into the milestone spec.

- **Item:** v1.1-vs-v2 protocol versioning call
- **Source:** `docs/STABILIZATION_AND_RELEASE.md` §C4 prerequisite 3
- **Why deferred:** Whether the envelope is v1.1 (negotiated in-band, version byte unchanged) or v2 (version byte bump) follows from the interop stance; the wire-parity rule (identical across jvmMain/androidMain/appleMain) applies either way.
- **Risk if left deferred through RC:** None — no bytes change until decided.
- **RC verdict:** Safe post-RC
- **Owner & timing:** maintainer decision, with the interop stance
- **Next step:** Decide v1.1 vs v2 in the same milestone-spec commit as the interop stance.

- **Item:** Receive-side metadata bounds and input validation
- **Source:** `docs/STABILIZATION_AND_RELEASE.md` §C4 prerequisite 2
- **Why deferred:** Key/value/count limits (sized against the 4 MiB message cap and reassembly caps) only matter once metadata is decoded from the wire.
- **Risk if left deferred through RC:** None at RC (nothing is decoded today); at milestone time the bounds are mandatory so malformed or excessive peer metadata is rejected as a typed, bounded failure rather than growing memory.
- **RC verdict:** Safe post-RC
- **Owner & timing:** assistant-able, lands with the envelope
- **Next step:** Specify the limits in the milestone spec and enforce them in the decode path with typed refusal.

- **Item:** P1-06 pin flip (`MessageMetadataContractTest`)
- **Source:** `docs/STABILIZATION_AND_RELEASE.md` §C4; `.review-2026-07/IMPLEMENTATION_NOTES.md` Group M5
- **Why deferred:** The test deliberately pins asserted-empty receive plus envelope-free DATA bytes for v1; flipping to round-trip equality belongs in the same commit as the envelope.
- **Risk if left deferred through RC:** None — the pin actively protects the RC contract until then.
- **RC verdict:** Safe post-RC
- **Owner & timing:** assistant-able, same commit as the envelope
- **Next step:** Consciously flip the pin from asserted-empty to round-trip equality in the envelope commit, per §C4's instruction.

## 2. Device/runtime items

- **Item:** Device smoke matrix A1–A12 (all rows unrun)
- **Source:** `docs/STABILIZATION_AND_RELEASE.md` Part A + C3; `INTERNAL_TESTING.md` §A–§K and §4 (all boxes unchecked); `TEST_COVERAGE_PLAN_2026-07.md` §5
- **Why deferred:** Hardware-only coverage (real radios, real Bonjour removal, hotspot provisioning) that no automated suite can reach; needs human hands and devices.
- **Risk if left deferred through RC:** Real. The Android rows are the first execution ever of the Android-specific LAN paths (no instrumented tests by policy) — and those paths were reshaped this campaign by Group I's `JmdnsLifecycleCoordinator` extraction and M3's discovery heartbeat, so A1/A4/A7/A10 now exercise new code on hardware for the first time. A12 validates the write watchdog end-to-end.
- **RC verdict:** Blocks RC (C3 requires A1–A8, A10–A12 PASS)
- **Owner & timing:** maintainer (devices required), before-tag
- **Next step:** Schedule one device-day; run the rows per `INTERNAL_TESTING.md` recipes and link logs into Part A.

- **Item:** A9 LocalOnlyHotspot host/join — run vs waive
- **Source:** Part A row A9 + C3 ("PASS or explicitly waived"); `WORKSPACE_SYNC_DASHBOARD.md` §1 (§H/§I pending since v0.2.1); session decision-state (open owner decision)
- **Why deferred:** Needs two physical Android phones (mixed OEMs preferred); the provisioning host/join path has never been device-verified in the project's history.
- **Risk if left deferred through RC:** The Android provisioning sidecar ships with zero device execution; the gap analysis suggested `@ExperimentalP2pApi` gating until A9 passes. Host-test coverage (P1-27/P1-28 and the P2 rows) bounds but does not replace OS behavior.
- **RC verdict:** Waive explicitly at RC (or run) — open owner decision
- **Owner & timing:** maintainer, before-tag (the decision; the run can ride the device-day)
- **Next step:** Decide run-vs-waive; if waived, record the waiver in C3 and keep §H/§I as the standing backlog row.

- **Item:** Hardware-matrix hold (standing owner scheduling constraint)
- **Source:** standing owner instruction (project memory note: hardware matrix on hold, revisit after the Parlor milestone); `WORKSPACE_SYNC_DASHBOARD.md` §1
- **Why deferred:** Owner prioritized another project's milestone; the matrix cannot run without the owner's devices and time.
- **Risk if left deferred through RC:** The hold and C3's device-matrix requirement are in direct tension — the tag date is effectively pinned to the hold's end unless rows are explicitly waived.
- **RC verdict:** Blocks RC (schedule constraint on the two items above)
- **Owner & timing:** maintainer, timing owned by the other milestone
- **Next step:** After the Parlor milestone, surface the reminder and book the device-day (per the standing note).

- **Item:** iOS simulator churn tests — re-evaluate after A4
- **Source:** `docs/STABILIZATION_AND_RELEASE.md` C2; `TEST_COVERAGE_PLAN_2026-07.md` §5 (stay ACTIVE, never mask)
- **Why deferred:** The simulator's NWBrowser does not reliably deliver removed results, so `peerLostEventFiresWhenPeerStops` and `advertiseStopRestartProducesObservablePeerChurn` fail there; the peer-Lost path is validated on real hardware via A4.
- **Risk if left deferred through RC:** Negligible — the two sanctioned failures are documented in C2/C3 and every gate run; residual risk exists only if A4 fails on hardware.
- **RC verdict:** Waive explicitly at RC (already codified: C3 reads the suite green "except" these two)
- **Owner & timing:** maintainer via A4; re-evaluation after-RC if A4 rides the post-hold device-day
- **Next step:** After A4 passes on hardware, re-evaluate the two tests per C2 — never widen timeouts or `@Ignore`.

- **Item:** iOS AWDL `include_peer_to_peer` asymmetry (issue #3)
- **Source:** `AUDIT_REPORT_2026-06.md` deferred list `[STILL OPEN — deliberate]`; C1; `P2PKIT_GAP_ANALYSIS_2026-07.md` P5; `docs/LAN_DIAGNOSTICS_PROTOCOL.md`
- **Why deferred:** The browser opts into peer-to-peer but listener/dial parameters do not; the fix direction (symmetric enablement vs stop browsing AWDL) needs real-device traces (A2/A3).
- **Risk if left deferred through RC:** AWDL-discovered peers may be undialable on real iOS hardware — would surface as A2/A3 anomalies; invisible on simulator and wired LANs.
- **RC verdict:** Safe post-RC (C1: explicitly out of RC scope)
- **Owner & timing:** maintainer (hardware), diagnose during A2/A3; fix after-RC
- **Next step:** Run the LAN_DIAGNOSTICS capture during A2/A3 and pick the fix direction from the traces.

- **Item:** Interface selection / NIC binding (issue #2)
- **Source:** `AUDIT_REPORT_2026-06.md` deferred list `[STILL OPEN — deliberate]`; C1; `P2PKIT_GAP_ANALYSIS_2026-07.md` P5 (VPN-NIC case live-confirmed)
- **Why deferred:** Bind-address selection can pick a cellular/loopback/VPN interface and the JVM transport has no network-rotation rebind; changes are best validated on multi-interface hardware (A7).
- **Risk if left deferred through RC:** Real on multi-interface hosts (a JVM peer bound to a VPN NIC is undiscoverable/undialable); single-interface home-LAN use is unaffected.
- **RC verdict:** Safe post-RC
- **Owner & timing:** maintainer diagnosis on hardware (A7); assistant-able fix after-RC
- **Next step:** Diagnose during A7, then land a routable-interface picker + JVM rotation rebind (+ an explicit bind escape hatch per the gap analysis).

## 3. Flake/watchlist items

Context: the 2026-07-05 post-merge stress-chase (10× core:jvmTest, 4× lan:jvmTest, 3× concurrent --parallel, 3× iosSimulatorArm64Test) reproduced **none** of the watchlist one-offs (20/20 PASS; logs in `.review-2026-07/impl-logs/stress/`). All entries are load-sensitive one-offs, not product defects.

- **Item:** FIL-15 latent flake (`cancelMidStreamPropagatesToReceiver`)
- **Source:** `CODEBASE_FINDINGS_2026-07.md` §3.5 FIL-15 (FileTransferFlowTest.kt:326-352); `.review-2026-07/IMPLEMENTATION_NOTES.md` Groups C/G/N + stress addendum
- **Why deferred:** Test-structure improvement (tolerates two outcomes but hard-asserts the sender side); fired three one-offs across the whole campaign, always green standalone and on re-run.
- **Risk if left deferred through RC:** Negligible product risk; occasional red CI run under full parallel load.
- **RC verdict:** Safe post-RC
- **Owner & timing:** assistant-able, after-RC (with item 3.6)
- **Next step:** Restructure the test's outcome handling in the post-RC test batch — never widen timeouts.

- **Item:** Rotation seed-wait one-offs (`SessionReconnectRotationTest`)
- **Source:** `.review-2026-07/IMPLEMENTATION_NOTES.md` Group D (registry SEED wait, 3.5 s bound), Group M1 and Group M5 gate notes (`reconnectUsesRefreshedHintsAfterPeerRegistryUpdate[iosSimulatorArm64]`)
- **Why deferred:** The waits are load-sensitive under parallel-suite CPU saturation — the sensitivity the test's own KDoc documents; product paths not implicated; snapshots captured before every re-run.
- **Risk if left deferred through RC:** Negligible; one-off timeouts on saturated hosts.
- **RC verdict:** Safe post-RC
- **Owner & timing:** assistant-able, after-RC (with item 3.6)
- **Next step:** Fold the seed-waits into the virtual-time stabilization batch below.

- **Item:** Unattributed LAN jvmTest one-off (post-b064622)
- **Source:** `.review-2026-07/IMPLEMENTATION_NOTES.md` Group M3 orchestrator addendum; stress addendum (no reproduction)
- **Why deferred:** One BUILD FAILED whose failing-test identity was lost to a results overwrite (snapshot rule adopted since); two full re-runs plus targeted repetitions of both suspect heartbeat suites all pass.
- **Risk if left deferred through RC:** Low. Watchlist note: the kit-level heartbeat test uses real-time 20 s/35 s windows over a 5 s tick vs 15 s eviction horizon — ~3 ticks of margin that could thin under CPU saturation.
- **RC verdict:** Safe post-RC
- **Owner & timing:** assistant-able on recurrence
- **Next step:** On an attributed recurrence, tighten the TEST's timing setup (eviction-horizon override or a virtual-time seam) — never the product invariant.

- **Item:** `SessionFlowTest` close-classification one-off
- **Source:** `.review-2026-07/IMPLEMENTATION_NOTES.md` Group N (allTests run 2; snapshot `groupN-flake-snapshot-allTests-run2/`)
- **Why deferred:** `closeTransitionsSessionToClosed[jvm]` once observed `Failed` where the P1-02-tightened assertion expects `Closed`, under full parallel load; standalone 4/4 and the next full run green; not attributable to the doc-only batch that ran it.
- **Risk if left deferred through RC:** Low, but the most substantive watchlist entry: a recurrence could indicate a residual close-vs-break classification window left by the SES-1 classification-deferral under CPU saturation.
- **RC verdict:** Safe post-RC
- **Owner & timing:** assistant-able triage on recurrence
- **Next step:** On an attributed recurrence, triage the SES-1 residual-window hypothesis before touching the test.

- **Item:** Desktop-provisioning one-off (prov-1)
- **Source:** `.review-2026-07/IMPLEMENTATION_NOTES.md` 2026-07-05 stress-chase addendum
- **Why deferred:** `:p2p-network-provisioning-desktop:test` failed once right after the stress batches; identity lost (the snapshot guard was missing from that loop — since added to all loops); 5× isolated + 3× paired re-runs green.
- **Risk if left deferred through RC:** Negligible; same load-sensitive one-off class as the rest of this section.
- **RC verdict:** Safe post-RC
- **Owner & timing:** watchlist only
- **Next step:** No action; the snapshot guard now guarantees attribution on recurrence.

- **Item:** Post-RC real-time-window stabilization batch (virtual-time seams)
- **Source:** session decision-state (orchestrator recommendation); `TEST_COVERAGE_PLAN_2026-07.md` §2.1 F9 + TST-12; Group M3 addendum watchlist
- **Why deferred:** Every async suite runs `runBlocking` + wall clock (kotlinx-coroutines-test is declared but unused in 5 modules); the F9 virtual-time migration and window restructuring were deliberately kept off the RC-critical path.
- **Risk if left deferred through RC:** None to the product; the one-off class above persists until it lands.
- **RC verdict:** Safe post-RC
- **Owner & timing:** assistant-able; recommended as a post-RC P2 batch
- **Next step:** Owner approves the batch; migrate the pure-fake suites to virtual time (F9) and de-real-time the heartbeat/rotation/seed-wait windows.

## 4. Publishing/release items

- **Item:** RC scope decision — git tag + local artifacts vs Central wiring first
- **Source:** session decision-state (open owner decision); `docs/STABILIZATION_AND_RELEASE.md` Part B scoping note ("not required for an internal RC tag")
- **Why deferred:** The owner has not yet chosen whether `v0.6.0-rc1` is a git tag plus locally-produced signed artifacts only, or waits for a remote publish target.
- **Risk if left deferred through RC:** None technical, but every remaining publishing step sequences off this choice.
- **RC verdict:** Blocks RC (the decision, not any wiring)
- **Owner & timing:** maintainer, before-tag
- **Next step:** Record the choice in C3; if tag-only, the Central wiring below formally moves post-RC.

- **Item:** Remote Maven Central wiring
- **Source:** `docs/STABILIZATION_AND_RELEASE.md` Part B "Remaining release-infra step (NOT yet wired)"; `P2PKIT_GAP_ANALYSIS_2026-07.md` P0
- **Why deferred:** The publishing block has no remote `repositories { maven { … } }` target — artifacts can be produced and signed but not uploaded; explicitly not required for an internal RC tag.
- **Risk if left deferred through RC:** None for a tag-only RC; blocks any external consumption and the public release.
- **RC verdict:** Safe post-RC (before-tag only if the scope decision says publish)
- **Owner & timing:** assistant-able wiring + maintainer credentials; before the public release
- **Next step:** Add a Central Portal/Sonatype target (e.g. `com.vanniktech.maven.publish` or `nmcp`) plus credentials and run one real `publish` smoke test.

- **Item:** Keyless-signing verification leg
- **Source:** `.review-2026-07/IMPLEMENTATION_NOTES.md` Group J note + stress addendum "Remaining C3"; C3 sign-off line ("`sign*` SKIPPED without a key"); session decision-state (open owner decision)
- **Why deferred:** The dev box's global `~/.gradle/gradle.properties` supplies a signing key, so the keyless SKIPPED behavior cannot be exercised there without a clean `GRADLE_USER_HOME`; it is verified by code inspection only. The with-key leg (the stricter one for the Group J change) was verified empirically, including a post-merge `.asc` spot-check.
- **Risk if left deferred through RC:** Low — the signing conditional was untouched by Group J; the residual is process assurance, not code.
- **RC verdict:** Blocks RC (as a decision: run the clean-environment leg, or explicitly accept inspection and note it in C3)
- **Owner & timing:** maintainer decision; assistant-able execution; before-tag
- **Next step:** Run `GRADLE_USER_HOME=$(mktemp -d) ./gradlew publishToMavenLocal` and confirm `Sign*` tasks report SKIPPED — or record inspection-acceptance against the C3 line.

- **Item:** Release notes incl. the `NoneForMvp` trust-model statement
- **Source:** C3 unchecked line ("Release notes state the trust model honestly…"); stress addendum "Remaining C3"; session decision-state (not yet drafted)
- **Why deferred:** Notes are naturally drafted at tag time; nothing blocks drafting now.
- **Risk if left deferred through RC:** C3 cannot be signed off without them; the statement that identity/encryption is `NoneForMvp` (trusted-LAN only) is the RC's disclosure leg for the deferred encryption milestone.
- **RC verdict:** Blocks RC
- **Owner & timing:** assistant-able draft + maintainer sign-off; before-tag
- **Next step:** Draft the `v0.6.0-rc1` notes with the trusted-LAN trust-model statement plus the C1/C2 known-caveat list.

## 5. API/spec items deferred from the 15 decisions

All 15 open decisions carry recorded answers (2026-07-04). The items below are the halves those answers deliberately postponed, plus two Group M2 implementation notes.

- **Item:** `unregisterManualPeer(peerId)`
- **Source:** `OPEN_DECISIONS_2026-07.md` #6 (option (b) landed @ d2075c0); IDN-7; `AUDIT_REPORT_2026-06.md` deferred bullet
- **Why deferred:** A public API addition locked by `P2pKit-Spec.md` during stabilization; the no-API-change half (KDoc'd until-`stop()` lifetime + `deviceName` refresh on dedupe-hit) shipped.
- **Risk if left deferred through RC:** Low — manual peers are few per session, session-scoped, and the silent name-drop is fixed; only the removal path is missing.
- **RC verdict:** Safe post-RC
- **Owner & timing:** maintainer decision at the next spec revision; assistant-able implementation
- **Next step:** Revisit alongside the next deliberate spec revision (bundle with the other API-change candidates in this section).

- **Item:** `leaveNetwork()` / provisioning lifecycle redesign (incl. the P1-27 fold-in)
- **Source:** `OPEN_DECISIONS_2026-07.md` #8 (option (c) landed: message reword + doc); `.review-2026-07/IMPLEMENTATION_NOTES.md` Group C (P1-27) and Group N (#8c notes)
- **Why deferred:** Adding `leaveNetwork()` or redefining `stopLocalNetwork` is a spec-level semantics change. P1-27 pins the adjacent gap as actual behavior: `startLocalNetwork` after parent-job cancellation returns `Started`, and the reservation sits outside parent-job cleanup (explicit `close()` only) — any lifecycle rework must sweep it.
- **Risk if left deferred through RC:** Low — join lifetime is bounded by kit lifetime; the misleading diagnostic is fixed; the P1-27 wrinkle is pinned by test + KDoc.
- **RC verdict:** Safe post-RC
- **Owner & timing:** maintainer (spec discussion), after-RC
- **Next step:** Post-RC spec discussion picks (a) `leaveNetwork()` vs (b) redefined `stopLocalNetwork`, folding the P1-27 lifecycle gap into the same rework.

- **Item:** Offer-timeout terminal-state alignment
- **Source:** `OPEN_DECISIONS_2026-07.md` #11 (option (a) landed: per-side outcomes documented); API-19
- **Why deferred:** Aligning the sender to `Rejected("timeout")` changes a terminal state apps may pattern-match on; queued for the next deliberate behavior-change window with the P2 unanswered-offer row.
- **Risk if left deferred through RC:** Low — both sides reach terminal states and the asymmetry is now documented; purely an API-clarity residual.
- **RC verdict:** Safe post-RC
- **Owner & timing:** maintainer decision at the next behavior-change window
- **Next step:** Take up option (b) with its P2 test row when a behavior-change window opens.

- **Item:** Incoming-session receive contract at replay = 0
- **Source:** `OPEN_DECISIONS_2026-07.md` #13 (option (b) landed: strengthened spec/sample guidance); SMP-8; spec §10
- **Why deferred:** A replay buffer changes late-subscriber semantics for every session — a locked-spec semantics change; the documented subscribe-before-send guidance shipped instead.
- **Risk if left deferred through RC:** Low-moderate — a documented but common trap: a fast first message from the dialer can still be missed in principle; no corruption, no hang.
- **RC verdict:** Safe post-RC
- **Owner & timing:** maintainer decision, after-RC
- **Next step:** Evaluate `replay = 1..N` as a deliberate post-RC semantics change together with the P2 loss-contract row.

- **Item:** Async/suspending kit construction
- **Source:** `docs/production-readiness.md` §11 (recorded backlog, decision #5a); ARCH-10 / catalogued B:201
- **Why deferred:** A builder-surface change locked by the spec; the RC ships the documented deferral ("construct off the main thread on Android" in the `P2pKit.create` KDoc).
- **Risk if left deferred through RC:** Low — worst case a brief first-launch stall for apps constructing on the Android main thread (one small-file read/write).
- **RC verdict:** Safe post-RC
- **Owner & timing:** assistant-able, before-stable
- **Next step:** Per §11, move the identity load behind a suspend point (lazy/async or first-`start()`), weighed against the builder-surface lock.

- **Item:** Per-operation permission model redesign
- **Source:** `OPEN_DECISIONS_2026-07.md` #7 (option (a) landed: guidance in README + the two flagged KDocs per Group N); PRM-1
- **Why deferred:** Per-operation permission sets on `P2pPermissionManager` are a public API redesign; deferred as input to the encryption-milestone API pass.
- **Risk if left deferred through RC:** Moderate-low — the fix is convention, not types: an integrator wiring the sidecar manager kit-wide would re-create the over-gating fix #9 removed; the corrected guidance mitigates, and the P2 `PermissionGateTest` contract row will pin the gate either way.
- **RC verdict:** Safe post-RC
- **Owner & timing:** maintainer, with the encryption-milestone API pass
- **Next step:** Carry option (b) into the encryption-milestone API design as its permission-granularity input.

- **Item:** `ChangeWifiState` revisit condition
- **Source:** `OPEN_DECISIONS_2026-07.md` #4 (#4a recorded); `docs/STABILIZATION_AND_RELEASE.md` C3 decision box (DECIDED, deferral assessed sound)
- **Why deferred:** The enum member has a single Android mapping today; rework would be public-API churn for a hypothetical.
- **Risk if left deferred through RC:** Negligible — pure record-keeping, now formally recorded.
- **RC verdict:** Safe post-RC
- **Owner & timing:** none until the trigger fires
- **Next step:** Revisit only if a second platform mapping for the enum member ever appears (the recorded condition).

- **Item:** Internal wrap sites still dropping the cause (M2 follow-up)
- **Source:** `.review-2026-07/IMPLEMENTATION_NOTES.md` Group M2 (candidate follow-up rider)
- **Why deferred:** M2 confined cause-preservation to the `send()`/`sendFile()` boundary and the dispatcher's FILE_OFFER wrap; parallel pre-typing wrap sites (the FILE_ACCEPT write in `P2pFileOffer.accept`, receive-side finalize wraps, `SessionManager` connect/handshake wraps at :216/:442) still drop the underlying cause — out of M2 scope.
- **Risk if left deferred through RC:** Low — diagnostics completeness only; the error types themselves are already correct.
- **RC verdict:** Safe post-RC
- **Owner & timing:** assistant-able, after-RC
- **Next step:** One small rider commit attaching the underlying cause at the listed wrap sites, mirroring the M2 mechanism.

- **Item:** Negative-`sizeBytes` refusal shape
- **Source:** `.review-2026-07/IMPLEMENTATION_NOTES.md` Group M2 (candidate register addendum)
- **Why deferred:** Decision #12a's letter passes only `CancellationException` and `P2pError` through, so `sendFile`'s `require(sizeBytes >= 0)` now surfaces as `ConnectionFailed` wrapping the `IllegalArgumentException` (pinned by test); `Errors.kt` reserves plain ISE/UOE for misuse but is silent on IAE.
- **Risk if left deferred through RC:** Low — an argument-misuse error carries a connection-shaped type, but the behavior is pinned and documented.
- **RC verdict:** Safe post-RC
- **Owner & timing:** maintainer decision at the next error-contract review
- **Next step:** Decide whether argument misuse deserves a distinct shape; if so, flip the pinning test deliberately in the same commit.

- **Item:** Encryption milestone (incl. inbound HELLO peerId verification)
- **Source:** `AUDIT_REPORT_2026-06.md` deferred list (`[PARTIALLY IMPLEMENTED @ b9f6311; remainder STILL OPEN — deliberate]`); C1 first bullet; `TODO(encryption-milestone)` in `SessionManager`; `P2PKIT_GAP_ANALYSIS_2026-07.md` P1
- **Why deferred:** Full inbound identity verification requires the encryption handshake; the interim reject-own-peerId guard shipped, and `SecurityMode.NoneForMvp` scopes the RC to trusted LANs. The gap analysis adds that the `SecurityManager` read-path seam needs a connection-ownership re-plumb (the frame reader owns the stream pre-wrap; HELLO runs outside the tunnel) — the milestone is a re-plumb, not a drop-in.
- **Risk if left deferred through RC:** Real but scoped and disclosed: identity is claim-based, so on a non-trusted LAN a same-appId peer can claim another peerId. The release notes (category 4) carry the disclosure; trusted-LAN use matches the stated model.
- **RC verdict:** Safe post-RC (before-stable for any non-trusted-network posture)
- **Owner & timing:** maintainer-scoped design phase, after-RC (the v0.9 arc in the gap analysis)
- **Next step:** Schedule the encryption milestone as its own design phase (identity keys, handshake-first bring-up, injectable `SecurityManager`), folding in the permission-granularity item above.

## 6. Campaign/documentation leftovers

- **Item:** `.review-2026-07/` untracked working directory
- **Source:** `git status` (untracked, not gitignored); contents: `BRIEF.md`, `IMPLEMENTATION_NOTES.md`, `RESUME.md`, `reports/` (18 section reports), `impl-logs/` (gate logs, negative-verification logs, flake snapshots, stress logs), plus the rejected provisional draft `CODEBASE_FINDINGS_2026-07.OPUS-PROVISIONAL.md` (superseded; the accepted register's provenance note states no content derives from it)
- **Why deferred:** Campaign working artifacts, untracked by design while the campaign ran; no post-merge disposition has been recorded.
- **Risk if left deferred through RC:** Low-moderate — one `git clean -fd` from losing `IMPLEMENTATION_NOTES.md` (the only home of several watchlist/candidate notes referenced by this register) and the evidence logs; the same exposure class decision #1 closed for the gap analysis.
- **RC verdict:** Safe post-RC (cheap to settle before the tag)
- **Owner & timing:** maintainer decision; assistant-able execution
- **Next step:** Owner picks: commit the durable artifacts (IMPLEMENTATION_NOTES + reports), archive outside the repo, or gitignore deliberately — and delete or archive the superseded provisional draft.

- **Item:** Merged audit branch retained (not deleted)
- **Source:** session decision-state (owner instruction); `git branch -a` (exists locally and on origin, fully merged at 6a05ccd)
- **Why deferred:** Owner instructed that `audit/exhaustive-review-2026-06` not be deleted yet.
- **Risk if left deferred through RC:** Negligible — a fully-merged branch; cosmetic ref clutter only.
- **RC verdict:** Safe post-RC
- **Owner & timing:** maintainer releases the hold; assistant-able cleanup
- **Next step:** When released, delete both refs (`git branch -d` + `git push origin --delete`).

- **Item:** P2/P3 test backlog (bulk: 70 P2 + 53 P3 rows)
- **Source:** `TEST_COVERAGE_PLAN_2026-07.md` §3.2/§3.3; `REMEDIATION_PLAN_2026-07.md` §4 note
- **Why deferred:** The campaign's pre-tag bar was the 32 P1 rows (all landed); P2/P3 are the strongly-recommended and hardening tiers. Named examples: the `PermissionGateTest` kit-gate contract row (PRM-1), the close-sequence pin (no `Closing` emission), the unanswered-offer terminal-pair row (API-19), the loss-contract row (SMP-8), and PRO-1 HELLO encode-side caps (decode-side landed with M4).
- **Risk if left deferred through RC:** Low per row; in aggregate the P2 tier holds the regression nets for several decided-but-doc-only contracts from category 5.
- **RC verdict:** Safe post-RC
- **Owner & timing:** assistant-able; P2 first after-RC, P3 opportunistic
- **Next step:** Schedule P2 as the first post-RC test batch (several rows pin category-5 decisions), merged with the virtual-time batch from category 3.

- **Item:** Group F follow-up — bounded accept-loop re-collect
- **Source:** `REMEDIATION_PLAN_2026-07.md` CON-3 fix text; `.review-2026-07/IMPLEMENTATION_NOTES.md` Group F
- **Why deferred:** The RC scope was deliberately minimal: an accept-loop failure is logged and inbound stays down on that transport until a later `start()`/rebind re-serves it; automatic bounded re-collect was noted as a follow-up rather than smuggled in.
- **Risk if left deferred through RC:** Low — the failure now degrades loudly instead of ending inbound silently or escalating into the kit scope; network-churn rebinds restore service.
- **RC verdict:** Safe post-RC
- **Owner & timing:** assistant-able, after-RC
- **Next step:** Design the bounded re-collect (retry budget + backoff) as its own small change with a P2-style test.

- **Item:** Group G follow-up — `ensureStarted` stopped re-check window
- **Source:** `.review-2026-07/IMPLEMENTATION_NOTES.md` Group G (candidate register addendum, Low/Medium)
- **Why deferred:** Discovered while writing P1-09; narrow trigger (observer `start()` parked + concurrent lock-less `stop()` fallback + observer eventually resuming) — a late `ensureStarted` could latch `Running` over terminal `Stopped`. Not fixed in Group G to stay within accepted scope.
- **Risk if left deferred through RC:** Low — the interleaving is narrow and the existing AUDIT-2026-06 re-check covers the hung-transport variant.
- **RC verdict:** Safe post-RC
- **Owner & timing:** assistant-able, after-RC
- **Next step:** Add a second `stopped` re-check before the success latch (after `pathObserver.start()`), with a companion KitLifecycleTest row.

- **Item:** Group I notes — sample accept-failure parity + compiler warning
- **Source:** `.review-2026-07/IMPLEMENTATION_NOTES.md` Group I
- **Why deferred:** Pre-existing, samples-only divergence (the Android sample deletes the just-created destination on `offer.accept` failure; CLI/desktop-ui leave a zero-byte claimed file, so the next same-named offer lands on "<name> (1)"), plus a pre-existing androidMain warning (nullable `hostAddress` in `joinToString`; JVM twin identical). Both out of Group I scope.
- **Risk if left deferred through RC:** Negligible — sample-harness UX and one compiler warning.
- **RC verdict:** Safe post-RC
- **Owner & timing:** assistant-able, later
- **Next step:** Align the three samples on one accept-failure cleanup behavior and map `hostAddress` non-null in both transport twins.

- **Item:** Group K note — install-provenance check semantics + stamp-lag matrix
- **Source:** `.review-2026-07/IMPLEMENTATION_NOTES.md` Group K; `TEST_COVERAGE_PLAN_2026-07.md` P2 stamp-lag row (plan :202)
- **Why deferred:** `simctl install` copies the bundle into the simulator container, so P1-31 landed as SHA-256 equality of built-vs-installed executables (stronger than the anticipated `get_app_container` path check and valid for both install routes; documented in `INTERNAL_TESTING.md` §K.3). The genuine stamp-lag path needs history mutation to simulate and stays a P2 manual-matrix row; in-place tampering was shown to self-heal.
- **Risk if left deferred through RC:** Negligible — the landed checks are stronger than specified; only the manual matrix rehearsal remains.
- **RC verdict:** Safe post-RC
- **Owner & timing:** maintainer (macOS manual), during a release-recipe rehearsal
- **Next step:** Run the P2 stamp-lag manual matrix once during a release-recipe rehearsal.

- **Item:** JmDNS goodbye observation — disposition inside decision #14's landed fix
- **Source:** `.review-2026-07/IMPLEMENTATION_NOTES.md` Group A + Group M3; `OPEN_DECISIONS_2026-07.md` #14
- **Why deferred:** An observation, not an open defect: JmDNS goodbye removals (TTL=0) deliver no TXT data, so the JVM/Android removed→`Lost` path never fires for real goodbyes — registry staleness eviction is the disappearance mechanism there, which is exactly why #14a kept heartbeat + eviction as a pair. Companion M3 note: silent (non-goodbye) departures are now cache-TTL-bound (visible beyond the old 15 s horizon until JmDNS TTL pruning); clean goodbyes still age out in ~15–17 s (pinned by the loopback test).
- **Risk if left deferred through RC:** Low — deliberate, matches the iOS daemon-backed browse semantics, and documented in the `JvmDiscoveryRecordValidationTest` KDoc; session-level connect failures remain the liveness signal for silent departures.
- **RC verdict:** Safe post-RC
- **Owner & timing:** assistant-able doc lift, after-RC
- **Next step:** Promote the goodbye + TTL-visibility semantics from test-KDoc lore into the spec/README discovery-semantics text.

- **Item:** CON-9 — iOS inbound queue parity
- **Source:** `CODEBASE_FINDINGS_2026-07.md` CON-9 (Low; explicitly "tracked separately" from SEC-1/M4); `TEST_COVERAGE_PLAN_2026-07.md` P3 row
- **Why deferred:** iOS `Channel.UNLIMITED` vs JVM/Android bounded-64 + drop-close is a parity/bounded-usage posture divergence; M4's admission control now bounds what matters downstream (16 concurrent pre-handshake setups, 64 total sessions), leaving the queue bound as residual polish.
- **Risk if left deferred through RC:** Low — post-M4 the unbounded queue feeds a bounded admission stage.
- **RC verdict:** Safe post-RC
- **Owner & timing:** assistant-able, after-RC
- **Next step:** Decide UNLIMITED-vs-bounded for iOS and land it with its P3 appleTest row.

- **Item:** B:317 — Android `refresh()` 200 ms `list()` snapshot
- **Source:** campaign brief catalogue (B:317); `REMEDIATION_PLAN_2026-07.md` §7.8; `.review-2026-07/IMPLEMENTATION_NOTES.md` Group M3 (explicitly untouched)
- **Why deferred:** A deliberate latency trade-off from the older audit; M3's heartbeat deliberately reads the in-process cache without disturbing it.
- **Risk if left deferred through RC:** Negligible — a bounded `refresh()` latency trade-off only.
- **RC verdict:** Safe post-RC
- **Owner & timing:** none until symptoms appear
- **Next step:** None; keep it annotated as deliberate wherever it resurfaces.

- **Item:** Group M4 residual notes (shutdown-window permit; constant mirror)
- **Source:** `.review-2026-07/IMPLEMENTATION_NOTES.md` Group M4
- **Why deferred:** (1) An admission permit can go unreturned if the kit scope is cancelled between `tryAcquire` and the setup coroutine's first execution — reachable only during kit shutdown, when the `SessionManager` and its `Semaphore` are terminal anyway. (2) `JvmLanAdmissionControlTest` hard-codes `PRE_HANDSHAKE_BOUND = 16` across the module boundary (documented in the test).
- **Risk if left deferred through RC:** Negligible for (1); for (2) a value change without the test update fails loudly, which is the intended guard.
- **RC verdict:** Safe post-RC
- **Owner & timing:** none for (1); assistant-able for (2) if caps ever become configurable
- **Next step:** If decision #9's configuration-surface variant is ever taken, share the constant properly at that time.

- **Item:** §5 runtime-verification residuals (Medium and below)
- **Source:** `CODEBASE_FINDINGS_2026-07.md` §5 ("Uncertain / needing a runtime check")
- **Why deferred:** A dozen catalogued items whose only remaining sub-question needs one runtime/stress/manual check each — e.g. IDN-3 stale-publish frequency, FIL-5 sink-race consequences, SES-3 park frequency, PRM-4 cancellation window, CON-13 NW dealloc timing, DOCA-18 hotspot subnet, DOCA-21 plist-wipe, IOSB-8 include-path experiment, FIL-12 slow-sink measurement, PERF-7 refresh magnitude. The Critical/High residuals in the same section were all closed during implementation (RBS-1, BLD-2, DSC-1, ARCH-1).
- **Risk if left deferred through RC:** Low — each is Medium-or-below with the mechanism already confirmed in source.
- **RC verdict:** Safe post-RC
- **Owner & timing:** mixed; several checks ride the post-hold device-day, the rest attach to P2/P3 rows
- **Next step:** Attach each named check to the P2/P3 row or manual recipe that covers it.

- **Item:** Remaining catalogued Medium/Low/Improvement findings (incl. the PROBLEMS_P2PKIT annotation pass)
- **Source:** `CODEBASE_FINDINGS_2026-07.md` §3.3–§3.5 (47 Medium / 88 Low / 96 Improvement rows, minus the landed riders); DOCB-4/DOCB-5
- **Why deferred:** The campaign's remediation bar was the Critical plus all 16 Highs (with named riders); the rest remain catalogued with proposed fixes. Verified in this sweep: `PROBLEMS_P2PKIT.md` still carries no annotation pass (zero status markers), so DOCB-4/5 — since-fixed findings presented as open, plus fix texts unsafe to follow where code moved — remain live; CLAUDE.md's "trust the newer report" note is the current mitigation.
- **Risk if left deferred through RC:** Low-moderate in aggregate; the doc-of-record staleness is the piece with real mis-steering potential for future agents.
- **RC verdict:** Safe post-RC
- **Owner & timing:** assistant-able; the annotation pass is a cheap early win after-RC
- **Next step:** Run the DOCB-1-style dated annotation pass over `PROBLEMS_P2PKIT.md` as one small doc commit; work the Medium tier opportunistically alongside adjacent code changes.

- **Item:** Gap-analysis roadmap (banner-deferred strategic items)
- **Source:** `P2PKIT_GAP_ANALYSIS_2026-07.md` (status banner, decision #1a: point-in-time; the findings register supersedes overlaps); §6 roadmap
- **Why deferred:** Strategic roadmap, not RC work: CI, consumer R8/ProGuard rules, `explicitApi()`/BCV/Dokka, SPM manifest + transport AndroidManifest, transfer resume/integrity/stall-timeout, transmitted-metadata ergonomics (P4), version-range negotiation + `PROTOCOL.md`, backoff + jitter, background-lifecycle helpers, dispatcher/scope injection, the SPI rework before any second transport, and the v0.9 security arc.
- **Risk if left deferred through RC:** None at RC; these define the v0.7 → v1.0 arc after it.
- **RC verdict:** Safe post-RC
- **Owner & timing:** maintainer prioritization; largely assistant-able execution; after-RC
- **Next step:** After the tag, turn the v0.7 "anyone can consume it" block (CI + publish target + R8 + API-stability tooling) into the next milestone plan.
