# A12-TESTS — S15 test fixtures (fidelity review) + repo-wide test-quality sweep

Reviewer: A12-TESTS. Branch `audit/exhaustive-review-2026-06`, HEAD `870bf10`. Read-only review; every claim below was verified against the tree (file:line cited). Method for Part 1: each fake compared against (a) the SPI contracts in `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transport/*.kt`, (b) the shipped implementations (`JvmRawConnection`, `AndroidRawConnection` [pair-parity], `IosRawConnection`, `JvmLanDataTransport`, `Jvm/Android/IosLanDiscoveryTransport`, `NoOpNetworkPathObserver`), and (c) what core actually consumes (`P2pSessionImpl`, `SessionManager`, `PeerRegistry`, `DefaultP2pProtocol`), plus a grep of every fixture call site in commonTest.

## 1. Per-file verdicts (S15)

| File | Lines | Verdict | Tests covering it (consumers) | Test gaps (1 line) |
|---|---|---|---|---|
| p2p-core/src/commonTest/kotlin/dev/p2pkit/core/testfixtures/FakeRawConnection.kt | 64 | findings: TST-1, TST-2 · improvements: TST-5, TST-7 | 15 commonTest suites (SessionFlowTest, ReconnectPolicyTest, SessionReconnectRotationTest, NetworkPathRecoveryTest, KeepAliveTest, SimultaneousOpenTest, Handshake*, FileTransfer*, ManualPeerIdentityTest, DefaultP2pProtocolTest, FileTransferProtocolTest, …) | Remote-initiated termination is unmodelable (TST-1); no write-fault injection (TST-5) |
| p2p-core/src/commonTest/kotlin/dev/p2pkit/core/testfixtures/FakeDataTransport.kt | 65 | findings: TST-3 · improvements: TST-6, TST-7 | SessionFlowTest, ReconnectPolicyTest, SessionReconnectRotationTest, NetworkPathRecoveryTest, SimultaneousOpenTest, ManualPeerIdentityTest, HandshakeIdentityTest, LocalIdentityTest, PermissionGateTest | incoming flow can never fail with a cause (TST-3); start() contract unmodeled (TST-6) |
| p2p-core/src/commonTest/kotlin/dev/p2pkit/core/testfixtures/FakeDiscoveryTransport.kt | 68 | findings: TST-4 · improvements: TST-8 | SessionReconnectRotationTest, NetworkPathRecoveryTest, ManualPeerIdentityTest, PermissionGateTest, LocalIdentityTest, HandshakeIdentityTest (NOT PeerRegistryTest — rolls its own `FakeDiscovery`, see TST-14) | Overflow semantics diverge from production (TST-4); no burst/drop scenario possible |
| p2p-core/src/commonTest/kotlin/dev/p2pkit/core/testfixtures/FakeNetworkPathObserver.kt | 41 | clean | NetworkPathRecoveryTest (sole consumer; lifecycle counters asserted at NetworkPathRecoveryTest.kt:258-277) | None material — kit start/close ordering is pinned by its consumer |

Compliance checks requested by the campaign (verified, no finding):
- `@Ignore` inventory: exactly one, `IosLanDiagnosticTest.kt:32` — a deliberate, documented manual diagnostic harness (KDoc lines 16-25 explain the policy). The 2 known-flaky iOS churn tests are **active** (`IosLanLifecycleTest.kt:84-85` and `:344-345`, plain `@Test`, no masking, timeouts unchanged). [CATALOGUED]
- `SessionStore(strictInvariants=true)` is constructed in tests — but only in `SessionStoreInvariantTest` (see TST-9 for why that is a finding anyway).

## 2. Findings

### Part 1 — fixture fidelity (S15)

