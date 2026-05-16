# P2pKit v0.2 — Internal Testing Guide

How to validate v0.2-dev by hand. Read top to bottom on the first run; the checklist at the end is what to re-check before tagging future internal builds.

The two canonical test harnesses are:
- **`:p2p-sample-android`** — the primary visual harness (room mode, reconnect picker, log strip).
- **`:p2p-sample-desktop`** — the CLI; the canonical JVM harness.

`:p2p-sample-desktop-ui` (Compose) is a **legacy v0.1 single-session demo** and is not used for v0.2 testing. It still compiles and ships a banner saying so.

---

## 0. Prerequisites

| Need | What works |
|---|---|
| Operating system | Windows 11, recent macOS, recent Linux |
| JDK | JDK 17 or JDK 21 (project builds on 21; 17+ is enough to run) |
| Android SDK | API 36 platform installed |
| Two endpoints minimum | desktops, phones, or any mix on the **same Wi-Fi LAN** |
| Wi-Fi network | Home / phone hotspot / co-located LAN. **Corporate, guest, hotel networks frequently block mDNS multicast** — see §E. |

Three endpoints unlock the multi-peer room test (§B). Any further peers work identically — there is no SDK cap.

---

## 1. Build the artifacts

From the project root:

```powershell
.\gradlew.bat :p2p-core:allTests `
              :p2p-transport-lan:jvmTest `
              :sample-kmp-shared:jvmTest `
              :p2p-sample-desktop:installDist `
              :p2p-sample-android:assembleDebug
```

POSIX:
```bash
./gradlew :p2p-core:allTests \
          :p2p-transport-lan:jvmTest \
          :sample-kmp-shared:jvmTest \
          :p2p-sample-desktop:installDist \
          :p2p-sample-android:assembleDebug
```

**Expected**: `BUILD SUCCESSFUL`, 93 tests completed in `:p2p-core:allTests` / 0 failed, plus the LAN + KMP loopback tests green. APK at `p2p-sample-android/build/outputs/apk/debug/p2p-sample-android-debug.apk`. Launcher at `p2p-sample-desktop/build/install/p2p-sample-desktop/bin/p2p-sample-desktop[.bat]`.

Install the APK on the test device:
```powershell
adb install -r .\p2p-sample-android\build\outputs\apk\debug\p2p-sample-android-debug.apk
```

Keep a logcat terminal open for the duration of the test:
```powershell
adb logcat -c
adb logcat -s p2pkit:*
```

---

## A. Android ↔ JVM test

Verifies discovery both ways, connect in both directions, send in both directions.

**Devices:** one Android phone + one JVM desktop on the **same** Wi-Fi.

1. Launch the JVM CLI: `p2p-sample-desktop.bat Alice`. Expect banner `[P2pKit CLI] deviceName=Alice  appId=p2pkit-desktop-sample  reconnect=Disabled`.
2. Launch the Android sample on the phone, name `Bob`, leave reconnect on **Disabled**, tap **Start**. Logcat: `kit started: deviceName=Bob appId=p2pkit-desktop-sample peerId=<uuid> reconnect=Disabled`.
3. Within ~5–10 s:
   - **Desktop**: `[peers] 1: Bob(<id>)`.
   - **Phone**: "Discovered peers (1)" with `Alice` row.
4. **`info`** on the desktop CLI → prints `appId`, `localDeviceName`, `localPeerId`, kit state Running, advertising true, discovering true, peers known 1, active sessions 0.
5. **On the phone**: tap **Connect** on Alice's row. Phone timeline: `[system] connected to Alice`. Desktop: `[incoming] from Bob (<id>)` + `[state] Bob → Connected`.
6. **Phone → JVM**: phone has 1 chip "Alice · connected", no chip selected (broadcast), Send button reads `Broadcast (1)`. Type "hi from Bob" and Send. Desktop: `[Bob] hi from Bob`. Phone timeline: `me [broadcast]: hi from Bob`.
7. **JVM → Phone**: desktop `> send hi from Alice`. Desktop: `[broadcast → 1] hi from Alice`. Phone timeline: `Alice → hi from Alice`.
8. **Targeted send (desktop side)**: `> to bob private msg`. Desktop: `[to Bob] private msg`. Phone: `Alice → private msg`. (No other peers, but the codepath is exercised.)
9. **Reverse connect** — tap **Stop** on the phone, **Start** again. Wait for desktop's `[peers] 1: Bob(<id>)`. On desktop: `> connect bob`. Expect `connected to Bob` + `[state] Bob → Connected`. Then `> send hi again`. Phone receives.

