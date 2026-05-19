# P2pKit iOS sample app — build + device-test guide

A minimal SwiftUI sample for validating v0.3.0-dev on a physical iPhone. Everything below is **ready to copy into a new Xcode project** — no part of this directory is wired into the Gradle build for the SDK itself.

The required `linkDebugFrameworkIosSimulatorArm64` / `linkReleaseFrameworkIosArm64` tasks are already declared on `:p2p-transport-lan`, so the framework artifact is produced by the existing build.

---

## 1. Build the framework

For Simulator (Apple Silicon Mac):

```bash
./gradlew :p2p-transport-lan:linkDebugFrameworkIosSimulatorArm64
# Output: p2p-transport-lan/build/bin/iosSimulatorArm64/debugFramework/P2pKitShared.framework
```

For a real iPhone (arm64 device):

```bash
./gradlew :p2p-transport-lan:linkReleaseFrameworkIosArm64
# Output: p2p-transport-lan/build/bin/iosArm64/releaseFramework/P2pKitShared.framework
```

For a universal XCFramework that handles both (recommended for distribution):

```bash
# Not currently declared as a Gradle task — uncomment the XCFramework
# section in p2p-transport-lan/build.gradle.kts when you need it.
```

The framework exports the full `:p2p-core` API (P2pKit, AppId, Peer, P2pMessage, FileTransferState, …) alongside the LAN transport's `lan()` extension. From Swift you'll see them under the `P2pKitShared` module.

---

## 2. Create the Xcode project

