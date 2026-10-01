# RPC device-testing handoff

This is a **test-workstream handoff**, not a release or a statement that physical
devices are qualified. Foundation remains **NOT_READY** and every external HOLD
remains in force. Use the source-specific [qualification status](qualification.md)
and [runtime evidence](vps-lab-runtime-20260929.md), not a green workflow badge alone.

## Package status

At this checkpoint, the fresh Android delivery workflow is implemented and its
offline controls pass. **No new hosted APK artifact has been verified yet.**
The first [delivery attempt](https://github.com/p2pKit/P2pKit/actions/runs/36853495799)
built both APKs with verified native finalization, but a diagnostic-schema
integration error stopped the coordinator before the emulator ran. The exact
build-purpose name is now registered in the existing closed diagnostic validator;
the reproduction and negative controls pass. The [follow-up](https://github.com/p2pKit/P2pKit/actions/runs/36854821191)
completed all six commands, including the supplemental AVD, with native
finalization, but post-execution package verification still failed. A reproduced
APK/report-size mismatch is corrected; fresh successful collection is still
required. Neither failed attempt provides an approved handoff package.
The earlier Mac was deleted; its unsigned iPhone app cannot be recovered from
that workspace. A [fresh native-ARM handoff workflow](../../.github/workflows/rpc-ios-handoff.yml)
is now implemented and its offline controls pass; hosted execution is pending.
Supported-host checks remain separate work. An unsigned `.app` is not an
installable signed iPhone package.

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

Once verified, the deliverable artifact is named
`rpc-android-debug-test-app-<exact-commit>-<attempt>` and contains only:

- `p2pkit-rpc-android-debug.apk` — the installable debug test application.
- `p2pkit-rpc-android-debug-androidTest.apk` — its matching instrumentation APK.
- `manifest.json` — exact source, scope, test counts and both file hashes/sizes.

The instrumentation package supports the recorded emulator controls; installing
it does not certify an arbitrary physical phone/API level. The separate evidence
artifact retains the same manifest. Actions retention is seven days; preserve the
verified test package before it expires. Never export the job's private state.

## Android installation after artifact verification

Use the final handoff's explicit run ID, commit and attempt, not "latest":

```bash
gh run download RUN_ID --repo p2pKit/P2pKit \
  --name rpc-android-debug-test-app-COMMIT-ATTEMPT --dir rpc-device-package
```

Check that `manifest.json` says `result: PASS`, binds the announced source and
records the supplemental-only scope. Verify each file against its SHA-256 and
byte count before installing. Select the actual owner-approved device explicitly:

```bash
adb devices
adb -s "$ANDROID_SERIAL" install rpc-device-package/p2pkit-rpc-android-debug.apk
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

The existing phone controller produces the current-source framework, executes
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

## iPhone installation boundary

The maintained [phone lab project and build instructions](../../samples/p2p-sample-rpc/phone-ios/README.md)
describe its fresh, source-verified framework, XcodeGen project and actual simulator
controls. Physical installation requires your development team/provisioning and
the device's local trust/Developer Mode approval. Keep those credentials and
provisioning profiles local; do not put them in Git, issue text or public evidence.
Final handoff must identify any freshly produced project/app and its tested
commit. A source project or simulator pass alone is not a device-installation pass.

## Device-only work: do not repeat unrelated hosted suites

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