**Pass criteria**: all nine steps complete with the exact log/UI signals shown. Any deviation → §E troubleshooting.

---

## B. Multi-peer room test (3+ devices)

Verifies broadcast, targeted send, and that one peer leaving doesn't break the others. There is no fixed SDK cap on peer count — 4, 5, 10+ devices work the same way, only network capacity changes the practical limit.

**Devices:** three or more endpoints on the same Wi-Fi.

1. Start **Alice** (desktop CLI) and **Charlie** (desktop CLI in a second terminal).
2. Start **Bob** (Android sample).
3. Verify each sees the other two: `> peers` on Alice/Charlie should list two; phone shows "Discovered peers (2)".
4. **Connect Bob → Alice** and **Bob → Charlie** on the phone (tap **Connect** on both). Connected-peer row shows two chips: `Alice · connected` and `Charlie · connected`.
5. **Broadcast from Bob**: no chip selected, Send button reads `Broadcast (2)`. Type "hello room" → both Alice's terminal and Charlie's terminal print `[Bob] hello room`. Phone logcat shows `room: broadcast → 2 peer(s): hello room`.
6. **Broadcast from Alice**: `> connect bob` and `> connect charlie` on Alice, then `> send hi all`. Alice prints `[broadcast → 2] hi all`. Bob's phone timeline gains `Alice → hi all`. Charlie prints `[Alice] hi all`.
7. **Targeted send (Android multi-select)**: on the phone, tap the Alice chip only. Send button reads `Send to 1`. Type "for Alice only", Send. Alice receives, Charlie does **not**. Phone logcat: `room: targeted → 1 peer(s)`.
8. **Targeted send (desktop)**: Alice's CLI `> to charlie just for Charlie`. Charlie receives, Bob's phone does **not**.
9. **One peer leaves**: Charlie's CLI `> quit`. Alice's terminal shows `[peers]` shrinking and `[state] Charlie → Closed`. Phone's room shrinks to one chip; phone sends another broadcast → reaches Alice only (`Broadcast (1)`).
10. **Scaling smoke**: start a fourth instance (`p2p-sample-desktop.bat Dave`). Within seconds Bob's phone shows a "Connected (3)" potential count and Alice/Bob list it. Connect to Dave from Bob (tap Connect). Broadcast → reaches both Alice and Dave (and Charlie if re-launched). The N grows; no code changes needed.

**Pass criteria**: broadcast count matches the live connected-peer count at every send. Targeted sends never leak. Closing one peer leaves the others' sessions intact.

---

## C. ReconnectPolicy test

Verifies `ReconnectPolicy.Enabled(maxAttempts, retryDelayMillis)` drives a session through `Reconnecting` and back to `Connected` after a transient break, or to `Failed` after exhaustion.

**Devices:** Android phone + JVM CLI on the same Wi-Fi.

1. On the phone Setup screen, switch reconnect to **Enabled** with **maxAttempts = 5** and **retryDelayMillis = 1000**. Tap **Start**. Logcat: `kit started: … reconnect=Enabled(maxAttempts=5, retryDelayMillis=1000)`.
2. Start the JVM CLI with **matching** reconnect: `p2p-sample-desktop.bat Alice p2pkit-desktop-sample reconnect=5,1000`.
3. Connect Bob → Alice from the phone. Phone chip shows `Alice · connected`. Desktop `[state] Bob → Connected`.
4. **Trigger a transient break**: kill Alice's process (Ctrl-C in the terminal).
5. **Phone observation**:
   - Chip flips to `Alice · reconnecting` within ~1 s.
   - Logcat: `session Alice → Reconnecting`.
   - Logcat continues: `Reconnect attempt 1/5 for Alice failed: …` every second.
