# P2pKit v0.6 — Internal Testing Guide

How to validate v0.6-dev by hand. Read top to bottom on the first run; the checklist at the end is what to re-check before tagging future internal builds. Recipes were added incrementally from v0.2 onwards (the milestone tags in section headings are historical). For the v0.4 runtime-foundation hardware tests (Wi-Fi flap, hotspot switch, rebind log signatures) use `docs/v0.4-cumulative-validation-runbook.md`; for the five-test phone checklist use `docs/hardware-validation-checklist.md`.

The four canonical test harnesses:
- **`:p2p-sample-android`** — the primary visual harness on mobile (room mode, reconnect picker, log strip, chip state).
- **`:p2p-sample-desktop`** — the JVM CLI, scriptable from a terminal (`info`, `adv on/off`, `disc on/off`, `connect`, `send`, `to`, `close`).
- **`:p2p-sample-desktop-ui`** — Compose Desktop GUI mirroring the Android sample. Run with `./gradlew :p2p-sample-desktop-ui:run`.
- **`:iosApp`** — the SwiftUI iOS sample (Xcode project at `iosApp/p2pkit-sample.xcodeproj`, shipped in v0.4). The Xcode pre-build script rebuilds the XCFramework via `sh ./gradlew`; see §K.2 for running it.

Pick whichever fits the device under test. The same flows (§A–§K below) apply across all of them.

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

**Expected**: `BUILD SUCCESSFUL`, all test tasks green — `:p2p-core:allTests` (134 unique test methods; the reported total is higher because `allTests` runs commonTest on every target), 6 tests in `:p2p-network-provisioning-desktop:test` / 0 failed, 15 tests in `:p2p-network-provisioning-android:testAndroidHostTest` / 0 failed, plus the LAN + KMP loopback tests green. APK at `p2p-sample-android/build/outputs/apk/debug/p2p-sample-android-debug.apk`. Launcher at `p2p-sample-desktop/build/install/p2p-sample-desktop/bin/p2p-sample-desktop[.bat]`.

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

**Auto-mesh** is ON by default in every sample. When ON, each sample auto-connects to every newly-discovered peer using a lexicographic tie-break on `localPeerId` (only one side per pair initiates, the other accepts). With three samples on the same LAN this means **all three pair-wise sessions form automatically** — no manual Connect taps needed. To verify selective-connect behavior instead, toggle the Auto-mesh switch / `mesh off` first.

**Devices:** three or more endpoints on the same Wi-Fi.

1. Start **Alice** (desktop CLI) and **Charlie** (desktop CLI in a second terminal).
2. Start **Bob** (Android sample) — Auto-mesh ON.
3. Within ~5–10 s **all three** samples should show two chips / two sessions: every peer connected to every other peer via auto-mesh. On Alice's CLI: `> sessions` lists `Bob` and `Charlie`. On Bob's phone: chip row shows `Alice · connected` and `Charlie · connected`. On Charlie's CLI: `> sessions` lists `Alice` and `Bob`. Logs show `auto-mesh: initiating connect to <name>` for each pair where the local id was smaller.
4. (Skip if you used auto-mesh — already done.) If auto-mesh is OFF, **manually** connect each pair: `Connect Bob → Alice` and `Connect Bob → Charlie` on the phone, plus `> connect bob` and `> connect charlie` on Alice. Resulting state should match step 3.
5. **Broadcast from Bob**: no chip selected, Send button reads `Broadcast (2)`. Type "hello room" → both Alice's terminal and Charlie's terminal print `[Bob] hello room`. Phone logcat shows `room: broadcast → 2 peer(s): hello room`.
6. **Broadcast from Alice**: `> connect bob` and `> connect charlie` on Alice, then `> send hi all`. Alice prints `[broadcast → 2] hi all`. Bob's phone timeline gains `Alice → hi all`. Charlie prints `[Alice] hi all`.
7. **Targeted send (Android multi-select)**: on the phone, tap the Alice chip only. Send button reads `Send to 1`. Type "for Alice only", Send. Alice receives, Charlie does **not**. Phone logcat: `room: targeted → 1 peer(s)`.
8. **Targeted send (desktop)**: Alice's CLI `> to charlie just for Charlie`. Charlie receives, Bob's phone does **not**.
9. **One peer leaves**: Charlie's CLI `> quit`. Alice's terminal shows `[peers]` shrinking and `[state] Charlie → Closed`. Phone's room shrinks to one chip; phone sends another broadcast → reaches Alice only (`Broadcast (1)`).
10. **Scaling smoke**: start a fourth instance (`p2p-sample-desktop.bat Dave`). Within seconds Bob's phone shows a "Connected (3)" potential count and Alice/Bob list it. Connect to Dave from Bob (tap Connect). Broadcast → reaches both Alice and Dave (and Charlie if re-launched). The N grows; no code changes needed.

