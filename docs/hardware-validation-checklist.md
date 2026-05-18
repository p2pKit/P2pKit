# Hardware validation checklist

Practical step-by-step. Five priority tests, copy-paste commands, clear paste-back format. Run them in order. Stop and paste back if anything fails.

---

## Prerequisites (one-time, ~5 minutes)

### iPhone

1. Plug iPhone into your Mac via USB.
2. In Xcode: `open /Users/abdelrahman/Projects/P2pKit/iosApp/p2pkit-sample.xcodeproj`. If Xcode complains about a stale project, run `cd /Users/abdelrahman/Projects/P2pKit/iosApp && xcodegen generate` first, then re-open.
3. In Xcode's top toolbar, change the destination from "iPhone 17 Simulator" to **your iPhone's name**.
4. Press **⌘R**. Xcode builds, signs, deploys, and launches. If iPhone asks, trust the developer in Settings → General → VPN & Device Management.
5. At the bottom of the Xcode window, the **Console** pane is on the right. If you only see one pane, toggle the bottom bar with **⇧⌘C**.
6. At the bottom-right of the Console, there's a **Filter** box. Type exactly:
   ```
   p2pkit
   ```
   That's the filter for all SDK + UI diagnostic lines.

### Android

1. Plug Android into your Mac via USB. Enable USB debugging on Android if not already.
2. In a terminal:
   ```sh
   cd /Users/abdelrahman/Projects/P2pKit
   ./gradlew :p2p-sample-android:installDebug
   adb shell am start -n dev.p2pkit.sample.android/.MainActivity
   ```
3. Open a **second terminal** and keep it open during all tests:
   ```sh
   adb logcat -c
   adb logcat -s p2pkit:V
   ```
   First line clears the buffer once. Second line streams all `p2pkit`-tagged logs.

### Both apps

1. On **both** devices, in the app:
   - iOS sample: type a device name like `iPhone`, tap **Start**.
   - Android sample: type a device name like `Android-test`, leave Reconnect on Disabled OR toggle Enabled (see Test 1 note). Tap **Start**.
2. Wait ~5 seconds. Each device should show the other in its Peers list.
3. **Smoke test**: tap **Connect** on the iPhone's PeerRow for Android. Both sides should show one session, status "Connected". Send "hello" each way. Confirm messages arrive.
4. If smoke test fails, stop and paste back. Don't proceed.

### Log capture commands (memorize these)

For each test, in the Android terminal:
```sh
# Replace <TEST> with the test slug (wifi-flap / hotspot-switch / etc.)
adb logcat -c
adb logcat -s p2pkit:V > /tmp/p2pkit-<TEST>.log &
LOGCAT_PID=$!
# ... run the test ...
kill $LOGCAT_PID
```

For each test, in Xcode:
1. Right-click anywhere in the Console pane.
2. "Save As..." → save to `/tmp/p2pkit-<TEST>-ios.txt`.
3. Then "Clear Console" before the next test starts.

---

## Test 1 — WiFi flap

**Goal.** Verify that toggling Wi-Fi off/on while connected does not leave either side in a stuck Reconnecting state, doesn't trigger ZOMBIE warnings, and that messages flow again after recovery.

**Setup.**
- Both devices Connected per Prerequisites smoke test.
- Android Reconnect Policy: **Enabled** (Setup screen toggle before tapping Start). MaxAttempts = 5, retry delay = 500 ms (default).
- iPhone has no reconnect-policy UI; uses Disabled by default — that's fine.

**Steps to reproduce.**
1. Start log capture (commands above, `<TEST>=wifi-flap`).
2. In iOS app: type "before-flap" → tap **Send all**. Confirm Android receives.
3. In Android app: type "before-flap" → tap Send. Confirm iOS receives.
4. On iPhone: **Settings → Wi-Fi → toggle Off**. Wait 3 seconds (count "one Mississippi, two Mississippi, three Mississippi").
5. **Toggle Wi-Fi On**. Wait 5 seconds for reconnect.
6. iOS app: type "after-flap-1" → Send all. Note whether it arrives on Android.
7. Repeat steps 4–6 four more times (5 cycles total).
8. Stop log capture.