6. **Within the retry window**: relaunch Alice with the same name and appId (`p2p-sample-desktop.bat Alice p2pkit-desktop-sample reconnect=5,1000`).
7. **Phone observation**: chip flips back to `Alice · connected`. Logcat: `session Alice → Connected` + `Session …: reconnected to Alice on attempt N`.
8. **Exhaustion path**: kill Alice and don't relaunch. After 5 attempts, phone chip flips to `Alice · failed`. Logcat: `session Alice → Failed`. The phone's connected-peer row clears the Alice chip on the next reconcile pass.
9. **Manual close beats retry**: connect again, kill Alice, while phone shows `Alice · reconnecting`, long-press the chip → **Close session**. Chip clears; logcat: `session Alice → Closed` (not `Failed`).

**Pass criteria**: state machine walks `Connected → Reconnecting → Connected` on success, `→ Failed` after `maxAttempts`, `→ Closed` when user closes mid-retry. No spurious transitions in either direction.

---

## D. PeerId persistence test

Verifies the local PeerId survives a restart of either platform.

**Desktop ↔ Desktop**:

1. Start `Alice`. On `Alice's` terminal run `info`; record the `localPeerId` line.
2. Start `Bob` in another terminal. On Bob's terminal, `peers` shows Alice with that same id prefix.
3. Quit Alice (`> quit`). Re-launch with the same args.
4. On Alice's new session, `info` shows the **same** `localPeerId` as step 1.
5. Bob's `peers` re-shows Alice with the same id prefix.

**Android ↔ JVM**:

1. Launch the Android sample, note the `peerId` shown in the Room header status block.
2. Force-stop the Android app (Settings → Apps → P2pKit Sample → Force stop).
3. Re-launch. The `peerId` in the header is the **same** value.
4. JVM CLI peers list shows the phone with the same id prefix.

**Negative case (Android without init)**: temporarily revert `P2pKitSampleApplication.onCreate` to not call `P2pKitAndroid.initialize(this)`. On launch, logcat warns `PeerId persistence: P2pKitAndroid.initialize(context) was not called…`. PeerId rotates on every relaunch. Restore the init call.

**Pass criteria**: same `localPeerId` across restarts on JVM (file-backed), on Android with `P2pKitAndroid.initialize` (filesDir-backed), and on iOS (NSUserDefaults — only verifiable on macOS once iOS LAN ships in v0.3).

---

## E. Android mDNS / MulticastLock test

Verifies the Android side actually receives mDNS broadcasts. The v0.2 `AndroidLanDiscoveryTransport` acquires a `WifiManager.MulticastLock` tagged `p2pkit-mdns` on the first of `startAdvertising` / `startDiscovery`, released when both have stopped.

1. **Setup**: phone running the sample, JVM CLI on the same Wi-Fi.
2. **Asymmetric symptom check**:
   - Desktop sees the phone in `[peers]`? Yes → outgoing multicast from Android works (lock not needed for *sending*).
   - Phone shows the desktop in "Discovered peers"? Yes → receiving multicast works → lock is active.
   - If desktop sees phone but phone shows 0 peers → lock is failing or never acquired.
3. **Lock diagnostic** (`adb shell` accepts Windows backslash too):
   ```powershell
   adb shell dumpsys wifi | findstr /i "multicast p2pkit-mdns"
   ```
   Expect a line containing `p2pkit-mdns`. If absent after **Start**, the lock isn't being acquired and v0.2 task 5 isn't taking effect on this device.
