# A6-CONN — S7 Data transports & raw connections review

Scope: 6 sources + 3 tests under `p2p-transport-lan/src/`. All call-site claims verified against
`p2p-core/src/commonMain` (`SessionManager`, `P2pSessionImpl`, `P2pKitImpl`, `TransportManager`,
`DefaultP2pProtocol`, `Handshake`, `RawConnection`/`DataTransport` SPI) and the cinterop header
`p2p-transport-lan/src/nativeInterop/cinterop/p2pkit_nw.h`. `diff` run over the JVM/Android pair.

## 1. Per-file verdicts

| File | Lines | Verdict | Tests covering it | Test gaps (1 line) |
|---|---|---|---|---|
| jvmMain/.../JvmLanDataTransport.kt | 181 | findings: CON-2, CON-3, CON-4, CON-9(minor) · improvements: CON-18 | JvmLanLoopbackTest (full-stack, indirect) | no unit tests for dial-cancel, accept-failure, close/start race |
| androidMain/.../AndroidLanDataTransport.kt | 173 | findings: CON-2, CON-3, CON-4, CON-10 | none (no instrumented Android tests — catalogued) | parity held only by manual diff; same gaps as JVM |
| appleMain/.../IosLanDataTransport.kt | 766 | findings: CON-2(iOS variant), CON-4, CON-8, CON-9, CON-11, CON-12, CON-13 · improvements: CON-15, CON-16 | IosLanLoopbackTest (indirect); IosLanLifecycleTest (adjacent, not in scope) | listener-failed path, stop-vs-start race, rebind debounce race untested |
| jvmMain/.../JvmRawConnection.kt | 208 | findings: CON-1, CON-6, CON-7(contributing) · improvements: CON-14 | JvmLanLoopbackTest.remoteDisconnectClosesLocalSocketFd + loopback suite | watchdog and close-under-cancellation have zero automated coverage |
| androidMain/.../AndroidRawConnection.kt | 207 | findings: CON-1, CON-6, CON-7 (identical code) | none direct | entire class untested; parity verified by diff only (log-only divergence) |
| appleMain/.../IosRawConnection.kt | 383 | findings: CON-5, CON-7(contributing) | IosRawConnectionTest, IosLanLoopbackTest | send deadline manual-only; no leak/cancel-race assertions |
| jvmTest/.../JvmLanLoopbackTest.kt | 351 | clean (asserts fd invariant robustly via `socket.isClosed`) | n/a | covers EOF path only; no watchdog, no cancelled-close, keep-alive disabled (60 s ping) |
| appleTest/.../IosLanLoopbackTest.kt | 201 | improvements: CON-17 | n/a | no iOS analogue of the fd/cancel-leak assertion; keep-alive disabled |
| appleTest/.../IosRawConnectionTest.kt | 75 | improvements: CON-19 | n/a | write deadline + receive path explicitly not covered (documented as manual) |

JVM↔Android pair parity: `diff` of the two RawConnections and the two LanDataTransports shows
**only** logging/comment/TAG differences (JvmLanDiag vs `Log.d`/AndroidLanDiag) — control flow,
CAS logic, timeouts, and error paths are line-for-line identical. Lockstep invariant currently holds.
The one behavioral logging divergence is CON-10.

## 2. Findings