**iOS logs to capture.** Save the Xcode console to `/tmp/p2pkit-wifi-flap-ios.txt`. Specifically look for these substrings:
- `[ui] Send All tapped`
- `[conn] state-changed -> failed`
- `[conn] state-changed -> ready`
- `[session] … Connected → Reconnecting`
- `[session] … Reconnecting → Connected`
- `ZOMBIE`
- `STUCK`
- `WARN:`

**Android logs to capture.** Already going to `/tmp/p2pkit-wifi-flap.log`. Same substrings.

**Success criteria.**
- All five "after-flap-N" messages arrive on Android.
- Each cycle's iOS log shows `Connected → Reconnecting → Connected` within ~5 seconds.
- Zero `ZOMBIE` lines.
- Zero `STUCK` lines.
- Zero lines starting with `WARN: 2 sessions for peer=` or `WARN: peer X has no matching session row`.
- Final session count on each side = 1.

**Failure signatures (paste back if seen).**
- Any `ZOMBIE session emitting Message: …` line.
- Any `STUCK in Reconnecting for >30000ms` line.
- Any `WARN: 2 sessions for peer=` or `WARN: peer X has no matching session row`.
- Any uncaught Kotlin exception or `check()` failure (Xcode console will show a stack trace and the iPhone app will crash).
- After 30+ seconds of Wi-Fi being back on, iOS app still shows "Connect" button next to Android (not "Connected").

**Repeat.** 1 run of 5 cycles. If clean, move to Test 2.

**Paste back.**
```
Test 1 — WiFi flap: PASS / FAIL / ANOMALY
ZOMBIE count: <number>
STUCK count: <number>
duplicate-session warnings: <number>
peer-id mismatch warnings: <number>
check() failures: <number>
Messages delivered: <X>/5
Notes: <one line if anomaly, "all clean" otherwise>
If anomaly: paste 10 lines around the first occurrence.
```

---

## Test 2 — Reconnect storm

**Goal.** Verify SDK survives the entire Wi-Fi network going down briefly multiple times in succession.

**Setup.**
- Same as Test 1.
- You'll need physical access to your **Wi-Fi router** (the home one, not the phone's). If you can't easily power-cycle it, use the iPhone's Wi-Fi toggle as a substitute and skip to Test 1's instructions, but try to test the router itself if possible — it more closely matches a real outage.

**Steps to reproduce.**
1. Start log capture (`<TEST>=reconnect-storm`).
2. Send "before-storm" each way. Confirm both arrive.
3. **Unplug the router** (or toggle the Wi-Fi network off via its admin app). Wait 3 seconds.
4. **Plug router back in** (or toggle on). Wait until both devices' Wi-Fi indicators show full bars (~30 seconds).
5. Send "after-storm-1" from iOS, "after-storm-1" from Android. Confirm both arrive.
6. Repeat steps 3–5 two more times (3 storms total).
7. Stop log capture.

**iOS / Android logs to capture.** Same channels as Test 1, file slug `reconnect-storm`.

**Success criteria.**
- All 3 rounds of "after-storm-N" delivered both ways.
- Zero ZOMBIE / STUCK / WARN warnings.
- Each Wi-Fi-back-on event shows session reaching Connected within 10 seconds of full bars.
- Final session count = 1 per side.

**Failure signatures.**
- After router is back on for 60+ seconds, either side shows session count = 0 and the other peer in Peers list says "Connect" (not "Connected").
- ZOMBIE / STUCK warnings.
- A `WARN: 2 sessions for peer=` indicating the SDK ended up with duplicate sessions and didn't clean one up.

**Repeat.** 1 run of 3 storms. If clean, move to Test 3.

**Paste back.** Same format as Test 1, replace test name.

---

## Test 3 — Hotspot switch / network rotation

**Goal.** Verify the SDK recovers when **one device** moves to a different Wi-Fi network while the other stays put. This is the test that exercises the "stale internalPeer" weakness — we're verifying v0.3 recovers even if not optimally.

**Setup.**
- You'll need **two Wi-Fi networks** that the iPhone can join. Easiest combo: your home Wi-Fi + your Android phone's personal hotspot.
- Enable Personal Hotspot on Android: Settings → Network & Internet → Hotspot & Tethering → Wi-Fi Hotspot → On. Note the SSID and password.
- Both apps Connected on the **home** Wi-Fi.

