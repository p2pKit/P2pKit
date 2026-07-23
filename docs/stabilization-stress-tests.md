# Stabilization stress tests (post-S3)

> **Superseded by `docs/v0.4-cumulative-validation-runbook.md`.** This runbook
> is pinned to the window between S3 (`473f4d4`) and S1. Since then S1 landed
> (`3622b49`, `f84a218`) and `V0.4-RECONNECT` (`035eef1`) shipped per-attempt
> endpoint re-resolution, which invalidates Test 3's expected logs (see the
> note there). Kept for the historical S3 context; run the v0.4 runbook for
> current hardware validation.

**Status:** runbook for hardware validation between S3 (`473f4d4`) and S1.

## What we're validating

The recent commits restructured terminal-state semantics:

- `b6ffb31` — `_sessions` desync after reconnect, plus iOS sample watchdogs.
- `2af8d67` — symmetric Failed-path cleanup + zombie-session detection.
- `473f4d4` — single `transitionToTerminal` for every terminal path; hard runtime invariants.

The SDK now claims, **as runtime invariants**:

- I-double-terminal: a second terminal transition is a no-op.
- I-terminal-state: post-condition `state == target` after `transitionToTerminal`.
- I-terminal-epoch: post-condition `epochJob.isCancelled` after `transitionToTerminal`.
- I-no-incoming-after-terminal: no `_incoming.emit` after the epoch is cancelled (enforced by epoch cancellation + the zombie watchdog).
- I-no-duplicate-sessions: at most one session per peerId in `_sessions` (enforced by atomic add+filter in `registerSession` and `connect()`).

Plus a soft watchdog:

- **Stuck-Reconnecting**: WARN if a session sits in `Reconnecting` for >30 s.

These invariants pass the unit tests. The stabilization phase verifies they hold under real-device chaos before we refactor on top of them in S1.

## Setup

### Mac side

1. Plug iPhone via USB.
2. Open the project in Xcode (`open iosApp/p2pkit-sample.xcodeproj` after `xcodegen generate`).
3. Pick the iPhone as the run destination.
4. ⌘R to build + install + launch. Trust the developer certificate on the iPhone if prompted.
5. **Xcode console** at the bottom. Filter on `p2pkit`. Right-click → Save As… at the end of each test to dump the console.

### Android side

1. Plug Android via USB, enable USB debugging.
2. In a terminal: `adb logcat | grep -i p2pkit > /tmp/p2pkit-android-${TEST}.log` (one per test).
3. Build + install: `./gradlew :p2p-sample-android:installDebug` and launch the app on the device.

### Common preparation

Both apps started, both kits running, both peers visible in their respective Peers lists, an initial Connected session established, and a smoke test ("send hello in each direction") proves the baseline before any stress.

## What to watch for in the logs

| Signature | Source | What it means |
|---|---|---|
| `ZOMBIE session emitting Message: …` | SDK `routeEvents` | A session that's been evicted from `kit.sessions` is still pushing messages into `_incoming`. Should never appear post-S3. |
| `STUCK in Reconnecting for >30000ms` | SDK `onConnectionLost` watchdog | A session has been in Reconnecting for half a minute. Should never appear unless a deeper lifecycle bug exists. |
| `I-terminal-state` / `I-terminal-epoch` / `I-double-terminal` | SDK `check()` failures | A `transitionToTerminal` post-condition failed. **Hard failure** — the SDK crashes the host. Capture the stack. |
| `WARN: N sessions for peer=X` | iOS sample watchdog | Duplicate sessions for the same peer in iOS UI for >1 poll-tick. |
| `WARN: peer X has no matching session row` | iOS sample watchdog | Peer is in `peers` but no session matches by `peer.id`. The B1 symptom signature. |
| `decision=Replaced existingState=Reconnecting` | SDK `registerSession` | Simultaneous-open arbitration replaced a stale Reconnecting session — expected during fast reconnects. |
| `decision=Rejected existingState=Connected` | SDK `registerSession` | Smaller-id side rejected an incoming session that arrived after its own outgoing — expected on simultaneous-open. |

## Test plan

Run each test once, capture the log files, fill the result table at the bottom. Sequence is intentional — earlier tests bring up infrastructure that later tests reuse.

---

### Test 1 — Reconnect storm