### TST-1 — FakeRawConnection models remote-initiated termination unlike any shipped transport; the real clean-close-vs-reconnect race is structurally invisible to commonTest
- Severity: High | Confidence: Confirmed (all paths read; all call sites grepped)
- File(s): FakeRawConnection.kt:37-63; JvmRawConnection.kt:149-176, 178-189; IosRawConnection.kt:284-332; P2pSessionImpl.kt:222-233 (observeRawState), :483-561 (routeEvents), :603-614 (markCleanlyClosed), :638-696 (onConnectionLost); SessionManager.kt:300-311 (events→channel bridge)
- Category: bug (test-infrastructure fidelity defect)
- Root cause: three coupled divergences.
  1. **Real `read()` never throws.** JVM catches IOException and `break`s (JvmRawConnection.kt:153-159), EOF `break`s (:160-163); iOS resumes `null` on error/EOF and breaks (IosRawConnection.kt:298-309). Both then flip `_state = Closed` and complete the flow **normally**. The fake's `breakWith(cause)` closes the receive channel *with* a cause (FakeRawConnection.kt:61) so the read flow **throws** — driving SessionManager's `eventChannel.close(e)` (SessionManager.kt:310-311) and routeEvents' catch-Throwable → `onConnectionLost` branch (P2pSessionImpl.kt:557-560), a code path **no shipped transport can produce**.
  2. **Peer-side close leaves the local fake alive.** `close()` only closes the local send channel (FakeRawConnection.kt:44-48). The peer's `read()` completes normally, but the peer's `_state` stays `Connected` and the peer's subsequent `write()`s **succeed** into the unbounded orphaned channel. Real transports: remote close → local read loop EOF → `closeSocketOnce()` + `_state = Closed` → later writes throw. So `observeRawState` (P2pSessionImpl.kt:222-233) — a load-bearing detector added specifically for remote-initiated ends — can never fire from a peer-side close in commonTest.
  3. **Consequence — deterministic tests over a nondeterministic product.** On real transports, ANY remote wire end (crash, FIN, reset) triggers BOTH `observeRawState` (raw state → Closed → `onConnectionLost` → Reconnecting for outgoing-with-policy) AND routeEvents channel-completion (→ `markCleanlyClosed` → terminal Closed, no retry). These race with **opposite outcomes** (each is gated on `_state == Connected`, so whichever wins the connectionLock decides retry-vs-no-retry). With the fake, "abrupt failure" (`breakWith`) deterministically reconnects (both signals agree) and "peer hangup" (`b.close()`) deterministically clean-closes (only one signal exists). Every `breakWith` call site — all 11: ReconnectPolicyTest.kt:97,130,165,205,237,278,309; SessionReconnectRotationTest.kt:138,234,329; NetworkPathRecoveryTest.kt:177 — breaks the **local** side; zero commonTests simulate a remote-initiated raw termination.
- Evidence:
  ```kotlin
  // FakeRawConnection.kt:58-63 — models an exception no real transport throws
  fun breakWith(cause: Throwable) { ... receive.close(cause); send.close() }
  // JvmRawConnection.kt:155-158 — real error path completes the flow normally
  } catch (e: IOException) { ...; break }
  // P2pSessionImpl.kt:548-552 — the branch real transports actually hit on hangup
  // Channel completed without explicit close or error frame ... markCleanlyClosed()
  ```
- Runtime impact: none directly (test code) — but the session layer's remote-termination semantics (retry vs clean-close), the single most user-visible reconnect behavior, are effectively unvalidated against what shipped transports actually deliver. Tests asserting "wire break → Reconnecting" pass via a synthetic exception path; on hardware the same break may clean-close with no retry (or vice versa). **Cross-ref for A03/A06:** the underlying product race (`markCleanlyClosed` vs `onConnectionLost` on every remote wire end) looks real and undecided in P2pSessionImpl — flagging for the session owner; my finding here is that the fixture makes it untestable.
- Failure class: none (test blindness) / hides a candidate product race
- Proposed fix (do NOT implement): teach FakeRawConnection the real terminal contract: (a) `breakWith` should close the receive channel **without** cause and flip state (matching real), with a separate opt-in `breakWithException` retained only if a test explicitly wants the defensive path; (b) peer-close must flip the remote side's state to Closed and fail its subsequent writes (e.g. wire the pair so `close()` also closes the partner's receive channel and latches a shared "wire down" flag checked in `write`); (c) add a pair-level `hangUp(side)` helper. Then add commonTests driving remote hangup and assert whichever retry-vs-clean-close semantics A03 decides is canonical.
- Required tests: new SessionFlow/ReconnectPolicy cases: "remote raw termination while outgoing policy Enabled" pinning the intended outcome; regression that `observeRawState` fires on remote close.

### TST-2 — Fake write-failure exception type matches no platform pair
- Severity: Low | Confidence: Confirmed
- File(s): FakeRawConnection.kt:37-40 (write → `send.send` throws kotlinx `ClosedSendChannelException`, an `IllegalStateException` subtype, only after close/break); JvmRawConnection.kt:116-137 (IOException, incl. watchdog-wrapped IOException); IosRawConnection.kt:188-209, 252-279 (`IllegalStateException` / `NetworkException`)
- Category: bug (fidelity divergence, currently latent)
- Root cause: core deliberately catches `Throwable` around PING/PONG/CLOSE sends (P2pSessionImpl.kt:519-521, 582-589), so today's tests pass identically. But `P2pSessionImpl.send()` (:235-242) does **not** wrap the raw exception — [KNOWN API-2: send() leaks raw IOException]. Any future test pinning the app-visible failure type of `send()` against the fake would observe `ClosedSendChannelException` and be blind to the IOException (JVM/Android) vs IllegalStateException/NetworkException (iOS) divergence the fake cannot represent.
- Runtime impact: none today; blinds the exact test that API-2's fix will need. | Platforms: all | User-visible: no
- Failure class: none
- Proposed fix (do NOT implement): when API-2 is fixed (typed error from send), give FakeRawConnection an injectable `writeFailure: (() -> Throwable)?` so tests can simulate platform-shaped raw exceptions; assert the wrapper type in commonTest.
- Required tests: send()-failure-type test accompanying the API-2 fix.

