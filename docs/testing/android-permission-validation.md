# API37 LAN permission validation

Issue [#372](https://github.com/p2pKit/P2pKit/issues/372) permits an eligible
**emulator**. It does not inherently require physical hardware. The successful
production repair is preserved; this explicit lane exercises the missing live
revocation boundary rather than rewriting the manager or sample flow.

## Explicit lane and exact source

`.github/workflows/android-permission-validation.yml` supports no-input
`workflow_call` and `workflow_dispatch`. The maintained dispatcher may call it as
`android-permission-diagnostic`; it is not an ordinary CI matrix component or a
release gate. Its separate entry point is
`scripts/run-android-permission-validation.py`. The API35 UI command keeps only
`317`, `324`, and `both`; #372 cannot be selected through that CLI.

The shared source-owned bootstrap builds the exact debug app/test APKs and
maintained JVM CLI distribution, with the checked-in wrapper, strict dependency
locks/checksums, Java17/21 and NDK29.0.14206865. It inspects actual APK manifests,
checks all five explicit runners, hashes both APKs, records source commit/tree,
and creates one fresh API37 Google APIs x86_64 AVD/private adb server. Installed
APK hashes must match. Installed emulator/image revisions and actual runtime
properties are retained. No personal device, existing AVD or prior installation
is adopted. Only the existing public evidence-recipient key is needed; raw
synthetic output is encrypted by the native-owned `ci_evidence.py` exporter.

The newly created, unbooted AVD requests a **2-GiB userdata partition**, following
the maintained RPC Android fixture's bounded allocation pattern. Only its fresh
`config.ini` is changed before first launch; SDK/system images, existing AVDs,
host caches and personal data are never resized or deleted. The generated config
and actual admitted guest `df -k /data /data/local/tmp` observation are retained
privately. This prepares space for APK staging/install and synthetic evidence;
it is not storage qualification, and a successful allocation/install is not
permission acceptance. No boot, instrumentation or retirement bound is extended.

Before either API35 UI or API37 permission instrumentation, the shared bootstrap
requires the boot flag **and** real `input`, `activity`, `package` and `settings`
binder services. The original 180-second boot deadline also bounds identity
checks and the single unlock command; a failed unlock is not retried. A boot
property alone does not establish that Android's system services are usable.
Pre-admission failure retains a fixed, read-only service/process/property and
filtered system-error snapshot privately, within a separate 20-second diagnostic
bound. Before those queries, the same bound covers exact generated-AVD identity
and live original-emulator checks; an unverified/dead guest is `NOT_CAPTURED`.
That retention cannot admit the guest or run any test. Persistent missing
services remain a failed setup, not a permission result or an unavailable-runtime
claim; no APK is installed before this admission completes.

## Real campaign, not shell network identity

The existing `LanPermissionRuntimeInstrumentation` gains explicit modes; its
original no-mode caller and `NOT_EXECUTED` revocation terminal remain separate.

1. Fresh target37 app, ordinary target UID, no prior Nearby grant; require actual
   API37/REL/preview0 and the platform's dangerous LAN permission definition.
   Read the mandatory flag through the public `AconfigPackage`, retaining the
   same real object for false-default then true-default reads. Both must return
   true. Retain package/grant, active-module, compat and aconfig shell observations
   separately; absence/errors remain visible, not guessed values.
2. Exercise the real default permission manager and denied feature gate; a raw
   socket to the **already-listening** host control endpoint must be denied.
   `10.0.2.2` is the guest's non-loopback host gateway, not Android loopback or adb
   forwarding. Its eligibility is established by actual denied/granted behavior,
   not assumed from the address alone.
3. Use the sample's actual permission dialog, recreate while the request is
   outstanding, grant through the UI, and require the original manager/VM to
   observe the grant without automatic replay. Complete the raw nonce exchange
   and pinned authenticated bidirectional P2pKit session with the maintained JVM
   peer. The host verifies final, drained CLI output, not an early send snapshot.
4. Persist a source/UID/process/install-bound checkpoint **after duplex traffic**,
   then signal the host. Only then issue the real OS `pm revoke` command. Never
   grant through shell identity or use force-stop as a revocation surrogate.
5. If the original process survives, require that exact manager to report denial,
   reject a previously inactive feature, deny a new raw socket, and preserve
   denial/no replay across actual Activity recreation. If Android kills it,
   missing instrumentation output is **not** success: launch a separate reentry
   mode in the unchanged installation and require the platform's
   `ApplicationExitInfo.REASON_PERMISSION_CHANGE` for the original PID/UID after
   its checkpoint. The new manager, raw socket and explicit sample Start must
   remain denied. This branch never claims a surviving original manager.

The original 90-second instrumentation body bounds remain; the host campaign is
bounded separately. Failures still trigger every owned retirement attempt. The
host never reads exit trace streams, unrelated app storage or credentials.

If the original, fully drained command stream contains no instrumentation
records, the controller records `NO_INSTRUMENTATION_OUTPUT` and fails. This
classifies output only: it does not prove whether the runner body started or
attribute a platform/service failure. It never authorizes a launch retry or
substitutes for traffic, permission or terminal evidence. Invalid/missing-file
output from optional record retrieval remains a private command capture, not a
misleading `.json` evidence record.

On a live-campaign failure, a source-owned callback revalidates the original live
emulator and exact generated AVD before private diagnostics. The same20-second
diagnostic work budget covers identity and fixed read-only queries: at most200
filtered system/ActivityManager/ServiceManager/low-memory/audit log entries,
service list, system-server PID, native `cmd activity get-current-user`, and
fixed aggregate memory-pressure/cgroup counters. No root, dynamic PID paths,
app-storage search, memory/image change, or instrumentation replay is used.
Missing observers stay explicit; failed diagnostics preserve the original
failure. Existing exact-owned-leader retirement tails are unchanged, not an
acceptance grace period or a claim of a hard20-second wall-clock cleanup bound.

## Acceptance boundary

A completed result is `HARNESS_PASS_PENDING_PROFILE_REVIEW`, not issue closure or
full-release qualification. Independently review the exact loaded permission
module, mandatory-flag/generated-cache and compat semantics, original route,
no-prior-Nearby installation, traffic, revocation branch and cleanup evidence.
Matching public flag reads alone are **not** generated-cache or enforcement
proof. Conversely a bypassed raw route, unsupported public reader, unrelated
process death, stale installation, partial output or an inconclusive profile
must not become a pass. A suitable runtime is unqualified until this executes;
it is not declared unavailable merely because local KVM is absent.

No physical-phone/OEM behavior, legacy target36, Android16 opt-in or wider test
campaign is claimed. Offline parser tests and compilation do not execute Android:

```sh
python3 -B scripts/tests/run-android-permission-validation-test.py
python3 -B scripts/tests/run-android-ui-validation-test.py
python3 -B scripts/tests/run-android-art-smoke-test.py
```
