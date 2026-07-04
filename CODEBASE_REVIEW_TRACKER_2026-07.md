# P2pKit — Codebase Review Tracker (2026-07)

Phase 1 artifact. One row per repository file (235 tracked + 1 untracked =
**236**). Sections and owners are defined in `CODEBASE_REVIEW_MAP_2026-07.md`;
finding IDs resolve in `CODEBASE_FINDINGS_2026-07.md`; missing-test IDs in
`TEST_COVERAGE_PLAN_2026-07.md`.

**Status legend:** `not started` → `in progress` → `reviewed` (clean) /
`reviewed — needs fix` (has confirmed bug findings; fixes are a post-approval
phase) · later phases: `fixed` → `verified`.
A section is complete only when every row is at least `reviewed`.

**Campaign status: REVIEW PHASE COMPLETE — 2026-07-04.** All sections
S1–S15 done; **236/236 files reviewed.** 18/18 reports on disk in
`.review-2026-07/reports/` (A01-arch, A02-api, A03-session, A04-identity,
A05-discovery, A06-conn, A07-proto, A08-filetransfer, A09-permprov,
A10-iosbuild, A11-build, A12-tests, A13a-docs-core, A13b-docs-audit,
A14-robustness, A14-sec, A15-perf, A16-samples). The cross-cutting reviews
(A14-robustness, A14-sec, A15-perf) own no tracker rows — their findings
attach to the owning sections in the register. Deliverables:
`CODEBASE_FINDINGS_2026-07.md` (consolidated register — **its severity
totals are the authoritative counts**), `TEST_COVERAGE_PLAN_2026-07.md`,
and the forthcoming `FINAL_REVIEW_SUMMARY_2026-07.md`. No model fallback
occurred in any merged wave; all merged agents ran on Fable 5.

---

## S1 — Public API surface — reviewer A2-API — 31/31 reviewed ✅

Base: `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/` unless noted.
Report: `.review-2026-07/reports/A02-api.md` (verified by orchestrator:
API-1 confirmed — `metadata` is public on Text/Binary (participates in
equals/hashCode) but Chunker.kt:29-31 encodes only value/bytes,
Reassembler decodePayload:182-184 reconstructs with default emptyMap(), and
grep shows zero P2pMessage.metadata consumers in commonMain → silent data
loss; must be decided before RC wire-lock. API-2 confirmed — send()
(P2pSessionImpl.kt:235-242) wraps only the pre-write state check;
DefaultP2pProtocol.sendMessage:22-27 is a bare writeFrame loop → raw
IOException (JVM/Android) / ISE+NetworkException (iOS) escape where KDoc
promises P2pError.ConnectionFailed. API-3 confirmed — P2pSession.kt:31-33
KDoc says "[incoming] completes" after close; the property is a SharedFlow,
which never completes → doc-induced app hang/leak. Shape conformance vs
P2pKit-Spec.md otherwise near-exact; C:54 deferral re-assessed sound).

| File | Lines | Status | Tests covering | Missing tests | Findings | Improvements | Verdict |
|---|---|---|---|---|---|---|---|
| Config.kt | 83 | reviewed | KeepAliveTest, ReconnectPolicyTest, CloseSemanticsTest | require/IAE validation unasserted (A2 §3 r3) | API-16 (Low, doc) | | needs fix (doc) |
| Errors.kt | 61 | reviewed | HandshakeTest, SessionFlowTest, TransportManagerTest | send()-failure-is-P2pError pin (A2 §3 r1) | API-2 (High, taxonomy leg), API-16 (Low) | | needs fix (High) |
| ExperimentalP2pApi.kt | 20 | reviewed | n/a (annotation) | none | | | clean |
| Identity.kt | 41 | reviewed | HandshakeTest, InMemoryPeerIdStorageTest, LocalIdentityTest | blank-id network-parse guards (transport-side) | API-17 (Low) | | needs fix (Low) |
| NetworkPath.kt | 94 | reviewed | NetworkPathRecoveryTest | observer shared across two kits | | | clean |
| NetworkProvisioningError.kt | 31 | reviewed | provisioning sidecar tests | none | | | clean |
| P2pKit.kt | 195 | reviewed | KitLifecycleTest, PermissionGateTest, LocalIdentityTest, loopback | TransportStartFailed via lazy connect() (A2 §3 r7) | API-5 (Low, doc), API-6 (Low, doc) | | needs fix (doc) |
| P2pLogger.kt | 24 | reviewed | used ubiquitously | none | | | clean |
| P2pMessage.kt | 44 | reviewed | ChunkerTest, ReassemblerTest, SessionFlowTest (payload only) | metadata round-trip — would fail today (A2 §3 r2) | API-1 (High) | | needs fix (High) |
| P2pSession.kt | 94 | reviewed | SessionFlowTest, CloseSemanticsTest, KeepAliveTest | mid-send exception-type assertion (A2 §3 r1) | API-2 (High), API-3 (Med, doc), API-4 (Low, spec) | | needs fix (High) |
| Peer.kt | 48 | reviewed | PeerRegistryTest | none | | API-21 | clean (improvements) |
| States.kt | 46 | reviewed | KitLifecycleTest, SessionFlowTest | observable state-set enumeration (A2 §3 r10) | API-9 (Low, doc), API-10 (Low, doc) | | needs fix (doc) |
| dsl/Builders.kt | 226 | reviewed | every kit-constructing test; no dedicated builder test | repeated-block + required-field errors (A2 §3 r3) | API-7 (Low) | API-11, API-12 | needs fix (Low) |
| permission/NoOpP2pPermissionManager.kt | 16 | reviewed | PermissionGateTest | none | API-13 (Low, doc) | | needs fix (doc) |
| permission/P2pPermissionManager.kt | 35 | reviewed | PermissionGateTest (4 cases) | none | [CATALOGUED] C:54 assessed sound | | clean |
| provisioning/ManualPeerRegistrar.kt | 43 | reviewed | ManualPeerIdentityTest | IAE on bad host/port unasserted | API-18 (Low, doc) | | needs fix (doc) |
| provisioning/NetworkProvisioningFactory.kt | 69 | reviewed | sidecar tests (desktop/android) | none | | API-22 | clean (improvements) |
| provisioning/NetworkProvisioningTypes.kt | 152 | reviewed | sidecar tests | none | API-18 (Low, doc) | | needs fix (doc) |
| provisioning/UnsupportedNetworkProvisioningManager.kt | 47 | reviewed | none direct | stub return-value test | API-8 (Low) | | needs fix (Low) |
| security/SecurityManager.kt | 41 | reviewed | HandshakeIdentityTest (indirect) | none | | API-11 | clean (improvements) |
| transfer/FileTransferConfig.kt | 35 | reviewed | FileTransferFlowTest | validation boundaries (chunk 0 / 4MiB+1) | API-16 (Low, doc) | | needs fix (doc) |
| transfer/FileTransferState.kt | 51 | reviewed | FileTransferFlowTest, FileTransferErrorIsolationTest | timeout state pair (A2 §3 r4) | API-19 (Low, doc) | | needs fix (doc) |
| transfer/P2pFileOffer.kt | 52 | reviewed | FileTransferFlowTest | accept-after-timeout ISE (A2 §3 r5) | API-19 (Low), API-20 (Low, doc) | | needs fix (doc) |
| transfer/P2pFileTransfer.kt | 51 | reviewed | FileTransferFlowTest, StreamingFileReceiver/SenderTest | zero-byte E2E (A2 §3 r6) | [LIKELY-DUP FIL-1/FIL-2] | | clean (dups noted) |
| transport/DataTransport.kt | 54 | reviewed | JvmLanLoopbackTest, iOS loopback | double-close idempotency contract | | API-15 | clean (improvements) |
| transport/DiscoveryTransport.kt | 44 | reviewed | SessionReconnectRotationTest, loopback suites | none | | | clean |
| transport/HasLocalTcpEndpoint.kt | 27 | reviewed | iOS lifecycle tests | none | | | clean |
| transport/Internal.kt | 72 | reviewed | ManualPeerIdentityTest, PeerRegistryTest | none | API-14 (Low, spec) | | needs fix (spec) |
| transport/RawConnection.kt | 29 | reviewed | loopback + FakeRawConnection suites | none | | API-15 | clean (improvements) |
| transport/TransportFactory.kt | 38 | reviewed | every integration test | none | | | clean |
| [androidMain] android/P2pKitAndroid.kt | 33 | reviewed | none (no instrumented tests, per repo policy) | manual recipe only (INTERNAL_TESTING.md) | | | clean |

