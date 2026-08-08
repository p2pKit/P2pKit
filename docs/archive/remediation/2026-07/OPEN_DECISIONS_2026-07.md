# P2pKit — Open Decisions Brief (2026-07)

- **Date:** 2026-07-04
- **Branch / HEAD:** `audit/exhaustive-review-2026-06` @ `08146ea`
- **Purpose:** one decision brief for the 15 open decisions from the 2026-07 review campaign, consolidated from `CODEBASE_FINDINGS_2026-07.md` §6 (authoritative register), `REMEDIATION_PLAN_2026-07.md` §6 + the M1–M5 plan items, and `FINAL_REVIEW_SUMMARY_2026-07.md` §6, with implementation-phase discoveries from `.review-2026-07/IMPLEMENTATION_NOTES.md` folded in where they affect a decision.
- **Status:** remediation groups A–L are implemented and committed at HEAD. **No Tier M work has been started** — groups M1–M5 are parked awaiting decisions #15, #12, #14, #9, #3 respectively. The other ten decisions block no implementation.
- File:line citations were re-verified against HEAD `08146ea` (the register/plan cite pre-remediation line numbers; they have shifted).
- Wording follows the campaign's neutral defensive-QA vocabulary (`.review-2026-07/BRIEF.md` rule 7).
- "RC gate?" judgments are tied to `docs/STABILIZATION_AND_RELEASE.md` (Part A smoke matrix, Part B publishing, Part C1 deferrals / C3 sign-off checklist). Per DOCA-14 (folded into decision #3), the C3 checklist gains a decision box, so every one of the 15 should carry a *recorded* answer by tag time even where the answer is "defer".

---

## Part 1 — The five Tier-M-gating decisions (recommended implementation order)

### Decision #15 — Approve internal-only `strictInvariants` wiring for kit-level suites

- **Gates:** Tier **M1** (TST-9 fix + fixture F6 + test P1-03). Approval-only — the plan's original suggestion to fold M1 into Group B is moot (Group B already landed at `73e255a`); M1 now lands as its own small commit.
- **Problem:** `SessionManager` takes `strictInvariants: Boolean = false` (`p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionManager.kt:110`) and forwards it to `SessionStore` (`:120`), where bookkeeping-invariant violations throw only under the flag and otherwise `logger.warn`. The only production construction site never sets it, and the behavioral suites run NoOp/quiet loggers — so the safety net restored by commit `e91e094` protects only its own unit test, and a store-bookkeeping regression would pass every kit-level test silently.
- **Options:**
  - **(a) Approve the internal wiring** (internal constructor parameter or a commonTest `TestHooks` object) so kit-level suites construct with `strictInvariants = true`, plus a meta-test proving a violation throws under the flag. Pros: every existing behavioral suite doubles as an invariant net; explicitly no public API change; production default (warn-only) untouched. Cons: any latent invariant violation in existing suites surfaces immediately and must be triaged (which is the point).
  - **(b) Defer / keep as-is.** Pros: zero work. Cons: the safety net stays inert; regressions warn into the void; P1-03 (a pre-tag P1 coverage row) stays blocked.
- **Recommendation:** (a) — it is approval of a mechanism, not a design fork; lowest-risk item in Tier M and it unblocks a P1 row.
- **Risk if deferred:** No user-visible product risk; the cost is silent-passing suites over store regressions and one unlandable P1 row.
- **RC gate?:** Recommended before RC — no C3 line item fails without it, but the campaign policy is that all 32 P1 coverage rows land pre-tag, and P1-03 is blocked solely on this approval.

### Decision #12 — Land the typed-error contract for `send()` before the tag?

- **Gates:** Tier **M2** (API-2 fix + test P1-05; the required F2 write-fault fixture already landed with Group B).
- **Problem:** `P2pSessionImpl.send()` types only its pre-check — `throw P2pError.ConnectionFailed(...)` when not `Connected` (`p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pSessionImpl.kt:264`) — then calls `protocol.sendMessage(connection, message)` unwrapped (`:267`). The write path therefore surfaces raw platform exceptions to the app (JVM/Android `IOException`, including the 30 s watchdog timeout; iOS its own shapes), diverging per platform and contradicting the typed-`P2pError` contract in `Errors.kt` and the spec. A standing deferral existed (A-G2-core-internal-14), but the campaign re-assessed it as **unsound to carry into an RC**.
- **Options:**
  - **(a) Land the wrap pre-tag:** at the `P2pSessionImpl.send()`/`sendFile()` boundary, rethrow `CancellationException` and existing `P2pError` as-is; wrap any other `Throwable` in `P2pError.ConnectionFailed` with the original preserved as cause. Internal callers (keep-alive, dispatcher) keep seeing raw exceptions. Pros: the documented contract becomes true on the hottest API call, uniformly across platforms. Cons: app-observable error-shape change (apps catching `IOException` today must switch to `P2pError`) — better absorbed pre-RC than post.
  - **(b) Defer with a documented deferral.** Pros: no behavior change on the RC line. Cons: the RC ships a documented-but-false error contract with per-platform divergence; changing it after tagging is a larger compatibility event.
- **Recommendation:** (a) — the register's own re-assessment says the deferral is unsound for an RC, and pre-tag is the cheapest moment for the observable change.
- **Risk if deferred:** Apps written against the RC will code to raw platform exceptions; correcting the contract later breaks them a second time.
- **RC gate?:** Required before RC — this is precisely the "decide whether it lands pre-tag" item; tagging with the contract knowingly false undermines the C3 sign-off's meaning for the public API of record.
- **Implementation note to fold in (Group H):** `sendFile`'s pre-handle validation refusals (top-of-function closed check, `PayloadTooLarge`, negative-`sizeBytes` require) throw with the caller's `RawSource` left open, while later refusal paths close it via the handle's terminal transition — the ownership contract for pre-handle refusals is unstated. M2's fix site is the same `send()`/`sendFile()` boundary; state (and KDoc) that ownership rule in the same commit.

### Decision #14 — JVM/Android steady-state discovery heartbeat mechanism

- **Gates:** Tier **M3** (DSC-1 fix + test P1-13).
- **Problem:** `PeerRegistry.evictStalePeers()` (`p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerRegistry.kt:95`) evicts any non-manual peer 15 s after `lastSeen` (`DEFAULT_STALE_TIMEOUT_MS = 15_000`, `:169`), but the JVM/Android transports emit `Found` only when JmDNS fires `serviceResolved` — nothing re-emits for a healthy idle peer — so `kit.peers` silently empties ~15 s after resolution and stays empty. Only iOS has a heartbeat (5 s re-announce loop, `p2p-transport-lan/src/appleMain/kotlin/dev/p2pkit/transport/lan/IosLanDiscoveryTransport.kt:705`). **Implementation-phase discovery (Group A) that sharpens this decision:** JmDNS goodbye removals (TTL=0) deliver no TXT data, so the JVM/Android removed→`PeerEvent.Lost` path never fires for real goodbyes — registry staleness eviction is currently the *only* peer-disappearance mechanism on those platforms. Any option that exempts discovered peers from eviction would remove disappearance entirely there.
- **Options:**
  - **(a) Transport-side re-emit (mirror iOS):** while discovery is active, re-emit `PeerEvent.Updated` every ~5 s for every cached, appId-matching JmDNS service, reading the in-process cache (`list()`-free — preserves the deliberate B:317 deferral). Pros: uniform `PeerRegistry` semantics on all three platforms; no core change; no added multicast; keeps eviction as the disappearance mechanism (which the goodbye observation shows is load-bearing). Cons: periodic registry churn (already de-noised by `publishPeers`'s equality check).
  - **(b) Registry-side periodic `refresh()`.** Pros: single core-side mechanism. Cons: multicast-noisier; on Android `refresh()` carries the deliberate 200 ms `list()` snapshot trade-off (B:317).
  - **(c) Eviction-exempt discovered peers.** Cons: changes `kit.peers` liveness semantics on all platforms, and — per the goodbye observation — JVM/Android peers would then never disappear. Not recommended.
  - **(d) Defer.** Not viable: steady-state `kit.peers` is user-visibly broken on 2 of 3 platforms.
- **Recommendation:** (a) — the proven iOS pattern, confined to the two transport files, with the Group A goodbye observation reinforcing that heartbeat + eviction must remain a pair.
- **Risk if deferred:** High and user-visible: any app watching `kit.peers` on JVM/Android shows an empty list after ~15 s idle; Part A smoke rows would be run against broken steady-state semantics.
- **RC gate?:** Required before RC — the register says pick the mechanism before RC because it defines cross-platform `kit.peers` semantics, and smoke rows A1/A10 exercise exactly this surface on hardware.

### Decision #9 — Inbound connection admission control: cap policy and values

- **Gates:** Tier **M4** (SEC-1 fix + test P1-26).
- **Problem:** Nothing bounds inbound-session admission: `startAcceptingIncoming` collects every accepted connection (`SessionManager.kt:147-150`), `handleIncoming` launches one setup coroutine per connection (`:219`), and each handshake allocates a 256-slot `Channel<ProtocolEvent>` plus a reader job before completing (`:321`). The 10 s handshake timeout bounds each individual setup but not their number, and there is no cap on total registered sessions — so malformed or excessive peer input (a non-conforming device opening many connections that never complete HELLO, or very many peers at once) drives unbounded fd/coroutine/heap growth. JVM/Android accept queues bound bursts (64, drop-and-close) but not sustained admission; the iOS inbound queue is unbounded (CON-9, Low, tracked separately).
- **Options:**
  - **(a) Internal caps, no API change:** a pre-handshake `Semaphore` (suggested 16) — `handleIncoming` uses `tryAcquire`, refusal closes the connection immediately with a warn log before anything is allocated — plus a max-total-active-sessions bound (suggested 64) in the store's admission path. Pros: bounded resource usage with diagnostics; refused connections hold no session state. Cons: a conforming mesh larger than the session cap is refused — the values need owner sign-off.
  - **(b) Same caps surfaced as builder configuration [API-CHANGE].** Pros: apps can size for their mesh. Cons: public API addition locked by `P2pKit-Spec.md`; new surface during RC stabilization.
  - **(c) Defer.** Pros: none needed for the happy path. Cons: every listener retains a bounded-usage gap; a single misbehaving device on the LAN can degrade the kit.
- **Recommendation:** (a) — internal constants now (they can be surfaced as configuration later without breaking anyone), with the suggested 16/64 values treated as proposals to confirm.
- **Risk if deferred:** Moderate: on the RC's trusted-LAN scope, exposure comes from non-conforming or faulty devices rather than routine use — real but not the common case.
- **RC gate?:** Recommended before RC — SEC-1 is a High and P1-26 is a P1 row, but C3's release-notes leg already scopes the RC to trusted-LAN (`NoneForMvp`), which partially bounds the exposure if the owner chooses to defer.
- **Adjacent implementation note (Group C, P1-18):** `HelloPayload.decode` applies no length bound to the `platform`/per-transport strings (pinned as actual behavior; candidate register addendum). Same inbound-input robustness family — cheap to ride along with M4 if approved.

### Decision #3 — `P2pMessage.metadata` contract: wire / deprecate / document

- **Gates:** Tier **M5** (API-1 + test P1-06), plus the DOCA-14 rider: an explicit decision box in the C3 RC sign-off checklist so an RC cannot tag with this undecided.
- **Problem:** `P2pMessage.Text`/`Binary` carry a public `metadata: Map<String, String>` (`p2p-core/src/commonMain/kotlin/dev/p2pkit/core/P2pMessage.kt:18`, `:24`), but the send path serializes only `value`/`bytes` (`Chunker`) and the receive side reconstructs with the `emptyMap()` default (`Reassembler`). Metadata a caller attaches is silently lost end-to-end — public-API data loss with no error and no doc statement (spec gap DOCA-15).
- **Options:**
  - **(a) Wire it** — serialize metadata in a DATA-payload envelope (commonMain codec; PP2K header/frame types untouched). Pros: the field finally works. Cons: cross-*version* interop change (v-next sender → current receiver) needing a deliberate compatibility stance; wrong scope for a stabilization RC.
  - **(b) Deprecate/remove the parameter.** Pros: honest surface. Cons: public API change locked by `P2pKit-Spec.md`; churn for consumers.
  - **(c) Document "not transmitted in protocol v1"** — KDoc + spec §9.4 statement + P1-06 pinning the receive side as asserted-empty; record (a) as the metadata milestone. Pros: zero code risk; removes the silence. Cons: field remains a decoy until the milestone.
- **Recommendation:** (c) for the RC line, with (a) recorded as a named post-RC milestone — the plan's own recommendation.
- **Risk if deferred:** The silent data loss stays undocumented and users find it by debugging; DOCA-14 exists specifically to prevent the RC tagging in that state.
- **RC gate?:** Required before RC (the *decision*, not the wiring): the C3 decision box makes an undecided state a sign-off blocker, and option (c) costs only a doc + one test.

---

## Part 2 — The remaining ten decisions (register order)

### Decision #1 — Disposition of the untracked `P2PKIT_GAP_ANALYSIS_2026-07.md`

- **Gates:** blocks no implementation — repo hygiene / documentation of record (would have ridden Group L; now a standalone docs commit).
- **Problem:** The 197-line strategic gap-analysis/roadmap doc is still untracked at HEAD `08146ea` (confirmed in `git status`), so it is one `git clean -fd` from loss. The A13a report verified 12 of its load-bearing claims (1 inaccurate, §4.3) and flagged that its P7 suggestion collides with the repo's no-`@Ignore` rule.
- **Options:**
  - **(a) KEEP and COMMIT** with a status banner, the §4.3 correction, and a reword of the P7 suggestion. Pros: preserves verified strategic analysis; corrections prevent future agents being mis-steered. Cons: one more doc of record to maintain.
  - **(b) Archive outside the repo / discard.** Pros: smaller doc surface. Cons: loses analysis the campaign already fact-checked.
  - **(c) Defer (leave untracked).** Pros: none. Cons: the accidental-loss exposure persists indefinitely.
- **Recommendation:** (a) — the report's own recommendation; the corrections are already itemized.
- **Risk if deferred:** Genuinely low for the product; the only real exposure is accidental file loss.
- **RC gate?:** Can wait — no C3 criterion references this document.

### Decision #2 — Commit (or amend) the working-tree `CLAUDE.md`

- **Gates:** blocks no implementation — docs/process. It also parks one Group L follow-up: the annotate-on-fix process rule could not be added to `CLAUDE.md` during implementation (file untouchable pending this decision) and currently lives only in the `AUDIT_REPORT_2026-06.md` header note; porting it is a one-line rider once this lands.
- **Problem:** `CLAUDE.md` is modified in the working tree while the committed HEAD version contains a now-false publishing claim (DOCA-1). `CLAUDE.md` steers every future agent session, so drift between HEAD and the corrected working-tree copy mis-steers anyone reading the committed version.
- **Options:**
  - **(a) Commit the working-tree version**, optionally folding in the annotate-on-fix rule and the PRM-12 wording precision (iOS *hotspot/join* provisioning is Unsupported, but `iosManualIp()` ships). Pros: HEAD becomes truthful; unblocks the Group L rider. Cons: none of substance.
  - **(b) Defer / keep as-is.** Pros: zero effort. Cons: HEAD keeps a false publishing claim in the highest-leverage doc.
- **Recommendation:** (a) — cheapest correctness win in the list.
- **Risk if deferred:** Low-moderate: doc-of-record drift only, but in the one file every agent loads first.
- **RC gate?:** Recommended before RC — no explicit C3 line, but Part B's publishing recipe is cross-referenced from `CLAUDE.md`, and the sign-off assumes the docs of record are truthful.

### Decision #4 — Record the `ChangeWifiState` disambiguation deferral formally

- **Gates:** blocks no implementation — pure record-keeping for the C3 decision sweep.
- **Problem:** The older audit's C:54 asked whether the `P2pPermission` enum needs disambiguation around `ChangeWifiState`. The A09 review re-verified there is a single Android mapping today and assessed the deferral as **sound**. The only open item is that no formal record exists, so the question keeps resurfacing in every review pass.
- **Options:**
  - **(a) Record the decision** ("deferral sound; revisit only if a second platform mapping appears") in the decision log / audit report annotations. Pros: one paragraph; stops the churn. Cons: none.
  - **(b) Rework the enum now [API-CHANGE].** Pros: none today — no current defect motivates it. Cons: public API churn for a hypothetical.
  - **(c) Defer silently again.** Cons: guaranteed to resurface in the next review.
- **Recommendation:** (a) — the assessment is already done; only the recording is missing.
- **Risk if deferred:** Negligible — process noise only.
- **RC gate?:** Can wait — no C3 criterion touches it; the C3 decision-box sweep will tick it naturally.

### Decision #5 — Construction-time blocking disk I/O in `newP2pKit`

- **Gates:** blocks no implementation — backlog disposition (Low finding, not scheduled in the plan).
- **Problem:** Kit construction runs `peerIdStorage.loadOrGenerate()` on the caller's thread (`p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt:615`) — blocking disk I/O at `newP2pKit` time; on Android, constructing on the main thread risks a jank/ANR-adjacent stall (catalogued B:201). It sits in neither the remediated list nor any deferral note, so the ask is an explicit disposition either way.
- **Options:**
  - **(a) Documented deferral:** KDoc "construct off the main thread" + a backlog item for lazy/async identity load. Pros: zero code risk on the RC line. Cons: the hazard remains for careless callers.
  - **(b) Suspending/async construction [API-CHANGE-adjacent].** Pros: structurally correct. Cons: builder-surface change locked by the spec; wrong scope for RC stabilization.
  - **(c) Move the I/O internally to first `start()`** (no API change). Pros: main-thread-safe construction. Cons: relocates rather than removes the block; `start()` is already suspending but the change needs its own lifecycle care.
- **Recommendation:** (a) for the RC line — it is a one-time small-file read/write; a doc note is proportionate.
- **Risk if deferred:** Low — worst case a brief first-launch stall for apps that construct on the Android main thread.
- **RC gate?:** Can wait — no C3 criterion fails; record the disposition in the decision sweep.

### Decision #6 — `unregisterManualPeer(peerId)` vs documented lifetime

- **Gates:** blocks no implementation — backlog / API discussion (Improvement finding IDN-7).
- **Problem:** Manual peers registered via `ManualPeerRegistrar.registerManualPeer` (`p2p-core/src/commonMain/kotlin/dev/p2pkit/core/provisioning/ManualPeerRegistrar.kt:37-42`) have no unregister or expiry path — they live until `kit.stop()` — and a dedupe-hit on (host, port, kind) silently drops a newly supplied `deviceName`, so a re-registration with a fresh display name appears to do nothing.
- **Options:**
  - **(a) Add `unregisterManualPeer(peerId)` [API-CHANGE].** Pros: clean lifecycle symmetry. Cons: public surface addition locked by the spec, during RC stabilization.
  - **(b) No-API-change alternative:** KDoc the until-`stop()` lifetime + registry-internal `deviceName` refresh on dedupe-hit. Pros: fixes the silent drop and documents the lifetime with no surface change. Cons: still no removal path.
  - **(c) Defer entirely.** Pros: manual peers are few in practice. Cons: the silent name-drop stays surprising.
- **Recommendation:** (b) now; revisit (a) post-RC alongside the next deliberate spec revision.
- **Risk if deferred:** Low — manual peers are an experimental-surface fallback (smoke row A10 scope), few per session.
- **RC gate?:** Can wait — nothing in C3 or the smoke matrix requires a removal path.

### Decision #7 — Permission-gate granularity after fix #9

- **Gates:** blocks no implementation — gates the P2 `PermissionGateTest` contract row; affects integrator-facing docs guidance.
- **Problem:** Audit fix #9 (`881fb31`) stopped hard-gating core LAN on install-time permissions, but the kit-wide permission gate re-creates LAN over-gating for apps that wire the provisioning sidecar's permission manager into the kit — which is exactly what the docs currently recommend (finding PRM-1: mechanism deliberate and test-pinned, but the granularity contradicts the fix's stated goal).
- **Options:**
  - **(a) Doc-level guidance:** keep the default empty manager on the kit; query the sidecar manager only immediately before provisioning calls. Pros: no API change; removes the docs-driven regression path. Cons: convention, not enforced by types.
  - **(b) Per-operation permission sets on `P2pPermissionManager` [API-CHANGE].** Pros: structurally correct granularity. Cons: public API redesign during RC stabilization.
  - **(c) Defer.** Cons: the recommended integration pattern silently re-introduces the over-gating fix #9 removed.
- **Recommendation:** (a) for the RC line; treat (b) as input to the encryption-milestone API pass.
- **Risk if deferred:** Moderate-low: only integrators following the current doc recommendation on Android are affected, but they regress to pre-fix behavior.
- **RC gate?:** Recommended before RC — smoke row A11 (permission gating on fresh installs) validates this area on hardware and should run against the corrected guidance.

### Decision #8 — `leaveNetwork()` and the join-rejection wording

- **Gates:** blocks no implementation — spec discussion (Improvement PRM-16) plus a trivially safe message reword.
- **Problem:** There is no way to leave a joined network short of closing the kit, and the join-rejection message claims "a join is already in progress; close the kit before retrying" (`p2p-network-provisioning-android/src/main/kotlin/dev/p2pkit/provisioning/android/AndroidNetworkProvisioningManager.kt:193`) even when the state is already-joined — misleading diagnostics. **Related implementation-phase note (Group C, P1-27):** `startLocalNetwork` attempted after parent-job cancellation is accepted (returns `Started`) and the reservation sits outside parent-job cleanup (explicit `close()` only) — pinned as actual behavior; any lifecycle-semantics rework here should sweep that too.
- **Options:**
  - **(a) Add `leaveNetwork()` [API-CHANGE].** Pros: explicit lifecycle. Cons: new public surface pre-RC.
  - **(b) Redefine `stopLocalNetwork` to also release a join.** Pros: no new symbol. Cons: semantics change on an existing call; needs spec wording.
  - **(c) Minimum now:** reword the rejection message + document "a join is released on kit close". Pros: fixes the misleading diagnostic at zero risk. Cons: still no leave path.
  - **(d) Defer all.** Cons: the paper-cut message persists.
- **Recommendation:** (c) now; take (a) vs (b) into the post-RC spec discussion, folding in the P1-27 lifecycle gap.
- **Risk if deferred:** Low — join lifetime is bounded by kit lifetime; the defect is ergonomic, not functional.
- **RC gate?:** Can wait — smoke row A9 (hotspot/join) may be explicitly waived per C3, and no criterion needs a leave path.

### Decision #10 — `ConnectionState.Closing`: spec fix vs emitting it

- **Gates:** blocks no implementation — the Group D constraint (SES-1 must not begin emitting `Closing`) was honored at `13fd3de`; gates the P2 close-sequence row.
- **Problem:** The spec still documents `close()` transitions: `Connected → Closing → Closed` (`P2pKit-Spec.md` §10), but the session never enters `Closing`. At HEAD the code-side KDoc is already truthful — `States.kt:31-35` states that `close()` moves directly to `Closed` and `Closing` "is never emitted" — so the residual is the spec sentence plus a classification disagreement between reports (A03 treats emitting `Closing` as an observable-behavior/API-adjacent change; A13a calls it API-change-free since the constant exists).
- **Options:**
  - **(a) Fix spec §10** to match code ("directly to Closed; `Closing` reserved"). Pros: one-line change, zero behavior risk; aligns the locked contract with reality. Cons: the enum keeps a never-emitted constant.
  - **(b) Start emitting `Closing`.** Pros: enum becomes honest. Cons: observable state-sequence change apps may key on; needs the P2 close-sequence tests and a deliberate compatibility call.
  - **(c) Defer.** Cons: the API contract of record keeps disagreeing with the shipped behavior.
- **Recommendation:** (a) — the KDoc already committed to this reading; the spec should follow, and (b) can be revisited at the next behavior-change window.
- **Risk if deferred:** Low — doc/spec mismatch only, but in the locked API contract.
- **RC gate?:** Recommended before RC — `P2pKit-Spec.md` is the contract the tag certifies; a one-line spec fix keeps it truthful.

### Decision #11 — Offer-timeout terminal-state asymmetry

- **Gates:** blocks no implementation — gates the P2 unanswered-offer row.
- **Problem:** When a file offer goes unanswered, the receiver's transfer terminalizes as `Rejected("timeout")` while the sender's terminalizes as `Cancelled("offer not accepted within …ms")` (`p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/FileTransferDispatcher.kt:680`), and `Cancelled`'s KDoc claims timeouts land in `Cancelled` — the two sides of one event disagree, and the docs mislabel one of them (API-19).
- **Options:**
  - **(a) Document the per-side outcomes** (KDoc + spec): sender sees `Cancelled(timeout-reason)`, receiver sees `Rejected("timeout")`. Pros: zero behavior risk. Cons: the asymmetry persists.
  - **(b) Align the sender to `Rejected("timeout")`.** Pros: symmetric terminal states. Cons: behavioral change to a terminal state apps may pattern-match on; needs its own test row.
  - **(c) Defer.** Cons: KDoc stays wrong.
- **Recommendation:** (a) for the RC line; queue (b) for the next deliberate behavior-change window.
- **Risk if deferred:** Low — both sides do reach terminal states; this is an API-clarity defect, not a hang.
- **RC gate?:** Can wait — no C3 criterion or smoke row (A5/A6 exercise accepted/cancelled transfers) covers unanswered-offer timeouts.

### Decision #13 — Incoming-session receive contract at replay = 0

- **Gates:** blocks no implementation — gates the P2 loss-contract row; affects spec/sample guidance (root cause of the SMP-8 sample-test latent flake).
- **Problem:** `P2pSession.incoming`/`incomingFiles` are hot `SharedFlow`s with `replay = 0` (`P2pSessionImpl.kt:132`; spec §10 documents "late subscribers miss earlier messages"). An *incoming* session is created by the remote's dial, so there is an inherent window between the session being emitted to the app and the app's collector subscribing — a fast first message from the dialer lands with no subscriber and is dropped. SMP-8 documents exactly this race in the sample loopback test.
- **Options:**
  - **(a) Small replay buffer** (e.g. `replay = 1..N`). Pros: closes the window for typical first-message patterns. Cons: changes late-subscriber semantics for every session (re-subscribers see stale messages); an API-semantics change to the locked spec §10 wording.
  - **(b) Documented sender-side grace period:** strengthen spec/KDoc/sample guidance — subscribe before sending on a fresh session, or sender waits for an app-level ready signal. Pros: no code change; the spec already warns. Cons: pushes the burden onto app authors; the sample race remains possible in principle.
  - **(c) Defer as-is.** Same as (b) minus the strengthened wording — strictly worse.
- **Recommendation:** (b) for the RC line — spec §10 already states the semantics; make the guidance explicit and fix the samples, and evaluate (a) as a deliberate post-RC semantics change with the P2 loss-contract row.
- **Risk if deferred:** Low-moderate — a documented but common trap: apps that fire a message immediately after connect can lose it; no corruption, no hang.
- **RC gate?:** Can wait — the behavior is documented in the locked spec today; record the disposition in the C3 sweep.

---

## Tally

- **Required before RC:** #12, #14, #3 (for #3 the *decision* is required; the recommended fix is doc+test only).
- **Recommended before RC:** #15, #9, #2, #7, #10.
- **Can wait:** #1, #4, #5, #6, #8, #11, #13.

