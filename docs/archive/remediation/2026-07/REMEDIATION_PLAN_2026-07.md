# P2pKit — Remediation Plan (2026-07 review campaign)

## 1. Header

- **Date:** 2026-07-04
- **Branch / HEAD:** `audit/exhaustive-review-2026-06` @ `870bf10`
- **Scope statement:** **Plan only; no fixes implemented; nothing pushed.** This document sequences the remediation of the 2026-07 review campaign's findings. No repository code, test, build file, or doc is changed by this plan itself; every proposed fix awaits execution and the decision-gated items await the user's call.
- **Inputs used:**
  - `CODEBASE_FINDINGS_2026-07.md` — authoritative findings register (248 rows; §3.1 the 1 Critical, §3.2 the 16 Highs, §2 verification evidence, §6 the 15 open decisions).
  - `TEST_COVERAGE_PLAN_2026-07.md` — §3.1 the 32 P1 test items; §2 the fixture-upgrade prerequisite (F1–F9; 14 rows blocked) and §2.2 seams/source sets.
  - `FINAL_REVIEW_SUMMARY_2026-07.md` — campaign overview, decision list, constraints.
  - `CLAUDE.md` — build/test commands, architecture, standing engineering constraints.
  - `AUDIT_REPORT_2026-06.md` — deferred-decisions list only (to avoid re-proposing deliberate deferrals unflagged).
  - `REMEDIATION_2026-07.md` — the 9-commit remediation record this plan builds on.
  - Source tree at HEAD `870bf10` — every Critical/High root cause below was re-read directly from the cited files (not taken from report prose).
- **Wording:** neutral defensive-QA vocabulary throughout (input validation, malformed/excessive peer input, resource-limit enforcement, bounded resource usage, admission control, crash prevention, defensive robustness), per campaign rule 7.

## 2. Recommended execution order

Groups land in this order; each group must leave the tree green (its gates in §5 pass) before the next lands. Ordering logic: (a) the Critical crash-prevention item first; (b) the fixture upgrade and behavior-pinning tests land **before** the session/connection behavior changes they protect; (c) decision-gated work is parked in tier M and never blocks tiers A–L; (d) transport/platform groups carry their platform gates; (e) doc/tooling groups land last among the ungated work because nothing depends on them.

| Order | Group | Name | Part-1 items | P1 test rows | Decision gate | One-line rationale |
|---|---|---|---|---|---|---|
| 1 | A | Discovery-callback input validation | RBS-1 (Critical) | P1-25 | None | Process-crash prevention on malformed discovery input; zero dependencies; highest severity first. |
| 2 | B | Shared test-fixture upgrade (F1–F5, F7–F9) | TST-1 | P1-00 | None (F6 split to M1) | Unblocks 5 P1 rows (14 plan-wide); test-only, so it cannot destabilize the tree; must precede Group D's tests. |
| 3 | C | P1 pinning tests (no SDK behavior change) | — | P1-10,11,12,17,18,19,27,28,32 | None | Pins current protocol/registry/identity/provisioning behavior before the behavior-changing groups touch adjacent code. |
| 4 | D | Session remote-termination determinism | SES-1 | P1-01, P1-02 | None | The highest field-impact correctness race; its deterministic tests exist only after Group B (F1). |
| 5 | E | Connection cancellation + fd release | CON-1 | P1-16 | None | JVM/Android cleanup-path fix (parity pair in lockstep); independent of D but same subsystem family — land after D so loopback gates run once per state change. |
| 6 | F | Inbound accept-loop resilience | CON-3 | P1-04 | None | Removes an Android host-app crash path; commonTest half needs F3 from Group B. |
| 7 | G | Kit lifecycle cancellation correctness | ARCH-1, ARCH-2 | P1-07, P1-08, P1-09 | None | start/stop CE handling; isolated to `P2pKitImpl`, protected by the new KitLifecycleTest rows. |
| 8 | H | File-transfer terminal-path robustness | FIL-1, FIL-2 (+ riders FIL-4, FIL-6, FIL-11) | P1-20…P1-24 | None | One subsystem, one reviewable diff; riders are required by the P1 tests themselves. |
| 9 | I | Transport test seams + platform P1 tests | — (+ riders DSC-3, DSC-13) | P1-14, P1-15 | None | Behavior-preserving injection seams (JmDNS factory, watchdog timeout) enabling the last automated P1 transport rows. |
| 10 | J | Publishing readiness | BLD-2 | P1-29 | None | Release-gate wiring; independent of all code groups; verified by its own script gate. |
| 11 | K | iOS build provenance | IOSB-3 | P1-30, P1-31 | None | Script-only; needs a macOS manual verification pass, so batched near the end. |
| 12 | L | Documentation of record refresh | DOCB-1 | — | None | Doc-only; written last so status annotations can reference the landed groups A–K. |
| 13 | M1 | strictInvariants suite wiring (awaiting decision) | TST-9 (+ F6) | P1-03 | **#15** | Approval-only internal wiring; if #15 is granted at plan review, fold M1 into Group B. |
| 14 | M2 | Typed send() error contract (awaiting decision) | API-2 | P1-05 | **#12** | App-observable error-shape change; register assessed the standing deferral unsound for an RC — user call. |
| 15 | M3 | JVM/Android discovery heartbeat (awaiting decision) | DSC-1 | P1-13 | **#14** | Mechanism choice defines cross-platform `kit.peers` semantics; must be picked before RC. |
| 16 | M4 | Inbound admission control (awaiting decision) | SEC-1 | P1-26 | **#9** | Internal caps need no API change, but cap values/config surface are the user's call. |
| 17 | M5 | P2pMessage.metadata contract (awaiting decision) | API-1 | P1-06 | **#3** | Wire it / deprecate it / document it — three materially different diffs; cannot start unpicked. |

Tier M items are ordered by expected decision latency (M1 is approval-only), not by severity; any of M2–M5 may land earlier the moment its decision arrives. All five block the RC tag per the register/coverage plan, so the decisions themselves are the critical path once tiers A–L are done.

## 3. Part 1 — Critical + High remediation (17 items)

### 3.1 Critical

#### RBS-1 — Discovery TXT peer-id reaches `PeerId()` unguarded on all three platforms

- **Finding ID:** RBS-1
- **Severity:** Critical
- **Root cause:** `PeerId`'s `init` enforces `require(value.isNotBlank())` (`p2p-core/src/commonMain/kotlin/dev/p2pkit/core/Identity.kt:29`), and every discovery callback constructs `PeerId(pid)` directly from an mDNS TXT-record value that has only been null-checked, never blank-checked: iOS `emitPeer` (`p2p-transport-lan/src/appleMain/kotlin/dev/p2pkit/transport/lan/IosLanDiscoveryTransport.kt:634`) and `emitLostById` (`:675`, reached from `emitLost` which only null-checks at `:659`; `emitLostById` has a self-id check at `:674` but no appId gate); JVM `serviceRemoved` (`JvmLanDiscoveryTransport.kt:134`) and `serviceResolved` (`:171`); Android `serviceRemoved` (`AndroidLanDiscoveryTransport.kt:524`) and `serviceResolved` (`:567`). A whitespace-only `pid` TXT value passes the null checks and throws `IllegalArgumentException` inside the platform discovery callback. On iOS the throw crosses the `nw_browser` callback boundary — a process-crash path on malformed discovery input; on JVM/Android it is an untyped failure on a JmDNS listener thread (either disposition violates the typed-error invariant). The wire-HELLO twin of this input path was hardened in AUDIT-2026-06; this path received neither the `isNotBlank` guard nor a `runCatching` wrapper. Additionally, the Lost paths on all three platforms are not appId-gated (any same-service-type advertiser's removal can target the registry).
- **Affected files:** `IosLanDiscoveryTransport.kt` (appleMain), `JvmLanDiscoveryTransport.kt` (jvmMain), `AndroidLanDiscoveryTransport.kt` (androidMain); optionally a small shared record-validation helper per coverage plan §2.2 (extracted `parsePeerRecord`-style TXT helper) for the commonTest unit leg.
- **Proposed fix:** Validate the TXT `pid` (non-blank after trim) before any `PeerId()` construction on **both** the found and lost paths of all three platforms; on invalid input, skip the record with a trace-level diagnostic (`JvmLanDiag`/`Log.d`-gated/`IosLanDebug`) and emit nothing. Add the appId gate to the Lost paths where the TXT record is available (JVM/Android `event.info.getPropertyString(TXT_APP_ID)`, iOS `attrs` map), mirroring the existing Found-path filters. Extract the validate-and-parse step into a per-platform-callable helper so a commonTest unit leg exists. Explicitly **not** in scope: peer-identity verification — the identity-trust dimension of the Lost path (DSC-11) is `[CATALOGUED]` under the pre-encryption trust model (the inbound HELLO peerId deferral to the encryption milestone, `TODO(encryption-milestone)` in `SessionManager`); this fix is input validation plus appId scoping only and does not conflict with that deliberate deferral.
- **Required tests:** Coverage plan P1 row P1-25 (RBS-1, API-17): blank/empty/whitespace TXT `pid` on found AND removed paths never throws out of a discovery callback — `p2p-transport-lan` iosSimulatorArm64Test + jvmTest loopback (crafted advertiser) + commonTest unit for the extracted parser helper. The JVM/Android listener-thread disposition residual named in register §5 is settled by the crafted-advertiser loopback test.
- **Risk of change:** Low — additive validation that skips malformed records; no wire/TXT format change; behavior identical for all conforming peers. Parity note: the guard must be mirrored across the three platform files in one commit.
- **Suggested commit grouping:** Group A — Discovery-callback input validation.
- **Open-decision dependency:** None.

### 3.2 High — grouped by root cause

#### Root-cause group: cancellation-handling defects in lifecycle/cleanup paths

