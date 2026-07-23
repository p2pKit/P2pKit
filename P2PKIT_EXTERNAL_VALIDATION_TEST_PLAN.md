# P2pKit external validation test plan

This document is the execution plan for the validations that cannot be
closed by the repository's deterministic JVM, Android-host, Apple-simulator,
ABI, Dokka, publication-consumer, Swift, or release-XCFramework gates.

All tests in this document must be run against one immutable repository
revision. Record the exact `git rev-parse HEAD` value in the result template;
do not replace it with a branch name. A passing build or a code review is not
external evidence. Do not change a blocked tracker row to `Verified` until
the required evidence below has been collected and reviewed.

At the time this document was prepared, the remediation branch and `main`
contained the same pushed history. The final test run must still record the
actual SHA used by the tester.

## 1. Shared execution contract

### 1.1 Required tools and accounts

The baseline workstation must have:

* macOS 14 or newer for Apple builds, Xcode 15.4 or newer, `xcodebuild`,
  `xcrun`, `simctl`, `dns-sd`, `log`, `Console.app`, and XcodeGen.
* JDK 17, Gradle wrapper from this repository, Kotlin/Native toolchains
  resolved by Gradle, and Git.
* Android SDK Platform 37, build-tools, platform-tools, an API-26 through
  API-37 emulator, and at least one physical Android device. Install
  `adb`, `apkanalyzer`, and Android Studio Logcat or `adb logcat`.
* Two independent network interfaces where possible: Wi-Fi and Ethernet or
  a USB Ethernet adapter. The hostile-network tests additionally need a
  managed access point/router, a second isolated SSID/VLAN, and a Linux or
  macOS machine capable of `pf`, `ipfw`, `iptables`, `nft`, or an equivalent
  packet filter.
* A GitHub account with write access to `https://github.com/p2pKit/P2pKit.git`.
  Publication tests additionally need the owner-approved Central/Portal
  namespace, signing identity, test key, and short-lived CI credentials.
  Never put credentials in the repository, shell history, screenshots, or
  captured logs.

Use a private test SSID. Do not run hostile packet injection against a
production, public, or third-party network.

### 1.2 Immutable checkout and evidence directory

```sh
export P2PKIT_ROOT=/Users/abdelrahman/Projects/P2pKit
cd "$P2PKIT_ROOT"
git fetch origin
git status --short
git rev-parse HEAD
export P2PKIT_SHA="$(git rev-parse HEAD)"
export EVIDENCE="$P2PKIT_ROOT/.external-validation/$P2PKIT_SHA/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$EVIDENCE"/{logs,screen,video,pcap,files,metadata}
```

The protected user-owned review files must not be copied into evidence,
staged, or modified. Hash every generated file:

```sh
find "$EVIDENCE" -type f -print0 | sort -z | xargs -0 shasum -a 256 > "$EVIDENCE/sha256sums.txt"
```

Record UTC timestamps, hostnames, OS versions, device model/build, app build
number, SDK `BuildInfo.describe()` value, network SSID/BSSID (or an opaque
test-network identifier), and the exact commands used.

### 1.3 Build and installation baseline

From the pinned checkout:

```sh
./gradlew :p2p-sample-android:assembleDebug \
  :p2p-sample-android:testDebugUnitTest \
  :p2p-sample-desktop:test \
  :p2p-sample-desktop-ui:test
./gradlew :p2p-transport-lan:assembleP2pKitSharedReleaseXCFramework
```

Install Android:

```sh
adb -s "$ANDROID_SERIAL" uninstall dev.p2pkit.sample.android || true
adb -s "$ANDROID_SERIAL" install \
  p2p-sample-android/build/outputs/apk/debug/p2p-sample-android-debug.apk
adb -s "$ANDROID_SERIAL" shell am force-stop dev.p2pkit.sample.android
adb -s "$ANDROID_SERIAL" shell monkey -p dev.p2pkit.sample.android 1
```

Generate and build the iOS sample:

```sh
(cd iosApp && xcodegen generate)
xcodebuild -project iosApp/p2pkit-sample.xcodeproj \
  -scheme p2pkit-sample -configuration Debug \
  -destination "platform=iOS,id=$IOS_UDID" build
```

Install/run the iOS app with Xcode or:

```sh
xcrun devicectl device install app --device "$IOS_UDID" \
  iosApp/build/Build/Products/Debug-iphoneos/p2pkit-sample.app
xcrun devicectl device process launch --device "$IOS_UDID" dev.p2pkit.sample
```

The iOS sample's test-only file menu provides deterministic `200 KiB`,
`5 MiB`, and `49 MiB` binary snapshots. Android and Desktop select arbitrary
files through the system picker; create fixtures with:

```sh
dd if=/dev/zero of="$EVIDENCE/files/zero-200k.bin" bs=1024 count=200
dd if=/dev/urandom of="$EVIDENCE/files/random-5m.bin" bs=1m count=5
python3 - <<'PY'
import os
from pathlib import Path
p = Path(os.environ["EVIDENCE"]) / "files" / "boundary-49m.bin"
p.write_bytes(bytes((i * 31 + 7) & 0xff for i in range(49 * 1024 * 1024)))
PY
shasum -a 256 "$EVIDENCE"/files/*
```