**Race targeted.** Many sessions hitting connection loss at the same instant compete for the same `pathSatisfiedSignal` wake-up.

**Setup.** Two devices. iOS side: `ReconnectPolicy.Disabled` (sample default); Android side: `ReconnectPolicy.Enabled(maxAttempts = 8, retryDelayMillis = 500)`. Establish session A↔B as the baseline.

**Procedure.**
1. On the **router**, briefly drop the entire Wi-Fi network (toggle the AP off for ~3 seconds, then on).
2. Repeat 3 times with 5 s between flips.

**Expected logs.**
- iOS: session goes Connected → Failed (no handler), then `[data] listener: accepted inbound` when Android redials, new session reaches Connected within 1–2 seconds of Wi-Fi return.
- Android: session goes Connected → Reconnecting → Connected via `decision=Replaced` (or Connected after redial).
- No STUCK warnings, no ZOMBIE warnings.
- `kit.sessions` size ends at 1 per side after each round.

**Failure signatures.**
- STUCK warning on either device.
- After the third flip-cycle, more than 1 session per peer in either kit.
- ZOMBIE warning.
- iOS UI shows "Connect" (not "Connected") despite messages flowing — re-check the WARN watchdogs.

**Collect.** Xcode console + `adb logcat` for the full run, plus iOS app screenshots showing the peer/session UI at the end of each cycle.

---

### Test 2 — Wi-Fi flap

**Race targeted.** The `Unsatisfied → Satisfied` cycle on `NetworkPathObserver` faster than the reconnect handler's `withTimeoutOrNull(retryDelayMillis) { pathSatisfiedSignal.first() }` can complete.

**Setup.** Same as Test 1.

**Procedure.**
1. Send `iPhone → Android: "before"` and `Android → iPhone: "before"`. Verify both arrive.
2. On iPhone: Settings → Wi-Fi off, count to 2, on. Repeat 5x with no pause between cycles.
3. Within 5 s of the last "on," send `"after"` from each side.

**Expected logs.**
- iPhone shows `network: offline` chip during the off cycles, `online` chip when back.
- Each off cycle: `[ui] session.send THREW` or `[conn] write(N): completion ERROR — flipping state to Closed` on iPhone-initiated sends.
- Final state: session Connected on both sides, "after" delivered both ways.

**Failure signatures.**
- After Wi-Fi is back on for 5+ seconds, session is still in `Reconnecting` on either side.
- STUCK warning after 30 s.
- Send "after" fails despite chip saying `online`.
- iPhone shows `Connect` button next to Android in PeerRow.

**Collect.** Logs + a 5–10 s screen recording of the iPhone showing the chip toggles + Sessions list updates.

---

### Test 3 — Hotspot switch

**Race targeted.** Same peer id but rotated wire address. The `SessionReconnectHandler` captures `internalPeer` at session creation — if iPhone moves to a different Wi-Fi network where Bonjour resolves Android to a different IP / port, reconnect attempts dial the stale address.

**Setup.**
1. Set up two Wi-Fi networks the iPhone has access to (home + phone-hotspot is the easiest).
2. Both apps running, session Connected on the **home** Wi-Fi.

**Procedure.**
1. On iPhone: switch Wi-Fi network from home to hotspot. Android stays on home.
2. Wait 30 s. Watch the iPhone log.
3. Switch iPhone back to home. Wait 30 s.

**Expected logs.**
- During step 1: iPhone goes `Unsatisfied`, session goes to Reconnecting. **With current SDK**: the captured `internalPeer` points at Android's home-network IP, which iPhone can't reach from the hotspot → all retry attempts fail → `markFailedAfterExhaustion` after ~4 s (default delay × attempts) → session goes Failed → session disappears from `kit.sessions`.
- During step 2: STUCK warning will NOT fire because we already reached Failed terminal state.
- During step 3 (re-join home): Bonjour rediscovers Android, Android's auto-mesh re-dials, a new incoming session arrives → `decision=Accepted` → session resumes.

**Failure signatures.**
- STUCK warning in step 2 — that means `markFailedAfterExhaustion` didn't run.
- In step 3 (back on home), iPhone's `Connect` button doesn't change to `Connected` even though `[session] new …` log appears.
- iPhone shows duplicate sessions for Android in PeerRow watchdog log.

**Collect.** Logs + the final state screenshot.

