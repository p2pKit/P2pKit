# P2pKit remediation master tracker

Created: 2026-07-17

Source register: `P2PKIT_FULL_CODE_REVIEW_2026-07-17.md`

Baseline commit: `6a05ccd04fcb6fb8106ed47941618fb6bcfd3fa6`

Working branch: `remediation/full-register-2026-07`

## Purpose and non-negotiable rules

This is the mutable execution record for remediating the source review. The source review is evidence and must not be edited as a substitute for fixing code. The pre-existing `.review-2026-07/` directory and `DEFERRED_ITEMS_REGISTER_2026-07.md` are user-owned and remain outside this program.

The register contains exactly 150 unique findings and 54 separately listed test gaps. No row may be deleted, silently merged, downgraded, or marked irrelevant. A shared architectural fix may cover multiple rows only when the shared root cause is recorded before implementation and every row receives independent acceptance and verification evidence.

Statuses have these meanings:

- `Planned`: inventoried, but the finding-specific analysis and implementation have not started.
- `In Progress`: the current finding/group is being analyzed, implemented, reviewed, or verified.
- `Implemented`: the root fix and required tests exist locally, but all acceptance gates have not passed.
- `Verified`: every acceptance criterion passed from the focused committed state, the committed diff was reviewed, required checks were rerun, and the focused commit was pushed.
- `Blocked`: a concrete product decision, breaking-change approval, physical-device result, credential, or external service is required. Evidence and the exact unblock condition must be recorded.

`Verified` is deliberately stricter than “tests passed once.” A row needs a plan, changed-file ledger, regression tests, exact commands/results, compatibility notes, focused commit hash, pushed branch, and post-commit verification. Test retries must demonstrate determinism; they may not hide failures by weakening assertions, accepting multiple terminal outcomes, increasing timeouts, or adding arbitrary delays.

Operating safeguards:

- Do not advance to a new finding while the active finding is partially implemented, unverified, or has an unresolved regression. A documented `Blocked` boundary ends that unit without pretending it is complete.
- A finding believed invalid or already fixed remains open until concrete code/test evidence is recorded and the owner explicitly approves closure.
- Never rewrite history, force-push, destructively clean the repository, or delete existing/user work. Stage only the focused finding's files.
- Preserve `CancellationException`; do not silently swallow failures, hide warnings, skip required checks, or replace real platform evidence with mocks.
- Breaking API/protocol/security decisions, unavailable hardware, credentials, and external release actions stop before mutation and require explicit authority.
- A blocked unit blocks only itself and genuinely dependent units. Record its IDs, evidence, attempts, options, recommendation, consequences, and exact unblock request; continue every dependency-ready independent unit. Consolidate unresolved owner decisions only when no ready unblocked work remains.

## Baseline inventory

| Register | Count |
| --- | ---: |
| CORE | 30 |
| PROTO | 8 |
| FILE | 15 |
| LAN | 26 |
| PROV-A | 12 |
| PROV-D | 5 |
| SAMPLE | 39 |
| BUILD | 15 |
| Findings total | 150 |
| Explicit test gaps | 54 |

Current finding state: 105 `Planned`, 7 `Implemented`, 29 `Verified`, and 9 `Blocked`. PEER-CTRL-01 locally implements `CORE-02/04/05/14`; `CORE-15/17/27/28` are isolated at documented public-API/model decisions after completing their safe independent portions. XFER-01 verified `PROTO-04` and `FILE-01/02/03/07/08/09/10/12/14`; `FILE-15` is implemented pending real Android-provider instrumentation, while `FILE-05/06/11` remain at documented API decisions. SEC-01 remains implemented but externally gated by cryptographic audit, physical interoperability, hostile-network validation, and the final green repository gate.

### Baseline gate evidence and reusable command catalog

The following failures are preserved from the source review baseline; they were not rerun while creating this documentation-only tracker:

| Gate | Baseline result at `6a05ccd` |
| --- | --- |
| `./gradlew :p2p-sample-android:lintDebug` | Red: one `CoarseFineLocation` error and three warnings |
| Forced `:p2p-core:jvmTest` | 258 tests, one failure: `FileTransferFlowTest.cancelMidStreamPropagatesToReceiver`; sender was `Completed`, required `Cancelled` |
| `:p2p-core:iosSimulatorArm64Test` | 243 tests, one 3,500 ms timeout: `SessionReconnectRotationTest.reconnectUsesRefreshedHintsAfterPeerRegistryUpdate` |
| `:p2p-transport-lan:iosSimulatorArm64Test` | 37 tests, two 30-second timeouts: `IosLanLifecycleTest.peerLostEventFiresWhenPeerStops` and `advertiseStopRestartProducesObservablePeerChurn`; one diagnostic intentionally skipped |
| Compiler/test hygiene | Existing ungated ExperimentalCoroutinesApi, deprecated multicast API, and Android nullable type warnings |

Every finding record must replace placeholders with exact commands. The standard escalation ladder is:

1. Run the smallest named test/class/task proving the regression.
2. Run the complete affected source-set/module test and compile tasks.
3. Run every affected JVM, Android, iOS simulator/device, KMP, sample, lint/static, publication, and integration target.
4. Repeat concurrency/timing tests with deterministic synchronization from the committed state.
5. Run repository-wide `check` plus the separate Android lint, publication-artifact, XCFramework/Xcode, and external-consumer gates; record every task and result rather than writing only “full gate passed.”

### Per-finding execution-record template

Copy this template below the active unit before implementation and fill every field:

| Field | Required content |
| --- | --- |
| Finding/group | IDs, raw severities, why any grouping shares one root cause |
| Status | Planned / In Progress / Implemented / Verified / Blocked |
| Root cause/reproduction | Current-code evidence and deterministic reproduction result |
| Affected surface | Files, components, modules, targets/platforms, public contracts |
| Compatibility/migration | Source, binary, runtime, wire, data, security, rollout implications |
| Plan/cleanup | Long-term design, ownership, cancellation, rollback, failure behavior |
| Acceptance criteria | Precise independently testable results for every finding/gap conjunct |
| Files changed | Exhaustive focused diff ledger |
| Tests added/updated | Exact test names and why each fails before the fix |
| Commands/results | Exact commands, counts, failures/warnings/skips, repeat evidence |
| Diff review | External-PR-style review result, equivalent-implementation search, regressions checked |
| Remaining risks | None, or concrete residual risk/blocker without downgrading |
| Source control | Branch, focused commit hash/message, pushed remote/ref, committed diff review |
| Post-commit verification | Commands rerun from committed state and exact results |

## Dependency-ordered execution plan

The order below is a dependency graph, not permission to combine every row in a wave into one commit. Each execution unit remains focused; independent findings get independent commits.

| Order | Unit | Scope | Why it is ordered here | Gate before advancing |
| ---: | --- | --- | --- | --- |
| 0 | GOV-01 | Tracker/baseline; test-foundation findings CORE-30 and gap LAN-T11 are executed before the affected suites | Establishes traceability and deterministic test infrastructure before source fixes | 150 findings/54 gaps reconciled; baseline gate catalog preserved; fixture isolation completed before dependent work |
| 1 | SEC-01 | CORE-06, CORE-07 | Security must own the sole raw byte stream and determines identity/wire/public compatibility; coupled prerequisites remain separately assigned as recorded below | Explicit approval of all SEC-01 decisions; implementation resumes after focused prerequisite sub-units |
| 2 | REL-REMOTE-01 | BUILD-02 | High release blocker is actionable locally even though real upload is external | Portal choice/configuration and local dry-run complete; ENV-07 alone retains credentialed upload evidence |
| 3 | REL-ABI-01 | BUILD-01; gaps CORE-T13, PS-T09 | Public artifacts must be independently consumable before new public security/API dependencies land | Temp-published JVM/Android/KMP/iOS consumers compile with correct API scopes |
| 4 | LIF-SES-01 | CORE-01, CORE-03, CORE-08, CORE-09, CORE-10, CORE-11, CORE-12, CORE-13, CORE-16, CORE-23, CORE-24; gaps CORE-T01, CORE-T02, CORE-T07, CORE-T08, CORE-T09, CORE-T10 | Terminal generation, connect ownership, setup deadline, inbound recovery, and close contract underpin later systems | Exact cancellation/rollback/bounded cleanup results; CORE-13 follows approved SEC-01 setup order; CORE-24 API decision approved |
| 5 | PEER-CTRL-01 | CORE-02, CORE-04, CORE-05, CORE-14, CORE-15, CORE-17, CORE-27, CORE-28; gaps CORE-T03, CORE-T04, CORE-T05, CORE-T06 | Correct aggregation/arbitration/control plane/state/public values precede higher layers | Multi-source/direction/backpressure/monotonic tests prove one precise result |
| 6 | ID-01 | CORE-18, CORE-19, CORE-20, CORE-21, CORE-29, SAMPLE-35; gap CORE-T11 | Secure identity depends on collision-safe, concurrent, stable, atomic persistence and per-sample isolation | All CORE-T11 conjuncts pass, including concurrent first creation; approved migration/key contract implemented |
| 7 | PATH-PERM-01 | CORE-22, CORE-25, CORE-26; gap CORE-T12 | Path generation/cleanup and Android permission defaults precede provisioning | Platform observer lifecycle/generation and permission matrix pass |
| 8 | PROV-A-HIGH-01 | PROV-A03 | Mixed Medium/High lifecycle race is sequenced at its maximum severity after core lifecycle prerequisites | Concurrent close/start/join has one owner/result; real-platform proof remains linked through PS-T01 |
| 9 | PARSE-01 | PROTO-01, PROTO-02, PROTO-03, PROTO-04, PROTO-05, PROTO-06, PROTO-07, PROTO-08; gaps PT-T01, PT-T02, PT-T03, PT-T04, PT-T05, PT-T21 | Parser/version/API decisions precede hostile records and transfer protocol changes | Linear work, early/version/type validation, strict text/structure, isolated diagnostics, metadata contract, fuzz/property gates |
| 10 | XFER-01 | FILE-01, FILE-02, FILE-03, FILE-05, FILE-06, FILE-07, FILE-08, FILE-09, FILE-10, FILE-11, FILE-12, FILE-14, FILE-15; gaps PT-T06, PT-T07, PT-T08, PT-T09, PT-T10, PT-T11, PT-T12, PT-T13, PT-T14, PT-T15, PT-T17, PT-T19, PT-T20 | Transactional ownership/state is prerequisite to durability protocol and sample receives | Deterministic cancellation/timeouts/sink serialization/release/boundaries/platform metadata; FILE-04/PT-T16 are not claimed here |
| 11 | XFER-PROTO-01 | FILE-04, FILE-13; gaps PT-T16, PT-T18 | Receiver acknowledgement and digest intentionally alter the wire contract | Approved protocol revision; durability/integrity failures produce one exact sender result |
| 12 | SAMPLE-HIGH-01 | SAMPLE-01, SAMPLE-02, SAMPLE-03, SAMPLE-04 | High sample data-integrity/security/availability work immediately follows completed transfer dependencies | Failure propagation, atomic names, consent/quota/free-space, bounded binary history proven |
| 13 | LAN-LIFE-01 | LAN-01, LAN-02, LAN-03, LAN-04, LAN-05, LAN-06, LAN-07, LAN-08, LAN-09, LAN-10, LAN-11, LAN-12, LAN-23, LAN-24, LAN-25, LAN-26; gaps LAN-T02, LAN-T03, LAN-T04, LAN-T05, LAN-T06, LAN-T10 | Resource ownership/admission/cancellation/recovery precede selection/trust work | Repeated JVM/Android/Apple lifecycle gates; no ghost, stale, unbounded, or undrained resource |
| 14 | LAN-NET-01 | LAN-13, LAN-14, LAN-15, LAN-16, LAN-17, LAN-18, LAN-19, LAN-20, LAN-22; gaps LAN-T01, LAN-T07, LAN-T08, LAN-T09 | Network selection/liveness/schema/trust/permissions/diagnostics build on sound lifecycle | All hostile-record and platform-selection conjuncts pass; hardware criteria remain explicit |
| 15 | PROV-A-01 | PROV-A01, PROV-A02, PROV-A04, PROV-A05, PROV-A06, PROV-A07, PROV-A08, PROV-A09, PROV-A10, PROV-A11, PROV-A12; gaps PS-T01, PS-T02 | Remaining Android provisioning builds on fixed PROV-A03 lifecycle ownership | Fake plus real callback/permission/LinkProperties/process-binding tests pass |
| 16 | PROV-D-01 | PROV-D01, PROV-D02, PROV-D03, PROV-D04, PROV-D05; gap PS-T03 | Desktop provisioning validation/interface behavior and test isolation | Boundary/ranking/fatal propagation/global-state restoration tests pass |
| 17 | SAMPLE-XFER-01 | SAMPLE-05, SAMPLE-06, SAMPLE-07, SAMPLE-12, SAMPLE-13, SAMPLE-14, SAMPLE-15, SAMPLE-22, SAMPLE-23, SAMPLE-24, SAMPLE-34; gaps PS-T06, PS-T07, PS-T08 | Remaining sample transfer/path/history changes consume fixed transfer APIs | Every conjunct for desktop/Swift/path tests passes; partial files/resources are cleaned deterministically |
| 18 | SAMPLE-LIFE-01 | SAMPLE-08, SAMPLE-09, SAMPLE-10, SAMPLE-11, SAMPLE-16, SAMPLE-17, SAMPLE-18, SAMPLE-19, SAMPLE-20, SAMPLE-21, SAMPLE-25, SAMPLE-26, SAMPLE-27, SAMPLE-28, SAMPLE-29, SAMPLE-30, SAMPLE-31, SAMPLE-32, SAMPLE-33, SAMPLE-36, SAMPLE-37, SAMPLE-38, SAMPLE-39; gaps PS-T04, PS-T05 | Lifecycle/CLI/UI/permission/logging/consumer correctness after library contracts settle | Full Android sample tests and every CLI collector/shutdown conjunct; all samples build/lint |
| 19 | REL-PROV-01 | BUILD-03, BUILD-07, BUILD-09, BUILD-10, BUILD-11, BUILD-12, LAN-21 | Reproducibility/provenance/XCFramework/launcher work follows stable source/artifact flow | Repeat builds deterministic; declared outputs and scripts behave under deletion/concurrency |
| 20 | REL-GATE-01 | BUILD-08, BUILD-14, BUILD-15 | Deterministic repository gate blockers/warnings must be removed, not waived | Android lint and warning/static gates are green |
| 21 | REL-SUPPLY-01 | BUILD-04, BUILD-05, BUILD-06, BUILD-13 | Publication validation, wrapper, supply-chain and release maintenance close after artifact shape stabilizes | Wrapper/checksums/signatures/scopes/archives/CI/locks/SBOM/ABI/release policy validated |
| 22 | FINAL-01 | All 150 findings, all 54 gaps, ENV-01, ENV-02, ENV-03, ENV-04, ENV-05, ENV-06, ENV-07 | Repository-wide closure only after every focused unit | Repeated full gate green; physical-device/two-machine/hostile-network/external release evidence complete; every row Verified |

### Known external and decision boundaries

- SEC-01's security, wire, migration, and storage-A decisions were approved and frozen on 2026-07-17. Implementation is active; only external professional cryptographic audit and physical-device/hostile-network certification remain blocked release evidence.
- FILE-04/FILE-13 require a completion/digest wire-protocol decision; they cannot be declared compatible by silently reinterpreting existing frames.
- PROV-A12, parts of LAN-T01/LAN-T07, and FINAL-01 require physical Android/Apple devices or platform instrumentation that may not be available locally.
- BUILD-02 requires release-service configuration and ultimately external credentials; credentials must never be committed.
- Remote publication, signing identity, vulnerability-service results, two-machine validation, and hostile-network certification remain explicit external evidence, not inferred from unit tests.

## Finding traceability register

The `Unit/dependencies` column identifies ordering, not automatic commit grouping. `Plan/code`, `Tests`, `Commit/push`, and `Verification` must be replaced with links or exact evidence as work progresses.

### Core runtime, API, identity, and sessions (30)