The fastest path uses [XcodeGen](https://github.com/yonaskolb/XcodeGen) (`brew install xcodegen`):

```bash
mkdir -p iosApp && cd iosApp
cp ../docs/ios-sample-app/project.yml .
cp ../docs/ios-sample-app/Info.plist .
cp ../docs/ios-sample-app/*.swift .
# Drop the framework next to project.yml:
cp -R ../p2p-transport-lan/build/bin/iosSimulatorArm64/debugFramework/P2pKitShared.framework .
xcodegen generate
open p2pkit-sample.xcodeproj
```

If you don't have XcodeGen, the manual recipe is:

1. **File → New → Project → iOS App** (SwiftUI, Swift, no Core Data, no tests).
2. Drop `P2pKitShared.framework` into the project navigator. Choose "Copy items if needed" and add it to the app target's **Frameworks, Libraries, and Embedded Content** as **Embed & Sign**.
3. Replace the generated `ContentView.swift`, `<projectName>App.swift`, and `Info.plist` with the templates in this directory.
4. In **Signing & Capabilities**, set a Team. The local-network privacy entries below are honored automatically once they're in Info.plist.

---

## 3. Required Info.plist entries

The relevant keys are already in `Info.plist` in this directory. The two that gate the iOS test plan:

```xml
<key>NSLocalNetworkUsageDescription</key>
<string>P2pKit needs local network access to discover nearby devices over Bonjour and exchange messages over TCP.</string>

<key>NSBonjourServices</key>
<array>
    <string>_p2pkit._tcp</string>
</array>
```

Without `NSLocalNetworkUsageDescription`, iOS 14+ silently blocks `nw_listener_start` / `nw_browser_start` (no permission prompt, no error — just zero discoveries). Without `NSBonjourServices`, iOS 14+ similarly blocks the browse direction. Both are **required**.

---

## 4. Run on a real iPhone — test checklist

Connect an iPhone via USB or via Xcode's wireless device pairing. In Xcode → product menu → Run, select the iPhone as the destination.

### T1.1 — Local network permission prompt
**Steps**
1. Launch the app on the iPhone for the first time after install.
2. Tap "Start" in the sample.
**Expected:** iOS shows a system dialog: "p2pkit-sample would like to find and connect to devices on your local network." Tap **Allow**.
**Pass criteria:** Prompt appears exactly once on first launch; subsequent launches use the saved decision. Logs show the kit starting cleanly.
**Fail if:** No prompt appears AND the app never discovers any peer — that indicates the Info.plist entries are missing or the framework was not signed correctly.

### T1.2 — Discover a JVM peer
**Steps**
1. On the macOS host, run `./p2p-sample-desktop/build/install/p2p-sample-desktop/bin/p2p-sample-desktop JvmAlice` (default `appId = p2pkit-desktop-sample`). Same SSID for both devices.
2. On the iPhone, ensure the sample's `appId` field is set to `p2pkit-desktop-sample` and tap **Start**.
**Expected:** Within ~5 s the iPhone's peer list shows `JvmAlice`; the JVM CLI's `[peers]` line shows the iPhone.
**Pass criteria:** Both sides see each other. The iPhone's `P2pKitShared.LocalConstants.SERVICE_TYPE_BONJOUR` advertise (`_p2pkit._tcp`) is matched by JmDNS on the JVM and vice versa.
**Fail if:** iPhone shows 0 peers AND `dns-sd -B _p2pkit._tcp local.` on the host shows no iPhone-advertised service — the most common cause is Wi-Fi multicast blocking (corporate / guest / hotel SSID).

### T1.3 — Open a session iPhone → JVM
**Steps**
1. With both peers visible, tap `JvmAlice` in the iPhone's peer list to call `kit.connect(peer)`.
**Expected:** Session reaches `Connected` state within 2 s; JVM CLI prints `[incoming] from <iPhoneName>` and `[state] <iPhoneName> → Connected`.
**Pass criteria:** Both sides land on `Connected`; neither side observes `Connecting` for longer than 10 s (matching `CONNECT_TIMEOUT_MILLIS`).

### T1.4 — Open a session JVM → iPhone
**Steps**
1. From the JVM CLI: `connect <iPhoneIdPrefix>` (e.g., `connect 612c`).
**Expected:** iPhone's "incoming sessions" view shows the new session; reaches `Connected`.
**Pass criteria:** Same as T1.3 in the reverse direction.

### T1.5 — Bidirectional text message
**Steps**
1. From the iPhone: tap "Send text" with body `hi-from-iphone`.
2. From the JVM CLI: `send hi-from-jvm`.
**Expected:** Each side prints the other's message verbatim.
**Pass criteria:** Both messages arrive byte-identical, ordering preserved, within 1 s.

### T1.6 — 200 KB binary round-trip
**Steps**
1. iPhone send action with the "200KB binary" preset.
2. JVM CLI receives, computes SHA-256.
3. Reverse direction.
**Pass criteria:** Both SHA-256 values match the source. No partial / truncated message.

### T1.7 — 5 MB file round-trip
**Steps**
1. iPhone: pick a 5 MB photo / document; send via `sendFile`.
2. JVM CLI saves to `~/.p2pkit/incoming/<peer>/`. Compute `shasum -a 256` against the original on the iPhone (visible via the share-sheet copy).
3. Reverse direction.
**Pass criteria:** Both saved files are byte-identical. Sender's `FileTransferState` walks `Offered → Accepted → Sending(0..1) → Completed`; receiver mirrors.

### T1.8 — Stop / restart cycle
**Steps**
1. Tap **Stop** in the sample.
2. Confirm JVM CLI sees the iPhone disappear from `[peers]`.
3. Tap **Start** again.
**Pass criteria:** JVM CLI sees the iPhone reappear with the **same** `localPeerId` (PeerId persistence via `NSUserDefaults`). No leaked Bonjour service — `dns-sd -B _p2pkit._tcp local.` should show exactly one entry per peer at all times.

### T1.9 — Background / foreground
**Steps**
1. With a session active, swipe the app to background.
2. Wait 30 s.
3. Foreground the app.
**Expected (documented behavior):** iOS suspends background networking aggressively; the session may drop. On foreground, `NWBrowser` resumes within ~2 s and rediscovery + auto-mesh re-opens the session.
**Pass criteria:** The app does not crash on background-to-foreground. The session either survives or is observably re-established. *(Real-iPhone-only — the simulator does not background applications meaningfully.)*

### T1.10 — Wi-Fi off / on
**Steps**
1. With a session active, toggle Wi-Fi off in Settings.
2. After ~5 s, toggle Wi-Fi on.
**Expected:** Session transitions to `Closed` or `Reconnecting` (depending on `ReconnectPolicy`). On reconnect, the peer is rediscovered and a fresh session can be opened.
**Pass criteria:** No crash; no hung `Connecting`; the kit recovers without restart.

---

## 5. Failure modes worth knowing

| Symptom | Root cause |
|---|---|
| 0 peers, no permission prompt | Missing `NSLocalNetworkUsageDescription` or `NSBonjourServices` |
| 0 peers AND prompt was denied | Settings → Privacy → Local Network → enable for the app |
| Discovery works but connect hangs | Same Wi-Fi but different subnet, OR firewall blocking inbound TCP. Confirm with `dns-sd -L "<instance>" _p2pkit._tcp local.` from a Mac on the same SSID |
| App crashes on first send with `KotlinNullPointerException` | `P2pKitShared` was built for the wrong arch (simulator framework on device, or vice versa). Rebuild with the matching `linkXXXFrameworkIos*` task |
| `nw_listener` errors in console at startup | Bonjour service type mismatch (typo in `_p2pkit._tcp`) — check spelling exactly |