#### ARCH-1 — `ensureStarted` bind loop swallows `CancellationException` and latches `Failed`

- **Finding ID:** ARCH-1
- **Severity:** High
- **Root cause:** `P2pKitImpl.ensureStarted()` wraps each transport start in `runCatching { transport.start() }` (`p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt:266`). `runCatching` captures **all** `Throwable` including `CancellationException`, so a caller cancelled mid-bind has its CE converted into `P2pError.TransportStartFailed` (`:269-273`), `startResult` latched as failure (`:274`), and `P2pState.Failed` published (`:280`) — the CE is swallowed (invariant violation) and the public state is corrupted by a routine lifecycle event (e.g. an Android scope cancelling `kit.start()`). The secondary site `runCatching { pathObserver.start() }` (`:301`) has the same CE-capture shape.
- **Affected files:** `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt`.
- **Proposed fix:** In the bind loop, rethrow `CancellationException` before any wrapping/latching (explicit `try/catch (e: CancellationException) { throw e }` or a shared `runCatchingNonCancellable` helper); on CE, do not set `startResult` and do not publish `Failed` — leave state at `Starting`/prior so a subsequent `start()` retries cleanly (the existing Idle/Failed → Starting logic at `:262` already supports retry). Apply the same CE-rethrow to the `pathObserver.start()` `runCatching` at `:301` (its failure-swallowing for non-CE throwables is intentional and stays). The Android crash-escalation sub-claim (register §5) gets its repro via the new test rather than a field diagnosis.
- **Required tests:** Coverage plan P1 row P1-08 (ARCH-1): cancelling `kit.start()` mid-bind → state NOT `Failed`, CE (not `TransportStartFailed`) propagates, subsequent `start()` succeeds (KitLifecycleTest, hung-start fake). Plus P1-07 (A01 §3 r1): the P2pState machine suite (Idle→Starting→Running, bind failure→Failed, failed start does not latch) which currently has zero assertions and pins this group's semantics.
- **Risk of change:** Medium — start-path control flow; mitigated by the fact that CE-rethrow is the codebase's stated invariant and by landing P1-07's state-machine pinning tests in the same group.
- **Suggested commit grouping:** Group G — Kit lifecycle cancellation correctness.
- **Open-decision dependency:** None.

#### ARCH-2 — `stop()` tail runs `pathObserver.close()` outside `NonCancellable`, unbounded

- **Finding ID:** ARCH-2
- **Severity:** High
- **Root cause:** `P2pKitImpl.stop()`'s `withContext(NonCancellable)` block ends at `P2pKitImpl.kt:463`; the tail — `runCatching { pathObserver.close() }` (`:469`), `internalJob.cancel()` (`:470`), and the `Stopped` latch (`:471`) — runs outside it and unbounded. Two failure shapes: (1) if the caller's coroutine is cancelled during teardown, the suspend call `pathObserver.close()` throws CE at its first suspension point without completing — the platform observer (Android `ConnectivityManager` callback registration / iOS `nw_path_monitor`) leaks and `Stopped` is never latched by this call; (2) if a platform observer's `close()` blocks on its internal mutex (`AndroidNetworkPathObserver.kt:69-118`, `IosNetworkPathObserver.kt:71-109`), `stop()` hangs with no bound. This is the same hazard class the f4dd3a9 #17 fix closed for transports — the observer is the one resource left outside that fix's pattern.
- **Affected files:** `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt` (fix site); `AndroidNetworkPathObserver.kt`, `IosNetworkPathObserver.kt` (behavior referenced, no change required).
- **Proposed fix:** Move the tail inside the `NonCancellable` block and bound the observer close: `withTimeoutOrNull(OBSERVER_CLOSE_TIMEOUT_MS) { runCatching { pathObserver.close() } }` with a `logger.warn` on timeout, then `internalJob.cancel()` and `_state.value = P2pState.Stopped` — mirroring the bounded-acquisition pattern already used for `startMutex` at `:452-462` (keep its AUDIT-2026-06 marker comments intact). No observer-side change needed.
- **Required tests:** Coverage plan P1 row P1-09 (ARCH-2): `stop()` completes within a bound when a fake observer's `start()` hangs and its `close()` blocks on the same mutex; cancelling the stop caller still invokes the observer's `close()` (KitLifecycleTest, fake observer).
- **Risk of change:** Low — extends an already-audited teardown pattern by one resource; teardown remains idempotent and `runCatching`-wrapped.
- **Suggested commit grouping:** Group G — Kit lifecycle cancellation correctness.
- **Open-decision dependency:** None.

#### CON-1 — JVM/Android `close()` and read loop skip fd release when the caller is cancelled

- **Finding ID:** CON-1
- **Severity:** High
- **Root cause:** `JvmRawConnection.close()` releases the socket via `withContext(Dispatchers.IO) { closeSocketOnce() }` (`p2p-transport-lan/src/jvmMain/kotlin/dev/p2pkit/transport/lan/JvmRawConnection.kt:185-187`). Per documented kotlinx-coroutines behavior, `withContext` on an already-cancelled caller throws CE **on entry without running the block** — so a close issued from a cancelled coroutine (e.g. `SessionManager` cleanup during scope teardown, `SessionManager.kt:386-389`, `:574`; `P2pSessionImpl.kt:320`, `:340`) skips both `closeSocketOnce()` and the subsequent `connScope.cancel()` (`:188`), leaking the fd and the watchdog scope. The read loop has the same shape: CE thrown from `withContext(Dispatchers.IO) { input.read(buffer) }` (`:154`) propagates out of the `flow` block, skipping the terminal `closeSocketOnce()` at `:173`. `AndroidRawConnection.kt:149-188` is the intentionally-duplicated twin with the identical defect.
- **Affected files:** `JvmRawConnection.kt` (jvmMain), `AndroidRawConnection.kt` (androidMain) — the behavior-parity pair, changed in lockstep in one commit.
- **Proposed fix:** Make fd release cancellation-proof: `closeSocketOnce()` is a plain non-suspending function (a CAS + `socket.close()`), so in `close()` call it (and `connScope.cancel()`) **before** or instead of the dispatcher hop — or wrap the hop as `withContext(NonCancellable + Dispatchers.IO)`; simplest safe shape is to drop the `withContext` entirely (a one-shot `socket.close()` is acceptable on the caller thread and already runs on arbitrary threads via the watchdog path at `:104`). In `read()`, wrap the loop body in `try/finally` so `closeSocketOnce()` + the `Closed` state flip run on every exit including CE (rethrowing the CE — never swallow it). Keep the AUDIT-2026-06 fd-leak marker comments and the `closeSocketOnce` single-release invariant.
- **Required tests:** Coverage plan P1 row P1-16 (CON-1): `close()` called from an already-cancelled coroutine still releases the fd; cancelled read collector + remote close still ends with `socket.isClosed` (`p2p-transport-lan` jvmTest, extending the existing `remoteDisconnectClosesLocalSocketFd` pattern).
- **Risk of change:** Low/Medium — cleanup-path-only change on the hottest transport pair; parity risk managed by changing both files in one commit and running the loopback suite; no wire behavior change.
- **Suggested commit grouping:** Group E — Connection cancellation + fd release.
- **Open-decision dependency:** None.

#### Root-cause group: remote-termination signal ambiguity (product + fixture sides)

#### SES-1 — Terminal-outcome race on remote connection loss (reconnect skipped / clean close retried)