### 1.4 Evidence and result template

Every test section below must end with a completed record:

```text
Tracker ID / test:
Date (UTC):
Tester:
Repository SHA:
Host OS/build:
Device model/OS/build and serial/UDID:
App build / BuildInfo.describe():
Network equipment, SSID/VLAN, and topology:
Commands executed:
UI actions executed:
Result: PASS / FAIL / BLOCKED
Evidence paths (logs/screens/video/pcap/files/hashes):
Observed output and timestamps:
Notes, deviations, and follow-up:
```

PASS means every pass criterion is met and every required artifact exists.
FAIL means any fail criterion occurs, even if the final transfer later
recovers. BLOCKED means the required hardware, credential, or independent
reviewer was unavailable; it is not a pass.

## 2. Android instrumentation and physical-device tests

### PROV-A12 / PS-T01 — real provisioning callback, permission, and cancellation matrix

Purpose and risk: validate LocalOnlyHotspot and WifiNetworkSpecifier callback
ordering, cancellation ownership, process binding/unbinding, OEM return
values, merged manifest permissions, and lifecycle UI behavior that JVM fakes
cannot prove.

Required setup: one API-26, one API-30/32, and one API-33/37 Android device
where possible; at least one physical device must support LocalOnlyHotspot.
Use a USB cable for each device, an Android SDK host, a private Wi-Fi AP, and
the Android sample. No account or secret is needed.

Preparation and commands:

```sh
./gradlew :p2p-sample-android:connectedDebugAndroidTest
adb -s "$ANDROID_SERIAL" logcat -c
adb -s "$ANDROID_SERIAL" shell dumpsys package dev.p2pkit.sample.android \
  > "$EVIDENCE/metadata/package-dumpsys.txt"
adb -s "$ANDROID_SERIAL" shell pm list permissions -g -d \
  > "$EVIDENCE/metadata/permissions.txt"
adb -s "$ANDROID_SERIAL" logcat -v threadtime \
  -s P2pKit P2pKitLAN P2pKitFrame AndroidRuntime '*:S' \
  > "$EVIDENCE/logs/prov-a12.log" &
export LOGCAT_PID=$!
```

UI/actions:

1. Launch the app, record the title-bar SDK build identity, and grant only the
   requested Nearby Wi-Fi/Location permissions.
2. Turn the system Location switch off, tap Start/Host hotspot, and verify the
   app reports the actionable permission/location state without claiming a
   started hotspot.
3. Turn Location on; tap Host hotspot; capture SSID, masked credential
   indicator, manual port, and the `Started` result.
4. Tap Stop hotspot while the callback is pending and repeat with a delayed
   callback. The UI must return to an idle/failed state and must not leave a
   live network or process binding.
5. Start a second manager instance where the device permits it, attempt Join
   while the first manager is closing, and repeat with rapid Host/Stop/Retry
   taps.
6. On API-33+, revoke `NEARBY_WIFI_DEVICES` in Settings and repeat. On
   API-32 and below repeat with Location permission and system switch changes.
7. Capture `dumpsys connectivity`, `dumpsys wifi`, and package permission state
   after every terminal outcome.

Pass criteria: every callback sequence has one terminal result; late callbacks
close their reservation; `bindProcessToNetwork(false)`/unbind is visible where
the platform exposes it; no stale hotspot remains after Stop; merged manifest
contains the declared permissions; error text identifies the missing
permission or Location switch; no crash, duplicate owner, or leaked process
binding is observed.

Fail criteria: a failed start leaves a live reservation, a cancelled join
rebinds, two managers both own process binding, callbacks arrive after close
without cleanup, or the UI reports success while `dumpsys` shows no network.

Collect: screen recording of each callback race, logcat, package and network
dumps, permission screenshots, device build fingerprint, and timestamps.

Cleanup: stop hotspot, call Stop in the app, revoke temporary permissions if
the device is shared, kill the app, and disconnect USB. Do not retain SSIDs or
passwords in public evidence.

### PROV-A12 / PS-T02 — two-manager process-binding ownership

Purpose and risk: prove the process-wide binding arbiter against real Android
ConnectivityManager state rather than host fakes.

Required setup: one Android device that supports a local-only hotspot and a
second Android device or AP to keep ordinary Wi-Fi available. Use two
installed sample processes if the OEM permits work profiles; otherwise use the
sample plus a small owner-approved instrumentation activity in the same APK.

Actions:

1. Capture baseline `dumpsys connectivity` and the active network transport.
2. Start manager A and join/host a local network; capture its network handle.
3. Start manager B and request a second join while A is active.
4. Close A, verify B does not inherit A's token, then close B.
5. Repeat in reverse order and during a queued `onAvailable` callback.

Pass: only the current token owner can bind; closing one manager never unbinds
the other; all callbacks after close are ignored/closed; the ordinary network
is restored after both managers close. Fail: an unrelated manager loses
connectivity or a late callback reclaims a released token.

Collect the same logs/dumps as PS-T01 plus a sequence diagram with callback
timestamps. Cleanup all local networks and reboot the device if OEM state does
not return to baseline.