**Pass criteria**: broadcast count matches the live connected-peer count at every send. Targeted sends never leak. Closing one peer leaves the others' sessions intact. With auto-mesh ON, a 3-peer room forms three pair-wise sessions automatically (Alice↔Bob, Alice↔Charlie, Bob↔Charlie). With auto-mesh OFF, only the sessions you manually opened exist.

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

**Pass criteria**: same `localPeerId` across restarts on JVM (file-backed), on Android with `P2pKitAndroid.initialize` (filesDir-backed), and on iOS (NSUserDefaults-backed — launch the iosApp sample in the Simulator, note the peerId in the status header, quit and relaunch, and confirm it is unchanged).

---

## E. Android mDNS / MulticastLock test

Verifies the Android side actually receives mDNS broadcasts. The `AndroidLanDiscoveryTransport` (rewritten on in-process JmDNS in v0.5) still acquires a `WifiManager.MulticastLock` tagged `p2pkit-mdns` on the first of `startAdvertising` / `startDiscovery`, released when both have stopped.

1. **Setup**: phone running the sample, JVM CLI on the same Wi-Fi.
2. **Asymmetric symptom check**:
   - Desktop sees the phone in `[peers]`? Yes → outgoing multicast from Android works (lock not needed for *sending*).
   - Phone shows the desktop in "Discovered peers"? Yes → receiving multicast works → lock is active.
   - If desktop sees phone but phone shows 0 peers → lock is failing or never acquired.
3. **Lock diagnostic** (`adb shell` accepts Windows backslash too):
   ```powershell
   adb shell dumpsys wifi | findstr /i "multicast p2pkit-mdns"
   ```
   Expect a line containing `p2pkit-mdns`. If absent after **Start**, the lock isn't being acquired on this device.