- **Finding ID:** SES-1 (canonical; duplicate CON-7 collapsed into it)
- **Severity:** High
- **Root cause:** Two independent observers race to classify a remote disconnect, and the transport erases the signal they would need to agree. `JvmRawConnection.read()` collapses a read `IOException` (`:153-158`) and EOF (`:160-162`) into the **same** normal flow completion + `Closed` state flip (`:169-175`); `IosRawConnection` mirrors this. At the session layer, (1) `observeRawState` (`p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pSessionImpl.kt:222-233`) sees raw `Closed` and calls `onConnectionLost` (reconnect-eligible) if still `Connected`, while (2) `routeEvents`'s channel-completion branch (`:548-552`) calls `markCleanlyClosed()` ("remote hangup … treat it like a clean close … never retry"). Whichever coroutine wins determines the outcome: an abrupt reset may terminalize as `Closed` (reconnect skipped) or a genuinely clean hangup may enter `Reconnecting` — nondeterministic on every remote loss without a CLOSE frame.
- **Affected files:** `P2pSessionImpl.kt` (fix site — `routeEvents` completion branch, ordering of `markCleanlyClosed` vs raw-state observation); `SessionManager.kt:300-313` and the transports referenced for context (no transport change: they legitimately cannot distinguish reset from EOF once the read has failed).
- **Proposed fix:** Establish a single classification authority in the session: **only an explicit received CLOSE frame (`ProtocolEvent.Close`, `:530-534`) or a local `close()` yields the clean-`Closed` outcome; protocol-events completion without a prior CLOSE frame routes to `onConnectionLost("remote hangup without CLOSE")`** — outgoing sessions with `ReconnectPolicy.Enabled` deterministically reach `Reconnecting`, incoming sessions deterministically reach `Failed` (matching the documented "incoming go straight to Failed" rule). Also treat `ClosedReceiveChannelException` (`:555-556`) the same way. Ensure the CLOSE-frame path latches its terminal state via `transitionToTerminal` **before** the raw connection's subsequent close can trigger `observeRawState` (the `_state.value == Connected` guard at `:226` plus the existing terminal serialization covers this once `markCleanlyClosed` runs first; the F1-enabled race test pins it). Honesty note: this deliberately changes the in-code "treat remote hangup as clean close" comment's behavior — the register, the spec invariant ("clean closes never retry" — a hangup without CLOSE is not a clean close), and P1 rows P1-01/P1-02 all define the deterministic semantics this fix implements; it is registered as a defect, not an open decision. Interaction: must not introduce `ConnectionState.Closing` emission (that is open decision #10 / DOCA-16 — untouched here).
- **Required tests:** Coverage plan P1 rows P1-01 (abrupt remote termination → deterministic `Reconnecting`; `observeRawState` fires on remote close; incoming EOF → deterministic `Failed` — **blocked on F1**) and P1-02 (remote CLOSE → exactly `Closed`, never `Failed`; dial factory never re-invoked; tighten `SessionFlowTest.kt:222-231` from `Closed || Failed` to exact state — strict assertion writable now, CLOSE-then-socket-close race variant blocked on F1).
- **Risk of change:** High — this is the SDK's touchiest state machine (reconnect semantics, "frequently touched" per CLAUDE.md); mitigated by landing Groups B (fixture fidelity) and C (pinning tests) first and by the exact-state assertions replacing the current disjunctive one.
- **Suggested commit grouping:** Group D — Session remote-termination determinism.
- **Open-decision dependency:** None.

#### TST-1 — `FakeRawConnection` models remote termination unlike any shipped transport

- **Finding ID:** TST-1 (canonical; duplicate SES-10 collapsed into it)
- **Severity:** High
- **Root cause:** `FakeRawConnection.read()` is `receive.receiveAsFlow()` with no state flip on completion (`p2p-core/src/commonTest/kotlin/dev/p2pkit/core/testfixtures/FakeRawConnection.kt:42`), and `breakWith(cause)` closes the receive channel **with** a cause so the read flow throws (`:58-63`) — a failure signature no shipped transport produces (`JvmRawConnection.kt:153-176` collapses read error and EOF into normal completion + state flip; iOS mirrors it). Consequently the SES-1 clean-close-vs-reconnect race is structurally invisible to commonTest: the fake drives `routeEvents` into the `catch (Throwable)` branch that production never takes, and never exercises the completion-vs-raw-state race at all.
- **Affected files:** `FakeRawConnection.kt` (commonTest test fixture); ripple: every commonTest suite that uses `breakWith` must be re-audited for reliance on the throwing signature.
- **Proposed fix:** Fixture upgrade F1 from coverage plan §2.1, verbatim: `breakWith` closes the receive channel **without** a cause and flips `state` to `Closed` (matching every shipped transport); peer-side `close()` propagates to the partner (partner state → `Closed`, partner writes then fail); add a pair-level `hangUp(side)` helper; keep an opt-in `breakWithException` for tests that deliberately exercise the defensive `routeEvents` failure branch. Suites currently passing via the unrealistic signature are updated deliberately (no assertion relaxation — where a test asserted the defensive branch, it switches to `breakWithException` explicitly).
- **Required tests:** F1 unblocks P1-01 and P1-02 (Group D) plus a regression that `observeRawState` fires on remote close; add a small fixture-fidelity self-test documenting the contract ("read completes normally and state flips, like the shipped transports"). Ships together with the other fixture upgrades F2–F5/F7–F9 (write-fault injection, `FakeDataTransport.failIncoming`, discovery-buffer parity, start-contract knob, `RecordingLogger`, fixture-state sync, virtual-time migration).
- **Risk of change:** Low — test-code only; the risk is behavioral masking during the suite re-audit, handled by making any intentional use of the throwing path explicit (`breakWithException`).
- **Suggested commit grouping:** Group B — Shared test-fixture upgrade.
- **Open-decision dependency:** None (F6, the strictInvariants threading, is split out to Group M1 under decision #15).

#### Root-cause group: missing failure handling on the inbound accept path

#### CON-3 — Accept-loop failure propagates uncaught and permanently ends inbound acceptance

- **Finding ID:** CON-3
- **Severity:** High
- **Root cause:** When `ServerSocket.accept()` fails while the transport is not closed, the accept loop calls `close(e)` on its `callbackFlow` channel and breaks (`p2p-transport-lan/src/jvmMain/kotlin/dev/p2pkit/transport/lan/JvmLanDataTransport.kt:144-146`; Android twin `AndroidLanDataTransport.kt:130-137`) — so `incomingConnections()` terminates **with that cause**. The sole collector, `SessionManager.startAcceptingIncoming`, is `onEach { handleIncoming(it) }.launchIn(scope)` with no `catch`/completion handling (`SessionManager.kt:146-152`): the failure cancels the collector and escalates as an uncaught exception into the kit scope, which has no `CoroutineExceptionHandler` (`P2pKitImpl.kt:78-79`; ARCH-4) — on Android that reaches the default handler and terminates the host app. Either way, inbound connection acceptance is permanently over for the kit's lifetime.
- **Affected files:** `SessionManager.kt` (primary fix site — the collector); `P2pKitImpl.kt` (companion CEH); `JvmLanDataTransport.kt`/`AndroidLanDataTransport.kt` referenced (their `close(e)` contract is reasonable and stays).
- **Proposed fix:** Add `.catch { e -> logger.warn("inbound acceptance ended for ${transport.type}", e) }` (rethrowing CE) to the `startAcceptingIncoming` pipeline so an accept-loop failure is surfaced as a logged, typed-diagnostic event instead of a kit-scope escalation; define the post-failure behavior explicitly — minimal RC scope is "log + inbound stays down until the next transport `start()`/rebind re-serves the accept loop" (the `serverSocketFlow` nullable-StateFlow design already supports a later re-serve), with a bounded re-collect noted as a follow-up rather than smuggled in. Companion (Medium rider ARCH-4, recommended in the same commit as defense-in-depth): install a `CoroutineExceptionHandler` on the kit scope that logs instead of crashing the host process.
- **Required tests:** Coverage plan P1 row P1-04 (CON-3, TST-3): accept-loop failure → kit survives, failure surfaced, inbound behavior defined — commonTest half via `FakeDataTransport.failIncoming(cause)` (**blocked on F3**, Group B) + `p2p-transport-lan` jvmTest with a real `ServerSocket` closed under the loop.
- **Risk of change:** Low — additive failure handling on a path that today crashes or dies silently; no change to the happy path.
- **Suggested commit grouping:** Group F — Inbound accept-loop resilience.
- **Open-decision dependency:** None.

#### Root-cause group: missing resource-limit enforcement on inbound connection setup

#### SEC-1 — No admission control on inbound connection setup

- **Finding ID:** SEC-1
- **Severity:** High ([API-CHANGE-if-surfaced])
- **Root cause:** Nothing bounds inbound-session admission: `startAcceptingIncoming` collects every accepted connection (`SessionManager.kt:146-152`), `handleIncoming` unconditionally launches one setup coroutine per connection (`:198-215`), and `runHandshake` allocates a 256-slot `Channel<ProtocolEvent>` plus a reader job per connection **before** the handshake completes (`:300-313`). The 10 s handshake timeout bounds each individual setup but not their number, and there is no cap on total registered sessions. A non-conforming peer opening many connections (or many peers at once) drives unbounded concurrent pre-handshake work and unbounded session count — fd/coroutine/heap growth without a limit. Transport-side accept queues are bounded (64, drop-and-close) on JVM/Android, which throttles burst delivery but not sustained admission; iOS's inbound queue is `Channel.UNLIMITED` (CON-9, Low, tracked separately).
- **Affected files:** `SessionManager.kt` (admission points), `SessionStore.kt` (session-count bound), `Handshake.kt:47-54` referenced; `Config.kt` only if decision #9 surfaces the caps as configuration.
- **Proposed fix (shape, pending decision #9):** Two internal caps, both enforcement-with-diagnostics: (1) a `Semaphore` bounding concurrent pre-handshake setups — `handleIncoming` acquires with `tryAcquire` and on refusal closes the connection immediately with a warn log (nothing allocated yet), suggested initial bound 16; (2) a max-total-active-sessions bound checked in the store's admission path before registering an incoming session, suggested initial bound 64, excess connections closed post-refusal with a typed diagnostic. Both as internal constants (no public API change); surfacing them as builder configuration is the `[API-CHANGE]` variant that decision #9 must approve. Cap values are proposals for the decision, not conclusions.
- **Required tests:** Coverage plan P1 row P1-26 (SEC-1): K sockets that never send HELLO leave the kit responsive (outbound + one legitimate inbound still succeed), fd/session count bounded, no uncaught exception in the kit scope (`p2p-transport-lan` jvmTest). P2 companion: N inbound connections with distinct peerIds → active sessions capped (SEC-1(b), commonTest).
- **Risk of change:** Medium — introduces refusal behavior on the inbound path (a conforming mesh larger than the session cap would be affected, hence the decision gate on values/surface); pre-handshake gating itself is low-risk since refused connections have no session state yet.
- **Suggested commit grouping:** Group M4 — Inbound admission control (awaiting decision).
- **Open-decision dependency:** Decision **#9** (cap policy: internal constants vs configuration surface; cap values).

#### Root-cause group: public API contract gaps (data + error contracts)

#### API-1 — `P2pMessage.metadata` accepted by the API but silently dropped on the wire

- **Finding ID:** API-1
- **Severity:** High
- **Root cause:** Both `P2pMessage.Text` and `P2pMessage.Binary` carry a public `metadata: Map<String, String>` (`p2p-core/src/commonMain/kotlin/dev/p2pkit/core/P2pMessage.kt:16-24`), but the send path destructures only bytes/isText — `Chunker.chunk` reads `message.value`/`message.bytes` and nothing else (`Chunker.kt:29-31`) — and the receive path reconstructs with the `emptyMap()` default (`Reassembler.kt:182-184`, `decodePayload`). Metadata a caller attaches is silently lost end-to-end: public-API data loss with no error and no doc statement (spec-side gap tracked as DOCA-15).
- **Affected files:** Depends on the option chosen: (c) doc-only → `P2pMessage.kt` KDoc + `P2pKit-Spec.md` §9.4; (a) wire it → `Chunker.kt`, `Reassembler.kt`, `Frame`/payload envelope encoding + spec §13; (b) deprecate → `P2pMessage.kt` (public API change).
- **Proposed fix (three options for decision #3):** (a) **Wire it** — serialize metadata in a DATA-payload envelope. This changes the DATA payload encoding: the PP2K header/frame types stay untouched and the codec lives in commonMain (all three platforms share it — no per-platform mirroring needed), but it is a cross-**version** interop change (a v-next sender to a current receiver) and needs a deliberate compatibility stance; wrong scope for a stabilization RC. (b) **Deprecate/remove** the parameter — public API change, locked by `P2pKit-Spec.md`. (c) **Document "not transmitted in protocol v1"** — KDoc + spec §9.4 statement + a test pinning the receive side as asserted-empty; zero code risk. **Recommendation: (c) for the RC line**, with (a) recorded as the metadata milestone; DOCA-14's ask (an explicit decision box in the C3 RC sign-off checklist) is satisfied by whichever option is recorded.
- **Required tests:** Coverage plan P1 row P1-06 (API-1, DOCA-15): metadata receive-side contract pinned — round-trip equality if transmitted, or asserted-empty + documented if dropped, per the decision (Chunker/Reassembler round-trip in commonTest; loopback variant).
- **Risk of change:** Option-dependent — (c) Low (doc + test only); (a) Medium/High (payload-encoding change with cross-version interop obligations); (b) Medium (public API surface). This is exactly why it is decision-gated.
- **Suggested commit grouping:** Group M5 — `P2pMessage.metadata` contract (awaiting decision).
- **Open-decision dependency:** Decision **#3** (wire / deprecate / document; plus the C3 checklist decision box per DOCA-14).

#### API-2 — `send()` leaks raw platform exceptions instead of typed `P2pError.ConnectionFailed`

- **Finding ID:** API-2 (canonical; duplicate SES-2 collapsed into it)
- **Severity:** High
- **Root cause:** `P2pSessionImpl.send()` types only its pre-check — `throw P2pError.ConnectionFailed(...)` when not `Connected` (`P2pSessionImpl.kt:235-238`) — then calls `protocol.sendMessage(connection, message)` unwrapped (`:239-241`). The write path throws raw platform exceptions to the app: `JvmRawConnection.write` throws `IOException` (including the watchdog-timeout `IOException`, `JvmRawConnection.kt:116-137`); iOS throws its own exception shapes (`IosRawConnection.kt:190-353`); Android mirrors JVM. `Errors.kt:6-13` and the spec document typed `P2pError` for the hottest API call; exception types additionally diverge per platform (typed-error facet of CON-6 consolidated here). `sendFile`'s offer write has partial wrapping in the dispatcher, but `send()` has none.
- **Affected files:** `P2pSessionImpl.kt` (fix site: `send()`/`sendFile()` boundary); `Errors.kt` KDoc; platform `RawConnection`s referenced (no change — the wrapping belongs at the public-API boundary, not the transport).
- **Proposed fix (pending decision #12):** At the session public-API boundary, wrap the send path: rethrow `CancellationException` and existing `P2pError` as-is; wrap any other `Throwable` in `P2pError.ConnectionFailed(reason = ..., underlying preserved as cause/message)`. Doing it in `P2pSessionImpl.send()` (not in `DefaultP2pProtocol.writeFrame`) keeps internal callers (keep-alive, dispatcher) seeing raw exceptions where their logic expects them, and confines the observable change to the documented public contract. Note: a standing deferral existed for this (A-G2-core-internal-14), but the campaign re-assessed it as unsound to carry into an RC — the decision is precisely whether this lands pre-tag.
- **Required tests:** Coverage plan P1 row P1-05 (API-2, SES-2, TST-2): `send()` on a failing connection surfaces `P2pError.ConnectionFailed` (never raw `IOException`/ISE), single- and multi-chunk; variant where `rearmWith` swaps the connection between state check and write — **blocked on F2** (write-fault injection fixture, Group B).
- **Risk of change:** Medium — app-observable error-shape change (apps catching `IOException` today would need `P2pError`); this is the register's own reason for gating it on decision #12 rather than landing it silently.
- **Suggested commit grouping:** Group M2 — Typed send() error contract (awaiting decision).
- **Open-decision dependency:** Decision **#12** (whether the typed-error wrapping lands before the RC tag).

#### Root-cause group: file-transfer terminal-path gaps

#### FIL-1 — `sendFile` source-close watcher cancelled before it can close the source

- **Finding ID:** FIL-1
- **Severity:** High
- **Root cause:** `sendFile` takes ownership of the caller's `RawSource` (KDoc contract: "kit closes it … callers must not close it") and implements that ownership as a plain watcher coroutine — `scope.launch { handle.state.first { it.isTerminal() }; runCatching { source.close() } }` (`p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/FileTransferDispatcher.kt:141-144`). `P2pSessionImpl.close()` → `transitionToTerminal` (`P2pSessionImpl.kt:291-301`) cancels the dispatcher's transfers/scope; the watcher is cancelled **before** it observes the handle's terminal state, so the source is never closed — a contract-violating `RawSource`/fd leak, deterministic on single-threaded event loops and racy on `Dispatchers.Default`.
- **Affected files:** `FileTransferDispatcher.kt` (watcher + `closeAll`/terminal-transition sites); `OutgoingFileTransferImpl` (close-once guard).
- **Proposed fix:** Stop relying on a cancellable watcher for a must-run cleanup: close the source **at the terminal-transition sites themselves**, under dispatcher control — add an idempotent close-once guard on the outgoing handle (CAS flag) invoked from `closeAll`'s per-transfer teardown, `markFailed`, and the terminal `setState` paths; keep the watcher as a backstop for externally-observed terminal states (or convert it to `invokeOnCompletion`-based cleanup that runs on cancellation too). Fold in the FIL-6 Medium rider (same asymmetry family): add the closed re-check **under the lock** in `sendFile` before insert/emit, mirroring the #16 fix's `onFileOffer` shape, so a `sendFile` racing `closeAll` cannot mint a handle that never terminalizes (which would also orphan its source).
- **Required tests:** Coverage plan P1 row P1-20 (FIL-1, FIL-6): outgoing file source closed **exactly once** on every terminal path — complete, reject, cancel-before/after-accept, offer-write failure, `session.close()` / `kit.stop()` mid-stream, rearm `closeAll` — with idempotency asserted (FileTransferFlowTest, close-tracking fake `RawSource`).
- **Risk of change:** Low/Medium — confined to the dispatcher's teardown paths; the close-once CAS keeps double-close impossible; broad terminal-path test matrix lands in the same commit.
- **Suggested commit grouping:** Group H — File-transfer terminal-path robustness.
- **Open-decision dependency:** None.

#### FIL-2 — Sender-side source read failure never notifies the receiver

- **Finding ID:** FIL-2
- **Severity:** High
- **Root cause:** `streamOutgoingPayload`'s failure branch marks the local handle `Failed` and removes the entry but sends nothing to the peer: `catch (e: Throwable) { … handle.markFailed(err); lock.withLock { outgoing.remove(...) }; logger.warn(...) }` (`FileTransferDispatcher.kt:582-587`). Contrast the receiver-side failure path, which sends a best-effort `FILE_CANCEL` (`:450-458`). `streamFileData` throws when the source read fails or the source is shorter than `sizeBytes` (`StreamingFileSender.kt:15-16, :40`). Result: the receiver of an already-accepted transfer waits indefinitely for FILE_DATA/FILE_DONE that will never come — compounded by FIL-3 (no post-accept inactivity timeout, Medium, tracked separately).
- **Affected files:** `FileTransferDispatcher.kt` (`streamOutgoingPayload` catch branch).
- **Proposed fix:** Mirror the receiver path: in the catch branch, after `markFailed`, best-effort-send `FILE_CANCEL(transferId, reason = "sender source failure")` under `sendMutex`, wrapped so a dead wire cannot turn the cleanup into a second failure (`runCatching` with CE rethrown — same CE-safety shape the 7854ca7 fix gave the dispatcher's other best-effort sends). Distinguish the two failure classes: if the streaming failure was itself a connection-write failure, skip the send (the wire is gone and session-level teardown handles the peer); if it was a source-read failure on a healthy connection, the FILE_CANCEL must go out and the session must stay `Connected` (transfer-failure-isolation invariant). No wire-format change — `FILE_CANCEL` is an existing PP2K frame type encoded in shared commonMain code.
- **Required tests:** Coverage plan P1 row P1-21 (FIL-2): sender-side source read failure (throws mid-stream / shorter than `sizeBytes`) → sender `Failed`, receiver reaches a terminal state within a bound, `FILE_CANCEL` recorded on the wire, session stays `Connected` (commonTest E2E + direct-dispatcher with RecordingFileProtocol).
- **Risk of change:** Low — additive control frame on an existing type; failure isolation asserted by the new test.
- **Suggested commit grouping:** Group H — File-transfer terminal-path robustness.
- **Open-decision dependency:** None.

#### Root-cause group: discovery steady-state gap (JVM/Android heartbeat absence)

#### DSC-1 — JVM/Android discovered peers evicted after 15 s and never return in steady state

- **Finding ID:** DSC-1
- **Severity:** High (reporter: borders Critical for discovery UX)
- **Root cause:** `PeerRegistry.evictStalePeers()` removes any non-manual entry with `now - lastSeenAtMillis > staleTimeoutMillis` (`PeerRegistry.kt:95-106`), polled every second against `DEFAULT_STALE_TIMEOUT_MS = 15_000` (`:169-170`). Only a fresh `Found`/`Updated` event re-stamps `lastSeen` (`:82-83`). The JVM and Android discovery transports emit `Found` only when JmDNS fires `serviceResolved` — effectively once per service appearance — and `Lost` on removal (`JvmLanDiscoveryTransport.kt:123-188`; `AndroidLanDiscoveryTransport.kt:514-584`); nothing re-emits for an unchanged, healthy peer. Only iOS has a heartbeat (the 5 s re-announce loop, `PEER_REANNOUNCE_INTERVAL_MS`, `IosLanDiscoveryTransport.kt:688`, added by AUDIT-2026-06 for exactly this defect). Net: on JVM/Android, `kit.peers` silently empties ~15 s after resolution and stays empty in steady state.
- **Affected files:** Mechanism-dependent (decision #14): recommended option touches `JvmLanDiscoveryTransport.kt` + `AndroidLanDiscoveryTransport.kt` only; alternatives touch `PeerRegistry.kt` / core semantics.
- **Proposed fix (pending decision #14):** Recommended mechanism — **mirror the iOS pattern on JVM/Android**: while discovery is active, a transport-side loop re-emits `PeerEvent.Updated` for every currently-cached, appId-matching JmDNS service every ~5 s, reading from the JmDNS in-process cache (`list()`-free, no forced network re-query — this must not disturb the deliberate B:317 deferral of the 200 ms `list()` snapshot behavior in `refresh()`). This keeps `PeerRegistry` semantics uniform across platforms and requires no core change. Alternatives for the decision: registry-side TTL refresh via periodic `refresh()` (multicast-noisier), or eviction-exempt discovered peers (changes `kit.peers` liveness semantics on all platforms — not recommended). Cross-platform `kit.peers` meaning is defined by this choice, which is why it is RC-gated.
- **Required tests:** Coverage plan P1 row P1-13 (DSC-1): JVM/Android discovered peer remains in `kit.peers` at t = 20 s and 35 s idle with no connect activity (`p2p-transport-lan` jvmTest loopback) + a commonTest contract test that a `DiscoveryTransport` must re-emit within the stale timeout (FakeDiscoveryTransport contract). The two-CLI 20 s idle run named in register §5 remains the end-to-end demonstration.
- **Risk of change:** Medium — new periodic emission on two platforms (registry churn is de-noised by `publishPeers`'s equality check, `PeerRegistry.kt:92`; the P2 de-noising row pins that); no wire or TXT change.
- **Suggested commit grouping:** Group M3 — JVM/Android discovery heartbeat (awaiting decision).
- **Open-decision dependency:** Decision **#14** (heartbeat mechanism choice).

#### Root-cause group: inert test-safety-net wiring

#### TST-9 — The e91e094 `strictInvariants` safety net is inert in every kit-level suite

- **Finding ID:** TST-9 (canonical; duplicate SES-8 collapsed into it)
- **Severity:** High
- **Root cause:** `SessionManager`'s `strictInvariants: Boolean = false` parameter (`SessionManager.kt:109`, KDoc: "\[P2pKitImpl\] never sets it") is forwarded to `SessionStore` (`:119`), where violations throw only under the flag and otherwise `logger.warn` (`SessionStore.kt:272-277`). The only production construction site — `P2pKitImpl.kt:153-184` — never passes it, and the behavioral suites run NoOp/quiet loggers, so a store-bookkeeping regression warns into the void and passes every kit-level test silently. The safety net restored by commit e91e094 protects only its own unit test.
- **Affected files:** `SessionManager.kt` / `P2pKitImpl.kt` (internal-only threading), commonTest infrastructure (suite construction path / TestHooks), plus one meta-test.
- **Proposed fix (pending decision #15):** Fixture change F6, verbatim from coverage plan §2.1: thread an internal-only knob (internal constructor parameter or a commonTest `TestHooks` object) so kit-level suites construct `SessionManager(strictInvariants = true)`; every existing behavioral suite then doubles as an invariant net. Add a meta-test proving a violation inside a kit-built store throws under the flag. Explicitly **no public API change** — the decision is approval of the internal wiring mechanism only. Companion (from F7, lands with Group B): promote `RecordingLogger` to `testfixtures/` so warn-mode diagnostics are assertable where strict mode is not used.
- **Required tests:** Coverage plan P1 row P1-03 (TST-9, SES-8): kit-level behavioral suites run with `strictInvariants = true`; meta-test that a violation inside a kit-built store throws under the flag — **blocked on F6**.
- **Risk of change:** Low — test-infrastructure wiring behind an internal flag; production default (`false`, warn-only) is untouched. The one real risk is desirable: latent store-invariant violations in existing suites surface immediately and must be triaged, not silenced.
- **Suggested commit grouping:** Group M1 — strictInvariants suite wiring (awaiting decision). If decision #15 is granted at plan review (it is approval-only), fold M1 into Group B so the whole fixture upgrade lands as one commit.
- **Open-decision dependency:** Decision **#15** (approve the internal-only wiring mechanism).

#### Root-cause group: build/release tooling defects

#### IOSB-3 — run-ios-app.sh can install a stale app bundle from another checkout

- **Finding ID:** IOSB-3
- **Severity:** High
- **Root cause:** `scripts/run-ios-app.sh` invokes `xcodebuild` without `-derivedDataPath` (`:35-44`), so the build lands in global DerivedData; it then locates the bundle with `find "$DERIVED_DATA_BASE" -name 'p2pkit-sample.app' -path '*Debug-iphonesimulator*' -print -quit` (`:47-50`) — the **first** match in arbitrary filesystem order anywhere in global DerivedData. With more than one checkout/worktree (this repo actively uses worktrees), the script can silently install and launch a stale bundle from a different tree, invalidating any manual verification or smoke-matrix result obtained through it.
- **Affected files:** `scripts/run-ios-app.sh`; `docs/STABILIZATION_AND_RELEASE.md` / `INTERNAL_TESTING.md` (provenance note); adjacent same-file Mediums IOSB-1 (dead FATAL path under `set -e`) and IOSB-2 (unescaped `SIM_NAME` ERE) are natural riders since the diff is the same 40 lines — include them if trivially safe, otherwise leave catalogued.
- **Proposed fix:** Pass a repo-local `-derivedDataPath` (e.g. `"$PROJECT_DIR/build/DerivedData"`) to `xcodebuild` and resolve the app path deterministically under it (fixed `Build/Products/Debug-iphonesimulator/p2pkit-sample.app` path, or `xcodebuild -showBuildSettings`/`TARGET_BUILD_DIR`); fail loudly if absent. Optionally add a post-install provenance check (bundle's build stamp vs current HEAD — dovetails with the adca586 check-xcframework stamp work).
- **Required tests:** Coverage plan P1 rows P1-31 (IOSB-3: manual verification that the installed bundle is the one THIS build produced — `simctl get_app_container` resolves under the invoking checkout's DerivedData; note added to `INTERNAL_TESTING.md`) and P1-30 (related provenance gate: post-build grep that the built .app's Info.plist contains `NSBonjourServices` `_p2pkit._tcp` + `NSLocalNetworkUsageDescription` — guarding the documented zero-discovery failure mode; wired into check-xcframework.sh / run-ios-app.sh).
- **Risk of change:** Low — build script only; needs one macOS `./gradlew :iosApp:runIosSimulator` pass to verify; no SDK code touched.
- **Suggested commit grouping:** Group K — iOS build provenance.
- **Open-decision dependency:** None.

#### BLD-2 — Javadoc-jar requirement satisfied on only 1 of 4 publishable modules

- **Finding ID:** BLD-2
- **Severity:** High
- **Root cause:** Maven Central requires a javadoc jar per publication. Grep across the four library modules confirms wiring exists only in `p2p-network-provisioning-desktop/build.gradle.kts:14` (`withJavadocJar()`); `p2p-core`, `p2p-transport-lan`, and `p2p-network-provisioning-android` have none (their publishing blocks at `p2p-core/build.gradle.kts:118-143`, `p2p-transport-lan/build.gradle.kts:139-164`, `p2p-network-provisioning-android/build.gradle.kts:34-62` configure POMs but no javadoc artifact). `docs/STABILIZATION_AND_RELEASE.md:76-77` claims KMP modules "get theirs automatically" — the claim is unverified and, per current KGP behavior, presumed wrong. Release-readiness defect: the RC checklist's publish gate cannot pass for 3 of 4 modules.
- **Affected files:** Root `build.gradle.kts` (preferred single wiring point, where signing/publishing conventions already live) or the three module build files; `docs/STABILIZATION_AND_RELEASE.md:76-77, :99-104`.
- **Proposed fix:** Step 1 (closes the register's named residual): run `./gradlew publishToMavenLocal && ls ~/.m2/repository/dev/p2pkit/*/0.6.0/` and record whether KGP auto-attaches javadoc jars. Step 2 (expected): add an empty-javadoc-jar convention (the accepted Central practice for Kotlin modules; Dokka optional later) to every KMP/Android publication in the root build so all four modules publish `-javadoc.jar` alongside `-sources.jar`. Step 3: correct the release-doc claim either way. Keyless signing behavior (Sign tasks SKIPPED without a key) must remain intact.
- **Required tests:** Coverage plan P1 row P1-29 (BLD-2): a `scripts/` verification script, invoked by the release recipe, asserting `publishToMavenLocal` produces the full Central artifact set per module (jar/klib/aar, `-sources`, `-javadoc`, `.pom`, `.module`) — turning the RC checklist item into an executable gate.
- **Risk of change:** Low — publishing wiring only, no runtime code; verified end-to-end by the new script against mavenLocal.
- **Suggested commit grouping:** Group J — Publishing readiness.
- **Open-decision dependency:** None.

#### Root-cause group: stale documentation of record

#### DOCB-1 — AUDIT_REPORT "Deferred (39)" list is heavily stale and maintenance-steering

- **Finding ID:** DOCB-1
- **Severity:** High
- **Root cause:** `AUDIT_REPORT_2026-06.md:60-86` still presents its deferred list as open while at least 10 of 16 deferred bullets were since implemented on this branch — re-verified directly for this plan: the permission-manager builder knob (shipped, public `permissionManager` knob per `Builders.kt`), `registerManualPeer` dedupe (shipped in `b9f6311`; confirmed at `PeerRegistry.kt:118-131`), the `JvmRawConnection` write deadline (30 s watchdog shipped in `f4dd3a9`; confirmed `WRITE_TIMEOUT_MILLIS` at `JvmRawConnection.kt:206`), the `~/.p2pkit` path decision (resolved in code), and 4-module publishing (all four wired). `CLAUDE.md` routes every future agent to this list as the check-before-fixing source of truth, so the staleness actively mis-steers maintenance (an agent could re-implement shipped work or trust a dead deferral).
- **Affected files:** `AUDIT_REPORT_2026-06.md` (annotation pass); companion Mediums in the same doc family — DOCB-2 (the C1 fix description now states the opposite of current manual-peer behavior post-012e49e) and CLAUDE.md's pointer language — are natural riders; `PROBLEMS_P2PKIT.md` staleness (DOCB-4/5) can ride or follow as the same mechanical pattern.
- **Proposed fix:** Annotate, do not rewrite: add a dated status marker to every deferred bullet — `[IMPLEMENTED @ <commit>]`, `[STILL OPEN]`, or `[SUPERSEDED by <finding/decision>]` — with a one-line header note dating the annotation pass; correct the DOCB-2 C1 description to match the shipped keep-dialed-identity behavior. Genuinely-still-deferred items (inbound HELLO peerId → encryption milestone; interface selection / iOS AWDL → hardware diagnosis; B:317) are explicitly marked `[STILL OPEN — deliberate]` so the deliberate deferrals stay visible. Adopt the coverage plan's P2 process rule (annotate the audit line whenever an audit item is fixed) as a CLAUDE.md convention so the list cannot rot again.
- **Required tests:** n/a (documentation); the P2 `check-doc-signatures.sh` script row is the automation follow-up, not required for this group.
- **Risk of change:** Low — documentation only; no code, no markers removed (marker comments in code untouched).
- **Suggested commit grouping:** Group L — Documentation of record refresh.
- **Open-decision dependency:** None (decisions #1/#2 concern adjacent docs — `P2PKIT_GAP_ANALYSIS_2026-07.md` disposition and the uncommitted CLAUDE.md — and can ride along if approved, but DOCB-1 itself is not gated).

## 4. Part 2 — P1 test coverage gaps (32 items + fixture work item)

All 32 P1 rows from `TEST_COVERAGE_PLAN_2026-07.md` §3.1, in table order, minted here as P1-01…P1-32. The shared-fixture upgrade is listed first as its own work item (P1-00) because 5 of the 32 P1 rows (and 14 coverage-plan rows overall) are strictly blocked on it. Rows marked "lands with group X" are the required tests of a Part-1 fix and are not scheduled twice. Three P1 rows presuppose Medium fixes as riders (noted inline): P1-14 (DSC-3/DSC-13 assertions), P1-22 (FIL-4 guard), P1-32 (SMP-1 helper).

**P1-00 — Shared test-fixture upgrade (the prerequisite work item).** Fixture changes F1–F9 from coverage plan §2.1: F1 `FakeRawConnection` remote-termination fidelity; F2 write-fault injection; F3 `FakeDataTransport.failIncoming(cause)`; F4 `FakeDiscoveryTransport` production-shaped buffers; F5 `FakeDataTransport` start-contract/close-visibility; F6 internal `strictInvariants` threading (**split to Group M1, decision #15**); F7 `RecordingLogger` promotion; F8 fixture-state synchronization; F9 virtual-time migration. Location: `p2p-core/src/commonTest/.../testfixtures/` (+ internal wiring for F6). Commit group: **B** (F6 → M1). Unblocks P1-01, P1-02, P1-03 (F6), P1-04 (commonTest half), P1-05; materially aids later P2 rows. The §2.2 product-side seams (JmDNS factory, injectable watchdog timeout, extracted TXT/prune helpers) are scheduled in Groups A and I where their tests live.

| ID | What it covers | Test file / location | Blocked on fixture upgrade? | Commit group | Related finding ID(s) | Decision dependency |
|---|---|---|---|---|---|---|
| P1-01 | Remote abrupt raw termination (EOF/reset, no CLOSE) with `ReconnectPolicy.Enabled` → deterministic `Reconnecting`; `observeRawState` fires on remote close; incoming EOF → deterministic `Failed` | p2p-core commonTest (ReconnectPolicyTest / SessionFlowTest) | **Yes — F1** | lands with Group D | SES-1, SES-10, TST-1, CON-7 | None |
| P1-02 | Remote CLOSE frame → exactly `Closed`, never `Failed`; dial factory never re-invoked; tighten SessionFlowTest.kt:222-231 to exact state; CLOSE-then-socket-close stress variant | p2p-core commonTest (SessionFlowTest + ReconnectPolicyTest) | Partial — strict assertion now, race variant F1 | lands with Group D | SES-1, TST-11 | None |
| P1-03 | Kit-level behavioral suites run `strictInvariants = true`; meta-test that a violation in a kit-built store throws | p2p-core commonTest infra | **Yes — F6** | lands with Group M1 | SES-8, TST-9 | **#15** |
| P1-04 | Accept-loop failure → kit survives, failure surfaced, inbound behavior defined | p2p-core commonTest (**F3**) + p2p-transport-lan jvmTest (real ServerSocket closed under loop) | **Yes — F3** (commonTest half) | lands with Group F | CON-3, TST-3, ARCH-4-adjacent | None |
| P1-05 | `send()` on failing connection surfaces `P2pError.ConnectionFailed` (never raw IOException/ISE), single-/multi-chunk; rearm-swap variant | p2p-core commonTest (SendErrorContractTest / SessionFlowTest) | **Yes — F2** | lands with Group M2 | API-2, SES-2, TST-2 | **#12** |
| P1-06 | `P2pMessage.metadata` receive-side contract pinned (round-trip or asserted-empty per decision) | p2p-core commonTest (Chunker/Reassembler round-trip; loopback variant) | No | lands with Group M5 | API-1, DOCA-15 | **#3** |
| P1-07 | P2pState machine: Idle→Starting→Running; bind failure→Failed; failed start does not latch; re-advertise clears Failed | p2p-core commonTest (KitLifecycleTest) | No | lands with Group G | A01 §3 r1 | None |
| P1-08 | Cancelling `kit.start()` mid-bind: state NOT `Failed`, CE (not `TransportStartFailed`) propagates, subsequent `start()` succeeds | p2p-core commonTest (KitLifecycleTest, hung-start fake) | No | lands with Group G | ARCH-1 | None |
| P1-09 | `stop()` bounded when a fake observer's `start()` hangs and `close()` blocks; cancelled stop caller still closes the observer | p2p-core commonTest (KitLifecycleTest, fake observer) | No | lands with Group G | ARCH-2 | None |
| P1-10 | Manual peers exempt from staleness eviction (survive `evictStalePeers` after clock advance) | p2p-core commonTest (PeerRegistryTest) | No | C | A04 §3 r1 | None |
| P1-11 | `registerManualPeer` dedupes by (host, port, kind); repeat returns same `Peer`/id; new endpoint mints new id | p2p-core commonTest (PeerRegistryTest) | No | C | IDN-5 | None |
| P1-12 | JVM legacy migration `<root>/p2pkit` → `<root>/.p2pkit` adopts and re-persists the old id | p2p-core jvmTest (FilePeerIdStorageTest) | No | C | A04 §3 r3 | None |
| P1-13 | JVM/Android discovered peer remains in `kit.peers` at 20 s / 35 s idle; DiscoveryTransport re-emit contract test | p2p-transport-lan jvmTest loopback + p2p-core commonTest | No | lands with Group M3 | DSC-1 | **#14** |
| P1-14 | Android JmDNS rebind machinery: intent flags vs handles, create-retry bounds, restore-failure repair, cancelled create closes handle, failed `start*` releases handle + multicast lock | seamed JmDNS factory → androidHostTest or jvm-style unit (**needs §2.2 seam**) | No (needs product seam; rider fixes DSC-3/DSC-13 asserted) | I | DSC-3, DSC-4, DSC-5, DSC-13 | None |
| P1-15 | Real 30 s write watchdog at transport level: wedged socket write → IOException, `socket.isClosed`, state Closed (real `JvmRawConnection`) | p2p-transport-lan jvmTest (**needs injectable timeout seam**, §2.2; mirrored JVM/Android) | No (needs product seam) | I | CON-14 | None |
| P1-16 | `close()` from an already-cancelled coroutine still releases the fd; cancelled read collector + remote close → `socket.isClosed` | p2p-transport-lan jvmTest | No | lands with Group E | CON-1 | None |
| P1-17 | Declared `payload_len` > `MAX_FRAME_PAYLOAD_BYTES` → immediate `ProtocolError`, no buffering (FrameReader) + decode rejection (FrameCodec) | p2p-core commonTest (FrameReaderTest + FrameCodecTest) | No | C | A07 §3 r1 | None |
| P1-18 | `HelloPayload.decode` input-validation guards: malformed JSON, missing fields, blank ids, 513-char fields, 33 transports, over-limit `platform`/per-transport strings | p2p-core commonTest (HelloPayloadTest) | No | C | PRO-4, SEC-I2 | None |
| P1-19 | Malformed HELLO / FILE_OFFER frame skipped (warn) and events flow keeps delivering subsequent frames | p2p-core commonTest (DefaultP2pProtocolTest / FileTransferProtocolTest) | No | C | A07 §3 r3 | None |
| P1-20 | Outgoing file source closed exactly once on EVERY terminal path (complete, reject, cancel-before/after-accept, offer-write failure, close/stop mid-stream, rearm closeAll; idempotency asserted) | p2p-core commonTest (FileTransferFlowTest, close-tracking fake RawSource) | No | lands with Group H | FIL-1, FIL-6 | None |
| P1-21 | Sender-side source read failure: sender `Failed`, receiver terminal within a bound, FILE_CANCEL on the wire, session stays Connected | p2p-core commonTest (E2E + direct-dispatcher, RecordingFileProtocol) | No | lands with Group H | FIL-2 | None |
| P1-22 | Duplicate FILE_ACCEPT ignored: one streamer, chunks 0..n-1 once, one FILE_DONE, no state regression, exact `bytesTransferred` | p2p-core commonTest (direct-dispatcher) | No (**requires FIL-4 rider fix**) | H | FIL-4 | None |
| P1-23 | Oversize offer never surfaces on `incomingFiles` — real subscriber assertion replacing the current no-op `assertSubscriberSeesNoOffer` | p2p-core commonTest (FileTransferFlowTest) | No (test repair — FIL-11) | H | FIL-11 | None |
| P1-24 | Session close mid-transfer: both sides' transfer handles reach terminal states (no awaiter hang) | p2p-core commonTest | No | H | A08 §3 r5 | None |
| P1-25 | Blank/empty/whitespace TXT `pid` on found AND removed paths never throws out of a discovery callback (no bogus event, no process crash, no worker death); unit leg for the extracted parser | p2p-transport-lan iosSimulatorArm64Test + jvmTest loopback + commonTest unit (parser helper, §2.2) | No | lands with Group A | RBS-1, API-17 | None |
| P1-26 | Inbound admission control: K never-HELLO sockets → kit responsive, fd/session count bounded, no uncaught kit-scope exception | p2p-transport-lan jvmTest | No | lands with Group M4 | SEC-1 | **#9** |
| P1-27 | Provisioning `parentJob` cancellation closes hotspot reservation + join binding; post-cancel start refused | p2p-network-provisioning-android androidHostTest | No | C | PRM-10, A09 §3 r2 | None |
| P1-28 | Join release closes the JoinHandle (`lastJoinHandle.isClosed`) | p2p-network-provisioning-android androidHostTest (extend existing system-initiated-release test) | No | C | A09 §3 r3 | None |
| P1-29 | `publishToMavenLocal` produces the full Central artifact set per module (jar/klib/aar, -sources, -javadoc, .pom, .module) | scripts/ verification script invoked by the release recipe | No | lands with Group J | BLD-2 | None |
| P1-30 | Built .app's Info.plist contains `NSBonjourServices` `_p2pkit._tcp` + `NSLocalNetworkUsageDescription` (post-build grep) | check-xcframework.sh / scripts/run-ios-app.sh | No | lands with Group K | IOSB-9, A10 §3 r1 | None |
| P1-31 | run-ios-app.sh installs the bundle produced by THIS build (`simctl get_app_container` under the invoking checkout's DerivedData) | manual verification + note in INTERNAL_TESTING.md | No | lands with Group K | IOSB-3 | None |
| P1-32 | Incoming-file destination uniquification in samples: two same-named offers → distinct paths, no overwrite/interleave | small JVM unit for the shared helper (+ manual two-offer recheck per INTERNAL_TESTING) | No (**requires SMP-1 rider fix** in desktop-ui) | C | SMP-1 | None |

Row count: 32 (P1-01…P1-32) + the P1-00 fixture work item. Manual/hardware rows among them: P1-31 (manual) and the manual halves of P1-30/P1-32, consistent with the coverage plan's 2 × P1 manual designation.

## 5. Commit grouping summary

Gate policy: `./gradlew :p2p-core:jvmTest` is the fast gate after **every** group; target-specific gates are added where the group touches transport/platform/build code. The `iosSimulatorArm64Test` gate is read as green when the **only** failures are the 2 documented known-flaky churn tests (`IosLanLifecycleTest.peerLostEventFiresWhenPeerStops`, `advertiseStopRestartProducesObservablePeerChurn`) — they are never masked or widened.

### Group A — Discovery-callback input validation
- **Items:** RBS-1 (Critical) + the extracted TXT-parse helper seam (§2.2) + P1-25.
- **Rationale:** One root cause (unvalidated TXT `pid` reaching `PeerId()`), one defect class, three platform files that must change identically in a single commit to preserve platform parity.
- **Gates:** `./gradlew :p2p-core:jvmTest` · `./gradlew :p2p-transport-lan:jvmTest` · `./gradlew :p2p-transport-lan:iosSimulatorArm64Test` (macOS) · `./gradlew :p2p-core:assemble :p2p-transport-lan:assemble`.

### Group B — Shared test-fixture upgrade
- **Items:** TST-1 (High) via F1; F2, F3, F4, F5, F7, F8, F9 (P1-00). F6 parked in M1 (decision #15) — folds back in if approved at plan review.
- **Rationale:** Test-code only, so it cannot break the product; it is the prerequisite for Groups D/F/M1/M2's tests (5 P1 rows, 14 plan-wide), so it must precede them; one commit keeps the fixture-contract change reviewable as a unit.
- **Gates:** `./gradlew :p2p-core:jvmTest` · `./gradlew :p2p-core:allTests` (all suites must still pass against the higher-fidelity fakes; any suite that relied on the unrealistic throwing signature is updated explicitly, never relaxed).

### Group C — P1 pinning tests (no SDK behavior change)
- **Items:** P1-10, P1-11, P1-12, P1-17, P1-18, P1-19, P1-27, P1-28, P1-32 (+ SMP-1 sample-side uniquification helper as the one code rider, sample-only).
- **Rationale:** Pure regression pinning of behavior that already exists at HEAD (registry exemptions, dedupe, migration, protocol caps and skip-not-throw policy, provisioning handle lifecycle) — landing it before the behavior-changing groups gives every later diff a wider safety net; grouped because none of it changes SDK behavior.
- **Gates:** `./gradlew :p2p-core:jvmTest` · `./gradlew :p2p-core:allTests` · `./gradlew :p2p-network-provisioning-android:testAndroidHostTest` · `./gradlew :p2p-network-provisioning-desktop:test`.

### Group D — Session remote-termination determinism
- **Items:** SES-1 (High) + P1-01, P1-02.
- **Rationale:** Single root cause (two racing classifiers of remote loss); the fix and its two deterministic-outcome tests are meaningless apart; depends on Group B (F1).
- **Gates:** `./gradlew :p2p-core:jvmTest` · `./gradlew :p2p-core:allTests` · `./gradlew :p2p-transport-lan:jvmTest` (loopback sanity over real TCP after the semantics change).

### Group E — Connection cancellation + fd release
- **Items:** CON-1 (High) + P1-16.
- **Rationale:** One root cause (`withContext` skipping cleanup on an already-cancelled caller) in the intentionally-duplicated JVM/Android pair — must land as one commit touching both files to keep the parity invariant auditable.
- **Gates:** `./gradlew :p2p-core:jvmTest` · `./gradlew :p2p-transport-lan:jvmTest` · `./gradlew :p2p-transport-lan:assemble` (Android target compile).

### Group F — Inbound accept-loop resilience
- **Items:** CON-3 (High) + ARCH-4 CEH rider (Medium, defense-in-depth) + P1-04.
- **Rationale:** One failure channel (accept-loop termination escalating uncaught into the kit scope); the collector `catch` and the kit-scope `CoroutineExceptionHandler` are the two halves of closing it; commonTest half depends on Group B (F3).
- **Gates:** `./gradlew :p2p-core:jvmTest` · `./gradlew :p2p-transport-lan:jvmTest` (real-ServerSocket half of P1-04).

### Group G — Kit lifecycle cancellation correctness
- **Items:** ARCH-1, ARCH-2 (Highs) + P1-07, P1-08, P1-09.
- **Rationale:** Same root cause family (CE mishandled in `P2pKitImpl` start/stop paths), same file, protected by the same new KitLifecycleTest rows — one reviewable lifecycle commit.
- **Gates:** `./gradlew :p2p-core:jvmTest` · `./gradlew :p2p-core:allTests`.

### Group H — File-transfer terminal-path robustness
- **Items:** FIL-1, FIL-2 (Highs) + riders FIL-4 (duplicate-accept guard, required by P1-22), FIL-6 (sendFile closed re-check, covered by P1-20), FIL-11 (no-op assertion repair, P1-23) + P1-20…P1-24.
- **Rationale:** One subsystem (`FileTransferDispatcher` terminal paths), one root-cause family (terminal-transition cleanup/notification gaps); the P1 test matrix spans all of them, so splitting the fixes would leave intermediate commits red or force weakened tests.
- **Gates:** `./gradlew :p2p-core:jvmTest` · `./gradlew :p2p-core:allTests`.

### Group I — Transport test seams + platform P1 tests
- **Items:** §2.2 seams (seamed `JmDNS.create`/handle factory; injectable write-watchdog timeout in `JvmRawConnection`/`AndroidRawConnection` — mirrored identically in both) + P1-14, P1-15 + riders DSC-3/DSC-13 (cancellation-safe `JmDNS.create` / failed-`start*` cleanup — the P1-14 assertions presuppose them; if the user prefers to defer these Mediums, P1-14's affected assertions are split out with them rather than weakened).
- **Rationale:** Behavior-preserving injection seams and the platform tests they enable; grouped because the seams have no purpose without the tests and vice versa.
- **Gates:** `./gradlew :p2p-core:jvmTest` · `./gradlew :p2p-transport-lan:jvmTest` · `./gradlew :p2p-transport-lan:assemble` (Android compile; androidHostTest if that source set is chosen per §2.2).

### Group J — Publishing readiness
- **Items:** BLD-2 (High) + P1-29 artifact-set script + release-doc correction.
- **Rationale:** Self-contained publishing wiring with its own executable gate; independent of every code group.
- **Gates:** `./gradlew publishToMavenLocal` + the new artifact-set verification script (all four modules) · `./gradlew :p2p-core:jvmTest` (fast sanity that build-file changes broke nothing).

### Group K — iOS build provenance
- **Items:** IOSB-3 (High) + P1-30 plist grep + P1-31 manual provenance note (+ IOSB-1/IOSB-2 riders if trivially safe).
- **Rationale:** One script, one provenance theme (run what you built, with the load-bearing plist keys present); requires a macOS verification pass, so batched together.
- **Gates:** manual `./gradlew :iosApp:runIosSimulator` on macOS (verify install path under the repo-local DerivedData; P1-30 grep passes) · `./gradlew :p2p-core:jvmTest`.

### Group L — Documentation of record refresh
- **Items:** DOCB-1 (High) + DOCB-2 rider + the CLAUDE.md annotate-on-fix process rule.
- **Rationale:** Doc-only; written after Groups A–K land so status annotations can cite the final commit hashes.
- **Gates:** none required (no code); `./gradlew :p2p-core:jvmTest` optional sanity.

### Tier M — awaiting decision (parked; never blocks A–L)

| Group | Items | Decision | Gates when it lands |
|---|---|---|---|
| M1 — strictInvariants suite wiring | TST-9 + F6 + P1-03 | #15 (approval-only — recommend deciding at plan review so M1 folds into Group B) | `:p2p-core:jvmTest` · `:p2p-core:allTests` |
| M2 — Typed send() error contract | API-2 + P1-05 (needs F2 from Group B) | #12 | `:p2p-core:jvmTest` · `:p2p-core:allTests` · `:p2p-transport-lan:jvmTest` |
| M3 — JVM/Android discovery heartbeat | DSC-1 + P1-13 | #14 | `:p2p-core:jvmTest` · `:p2p-transport-lan:jvmTest` (incl. the new 20 s/35 s idle loopback) · `:p2p-transport-lan:iosSimulatorArm64Test` (parity sanity — iOS loop untouched) |
| M4 — Inbound admission control | SEC-1 + P1-26 | #9 | `:p2p-core:jvmTest` · `:p2p-core:allTests` · `:p2p-transport-lan:jvmTest` |
| M5 — P2pMessage.metadata contract | API-1 + P1-06 | #3 | Option (c): `:p2p-core:jvmTest`; option (a): full matrix incl. `:p2p-transport-lan:jvmTest` + `iosSimulatorArm64Test` + cross-version interop consideration; option (b): `:p2p-core:allTests` + spec update |

Final sweep after the last group lands (whichever it is): `./gradlew :p2p-core:allTests :p2p-transport-lan:jvmTest :p2p-network-provisioning-android:testAndroidHostTest :p2p-network-provisioning-desktop:test` plus `:p2p-transport-lan:iosSimulatorArm64Test` on macOS — the same matrix REMEDIATION_2026-07.md used as its gate table.

## 6. Decision-gated work (all 15 open decisions)

All 15 open decisions from register §6, each mapped to the plan items it gates. Ten of the fifteen block nothing in this plan (they gate Medium/Low/Improvement work or pure record-keeping); they are listed for completeness and so the RC sign-off (DOCA-14's C3 decision box) can tick every one.

| # | Finding(s) | Decision (compact) | Plan items blocked |
|---|---|---|---|
| 1 | DOCA-20 | Disposition of untracked `P2PKIT_GAP_ANALYSIS_2026-07.md` (recommend KEEP + COMMIT with status banner) | Blocks nothing in this plan (can ride with Group L if approved) |
| 2 | DOCA-1 | Commit/amend the working-tree CLAUDE.md (HEAD version has a now-false publishing claim) | Blocks nothing in this plan (natural rider on Group J or L) |
| 3 | API-1, DOCA-15, DOCA-14 | `P2pMessage.metadata`: wire / deprecate / document as not transmitted; add C3 decision box | **Group M5** (API-1 fix + P1-06) |
| 4 | C:54 (via A09) | `P2pPermission` `ChangeWifiState` disambiguation — deferral re-assessed sound; record formally | Blocks nothing in this plan |
| 5 | ARCH-10 | Construction-time blocking disk I/O in `newP2pKit`: fix vs documented deferral | Blocks nothing in this plan (Low finding; not scheduled here) |
| 6 | IDN-7 | `unregisterManualPeer(peerId)` [API-CHANGE] vs KDoc lifetime + internal name refresh | Blocks nothing in this plan |
| 7 | PRM-1 | Permission-gate granularity after fix #9: doc guidance vs per-operation permission sets [API-CHANGE] | Blocks nothing in this plan (gates the P2 PermissionGateTest contract row) |
| 8 | PRM-16 | `leaveNetwork()` [API-CHANGE] or redefine `stopLocalNetwork`; reword the misleading rejection | Blocks nothing in this plan |
| 9 | SEC-1 | Inbound admission-control caps: internal constants vs configuration surface; cap values | **Group M4** (SEC-1 fix + P1-26) |
| 10 | DOCA-16 / SES-9 | `ConnectionState.Closing`: fix spec/KDoc vs start emitting it (observable change) | Blocks nothing in this plan directly; **constraint on Group D** (the SES-1 fix must not begin emitting `Closing`) and gates the P2 close-sequence row |
| 11 | API-19 | Offer-timeout terminal-state asymmetry: document vs align sender to `Rejected("timeout")` | Blocks nothing in this plan (gates the P2 unanswered-offer row) |
| 12 | API-2 (incl. SES-2) | Typed-error contract for `send()`: land the wrapping before the RC tag? | **Group M2** (API-2 fix + P1-05) |
| 13 | A16 (root of SMP-8) | Incoming-session receive contract at replay=0: small replay buffer vs documented grace period | Blocks nothing in this plan (gates the P2 loss-contract row) |
| 14 | DSC-1 | JVM/Android steady-state discovery heartbeat mechanism | **Group M3** (DSC-1 fix + P1-13) |
| 15 | TST-9 (incl. SES-8) | Approve internal-only `strictInvariants` wiring (no public API change) | **Group M1** (TST-9 + F6 + P1-03) |

Decision-gated plan items: **5** (M1–M5). Recommended decision order: #15 first (approval-only, unblocks the full fixture group), then #12/#14/#9 (each unblocks a High with its P1 test), then #3 (three-way fork with the largest option spread).

## 7. Standing constraints this plan honors

1. **No NsdManager reintroduction.** Android discovery stays on in-process JmDNS (v0.5 migration); nothing in Groups A/I/M3 proposes otherwise — M3's recommended heartbeat reads the existing JmDNS cache.
2. **PP2K wire protocol byte-identical across JVM/Android/iOS.** No group changes the magic, version, 36-byte header, frame types, or `ProtocolConstants` limits. Protocol-adjacent work: Group H's FILE_CANCEL send uses an existing frame type encoded in shared commonMain code; Group A changes TXT-record *handling* (not content) and is mirrored across jvmMain/androidMain/appleMain in one commit; M5 option (a) is the only item that would alter payload encoding, which is exactly why it is decision-gated and flagged for cross-version interop review.
3. **JVM/Android behavior-parity pairs stay in sync.** Groups E (CON-1) and I (watchdog seam) change `JvmRawConnection` and `AndroidRawConnection` identically in the same commit; Group A does the same for the two JmDNS discovery transports.
4. **The 2 known-flaky iOS churn tests are not masked.** No `@Ignore`, widened timeout, or relaxed assertion anywhere in this plan; the `iosSimulatorArm64Test` gate explicitly tolerates only those two documented failures (smoke-matrix row A4 remains the real-hardware validation).
5. **Public-API changes only via the decision-gated items.** Tiers A–L are internal/test/doc/script only. Every `[API-CHANGE]`-tagged option lives in tier M (M2, M4, M5) or in the blocks-nothing decisions (#5, #6, #7, #8), each with its no-API-change alternative recorded.
6. **Marker comments preserved.** `AUDIT-2026-06`, `V0.4-RECONNECT`, `V0.4-D-ANDROID-NUDGE`, `V0.5-FORCED-REFRESH`, `V0.6-WRITE-TIMEOUT` and peers are load-bearing references from docs; fixes that touch marked code (Groups D, E, G, H) keep the markers and extend, never delete, their comments.
7. **The 9 remediation commits at HEAD stay intact.** All work builds on `870bf10`; no rewrite, no amend, no revert. Where a High sits adjacent to a fresh fix (ARCH-2 next to f4dd3a9 #17; FIL-6 as the symmetry gap in 7854ca7 #16; DSC-7 in the #7 fix), the plan scopes to the residual and says so in the item.
8. **Deliberate deferrals honored and flagged.** The unverified inbound HELLO peerId stays deferred to the encryption milestone (`TODO(encryption-milestone)`) — Group A's RBS-1 fix is input validation, not identity verification, and is explicitly scoped away from that trust-model decision. B:317 (Android `refresh()` 200 ms snapshot) is untouched by M3's recommendation. Interface selection / iOS AWDL asymmetry (issues #2/#3) remain hardware-diagnosis items outside this plan.
9. **Test-masking prohibited plan-wide.** Where a P1 row replaces a weak assertion (P1-02's exact-state tightening, P1-23's no-op repair), the change strengthens the assertion; the two coverage-plan rows that adjust over-tight negatives (TST-10-family) are P2 semantic corrections, not relaxations, and are not scheduled here.
10. **Read-only until approved; nothing pushed.** This plan makes no change itself; execution of any group awaits the user's go-ahead, and all work stays local on `audit/exhaustive-review-2026-06` until the user says otherwise.