## S2 — Kit wiring & platform services — reviewer A1-ARCH — 19/19 reviewed ✅

Base: `p2p-core/src/` (source set in brackets).
Report: `.review-2026-07/reports/A01-arch.md` (verified by orchestrator:
ARCH-1 CE-swallow at :266, ARCH-2 NonCancellable boundary :463 vs :469-471 +
observer-mutex hold, ARCH-3 unguarded :313-316, and the false map edge all
re-checked against source — accurate). Architecture pass: layering clean,
SPI/PeerOrigin coherent, 6 expects × 3 actuals verified; 4 map corrections
applied to `CODEBASE_REVIEW_MAP_2026-07.md`.

| File | Lines | Status | Tests covering | Missing tests | Findings | Improvements | Verdict |
|---|---|---|---|---|---|---|---|
| [common] internal/P2pKitImpl.kt | 559 | reviewed | KitLifecycleTest, NetworkPathRecoveryTest, PermissionGateTest, LocalIdentityTest | MT-ARCH-1..6 (state machine, CE, stop races — 3× P1) | ARCH-1 (High), ARCH-2 (High), ARCH-3 (Med), ARCH-4 (Med), ARCH-5 (Low), ARCH-10 (Low, catalogued B:201) | ARCH-11, ARCH-12, ARCH-14 | needs fix (High) |
| [common] internal/TransportManager.kt | 32 | reviewed | TransportManagerTest | MT-ARCH-7 (tie-break determinism) | ARCH-8 (Low, spec drift) | ARCH-15 | needs fix (spec) |
| [common] internal/Platform.kt | 9 | reviewed | indirect (all clock users) | — | | | clean |
| [common] internal/NativeBuildLog.kt | 14 | reviewed | none | — | ARCH-7 (Low, doc) | | needs fix (doc) |
| [common] internal/NetworkPathObserverFactory.kt | 16 | reviewed | indirect | — | | | clean |
| [common] internal/NoOpNetworkPathObserver.kt | 25 | reviewed | indirect (JVM/Android kit tests) | — | | | clean |
| [android] internal/Platform.android.kt | 7 | reviewed | none (no Android host tests) | — | | | clean |
| [jvm] internal/Platform.jvm.kt | 7 | reviewed | indirect (all jvmTest) | — | | | clean |
| [ios] internal/Platform.ios.kt | 10 | reviewed | indirect (iosSimTest) | — | | | clean |
| [android] internal/NativeBuildLog.android.kt | 7 | reviewed | none | — | | | clean |
| [jvm] internal/NativeBuildLog.jvm.kt | 25 | reviewed | none | — | ARCH-7 (violating side) | | needs fix (doc) |
| [ios] internal/NativeBuildLog.ios.kt | 8 | reviewed | none | — | | | clean |
| [android] AndroidNetworkPathObserver.kt | 119 | reviewed | **none** (no automation) | MT-ARCH-8 (register/unregister symmetry, P2) | ARCH-6 (Low) | ARCH-13 | needs fix (Low) |
| [android] internal/AndroidNetworkPathObserverFactory.kt | 19 | reviewed | none | — | | | clean |
| [ios] internal/IosNetworkPathObserver.kt | 110 | reviewed | **none** (implicit only) | MT-ARCH-9 (start/close/restart, P3) | ARCH-6 (shared) | ARCH-16 | needs fix (Low) |
| [ios] internal/IosNetworkPathObserverFactory.kt | 8 | reviewed | indirect | — | | | clean |
| [jvm] internal/JvmNetworkPathObserverFactory.kt | 12 | reviewed | indirect (every JVM kit test) | — | | | clean |
| [commonTest] internal/KitLifecycleTest.kt | 239 | reviewed | — | stop-hang failure variants | ARCH-9 (Low, `~/.p2pkit` pollution) | | needs fix (test hygiene) |
| [commonTest] internal/TransportManagerTest.kt | 84 | reviewed | — | tie-break | | ARCH-15 | clean (impr. noted) |

## S3 — Session lifecycle — reviewer A3-SESSION — 13/13 reviewed ✅

Base: `p2p-core/src/commonMain|commonTest/kotlin/dev/p2pkit/core/internal/`.
Report: `.review-2026-07/reports/A03-session.md` (verified by orchestrator:
SES-1 crux sites (observeRawState :222-233 vs routeEvents :548-552) + the spec
§16.3 contradiction re-read from source; SES-8 grep-confirmed (strictInvariants
never true outside its own unit test); SES-3 cleanup gap confirmed at :432 —
accurate). SES-1 = adjudicated CON-7, now confirmed by two independent
reviewers. Remediation 012e49e/f4dd3a9 verified sound; e91e094 partially
realized (SES-8).

| File | Lines | Status | Tests covering | Missing tests | Findings | Improvements | Verdict |
|---|---|---|---|---|---|---|---|
| SessionManager.kt | 789 | reviewed | SessionFlowTest, ReconnectPolicyTest, SessionReconnectRotationTest, SimultaneousOpenTest, NetworkPathRecoveryTest | MT-SES-1,2 (production-shaped connection loss), reader cleanup | SES-1 (High), SES-2, SES-3 (Med), SES-4 (Med), SES-5 (Low), SES-6 (Low), SES-7 (Low), SES-8 (Med) | SES-12, SES-13, SES-14, SES-16 | needs fix (High) |
| P2pSessionImpl.kt | 717 | reviewed | KeepAliveTest, CloseSemanticsTest, SessionFlowTest, ReconnectPolicyTest | remote-CLOSE+reconnect; keep-alive pre-send/rearm-reset | SES-1 (High), SES-2 (Med), SES-3 (co), SES-7, SES-9 (Low) | SES-14, SES-15 | needs fix (High) |
| SessionStore.kt | 332 | reviewed | SessionStoreInvariantTest (direct), flow suites (indirect) | arbitration-vs-zombie interleaving | SES-4 (Med), SES-8 (Med) | | needs fix (Med) |
| Handshake.kt | 89 | reviewed | HandshakeTest (+S4 suites) | timeout + wrong-first-event paths (zero coverage) | SES-11 (Low) | SES-16 | needs fix (Low) |
| [test] SessionFlowTest.kt | 270 | reviewed | — | interleave test single-frame-only; relaxed Closed‖Failed masks SES-1 | SES-10 (shared) | SES-17 | needs fix (test-fidelity) |
| [test] CloseSemanticsTest.kt | 143 | reviewed | — | close-during-active-inbound (SES-3 trigger) | | | clean |
| [test] KeepAliveTest.kt | 201 | reviewed | — | rearm PONG-reset, PING-fail, pre-send-check | | SES-18 | clean (gaps noted) |
| [test] ReconnectPolicyTest.kt | 327 | reviewed | — | remote-clean-close-never-retries missing | SES-10 (breakWith fidelity) | | needs fix (test-fidelity) |
| [test] SessionReconnectRotationTest.kt | 359 | reviewed | — | periodic ~3 s refresh cadence unexercised | SES-10 (shared) | | clean (fidelity caveat) |
| [test] SessionStoreInvariantTest.kt | 184 | reviewed | — | strict mode absent from behavioral flows | SES-8 (evidence) | | needs fix (wiring) |
| [test] SimultaneousOpenTest.kt | 137 | reviewed | — | tie-break direction/health/orders unasserted | | SES-19 | clean (weak asserts) |
| [test] NetworkPathRecoveryTest.kt | 281 | reviewed | — | incoming-fails-on-Unsatisfied missing | | | clean |
| [test] HandshakeTest.kt | 147 | reviewed | — | timeout, wrong-first-event, ERROR-frame | | SES-16 (test side) | clean (gaps noted) |