### TST-3 — FakeDataTransport's incoming flow can never terminate with an error; `startAcceptingIncoming` has no failure handling and is therefore untested against accept-loop death
- Severity: Medium | Confidence: Confirmed for the fixture gap; Uncertain for product impact (would need A03/A06 confirmation of scope-level exception behavior)
- File(s): FakeDataTransport.kt:26, 55-59, 61-64 (Channel + `receiveAsFlow`; `close()` closes without cause); JvmLanDataTransport.kt:139-147 (real accept loop: on accept failure while not closed → `close(e)` — the flow terminates **with a cause**); SessionManager.kt:146-152 (`transport.incomingConnections().onEach{...}.launchIn(scope)` — no catch, no retry, no completion handling)
- Category: bug (test-infrastructure blind spot over an unhandled product path)
- Evidence:
  ```kotlin
  // SessionManager.kt:146-151 — nothing handles a failed incoming flow
  fun startAcceptingIncoming(transports: List<DataTransport>) {
      for (transport in transports) {
          transport.incomingConnections()
              .onEach { connection -> handleIncoming(connection) }
              .launchIn(scope)
  ```
- Root cause: the fake's incoming channel is only ever closed cleanly, so no commonTest can exercise "accept loop failed with exception". On the real JVM transport a `ServerSocket.accept()` error (e.g. EMFILE fd exhaustion) fails the callbackFlow; the `launchIn` coroutine then dies with that exception into the kit scope — at minimum silently ending inbound accepts for that transport for the kit's lifetime, with nothing surfaced to the app.
- Runtime impact: on real hardware an accept-loop failure silently kills inbound connectivity; no test exists or can exist against the current fake. | Platforms: JVM/Android primarily | User-visible: potentially (peers can no longer connect in)
- Failure class: none in tests / potential silent degradation in product (cross-ref A03)
- Proposed fix (do NOT implement): add `failIncoming(cause: Throwable)` to FakeDataTransport (`incoming.close(cause)`); add a commonTest pinning whatever resilience SessionManager should have (log + optional resubscribe, or at minimum a typed diagnostics event).
- Required tests: "incoming flow fails → kit survives, logs, and (decision) resumes accepting or reports" in commonTest.

### TST-4 — FakeDiscoveryTransport buffer semantics diverge from all three production transports; its KDoc overclaims parity
- Severity: Low | Confidence: Confirmed
- File(s): FakeDiscoveryTransport.kt:18-30 (`replay=0, extraBufferCapacity=64, BufferOverflow.SUSPEND`, suspending `emit`; KDoc: "replay = 0 to match the production semantics"); JvmLanDiscoveryTransport.kt:49-52, AndroidLanDiscoveryTransport.kt:97-100, IosLanDiscoveryTransport.kt:89-92 (all `replay=0, extraBufferCapacity=256, DROP_OLDEST`, non-suspending `tryEmit`)
- Category: bug (fidelity divergence; doc claim inaccurate)
- Root cause: replay matches; overflow strategy and emitter behavior do not. Production silently **drops oldest** events under burst; the fake **suspends** the emitter. Consequences: (a) PeerRegistry's tolerance of lost events (mDNS re-announce is the recovery mechanism) is untestable and untested; (b) a test that emits >64 events before the registry's collector keeps up would deadlock instead of dropping — a confusing failure shape; (c) same divergence class as [KNOWN PRM-17] (provisioning fakes replay=0 vs production replay=1) — this is the inverse direction but the identical hazard.
- Runtime impact: none today (no current test bursts). | User-visible: no | Failure class: none
- Proposed fix (do NOT implement): mirror production (`extraBufferCapacity=256, DROP_OLDEST`, expose `tryEmit`-shaped emit) and fix the KDoc sentence; optionally keep a `strictDelivery` constructor flag for tests that genuinely need lossless delivery.
- Required tests: PeerRegistry burst test (peer set converges despite dropped intermediate events).