**Note.** This test is expected to exercise the "stale internalPeer" weakness called out in the architecture review. Failed → re-dial via auto-mesh is the v0.3 recovery path. The cleaner fix (re-resolve from `peerRegistry` per attempt) is queued for v0.4. The test is to confirm v0.3 recovers cleanly even if not optimally. *Since shipped: `V0.4-RECONNECT` (`035eef1`) landed exactly that fix — on v0.4+ trees each retry re-resolves the endpoint (look for `Reconnect target changed` in the logs) and the "all retry attempts dial the stale address" expectation above no longer holds. Use the v0.4 runbook's R1/R2 instead.*

---

### Test 4 — Simultaneous-open

**Race targeted.** Both peers call `kit.connect` for each other within the same RTT. `registerSession` arbitration must converge to the same survivor on both sides.

**Setup.** Two phones, both apps cold-started, both `ReconnectPolicy.Enabled` (Android sample's Setup screen toggle; the iOS sample doesn't expose this — pre-configure if testing this scenario rigorously).

**Procedure.**
1. Force-quit both apps.
2. Bring both apps to foreground at the same instant (within ~200 ms — practice the gesture or use Shortcuts).
3. Watch both logs.

**Expected logs.**
- Both sides see `[browse] emitPeer: ACCEPTED Found …`.
- Both sides initiate `auto-mesh` (Android) or stay quiet (iPhone — manual connect only).
- If both initiate within ~RTT: arbitration log appears.
  - Smaller-id side: `decision=Rejected existingState=Connected … existing wins`.
  - Larger-id side: `decision=Replaced existingState=Connected … promoting new …, closing previous`.
- Both sides converge to exactly one Connected session for the other peer.

**Failure signatures.**
- Either side ends with 2 sessions for the same peer in `kit.sessions`.
- Either side's session goes Connected → Failed → never recovers (one side closed its winning candidate by mistake).
- Both sides simultaneously decide they're the smaller-id (impossible by string compare; if observed, the peer-id formatting differs between Bonjour TXT and HELLO — separate bug).

**Collect.** Logs from both sides, side-by-side.

---

### Test 5 — Background / foreground churn

**Race targeted.** iOS `BackgroundPolicy.CloseActiveSessions` (the default) interleaved with foreground resumes. The known weakness here: the kit's state goes `Stopped` but the transports stay bound — the next `startAdvertising` lazy-ensures and may short-circuit `ensureStarted`.

**Setup.** iPhone + Android paired with a Connected session.

**Procedure.**
1. Send `Android → iPhone: "before bg"`. Verify it arrives.
2. iPhone: home gesture (app → background). Wait 5 s.
3. iPhone: bring app to foreground.
4. Repeat ×5 in rapid succession (gesture + wait ~3 s + return).
5. After the last return, send `Android → iPhone: "after bg"`.