## S4 — Peer identity & provenance — reviewer A4-IDENTITY — 16/16 reviewed ✅

Base: `p2p-core/src/` (source set in brackets).
Report: `.review-2026-07/reports/A04-identity.md` (verified by orchestrator:
IDN-5 confirmed via `git show b9f6311` + live dedupe code at
PeerRegistry.kt:126-131 — REMEDIATION:63 + map + BRIEF were stale, all three
campaign artifacts corrected; IDN-1's Lost leg confirmed from the earlier
PeerRegistry read — accurate). 012e49e provenance fix verified sound;
adjudication: unfiltered-Lost spoof is real for discovered peers (DSC-11) but
NOT practically reachable against manual entries (122-bit local-only uuid).

| File | Lines | Status | Tests covering | Missing tests | Findings | Improvements | Verdict |
|---|---|---|---|---|---|---|---|
| [common] internal/PeerRegistry.kt | 186 | reviewed | PeerRegistryTest (discovered paths only) | MT-IDN-1,2,4,5,6 (manual/provenance surface — 2× P1) | IDN-1 (Low), IDN-2 (Low), IDN-3 (Low) | IDN-7, IDN-9 | needs fix (Low) |
| [common] internal/PeerIdStorage.kt | 34 | reviewed | persistence integration (indirect) | contract pinned jvm-only | | IDN-6 (KDoc omits iOS) | clean (impr. noted) |
| [common] internal/InMemoryPeerIdStorage.kt | 27 | reviewed | InMemoryPeerIdStorageTest | — | | IDN-9 (plain var, guarded by single-call) | clean |
| [android] internal/FilePeerIdStorage.kt | 74 | reviewed | **none** (no Android test target) | MT-IDN-7 (whole class, P2) | IDN-4 (Low), IDN-6 (Low, stale "copy" header) | | needs fix (Low) |
| [jvm] internal/FilePeerIdStorage.kt | 125 | reviewed | FilePeerIdStorageTest, PeerIdPersistenceIntegrationTest | MT-IDN-3 (legacy migration, P1), corrupt-nonblank | IDN-4 (Low) | | needs fix (Low) |
| [ios] internal/NSUserDefaultsPeerIdStorage.kt | 77 | reviewed | **none** (injectable ctor unused) | MT-IDN-8 (P2) | IDN-4 (shared) | | needs fix (Low) |
| [android] internal/PeerIdStorageFactory.android.kt | 19 | reviewed | none | fallback-warn untestable today | | | clean |
| [jvm] internal/PeerIdStorageFactory.jvm.kt | 11 | reviewed | indirect | — | | | clean (empty-home nit noted) |
| [ios] internal/PeerIdStorageFactory.ios.kt | 7 | reviewed | none | trivial | | | clean |
| [commonTest] internal/PeerRegistryTest.kt | 221 | reviewed | — | manual-peer surface entirely unpinned | | coverage gaps | clean, coverage gap |
| [commonTest] internal/ManualPeerIdentityTest.kt | 231 | reviewed | — | Found-path spoof variant | | path-vs-comment nit | clean |
| [commonTest] internal/HandshakeIdentityTest.kt | 144 | reviewed | — | acceptor-side rejection unasserted (NoOp-logger blind) | | hidden-failure nit | clean (gap noted) |
| [commonTest] internal/LocalIdentityTest.kt | 74 | reviewed | — | — | | | clean |
| [commonTest] internal/InMemoryPeerIdStorageTest.kt | 30 | reviewed | — | — | | | clean |
| [jvmTest] internal/FilePeerIdStorageTest.kt | 86 | reviewed | — | migration, garbage, unreadable | | | clean (gaps noted) |
| [jvmTest] internal/PeerIdPersistenceIntegrationTest.kt | 151 | reviewed | — | direct kit-level id equality | | | clean |

## S5 — Discovery transports & LAN plumbing — reviewer A5-DISCOVERY — 18/18 reviewed ✅

Base: `p2p-transport-lan/src/` (source set in brackets).
Report: `.review-2026-07/reports/A05-discovery.md` (verified by orchestrator:
DSC-1's three legs re-checked — 15 s eviction at PeerRegistry.kt:102/169,
`PeerEvent.Updated` emitted ONLY in appleMain (grep), iOS announce loop is the
prior fix for the identical symptom; JmDNS 3.6.3 renewal behavior verified by
the agent against the actual dependency sources — accurate). Wire/TXT parity
table built: keys/formats/service type identical; divergences degenerate-only.

| File | Lines | Status | Tests covering | Missing tests | Findings | Improvements | Verdict |
|---|---|---|---|---|---|---|---|
| [jvm] JvmLanDiscoveryTransport.kt | 361 | reviewed | JvmLanLoopbackTest (indirect), HostSelectorTest | MT-DSC-1 (steady-state persistence, P1), refresh CE paths | DSC-1 (High), DSC-3 (Med), DSC-7 (Med), DSC-11 (Low), DSC-12 (Low), DSC-13 (Low) | DSC-I1, I4, I5, I10 | needs fix (High) |
| [android] AndroidLanDiscoveryTransport.kt | 1031 | reviewed | **none** (zero automated) | MT-DSC-2 (rebind machinery seam, P1) | DSC-1, DSC-2 (Med), DSC-3, DSC-4 (Med), DSC-5 (Med), DSC-7, DSC-10 (Low), DSC-11, DSC-12, DSC-13 | DSC-I3, I4, I5 | needs fix (High) |
| [apple] IosLanDiscoveryTransport.kt | 782 | reviewed | AnnounceCacheReconcileTest, IosLanLifecycleTest, loopback | hook-vs-stop races, generation stamping | DSC-6 (Med), DSC-8 (Low), DSC-9 (Low) | DSC-I2, I6 | needs fix (Med) |
| [apple] IosBonjour.kt | 97 | reviewed | IosBonjourTest | oversize/duplicate-key decode | DSC-12 (shared) | | needs fix (Low) |
| [apple] IosEndpointRegistry.kt | 42 | reviewed | indirect | no direct unit | | DSC-I6 | clean (impr. noted) |
| [common] Lan.kt | 70 | reviewed | indirect | tcpPort==0 precondition unasserted | | DSC-I10 | clean (impr. noted) |
| [jvm] JvmLanDsl.kt | 47 | reviewed | JvmLanLoopbackTest | — | | | clean |
| [android] AndroidLanDsl.kt | 60 | reviewed | none | factory wiring (low risk) | | | clean |
| [apple] IosLanDsl.kt | 37 | reviewed | iOS suites | — | | | clean |
| [jvm] JvmLanDiag.kt | 100 | reviewed | none | "zero-alloc when disabled" claim unpinned | | DSC-I1 | clean (impr. noted) |
| [android] AndroidLanDiag.kt | 80 | reviewed | none | — | DSC-2 (context) | DSC-I1 | needs fix (Med, DSC-2) |
| [apple] IosLanDebug.kt | 75 | reviewed | IosLanDiagnosticTest | unconditional emit unpinned | | DSC-I1 | clean (impr. noted) |
| [apple] IosSwiftHelpers.kt | 50 | reviewed | none (used by iosApp) | trivial | | DSC-I8 (spec drift) | clean (impr. noted) |
| [jvmTest] HostSelectorTest.kt | 132 | reviewed | — | IPv4-mapped-IPv6; pins only JVM copy | | | clean |
| [appleTest] AnnounceCacheReconcileTest.kt | 155 | reviewed | — | caller CAS race out of reach (DSC-8) | | | clean (7 cases sound) |
| [appleTest] IosBonjourTest.kt | 132 | reviewed | — | >255 B + duplicate-key cases | | | clean (gaps noted) |
| [appleTest] IosLanLifecycleTest.kt | 415 | reviewed | — | 2 catalogued sim flakes; weak no-exception assert | | DSC-I9 (1 s id collision) | clean (impr. noted) |
| [appleTest] IosLanDiagnosticTest.kt | 65 | reviewed | — | — | | | clean (@Ignore documented) |