### TST-5 — [improvement] No reusable write-fault injection (blocked/slow/transient-fail) in the shared fixture
- Severity: Improvement | Confidence: Confirmed
- File(s): FakeRawConnection.kt:37-40 (writes always succeed instantly — `Channel.UNLIMITED` never suspends); CloseSemanticsTest.kt:117-143 (`WedgedWriteConnection`, a one-off private fake with a NonCancellable gate modeling the 30 s watchdog scenario)
- Category: improvement
- Detail: the wedged-write semantics (JvmRawConnection.kt:76-147, IosRawConnection.kt:221-263) are core to AUDIT-2026-06 #4/#18, yet the only test double that can model them is private to one test. Nothing can model: a write that blocks then succeeds, a transient write error on a still-open connection (distinct from full `breakWith` kill — relevant to "one transfer failure must not tear down a healthy session"), or per-write latency. Promote a gated-write knob (`suspendWrites()` / `failNextWrite(t)`) into FakeRawConnection so keep-alive-under-stalled-writer and mid-transfer-write-error scenarios become writable in commonTest.

### TST-6 — [improvement] FakeDataTransport models neither the start() contract nor close-visibility
- Severity: Improvement | Confidence: Confirmed
- File(s): FakeDataTransport.kt (no `start()` override → inherits always-success default from DataTransport.kt:38); JvmLanDataTransport.kt:60-81 (start-after-close → `Result.failure`, idempotent success path); FakeDataTransport.kt:57-59 (`emitIncoming` ignores `trySend` result — silent no-op after `close()`); `closed` is private with no getter (tests cannot assert the kit closed its transports; KitLifecycleTest had to build its own `TrackingTransport` for exactly that)
- Category: improvement
- Detail: add a start-behavior knob (record calls; fail-after-close per the real contract), expose `isClosed`, and make `emitIncoming` `check()` the trySend result so a test that stages a connection after close fails loudly instead of silently doing nothing.

### TST-7 — [improvement] Unsynchronized mutable state in fixtures read/written across dispatcher threads
- Severity: Improvement (latent race, benign today) | Confidence: Confirmed
- File(s): FakeRawConnection.kt:35 (`writtenChunks: MutableList` — appended from session writer coroutines on Dispatchers.Default; read live while the keep-alive loop is still writing at KeepAliveTest.kt:192); FakeDataTransport.kt:35-36 (`_connectCalls` plain MutableList; `connectCalls` does `toList()` — concurrent `connect()` from two peers would race)
- Category: improvement
- Detail: no current test triggers a corrupting interleaving (per-session writes are sendMutex-serialized; reconnect dials are sequential; SimultaneousOpenTest gives each kit its own transport instance — verified SimultaneousOpenTest.kt:58-88). Cheap hardening: back both with a lock or atomic snapshot list to keep future multi-peer tests from inheriting a heisen-flake.

### TST-8 — [improvement] Address-rotation coverage drives re-resolution only via `PeerEvent.Updated`, which no shipped JVM/Android transport emits; fake `refresh()` has no side effects
- Severity: Improvement | Confidence: Confirmed
- File(s): SessionReconnectRotationTest.kt:148 (`aliceDiscovery.emit(PeerEvent.Updated(bobV2))`); JVM emits only Found/Lost (JvmLanDiscoveryTransport.kt:134,186), Android likewise (AndroidLanDiscoveryTransport.kt:524,582) — [KNOWN DSC-1]; iOS does emit Updated (IosLanDiscoveryTransport.kt:269,651); PeerRegistry treats Found/Updated identically (PeerRegistry.kt:82-83), so the divergence is currently benign; real JVM `refresh()` re-emits **Found** for cached services (JvmLanDiscoveryTransport.kt:212-252) while the fake's `refresh()` only increments a counter (FakeDiscoveryTransport.kt:60-62) — permitted by the SPI KDoc (DiscoveryTransport.kt:39-41), but it means the production re-resolution stimulus shape (repeat Found) is never what rotation tests exercise
- Category: improvement
- Detail: add a Found-based variant of the rotation scenario (1-line change to an existing test) so that if `Found`-for-known-peer and `Updated` handling ever diverge in PeerRegistry, the JVM/Android-real shape stays covered. Optionally let the fake's `refresh()` re-emit its last-known peers to mimic the JVM behavior behind a flag.

### Part 2 — repo-wide sweep findings

