# A3-SESSION — Session lifecycle (S3) review

Scope: `SessionManager.kt`, `P2pSessionImpl.kt`, `SessionStore.kt`, `Handshake.kt`
(commonMain `dev/p2pkit/core/internal/`) + 9 commonTest suites. Includes the
adjudication of the transport-layer reviewer's clean-close/reconnect race claim
(verdict in SES-1) and review-as-new-code of remediation commits 012e49e
(manual-peer provenance), e91e094 (strictInvariants), f4dd3a9 (`close()` CLOSE-send
job). All paths below are relative to `/Users/abdelrahman/Projects/P2pKit/`.

## 1. Per-file verdicts

| File | Lines | Verdict | Tests covering it | Test gaps (1 line) |
|---|---|---|---|---|
| p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionManager.kt | 789 | findings: SES-1, SES-2 (route), SES-3, SES-4, SES-5, SES-6, SES-7, SES-8; improvements: SES-12, SES-13, SES-14, SES-16 | SessionFlowTest, ReconnectPolicyTest, SessionReconnectRotationTest, SimultaneousOpenTest, NetworkPathRecoveryTest (kit-level) | No test drives connection loss the way real transports report it (normal read completion); reader-channel cleanup untested |
| p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pSessionImpl.kt | 717 | findings: SES-1, SES-2, SES-3 (co-owner), SES-7, SES-9; improvements: SES-14, SES-15 | KeepAliveTest, CloseSemanticsTest, SessionFlowTest, ReconnectPolicyTest | Remote-CLOSE-frame-with-reconnect-enabled never tested; keep-alive pre-send check and rearm PONG-timer reset untested |
| p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionStore.kt | 332 | findings: SES-4, SES-8 | SessionStoreInvariantTest (direct), SessionFlowTest/SimultaneousOpenTest (indirect) | strictInvariants active in zero kit-level suites; arbitration-vs-zombie-slot interleaving untested |
| p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/Handshake.kt | 89 | findings: —; improvements: SES-16 | HandshakeTest; HandshakeIdentityTest/ManualPeerIdentityTest (S4 suites) | Timeout path and non-HELLO-first-event path have no test; ERROR-frame emission never asserted |
| p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/SessionFlowTest.kt | 270 | findings: SES-10 (shared); improvements: SES-17 | n/a | Relaxed `Closed || Failed` on remote close masks SES-1 (catalogued A-G5-core-tests-20); interleave test payloads all single-frame (catalogued A-G5-core-tests-06) |
| p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/CloseSemanticsTest.kt | 143 | clean | n/a | Only the wedged-write close path; no close-during-active-inbound-traffic case (SES-3 trigger) |
| p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/KeepAliveTest.kt | 201 | improvements: SES-18 | n/a | No rearm-resets-PONG-deadline test, no PING-send-failure test, no wedged-mutex pre-send-check test; real-time cadences (margined) |
| p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/ReconnectPolicyTest.kt | 327 | findings: SES-10 (shared) | n/a | Every break goes through `breakWith` (exceptional read) — a path no shipped transport produces; no remote-clean-close-never-retries test |
| p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/SessionReconnectRotationTest.kt | 359 | clean (findings: SES-10 shared) | n/a | Periodic ~3 s refresh cadence never exercised (only the one-shot refresh); real-time 200 ms retry delays |
| p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/SessionStoreInvariantTest.kt | 184 | findings: SES-8 (evidence) | n/a | Enforces strict mode only on a synthetic forced violation in a locally-built store; kit-level flows still run warn-mode |
| p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/SimultaneousOpenTest.kt | 137 | improvements: SES-19 | n/a | Asserts only session count; tie-break direction, same-physical-connection, winner health (tolerates `Reconnecting`), and arrival-order permutations unasserted |
| p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/NetworkPathRecoveryTest.kt | 281 | clean | n/a | No incoming-session-fails-on-Unsatisfied test; no Unsatisfied-during-Reconnecting no-op test |
| p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/HandshakeTest.kt | 147 | improvements: SES-16 (test side) | n/a | Happy path + 2 reject paths only; timeout, wrong-first-event, ERROR-frame-on-wire untested |

## 2. Findings

### SES-1 — ADJUDICATED: terminal-outcome race on remote connection loss — reconnect nondeterministically skipped, clean close nondeterministically retried

- Severity: High | Confidence: **Confirmed** (pure code-reading proof; all line refs verified this review)
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pSessionImpl.kt:222-233, 483-561, 603-614, 638-696; p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionManager.kt:300-313; p2p-transport-lan/src/jvmMain/kotlin/dev/p2pkit/transport/lan/JvmRawConnection.kt:149-176; p2p-transport-lan/src/androidMain/kotlin/dev/p2pkit/transport/lan/AndroidRawConnection.kt:149-175; p2p-transport-lan/src/appleMain/kotlin/dev/p2pkit/transport/lan/IosRawConnection.kt:284-332; p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/DefaultP2pProtocol.kt:121-140
- Category: bug

**Adjudication verdict: the transport reviewer's observation is CORRECT, and the impact is broader than claimed.** Independent verification:

1. All three `RawConnection.read()` implementations complete **normally** for both genuine EOF and hard read errors, and flip their state to `Closed` (never `Failed`):
   - JVM (JvmRawConnection.kt:153-158): `catch (e: IOException) { … break }` — "Socket closed locally or remotely; complete the flow normally"; EOF `if (n < 0) break` (160-162); then `closeSocketOnce(); _state.value = ConnectionState.Closed` (173-174).
   - Android (AndroidRawConnection.kt:153-173): byte-for-byte the same structure.
   - iOS (IosRawConnection.kt:298-309): both the error and EOF completion branches do `closed = true; _state.value = ConnectionState.Closed; … cont.resume(null)` and the loop `if (chunk == null) break` (328) — never throws out of the flow.