### LAN-T01 / PT-T20 — Android LAN callback, multicast, selected-network, IPv6, and file-provider matrix

Purpose and risk: validate real NSD/JmDNS registration, multicast lock,
selected-network address projection, IPv4/IPv6 candidates, abrupt peer loss,
log sanitization, and content-provider file metadata.

Required setup: two Android devices on the same AP, one API-26/32 and one
API-33/37 if possible; USB cables; router with IPv4 and IPv6 enabled; files
`zero-200k.bin`, `random-5m.bin`, and a provider-backed document (Files/Drive
provider if approved). Capture packet traces only on the private AP.

Actions:

1. On both devices start the sample, enable Advertise, Discover, and Auto-mesh,
   and record peer IDs, app IDs, protocol/security state, network-path chip,
   and local port.
2. Toggle Wi-Fi off/on on one device; then move it between the AP's 2.4 GHz
   and 5 GHz radios without changing SSID. Record Lost/Found, Reconnecting,
   port/address changes, and final Connected state.
3. Disable multicast or change AP client isolation; verify the UI reports no
   peer rather than a false connection.
4. Send each fixture through the Android system picker and accept it on the
   receiver. Compare sender and receiver SHA-256 lines and the saved file.
5. Use a content-provider URI, revoke its read grant before the send starts,
   and verify a typed failure without a crash.
6. Send a filename containing control characters and path separators from an
   owner-controlled Desktop peer. Verify the Android path remains inside the
   sample inbox and logcat strips controls.
7. Kill the peer process with `adb shell am force-stop` and repeat with an
   abrupt AP disconnect.

Commands:

```sh
adb -s "$ANDROID_A" logcat -v threadtime -s P2pKit P2pKitLAN P2pKitFrame '*:S' \
  > "$EVIDENCE/logs/lan-t01-a.log" &
adb -s "$ANDROID_B" logcat -v threadtime -s P2pKit P2pKitLAN P2pKitFrame '*:S' \
  > "$EVIDENCE/logs/lan-t01-b.log" &
adb -s "$ANDROID_B" shell run-as dev.p2pkit.sample.android \
  find files -type f -maxdepth 4 -print > "$EVIDENCE/metadata/android-files.txt"
```

Pass: real callbacks show registration/unregistration and multicast lifecycle;
selected-network addresses match `LinkProperties`; valid alternate candidates
recover; no stale peer survives loss; every completed file has equal hashes and
no partial file remains after cancellation; logs include timestamps, peer IDs,
frame/transfer IDs, and sanitized reasons. Fail: false Connected/Found,
stale listener, wrong interface, leaked multicast, mismatched digest, or
provider metadata crash.

Cleanup: Stop both kits, remove app data only after copying evidence, restore
AP isolation/multicast settings, and release packet captures.

### PS-T04 — Android sample consent, storage, lifecycle, backup, and UI instrumentation

Purpose and risk: exercise the actual Compose controls and storage policy:
explicit offer consent, accept/reject/expiry, low storage, collision,
cancellation, partial cleanup, rapid toggles, failed startup, rotation,
process death, and Android 12+ backup/device-transfer exclusion.

Required setup: one API-26+ physical device and one second sender; USB,
`adb`, screen recording, and at least 100 MiB free space. Use a test-only
sender that can offer repeated files and a receiver with a controlled low-space
fixture or owner-approved storage shim.

Actions:

1. Start the receiver and rotate the device while the picker and while an
   offer is visible. Verify the target peer, offer, and logs remain coherent.
2. Offer the 200 KiB, 5 MiB, and 49 MiB files. Verify no destination is
   created before Accept; Reject sends a rejection; Accept shows progress,
   destination, terminal state, and SHA-256.
3. Offer a file over 50 MiB, an empty file, duplicate names concurrently, and
   repeated identical offers. Verify quota/rejection/collision behavior.
4. Cancel during Offered, Accepted, and Sending; then force-stop the receiver.
   Verify only complete committed files remain and `.p2pkit-*.part` files are
   removed on the next run.
5. Rapidly toggle Advertise/Discover 50 times, tap Stop/Start repeatedly, and
   inject a failed start by revoking permissions between taps.
6. Capture `adb shell bmgr backupnow`, package data-extraction rules, and
   `adb shell dumpsys package` to confirm credentials/device-protected data
   are excluded.

Pass: every UI action has one deterministic result, no crash/ANR, no partial
file survives a non-completed transfer, logs and screen state agree, and
backup/device-transfer rules match the manifest. Fail: auto-accept, lost
consent, stale progress, path escape, orphaned files/resources, or a Start
button wedged after failure.

Collect: screen recording, UI hierarchy (`uiautomator dump`), logcat,
filesystem listings, SHA-256 list, backup-rule output, and device metadata.
Reset app data and restore the device's original backup setting after the run.

## 3. Apple physical and runtime tests

### LAN-T07 — physical Apple LAN, AWDL, path rotation, browser/listener recovery

Purpose and risk: validate Network.framework behavior that a simulator cannot
prove: Local Network permission, AWDL/peer-to-peer, same-SSID interface
rotation, native TTL/abrupt departure, listener recreation, and exact port
release.