| ID | Severity | Finding | Unit/dependencies | Status | Plan/code | Tests | Commit/push | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CORE-01 | High | Stop does not serialize terminal lifecycle with ongoing operations | LIF-GEN-01 (first LIF-SES-01 slice) | Verified | Terminal generation gate, stale-resource compensation, atomic session-registration commit | CORE-T01 | `a4e0bb0`; tracker evidence pending push | Focused committed suite + iOS Simulator + Android compilation pass; only registered FILE-04 full-JVM baseline remains |
| CORE-02 | High | PeerRegistry is not a correct multi-transport aggregator | PEER-CTRL-01 after LIF-SES-01 | Implemented | Per-transport contributions with merged hints/capabilities and source-specific loss/staleness | CORE-T03 | PEER-CTRL commit pending | Focused + complete JVM/iOS pass |
| CORE-03 | High | Cancelled connect can poison coalescing and leak a live session | CORE-SESSION-01 | Verified | Transactional raw/session/pending ownership with forced rollback before commit | CORE-T02 | `68934be`; test follow-up `82a9b41`; pushed | Dial/HELLO/security/pre-commit cancellation and exact retry pass on JVM/iOS |
| CORE-04 | High | Application receive backpressure blocks protocol controls | PEER-CTRL-01 after LIF-SES-01 | Implemented | Separate delivery coroutine behind count/byte budget; overflow fails rather than drops | CORE-T05 | PEER-CTRL commit pending | Slow collector cannot block PONG/CLOSE; overflow exact Failed |
| CORE-05 | High | Duplicate arbitration treats every active duplicate as simultaneous-open | PEER-CTRL-01 after LIF-SES-01 | Implemented | Store registration direction; arbitrate only opposite-direction candidates | CORE-T04 | PEER-CTRL commit pending | Repeated inbound candidates never churn either PeerId ordering |
| CORE-06 | High security limitation | Identity is unauthenticated and traffic plaintext | SEC-01 | Implemented | Authenticated v2 is the default; explicit deprecated legacy only | Noise/KAT, identity, raw-confidentiality, authorization, integration, LAN loopback | `b79c9ba`, pushed to `origin/remediation/full-register-2026-07` | Local platform/module gates pass; external certification remains |
| CORE-07 | Medium architecture | Security extension cannot safely implement encryption | SEC-01 | Implemented | Security owns the sole raw reader before protocol construction | Single-collector, cancellation, close-once, encrypted-HELLO tests | `b79c9ba`, pushed to `origin/remediation/full-register-2026-07` | Local platform/module gates pass; external certification remains |
| CORE-08 | Medium | SessionStore reads mutable HashMap without mutex | CORE-SESSION-01 | Verified | Immutable published registration snapshot | Concurrent read/mutation regression | `68934be`; pushed | 2,000 mutations with four concurrent readers; repeated JVM + iOS pass |
| CORE-09 | Medium | Remotely terminated sessions retain active child Job | CORE-SESSION-01 | Verified | Cancel session runtime after terminal resource cleanup | CORE-T07 | `68934be`; pushed | Exact remote CLOSE and failure job-completion tests pass on JVM/iOS |
| CORE-10 | Medium | Public sessions can retain terminal entries after stop | CORE-SESSION-01 | Verified | Atomic store shutdown drain before watcher cancellation | CORE-T08 | `68934be`; test follow-up `82a9b41`; pushed | stop returns with exact empty public sessions; JVM/iOS pass |
| CORE-11 | Medium | Partial startup/advertising/discovery is not rolled back | LIF-SES-01 | Planned | — | CORE-T09 | — | — |
| CORE-12 | Medium | Teardown can report success while resources remain open | LIF-SES-01 | Planned | — | CORE-T10 | — | — |
| CORE-13 | Medium | Inbound setup timeout excludes operations that can hang | CORE-SESSION-01 | Verified | One outer deadline covers secure preface/security/HELLO; timeout closes raw and releases inbound admission | Full-transaction deadline tests | `68934be`; test follow-up `82a9b41`; pushed | Secure/legacy outbound and idle-inbound deadline+retry pass on JVM/iOS |
| CORE-14 | Medium | Keepalive uses wall clock and misses exact deadline | PEER-CTRL-01 | Implemented | Platform monotonic elapsed clock and `>=` deadline | CORE-T06 | PEER-CTRL commit pending | Exact virtual deadline ignores forward/backward wall jumps |
| CORE-15 | Medium | Global P2pState hides independent feature failures | PEER-STATE-API-01 | Blocked | Requires explicit public per-feature state/error contract; no later success may erase another failure | Feature-state tests | — | Owner API decision recorded below |
| CORE-16 | Medium | One incoming-flow exception permanently disables a transport | LIF-SES-01 inbound recovery | Planned | — | Recollection/backoff tests | — | — |
| CORE-17 | Medium | Public values expose mutable backing storage | IMMUTABLE-MODEL-API-01 | Blocked | Binary and registry ownership snapshots implemented; public data-class collection getters still require a model/API change for cast-proof immutability | Mutation/ownership tests | PEER-CTRL partial pending | Owner compatibility decision recorded below |
| CORE-18 | Medium | Distinct AppIds collide in persistent identity storage | ID-STORE-01 | Verified | Full AppId hash namespace + rollback-safe migration | CORE-T11 | `ee69d09`, pushed | Focused/platform tests pass |
| CORE-19 | Medium | First-use PeerId creation is not concurrency-safe | ID-STORE-01 | Verified | Process/cross-process commit lock + reread winner | CORE-T11 | `ee69d09`, pushed | 16-thread + four-process tests pass repeatedly |
| CORE-20 | Medium | Persistence failure breaks same-instance identity stability | ID-STORE-01 | Verified | Instance memoization on every outcome | CORE-T11 | `ee69d09`, pushed | JVM/iOS failure tests pass |
| CORE-21 | Medium | Android/JVM identity fallback can truncate durable value | ID-STORE-01 | Verified | Android AtomicFile + JVM fsync/atomic move | CORE-T11 | `ee69d09`, pushed | JVM atomic/migration suite + Android compile pass |
| CORE-22 | Medium | Android/iOS path observers retain stale state/cleanup ownership | PATH-PERM-01 | Planned | — | CORE-T12 | — | — |
| CORE-23 | Medium | New session can miss authoritative Unsatisfied path state | CORE-SESSION-01 | Verified | Retained versioned path authority applied after every registration | Registration after prior `Unsatisfied` without re-emission | `68934be`; pushed | Exact Failed outcome passes on JVM/iOS |
| CORE-24 | Medium API gap | NetworkProvisioningManager has no close contract | LIF-SES-01 before provisioning | Planned | — | Close contract/ABI tests | — | — |
| CORE-25 | Low | Android permission diagnostics omit two declared requirements | PATH-PERM-01 | Planned | — | Permission matrix | — | — |
| CORE-26 | Low limitation | Android defaults to no-op path observer | PATH-PERM-01 | Planned | — | Default wiring test | — | — |
| CORE-27 | Low API mismatch | Factories cannot express discovery-only transport | TRANSPORT-FACTORY-API-01 | Blocked | TransportPair data nullability/capability declaration changes implementer source/ABI | Factory/API tests | — | Owner API decision recorded below |
| CORE-28 | Low | Builder validation is incomplete | PEER-CTRL-01 + TRANSPORT-FACTORY-API-01 | Blocked | Names/manual hosts/same-instance duplicates validated; duplicate-kind preflight needs factory capability declaration before resource construction | Boundary/duplicate tests | PEER-CTRL partial pending | Owner API decision recorded below |
| CORE-29 | Low | JVM identity fallback can silently use working directory | ID-STORE-01 | Verified | Validate home/temp roots; explicit failure if none | Property/path failure tests | `ee69d09`, pushed | Blank/invalid property tests pass |
| CORE-30 | Low | Test fixtures hide important race conditions | GOV-01 test foundation | Planned | — | Fixture meta-tests | — | — |

### Protocol and messaging (8)

| ID | Severity | Finding | Unit/dependencies | Status | Plan/code | Tests | Commit/push | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PROTO-01 | High availability | FrameReader performs quadratic copying | PARSE-01 | Verified | Reusable one-frame buffer; header-first allocation; in-place window decode; no tail copies | PT-T01/PT-T21 parser portion | `aa3ac0c`; pushed with batch | Linear relocation/property tests pass JVM/iOS; exact committed state green |
| PROTO-02 | Medium | Frame header version is ignored | SEC-01 dependency; PARSE-01 | Verified | Reader and direct codec reject a mismatched major from the fixed header | PT-T02 | `aa3ac0c`; pushed with batch | Secure-v2/legacy-v1 version tests pass with no fallback |
| PROTO-03 | Medium security/availability | Packet-specific size limits are absent | PARSE-01 | Verified | Header-time per-packet caps plus outbound codec/payload validation | PT-T03/PT-T05 | `aa3ac0c`; pushed with batch | HELLO/OFFER/reason/data/empty-control/unknown cap boundaries pass JVM/iOS |
| PROTO-04 | Medium | Control/chunk structures are too permissive | PARSE-01 before XFER-01 | Verified | Central structural validator plus transfer phase table; REJECT after ACCEPT/streaming is ignored as invalid | PT-T02/PT-T04/PT-T07 | `aa3ac0c`, `68c579f`; pushed | Parser and exact transition regressions pass JVM/iOS from committed state |
| PROTO-05 | Medium | Diagnostics can change protocol behavior | PARSE-01 | Verified | Throwing trace/logger sinks are isolated and disabled; cancellation is preserved | Throwing trace tests | `aa3ac0c`; pushed with batch | Protocol PING still delivered after throwing trace; exact committed JVM/iOS pass |
| PROTO-06 | Low | Remote text accepts invalid/canonicalization-hostile data | PARSE-01 | Verified | Strict UTF-8/Unicode; bounded nonblank control-safe text; leaf file names; exact reason/null distinction | PT-T04/PT-T05 | `aa3ac0c`, `6171588`; pushed with batch | Inbound/outbound malformed UTF-8, controls, bidi, separators, dot segments, blank and boundaries pass |
| PROTO-07 | Low | Malformed/unknown frames can flood logs | PARSE-01 | Verified | Four-message burst plus one suppression summary per fixed category/connection | PT-T03 | `aa3ac0c`; pushed with batch | 100 hostile frames produce exactly five warnings and delivery continues |
| PROTO-08 | Low API surprise | P2pMessage metadata is never transmitted | PARSE-META-01 after SEC-01 | Blocked | Requires an explicit public/API and secure-v2 envelope choice; no silent removal or incompatible wire reinterpretation | Versioned envelope/contract tests | — | Owner decision package deferred until no independent work remains |

### File transfer (15)

| ID | Severity | Finding | Unit/dependencies | Status | Plan/code | Tests | Commit/push | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FILE-01 | High | Cancellation during accept can orphan accepted transfer/sink | XFER-01 after LIF-SES-01/PARSE-01 | Verified | Transactional accept with bounded write and non-cancellable compensating cancel/receiver release | PT-T09 | `68c579f`; pushed | Deterministic gated FILE_ACCEPT cancellation passes JVM/iOS |
| FILE-02 | High availability | Accepted inbound transfers have no idle/overall timeout | XFER-01 | Verified | Positive-progress idle deadline, fixed overall deadline, 64-slot release | PT-T08/PT-T14 | `68c579f`; pushed | Exact virtual-time and full-capacity regressions pass |
| FILE-03 | High data race | Receive, finish, and cancel race on sink | XFER-01 | Verified | Per-transfer operation mutex serializes write/finish/terminal release outside map lock | PT-T10 | `68c579f`; pushed | Gated sink proves cancel waits and terminal cleanup is ordered |
| FILE-04 | High data-integrity contract | Sender completes before receiver durability | XFER-PROTO-01 after XFER-01 | Planned | — | PT-T16 | — | Protocol decision required before implementation |
| FILE-05 | Medium | Actionable offers disappear or arrive stale/out of order | XFER-OFFER-API-01 | Blocked | Requires retained pending-offer state API; `SharedFlow` replay cannot remove stale entries without duplicate live emissions | PT-T13 | — | Owner API decision recorded below; independent transfer work continued |
| FILE-06 | Medium | Offer timeout starts before offer is writable/observable | XFER-01 + XFER-OFFER-API-01 | Blocked | Sender watchdog now starts after wire write; receiver observability requires retained-offer API | PT-T12 | `68c579f` sender portion; pushed | Exact gated-write regression passes; receiver conjunct waits on FILE-05 decision |
| FILE-07 | Medium | Timeout terminal states are nondeterministic | XFER-01 | Verified | Receiver normal timeout precedes a grace-delayed sender safety watchdog; exact REJECT result | PT-T14 | `68c579f`; pushed | End-to-end test asserts only `Rejected("timeout")` |
| FILE-08 | Medium | User I/O runs under global dispatcher mutex | XFER-01 | Verified | Map lock only transfers ownership; source/sink work uses per-transfer gate outside it | PT-T11 | `68c579f`; pushed | Blocking sink/cancel regression and diff review pass |
| FILE-09 | Medium | Terminal handles retain sources/sinks | XFER-01 | Verified | Atomic nullable source plus serialized nullable receiver cleared on all terminal paths | PT-T17 | `68c579f`; pushed | Completed/cancelled/failed matrix plus internal retention assertions pass |
| FILE-10 | Medium | Chunk arithmetic can overflow valid configuration | XFER-01 | Verified | Subtraction-based Long arithmetic and explicit Int chunk-count configuration/send bounds | PT-T06 | `68c579f`; pushed | Overflow rejected before source read; boundary tests pass |
| FILE-11 | Medium API | Transfer failures use misleading errors and lose causes | XFER-ERROR-API-01 | Blocked | Unexpected causes are preserved; correct public transfer error subtypes change sealed exhaustiveness | Typed cause-preservation tests | — | Owner API decision recorded below |
| FILE-12 | Medium | Progress can advance after terminal state | XFER-01 | Verified | State/byte commits share per-transfer mutex; terminal state freezes progress | PT-T15 | `68c579f`; pushed | Gated outgoing and concurrent incoming regressions pass |
| FILE-13 | Low integrity | Byte count checked but content is not | XFER-PROTO-01 after SEC-01 | Planned | — | PT-T18 | — | Protocol decision required before implementation |
| FILE-14 | Low | Transfer ID collision overwrites ownership | XFER-01 | Verified | Bounded unique allocation under lock across both maps; failure closes uncommitted source | PT-T19 | `68c579f`; pushed | Constant-random collision regression passes |
| FILE-15 | Low | Platform file helpers lack snapshot semantics | XFER-01/platform follow-up | Implemented | JVM descriptor-size snapshot; Android descriptor/query consistency, negative rejection, descriptor ownership | PT-T20 | `68c579f`; pushed | JVM tests and Android compile pass; hostile real-provider instrumentation remains external |

### LAN transport (26)

| ID | Severity | Finding | Unit/dependencies | Status | Plan/code | Tests | Commit/push | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LAN-01 | High | Cancellation leaks ghost JmDNS service/listener | LAN-LIFE-01 after LIF-SES-01 | Planned | — | LAN-T02 | — | — |
| LAN-02 | High | Failed restoration committed as successful rebind | LAN-LIFE-01 | Planned | — | Restoration transaction tests | — | — |
| LAN-03 | High | Apple browser/listener failure can pin ghost peers permanently | LAN-LIFE-01 | Planned | — | LAN-T07 | — | — |
| LAN-04 | High availability | Apple inbound connection buffering is unbounded | LAN-LIFE-01 | Planned | — | LAN-T07/LAN-T08 | — | — |
| LAN-05 | Medium | Cancelled JVM/Android outbound connect can orphan a socket | LAN-LIFE-01 | Planned | — | LAN-T04 | — | — |
| LAN-06 | Medium | Cancelled Apple connect leaves NWConnection active | LAN-LIFE-01 | Planned | — | LAN-T04 | — | — |
| LAN-07 | Medium | Fatal JVM/Android accept-loop exit leaves a stale advertised port | LAN-LIFE-01 | Planned | — | LAN-T06 | — | — |
| LAN-08 | Medium | Ordinary write failure leaves raw connection connected | LAN-LIFE-01 | Planned | — | LAN-T05 | — | — |
| LAN-09 | Medium | Raw-read cancellation does not unblock I/O | LAN-LIFE-01 | Planned | — | Cancellation tests all targets | — | — |
| LAN-10 | Medium | Cleanup failure discards ownership | LAN-LIFE-01 | Planned | — | LAN-T03 | — | — |
| LAN-11 | Medium | Apple listener start/close races and retains stale state | LAN-LIFE-01 | Planned | — | LAN-T07/LAN-T10 | — | — |
| LAN-12 | Medium | Apple cache pruning can delete fresh rediscovery | LAN-LIFE-01 | Planned | — | LAN-T07 | — | — |
| LAN-13 | Medium | Network rotation support incomplete on every platform | LAN-NET-01 after LAN-LIFE-01 | Planned | — | LAN-T01/LAN-T07 | — | — |
| LAN-14 | Medium | Synthetic cache heartbeat treats presence as liveness | LAN-NET-01 | Planned | — | TTL/liveness tests | — | — |
| LAN-15 | Medium | Local TXT values unbounded and failures silent | LAN-NET-01 | Planned | — | LAN-T08 | — | — |
| LAN-16 | Medium security | Discovery records trusted too broadly | SEC-01 dependency; LAN-NET-01 | Planned | — | LAN-T08 | — | — |
| LAN-17 | Medium | Apple discovers AWDL endpoints data path may reject | LAN-NET-01 | Planned | — | LAN-T07/device check | — | — |
| LAN-18 | Medium | Only one advertised address is retained | LAN-NET-01 | Planned | — | LAN-T08 | — | — |
| LAN-19 | Low | Library manifests omit normal network permissions | LAN-NET-01 | Planned | — | Manifest-consumer merge tests | — | — |
| LAN-20 | Low | Apple packaging denial has weak diagnostics | LAN-NET-01 | Planned | — | Packaging/preflight tests | — | — |
| LAN-21 | Low | Provenance stamp may become unknown/missing | REL-PROV-01 with BUILD-07 | Planned | — | Declared-output tests | — | — |
| LAN-22 | Low | Diagnostics accept peer control characters | LAN-NET-01 | Planned | — | Sanitization/retention tests | — | — |
| LAN-23 | Low | Terminal close retains listener ports/references | LAN-LIFE-01 | Planned | — | Repeated close/state tests | — | — |
| LAN-24 | Low race | Apple queued writer can run after close | LAN-LIFE-01 | Planned | — | Write-close interleaving test | — | — |
| LAN-25 | Medium | Retry budget carries into genuinely new network | LAN-LIFE-01 | Planned | — | Per-target generation tests | — | — |
| LAN-26 | Low concurrency risk | Rebind scheduling is unsynchronized | LAN-LIFE-01 | Planned | — | LAN-T03 | — | — |

### Android network provisioning (12)

| ID | Severity | Finding | Unit/dependencies | Status | Plan/code | Tests | Commit/push | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PROV-A01 | Medium | Start can return Failed while hotspot remains live | PROV-A-01 after CORE-24/LIF-SES-01 | Planned | — | Transaction/state tests | — | — |
| PROV-A02 | Medium | Start allowed after parent cancellation | PROV-A-01 | Planned | — | Closed-parent tests | — | — |
| PROV-A03 | Medium/High race | Close not serialized with start/join | PROV-A-HIGH-01 | Planned | — | Concurrent lifecycle tests/PS-T01 | — | — |
| PROV-A04 | Medium | Hotspot callback cancellation can lose a reservation handle | PROV-A-01 | Planned | — | PS-T01 | — | — |
| PROV-A05 | Medium | Join callback cancellation can leak process binding | PROV-A-01 | Planned | — | PS-T01/PS-T02 | — | — |
| PROV-A06 | Medium | bindProcessToNetwork result/exception ignored | PROV-A-01 | Planned | — | PS-T01 | — | — |
| PROV-A07 | Medium | Queued onAvailable can rebind after handle close | PROV-A-01 | Planned | — | PS-T01 | — | — |
| PROV-A08 | Medium | Process binding has no global ownership arbitration | PROV-A-01 | Planned | — | PS-T02 | — | — |
| PROV-A09 | Medium | Joined snapshot enumerates unrelated interfaces | PROV-A-01 | Planned | — | LinkProperties tests/device test | — | — |
| PROV-A10 | Medium | Normal-permission failures absent/misdiagnosed | PROV-A-01 | Planned | — | PS-T01 | — | — |
| PROV-A11 | Low | Capability/input validation is shallow | PROV-A-01 | Planned | — | SDK/hardware/input matrix | — | — |
| PROV-A12 | Test gap | Real Android callbacks are untested | PROV-A-01 | Planned | — | PS-T01/PS-T02 | — | Requires Android instrumentation evidence |

### Desktop provisioning (5)

| ID | Severity | Finding | Unit/dependencies | Status | Plan/code | Tests | Commit/push | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PROV-D01 | Medium | pollIntervalMillis is not validated | PROV-D-01 | Planned | — | PS-T03 | — | — |
| PROV-D02 | Medium/Low | Interface scan can report unreachable addresses as Wi-Fi | PROV-D-01 | Planned | — | PS-T03 | — | — |
| PROV-D03 | Low | Broad Throwable catch can hide fatal errors | PROV-D-01 | Planned | — | Cancellation/fatal propagation tests | — | — |
| PROV-D04 | Low | Tests allow null manual result without proving behavior | PROV-D-01 | Planned | — | Strengthened deterministic test | — | — |
| PROV-D05 | Low | Tests mutate process-global properties | PROV-D-01/GOV-01 | Planned | — | Isolation/restoration tests | — | — |

### Sample applications (39)

