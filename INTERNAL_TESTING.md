# P2pKit v0.1 — Internal Testing Guide

How to validate the **v0.1-internal** build by hand: two desktops, two phones, or one of each. Read top to bottom on the first run; the checklist at the end is what to re-check before tagging future internal builds.

---

## 0. Prerequisites

| Need | What works |
|---|---|
| Operating system | Windows 11, recent macOS, recent Linux |
| JDK | JDK 17 or JDK 21 (the project uses 21 locally; 17+ is enough to run) |
| Android SDK | API 36 platform installed (Android Studio with SDK platform 36 is the easiest way) |
| Two endpoints | Two desktops, two phones, or one of each — both on the **same Wi-Fi LAN** |
| Wi-Fi network | Any home / personal hotspot / co-located LAN. **Corporate, guest, and hotel networks frequently block mDNS multicast** — see §6. |

You don't need IntelliJ / Android Studio to run the samples — Gradle is enough. They make Android-side debugging easier though.

---

## 1. One-time build

From the project root (`D:\shareing lib` in this checkout):

```powershell
.\gradlew.bat :p2p-core:allTests `
              :p2p-transport-lan:jvmTest `
              :p2p-core:assemble `
              :p2p-transport-lan:assemble `
              :p2p-sample-desktop:installDist `
              :p2p-sample-android:assembleDebug
```

POSIX shell:
```bash
./gradlew :p2p-core:allTests \
          :p2p-transport-lan:jvmTest \
          :p2p-core:assemble \
          :p2p-transport-lan:assemble \
          :p2p-sample-desktop:installDist \
          :p2p-sample-android:assembleDebug