2. `DefaultP2pProtocol.events` is `flow { connection.read().collect { … } }` (DefaultP2pProtocol.kt:121-140) — a normally-completing read flow means a normally-completing events flow.
3. The reader coroutine (SessionManager.kt:301-313) therefore takes the **clean** path: `collect` returns → `eventChannel.close()` (306) with no cause.
4. In `P2pSessionImpl.routeEvents`, the `for (event in channel)` loop then ends and hits the channel-completed handler (P2pSessionImpl.kt:548-552): *"Channel completed without explicit close or error frame … we treat it like a clean close … The clean close path skips reconnect per spec"* → `markCleanlyClosed()` → `transitionToTerminal(Closed)` — **no retry, ever**.
5. Concurrently, `observeRawState` (P2pSessionImpl.kt:222-233) sees the raw StateFlow flip to `Closed` and calls `onConnectionLost("raw connection -> Closed")` → `Reconnecting` (outgoing + handler) or `Failed` (otherwise).
6. Both arbiters gate on `_state.value == Connected` under `connectionLock` (markCleanlyClosed 608-610; onConnectionLost 645-661): **first to acquire the lock from `Connected` decides the session's fate; the loser silently no-ops.**

Refinements beyond the original claim:

- **The race is biased by traffic, in the worst direction.** In the read flow the state flip (JvmRawConnection.kt:174) happens-before the channel close (SessionManager.kt:306), so when `routeEvents` is idle-parked both wakeups are dispatched in that order and `observeRawState` usually wins → `Reconnecting` (desired). But when `routeEvents` is **actively draining a backlog** (busy message/file traffic — precisely the cable-pull-mid-transfer case), it observes channel-end synchronously on its own worker without a dispatch round-trip and beats the parked `observeRawState` to the lock → `Closed`, reconnect **skipped**. The busier the session, the likelier the reconnect feature silently does nothing.
- **The reverse direction violates "clean closes never retry".** A well-behaved peer's `close()` sends a CLOSE frame and then closes the socket ~immediately (P2pSessionImpl.kt:283-291). On the receiving side the `ProtocolEvent.Close` sits *in* the channel while the EOF-driven raw-state flip is delivered *out-of-band*; if `observeRawState` takes the lock before `routeEvents` dequeues the Close event, an outgoing session with `ReconnectPolicy.Enabled` enters `Reconnecting` and **re-dials a peer that deliberately closed** — it can resurrect the session (remote sees a fresh unexplained incoming session). This directly contradicts CLAUDE.md ("Clean closes (local `close()` or peer CLOSE frame) never trigger retry") and spec §10.
- **Incoming sessions get a nondeterministic terminal state** for the same wire event: `Failed` (via observeRawState, handler==null) vs `Closed` (via channel-end). Apps that branch on `Failed` vs `Closed` see coin-flip semantics. `SessionFlowTest.closeTransitionsSessionToClosed` already tolerates this (`finalState == Closed || finalState == Failed`, SessionFlowTest.kt:223-230) — the nondeterminism is baked into a relaxed assertion rather than fixed (catalogued A-G5-core-tests-20).
- **The "per spec" claim in the code comment is unsupported.** P2pKit-Spec.md §16.3 says the opposite for socket death: *"If the underlying socket dies … The session emits Failed immediately. If ReconnectPolicy.Enabled, the session enters Reconnecting and retries."* Neither the spec nor CLAUDE.md defines bare EOF/read-error as a clean close; CLAUDE.md enumerates exactly two clean triggers (local `close()`, peer CLOSE frame). The channel-end→`markCleanlyClosed` policy at P2pSessionImpl.kt:548-552 is therefore the *wrong* policy racing against the right one.

- Root cause: two independent observers of the same underlying event ("this epoch's connection died") implement **contradictory policies** (clean-close vs connection-lost), and the transports collapse EOF and hard error into one indistinguishable signal (normal completion + state=`Closed`), leaving the winner to a scheduler race.
- Evidence (key quotes):
  - JvmRawConnection.kt:155-157 — `} catch (e: IOException) { // Socket closed locally or remotely; complete the flow normally. … break }`
  - P2pSessionImpl.kt:548-552 — `// Channel completed without explicit close or error frame. This is a "remote hangup". … The clean close path skips reconnect per spec.  markCleanlyClosed()`
  - P2pSessionImpl.kt:225-228 — `ConnectionState.Closed, ConnectionState.Failed -> { if (_state.value == ConnectionState.Connected) { onConnectionLost("raw connection -> $rawState") } }`