## S6 — Wire protocol — reviewer A7-PROTO — 20/20 reviewed ✅

Base: `p2p-core/src/commonMain|commonTest/kotlin/dev/p2pkit/core/protocol/`.
Report: `.review-2026-07/reports/A07-proto.md` (verified by orchestrator:
PRO-1/PRO-5/PRO-7 evidence re-checked against source — accurate).

| File | Lines | Status | Tests covering | Missing tests | Findings | Improvements | Verdict |
|---|---|---|---|---|---|---|---|
| Chunker.kt | 75 | reviewed | ChunkerTest | MT-PRO-11 (UTF-8 split); MAX_TOTAL_CHUNKS consistency | | PRO-9 | clean (impr. noted) |
| DefaultP2pProtocol.kt | 219 | reviewed | DefaultP2pProtocolTest, FileTransferProtocolTest | MT-PRO-3 (malformed-payload skip), MT-PRO-9, MT-PRO-12 | PRO-7 (Low) | PRO-12 | needs fix (Low) |
| FileOfferPayload.kt | 54 | reviewed | FileOfferPayloadTest | MT-PRO-8 (decode guards) | | | clean |
| Frame.kt | 112 | reviewed | FrameCodecTest (indirect) | — | | PRO-9 | clean (impr. noted) |
| FrameCodec.kt | 126 | reviewed | FrameCodecTest | MT-PRO-1 (oversized len), MT-PRO-10 (fwd-compat) | PRO-6 (Low) | PRO-9 | needs fix (Low) |
| FrameReader.kt | 86 | reviewed | FrameReaderTest | MT-PRO-1 (8 MiB resource-limit guard — zero coverage) | | PRO-8, PRO-10, PRO-12 | clean (impr. noted) |
| FrameTrace.kt | 38 | reviewed | none (diagnostic) | — | | | clean |
| HelloPayload.kt | 59 | reviewed | HelloPayloadTest | MT-PRO-2 (all decode guards) | PRO-1 (Med), PRO-4, PRO-5 | | needs fix (Medium) |
| P2pProtocol.kt | 46 | reviewed | protocol tests | — | PRO-2 (Low, spec) | | needs fix (spec) |
| ProtocolConstants.kt | 64 | reviewed | ReassemblerTest, FrameCodecTest | — | PRO-3 (Low, spec) | PRO-11 | needs fix (spec) |
| ProtocolEvent.kt | 36 | reviewed | protocol tests | — | | | clean |
| Reassembler.kt | 185 | reviewed | ReassemblerTest (14 cases; accounting verified exact) | MT-PRO-4..7 (caps + evict-budget) | PRO-7 (Low) | | needs fix (Low) |
| [test] ChunkerTest.kt | 149 | reviewed | — | — | | | clean (asserts invariants) |
| [test] DefaultP2pProtocolTest.kt | 175 | reviewed | — | happy-path only | | test gap | clean, coverage gap |
| [test] FileOfferPayloadTest.kt | 38 | reviewed | — | happy-path only | | test gap | clean, coverage gap |
| [test] FileTransferProtocolTest.kt | 177 | reviewed | — | malformed FILE_OFFER; reason truncation | | | clean |
| [test] FrameCodecTest.kt | 162 | reviewed | — | oversized-len; fwd-compat pins | | | clean (good negatives) |
| [test] FrameReaderTest.kt | 130 | reviewed | — | oversized-declared-length | | | clean |
| [test] HelloPayloadTest.kt | 66 | reviewed | — | no rejection cases | | test gap | clean, coverage gap |
| [test] ReassemblerTest.kt | 312 | reviewed | — | see Reassembler row | | | clean (asserts accounting) |

## S7 — Data transports & raw connections — reviewer A6-CONN — 9/9 reviewed ✅

Base: `p2p-transport-lan/src/` (source set in brackets).
Report: `.review-2026-07/reports/A06-conn.md` (verified by orchestrator: CON-1
close()/read cancellation-skip re-checked against source, CON-3 accept-loop
`close(e)` channel-failure → bare `launchIn(scope)` (SessionManager.kt:148-150)
re-checked — accurate; CON-3 converges with ARCH-4 on the unfenced kit scope).
JVM↔Android pair diffed: control flow line-for-line identical, divergence is
logging-only (CON-10).

| File | Lines | Status | Tests covering | Missing tests | Findings | Improvements | Verdict |
|---|---|---|---|---|---|---|---|
| [jvm] JvmLanDataTransport.kt | 181 | reviewed | JvmLanLoopbackTest (indirect) | MT-CON-4,5,6 (dial-cancel, accept-failure, stop/start race) | CON-2 (Med), CON-3 (High), CON-4 (Med), CON-9 (minor) | CON-18 | needs fix (High) |
| [android] AndroidLanDataTransport.kt | 173 | reviewed | **none** (no instrumented tests — catalogued) | same as JVM | CON-2, CON-3, CON-4, CON-10 (Low) | | needs fix (High) |
| [apple] IosLanDataTransport.kt | 766 | reviewed | IosLanLoopbackTest (indirect) | MT-CON-6,7 (stop/start race, listener-failed) | CON-2 (iOS), CON-4, CON-8 (Med), CON-9 (Low), CON-11 (Low), CON-12 (Low), CON-13 (Low) | CON-15, CON-16 | needs fix (Med) |
| [jvm] JvmRawConnection.kt | 208 | reviewed | JvmLanLoopbackTest (fd-leak EOF path) | MT-CON-1 (real watchdog, P1), MT-CON-2 (cancelled close, P1) | CON-1 (High), CON-6 (Med), CON-7 (contrib) | CON-14 | needs fix (High) |
| [android] AndroidRawConnection.kt | 207 | reviewed | **none** (parity by diff only) | any automated execution (P3, manual) | CON-1, CON-6, CON-7 (identical code) | | needs fix (High) |
| [apple] IosRawConnection.kt | 383 | reviewed | IosRawConnectionTest, IosLanLoopbackTest | send-deadline manual-only | CON-5 (Med), CON-7 (contrib) | | needs fix (Med) |
| [jvmTest] JvmLanLoopbackTest.kt | 351 | reviewed | — | watchdog, cancelled-close, keep-alive never fires (60 s ping) | | | clean (fd assert robust) |
| [appleTest] IosLanLoopbackTest.kt | 201 | reviewed | — | no iOS fd/cancel-leak analogue | | CON-17 (1 s id flake) | clean (impr. noted) |
| [appleTest] IosRawConnectionTest.kt | 75 | reviewed | — | deadline/receive not covered (documented manual) | | CON-19 (message-string coupling) | clean (impr. noted) |

## S8 — File transfer — reviewer A8-FILET — 12/12 reviewed ✅

Base: `p2p-core/src/` (source set in brackets).
Report: `.review-2026-07/reports/A08-filetransfer.md` (verified by orchestrator:
FIL-1 confirmed — watcher is a `sessionJob` child (P2pSessionImpl.kt:126,:172)
cancelled at :301 after `closeAll` markFaileds the handle; deterministic
source-leak on single-threaded dispatchers, race on Default; rearm path NOT
affected. FIL-2 confirmed — streamOutgoingPayload catch:582-587 sends no
FILE_CANCEL vs onFileData:449-461 which does; receiver has no post-accept
timer. Verification addendum appended to the report). 7854ca7 isolation +
LAZY-streamer verified sound.

**FIL-1 corrects REMEDIATION #21's disposition:** #21's KDoc claim is right,
but the implementation does not honor "kit closes the source" on close()/stop().