```

**Expected**: `BUILD SUCCESSFUL`, `91 tests completed, 0 failed`, an APK at `p2p-sample-android/build/outputs/apk/debug/p2p-sample-android-debug.apk`, and a launcher script at `p2p-sample-desktop/build/install/p2p-sample-desktop/bin/p2p-sample-desktop[.bat]`.

---

## 2. Desktop ↔ Desktop

Run two CLI instances on **two terminals on the same machine** *or* on two machines on the same Wi-Fi.

**Terminal 1 (Alice):**
```powershell
.\p2p-sample-desktop\build\install\p2p-sample-desktop\bin\p2p-sample-desktop.bat Alice
```

**Terminal 2 (Bob):**
```powershell
.\p2p-sample-desktop\build\install\p2p-sample-desktop\bin\p2p-sample-desktop.bat Bob
```

POSIX equivalent: `./p2p-sample-desktop/build/install/p2p-sample-desktop/bin/p2p-sample-desktop Alice` / `Bob`.

**Then in Terminal 1:**
```
> peers
> connect <id-prefix-shown-for-bob>
> send hello from Alice
```

**Expected**:
- Within ~5 seconds of starting the second instance, each terminal prints a `[peers] 1: …` line that lists the other.
- After `connect`, Terminal 1 prints `connected to Bob (<id-prefix>)`.
- After `send`, Terminal 2 prints `[Alice] hello from Alice`.
- Typing `quit` (or Ctrl-D) on either side exits cleanly with `Stopping…`.

---

## 3. Android ↔ Android

Install the debug APK on two devices on the same Wi-Fi:

```powershell
$apk = ".\p2p-sample-android\build\outputs\apk\debug\p2p-sample-android-debug.apk"
adb devices                                    # list connected devices
adb -s <serial-A> install -r $apk
adb -s <serial-B> install -r $apk
```

**On each device:**
1. Launch the **P2pKit Sample** app.
2. Enter a distinct device name (`Alice` / `Bob`).
3. Tap **Start**.

**Expected**:
- Within ~5 seconds, each device shows the other under `Discovered peers (1)`.
- Tap **Connect** on the discovered peer. Within a second or two the session pane appears with `Connected`.
- Type a message in the text field and tap **Send**. The other device shows `<other-name>: hello`.
- Tap **Stop** to return to setup. The kit cleans up.

---

## 4. Desktop ↔ Android

**Same as §2 and §3 above, but the two endpoints must use the same `appId`.** v0.1 samples ship with different defaults:

| Sample | Default `appId` |
|---|---|
| `p2p-sample-desktop` | `p2pkit-desktop-sample` |
| `p2p-sample-android` | `dev.p2pkit.sample.android` |

Pick one option to align them:

### Option A — pass the Android `appId` to the desktop sample

```powershell
.\p2p-sample-desktop\build\install\p2p-sample-desktop\bin\p2p-sample-desktop.bat Alice dev.p2pkit.sample.android
```

### Option B — edit the Android sample to match the desktop

```kotlin
// p2p-sample-android/src/main/java/dev/p2pkit/sample/android/MainActivity.kt
private const val APP_ID = "p2pkit-desktop-sample"   // was "dev.p2pkit.sample.android"
```

Then rebuild + reinstall: `./gradlew :p2p-sample-android:installDebug`.

Once the `appId`s match, the rest is the same — start, discover, connect, send. **Expected behavior is identical to §2 and §3.**

---

## 5. Windows Defender Firewall

On Windows, the **first** time you run the desktop sample, Defender prompts to allow inbound TCP for the Java runtime.

- **Allow on Private networks.** Public networks are usually fine for outbound, but inbound (i.e., accepting a connection from another instance) needs the rule.
- If you accidentally clicked "Block", clear the rule:
  ```powershell
  Get-NetFirewallRule -DisplayName "*OpenJDK*","*Java*","*p2pkit*" | Remove-NetFirewallRule
  ```
  Re-run the sample to get the prompt again.

mDNS (UDP 5353) is normally permitted on private profiles by default. If discovery doesn't work even after allowing TCP, double-check the firewall profile (private vs public).

---

## 6. Wi-Fi / mDNS multicast — common failure mode

P2pKit v0.1 uses **mDNS** (UDP multicast on 224.0.0.251 : 5353) for peer discovery. Many networks block multicast:

| Network type | Multicast support |
|---|---|
| Home Wi-Fi | usually fine |
| Phone hotspot | fine |
| Personal ethernet LAN | fine |
| Office / guest / hotel Wi-Fi | **usually blocked** |
| University residential Wi-Fi | mixed; often blocked |
| Some VPNs | mDNS doesn't traverse them |

**Symptom**: both endpoints start cleanly and stay on `Discovered peers (0)` indefinitely.

**Workaround for testing**: use a phone hotspot or home Wi-Fi. v0.2 will add a manual-IP fallback so testers can paste a host:port pair when discovery fails.

Also: **Android on mobile data only** cannot discover LAN peers — both endpoints must be on Wi-Fi.

---

## 7. Success criteria

A v0.1-internal / v0.2-dev release passes when **all six** are true:

1. `./gradlew :p2p-core:allTests :p2p-transport-lan:jvmTest :sample-kmp-shared:jvmTest` reports **all tests passing, 0 failures**.
2. Two desktop CLIs on the same machine **discover each other within 10 s** and exchange a text message both ways.
3. Two Android devices on the same Wi-Fi **discover each other within 10 s** and exchange a text message both ways.
4. One desktop + one Android (with `appId` aligned per §4) discover each other and exchange a text message both ways.
5. **`PeerId` persists across restarts** on both platforms — see "Verifying PeerId persistence manually" below.
6. The items under **"Known limitations"** in [README.md](./README.md) have been reviewed and accepted by the tester.

If any of these fails, file a bug. If discovery hangs on a network you suspect blocks multicast, **first** retry on a phone hotspot before filing.

### Verifying Android rotation manually (v0.2 Task 2)

1. Install the sample APK on one Android device and another peer (desktop or second Android).
2. Tap **Start** on the Android side. Wait for the other peer to appear in the list. Optionally tap **Connect** and exchange a message.
3. Rotate the phone (portrait ↔ landscape).
4. The running screen should **stay on screen** — no flip back to setup, no flicker. The discovered-peers count, active session, and chat log should all be preserved.
5. Tap **Stop** to confirm the explicit teardown still works.
6. Swipe the app away from recents to confirm process-level cleanup runs `kit.stop()` in `ViewModel.onCleared()`.

If rotation sends you back to the setup screen, the host activity was destroyed without preserving the ViewModel — check that `MainActivity` is using `viewModel()` (not `remember`) for the `P2pKitViewModel`.

**Known boundary**: Android may kill the app's process while it's backgrounded under memory pressure. When that happens, the ViewModel is destroyed with the process. Re-launching the app returns to the setup screen. This is documented as v0.3 work (`SavedStateHandle` integration).

### iOS scaffolding (v0.2 Task 4) — out of scope for the Windows release pipeline

v0.2 adds `iosX64`, `iosArm64`, and `iosSimulatorArm64` targets to `:p2p-core` with `iosMain` actuals for `Platform.IOS`, `systemTimeMillis()`, and `PeerId` persistence via `NSUserDefaults`. **No LAN transport is implemented for iOS in v0.2** — Bonjour / `NWBrowser` / `NWListener` / `NWConnection` ship in v0.3.

The release pipeline here is **Windows-host only**. iOS compile / link / test tasks require a macOS host with Xcode and are not exercised. The Windows acceptance criteria are:

1. The four-module command (§7 item 1) still passes — i.e., adding the iOS targets did not regress JVM/Android.
2. `./gradlew :p2p-core:tasks --all | findstr /i ios` lists iOS-scoped tasks (`compileKotlinIosArm64`, `iosSimulatorArm64MainKlibrary`, etc.) — proving the project model is consistent.

Full iOS verification — Local Network permission prompt, `NSUserDefaults` round-trip on simulator, cross-platform discovery with Android/JVM peers — is **deferred to v0.3** when the LAN transport actually exists. On macOS, future testers should run `./gradlew :p2p-core:iosSimulatorArm64Test` (which exercises the commonTest suite on iOS simulator) and confirm `BUILD SUCCESSFUL`. Until v0.3 lands, iOS targets cannot exchange messages with Android/JVM peers over LAN — they only verify that core types compile and `PeerId` persists.

### Verifying PeerId persistence manually

**Desktop ↔ Desktop:**

1. Start one CLI (`Alice`). Note the `id-prefix` shown for Alice in another machine's peer list (or another desktop UI window on the same machine).
2. `quit` Alice.
3. Re-launch Alice with the same args.
4. The other side's peers list should show Alice with the **same** id-prefix as before — confirming the JVM persisted `peer-id` under `<user.home>/.p2pkit/<appId>/peer-id`.

**Android ↔ Android:**

1. Launch the sample on phone A. Note the id-prefix shown for phone A in phone B's peer list.
2. Force-stop phone A's app (Settings → Apps → P2pKit Sample → Force stop).
3. Re-launch phone A's app.
4. Phone B's peer list should show phone A with the **same** id-prefix.
5. If you instead see a new id-prefix, the host app did not call `P2pKitAndroid.initialize(applicationContext)` from `Application.onCreate`. Check `adb logcat | grep p2pkit` for the warning `PeerId persistence: P2pKitAndroid.initialize(context) was not called …`.

### Verifying ReconnectPolicy.Enabled manually (v0.2 Task 3)

This exercises the **outgoing-only** reconnect path. The accepting peer doesn't auto-redial — it sees the dropped session as `Failed` and a new incoming session arrives once the dialler retries.

**Desktop ↔ Desktop**, easiest setup:

1. Edit `p2p-sample-desktop/src/jvmMain/kotlin/.../Main.kt` (or your local copy) to wrap the `lifecycle { }` block with `reconnectPolicy = ReconnectPolicy.Enabled(maxAttempts = 5, retryDelayMillis = 1_000)`. Rebuild with `:p2p-sample-desktop:installDist`.
2. Start two instances (`Alice` and `Bob`). Wait for `[peers] 1: …` on both, then on Alice run `connect <bob-id>` followed by `send hi`.
3. With Alice still running, **Ctrl-C Bob**. On Alice you should see a session state change to `Reconnecting`, then attempt logs (`Reconnect attempt 1/5 for Bob failed …`) every second.
4. Re-launch Bob (same name and `appId`) within the 5-attempt window. Alice's session should flip back to `Connected` and you can `send` again on the same session id.
5. If you don't re-launch Bob, Alice's session ends in `Failed` after 5 failed dials. Alice should not retry beyond `maxAttempts`.

**Manual close stops retries:** while Alice's session is in `Reconnecting`, type `close <session>` (or `quit`) on Alice. The session should immediately end in `Closed`, never `Failed`, and no further retry attempts should hit the log.

**Stale address note:** if Bob comes back on a *different* IP (e.g., joined a different Wi-Fi), Alice's retries will keep dialling Bob's old IP and exhaust. The app must call `connect(peer)` again after the peer is re-discovered. Reconnect does not re-resolve discovery in v0.2.

---

## Release checklist (v0.1-internal)

Run through this before tagging.

- [ ] **All tests pass** — `./gradlew :p2p-core:allTests :p2p-transport-lan:jvmTest :sample-kmp-shared:jvmTest` → all green.
- [ ] **Desktop sample runs** — `:p2p-sample-desktop:installDist` succeeds; two instances on one machine reach `connect` + `send` (§2).
- [ ] **Android sample builds** — `:p2p-sample-android:assembleDebug` produces an APK; smoke-installs on one device and launches to the setup screen.
- [ ] **Known limitations reviewed** — the seven items in `README.md` § "Known limitations (v0.1)" are still accurate; nothing new has slipped in.
- [ ] **`appId` aligned for the cross-platform test** — confirmed via §4 by running one desktop ↔ one Android session end-to-end, or by code review of `Main.kt` / `MainActivity.kt`.
- [ ] **No new public APIs accidentally added** — public-symbol inventory matches Spec §7. (Quick grep: `grep -r "^public" p2p-core/src/commonMain/kotlin` should match the list in the v0.1 final report.)
- [ ] **No leftover TODO / FIXME / debug `println`** in shipping code — sample code's `println`s are fine.
- [ ] **`PeerId` is fresh per launch.** Documented; testers should expect a "new device" with a new id every time the sample app restarts. Persistent `PeerId` is v0.2.
- [ ] **`ReconnectPolicy.Enabled` retries outgoing sessions** (v0.2 task 3). Configuring it causes outgoing sessions to transition through `Reconnecting` and retry the dial up to `maxAttempts` times. Incoming sessions still go directly to `Failed` on connection loss. Verified by the manual recipe under "Verifying ReconnectPolicy.Enabled manually" above.

When all boxes are ticked, **tag `v0.1-internal`** and share this guide with the testers.