- Runtime impact: on abrupt disconnect (peer crash/kill → RST or FIN-without-CLOSE, local interface down): outgoing sessions with reconnect enabled nondeterministically end `Closed` (no retry) instead of `Reconnecting`; on graceful remote close: occasional spurious `Reconnecting`/redial; incoming sessions: `Failed` vs `Closed` coin flip. (A silent cable pull with no in-flight traffic produces no read signal at all and goes down the deterministic keep-alive path — the racy trigger is any OS-surfaced read termination.) | Platforms: all three | User-visible: yes
- Failure class: none of the hard classes (no data loss/crash) — feature-defeating race + spec violation
- Proposed fix (do NOT implement): make `routeEvents` the **single** decision point. (a) Track "CLOSE frame seen" in routeEvents; on channel end decide: CLOSE seen → `markCleanlyClosed()`, otherwise → `onConnectionLost("remote hangup/EOF")` (aligns with spec §16.3 and CLAUDE.md). (b) Demote `observeRawState` from decision-maker to nudge/backstop: on raw terminal state, do not call `onConnectionLost` directly; instead give routeEvents a short grace window to drain and decide (the raw close guarantees the reader flow ends, so the channel closes promptly), falling back to `onConnectionLost` only if the channel doesn't end within the grace period. No public-API change. Alternative (larger): have `read()` distinguish EOF from error (complete vs throw) — that is a transport-SPI behavior change and still doesn't fix the CLOSE-frame race by itself, so (a)+(b) is preferred.
- Required tests: (1) fake that mirrors real transports (read completes normally + state→Closed on both sides — see SES-10); (2) EOF-without-CLOSE with reconnect enabled → deterministic `Reconnecting`; (3) remote CLOSE frame followed immediately by socket close, repeated under dispatcher stress → always `Closed`, factory never re-dialed; (4) incoming session EOF → deterministic terminal state; (5) tighten SessionFlowTest.kt:223-230 to the exact expected state.

### SES-2 — `session.send()` leaks raw platform exceptions instead of typed `P2pError`

- Severity: Medium | Confidence: Confirmed | **[CATALOGUED]** — this is the typed-error face of A-G2-core-internal-14 ("connection/events fields written under connectionLock, read without it", minor, deferred) and PROBLEMS_P2PKIT.md:486-487; I re-verified it is still open and assess the deferral as unsound for an RC (see below).
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pSessionImpl.kt:235-242; p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/DefaultP2pProtocol.kt:102-105; p2p-transport-lan/src/jvmMain/kotlin/dev/p2pkit/transport/lan/JvmRawConnection.kt:116-137; p2p-transport-lan/src/appleMain/kotlin/dev/p2pkit/transport/lan/IosRawConnection.kt:200-280, 353
- Category: bug
- Root cause: `send()` does a state pre-check then writes with **no exception mapping**:
  ```kotlin
  override suspend fun send(message: P2pMessage) {
      if (_state.value != ConnectionState.Connected) {
          throw P2pError.ConnectionFailed("Session $id is ${_state.value}; cannot send")
      }
      sendMutex.withLock { protocol.sendMessage(connection, message) }
  }
  ```
  `DefaultP2pProtocol.writeFrame` → `connection.write(bytes)` with no wrap either. The raw connections throw platform types: JVM/Android `IOException` (incl. the watchdog's synthetic `IOException("socket write timed out …")`, JvmRawConnection.kt:122-137); iOS `IosRawConnection.NetworkException` (RuntimeException subtype, :252-254) and `IllegalStateException` ("connection closed" :208, send-timeout :276-279). The state check is also TOCTOU: state can flip / `connection` can be swapped by `rearmWith` (:341) or closed by `transitionToTerminal` (:434) after the check, since `send()` never takes `connectionLock`.
- Evidence: quoted above; contrast with `performConnect`, which wraps the same class of failure for `connect()` (SessionManager.kt:174-180), and `runHandshake`'s wrap comment "callers only ever see a documented P2pError" (SessionManager.kt:396-406) — the send path is the only remaining public suspend entry point without the wrap.
- Runtime impact: any send racing a disconnect/reconnect/close surfaces `IOException` / `IllegalStateException` / `NetworkException` to app code. Apps following the documented `catch (e: P2pError)` pattern crash or mishandle; behavior differs per platform (violates both the typed-failure invariant and platform-parity invariant in the BRIEF). | Platforms: all three (different leak types per platform) | User-visible: yes
- Failure class: none (wrong error semantics; possible app-level crash from unexpected exception type)
- Proposed fix (do NOT implement): in `P2pSessionImpl.send` (and the dispatcher's write choke points, S8's scope), catch non-`CancellationException` throwables from the write and rethrow `P2pError.ConnectionFailed(reason, cause)`; rethrow `P2pError` and `CancellationException` untouched. Deferral assessment: the original "minor" rating covered the lock-discipline aspect; the typed-error contract breach is cheap to fix (one catch block), platform-divergent, and app-facing — worth pulling into the RC.
- Required tests: unit test with a `FakeRawConnection` whose `write` throws a platform-style exception mid-`send` → assert `P2pError.ConnectionFailed` with cause preserved; a variant where the connection is swapped by rearm between state check and write.

### SES-3 — Reader coroutine parks forever in `eventChannel.send` when a session terminates with a full event channel (memory/coroutine leak)

- Severity: Medium | Confidence: Confirmed (structural; the park-forever interleaving is reasoned, not reproduced — a stress test would settle the trigger frequency)
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionManager.kt:300-313, 409-414 (readerJob returned but dropped by `setupSession` at :230-244); p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pSessionImpl.kt:420-435 (`transitionToTerminal` cleanup), 313-354 (`rearmWith`)
- Category: bug
- Root cause: the reader (`scope.launch { protocol.events(rawConnection).collect { eventChannel.send(event) } … }`, SessionManager.kt:301-313) runs on the **kit** scope, not the session's. `HandshakeOutputs.readerJob` is dropped in `setupSession` — after registration nobody holds it. Session teardown (`transitionToTerminal`) cancels the epoch (stops the channel's only consumer) and closes the raw connection, but **never cancels the reader and never cancels the events channel**. Closing the socket only helps if the reader is parked in a read; if it is parked in `eventChannel.send` (buffer full, 256 events) it can never reach the read that would fail — no receiver, no close, no cancellation → parked until `kit.stop()`.
- Evidence:
  - SessionManager.kt:303-305 — `protocol.events(rawConnection).collect { event -> eventChannel.send(event) }` (capacity 256, :300)
  - P2pSessionImpl.kt:430-434 — cleanup is exactly `epochJob?.cancel()` + `runCatching { connection.close() }`; the `events` channel field is dropped, not cancelled. Same in `rearmWith` (:340-342) for the old epoch's channel/reader.