Required setup: two physical iPhones/iPads on the supported iOS deployment
target, one Mac with Xcode and USB cables, an AP with 2.4/5 GHz bands, and a
second Apple device or approved Android peer. Enable Developer Mode and trust
the Mac. No production credentials are needed.

Actions:

1. Build/install the exact pinned app. On first launch allow Local Network;
   repeat after denying it and verify the explicit Settings guidance.
2. Start both apps. Record BuildInfo, local peer IDs/ports, diagnostic log,
   browser `ready`, listener `ready`, and Connected/session transitions.
3. Toggle Wi-Fi off/on, move between AP bands without changing SSID, and
   briefly enable Personal Hotspot/AWDL where supported. Record interface and
   address fingerprints, port changes, Lost/Found, Reconnecting, and final
   recovery.
4. Kill the peer from Xcode/`devicectl`; verify the remaining peer removes it
   and does not retain ghost heartbeats. Restart and repeat 20 cycles.
5. Start/Stop while browser/listener readiness is pending and verify terminal
   cleanup and exact old-port release with `nc`/`lsof`.
6. Send each iOS preset and an Android/JVM fixture; accept/reject/cancel and
   compare SHA-256 output.

Commands:

```sh
log stream --level debug --style compact \
  --predicate 'process == "p2pkit-sample" OR eventMessage CONTAINS[c] "P2pKit"' \
  > "$EVIDENCE/logs/lan-t07.log" &
xcrun devicectl device info details --device "$IOS_UDID" \
  > "$EVIDENCE/metadata/ios-device.txt"
dns-sd -B _p2pkit2._tcp local > "$EVIDENCE/logs/dns-sd-browser.log" &
```

Pass: permission denial is distinguishable from transport failure; AWDL or
same-interface rotation recovers without a stale peer; listener/browser
cleanup is acknowledged; no old descriptor accepts connections; secure-v2
peers exchange messages/files and equal hashes. Fail: ghost peer, unreleased
port, false ready, permanent failure after rotation, or legacy-v1 fallback.

Collect Console/log stream, on-screen diagnostic log, `dns-sd` capture,
screen/video, `lsof`/`nc` port probes, packet capture where permitted, and
device sysdiagnose reference. Cleanup by Stop, app termination, and restoring
Wi-Fi/Hotspot settings.

### ENV-01 — physical Android/Apple release matrix

Purpose and risk: combine the supported platform/runtime matrix into one
repeatable acceptance run.

Required setup: one API-26, one API-32, one API-37 Android device or approved
emulator set, two physical Apple devices, a Mac, USB cables, private AP, and
the exact release/debug artifacts produced from the pinned SHA.

Run PS-T01, PS-T02, PS-T04, LAN-T01, and LAN-T07 once per device pair. Record
OS/build, ABI, target SDK, permission prompts, background/foreground behavior,
process restart, transfer hashes, and all terminal errors. PASS requires every
pair's supported conjunct to pass; any unsupported device is recorded as
NOT RUN with the owner-approved reason, not silently omitted.

### ENV-04 — iOS x86_64 host/runtime

Purpose and risk: validate the Apple x86_64 slice and Swift bridge on an
Intel Mac or approved x86_64 CI runner.

Required setup: Intel macOS host, Xcode version used by the project, x86_64
iOS Simulator runtime, and the pinned checkout. A physical device is not a
substitute.

Commands:

```sh
./gradlew :p2p-core:iosX64Test :p2p-transport-lan:iosX64Test
./gradlew :p2p-transport-lan:assembleP2pKitSharedReleaseXCFramework
xcrun simctl list runtimes
```

Launch the generated iOS sample on an x86_64 simulator, run the committed
Start/Stop UI test, connect to a JVM peer if the simulator networking allows
it, and perform one 200 KiB transfer. PASS requires the x86_64 framework
loads, Swift warnings-as-errors remain clean, and the UI/transfer evidence
matches arm64. FAIL includes missing slice, loader error, or a target-specific
protocol difference.

### PS-T07 — iOS sink failure, collision, partial cleanup, and collector cancellation

Purpose and risk: prove the Swift `AtomicFileTransferDestination`,
FileHandle/fsync/atomic replacement, collision naming, and task cancellation
under real device filesystem and lifecycle timing.

Required setup: one physical iOS device, a second sender, USB/Mac, a private
AP, at least 100 MiB free storage, and an owner-approved test build with the
test-only fault injection or a controlled filesystem-full/sink-failure
mechanism. Do not alter production security or use a real user's files.

Actions:

1. Pre-create `P2pKitInbox/name.bin` and two simultaneous offers with the same
   name; verify atomic `name (1).bin`/`name (2).bin` reservations.
2. Accept a 5 MiB transfer, background the app, lock/unlock, foreground it,
   and verify progress and final hash.
3. Cancel at Offered, Accepted, and mid-Sending; kill the receiver process;
   verify temporary `.p2pkit-part` files and reserved placeholders are gone.
4. Fill the inbox or enable the approved sink-write fault; verify a typed
   failure, no committed target replacement, and cleanup.
5. Repeat Stop during active transfer and verify SDK writers quiesce before
   sample watcher tasks are cancelled.

