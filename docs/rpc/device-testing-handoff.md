# RPC device-testing handoff

This is a **test-workstream handoff**, not a release or a statement that physical
devices are qualified. Foundation remains **NOT_READY** and every external HOLD
remains in force. Use the source-specific [qualification status](qualification.md)
and [runtime evidence](vps-lab-runtime-20260929.md), not a green workflow badge alone.

Moving the work to an owner laptop? Use the [laptop continuation instructions](laptop-continuation.md)
for the exact branch, portable evidence, completed/open gates and new-session prompt.

## Package status

**Android replacement verified; physical coordinator still a candidate:** the phone apps now
have bounded private USB control records, source/installed-artifact binding,
actual phone CPU/RSS/thread collectors and failed-session-aware pin retirement.
The JVM lab has an explicit mobile-record decoder; it cannot accept JVM telemetry
as phone evidence. All original app controls remain mandatory, with new totals
of ten Android and ten unit/two UI iPhone controls. The Android build and all ten
controls and all nine real Android shell-file checks passed in the replacement
below. The Linux Android USB coordinator has offline regression coverage and
actual emulator shell integration, **not physical USB/runtime evidence**. Its
[execution instructions and remaining prerequisites](mobile-capacity.md) separate
USB control from actual LAN RPC traffic. The iPhone replacement is still blocked
by cold simulator readiness; its older package below lacks the new mobile controls.
Neither package is a turnkey proof of mobile capacity.

