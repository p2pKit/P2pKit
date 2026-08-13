# Apple physical-device and AWDL validation

**Status: NOT STARTED.** Simulator compilation and simulator UI tests do not
prove Local Network permission, AWDL, radio/path changes, suspension, or
real-device process recovery.

## Purpose and scope

Validate Bonjour/AWDL discovery, Network.framework listener/browser behavior,
authenticated sessions, bidirectional durable transfer, path rotation,
foreground/background behavior, process restart, and the Swift sample on real
iPhone/iPad hardware. This covers `LAN-T07`, `ENV-01`, `ENV-04`, `PS-T07`,
`PS-T08`, and `PS-T09`; use the matching diagnostic sequences in
[`test-catalog.md`](test-catalog.md).

Implementation commit `fc73837cfa154caa82a6f96172603108b8577842`
passes four Apple manual-provisioning lifecycle tests inside the 89-test
arm64-simulator suite. They prove manager-owned caller cancellation, terminal
parent-job shutdown, post-close rejection, and fingerprint/pairing-QR
projection in a controlled runtime. Simulator evidence cannot prove actual
iOS suspension, termination, signing, radio paths, or AWDL, so this handbook's
status remains **NOT STARTED**.

## Required equipment and coverage

- Two physical Apple devices signed by a development team; one iPhone and one
  iPad are preferred. Add a third device when testing discovery churn.
- Cover iOS/iPadOS 14, one intermediate release, and the newest available
  release, with at least two hardware generations. The checked-in sample may
  retain a newer UI deployment target, but the candidate library/XCFramework
  must be built with and prove the documented iOS 14 compatibility floor.
- A Mac with compatible Xcode, command-line tools, repository JDK, Kotlin/Native
  toolchain, free USB ports/cables, and permission to install development apps.
- A normal Wi-Fi LAN and an AWDL peer-to-peer topology. Administrative access
  to the AP is required for path rotation and packet-capture correlation.
- A valid non-production signing team/profile and an app identifier allowed to
  request Local Network access. Never commit signing identifiers or profiles.

`ENV-04` additionally requires a real Intel Mac or a supported x86_64 runtime.
Rosetta alone does not prove an x86_64 iOS simulator/runtime path; record the
actual host architecture and destination.

## Build, sign, and install

From a clean immutable checkout:

```bash
export P2PKIT_SHA="$(git rev-parse HEAD)"
test -z "$(git status --short)"
./gradlew --no-daemon :p2p-core:iosSimulatorArm64Test \
  :p2p-transport-lan:iosSimulatorArm64Test \
  :p2p-transport-lan:assembleP2pKitSharedReleaseXCFramework
cd samples/iosApp
xcodegen generate
xcodebuild -project p2pkit-sample.xcodeproj \
  -scheme p2pkit-sample-ui \
  -configuration Debug \
  -destination 'generic/platform=iOS' \
  CODE_SIGN_STYLE=Automatic DEVELOPMENT_TEAM=<team-id> build
```

Use Xcode's Devices and Simulators window or `xcrun devicectl` to identify and
install the built `.app`:

```bash
xcrun devicectl list devices
xcrun devicectl device install app --device <device-id> <path-to-p2pkit-sample.app>
xcrun devicectl device process launch --device <device-id> dev.p2pkit.sample
```

Record the full `xcodebuild` command, Xcode/Swift version, signing team name
(not credentials), app bundle version, device model, OS build, and candidate
SHA. Generate the Xcode project from `project.yml`; do not hand-edit the
generated project.

## Diagnostics and permissions

On first launch, capture the Local Network prompt. Test allow and deny on a
clean install. For a denied app, confirm the UI and `discovery` state report a
permission/error outcome and never claim peers were found. Re-enable under
Settings > Privacy & Security > Local Network, then tap **Stop** and **Start**.

Open **Test Diagnostics**, enter the test ID and a shared session ID used on
both peers, choose the role, and start the session. Record the displayed build,
peer, connection, transfer, protocol, path, hash, and final-result values. Use
**Export Test Evidence** and save the share-sheet ZIP for each peer.

For current post-RC2 candidates, search the structured transport observations
for these stable fields/substrings as applicable:

- `browser params: cellular=PROHIBITED, include_peer_to_peer=true`;
- `path-monitor:` with `usesWifi`, `usesCellular`, `usesWired`, `usesOther`,
  address fingerprint, and change flags;
- `lifecycle notification observed signal=` with `rebindScheduled=`;
- `rebindNow: starting`, `new listener ready`, and `rebindNow: complete`;
- `cached endpoint invalidation` with peer, browser generation, removal result,
  and reason;
- `write(...): TIMEOUT` followed by `nw_connection_cancel (write-ready timeout)`.

These are internal evidence signals, not standalone PASS criteria. Correlate
them with the diagnostics screen's test/session/connection identifiers and
both peers' visible state. Redacted `transport.log` or `network.path.changed`
events in an evidence export are the expected structured wrappers.

Collect an external unified log in parallel:

```bash
log stream --level debug --style compact \
  --predicate 'process == "p2pkit-sample" OR eventMessage CONTAINS[c] "P2pKit"' \
  > <evidence-dir>/<role>-apple-unified.log
xcrun devicectl device info details --device <device-id> \
  > <evidence-dir>/<role>-device.txt
```

Use only synthetic payloads. Apple system logs can contain device identifiers;
redact those before sharing while retaining a private unredacted original.

## Test cases

### B1 — permission, Bonjour, and baseline LAN

Run `LAN-T07` on the normal Wi-Fi LAN. Start both samples; **Start** must create
one listener and one browser and reach their ready states. Discover each peer,
connect manually, then repeat through auto-mesh where supported. Verify
`secure-v2`, authenticated remote fingerprint/policy, and matched peer/session
identity in both exports.

Send text and deterministic 1-byte, 200 KiB, 5 MiB, and 49 MiB files in both
directions. Exercise accept, reject, cancel before acceptance, cancel during
transfer, and success. Success requires exact source/receiver size and SHA-256,
durable commit before acknowledgment, one final outcome, and no partial output.

### B2 — AWDL peer-to-peer path

Disconnect both devices from the test Wi-Fi AP while leaving Wi-Fi enabled so
the OS may use peer-to-peer interfaces. Start advertising/discovery on both
devices, wait the catalog timeout, and record Network.framework path/interface
diagnostics. Establish a session and transfer in both directions.

Pass requires discovery and data to use an Apple-supported peer-to-peer path,
with no hidden cellular fallback, and recovery/teardown events on both peers.
The browser, listener, and outbound connection must all report peer-to-peer
enabled; the browser policy must report cellular prohibited. A browser that
fails to become ready under that policy is a FAIL, not permission to remove the
restriction for the test.
If the OS does not expose a shareable interface name, retain the safely exposed
path flags, `dns-sd` observation from the Mac, timestamps, and a packet capture
where lawful. “Peers connected” without path evidence does not prove AWDL.

### B3 — path and interface rotation

During discovery, handshake, idle connected state, and mid-transfer separately:

1. Join and leave the Wi-Fi AP.
2. Switch between two APs/subnets.
3. Disable/enable Wi-Fi while cellular remains available.
4. Move from infrastructure Wi-Fi to the AWDL topology and back.

Expected behavior is a bounded path-change/rebind sequence, removal of stale
endpoints, a new connection ID after reconnection, and either a typed transfer
interruption/recovery or an explicit terminal failure. It must never silently
route over prohibited cellular, preserve a ghost peer indefinitely, reuse a
stale endpoint after restart, or show `Connected` after the transport is gone.
An `other=false→true` or `true→false` path transition must participate in the
fingerprint even if the Wi-Fi/cellular/wired bits do not change. During browser
or listener replacement, a connection attempt must either use an endpoint
confirmed by the new browser generation or fail explicitly until one arrives.
If an old dial fails after a fresh result arrives, `removed=false` is expected
and the fresh endpoint must remain usable.

### B4 — lifecycle, lock, termination, and restart

Run each action while idle, connected, and transferring:

- background for 30 seconds and for 5 minutes, then foreground;
- lock for 30 seconds, unlock, and foreground;
- swipe-kill the app and relaunch;
- terminate with `devicectl`, relaunch, and start a new diagnostic session;
- tap **Stop** while browser/listener readiness is pending, then **Start**.