Collect device Console logs, diagnostic log, filesystem listings before/after,
video, hashes, transfer IDs, and storage free-space snapshots. PASS requires
all non-completed paths leave no partial output and all completed paths are
durable and hash-equal. FAIL includes a partial file, overwritten existing
file, leaked task, or untyped crash.

### PS-T08 — hostile names and scoped IPv6 across samples

Purpose and risk: validate path containment and manual endpoint parsing on
physical interfaces with IPv6 scope IDs.

Required setup: one iOS device, one Android or Desktop peer, AP with IPv6
link-local addressing, and a sender able to set an owner-controlled display
name/file name containing `../`, `..\\`, control characters, Unicode bidi
marks, and long names.

Actions: set safe/hostile names, use the iOS Manual connect fields with
`[fe80::1%en0]:<port>` and unbracketed scoped forms where supported, connect
using the full `p2f1` fingerprint, send a fixture, and inspect the receiver
inbox and logs. PASS requires the connection uses the intended interface,
the file remains inside the fixed inbox, and terminal/log output contains no
control escape. FAIL includes path escape, wrong peer, or parser truncation.

### PS-T09 — physical KMP Android and iOS consumer runtime

Purpose and risk: prove that a consumer built through the documented KMP
surface loads and runs on Android and that the generated XCFramework/Swift
consumer loads and runs on a physical iOS device. Host compilation and
simulator launch do not close this gap.

Required setup: one API-26+ Android device, one physical iOS 15+ device, Mac
with Xcode, USB cables, private AP, and a JVM/Desktop peer using App ID
`p2pkit-desktop-sample`. The Android consumer must call
`initP2pKitAndroid(applicationContext)` before `createP2pKit`; the iOS target
must link the exact release XCFramework produced from the pinned SHA.

Build:

```sh
./gradlew :sample-kmp-shared:check \
  :p2p-transport-lan:assembleP2pKitSharedReleaseXCFramework
scripts/check-published-consumers.sh
```

For Android, use the sample consumer build that depends on
`:sample-kmp-shared`, install it, initialize the platform context from
`Application.onCreate`, call `createP2pKit`, and invoke
`runDiscoverAndGreet`. For iOS, generate/build the checked-in sample against
`P2pKitShared.xcframework`, launch it on the physical device, Start, discover
the JVM peer, connect, send text, and complete one 200 KiB file transfer.

Expected Android output is either `sent greeting to <name> (<id>…)` or the
explicit timeout string when the peer was deliberately absent; in both cases
the demo must close its session and stop its kit. Expected iOS output is
Running, one authenticated Connected session, frame/transfer diagnostics, a
Completed transfer, and equal SHA-256 values.

PASS requires both device runtimes to load the exact artifacts, exercise
advertise/discover/connect/send/close/stop, and leave no live listener after
cleanup. FAIL includes missing symbol/slice, initialization error, identity
reset caused by missing Android initialization, leaked listener, or different
secure-v2 behavior. Collect device logs, screen/video, consumer dependency
report, artifact hashes, BuildInfo, and final port probes. Uninstall consumer
apps and remove test profiles after evidence is secured.

## 4. Two-machine hostile-network tests

### LAN-T08 — hostile LAN records, spoofing, alternate candidates, and flood

Purpose and risk: validate DNS-SD/TXT bounds, service ownership, duplicate-PID
spoof resistance, off-subnet filtering, alternate-address fallback, and
connection-flood admission under a real network.

Required setup: two machines/devices plus a controlled AP/VLAN; one legitimate
Android/iOS/JVM peer; one attacker machine on the same test network; packet
capture capability; owner-approved service-record/flood generator. Never run
this on an untrusted network.

Preparation:

1. Put legitimate peers on VLAN A. Put the attacker on VLAN A, then VLAN B.
2. Capture the baseline legitimate `_p2pkit2._tcp` record and full fingerprint.
3. Start the legitimate samples with diagnostic/frame traces enabled.

Attack cases:

* 255-byte and overlong TXT values, invalid UTF-8, unsupported protocol/security
  version, excessive capability tags, control/bidi characters.
* Same peer ID with a different service instance/fingerprint, duplicate PID,
  TXT-less removal, stale listener generation, and off-subnet host addresses.
* Eight valid address candidates with the first candidate blocked, then all
  candidates blocked.
* A bounded burst of new TCP connections and incomplete handshakes.

Expected: invalid records are rejected before connection; a removal can only
  withdraw the previously admitted exact service instance; off-subnet
  candidates are ignored; the next valid address can recover; floods are
  bounded without starving an existing session; no spoofed authenticated peer
  is accepted. PASS requires packet capture plus matching sanitized diagnostics.
  FAIL includes spoof acceptance, unbounded memory/connection growth, or a
  legitimate peer becoming permanently undiscoverable.

Collect PCAP, generator configuration, firewall rules, CPU/memory samples,
application logs, screen/video, and device/host metadata. Tear down all
advertised records and restore VLAN/firewall rules.

### ENV-02 — two-machine hostile-network end-to-end

Purpose and risk: combine LAN-T08 with secure-v2 tamper, replay, off-subnet,
loss, and recovery behavior across independent machines.