| File | Lines | Status | Tests covering | Missing tests | Findings | Improvements | Verdict |
|---|---|---|---|---|---|---|---|
| [common] internal/FileTransferDispatcher.kt | 644 | reviewed | FileTransferFlowTest, FileTransferErrorIsolationTest | MT-FIL-1..9 (source-close, sender-read-fail, dup-ACCEPT, cap, malformed-input FILE_* — 5× P1) | FIL-1 (High), FIL-2 (High), FIL-3 (Med), FIL-4 (Med), FIL-5 (Med), FIL-6 (Med), FIL-7 (Low) | FIL-12, FIL-13, FIL-14 | needs fix (High) |
| [common] internal/IncomingFileSession.kt | 86 | reviewed | FileTransferFlowTest (indirect) | terminal-CAS under contention | FIL-10 (Low, doc) | | needs fix (doc) |
| [common] internal/OutgoingFileTransferImpl.kt | 79 | reviewed | FileTransferFlowTest (indirect) | bytesTransferred ≤ sizeBytes | FIL-10 (Low, doc) | | needs fix (doc) |
| [common] protocol/StreamingFileReceiver.kt | 94 | reviewed | StreamingFileReceiverTest | abort idempotency, double finish | FIL-5 (shared), FIL-10 (doc) | | needs fix (Med) |
| [common] protocol/StreamingFileSender.kt | 55 | reviewed | StreamingFileSenderTest | short-source EOF, mid-collect cancel | | | clean |
| [android] transfer/FileTransferAndroid.kt | 78 | reviewed | **none** (no instrumented tests) | MT-FIL (URI/-1 SIZE/FNF/SecurityException, P3) | FIL-9 (Low) | | needs fix (Low) |
| [jvm] transfer/FileTransferJvm.kt | 38 | reviewed | FileTransferJvmTest | unreadable, delete-race, source-close | FIL-9 (shared) | | needs fix (Low) |
| [commonTest] internal/FileTransferFlowTest.kt | 573 | reviewed | — | FIL-11 no-op assertion | FIL-11 (Med, test defect) | FIL-15 (racy assert) | needs fix (test) |
| [commonTest] internal/FileTransferErrorIsolationTest.kt | 199 | reviewed | — | onFileData write-path E2E | | | clean (finish-leg only) |
| [commonTest] protocol/StreamingFileReceiverTest.kt | 112 | reviewed | — | abort/double-finish/chunk-after-finish | | | clean |
| [commonTest] protocol/StreamingFileSenderTest.kt | 125 | reviewed | — | short-source, cancellation | | | clean |
| [jvmTest] transfer/FileTransferJvmTest.kt | 163 | reviewed | — | permission-denied, stream-closed-after-terminal | | | clean |

## S9 — Permissions — reviewer A9-PERMPROV — 5/5 reviewed ✅

Base: `p2p-core/src/` (source set in brackets).
Report: `.review-2026-07/reports/A09-permprov.md` (verified by orchestrator:
PRM-1 confirmed — ensurePermissions (P2pKitImpl.kt:497-500) throws on ANY
missing perm, while Builders.kt:73-80 + PermissionManagerFactory.android.kt:85-88
recommend wiring the sidecar manager that reports provisioning-only perms →
the documented wiring over-gates core LAN, the exact class #9 removed.
Remediation #9 itself verified complete/consistent at both call sites
(:321,:358); connect() un-gated by design. C:54 single-mapping re-verified,
enum-constant deferral sound).

| File | Lines | Status | Tests covering | Missing tests | Findings | Improvements | Verdict |
|---|---|---|---|---|---|---|---|
| [common] internal/PermissionManagerFactory.kt | 28 | reviewed | PermissionGateTest (default path) | none | | | clean |
| [android] internal/PermissionManagerFactory.android.kt | 93 | reviewed | none automated — manual recipe in KDoc | A9 §3 r7 (host-test harness for empty-report + manifest-warn) | PRM-1 (Med, systemic) | PRM-2 | needs fix (Med) |
| [ios] internal/PermissionManagerFactory.ios.kt | 14 | reviewed | PermissionGateTest default path (iOS) | none | | | clean |
| [jvm] internal/PermissionManagerFactory.jvm.kt | 9 | reviewed | PermissionGateTest default path (JVM) | none | | | clean |
| [commonTest] internal/PermissionGateTest.kt | 155 | reviewed | n/a (is a test) | A9 §3 r6 (connect()-bypasses-gate pin) | | PRM-3 | clean (improvements) |

## S10 — Network provisioning — reviewer A9-PERMPROV — 14/14 reviewed ✅

Report: `.review-2026-07/reports/A09-permprov.md` (verified by orchestrator:
PRM-4 confirmed — join bridge binds the process (WifiManagerWrapperImpl.kt:165)
before publishing `handle` (plain captured var, :172); invokeOnCancellation's
`?:` fallback (:195-198) only unregisters the callback → cancellation racing
the OS callback can leave bindProcessToNetwork set with no owner (process-wide
blackhole until restart). PRM-5 confirmed — mapStartException collapses every
SecurityException to PermissionMissingForProvisioning (cause hardcoded null at
NetworkProvisioningError.kt:26); RequiresUserAction never returned anywhere in
androidMain (grep). PRM-6 confirmed — JVM collectNonLoopbackAddresses lacks
Android's per-NIC SocketException guard; raw SocketException reachable from
public getManualConnectionInfo(). PRM-12 confirmed — iOS manual-IP is real
shipped code (createManualPeer → manualPeerRegistrar; dial branch in
IosLanDataTransport); only hotspot/join are Unsupported → CLAUDE.md blanket
claim imprecise; BRIEF.md corrected for later waves).

| File | Lines | Status | Tests covering | Missing tests | Findings | Improvements | Verdict |
|---|---|---|---|---|---|---|---|
| p2p-network-provisioning-android/src/androidMain/AndroidManifest.xml | 14 | reviewed | n/a | n/a (declares nothing by documented policy) | | PRM-20 (note) | clean |
| …provisioning-android …/AndroidDsl.kt | 42 | reviewed | none (glue) | none | | PRM-20 | clean |
| …provisioning-android …/AndroidNetworkProvisioningManager.kt | 425 | reviewed | AndroidNetworkProvisioningManagerTest (12 tests, fake wrapper) | A9 §3 r1,2,4,5 (timeout path, parentJob-cancel teardown, API-gate Unsupported, restartability) | PRM-5 (Med), PRM-7 (Low), PRM-8 (Low), PRM-9 (Low), PRM-10 (Low) | PRM-16, PRM-20 | needs fix (Med) |
| …provisioning-android …/AndroidP2pPermissionManager.kt | 70 | reviewed | none | A9 §3 r8 (targetSdk×API matrix) | [CATALOGUED] C:54 assessed sound | | clean |
| …provisioning-android …/AndroidProvisioningFactory.kt | 28 | reviewed | none (glue) | none | | PRM-20 | clean |
| …provisioning-android …/WifiManagerWrapper.kt | 129 | reviewed | via fakes in manager test | contract asserted via fakes only (acceptable) | | | clean |
| …provisioning-android …/WifiManagerWrapperImpl.kt | 335 | reviewed | **none** (real OS deps; manual only) | A9 §3 r12 (device-manual rows: decline/timeout/location-off) | PRM-4 (Med), PRM-11 (Low, doc) | | needs fix (Med) |
| …provisioning-android [androidHostTest] AndroidNetworkProvisioningManagerTest.kt | 478 | reviewed | n/a (is a test) | A9 §3 r1–5 (fakes replay=0 vs prod replay=1; handle-close unasserted) | | PRM-17 | clean (improvements) |
| …provisioning-desktop …/JvmDsl.kt | 31 | reviewed | ManualIpLoopbackTest | none | | | clean |
| …provisioning-desktop …/JvmNetworkProvisioningManager.kt | 164 | reviewed | JvmNetworkProvisioningManagerTest, ManualIpLoopbackTest | A9 §3 r10 (poll loop; needs enumeration seam) | PRM-6 (Med) | PRM-15 | needs fix (Med) |
| …provisioning-desktop …/JvmProvisioningFactory.kt | 14 | reviewed | ManualIpLoopbackTest | none | | | clean |
| …provisioning-desktop [test] JvmNetworkProvisioningManagerTest.kt | 139 | reviewed | n/a (is a test) | silent-pass guard (NIC-less host) | | PRM-19 | clean (improvements) |
| …provisioning-desktop [test] ManualIpLoopbackTest.kt | 116 | reviewed | n/a (is a test) | dead 127.* branch; only one direction asserted | | PRM-18 | clean (improvements) |
| p2p-transport-lan [apple] IosManualNetworkProvisioningManager.kt | 140 | reviewed | **none** (sample-manual only) | A9 §3 r11 (appleTest manual-IP loopback) | PRM-12 (Low, doc — code is the correct side), PRM-13 (Low, doc) | PRM-14 | needs fix (doc) |