**Android package verified:** [run 36941905738, attempt 1](https://github.com/p2pKit/P2pKit/actions/runs/36941905738),
source `ea566ef4c9fa02ee752dc63c1daed3f052bf29d9`, passed all 127 native ownership
controls, all six command finalizations and all ten supplemental API-24
RPC/Keystore/Activity/resource/file controls, plus **all nine actual shell-v2
create/read/missing/overwrite/Stop controls**. Its x86_64 software emulator booted in
109.050 seconds (emulator 37.2.12, system-image revision 8, acceleration off,
VM property `Dalvik`); natural cleanup and unchanged source were verified.
Both APKs and the matching prepared 24-JAR JVM driver were downloaded and
independently hash-checked, along with all three artifact digests and 20 complete
workflow log entries. This is not maintained ART, physical LAN or mobile capacity.
The exact `app_process`/public `Os.fstat` replacement now works on the actual
API-24 guest, with create-only seals and all inode/owner/mode checks intact.
The read-only probe corroborated unsupported `stat -L`; no SELinux/security
policy changed. See the [complete execution](vps-lab-runtime-20260929.md#october-1-complete-android-shell-integration-and-owner-bundle-verified).

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
existing ten **supplemental API-24 software-emulator** controls and nine additional
real shell-file controls. It does not
change KVM permissions, replace the maintained API-37/24/25 ART gate, request
production signing, publish a release, or send application data off-device.

The independent collector rechecks command receipts, source, actual ten-control
and complete shell results, original artifact hashes and cleanup. It stages files privately and
exposes them atomically only after every required check succeeds. Copy failures,
source drift, missing controls or unproven cleanup cannot produce a binary upload.
The closed manifest contains only source hashes, numeric results, fixed names and
artifact hashes; no identities, invitations, payloads, tokens or raw device logs.

The verified deliverable artifact is
`rpc-android-debug-test-app-ea566ef4c9fa02ee752dc63c1daed3f052bf29d9-1`
and contains only:

- `p2pkit-rpc-android-debug.apk` — the installable debug test application.
- `p2pkit-rpc-android-debug-androidTest.apk` — its matching instrumentation APK.
- `manifest.json` — exact source, scope, test counts and both file hashes/sizes.

The instrumentation package supports the recorded emulator controls; installing
it does not certify an arbitrary physical phone/API level. The separate evidence
artifact retains the same manifest. Actions retention is seven days; preserve the
verified test package before it expires. Never export the job's private state.

### Current verified owner bundle

The isolated clone now preserves a **16-file owner handoff** containing both
current Android APKs, their source-matched prepared JVM driver, the earlier
verified unsigned iPhone app, original manifests/reviews, full same-host JVM
capacity summary, source-version mobile instructions and an offline hash verifier:

```text
/root/projects/p2pkit-feature-prep-20260927-yiDjCB/.git/rpc-bonjour-qualification-20260930.oOYgSoqr/owner-device-handoff-ea566ef4-elw86vae.zip
```

Archive size: **39,392,185 bytes**. SHA-256:
`010b501fd2b7f51df77a3bccc41157a1127e3e99d6da30691c3fa7066b242f69`.
The archive inventory, all copied bytes and a fresh extraction were rechecked;
`python3 -B verify-handoff.py` passed in that extraction. The verifier also has
12 passing positive/negative offline controls. Verify the archive hash **before**
extracting into a new directory, then run that verifier there; it installs nothing
and makes no runtime/qualification decision. Keep the archive before deleting
this workspace or allowing Actions artifacts to expire.

`READ_ME_FIRST.txt` records exact source checkouts and separate remaining work.
`handoff.json` deliberately retains `qualificationComplete: false`: the iPhone
app is older/unsigned, the physical mobile coordinator has not run, and the
Apple/ART prerequisites below remain open. No keys, pins, device identifiers,
private execution receipts or raw application logs are bundled. This is a verified
**device-testing starting package**, not a full mobile-capacity or release pass.

### Earlier checkpoint bundle — preserved, not the current package

The already verified Android APKs, unsigned iPhone app, their original manifests
and independent reviews, and the full JVM capacity summary/resource review have
also been copied into one **offline checkpoint bundle** in the isolated clone:

```text
.git/rpc-bonjour-qualification-20260930.oOYgSoqr/owner-handoff-checkpoint-awp86aco.zip
```

Archive size: **22,173,711 bytes**. SHA-256:
`4193f1c0fbbbcd6f6873c9f632e9c02f6be021d1be32387ecbf1f7bb6b144849`.
The containing clone is `/root/projects/p2pkit-feature-prep-20260927-yiDjCB`.
All copied bytes, archive entries and extracted content hashes were rechecked.
After verifying that archive hash and extracting into a **new directory**, run
`python3 -B verify-handoff.py` there. It performs offline hash verification only:
no installation, signing, network access or qualification decision.

The bundle deliberately says `complete: false`; it is not the final completion
handoff and must not be renamed a full qualification pass. It preserves each
package's own tested source, not a claim that the checkpoint commit built it.
This older bundle contains the earlier eight-control Android package, **not**
the replacement ten-control package described above. Do not use it for mobile
USB/resource qualification. It is retained rather than overwritten.
`READ_ME_FIRST.txt` distinguishes native/ART checks, unfinished mobile capacity
coordinator software, physical/signing prerequisites and external release HOLDs.
No keys, pairing invitations, private native execution state or raw payloads are
included. This local copy avoids losing the approved packages when Actions
artifacts expire; the original per-run downloads below remain reproducible.

## Android installation from the verified package

Use this explicit run ID, commit and attempt, not "latest". Download into a
new unused directory:

```bash
package_dir=$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-rpc-device.XXXXXXXX")
gh run download 36941905738 --repo p2pKit/P2pKit \
  --name rpc-android-debug-test-app-ea566ef4c9fa02ee752dc63c1daed3f052bf29d9-1 \
  --dir "$package_dir"
```

Check that `manifest.json` says `result: PASS`, binds the announced source and
records the supplemental-only scope. Verify each file against its SHA-256 and
byte count before installing:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `p2pkit-rpc-android-debug.apk` | 17,766,503 | `f2b8b65585cb9966d59ba44192e15dc0dac1370c12d2a7c97dbcf5c3d0e8f6e3` |
| `p2pkit-rpc-android-debug-androidTest.apk` | 117,740 | `d6136e48fb2b937910c5825aad4d6c64ed259e1b7dbc408ed697769058c1cf1e` |

The same verified bytes are preserved in this workstream's clone under
`.git/rpc-bonjour-qualification-20260930.oOYgSoqr/actions-36941905738/package.zip`;
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

## Matching prepared JVM driver

The same run exported the separately reviewed artifact
`rpc-mobile-jvm-test-driver-ea566ef4c9fa02ee752dc63c1daed3f052bf29d9-1`:

```bash
driver_dir=$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-rpc-driver.XXXXXXXX")
gh run download 36941905738 --repo p2pKit/P2pKit \
  --name rpc-mobile-jvm-test-driver-ea566ef4c9fa02ee752dc63c1daed3f052bf29d9-1 \
  --dir "$driver_dir"
```

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `p2pkit-rpc-jvm-capacity-driver.zip` | 19,410,066 | `5e53835b8f9d950818d076230de407fa8be25ec22162b84556c291b8e941d32d` |

Its manifest binds the original Android manifest SHA-256
`9bfe63dafb7fb5150408851932e8e5d5b6f96f54b9ef87fa070193cdd98c2c4f`.
All 24 JARs and the complete flat ZIP inventory were independently rechecked.
These same files are in `driver/` in the current owner bundle. Follow the
[exact-source extraction and native execution instructions](mobile-capacity.md);
do not mix driver/APK commits or overwrite an existing distribution. This is a
prepared test driver, **not a measurement of either phone's hosting capacity**.
The exact tested-source checkout predates this final artifact announcement; use
this handoff or the bundle's `READ_ME_FIRST.txt` for package selection, not older
APK links embedded in that historical checkout's documentation.
The real Android capacity coordinator requires a sufficiently provisioned local
Linux x86-64 generator, approved direct LAN and physical USB; a remote VPS path
does not become physical-LAN evidence just because it can reach SSH.

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
all ten unit and two UI XCTest methods on its own simulator, then builds the
unsigned arm64/iOS-15 device app. Both Xcode builds must execute their mandatory
nested provenance verifier. Shutdown and deletion of the exact created
simulator are independently required. No preexisting device is adopted or
retired. The collector rechecks actual method JSON, native receipts/ancestry,
source/tool/artifact hashes and the actual Mach-O platform/minimum OS.

Only a complete pass may atomically expose
`rpc-iphone-unsigned-test-app-<exact-commit>-<attempt>`, containing:

- `p2pkit-rpc-iphone-unsigned.app.zip` — unsigned arm64 device app, **not** an IPA
  or an installation/signing pass.
- `manifest.json` — exact tested source, actual method counts, cleanup and hashes,
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

## Open runner and tooling prerequisites

These are **not completed gates and not all physical-device work**. Preserve
their failures rather than assuming the handoff means every Actions check passed.
The earlier successful ARM executions keep their own recorded source; they do
not admit a later failed readiness prerequisite.

| Gate | Latest verified failure/limitation | What is needed to continue |
| --- | --- | --- |
| Complete Intel/macOS 15/Xcode 26.3 follow-through | [36911837915](https://github.com/p2pKit/P2pKit/actions/runs/36911837915): first runtime inventory took 120.163 s; no simulator was created. Native controls, multicast, host tests and exact Terminal retirement passed. | A supported runner whose CoreSimulator inventory and subsequent cold readiness satisfy the unchanged bounds; the evidence does not establish a unique provider-internal cause. |
| Latest ARM/macOS 26/Xcode 26.5 adapter cleanup | [36908958520](https://github.com/p2pKit/P2pKit/actions/runs/36908958520): 3,046 product cases passed, including 202 Native LAN cases; separate readiness failed at 120.039 s. Actual-adapter lifecycle/cancellation remained blocked. | Successful original-bound fresh-simulator readiness, then the unchanged actual-adapter gate; native unit tests or old ARM passes are not substitutes. |
| Replacement iPhone resource/control app | [36922719322](https://github.com/p2pKit/P2pKit/actions/runs/36922719322): cold readiness failed at 120.291 s during migration, before framework/XCTest/app production; exact cleanup passed. | A suitable native ARM runner, then the original ten unit/two UI controls and device-app producer. The preserved older unsigned app lacks these new controls. |
| Maintained API-37/24/25 ART suite | [36923543329](https://github.com/p2pKit/P2pKit/actions/runs/36923543329): virtualization is exposed, but the nonroot runner cannot read/write the `0660` KVM device. No emulator ran in that probe. | A supported environment already granting required KVM access, or separately authorized narrow access provisioning. No ACL/group/security change has been made. |
| iPhone USB capacity coordinator | `IosUsb` deliberately refuses execution; real-device create-only app-container publication and exact retirement have not been verified. | Device-backed Xcode/USB integration and regression validation. This is remaining engineering work requiring device access, not something that signing the old app alone completes. |

No service killing, prewarming, timeout extension, architecture substitution or
security exception is part of this handoff. The [runtime record](vps-lab-runtime-20260929.md)
retains the complete observations, failed attempts and limits of causal attribution.
The deleted Mac workspace is not an available fallback.

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
   Use the explicit [Android mobile candidate](mobile-capacity.md), not the
   same-host JVM coordinator's host telemetry. The first physical USB/control
   execution remains untested; its fail-closed checks must succeed before a
   workload is meaningful. An iPhone USB adapter is deliberately unavailable
   until Xcode/device create-only publication and cleanup are actually verified.
   Importing 128 public pins is not a capacity measurement.
5. **External acceptance.** Complete the applicable physical, hostile-network,
   independent-review and audit procedures in the [validation handbook](../validation/README.md).
   A phone echo success does not close those separate areas.

The final handoff checklist must distinguish verified container/Actions results,
unresolved software/runner failures and genuine physical/signing prerequisites.
Do not rerun JVM regression merely because it cannot test radio behavior; do
rerun a gate when the relevant source, device/runtime or approved topology changes.