### TST-9 — The e91e094 `strictInvariants` safety net is inert in every kit-level suite: P2pKitImpl never passes it, and SessionStore warnings go to NoOp loggers [owner S3]
- Severity: High (test blind spot defeating a shipped audit fix's stated purpose) | Confidence: Confirmed
- File(s): SessionManager.kt:109 (`strictInvariants: Boolean = false`), :119 (forwards to SessionStore); P2pKitImpl.kt:153-184 (the **only** SessionManager construction in the repo — grep-verified — passes no `strictInvariants`); SessionStore.kt:272-277 (`if (strictInvariants) error(message)` else warn); strict construction exists only at SessionStoreInvariantTest.kt:46,78
- Category: bug (test infrastructure)
- Root cause: REMEDIATION_2026-07.md:48 records finding #19 as fixed via "`strictInvariants` (throws in tests, warns in prod)". In reality only the 3 direct `SessionStore(...)` constructions inside the enforcement test run strict. Every suite that actually stresses the store's invariants — SessionFlowTest, ReconnectPolicyTest, SessionReconnectRotationTest, SimultaneousOpenTest, NetworkPathRecoveryTest, KitLifecycleTest, ManualPeerIdentityTest — builds kits through `P2pKit.create` → P2pKitImpl → strict=false, and (grep-verified) no commonTest suite installs a non-NoOp logger (`RecordingLogger` is private to SessionStoreInvariantTest.kt:175). Net effect: an invariant violation during simultaneous-open arbitration or reconnect rearm surfaces as a warn into a NoOp logger — i.e., nothing.
- Runtime impact: none in prod (by design); in tests, the safety net covers only synthetic direct-store scenarios. | User-visible: no | Failure class: none (blindness)
- Proposed fix (do NOT implement): thread an internal-only knob (e.g. internal builder/`P2pKitImpl` constructor param or an internal `TestHooks` object in commonTest) so kit-level suites run `strictInvariants = true`; no public API change needed (`[API-CHANGE]` not required — internal wiring suffices).
- Required tests: after wiring, the existing suites ARE the test — plus one meta-test that a violation inside a kit-built store throws under the flag.

### TST-10 — Negative assertions bounded by real-time windows shorter than the behavior they negate [owner S3]
- Severity: Medium | Confidence: Confirmed
- File(s): ReconnectPolicyTest.kt:247 and :283 (`delay(150)` then "Factory must not be called after close()/stop()") with `ReconnectPolicy.Enabled(maxAttempts = 5, retryDelayMillis = 1_000)` configured at :215/:264; NetworkPathRecoveryTest.kt:227 (`delay(100)` then "Unknown must be a no-op" — same class, milder: the reaction under test would be immediate)
- Category: bug (assertion cannot catch the regression it names)
- Evidence:
  ```kotlin
  // ReconnectPolicyTest.kt — retryDelayMillis = 1_000, but:
  alice.stop()
  delay(150)
  assertEquals(attemptsAtStop, attempts.value, "Factory must not be called after kit.stop()")
  ```
- Root cause: at close()/stop() time the retry loop is parked in its 1 s `delay`. If cancellation silently regressed, the next factory call would land up to ~1 s later — outside the 150 ms observation window. The test only catches "retry fires immediately after stop", not "retry loop not cancelled". Same pattern class as [KNOWN PRM-17]'s `delay(50)` windows in provisioning.
- Proposed fix (do NOT implement): assert structurally instead of temporally — e.g. expose/observe the handler job's completion (session scope cancelled ⇒ join the scope's job with a bounded wait), or lower `retryDelayMillis` below the window so a live loop must fire inside it (no timeout-widening involved).
- Required tests: rewritten post-stop/post-close non-retry assertions as above.