| ID | Severity | Finding | Unit/dependencies | Status | Plan/code | Tests | Commit/push | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SAMPLE-01 | High data integrity | iOS suppresses sink write failure | SAMPLE-HIGH-01 after XFER-01 | Planned | — | PS-T07 | — | — |
| SAMPLE-02 | High data integrity | iOS same-name destination is non-atomic | SAMPLE-HIGH-01 after XFER-01 | Planned | — | PS-T07 | — | — |
| SAMPLE-03 | High availability/security | Every sample auto-accepts untrusted files | SAMPLE-HIGH-01 after XFER-01 | Planned | — | Consent/quota/free-space tests | — | — |
| SAMPLE-04 | High availability | Android retains binary payloads in UI history | SAMPLE-HIGH-01 after XFER-01 | Planned | — | PS-T04/byte-budget tests | — | — |
| SAMPLE-05 | Medium | Failed/cancelled incoming transfers retain partial files everywhere | SAMPLE-XFER-01 | Planned | — | PS-T07/partial cleanup all samples | — | — |
| SAMPLE-06 | Medium | Desktop UI/Android leak stream during accept cancellation | SAMPLE-XFER-01 | Planned | — | PS-T06 | — | — |
| SAMPLE-07 | Medium | Android/CLI transfer collectors never terminate | SAMPLE-XFER-01 | Planned | — | PS-T04/PS-T05 | — | — |
| SAMPLE-08 | Medium | P2pKit.create failure wedges GUI Start | SAMPLE-LIFE-01 after LIF-SES-01 | Planned | — | PS-T06 | — | — |
| SAMPLE-09 | Medium | Desktop UI can overlap old/new kits | SAMPLE-LIFE-01 | Planned | — | PS-T06 | — | — |
| SAMPLE-10 | Medium | Stop failure swallowed after ownership discarded | SAMPLE-LIFE-01 | Planned | — | PS-T06 | — | — |
| SAMPLE-11 | Medium | CLI exceptions bypass shutdown | SAMPLE-LIFE-01 | Planned | — | PS-T05 | — | — |
| SAMPLE-12 | Medium | iOS stops watchers/sinks before SDK writers quiesce | SAMPLE-XFER-01 | Planned | — | PS-T07 | — | — |
| SAMPLE-13 | Medium | Swift flow adapters spawn unstructured Tasks | SAMPLE-XFER-01 | Planned | — | PS-T07 | — | — |
| SAMPLE-14 | Medium data loss | Android collision cap can return occupied file | SAMPLE-XFER-01 | Planned | — | PS-T04/PS-T08 | — | — |
| SAMPLE-15 | Medium path isolation | Remote peer-name dot segments escape sender directory | SAMPLE-XFER-01 | Planned | — | PS-T08 | — | — |
| SAMPLE-16 | Medium | Android sample omits CHANGE_NETWORK_STATE | SAMPLE-LIFE-01/PROV-A-01 | Planned | — | Manifest/lint tests | — | — |
| SAMPLE-17 | Medium | Android lint fails due missing coarse location | SAMPLE-LIFE-01 | Planned | — | lintDebug/permission tests | — | — |
| SAMPLE-18 | Medium | CLI option parsing can turn options into identity | SAMPLE-LIFE-01 | Planned | — | PS-T05 | — | — |
| SAMPLE-19 | Medium | CLI first-match targeting is ambiguous | SAMPLE-LIFE-01 | Planned | — | PS-T05 | — | — |
| SAMPLE-20 | Medium | Manual IPv6 parsing rejects common local addresses | SAMPLE-LIFE-01/LAN-NET-01 | Planned | — | PS-T08 | — | — |
| SAMPLE-21 | Medium | KMP demo leaks session on send failure | SAMPLE-LIFE-01 | Planned | — | PS-T09 | — | — |
| SAMPLE-22 | Medium | Desktop accept failure leaves empty claimed file | SAMPLE-XFER-01 | Planned | — | PS-T06 | — | — |
| SAMPLE-23 | Medium | iOS transfer history is unbounded | SAMPLE-XFER-01 | Planned | — | PS-T07 | — | — |
| SAMPLE-24 | Medium | GUI text histories are count-, not byte-bounded | SAMPLE-XFER-01 | Planned | — | PS-T06/PS-T07 | — | — |
| SAMPLE-25 | Low | Rapid advertise/discover toggles race stale UI booleans | SAMPLE-LIFE-01 | Planned | — | Intent serialization tests | — | — |
| SAMPLE-26 | Low | Android labels connecting/reconnecting as connected | SAMPLE-LIFE-01 | Planned | — | UI state mapping test | — | — |
| SAMPLE-27 | Low | Permission diagnostic failure becomes “nothing missing” | SAMPLE-LIFE-01 | Planned | — | Diagnostic failure test | — | — |
| SAMPLE-28 | Low security UX | Android displays credentials in clear text | SAMPLE-LIFE-01 | Planned | — | UI semantics/screenshot policy check | — | — |
| SAMPLE-29 | Low security | Desktop logs do not consistently sanitize terminal controls | SAMPLE-LIFE-01 | Planned | — | Control-character tests | — | — |
| SAMPLE-30 | Low | iOS PeerRow equality suppresses updates | SAMPLE-LIFE-01 | Planned | — | Equality/update test | — | — |
| SAMPLE-31 | Low | iOS cross-check diagnostics flood normal state | SAMPLE-LIFE-01 | Planned | — | Log-rate/state test | — | — |
| SAMPLE-32 | Low | Unknown transfer state is permanently nonterminal | SAMPLE-LIFE-01 | Planned | — | Future-enum bounded failure test | — | — |
| SAMPLE-33 | Low | Desktop cleanup uses disposing scope | SAMPLE-LIFE-01 | Planned | — | Window disposal cleanup test | — | — |
| SAMPLE-34 | Low | Unique-file helpers are duplicated/divergently unsafe | SAMPLE-XFER-01 | Planned | — | PS-T04/PS-T06/PS-T08 | — | — |
| SAMPLE-35 | Low | Alice/Bob run configs share PeerId | ID-01 | Planned | — | Two-profile launch config test | — | — |
| SAMPLE-36 | Medium | Android reports Running after partial startup | SAMPLE-LIFE-01 after LIF-SES-01 | Planned | — | Partial feature start test | — | — |
| SAMPLE-37 | Low | CLI reports close success after failure | SAMPLE-LIFE-01 | Planned | — | PS-T05 | — | — |
| SAMPLE-38 | Low | CLI stops kit before cancelling app jobs | SAMPLE-LIFE-01 | Planned | — | PS-T05 | — | — |
| SAMPLE-39 | Low | Android onCleared cleanup has no durable owner | SAMPLE-LIFE-01 | Planned | — | PS-T04 | — | — |

### Build, publication, tooling, and configuration (15)

| ID | Severity | Finding | Unit/dependencies | Status | Plan/code | Tests | Commit/push | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BUILD-01 | High | Published compile dependency metadata is wrong | REL-ABI-01 | Verified | Correct API scopes; desktop LAN test-only | CORE-T13 isolated published consumers pass | `8f15d75`; pushed with tracker evidence | POM/module/API variant and all platform consumers pass from committed state |
| BUILD-02 | High release blocker | No remote publication target exists | REL-REMOTE-01 | Blocked | Analysis complete; Portal workflow/namespace decision required | Local artifact shape passes; bundle/upload path awaits decision | Pending tracker-only blocker commit | Blocked on namespace type, workflow choice, and credentials; ENV-07 retains live upload proof |
| BUILD-03 | Medium | BuildInfo defeats incremental/reproducible builds | REL-PROV-01 | Planned | — | Double-build/reproducibility tests | — | — |
| BUILD-04 | Medium | Publication gate can pass invalid release | REL-SUPPLY-01 after BUILD-01/BUILD-02 | Planned | — | Invalid-scope/signature/archive fixtures | — | — |
| BUILD-05 | Medium | Gradle wrapper components are version-skewed | REL-SUPPLY-01 | Planned | — | Wrapper validation/checksums | — | — |
| BUILD-06 | Medium | Supply-chain/release automation controls absent | REL-SUPPLY-01 | Planned | — | CI/verification/lock/SBOM policy gates | — | External scanners/signing may be required |
| BUILD-07 | Medium | XCFramework stamp is undeclared/mis-targeted side effect | REL-PROV-01 with LAN-21 | Planned | — | Declared output/incremental tests | — | — |
| BUILD-08 | Medium | Android sample manifest fails project check | REL-GATE-01 after SAMPLE-LIFE-01 | Planned | — | lintDebug | — | — |
| BUILD-09 | Low | iOS launcher uses predictable/shared paths and name-first selection | REL-PROV-01 | Planned | — | Script syntax/concurrency/device selection tests | — | — |
| BUILD-10 | Low | Nested Gradle/Xcode preflight duplicates framework work | REL-PROV-01 | Planned | — | Invocation-count/incremental test | — | — |
| BUILD-11 | Low | Dirty-tree provenance ignores untracked inputs | REL-PROV-01 | Planned | — | Provenance fixture tests | — | — |
| BUILD-12 | Low | Provenance exposes local/volatile build information | REL-PROV-01 with BUILD-03 | Planned | — | Artifact content/reproducibility tests | — | — |
| BUILD-13 | Low | Release usability/maintenance gaps | REL-SUPPLY-01 | Planned | — | Javadoc/POM/tag/run-config gates | — | — |
| BUILD-14 | Low | Compiler/test hygiene warnings are not gated | REL-GATE-01 | Planned | — | Warnings-as-errors/static gates | — | — |
| BUILD-15 | Low | Android lint reports three additional warnings | REL-GATE-01 after SAMPLE-LIFE-01 | Planned | — | lintDebug warning-free | — | — |

## Explicit test-gap register (54)

Each row represents one bullet from “Missing or weak tests to add” in the source review. A gap may close with the same focused commit as its linked finding, but receives its own result/evidence.

### Core lifecycle/session/identity gaps (13)

| Gap ID | Required coverage | Linked findings | Status | Test files/evidence | Commit/push | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| CORE-T01 | Stop racing connect, advertising, discovery, and delayed observer start | CORE-01 | Verified | Six deterministic races in `KitLifecycleTest`; existing parked data-start test retained | `a4e0bb0`; tracker evidence pending push | Focused committed suite passes; three forced pre-commit repeats green |
| CORE-T02 | Cancellation at every outgoing-connect suspension, then successful retry | CORE-03 | Verified | `SessionOwnershipTest`, `SessionFlowTest`, secure integration: dial, coalesced wait, HELLO/security write, pre-commit | `68934be`; test follow-up `82a9b41`; pushed | Three exact committed-state JVM repeats plus focused iOS and Android compile pass |
| CORE-T03 | Two discovery transports contribute/lose same PeerId | CORE-02 | Implemented | Per-instance merge/loss plus mutable-input snapshot regressions | PEER-CTRL commit pending | JVM/iOS pass |
| CORE-T04 | Repeated same-direction inbound arbitration | CORE-05 | Implemented | Five repeated inbound candidates under both local-ID orderings | PEER-CTRL commit pending | JVM/iOS pass |
| CORE-T05 | Slow message subscriber while PONG/CLOSE arrives | CORE-04 | Implemented | Gated subscriber plus PONG/CLOSE and byte-overflow regressions | PEER-CTRL commit pending | JVM/iOS pass |
| CORE-T06 | Exact keepalive deadline and monotonic clock jumps | CORE-14 | Implemented | Exact 150 ms virtual boundary with extreme wall-clock jumps | PEER-CTRL commit pending | JVM/iOS pass |
| CORE-T07 | Session child Job completes after remote termination | CORE-09 | Verified | `SessionFlowTest` exact CLOSE/failure runtime joins | `68934be`; pushed | JVM/iOS pass |
| CORE-T08 | Public sessions empty after stop independent of watcher schedule | CORE-10 | Verified | `KitLifecycleTest.sessionCommittedBeforeStopIsIncludedInTeardown` | `68934be`; test follow-up `82a9b41`; pushed | JVM/iOS pass |
| CORE-T09 | Partial multi-transport startup rollback | CORE-11 | Planned | — | — | — |
| CORE-T10 | Throwing and permanently hung close operations | CORE-12 | Planned | — | — | — |
| CORE-T11 | Identity sanitizer collisions, concurrent first creation, persistence failure, and atomic replacement | CORE-18, CORE-19, CORE-20, CORE-21 | Verified | JVM process/thread/failure/migration tests + iOS bucket tests | `ee69d09`, pushed | Focused tests pass; committed full JVM 351/351 green |
| CORE-T12 | Path observer close/restart, stale callbacks, unregister failure, generation gating | CORE-22, CORE-23 | Planned | — | — | — |
| CORE-T13 | Clean external consumer compilation from published temp repository | BUILD-01 | Verified | `scripts/check-published-consumers.sh` | `8f15d75`; pushed with tracker evidence | JVM/Android/KMP/iOS pass from committed state |

### Protocol and transfer gaps (21)

| Gap ID | Required coverage | Linked findings | Status | Test files/evidence | Commit/push | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| PT-T01 | FrameReader fragmented/batched complexity and early bad-magic rejection | PROTO-01 | Verified | Linear relocation and early-header regression suite | `aa3ac0c` | Three forced JVM repeats plus exact committed JVM/iOS pass |
| PT-T02 | Header-version mismatch and every packet-type structural invariant | PROTO-02, PROTO-04 | Verified | Table-driven known-packet invariant matrix and early version/shape rejection | `aa3ac0c` | Exact committed JVM/iOS pass |
| PT-T03 | Large HELLO/OFFER/control payload attacks and log flooding | PROTO-03, PROTO-07 | Verified | Header-only cap attacks and bounded-log assertions | `aa3ac0c` | Exact boundaries and 100-frame flood pass |
| PT-T04 | Strict malformed UTF-8 and invalid flags/LAST | PROTO-04, PROTO-06 | Verified | Strict text decoders plus DATA/FILE_DATA flag and LAST invariants | `aa3ac0c` | JVM/iOS pass |
| PT-T05 | Outbound name/MIME/reason limits | PROTO-03, PROTO-06 | Verified | Encoder/send-path character and UTF-8 byte boundaries | `aa3ac0c`, `6171588` | Exact committed JVM/iOS pass |
| PT-T06 | 2 GiB with chunk size 1 and Long overflow boundaries | FILE-10 | Verified | Configuration and sender pre-read overflow tests | `68c579f`; pushed | JVM/iOS pass |
| PT-T07 | Empty FILE_DATA, changing totalChunks, invalid LAST, data after full size | PROTO-04, FILE-02 | Verified | Parser invariants plus dispatcher terminal/transition tests | `aa3ac0c`, `68c579f`; pushed | JVM/iOS pass |
| PT-T08 | Accepted-transfer idle exhaustion and all 64 admission slots exhausted | FILE-02 | Verified | Exact idle reset/overall bound and 64 accepted-slot release | `68c579f`; pushed | Virtual-time JVM/iOS pass |
| PT-T09 | Cancellation during accept mutex wait and FILE_ACCEPT write | FILE-01 | Verified | Gated accept cancellation with compensating cancel/reference assertion | `68c579f`; pushed | JVM/iOS pass |
| PT-T10 | Cancel/close racing sink write/finish | FILE-03 | Verified | Gated sink write proves per-transfer serialization | `68c579f`; pushed | JVM/iOS pass |
| PT-T11 | Blocking/reentrant source close and sink flush | FILE-08 | Verified | Ownership/I/O moved outside map lock; gated sink regression | `68c579f`; pushed | Diff review + JVM/iOS pass |
| PT-T12 | Timer scheduling before map registration, wire write, and offer emission | FILE-06 | Blocked | Sender gated-write origin proven; receiver emission/retention conjunct needs XFER-OFFER-API-01 | `68c579f` sender portion; pushed | Exact virtual-time sender test passes |
| PT-T13 | Ordered multiple offers and no emission after terminal | FILE-05 | Blocked | Requires XFER-OFFER-API-01 retained pending-state contract | — | Owner decision recorded |
| PT-T14 | One exact timeout authority/state on both peers | FILE-02, FILE-07 | Verified | Receiver authority + delayed sender watchdog; exact end-to-end REJECT | `68c579f`; pushed | JVM/iOS pass |
| PT-T15 | Byte progress frozen after terminal | FILE-12 | Verified | Gated outgoing and serialized incoming byte commits | `68c579f`; pushed | JVM/iOS pass |
| PT-T16 | Sender result when receiver flush/durability fails | FILE-04 | Planned | — | — | — |
| PT-T17 | Source/sink references released after every terminal outcome | FILE-09 | Verified | Close-once matrix plus nullable source/receiver retention assertions | `68c579f`; pushed | JVM/iOS pass |
| PT-T18 | Source mutation/digest mismatch | FILE-13 | Planned | — | — | — |
| PT-T19 | Deterministic transfer-ID collision | FILE-14 | Verified | Constant-random collision cannot overwrite and closes second source | `68c579f`; pushed | JVM/iOS pass |
| PT-T20 | Android hostile/null/negative provider metadata | FILE-15 | In Progress | Production validation implemented; real provider/instrumentation proof unavailable locally | `68c579f`; pushed | Android compile passes; external Android test remains |
| PT-T21 | Fuzz/property tests for codec, reader, reassembler, and transfer transitions | PROTO-01, PROTO-04, FILE-01, FILE-02, FILE-03, FILE-05, FILE-07, FILE-12 | In Progress | Deterministic randomized codec/reader/reassembler complete; exact transfer transition regressions complete, but retained-offer/API-dependent randomized transitions remain | `aa3ac0c`, `68c579f` partial | Parser properties and transfer concurrency tests passed three forced JVM repeats and iOS; API-dependent portion open |

### LAN gaps (11)

| Gap ID | Required coverage | Linked findings | Status | Test files/evidence | Commit/push | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| LAN-T01 | Android instrumentation for multicast locks, callback ordering, network rotation, permissions, unregister failure, process binding, and IPv6 | LAN-10, LAN-13, LAN-19 | Planned | — | — | Physical/emulated Android required |
| LAN-T02 | Partial-completion cancellation for service/listener registration | LAN-01 | Planned | — | — | — |
| LAN-T03 | Unregister/remove/close failures and concurrent rebind scheduling | LAN-10, LAN-26 | Planned | — | — | — |
| LAN-T04 | Outbound-connect cancellation on JVM, Android, Apple | LAN-05, LAN-06 | Planned | — | — | — |
| LAN-T05 | Normal write IOException reaches terminal state | LAN-08 | Planned | — | — | — |
| LAN-T06 | Restart/re-advertise after fatal accept failure | LAN-07 | Planned | — | — | — |
| LAN-T07 | Apple browser/listener recovery, start-close race, parent cancellation, inbound flood/drain, cache-prune race, same-type path rotation, and AWDL | LAN-03, LAN-04, LAN-11, LAN-12, LAN-13, LAN-17 | Planned | — | — | Simulator plus physical Apple evidence required where applicable |
| LAN-T08 | Oversized TXT, unsupported pv, control characters, duplicate-PID spoof, off-subnet hosts, alternate address candidates, and connection flood | LAN-04, LAN-15, LAN-16, LAN-18, LAN-22 | Planned | — | — | Hostile-network/device evidence partly required |
| LAN-T09 | Replace global replay-count assertions with per-test baselines | LAN test fixtures | Planned | — | — | — |
| LAN-T10 | Prove old Apple listener descriptors released, not merely new port differs | LAN-11, LAN-23 | Planned | — | — | Apple platform evidence required |
| LAN-T11 | Isolate tests that mutate user.home, JmDNS properties, and NSUserDefaults | CORE-18, CORE-19, CORE-20, CORE-21, CORE-30, PROV-D05, LAN tests | Planned | — | — | — |

### Provisioning and sample gaps (9)