**Steps to reproduce.**
1. Start log capture (`<TEST>=hotspot-switch`).
2. Send "before-switch" each way. Confirm both arrive.
3. On iPhone: Settings → Wi-Fi → connect to the **Android hotspot** (different network from Android-the-app, which is still on home Wi-Fi).
4. Wait 30 seconds. Watch the iOS app's Diagnostic log and Status header — the chip should go red ("offline") momentarily then green ("online") on the hotspot.
5. iOS app: tap **Send all**. Note whether it arrives. (It probably won't — Android is on a different network now.)
6. Now switch iPhone back: Settings → Wi-Fi → connect to **home Wi-Fi** (same as Android).
7. Wait 30 seconds for Bonjour to rediscover.
8. iOS app: type "after-rejoin" → Send all. Confirm Android receives.
9. Stop log capture.

**Logs to capture.** Same channels, file slug `hotspot-switch`.

**Success criteria.**
- During step 4 on the hotspot: iOS session for Android either goes to `Failed` (expected — `internalPeer` cached the old address) or stays Reconnecting until `markFailedAfterExhaustion` fires.
- The STUCK warning should **not** fire (because `markFailedAfterExhaustion` should kick in well before 30 s).
- After step 6 (back on home): iOS rediscovers Android, a new session forms, "after-rejoin" arrives.
- Zero ZOMBIE warnings. Zero check() failures.

**Failure signatures.**
- STUCK warning fires (meaning the session got stuck in Reconnecting and never reached terminal).
- After step 7 (60+ seconds on home Wi-Fi again), iOS still shows Android with the "Connect" button, no session forming despite `[browse] emitPeer: ACCEPTED Updated` in the log.
- "after-rejoin" message never arrives.
- Two sessions for Android in iOS UI after step 7.

**Repeat.** 1 run.

**Paste back.** Same format as Test 1. **Additionally** paste any single `[session]` transition line for the Android peer during the test — these tell us which path the SDK took.

---

## Test 4 — Background / foreground churn

**Goal.** Verify iOS scene-phase background-then-foreground transitions don't leave the kit in a half-stopped state. (This is the test most likely to expose a real bug — `BackgroundPolicy.CloseActiveSessions` is on the v0.4 cleanup list.)

**Setup.**
- Same as Test 1, session established.

**Steps to reproduce.**
1. Start log capture (`<TEST>=bgfg-churn`).
2. Send "before-bg" each way. Confirm.
3. On iPhone: swipe up from bottom to background the app. Wait 3 seconds.
4. Tap the app icon to bring back to foreground. Wait 3 seconds.
5. Repeat steps 3–4 four more times (5 cycles total).
6. After the fifth foreground: Android side → type "after-bg" → Send. Note whether iOS receives. iOS side → type "after-bg" → tap Send all. Note whether Android receives.
7. Stop log capture.

**Logs to capture.** Same channels, file slug `bgfg-churn`.

**Success criteria.**
- After the fifth return-to-foreground, "after-bg" arrives both ways within 10 seconds.
- Zero `ZOMBIE` warnings.
- Zero `check()` failures.

**Failure signatures.**
- After fifth foreground: iOS shows no peer or no session, AND tapping Start does nothing (`ensureStarted` shortcuts to success but the transports are actually torn down).
- ZOMBIE warning during a foreground cycle.
- `I-double-terminal` or `I-terminal-state` check() failure.
- iOS app crashes on a Kotlin exception in the Xcode console.
- iOS app shows pre-background sessions still listed even after going to background.

**Repeat.** 1 run of 5 cycles. Pre-test note: this is the test most likely to expose anomalies because `BackgroundPolicy.CloseActiveSessions` has known weaknesses. Document what you see — failures here are **expected to be documented but not blocking** for proceeding to S1.

**Paste back.** Same format as Test 1, with an additional note: "expected to fail in known ways" + describe what you observed.

---

## Test 5 — Parallel file-transfer + reconnect

**Goal.** Verify a file transfer in flight reaches a clean terminal state (Failed, not stuck Sending) when the underlying session goes Reconnecting / Failed mid-stream.

**Setup.**
- Same as Test 1, both devices Connected.
- On Android, have a **5–10 MB file** ready to send (any video clip or photo from gallery).

**Steps to reproduce.**
1. Start log capture (`<TEST>=file-reconnect`).
2. On Android app: in the Sessions section, tap the **⋮** menu next to the connected peer chip → "Send file…". Pick a 5–10 MB file.
3. Watch Android's File Transfers section: the row should transition `offered → accepted → sending NN%`.
4. **When progress reaches ~30%**: on iPhone toggle Wi-Fi Off → wait 5 seconds → toggle On.
5. Watch both devices' file-transfer rows. Note the final state.
6. After the file is in a terminal state (Completed, Failed, or Cancelled), send "after-file" each way to confirm the session is or isn't usable.
7. Stop log capture.

**Logs to capture.** Same channels, file slug `file-reconnect`.

**Success criteria.**
- Android's file row eventually reaches a clean terminal state: either `failed — …` or `cancelled — …`. It should NOT be stuck at `sending NN%`.
- iOS's incoming file row similarly reaches Failed/Cancelled, not stuck at Accepted.
- The session itself recovers (Reconnecting → Connected) once Wi-Fi is back, OR cleanly goes to Failed + a new session forms when Android auto-mesh re-dials. Either is acceptable.
- Zero ZOMBIE warnings. Zero STUCK warnings.

**Failure signatures.**
- File row stuck at `sending NN%` indefinitely after Wi-Fi is back.
- ZOMBIE warning during file transfer cleanup.
- iOS's incoming directory (`~/Library/Containers/.../Documents/p2pkit-incoming/` for the iOS app — accessible via Xcode → Window → Devices and Simulators → your iPhone → app → Files) contains a partial file that doesn't show up in the UI.
- `check()` failure during cleanup.

**Repeat.** 1 run.

**Paste back.** Same format as Test 1, plus the final state of the file-transfer row from each device.

---

## Quick reference

### Log filter expressions

| Channel | Filter |
|---|---|
| Xcode iOS console | type `p2pkit` in filter box at bottom-right |
| Android logcat | `adb logcat -s p2pkit:V` |

### Signature strings to grep for in saved logs

```sh
# In a saved log file (iOS or Android):
grep -E "ZOMBIE|STUCK|WARN.*session|WARN.*peer.*matching|registerSession|check.* failed|Uncaught Kotlin" /tmp/p2pkit-<TEST>.log
```

If that command outputs anything, that test has anomalies. Paste back the output plus 10 lines of context.

### iOS app crash recovery

If the iPhone app crashes (a `check()` failure does this), the Xcode console will show the stack trace. Copy the stack + the 30 lines preceding it. The crash is the signal — that's exactly what S3's hard invariants are designed to do.

---

## Final paste-back

After all 5 tests, paste this filled-in summary as a single block:

```
Hardware validation results — <date>

iOS device: <iPhone model, iOS version>
Android device: <model, Android version>
Wi-Fi: <SSID / type, e.g., 2.4 GHz home AP>

Test 1 — WiFi flap:       PASS / FAIL / ANOMALY
Test 2 — Reconnect storm: PASS / FAIL / ANOMALY
Test 3 — Hotspot switch:  PASS / FAIL / ANOMALY
Test 4 — Bg/fg churn:     PASS / FAIL / ANOMALY  (known-weak; describe)
Test 5 — File + reconnect: PASS / FAIL / ANOMALY

Aggregate counts (sum across all 5 tests):
ZOMBIE warnings:          <number>
STUCK warnings:           <number>
duplicate-session WARNs:  <number>
peer-id-mismatch WARNs:   <number>
check() failures:         <number>

Verdict (one of):
  CLEAN — proceed to S1
  ONE-OFF WATCHDOG — investigate <name> failure mode only
  ASSERTION FAILED — stop, root-cause before any refactor

Anomaly logs (if any): <attach files or paste excerpts>
```

After you paste this back, I'll either start S1 (clean run), open a focused fix branch for the one failure mode (watchdog fired), or stop and root-cause (check() crash). Don't proceed past the verdict to S1 without my acknowledgement.