### TST-11 — The only remote-CLOSE-frame test accepts `Closed || Failed`, leaving the spec's clean-close distinction unpinned [owner S3]
- Severity: Medium | Confidence: Confirmed
- File(s): SessionFlowTest.kt:222-231 (`closeTransitionsSessionToClosed`: waits `first { Closed || Failed }`, then `assertTrue(finalState == Closed || finalState == Failed)`)
- Category: bug (relaxed assertion on a spec invariant)
- Root cause: "clean closes never trigger retry" and Closed-vs-Failed are app-visible contract (BRIEF invariants; States.kt KDoc). The receiving side of a `close()` (CLOSE frame → `ProtocolEvent.Close` → `markCleanlyClosed` → **Closed**) is asserted only as "some terminal". With the fakes this is deterministically Closed (see TST-1 — the raw-state race doesn't exist in fakes), so the disjunction is pure slack today; on real transports the outcome genuinely races (TST-1 item 3) and this test shape would mask either resolution. Contrast: the sibling waits in ReconnectPolicyTest.kt:100-105/:208-212, KeepAliveTest.kt:74-77, NetworkPathRecoveryTest.kt:133-139 all pin the exact terminal state after the same disjunctive wait — this one does not. (IosLanLifecycleTest.kt:226-233 has the same disjunction but justifies it in a comment against a real network — acceptable there.)
- Proposed fix (do NOT implement): assert `assertEquals(Closed, finalState)` in the fake-based test; if that reveals instability, that is TST-1's product race surfacing — fix the race, not the assertion.
- Required tests: strict version of this test; plus the TST-1 remote-hangup counterpart once the fixture supports it.

### TST-12 — [improvement, repo-wide] Zero virtual-time usage: every async suite is `runBlocking` + wall clock; kotlinx-coroutines-test is a declared-but-unused dependency in 5 modules
- Severity: Improvement (flake debt + slow suites; no single test is broken by it) | Confidence: Confirmed
- Evidence: `runTest` count is 0 across all test sources; `import kotlinx.coroutines.test` count is 0; dependency declared at p2p-core/build.gradle.kts:106, p2p-transport-lan/build.gradle.kts:69, p2p-network-provisioning-android/build.gradle.kts:24, p2p-network-provisioning-desktop/build.gradle.kts:23, sample-kmp-shared/build.gradle.kts:24.
- Load-bearing real-time inventory (commonTest, all `runBlocking` on Dispatchers.Default):
  - KeepAliveTest.kt:67 (ping 50 ms/timeout 150 ms), :171-186 (PONG cadence 25 ms vs 600 ms budget over a 900 ms real sleep — the file's own comment at :166-170 argues the margin against "a saturated parallel suite"; still the top starvation-flake candidate);
  - SessionReconnectRotationTest.kt:144-148 — comment admits the design race: "retryDelayMillis (200ms) is more than enough for the update to land before the next dial" — Updated-event propagation through PeerRegistry's async pipeline racing a real 200 ms timer; loses under thread starvation → asserts stale hints at :159-162;
  - ReconnectPolicyTest/NetworkPathRecoveryTest waits on the **transient** `Reconnecting` via conflated StateFlow (9 sites, e.g. ReconnectPolicyTest.kt:133,166,238,279,310) — safe only because real retry delays (200 ms–1 s) hold the state long enough;
  - 91× `withTimeout(5_000)` liveness bounds; iOS/JVM loopback suites are legitimately wall-clock (real network).
  - Countervailing good practice: clocks are injected (`clock = { systemTimeMillis() }`) in registry/protocol tests (PeerRegistry, Reassembler eviction) — those are deterministic already.
- Proposed direction (do NOT implement): migrate pure-fake suites (KeepAlive, ReconnectPolicy, Rotation, NetworkPathRecovery, SessionFlow, SimultaneousOpen) to `runTest` + virtual time; either use the dependency or drop it from modules whose tests will stay wall-clock.

### TST-13 — [improvement] NoOp-logger blind spots: warn-only diagnostics are asserted nowhere; no shared RecordingLogger
- Severity: Improvement | Confidence: Confirmed
- Evidence: all commonTest kits/logging default to NoOp (grep: only SessionStoreInvariantTest.kt:63 installs a recording logger, and its class is `private` at :175). Warn-only invariants that no test can ever observe: ZOMBIE-session detection (P2pSessionImpl.kt:499-514), stuck-Reconnecting watchdog (:679-688), PONG/PING send-failure warnings (:519-521, :587), SessionStore soft invariants (SessionStore.kt:272-277, production mode), PeerRegistry evictLoop swallow (PeerRegistry.kt:162-164 — deliberately logger-free).
- Proposed direction: promote RecordingLogger to `testfixtures/`, and have the heavyweight suites assert "no unexpected warn/error" at teardown (allowlist expected ones). This converts a whole class of silent degradations into test failures without touching production code.

### TST-14 — [improvement] Fixture duplication drift: three discovery/transport fakes with three different event-flow configs
- Severity: Improvement | Confidence: Confirmed
- Evidence: shared FakeDiscoveryTransport (64/SUSPEND, FakeDiscoveryTransport.kt:26-30); PeerRegistryTest's private `FakeDiscovery` (PeerRegistryTest.kt:39 ff.); KitLifecycleTest's `TrackingTransport` with `MutableSharedFlow(extraBufferCapacity = 16)` (KitLifecycleTest.kt:~163); production uses 256/DROP_OLDEST. Also purpose-built one-offs that are fine but should be discoverable: CloseSemanticsTest's `WedgedWriteConnection` (CloseSemanticsTest.kt:117), FileTransferFlowTest's inline no-op protocol (FileTransferFlowTest.kt:547).
- Proposed direction: consolidate discovery fakes on the shared fixture (parameterize what PeerRegistryTest/KitLifecycleTest need: counters exist already); align buffer configs with production (see TST-4).

### TST-15 — [improvement] SimultaneousOpenTest accepts a `Reconnecting` survivor as "live" [owner: S3]
- Severity: Improvement (relaxed assertion, narrow) | Confidence: Confirmed
- Evidence: SimultaneousOpenTest.kt:113-121 — `state == Connected || state == Reconnecting` for the arbitration winner on both sides. A regression where arbitration closes the WRONG physical connection (winner's raw torn down, session limps into Reconnecting) would pass. The follow-up `delay(50)` at :126 is teardown-quiescence only (benign).
- Proposed direction: assert `Connected` for both survivors; additionally assert the surviving session can still exchange one message (would catch keeping the wrong/dead connection).

### TST-16 — [improvement] Integration layer is environment-conditional and mutates global JVM state
- Severity: Improvement (Low) | Confidence: Confirmed
- Evidence: `Assume.assumeTrue(routable != null)` silently skips the entire real-network integration layer on hosts without a routable IPv4 (JvmLanLoopbackTest.kt:60-64; KmpConsumerLoopbackTest.kt:58-61); `System.setProperty` mutation of `user.home` + JmDNS bind address in 3 suites (JvmLanLoopbackTest ×4, KmpConsumerLoopbackTest ×5, ManualIpLoopbackTest ×3) restored in teardown but only safe under serial, single-JVM execution (current Gradle default); mDNS suites advertise on the developer's real LAN, isolated by per-run unique appIds (`p2pkit-itest-${System.currentTimeMillis()}` — two suites instantiated in the same millisecond would collide, theoretical). No CI gate asserts the loopback tests actually RAN rather than skipped.
- Proposed direction: emit a hard failure (or a required-check marker) in CI when the Assume trips; document the serial-execution assumption next to the property swaps.
- Known adjacents not re-derived: [KNOWN SMP-8] (KmpConsumerLoopbackTest subscription race), [KNOWN SMP-14] (its `@AfterTest cleanup()` at KmpConsumerLoopbackTest.kt:42-49 handles temp homes/property but kit stops live in test bodies — the leak-if-stop-throws pattern), [KNOWN PRM-17]/[KNOWN PRM-19] (provisioning fakes replay=0 + delay(50) windows; conditional assert at JvmNetworkProvisioningManagerTest.kt:90-96), [KNOWN FIL-11]/[KNOWN FIL-15] (FileTransferFlowTest no-op/racy asserts), [KNOWN API §3] (no dedicated builder test).

## 3. Missing tests

| Invariant untested | Why it matters | Where it should live | Type | Priority |
|---|---|---|---|---|
| Remote-initiated raw termination → defined session outcome (retry vs clean close) | The most common field event (peer crash/kill); currently racy in product and unmodelable in fakes (TST-1) | commonTest SessionFlow/ReconnectPolicy + fixture upgrade | combination | P1 |
| Peer CLOSE frame → exactly `Closed`, never `Failed` | Spec: clean closes never retry; only test is disjunctive (TST-11) | SessionFlowTest | combination | P1 |
| Kit-level suites under `strictInvariants=true` | e91e094 safety net currently inert outside its own unit test (TST-9) | commonTest infra (internal knob) | combination | P1 |
| Accept-loop failure → kit behavior (log/resume/report) | Silent loss of inbound connectivity; no handling in SessionManager.kt:146-152 (TST-3) | commonTest + SessionManager decision | combination | P1 |
| JVM/Android write-after-close raw exception shape | iOS has IosRawConnectionTest.kt:49-59 pinning ISE; no JVM twin — parity pair is a stated invariant | p2p-transport-lan jvmTest | unit | P2 |
| Reconnect retry against typed `P2pError.ConnectionFailed` (what real transports actually throw, JvmLanDataTransport.kt:119) | All commonTest factories throw RuntimeException; typed-error path through performConnect/retry classification unexercised | ReconnectPolicyTest | unit | P2 |
| Address rotation via repeat `Found` (JVM/Android-real shape, not `Updated`) | DSC-1: no shipped JVM transport emits Updated (TST-8) | SessionReconnectRotationTest | unit | P2 |
| PeerRegistry convergence under event burst with DROP_OLDEST | Production drops events; fake can't (TST-4) | PeerRegistryTest + fixture change | unit | P3 |
| Post-stop non-retry asserted structurally (not a 150 ms window) | TST-10 windows can't catch a 1 s-late retry | ReconnectPolicyTest | unit | P2 |
| Builder/config coverage | [KNOWN API §3] — flag only | p2p-core commonTest | unit | P2 |
| Android transport paths, WifiManagerWrapperImpl, Android/Ios NetworkPathObserver | No instrumented tests by policy [CATALOGUED]; manual recipes in INTERNAL_TESTING.md — inventory-complete, no action proposed here | manual (device matrix) | manual | — |

## 4. Section summary

**What S15 owns.** The four in-memory fakes standing in for the transport SPI in commonTest. 15 of 29 commonTest suites build on them; the map's claim "depended on by all commonTest suites" (CODEBASE_REVIEW_MAP_2026-07.md:334) is slightly overstated — pure protocol/codec suites don't use them, and PeerRegistryTest deliberately rolls its own — otherwise the map's S15 entry (files, blast-radius rationale, Medium risk) is accurate.

**Overall health.** The fixtures are small, readable, and well-documented, and their consumers are disciplined (bounded waits, exact-state pins in most suites, lifecycle counters asserted). But the two highest-leverage fidelity axes are wrong or missing: remote-initiated termination (TST-1) and failure injection (TST-3/TST-5). Because real transports NEVER throw from `read()` and ALWAYS self-close on remote EOF, while the fake does the opposite on both counts, the session layer's most safety-critical behavior — what happens when the other device disappears — is validated only against synthetic semantics. Part-2 wise, the suite is `runBlocking`-everywhere (virtual time unused despite the dependency), and the e91e094 invariant safety net plus every warn-level diagnostic is invisible in exactly the suites meant to benefit (TST-9/TST-13). No test masking was found: 1 deliberate `@Ignore` diagnostic, both known-flaky churn tests active.

**Repo test-suite inventory.**

| Module / source set | Suites | What they cover | Gaps |
|---|---|---|---|
| p2p-core commonTest (runs on JVM + iosSimulatorArm64; 149 tests per REMEDIATION gate) | 29 files: 19 internal (session, reconnect, rotation, path recovery, keep-alive, handshake ×2, simultaneous-open, store invariants, kit lifecycle, close semantics, file-transfer flow/error-isolation, manual-peer identity, permission gate, registry, transport manager, storage) + 10 protocol (codec, framing, chunker, reassembler, HELLO/offer payloads, streaming sender/receiver, protocol integration) | Session/protocol/reconnect logic against fakes | Remote-hangup semantics (TST-1); strict invariants off (TST-9); everything wall-clock (TST-12) |
| p2p-core jvmTest | FilePeerIdStorageTest, PeerIdPersistenceIntegrationTest, FileTransferJvmTest | JVM peer-id persistence, real-file transfer plumbing | — |
| p2p-transport-lan jvmTest | JvmLanLoopbackTest (2 kits, real TCP+mDNS, 200 KB binary, SHA-256 5 MiB file, fd-leak regression), HostSelectorTest | The only automated cross-kit integration | Env-conditional skip (TST-16); no write-after-close pin (missing-tests) |
| p2p-transport-lan appleTest (iosSimulatorArm64) | IosLanLoopbackTest, IosLanLifecycleTest (2 known-flaky churn tests active), IosBonjourTest, IosRawConnectionTest, AnnounceCacheReconcileTest, IosLanDiagnosticTest (@Ignore, deliberate) | Real Bonjour/NWConnection loopback + #8/#18 fix regressions | Simulator can't deliver result_removed [CATALOGUED, smoke A4] |
| p2p-transport-lan androidMain | none | — | By policy: manual recipes (INTERNAL_TESTING.md); parity with JVM pair is the safeguard [CATALOGUED] |
| p2p-network-provisioning-android androidHostTest | AndroidNetworkProvisioningManagerTest | Hotspot/join state machine vs fake wrappers | [KNOWN PRM-17]; WifiManagerWrapperImpl manual-only [CATALOGUED] |
| p2p-network-provisioning-desktop test | JvmNetworkProvisioningManagerTest, ManualIpLoopbackTest | Manual-IP info + loopback join | [KNOWN PRM-19] conditional assert |
| sample-kmp-shared | KmpCallsiteSmokeTest (commonTest), KmpConsumerLoopbackTest (jvmTest) | Consumer-shaped API usage + loopback | [KNOWN SMP-8, SMP-14] |
| p2p-sample-* / iosApp | none | — | Samples/harness — by design |

**Top 3 risks.**
1. TST-1: commonTest validates remote-termination semantics no shipped transport produces, while hiding a candidate product race (`markCleanlyClosed` vs `observeRawState`→`onConnectionLost`) whose resolution decides retry-vs-no-retry in the field (cross-ref A03/A06).
2. TST-9 + TST-13: the invariant safety net and every warn-level diagnostic are dark in the suites that exercise the risky paths — regressions in store/zombie/stuck-reconnect invariants cannot fail any test today.
3. TST-12 + TST-10: pervasive wall-clock coupling — one admitted 200 ms propagation race, a 600 ms starvation budget, and negative-assertion windows that cannot catch late retries — is standing flake/blindness debt ahead of an RC.