Required setup: two physical hosts/devices, managed AP/VLAN, attacker/filter
machine, synchronized clocks (record NTP status), and a private test key
policy. Use a legitimate authenticated same-AppId pair and a distinct
attacker identity.

Run LAN-T08, then:

1. Capture one authenticated handshake and data transfer.
2. Drop, delay, duplicate, reorder, and bit-flip selected packets with the
   controlled filter. Do not alter the secure library or disable authentication.
3. Replay an old envelope/transfer ID after the session has rotated keys.
4. Interrupt the AP and restore it; repeat with the peer process terminated.

PASS: tampered/replayed data fails closed with a typed/authenticated error;
no partial commit occurs; legitimate reconnect obeys configured limits;
duplicate offers/transfers do not create duplicate committed files; logs expose
transfer ID, protocol version, failure phase, and timestamps. FAIL: plaintext
acceptance, digest-only acceptance without envelope authentication, duplicate
commit, or unbounded retry.

## 5. CLI fault-injection

### PS-T05 — packaged JVM CLI options, ambiguity, shutdown, and injected faults

Purpose and risk: validate the real terminal process, not only parser unit
tests: option isolation, separate identities, collector shutdown, process
termination, injected `create`/`stop`/REPL failures, and multi-peer ambiguity.

Required setup: two JVM 17 processes on one machine or two machines, two
isolated identity profiles, private LAN, terminal recorder (`script` or
`asciinema`), and an owner-approved fault-injection wrapper that can close
stdin, send SIGTERM, interrupt the process, and force a controlled exception.

Start Alice and Bob:

```sh
script -q "$EVIDENCE/logs/cli-alice.typescript" \
  ./gradlew :p2p-sample-desktop:run \
  -Pp2pkit.sample.identityProfile=alice \
  --args='Alice p2pkit-desktop-sample reconnect=5,1000 trace=frames'
script -q "$EVIDENCE/logs/cli-bob.typescript" \
  ./gradlew :p2p-sample-desktop:run \
  -Pp2pkit.sample.identityProfile=bob \
  --args='Bob p2pkit-desktop-sample reconnect=5,1000 trace=frames'
```

At each prompt run `info`, `peers`, `sessions`, `send`, `sendfile`,
`offers`, `accept`, `reject`, `close`, `adv off/on`, `disc off/on`, and
`quit`. Repeat with an unknown option, duplicate option, malformed reconnect,
ambiguous peer prefix, EOF, SIGTERM, and the approved injected create/stop/REPL
failure. PASS requires one clean shutdown, no stranded child process, no
duplicate collector output, and sanitized terminal text. FAIL includes a
process leak, bypassed `finally`, option treated as a device name, or a
terminal outcome that depends on timing.

Collect terminal recordings, exit codes, process tree, stdout/stderr, logs,
identity-profile paths, and command transcripts. Remove temporary profiles
after hashing evidence.

## 6. Headful Desktop UI

### PS-T06 — Compose Desktop lifecycle, transfer, and soak automation

Purpose and risk: exercise the actual window, file chooser, rapid lifecycle
controls, offer consent, cancellation, storage failure, and bounded history.

Required setup: a macOS/Linux/Windows desktop with a real display (not
headless), JVM 17, two Desktop UI instances or one UI plus CLI peer, private
LAN, screen recorder, and an owner-approved UI automation tool (AppleScript,
xdotool, Sikuli, WinAppDriver, or equivalent).

Launch:

```sh
./gradlew :p2p-sample-desktop-ui:run
```

UI actions:

1. On Setup enter unique Device name and identical App ID; select reconnect
   Enabled with `maxAttempts=5`, `retryDelayMillis=1000`; Start.
2. Record BuildInfo/identity, state, Advertise/Discover/Auto-mesh, local
   endpoint, and logs.
3. Connect peers, send a fixture through the native chooser, accept/reject
   offers, cancel during progress, and verify progress/terminal/hash output.
4. Rapidly toggle Advertise/Discover and Stop/Start; close the window during
   startup, during an offer, and during a transfer.
5. Run at least 1,000 terminal messages/transfers or the owner-approved
   byte-budget duration, then verify only bounded history remains and active
   rows are never evicted.
6. Inject the approved create/stop/sink fault and repeat.

PASS requires visible controls and logs match SDK state, no frozen window,
clean process exit, no partial files, and bounded memory/history. FAIL includes
an unresponsive window, orphaned JVM, lost consent, stale active row, or
unbounded log/byte growth. Collect video, screenshots, UI automation logs,
process tree, JVM heap sample, filesystem/hash evidence, and exact fixture
paths. Reset profiles and delete generated inboxes after the run.

## 7. Secure-v2 interoperability

### SECURE-V2-INTEROP-01 — independent implementation and version matrix

Purpose and risk: establish that the secure-v2 handshake, authenticated
metadata envelope, file-commit negotiation, SHA-256 snapshot, replay/downgrade
rules, and typed failures interoperate with an implementation not derived from
this repository.

