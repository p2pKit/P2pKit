# Android physical-device validation

**Status: NOT STARTED.** Emulator and JVM results do not satisfy this plan.

## Purpose and scope

Validate Android OS callbacks, permission flows, multicast discovery, selected
network routing, LocalOnlyHotspot/WifiNetworkSpecifier ownership, secure-v2
sessions, durable transfer, lifecycle recovery, and sample behavior on real
hardware. This handbook operationalizes `PROV-A12`, `PT-T20`, `LAN-T01`,
`PS-T01`, `PS-T02`, `PS-T04`, and the Android portions of `ENV-01`, `PS-T08`,
and `PS-T09`. Use the corresponding entries in
[`test-catalog.md`](test-catalog.md) for the required diagnostic events.

## Required equipment and matrix

- Two physical Android devices; three are preferred for simultaneous discovery
  and provisioning ownership. At least two different manufacturers are
  mandatory.
- One USB data cable per device, a powered USB hub if needed, and a development
  machine with the repository JDK, Android SDK, `adb`, and Gradle toolchain.
- A normal WPA2/WPA3 access point with administrative access, plus a topology
  where one device can host LocalOnlyHotspot. Record AP model and firmware.
- Minimum OS matrix: oldest supported API 26, one API 29-32 device, one API
  33-34 device, and one API 35-or-newer device. A device may cover multiple
  scenarios, but the two-manufacturer rule remains.
- At least 2 GiB free storage per device. Disable battery saver for the baseline
  run; test default OEM background policy separately.

Bluetooth is not a P2pKit LAN transport and must not be treated as a discovery
prerequisite. Record whether Bluetooth is enabled only to rule out accidental
coupling.

## Immutable preparation

From a clean checkout of the candidate commit:

```bash
export P2PKIT_SHA="$(git rev-parse HEAD)"
test -z "$(git status --short)"
test "$(git rev-parse 'v0.7.0-rc2^{commit}')" = \
  "90acb29583ea11d18685cf1315476756e7618245"
./gradlew --no-daemon :p2p-sample-android:clean \
  :p2p-sample-android:assembleDebug \
  :p2p-sample-android:assembleDebugAndroidTest
adb devices -l
```

Use a separate terminal with `ANDROID_SERIAL` set for each device:

```bash
export ANDROID_SERIAL=<serial-from-adb-devices>
adb shell getprop ro.product.manufacturer
adb shell getprop ro.product.model
adb shell getprop ro.build.version.release
adb shell getprop ro.build.version.sdk
adb install -r samples/p2p-sample-android/build/outputs/apk/debug/p2p-sample-android-debug.apk
adb shell pm clear dev.p2pkit.sample.android
```

If the APK name differs, locate it with
`find samples/p2p-sample-android/build/outputs/apk -name '*.apk' -type f`; record
the exact installed path. Do not grant permissions silently for permission-flow
cases. For baseline transfer cases, grant only through the displayed system UI.

Before each case, record:

```bash
adb shell dumpsys package dev.p2pkit.sample.android
adb shell dumpsys wifi
adb shell dumpsys connectivity
adb shell cmd location is-location-enabled
```

Start a timestamped OS log in a dedicated file:

```bash
adb logcat -c
adb logcat -v threadtime > <evidence-dir>/<device-role>-logcat.txt
```

## Common in-app procedure

1. Open the sample and the **Test diagnostics** screen.
2. Enter the catalog test ID, enter the same shared session ID on both devices,
   select `sender`, `receiver`, or `both`, and start the diagnostic session.
3. Return to the main screen. Record the build identity and local peer ID.
4. Use the visible **Advertise**, **Discover**, and **Auto-mesh** switches. Use
   **Host hotspot** and **Join hotspot** only for provisioning cases.
5. Record peer/session state, connection ID, transfer ID, selected path,
   progress, sender/receiver SHA-256, and final result as shown.
6. End the diagnostic session and tap **Export Test Evidence**. Use the Android
   share sheet to save the ZIP in the test evidence directory. Export both
   peers even if one UI reports failure.

Do not document a state as connected until both the UI and the correlated
`connection.state.changed` event say `Connected` after secure-v2 negotiation
and authentication.

## Test cases

### A1 — permission and provisioning terminal-callback matrix

Run `PROV-A12 / PS-T01` on every OS band. Start with Location off and all
nearby/location permissions denied. Tap **Host hotspot** and then **Join
hotspot** with synthetic credentials. Exercise deny, deny-and-do-not-ask-again,
grant, system cancellation, user cancellation, and a successful operation.

