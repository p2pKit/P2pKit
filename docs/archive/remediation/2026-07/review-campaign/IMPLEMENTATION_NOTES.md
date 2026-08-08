# Implementation-phase discoveries (2026-07 remediation, groups A–L)

Running log of issues surfaced *during* implementation that are not (yet) rows
in the accepted findings register. Neutral defensive-QA wording (BRIEF rule 7).
Surface these to the user at wrap-up; do not act unprompted.

## Group A (RBS-1, commit 7e40191)
- **JmDNS goodbye removals carry no TXT data** (JmDNS 3.6.3, observed
  empirically in the P1-25 loopback test): `serviceRemoved` for a real
  goodbye (TTL=0) delivers an `info` without TXT properties, so the
  JVM/Android removed→`PeerEvent.Lost` path never fires for real goodbyes;
  peer disappearance relies on PeerRegistry staleness eviction. Pre-existing
  (old code also returned early). Adjacent to DSC-1 / user decision #14 —
  fold into that decision. Documented in JvmDiscoveryRecordValidationTest KDoc.

## Group C (P1 pinning tests, commit efde8e1)
- **P1-18 divergence:** `HelloPayload.decode` applies no length bound to the
  `platform` or per-transport strings (coverage row expected them among the
  guards); over-limit values are currently accepted. Pinned as actual
  behavior with KDoc divergence note. Candidate register addendum (input
  validation, Low/Medium).
- **P1-27 divergence:** a `startLocalNetwork` attempted after parent-job
  cancellation is accepted (returns `Started`) rather than refused, and the
  reservation sits outside parent-job completion cleanup (explicit `close()`
  only). Pinned as actual behavior with KDoc divergence note. Candidate
  register addendum (lifecycle correctness).
- **P1-32 not deliverable in Group C as planned:** its coverage row requires
  the SMP-1 rider (new shared helper in sample main source + test wiring in a
  sample module that has no test source set) — conflicts with Group C's
  tests-only scope. Orchestrator disposition: **moved to Group I** (test
  seams), where the minimal sample-main helper + sample-module test wiring is
  in scope (samples are unpublished harnesses; not a public-API change).
- FIL-15 latent flake (`FileTransferFlowTest.cancelMidStreamPropagatesToReceiver`)
  fired once in the Group C allTests first run; passed standalone and on
  re-run. Already catalogued in the register — no action.

## Group D (SES-1, commit 13fd3de)
- **SessionReconnectRotationTest.reconnectFallsBackToOriginalWhenRegistryHasNoEntry
  lacked the Reconnecting synchronization its two sibling tests have** and
  implicitly relied on the pre-fix raw-state observer classifying a break
  within one dispatch; with the SES-1 classification-deferral it could
  observe the pre-break `Connected` and read `connectCalls` too early
  (fired once on iosSimulatorArm64). Fixed in the Group D commit by adding
  the same `first { Reconnecting }` wait the siblings use — assertion
  strengthened, nothing relaxed.