### CON-1 — JVM/Android `close()` and read-loop skip fd release when the calling coroutine is cancelled
- Severity: High | Confidence: Confirmed (kotlinx semantics: `withContext` throws CancellationException on entry/exit when the caller's job is cancelled, without running/using the block)
- File(s): p2p-transport-lan/src/jvmMain/kotlin/dev/p2pkit/transport/lan/JvmRawConnection.kt:178-189 (close), :149-176 (read); androidMain/.../AndroidRawConnection.kt:177-188, :149-175 (identical). Call sites: p2p-core/.../SessionManager.kt:386-389, :574; p2p-core/.../P2pSessionImpl.kt:320, :340
- Category: bug
- Root cause: the f4dd3a9 fd-leak fix routes every release through `closeSocketOnce()`, but two of the three paths to it sit *after a cancellable suspension point*:
  1. `close()` does `withContext(Dispatchers.IO) { closeSocketOnce() }` — when called from an already-cancelled coroutine, `withContext` throws CE **before** the block runs; `closeSocketOnce()` and `connScope.cancel()` are both skipped, yet `_state.value = Closed` was already set (state says Closed, socket open — state/socket incoherence).
  2. the read flow's post-loop release (`closeSocketOnce()` at JvmRawConnection.kt:173) is skipped when the collector is cancelled: `withContext(Dispatchers.IO) { input.read(buffer) }` rethrows CE once the blocking read returns, which propagates past the `catch (e: IOException)` and jumps out of the flow builder before line 173.
- Evidence:
  ```kotlin
  override suspend fun close() {
      _state.value = ConnectionState.Closed
      ...
      withContext(Dispatchers.IO) {   // throws CE here if caller cancelled → skips both lines below
          closeSocketOnce()
      }
      connScope.cancel()
  }
  ```
  Guaranteed-cancelled call site (SessionManager.kt:386-389):
  ```kotlin
  } catch (e: CancellationException) {
      readerJob.cancel()
      runCatching { rawConnection.close() }   // close() no-ops; runCatching swallows the CE it throws
      throw e
  }
  ```
- Runtime impact: every cancellation that lands during a dial/handshake (app cancels `kit.connect(peer)` — routine lifecycle-scope pattern — or `kit.stop()` during an in-flight inbound handshake) leaks the socket fd. The readerJob's IO thread stays parked in `input.read()` until the remote closes (≥10 s remote handshake timeout; **forever** if the remote is dead), and the fd is retained until GC because the read loop's release is also skipped. `connScope`'s Job is never cancelled (minor). Same window in `rearmWith` when session teardown races a reconnect. `transitionToTerminal` is immune (wraps close in `NonCancellable`), which is why the steady-state path works and only cancellation paths leak. iOS is immune: `close()` delegates to non-suspending `cancelNow`.
- Failure class: leak (fd + parked IO thread, accumulates) | Platforms: JVM, Android | User-visible: yes (fd limits reached under churn; feeds CON-3)
- Proposed fix (do NOT implement): make close() cancellation-proof — `closeSocketOnce()` is a cheap thread-safe syscall; call it (and `connScope.cancel()`) before/without the cancellable `withContext`, or wrap the body in `withContext(NonCancellable + Dispatchers.IO)`. In `read()`, wrap the loop in `try { … } finally { closeSocketOnce(); _state.value = Closed }`. Mirror identically in AndroidRawConnection.
- Required tests: jvmTest unit — call `close()` from a coroutine whose job is already cancelled, assert `socket.isClosed`; cancel a read collector mid-block, close remote side, assert `socket.isClosed`.

### CON-2 — Cancelled dial leaks the freshly-connected socket (`withContext` discards its result on caller cancellation)
- Severity: Medium | Confidence: Confirmed (documented `withContext` behavior: result discarded + CE thrown when calling coroutine is cancelled)
- File(s): jvmMain/.../JvmLanDataTransport.kt:99-121; androidMain/.../AndroidLanDataTransport.kt:93-115; appleMain/.../IosLanDataTransport.kt:482-490 (iOS variant)
- Category: bug
- Root cause: `val socket = withContext(Dispatchers.IO) { val s = Socket(); try { s.connect(...); s } catch (e: Throwable) { s.close(); throw ... } }` — the catch covers only a *failing* connect. If the caller is cancelled while the (uninterruptible) connect succeeds, `withContext` discards the returned socket and throws CE; nothing closes `s`. iOS variant: `connect()` catches only `TimeoutCancellationException` around `raw.state.first{...}`; a plain caller CE propagates without `raw.close()`, leaving a **started** `nw_connection_t` un-cancelled (it self-heals only because a P2pKit remote's 10 s handshake timeout eventually RSTs it → `failed` handler → `cancelOnce`; a manual-IP dial to a non-P2pKit endpoint has no such guarantee).
- Evidence (JvmLanDataTransport.kt:99-121): the only `s.close()` is inside `catch (e: Throwable)` for a failed `s.connect(...)`.
- Runtime impact: one leaked connected fd (JVM/Android, until GC/Cleaner) or one lingering nw_connection (iOS) per dial cancelled in the ≤5 s (JVM) / ≤10 s (iOS) connect window. Compounds with CON-1 under connect/cancel churn.
- Failure class: leak | Platforms: all three (iOS lesser) | User-visible: indirectly (fd pressure)
- Proposed fix: hoist the socket out of the `withContext` and close it in a `catch (e: CancellationException)` (rethrowing), or run the dial+wrap under a `try/finally` that closes on non-return. iOS: add `catch (e: CancellationException) { raw.cancelNow("connect cancelled"); throw e }`.
- Required tests: jvmTest — launch `transport.connect(peer)` against a local listener, cancel the job immediately, assert the accepted remote side observes close / no lingering local socket.

### CON-3 — Accept-loop failure propagates as an uncaught exception (Android app crash) and permanently kills inbound
- Severity: High | Confidence: Confirmed (code-path); crash consequence follows from standard Android uncaught-handler behavior
- File(s): jvmMain/.../JvmLanDataTransport.kt:140-147 + 162; androidMain/.../AndroidLanDataTransport.kt:130-137; consumed at p2p-core/.../SessionManager.kt:146-152; scope at p2p-core/.../P2pKitImpl.kt:78-79
- Category: bug
- Root cause: a non-cancellation `accept()` failure while the transport is open does `if (!closed) close(e)` — the callbackFlow completes **exceptionally**. The collector is `transport.incomingConnections().onEach { … }.launchIn(scope)` with `scope = CoroutineScope(Dispatchers.Default + SupervisorJob(...))` and **no CoroutineExceptionHandler**: the exception is uncaught. On Android the default uncaught handler kills the process; on JVM it prints to stderr and the kit silently continues **without inbound accept forever** (single-collector contract; nothing restarts the loop, no typed error, no state change — outbound and discovery keep working, so the failure is invisible).
- Evidence:
  ```kotlin
  } catch (e: Throwable) {
      if (!closed) close(e)   // flow fails → launchIn collector throws → uncaught in kit scope
      break
  }
  ```
- Runtime impact: realistic triggers are `EMFILE`/`ENFILE` under fd pressure — which CON-1/CON-2 make more likely — i.e. a non-conforming LAN peer opening connections (or heavy legitimate churn) can walk the app into a crash (Android) or silent inbound deafness (JVM). This is an SDK crashing its host app on a transient OS error.
- Failure class: crash (Android) / silent degradation (JVM) | Platforms: JVM, Android (iOS analogue is CON-8) | User-visible: yes
- Proposed fix: never fail the flow for recoverable accept errors — log + retry accept with a short backoff while `!closed` (EMFILE is transient); if the flow must fail, SessionManager's collector should catch and surface via `logger`/a typed transport-error channel rather than letting it escape `launchIn` (and P2pKitImpl's scope should carry a last-resort CoroutineExceptionHandler).
- Required tests: jvmTest — close the ServerSocket out from under the loop with `closed == false` (or inject an accept failure), assert the kit survives and the failure is observable (logged/typed), not process-fatal.

### CON-4 — stop() racing a slow start() orphans bound resources; both intended safety nets are defeated
- Severity: Medium | Confidence: Confirmed (code inspection of both layers; window = `STOP_START_MUTEX_TIMEOUT_MS` 5 s vs iOS 5 s listener bind)
- File(s): appleMain/.../IosLanDataTransport.kt:304-333 (start: no `closed` re-check after `buildListener()`), :688-732 (rebindNow **has** the re-check at :728-732), :501-511 (close); jvmMain/.../JvmLanDataTransport.kt:60-81 + 173-180; androidMain/.../AndroidLanDataTransport.kt:57-78 + 160-168; kit-level sweep p2p-core/.../P2pKitImpl.kt:284-296
- Category: bug
- Root cause (two defeated layers, same scenario):
  1. Transport layer: `close()` deliberately doesn't take `startMutex`. Interleaving `start()` checks `closed` (false) → `close()` sets `closed=true`, sees `listener`/`serverSocket` null, returns → `start()` finishes the bind and assigns. On iOS the bind is a **5-second** semaphore wait, so the window is real, and `start()` then also runs `startPathMonitor()` + `startForegroundObserver()` **after** close already tore those down (they were null at close time). `rebindNow` had exactly this bug and was given a post-rebuild `if (closed) { nw_listener_cancel(fresh); return }` re-check (AUDIT-2026-06); `start()` was not.
  2. Kit layer: `ensureStarted` (P2pKitImpl.kt:291-296) anticipates this — "Close whatever this bind loop just (re)opened; transport close() is idempotent" — and re-calls `transport.close()` after the bind when `stopped`. But all three transports open `close()` with `if (closed) return` (JvmLanDataTransport.kt:174, AndroidLanDataTransport.kt:161, IosLanDataTransport.kt:502): the second close **early-returns without closing the just-bound resource**, so the documented safety net is a no-op.
- Evidence (IosLanDataTransport.kt:322-332): `val l = buildListener() ?: return ...; listener = l; ...; startPathMonitor(); startForegroundObserver()` — no `closed` re-check, unlike rebindNow:728.
- Runtime impact: `kit.stop()` overlapping a slow `start()` leaves — iOS: a bound `nw_listener_t` on a live port, a running `nw_path_monitor_t`, and an `NSNotificationCenter` observer that retains the transport for the process lifetime (memory leak per kit instance; inbound connections it accepts are at least cancelled via the closed-channel → `cancelNow` path). JVM/Android: a bound ServerSocket leaks unless the incoming-connections collector happens to still be alive to run `awaitClose`.
- Failure class: leak | Platforms: all three (iOS worst) | User-visible: rarely (port held, memory)
- Proposed fix: (a) in iOS `start()`, mirror rebindNow's post-bind re-check (cancel fresh listener, skip monitor/observer when `closed`); (b) make all three `close()` implementations re-sweep current resources instead of latching on `closed` alone (keep the flag for the "refuse new work" meaning, but always cancel/close a non-null listener/serverSocket).
- Required tests: unit per platform — call `close()` concurrently with a `start()` stalled mid-bind (injectable bind hook or subclass), then assert no bound listener/socket survives.

### CON-5 — iOS: `catch (TimeoutCancellationException)` intercepts an *outer* timeout, tearing down a healthy connection and swallowing cancellation
- Severity: Medium | Confidence: Confirmed mechanics (classic nested-withTimeout footgun); trigger requires an app-level `withTimeout` around `send()`/`connect()` — an idiomatic pattern
- File(s): appleMain/.../IosRawConnection.kt:264-280 (send await), :194-204 (Connecting await); appleMain/.../IosLanDataTransport.kt:486-490 (connect await)
- Category: bug
- Root cause: `TimeoutCancellationException` is caught by type, not by ownership. If the **app** wraps `session.send(...)` in its own `withTimeout` (no core path does — verified: the only core `withTimeout*` sites are Handshake.kt:49, P2pSessionImpl.kt:286, P2pKitImpl.kt:452, SessionManager.kt:517, none of which wrap transport write/connect), an app timeout firing during the send await delivers the *outer* TCE at the suspension point; IosRawConnection.write catches it, runs `closed = true; _state.value = Closed; cancelOnce("write timeout")` — cancelling a healthy connection — and replaces the cancellation with `IllegalStateException`. The same catch-by-type in `IosLanDataTransport.connect` converts an outer TCE into `P2pError.ConnectionFailed` (connection correctly closed there, but the cancellation exception is swallowed/retyped). JVM/Android are immune (they catch `IOException`).
- Evidence (IosRawConnection.kt:264-268): the comment explicitly distinguishes plain CE ("must keep propagating untouched") but TCE from an enclosing scope is indistinguishable by type from its own.
- Runtime impact: app-side `withTimeout(N) { session.send(msg) }` with N shorter than a transient stall kills the session's connection instead of just abandoning the send, and breaks the app's timeout handling (gets ISE instead of TCE). iOS only.
- Failure class: wrong error semantics / unnecessary connection teardown | Platforms: iOS | User-visible: yes (session drops)
- Proposed fix: replace `withTimeout` + catch with `withTimeoutOrNull` and act on the null return (its TCE never escapes to be confused), in all three sites.
- Required tests: appleTest — wrap `raw.write(...)` in an outer 50 ms `withTimeout` against a never-completing send (unconnected peer), assert the outer TCE propagates and `cancelIssued` is untouched.

### CON-6 — Write-error parity divergence: JVM/Android leave socket open and state=Connected on a non-timeout write failure; exception types diverge across platforms
- Severity: Medium | Confidence: Confirmed
- File(s): jvmMain/.../JvmRawConnection.kt:116-128; androidMain/.../AndroidRawConnection.kt:116-128; appleMain/.../IosRawConnection.kt:240-254
- Category: bug (parity divergence without steady-state symptom + untyped error surface)
- Root cause: on iOS a send-completion error latches `closed=true; _state.value=Closed; cancelOnce(...)` — the KDoc explains why ("without this the keep-alive only learns the connection is dead one ping interval later"). On JVM/Android, the watchdog-lost `IOException` branch just logs and rethrows: no `closeSocketOnce()`, no `_state` change. `observeRawState` (P2pSessionImpl.kt:222-233) therefore never fires from a write error on JVM/Android; detection falls back to the read loop erroring (usual case) or, for a half-broken socket (EPIPE on write, read still parked), to the next keep-alive PING — the exact latency the iOS fix was written to remove. Additionally, the same failure surfaces to `session.send()` callers as `IOException` (JVM/Android) vs `IllegalStateException`/`NetworkException` (iOS) — `RawConnection.write` has no exception contract and nothing in core wraps it into a typed `P2pError`, so apps see different, untyped exceptions per platform for the same event (BRIEF invariant: typed failures).
- Evidence: JVM catch block ends `JvmLanDiag.log(...); throw e` (no state/socket action); iOS completion handler sets closed/Closed/cancelOnce before resuming with the exception.
- Runtime impact: platform-dependent failure-detection latency (up to one ping interval on JVM/Android in the half-broken case) and platform-dependent exception types out of the public `send()`.
- Failure class: none (degraded parity/diagnostics) | Platforms: all | User-visible: yes (error type)
- Proposed fix: in JVM/Android's write-error branch (watchdog-lost), also `closeSocketOnce()` + `_state.value = Closed` (a socket whose write threw is dead for this protocol); have `P2pSessionImpl.send`/protocol wrap transport exceptions into `P2pError.ConnectionFailed` (core change — flag for S3 owner; no API change, `P2pError` already public).
- Required tests: jvmTest — force a write IOException (close peer receive side, write until EPIPE), assert `state` becomes Closed and socket closes without waiting for keep-alive.

### CON-7 — Abrupt disconnect races clean-close vs connection-lost: reconnect is nondeterministically skipped (transports collapse read-error and EOF into identical normal completion)
- Severity: Medium | Confidence: Confirmed race (both coroutines guard on `Connected` and race for `connectionLock`); which side wins is timing-dependent. Possibly catalogued — routeEvents' comment documents "treat channel end as clean close" as a v0.2 decision, but the race with `observeRawState` is not acknowledged anywhere I could find (AUDIT_REPORT_2026-06.md has no hangup/clean-close entry). Ownership is S3; reported here because the transport behavior is the root enabler.
- File(s): jvmMain/.../JvmRawConnection.kt:153-159 (IOException → `break` → flow completes *normally*); appleMain/.../IosRawConnection.kt:298-309 (error and EOF both resume(null) → normal completion); p2p-core/.../P2pSessionImpl.kt:548-552 (`markCleanlyClosed` on channel end, "never retry") vs :222-233 (`observeRawState` → `onConnectionLost` → Reconnecting)
- Category: bug
- Root cause: all three RawConnections complete `read()` normally for **both** a genuine EOF and a hard read error, so core cannot distinguish "peer said goodbye" from "peer vanished". After an abrupt drop, two session coroutines fire: the raw-state observer (wants Reconnecting) and routeEvents' channel-end handler (wants terminal Closed, no retry). First to take `connectionLock` from state=Connected wins; the other no-ops. `observeRawState` usually wins (shorter chain from `_state.value = Closed`), but under dispatcher load `markCleanlyClosed` can win → an outgoing session with `ReconnectPolicy.Enabled` dies instantly with no retry on a network drop.
- Evidence: `catch (e: IOException) { … break }` then `closeSocketOnce(); _state.value = Closed` — identical observable outcome to `if (n < 0) break`.
- Runtime impact: occasional no-retry session death on cable-pull/AP-loss — the exact scenario reconnect exists for; intermittent, timing-dependent, would present as a "reconnect sometimes doesn't happen" field bug.
- Failure class: wrong lifecycle semantics (intermittent) | Platforms: all | User-visible: yes
- Proposed fix: have `read()` distinguish outcomes (e.g. complete normally on EOF, throw/flag on error — protocol.events already propagates flow errors into `eventChannel.close(e)`, and routeEvents' `catch (Throwable)` branch already routes to `onConnectionLost`); alternatively (core-side, no transport change) make routeEvents' channel-end path defer to raw-state (`if raw state Closed-due-to-error → onConnectionLost`). Coordinate with S3 owner.
- Required tests: commonTest with fakes — abrupt raw close (no CLOSE frame) with reconnect enabled, run repeatedly / with a worst-case dispatch order, assert the session always reaches Reconnecting, never terminal Closed.

### CON-8 — iOS listener failure after ready is silent: no rebind, no error to core, listener not cancelled
- Severity: Medium | Confidence: Confirmed
- File(s): appleMain/.../IosLanDataTransport.kt:394-411
- Category: bug
- Root cause: the state-changed handler installed by `buildListener` only signals the (one-shot, bind-time) semaphore and logs. A post-ready `nw_listener_state_failed` — Network.framework does fail listeners at runtime (daemon restart, entitlement/agent issues) — leaves `listener` non-null and `_tcpPort` set: `start()` still reports started, no `afterListenerRebind`/recreate is attempted (the path monitor rebinds only on *path* transitions, which need not accompany a listener failure), the failed listener is never `nw_listener_cancel`ed, and core gets no signal (the incoming channel just goes quiet). JVM analogue at least fails the flow (see CON-3); iOS is fully silent.
- Evidence: `when (state) { ready, failed, cancelled -> dispatch_semaphore_signal(ready) }` — that is the entire failure handling after bind.
- Runtime impact: inbound-deaf transport until an unrelated path change or app restart; advertised Bonjour port points at a dead listener → peers' dials time out.
- Failure class: silent degradation | Platforms: iOS | User-visible: yes (undiscoverable/undialable)
- Proposed fix: on `failed` when this listener is still the current one, cancel it and `scheduleRebind("listener failed")` (all machinery exists); log with a distinct signature.
- Required tests: hard to unit-test against real NW; at minimum a hook-level test that a `failed` transition triggers scheduleRebind (extract the handler decision into a testable function, like AnnounceCacheReconcileTest did for #8).

### CON-9 — Inbound queue parity: iOS `Channel.UNLIMITED` vs JVM/Android bounded callbackFlow(64)+drop-close
- Severity: Low | Confidence: Confirmed
- File(s): appleMain/.../IosLanDataTransport.kt:185; jvmMain/.../JvmLanDataTransport.kt:132+156-160; androidMain/.../AndroidLanDataTransport.kt:122+143-147
- Category: bug (parity / resource-limit posture divergence)
- Root cause: JVM/Android accept into a default-buffered callbackFlow (64) and close the socket when `trySend` fails (bounded memory/fd exposure under an accept burst with a stalled collector). iOS queues wrapped-and-**started** connections into an UNLIMITED channel — under a stalled collector (kit scope busy) a non-conforming peer can grow live nw_connections without bound; `trySend` on iOS can only fail when the channel is closed.
- Runtime impact: unbounded fd/memory growth on iOS in the stalled-collector window; none in steady state.
- Failure class: resource-limit / unbounded-usage (narrow) | Platforms: iOS | User-visible: no
- Proposed fix: give iOS's incomingChannel the same bounded capacity (e.g. 64) and `raw.cancelNow("accept queue full")` on trySend failure (the #20b path already exists for the closed case).
- Required tests: appleTest unit — fill a small-capacity channel and assert overflow connections are cancelled.

### CON-10 — Android lifecycle trace is unconditional `Log.d`, contradicting the documented default-off trace
- Severity: Low | Confidence: Confirmed
- File(s): androidMain/.../AndroidRawConnection.kt:67, 100-106, 127, 156, 160, 174, 183; androidMain/.../AndroidLanDataTransport.kt:71-74, 92, 112, 118, 142, 145, 164; CLAUDE.md ("Two trace layers … default-off in the SDK")
- Category: bug (doc mismatch, minor info exposure)
- Root cause: JVM gates every lifecycle line behind `JvmLanDiag.enabled` (default off, JvmLanDiag.kt:34-36); iOS gates the console mirror behind `mirrorToConsole` (default off). Android emits per-connection lifecycle lines (peer IPs/ports, timeouts, errors) straight to logcat with no gate — only the per-frame layer is gated (`AndroidLanDiag.traceFrames`). AndroidLanDiag's KDoc half-acknowledges this ("Android already logs through android.util.Log"), but it diverges from the repo-level "default-off in the SDK" claim and from JVM/iOS behavior.
- Runtime impact: release apps embedding the SDK always write connection metadata (remote addresses) to logcat; trivial perf cost.
- Failure class: none (diagnostics/doc) | Platforms: Android | User-visible: log noise
- Proposed fix: add an `AndroidLanDiag.enabled` gate mirroring JvmLanDiag (samples opt in), or amend CLAUDE.md/docs to state Android's lifecycle trace is always-on by design.
- Required tests: n/a (doc/logging).

### CON-11 — `pendingRebindJob` data race: `scheduleRebind` runs unsynchronized from three threads
- Severity: Low | Confidence: Confirmed (plain `var`, no @Volatile/atomic; callers on pathQueue, main thread, and close()'s caller)
- File(s): appleMain/.../IosLanDataTransport.kt:281 (plain `private var pendingRebindJob: Job?`), :662-672 (scheduleRebind: read-cancel-write), :606-607 (stopPathMonitor reset), :633-639 (foreground observer → main thread)
- Category: bug
- Root cause: path-monitor callbacks (serial pathQueue) and the foreground notification (main thread) can call `scheduleRebind` concurrently; both read/cancel/replace the same non-volatile field. Two jobs can be launched (double rebind → two back-to-back port rotations and discovery churn), and on K/N the write may not even be visible cross-thread, so `stopPathMonitor`'s cancel can miss the latest job (a rebind can fire after close — benign only because `rebindNow` re-checks `closed`).
- Runtime impact: occasional double listener rebind after a wake-coinciding-with-path-change; extra churn, no corruption.
- Failure class: none (redundant work) | Platforms: iOS | User-visible: transient reconnect churn
- Proposed fix: funnel `scheduleRebind` onto one serial context (e.g. dispatch to pathQueue, or make the field an `AtomicReference` with getAndSet-cancel).
- Required tests: none practical; code-review invariant.

### CON-12 — iOS `close()` leaves `listener` non-null and `_tcpPort` set
- Severity: Low | Confidence: Confirmed
- File(s): appleMain/.../IosLanDataTransport.kt:501-511 (also JVM/Android leave `_tcpPort` stale after close — jvmMain/.../JvmLanDataTransport.kt:173-180)
- Category: bug (stale-state hygiene)
- Root cause: `close()` cancels the listener but doesn't null `listener` or `_tcpPort`. `HasLocalTcpEndpoint.tcpPort` (read by provisioning via `lanTcpPort` lambda, P2pKitImpl.kt:207) keeps reporting a dead port after stop; discovery's descriptor-attach path (IosLanDiscoveryTransport:215-217) checks nullity of `listener` and would see the cancelled listener as attachable.
- Runtime impact: negligible today (everything else is stopped in the same teardown), but a trap for future callers of the SPI.
- Failure class: none | Platforms: all three (`_tcpPort`), iOS (`listener`) | User-visible: no
- Proposed fix: null both in `close()` after cancelling.
- Required tests: unit assert `tcpPort.value == null` after close.

### CON-13 — iOS: inbound connection arriving after `closed` is ignored without cancelling it
- Severity: Low | Confidence: Confirmed code; Uncertain on NW dealloc timing (an unstarted, unreferenced nw_connection is torn down at dealloc — K/N GC-latency-bound)
- File(s): appleMain/.../IosLanDataTransport.kt:382-387
- Category: bug (defensive gap)
- Root cause: the `else` branch of the new-connection handler (`conn != null && closed`) only logs. The accepted connection is neither started nor `nw_connection_cancel`ed — release of the underlying accepted TCP socket waits for K/N GC of the block-held reference, so the remote can sit on an accepted-but-dead connection until its own handshake timeout. JVM parity path explicitly closes dropped sockets.
- Proposed fix: `nw_connection_cancel(conn)` in the else branch (cancelling a connection in setup state is legal).
- Required tests: covered by review; no practical automated probe.
- Failure class: leak (brief) | Platforms: iOS | User-visible: no

### CON-14 — Improvement: JVM/Android write watchdog is untestable (constant timeout) and untested at transport level
- Severity: Improvement | Confidence: Confirmed
- File(s): jvmMain/.../JvmRawConnection.kt:206 (`WRITE_TIMEOUT_MILLIS = 30_000` in private companion); androidMain/.../AndroidRawConnection.kt:205; REMEDIATION_2026-07.md row #4 (its test, `CloseSemanticsTest`, lives in p2p-core commonTest and drives a **FakeRawConnection** — the real watchdog/CAS/socket-close interplay in JvmRawConnection has zero automated coverage)
- Category: improvement
- Proposed fix: make the timeout an internal constructor parameter (default 30 s); add a jvmTest that writes into a socket whose peer never reads (tiny SO_SNDBUF/receive buffer) with a short timeout and asserts: write throws the timeout IOException, `socket.isClosed`, state == Closed, and a subsequent `close()` is a no-op.
- Required tests: as above (P1 in §3).

### CON-15 — Improvement: `buildListener` blocks the calling thread up to 5 s (`dispatch_semaphore_wait`) inside a suspend path
- Severity: Improvement | Confidence: Confirmed
- File(s): appleMain/.../IosLanDataTransport.kt:413-416
- Category: improvement
- Rationale: `start()` runs in the caller's context; a Swift app calling `kit.start()` from the main actor parks the main thread for up to 5 s in the failure case (iOS watchdog territory at launch). No deadlock (listener queue is separate), but it violates suspend-functions-don't-block. `rebindNow` is safe (rebindScope = Default).
- Proposed fix: await the ready/failed transition via `suspendCancellableCoroutine` (+ `withTimeoutOrNull(5s)`), or at minimum wrap `buildListener()` in `withContext(Dispatchers.Default)` inside `start()`.

### CON-16 — Improvement: `IosLanDebug.log` builds strings and emits per event with no master gate; one line per `write()` on the hot path
- Severity: Improvement | Confidence: Confirmed
- File(s): appleMain/.../IosLanDebug.kt:58-63 (no early-out; only the `println` is gated); appleMain/.../IosRawConnection.kt:219 (one log line per write → per 64 KiB FILE_DATA chunk)
- Category: improvement
- Rationale: the AUDIT-2026-06 fix gated the console mirror but the allocation + SharedFlow emit still run unconditionally for every transport event, including per-chunk writes — JVM's equivalent is double-gated (`enabled` + `traceFrames`). Bounded memory (DROP_OLDEST), but avoidable steady-state churn and a parity gap in trace-layer semantics.
- Proposed fix: add an `enabled` master switch mirroring `JvmLanDiag` (samples/tests opt in), and route the per-write line through a frames-style gate.

### CON-17 — Improvement: iOS loopback test `unique` id has 1-second resolution
- Severity: Improvement | Confidence: Confirmed
- File(s): appleTest/.../IosLanLoopbackTest.kt:43-44 (`NSDate().timeIntervalSince1970.toLong()`)
- Category: improvement
- Rationale: per-test-instance appId is truncated to whole seconds (JVM twin uses millis). Two instantiations in the same wall-clock second (fast-failing test followed by the next) share an appId, letting stale Bonjour announcements from the previous kit pair leak into `peers.first { it.name == "Bob" }` and produce a confusing handshake-timeout flake.
- Proposed fix: `(timeIntervalSince1970 * 1000).toLong()` or append a monotonic counter.

### CON-18 — Improvement: dial uses only the first LAN hint; no multi-address fallback
- Severity: Improvement | Confidence: Confirmed (adjacent to catalogued issue #2 — interface selection awaits hardware diagnosis; the multi-hint iteration itself is not explicitly catalogued)
- File(s): jvmMain/.../JvmLanDataTransport.kt:88-93; androidMain/.../AndroidLanDataTransport.kt:85-90; appleMain/.../IosLanDataTransport.kt:446-455
- Category: improvement
- Rationale: `transportHints.firstOrNull { … }` — a peer announcing multiple A records (Wi-Fi + Ethernet, IPv4+IPv6) gets one dial attempt at whichever hint was stored first; a reachable second address is never tried in the same attempt (reconnect retries re-resolve but re-pick the same first hint unless the registry order changed).
- Proposed fix: iterate matching hints on connect failure (bounded), keeping the 5 s per-attempt budget in mind.

### CON-19 — Improvement: IosRawConnectionTest asserts exact exception message strings
- Severity: Improvement | Confidence: Confirmed
- File(s): appleTest/.../IosRawConnectionTest.kt:58, 73 (`assertEquals("connection closed", e.message)`)
- Category: improvement
- Rationale: couples the test to a diagnostic string; a harmless message reword breaks it. Asserting the type + the prompt-throw bound (already done via `withTimeout(2_000)`) is the invariant.
- Proposed fix: drop the message equality or match on a stable prefix.

Notes on scope-emphasis items verified clean (no finding):
- **Watchdog/writer CAS** (f4dd3a9): the per-write `AtomicInteger` makes every interleaving safe, including a stale watchdog from write *N* running concurrently with write *N+1* (fresh AtomicInteger per write; old watchdog's CAS fails against DONE). `watchdog.cancel()` without join is safe for the same reason. Exceptions under `writeLock` release via withLock's finally. Watchdog-cancel latency after a wedged-write unblock is nil (watchdog already completed).
- **usePinned + async send** is safe: `p2pkit_nw.h:53` calls `dispatch_data_create(buffer, size, NULL, NULL)` — NULL destructor copies synchronously before return, as the header documents; receive-side `objc_precise_lifetime` mapping fix present (p2pkit_nw.h:88-91).
- **IosRawConnection continuation discipline**: every receive completion resumes exactly once (disjoint branches); resume of a cancelled continuation is a no-op (late send completions, cancelled read collectors). `cancelOnce`/`cancelNow` CAS idempotency confirmed incl. framework-cancelled latch (:174).
- **Single-collector contracts** hold: `protocol.events` collects `read()` once per connection (DefaultP2pProtocol.kt:121-139, one readerJob per handshake); `startAcceptingIncoming` collects `incomingConnections()` once per transport for kit lifetime (SessionManager.kt:146-152, P2pKitImpl.kt:186).
- **Cellular prohibition** intact (IosLanDataTransport.kt:150) with CAS-safe `ensureParameters` (#20a fix correct: losing racer's object is dropped unassigned); #20b inbound trySend→`cancelNow` correct; 20c not re-reported per REMEDIATION.
- **State machine**: no path skips Closed on either platform's terminal transitions; iOS Connecting→Closed (never Connected) is handled by `connect()`'s terminal check and `write()`'s post-await `closed` recheck.

## 3. Missing tests

| Invariant untested | Why it matters | Where it should live | Type | Priority |
|---|---|---|---|---|
| Real 30 s write watchdog: wedged socket write → IOException + `socket.isClosed` + state Closed (JvmRawConnection, not the Fake) | f4dd3a9's core mechanism has no transport-level coverage; REMEDIATION's cited test uses FakeRawConnection | transport-lan jvmTest (needs injectable timeout, CON-14) | integration | P1 |
| `close()` from an already-cancelled coroutine still releases the fd (CON-1) | routine app-cancels-connect path leaks fd + IO thread today | transport-lan jvmTest | unit | P1 |
| Abrupt disconnect with ReconnectPolicy.Enabled always reaches Reconnecting, never clean-Closed (CON-7) | intermittent no-retry session death | p2p-core commonTest (fakes) | combination | P1 |
| Cancelled dial closes the just-connected socket (CON-2) | fd leak per cancelled connect | transport-lan jvmTest | unit | P2 |
| Accept-loop failure does not crash the host / is surfaced (CON-3) | SDK must not kill the app on EMFILE | transport-lan jvmTest + core | combination | P2 |
| stop() racing slow start() leaves no bound listener/socket (CON-4) | orphaned port/listener/observer | per-platform unit (injectable bind stall) | unit | P2 |
| iOS listener `failed`-after-ready triggers rebind (CON-8) | silent inbound deafness | appleTest (extract handler decision) | unit | P2 |
| iOS 30 s send deadline tears down connection | currently manual-only (REMEDIATION #18) | appleTest vs a non-reading local listener, or stays manual (smoke matrix) | manual/integration | P3 |
| Keep-alive PING/PONG over a real socket (both loopback suites set 60 s ping — never fires) | keep-alive is only fake-tested | transport-lan jvmTest with short ping config | integration | P3 |
| AndroidRawConnection behavior parity (any automated execution) | class has zero test executions; parity by diff only | catalogued (no instrumented tests) — manual §recipes | manual | P3 |

## 4. Section summary

**What S7 owns:** the three per-platform dial/listen data transports and the three raw byte-pipe
implementations underneath the protocol layer — connect timeouts, accept loops, write deadlines,
fd/NW-object ownership, and the state StateFlow that core's session lifecycle keys off.

**Overall health:** the f4dd3a9 rewrite is genuinely good where it aimed: the per-write CAS watchdog
is race-free under every interleaving I could construct, `closeSocketOnce` correctly unifies the
user/EOF/watchdog release paths, the JVM↔Android pair is behaviorally identical (verified by diff),
and the iOS cancel latch (`cancelOnce`/`cancelNow`) plus the cinterop copy semantics are sound.
The weak flank is **cancellation-robustness of the cleanup paths**: `close()`, the dial, and the
read-loop's release all sit behind cancellable suspension points on JVM/Android, so exactly the
cancellation-heavy paths (app cancels connect, stop during handshake, teardown racing rearm) skip
the resource release the fix was built for. Secondary theme: **failure propagation of the inbound
path** is inconsistent — JVM/Android escalate an accept failure into an uncaught exception (Android
crash), iOS swallows listener failure entirely.

**Top 3 risks:**
1. CON-1/CON-2 — accumulating fd + parked-IO-thread leaks on routine cancellation (JVM/Android).
2. CON-3/CON-8 — inbound-accept failure is either fatal (Android) or silent (iOS); no recovery path.
3. CON-7 — timing-dependent reconnect skip on abrupt disconnects (with CON-5's iOS outer-timeout
   footgun as the adjacent session-killer).

**CODEBASE_REVIEW_MAP_2026-07.md accuracy:** the S7 entry is accurate — file list, the duplicated-pair
invariant, watchdog/CAS description, dependency edges (S1 SPI, S5 endpoint registry, S12 cinterop,
S3 consumer), and the coverage assessment ("JVM loopback good; Android raw connection has no
automated tests; iOS partial") all match what I found. Risk rating "High — remediation group D is
new" is justified by the findings above. No discrepancies to report; one refinement: the map's
"read-loop EOF fd release" bullet should not be read as unconditional — the release is skipped
under collector cancellation (CON-1).