For every request, verify exactly one terminal UI result and one correlated
terminal diagnostic event. A permission-required result must not claim that a
network started. After success, **Stop hotspot** must release the reservation;
after cancellation or timeout, no late callback may change the completed
result. Capture permission dialogs and the final provisioning card.

### A2 — two-manager ownership

Run `PROV-A12 / PS-T02` on a device/OS combination that exposes the real
ConnectivityManager behavior. Start manager A and acquire a hotspot or joined
network. While A is active, initiate the same operation as manager B from a
second app process or the test harness specified by the catalog. Close B first,
then A; repeat in reverse order.

Pass requires explicit ownership behavior, no release of A's network by B, no
process-wide bind leak, and successful reacquisition after both managers close.
Capture network handles and `dumpsys connectivity` before and after each close.

### A3 — LAN discovery, selected route, IPv4/IPv6, and secure transfer

Run `LAN-T01 / PT-T20` on the normal AP, LocalOnlyHotspot, IPv4-only network,
dual-stack network, and an IPv6 link-local-capable topology where available.
Enable **Advertise** and **Discover** on both peers, first with **Auto-mesh** off
and then on. Connect manually once and automatically once.

The discovered identity, chosen interface/network, address family, and data
socket must describe the same LAN. Cellular or VPN must not silently carry the
session. Send in both directions:

- empty and 1-byte files;
- deterministic 200 KiB, 5 MiB, and 49 MiB files;
- UTF-8, binary, image, and filename-with-hostile-characters fixtures from the
  catalog.

Accept, reject, cancel before acceptance, cancel mid-transfer, and complete.
Independently hash source and committed destination where the sample/Android
picker permits. Completion requires equal length and SHA-256, durable commit,
and a final acknowledgment. No partial destination may be presented as
completed.

### A4 — lifecycle, interruption, and process recovery

Run `PS-T04`. During discovery, handshake, and transfer separately:

1. Rotate the screen and background/foreground the app for 30 seconds.
2. Lock/unlock the device.
3. Disable/enable Wi-Fi; then move between AP and hotspot.
4. Use `adb shell am force-stop dev.p2pkit.sample.android`, relaunch, and start a
   new diagnostic session that records recovery state.
5. Repeat **Advertise**/**Discover** toggles 50 times and **Stop kit**/start 20
   times, waiting for each terminal state rather than racing the UI.

The UI must remain responsive, stale peers must disappear, no old transfer may
be reported complete after process death, and retained durable outputs must be
uncorrupted. Recovery must use new connection IDs while preserving transfer-ID
semantics where the protocol supports recovery.

### A5 — physical consumer runtime and hostile input

Run `ENV-01`, `PS-T08`, and `PS-T09`. Tap **Run KMP consumer smoke** and verify
that the checked-in KMP consumer initializes against the exact candidate.
Exchange hostile-but-safe peer names, scoped IPv6 addresses, maximum permitted
metadata, and invalid/oversized forms generated by the approved harness.

Invalid records must be rejected with typed, redacted diagnostics; they must
not create a peer/session, escape a destination directory, crash the app, or
expose raw payloads.

## Pass/fail and retained evidence

Pass only if every mandatory matrix cell completes with matching UI and logs,
all successful transfers have matching independent hashes, all negative cases
fail closed, and three consecutive reruns on each topology are deterministic.

Fail for any false `Connected`/`Completed` state, callback after terminal
completion, leaked hotspot/network binding, wrong-interface routing, stale peer
that survives the documented timeout, unbounded retry, crash/ANR, missing peer
evidence, hash mismatch, committed partial file, or secret/payload disclosure.

Retain both evidence ZIPs, logcat, `dumpsys` snapshots, screenshots/video,
source/destination hashes, AP/router logs, packet capture when route/multicast is
being proven, device properties, exact commands, and the completed catalog
result template.

## Cleanup and reset

```bash
adb shell am force-stop dev.p2pkit.sample.android
adb shell pm clear dev.p2pkit.sample.android
adb logcat -d -v threadtime > <evidence-dir>/<role>-logcat-final.txt
```

Stop LocalOnlyHotspot, forget synthetic test networks, restore Wi-Fi/location
and OEM battery settings, remove only synthetic received files, stop logcat,
hash the evidence directory, and confirm no test VPN/firewall rule remains.

## Completion checklist

- [ ] Required OS and manufacturer matrix completed.
- [ ] Permission, ownership, LAN, lifecycle, consumer, and hostile-input cases passed.
- [ ] Both-peer exports and external routing evidence correlate.
- [ ] Three deterministic reruns retained per mandatory topology.
- [ ] Independent reviewer signed the result record.