| Gap ID | Required coverage | Linked findings | Status | Test files/evidence | Commit/push | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| PS-T01 | Real Android provisioning callback/cancellation and permission behavior | PROV-A01, PROV-A02, PROV-A03, PROV-A04, PROV-A05, PROV-A06, PROV-A07, PROV-A09, PROV-A10, PROV-A12 | Planned | — | — | Android instrumentation required |
| PS-T02 | Process-wide binding ownership across managers | PROV-A05, PROV-A08, PROV-A12 | Planned | — | — | Android instrumentation required |
| PS-T03 | Desktop poll boundaries and interface ranking | PROV-D01, PROV-D02 | Planned | — | — | — |
| PS-T04 | Android sample unit/instrumentation tests | SAMPLE-03, SAMPLE-04, SAMPLE-05, SAMPLE-06, SAMPLE-07, SAMPLE-08, SAMPLE-10, SAMPLE-14, SAMPLE-15, SAMPLE-16, SAMPLE-17, SAMPLE-25, SAMPLE-26, SAMPLE-27, SAMPLE-28, SAMPLE-34, SAMPLE-36, SAMPLE-39, BUILD-08, BUILD-15 | Planned | — | — | Android instrumentation required |
| PS-T05 | CLI option parsing, target ambiguity, shutdown finally, and terminal collector cleanup | SAMPLE-07, SAMPLE-11, SAMPLE-18, SAMPLE-19, SAMPLE-37, SAMPLE-38 | Planned | — | — | — |
| PS-T06 | Desktop GUI create/stop races, accept cancellation, and byte-budgeted history | SAMPLE-06, SAMPLE-08, SAMPLE-09, SAMPLE-10, SAMPLE-22, SAMPLE-24, SAMPLE-33, SAMPLE-34 | Planned | — | — | — |
| PS-T07 | Swift sink failure, atomic filename collision, partial-file cleanup, and unstructured collector cancellation | SAMPLE-01, SAMPLE-02, SAMPLE-05, SAMPLE-12, SAMPLE-13, SAMPLE-23, SAMPLE-24 | Planned | — | — | Apple test target/device where applicable |
| PS-T08 | Dot-segment names and scoped IPv6 on every sample | SAMPLE-15, SAMPLE-20, SAMPLE-34 | Planned | — | — | — |
| PS-T09 | KMP Android runtime consumer and iOS consumer target | SAMPLE-21, BUILD-01 | Planned | BUILD-01 publication-consumer conjunct implemented; SAMPLE-21 runtime/device conjunct remains | KMP Android/iOS compile consumer passes | — | Physical/runtime portion remains |

## External-validation register

These seven boundaries were explicitly excluded from the original local review. They are additional final acceptance evidence, not part of the 54 test-gap count and not grounds for silently closing a finding.

| ID | Required evidence | Status | Unblock/evidence |
| --- | --- | --- | --- |
| ENV-01 | Physical Android and Apple device tests | Blocked | Compatible devices and test deployment path required |
| ENV-02 | Two-machine and hostile-network hardware validation | Blocked | At least two hosts/devices plus controlled hostile-network harness required |
| ENV-03 | Simulator app launch and UI automation | Planned | Add/run platform UI targets after sample fixes |
| ENV-04 | iOS X64 execution on compatible host | Blocked | x86_64 Apple host/runtime required |
| ENV-05 | Force-enable and resolve ignored Apple diagnostic test | Planned | Run when LAN lifecycle foundation is fixed |
| ENV-06 | Third-party dependency CVE/advisory scan | Planned | Select/configure and run a current advisory scanner; record a concrete blocker only if one is encountered |
| ENV-07 | Real remote Central/Portal upload | Blocked | Approved portal, signing identity, namespace access, and CI credentials required |

## Execution record: SEC-01

### Scope and status

| Field | Value |
| --- | --- |
| Primary findings | CORE-06 (High security limitation), CORE-07 (Medium architecture) |
| Status | Implemented; local SEC acceptance tests pass, external/repository-wide certification gates remain |
| Confirmed on | `6a05ccd04fcb6fb8106ed47941618fb6bcfd3fa6` |
| Source changes | Complete for SEC-01: provider dependencies, canonical identity/storage records, platform storage, Noise v2 engine, strict frame versioning, transport security profile, segregated LAN discovery, manual pinning, and sample migration |
| Approval | Owner approved SEC-01 and storage A on 2026-07-17; provider selection remains an implementation review, not an owner-policy blocker |
| Tightly coupled findings | CORE-13, CORE-18, CORE-19, CORE-20, CORE-21, PROTO-02, authentication portion of LAN-16; each keeps its own row/acceptance/commit evidence |
| Related but independently closable | PROTO-03, PROTO-04, PROTO-06, LAN-15, remaining LAN-16 concerns, FILE-13 |

### Reproduction evidence and root cause

The findings are confirmed in the current branch:

- `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/Config.kt:79` exposes only `SecurityMode.NoneForMvp`.
- `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/dsl/Builders.kt:51` defaults to it, but `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt:68` marks the value unused and line 118 always installs `NoOpSecurityManager`.
- `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/security/SecurityManager.kt:33` merely delegates the raw stream and constructs `PeerIdentity` from an unverified `Peer`. `SecureConnection.peerIdentity` is not consumed elsewhere.
- `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionManager.kt:406` launches `protocol.events(rawConnection)` first. It parses plaintext HELLO, trusts/resolves the peer, and only then calls `security.performHandshake` at line 485.
- `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transport/RawConnection.kt:18` explicitly allows exactly one byte-flow collector. A real security layer cannot take over that stream after the parser has started, while an encrypted wrapper would be bypassed by the existing reader.
- `SessionManager.kt:451` compares only attacker-controlled HELLO strings for outgoing sessions; line 466 explicitly accepts any non-local claimed PeerId inbound. PeerIds are visible through discovery, and manual peers intentionally bypass the expected-ID comparison.
- JVM/Android LAN use ordinary sockets and Apple constructs non-TLS Network.framework parameters. This is acceptable only as a byte-stream substrate if core encrypts above it; today core does not.
- Existing `HandshakeIdentityTest`, `ManualPeerIdentityTest`, and `HandshakeTest` prove claimed-string/plaintext behavior only. There is no key-possession, confidentiality, integrity, replay, downgrade, tamper, or sole-reader security test.

The root cause is ordering and identity ownership, not just the absence of a cipher. The public security contract requires a `Peer` before authentication, while a trustworthy inbound `Peer` cannot exist until authentication. The protocol parser already owns the one raw reader before the extension point runs. Consequently the current extension API cannot be implemented securely.

### Security impact

Current LAN participants can passively read the TCP/data connection, including HELLO identity metadata, messages, file bytes, and control frames. AppId, PeerId, device name, endpoint, and traffic timing/length are also exposed separately by current mDNS discovery; encrypting the data connection does not make discovery private. An active participant knowing the public app ID can claim another visible PeerId, occupy or churn its session slot, or impersonate a manual endpoint. There is no cryptographic confidentiality, integrity, replay protection, authenticated identity, forward secrecy, authorization, or downgrade protection.

### Proposed long-term architecture

Subject to the decisions below, the recommended architecture is transport-independent authenticated encryption in `p2p-core`; LAN TCP remains a plain byte-stream carrier:

1. Open or accept a `RawConnection` and assign an explicit initiator/responder role.
2. Start one bounded setup deadline before the first security byte is written.
3. A v2 security engine becomes the sole owner/collector of `RawConnection.read()` for the connection lifetime.
4. Run a vetted authenticated key exchange with one canonical shared context—protocol name/version, AppId, and an identical direction tuple—bound into its transcript/prologue. Initiator/responder behavior comes from the handshake state machine; the two sides must not hash different local-role strings.
5. Return a bounded, backpressured secure record stream plus authenticated remote public-key identity.
6. Only then start `DefaultP2pProtocol.events()` on decrypted bytes and exchange HELLO inside encryption.
7. Derive/bind `PeerId` through a versioned, domain-separated hash of one canonical raw public-key encoding; validate HELLO metadata against that identity.
8. Apply the approved authorization policy and publish/register the session only after all security, HELLO, expected-peer, lifecycle-generation, and capacity checks commit.
9. On reconnect, require the same authenticated key before rearming the existing public session.

The preferred wire design is a vetted implementation of a Noise-style authenticated handshake, provisionally `Noise_XX_25519_ChaChaPoly_SHA256` for unknown/manual peers, with a pinned expected-key path only when prior trust/pairing supplies one. Unauthenticated discovery may nominate an expected fingerprint hint that the authenticated key must match, but it never creates a pin or authorization. Cryptographic primitives must not be implemented in this repository. Exact provider suitability requires a focused dependency review covering implementation provenance, independent review/audit status, KMP interoperability and platform parity, maintenance and release/CVE response, license, entropy/CSPRNG integration, constant-time/side-channel posture, known-answer vectors, publication impact, and proof that released artifacts contain the reviewed implementation.

There must be a distinct secure preface/protocol major, strict handshake and record size bounds, monotonic nonces, authenticated record framing, counter exhaustion handling, and no automatic plaintext fallback. General application-frame limits and validation remain separate PROTO findings.

If legacy mode remains, it is a whole-kit explicit configuration with segregated discovery capability/advertisement and listener behavior. A secure kit never selects plaintext from attacker-controlled TXT data, and a secure listener closes a legacy preface with uniform bounded behavior rather than detailed plaintext diagnostics.

