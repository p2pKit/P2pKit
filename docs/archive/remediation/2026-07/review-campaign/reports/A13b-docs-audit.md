# A13b-DOCS-audit — S14 batch b: audit & history docs review

Scope: 10 files (audit reports, hardware runbooks, evidence, LICENSE) at HEAD `870bf10`,
branch `audit/exhaustive-review-2026-06`. Read-only review; every claim below was
verified against the current tree (grep/read), not against the docs' own claims.

## 1. Per-file verdicts
| File | Lines | Verdict | Tests covering it | Test gaps (1 line) |
|---|---|---|---|---|
| AUDIT_REPORT_2026-06.md | 107 | findings: DOCB-1, DOCB-2, DOCB-3 | n/a (doc) | no automated doc-drift check (see §3) |
| PROBLEMS_P2PKIT.md | 1189 | findings: DOCB-4, DOCB-5 | n/a (doc) | n/a |
| docs/audit-evidence/README.md | 80 | clean; improvement: DOCB-I2 | n/a (doc) | n/a |
| docs/audit-evidence/dns-sd-browse.log | 9 | clean (matches README's reading; timestamps/interfaces/60 s window consistent) | n/a (artifact) | n/a |
| docs/audit-evidence/jvm-cli.log | 10 | clean (README quote matches verbatim; auto-mesh initiator consistent with smaller-peer-id rule) | n/a (artifact) | n/a |
| docs/audit-real-device-checklist.md | 147 | findings: DOCB-11 | n/a (doc) | n/a |
| docs/hardware-validation-checklist.md | 334 | findings: DOCB-6, DOCB-7; improvement: DOCB-I3 | n/a (doc) | n/a |
| docs/stabilization-stress-tests.md | 298 | clean (properly bannered "Superseded by v0.4 runbook", pinned to its historical commit window) | n/a (doc) | n/a |
| docs/v0.4-cumulative-validation-runbook.md | 978 | findings: DOCB-8, DOCB-9, DOCB-10 | n/a (doc) | no signature-string parity check vs code (§3) |
| LICENSE | 190 | clean; improvement: DOCB-I1 | n/a (legal text) | n/a |

LICENSE verification detail: complete Apache License 2.0 (header + Definitions §1
through §9 + appendix with boilerplate, LICENSE:1-190; the unfilled `[yyyy] [name]`
brackets are part of the canonical appendix instructions, not an omission). All four
published modules' POMs declare the same license — `p2p-core/build.gradle.kts:126-127`,
`p2p-transport-lan/build.gradle.kts:147-148`, `p2p-network-provisioning-android/build.gradle.kts:45`,
`p2p-network-provisioning-desktop/build.gradle.kts:45` (`"The Apache License, Version 2.0"`,
`https://www.apache.org/licenses/LICENSE-2.0.txt`) — consistent. PROBLEMS_P2PKIT.md:104
records the Apache-2.0 choice. Gap: README.md and P2pKit-Spec.md never mention the
license at all (DOCB-I1).

audit-evidence verification detail: TXT keys quoted in the README (`pid app name plat
caps pv`) exactly match `Lan.kt:45-50` (`TXT_PEER_ID`…`TXT_PROTOCOL_VERSION` — no extra
keys have been added since, so the "All LanConstants.TXT_* keys present" claim still
holds); CLI default appId `p2pkit-desktop-sample` matches `p2p-sample-desktop/.../Main.kt:80`;
the iOS fixture `IosLanDiagnosticTest.advertiseForSixtySecondsForInteropCapture` still
exists `@Ignore`d (IosLanDiagnosticTest.kt:16-25,33) and the README's "Un-@Ignore to
re-run" instruction matches the test's own header; `IosBonjour.txtRecordToMap` (IosBonjour.kt:70)
and `IosBonjourTest.kt` exist as claimed; the README's honest "Gaps in this evidence"
section remains accurate.

## 2. Findings

### DOCB-1 — AUDIT_REPORT_2026-06.md "Deferred (39)" list is heavily stale: at least 10 of its 16 deferred bullets were since implemented on this same branch, and CLAUDE.md routes every future agent to this list
- Severity: High | Confidence: Confirmed (each item re-verified against HEAD 870bf10 code, see evidence)
- File(s): AUDIT_REPORT_2026-06.md:60-86 (deferred list), CLAUDE.md ("Check here before 'fixing' something")
- Category: bug (doc — load-bearing maintenance-steering doc is wrong)
- Root cause: The report is a snapshot dated 2026-06-12; the same branch then received `b9f6311` ("feat(audit-decisions): JVM .p2pkit path, injectable permission manager, manual-peer dedup, inbound-peerId guard"), `47fe586` ("write/param timeouts, provenance fix, full publishing+signing"), `a08500a` ("close remaining deferred gaps — handshake wrap, cellular path, keep-alive/handshake tests"), and the 2026-07 remediation commits — but the deferred list was never annotated.
- Evidence (deferred bullet → current code state):
  1. Line 65 `SessionManager.kt:309` "inbound HELLO peerId is **never** verified … *Recommend:* reject inbound HELLOs claiming the local peerId": the recommended interim guard now EXISTS — `SessionManager.kt:356-358` rejects `peerHello.peerId == localPeerId.value` with `HandshakeRejected("remote announced our own peerId …")`; only the broader unverified-identity gap remains (`TODO(encryption-milestone)` at SessionManager.kt:360). "Never verified" + an already-implemented recommendation both misdescribe what is open. [CATALOGUED deferral itself is sound; the wording is stale.]
  2. Line 66 "permission manager is hardcoded to NoOp with no builder knob": knob EXISTS — `Builders.kt:81 public var permissionManager: P2pPermissionManager? = null` (+`permissionManagerOverride` at :146, platform default via `defaultPlatformPermissionManager`). Implemented by `b9f6311`; behavior reshaped again by remediation #9 (`881fb31`).
  3. Line 67 `PeerRegistry.kt:107` "mints a fresh id per call with no dedup": dedup EXISTS — `PeerRegistry.kt:118` "Dedup by (host, port, kind)" (commit `b9f6311`). Same stale claim as REMEDIATION_2026-07.md:63 (catalogued there as IDN-5) — AUDIT_REPORT echoes it as fully open.
  4. Line 68 `SessionManager.kt:171` "raw handshake-phase exceptions can still escape connect()": handshake wrap shipped in `a08500a` ("handshake wrap"); SessionManager.kt:391 comment "Already typed (HandshakeRejected / VersionMismatch…". (Campaign separately found `send()` raw exceptions — API-2 — a different method; the connect() bullet itself is stale.)
  5. Line 69 `JvmRawConnection.kt:34` "write() has no deadline": `WRITE_TIMEOUT_MILLIS` watchdog EXISTS (JvmRawConnection.kt:98-123; CLAUDE.md documents the 30 s watchdog as a required invariant; hardened again by remediation #4/`f4dd3a9`).
  6. Line 72 `IosLanDataTransport.kt:124` "`error()` in a property initializer can kill the iOS process": replaced by `ensureParameters()` + `AtomicReference` (IosLanDataTransport.kt:112-154; the code comment at :123 explicitly describes the old `error()` behavior as removed; remediation #20a).
  7. Line 75 `IosNetworkPathObserver.kt:68` "counts cellular as Satisfied": cellular-only is now reported `Unsatisfied` (IosNetworkPathObserver.kt:44-46 KDoc, `a08500a` "cellular path").
  8. Line 79 `iosApp/ContentView.swift` "no file-transfer UI (incoming offers time out invisibly)": an `incomingFiles` collector + offer handling now exists (ContentView.swift:861-1015; :902 comment says "previously nothing collected incomingFiles on iOS").
  9. Line 80 `iosApp/project.yml` "xcodegen regeneration drops the local-network Info.plist keys and the provenance build phase": keys + provenance phase are now IN the yml (project.yml:29-35 with `AUDIT-2026-06: load-bearing` comment, :72 "Check P2pKitShared XCFramework provenance").
  10. Line 81 "the path discrepancy needs a decision … I left the code as-is": decision was made — code moved to `<home>/.p2pkit` (FilePeerIdStorage.kt:11 "hidden directory"; commit `b9f6311` "JVM .p2pkit path"); P2pKit-Spec.md:955 and README both now say `.p2pkit`.
  11. Line 82 `build.gradle.kts:124` BUILD_COMMIT stamp "can lie": fixed by remediation #10 (`adca586`).
  12. Line 83 "maven-publish is on only two of four library modules; the provisioning sidecars are unpublishable": all four modules now have `maven-publish` + POM (p2p-network-provisioning-android/build.gradle.kts:4,34-36; -desktop:3,32-36; commit `47fe586`; CLAUDE.md states it too).
  13. Line 86 "`HandshakeTest`, `KeepAliveTest` … have no tests": both files EXIST (p2p-core/src/commonTest/…/internal/HandshakeTest.kt, KeepAliveTest.kt, plus HandshakeIdentityTest.kt; `a08500a` "keep-alive/handshake tests").
  Still-accurate deferred bullets: line 73 AWDL asymmetry, line 74 bind-address/interface selection (both hardware-blocked, catalogued), line 78 docs/ios-sample-app (still present, now marked deprecated per CLAUDE.md — "delete" recommendation still open), parts of line 79 (permission-banner claim unverified by me), line 81 spec-omission claims (see DOCB-3).
- Runtime impact: none directly; process impact is high — CLAUDE.md instructs every agent to consult this list before fixing, and 10+ entries now point at problems that no longer exist (wasted work, or worse: "re-fixing" a fixed area, e.g. re-adding HELLO-identity adoption that 012e49e deliberately removed). | Platforms: n/a | User-visible: no
- Failure class: none (documentation)
- Proposed fix (do NOT implement): add a dated "Status as of 2026-07" annotation block (or strikethrough per bullet) marking each deferred item Fixed-in-`<commit>` / Still-open, mirroring how REMEDIATION_2026-07.md maps finding→commit; alternatively add a banner deferring to REMEDIATION_2026-07.md + STABILIZATION_AND_RELEASE.md as the live worklist.
- Required tests: n/a (doc)

### DOCB-2 — AUDIT_REPORT C1 fix description now describes the opposite of current behavior (manual peers "adopt the remote's HELLO identity")
- Severity: Medium | Confidence: Confirmed
- File(s): AUDIT_REPORT_2026-06.md:25 (C1 row); REMEDIATION_2026-07.md:40 (#2)
- Category: bug (doc)
- Root cause: The C1 fix (June) made synthetic manual peers exempt from the peerId equality check and "adopt the remote's HELLO identity". Remediation #2 (`012e49e`, July) deliberately reversed the adoption half: "outgoing keeps dialed identity (no HELLO adoption)" with explicit `PeerOrigin` provenance. AUDIT_REPORT still presents HELLO-adoption as the shipped fix.
- Evidence: AUDIT_REPORT_2026-06.md:25 "Synthetic manual peers are now exempt from the equality check **and adopt the remote's HELLO identity**." vs REMEDIATION_2026-07.md:40 "Explicit `PeerOrigin`; outgoing keeps dialed identity (**no HELLO adoption**)" and test `ManualPeerIdentityTest.manualConnectKeepsDialedSyntheticIdentity…`.
- Runtime impact: none; an agent trusting the C1 row would misunderstand (or "restore") identity semantics that were deliberately changed. | Platforms: all | User-visible: no
- Failure class: none (documentation)
- Proposed fix: annotate the C1 row: "superseded by `012e49e` — dialed identity is kept; see REMEDIATION_2026-07.md #2".
- Required tests: n/a

### DOCB-3 — AUDIT_REPORT header/footer claims are stale or overstated: "two commits on top of main", "one commit, 33 files" review instruction, and its PROBLEMS_P2PKIT.md characterization describes already-repaired defects
- Severity: Low | Confidence: Confirmed
- File(s): AUDIT_REPORT_2026-06.md:3, :102, :96; PROBLEMS_P2PKIT.md:14, :1170-1189
- Category: bug (doc)
- Root cause: snapshot report never updated as the branch grew.
- Evidence: (a) Line 3 "two commits on top of `main`" / line 102 "Review this diff … one commit, 33 files" — the branch now has 14+ commits (git log: 870bf10..8281d97); following the line-102 instruction reviews a very different diff than described. (b) Line 96 says PROBLEMS_P2PKIT.md has "a double-counted entry (its 238 total is off by one)" and "a rejected-findings appendix that ends mid-entry" — both were repaired in commit `ce882a0` (2026-06-13): the header now reads "237 confirmed problems … de-duplicated" (PROBLEMS_P2PKIT.md:14) and the appendix ends cleanly with 8 entries + an explicit note that the blank ninth entry was removed (:1189). CLAUDE.md's "older 238-finding audit" phrasing inherits the same stale count. (c) The "Exhaustive … full coverage" framing (:1, :4) is now measurably overstated: the 2026-07 campaign confirmed ~30 new bug findings in the same tree (e.g. API-1 metadata never transmitted, API-2 send() raw exceptions, IOSB-3 run-ios-app.sh stale install) — worth a caveat note since CLAUDE.md tells agents to treat this report as the authority on what is already known.
- Runtime impact: none | Platforms: n/a | User-visible: no
- Failure class: none
- Proposed fix: update line 3/102 to name the commit range that constitutes the audit ("8281d97..9bb38df" baseline→fix), soften line 96 to past tense ("since repaired in ce882a0"), and add a one-line note that post-audit reviews found additional issues (pointer to the 2026-07 campaign reports).
- Required tests: n/a

### DOCB-4 — PROBLEMS_P2PKIT.md still presents since-fixed HIGH findings as open, including two whose "open" status would send an agent to re-fix shipped code
- Severity: Medium | Confidence: Confirmed (spot-checked against HEAD code)
- File(s): PROBLEMS_P2PKIT.md:105 (publishing "Remaining … not applied"), :156-161 (`ios-replay0-flow-late-subscribe-missed-messages`), :317-323 (`incoming-trysend-drops-sockets`), :324-330 (`missing-discovery-refresh-loop`), :391-397 (`permissions-always-noop-contract-dead`), :882 ("everything untagged is still open")
- Category: bug (doc)
- Root cause: The doc's own convention (line 882: "Entries whose fixes were already implemented in this pass are explicitly tagged FIXED below; everything untagged is still open") is now false for many entries fixed by the June audit/hardening commits — only 2 entries carry a "Status (2026-06)" annotation (:450, :521) and 8 Low entries a FIXED tag; the rest were never re-annotated.
- Evidence (entry → current code):
  - :105 "**Remaining (documented, not applied):** the `maven-publish`…plugin + POM + signing wiring" → wired on all four modules since `47fe586` (p2p-core/build.gradle.kts:126-127 Apache POM etc.). An agent following the doc would re-implement publishing.
  - :156 "NEVER subscribes to incomingFiles … iOS can never receive a file offer" → ContentView.swift:861-1015 now collects `incomingFiles` (comment :902 says exactly this history).
  - :317 `incoming-trysend-drops-sockets` → close-on-failure exists at JvmLanDataTransport.kt:156-159 ("DROPPED … — closing", AUDIT-2026-06 marker) and the Android twin.
  - :324 `missing-discovery-refresh-loop` (High: "iOS peers evicted after 15s") → `PEER_REANNOUNCE_INTERVAL_MS = 5_000` loop exists (IosLanDiscoveryTransport.kt:253, :688).
  - :391 "no builder knob to override" the permission manager → `Builders.kt:81` knob exists; the whole permission-gate area was additionally reshaped by remediation #9, so this entry's Fix guidance is doubly out of date.
  - Still-accurate open entries verified as such: `no-consumer-proguard-rules` (:310 — no consumer-rules files exist anywhere), `frame-header-version-not-validated` (:110 — FrameCodec.kt:72,110 still passes version through, by design), `blocking-sink-write-on-route-loop` (:109/:177 — no IO-dispatcher hop in FileTransferDispatcher).
- Runtime impact: none directly; risk is wasted or regressive work by future maintainers/agents. | Platforms: n/a | User-visible: no
- Failure class: none
- Proposed fix: add a banner at the top: "HISTORICAL (2026-05-29 snapshot). Statuses are not maintained; trust AUDIT_REPORT_2026-06.md and REMEDIATION_2026-07.md where they disagree. The 'everything untagged is still open' rule (line 882) no longer holds." Do not attempt per-entry re-annotation of 237 entries.
- Required tests: n/a

### DOCB-5 — PROBLEMS_P2PKIT.md contains concretely DANGEROUS-to-follow fix texts where the code has since moved
- Severity: Medium | Confidence: Confirmed
- File(s): PROBLEMS_P2PKIT.md:212-217 (`outgoing-peer-id-not-verified`), :82 (its Fixes-applied row), :521 (status note), :163-168 + :205-210 (stop() contract entries), :191-196 (`reconnect-rewrites-midstream`)
- Category: bug (doc)
- Root cause: fix prescriptions written against 2026-05 code, never reconciled with the June C1 critical and the July `PeerOrigin` redesign.
- Evidence:
  1. `outgoing-peer-id-not-verified` Fix (:217): "when expectedPeer != null assert peerHello.peerId == expectedPeer.id.value. On mismatch send an ERROR frame and throw HandshakeRejected." Applying this verbatim TODAY re-introduces AUDIT_REPORT critical C1 verbatim: a `manual-…` synthetic id can never equal the remote's persisted id, so every `registerManualPeer` connect would throw `HandshakeRejected` (AUDIT_REPORT_2026-06.md:25). Current code special-cases manual provenance via `PeerOrigin` (commit `012e49e`); neither the entry, nor the Fixes-applied row (:82 "outgoing handshake now verifies the remote's HELLO peerId matches the dialed peer"), nor the :521 status note mentions the manual-peer exemption.
  2. `kit-single-use-after-stop` (:168) and `stop-not-restartable-contract-mismatch` (:210) each offer "either (a) terminal or (b) restartable" — option (b) contradicts the contract that shipped ((a): terminal `stopped` flag, `ensureStarted` re-checks `stopped`, hardened by remediation #17/`f4dd3a9`). An agent picking (b) from this doc would break the locked P2pKit-Spec lifecycle.
  3. `reconnect-rewrites-midstream` Fix (:196): "In rearmWith … call fileTransferDispatcher.closeAll(…)" with no mention of `reopen()` — implementing closeAll alone was exactly audit critical C7 ("file transfer permanently dead after the first reconnect", AUDIT_REPORT_2026-06.md:31). The doc's prescription is the known-bad half of the final fix.
- Runtime impact: if followed: manual-IP connect 100% broken (1), spec-breaking lifecycle change (2), file transfer dead after first reconnect (3). | Platforms: all | User-visible: yes (if acted on)
- Failure class: none as-is (documentation), but the prescriptions map to real regressions
- Proposed fix: same banner as DOCB-4, with one added sentence: "Fix texts are as-of 2026-05 and several are known to be incomplete or regressive against current code (e.g. `outgoing-peer-id-not-verified`, `reconnect-rewrites-midstream`); never implement from this file."
- Required tests: n/a (the protecting tests already exist: ManualPeerIdentityTest, FileTransferFlowTest reconnect cases)

### DOCB-6 — hardware-validation-checklist.md Test 5 points the operator at a non-existent iOS incoming directory
- Severity: Medium | Confidence: Confirmed
- File(s): docs/hardware-validation-checklist.md:269; iosApp/ContentView.swift:437, :916, :928
- Category: bug (doc)
- Root cause: the checklist names the Android sample's directory scheme for the iOS side.
- Evidence: checklist:269 — "iOS's incoming directory (`~/Library/Containers/.../Documents/p2pkit-incoming/` for the iOS app …) contains a partial file that doesn't show up in the UI." The iOS sample actually auto-accepts into `Documents/P2pKitInbox/` (ContentView.swift:437 "auto-accepted into Documents/P2pKitInbox/", :916, :928 `fm.urls(for: .documentDirectory…)`). `p2pkit-incoming` is the ANDROID sample dir (P2pKitViewModel.kt:659 `File(baseDir, "p2pkit-incoming/${sanitize(session.peer.name)}")`).
- Runtime impact: an operator running Test 5's partial-file failure check inspects an empty/nonexistent folder and falsely concludes no partial file was leaked — the exact leak the step exists to catch goes undetected. This checklist is LIVE (INTERNAL_TESTING.md:3 sends operators here for "the five-test phone checklist"). | Platforms: iOS validation flow | User-visible: no (internal)
- Failure class: none (doc); masks a leak-detection step
- Proposed fix: change the path to `Documents/P2pKitInbox/` (and note the Android twin is `getExternalFilesDir/p2pkit-incoming/<sender>/`).
- Required tests: n/a

### DOCB-7 — hardware-validation-checklist.md invariant/crash framing and stage plumbing are stale (S1-era verdict flow, a non-fireable invariant named, post-e91e094 soft invariants not reflected)
- Severity: Low | Confidence: Confirmed
- File(s): docs/hardware-validation-checklist.md:231, :296-298, :326-334, :207, :235
- Category: bug (doc)
- Root cause: doc written in the S3→S1 stabilization window, never re-based; the invariant regime changed again in remediation #19 (`e91e094`).
- Evidence: (a) :231 and :296-298 name "`I-double-terminal` or `I-terminal-state` check() failure" and assert "a `check()` failure does this [crashes]… exactly what S3's hard invariants are designed to do". `I-double-terminal` is enforced as an idempotent no-op, not a check (P2pSessionImpl.kt:407 "I-double-terminal: a second call is idempotent") — it can never crash. `I-terminal-state`/`I-terminal-epoch` remain hard `check()`s (P2pSessionImpl.kt:441-447), but the SessionStore invariants now WARN in prod (`SessionStore.kt:277 if (strictInvariants) error(message)`, prod default false at :47 — remediation #19), so "assertion → crash" is no longer the main manifestation; the verdict tree ("ASSERTION FAILED — stop") keys off crashes an operator may never see. (b) :326-334 "CLEAN — proceed to S1… I'll either start S1…" — S1 landed in the v0.4 era (`3622b49`/`f84a218`); the gating flow is dead. (c) :207/:235 "`BackgroundPolicy.CloseActiveSessions` is on the v0.4 cleanup list" — stale in a v0.6 tree. Everything else in the file checked out: `p2pkit-sample.xcodeproj` (project.yml:1 `name: p2pkit-sample`), `dev.p2pkit.sample.android/.MainActivity`, Setup preset 10/1500 (MainActivity.kt:231), iOS sample has no reconnect-policy UI (no ReconnectPolicy reference in ContentView.swift → SDK default Disabled, matching :73), ZOMBIE (P2pSessionImpl.kt:507), `STUCK in Reconnecting for >30000ms` (:683 with threshold 30_000 at :715), `WARN: N sessions for peer=` (ContentView.swift:830), "has no matching session row" (:849), `markFailedAfterExhaustion` (P2pSessionImpl.kt:470).
- Runtime impact: operator watches for a crash signal that (for store invariants) can no longer occur; end-of-run verdict routes to a dead process stage. | Platforms: validation flow | User-visible: no
- Failure class: none
- Proposed fix: reword the invariant section — hard `check()` = I-terminal-state/I-terminal-epoch (still crash); SessionStore invariants surface as `WARN … SessionStore[…] INVARIANT` lines (grep `SessionStore\[`); replace "proceed to S1" with the current gate (STABILIZATION_AND_RELEASE.md sign-off); drop the v0.4-cleanup-list note.
- Required tests: n/a

### DOCB-8 — v0.4-cumulative-validation-runbook.md: reconnect-handler log signatures no longer exist in the code; two aggregate PASS criteria are impossible to satisfy
- Severity: Medium | Confidence: Confirmed
- File(s): docs/v0.4-cumulative-validation-runbook.md:359, :367-370, :386, :470, :692, :794; p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionManager.kt:536-585
- Category: bug (doc)
- Root cause: the runbook got a careful v0.5 signature refresh for the JmDNS migration (:19-31) but the reconnect-loop logging was reworked separately (now inline in SessionManager with a `reconnect: attempt=…` format) and those signatures were never refreshed.
- Evidence: runbook expects — R2:369 `Reconnect target changed for peer=f9d1f0ba on attempt N: previous=[…] new=[…]`; R2:367/E2:692 `Reconnect attempt N/5 … failed`; R2:370 `Session out-…: reconnected to iPhone on attempt N`. None of these strings exist anywhere in the tree (repo-wide grep for `Reconnect target changed` and `"Reconnect attempt` = 0 hits). Actual strings (SessionManager.kt:537-541, :562-566, :580-583): `reconnect: attempt=N/M peer=… cached=… resolved=… dialed=… source=REGISTRY|FALLBACK registryHit=… changedFromPrev=…`, `reconnect: attempt=… FAILED dialed=… reason=…`, `reconnect: attempt=… SUCCEEDED dialed=…`. Consequently R3's aggregate criterion (:470 "`Reconnect target changed` lines ≥4") and E3's (:794 "≥ 6") can NEVER be met — a fully-correct device run scores FAIL on those counters — and R2's "at least ONE of" success block survives only via its auto-mesh alternative. All other signatures in the runbook verified present and current: Android `NetworkCallback.onLost`/`DefaultNetworkCallback.onLost`/`scheduleRebind: … (debounce=…)`/`rebindNow: starting; reason=`/`rebindNow: registerService completed on fresh JmDNS`/`addServiceListener completed on fresh JmDNS`/`rebindNow: complete; boundNetwork=` (AndroidLanDiscoveryTransport.kt:697-961), `serviceResolved: pid=… no routable host in` (:547); iOS `buildListener: nw_listener_create`/`buildListener: SUCCESS port=`/`startPathMonitor: monitor started`/`rebindNow: starting/beforeListenerRebind hook complete/old listener cancelled/new listener ready/complete (port rotated…)/REBUILD FAILED/REBUILD OK but…` (IosLanDataTransport.kt:345-747), `rebind: re-attached descriptor on new listener`/`rebind: browser recreated on new listener queue` (IosLanDiscoveryTransport.kt:382,:398), `listener: accepted inbound nw_connection` (IosLanDataTransport.kt:364); core `registerSession in|out peer=… decision=… existingState=…` (SessionManager.kt:697-700), `Simultaneous-open for peer …` (:708,:717); samples `session <name> → <state>` (P2pKitViewModel.kt:1049), `auto-mesh: initiating connect to` (:387), `room: session added/removed` (:1021,:1030), `[buildInfo]` (P2pKitImpl.kt:129), iOS `[session] new id=`/`removed id=` (ContentView.swift:797,:807); pre-flight build guidance correct (XCFramework `P2pKitShared` → `assembleP2pKitSharedReleaseXCFramework` exists, `FRAMEWORK_SEARCH_PATHS` → `build/XCFrameworks/release` per project.yml:46,:59). The drift is confined to the reconnect block.
- Runtime impact: the RC hardware pass would mis-score R2/R3/E3 — this runbook is the CURRENT hardware doc (INTERNAL_TESTING.md:3 routes "v0.4 runtime-foundation hardware tests (Wi-Fi flap, hotspot switch, rebind log signatures)" here, and the hardware matrix is the known-deferred pre-RC step). An operator greps for lines that cannot appear and reports V0.4-RECONNECT as not firing. | Platforms: validation flow | User-visible: no
- Failure class: none (doc)
- Proposed fix: update the three signature shapes to the `reconnect: attempt=…` format; re-key the R3/E3 counters to `changedFromPrev=true` (semantic successor of "target changed") and `reconnect: … SUCCEEDED`; append these to the v0.5+ note's changed-lines list.
- Required tests: n/a (see §3 — signature-parity check)

### DOCB-9 — v0.4 runbook STOP-condition mechanics stale post-e91e094: SessionStore invariant violations no longer raise IllegalStateException in the field; "revert f84a218" is dead advice
- Severity: Low | Confidence: Confirmed
- File(s): docs/v0.4-cumulative-validation-runbook.md:145-146, :160, :956; p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionStore.kt:47, :251, :260, :277
- Category: bug (doc)
- Root cause: remediation #19 (`e91e094`) made SessionStore invariants warn-in-prod/throw-in-tests (`strictInvariants`); the runbook still describes pre-#19 crash behavior.
- Evidence: runbook:145-146 "`AndroidRuntime:E` catches any uncaught exceptions (including `kotlin.IllegalStateException` from SessionStore invariants)"; :160 STOP condition "`kotlin.IllegalStateException: SessionStore[...]:`". Current code: `SessionStore.kt:277 if (strictInvariants) error(message)` else loud `logger.warn`, with prod default `strictInvariants=false` (:47). The message prefix `SessionStore[$site] INVARIANT:` is retained (:251,:260) and the sample's `TailLogger.warn` forwards to logcat tag `p2pkit`, so the aggregation grep `grep -c "SessionStore\["` (:927) still detects violations — but as WARN lines, not via `AndroidRuntime:E`/FATAL; the doc's framing makes an operator wait for a crash that never comes. Also :956 "Halt; revert `f84a218` (Commit 2 only) and re-validate" — reverting a v0.4-era commit on a v0.6 tree whose invariant layer was since reworked (#19) is no longer sane remediation.
- Runtime impact: mis-triage of an invariant violation during the hardware pass; dangerous-if-followed revert instruction. | Platforms: validation flow | User-visible: no
- Failure class: none
- Proposed fix: reword the STOP condition to "`SessionStore[` INVARIANT line (WARN in prod since `e91e094`; ISE only under test-mode strictInvariants)" and replace the revert advice with "capture + report; see REMEDIATION_2026-07.md #19".
- Required tests: n/a

### DOCB-10 — v0.4 runbook minor signature/parameter drift: browser-cancel suffix, maxAttempts=5 examples vs sample preset 10/1500, JmDNS.create-failure now retried
- Severity: Low | Confidence: Confirmed
- File(s): docs/v0.4-cumulative-validation-runbook.md:278, :103-104, :293, :367, :672, :692, :719; IosLanDiscoveryTransport.kt:356; MainActivity.kt:231, :252; AndroidLanDiscoveryTransport.kt:905
- Category: bug (doc)
- Root cause: post-authoring code changes (remediation #5/#8, sample preset bump) not mirrored into the exact expected lines.
- Evidence: (a) :278 lists `[browse] rebind: cancelling old browser (wasBrowsing=true)` under "all must appear"; the actual line has no suffix — `IosLanDebug.log("browse", "rebind: cancelling old browser")` (IosLanDiscoveryTransport.kt:356; the flag lives in `wasBrowsingBeforeRebind` and is not logged there). (b) Check 4 (:103-104) example `reconnect=Enabled(maxAttempts=5, retryDelayMillis=1000)` — the Android Setup screen now presets **10/1500** (MainActivity.kt:231 "the picker preset is 10 / 1500", :252). Check 4's hedge covers itself, but R1:293 `Reconnect attempt 5/5`, R2:367 `attempt N/5`, E2:672/:692 "5/5 reconnects fail … T+~8s" bake in 5×1000 ms; at 10×1500 ms exhaustion lands ~15-18 s, invalidating E2's expected-timing row ("session iPhone → Failed | T+~8s" — Failed would arrive around/after the airplane-off trigger at T+15s). (c) E2 failure signature :719 treats any `rebindNow: JmDNS.create failed` as FAIL; since remediation #5 the actual line is `rebindNow: JmDNS.create failed; retry N/M` (AndroidLanDiscoveryTransport.kt:905) followed by a bounded retry — a transient failure that self-recovers still prints the substring, so the criterion flags designed-for recovery as failure.
- Runtime impact: operator confusion; (b) can cause a spurious E2 timing FAIL. | Platforms: validation flow | User-visible: no
- Failure class: none
- Proposed fix: drop the `(wasBrowsing=true)` suffix; parameterize attempt counts as `N/<maxAttempts>` with a note on the sample preset; requalify (c) as "FAIL only if the retry chain exhausts without a subsequent `rebindNow: complete`".
- Required tests: n/a

### DOCB-11 — audit-real-device-checklist.md gates an obsolete tag (v0.3-internal) with no superseded banner; A.4's payload spec contradicts its own steps
- Severity: Low | Confidence: Confirmed
- File(s): docs/audit-real-device-checklist.md:1, :50-54, :147
- Category: bug (doc)
- Root cause: v0.3-era (2026-05-17) checklist never bannered after the release gate moved to `docs/STABILIZATION_AND_RELEASE.md`'s A1–A12 smoke matrix (the active gate per CLAUDE.md) — unlike its sibling `stabilization-stress-tests.md`, which carries an explicit "Superseded by…" banner.
- Evidence: :1 "v0.3.0-dev real-device validation checklist"; :147 "When all … rows are PASS, the **v0.3-internal tag** is ready to cut" — the current line is v0.6-RC gated by A1–A12, so this doc's sign-off authority is dead. Internal contradiction: A.4 heading (:50 "200 KB binary + 5 MB file over hotspot") vs its own steps (:54 "pick a **≥ 10 MiB** file via the SAF picker") — neither a 200 KB binary send nor a 5 MB file appears in the steps, so the row's SHA-256 evidence is ambiguous. The rest holds up: §H/§I/§J anchors exist in INTERNAL_TESTING.md (:233, :268, :300), `docs/LAN_DIAGNOSTICS_PROTOCOL.md` exists, T1.8's NSUserDefaults-persistence claim matches `NSUserDefaultsPeerIdStorage.kt:8-13`.
- Runtime impact: an operator or agent could run a superseded gate believing it authorizes a tag. | Platforms: validation flow | User-visible: no
- Failure class: none
- Proposed fix: add a banner in the style of stabilization-stress-tests.md ("Historical v0.3 gate — superseded by STABILIZATION_AND_RELEASE.md A1–A12; recipes remain reachable via INTERNAL_TESTING §H/§I"); make the A.4 heading and steps agree.
- Required tests: n/a

## Improvements

### DOCB-I1 — README/Spec have no License section despite shipping Apache-2.0 POMs
- Category: improvement | File(s): README.md, P2pKit-Spec.md, LICENSE, four module build.gradle.kts
- The LICENSE file and all four POM `licenses{}` blocks agree on Apache-2.0, but `grep -i licen README.md P2pKit-Spec.md` finds no mention. For a to-be-published SDK, add a one-line "License: Apache-2.0" section to README (pre-RC polish; no correctness impact).

### DOCB-I2 — audit-evidence README's third proof (TXT dump) has no captured artifact behind it
- Category: improvement | File(s): docs/audit-evidence/README.md:61-74, :13-16
- The `dns-sd -L` TXT-record output is quoted inline only; the Files section lists just the two logs, so one of the three "What the evidence proves" claims rests on an unsaved capture (the README's Gaps section is honest about the missed iOS-side `-L` window but not about the JVM-side quote lacking a file). Next capture, save it as a third log alongside the others.

### DOCB-I3 — hardware-validation-checklist's Android capture filter drops all SDK transport-trace tags
- Category: improvement | File(s): docs/hardware-validation-checklist.md:34, :53, :285
- `adb logcat -s p2pkit:V` captures only the sample-logger tag; the SDK transport/frame traces log under `P2pKitJmDNS`/`P2pKitLanConn`/`P2pKitLanData`/`P2pKitFrame` (AndroidLanDiscoveryTransport.kt TAG, P2pKitViewModel.kt:276) and are silently excluded from saved logs. The checklist's own PASS/FAIL greps still work (ZOMBIE/STUCK/WARN flow through tag `p2pkit` via TailLogger), but "paste 10 lines around the first occurrence" triage will lack transport context that `docs/LAN_DIAGNOSTICS_PROTOCOL.md` and the v0.4 runbook (filter `p2pkit:* P2pKitJmDNS:* AndroidRuntime:E *:S`) rely on. Align the filter with the runbook's.

## Out-of-scope observations (defects in batch-a files, surfaced by this review — not counted in my findings)

- **CLAUDE.md** still calls PROBLEMS_P2PKIT.md "the older 238-finding audit"; the doc self-corrected to 237 in `ce882a0` (PROBLEMS_P2PKIT.md:14). One-word fix when batch a touches CLAUDE.md.
- **INTERNAL_TESTING.md:3** routes operators to both `docs/v0.4-cumulative-validation-runbook.md` and `docs/hardware-validation-checklist.md` with no precedence statement relative to STABILIZATION_AND_RELEASE.md's A1–A12 — combined with my DOCB-8/DOCB-6 this means the live pointers lead to docs with unreachable PASS criteria. Precedence line belongs in INTERNAL_TESTING (batch a).
- **REMEDIATION_2026-07.md:63** manual-peer-dedupe stale-deferral — already catalogued as IDN-5 (batch a); AUDIT_REPORT's echo of it is my DOCB-1 item 3.

## 3. Missing tests

These files are documentation; no unit tests apply. Two automatable guards would have caught most findings here:

| Invariant untested | Why it matters | Where it should live | Type | Priority |
|---|---|---|---|---|
| Runbook/checklist log-signature strings exist in source (`Reconnect target changed`, `(wasBrowsing=true)`, `kotlin.IllegalStateException: SessionStore[`…) | DOCB-8/9/10: an RC hardware pass scores false FAILs when expected lines can never be printed | small script (e.g. `scripts/check-doc-signatures.sh`) greping each doc's fenced signature lines against `src/` | manual/CI script | P2 |
| "Deferred/open" claims in AUDIT_REPORT/PROBLEMS cross-checked when a fix commit lands | DOCB-1/4/5: the load-bearing deferred list silently rotted through 5 fix commits | process rule in CLAUDE.md ("when fixing an audit item, annotate its line in AUDIT_REPORT_2026-06.md") | manual/process | P2 |

## 4. Section summary

**What this batch owns:** the project's audit history (AUDIT_REPORT_2026-06.md, PROBLEMS_P2PKIT.md), the interop evidence bundle (docs/audit-evidence/), four hardware validation runbooks/checklists spanning v0.3→v0.4 eras, and LICENSE.

**Overall health:** the *artifacts* are sound — LICENSE is a complete Apache-2.0 consistent with all four POMs; the audit-evidence logs genuinely evidence what their README claims (every quoted line, TXT key, test name, and CLI default re-verified against the tree); stabilization-stress-tests.md is a model of how to retire a runbook (explicit superseded banner). The *statuses*, however, have rotted: the tree moved through `b9f6311`/`47fe586`/`a08500a` (June "audit-decisions"/"close remaining deferred gaps" commits) and the 9-commit July remediation, and none of the status-bearing docs were re-annotated. The result: AUDIT_REPORT's load-bearing deferred list is ~10/16 stale (DOCB-1), its C1 fix description now states the opposite of shipped identity semantics (DOCB-2), PROBLEMS_P2PKIT still presents fixed HIGHs as open with three fix prescriptions that would re-introduce known criticals if followed today (DOCB-4/5), and the two LIVE hardware docs (both still routed to by INTERNAL_TESTING.md:3) contain unreachable PASS criteria (DOCB-8), a wrong iOS directory that would mask the leak it checks for (DOCB-6), and pre-`e91e094` crash expectations (DOCB-7/9).

**Top 3 risks:**
1. **A future agent trusts the deferred/open lists** (CLAUDE.md explicitly routes them there) and re-implements or reverts deliberate fixes — worst case re-introducing audit critical C1 via PROBLEMS' `outgoing-peer-id-not-verified` fix text (DOCB-5) — mitigation: banners + per-line annotations, cheap.
2. **The pre-RC hardware pass mis-scores**: R3/E3 counters keyed to a log line that no longer exists (DOCB-8) plus stale reconnect-policy timings (DOCB-10) produce false FAILs; the invariant-crash framing (DOCB-7/9) produces false confidence in the other direction. The hardware matrix is currently deferred (known), so there is time to fix the docs first.
3. **Two parallel live hardware docs** (hardware-validation-checklist's 5 tests vs the v0.4 runbook's R/E suite, plus the unbannered v0.3 checklist) with no statement of precedence relative to STABILIZATION_AND_RELEASE.md's A1–A12 — an operator can pick the wrong gate. Recommended disposition: keep the v0.4 runbook as the deep-dive companion (after DOCB-8/9/10 fixes), banner audit-real-device-checklist as historical (DOCB-11), and have INTERNAL_TESTING/STABILIZATION_AND_RELEASE state which is authoritative.

**Recommended disposition for PROBLEMS_P2PKIT.md:** historical — add a top banner deferring to AUDIT_REPORT_2026-06.md + REMEDIATION_2026-07.md and revoking its line-882 "everything untagged is still open" rule; do not attempt per-entry re-annotation of 237 entries.

**CODEBASE_REVIEW_MAP_2026-07.md accuracy:** accurate for this batch (map:317-324 lists exactly these files; its warning "PROBLEMS_P2PKIT.md — older audit, IDs/counts drifted" is correct in direction, though the drift note about counts is itself slightly stale: the doc self-corrected to 237 in `ce882a0`, and its internal severity/category/module sums now all reconcile to 237 — the deeper problem is stale open/closed statuses, not arithmetic). One nuance for the orchestrator: CLAUDE.md's phrase "the older 238-finding audit" inherits the pre-`ce882a0` count (CLAUDE.md is batch-a scope).

**Cross-batch notes (for the orchestrator, not re-reported on my side):** REMEDIATION_2026-07.md:63's stale manual-peer-dedupe deferral is catalogued as IDN-5 (batch a); AUDIT_REPORT's echo of the same claim is my DOCB-1(item 3). The campaign's ~30 new findings (API-1, API-2, IOSB-3, …) do not contradict any specific "verified ✅" claim in the evidence README, but do bound AUDIT_REPORT's "exhaustive / full coverage" self-description (noted in DOCB-3).