## S11 — Samples & harnesses — reviewer A16-SAMPLES — 13/13 reviewed ✅

Report: `.review-2026-07/reports/A16-samples.md` (verified by orchestrator:
SMP-1 confirmed — desktop-ui writes incoming files to
`File(saveDir, sanitize(offer.name))` + truncating `outputStream()`
(ui/Main.kt:674,678) with NO uniquifier anywhere in the file, while the CLI
got `uniqueSaveFile` (atomic createNewFile, Main.kt:734-742) and Android got
`uniqueDestination` (VM:807) for the identical audit finding → same-named
offers silently overwrite/corrupt. SMP-4 asymmetry confirmed — desktop-ui has
watchTransfer (:750) ending at first terminal state; CLI (:519-526) and
Android VM (:716-721) collect StateFlows forever, 1-2 leaked coroutines per
transfer. Section-wide clean bills verified by agent and spot-checked: NO
sendFile source-close recurrence (IOSB-11 stayed iOS-only), sink ownership
correct in all 3, appId parity `p2pkit-desktop-sample` across all 4 samples,
manifest matches README perm set. Dominant pattern: 2026-06 audit fixes
propagated to only a subset of the three sibling samples — uniquify (2/3),
CE-safe catch (2/3), terminal sanitization (1/3), reason bounding (1/3),
collector cleanup (1/3); samples lack the parity review gate transports have).

| File | Lines | Status | Tests covering | Missing tests | Findings | Improvements | Verdict |
|---|---|---|---|---|---|---|---|
| p2p-sample-desktop/…/Main.kt | 774 | reviewed | none (manual — INTERNAL_TESTING §A-§K) | arg parsing + uniqueSaveFile collision (A16 §3 r5) | SMP-2 (Low), SMP-3 (Low, CE swallow), SMP-4 (Low), SMP-5 (Low, no SIGINT hook) | SMP-13 | needs fix (Low) |
| p2p-sample-desktop-ui/…/Main.kt | 1752 | reviewed | none (manual) | destination-collision test (A16 §3 r1) | SMP-1 (Med, data loss), SMP-6 (Low), SMP-7 (Low) | SMP-9, SMP-10 | needs fix (Med) |
| p2p-sample-android/…/MainActivity.kt | 1354 | reviewed | none (no instrumented tests) | grant→resume flow manual-only | SMP-6 (Low, logcat leg) | SMP-11, SMP-12 | needs fix (Low) |
| p2p-sample-android/…/P2pKitViewModel.kt | 1215 | reviewed | none | stop()/onCleared ordering untested | SMP-4 (Low), SMP-6 (Low) | SMP-9, SMP-11 | needs fix (Low) |
| p2p-sample-android/…/P2pKitSampleApplication.kt | 16 | reviewed | none | n/a | | | clean |
| p2p-sample-android/src/main/AndroidManifest.xml | 41 | reviewed | none | n/a — matches README perm set | | | clean |
| p2p-sample-android/src/main/res/values/themes.xml | 4 | reviewed | none | n/a | | | clean |
| sample-kmp-shared [common] Demo.kt | 35 | reviewed | KmpConsumerLoopbackTest (jvm) | failure path documented, untested | | | clean |
| sample-kmp-shared [common] P2pKitFactory.kt | 15 | reviewed | KmpCallsiteSmokeTest, KmpConsumerLoopbackTest | n/a | | | clean |
| sample-kmp-shared [android] P2pKitFactory.android.kt | 35 | reviewed | none (module has no android host test) | pre-init error() path (A16 §3 r2) | | | clean |
| sample-kmp-shared [jvm] P2pKitFactory.jvm.kt | 12 | reviewed | KmpConsumerLoopbackTest | n/a | | | clean |
| sample-kmp-shared [commonTest] KmpCallsiteSmokeTest.kt | 22 | reviewed | self | compile-resolution smoke by design — acceptable | | | clean |
| sample-kmp-shared [jvmTest] KmpConsumerLoopbackTest.kt | 130 | reviewed | self (real mDNS+TCP loopback) | happy-path only; subscription-race pin (A16 §3 r3) | SMP-8 (Low, latent flake — Uncertain frequency, mechanism confirmed) | SMP-14 | needs fix (test) |

## S12 — iOS/Xcode build integration — reviewer A10-IOSBUILD — 10/10 reviewed ✅

Report: `.review-2026-07/reports/A10-iosbuild.md` (verified by orchestrator:
IOSB-3 confirmed High — run-ios-app.sh:47-50 `find` over the GLOBAL
DerivedData root takes the first `p2pkit-sample.app` in traversal order;
xcodebuild (:35-40) pins no -derivedDataPath → with a second
checkout/worktree (this repo uses .claude/worktrees/) simctl install (:74)
can install a stale bundle, silently defeating the provenance gate.
IOSB-1 confirmed — set -euo pipefail (:19) + plain assignment (:58) abort on
the empty-match grep pipeline, making the FATAL hint (:63-67) dead in exactly
its target case (find at :47 exits 0, so THAT guard is reachable — contrast
holds). IOSB-2 confirmed — `grep -E "…${SIM_NAME} \("` (:59) interpolates the
device name unescaped into an ERE; parenthesized stock names never match
while the xcodebuild destination is exact-string → build succeeds, run dies.
Load-bearing plist keys verified in project.yml:34-36 matching
LanConstants.SERVICE_TYPE_BONJOUR. A10's out-of-scope question answered:
"create not @Throws → iOS process crash" IS catalogued —
PROBLEMS_P2PKIT.md:349 `ios-start-create-not-throwing-crashes-process`;
P2pKit.kt:190 confirmed unannotated → [CATALOGUED], no new finding).

| File | Lines | Status | Tests covering | Missing tests | Findings | Improvements | Verdict |
|---|---|---|---|---|---|---|---|
| iosApp/ContentView.swift | 1534 | reviewed | none automated; manual smoke matrix + INTERNAL_TESTING recipes | Swift-bridge exercise absent (A10 §1) | IOSB-11 (Low, contract violation in sample) | IOSB-12 | needs fix (Low) |
| iosApp/P2pKitSampleApp.swift | 10 | reviewed | n/a (trivial @main) | none | | | clean |
| iosApp/Info.plist | 36 | reviewed | none (config) | A10 §3 r1 (built-product plist-key check) | IOSB-9 (Low, generated-file trap) | | needs fix (Low) |
| iosApp/build.gradle.kts | 27 | reviewed | none (manual harness task) | none (macOS-only, acceptable) | | IOSB-10 | clean (improvements) |
| iosApp/project.yml | 74 | reviewed | manual (regenerated every run) | A10 §3 r1 | | | clean |
| iosApp/scripts/README.md | 44 | reviewed | n/a (doc) | n/a | IOSB-6 (Low, stale doc — teaches double-wiring) | | needs fix (doc) |
| iosApp/scripts/check-xcframework.sh | 107 | reviewed | manual recipe STABILIZATION §provenance (matches new behavior) | A10 §3 r3 (unresolvable-stamp case) | IOSB-4 (Low), IOSB-5 (Low) | | needs fix (Low) |
| scripts/run-ios-app.sh | 82 | reviewed | none (manual harness) | A10 §3 r2, r4 | IOSB-1 (Med), IOSB-2 (Med), IOSB-3 (High) | | needs fix (High) |
| p2p-transport-lan/src/nativeInterop/cinterop/p2pkit_nw.def | 7 | reviewed | indirect: all iosSimulatorArm64 tests link through it | wrong-SDK regression only via full iOS run | | IOSB-8 | clean (improvements) |
| p2p-transport-lan/src/nativeInterop/cinterop/p2pkit_nw.h | 99 | reviewed | IosRawConnectionTest + IosLanLoopbackTest (all 3 helpers, real NWConnections) | A10 §3 r5 (leak assertion) | | IOSB-7 (ownership verified correct under ARC) | clean (improvements) |

