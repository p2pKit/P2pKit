# A13a-DOCS-core — dev-critical documentation review

Scope: S14 batch a — 16 files: CLAUDE.md (working tree), README.md, P2pKit-Spec.md
(prose semantics only), INTERNAL_TESTING.md, docs/STABILIZATION_AND_RELEASE.md,
docs/LAN_DIAGNOSTICS_PROTOCOL.md, docs/production-readiness.md,
WORKSPACE_SYNC_DASHBOARD.md, REMEDIATION_2026-07.md, P2PKIT_GAP_ANALYSIS_2026-07.md
(identify), docs/ios-sample-app/* (6 files, deprecated template).

Status: COMPLETE — all 16 files reviewed; every load-bearing claim verified against code/build/git (read-only; no repo file modified other than this report).

Totals: 8 Medium (DOCA-2, -3, -8, -10, -13, -14, -16, -21) · 12 Low (DOCA-1, -4, -5, -6, -7, -9, -11, -12, -15, -17, -18, -19) · 1 informational identification (DOCA-20) · 4 improvements (DOCA-I1…I4) · 6 known campaign findings incorporated ([PRM-12], [IDN-5], [API-4], [SES-1], [API-14], [FIL-1]).

## 1. Per-file verdicts

| File | Lines | Verdict | Tests covering it | Test gaps (1 line) |
|---|---|---|---|---|
| CLAUDE.md (working tree) | 108 | findings: [KNOWN PRM-12], DOCA-1 | n/a (doc) | n/a |
| README.md | 417 | findings: DOCA-2, DOCA-3, DOCA-4, DOCA-5, DOCA-6, DOCA-7; improvements: DOCA-I1 | n/a (doc) | n/a |
| P2pKit-Spec.md | 1440 | findings: [KNOWN API-4, SES-1, API-14], DOCA-8, DOCA-9, DOCA-10, DOCA-11, DOCA-12, DOCA-15, DOCA-16; improvements: DOCA-I4 | n/a (doc) | n/a |
| INTERNAL_TESTING.md | 454 | findings: DOCA-13 | n/a (doc) | n/a |
| docs/STABILIZATION_AND_RELEASE.md | 218 | findings: DOCA-14; improvements: DOCA-I2, DOCA-I3 | n/a (doc) | n/a |
| docs/LAN_DIAGNOSTICS_PROTOCOL.md | 211 | findings: DOCA-18 (minor); trace tags/strings verified accurate | n/a (doc) | n/a |
| docs/production-readiness.md | 177 | findings: DOCA-17 | n/a (doc) | n/a |
| WORKSPACE_SYNC_DASHBOARD.md | 229 | findings: DOCA-13 (counts, shared), DOCA-3 (iOS-prov wording, shared); pending items verified still-pending | n/a (doc) | n/a |
| REMEDIATION_2026-07.md | 73 | findings: [KNOWN IDN-5], [KNOWN FIL-1 → :57 disposition], DOCA-19 | n/a (doc) | n/a |
| P2PKIT_GAP_ANALYSIS_2026-07.md | 197 (untracked) | identified: DOCA-20 (keep + commit, with 3 corrections) | n/a (doc) | n/a |
| docs/ios-sample-app/ContentView.swift | 86 | findings: DOCA-21a/d (no deprecation marker; orphan T1 pointer) | none (deprecated template) | n/a |
| docs/ios-sample-app/Info.plist | 48 | content correct (both LAN keys present); DOCA-21b (wiped by own project.yml usage; no marker) | none (deprecated template) | n/a |
| docs/ios-sample-app/KitController.swift | 122 | clean — exemplary honest AUDIT-2026-06 drift header; its 5 technical drift claims spot-verified plausible | none (deprecated template) | n/a |
| docs/ios-sample-app/P2pKitSampleApp.swift | 16 | findings: DOCA-21a ("Drop into a new app target" invite, no marker) | none (deprecated template) | n/a |
| docs/ios-sample-app/README.md | 26 | clean — exemplary deprecation banner; its build commands verified valid | none (deprecated template) | n/a |
| docs/ios-sample-app/project.yml | 42 | findings: DOCA-21b/c (dangerous usage steps, stale wiring, no marker) | none (deprecated template) | n/a |

## 2. Findings

### DOCA-1 — CLAUDE.md is uncommitted while the committed (HEAD) version contains a now-false publishing claim
- Severity: Low | Confidence: Confirmed
- File(s): CLAUDE.md (working tree vs HEAD, `git diff CLAUDE.md`)
- Category: bug (stale doc at HEAD / process gap)
- Root cause: The working-tree CLAUDE.md was rewritten (correctly) but never committed. HEAD's version still says: "a publishing plugin is not yet wired (see `PROBLEMS_P2PKIT.md`)" — false since the publishing/signing work (root build.gradle.kts:19 "`maven-publish` now ships on all four library modules", commit 47fe586). HEAD also lacks the v0.6/RC pointer, the known-flaky iOS test warning, the runIosSimulator command, the AUDIT_REPORT_2026-06 pointer, and the deprecation note for docs/ios-sample-app/.
- Evidence: `git diff CLAUDE.md` — HEAD line: "a publishing plugin is not yet wired (see `PROBLEMS_P2PKIT.md`)." vs build.gradle.kts:19-53 (maven-publish + signing wired). Every load-bearing claim in the WORKING-TREE version was verified against code and is correct: `jvmToolchain(17)` (all 7 build files), task names (`runIosSimulator` iosApp/build.gradle.kts:9; `testAndroidHostTest` via `withHostTest{}` p2p-network-provisioning-android/build.gradle.kts:15; `assembleP2pKitSharedXCFramework` p2p-transport-lan/build.gradle.kts:13), test classes (SessionFlowTest/FileTransferFlowTest exist at the stated package), fakes (4 files in testfixtures/), `WRITE_TIMEOUT_MILLIS` in Jvm+Android+IosRawConnection, cellular prohibition (IosLanDataTransport.kt:50-118), project.yml plist keys (iosApp/project.yml:34-36), frame types (Frame.kt:53-69 — all 13), magic PP2K/header 36 (ProtocolConstants.kt:7-16), limits 4 MiB/8 MiB/64 KiB (ProtocolConstants.kt:19-33), trace tags (JvmLanDiag.kt, FrameTrace.kt, IosLanDebug.kt, Main.kt:86-100), markers (V0.4-RECONNECT, V0.4-D-ANDROID-NUDGE, AUDIT-2026-06 all present), audit counts (AUDIT_REPORT_2026-06.md:11 — 7/71/290=368; :21 "all 7 fixed"; :35 "32 fixed, 39 deferred"), VERSION_NAME=0.6.0 (gradle.properties:10).
- Runtime impact: Any agent/tool reading CLAUDE.md from a fresh checkout of HEAD (e.g. CI, a worktree, another clone) gets actively wrong publishing guidance and misses the RC-gate pointer. | Platforms: n/a | User-visible: no
- Failure class: none (doc)
- Proposed fix (do NOT implement): commit the working-tree CLAUDE.md (it is strictly more accurate than HEAD). Fold the PRM-12 wording fix (below) into the same commit.
- Required tests: n/a

Also in CLAUDE.md: [KNOWN PRM-12] — "iOS provisioning is permanently `Unsupported` (Apple policy)" (module-structure bullet, unchanged between HEAD and working tree) is imprecise: manual-IP provisioning ships via `iosManualIp()` (IosManualNetworkProvisioningManager.kt:138); only hotspot-host/Wi-Fi-join are Unsupported.

### DOCA-8 — Spec §13.4 receive-path caps are stale: the 16 MiB aggregate pending-bytes session-closing cap is undocumented
- Severity: Medium | Confidence: Confirmed
- File(s): P2pKit-Spec.md:838 (§13.4 "Receive-path caps (session-closing)")
- Category: bug (spec/wire-contract drift)
- Root cause: Audit fix #12 (commit 6de50db, 2026-07) added `MAX_TOTAL_PENDING_BYTES = 16 MiB` — a new session-closing protocol rule — after the spec's "Last updated: 2026-06-12"; §13.4 was never amended.
- Evidence: Spec §13.4 lists exactly three session-closing receive caps (8 MiB frame, `total_chunks ≤ 1024`, "at most 256 concurrently-incomplete multi-chunk messages") and states "conforming senders must chunk a ≤ 4 MiB message into ≤ 1024 chunks". Code: ProtocolConstants.kt:51-60 — "Aggregate cap on buffered chunk bytes across ALL concurrently-pending partial messages … 16 MiB … Exceeding it closes the session (AUDIT-2026-06 fix)." A wire-conforming third-party sender that interleaves chunks of multiple ≤ 4 MiB messages (explicitly supported by the frame format — reassembly is keyed by `message_id`, and §13.4 permits up to 256 concurrent partials ≈ 1 GiB) is killed at 16 MiB aggregate — far below what §13.4 promises is tolerated. (Fix #11's receiver-side single-frame 4 MiB enforcement is likewise unmentioned, though a conforming sender can't hit it since `send()` caps at 4 MiB.)
- Runtime impact: none for the SDK talking to itself (P2pKitImpl serializes one message's chunks back-to-back); real for any future/interop implementation written against the spec. The spec is the locked contract — receivers now enforce more than it says. | Platforms: all | User-visible: interop only
- Failure class: none (doc) — masks a potential interop protocol break
- Proposed fix: amend §13.4 with the aggregate 16 MiB budget and state the practical rule ("senders must not exceed 16 MiB of interleaved incomplete message bytes; the SDK's own sender never interleaves DATA messages").
- Required tests: n/a (doc)

### DOCA-9 — Spec §9.1 PeerId persistence backends contradict §16.2 and the code
- Severity: Low | Confidence: Confirmed
- File(s): P2pKit-Spec.md:532 (§9.1) vs P2pKit-Spec.md:954-960 (§16.2)
- Category: bug (self-contradictory doc)
- Root cause: §9.1 kept its v0.1 design sketch after the real implementation landed.
- Evidence: §9.1: "persisted (Android: `DataStore` or `SharedPreferences`; JVM: file under user app data)". §16.2 (same doc): Android writes to `<filesDir>/p2pkit/<sanitized-appId>/peer-id`. Code: p2p-core/src/androidMain/…/FilePeerIdStorage.kt:14 (plain file, no DataStore/SharedPreferences anywhere); iOS uses NSUserDefaults (§5.1 documents that correctly).
- Runtime impact: adopters auditing storage locations (e.g. for backup rules / data-privacy reviews) are pointed at the wrong Android storage mechanism. | Platforms: Android | User-visible: no
- Failure class: none (doc)
- Proposed fix: align §9.1 with §16.2 (file-based on both JVM and Android; NSUserDefaults on iOS).
- Required tests: n/a

### DOCA-10 — Spec asserts iOS `networkProvisioning` "will continue to throw `Unsupported` … in every future version" — contradicted by shipped `iosManualIp()`
- Severity: Medium | Confidence: Confirmed
- File(s): P2pKit-Spec.md:99 (§5.1), P2pKit-Spec.md:1316 (§21.3 iOS row "never — Apple policy; always `Unsupported`")
- Category: bug (stale doc / contract drift)
- Root cause: Spec-level counterpart of [KNOWN PRM-12]: the manual-IP iOS provisioning manager shipped without amending the two blanket "never on iOS" statements.
- Evidence: Spec §5.1:99 "`P2pKit.networkProvisioning` will continue to throw `Unsupported` on iOS in every future version." vs IosManualNetworkProvisioningManager.kt:34-41 (manual-IP fallback: `getManualConnectionInfo` / `createManualPeer` fully functional on iOS), :138 `NetworkProvisioningConfigBuilder.iosManualIp()`; used in the maintained sample (iosApp/ContentView.swift:659). Hotspot/join correctly remain Unsupported.
- Runtime impact: a spec-conforming adopter will not wire `iosManualIp()` and loses the only mDNS-blocked fallback on iOS; the spec also now under-specifies a shipped public API surface (the locked contract omits a shipped feature). | Platforms: iOS | User-visible: yes
- Failure class: none (doc)
- Proposed fix: amend §5.1/§21.3 to "hotspot host + Wi-Fi join: permanently Unsupported (Apple policy); manual-IP fallback ships via `iosManualIp()` in `:p2p-transport-lan`" and add the iOS row to §20's provisioning section.
- Required tests: n/a

### DOCA-11 — Spec §7.2 documents `connect(peer)` as throwing `P2pError.PermissionMissing`; connect() has no permission gate
- Severity: Low | Confidence: Confirmed
- File(s): P2pKit-Spec.md:233-235 (§7.2 connect KDoc)
- Category: bug (doc/behavior mismatch)
- Root cause: The permission gate only ever ran in `startAdvertising()`/`startDiscovery()` (`ensurePermissions`); the spec's connect() throws-list includes it anyway.
- Evidence: Spec §7.2: "Throws P2pError.NoTransportAvailable, P2pError.ConnectionFailed, **P2pError.PermissionMissing**, or P2pError.TransportStartFailed". Code: P2pKitImpl.kt:384-393 — `connect` calls only `ensureStarted()`; the sole `PermissionMissing` throw site is `ensurePermissions` (P2pKitImpl.kt:499), which `connect` never calls. §15.2 correctly scopes the gate to startAdvertising/startDiscovery — §7.2 contradicts it.
- Runtime impact: adopters write dead catch branches / expect a gate that doesn't exist (relevant if a future transport does require runtime perms for dialing). | Platforms: all | User-visible: no
- Failure class: none (doc)
- Proposed fix: drop `PermissionMissing` from §7.2's connect() throws-list (or implement the gate — [API-CHANGE]-free either way; doc fix is the right call since §15.2 is the normative rule).
- Required tests: n/a

### DOCA-12 — Spec prose nits: dangling "retention" reference, §16.1 mechanism fiction, manual-peer eviction exemption undocumented, MB/MiB
- Severity: Low | Confidence: Confirmed
- File(s): P2pKit-Spec.md:670 (§10), P2pKit-Spec.md:935 (§16.1), P2pKit-Spec.md:718 (§11.2), P2pKit-Spec.md:608 (§9.4), P2pKit-Spec.md:835 (§13.4), P2pKit-Spec.md:5
- Category: bug (grouped minor doc inaccuracies)
- Root cause / Evidence (one line each):
  - §10:670 "removed from `sessions` (after retention or immediately, see below)" — no retention concept is defined anywhere below or elsewhere; dangling reference.
  - §16.1:935 "Calling either method posts to an internal channel; a worker coroutine applies the configured policy" — actual implementation applies the policy inline/directly (P2pKitImpl.kt:398-415: `scope.launch { stopAdvertising… }` + synchronous `sessionManager.applyBackgroundPolicy`); observable semantics (non-suspending, fire-and-forget) are right, the described mechanism doesn't exist.
  - §11.2:718 "A peer is evicted … after `staleTimeoutMillis` (default 15s)" — manual peers are exempt (PeerRegistry.kt:102 `tracked.isManual || now - … <= staleTimeoutMillis`); the spec never states manual peers are pinned. (Default 15 s itself verified: PeerRegistry.kt:169.)
  - §9.4:608 "4 MB" and §13.4:835 "64 KB" — actual constants are binary units (4 MiB = 4·1024·1024, 64 KiB; ProtocolConstants.kt:19,22). CLAUDE.md/README use MiB/KiB correctly.
  - Header:5 "Last updated: 2026-06-12" predates the July remediation commits that changed spec-relevant behavior (see DOCA-8, [KNOWN API-14]) — the "living contract, amended in place" promise (:4) is currently unmet.
- Runtime impact: none directly; erodes trust in the contract doc. | Platforms: n/a | User-visible: no
- Failure class: none (doc)
- Proposed fix: one editorial pass fixing the five items; bump "Last updated".
- Required tests: n/a

Spec claims verified as ACCURATE (no finding): keep-alive defaults 10 s/30 s (Config.kt:11-13); unknown packet type skipped+warn without closing (FrameReader.kt:69-75, comment cites §17); reassembly timeout 60 s (ProtocolConstants.kt:63); MAX_PENDING_REASSEMBLIES 256 / MAX_TOTAL_CHUNKS 1024 (ProtocolConstants.kt:41,49); `incoming` SharedFlow replay=0/buffer=64/SUSPEND (P2pSessionImpl.kt:131-135); connect() idempotency states {Connecting,Handshaking,Connected,Reconnecting} (SessionStore.kt:298-303); §16.2 background/foreground semantics incl. "stays Running" (P2pKitImpl.kt:398-420); §15.2 permission-gate rule still mechanically true post-#9 (gate exists at P2pKitImpl.kt:499; LAN just requires no runtime perms); stale-timeout 15 s; §7.6 sink ownership ("caller closes sink") matches P2pFileOffer.kt:33-37; refresh() ~3 s cadence (SessionManager.kt:613); heartbeat-dedupe claim for `peers` StateFlow (map-derived + StateFlow equality dedupe).

### DOCA-2 — README describes shipped network provisioning in the future tense (self-contradictory)
- Severity: Medium | Confidence: Confirmed
- File(s): README.md:44, README.md:219, README.md:229-233, README.md:249
- Category: bug (stale/self-contradictory doc)
- Root cause: Sections written in the v0.1 era were never updated when the provisioning sidecars shipped (v0.2.1).
- Evidence: README.md:44 "**Network provisioning** is a planned v0.2 sidecar."; README.md:219 "In v0.1, `P2pKit.networkProvisioning` is implemented by an `UnsupportedNetworkProvisioningManager` stub … when v0.2 replaces the stub"; README.md:233 "v0.2 **will add** a manual-IP fallback through `networkProvisioning.createManualPeer(host, port)`."; README.md:249 architecture diagram "(v0.2 sidecar — Unsupported stub in v0.1)". All contradict README.md:274-275 (same file), which documents `:p2p-network-provisioning-desktop` / `-android` as shipped v0.2.1 modules, and the code (both modules exist and publish).
- Runtime impact: An adopter reading top-to-bottom concludes manual-IP fallback / hotspot provisioning are unavailable; "Recommended connection flow" (:229-233) tells users a shipped mDNS-blocked fallback doesn't exist yet. | Platforms: all | User-visible: yes (adopter-facing)
- Failure class: none (doc)
- Proposed fix: rewrite the three future-tense passages to present tense with the `networkProvisioning { jvm() / android(ctx) / iosManualIp() }` wiring; fix the diagram annotation.
- Required tests: n/a

### DOCA-3 — README claims iOS `networkProvisioning` "will continue to throw `Unsupported`" — contradicted by shipped `iosManualIp()`
- Severity: Medium | Confidence: Confirmed
- File(s): README.md:52, README.md:63, README.md:329-330 ("network provisioning (never supported on iOS)"); same wording also at INTERNAL_TESTING.md:194 ("iOS Network Provisioning is **never planned**") and WORKSPACE_SYNC_DASHBOARD.md:202 ("This will *never* be implemented") — fix all instances together
- Category: bug (stale doc, feature under-advertised)
- Root cause: README predates the iOS manual-IP provisioning manager; related to [KNOWN PRM-12] (which catalogued the CLAUDE.md wording) — this is the README instance, plus the Modules section omits the iOS manager entirely.
- Evidence: README.md:63 "iOS Network Provisioning is **not** planned and will remain `Unsupported` indefinitely. … The `networkProvisioning` accessor on `P2pKit` will continue to throw `Unsupported` on iOS." vs p2p-transport-lan/src/appleMain/…/IosManualNetworkProvisioningManager.kt:34-41 ("The single feature this manager DOES expose is **manual-IP fallback**"), :138 `public fun NetworkProvisioningConfigBuilder.iosManualIp()`, used by iosApp/ContentView.swift:659. Only hotspot/join return Unsupported (correct per Apple policy); `getManualConnectionInfo()`/`createManualPeer()` work.
- Runtime impact: iOS adopters on mDNS-blocked networks are told there is no fallback when one ships; the maintained iOS sample itself uses it. | Platforms: iOS | User-visible: yes
- Failure class: none (doc)
- Proposed fix: platform-support table row → "manual-IP fallback via `iosManualIp()`; hotspot/join permanently Unsupported (Apple policy)"; rewrite :63; add the iOS manager to §Modules (it lives in `:p2p-transport-lan`, not a sidecar module — worth stating).
- Required tests: n/a

### DOCA-4 — README test counts are stale (134/17/20 vs actual 161/18/29)
- Severity: Low | Confidence: Confirmed
- File(s): README.md:381
- Category: bug (stale doc)
- Root cause: Counts not updated after the 2026-06/07 audit-remediation test waves (ReassemblerTest additions, ManualPeerIdentityTest, PermissionGateTest, SessionStoreInvariantTest, KitLifecycleTest, CloseSemanticsTest, IosRawConnectionTest, fd-leak loopback test…).
- Evidence: README.md:381 "**134 unit + integration tests** in `:p2p-core` (122 common + 12 JVM-only), 17 in `:p2p-transport-lan:jvmTest`, 20 in `:p2p-transport-lan:iosSimulatorArm64Test`". Actual `@Test` counts: p2p-core commonTest 149 + jvmTest 12 = 161; p2p-transport-lan jvmTest 18; appleTest 29. REMEDIATION_2026-07.md:19-24 corroborates (149 on iosSimulatorArm64; 29 iOS-transport tests).
- Runtime impact: understates coverage; a release reviewer diffing "expected vs ran" against README gets false alarm/false comfort. | Platforms: n/a | User-visible: no
- Failure class: none (doc)
- Proposed fix: update counts or replace exact numbers with an order-of-magnitude statement + the gradle commands.
- Required tests: n/a

### DOCA-5 — README claims the iOS sample provides a "Network entitlement"; no entitlement exists or is needed
- Severity: Low | Confidence: Confirmed
- File(s): README.md:55, README.md:391, README.md:403
- Category: bug (inaccurate doc)
- Root cause: Copied from an early plan; the shipped `iosApp/project.yml` configures no entitlements (Bonjour browse/advertise via NWBrowser/NWListener needs only the two Info.plist keys).
- Evidence: README.md:55 "provides the required `Info.plist` entries (`NSLocalNetworkUsageDescription`, `NSBonjourServices`) and Network entitlement." `grep -n entitlement iosApp/project.yml docs/ios-sample-app/project.yml` → no matches; iosApp/project.yml:22-43 has no `entitlements:` block.
- Runtime impact: an adopter integrating the SDK may hunt for / add an unnecessary entitlement (`com.apple.developer.networking.multicast` requires an Apple grant — a real time sink). | Platforms: iOS | User-visible: yes (adopter-facing)
- Failure class: none (doc)
- Proposed fix: drop "and Network entitlement" (3 places), state explicitly that no entitlement is required for `_p2pkit._tcp` Bonjour.
- Required tests: n/a

### DOCA-6 — README architecture diagram lists "ACK" as an implemented protocol feature; ACK is decode-only and never sent
- Severity: Low | Confidence: Confirmed
- File(s): README.md:256
- Category: bug (doc overstates behavior)
- Root cause: ACK frame type is reserved in the wire protocol but no code path sends one or sets NEEDS_ACK.
- Evidence: README.md:256 "Protocol Layer ← framing, chunking, ACK, keepalive". Code: `PacketType.ACK` decoded at DefaultP2pProtocol.kt:167 and handled at P2pSessionImpl.kt:527, but `grep -rn "needsAck = true|PacketType.ACK"` over commonMain shows no sender; Chunker.kt:72 supports the flag but no caller passes `needsAck=true`.
- Runtime impact: adopters may assume per-message delivery acknowledgement exists (it doesn't; delivery is TCP-level only). | Platforms: all | User-visible: yes (expectation-setting)
- Failure class: none (doc)
- Proposed fix: drop "ACK" from the diagram or annotate "(reserved, not yet used)".
- Required tests: n/a

### DOCA-7 — README "Status" changelog ends at early v0.6; the entire 2026-06 audit/hardening line is absent
- Severity: Low | Confidence: Confirmed
- File(s): README.md:405
- Category: bug (stale doc)
- Root cause: Status bullet for v0.6-dev written before the audit branch work.
- Evidence: README.md:405 describes v0.6-dev as only "iOS LAN hardening — cellular prohibition (issue #11, d6bf1e4)" + "JVM LAN loopback tests stabilized (issue #12)". The last ~15 commits on this branch (47fe586 publishing+signing+RC checklist, 742c071/5568355 trace layers, adca586…f4dd3a9 audit waves, 870bf10 remediation report) are all v0.6 content and unmentioned. README:5 "v0.6-dev" is otherwise consistent with VERSION_NAME=0.6.0.
- Runtime impact: changelog consumers (and the RC notes derived from it) under-describe v0.6. | Platforms: n/a | User-visible: yes at release time
- Failure class: none (doc)
- Proposed fix: extend the v0.6-dev bullet (audit remediation, write-watchdog parity, publishing/signing, diagnostics layers) before tagging RC.
- Required tests: n/a

### DOCA-13 — INTERNAL_TESTING.md test counts stale and iOS suite "all green" expectation contradicts the documented known-flaky failures
- Severity: Medium | Confidence: Confirmed
- File(s): INTERNAL_TESTING.md:50, :202, :347, :366-371, :438, :444; also WORKSPACE_SYNC_DASHBOARD.md:38 ("134 unique test methods as of v0.6"), :196 and :209 ("the appleTest suite has since grown to 20 tests") — same stale numbers, fix together
- Category: bug (stale + dangerous-to-follow release instructions)
- Root cause: Doc predates the 2026-06/07 remediation test waves and the known-flaky classification of the two simulator churn tests.
- Evidence:
  - :202 "Expected: all green — the `appleTest` suite is now **20 test methods** across `IosLanLoopbackTest` …, `IosBonjourTest`, `IosLanLifecycleTest`, and `IosLanDiagnosticTest`" and :366 "all 20 `appleTest` methods green (four classes)" and :444 "passes — all 20 cases green". Actual: **29 @Test across six classes** (IosBonjourTest 9, AnnounceCacheReconcileTest 7, IosLanLifecycleTest 7, IosLanLoopbackTest 3, IosRawConnectionTest 2, IosLanDiagnosticTest 1), and per REMEDIATION_2026-07.md:24-26 / docs/STABILIZATION_AND_RELEASE.md C2 **two of them are expected to fail on the simulator** (`peerLostEventFiresWhenPeerStops`, `advertiseStopRestartProducesObservablePeerChurn`).
  - :50 and :438 "`:p2p-core` … **134 unique test methods**" — actual 161 (149 commonTest + 12 jvmTest `@Test`).
  - :438 "`:p2p-transport-lan:jvmTest` runs **17** (14 `HostSelectorTest` + the 3 loopback tests)" — actual 18 (JvmLanLoopbackTest now has 4, incl. the new `remoteDisconnectClosesLocalSocketFd`).
  - :347 "**7 commonTest cases** in `FileTransferFlowTest`" — actual 9 (remediation added 2). (`FileTransferJvmTest` 3 ✓; provisioning counts 6/15 ✓ still accurate.)
- Runtime impact: the §4 release checklist is the pre-tag runbook. A runner sees 29 tests with 2 failures where the doc demands "all 20 green": either they fail the release on documented-expected failures, or — worse — they "fix" the two flaky tests by masking (the exact remedy CLAUDE.md forbids). | Platforms: n/a | User-visible: no
- Failure class: none (doc) — risk of masked tests / blocked release
- Proposed fix: update all counts; change the iOS expectation to "29 tests; exactly the 2 known-flaky churn tests may fail on the simulator (see STABILIZATION C2 / smoke A4) — any OTHER failure is a regression"; cross-link §4 to docs/STABILIZATION_AND_RELEASE.md as the authoritative RC gate.
- Required tests: n/a

### DOCA-14 — RC gate (STABILIZATION_AND_RELEASE.md) sign-off checklist omits campaign-known open RC decisions; header date stale
- Severity: Medium | Confidence: Confirmed (metadata-drop verified in code; stale-install item cited from campaign context)
- File(s): docs/STABILIZATION_AND_RELEASE.md:204-218 (C3), :5 ("Updated: 2026-06-13")
- Category: bug (release instructions incomplete relative to known state)
- Root cause: C3 was written before the review campaign surfaced release-relevant defects; the doc is the *active gate* so omissions here directly shape the RC.
- Evidence: (a) `P2pMessage.Text/Binary.metadata` is silently dropped on the wire — no protocol code reads `.metadata` (grep over `protocol/` = zero hits) and the receiver reconstructs with defaults (Reassembler.kt:183-184: `P2pMessage.Text(bytes.decodeToString())` / `P2pMessage.Binary(bytes)`); public KDoc (P2pMessage.kt:15-24 "optional string metadata") and spec §9.4 promise the field with no non-transmission caveat. The campaign holds this as pending an RC decision — C3 has no box to make/record that decision, so an RC can tag with a silently-lossy public API field undecided. (b) The S12-confirmed stale-app-install defect in the iOS run script means Part A smoke rows exercised via the sample can test a stale binary; Part A's preamble has no "verify on-device build identity (stamp) matches HEAD" step even though the v0.4 build-identity stamping exists for exactly this. (c) Header says "Updated: 2026-06-13" but the file's last edit is adca586 (2026-07-03) — the freshness signal on the gate doc is wrong.
- Runtime impact: gate followers can legitimately tag an RC with the metadata decision unmade and smoke rows run against stale binaries. | Platforms: all | User-visible: at release
- Failure class: none (doc)
- Proposed fix: add two C3 boxes ("metadata wire-drop: decide drop-and-document vs implement-before-RC, update spec §9.4 + KDoc accordingly", "device smoke runs confirm in-app build stamp == HEAD"); refresh the Updated date on each edit.
- Required tests: n/a
- Otherwise verified: Part B matches the build (signing props build.gradle.kts:45-46, conditional signing, four modules, no remote repo — consistent with CLAUDE.md); C2 matches reality (29-test suite, 2 expected churn failures); C3's "green except the two C2 churn tests" is the CORRECT expectation that INTERNAL_TESTING.md contradicts (DOCA-13); provenance-guard recipe's task names and script path exist; C1 deferred list matches the BRIEF's catalogued decisions; resolved-items list confirmed (HandshakeIdentityTest/KeepAliveTest exist).

### DOCA-15 — Spec never states that `P2pMessage.metadata` is not transmitted
- Severity: Low | Confidence: Confirmed (builds on the campaign's known metadata wire-drop finding — code side catalogued elsewhere; this is the contract-doc side)
- File(s): P2pKit-Spec.md:584-608 (§9.4)
- Category: bug (spec under-specifies; adopter-visible data loss undocumented)
- Root cause: §9.4 defines `metadata: Map<String, String>` on both message types and §13 defines the frame layout with no metadata field; nowhere does the spec (or the KDoc) say the map is local-only/dropped.
- Evidence: §9.4 type sketch includes `metadata` (spec:590, :598); frame layout §13.2 has no metadata slot; implementation drops it (Reassembler.kt:183-184, no `.metadata` reads in the protocol layer).
- Runtime impact: a spec-following adopter attaches routing/content-type metadata and silently loses it cross-device. | Platforms: all | User-visible: yes
- Failure class: data loss (of a documented-looking field) — doc-side
- Proposed fix: whatever the RC decision (DOCA-14), amend §9.4 with explicit semantics ("not transmitted in protocol v1" or the new wire mapping).
- Required tests: if "transmit" is chosen: round-trip test asserting metadata equality; if "drop": KDoc/spec statement + a test asserting the receiver's metadata is empty (pinning the contract).

### DOCA-16 — Spec §10 documents `close()` as `Connected → Closing → Closed`; the session never enters `Closing`
- Severity: Medium | Confidence: Confirmed
- File(s): P2pKit-Spec.md:669 (§10)
- Category: bug (spec/behavior mismatch in the locked contract)
- Root cause: `ConnectionState.Closing` is a reserved enum value that no code path assigns; the spec documents it as a real transition.
- Evidence: Spec §10: "`close()` transitions: `Connected → Closing → Closed`." Code: zero assignments of `ConnectionState.Closing` anywhere in commonMain (only comparisons, e.g. P2pSessionImpl.kt:319 guard, :662 comment); close() flips state directly to `Closed` (P2pSessionImpl.kt:289 area). docs/production-readiness.md:136 states it correctly: "`Closing` is reserved in `ConnectionState` but never entered" — the two docs contradict each other and the spec is the wrong one.
- Runtime impact: adopter code that awaits `Closing` (e.g. `state.first { it == Closing }` for close-progress UI) suspends forever; `when`-branches on it are dead code. Same drift family as [KNOWN SES-1] (§16.3 Failed→Reconnecting prose): the spec's session state-machine prose has multiple transitions that don't match the shipped machine. | Platforms: all | User-visible: yes (adopter-visible)
- Failure class: hang (in adopter code following the spec)
- Proposed fix: amend §10 to "close() transitions directly to Closed; `Closing` is reserved and currently never emitted" (or start emitting it — [API-CHANGE]-free behavior change, but the doc fix matches production-readiness and reality).
- Required tests: a commonTest pinning the close() state sequence (Connected → Closed, no intermediate) so the contract stays deliberate.

### DOCA-17 — production-readiness.md §8 still describes shipped PeerId persistence as a future "v0.4" item; §4 status note names a nonexistent signal
- Severity: Low | Confidence: Confirmed
- File(s): docs/production-readiness.md:140-147 (§8), :71-74 (§4 status note)
- Category: bug (stale doc)
- Root cause: The 2026-06 status-note pass annotated §2-§6 but skipped §8; §4's note used an approximate name.
- Evidence: §8: "**v0.4 (not in this milestone).** Optional persistent `localPeerId` in `SharedPreferences` / `NSUserDefaults`…" — persistence shipped in v0.2 Task 1, file-backed on JVM/Android (FilePeerIdStorage.kt) and NSUserDefaults on iOS (NSUserDefaultsPeerIdStorage.kt); not SharedPreferences. §4 note: "SessionManager reacts via `pathSatisfiedSignal`" — actual mechanism is `pathSatisfiedGeneration` (SessionManager.kt:144).
- Runtime impact: readers of the hardening design doc get wrong current-state info (persistence "future", wrong symbol name for code navigation). | Platforms: n/a | User-visible: no
- Failure class: none (doc)
- Proposed fix: add a §8 status note ("shipped v0.2, file-backed + NSUserDefaults"); correct the §4 symbol name.
- Required tests: n/a
- Otherwise verified: §3/§4 "implemented in v0.4" claims check out (DataTransport.start(): Result<Unit> in spec+code; NetworkPathObserver impls exist); §2/§5/§6 "still proposed" confirmed (no backoff fields, no IosBackgroundTaskGuard/P2pKitForegroundService anywhere); §7's "Closing never entered" is CORRECT (see DOCA-16).

### DOCA-18 — LAN_DIAGNOSTICS_PROTOCOL.md: wrong expected subnet for LocalOnlyHotspot; unescaped pipes break the capture table
- Severity: Low | Confidence: Confirmed (subnet: cross-doc + platform convention; would be settled by one §H run's logs)
- File(s): docs/LAN_DIAGNOSTICS_PROTOCOL.md:123, :27-28
- Category: bug (misleading diagnostic expectation; rendering defect)
- Root cause / Evidence: (a) :123 "the `bind`/`active` lines showing the hotspot subnet (often `192.168.49.x` for LocalOnlyHotspot)" — 192.168.49.x is the Wi-Fi **Direct** group-owner subnet; `LocalOnlyHotspot` conventionally hands out 192.168.43.x, which is what the sibling recipes document (INTERNAL_TESTING.md:244 "host(s): 192.168.43.1", :278 "typically `192.168.43.x`"). A tester grepping logs for 49.x would wrongly fail the check. (b) :27-28 embed literal `|` inside markdown table cells ("`… | tee jvm-trace.log`") — the pipes split the cells, so the rendered capture commands are garbled exactly where a field tester reads them.
- Runtime impact: mis-evaluated Issue-#2D hotspot runs; broken rendering of the capture cheat table. | Platforms: Android (doc) | User-visible: no
- Failure class: none (doc)
- Proposed fix: change :123 to 192.168.43.x (with "may vary by OEM/API level"); escape the pipes (`\|`) or move commands out of the table.
- Required tests: n/a
- Otherwise verified (extensively — this doc is accurate): all trace strings exist verbatim in code — `P2pKitFRAME` default sink (FrameTrace.kt:32), Android `P2pKitFrame` logcat tag (P2pKitViewModel.kt:276), `AndroidLanDiag.traceFrames` (AndroidLanDiag.kt:35), `FrameTrace.shared.enabled` set by the iOS sample (ContentView.swift:601), AWDL asymmetry lines (IosLanDiscoveryTransport.kt:494, IosLanDataTransport.kt:165, :474), `WAITING errCode … endpoint not yet routable` (IosRawConnection.kt:159), connect timeout 10 000 ms (IosLanDataTransport.kt:755, :487), `ensureJmdns`/NICs (AndroidLanDiscoveryTransport.kt:424-425), `boundInterface=`/`publishedAddrs` (JvmLanDiscoveryTransport.kt:297, :93).

### DOCA-19 — REMEDIATION_2026-07.md scope claim: "confined to the 27 source/test/doc files listed above" — no list exists and the count is 33
- Severity: Low | Confidence: Confirmed
- File(s): REMEDIATION_2026-07.md:73
- Category: bug (inaccurate audit-trail claim)
- Root cause: The closing no-unrelated-changes assertion references a file list the document never includes, with a wrong count.
- Evidence: REMEDIATION_2026-07.md:73 "The remediation diff is confined to the 27 source/test/doc files listed above (verified via `git status`)." The document contains no file list; `git diff --name-only adca586^..f4dd3a9` (the 8 fix commits it describes) = **33** unique files (34 with the report itself in 870bf10).
- Runtime impact: weakens the report's audit-trail value; a verifier reconciling the diff against "27" flags a phantom discrepancy. | Platforms: n/a | User-visible: no
- Failure class: none (doc)
- Proposed fix: either append the actual file list or restate as "confined to the N files in commits adca586..870bf10".
- Required tests: n/a
- Also carried on this file: [KNOWN IDN-5] — :63 lists `registerManualPeer` (host,port) dedup as still-deferred, but it landed in b9f6311 ("manual-peer dedup", 2026-06-12; predates the remediation) — only the synthetic-id-format point stands. [KNOWN FIL-1 impact] — :57's #21 disposition ("False positive … matches behavior") and therefore :10's "19 fixed, **1 false positive**" tally are now inaccurate: FIL-1 showed the KDoc is right but the implementation leaks the source on close()/stop(), so #21 was a real (partial) finding. Both rows need a correction note when FIL-1's fix lands.

### DOCA-20 — P2PKIT_GAP_ANALYSIS_2026-07.md: identification, accuracy assessment, and disposition recommendation
- Severity: Informational (identification requested by the campaign) | Confidence: Confirmed on identification; claims spot-checked as below
- File(s): P2PKIT_GAP_ANALYSIS_2026-07.md (197 lines, untracked)
- Category: identification (not a defect report)
- **What it is:** a strategic gap-analysis and v0.7→v1.x roadmap evaluating P2pKit as a *general-purpose* SDK — six pillars P0 (release engineering) … P8 (docs/DX), a "net-new findings" list (§4), a genericity stress-test against a consumer app plan ("Kira" manga app, `LOCAL_MANGA_SHARING_PLAN.md`), and explicit anti-goals. Analysis-only; proposes no immediate code changes.
- **Who/what produced it:** an AI-assisted full-source strategic review commissioned by the maintainer, run on 2026-07-03 against the pre-remediation tree. Forensic pinning: the doc states the branch is "12 commits ahead of `main`"; the branch is now 21 ahead and the remediation added exactly 9 commits → 21−9=12, i.e. written at 5568355, immediately before the remediation began. REMEDIATION_2026-07.md:73 (committed 870bf10) corroborates: "present before this task; origin unknown, not created by the remediation". The author had GitHub context (cites "24 open GitHub issues", "stale open PR (#46)") and read the consumer app's plan doc — consistent with a maintainer-driven assistant session, not this review campaign (which it predates).
- **Accuracy (12 load-bearing claims verified):** overwhelmingly accurate.
  - Confirmed: `P2pMessage.metadata` never transmitted (protocol layer has zero `.metadata` reads; Reassembler reconstructs with defaults) — independently the campaign's known wire-drop finding; `SecurityManager` read-path bypass (frame reader collects `protocol.events(rawConnection)` at SessionManager.kt:301-303 *before* `security.performHandshake` at :379 — reads never pass the wrap); TXT `pv` written by all three advertisers (JvmLanDiscoveryTransport.kt:80, AndroidLanDiscoveryTransport.kt:494, IosLanDiscoveryTransport.kt:561) and read by none; `.github/` absent (no CI); no `consumer-rules.pro` anywhere; gradle.properties NOTE concedes no remote repo; kit scope hardcoded `Dispatchers.Default` (P2pKitImpl.kt:79); `ConnectionState.Closing` never emitted (= my DOCA-16); ACK plumbing dead code (= my DOCA-6); INTERNAL_TESTING §4 has exactly 15 boxes; device matrix A1-A12 all unchecked; "28 commonTest files" right for its date (now 29+ after remediation).
  - **Inaccurate (1):** §4.3 "`incomingSessions` replay contradicts its own KDoc" — overstated. The KDoc (P2pKit.kt:83-86) says "sessions are not silently dropped **if subscribed eagerly**", and the flow is replay=0 / buffer 64 / **SUSPEND** overflow (SessionManager.kt:122-126) — an eager subscriber never loses sessions; only late subscribers miss, which the KDoc's condition covers. The ergonomic gap is real; the "contradicts" framing is wrong.
  - **Caveats:** all its file:line refs are pre-remediation (e.g. cites Reassembler.kt:124-126 for the metadata construct; now :183-184) — stale against HEAD. Its P7 proposal to "tag/`@Ignore`-gate" the two churn tests into a separate suite collides in wording with the repo's standing rule (CLAUDE.md / STABILIZATION C2: never `@Ignore`) — a segregated non-default suite may be defensible, but the wording invites exactly the masking the rule forbids and must be rewritten before anyone acts on it. A few P0 rows need re-verification post-remediation before adoption.
- **Recommendation: KEEP and COMMIT (do not discard).** It is the only artifact holding several net-new, campaign-corroborated findings and the only articulated post-RC roadmap; untracked, it is one `git clean -fd` from loss. Commit with a status banner ("unreviewed proposal; line refs as of 5568355, pre-remediation"), correct §4.3, reword the P7 `@Ignore` suggestion, and triage §4 into the issue tracker. Location suggestion: `docs/`.
- Failure class: none | Required tests: n/a

### DOCA-21 — Deprecated iOS template: 4 of 6 files carry no deprecation marker, and project.yml's own usage steps wipe the load-bearing Info.plist keys
- Severity: Medium | Confidence: Confirmed for markers/wiring; the plist-wipe mechanism is per XcodeGen's documented `info:` generate-semantics (not executed here — read-only review; one `xcodegen generate` run in that dir would demonstrate it)
- File(s): docs/ios-sample-app/project.yml:1-10, :28-29; docs/ios-sample-app/ContentView.swift:1-4; docs/ios-sample-app/P2pKitSampleApp.swift:1-2; docs/ios-sample-app/Info.plist; (README.md and KitController.swift are properly marked)
- Category: bug (dangerous-to-follow deprecated content)
- Root cause: Deprecation was applied at directory level (README banner) and to KitController.swift (AUDIT-2026-06 header), but the other four files read as current, and project.yml still opens with fresh 3-step usage instructions.
- Evidence:
  - project.yml:3-6 "Usage: 1. Drop a built P2pKitShared.framework next to this file. 2. `xcodegen generate` 3. `open p2pkit-sample.xcodeproj`" — no deprecation note. Step 2 is destructive: the spec sets `info: path: Info.plist` with **no `properties:` block** (:28-29), and XcodeGen *generates* (overwrites) the plist at `info.path` — wiping the checked-in Info.plist's `NSLocalNetworkUsageDescription`/`NSBonjourServices` (Info.plist:27-32), i.e. the exact silent zero-discovery trap AUDIT-2026-06 documents; the maintained iosApp/project.yml:26-36 carries both keys in `info.properties` for precisely this reason. It also dirties a *tracked* file.
  - P2pKitSampleApp.swift:2 "Drop into a new SwiftUI iOS app target" — an explicit copy invitation with no deprecation marker (README one level up says "Do not copy these files").
  - ContentView.swift:1-4 presents itself as the current device-checklist UI ("Enough to walk through T1.1–T1.5") with no marker, and references the T1 checklist without naming its home (docs/audit-real-device-checklist.md:126-135).
  - Contradictions vs maintained iosApp/: deployment target 14.0 (:16, :23) vs 15.0 (iosApp/project.yml:5); plain `.framework` beside the yml + `FRAMEWORK_SEARCH_PATHS: $(SRCROOT)` (:37-40) vs XCFramework at `../p2p-transport-lan/build/XCFrameworks/release` + provenance pre-build script (iosApp/project.yml:46, :62-74). A developer landing here by mistake hits, in order: Swift compile errors (KitController's documented drift: `AppId(value:)` not exported, `LanIosDslKt` wrong bridge name, missing `metadata:` arg, `Set<Peer>` cast yields nil), then — if they push through with their own Swift — the plist wipe and stale framework wiring.
  - Verified NOTHING else in the repo points to the template as current: every reference (working-tree CLAUDE.md:49, AUDIT_REPORT_2026-06.md:78/:104, .audit maps) labels it deprecated/stale. AUDIT_REPORT:78 already recommends deleting the directory; the template README itself says it "can be deleted once no external notes reference it".
- Runtime impact: wasted adopter hours; silent zero-discovery if the yml is reused; a tracked file overwritten by following in-file instructions. | Platforms: iOS | User-visible: yes (adopter-facing)
- Failure class: none (doc) — induces a build/config failure for followers
- Proposed fix: delete the directory (the audit's own recommendation), or minimally: one-line `DEPRECATED — see iosApp/` header in all four unmarked files, remove/neutralize project.yml's usage steps, and move the two keys into `info.properties` if the yml is kept at all.
- Required tests: n/a

### Improvements (not defects)

#### DOCA-I1 — README teaser snippet is non-compiling; CLI arg list omits the trace switch
- Severity: Improvement | File(s): README.md:15-24, :356-361
- The opening teaser calls `startAdvertising()`/`startDiscovery()`/`connect()` (all `suspend` — P2pKit.kt:148-169) and `Flow.first()` at top level with no coroutine context; the Quick start (:98-122) does it correctly. Adopters who paste the teaser get compile errors. Also the documented CLI arg list (:356-361) omits the `trace=frames`/`trace=off` positional arg that CLAUDE.md and docs/LAN_DIAGNOSTICS_PROTOCOL.md:27 document (Main.kt:86-100 supports it). Suggest: wrap the teaser in `scope.launch`/mark it illustrative, and add the trace arg to the CLI section.

#### DOCA-I2 — STABILIZATION Part A row A11 wording predates the #9 permission-model change
- Severity: Improvement | File(s): docs/STABILIZATION_AND_RELEASE.md:55
- A11 ("no LAN perms granted … new functional manager") was written for the pre-881fb31 gate. Post-#9, core LAN reports no runtime perms and undeclared install-time perms produce a startup warning instead of `PermissionMissing`. Reword A11 to smoke-test the new contract on device: declared manifest → clean start, no throw; undeclared manifest → warning visible in logcat, kit still starts; provisioning runtime perms still listed by `missingPermissions()`.

#### DOCA-I3 — Part A smoke preamble should require an on-device build-identity check
- Severity: Improvement | File(s): docs/STABILIZATION_AND_RELEASE.md:34-41
- Given the S12-confirmed stale-app-install defect in the iOS run script, add one preamble line to Part A: "before recording any row, confirm the in-app build stamp (commit/branch, shipped since v0.4 build-identity stamping) matches HEAD on every device". Cheap insurance that smoke results describe the RC bits.

#### DOCA-I4 — Spec §24 item 8 instructs the README to "mark provisioning as v0.2"
- Severity: Improvement | File(s): P2pKit-Spec.md:1399
- §24's README-requirements list still mandates the future-tense provisioning framing that DOCA-2 flags in the README. Update the instruction ("document the shipped v0.2.1 sidecars per platform") so the next README sync doesn't reintroduce the staleness.

## 3. Missing tests

| Invariant untested | Why it matters | Where it should live | Type | Priority |
|---|---|---|---|---|
| `close()` state sequence is exactly Connected → Closed (no `Closing`) — pin whichever way DOCA-16 is resolved | Spec-contract drift went unnoticed because nothing asserts the sequence | p2p-core commonTest (SessionFlowTest or CloseSemanticsTest) | unit | P2 |
| `P2pMessage.metadata` receive-side contract (currently: always empty) — pin whichever way the RC decision (DOCA-14/15) goes | Silent public-API data loss has no pinning test; a future "fix" or regression would be invisible | p2p-core commonTest (protocol round-trip tests) | unit | P1 |
| Doc-vs-code count drift (test totals quoted in 4 docs) | Manual counts rot every merge; three docs now disagree with reality | Not a test — suggest dropping exact counts from docs or a tiny CI grep script | n/a | P3 |

## 4. Section summary

**What this section owns:** the 16 dev-critical documents — the agent guide (CLAUDE.md), the adopter surface (README), the locked API contract (P2pKit-Spec.md), the manual-test runbook (INTERNAL_TESTING.md), the active RC gate (STABILIZATION_AND_RELEASE.md), the field-diagnostics protocol, the hardening design notes, the workspace scratchpad, the remediation report, one unidentified untracked strategy doc, and the deprecated iOS template.

**Overall health:** two-tier. The *operationally load-bearing* docs are in excellent shape: working-tree CLAUDE.md verified claim-by-claim (every command, task name, constant, tag and count checked — all correct; it just needs committing, DOCA-1), LAN_DIAGNOSTICS_PROTOCOL is near-perfectly code-accurate (every trace string verified verbatim), and STABILIZATION Part B/C2/C3 match the build and the known-flaky reality. The *adopter-facing and historical* docs carry systematic drift: provisioning described in future tense years after shipping (README), three docs still claiming iOS provisioning can "never" exist despite shipped `iosManualIp()` (PRM-12 family), four spec-vs-behavior mismatches beyond the already-known API-4/SES-1/API-14 (16 MiB aggregate cap undocumented DOCA-8, `Closing` never entered DOCA-16, connect() PermissionMissing DOCA-11, metadata semantics DOCA-15), and test counts stale in four documents.

**Top 3 risks:**
1. **INTERNAL_TESTING's release checklist misfires as written** (DOCA-13): it demands "all 20 iOS tests green" when the suite is 29 tests with 2 documented expected failures — the exact setup that pressures a release runner into masking tests or failing a healthy build. STABILIZATION C3 has the correct expectation; the two runbooks disagree.
2. **The locked spec has accumulated behavior drift** (DOCA-8/-11/-15/-16 + known API-4/SES-1/API-14): a spec-conforming interop implementation can now be killed by an undocumented session-closing cap, and spec-following adopters can hang awaiting a state that never fires. The "living contract" promise (spec:4) is unmet post-remediation.
3. **The RC gate lacks boxes for known pending decisions** (DOCA-14): metadata wire-drop and smoke-binary freshness are campaign-known release-relevant items with no sign-off line — an RC can tag with them unresolved.

**CODEBASE_REVIEW_MAP_2026-07.md accuracy for S14:** accurate. Batch-a file list (:311-317) matches the 16 files reviewed exactly (including flagging CLAUDE.md as modified/uncommitted and the gap analysis as untracked/identify); the review dimensions and Medium risk rating (:325-327, "docs steer future agents; a wrong instruction becomes a wrong change") are exactly what the findings above bear out. No discrepancies.

## Out-of-scope observations

- **docs/audit-real-device-checklist.md:147** (batch-b file) still ends "the v0.3-internal tag is ready to cut" — three versions stale; batch-b reviewer should catch, noting here since ContentView.swift's T1 pointer led to it.
- **P2pKit.kt:83-86** `incomingSessions` KDoc is defensible (see DOCA-20 assessment), but the late-subscriber ergonomic gap the gap-analysis describes is real (the iOS sample polls as a workaround) — API-owner territory (S2), worth a look if not already filed.
- **SessionManager security-wrap ordering** (reads bypass `SecureConnection`, SessionManager.kt:301 vs :379) — verified true while assessing DOCA-20; encryption-milestone territory (S3), flagged in the gap analysis §4.2; ensure it's in the tracker before the encryption work starts.
- **gradle.properties:2-8 publishing NOTE** is accurate and current — no action; recorded because HEAD's CLAUDE.md contradicts it (see DOCA-1).
- **iosApp/project.yml** (S12 territory) verified healthy while comparing against the template: keys in `info.properties` with the AUDIT-2026-06 warning comment, provenance pre-build script declared in the yml.