- **One-off JVM timeout in the same test's registry SEED wait**
  (`alice.peers.first { any }` after `PeerEvent.Found`, 3.5 s bound,
  SessionReconnectRotationTest.kt:227) in the first Group D jvmTest run;
  passed standalone and on every re-run. Outside Group D's touched paths
  (PeerRegistry propagation under parallel-suite CPU saturation — the same
  load sensitivity the test's own KDoc documents). Candidate latent-flake
  note alongside FIL-15; no action taken.
- FIL-15 did not fire in any Group D gate run.

## Group F (CON-3 + ARCH-4 rider, commit eb93478)
- No new issues discovered during implementation.
- Neither known latent flake fired in any Group F gate run (FIL-15
  cancelMidStreamPropagatesToReceiver; SessionReconnectRotationTest
  registry-seed wait) — jvmTest, allTests, and lan jvmTest all green
  first run.
- Post-failure inbound behavior is the plan's minimal RC scope as specified:
  log + inbound down on that transport until a later start()/rebind
  re-serves its accept loop; the bounded re-collect remains the plan's
  tracked follow-up (not new).

## Group G (ARCH-1 + ARCH-2)
- **`ensureStarted` re-checks `stopped` only after the bind loop, not after
  `pathObserver.start()`** (P2pKitImpl.kt): if an observer `start()` is parked
  while `stop()` takes its lock-less mutex-starvation fallback, the late
  `ensureStarted` that later resumes normally would latch
  `startResult = success` and publish `Running` over the terminal `Stopped`
  (the AUDIT-2026-06 re-check covers only a hung `transport.start()`). Narrow
  trigger (hung observer start + concurrent stop + observer eventually
  returning); the new P1-09 test avoids it by cancelling the parked starter,
  so it remains an open lifecycle-correctness gap. Candidate register addendum
  (Low/Medium); minimal fix is a second `stopped` re-check before the success
  latch.
- FIL-15 latent flake (`FileTransferFlowTest.cancelMidStreamPropagatesToReceiver`)
  fired once in the first Group G jvmTest gate run; passed on re-run
  (`--rerun-tasks`). Already catalogued — no action. The
  SessionReconnectRotationTest registry-seed wait did not fire; allTests green
  first run.

## Group H (FIL-1, FIL-2 + riders FIL-4/FIL-6/FIL-11)
- **`sendFile` ownership-on-throw is inconsistent for pre-handle validation
  refusals**: the top-of-function closed check, `PayloadTooLarge`, and the
  negative-`sizeBytes` `require` all throw with the caller's `RawSource` left
  open, while the offer-write-failure path and the new under-lock closed
  refusal (FIL-6) close it via the handle's terminal transition. The public
  KDoc ties ownership to "the returned transfer", so the pre-handle refusals
  are arguably caller-owned, but the contract is unstated. Candidate register
  addendum (contract clarification; adjacent to the API-4 / FIL-1 family) —
  deliberately not changed in Group H to stay within the accepted scope.
- Neither known latent flake fired in any Group H gate run (FIL-15
  `cancelMidStreamPropagatesToReceiver`; SessionReconnectRotationTest
  registry-seed wait) — jvmTest and allTests green first run with the fixes
  in place. (A deliberate negative-verification run against the pre-fix
  sources showed 5 of the new tests failing, confirming they bite.)

## Group I (P1-14, P1-15, P1-32 + riders DSC-3/DSC-13)
- **P1-14 seam disposition:** the coverage row's "androidHostTest or jvm-style
  unit" fork was resolved to the jvm-style unit — enabling androidHostTest in
  `:p2p-transport-lan` needs its build file (`withHostTest`), which is
  off-limits (published module). The seam is therefore the §2.2 extraction:
  the Android JmDNS lifecycle/rebind state machine moved verbatim into
  commonMain `JmdnsLifecycleCoordinator` behind a `JmdnsLifecycleOps`
  interface; `AndroidLanDiscoveryTransport` supplies the JmDNS/Android
  specifics. `Dispatchers.IO` is not in the coroutines common API, so the
  blocking-call context is a constructor injection (`ioContext`); the
  transport passes `Dispatchers.IO`, preserving the pre-extraction hops.
- **Sample accept-failure parity divergence (pre-existing, samples only),**
  observed while wiring SMP-1: on `offer.accept` failure the Android sample
  deletes the just-created destination file, while the CLI and (now also)
  desktop-ui samples close the stream but leave the zero-byte claimed file on
  disk, so the next same-named offer lands on "<name> (1)". Cosmetic;
  candidate register addendum (sample-parity, Low). Not changed in Group I.
- **Pre-existing compiler warning surfaced during the port** (androidMain):
  `candidates.joinToString(",") { it.hostAddress }` in `serviceResolved`
  infers `String?` where `CharSequence` is expected (hostAddress is nullable).
  Identical expression existed before Group I (and exists in the JVM twin);
  warning only, no behavior change made.
- Neither known latent flake fired in any Group I gate run (FIL-15
  `cancelMidStreamPropagatesToReceiver`; SessionReconnectRotationTest
  registry-seed wait) — core jvmTest, lan jvmTest, assemble, and the new
  `:p2p-sample-desktop-ui:test` all green (one iteration fixed a new
  coordinator test's own too-strict `== 2` wait racing the 1 ms retry
  backoff — test-side only, condition widened to `>= 2` with a comment).

## Group J (BLD-2, P1-29)
- **BLD-2 residual settled empirically (pre-fix run):** a `publishToMavenLocal`
  into a throwaway repo (`-Dmaven.repo.local`) on df2dbea showed KGP does NOT
  auto-attach javadoc jars — only the desktop sidecar (via `withJavadocJar()`)
  had one; all 14 KMP publications lacked it. The release-doc claim at
  STABILIZATION_AND_RELEASE.md:76-77 was wrong and is now corrected. Evidence:
  impl-logs/groupJ-publishToMavenLocal-before.log.
- **This dev box signs every publish:** `signingInMemoryKey` is set in the
  user's global `~/.gradle/gradle.properties`, so `Sign*` tasks actively run
  here (`.asc` produced) and the doc/C3 leg "`sign*` SKIPPED without a key"
  cannot be exercised on this machine without altering the user's global
  Gradle config. Keyless behavior verified by inspection only (the signing
  conditional in the root build is untouched by the Group J change); the
  with-key path — the stricter one for this change, since a shared javadoc
  jar would have collided on `.asc` outputs across per-publication Sign
  tasks — was verified empirically (distinct jar + `.asc` per publication).
- **Pre-existing artifactId doubling recorded, not changed:** the provisioning
  sidecar's Android target publishes as
  `p2p-network-provisioning-android-android` (KMP `<module>-<target>` naming).
  Cosmetic/naming observation; the P1-29 script pins it explicitly, so a
  future rename would fail the gate loudly rather than silently.
- Neither known latent flake fired in any Group J gate run (FIL-15
  `cancelMidStreamPropagatesToReceiver`; SessionReconnectRotationTest
  registry-seed wait) — core jvmTest, lan jvmTest, assemble, and the P1-29
  script gate all green first run.

## Group K (IOSB-3 + riders IOSB-1/IOSB-2, P1-30, P1-31)
- **P1-31 empirical nuance vs the coverage-row wording:** the row anticipated
  `simctl get_app_container` resolving under the invoking checkout's
  DerivedData; empirically `xcrun simctl install` COPIES the bundle into the
  simulator's app container (`~/Library/Developer/CoreSimulator/Devices/...`),
  so a path-prefix check cannot hold for this install route (it holds only for
  Xcode's own install-by-reference). The in-script check was therefore
  implemented as SHA-256 equality of the built vs installed executable —
  stronger than the path check and valid for both install routes.
  INTERNAL_TESTING.md §K.3 documents the hash-based manual recipe.
- **check-xcframework.sh stamp-lag branches self-heal under in-place
  tampering:** overwriting BUILD_COMMIT.txt (which lives inside the assemble
  task's output directory) marks the Gradle task out-of-date, so the script's
  step-1 Gradle run re-executes the assembly and re-stamps with HEAD — the
  tampered-stamp scenarios (df2dbea, 870bf10, "unknown") all converged back to
  "fresh" instead of exercising the lag/fail branches (observed in
  impl-logs/groupK-check-xcframework-scenarios.log). This is desirable
  behavior, not a defect. The genuine stamp-lag path (HEAD moves while
  outputs stay put) requires history mutation to simulate and remains covered
  by the P2 stamp-lag matrix row (coverage plan :202) — unchanged here; the
  earlier-round stamp-lag semantics in the script were not modified.
- **IOSB-2 verified synthetically:** no parenthesized stock simulator name is
  installed on this box, so the fix was verified against a fabricated
  device-list line ("iPad Pro (11-inch)": old unescaped ERE fails to resolve
  the UDID; new escaped ERE resolves it) plus real-name checks ("iPhone 17"
  still resolves exactly, without over-matching "iPhone 17 Pro").
- Neither known latent flake fired in any Group K gate run (FIL-15
  `cancelMidStreamPropagatesToReceiver`; SessionReconnectRotationTest
  registry-seed wait) — core jvmTest, lan jvmTest, assemble, the XCFramework
  assembly, and the full `:iosApp:runIosSimulator` pass all green first run.

## Group L

- The plan's Group L rider "adopt the annotate-on-fix process rule as a
  CLAUDE.md convention" was not applied to CLAUDE.md (excluded by the
  implementation task's strict boundaries — CLAUDE.md untouchable; it is also
  open decision #2). The rule is recorded instead as the maintenance sentence
  in the new annotation-pass header note inside AUDIT_REPORT_2026-06.md;
  porting it to CLAUDE.md remains a one-line follow-up once decision #2 lands.
- Provenance nuance found while verifying DOCB-1 claims: the 30 s write
  watchdog (`WRITE_TIMEOUT_MILLIS`) was introduced @ 47fe586 and hardened
  @ f4dd3a9 — the findings/plan rows cite only f4dd3a9. The annotation in
  AUDIT_REPORT_2026-06.md records both commits; no doc change needed in the
  2026-07 deliverables (out of Group L scope).

## Group M1 (TST-9 + F6, P1-03; decision #15a)

- No latent store-invariant violations surfaced: all 13 kit-level behavioral
  suites pass under `strictInvariants = true` on every target (jvm +
  iosSimulatorArm64), so no suite needed to stay on the production default.
- Known latent flake fired once in the first `:p2p-core:allTests` gate run:
  `SessionReconnectRotationTest.reconnectUsesRefreshedHintsAfterPeerRegistryUpdate`
  [iosSimulatorArm64] timed out (the registry-seed wait shape); clean pass on
  the immediate re-run with strict mode active. Not masked, no test changed.
- Mechanism note: the meta-test's private stubs are named `KitStubSession` /
  `KitFactoryFor` because file-private top-level classes in the same package
  (`StubSession` in SessionStoreInvariantTest.kt, `FactoryFor` in
  SessionFlowTest.kt) collide at resolution when duplicated by name.
- No new codebase issues discovered.

## Group M2 (API-2, P1-05; decision #12a)
- **Cause preservation without a signature change:** the spec-locked
  `ConnectionFailed(val reason: String)` data-class shape (constructor,
  `copy`, `equals`/`hashCode`, destructuring) is untouched; the original
  exception rides in an `internal var underlying` backing an
  `override val cause` getter. Consequence documented in KDoc: `copy()` does
  not carry the cause.
- **Negative-`sizeBytes` refusal shape changed by the decision's letter:**
  decision #12a passes only `CancellationException` and `P2pError` through,
  so the `require(sizeBytes >= 0)` argument refusal in `sendFile` now
  surfaces as `ConnectionFailed` wrapping the underlying
  `IllegalArgumentException` (pinned by test). Noted in case the register
  prefers a distinct argument-misuse shape (`Errors.kt`'s header reserves
  plain ISE/UOE for misuse but is silent on IAE). Candidate register
  addendum.
- **sendFile ownership-on-throw documented as-is (no pre-handle alignment):**
  per the decision-#12 fold-in note, the rule is stated in
  `P2pSession.sendFile` KDoc: refusals before internal registration leave the
  source open and caller-owned (not-Connected pre-check, negative size,
  `PayloadTooLarge`, dispatcher already shut down); throws at/after
  registration close it via the FIL-1 close-once terminal transition. The two
  concurrent-close refusal shapes (just before vs. just after registration)
  surface as the same `ConnectionFailed` message, so the KDoc advises
  treating the source as unusable after any throw; a caller-distinguishable
  shape would need a message/API change. Candidate register addendum
  (adjacent to the Group H note above).
- **Dispatcher's FILE_OFFER wrap now attaches the cause** (it pre-types the
  sendFile boundary's transport failure, and the boundary passes typed
  errors through as-is). Parallel internal wrap sites that also pre-type
  errors reaching other public surfaces (FILE_ACCEPT write in
  `P2pFileOffer.accept`, receive-side finalize wraps, `SessionManager`'s
  connect/handshake wraps at :216/:442) still drop the cause — out of M2
  scope, candidate follow-up rider.
- **Spec untouched:** the plan's M2 entry lists no `P2pKit-Spec.md` line, so
  §17/§7.3 were left alone; the spec's send/sendFile prose does not yet
  describe the cause-preservation rule the code KDoc now states. Natural
  doc rider for a future Group L-style refresh.
- **Gate + verification:** all four gates green first run; neither known
  latent flake fired (FIL-15 `cancelMidStreamPropagatesToReceiver`;
  SessionReconnectRotationTest waits). Negative verification against the
  pre-fix sources (boundary + dispatcher reverted, `Errors.kt` kept for
  compile): 6 of the 11 new SendErrorContractTest tests fail, confirming
  they bite; the other 5 are pass-through pins that hold on both sides by
  design (`impl-logs/groupM2-negative-verification.log`).

## Group M3 (DSC-1, P1-13; decision #14a)
- **Decision-record wording vs. implementation, reconciled:** decision #14a's
  option text says "`list()`-free"; the accepted work order's operative
  parenthetical specifies "`list()` of already-resolved services / cached
  ServiceInfo — NOT a network-level re-query loop", which is what landed
  (same short 200 ms snapshot `refresh()` uses; B:317 untouched; no
  `requestServiceInfo` force re-query on the heartbeat path). Mechanism
  nuance worth recording: the FIRST heartbeat tick per JmDNS handle lazily
  creates JmDNS's per-type ServiceCollector, whose listener registration
  triggers one bounded ServiceResolver burst (3 spaced PTR queries) — a
  one-time cost per handle lifetime, strictly less multicast than a single
  `refresh()` rotation; steady-state ticks read the in-process cache only.
- **Silent (non-goodbye) departure visibility is now cache-TTL-bound:** a
  peer that vanishes without a goodbye keeps its JmDNS cache entries until
  record TTL/expiry handling prunes them, so the heartbeat keeps re-emitting
  it during that window and `kit.peers` shows it beyond the old 15 s horizon.
  This is inherent to decision #14a (heartbeat + eviction as a pair), matches
  the iOS daemon-backed browse semantics, and clean stops/goodbyes still age
  out in ~15-17 s (pinned by the new loopback test). Session-level connect
  failures remain the liveness signal for such peers. Neutral observation
  for the register, not acted on.
- **Gate + verification:** core jvmTest, lan jvmTest, and assemble green
  first run; neither known latent flake fired (FIL-15
  `cancelMidStreamPropagatesToReceiver`; SessionReconnectRotationTest
  waits). The plan's parity-sanity `iosSimulatorArm64Test` gate completed
  with exactly the two catalogued known-flaky simulator churn failures
  (`IosLanLifecycleTest.peerLostEventFiresWhenPeerStops`,
  `advertiseStopRestartProducesObservablePeerChurn` — NWBrowser removed-result
  limitation; iOS sources untouched by M3), 35/37 passing, not masked.
  Negative verification: with only the JVM `startHeartbeatLocked()` call
  disabled, the new kit-level idle test fails at the t=20 s mark exactly as
  the pre-fix defect predicts (`impl-logs/groupM3-negative-verification.log`).

## Group M3 — orchestrator addendum (post-verification)
- **Unattributed one-off full-suite failure** on the orchestrator's first
  independent `:p2p-transport-lan:jvmTest` re-run after b064622 (BUILD FAILED,
  2m43s). The failing test's identity was lost — the next run overwrote
  build/test-results before the report was captured (orchestrator process
  lesson: snapshot test-results before re-running). Two subsequent full-suite
  runs and 3 targeted repetitions of the two suspect long-window suites
  (JvmLanDiscoveryHeartbeatTest, JvmDiscoveryRecordValidationTest) all pass.
  Shape matches the known load-sensitive one-off class (FIL-15, rotation
  seed-wait). Watchlist: the kit-level heartbeat test uses real-time 20 s/35 s
  windows over a 5 s tick vs 15 s eviction horizon — margin is ~3 ticks and
  could thin under full parallel-suite CPU saturation. If it recurs with an
  attributed report, tighten the TEST's timing setup (never the product
  invariant): e.g. eviction-horizon override for the test kit, or a
  virtual-time seam for the loop.

## Group M4 (SEC-1 + P1-26, P1-18 rider; decision #9a)
- **What landed:** two-stage inbound admission control, internal constants
  only (no public API, no wire change), owner-confirmed values 16/64.
  Stage 1: `preHandshakeGate = Semaphore(MAX_CONCURRENT_PRE_HANDSHAKE_SETUPS
  = 16)` in `SessionManager.handleIncoming` — non-suspending `tryAcquire`;
  refusal = close + one warn, before any per-connection allocation. The
  permit is released exactly once at handshake settle (success or failure)
  via `setupSession`'s `onHandshakeSettled` finally — deliberately NOT at
  full-setup completion, so registration/`incomingSessions.emit` never hold
  admission capacity — with a same-coroutine flag-guarded safety-net release
  in `handleIncoming`'s outer finally. Stage 2:
  `MAX_TOTAL_ACTIVE_SESSIONS = 64` enforced in `SessionStore.tryRegister`
  for NET-NEW incoming registrations only (new outcome
  `RegisterOutcome.RefusedAtCapacity`); `SessionManager.registerSession`
  turns it into warn + clean `session.close()` (CLOSE frame), never an
  exception into the accept collector and never an `incomingSessions` emit.
- **Exemptions, per the plan:** outgoing (app-initiated) registrations are
  never refused by the total bound; simultaneous-open arbitration is exempt
  by construction (the existing-active branch runs before the cap check —
  replace/reject causes no net session growth); only ACTIVE_STATES sessions
  count, so a terminal-but-not-yet-evicted entry cannot block a live peer.
- **P1-18 rider:** `HelloPayload.decode` now bounds `platform` and each
  per-transport tag at the existing `MAX_FIELD_LEN` (512) with the same
  `require` → IllegalArgumentException path the other HELLO guards use
  (caller treats it as a malformed HELLO: skip + warn). Decode-side only —
  the encode-side caps remain the separate P2 row (PRO-1), which the plan
  does not fold into M4. The two Group C divergence-pinning tests
  (`overLimit*IsCurrentlyAccepted`) are flipped to rejection guards; the
  at-limit test now covers all five string surfaces.
- **Shutdown-window permit note (neutral, not acted on):** if the kit scope
  is cancelled between `tryAcquire` and the setup coroutine's first
  execution, neither release site runs and that permit is never returned —
  reachable only during kit shutdown, when the SessionManager and its
  Semaphore are terminal anyway; the raw connection in that same window was
  already (pre-M4) left to the transport's own close-path cleanup.
- **Cross-module constant mirror:** `JvmLanAdmissionControlTest` hard-codes
  `PRE_HANDSHAKE_BOUND = 16` (core internals not visible across the module
  boundary), documented in the test to be updated with the policy constant.
- **Gate:** all four tasks green first run (core jvmTest 26s, core allTests
  1m16s, lan jvmTest 2m25s, assemble 1m45s; logs at
  `impl-logs/groupM4-*.log`); neither known latent flake fired and the M3
  addendum's unattributed one-off did not recur.

## Group M5 (API-1 + P1-06, DOCA-14/DOCA-15 riders; decision #3c)
- **What landed (docs + test only; no behavior, wire, or API-signature
  change):** the protocol v1 metadata contract is now documented and pinned.
  KDoc on `P2pMessage` (class-level section + `@property` notes on both
  `metadata` fields): metadata is NOT transmitted in v1 — local-only on
  send, always empty on receive. Spec `P2pKit-Spec.md` §9.4 gains one
  statement to the same effect (dated, decision #3c), making the locked
  contract true. `docs/STABILIZATION_AND_RELEASE.md` C3 gains the DOCA-14
  decision box, marked DECIDED (option c, 2026-07-04).
- **Post-RC milestone (durable record):** new §C4 "`metadata-wire`" in
  `docs/STABILIZATION_AND_RELEASE.md` — scope (DATA-payload envelope,
  commonMain codec in Chunker/Reassembler), prerequisites (cross-version
  interop stance, receive-side bounds/input validation, protocol version
  consideration v1.1-vs-v2), and the instruction to consciously flip the
  P1-06 pin in the same commit. Owner wants this soon after RC.
- **P1-06 test:** `MessageMetadataContractTest` (p2p-core commonTest,
  6 tests): Text + Binary, single- and multi-chunk Chunker/Reassembler
  round-trips (also asserting the DATA payload bytes equal exactly the
  value/bytes — no envelope), plus Text + Binary loopback variants over
  `FakeConnectionPair` via `DefaultP2pProtocol`. All assert received
  metadata == emptyMap.
- **M2 cause-rule spec line:** NOT included — the plan's M5/DOCA text does
  not direct a spec line for send() error causes; left for the decision
  batch.
- **Gate:** core jvmTest green first run (27s); core allTests failed once on
  the known latent flake `SessionReconnectRotationTest.
  reconnectUsesRefreshedHintsAfterPeerRegistryUpdate[iosSimulatorArm64]`
  (TimeoutCancellationException) — test-results snapshotted to
  `impl-logs/groupM5-flake-snapshot/test-results-allTests-run1/` before the
  re-run; re-run green (1m14s, log `groupM5-core-allTests-rerun.log`);
  assemble green (1m50s). New test verified executed: 6/6 pass on jvmTest
  and iosSimulatorArm64Test.
- **New issues discovered:** none.

## Group N (decision batch: #1a, #2a, #4a, #5a, #6b, #7a, #8c, #10a, #11a, #13b + M2 spec rider)

- **Four commits:** da6acb3 (docs/spec decision-record corrections),
  d2075c0 (#6b manual-peer name refresh + #8c join-state wording),
  d77bc83 (gap analysis committed per #1a), b155bd8 (CLAUDE.md per #2a).
- **Gate one-offs (both snapshotted before re-run; nothing masked, no test
  weakened):**
  - allTests run 1: FIL-15
    `FileTransferFlowTest.cancelMidStreamPropagatesToReceiver[jvm]` — the
    already-catalogued latent flake; snapshot
    `impl-logs/groupN-flake-snapshot-allTests-run1/`.
  - allTests run 2: **new one-off** —
    `SessionFlowTest.closeTransitionsSessionToClosed[jvm]` failed once under
    full parallel-suite load with `expected:<Closed> but was:<Failed>`: the
    P1-02-tightened exact-close-classification assertion observed the
    remote-termination `Failed` shape once. Not attributable to this batch
    (no session/close runtime code touched; the test's peer is a plain
    constructor `Peer`, not a manual peer). Passed standalone 4/4 with
    `--rerun-tasks`; the next full allTests run is green. Snapshot
    `impl-logs/groupN-flake-snapshot-allTests-run2/`. Candidate addition to
    the latent-flake watchlist (same load-sensitive one-off class as FIL-15 /
    the rotation seed-waits / the M3 addendum's unattributed one-off). If it
    recurs with an attributed report, triage whether the SES-1
    classification-deferral leaves a residual close-vs-break classification
    window under CPU saturation before touching the test.
- **Other observations:**
  - Pre-existing misplaced KDoc in `AndroidNetworkProvisioningManager`: the
    doc comment describing `close()` was attached to `private companion
    object`; relocated onto `close()` (and extended with the P1-27
    limitation) as part of #8c.
  - #8c empirical nuance recorded at the refusal site: `joinHandle != null`
    is reachable only after a *successful* still-active join (an in-flight
    join holds `lifecycleLock`, so concurrent callers wait), so the reworded
    message names the already-joined state ("a joined network is already
    active; it is released only when the kit is closed").
  - #7a placement note: besides the README permission section, the same
    guidance was mirrored into the two KDocs whose text was the flagged
    recommendation path (Builders.kt `permissionManager`,
    PermissionManagerFactory.android.kt trailing paragraph) — doc-only,
    within option (a)'s scope.

## Post-merge flake stress-chase + C3 closers (2026-07-05, orchestrator)
- Stress: 10x core:jvmTest, 4x lan:jvmTest, 3x concurrent core+lan --parallel,
  3x core:iosSimulatorArm64Test — 20/20 PASS, zero reproductions of FIL-15,
  rotation seed-waits, the unattributed LAN one-off, or the SessionFlowTest
  close-classification one-off. Logs: .review-2026-07/impl-logs/stress/.
- New same-class one-off: :p2p-network-provisioning-desktop:test failed once
  (prov-1) right after the stress batches; identity lost to overwrite before
  capture (snapshot guard was missing from that follow-up loop — added for
  all subsequent loops); 5x isolated + 3x paired re-runs all green. Watchlist.
- C3 closers on merged main (6a05ccd): assemble all targets PASS; provisioning
  pair 3x PASS (prov-4..6); lan iosSimulatorArm64Test = exactly the 2
  sanctioned C2 churn failures; .asc spot-check: 5 signature files present
  for the desktop sidecar publication (signed-publish leg evidenced).
- Remaining C3: device matrix A1-A12 (hardware, user), release notes,
  keyless-signing leg (needs clean GRADLE_USER_HOME run or inspection
  acceptance), the tag itself.
