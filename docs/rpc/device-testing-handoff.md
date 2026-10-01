# RPC device-testing handoff

This is a **test-workstream handoff**, not a release or a statement that physical
devices are qualified. Foundation remains **NOT_READY** and every external HOLD
remains in force. Use the source-specific [qualification status](qualification.md)
and [runtime evidence](vps-lab-runtime-20260929.md), not a green workflow badge alone.

## Package status

**Android package verified:** [run 36857064456, attempt 1](https://github.com/p2pKit/P2pKit/actions/runs/36857064456),
source `489b1f92caecce3b60df2647795de2c2be24c763`, passed all 124 native ownership
controls, all six command finalizations and all eight supplemental API-24
RPC/Keystore/Activity controls. Its x86_64 software emulator actually booted in
100.449 seconds (emulator 37.1.11, system-image revision 8, acceleration off,
VM property `Dalvik`); natural cleanup and unchanged source were verified.
Both APK byte counts and SHA-256 hashes were independently rechecked after
download. This is not maintained ART, physical LAN or mobile-capacity evidence.

The first [delivery attempt](https://github.com/p2pKit/P2pKit/actions/runs/36853495799)
built both APKs with verified native finalization, but a diagnostic-schema
integration error stopped the coordinator before the emulator ran. The exact
build-purpose name is now registered in the existing closed diagnostic validator;
the reproduction and negative controls pass. The [follow-up](https://github.com/p2pKit/P2pKit/actions/runs/36854821191)
completed all six commands, including the supplemental AVD, with native
finalization, but post-execution package verification still failed. A reproduced
APK/report-size mismatch is corrected and the fresh collection above passed.
Neither failed attempt provides an approved handoff package.
The earlier Mac was deleted; its unsigned iPhone app cannot be recovered from
that workspace. A [fresh native-ARM handoff workflow](../../.github/workflows/rpc-ios-handoff.yml)
is now implemented and its offline controls pass. Its
[first hosted attempt](https://github.com/p2pKit/P2pKit/actions/runs/36858137736)
passed native admission but failed inside `phone-controls`; no app was exported.
A [phase-level diagnostic rerun](https://github.com/p2pKit/P2pKit/actions/runs/36860697654)
verified framework production and exact simulator shutdown/deletion, but the
unchanged 120-second cold-boot readiness bound failed during migration/system-app
startup. No phone XCTest or device build ran. The
[cold-first follow-up](https://github.com/p2pKit/P2pKit/actions/runs/36863266184)
also exceeded the original deadline before compilation. Its 125 native controls,
11 outer command finalizations and exact simulator cleanup passed independently;
no phone tests or app export occurred. A bounded read-only process/CPU observer
now records intervals during that same cold prerequisite, not a retry, longer
deadline or warm-up. Those failed attempts remain preserved.

**Fresh unsigned iPhone package verified:** [36869803924, attempt 1](https://github.com/p2pKit/P2pKit/actions/runs/36869803924),
source `834c02c9a7819754dcf8a9a2db62306e3cfc9fe8`, passed all **128 native
controls**, **seven unit/two UI XCTest methods**, both nested framework-provenance
checks and all eleven outer finalizations. Exact simulator shutdown/deletion
and unchanged source were verified. Independent archive inspection checked all
three Mach-O images, not just the small launcher: each is unsigned **arm64,
iOS platform 2, minimum iOS 15.0, SDK 26.5**, never a simulator substitution.

The boot controller recorded exit zero under its unchanged monotonic deadline
checks. The exported UTC command interval is 118.254 seconds; the diagnostic
observer's later `finish()` interval is 125.825906 seconds. These use different
endpoints/clocks; the exported record lacks the decision's monotonic timestamp,
so the difference is **not independently attributed**. Neither an extended
readiness allowance nor an observer-caused boot fix is claimed. This phone
result does not resolve the separate Intel readiness failure.

Supported-host checks remain separate work. This is a recovered unsigned
`.app`, **not** an installable signed iPhone package, full Apple matrix pass or
physical/mobile-host qualification.

The feature-only [Android handoff workflow](../../.github/workflows/rpc-android-handoff.yml)
requires the explicit `[rpc-android-handoff]` marker. It uses a new full-history,
untagged checkout, private SDK/state and the unchanged native executor. Its
six exact commands establish native admission and Java versions, install the
required public SDK packages, produce both same-source APKs, then execute the
existing eight **supplemental API-24 software-emulator** controls. It does not
change KVM permissions, replace the maintained API-37/24/25 ART gate, request
production signing, publish a release, or send application data off-device.

The independent collector rechecks command receipts, source, actual eight-control
result, original artifact hashes and cleanup. It stages files privately and
exposes them atomically only after every required check succeeds. Copy failures,
source drift, missing controls or unproven cleanup cannot produce a binary upload.
The closed manifest contains only source hashes, numeric results, fixed names and
artifact hashes; no identities, invitations, payloads, tokens or raw device logs.

The verified deliverable artifact is
`rpc-android-debug-test-app-489b1f92caecce3b60df2647795de2c2be24c763-1`
and contains only:

- `p2pkit-rpc-android-debug.apk` — the installable debug test application.
- `p2pkit-rpc-android-debug-androidTest.apk` — its matching instrumentation APK.
- `manifest.json` — exact source, scope, test counts and both file hashes/sizes.

The instrumentation package supports the recorded emulator controls; installing
it does not certify an arbitrary physical phone/API level. The separate evidence
artifact retains the same manifest. Actions retention is seven days; preserve the
verified test package before it expires. Never export the job's private state.

## Android installation from the verified package

Use this explicit run ID, commit and attempt, not "latest". Download into a
new unused directory:

```bash
package_dir=$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-rpc-device.XXXXXXXX")
gh run download 36857064456 --repo p2pKit/P2pKit \
  --name rpc-android-debug-test-app-489b1f92caecce3b60df2647795de2c2be24c763-1 \
  --dir "$package_dir"
```

Check that `manifest.json` says `result: PASS`, binds the announced source and
records the supplemental-only scope. Verify each file against its SHA-256 and
byte count before installing:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `p2pkit-rpc-android-debug.apk` | 17,750,119 | `94db6d54848f163b27ace1ebbf32badb4e4c01652a3c6abd137aa51752342f3a` |
| `p2pkit-rpc-android-debug-androidTest.apk` | 107,576 | `fbf84c0a12b6f7cbe0dbae3f2292b2be293f2f50ccd2d21c05472b05500e37fb` |

The same verified bytes are preserved in this workstream's clone under
`.git/rpc-bonjour-qualification-20260930.oOYgSoqr/android-handoff-36857064456-attempt1/`;
they are not committed to Git. Select the actual owner-approved device explicitly:

```bash
adb devices
adb -s "$ANDROID_SERIAL" install "$package_dir/p2pkit-rpc-android-debug.apk"
adb -s "$ANDROID_SERIAL" shell am start \
  -n dev.p2pkit.sample.android/.rpclab.RpcLabActivity
```

The launcher is **P2pKit RPC Lab**, distinct from the existing P2P launcher. Use a
fresh test device/profile. If an existing package uses a different debug signer,
stop: do not silently uninstall it or erase its trust/application data. No
production/custodian keys are needed. Do not export the ADB device serial.

## Fresh iPhone handoff scope

The explicit `[rpc-ios-handoff]` request uses native ARM/macOS 26/Xcode 26.5,
a fresh full-history untagged checkout and the existing process-local audit
session bootstrap. The unchanged native executor must pass its complete control
inventory and finalize all eleven ordered commands. This app-only workflow
does **not** replace or remove either Apple matrix cell, multicast, the dedicated
ARM adapter cancellation/cleanup gate or any release/physical-capacity gate.

The phone controller first requires one fresh simulator's actual cold readiness
within the original 120-second bound, before spending resources on compilation.
It then produces the current-source framework, executes
all seven unit and two UI XCTest methods on its own simulator, then builds the
unsigned arm64/iOS-15 device app. Both Xcode builds must execute their mandatory
nested provenance verifier. Shutdown and deletion of the exact created
simulator are independently required. No preexisting device is adopted or
retired. The collector rechecks actual method JSON, native receipts/ancestry,
source/tool/artifact hashes and the actual Mach-O platform/minimum OS.

Only a complete pass may atomically expose
`rpc-iphone-unsigned-test-app-<exact-commit>-<attempt>`, containing:

- `p2pkit-rpc-iphone-unsigned.app.zip` — unsigned arm64 device app, **not** an IPA
  or an installation/signing pass.
- `manifest.json` — exact tested source, nine method counts, cleanup and hashes,
  with physical installability, Apple matrix and mobile capacity all false.

The archive rejects provisioning profiles and signature directories. Raw XCTest
bundles, private native records, simulator identities, credentials and payloads
are not uploaded. Failed/partial runs cannot export an app. The artifact has
seven-day retention and still requires independent review before handoff.
Manifest schema 2 additionally retains source-bound tool-stage, boot-status and
nested-producer diagnostic categories. Those observations are explicitly not
test/ownership admission and cannot populate a failed run's `controls` or app.

## iPhone installation boundary

Download the exact verified package into a new directory before its seven-day
Actions retention expires:

```bash
iphone_dir=$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-rpc-iphone.XXXXXXXX")
gh run download 36869803924 --repo p2pKit/P2pKit \
  --name rpc-iphone-unsigned-test-app-834c02c9a7819754dcf8a9a2db62306e3cfc9fe8-1 \
  --dir "$iphone_dir"
```

Verify the source and `PASS` manifest before unpacking:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `p2pkit-rpc-iphone-unsigned.app.zip` | 4,661,051 | `f1da24d09a771be16f1c4137df056ae551a0c5efa53c23ca6e923d32383c8e7a` |

The same bytes and independent reviews are preserved privately in this clone's
`.git/rpc-bonjour-qualification-20260930.oOYgSoqr/ios-handoff-36869803924-attempt1/`.
The bundle identifier is `dev.p2pkit.rpc.phonelab`. Keep this original unsigned
archive unchanged; record the separate signed build's source, signing method
and hash in owner evidence. Do not pretend its post-signing hash still matches
the unsigned archive, or install an unsigned archive as though it were an IPA.

The maintained [phone lab project and build instructions](../../samples/p2p-sample-rpc/phone-ios/README.md)
describe its fresh, source-verified framework, XcodeGen project and actual simulator
controls. Physical installation requires your development team/provisioning and
the device's local trust/Developer Mode approval. Keep those credentials and
provisioning profiles local; do not put them in Git, issue text or public evidence.
The source project at the recorded commit remains the maintained signing/build
input; the hosted job does not export a development identity or provisioning
profile. A source project or simulator pass alone is not a device-installation pass.

## Device-only work: do not repeat unrelated hosted suites

The [full 30-minute same-host JVM workload at `a658740d`](vps-lab-runtime-20260929.md#october-1-full-rate-jvm-workload-and-observed-resource-review-passed)
has now been independently verified: **2,304,000 replies, zero misses/errors,
p95/p99 4/21 ms**, bounded observed resources and exact cleanup, plus the separate
20-call one-MiB test. Do not repeat that same-host run merely to start phone
interoperability. It does **not** replace the actual mobile-host workloads below.
The package sources above remain their own exact verified builds, not a claim
that every later commit or every Apple/ART gate passed.

Record device model, OS/API, tested app/source hashes, approved topology and
numeric results in private owner evidence. Share a sanitized summary, not keys,
pairing invitations, device serials, payloads or raw network/application logs.

1. **Physical LAN and roles.** On an approved organization LAN, run Android host
   with iPhone client, then iPhone host with Android client. Follow the phone
   lab's explicit interface/CIDR/endpoint selection and local pairing approval.
   Confirm host identity; unapproved clients cannot invoke procedures. No
   automatic mesh, cellular, public relay, VPN or SSH-tunnel substitution.
2. **Permission/network behavior.** Exercise real local-network permission
   approval/denial/revocation, foreground loss, locking/sleep, Wi-Fi disconnect
   and host restart. Confirm explicit state/errors and no unsafe replay. Capture
   the required local-only traffic evidence through the approved procedure.
3. **Real interoperability.** Run typed 1-KiB calls and the separate 20-call
   one-MiB request/reply experiment at concurrency two in both host directions.
   Check cancellation, Stop, reconnection and revoked trust with independent
   identities. The apps' interactive tests are not the full capacity workload.
4. **Actual mobile hosting capacity.** Each mobile host still needs its own
   authenticated 128-client, ten-calls/second/client, full 30-minute execution,
   complete scheduling accounting and **that phone's** resource/cleanup evidence.
   The current JVM lab coordinator is not a turnkey mobile coordinator; it binds
   JVM host telemetry. Do not point it at a phone and relabel the evidence. Secure
   mobile provisioning/telemetry integration is still required before this gate
   can be executed. Importing 128 public pins is not a capacity measurement.
5. **External acceptance.** Complete the applicable physical, hostile-network,
   independent-review and audit procedures in the [validation handbook](../validation/README.md).
   A phone echo success does not close those separate areas.

The final handoff checklist must distinguish verified container/Actions results,
unresolved software/runner failures and genuine physical/signing prerequisites.
Do not rerun JVM regression merely because it cannot test radio behavior; do
rerun a gate when the relevant source, device/runtime or approved topology changes.