**Expected logs.**
- Each background: `notifyAppBackgrounded` → `applyBackgroundPolicy(CloseActiveSessions)` → `kit.state = Stopped` → all sessions go straight to `Closed` (the `Closing` member is never entered — see the cleanup note at the bottom) → `[session] removed …`.
- Each foreground: the app may need to call `startAdvertising` / `startDiscovery` again (the sample handles this when the user taps Start; if scenePhase isn't wired to do it automatically, the user has to re-tap).
- After step 5, session is Connected again and "after bg" arrives.

**Failure signatures.**
- ZOMBIE warning during/after background cycles.
- `I-double-terminal` check() failure during rapid bg/fg.
- After return-to-foreground, the kit state is `Stopped` but transports won't restart on the next `startAdvertising` call (`ensureStarted` shortcuts thanks to a stale `startResult`).
- Session list shows pre-background sessions still listed after returning to foreground.

**Collect.** Logs + screen recording.

**Note.** This test is expected to find rough edges. `BackgroundPolicy.CloseActiveSessions` is on the v0.4 cleanup list. Document what you see — don't necessarily expect it to pass cleanly.

---

### Test 6 — Delayed-close socket

**Race targeted.** Apple's `nw_connection_cancel` callback can fire ~100–500 ms after the call. During that window, the Kotlin-side `closed=true`/`_state=Closed` is set but the OS connection isn't fully torn down. A new connection arriving in this window must not corrupt the closing session's state.

**Setup.** Two phones, session A→B Connected. **Use Android = stable, iPhone = the one going down.**

**Procedure.**
1. On iPhone: turn off Wi-Fi.
2. **Within 500 ms** (practice the timing): turn Wi-Fi back on.
3. Wait for the chip to go `online`.
4. Send `iPhone → Android: "after blip"`.

**Expected logs.**
- `[ui] Send All tapped` then either:
  - Session has gone Reconnecting (path observer fired Unsatisfied), reconnect handler re-dialed and rearmed within a few hundred ms → `[session] X Reconnecting → Connected` → send succeeds.
  - OR the path-flap was too fast for `observeRawState` to register, in which case the existing session keeps running on a renewed `nw_connection` after Apple's auto-recovery → send succeeds without state change.

**Failure signatures.**
- iPhone's `[conn] state-changed -> failed` fires followed by a different connection's `state-changed -> ready` going onto the *same session* (wrong epoch wired).
- `I-terminal-state` check() failure during the close → re-open dance.
- Send fails with `state=Connected` but no inbound bytes arrive at Android (wedged half-open socket).

**Collect.** Logs.

---

### Test 7 — Parallel file transfer + reconnect

**Race targeted.** A `sendFile` is mid-stream when the wire drops. The Failed transitions in `transitionToTerminal` (post-S3) now correctly call `fileTransferDispatcher.closeAll(reason)` on every path — this test verifies the file transfer's final state surfaces as `Failed(FileTransferFailed(kind = REMOTE_DISCONNECTED, …))` and not as a silent stuck `Sending` state.

**Setup.** Two phones, session Connected. On Android: open Send file menu and pick a moderately large file (1–10 MB, e.g., a video clip).

**Procedure.**
1. On Android: tap "Send file" — pick the 5+ MB file via SAF. Verify the iPhone shows "incoming file" event and the transfer enters Sending state on Android.
2. **Mid-transfer (10–50% complete)**: on iPhone, toggle Wi-Fi off.
3. Wait 5 s.
4. On iPhone: turn Wi-Fi back on.
5. Check the file transfer row in Android's UI.

**Expected logs.**
- Android: `Sending NN%` progress lines stop, eventually `FileTransferState.Failed(ConnectionFailed("session $id Failed: …"))`.
- iPhone: incoming file transfer also transitions to `Failed`.
- After Wi-Fi recovery: a new session establishes (if both reconnect). The old file transfer is not resumed (we don't do mid-transfer resume in v0.3); the user has to manually retry.
- No partial files left in incoming folder.

**Failure signatures.**
- Android file transfer stuck in `Sending NN%` forever after Wi-Fi recovers.
- ZOMBIE warning during the cleanup.
- The incoming file on iPhone exists at expected size but with garbled contents (data races during close).

**Collect.** Logs + the transfer-row screenshots showing the final state.

---

## Results template

After all tests, fill this table and decide whether to proceed to S1.

| Test | Pass / Fail / Anomaly | Notes |
|---|---|---|
| 1 — Reconnect storm |   |   |
| 2 — Wi-Fi flap |   |   |
| 3 — Hotspot switch |   |   |
| 4 — Simultaneous-open |   |   |
| 5 — Bg/fg churn |   |   |
| 6 — Delayed-close socket |   |   |
| 7 — Parallel file + reconnect |   |   |

**ZOMBIE warnings seen.** Count + which test(s).
**STUCK warnings seen.** Count + which test(s).
**check() failures.** Stack(s) + which test triggered.
**Other lifecycle anomalies.** Describe.

**Verdict.**
- Zero ZOMBIE, zero STUCK, zero check() → proceed to S1.
- Anything else → freeze S1 plans, investigate.

## What happens after a clean run

S1 (replace `active` map + `_sessions` StateFlow with a single store) becomes the next milestone. The current invariants — now hardened structurally by S3 and validated empirically by this runbook — are the contract S1's refactor must preserve.

A clean run also unlocks deletion of:

- The `Closing` enum member from `ConnectionState` (currently unused).
- The Swift sample's `Optional(Connected)` workaround comment in `IosSwiftHelpersKt.stateName` (the bridge fix is permanent).
- The temporary watchdog `STUCK_RECONNECTING_THRESHOLD_MS` line (S1 should make stuck-states structurally impossible).

If anything fails, **don't** delete those before S1 lands — the watchdogs are the only thing currently keeping us honest about the invariants.