## S13 — Build, Gradle, publishing & release — reviewer A11-BUILD — 26/26 reviewed ✅

Report: `.review-2026-07/reports/A11-build.md` (verified by orchestrator:
BLD-2 grep-confirmed — `withJavadocJar()` only in provisioning-desktop, doc
claims otherwise at STABILIZATION:76-77; BLD-1 `Instant.now()` at
p2p-core/build.gradle.kts:42 confirmed — accurate). Publishing scope (exactly
4 modules), signing wiring, POM completeness, stock wrapper scripts, and every
CLAUDE.md build-command claim verified correct. adca586 stamp writer sound.

| File | Lines | Status | Tests covering | Missing tests | Findings | Improvements | Verdict |
|---|---|---|---|---|---|---|---|
| build.gradle.kts (root) | 62 | reviewed | gate builds | signing skip/keyed path unautomated | | | clean |
| settings.gradle.kts | 33 | reviewed | implicit | fresh-machine JDK-17 bootstrap | | BLD-5, BLD-10 | clean (impr. noted) |
| gradle.properties | 16 | reviewed | implicit | caching benefit defeated by BLD-1 | | | clean |
| gradle/gradle-daemon-jvm.properties | 12 | reviewed | implicit | — | | | clean |
| gradle/libs.versions.toml | 41 | reviewed | implicit | — | | BLD-10 (stale androidx set) | clean |
| gradle/wrapper/gradle-wrapper.jar | binary | reviewed | implicit | — | | | clean (valid zip, pairs with properties) |
| gradle/wrapper/gradle-wrapper.properties | 7 | reviewed | implicit | — | | BLD-6 (no sha256 pin) | clean (impr. noted) |
| gradlew | 248 | reviewed | implicit | — | | | clean (stock 9.3.1) |
| gradlew.bat | 93 | reviewed | none | — | | | clean (stock) |
| .editorconfig | 20 | reviewed | none | — | | BLD-10 (ktlint knobs unwired) | clean (impr. noted) |
| .gitignore | 34 | reviewed | none | — | BLD-3 (Low: `*.log` vs evidence logs) | BLD-10 (dead rules) | needs fix (Low) |
| .run/Build iOS Framework (Device).run.xml | 24 | reviewed | none | — | | | clean (task exists) |
| .run/Build iOS Framework (Simulator).run.xml | 24 | reviewed | none | — | | | clean |
| .run/Compose Desktop UI.run.xml | 24 | reviewed | none | — | | | clean |
| .run/JVM CLI Alice.run.xml | 24 | reviewed | none | — | | | clean |
| .run/JVM CLI Bob.run.xml | 24 | reviewed | none | — | | | clean |
| .run/iOS Sample (Simulator).run.xml | 24 | reviewed | none | — | | | clean (SIM_NAME default consistent) |
| .run/iOS Simulator Tests.run.xml | 24 | reviewed | gate | — | | | clean |
| p2p-core/build.gradle.kts | 143 | reviewed | gate builds | MT-BLD-3 (no-change rebuild UP-TO-DATE) | BLD-1 (Med, catalogued-open), BLD-2 (High) | BLD-4, BLD-7 | needs fix (High) |
| p2p-transport-lan/build.gradle.kts | 164 | reviewed | gate builds + manual stamp recipe | MT-BLD-4 (stamp TestKit) | BLD-2 | BLD-4, BLD-7, BLD-9 | needs fix (High) |
| p2p-network-provisioning-android/build.gradle.kts | 62 | reviewed | testAndroidHostTest gate | publish-set assertion | BLD-2 | BLD-7 | needs fix (High) |
| p2p-network-provisioning-desktop/build.gradle.kts | 63 | reviewed | test gate | — | | BLD-10 (redundant dep) | clean (has javadoc jar) |
| p2p-sample-android/build.gradle.kts | 48 | reviewed | assembleDebug | — | | BLD-10 (versionName literal) | clean (impr. noted) |
| p2p-sample-desktop/build.gradle.kts | 30 | reviewed | manual recipes | — | | BLD-8 (CC-incompatible stdin) | clean (impr. noted) |
| p2p-sample-desktop-ui/build.gradle.kts | 41 | reviewed | manual runs | — | | | clean (mainClass verified) |
| sample-kmp-shared/build.gradle.kts | 27 | reviewed | jvmTest gate | — | | | clean |

## S14 — Documentation — reviewers A13a (core) / A13b (audit) — 26/26 reviewed ✅

Batch-b report: `.review-2026-07/reports/A13b-docs-audit.md` (verified by
orchestrator: DOCB-1 confirmed High — AUDIT_REPORT:60-86 deferred list quotes
verified stale in ≥10/16 bullets (e.g. :66 "no builder knob" vs Builders.kt:81
knob; :67 "no dedup" vs PeerRegistry dedupe — both independently verified
earlier this campaign; :69 "write() has no deadline" vs the shipped watchdog);
CLAUDE.md routes every future agent to this list. DOCB-2 confirmed —
AUDIT_REPORT:25 "adopt the remote's HELLO identity" is the opposite of
012e49e's shipped keep-dialed-identity semantics. DOCB-5 confirmed —
PROBLEMS:217 prescribes the unconditional peerId assert that would
re-break manual-IP (C1) and :196 prescribes closeAll-without-reopen (the C7
regression half). DOCB-6 confirmed — checklist:269 names `p2pkit-incoming/`
for iOS; the app uses `Documents/P2pKitInbox/` (ContentView:437). DOCB-8
confirmed — "Reconnect target changed"/"Reconnect attempt" grep to ZERO hits;
actual format is `reconnect: attempt=N/M` (SessionManager.kt:537,562,580) →
runbook R3/E3 PASS counters are unsatisfiable. LICENSE verified complete
Apache-2.0, consistent with all four module POMs).

Batch-a report: `.review-2026-07/reports/A13a-docs-core.md` (verified by
orchestrator: DOCA-2/3/10 confirmed — README:44/:219/:233 describe shipped
provisioning in future tense, and README:63 + spec:99 both claim iOS
provisioning "will continue to throw Unsupported … in every future version"
vs shipped iosManualIp(). DOCA-16 confirmed — spec:669 documents
`Connected → Closing → Closed` but grep shows ZERO assignments of
ConnectionState.Closing (only a comparison at P2pSessionImpl:319). DOCA-8
confirmed — ProtocolConstants:60 MAX_TOTAL_PENDING_BYTES=16 MiB session-closing
cap absent from spec §13.4. DOCA-13 confirmed — INTERNAL_TESTING:202 says
"Expected: all green — 20 test methods"; actual appleTest count is 29 with 2
documented expected failures → pressures a release runner toward masking.
DOCA-21 confirmed — template project.yml carries live 3-step usage
instructions, no deprecation marker, and `info: path:` with NO properties
block → xcodegen generate wipes the checked-in plist's LAN keys. Working-tree
CLAUDE.md verified claim-by-claim accurate (needs committing — HEAD's copy has
a false publishing claim, DOCA-1). Gap-analysis file identified (DOCA-20):
maintainer-commissioned AI strategic review, pinned to 2026-07-03 @ 5568355,
11/12 spot-checked claims accurate; recommendation keep + commit with banner —
user decision. Its SecurityManager read-path-bypass observation
(SessionManager.kt:301 vs :379) verified true by A13a — encryption-milestone
territory, catalogued for S3).