4. **Lifecycle**: toggle the Discover switch off in the Android sample. Wait a moment, re-check the dumpsys output — if advertising is also off, the lock should disappear from the output (it's only held while at least one of adv/disc is on).
5. **Failure modes to recognise**:
   - Phone "Discovered peers (0)" + desktop sees phone → multicast filter (lock issue or OEM filtering).
   - Neither side sees anything → router blocks multicast, VPN active, or different Wi-Fi SSIDs.
   - Phone sees desktop briefly then loses it → MulticastLock dropped because the kit was stopped/restarted; tap **Stop** then **Start** to re-acquire.

**Pass criteria**: dumpsys shows the lock during operation, lock disappears after kit stops, discovery works both ways.

---

## F. Unsupported iOS status

iOS in v0.2 is **core scaffolding only**:

- `:p2p-core` declares `iosX64`, `iosArm64`, `iosSimulatorArm64` targets.
- `iosMain` ships `Platform.IOS`, `systemTimeMillis()`, and `NSUserDefaults`-backed `PeerIdStorage`.
- **No iOS LAN transport** in `:p2p-transport-lan`. No `NWBrowser`, no `NWListener`, no `NWConnection`, no iOS sample app.
- iOS targets cannot exchange LAN messages with Android/JVM peers in v0.2.
- iOS Network Provisioning is **never planned** — Apple does not allow third-party apps to create hotspots or join Wi-Fi silently.

Verification on this Windows release pipeline is limited to:

```powershell
.\gradlew.bat :p2p-core:tasks --all | findstr /i ios
```

— which should list `compileKotlinIosArm64`, `iosSimulatorArm64MainKlibrary`, etc., proving the project model is consistent. Actually running iOS compile / link / test tasks requires a macOS host with Xcode. Cross-platform iOS verification waits for v0.3.

When v0.3 ships iOS LAN, the test sections will gain an iOS device matching steps A/B/C with `_p2pkit._tcp` Bonjour interop.

---

## 5. Windows Defender Firewall

On Windows, the **first** time you run the desktop sample, Defender prompts to allow inbound TCP for the Java runtime.

- **Allow on Private networks.**
- If you accidentally clicked "Block":
  ```powershell
  Get-NetFirewallRule -DisplayName "*OpenJDK*","*Java*","*p2pkit*" | Remove-NetFirewallRule
  ```
  Re-run the sample to get the prompt again.

mDNS (UDP 5353) is normally permitted on private profiles by default.

---

## 6. Wi-Fi / mDNS multicast — common failure mode

P2pKit v0.2 uses **mDNS** (UDP multicast on 224.0.0.251 : 5353) for peer discovery. Many networks block multicast:

| Network type | Multicast support |
|---|---|
| Home Wi-Fi | usually fine |
| Phone hotspot | fine |
| Personal ethernet LAN | fine |
| Office / guest / hotel Wi-Fi | **usually blocked** |
| University residential Wi-Fi | mixed; often blocked |
| Some VPNs | mDNS doesn't traverse |

**Symptom**: both endpoints start cleanly and stay on "Discovered peers (0)" indefinitely.

**Workaround for testing**: use a phone hotspot or home Wi-Fi.

Also: **Android on mobile data only** cannot discover LAN peers — both endpoints must be on Wi-Fi.

---

## 7. Release checklist (v0.2-dev)

Run through this before tagging.

- [ ] `./gradlew :p2p-core:allTests :p2p-transport-lan:jvmTest :sample-kmp-shared:jvmTest :p2p-sample-android:assembleDebug :p2p-sample-desktop:installDist :p2p-sample-desktop-ui:assemble` → all green.
- [ ] **§A** Android ↔ JVM walkthrough passes nine-of-nine.
- [ ] **§B** Three-device room broadcast verified at N ≥ 3 (4+ ideally).
- [ ] **§C** ReconnectPolicy roundtrip verified: Connected → Reconnecting → Connected, and exhaustion → Failed.
- [ ] **§D** PeerId persistence verified on both JVM and Android.
- [ ] **§E** MulticastLock dumpsys diagnostic shows `p2pkit-mdns` during operation.
- [ ] **§F** iOS scaffolding state is unchanged: targets visible in `:p2p-core:tasks --all`, no LAN transport.
- [ ] Known Limitations in `README.md` reviewed; nothing new has slipped in.
- [ ] No leftover TODO / FIXME / debug `println` in shipping code (sample `println` is fine).
- [ ] Compose Desktop UI sample (`:p2p-sample-desktop-ui`) compiles and shows the legacy banner.

When all boxes tick, **tag the v0.2-internal milestone** and share this guide with the testers.