Required setup: an independent reviewer-owned or vendor-owned secure-v2 peer,
published P2pKit artifacts from the pinned SHA, JVM/Android/Apple endpoints,
protocol test vectors, and a packet capture harness. The independent peer
must not share P2pKit's parser, test fixtures, or private keys.

Procedure:

1. Exchange version/capability vectors and confirm secure-v2 is selected only
   when both peers advertise `file-commit-sha256-v1` and authenticated
   metadata. Legacy-v1 must not silently upgrade.
2. Run handshake with fresh keys, pinned expected key, wrong key, wrong AppId,
   downgraded protocol version, malformed envelope, and replayed nonce.
3. Send text and files with known metadata: message type, sender/recipient
   IDs, protocol version, transfer ID, name, MIME, size, sequence, timestamp,
   content length, digest, and commit marker. Verify canonical encodings byte
   for byte against the independent vectors.
4. Interrupt before offer, after accept, after final digest, before durable
   commit, after commit, and after sender receives acknowledgement.
5. Compare all terminal outcomes and typed error kinds. Confirm duplicate
   retries are idempotent and do not create two committed files.

PASS requires independent logs and packet/vector comparison, equal final
hashes, fail-closed downgrade/tamper/replay behavior, and no dependency on
private P2pKit internals. FAIL includes any unauthenticated metadata
acceptance, silent legacy fallback, different canonical bytes, duplicate
commit, or inconsistent error mapping. Preserve the independent test report,
vectors, PCAP, key provenance, and reviewer signature.

## 8. Professional cryptographic audit preparation

### CRYPTO-AUDIT-01 — independent review package

Purpose and risk: prepare an external cryptographer to review the Noise-style
secure-v2 state machine, provider integration, key storage, canonical
identity/metadata encoding, replay/downgrade controls, and durable file
commit. This is an audit preparation package, not an audit result.

Required people and materials: professional cryptographic auditor under an
owner-approved engagement; pinned source SHA; dependency lockfiles and SBOM;
release XCFramework/AAR/JVM artifacts; threat model; protocol specification;
known-answer/interoperability vectors; Android Keystore/iOS Keychain/JVM
storage documentation; and reproducible build/provenance output.

Preparation steps:

1. Export a clean source archive at the pinned SHA, excluding protected review
   files, credentials, generated build output, and local evidence.
2. Run `scripts/check-sbom.sh`, publication-consumer checks, ABI/Dokka checks,
   release-XCFramework provenance, and the complete repository gate; preserve
   outputs.
3. Give the auditor the exact files named in the tracker PARSE-META/XFER-PROTO
   record, secure-v2 wire diagrams, canonicalization rules, failure matrix,
   migration/legacy-v1 boundary, and independent test vectors.
4. Ask for explicit written conclusions on key agreement, transcript binding,
   provider suitability, nonce/replay safety, downgrade resistance,
   side-channel/constant-time assumptions, metadata coverage, SHA-256
   limitations, durable commit ordering, crash recovery, and platform key
   protection.
5. Require findings to identify severity, affected commit/file/line, exploit
   preconditions, and a retest criterion. Do not remediate or close findings
   inside the audit report without owner review.

Pass for preparation: the auditor confirms receipt of the complete pinned
package and can reproduce the stated vectors/build hashes. The professional
audit itself must be recorded separately and is required before security
production claims. Fail: missing source/artifact provenance, unreviewed
dependency/provider, absent vectors, or an audit performed against a
different SHA.

## 9. Remote Central/Portal publication

### BUILD-02 / ENV-07 — credentialed publication and remote status

Purpose and risk: verify release publication, signing, namespace ownership,
metadata, checksum, and remote availability through the owner-approved
Central/Portal service.

Required setup: owner-approved portal and namespace, signing key/test key held
outside the repository, CI environment with short-lived credentials, a
release tag policy, and a second machine able to consume the published
coordinates. Never commit credentials or upload unreleased private material.

Preparation and commands:

```sh
git status --short
git rev-parse HEAD
./gradlew check
./gradlew :p2p-core:publishAllPublicationsToLocalRepository
./gradlew :p2p-transport-lan:publishAllPublicationsToLocalRepository
scripts/check-published-consumers.sh
```

Use the owner-approved CI workflow or Portal upload command with credentials
in the CI secret store. Verify every published POM/module metadata/API scope,
signature, checksum, SBOM/provenance sidecar, and release visibility. From a
clean second machine resolve the exact version and run the JVM, Android, KMP,
and Swift/publication-consumer checks. Verify no snapshot or wrong namespace
was published.

PASS: remote status is successful, signatures/checksums match the locally
verified artifacts, the exact coordinates resolve from a clean consumer, and
the Portal records the expected commit/version. FAIL: wrong namespace,
unsigned/mismatched artifact, missing platform publication, credential leak,
or consumer resolution from a different commit. Revoke test credentials,
delete test staging artifacts only through the portal's documented workflow,
and retain the final remote status/audit trail.

## 10. Sample-app capability matrix

The following matrix is based on the checked-in applications and their actual
controls. “External” means the sample exposes the observation needed by the
test, while the missing hardware/infrastructure remains a blocker.