Record `WillEnterForeground`/`DidBecomeActive`-equivalent observable events,
listener/browser state, temporary-file cleanup, and whether a transfer was
durably committed before termination. A pre-commit transfer must not be shown
as successful after restart. The app must not retain stale collectors or
duplicate sessions.

On one device run the manual-provisioning lifecycle probe from the signed test
harness while **Stop** races `getManualConnectionInfo()`. Cancellation of the
UI caller alone must not leave manager work detached; stopping the owning kit
must close the manager terminally and every later provisioning method must
return the typed ManagerClosed failure. Repeated close/Stop calls must remain
safe. Before Stop, inspect the returned object through the harness: app ID,
peer ID, device name, fingerprint, pairing QR, and listener port must match the
running kit. Compare `hostAddresses` with a same-moment `getifaddrs` capture.
Every returned value must be an active LAN/AWDL unicast address; IPv6
link-local values must retain their validated interface zone. Loopback,
wildcard, multicast, broadcast, cellular, VPN/tunnel, and down-interface
values are a FAIL. An empty list is valid only when the capture has no eligible
address or enumeration reports an error. A missing secure identity, detached
callback after Stop, or successful post-close operation is also a FAIL.

For each inactive episode, retain the ordered lifecycle and rebind events.
`WillEnterForeground` followed by `DidBecomeActive` may produce only one actual
rebind; if a path-driven rebind already completed while inactive, both later
lifecycle events must show `rebindScheduled=false`. A Control Center or system
dialog path that emits DidBecomeActive without WillEnterForeground must still
schedule one recovery. More than one completed listener rotation for the same
episode is a FAIL.

When testing the write-ready wedge, the first timeout must transition the
connection to Closed and emit exactly one native cancellation. A subsequent
write must fail immediately instead of waiting another 10 seconds. The current
10-second production ceiling remains measurement-dependent and is not itself
accepted or changed by simulator tests.

### B5 — sink failure, collision, and hostile values

Run `PS-T07` and `PS-T08` with an owner-approved test harness or controlled
filesystem condition. Exercise destination collision, unwritable destination,
bounded storage exhaustion, export failure, hostile file names, maximum safe
metadata, invalid UTF-8/wire forms, and scoped IPv6 endpoints.

Every failure must be typed and redacted, leave no escaped or committed partial
file, clean temporary state, and leave the protocol usable for the next valid
transfer. If evidence export itself fails, copy the live JSONL/text and unified
log; do not mark the case passed without reconstructable evidence.

### B6 — KMP consumer and x86_64 coverage

Run `PS-T09` using the checked-in Swift/XCFramework sample on each physical
device. For `ENV-04`, build and launch the x86_64 simulator/runtime on an Intel
host and repeat start/stop plus a JVM-peer connection when networking permits.
Record architecture with `uname -m` and the exact Xcode destination.

## Pass/fail and evidence

Each mandatory case must pass three consecutive times on every required
device/OS/topology cell. Fail on false connected/completed UI, cellular
fallback, missing Local Network error, duplicate session/collector, ghost peer,
unbounded retry, crash/hang, unmatched hash, partial durable file, incorrect
post-restart success, or an export that cannot correlate both peers.

Retain both evidence ZIPs, UI screenshots/video, unified logs, build log,
device/OS inventory, `dns-sd` output, path evidence, source/receiver hashes,
router/AP events, packet capture where required, and the completed catalog
result record.

## Cleanup

Stop the kit on both peers, remove only synthetic received files, uninstall the
development app where required, reset Local Network permission for the next
deny test, restore Wi-Fi/cellular/AP settings, stop log capture, delete any
temporary test profile, and hash the immutable evidence directory.

## Completion checklist

- [ ] Physical device/OS matrix and Intel/x86_64 case completed.
- [ ] Local Network deny/allow and baseline Bonjour cases passed.
- [ ] AWDL path proven independently of the UI.
- [ ] Path rotation, lifecycle, lock, termination, and recovery passed.
- [ ] Sink/hostile-input and KMP consumer cases passed.
- [ ] Both-peer evidence reviewed and signed off independently.