Standards basis: the [official Noise Protocol Framework](https://noiseprotocol.org/noise.pdf) limits Noise messages, treats remote static-key acceptability as an application decision beyond proof of possession, and warns that negotiation not bound into the prologue can enable rollback. Those constraints are why authorization remains a separate explicit policy and why protocol/security selection must be transcript-bound rather than opportunistically negotiated.

### Expected implementation surface

The exact file list will be finalized after the decisions, but the current architectural surface is:

- Core public/API: `Config.kt`, `Identity.kt`, `Errors.kt`, `P2pKit.kt`, `P2pSession.kt`, `dsl/Builders.kt`, and the security package.
- Core orchestration: `internal/P2pKitImpl.kt`, `internal/SessionManager.kt`, `internal/Handshake.kt`, local identity/key storage, and reconnect/session commit paths.
- Wire: `protocol/ProtocolConstants.kt`, `HelloPayload.kt`, version enforcement in `FrameCodec.kt`/`FrameReader.kt`, plus new bounded secure-handshake/record code.
- Transport contract: `transport/RawConnection.kt` ownership documentation; the external transport SPI should remain a byte stream unless provider review proves a necessary break.
- LAN discovery: common TXT schema and JVM/Android/Apple encode/decode validation if security capability/fingerprint hints are advertised. Discovery hints never establish identity by themselves.
- Manual provisioning: `provisioning/ManualPeerRegistrar.kt`, `NetworkProvisioningTypes.kt`, `NetworkProvisioningFactory.kt`, unsupported/platform managers, Android/desktop sidecars, and all manual-peer tests. A fingerprint, trust token, or pending authenticated identity necessarily changes these contracts.
- Build/publication: `gradle/libs.versions.toml`, `p2p-core/build.gradle.kts`, POM/module metadata, ABI baselines, and external-consumer checks.
- Consumers: samples and KMP/Swift bridges where secure defaults, authorization callbacks, pairing, or migration must be configured.

### Lifecycle, concurrency, cleanup, and performance contract

- One deadline covers security exchange, secure-stream creation, encrypted HELLO write/read, identity/metadata validation, and session commit. It includes previously unbounded first writes and security implementations (CORE-13).
- `CancellationException` propagates unchanged. Cancellation, authentication failure, protocol failure, or timeout cancels security reader/record jobs, closes secure/raw ownership exactly once, performs bounded `NonCancellable` cleanup, releases the inbound permit, and publishes no session.
- Authentication failure never falls back to plaintext or reconnects under another identity.
- One owner reads the raw connection. Bounded ciphertext and plaintext queues apply backpressure; no unbounded handshake/record buffer or task is allowed.
- Secure record writes and nonce allocation are serialized inside the secure stream regardless of which session/control/file producer calls it. Authentication failure atomically terminalizes both directions, discards queued plaintext, and prevents every later record from being processed or reusing a nonce.
- No socket/session/key ownership is committed after terminal kit generation. Simultaneous-open and reconnect roles must be deterministic.
- Long-term key creation is atomic across concurrent instances where the platform permits; persistence corruption/failure fails closed according to the approved contract and never silently rotates identity mid-instance.
- CSPRNG failure is fatal. Private/session keys are never logged or exposed through public models, and temporary key material is cleared where Kotlin/platform runtime semantics permit.
- If interactive authorization is selected, it is not allowed to consume the security-setup deadline or one of the 16 pre-handshake permits indefinitely. It needs a separately bounded/capped pending-authorization state, cancellation-safe callback contract, timeout, denial result, and terminal cleanup.

### API, binary, wire, migration, and cross-platform implications

- The current public `SecurityManager.performHandshake(connection, peer)` contract is unusable and must be deprecated/replaced or break in the next major API. It needs role, expected authenticated identity, local identity, deadline/cancellation ownership, and authorization outcome before `Peer` creation.
- Making secure mode the default changes runtime behavior. Removing `NoneForMvp` is an immediate source/runtime break; retaining it as deprecated explicit opt-in preserves a migration escape hatch but must never be negotiated automatically.
- A secure preface and major protocol version intentionally break wire compatibility with plaintext v1 in secure mode.
- A key-derived PeerId changes existing persisted UUID identities once. Preserving an old UUID cannot retroactively authenticate it without an independently trusted binding; a migration must not claim otherwise.
- Key storage design must distinguish exportable software X25519 key bytes wrapped/stored by Keychain/Keystore, non-exportable keys operated through platform APIs, and hardware-backed keys. A common Noise provider may require raw private bytes, so provider and storage choices are one decision rather than independent promises.
- Key lifecycle must define per-AppId versus device-global identity, backup/restore and uninstall behavior, rotation, compromise/revocation, corruption/lost-key recovery, and orphaned backup state. Android restored data can outlive a Keystore key; iOS Keychain lifetime differs from `NSUserDefaults`.
- `P2pKit.create` currently loads identity synchronously, exposes `localPeerId` immediately, and constructs transports with it. Secure key loading/generation must either preserve that blocking construction contract explicitly or introduce a documented public construction/start/identity migration.
- Android Keystore, iOS Keychain, and the approved JVM key-protection policy affect persistence behavior and tests. All platforms must emit the identical secure wire protocol and pass common known-answer/interoperability vectors.
- If pinning or TOFU exists, its authorization store needs an AppId namespace, atomic/concurrent decisions, denial persistence policy, revocation/reset, key-change handling, and deterministic behavior when callbacks are absent, throw, or are cancelled.
- A crypto dependency may enter public metadata depending on the final API shape; BUILD-01 external-consumer checks must catch the resulting scope.

### Coupled-finding ownership and commit boundaries

SEC-01 is an architectural program, not permission for one large commit. After approval it is split into focused prerequisite/implementation commits:

| Sub-unit | Finding ownership | Required order |
| --- | --- | --- |
| SEC-ID-01 | CORE-18, CORE-19, CORE-20, CORE-21: collision-safe atomic cryptographic identity storage and migration | Before secure sessions consume long-term keys |
| SEC-WIRE-01 | PROTO-02: explicit secure major/preface and frame-version validation | Before secure v2 interoperability is claimed |
| SEC-SETUP-01 | CORE-13: one bounded setup transaction including security and encrypted HELLO | With/before SessionManager secure-stream commit |
| SEC-CORE-01 | CORE-06/CORE-07: secure-stream architecture, authenticated identity, authorization, no downgrade | After the preceding contracts are defined |
| SEC-LAN-AUTH-01 | Authentication portion of LAN-16: discovery is only an untrusted routing/hint source | Verified with secure core; remaining LAN-16 address/ownership/log concerns stay in LAN-NET-01 |

Each row is committed, tested, and marked independently. SEC-01 cannot be Verified until these coupled rows are individually Verified, but their separate units are not double-owned or silently closed by the CORE-06/CORE-07 commit.

### Required tests

Security and wire tests:

- Secure message and file round trips across supported targets.
- Captured raw data-connection bytes contain none of AppId, identifiers, names, message text, or file bytes; repeated equal plaintext produces different ciphertext. A separate test/documented threat limit confirms current mDNS discovery metadata remains observable.
- PeerId is bound to key possession; inbound/outgoing victim-ID claims fail.
- An attacker may copy a victim's mDNS PeerId/endpoint/fingerprint hint but cannot complete a session without the victim private key; advertising a new attacker-owned identity follows the selected authorization policy.
- Tampered authentication tag, replay, reorder, truncation, oversized security message/record, wrong app, wrong key, wrong role, and wrong protocol version each produce one precise local typed outcome and close. Pre-authentication peer-visible behavior stays uniform—a bounded close without detailed plaintext diagnostics—so failures do not become an oracle.
- Secure mode rejects plaintext v1 without downgrade; explicit legacy mode, if retained, works only when both endpoints explicitly select it.
- A fake that fails on a second `RawConnection.read()` proves security plus session traffic uses one raw collector.
- Reconnect accepts the same key and rejects an attacker at a refreshed endpoint; simultaneous-open role resolution is deterministic.
- Manual connections follow the approved high-entropy pin/QR, PAKE, approval, TOFU, or accept-any policy exactly; no test treats a low-entropy code as a raw PSK.
- Canonical public-key encoding, domain-separated PeerId derivation, handshake transcript, record encryption, and cross-platform key parsing have fixed interoperability vectors.
- Authorization tests cover absent/throwing/cancelled callbacks, concurrent decisions, timeout, denial, revocation, key change, reset, and capacity exhaustion if an interactive/persistent trust mode is approved.

Lifecycle tests:

- Cancellation at every security read/write/key-exchange/HELLO/commit suspension leaves no job, socket, permit, pending connect, or session.
- Stalled initial write/security implementation is bounded by the single setup deadline.
- Pre-handshake capacity returns after every failure and repeated failed-then-successful connects remain leak-free.

Identity storage and platform tests:

- Stable fingerprint across restart; collision-prone AppIds remain distinct.
- Concurrent first creation produces one key/identity, persistence failure follows one explicit contract, writes are atomic, corrupted keys fail closed, and migration is deterministic.
- Backup without the corresponding platform key, uninstall/reinstall, rotation, compromise/revocation, lost/corrupt key, and orphaned authorization data follow the approved lifecycle on each platform.
- Common known-answer/interop vectors run on JVM, Android, and Apple; secure LAN loopback runs on JVM/Apple simulator and physical Android/Apple before final verification.
- Samples/KMP/Swift compile with the approved trust configuration; temp-published external consumers compile; ABI/API changes are reviewed.

### Acceptance criteria

SEC-01 cannot be marked Verified until all of the following are true:

- No application protocol parser reads raw bytes before authenticated security succeeds.
- Every non-explicit-legacy session is encrypted and integrity protected with no downgrade path.
- Session identity is derived from and verified against authenticated key material.
- Unknown/manual peer admission follows the approved authorization policy.
- Entire setup and cleanup are bounded, cancellation-correct, and leak-free.
- Identity/key persistence is collision-safe, stable, atomic, and fails closed.
- JVM, Android, and Apple implementations interoperate on one versioned wire format.
- All targeted, module, cross-platform, consumer, repeated concurrency, full-repository, physical-device, and hostile-network gates pass.
- Public API/wire compatibility and one-time identity migration are recorded for consumers.
- Documented threat limits are accurate: this design does not hide mDNS metadata or traffic timing/length, prevent endpoint-advertisement DoS, authorize an unknown key by itself, or protect a compromised local private key.

### Approved owner decisions

The owner approved this package on 2026-07-17:

1. Authenticated encryption is mandatory by default; retain `NoneForMvp` only as deprecated whole-kit migration opt-in with segregated advertisement/listener behavior and never an automatic fallback.
2. Introduce secure protocol major v2 with a distinct preface; reject plaintext v1 uniformly in secure mode.
3. Use versioned, domain-separated, key-derived self-certifying PeerIds and accept a documented one-time identity change from legacy UUIDs.
4. Reject unknown identities by default. For the first secure release, support high-entropy fingerprint/QR pinning and a separately explicit “accept any authenticated same-AppId identity” policy. Do not market AppId as authorization. Defer short human-entered pairing codes until a named PAKE is chosen; never use a low-entropy code directly as a Noise PSK.
5. Decide whether interactive approval is required. Recommended initial scope is preconfigured pin/QR or explicit accept-any, avoiding a human callback inside connection setup. If interactive approval is required now, approve a separate bounded/capped pending-authorization state and UI-safe callback contract.
6. Manual IP requires a high-entropy pinned fingerprint/QR or the approved pending-identity flow; synthetic IDs are not authenticated identities.
7. Replace/deprecate the current `SecurityManager` API with a role-aware v2 contract and built-in audited secure engines. Do not extend P2pKit's security guarantee to arbitrary custom crypto providers; any future custom-engine SPI must be explicitly experimental/unsafe and separately threat-modeled.
8. Approve a focused vetted KMP provider review against the expanded criteria above; no repository-local cryptographic primitives.
9. Decide storage capability with the provider: exportable wrapped software keys versus non-exportable platform-operated keys and whether hardware backing is mandatory. Also approve the JVM at-rest protection policy. Persistence/CSPRNG failure fails closed.
10. Use a per-AppId long-term identity by default and explicitly approve backup/restore, uninstall, rotation, revocation, corruption/lost-key recovery, and authorization-store lifecycle behavior.
11. Preserve synchronous `P2pKit.create` and immediate `localPeerId` for the smallest API change, with the existing off-main-thread requirement, or approve a breaking suspending/lazy construction and nullable/stateful identity contract. The recommendation for this remediation is to preserve the current construction shape unless provider constraints make that unsafe.
12. Approve the focused sub-unit ownership table above so CORE-13, CORE-18, CORE-19, CORE-20, CORE-21, PROTO-02, and LAN-16 receive their own commits/evidence while remaining prerequisites to SEC-01 closure.

### SEC-01 implementation contract freeze — Frozen 2026-07-17

The provider, platform-store, and protocol reviews independently agreed that this contract is implementable. This section is now the normative SEC-01 implementation contract; production edits may proceed only within it. Any change to the fixed suite, identity derivation, authorization semantics, legacy separation, persistent record format, or failure matrix requires a new recorded owner decision before dependent code changes.

#### Protocol version and negotiation

- Secure mode is application protocol 2.0. The only suite is `Noise_XX_25519_ChaChaPoly_SHA256` with suite ID `0x01`; there is no algorithm list, IK/PSK variant, or suite agility in v2. The initiator is always the transport dialer and the responder is always the accepted connection.
- Each side uses this exact 16-byte preface: offsets 0..3 ASCII `P2KS`; offset 4 preface format `0x01`; offset 5 application major `0x02`; offset 6 minor `0x00`; offset 7 suite `0x01`; offset 8 role (`0x01` initiator, `0x02` responder); offset 9 flags `0x00`; offsets 10..15 reserved zero. The initiator writes first, the responder validates then writes its responder preface, and the initiator validates it. Every field is exact.
- Secure v2 has no downgrade-capable negotiation. A secure endpoint accepts only the exact v2 preface/suite it is configured to implement. Missing, legacy, malformed, or unknown prefaces receive a uniform bounded close with no detailed plaintext error.
- `SecurityMode.NoneForMvp` remains source-compatible but deprecated and must be selected explicitly for the whole kit. It uses the existing plaintext protocol/frame major 1. A kit never switches mode from discovery TXT, peer input, handshake failure, retry, or reconnect.
- Secure LAN advertises/browses `_p2pkit2._tcp`; explicit legacy advertises/browses `_p2pkit._tcp`. The discovery protocol/fingerprint values remain untrusted usability/routing claims and never authorize a peer or select a weaker mode. A kit never enables both namespaces.
- Both sides use this byte-identical Noise prologue: ASCII `dev.p2pkit.secure-channel.v2\0`, then U16BE exact UTF-8 AppId byte length, exact AppId UTF-8 bytes, initiator preface, responder preface. AppId UTF-8 is bounded before allocation and is neither normalized nor sent separately in plaintext on the data connection.
- Noise messages have an unsigned U16BE length prefix, empty application payload, and exact body lengths 32, 96, and 64 bytes for XX messages 1, 2, and 3. The initiator authorizes the responder static key after message 2 and before revealing its static in message 3; the responder authorizes after message 3. Split maps cipher state 1 to initiator-to-responder and state 2 to responder-to-initiator.
- After `Split`, records are `U16BE(ciphertextLength) || NoiseTransportCiphertext` with zero-length Noise associated data. Plaintext is segmented at 16,384 bytes; valid ciphertext lengths are 16 through 16,400 bytes. This deliberately follows the standard Noise transport cipher instead of inventing length-header associated data.
- Secure record writes, encryption, and nonce allocation are serialized. Ciphertext records are processed strictly in order. Nonces use the Noise ChaChaPoly encoding and may never wrap; authentication failure, invalid length, truncation, replay/reorder, EOF mid-record, or counter exhaustion atomically closes both directions and discards queued plaintext.
- Directional nonces are implicit `0` through `2^64 - 2`; the maximum unsigned value is never used and v2 performs no rekey. A fresh handshake is required before exhaustion.
- One bounded security-owned raw pump starts before preface parsing and remains the only collector of `RawConnection.read()`. It hands a bounded segmented input from the sequential handshake decoder to the sequential record decoder without a second collector. A bounded plaintext channel propagates application backpressure to the socket.
- The application `DefaultP2pProtocol` reader is created only over the decrypted `SecureConnection` after Noise and authorization succeed. HELLO, frame headers, controls, messages, and files are inside encryption.
- Inner HELLO and every frame use major 2 and are rejected immediately on any other header/payload version. Legacy mode uses major 1. Version checks occur as soon as the fixed header is available.

#### Cryptographic identity and fingerprint format

- Each AppId has one independent long-term X25519 static keypair. The canonical public-key encoding is the 32-byte raw RFC 7748 u-coordinate; provider-specific DER/PEM encodings never enter identity derivation or the wire.
- `fingerprintDigest = SHA-256(ASCII("dev.p2pkit.x25519-fingerprint.v1\0") || rawPublicKey32)`.
- `peerIdDigest = SHA-256(ASCII("dev.p2pkit.peer-id.v2\0") || U16BE(appIdUtf8.length) || appIdUtf8 || fingerprintDigest)`.
- The canonical fingerprint is `p2f1-` plus lowercase unpadded Base32 of the full 32-byte fingerprint digest. The canonical PeerId is `p2id2-` plus lowercase unpadded Base32 of the full 32-byte PeerId digest. Neither authorization value is truncated; decoded digest comparisons are constant-time.
- The Noise static key proves possession; the derived PeerId must exactly equal the encrypted HELLO PeerId and the expected discovery/manual hint. Copied mDNS identifiers cannot authenticate without the corresponding private key.
- `appBinding = p2a1- || Base32LowerNoPad(SHA-256(ASCII("dev.p2pkit.app-binding.v1\0") || U16BE(appIdUtf8.length) || appIdUtf8))`. The exact QR text is `p2pkit:v2:<appBinding>:<fingerprint>`. Parsing requires exactly four colon-separated fields, canonical prefixes/lengths/characters, and an AppId binding equal to the local exact AppId. QR data is only a high-entropy pin transport; no low-entropy code or raw-PSK mode exists.
- Private keys, wrapping keys, handshake/session keys, decrypted queued data, and full fingerprints are never logged. CSPRNG/key-generation failure is fatal. Temporary key bytes are cleared where the runtime permits.

#### Authorization and manual peers

- Unknown authenticated identities are rejected by default.
- Built-in authorization modes are: reject unknown (the default), a static/configured set or trusted store of full v2 fingerprints, a per-connect/manual full fingerprint, and an explicitly selected `AcceptAnyAuthenticatedSameApp` mode. Same AppId is scoping, not authorization. There is no interactive approval callback, TOFU, or human-entered code in this first implementation.
- Outgoing discovered connections must authenticate the exact key-derived PeerId advertised by the selected peer. Inbound identities must satisfy the configured authorization mode before HELLO/session publication.
- Secure manual-IP registration requires an expected v2 fingerprint and derives its real expected PeerId from the exact AppId plus fingerprint. The synthetic manual identity path is legacy-only. Existing no-fingerprint manual APIs remain for source compatibility but fail with a typed security-configuration error when the kit is secure.
- Reconnect permanently retains and authenticates the initially established fingerprint even under accept-any before rearming the existing session. A refreshed endpoint can change routing only, never identity. Simultaneous-open arbitration occurs only after both candidates are authenticated.

#### Identity migration and rollback

- Secure v2 uses a new identity-store namespace and never overwrites/deletes the existing UUID `peer-id` storage. First secure construction creates a new key-derived PeerId, so consumers must treat the device as a new authenticated identity and re-pin it. No claim is made that the legacy UUID was cryptographically bound.
- Successful secure creation is atomic: all concurrent constructors for one AppId return the same committed key. A losing creator discards its uncommitted material and reloads the winner.
- Downgrading application configuration to explicit legacy mode resumes the untouched legacy UUID and v1 wire behavior; it does not translate pins or delete v2 keys. Re-enabling secure mode returns to the same v2 identity. Rollback is therefore operationally possible but always an explicit security downgrade.
- Old binaries interoperate only when the new binary explicitly selects legacy mode. Secure-v2 and legacy-v1 endpoints do not connect. There is no dual listener, fallback retry, opportunistic mode, or same-session upgrade.
- Secure identity material is per-AppId and device-local. Android secure files live in no-backup storage; iOS uses a device-only Keychain accessibility class; neither identity is restored to another device. JVM persistence behavior is defined by the injected store.

#### Storage A and failure behavior

- The canonical inner identity record is exactly 104 bytes: magic ASCII `P2KI` (4), schema `0x01` (1), algorithm X25519 `0x01` (1), zero flags U16BE (2), full 32-byte AppId namespace hash (32), raw private key (32), raw public key (32). `namespaceHash = SHA-256(ASCII("dev.p2pkit.identity-namespace.v2\0") || U16BE(appIdUtf8.length) || appIdUtf8)`. Unknown magic/schema/algorithm/flags, wrong namespace, wrong length, trailing bytes, or public/private mismatch is corruption.
- Every load derives the public key again from the private key and compares it with the record. A store returns only a durable, reread, fully validated winner. Generated and losing private arrays are cleared best-effort.

- Android stores the inner record only as AES-256-GCM ciphertext at `noBackupFilesDir/p2pkit/identity-v2/<full-namespace-hash>/identity.blob`. The non-exportable wrapping key alias is `dev.p2pkit.identity.v2.<full-namespace-hash>` in Android Keystore. The exact strict outer blob is ASCII `P2KB` (4), schema `0x01` (1), AES-GCM algorithm `0x01` (1), zero flags U16BE (2), namespace hash (32), IV length `0x0c` (1), ciphertext length U16BE (2), random IV (12), and ciphertext/tag (120 for the 104-byte inner record). The fixed header through ciphertext length is AAD. A process lock plus cross-process file lock and `AtomicFile` commit protect creation.
- Android's state matrix is exact: blob absent/alias absent creates; present/present decrypts and validates; present/absent is permanent key loss; absent/present is incomplete creation/storage damage; malformed/tag failure is corruption. Only an alias created by a currently failing first transaction may be cleaned up; no state silently regenerates.
- iOS stores the 104-byte record as a non-synchronizable generic-password Keychain item: service `dev.p2pkit.identity.v2`, account full namespace hash, default access group, `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`. `SecItemAdd` duplicate means reload the winner. The strict nonsecret marker is exactly 72 bytes: ASCII `P2KM` (4), schema `0x01` (1), X25519 algorithm `0x01` (1), zero flags U16BE (2), namespace hash (32), fingerprint digest (32). It is atomically stored under Application Support and excluded from backup.
- iOS's state matrix is exact: item plus matching marker is valid; marker without item is key loss; item without marker is a recoverable interrupted commit/reinstall and recreates the marker after validation; both absent creates; any mismatch/corruption fails closed. `errSecInteractionNotAllowed`/before-first-unlock is retry-after-unlock and never rotates identity.
- JVM secure mode requires an injected synchronous `JvmSecureIdentityStore` with `read`, durable cross-process atomic `putIfAbsent` returning the durable winner, and durable idempotent `delete`. It stores the opaque 104-byte record and is responsible for confidentiality/integrity at rest. Core supplies no silently plaintext “secure” default; absence fails before any transport factory. Tests may use a loudly named in-memory test store; samples must make development-only storage explicit and must not describe it as production protection.
- Existing mobile PeerId-storage fallbacks are legacy-only. Secure mode never falls back to UUID, plaintext file, `NSUserDefaults`, in-memory identity, regenerated key, or legacy mode.
- First-use absence creates and atomically commits a key. Once any v2-store marker/item exists, unreadable, undecryptable, missing-key, corrupt, or inconsistent material is `KeyLostOrCorrupt`: fail closed, preserve evidence, and never auto-rotate.
- Key loss has no implicit recovery. Recovery requires an explicit destructive reset operation initiated by the application/owner, which deletes only the selected AppId's v2 local identity and generates a different PeerId on the next construction. The durable reset marker is exactly 40 bytes: ASCII `P2KR` (4), schema `0x01` (1), local-identity-reset action `0x01` (1), zero flags U16BE (2), namespace hash (32). It is committed before deletion; interrupted reset is completed only by the next explicit maintenance call, never by ordinary construction. The reset API reports the identity-change/re-pinning consequence, rejects a known live in-process kit, documents its cross-process exclusivity precondition, keeps configured remote pins by default, and never runs from connection error handling.
- A failed initial persistence writes no usable kit and exposes no process-local transient identity. Private material from failed/losing creation is discarded/cleared. Store exceptions retain their cause without including secrets.
- On Android uninstall/clear-data, both no-backup ciphertext and Keystore alias are expected to disappear. If restored ciphertext exists without its wrapping key, construction fails closed. On iOS, device-only Keychain material may survive reinstall on the same device according to OS behavior, but never migrates to another device; explicit reset rotates it. JVM lifecycle follows the host store contract.

#### Provider freeze and assurance boundary

- Common code uses `cryptography-core:0.6.0` only as a primitive API. JVM and Android explicitly instantiate `CryptographyProvider.JDK(BouncyCastleProvider())` using `cryptography-provider-jdk:0.6.0` and `bcprov-jdk18on:1.85`. Apple explicitly instantiates `CryptographyProvider.CryptoKit` using `cryptography-provider-cryptokit:0.6.0` and the `dev.whyoleg.cryptography` 0.6.0 linker plugin.
- The engine never uses `CryptographyProvider.Default`, service/provider discovery, the optimal provider, or application-installed provider ordering. Provider types remain internal and publication metadata must not leak them into the public ABI.
- The repository implements the strict Noise state machine but no cryptographic primitive. It follows the official Noise specification and is tested against official/Cacophony vectors plus RFC/provider KATs. All-zero X25519 output is independently rejected with a fixed-work accumulator. Owned key/chaining buffers are wiped best-effort, without claiming JVM/Swift/provider copies are erasable.
- No suitable maintained KMP Noise implementation was found. `cryptography-kotlin` 0.6.0's X25519/ChaCha adapters and the repository's Noise state machine have no identified independent professional audit. Local implementation may proceed, but external cryptographic design/code audit, physical API-24/device interoperability, and hostile-network validation remain mandatory production-release gates. SEC-01 must not be presented as production-security certification without them.

#### Compatibility acceptance matrix

| Local | Remote | Required result |
| --- | --- | --- |
| Secure v2 | Secure v2, same AppId, authorized correct key | Authenticated encrypted session; frame/HELLO major 2 |
| Secure v2 | Secure v2, different AppId | Uniform authentication/setup failure; no session/publication |
| Secure v2 | Secure v2, copied victim discovery ID but attacker key | Exact local identity-mismatch failure; uniform peer-visible close |
| Secure v2 | Secure v2, valid but unknown key under default policy | Typed unauthorized failure; no session/publication |
| Secure v2 | Legacy v1 or old 0.6.x | Uniform bounded close; no fallback or second dial |
| Legacy v1 explicit | Legacy v1 explicit or old 0.6.x | Existing plaintext interoperability preserved |
| Legacy v1 explicit | Secure v2 | Incompatible close; secure endpoint never downgrades |
| Secure v2 after legacy upgrade | Previously known legacy UUID peer | New key-derived identity; explicit re-pin required |
| Explicit rollback to legacy | Old peer | Old UUID/v1 behavior resumes; v2 identity remains stored for re-upgrade |

Compatibility is accepted only when source/API compatibility for explicit legacy callers, binary metadata, public transport SPI, manual-IP overloads/errors, discovery filtering, cross-platform known-answer vectors, sole-reader ownership, raw-wire confidentiality, key-store failure matrix, migration/rollback matrix, and the full test/build/publication gate all pass. Network encryption does not promise mDNS privacy, traffic-shape privacy, authorization of unknown keys, endpoint-advertisement availability, or protection after local private-key compromise.

Implementation is authorized. The exact protocol negotiation, migration/rollback, secure-store/key-loss behavior, provider selection, and compatibility acceptance contract above is frozen and reviewed.

### SEC-01 analysis commands and exact results

No compile/test command had been run at the contract-freeze checkpoint because no production source was yet modified. The prior owner-decision blocker is resolved; implementation and verification evidence is appended here as each focused SEC sub-unit proceeds. Existing red repository gates remain recorded in the baseline table and are not attributed to the security changes without reproduction.

| Command/check | Exact result |
| --- | --- |
| `git branch --show-current; git rev-parse HEAD; git rev-parse origin/main` | Branch `remediation/full-register-2026-07`; HEAD and `origin/main` both `6a05ccd04fcb6fb8106ed47941618fb6bcfd3fa6` |
| `rg -n "SecurityMode\|SecurityManager\|SecureConnection\|performHandshake" p2p-core/src` | Confirmed only `NoneForMvp`, always-installed no-op manager, unusable public extension ordering, and no consumer of authenticated `peerIdentity` |
| `sed`/`nl` inspection of `Config.kt`, `Identity.kt`, `Builders.kt`, `SecurityManager.kt`, `Handshake.kt`, `RawConnection.kt`, `P2pKitImpl.kt`, `SessionManager.kt`, protocol files, and security/identity tests | Confirmed sole raw reader starts at `SessionManager.kt:406` and security runs only at line 485 after plaintext identity parsing |
| `rg` inspection of LAN socket/Apple parameter implementations | Confirmed plain byte-stream transports; Apple explicitly uses non-TLS Network.framework parameters |
| Official Noise specification review | Confirmed key possession is not authorization, negotiation must be transcript/prologue-bound against rollback, records/messages are bounded, and nonce/application termination responsibilities must be specified |
| Independent SEC-01 protocol/store/provider reviews | Frozen 16-byte preface and standard Noise record profile; frozen Android/iOS/JVM state matrices; explicit CryptoKit and JDK+Bouncy Castle providers; no provider-selection blocker |
| Tracker finding-set comparison | 150 finding rows exactly match the 150 source IDs; no omissions/duplicates |
| Tracker gap/phase comparison | 54 gap rows; execution plan assigns 150 findings and 54 gaps exactly once; no omissions/duplicates or range shorthand |

### SEC-01 implementation and review result — 2026-07-18

#### Confirmed root cause and implemented correction

The implementation confirmed the analysis above: plaintext HELLO parsing owned the sole raw reader before the old public security hook ran, so identity was attacker-controlled and no encryption wrapper could safely take ownership. The correction makes `SecurityMode.AuthenticatedV2` the default and moves the complete Noise exchange ahead of construction of `DefaultP2pProtocol`. A security-owned pump is now the only collector of the raw connection for its lifetime; the application parser sees only authenticated decrypted bytes. `NoneForMvp` remains an explicitly selected, deprecated whole-kit v1 migration mode with no negotiation or fallback.

The v2 implementation includes the frozen preface/prologue, Noise XX state machine, bounded authenticated records, exact AppId/key-derived identity validation, reject-unknown/pinned/explicit accept-any authorization, reconnect key pinning, encrypted HELLO major 2, strict frame-major validation, full-fingerprint manual IP registration, secure/legacy Bonjour namespace separation, and typed failure results. A PR-style ownership review found and corrected one double-close path: after secure setup begins the security engine owns and closes raw exactly once; `SessionManager` closes raw directly only for legacy setup. The regression test now asserts the exact close count.

Storage A is implemented with the frozen inner record and reset marker. Android uses AES-GCM with a non-exportable Keystore wrapping key and no-backup atomic ciphertext; Apple uses a device-only nonsynchronizable Keychain item plus atomic nonsecret marker; JVM requires an injected `JvmSecureIdentityStore` and has no plaintext production default. Loads rederive and compare the public key, concurrent creation selects one durable reread winner, corrupt/lost material fails closed, cancellation is preserved, and explicit reset is rejected while a kit owns the identity.

#### Files and components changed

The focused diff contains 92 status entries before expansion of newly added directories. The exact authoritative file ledger is the focused commit's `git show --name-status`; the implementation surface is:

- dependency/provider configuration: `gradle/libs.versions.toml`, `p2p-core/build.gradle.kts`;
- public core/API and DSL: `Config.kt`, `Errors.kt`, `Identity.kt`, `P2pKit.kt`, `P2pSession.kt`, `dsl/Builders.kt`, and the public `security/` additions;
- core ownership/orchestration: `Handshake.kt`, `P2pKitImpl.kt`, `P2pSessionImpl.kt`, `PeerRegistry.kt`, `SessionManager.kt`, transport internal/factory contracts, secure identity factories, and the new `internal/security/` Noise/record engine;
- wire: `DefaultP2pProtocol.kt`, `Frame.kt`, `FrameCodec.kt`, `FrameReader.kt`, `HelloPayload.kt`, and `ProtocolConstants.kt`;
- platform identity/provider implementations: Android secure storage/provider, iOS Keychain storage/CryptoKit provider, and JVM injected-store adapter/JDK+Bouncy Castle provider;
- manual provisioning: common registrar/types/factories plus Android, desktop, and Apple managers;
- LAN discovery/security profile: common `Lan.kt`; JVM, Android, and Apple discovery/DSL implementations and their tests;
- consumers: Android, desktop CLI, desktop UI, KMP JVM/Android, and Swift sample configuration, plus clearly named JVM development-only in-memory sample stores;
- tests: new common Noise, wire, identity, engine, and end-to-end secure-session suites; JVM store/provider tests; iOS Keychain tests; LAN secure loopback/record tests; provisioning secure manual-loopback tests; legacy fixture updates.

No original review report, deferred register, `.review-2026-07/` content, or unrelated user file is part of this unit.

#### Tests added or strengthened

- Noise/KAT: exact Cacophony `Noise_XX_25519_ChaChaPoly_SHA256` handshake flights, handshake hash, and bidirectional transport ciphertext; canonical Base32/RFC vectors; frozen provider/identity derivation values; all-zero DH and nonce/authentication terminal behavior.
- Wire/records: exact v2 preface and prologue, every unsupported field, length/allocation boundaries, exact XX flight sizes, fragmented/batched records, early invalid-length rejection, truncation, one raw collector, no legacy fallback, and initiator-static non-disclosure on rejected responder identity.
- Authentication/authorization: default reject unknown, configured pins, caller-owned pin-set snapshot/immutability, per-connect pin, explicit accept-any, wrong AppId/key/PeerId/fingerprint, copied victim identity, encrypted HELLO, raw-wire confidentiality, manual pin requirement, reconnect pin retention, and explicit legacy incompatibility.
- Lifecycle: cancellation during blocked Noise write, exact raw close count, pending-connect removal, retry after cancellation, setup cleanup, immutable authenticated identities, and live-use reset exclusion.
- Storage: exact 104/72/40-byte formats, strict corrupt-field rejection, AppId collision independence, atomic/concurrent first creation, durable-winner reread, persistence failure/cancellation, mismatch/key loss/interrupted reset, private-array clearing, iOS Keychain/marker state matrix, and absent JVM-store fail-closed behavior.
- Integration: real JVM mDNS/TCP secure text/binary/file loopback, real desktop manual-IP secure loopback, common JVM/Apple fake-raw secure sessions, sample/KMP/Swift compilation, and publication assembly.

#### Verification commands and exact results

| Command/check | Result |
| --- | --- |
| Focused `:p2p-core:jvmTest` security/identity/session suites | Pass; the final post-review run includes `SecureSessionIntegrationTest`, all internal security tests, and all public security tests |
| `:p2p-core:jvmTest` | 336 tests, 0 failures/errors/skips after the final authorization-snapshot regression |
| `:p2p-core:iosSimulatorArm64Test` | 317 tests, 0 failures/errors/skips after the final authorization-snapshot regression; the previously reported reconnect timeout did not reproduce |
| `:p2p-core:compileAndroidMain`, iOS simulator compilation/test linkage | Pass |
| Secure session integration repeated three consecutive forced runs | All three pass with deterministic subscription barriers |
| `:p2p-transport-lan:jvmTest` | 55 tests pass, including real secure mDNS/TCP/message/file loopback |
| Android host provisioning tests and desktop provisioning tests | Pass; desktop includes real secure manual-IP loopback |
| Desktop CLI/UI classes, KMP JVM tests/Android compile, Android sample assemble | Pass |
| Release `P2pKitShared` XCFramework and Swift simulator sample build with signing disabled | Pass; Xcode `BUILD SUCCEEDED` |
| `scripts/check-publish-artifacts.sh` | Pass; all 15 publications contain primary, sources, Javadoc, POM, and Gradle module artifacts |
| `git diff --check` | Pass |
| Final `./gradlew check` | Red only on registered non-SEC baselines: Android sample lint has 1 `CoarseFineLocation` error plus 3 warnings (`SAMPLE-17`/`BUILD-08`), and Apple LAN has 40 tests with the same 2 lifecycle timeouts plus 1 intentional skip (`LAN-03`/LAN lifecycle unit). Core JVM and iOS security tests pass within the run. Existing `ExperimentalCoroutinesApi` test warnings remain `BUILD-14`. |

#### Compatibility, migration, and remaining risk

This is an intentional runtime/wire security change: secure v2 is the default and does not interoperate with v1. Existing source callers can explicitly select deprecated `NoneForMvp` to resume the untouched UUID/v1 identity and wire behavior; there is no automatic fallback. First secure use creates a new key-derived identity and requires re-pinning. Full fingerprints/QRs are required for secure manual IP unless an explicit authorization policy permits the identity. Public transports remain byte-stream providers; security ownership is internal to core. Crypto providers remain implementation dependencies rather than public ABI types.

SEC-01 is `Implemented`, not `Verified`. The exact remaining gates are: independent professional review of the repository Noise state machine and provider integration; physical API-24+ Android Keystore and Android/Apple cross-device secure LAN interoperability; two-machine hostile-network/tamper/resource validation; and a green full repository gate after the independently tracked Android lint and Apple LAN lifecycle failures are fixed. These gates do not justify weakening or bypassing the secure default, but they prohibit a production-security claim.

#### Diff review conclusion

The final local review checked reader ownership, secure/raw close ownership, cancellation propagation, pending-connect cleanup, setup deadlines, record bounds/backpressure, nonce serialization/exhaustion, identity immutability and key clearing, reset/live-use exclusion, discovery downgrade separation, manual pinning, reconnect identity retention, provider selection, sample call sites, legacy-only call sites, and equivalent platform implementations. No new SEC-01 correctness defect remains in the local diff. The pre-existing full-gate failures and external assurance boundaries above remain explicit and are not waived.

#### Source control and post-commit verification

- Branch: `remediation/full-register-2026-07`.
- Focused implementation commit: `b79c9ba` (`SEC-01: add authenticated protocol v2 and protected identities`), 109 files, 10,996 insertions, 326 deletions.
- Committed diff review: `git show --check --stat --oneline b79c9ba` passed; the only remaining worktree entries were the expressly excluded untracked review/deferred files.
- Post-commit gate: `./gradlew :p2p-core:jvmTest :p2p-core:iosSimulatorArm64Test` passed from `b79c9ba` in 1m 5s; 336 JVM and 317 iOS-simulator tests passed. Only the separately registered `BUILD-14` test opt-in warnings were emitted.
- Push: `b79c9ba` pushed successfully to `origin/remediation/full-register-2026-07` on 2026-07-18. The remote reported that the repository has moved to `https://github.com/p2pKit/P2pKit.git`; the configured `origin` accepted the branch and now tracks it.

## Execution record: REL-REMOTE-01

### Finding, status, and confirmed root cause

| Field | Value |
| --- | --- |
| Finding | BUILD-02 — High release blocker — no remote publication target |
| Status | Blocked after analysis; no release behavior was guessed or modified |
| Confirmed root cause | All four library modules apply `maven-publish` and local conditional signing, but no `publishing.repositories`, Central bundle assembly/upload task, Portal status/release task, or CI credential contract exists. Only `publishToMavenLocal` is executable. |
| Affected surfaces | Root/module Gradle publication configuration, release bundle/check scripts, CI secret contract, `dev.p2pkit` namespace ownership, signing identity, and Central deployment policy |
| Dependent evidence | ENV-07 live remote upload; FINAL-01 release proof. REL-ABI-01 and other source units remain independent and are not blocked. |

### Analysis and attempted work

- Inspected root and all module publication/signing configuration, `gradle.properties`, and `scripts/check-publish-artifacts.sh`. No remote repository or Portal integration exists; the property file explicitly records that limitation.
- The existing local checker successfully assembled all 15 publication shapes during SEC-01, but it does not create the exact signed/checksummed Central bundle or exercise upload/status/drop/release behavior.
- Verified the current official service contract. Sonatype states that there is currently no official Gradle Portal plugin; supported choices are a Maven plugin, a Maven-layout bundle uploaded through the Portal/Publisher API, the Portal OSSRH Staging API for applicable existing namespaces, or unsupported community Gradle plugins. See [official Gradle guidance](https://central.sonatype.org/publish/publish-portal-gradle/), [Publisher API](https://central.sonatype.org/publish/publish-portal-api/), [bundle layout](https://central.sonatype.org/publish/publish-portal-upload/), and [artifact/signature/checksum requirements](https://central.sonatype.org/publish/requirements/).
- No token, namespace dashboard state, signing key, or release authorization was accessed or requested. No upload was attempted because Central releases are immutable and the repository does not yet know whether `dev.p2pkit` is a Portal or legacy OSSRH namespace.

### Exact blocker and required owner resources

The owner must provide one policy decision and later CI-held resources:

1. Confirm whether `dev.p2pkit` is verified in the Central Portal, and whether it appears as a **Central Portal namespace** or **OSSRH namespace**.
2. Approve the publication path. Recommended: repository-owned deterministic Maven-layout bundle assembly plus the first-party Portal Publisher API, initially `USER_MANAGED`. This avoids trusting an unsupported third-party Gradle publication plugin and prevents a valid CI build from irreversibly auto-publishing before owner review.
3. Confirm whether releases remain `USER_MANAGED` or become `AUTOMATIC` after validation. Automatic release shortens the pipeline but turns a credentialed CI invocation into an irreversible publish action.
4. Provide only through CI secrets when live validation is authorized: Portal token username/password, ASCII-armored signing private key/password, and the verified namespace/account access. No secret belongs in Git, Gradle properties committed to the repository, logs, or the tracker.

Realistic alternatives and consequences:

- Portal Publisher API + repository-owned bundle (**recommended**): smallest trust surface and exact local bundle dry-run; requires maintaining a small uploader/status client or CI script and checksum/signature validation.
- Portal OSSRH Staging API: reuses Gradle `maven-publish`, but is appropriate only if the namespace/account state supports that workflow and requires staging cleanup/status integration.
- Community Gradle/JReleaser plugin: less custom code, but adds a release-critical third-party plugin not supported by Sonatype; it requires separate provenance, maintenance, and supply-chain approval.
- Manual Portal upload: simple for rare releases but weakens repeatability/auditability and leaves BUILD-02's automated release path incomplete.

Precise owner reply format for the later consolidated decision package:

`REL-REMOTE-01: namespace=PORTAL|OSSRH; path=PORTAL_API_BUNDLE|OSSRH_STAGING|COMMUNITY_PLUGIN|MANUAL; release=USER_MANAGED|AUTOMATIC; live_credentials=AVAILABLE_IN_CI|NOT_YET`

Until that reply is supplied, only REL-REMOTE-01, ENV-07, and their genuinely dependent final-release proof are blocked. No assumptions from this unit may constrain REL-ABI-01 or other dependency-ready remediation.

## Current execution record: REL-ABI-01

### Analysis and confirmed reproduction

| Field | Value |
| --- | --- |
| Finding/gaps | BUILD-01 (High), CORE-T13, and the publication-consumer portion of PS-T09 |
| Status | In Progress; analysis and plan complete, no implementation edit made before this record |
| Root cause | Gradle `implementation` was used for dependencies whose types occur in public Kotlin metadata. Generated target POMs therefore mark them runtime and Gradle API variants omit them entirely. |
| Affected modules | `p2p-core`, `p2p-transport-lan`, Android provisioning, desktop provisioning; every published JVM/Android/KMP/iOS target and downstream Kotlin/Java consumer |
| Public dependencies | Core exposes coroutines `Flow`/`SharedFlow`/`StateFlow`/`Job` and kotlinx-io `RawSource`/`RawSink`; LAN exposes core types and direct coroutine diagnostics/implementations; both provisioning sidecars expose core provisioning types and coroutine flow types. Crypto/serialization/JmDNS/provider types remain internal and must stay runtime/implementation. |

Generated metadata reproduces the defect exactly:

- `p2p-core` JVM/Android POMs publish coroutines at runtime and API variants list only kotlinx-io/stdlib, even though core's public API contains coroutine types.
- LAN JVM/Android POMs correctly publish core at compile but publish coroutines at runtime; API variants omit coroutines even though `JvmLanDiag.events` and Apple diagnostics expose `SharedFlow` directly.
- Android provisioning publishes both core and coroutines at runtime and its API variant lists neither.
- Desktop provisioning publishes core, LAN, and coroutines at runtime and its API variant lists none. Production desktop code does not import LAN; LAN is used only by `ManualIpLoopbackTest`, so that dependency is both incorrectly scoped and unnecessarily shipped.
- The KMP root POMs flatten dependencies to runtime as a Kotlin publication convention; the authoritative Gradle module target variants still must carry correct API dependencies, and Maven target POMs must use compile scope.

### Comprehensive implementation plan

1. Change `p2p-core` common coroutines from `implementation` to `api`; retain kotlinx-io as `api`; keep serialization, cryptography core/providers, and Bouncy Castle internal.
2. Change LAN common coroutines to `api`; keep core as `api`; keep JmDNS internal.
3. Change Android provisioning core and coroutines to `api`.
4. Change desktop provisioning core and coroutines to `api`; move LAN from production `implementation` to `testImplementation` because only its test loopback uses it.
5. Add a repository-owned external-consumer gate that publishes to a throwaway Maven repository, creates isolated builds outside the composite/project dependency graph, and compiles consumers that declare only one published top-level artifact. Cover core JVM, LAN JVM, desktop provisioning JVM, Android provisioning, KMP common/JVM, and iOS simulator publication consumption. Do not add the transitive dependencies explicitly in the consumer; that would hide this regression.
6. Assert generated POM/API-variant scopes so a consumer compilation cannot accidentally pass because another test dependency supplies the missing library.
7. Run targeted metadata generation/consumer gates, all four affected module tests/compiles, Android/KMP/iOS consumer compilation, publication shape validation, samples, and the full repository gate. Repeat the clean consumer gate from committed state.

Expected files: the four module `build.gradle.kts` files; one new isolated publication-consumer check script and its generated inline fixtures; tracker updates. No production Kotlin source or public signature should change.

Compatibility and risk: this is source/binary compatible and only adds required transitive compile dependencies. Consumer classpaths become correct and slightly more explicit. Runtime artifacts/versions do not change. Moving desktop LAN to test-only removes an erroneous runtime dependency from that sidecar; applications needing LAN already select the LAN transport separately. The external-consumer test must use a throwaway repository/directory and never write credentials or publish remotely.

Cleanup/rollback: the gate uses `mktemp`, traps cleanup, and does not touch `~/.m2`. A failed nested build preserves only ordinary module `build/` diagnostics until the script exits; no external state changes. Rollback is the focused build-script/test-script commit only.

Acceptance criteria:

- Generated JVM/Android target POMs classify every public ABI dependency as compile and every implementation-only dependency as runtime.
- Gradle module API variants include core/coroutines/kotlinx-io exactly where public ABI requires them and exclude serialization, crypto providers, Bouncy Castle, JmDNS, and desktop's test-only LAN.
- Fresh isolated consumers compile without directly declaring transitive ABI dependencies for JVM, Android, KMP common/JVM, and iOS simulator targets.
- Existing module/platform/sample/publication tests pass; no warning is introduced.
- Full gate has no new failure; any existing unrelated baseline remains exact and separately owned.

### Implementation, tests, and diff review result

Implementation is complete in five focused files:

- `p2p-core/build.gradle.kts`: coroutines is now `api`; kotlinx-io remains `api`; serialization and every security provider remain `implementation`.
- `p2p-transport-lan/build.gradle.kts`: coroutines is now `api` alongside core; JmDNS remains `implementation`.
- `p2p-network-provisioning-android/build.gradle.kts`: core and coroutines are now `api`.
- `p2p-network-provisioning-desktop/build.gradle.kts`: core and coroutines are now `api`; LAN moved from production to `testImplementation`.
- `scripts/check-published-consumers.sh`: new executable, isolated, cleanup-safe publication consumer gate.

The new gate publishes all modules to an `mktemp` Maven repository, asserts exact target-POM scopes, confirms desktop does not publish LAN, generates fresh projects outside the repository dependency graph, and compiles:

- a core-only JVM consumer using `StateFlow` and `RawSink`;
- a LAN-only JVM consumer using direct LAN `SharedFlow` plus transitive core types;
- a desktop-provisioning-only JVM consumer using transitive core/coroutine types;
- an Android-library consumer depending only on the Android provisioning AAR;
- a KMP LAN consumer for common, JVM, Android, and iOS simulator source sets.

The gate deliberately does not declare core, coroutines, or kotlinx-io directly where they must arrive transitively. Review caught and removed an initial fixture weakness where LAN could have masked Android provisioning metadata; Android provisioning now has its own isolated module. It also imports only `sdk.dir` into the temporary project when Android environment variables are absent, never copies other local properties, removes the entire validated `mktemp` directory through a quoted trap, and performs no remote publication.

Regenerated API variants now contain:

- core JVM/Android: coroutines, kotlinx-io, stdlib;
- LAN JVM: core, coroutines, stdlib;
- Android provisioning: core, coroutines, stdlib;
- desktop provisioning: core, coroutines, stdlib and no LAN.

Serialization, cryptography core/providers, Bouncy Castle, and JmDNS remain runtime-only. No production source/public signature changed, and no equivalent module retained the wrong scope.

### Verification results before commit

| Command/check | Exact result |
| --- | --- |
| `bash -n scripts/check-published-consumers.sh` | Pass |
| `scripts/check-published-consumers.sh` | Pass; exact POM assertions plus isolated core JVM, LAN JVM, desktop JVM, Android provisioning, KMP JVM/Android/iOS simulator consumers |
| Generated target module JSON review with `jq` | API variants contain exactly the required public dependencies listed above |
| Affected module command: core JVM/iOS/Android, LAN JVM/Android/iOS compile, Android/desktop provisioning tests | Pass; core JVM 336/336, core iOS 317/317, LAN JVM 55/55, Android provisioning 18/18, desktop provisioning 6/6 |
| `:p2p-transport-lan:iosSimulatorArm64Test` | Registered baseline unchanged: 40 tests, 2 lifecycle timeouts, 1 intentional skip |
| `scripts/check-publish-artifacts.sh` | Pass; all 15 publication rows |
| `./gradlew check` | No new failure. Same registered baseline only: Android sample lint 1 error/3 warnings and Apple LAN 2 lifecycle timeouts/1 skip; existing BUILD-14 test opt-in warnings remain. |
| `git diff --check` | Pass |

Compatibility: source/binary/runtime behavior is unchanged. Published consumers now receive required compile dependencies; desktop provisioning loses only an unused production LAN runtime edge and retains it for its loopback test. Remaining PS-T09 physical/runtime SAMPLE-21 work is not claimed by this build-only unit.

### Source control and committed-state verification

The focused implementation is commit `8f15d75` (`BUILD-01: publish public ABI dependencies correctly`) on branch `remediation/full-register-2026-07`. `git show --check --stat --oneline 8f15d75` reports a clean six-file diff limited to the four affected Gradle modules, the new consumer gate, and this tracker. The committed-state rerun of `scripts/check-published-consumers.sh` passed every exact POM assertion and isolated JVM, Android, KMP, and iOS simulator consumer.

BUILD-01 and CORE-T13 are therefore `Verified`. The unrelated registered Android lint and Apple LAN baselines remain owned by their existing remediation units and do not weaken this unit's exact publication-metadata acceptance criteria. PS-T09 remains `Planned` because its SAMPLE-21 runtime/device conjunct is independent and incomplete.

## Current execution record: LIF-GEN-01

### Analysis and confirmed reproduction

| Field | Value |
| --- | --- |
| Finding/gap | CORE-01 (High) and CORE-T01 |
| Status | In Progress; current code and tests reviewed and implementation plan frozen before source modification |
| Root cause | `ensureStarted()` serializes only data-transport binding. `startAdvertising()`, `startDiscovery()`, and `connect()` perform resource creation and final publication outside that mutex. `stop()` latches a Boolean and closes a point-in-time snapshot, but there is no operation generation carried through the late commit. The observer-start path also checks `stopped` before, but not after, the suspending observer call. |
| Affected components | `P2pKitImpl` lifecycle/state/observer logic; `SessionManager` outgoing and inbound registration boundary; discovery transports on every platform; all data transports used by outgoing connect; public `state`, `sessions`, and `incomingSessions` observations |
| Public/API compatibility | No public signature or wire-protocol change is required. The terminal contract becomes stricter: an operation that loses the race to `stop()` fails with the same post-stop `IllegalStateException` family and cannot publish or relatch state. |

The defect is still deterministically reachable on the current branch:

1. Advertising/discovery call `ensureStarted()`, then suspend in a discovery transport outside `startMutex`. `stop()` can set `Stopped` and invoke the corresponding stop method; the original start then returns late and either leaves the platform resource reopened or writes `Running`/`Failed` after terminal shutdown.
2. Outgoing `connect()` calls `ensureStarted()`, then performs transport dial, secure v2 setup, `session.start()`, and `SessionStore.tryRegister()` outside the kit lifecycle lock. `stop()` can take `activeSnapshot()` before registration; the late session is then added to the public `sessions` flow after teardown.
3. `ensureStarted()` rechecks `stopped` after data binding but not after suspending `pathObserver.start()`. If stop's bounded fallback finishes while observer start is blocked, the late starter launches the collector, latches `startResult`, and writes `Running` over `Stopped`.
4. Existing `KitLifecycleTest` covers a hung data-transport start and cancelled observer start, but deliberately cancels the late observer instead of releasing it, and has no stop race for advertising, discovery, or connect. CORE-T01 is therefore open.

### Comprehensive implementation plan

1. Introduce one private lifecycle generation gate in `P2pKitImpl`. Every public start/advertise/discover/connect operation captures the current generation before creating resources. `stop()` atomically makes the generation terminal before taking snapshots or closing resources. Concurrent `stop()` callers join one completion signal rather than starting overlapping teardown or returning while the leader is incomplete.
2. Thread the captured generation through `ensureStarted()`. Validate it under the gate before the start fast path, after every suspending data-transport bind, after observer startup, and at the final `startResult`/`Running` commit. A late observer start must execute bounded non-cancellable close and a late data bind must close terminal resources; neither may launch a collector or mutate terminal state.
3. Gate advertising/discovery success and failure state commits by generation. If terminal stop wins while a platform start is suspended, run the matching stop operation in bounded non-cancellable cleanup before returning the terminal lifecycle failure. Preserve `CancellationException` exactly when cancellation, rather than terminal invalidation, is the cause. Do not use this slice to claim ordinary multi-transport failure rollback; that remains CORE-11/CORE-T09 because retry-safe data-transport rollback needs a separate transport lifecycle decision.
4. Add an internal session-registration commit callback to `SessionManager`. Outgoing setup carries the exact kit generation; inbound setup requires only a currently active kit. `SessionStore.tryRegister()` and the accepted incoming publication decision execute only when the kit gate admits the commit. If rejected, close the uncommitted session in bounded non-cancellable cleanup and fail setup. If registration wins first, stop acquires the gate afterward and its session snapshot necessarily includes the committed session.
5. Recheck the generation before returning an existing/coalesced outgoing session. If stop already won, do not return a stale terminal handle. Preserve the existing coalescing, secure handshake, duplicate arbitration, capacity, and reconnect behavior.
6. Review every lifecycle state write and every `SessionManager` registration path for an equivalent late commit. No test timeout will be increased and no assertion will allow multiple terminal outcomes.

Expected files: `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt`, `SessionManager.kt`, `KitLifecycleTest.kt`, a focused common test fixture/test file if connect needs separation, and this tracker. No platform implementation or public interface is expected to change.

Concurrency/cleanup rules:

- The lifecycle mutex is never held across platform transport dial/start/stop, cryptography, raw I/O, or session close. It is held only for generation checks and the short atomic registration/state commit.
- Stale resource cleanup runs in `NonCancellable`, is individually bounded, logs failures, and never converts an original caller cancellation into a lifecycle success.
- `stop()` remains terminal and idempotent. Only one caller owns teardown; followers await its completion. A non-cooperative platform operation can exceed the stop bound, but its later completion cannot commit and must immediately execute stale cleanup.
- Lock ordering is lifecycle gate before the short `SessionStore` registration lock only at commit; no store path calls back into the lifecycle gate. Session/resource close occurs after releasing both locks.

Tests to add/update:

- stop while advertising start is parked: release it after `Stopped`; assert precise terminal failure, compensating stop, and permanent `Stopped` state;
- the equivalent discovery race;
- stop while a data-transport start is parked and then released (retain existing coverage, assert generation cleanup path);
- stop while path-observer start is parked, then release rather than cancel; assert no collector/state resurrection and observer cleanup;
- stop while outgoing transport connect is parked, then finish a real secure handshake; assert the connection/session is closed, `sessions` stays empty, and connect fails precisely;
- registration winning immediately before stop: assert stop observes/closes it and `sessions` is empty on return;
- concurrent stop callers: both complete only after the same teardown and resources close once where the contract permits counting;
- repeat the race suite to demonstrate deterministic synchronization without sleeps.

Acceptance criteria:

- No state write after terminal stop can produce `Running` or `Failed`.
- No outgoing or inbound session can enter public session state after the terminal generation is latched; a registration committed first is included in stop cleanup.
- Any advertising/discovery/observer/data resource that completes after losing the generation race is compensatingly closed/stopped before that operation returns.
- Cancellation remains a `CancellationException`; lifecycle invalidation has one precise post-stop failure; no errors are swallowed silently.
- All new CORE-T01 tests, full core JVM/iOS tests, affected Android compilation, samples/publication checks, and the repository gate show no new failure or warning. Existing independently registered baselines remain exact until their units are fixed.

### Implementation and review result

Status: `Verified`; implementation commit `a4e0bb0` and committed-state checks complete.

Confirmed root cause: the kit previously serialized only part of startup. The terminal Boolean was not an operation token, state writes were not lifecycle commits, and session registration happened after `stop()` took its active-session snapshot. A platform call that ignored or narrowly outran cancellation could therefore create a resource or publish state after terminal teardown.

Implementation:

- `P2pKitImpl` now owns one lifecycle mutex, monotonically changing generation, and one teardown completion signal. Every public start/advertise/discover/connect operation captures the generation; `stop()` atomically invalidates it and publishes `Stopping` before any resource snapshot.
- `Starting`, `Running`, and `Failed` writes are generation-checked commits. Data-transport and path-observer startup recheck after every suspending resource boundary. A stale completion performs individually bounded, logged, `NonCancellable` compensation before returning.
- Advertising and discovery validate before and after each transport. If terminal stop wins, the matching stop operation is applied across the transport set in reverse order, and neither success nor failure can overwrite `Stopped`.
- `SessionManager` receives an internal lifecycle gate. Outgoing dial ownership is rechecked immediately after transport return, and an uncommitted raw connection is closed before protocol setup. Session-store registration and accepted-incoming publication admission are one lifecycle commit, so either registration precedes stop and is present in its snapshot, or the candidate is rejected and closed.
- Existing/coalesced outgoing sessions are checked against the caller's captured generation before return. Concurrent `stop()` followers now wait for the leader's complete teardown rather than returning while resources remain live.
- Stale connection/session/resource cleanup is bounded at 2,000 ms per resource and logs timeout/failure. No public API, binary ABI, stored identity, security mode, protocol frame, or wire-version change was made.

Files changed:

- `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt`
- `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionManager.kt`
- `p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/KitLifecycleTest.kt`
- `P2PKIT_REMEDIATION_TRACKER_2026-07.md`

Tests added:

1. `lateAdvertisingCompletionIsRolledBackAfterStop`
2. `lateDiscoveryCompletionIsRolledBackAfterStop`
3. `observerThatReturnsAfterStopCannotResurrectKit`
4. `outgoingConnectThatReturnsAfterStopCannotPublishSession`
5. `sessionCommittedBeforeStopIsIncludedInTeardown`
6. `concurrentStopCallersJoinOneTeardown`

All new races use `CompletableDeferred` entry/release gates. They contain no arbitrary delay, relaxed terminal outcome, retry, or increased production/test timeout. The pre-existing `stopCompletesWhenATransportStartHangs` continues to cover the data-start boundary released after terminal stop.

External-PR review:

- Every lifecycle state write was searched. Non-terminal writes are now inside generation commits; only the stop leader writes `Stopping`/`Stopped`.
- Every `SessionManager` registration path, including inbound setup, goes through the lifecycle gate. The gate/store lock order is one-way; store code does not acquire the lifecycle gate. Platform start/dial/close, cryptography, protocol I/O, and session close do not run while the lifecycle mutex is held.
- Registration's store mutation is short and cancellation-safe: mutex acquisition happens before mutation, and the mutation body has no suspension. Loser/capacity session closes remain launched after store mutation. Incoming publication uses the already bounded flow capacity; exhaustion now removes and closes the candidate explicitly instead of suspending while holding the lifecycle commit.
- Equivalent implementations were searched in startup, discovery, observer, outgoing and incoming session setup. No platform source implements a second kit-level registration/state commit.
- Ordinary partial startup rollback without terminal stop remains CORE-11/CORE-T09. Store cleanup after all sessions close remains CORE-10. Prompt-cancellation ownership inside individual platform transports remains in the relevant LAN/provisioning findings. None is claimed fixed by this unit.

### Pre-commit verification evidence

| Command/check | Exact result |
| --- | --- |
| Focused `KitLifecycleTest` JVM suite during implementation | Passed after the late-connect regression test first exposed raw connection setup proceeding after terminal stop; the lifecycle check was moved directly after dial ownership transfer and the suite then passed |
| Six focused lifecycle tests, forced three times | All three runs passed with deterministic gates and one precise outcome per race |
| `./gradlew :p2p-core:jvmTest :p2p-core:iosSimulatorArm64Test :p2p-core:compileAndroidMain` | `BUILD SUCCESSFUL`; JVM 342 tests, iOS Simulator ARM64 323 tests, zero failures/errors/skips; Android common/main compilation passed |
| `./gradlew check` | Reached the exact registered independent baselines: `FileTransferFlowTest.cancelMidStreamPropagatesToReceiver` expected `Cancelled` but observed `Completed`; Android lint reported the registered `CoarseFineLocation` error plus three registered warnings. No CORE-01 test failed |
| `./gradlew :p2p-transport-lan:iosSimulatorArm64Test` | Reproduced the registered Apple LAN baseline exactly: 40 tests, two lifecycle timeouts, one intentionally skipped diagnostic |
| `scripts/check-publish-artifacts.sh` | Passed all 15 publication rows |
| `scripts/check-published-consumers.sh` | Passed isolated JVM, Android, KMP, and iOS consumer builds |
| `./gradlew :p2p-transport-lan:assembleP2pKitSharedReleaseXCFramework` | `BUILD SUCCESSFUL`; release XCFramework assembled |
| `xcodegen generate` | Passed |
| Isolated Swift sample `xcodebuild` using `build/DerivedDataCore01` | Exit 0 with code signing disabled for generic iOS Simulator. A preceding reuse of the default build database reported a lock after an ambiguous verbose invocation; isolation proved this was concurrent DerivedData ownership, not a source failure |
| `git diff --check` | Passed |

The first attempted Android task name, `compileDebugKotlinAndroid`, does not exist in this multiplatform module; this was a command-selection diagnostic, not a product failure. It was corrected to the module's authoritative `compileAndroidMain` task, which passed. Existing `ExperimentalCoroutinesApi` warnings in unrelated core tests are registered under BUILD-14; the new lifecycle test file introduced no warning.

Compatibility and remaining risk:

- Calls linearized before terminal generation invalidation may succeed and are then included in teardown; calls losing the generation fail with the existing post-stop `IllegalStateException` contract. There is no automatic retry or fallback.
- Incoming session pressure now has a precise bounded refusal at publication capacity rather than allowing setup to block the terminal lifecycle commit. The refused session is removed from the store and closed.
- Full repository verification is not green because the independently registered FILE-04/SAMPLE-17/BUILD-08 and Apple LAN failures remain. They do not intersect the lifecycle paths or invalidate the focused committed-state evidence.

Committed-state evidence for `a4e0bb0`: `git show --check` passed; the focused JVM `KitLifecycleTest` suite passed under `--rerun-tasks`; the complete iOS Simulator ARM64 suite and Android main compilation passed under `--rerun-tasks`. The forced full JVM suite reproduced only FILE-04 (`cancelMidStreamPropagatesToReceiver`, 342 tests/1 failure), exactly matching the registered baseline and leaving all CORE-01 tests green.

## Active batch: ID-STORE-01 — legacy PeerId persistence

| Item | Concise plan |
| --- | --- |
| Findings/gap | CORE-18, CORE-19, CORE-20, CORE-21, CORE-29, CORE-T11 |
| Root causes | Lossy AppId sanitizers are storage identities; first creation is read/generate/write without process or cross-process exclusion; fixed temp names/direct target fallback are crash-unsafe; failed writes are not memoized; JVM root selection accepts blank/unusable properties. |
| Implementation | Use a domain-separated full SHA-256 AppId namespace while retaining legacy read migration. Serialize JVM/Android commits with a process lock plus file lock, reread under lock, write via JVM fsync+atomic move and Android `AtomicFile`, and memoize every returned ID. On iOS store a hash-keyed dictionary in the existing sanitized NSUserDefaults bucket under a process/POSIX file lock, preserving current test/reset and rollback behavior. Validate JVM home/temp roots and never select `.` implicitly. |
| Main files | Common storage-key helper; JVM/Android `FilePeerIdStorage`; iOS `NSUserDefaultsPeerIdStorage`; JVM factory; JVM/iOS tests; affected Apple LAN test cleanup only if the persisted representation requires it. |
| Tests | Sanitizer collisions and long-prefix collisions; repeated same-instance calls after persistence failure; concurrent threads and child JVM processes; legacy migration/rollback; corrupt-record replacement without partial target; JVM property fallback; iOS hash-bucket collision/migration/concurrency with deterministic fakes where OS behavior is not injectable. |
| Compatibility/migration | Public API unchanged. Existing JVM/Android paths and iOS string values are read-only migration inputs and are not deleted, allowing rollback. Updated processes coordinate with each other; an concurrently running pre-update process cannot honor the new lock/record format and is outside the compatibility guarantee. Explicit plaintext mode remains deprecated. |
| Acceptance | Distinct AppIds never share writable storage; one durable winner is returned to concurrent creators; target writes are atomic; an instance never changes its returned ID after a write failure; no working-directory fallback; JVM/iOS tests and Android/iOS compilation pass with no new warnings. |

Implementation result: full UTF-16 AppId hashing (including malformed-surrogate distinction), legacy read-only migration, JVM/Android process+file locks, JVM unique fsynced temp/atomic move, Android `AtomicFile`, iOS hash-bucket records under NSLock/POSIX lock, instance memoization, and explicit JVM root validation are complete. Public API is unchanged.

Verification: focused JVM storage and kit-persistence suites pass; contention passed in three executions including 16 threads and four child JVM processes; complete JVM core is 351/351 green; isolated iOS storage tests pass; Android main and affected Apple LAN tests compile. The complete iOS run executed 326 tests and reproduced only the registered `SessionReconnectRotationTest` timeout; no identity test failed. Existing BUILD-14 warnings are unchanged.

Committed/pushed evidence: `ee69d09` is on `origin/remediation/full-register-2026-07`; forced committed-state JVM core (351 tests), isolated iOS identity tests, Android main compilation, and affected Apple LAN test compilation all pass.

## Completed batch: CORE-SESSION-01 — session ownership and terminal state

| Item | Concise plan |
| --- | --- |
| Findings/gaps | CORE-03, CORE-08, CORE-09, CORE-10, CORE-13, CORE-23; CORE-T02, CORE-T07, CORE-T08 |
| Root causes | Raw/session ownership is not represented through every cancellable connect boundary; registration diagnostics read a concurrently mutated map; terminal cleanup does not terminate the session-wide job; stop relies on asynchronous watchers; path state is an event rather than retained authority. SEC-01 already moved security and initial HELLO inside one outer deadline, but lacks a focused regression. |
| Implementation | Make connector ownership transactional with non-cancellable close and pending completion; publish an immutable registration map; add atomic store shutdown drain; cancel the session runtime only after terminal resource cleanup; retain versioned path state and apply it to every registration; inject only an internal setup-timeout test value while keeping the production constant. |
| Main files | `SessionManager`, `SessionStore`, `P2pSessionImpl`, `P2pKitImpl`/internal builder timeout threading, focused session/path/handshake tests. |
| Tests | Cancellation during dial return, HELLO/security setup, and registration wait followed by exact successful retry; concurrent registration diagnostics; remote CLOSE/failure job termination; stop with watcher deliberately unable to run; hung initial write/security bounded by the outer deadline; registration racing retained `Unsatisfied`. |
| Compatibility | No public API or wire change. Cancellation remains `CancellationException`; stop empties public state earlier; a session created while the authoritative path is unsatisfied may enter reconnect/failure before `connect()` returns, which is the intended correction. |
| Acceptance | No stale pending slot or unowned raw/session after cancellation; waiters get one exact result; no mutable-map data race; terminal jobs become inactive; stop returns with empty sessions independent of watchers; all setup phases obey one deadline; no session misses retained path loss. |

Implementation result: connector/raw/session ownership is transactional through cancellation; pending cleanup is non-cancellable; uncommitted sessions use forced terminal rollback; diagnostics read an immutable map; terminal cleanup cancels the session runtime last; shutdown atomically drains public/store state; setup uses one outer deadline; network-path authority is retained and applied to every registration. No public API or wire format changed.

Verification: focused JVM suites passed three times; the complete pre-final-hook JVM suite was 358/358 and the final post-dial cancellation test passed on JVM/iOS. The final forced JVM gate reproduced only the registered FILE-04 race; no CORE-SESSION-01 test failed. A later full JVM and full iOS run with the final source both passed. Exact committed-state verification at `82a9b41` found and corrected a replay-zero test-subscription race without changing timeouts; `SessionOwnershipTest` then passed three forced JVM repeats, focused iOS Simulator, and Android compilation. Only registered BUILD-14 warnings were emitted. Commits `68934be` and `82a9b41` are pushed on `remediation/full-register-2026-07`.

## Completed batch: PARSE-01 — bounded protocol parser and validation

Scope: `PROTO-01` through `PROTO-07` and the parser portions of `PT-T01` through `PT-T05`/`PT-T21`. `PROTO-08` is split into `PARSE-META-01` and blocked because removing public metadata or adding a versioned secure-v2 envelope is a product/API/wire decision. The transfer transition portion of `PROTO-04`/`PT-T07` remains assigned to `XFER-01`.

Concise plan:

- Root causes: repeated whole-buffer/tail copies; generic-only payload cap; dispersed structural checks; permissive UTF-8/text validation; trace/log callbacks on the protocol path.
- Implementation: reusable cursor buffer with in-place decode; header-time per-packet caps; one encoder/decoder structural validator; strict bounded text codecs; stable DATA flags/LAST checks; trace isolation; rate-limited peer-controlled warnings.
- Main files: `ProtocolConstants`, `FrameCodec`, `FrameReader`, `DefaultP2pProtocol`, `HelloPayload`, `FileOfferPayload`, `Reassembler`, `FrameTrace`, and their common tests.
- Tests: fragmented/batched linear-work accounting, early header rejection, all packet invariant/cap boundaries, strict malformed UTF-8, outbound text boundaries, throwing trace, bounded logs, and deterministic randomized codec/reader/reassembler streams.
- Compatibility: secure-v2 and explicit legacy-v1 framing remain version-specific with no fallback; unknown packet types remain skippable for forward compatibility. Newly rejected frames were already malformed or exceeded newly documented limits. No public API/wire field is added in this batch.
- Acceptance: no payload-sized allocation before header validation; relocation work is linear in input; every known packet is validated before delivery; malformed text cannot be canonicalized silently; diagnostics cannot fail I/O or grow with attacker frame count; focused common JVM/iOS tests and affected target compiles pass.

Implementation/review result: commits `aa3ac0c` and `6171588` implement the parser/text portion and were reviewed as a 21-file protocol-only batch plus a six-file canonical-text follow-up. The reader buffers only the fixed header before validation, reuses one frame buffer, decodes from an offset window, and never copies an accumulated tail. Packet caps/shape rules are centralized and shared by encoder, direct decoder, and streaming reader. Known text is strict UTF-8 with invalid local Unicode rejected before encoding. Trace/log failures cannot alter protocol I/O, while `CancellationException` is preserved. Equivalent protocol decode/encode sites were searched; no second parser remained unchanged. Public ABI signatures and secure-v2/explicit-legacy framing are unchanged.

Tests added/strengthened: linear relocation and early header rejection, packet-family cap/shape tables, strict UTF-8/local Unicode/control/bidi/path/blank/boundary cases, stable DATA flags/LAST, FILE_DATA empty/total/LAST/post-size rules, throwing trace, bounded malformed/unknown logs, and deterministic randomized 500-frame fragmentation plus randomized reassembly.

Verification:

- Focused protocol JVM suite passed after the initial run exposed and corrected two assertion-message mismatches; no assertion was weakened.
- Final complete affected-module run: JVM `389/389`, iOS Simulator `364/364`; Android main and iOS Arm64 compilation passed.
- Parser/codec/reader/reassembler subset passed three forced JVM repeats.
- Exact committed state at `aa3ac0c`: full JVM `389/389`, focused iOS protocol `134/134`, Android/iOS device compilation passed.
- Exact final tip at `6171588`: full JVM plus focused iOS protocol passed; Android/iOS device compilation passed.
- `checkKotlinAbi` completed with the repository's ABI comparison task skipped by its own configuration; manual/public-diff review found no signature change.
- Repository-wide `./gradlew check --offline` reached and passed core, provisioning, desktop/sample, and KMP work, then failed only the registered unrelated baselines: LAN iOS `40` tests with the same two lifecycle timeouts and one intentional skip, and Android sample lint with the same `CoarseFineLocation` error plus three warnings. No PARSE-01 test failed and no new warning was introduced.

Remaining: `PROTO-04` stays `In Progress` solely for the ACCEPT/REJECT dispatcher transition assigned to XFER-01. `PT-T07` and `PT-T21` stay open for their dispatcher/transfer-transition conjuncts. `PROTO-08` remains separately blocked on the metadata API/wire decision.

`PROTO-08` blocker record: `P2pMessage.metadata` is public but absent from both legacy-v1 and secure-v2 message encoding. Work attempted: confirmed `Chunker` serializes only text/binary bytes and `Reassembler` constructs messages without metadata; existing tests pin the omission. Recommended option: add an authenticated versioned secure-v2 application-message envelope and keep explicit legacy migration mode metadata-free; this changes the secure-v2 message payload contract and needs owner approval. Alternatives: remove/deprecate metadata (source/API compatibility cost), or explicitly document it as local-only (preserves the surprising contract and does not resolve the finding). Required later reply: `Approve PARSE-META-01 envelope` or an explicitly chosen alternative. This decision unblocks `PROTO-08` and its envelope/compatibility tests only; it does not block XFER-01 or other local batches.

`XFER-OFFER-API-01` blocker (`FILE-05`, receiver conjunct of `FILE-06`, `PT-T12`, `PT-T13`): the public surface is `SharedFlow<P2pFileOffer>`. Replay can retain offers while no subscriber exists, but cannot selectively remove terminal entries; rebuilding replay broadcasts duplicates to existing collectors. A custom implementation cannot fulfill kotlinx.coroutines' `onSubscription` contract through public APIs. Attempted state-backed implementation reproduced that contract failure deterministically and was removed. Recommended option: add an authoritative `StateFlow<List<P2pFileOffer>> pendingFileOffers`, deprecate the lossy event flow, and migrate samples; this is an additive interface/API change but affects third-party `P2pSession` implementers and ABI. Alternatives: change `incomingFiles` directly to `StateFlow<List<...>>` (cleaner, breaking source/API), or accept stale/duplicate replay (does not resolve the finding). Exact reply: `Approve XFER-OFFER-API-01 pendingFileOffers`. This unblocks only the listed offer-delivery rows and dependent samples.

`XFER-ERROR-API-01` blocker (`FILE-11`): causes are now retained on unexpected transport/source/sink failures, but using `ConnectionFailed` for local I/O and session-closing `ProtocolError` for isolated transfer violations remains misleading. Recommended option: add public `FileTransferIoFailed` and `FileTransferProtocolError` `P2pError` subtypes with causes. This is binary-additive but can break exhaustive source `when` expressions over the sealed hierarchy. Alternatives: make `P2pError` non-sealed (larger source contract change), or retain generic errors (does not resolve the finding). Exact reply: `Approve XFER-ERROR-API-01 typed errors`. This unblocks `FILE-11` and its external-consumer compatibility tests only.

### XFER-01 concise implementation record

Commit `68c579f` is pushed. It verifies `PROTO-04` and `FILE-01/02/03/07/08/09/10/12/14`; `FILE-15` is implemented pending the explicitly external Android-provider instrumentation conjunct. Root change: dispatcher maps now own only phase/timer references; each transfer serializes state, progress, and source/sink ownership independently. Acceptance has bounded transactional compensation, accepted transfers have progress-sensitive idle plus overall deadlines, timeout roles are ordered, chunk arithmetic is bounded, IDs cannot overwrite, and platform helpers measure the opened resource. Public constructor/wire behavior is unchanged; the only observable runtime changes are deterministic timeout/cancellation/error cleanup and stricter invalid-configuration rejection.

Changed components: `FileTransferDispatcher`, incoming/outgoing handles, streaming sender/receiver, `FileTransferConfig`, Android/JVM helpers, common/JVM regression tests. Acceptance: no user I/O under the dispatcher map lock; cancellation preserves `CancellationException`; terminal state freezes progress and clears references; conforming unanswered offers have one exact sender state. Focused concurrency tests passed three forced JVM repeats; focused JVM/iOS tests and Android/iOS-device compilation passed again from the pushed commit. The complete JVM suite passed 401/401; a complete iOS run exposed three registered lifecycle/reconnect flakes outside this batch, and all three passed isolated forced reruns. Remaining local decision-independent risk: FILE-04 durability acknowledgement still permits the known completion/cancel race and is not claimed here.

### PEER-CTRL-01 concise implementation record

Decision-free scope: `CORE-02/04/05/14`, `CORE-T03..06`, plus safe portions of `CORE-17/28`. Discovery now retains one contribution per transport instance and merges routes/capabilities until the final source is lost or stale. Session registration records direction and never applies simultaneous-open arbitration to same-direction duplicates. Application messages use a count/byte-bounded delivery queue separate from protocol controls; overflow produces one terminal failure instead of silent loss. Keepalive deadlines use platform monotonic time and fire at the exact boundary. Binary messages and registry inputs are defensively snapshotted; device/manual-host/same-factory validation is early and deterministic. Complete core verification is 411/411 JVM and 386/386 iOS, with Android/iOS-device compilation green; commit pending.

`PEER-STATE-API-01` blocker (`CORE-15`): the current public surface exposes only one `P2pKit.state`, so independent advertising and discovery failures cannot be represented without either changing that contract or adding feature state. Attempted local boundary analysis confirmed that internal error flags alone would prevent incorrect clearing but would still hide which feature failed and would not satisfy the finding. Recommended option: add authoritative `StateFlow<FeatureState>` properties for advertising and discovery, reserve `P2pState` for core lifecycle, and provide default interface accessors during migration. Alternative: replace `P2pState` with one composite state (cleaner but broadly breaking); retaining one global failure is not a resolution. Exact later reply: `Approve PEER-STATE-API-01 feature states`.

`IMMUTABLE-MODEL-API-01` blocker (`CORE-17`): Kotlin read-only `Map/List/Set` values in public data classes can still expose caller backing storage or be cast to mutable implementations. This batch safely fixes `P2pMessage.Binary` and registry ownership, but cast-proof public immutability for `Peer`, `InternalPeer`, `TransportHint`, provisioning values, and `P2pMessage.Text` changes data-class/reflection/copy semantics or collection property types. Recommended option: snapshot-backed value classes that preserve constructors/getters/equality and manually preserve practical `copy`/component source use, with an ABI consumer suite. Alternatives: persistent immutable collection types (stronger type contract, larger API/dependency break) or documentation-only read-only collections (does not resolve the finding). Exact later reply: `Approve IMMUTABLE-MODEL-API-01 snapshot values`.

`TRANSPORT-FACTORY-API-01` blocker (`CORE-27` and duplicate-kind conjunct of `CORE-28`): `TransportPair.data` is non-null and `TransportFactory` declares no capabilities before `build()`. Making data nullable enables discovery-only transports, while detecting duplicate kinds only after build can leak resources because construction is non-suspending but transport close is suspending. Recommended option: add required pre-build data/discovery capability descriptors and make pair data nullable with an at-least-one-path invariant. Alternatives: a new parallel v2 factory interface with an adapter migration period (more maintenance, softer compatibility) or post-build validation (resource-ownership defect, rejected). Exact later reply: `Approve TRANSPORT-FACTORY-API-01 declared capabilities`.

## Execution log

| Date | Unit | Action | Result |
| --- | --- | --- | --- |
| 2026-07-17 | GOV-01 | Created isolated remediation branch and reconciled source register | Branch `remediation/full-register-2026-07`; 150 unique finding IDs, 54 unique gap rows |
| 2026-07-17 | SEC-01 | Read referenced implementation/tests and reproduced CORE-06/CORE-07 architecture | Confirmed; no source changes; blocked at mandated breaking security/protocol decision |
| 2026-07-17 | GOV-01/SEC-01 | Independent tracker and security-plan reviews, correction pass, mechanical revalidation | Phase allocation is exactly 150/54; tables valid; all security-review corrections addressed |
| 2026-07-17 | SEC-01 | Owner approved secure protocol v2 and storage A; protocol, provider, and platform-store reviews completed | Decision blocker cleared; exact contract frozen; production implementation authorized |
| 2026-07-18 | SEC-01 | Implemented authenticated secure v2, Storage A, migration/authorization/manual-pin/LAN separation, platform providers, samples, and regression suites | Local targeted, full core JVM/iOS, LAN JVM, provisioning, sample, XCFramework/Swift, and publication checks pass |
| 2026-07-18 | SEC-01/full gate | Ran `./gradlew check` after final ownership correction | SEC paths pass; gate remains red only for the registered Android lint error and two Apple LAN lifecycle timeouts; external security/device/network certification still required |
| 2026-07-18 | SEC-01/source control | Reviewed, committed, reran core JVM/iOS from committed state, and pushed | Implementation commit `b79c9ba`; post-commit 336 JVM + 317 iOS tests pass; pushed branch tracks origin |
| 2026-07-18 | REL-REMOTE-01 | Inspected local publication configuration and current official Central paths | BUILD-02 confirmed; unit blocked only on namespace/workflow/release policy and later CI credentials; independent work continues |
| 2026-07-18 | REL-ABI-01 | Inspected all public ABI imports plus generated POM/module variants and froze the implementation/test plan | BUILD-01 reproduced in core, LAN, and both provisioning sidecars; no source edit made before analysis completion |
| 2026-07-18 | REL-ABI-01 | Corrected API scopes, removed desktop's runtime LAN edge, added isolated consumer matrix, reviewed metadata, and ran all local gates | BUILD-01/CORE-T13 implemented; exact consumer and artifact gates pass; full-gate baselines unchanged |
| 2026-07-18 | REL-ABI-01/source control | Created focused commit and reran the isolated consumer gate from committed state | Commit `8f15d75`; clean committed diff; BUILD-01/CORE-T13 verified; JVM/Android/KMP/iOS consumer matrix passes |
| 2026-07-18 | LIF-GEN-01 | Reviewed current lifecycle/session code and deterministic interleavings; froze focused plan before source changes | CORE-01 confirmed in late advertise/discover/connect/observer commits; CORE-T01 in progress; CORE-11 explicitly remains separate |
| 2026-07-18 | LIF-GEN-01 | Implemented terminal generation commits, stale-resource compensation, atomic session registration, and six deterministic races; reviewed every equivalent path | CORE-01/CORE-T01 implemented; full core JVM/iOS and Android compilation green; independent repository baselines unchanged |
| 2026-07-18 | LIF-GEN-01/source control | Created `a4e0bb0` and reran focused JVM plus complete iOS Simulator/Android checks from committed state | CORE-01/CORE-T01 verified; forced full JVM reproduced only the registered FILE-04 failure |
| 2026-07-18 | ID-STORE-01 | Implemented collision-safe namespaces, transactional cross-process creation, atomic persistence, failure memoization, rollback migration, and JVM root validation | CORE-18/19/20/21/29 and CORE-T11 implemented; JVM 351/351 green; iOS focused green; Android/Apple compile green |
| 2026-07-18 | ID-STORE-01/source control | Committed, forced affected checks from committed state, and pushed `ee69d09` | CORE-18/19/20/21/29 and CORE-T11 verified on `remediation/full-register-2026-07` |
| 2026-07-18 | CORE-SESSION-01 | Implemented transactional connect ownership, immutable store publication, terminal runtime completion, atomic shutdown drain, full setup deadline, and retained path authority | CORE-03/08/09/10/13/23 and CORE-T02/T07/T08 verified locally |
| 2026-07-18 | CORE-SESSION-01/verification | Ran focused JVM/iOS, three concurrency repeats, complete core JVM/iOS, and cross-platform compilation; reviewed the full batch diff | Batch tests green; complete pre-final-hook JVM 358/358 and iOS 334/334; final hook test 4/4 per platform; forced JVM reproduced only FILE-04 |
| 2026-07-18 | CORE-SESSION-01/committed state | Exact verification exposed a replay-zero test collector race; replaced eager `async` scheduling with `CoroutineStart.UNDISPATCHED` and did not alter timeouts/retries | `SessionOwnershipTest` passed three forced JVM repeats, focused iOS, and Android compile at `82a9b41`; both commits pushed |
| 2026-07-18 | PARSE-01 | Replaced quadratic reader, centralized per-packet caps/shape, enforced strict canonical text, isolated diagnostics, and added deterministic properties | `PROTO-01/02/03/05/06/07`, `PT-T01..05` verified; parser portions of `PROTO-04`, `PT-T07`, `PT-T21` committed |
| 2026-07-18 | PARSE-01/verification | Ran focused/full JVM and iOS, Android/iOS compiles, three forced repeats, ABI task, exact committed-state worktrees, and repository `check` | Core JVM 389/389 and iOS 364/364; repository gate failed only registered LAN iOS and Android lint baselines |
| 2026-07-18 | XFER-01 | Refactored transfer ownership, acceptance compensation, deadlines, arithmetic, progress, collision handling, and platform snapshots; isolated two API decisions | Complete core JVM 401/401 green; focused transfer iOS green; complete iOS run exposed three unrelated registered lifecycle/reconnect flakes and each passed an isolated forced rerun; Android/iOS device compilation green |
| 2026-07-18 | XFER-01/determinism | Added gated accept/sink/write, exact virtual-time, 64-slot, transition, collision and retention regressions | Seven timing/concurrency tests passed three forced JVM repeats; updated focused iOS suite passes |
| 2026-07-18 | XFER-01/source control | Reviewed, committed, pushed, then reran focused JVM/iOS and Android/iOS-device compilation | `68c579f` pushed; covered findings/gaps marked Verified except the documented API/external-instrumentation boundaries |
| 2026-07-18 | PEER-CTRL-01 | Implemented per-transport peer aggregation, direction-aware duplicate handling, bounded application delivery, monotonic keepalive, and safe validation/snapshot portions | Complete core JVM 411/411 and iOS 386/386 green; Android/iOS-device compile green; five concurrency/timing tests pass three forced JVM repeats; three public API/model decisions isolated |