| Capability | iOS sample | Android sample | JVM CLI | Desktop UI |
| --- | --- | --- | --- | --- |
| Sender and receiver | Both; peer/session UI | Both; peer/session UI | Both; commands | Both; controls |
| Secure-v2 | `AuthenticatedV2`, same-AppId test policy | `AuthenticatedV2`, same-AppId test policy | `AuthenticatedV2`, same-AppId test policy | `AuthenticatedV2`, same-AppId test policy |
| Authenticated metadata | SDK secure-v2 path; frame trace/log | SDK secure-v2 path; `P2pKitFrame` logcat | SDK secure-v2; `trace=frames` | SDK secure-v2; stdout frame trace |
| Durable transfer/SHA-256 | Atomic destination; 200 KiB/5 MiB/49 MiB presets; sender/receiver SHA log | Durable destination; SAF selection; sender/receiver SHA log and UI row | Durable destination; `sha256` and `durable sha256` terminal lines | Durable destination; prepared/received SHA log and UI row |
| Progress/completion/cancel/failure | Session transfer rows, ProgressView, Cancel, typed state text | Transfer cards, bytes/percent, Cancel, typed state text | State lines, terminal failure/rejection/cancel | Transfer cards, bytes/percent, Cancel, typed state text |
| Pending offers | Accept/Reject rows retained until action | Accept/Reject rows retained until action | `offers`, `accept`, `reject` | Accept/Reject rows retained until action |
| Peer identity/state | BuildInfo, local peer ID, peer ID/session ID, state transitions | BuildInfo, local peer ID, state header, network-path chip | `info`, `peers`, `sessions`, state lines | BuildInfo/state/peer/session rows |
| Advertising/discovery state | Start/Stop plus diagnostic browser/listener lines | Advertise/Discover switches and `P2pState` | `adv on/off`, `disc on/off`, `info` | Advertise/Discover switches and state |
| Network interruption/reconnect | Wi-Fi/path rotation, reconnect policy in SDK, manual IP | Wi-Fi/path chip, configurable reconnect, hotspot host/join | `reconnect=n,delay`, manual endpoint, trace | Configurable reconnect, manual endpoint |
| Background/foreground/restart | Real iOS lifecycle and Stop cleanup | Activity rotation; process death is intentionally external | EOF/SIGTERM/quit | Window disposal/Stop |
| File selection/generation | Deterministic generated presets | Android SAF `OpenDocument` any type/size | Filesystem path | Native file chooser |
| KMP consumer runtime | Swift/XCFramework consumer plus physical sample | `Run KMP consumer smoke` button calls `initP2pKitAndroid`/`runDiscoverAndGreet` | JVM KMP consumer tests and CLI | Uses published JVM/consumer checks |
| Packet/timeout/fault controls | Logs and OS/network tools; no production fault toggle | Logs and adb/network tools; no production fault toggle | `trace=off|frames`, external process fault wrapper | External headful/fault harness |
| Evidence export | On-screen selectable log, Console/log stream, screen/video | Logcat, selectable UI rows, adb dumps, screen/video | Terminal transcript, stdout/stderr, PCAP | stdout/log tail, screenshots/video |
| Platform limitation | Physical AWDL/path and x86_64 require Apple hardware/runtime | Real hotspot/OEM callbacks and API matrix require devices | CLI fault injection requires approved wrapper | Headful UI/fault injection requires display and automation |

Applicable test IDs: iOS `LAN-T07`, `ENV-01`, `ENV-04`, `PS-T07`,
`PS-T08`, `PS-T09`, `SECURE-V2-INTEROP-01`; Android `PROV-A12`, `PT-T20`,
`LAN-T01`, `PS-T01`, `PS-T02`, `PS-T04`, `PS-T08`, `PS-T09`; CLI `LAN-T08`,
`ENV-02`, `PS-T05`, `SECURE-V2-INTEROP-01`; Desktop UI `PS-T06`, `PS-T08`.

The sample additions in this revision are test-focused only: deterministic
iOS size presets and SHA-256 evidence, plus equivalent Android/JVM/Desktop
hash display/logging and known-vector tests. They do not weaken production
security, change the public SDK ABI, or add secrets. The samples still do not
replace physical devices, hostile-network equipment, an independent secure-v2
peer, a cryptographic auditor, or owner-approved publication credentials.

## 11. Final readiness decision

The following can be executed immediately on a suitably provisioned local
machine: all JVM CLI happy-path/option tests, Desktop UI happy-path tests,
iOS simulator UI, Android host/unit tests, publication dry-runs/local
consumers, and the deterministic protocol/vector suites already recorded in
the tracker.

The following remain externally blocked until the evidence above exists:

* Android physical provisioning, OEM callback, process-binding, hotspot,
  multicast, selected-network, and instrumentation evidence.
* Apple physical Local Network/AWDL/path-rotation/runtime and x86_64 host
  evidence.
* Two-machine hostile-network, spoof/tamper/replay, and connection-flood
  evidence.
* Controlled CLI/Desktop UI fault-injection and iOS sink-failure/device
  cancellation evidence.
* Independent secure-v2 interoperability and professional cryptographic audit.
* Credentialed Central/Portal publication and remote consumer verification.

No one of these requirements may be marked `Verified` from compilation,
simulator output, or a single happy-path run.