- Runtime impact: per occurrence: one leaked coroutine + up to 256 buffered `ProtocolEvent`s (DATA events carry reassembled payloads up to 4 MiB; FILE_DATA frames 64 KiB) + the `RawConnection` object, retained until `kit.stop()`. Realistic trigger: the channel is full precisely when the local consumer is slower than the wire — e.g. disk-bound inbound file transfer or a slow `incoming` collector — and the session then terminates (user `close()` mid-transfer, keep-alive timeout, rearm). Accumulates across session churn in long-running apps. Note this is a side effect of the (correct) AUDIT-2026-06 bounded-channel fix (A-G2-core-internal-01, fixed): the old UNLIMITED channel could not park the sender. | Platforms: all | User-visible: indirectly (memory growth)
- Failure class: leak
- Proposed fix (do NOT implement): make the session own the reader's lifetime — e.g. `transitionToTerminal` and `rearmWith` call `events.cancel()` on the epoch's channel (releases buffered elements and resumes a parked `send` with cancellation, which the reader's `catch (e: CancellationException)` already handles), and/or retain `readerJob` in the session and cancel it in the NonCancellable cleanup block. Apply to the reconnect-loop discard path too (SessionManager.kt:569-576 already cancels the readerJob there — the terminal path should match it).
- Required tests: unit test — fill the events channel (slow/no consumer), terminate the session, assert the reader coroutine completes and the channel is cancelled (e.g. via a completion latch on a fake protocol flow).

### SES-4 — Arbitration rejects a live redial while a stale undetected-dead session holds the peer slot (reconnect lockout up to keep-alive timeout)

- Severity: Medium | Confidence: Confirmed (logic); not found in either audit catalogue (grepped AUDIT_REPORT_2026-06.md, PROBLEMS_P2PKIT.md, .audit/phase3/verified-findings.json for loser/zombie/arbitration entries — the catalogued PROBLEMS:543 item is a different loser-side issue)
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionStore.kt:129-172 (`tryRegister`); p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionManager.kt:715-722 (Rejected → `loser.close()`); p2p-core/src/commonMain/kotlin/dev/p2pkit/core/Config.kt:29-46 (design: "the remote peer is expected to redial")
- Category: bug
- Root cause: `tryRegister` treats any `existing` in `ACTIVE_STATES` as authoritative. When the smaller-id side (A) holds an outgoing session that is **actually dead but not yet detected** (asymmetric failure: remote rebooted/battery-pulled — A's TCP half sees nothing until keep-alive), and the larger-id peer (B) redials as the design instructs (`ReconnectPolicy` KDoc: incoming sessions "transition directly to Failed; the remote peer is expected to redial"), A's arbitration fires: A is smaller → keeps its (zombie) outgoing → `RegisterOutcome.Rejected` for B's fresh inbound → A closes it **with a CLOSE frame** → B's brand-new outgoing session ends `Closed` as a *clean close* (correctly no retry). Every subsequent redial by B completes a full TCP+HELLO handshake and is then immediately closed, until A's keep-alive finally kills the zombie (defaults: 10 s ping / 30 s timeout ⇒ up to ~30-40 s lockout).
- Evidence: SessionStore.kt:137-151 — `if (existing != null && existingState in ACTIVE_STATES) { … newWinsLocally = if (localPeerIdValue < peerId.value) !isIncoming … RegisterOutcome.Rejected(winner = existing, loser = session) }` — no liveness signal beyond the state enum is consulted; a wedged `Connected` counts as active.
- Runtime impact: after asymmetric abrupt failures, peers cannot re-establish for up to the keep-alive timeout even though one side is actively (and correctly) redialing; each rejected dial also costs a full handshake round-trip. Self-heals. | Platforms: all | User-visible: yes (tens of seconds of "cannot reconnect")
- Failure class: none (availability delay)
- Proposed fix (do NOT implement): treat an authenticated fresh inbound from peer P as evidence that P considers the old link dead — e.g. in the Rejected-would-be branch, nudge the existing session's liveness (send an immediate PING / probe) or prefer replacing an existing session whose last PONG is older than one ping interval. Keep the deterministic tie-break for the genuine simultaneous-open case (both sessions healthy).
- Required tests: combination test — A holds a session whose wire is silently dead (fake that swallows writes without failing), B redials; assert re-establishment well under the keep-alive timeout once the fix lands; today's behavior (lockout) documented as the regression baseline.

### SES-5 — `performConnect` wraps `CancellationException` into `P2pError.ConnectionFailed`

- Severity: Low | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionManager.kt:174-180
- Category: bug
- Root cause: the transport-connect wrap has no CE-first arm:
  ```kotlin
  val rawConnection = try {
      transport.connect(internalPeer)
  } catch (e: P2pError) {
      throw e
  } catch (e: Throwable) {
      throw P2pError.ConnectionFailed("Transport connect failed: ${e.message}")
  }
  ```
  `connect()` runs in the **caller's** coroutine; if the app cancels it mid-dial, the CE from `transport.connect` is converted into `ConnectionFailed` (also losing the original as `cause` — the wrap drops causes generally). This is the exact pattern the sibling wrap in `runHandshake` gets right (`catch (e: CancellationException)` first, SessionManager.kt:386-389), and violates the BRIEF invariant "CancellationException must never be swallowed".
- Runtime impact: cancellation of an in-flight `connect()` is misreported as a connection failure to any `JoinPending` co-waiter and to catch-P2pError logic in the cancelled caller before the cancellation reasserts at the next suspension. No hang/leak (the `finally { store.endPending(...) }` still runs; `deferred.completeExceptionally` still fires). | Platforms: all | User-visible: marginal (wrong error type in logs/handlers)
- Failure class: none
- Proposed fix (do NOT implement): add `catch (e: CancellationException) { throw e }` before the Throwable arm (and pass the original as `cause` in the wrap while there).
- Required tests: unit — cancel a `connect()` parked in a suspending fake `transport.connect`; assert the awaiting caller sees CE, and a JoinPending waiter sees a defined outcome.

### SES-6 — Cancellation window in the reconnect loop leaks the freshly-dialed connection

- Severity: Low | Confidence: Confirmed (window is real; small)
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionManager.kt:544-583; p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pSessionImpl.kt:317-353
- Category: bug
- Root cause: after `runHandshake` returns inside the retry loop, ownership of `handshake.secureConnection`/`readerJob` is in limbo until `rearmWith` completes the swap. The only cleanup sites are the explicit state-check branch (SessionManager.kt:569-576) and `rearmWith`'s terminal-guard branch (P2pSessionImpl.kt:319-322). If the handler coroutine is **cancelled** between the successful handshake and the swap — e.g. `kit.stop()`'s final `internalJob.cancel()` (P2pKitImpl.kt:470) landing while `rearmWith` suspends at `connectionLock.withLock` (:317) or at `epochJob?.cancelAndJoin()` (:323, before the swap) — the CE propagates and nothing closes the new connection or cancels its reader. (User `close()` cannot hit this window: it needs `connectionLock` itself before its `sessionJob.cancelAndJoin`, so it serializes behind `rearmWith`.)
- Evidence: SessionManager.kt:578 `session.rearmWith(handshake.secureConnection, handshake.events)` has no try/finally; the handler's only `finally` cancels `periodicRefreshJob` (:586-588).
- Runtime impact: one open socket + reader coroutine per occurrence, normally reclaimed only when the remote's keep-alive times the orphan out and our read loop then closes the fd. Narrow window, needs stop()/cancel racing an in-flight rearm. | Platforms: all | User-visible: no
- Failure class: leak (transient, mostly self-healing)
- Proposed fix (do NOT implement): wrap the post-handshake section in try/catch-CE (or try/finally with an "adopted" flag): on CE before `rearmWith` returned normally, cancel `handshake.readerJob` and close `handshake.secureConnection`, then rethrow.
- Required tests: unit — cancel the handler at a hook between handshake completion and rearm; assert the new fake connection's `close()` was called.

### SES-7 — `sessionJob` never completes for sessions that end via failure paths (unbounded Job accumulation under the kit scope)

- Severity: Low | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pSessionImpl.kt:125-126, 384-390 (documented: only `close()` cancels `sessionJob`), 397-448; p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionManager.kt:732-737 (`watchForTerminal` only cleans the store)
- Category: bug
- Root cause: `transitionToTerminal` deliberately does not cancel `sessionJob` (its callers are its children — sound reasoning), and only user `close()` performs `sessionJob.cancelAndJoin()` (:301). But no external party compensates on the other terminal paths (keep-alive timeout, remote hangup, reconnect exhaustion, PeerError, path-loss `Failed`): `watchForTerminal` observes the terminal state and evicts from the store but never cancels the session's `sessionJob`. A `SupervisorJob` with a parent stays registered in the parent's children list until it completes — it never does — so every non-`close()` session death leaves one live Job node attached to the kit's Job for the kit's lifetime.
- Runtime impact: small per item, unbounded count: a flappy network with reconnect exhaustion churns sessions and accumulates Jobs (plus anything reachable from unfinished children) until `stop()`. | Platforms: all | User-visible: no
- Failure class: leak (slow)
- Proposed fix (do NOT implement): have `watchForTerminal` (which is outside `sessionJob`) cancel the session's `sessionJob` after `store.removeIfMatches` — mirroring exactly why `close()` may do it — or expose an internal `disposeAfterTerminal()` on `P2pSessionImpl` that SessionManager calls there.
- Required tests: unit — drive a session to `Failed` via keep-alive timeout, then assert the session's job (exposed to tests or observed via parent children count) is completed.

### SES-8 — strictInvariants (#19 fix) is not wired into any behavioral suite — the blind spot it was built to close is still open

- Severity: Medium | Confidence: Confirmed (this is a defect *in* remediation e91e094, reviewed as new code)
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionManager.kt:100-109, 119; p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionStore.kt:37-48, 276-279; p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/SessionStoreInvariantTest.kt:46, 64, 78
- Category: bug (test blind spot in a shipped fix)
- Root cause: the `strictInvariants` seam exists in two places — `SessionStore(logger, strictInvariants)` and a pass-through parameter on `SessionManager` whose KDoc says *"Test-only (#19) … the suites run with a NoOp/quiet logger, so warn-only enforcement would let a store regression pass every test silently"*. Grep of the whole repo: the only `strictInvariants = true` construction is in `SessionStoreInvariantTest` on a **locally built store exercised via a synthetic forced violation** (`forceInvariantViolationForTest`). Every kit-level suite that exercises real store mutations (SessionFlowTest, ReconnectPolicyTest, SimultaneousOpenTest, SessionReconnectRotationTest, NetworkPathRecoveryTest — all via `P2pKit.create`) runs the store in warn-mode with the default NoOp logger. The `SessionManager` `strictInvariants` parameter is never set `true` by anyone — dead code. Net: a genuine bookkeeping regression occurring during any behavioral flow still passes every test silently — the precise #19 failure mode. The enforcement tests prove the *mechanism* works, not that the *flows* are covered by it.
- Evidence: SessionStoreInvariantTest.kt:46 `SessionStore(P2pLogger.NoOp, strictInvariants = true)` (direct store, forced violation only); no other `strictInvariants` reference outside commonMain.
- Runtime impact: none at runtime; regression-detection capability materially below what REMEDIATION_2026-07.md claims for #19 ("Fixed … `SessionStoreInvariantTest` (enforce + no-false-positive)"). | Platforms: n/a | User-visible: no
- Failure class: none (hidden-failure test gap)
- Proposed fix (do NOT implement): expose a test-only hook so kit-level suites construct `SessionManager(strictInvariants = true)` (e.g. an internal builder knob or test factory used by the common test helpers), so every behavioral suite runs strict. No public API change needed (internal constructor param already exists).
- Required tests: flip the suites' construction path; the existing behavioral tests then double as invariant enforcement.

### SES-9 — `ConnectionState.Closing` is a never-entered public state; spec §10 still documents `Connected → Closing → Closed`

- Severity: Low | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/States.kt:31-46; p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pSessionImpl.kt:319, 662 (dead guards); P2pKit-Spec.md §10 ("`close()` transitions: `Connected → Closing → Closed`")
- Category: bug (doc/spec drift; dead-state guards)
- Root cause: no code path assigns `Closing` (repo-wide grep). `States.kt` KDoc already documents that `close()` goes directly to `Closed`, but the spec (the locked contract) still promises an observable `Closing` phase, and `rearmWith`/`onConnectionLost` carry guards for a state that cannot occur. `SessionStore.ACTIVE_STATES` excludes `Closing`, so if a future change ever set it, a closing session would instantly become replaceable/evictable — a latent trap.
- Runtime impact: apps written against the spec that key on `Closing` never see it. | Platforms: all | User-visible: only to spec-following apps
- Failure class: none
- Proposed fix (do NOT implement): fix the spec sentence (spec change, not API change — the enum constant stays for compatibility) and add a one-line comment on the dead guards; or actually enter `Closing` in `close()` before the CLOSE-frame send — if so, `ACTIVE_STATES` and the `markCleanlyClosed`/`onConnectionLost` gates must be revisited together. Flag: the second option changes observable behavior — treat as `[API-CHANGE]`-adjacent; the doc fix is the no-change alternative.
- Required tests: n/a for the doc fix.

### SES-10 — Test model: `FakeRawConnection.breakWith` produces a failure signature no shipped transport can produce; the entire reconnect suite runs on it

- Severity: Medium | Confidence: Confirmed | Partially **[CATALOGUED]**: A-G5-core-tests-16 (deferred) covers the *remote* side ("breakWith gives the remote a clean EOF — inbound abrupt wire break untestable"); the sharper local-side half — that real transports never throw from `read()` at all, so `breakWith`'s exceptional close exercises a production-unreachable branch — is new (the older PROBLEMS:655 text assumed real TCP "surfaces as an error… on both ends", which the shipped `read()` implementations contradict by design).
- File(s): p2p-core/src/commonTest/kotlin/dev/p2pkit/core/testfixtures/FakeRawConnection.kt:58-63; consumers: ReconnectPolicyTest.kt:97,130,165,205,237,278,309; SessionReconnectRotationTest.kt:138,234,329; NetworkPathRecoveryTest.kt:177
- Category: bug (test-fidelity)
- Root cause: `breakWith` does `receive.close(cause)` → the local read flow **throws** → reader closes the events channel **with** a cause → `routeEvents`' `catch (e: Throwable)` → deterministic `onConnectionLost`. All three real transports complete `read()` normally on error (see SES-1 evidence), which routes through the channel-**end** handler and the raw-state race instead. Consequences: (a) every reconnect-policy behavior is validated only on the production-unreachable exceptional branch; (b) the production branch (`markCleanlyClosed` vs `observeRawState` race, SES-1) is structurally untestable with this fixture; (c) the fake's `close()` also diverges from real `close()` — it closes only the `send` channel, so the *local* read flow of a closed fake never ends (real transports unblock the local read and flip state).
- Evidence: FakeRawConnection.kt:58-63 — `fun breakWith(cause: Throwable) { … receive.close(cause); send.close() }` vs JvmRawConnection.kt:155-158 (IOException → normal completion).
- Runtime impact: none directly; it is the reason SES-1 shipped invisible and why "clean-close-never-retries from the remote side" has no true regression test. | Platforms: test-only | User-visible: no
- Failure class: none (hidden failure)
- Proposed fix (do NOT implement): add a fidelity mode to the fixture (or a second fixture): `breakLikeRealTransport()` = set `_state.value = Closed` + `receive.close()` (no cause) on the local side, `send.close()` for the remote — matching all three shipped transports; migrate the reconnect suites to it once SES-1's policy decision lands (order matters: migrating today would make the suite nondeterministic, which is exactly the point).
- Required tests: covered by SES-1's required tests.

### SES-11 — Handshake worst-case duration is bounded by the write watchdog (≈30 s), not the 10 s handshake timeout

- Severity: Low | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/Handshake.kt:47-54; p2p-transport-lan/src/jvmMain/kotlin/dev/p2pkit/transport/lan/JvmRawConnection.kt:206 (`WRITE_TIMEOUT_MILLIS = 30_000`)
- Category: bug (boundary/documentation of the timeout budget)
- Root cause: `performHandshake` bounds only `events.receive()` with `handshakeTimeoutMillis` (10 s). The preceding `protocol.sendHello(connection, localHello)` (:47) and each best-effort `sendError` on the reject paths (:52,57,64,70) are unbounded at this layer; against a SYN-accepted-but-non-draining peer the HELLO write parks until the transport watchdog fires at 30 s. Worst case ≈ 30 s (send) + 10 s (receive) per connect/reconnect attempt — also silently consuming most of a reconnect budget (`maxAttempts × retryDelayMillis`) in one attempt.
- Runtime impact: `connect()` and individual reconnect attempts can take ~4× the documented handshake timeout against a wedged or non-draining listener; a peer that accepts connections without reading delays every dial by up to 40 s. | Platforms: all (watchdog values identical) | User-visible: yes (long hangs before typed failure)
- Failure class: none (bounded — thanks to the f4dd3a9-era watchdogs — but 4× the intended budget)
- Proposed fix (do NOT implement): wrap the whole `performHandshake` call (send + receive) in the caller's timeout — e.g. `withTimeoutOrNull(handshakeTimeoutMillis)` around the send+receive pair in `runHandshake`, relying on the raw-close in its failure handler to unblock a parked write (same lever `close()` uses).
- Required tests: fake connection whose `write` parks; assert `connect()` fails typed within ~handshakeTimeout, not the transport watchdog.

### Improvements (not defects)

### SES-12 — `Rejected` log line mislabels `existingState`
- Severity: Improvement | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionManager.kt:694-699
- `existingStateLabel` uses `outcome.loser.state` for both branches; for `Rejected` the loser is the **new** session, so the log's "existingState" prints the newcomer's state, not the incumbent's (`outcome.winner`). Misleading during arbitration debugging (exactly where this log matters).

### SES-13 — `closeAllSessions` is sequential; stop latency scales with wedged sessions
- Severity: Improvement
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionManager.kt:739-744
- Each `close()` can legitimately take ~2 s (CLOSE_FRAME_TIMEOUT_MS) plus joins; N wedged sessions serialize to ~2 s × N inside `stop()`'s NonCancellable block. `supervisorScope { map { launch { close() } }.joinAll() }` keeps stop bounded by the slowest session instead of the sum.

### SES-14 — Tail-position `runCatching` around suspending close/send calls swallows CancellationException
- Severity: Improvement (letter-of-the-invariant; no behavioral harm found at these sites)
- File(s): SessionManager.kt:713, 721 (`scope.launch { runCatching { outcome.loser.close() } }`), 742 (`runCatching { session.close() }` — benign at `stop()` because P2pKitImpl.kt:435 wraps teardown in `NonCancellable`, but the same method is invoked from `applyBackgroundPolicy`'s plain `scope.launch`, SessionManager.kt:783-785, where a mid-loop scope cancellation is silently eaten per-session); P2pSessionImpl.kt:519-521 (PONG send; CE re-surfaces at the next channel receive, so only delayed).
- Convention fix: `try { … } catch (e: CancellationException) { throw e } catch (e: Throwable) { … }` helper, as already done in `handleIncoming` (SessionManager.kt:208-213).

### SES-15 — Session id collisions possible within one clock millisecond
- Severity: Improvement
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionManager.kt:233 (`id = "${…}-${handshake.resolvedPeer.id.value}-${clock()}"`)
- Two sessions for the same peer minted in the same ms (arbitration churn) share an id; the zombie detector compares `reg.activeSessionId != id` (P2pSessionImpl.kt:503-504) and would false-negative. Add a monotonic counter suffix.

### SES-16 — Handshake reject paths can stall on the best-effort `sendError`
- Severity: Improvement
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/Handshake.kt:52-70; SessionManager.kt:348, 357
- Each `runCatching { protocol.sendError(…) }` before a throw is itself an unbounded write (30 s watchdog worst case), delaying the typed failure the caller is waiting for. A short `withTimeoutOrNull` (or fire-and-forget on the kit scope) keeps rejects prompt. (Subsumed by SES-11's whole-handshake bound if that lands.)

### SES-17 — SessionFlowTest weaknesses (both catalogued, restated for the merge)
- Severity: Improvement
- File(s): SessionFlowTest.kt:198-204, 222-230
- `concurrentSendsDoNotInterleave` uses 2 000/3 000-byte payloads — below the 64 KiB chunk size (ProtocolConstants.kt:19), so every message is single-frame and interleaving is impossible by construction (catalogued A-G5-core-tests-06). `closeTransitionsSessionToClosed` accepts `Closed || Failed` on the peer (catalogued A-G5-core-tests-20) — masks SES-1; tighten to exactly `Closed` once SES-1 is fixed.

### SES-18 — KeepAliveTest gaps and real-time cadence
- Severity: Improvement
- File(s): KeepAliveTest.kt (all three tests)
- Missing: rearm resets the PONG deadline (`startEpoch`'s `lastPongAt.value = clock()`, P2pSessionImpl.kt:195 — a regression here causes an instant false timeout after every reconnect); PING-send-failure → `onConnectionLost` branch (P2pSessionImpl.kt:582-590); the AUDIT-2026-06 pre-send timeout check under a held `sendMutex` (P2pSessionImpl.kt:573-581 — the remediation table maps #4 only to CloseSemanticsTest, which exercises `close()`, not this branch). Positive test runs on real time with 24× margin — acceptable, but the three missing branches are cheap deterministic unit tests.

### SES-19 — SimultaneousOpenTest asserts count, not the arbitration contract
- Severity: Improvement
- File(s): SimultaneousOpenTest.kt:96-126
- Never asserts: tie-break direction (smaller id kept its outgoing — the session `id` prefix `out-`/`in-` makes this checkable), both sides on the same physical connection (exchange one message over the survivors), or winner health — the `Connected || Reconnecting` tolerance (:113-122) would pass even if arbitration closed the *winning* connection and the survivor was busy reconnecting, which is the exact regression the arbitration exists to prevent. Also only the concurrent-arrival order is tested; incoming-first and outgoing-first sequential arrivals (both `tryRegister` branches, SessionStore.kt:137-151) are unexercised at kit level.

## 3. Missing tests

| Invariant untested | Why it matters | Where it should live | Type | Priority |
|---|---|---|---|---|
| Remote CLOSE frame while Connected, reconnect **enabled** → `Closed`, factory never redialed | The "clean closes never retry" invariant is only tested for local `close()`; the remote half is the SES-1 race victim | ReconnectPolicyTest | unit/combination | P1 |
| EOF/read-error surfaced as real transports surface it (normal completion + state→Closed) → deterministic outcome | Entire reconnect suite currently runs on a production-unreachable failure signature (SES-10); SES-1 invisible | testfixtures (fidelity fake) + ReconnectPolicyTest | combination | P1 |
| Store invariants enforced (strict) during real kit-level flows | #19's blind spot still open (SES-8); warn-mode + NoOp logger hides regressions in every behavioral suite | common test helper wiring `SessionManager(strictInvariants=true)` | unit/combination | P1 |
| Reader/eventChannel released on session terminal and rearm (no parked `send`) | SES-3 leak has no regression guard | new SessionTeardownTest (commonTest) | unit | P2 |
| `session.send()` throws typed `P2pError` when the transport write fails mid-send | SES-2; app-facing contract, platform-divergent today | SessionFlowTest or new SendErrorTest | unit | P2 |
| Keep-alive: pre-send timeout check fires with `sendMutex` held by a wedged writer | The remediation #4 keep-alive half has no direct test | KeepAliveTest | unit | P2 |
| Keep-alive: PONG deadline reset on rearm (no instant false timeout post-reconnect) | Regression here breaks every reconnect under short timeouts | KeepAliveTest | unit | P2 |
| Arbitration: tie-break direction, survivor health, same-physical-connection, both arrival orders | SES-19; current test passes under broken arbitration | SimultaneousOpenTest | combination | P2 |
| Handshake timeout and non-HELLO-first-event reject paths | Handshake.kt:49-59 has zero coverage; both are two-line tests with the injectable timeout | HandshakeTest | unit | P2 |
| Redial-while-zombie-slot lockout (SES-4) | Documents/bounds the reconnect-lockout window | new combination test | combination | P2 |
| Periodic ~3 s discovery refresh cadence across a long Reconnecting window | CLAUDE.md documents the cadence; only the one-shot refresh is asserted (SessionReconnectRotationTest.kt:342-345 even asserts `refreshCalls == 1`, which would fail under a >3 s window — latent flake if retry budgets grow) | SessionReconnectRotationTest (virtual-time or widened budget) | unit | P3 |
| Incoming session → `Failed` on path Unsatisfied | NetworkPathRecoveryTest only wires the observer on the outgoing kit | NetworkPathRecoveryTest | unit | P3 |

## 4. Section summary

**What S3 owns:** session establishment (dial + accept + HELLO), the per-session
state machine (`P2pSessionImpl`), single-source-of-truth bookkeeping
(`SessionStore`), simultaneous-open arbitration, keep-alive, and the whole
reconnect pipeline (retry loop, endpoint re-resolution, discovery-refresh
cadence, `rearmWith`).

**Overall health:** structurally strong. The single-terminal-codepath
(`transitionToTerminal` — verified: nothing bypasses it; both failure guards
`markCleanlyClosed`/`markFailedAfterExhaustion` and `close()` funnel through it,
and its NonCancellable cleanup + post-condition checks are sound), the
store-with-one-mutex consolidation, the arbitration convergence (all four
arrival interleavings converge; self-peerId HELLOs rejected so the equal-id
case is unreachable), and the three reviewed remediation fixes are all
well-built: 012e49e's provenance threading is correct at both connect and
re-handshake call sites (`origin == PeerOrigin.Manual` at SessionManager.kt:186
and :555, never the id string); f4dd3a9's `close()` is correct and prompt
(bounded join, teardown unblocks the wedged writer, idempotent). The two
systemic weaknesses are (1) **two observers with contradictory policies for
connection death** (SES-1) and (2) **resource ownership at the edges of the
epoch model** — the reader coroutine, the events channel, and `sessionJob`
all outlive terminal transitions on some paths (SES-3/6/7).

**Top 3 risks:**
1. SES-1 — nondeterministic reconnect-vs-clean-close on every abrupt
   disconnect, biased against busy sessions; violates spec §16.3 and the
   clean-close invariant in both directions.
2. SES-2 + SES-3 under churn — raw platform exceptions escaping `send()` and
   per-terminal reader/channel leaks, both concentrated in exactly the flappy-
   network conditions the reconnect feature targets.
3. SES-8 + SES-10 — the safety nets meant to catch regressions here (strict
   store invariants, reconnect suite) don't observe production-shaped failures,
   so regressions in this highest-risk section are systematically invisible.

**CODEBASE_REVIEW_MAP_2026-07.md accuracy:** essentially accurate (13 files,
"concurrency heart", risk High, ~2.1k test lines all check out). One
discrepancy: the S3 entry (line 93-94) attributes "`transitionToTerminal`,
`strictInvariants`" to `SessionStore` — `transitionToTerminal` lives in
`P2pSessionImpl` (:397), and `strictInvariants` spans `SessionStore` plus a
(currently dead, SES-8) `SessionManager` constructor parameter. Also
"Platform boundaries: none (pure common)" is true of the code but hides that
S3's *behavior* is platform-coupled through the RawConnection read/error
contract — which is exactly where SES-1 lives.