| File | Lines | Status | Tests covering | Missing tests | Findings | Improvements | Verdict |
|---|---|---|---|---|---|---|---|
| CLAUDE.md (working-tree modified) | 108 | reviewed | n/a (doc) | n/a | [KNOWN PRM-12], DOCA-1 (Low — HEAD copy false; working tree verified accurate, commit it) | | needs fix (Low) |
| README.md | 417 | reviewed | n/a (doc) | n/a | DOCA-2 (Med), DOCA-3 (Med), DOCA-4 (Low), DOCA-5 (Low), DOCA-6 (Low), DOCA-7 (Low) | DOCA-I1 | needs fix (Med) |
| P2pKit-Spec.md | 1440 | reviewed | n/a (doc) | close-sequence + metadata pins (A13a §3) | [KNOWN API-4, SES-1, API-14], DOCA-8 (Med), DOCA-9 (Low), DOCA-10 (Med), DOCA-11 (Low), DOCA-12 (Low), DOCA-15 (Low), DOCA-16 (Med) | DOCA-I4 | needs fix (Med) |
| INTERNAL_TESTING.md | 454 | reviewed | n/a (doc) | n/a | DOCA-13 (Med — "all 20 green" vs 29 w/ 2 expected failures) | | needs fix (Med) |
| docs/STABILIZATION_AND_RELEASE.md | 218 | reviewed | n/a (doc) | n/a | DOCA-14 (Med — gate lacks metadata-drop + build-identity boxes) | DOCA-I2, DOCA-I3 | needs fix (Med) |
| docs/LAN_DIAGNOSTICS_PROTOCOL.md | 211 | reviewed | n/a (doc) | n/a | DOCA-18 (Low — wrong hotspot subnet; broken table pipes; trace strings otherwise verified verbatim) | | needs fix (Low) |
| docs/production-readiness.md | 177 | reviewed | n/a (doc) | n/a | DOCA-17 (Low) | | needs fix (Low) |
| WORKSPACE_SYNC_DASHBOARD.md | 229 | reviewed | n/a (doc) | n/a | DOCA-13 (shared counts), DOCA-3 (shared wording) | | needs fix (Low) |
| REMEDIATION_2026-07.md | 73 | reviewed | n/a (doc) | n/a | [KNOWN IDN-5 :63], [KNOWN FIL-1 → :57 #21 disposition + :10 tally now inaccurate], DOCA-19 (Low) | | needs fix (Low) |
| P2PKIT_GAP_ANALYSIS_2026-07.md (untracked) | 197 | reviewed | n/a (doc) | n/a | DOCA-20 (identification: maintainer-commissioned AI strategic review @ 5568355; 11/12 claims accurate; §4.3 overstated; P7 wording collides with no-masking rule) | | identified — recommend keep + commit w/ banner (user decision) |
| docs/ios-sample-app/ContentView.swift | 86 | reviewed | none (deprecated template) | n/a | DOCA-21a/d (no deprecation marker; orphan T1 pointer) | | needs fix (marker) |
| docs/ios-sample-app/Info.plist | 48 | reviewed | none (deprecated template) | n/a | DOCA-21b (wiped by own project.yml usage; no marker) | | needs fix (marker) |
| docs/ios-sample-app/KitController.swift | 122 | reviewed | none (deprecated template) | n/a | | | clean (exemplary drift header) |
| docs/ios-sample-app/P2pKitSampleApp.swift | 16 | reviewed | none (deprecated template) | n/a | DOCA-21a (copy invitation, no marker) | | needs fix (marker) |
| docs/ios-sample-app/README.md | 26 | reviewed | none (deprecated template) | n/a | | | clean (exemplary banner) |
| docs/ios-sample-app/project.yml | 42 | reviewed | none (deprecated template) | n/a | DOCA-21b/c (Med — live usage steps wipe LAN plist keys; stale wiring; no marker) | | needs fix (Med) |
| AUDIT_REPORT_2026-06.md | 107 | reviewed | n/a (doc) | doc-drift guard (A13b §3 r2) | DOCB-1 (High — deferred list ~10/16 stale), DOCB-2 (Med), DOCB-3 (Low) | | needs fix (High) |
| PROBLEMS_P2PKIT.md | 1189 | reviewed | n/a (doc) | n/a | DOCB-4 (Med — fixed HIGHs shown open), DOCB-5 (Med — 3 fix texts regressive if followed) | | needs fix (Med — banner, not re-annotation) |
| docs/audit-evidence/README.md | 80 | reviewed | n/a (doc) | n/a | | DOCB-I2 | clean (improvements) |
| docs/audit-evidence/dns-sd-browse.log | 9 | reviewed | n/a (artifact) | n/a | | | clean |
| docs/audit-evidence/jvm-cli.log | 10 | reviewed | n/a (artifact) | n/a | | | clean |
| docs/audit-real-device-checklist.md | 147 | reviewed | n/a (doc) | n/a | DOCB-11 (Low — obsolete v0.3 gate, no banner) | | needs fix (doc) |
| docs/hardware-validation-checklist.md | 334 | reviewed | n/a (doc) | n/a | DOCB-6 (Med — wrong iOS dir masks leak check), DOCB-7 (Low) | DOCB-I3 | needs fix (Med) |
| docs/stabilization-stress-tests.md | 298 | reviewed | n/a (doc) | n/a | | | clean (model superseded banner) |
| docs/v0.4-cumulative-validation-runbook.md | 978 | reviewed | n/a (doc) | signature-parity script (A13b §3 r1) | DOCB-8 (Med — unsatisfiable PASS counters), DOCB-9 (Low), DOCB-10 (Low) | | needs fix (Med) |
| LICENSE | 190 | reviewed | n/a (legal text) | n/a | | DOCB-I1 (README lacks License section) | clean (Apache-2.0, POM-consistent) |

## S15 — Test fixtures — reviewer A12-TESTS — 4/4 reviewed ✅

Base: `p2p-core/src/commonTest/kotlin/dev/p2pkit/core/testfixtures/`.
Report: `.review-2026-07/reports/A12-tests.md` (S15 fixture-fidelity review +
repo-wide test-quality sweep; per-file verdicts in report §1. Merged into the
register during consolidation, where TST-1 (High) was re-verified Confirmed
against source and absorbed duplicate SES-10; TST-3 product impact confirmed
via CON-3. Fixture severities: TST-1 High, TST-3 Med, TST-2/TST-4 Low,
TST-5..8 improvements).

| File | Lines | Status | Tests covering | Missing tests | Findings | Improvements | Verdict |
|---|---|---|---|---|---|---|---|
| FakeDataTransport.kt | 65 | reviewed | SessionFlowTest, ReconnectPolicyTest, SessionReconnectRotationTest, NetworkPathRecoveryTest, SimultaneousOpenTest, ManualPeerIdentityTest, HandshakeIdentityTest, LocalIdentityTest, PermissionGateTest | incoming flow can never terminate with a cause (TST-3); start() contract unmodeled (TST-6) | TST-3 (Med) | TST-6, TST-7 | needs fix (Med) |
| FakeDiscoveryTransport.kt | 68 | reviewed | SessionReconnectRotationTest, NetworkPathRecoveryTest, ManualPeerIdentityTest, PermissionGateTest, LocalIdentityTest, HandshakeIdentityTest (NOT PeerRegistryTest — rolls its own `FakeDiscovery`, TST-14) | overflow semantics diverge from all 3 production transports (TST-4); no burst/drop scenario expressible | TST-4 (Low) | TST-8 | needs fix (Low) |
| FakeNetworkPathObserver.kt | 41 | reviewed | NetworkPathRecoveryTest (sole consumer; lifecycle counters asserted at :258-277) | none material — kit start/close ordering pinned by its consumer | | | clean |
| FakeRawConnection.kt | 64 | reviewed | 15 commonTest suites (SessionFlowTest, ReconnectPolicyTest, SessionReconnectRotationTest, NetworkPathRecoveryTest, KeepAliveTest, SimultaneousOpenTest, Handshake*, FileTransfer*, ManualPeerIdentityTest, protocol suites, …) | remote-initiated termination unmodelable (TST-1); no write-fault injection (TST-5) | TST-1 (High, absorbs SES-10), TST-2 (Low) | TST-5, TST-7 | needs fix (High) |

---

**File-count check:** 31+19+13+16+18+20+9+12+5+14+13+10+26+26+4 = **236** ✓
(235 tracked + 1 untracked `P2PKIT_GAP_ANALYSIS_2026-07.md`).