4. **Lifecycle**: toggle the Discover switch off in the Android sample. Wait a moment, re-check the dumpsys output — if advertising is also off, the lock should disappear from the output (it's only held while at least one of adv/disc is on).
5. **Failure modes to recognise**:
   - Phone "Discovered peers (0)" + desktop sees phone → multicast filter (lock issue or OEM filtering).
   - Neither side sees anything → router blocks multicast, VPN active, or different Wi-Fi SSIDs.
   - Phone sees desktop briefly then loses it → MulticastLock dropped because the kit was stopped/restarted; tap **Stop** then **Start** to re-acquire.

**Pass criteria**: dumpsys shows the lock during operation, lock disappears after kit stops, discovery works both ways.

---

## F. iOS support status (v0.3+)

iOS LAN shipped in v0.3 — the same `transports { lan() }` API, the same `_p2pkit._tcp` service type, the same TXT record keys. Backed by `nw_listener_t` + `nw_connection_t` + `nw_browser_t` from `Network.framework`. The SwiftUI sample app (`iosApp/`, with `NSLocalNetworkUsageDescription` + `NSBonjourServices` wired in its `Info.plist`) shipped in v0.4, and v0.6 prohibits the cellular interface on the TCP parameters.

What works:
- Discovery via `NWBrowser` against the `_p2pkit._tcp` Bonjour service.
- Advertise via `nw_listener_set_advertise_descriptor` on the inbound listener.
- TCP data via `NWConnection` (non-TLS, matching `SecurityMode.NoneForMvp` on JVM/Android).
- File transfer, ReconnectPolicy, keep-alive — all the common-code features, since they're transport-agnostic.
- **iOS sample app** — Xcode project + SwiftUI UI under `iosApp/`; run it per §K.2. Consuming apps still need to wire their own `Info.plist` entries the same way.

Still missing on iOS:
- **iOS Network Provisioning** is **never planned** — Apple does not allow third-party apps to create hotspots or join Wi-Fi silently.

Quick code-only verification on macOS:

```bash
./gradlew :p2p-transport-lan:iosSimulatorArm64Test
```

— two `P2pKit` instances run inside the simulator process, advertise + discover over real Bonjour, and exchange text / 200 KB binary / 5 MiB file. Expected: all green — the `appleTest` suite is now 20 test methods across `IosLanLoopbackTest` (the three loopback cases), `IosBonjourTest`, `IosLanLifecycleTest`, and `IosLanDiagnosticTest` (`@Ignore`-gated capture fixture).

To see all iOS-related tasks: `./gradlew :p2p-transport-lan:tasks --all | grep -i ios`.

---

## G. JVM manual-IP fallback (v0.2.1 task 10)

Verifies the new `:p2p-network-provisioning-desktop` module: `getManualConnectionInfo()` surfaces local IP + port, and `createManualPeer(host, port)` lets you dial a peer without mDNS. Use when the router blocks multicast (corporate / guest / hotel Wi-Fi) or to bypass discovery entirely.

**Devices:** two JVM CLI samples, ideally on a network that blocks mDNS or with mDNS disabled (you can also just run two CLIs on `localhost` and skip discovery — call `manual` directly).

1. Start **Alice** and **Bob** (two JVM CLIs).
2. On each, run `> info` and read the `manual host(s)` and `manual port` lines. These come from `kit.networkProvisioning.getManualConnectionInfo()`. Expect one or more non-loopback IPv4 addresses and the LAN transport's TCP port.
3. From Alice's terminal, dial Bob by IP:
   ```
   > manual 192.168.x.y:NNNN
   ```
   Use one of the values from Bob's `info` output. Expect `connected manual peer …` plus a `[state] Bob → Connected` line and `[incoming] from Alice` on Bob's terminal.
4. Round-trip a message: `> send hello from Alice` — Bob's terminal prints `[Alice] hello from Alice`.
5. Repeat in reverse direction from Bob to confirm both sides can initiate.

**Pass criteria:** `info` shows non-empty manual info; `manual <host>:<port>` opens a session without any mDNS discovery; messages round-trip. Same Compose Desktop UI flow exists in the "Manual peer (mDNS fallback)" panel under the discovered-peers list.

**Common failure modes:**
- `manual info  (none — provisioning not configured or no LAN port)` — ensure the kit was built with `networkProvisioning { jvm() }` (both desktop samples ship this by default).
- `manual createManualPeer failed: host must not be blank` / `port out of range` — bad `host:port` syntax.
- Connect-then-immediate-close — the address you typed isn't reachable, or the other peer's TCP server isn't bound on that interface (try a different host address from `info`).

---

## H. Android hotspot host (v0.2.1 task 11)

Verifies the new `:p2p-network-provisioning-android` module: a phone can host a `LocalOnlyHotspot`, the sample shows the OS-chosen SSID + passphrase + `host:port`, and a second device joins via standard Wi-Fi settings.

**Devices:** one Android phone running the sample (the host) + a second Android phone (the guest) or any laptop with Wi-Fi.

1. **Install + launch the sample on the host phone.** Enter a name like `HostPhone`, leave reconnect at Disabled, tap **Start**. Logcat shows `kit started: …`.
2. **Tap "Host hotspot"** in the "Hotspot host (LocalOnlyHotspot)" Card on the running screen. If `NEARBY_WIFI_DEVICES` (API 33+) or `ACCESS_FINE_LOCATION` (API ≤ 32) isn't granted, the system prompts. Grant it. The Card now reads:
   ```
   SSID: AndroidShare_xxxx
   Pass: xxxxxxxx
   host(s): 192.168.43.1, …
   port: NNNNN
   ```
3. **On the guest device:** open Wi-Fi settings, find the `AndroidShare_xxxx` SSID, enter the passphrase from the host's screen, and connect. The guest is now on the host's hotspot subnet.
4. **Launch the sample on the guest device** (if Android) or any JVM CLI on the laptop. Both should auto-discover the host via mDNS over the hotspot subnet (auto-mesh forms the session). Round-trip a message.
5. **Tap "Stop hotspot"** on the host. The guest loses Wi-Fi (the AP went away). Host's Card returns to "Host a LocalOnlyHotspot …".
6. **OS-redacted credentials path:** revoke `NEARBY_WIFI_DEVICES` in Settings while the hotspot is running, then restart the kit. The Card should show `Hotspot up, but SSID/passphrase redacted by the OS. Share host:port directly.` with the manual `host:port` still visible.

**OEM quirks worth recording:**
- **Huawei (EMUI / HarmonyOS), MIUI, older Samsung**: `startLocalOnlyHotspot` throws `SecurityException: "Location mode is not enabled."` even when `NEARBY_WIFI_DEVICES` is granted. This is the **device-wide** Location toggle (Settings → Location), distinct from the runtime permission. The HotspotCard detects this case and shows an **"Open Location settings"** button; the user must flip the toggle, return to the sample, and tap **Retry**. No app-side workaround exists — this is enforced by the system Wi-Fi service.
- **Samsung One UI**: hotspot may also refuse while the user's Mobile Hotspot setting is on, or on enterprise-managed devices. Card shows `Failed: HotspotStopped — startLocalOnlyHotspot failed (reason code N: NAME)` with the decoded reason.
- **Xiaomi MIUI / HyperOS**: aggressive battery saver may kill the hotspot after a few minutes when no client is connected. Card flips to a Failed state via the `onStopped` event; tap **Retry** to start again.
- **Pre-API 30 devices**: SSID/passphrase come from `WifiConfiguration` (with surrounding quotes stripped) instead of `SoftApConfiguration`.

**Pass criteria:** Hotspot starts within ~2 seconds of tapping the button (after perm grant); SSID + passphrase + host:port appear; a second device on the same hotspot can find and connect via mDNS auto-mesh; tapping Stop releases the reservation cleanly.

**Common failure reasons:**
- `Failed: PermissionMissingForProvisioning — Missing permissions: [NearbyWifiDevices]` — the user denied the runtime perm. Re-tap "Grant permission and retry".
- `Failed: PermissionMissingForProvisioning — Missing permissions: [Location]` *(Huawei / MIUI / older Samsung)* — the device-wide Location toggle is OFF. The HotspotCard shows an "Open Location settings" button; flip the toggle, come back, hit Retry.
- `Failed: HotspotStopped — startLocalOnlyHotspot failed (reason code 0/1/2/3: NAME)` — system rejected. NO_CHANNEL (band conflict), GENERIC, INCOMPATIBLE_MODE, TETHERING_DISALLOWED. Try toggling Mobile Hotspot off, or rebooting.
- Card shows credentials but second device can't find the SSID — wait ~5 s after Started, then re-scan on the guest. Android can take a moment to bring up the AP interface.

---

## I. Android hotspot join (v0.2.1 task 12)

Verifies `WifiNetworkSpecifier`-based Wi-Fi join: the guest device joins the host device's `LocalOnlyHotspot` from inside our sample (no system Wi-Fi settings detour), the OS shows the per-app approval prompt, and once joined, our LAN transport's outgoing sockets route through the joined network so mDNS finds the host and auto-mesh forms.

**Devices:** the same two phones as §H — a host device running task 11's hotspot, and a guest device that will join via task 12.

1. **Host:** complete §H steps 1–2 so a `LocalOnlyHotspot` is up with visible `SSID: AndroidShare_xxxx` + `Pass: xxxxxxxx`.
2. **Guest:** launch the sample, tap **Start**, scroll to the **"Join hotspot (WifiNetworkSpecifier)"** Card directly below the **Hotspot host** Card.
3. **Guest:** type the SSID + passphrase from step 1 into the text fields. Tap **Join hotspot**. Grant `NEARBY_WIFI_DEVICES` (or `ACCESS_FINE_LOCATION` on API ≤ 32) if prompted.
4. **OS prompt:** Android shows its own "Use device's Wi-Fi to connect to '<SSID>'?" sheet. Tap **Connect**.
5. Within ~3 seconds the guest's Card flips to `Joined.` + the AP-subnet IP(s) (typically `192.168.43.x`). Logcat: `join Joined: state=ConnectedToWifi`.
6. Both phones' main rooms should now find each other via mDNS over the hotspot subnet — discovered-peers list populates, auto-mesh opens a session, broadcast/targeted send work the same as on home Wi-Fi.
7. **Guest:** tap **Clear status** to remove the joined-state Card text (does not release the join — `kit.stop()` releases it).
8. **Tear down**: guest taps **Stop**. The kit's `internalJob.cancel()` cascades through `ProvisioningContext.parentJob` and the manager's `close()` runs, which calls `connectivity.bindProcessToNetwork(null)` and `unregisterNetworkCallback`. The OS drops the join. Host's Card shows the guest disappear from its mesh.

**OEM quirks already handled:**
- Huawei / MIUI / older Samsung: same `Location mode is not enabled` SecurityException → mapped to `PermissionMissingForProvisioning([Location])`, and the JoinHotspotCard renders the same "Open Location settings" branch as the Hotspot card.
- MIUI / HyperOS backgrounding: the kit's manager subscribes to `JoinHandle.released`; system-released joins fire `NetworkProvisioningEvent.Failed(JoinFailed("system released …"))` and the Card returns to its idle state.

**Pass criteria:** Guest joins within ~5 seconds of OS approval; logcat shows `join Joined`; the guest's outgoing socket traffic routes through the joined network (auto-mesh confirms it by reaching the host). Tapping Stop on the guest cleanly releases the join.

**Common failure reasons:**
- `Failed: PermissionMissingForProvisioning — Missing permissions: [NearbyWifiDevices]` — user denied the perm. Re-tap.
- `Failed: PermissionMissingForProvisioning — Missing permissions: [Location]` — device-wide Location toggle is OFF. Card offers "Open Location settings".
- `Failed: JoinFailed — network unavailable — user declined, SSID not found, or wrong passphrase` — the OS callback fired `onUnavailable`. Common causes: user tapped Cancel on the prompt; SSID typo; passphrase typo; host phone moved out of range; host phone toggled the hotspot off.
- `Failed: JoinFailed — join released: ...` — the OS released a successful join. Battery saver (MIUI), user toggled Wi-Fi off, host AP went away. Tap Retry.
- `Failed: JoinFailed — a join is already in progress` — the manager allows only one active join per kit lifetime. Tap Stop and Start again to reset.

**Architectural note (visible from app code):** while the join is active, **all** the guest app's network traffic routes through the joined network. The local-only AP has no internet, so HTTP calls to anywhere except the host phone will fail until `kit.stop()` releases the binding. This is the v0.2.1 design choice (Option A — `bindProcessToNetwork`); per-socket binding (Option C) is a v0.3 candidate if any consumer needs internet-while-joined.

---

## J. Cross-device file transfer (v0.2.2)

Verifies the full `sendFile` / retained `pendingFileOffers` pipeline end-to-end: pick a file on the sender, watch progress + state on both sides, confirm the bytes on disk match. Three sub-recipes — pick whichever pair of platforms you have handy.

The pipeline streams the file in `chunkSizeBytes` (default 64 KiB) frames through the same TCP socket as messages and PING/PONG; nothing is buffered in memory. Sender state walks `Offered → Accepted → Sending(progress) → Completed`. Receiver walks the same states.

### J.1 — JVM CLI ↔ JVM CLI (smallest setup)

1. **Both:** `./gradlew :p2p-sample-desktop:installDist`, then launch two instances in two terminals (`Alice`, `Bob`). Auto-mesh forms within ~5 seconds.
2. **Bob (sender):** `> sendfile alice C:\path\to\large.zip` (or `/path/...` on macOS/Linux). The shell quotes paths with spaces (`> sendfile alice "C:\Users\me\Downloads\big file.zip"`).
3. **Bob:** sees `[file → Alice large.zip] Offered`, then `Accepted`, then `Sending(0.05)` … `Sending(1.0)`, then `Completed`.
4. **Alice:** sees `[file ← Bob] offered large.zip (10485760B) → C:\Users\me\.p2pkit\incoming\Bob\large.zip`, then state transitions, finally `Completed`.
5. **Verify:** open the saved file under Alice's `<user.home>/.p2pkit/incoming/Bob/`. Optional sanity: `Get-FileHash` / `sha256sum` should match the source.

**Pass criteria:** both sides reach `Completed`; the destination file is byte-identical to the source; the rest of the room (messages, peer discovery) keeps working during the transfer.

### J.2 — Android ↔ JVM CLI

1. **JVM CLI (Alice):** launch as above on a desktop on the same Wi-Fi.
2. **Android (Bob):** install + launch the sample app, tap **Start**. Wait for Alice to appear in **Discovered peers**, then auto-mesh connects.
3. **Android → JVM:** tap the **⋮** on Alice's chip in the Room row → **Send file…** → pick any file from the system picker (Downloads, Drive, Photos). The Android `sendFile(Context, Uri)` extension reads name/size/mime from `ContentResolver`.
4. **Android:** a new card appears in **File transfers** showing the file name, peer (Alice), state (`offered → accepted → sending 0% → … 100%`), and bytes counter. Cancel button is available while active.
5. **JVM (Alice):** auto-accepts; the destination prints in the CLI as `[file ← Bob] offered …`. State transitions echo as `[file ← Bob <name>] Sending(0.5)` etc. Final line: `Completed`.
6. **JVM → Android:** in Alice's CLI: `> sendfile bob /path/to/file.bin`. Android auto-accepts to `getExternalFilesDir(null)/p2pkit-incoming/Alice/<name>` and renders the inbound row with the destination path.

**Pass criteria:** both directions complete; the Android sample card shows real-time progress without UI freeze; the saved file on Android can be opened via `adb pull` or a file-manager app from the printed destination path.

### J.3 — Android ↔ Android (real-device end-to-end)

1. **Both phones:** install + launch the sample on the same Wi-Fi (or via §H/§I hotspot if no shared LAN). Tap **Start** on both. Auto-mesh connects them.
2. **Sender:** tap **⋮** on the peer chip → **Send file…** → pick a file (a small image or a multi-MB document both work; the cap is 2 GiB by default).
3. **Sender's File transfers card** shows the outgoing row with progress %.
4. **Receiver:** within the same screen, a new row appears with the `↓` arrow, peer name, and a destination path under `Android/data/dev.p2pkit.sample.android/files/p2pkit-incoming/<sender>/<name>` — this is the app-scoped external-files dir, so no runtime storage permission is needed even on API 33+.
5. **Both sides:** state goes to `Completed`. Verify with a file manager: navigate to the printed path on the receiver and open the file.
6. **Cancel test:** start a second, larger transfer (e.g., a video). While the row shows `sending N%`, tap **Cancel** on the sender. Both sides should flip to `Cancelled(user cancelled)` within ~1 second; the partial destination file is left behind on disk (verify it's shorter than the original).
7. **Reject test:** lower the receiver's `maxFileSizeBytes` to 1 MiB via the in-code `fileTransfer { … }` block (or just test with a file > 2 GiB on default settings). The sender's row goes straight to `Rejected — sizeBytes ... exceeds maxFileSizeBytes ...` without the offer ever surfacing to the receiver's UI.

**Pass criteria:** transfer completes in proportional time (a 50 MiB file over Wi-Fi takes ~10 seconds); cancel propagates both ways promptly; the receiver's app-scoped storage path is readable without manifest permission changes.

**Common failure reasons:**
- `Failed — kotlinx.io.IOException: Source exhausted before ... bytes` — the source file shrunk or was moved between the metadata read and the streaming read. Pick again.
- `Cancelled — offer not accepted within 30000ms` — receiver app was backgrounded or paused on the offer card too long. Default timeout is 30 s, raise with `fileTransfer { offerTimeoutMillis = ... }` if the test scenario expects user delay.
- Android sample card shows `Failed — Cannot determine size for content://...` — some Storage Access Framework providers (cloud-only documents, recent picker entries) don't expose `OpenableColumns.SIZE`. Workaround: pick the file from the device's local Files app instead, or download it locally first.

### Code-only verification (no device required)

Apart from the device recipes above, the file transfer pipeline is also exercised by automated tests on every build:
- `:p2p-core:allTests` includes **7 commonTest cases** in `FileTransferFlowTest` (happy path, reject, receiver-size cap, sender-side `PayloadTooLarge`, offer timeout, mid-stream cancel, parallel message+file send) plus **3 jvmTest cases** in `FileTransferJvmTest` (the JVM extension's `sendFile(File)` overload).
- `:p2p-transport-lan:jvmTest` includes `fileTransferRoundTripsOverTcpWithMatchingHash` — two real `P2pKit` instances over real mDNS + TCP transfer a deterministic 5 MiB temp file, with SHA-256 verified on the receiver. Completes in ~13 s.

---

## K. iOS Simulator ↔ JVM CLI cross-process LAN test (v0.3)

Verifies the iOS LAN transport against a real-network JVM peer using the standard `:p2p-sample-desktop` CLI. The Mac's loopback + the simulator's shared host network are enough — no real iPhone needed for the smoke test.

**Devices:** macOS host with Xcode + iOS Simulator runtime installed.

**Prereqs:** the in-process `:p2p-transport-lan:iosSimulatorArm64Test` (§K.1) remains the quickest smoke test for the iOS transport — it exercises everything `transports { lan() }` does without leaving Gradle. With the iOS sample app shipped in v0.4, the CLI ↔ Simulator pair (§K.2) is the real cross-process recipe.

### K.1 — In-process loopback (quickest smoke test)

```bash
./gradlew :p2p-transport-lan:iosSimulatorArm64Test
```

**Expected output:** all 20 `appleTest` methods green (four classes). The three loopback cases are the canonical smoke subset:
- `twoKitsDiscoverEachOtherAndExchangeText` — two kits with shared `appId`, mutual discovery, text message round-trip.
- `largeBinaryPayloadRoundTripsOverTcp` — 200 KB binary chunk through `NWConnection` framing.
- `fileTransferRoundTripsOverTcp` — 5 MiB deterministic file via `kotlinx-io` `Buffer`, `assertContentEquals` on the received bytes.

The rest are `IosBonjourTest` (TXT round-trips), `IosLanLifecycleTest` (start/stop/rebind), and the `@Ignore`-gated `IosLanDiagnosticTest`.

If the test stalls on discovery, check the simulator runtime is actually installed (`xcrun simctl list devices available`) and that `mDNSResponder` is reachable inside it (it always is on stock simulators; failures here are usually misconfiguration, not Bonjour).

### K.2 — iOS Simulator ↔ JVM CLI

Launch the iOS sample in the Simulator: `cd iosApp && xcodegen generate` if Xcode complains the project is stale, `open p2pkit-sample.xcodeproj`, pick an iPhone Simulator destination, ⌘R (the pre-build script refreshes the XCFramework via `sh ./gradlew`). In the app, enter a device name and tap **Start** — the SwiftUI sample registers itself for `_p2pkit._tcp` and runs a long-lived kit. From a Terminal on the same Mac:

```bash
./gradlew :p2p-sample-desktop:installDist
./p2p-sample-desktop/build/install/p2p-sample-desktop/bin/p2p-sample-desktop Mac
```

With the iOS sample running in the simulator and the JVM CLI in a terminal:
- The CLI's `peers` command should list the simulator within ~5 s.
- `connect <iosPeerId>` opens a session through `nw_connection_t` on the iOS side and `Socket` on the JVM side.
- `send hello iphone` round-trips through the same `_p2pkit._tcp` Bonjour service as Android peers use.

The wire format is additionally pinned by §K.1 plus the §A Android ↔ JVM recipe — an iOS peer is wire-indistinguishable from an Android peer because both use the same protocol version (`pv=1`), same TXT keys, same service type.

**Common failure reasons:**
- `iosSimulatorArm64Test` task missing: install the iOS simulator runtime through Xcode → Settings → Platforms.
- Compile-time crash mentioning `Kotlin_Interop_refFromObjC` on a void block: a new `nw_*` block macro slipped into the iOS code path. Wrap it in a static-inline helper in `src/nativeInterop/cinterop/p2pkit_nw.h` so the void-block global never round-trips through Kotlin/Native (rationale documented in that file's header comment).
- Discovery never resolves: Bonjour on the simulator can be flaky on some macOS versions when the host firewall is strict. `sudo lsof -nP -i UDP:5353` should show `mDNSResponder` listening; `dns-sd -B _p2pkit._tcp local.` should list every peer.

### K.3 — Simulator install provenance (2026-07, IOSB-3 / P1-30 / P1-31)

`./gradlew :iosApp:runIosSimulator` (which drives `scripts/run-ios-app.sh`) now builds into a **repo-local DerivedData** at `iosApp/build/DerivedData` and installs the bundle from the fixed path `iosApp/build/DerivedData/Build/Products/Debug-iphonesimulator/p2pkit-sample.app` — never from a `find` over the global `~/Library/Developer/Xcode/DerivedData`, which with multiple checkouts/worktrees could silently install a stale bundle from a different tree. The script also self-checks two provenance gates and fails loudly on either:

- **P1-30 (built-bundle plist keys):** after `xcodebuild`, the built `.app`'s Info.plist must contain `NSLocalNetworkUsageDescription` and `NSBonjourServices` with `_p2pkit._tcp` (the keys iOS 14+ requires for Bonjour; missing keys = the documented zero-discovery failure mode). The keys must live in `iosApp/project.yml`'s `info.properties` block — xcodegen regenerates the project, so keys added anywhere else are silently dropped.
- **P1-31 (installed bundle is THIS build):** after `simctl install`, the script resolves the installed container via `xcrun simctl get_app_container <UDID> dev.p2pkit.sample` and requires the installed executable's SHA-256 to match the one just built under this checkout's `iosApp/build/DerivedData`.

**Manual verification recipe (P1-31), for any smoke-matrix run whose result you intend to record:**

```bash
./gradlew :iosApp:runIosSimulator          # expect "[ios-run] Provenance OK: ..." in the output
xcrun simctl get_app_container booted dev.p2pkit.sample
shasum -a 256 "$(xcrun simctl get_app_container booted dev.p2pkit.sample)/p2pkit-sample" \
       iosApp/build/DerivedData/Build/Products/Debug-iphonesimulator/p2pkit-sample.app/p2pkit-sample
```

The two SHA-256 lines must be identical, and the second path must sit under **the checkout you invoked the build from**. If they differ, the simulator is running some other build — erase and rerun (`xcrun simctl uninstall booted dev.p2pkit.sample`, then `runIosSimulator` again) before recording any result. This complements the pre-build XCFramework stamp gate in `iosApp/scripts/check-xcframework.sh` (which pins the *framework* sources to HEAD); K.3 pins the *app bundle* actually installed on the simulator.

---

## 2. Windows Defender Firewall

On Windows, the **first** time you run the desktop sample, Defender prompts to allow inbound TCP for the Java runtime.

- **Allow on Private networks.**
- If you accidentally clicked "Block":
  ```powershell
  Get-NetFirewallRule -DisplayName "*OpenJDK*","*Java*","*p2pkit*" | Remove-NetFirewallRule
  ```
  Re-run the sample to get the prompt again.

mDNS (UDP 5353) is normally permitted on private profiles by default.

---

## 3. Wi-Fi / mDNS multicast — common failure mode

P2pKit uses **mDNS** (UDP multicast on 224.0.0.251 : 5353) for peer discovery. Many networks block multicast:

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

## 4. Release checklist (v0.6)

Run through this before tagging.

- [ ] `./gradlew :p2p-core:allTests :p2p-transport-lan:jvmTest :p2p-transport-lan:iosSimulatorArm64Test :p2p-network-provisioning-desktop:test :p2p-network-provisioning-android:testAndroidHostTest :p2p-sample-android:assembleDebug :p2p-sample-desktop:installDist :p2p-sample-desktop-ui:assemble` → all green, zero failures. Current sizes for orientation: `:p2p-core` has 134 unique test methods (`allTests` multiplies commonTest across targets, so the reported total is higher), `:p2p-transport-lan:jvmTest` runs 17 (14 `HostSelectorTest` + the 3 loopback tests, including the 5 MiB SHA-256 file-transfer round-trip), `:p2p-transport-lan:iosSimulatorArm64Test` runs 20 (includes text + 200 KB binary + 5 MiB file via real Bonjour and NWConnection).
- [ ] **§A** Android ↔ JVM walkthrough passes nine-of-nine.
- [ ] **§B** Three-device room broadcast verified at N ≥ 3 (4+ ideally).
- [ ] **§C** ReconnectPolicy roundtrip verified: Connected → Reconnecting → Connected, and exhaustion → Failed.
- [ ] **§D** PeerId persistence verified on both JVM and Android.
- [ ] **§E** MulticastLock dumpsys diagnostic shows `p2pkit-mdns` during operation.
- [ ] **§F** iOS LAN smoke test (`./gradlew :p2p-transport-lan:iosSimulatorArm64Test`) passes — all 20 cases green (the three loopback tests are the smoke subset).
- [ ] **§G** JVM manual-IP fallback verified (two CLIs, `manual host:port`).
- [ ] **§H** Android `LocalOnlyHotspot` host verified on two phones — *device verification pending; tracks the same backlog row as §I*.
- [ ] **§I** Android Wi-Fi join via `WifiNetworkSpecifier` verified on two phones — *device verification pending*.
- [ ] **§J** Cross-device file transfer verified (any one of J.1 / J.2 / J.3) — *device verification optional; the automated 5 MiB SHA-256 LAN loopback already covers the protocol layer*.
- [ ] **§K** In-process iOS Simulator loopback green (§K.1). Cross-process Simulator ↔ JVM CLI (§K.2) verified with the iosApp sample.
- [ ] Known Limitations in `README.md` reviewed; nothing new has slipped in.
- [ ] No leftover TODO / FIXME / debug `println` in shipping code (sample `println` is fine).
- [ ] Compose Desktop UI sample (`:p2p-sample-desktop-ui`) launches at feature parity with the Android sample — status header shows appId/peerId/state, Advertise/Discover switches work, room chips show state, broadcast and targeted send work, **Send file…** menu picks via AWT and surfaces the live progress row.

When all boxes tick, **tag the next `-internal` milestone** and share this guide with the testers.
