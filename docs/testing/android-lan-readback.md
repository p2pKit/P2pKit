# API37 LAN readback content contract

Refs [#372](https://github.com/p2pKit/P2pKit/issues/372). This is an additive
**source/offline preparation**, not the missing runtime campaign. The existing
production permission correction is not changed. The test-only collector is now
authored, but not compiled or executed. Loaded-platform qualification, the
ordinary-LAN route and live revoke/reentry still need implementation/execution.

[`android_lan_readback.py`](../../scripts/android_lan_readback.py) has one pure
API: `validate_readback(original_bytes, expected_binding)`. It performs no I/O,
Android calls, process launch, receipt admission or automatic test dispatch.
There is no runtime `trusted=true` or qualification switch. The caller supplies
the expected binding separately; supplying matching invented facts cannot make
the record authoritative. All outputs, even matching true/true, retain:

```text
evidence_level = RECORDED_INPUT_ONLY
runtime_state = COMPAT_STATE_UNPROVEN
qualification = HOLD_UNQUALIFIED_RUNTIME_SEMANTICS
permission_enforcement = NOT_PROVEN
same_instance_revocation = NOT_EXECUTED
```

## Closed record shape

The schema is `p2pkit-android-lan-readback/1`, mode `profile-readback`.
At most 16 KiB of UTF-8 JSON is parsed. Duplicate fields, unknown fields,
truncation, trailing records, floats/nonfinite numbers and mistyped values fail
closed. Original bytes remain available without truncation, also on failure;
the caller must keep them privately with the original receipts. The result's
default representation omits those bytes. No private record is a Git artifact.

Top-level keys are exactly `schema`, `mode`, `binding`, `readerClass`,
`flagPackage`, `flagName`, `events`. The public class/package/flag are exactly:

```text
android.os.flagging.AconfigPackage
android.permission.flags
access_local_network_permission_enabled
```

The binding is repeated at load and each read. It contains `token`,
`sourceCommit`, `sourceTree`, `appApkSha256`, `testApkSha256`, `profileSha256`,
`installId`, `packageName`, `user`, `uid`, `pid`, `processStartElapsedMillis`,
`installEpochMillis`, `sdkInt`, `targetSdk`, `codename`, `previewSdkInt`,
`buildDirty`. This initial declared profile is primary user0, application UID
10000–19999, the existing sample package, SDK37/target37/REL/preview0 and clean
BuildInfo. It is not another app identity or a fourth instrumentation component.
Commit/tree and APK/profile hashes are references, not proof they were observed
or loaded. The source tree remains host-bound to APK provenance, not independently
readable from ART. `installId` must eventually name the coordinator's fresh owned
installation episode; it is not an Android platform installation-ID API.

`events` contains one `load`, then two `read` events with literal boolean defaults
`false`, then `true`. Each event has exactly `phase`, `binding`, `readerId`,
`start`, `end`, `outcome`; reads additionally have `default`. Both clock records
have integer `epochMillis` and `elapsedMillis`. Their individual ordering,
install-epoch and process-elapsed lower bounds are checked separately. They are
never compared across clock domains or treated as an atomicity/freshness proof.
This data check sets no new runtime deadline or acceptable clock-skew tolerance.

Load outcome is `{"kind":"LOADED"}` with a 32-lowercase-hex `readerId`.
Read outcome is `{"kind":"RETURNED","value":true}` (or false) with the same
label. The producer must retain the actual same Java object directly;
matching serialized labels alone cannot prove it. The focused test's `packet()`
is an explicitly synthetic example of this shape, not captured Android evidence.

Errors instead use `{"kind":"ERROR","errorType":"<Java class>","errorCode":null}`.
For public `AconfigStorageReadException`, `errorCode` must be integer0–4; other
errors have no such code. A load error has null `readerId`; a read error retains
the loaded label. Collection ends at the error: no later successful event may
rehabilitate it. All errors HOLD, including public-surface/access failures;
none establishes clean flag absence or a false value.

| Declared false-default / true-default returns | Content result only |
| --- | --- |
| true / true | `MATCHING_DECLARED_TRUE`; runtime qualification still HOLD |
| false / false | `MATCHING_DECLARED_FALSE`; cannot admit mandatory-true enforcement |
| false / true | `LOOKUP_UNRESOLVED_OR_DRIFT` HOLD |
| true / false | `INCONSISTENT_OR_DRIFT` HOLD |

## Authored ordinary-UID collector — not runtime evidence

The existing LAN instrumentation now selects only explicit `mode=profile-readback`
for [this collector](../../samples/p2p-sample-android/src/androidTest/java/dev/p2pkit/sample/android/runtime/LanPermissionProfileReadback.kt).
The mode accepts exactly eight string arguments: `mode`, `token`, `sourceCommit`,
`sourceTree`, `appApkSha256`, `testApkSha256`, `profileSha256`, `installId`.
The hex lengths are those above. No arbitrary command/path/deadline or privileged
identity is accepted. Unknown modes/extra arguments fail. The existing no-mode
peer invocation retains its five arguments, original stages and terminal oracle.
There is no fourth manifest component or change to the closed 317/324 selectors.

The separate [API37 adapter](../../samples/p2p-sample-android/src/androidTest/java/dev/p2pkit/sample/android/runtime/Api37LanFlagReader.kt)
calls the public `AconfigPackage` directly. Its erased entry signatures keep the
flagged classes out of the older entry path. A missing public class/method/access
becomes an error, never a hidden-delegate/reflection fallback. The shared
[recorder](../../samples/p2p-sample-android/src/acceptanceTestSupport/java/dev/p2pkit/sample/android/runtime/LanReadbackCollector.kt)
loads once, retains that exact object, and passes it to false- then true-default
reads. It stops reader calls at the first exception and retains the original
failure even if error description, identity, timing or retention later fails.
The Android adapter records only the public error class/code, not its message.

The process actually re-reads UID/PID/start, package-manager installation epoch,
application UID/target and SDK/codename/preview plus `BuildInfo` around each API
call. User0/application UID10000–19999, runtime37/target37/REL/preview0 and clean
matching source are required. Epoch and elapsed observations are ordered
separately, with their own installation/process lower bounds. A **fixed 30-second
observation interval**, including successful retention, rejects backward/late
observations. It cannot interrupt a blocked synchronous Android/filesystem call
and is **not** an admitted host/profile execution envelope. The host coordinator
must separately bound original command execution, EOF, return and retirement;
its implementation/whole-profile budget remains outstanding. No existing
peer/CLI/UI timeout is increased by this source addition.

Source tree, APK hashes, profile hash and installation-episode ID are explicitly
**host-supplied references**. They are not measured ART/APK/loaded-module facts.
The future coordinator must bind them to the original successful producer,
installed APK readback, actual profile and fresh owned installation. Repeated
references or matching public reads do not prove that binding or cache validity.

The adapter creates a new private 0700 `no_backup/lan-readback-<token>` directory
and an exclusive no-follow 0600 `readback.json`. It writes at most16KiB, checks
same-descriptor bytes/EOF/identity and closes that owned descriptor once; a
write/read/close failure cannot return a successful collection. No evidence
contents are printed or uploaded, and no existing file is replaced or deleted.
This is not power-loss durability, an atomic platform snapshot or whole-process
retirement. Failure may leave a partial private record; retain it with the
original terminal/command evidence rather than interpreting it as complete.

The distinct terminal uses test `publicFlagProfileReadback` and
`p2pkitReadbackOutcome=RECORDED_UNQUALIFIED` or `FAILED`, never the old peer PASS.
Even completed collection retains qualification
`HOLD_UNQUALIFIED_RUNTIME_SEMANTICS`, enforcement `NOT_PROVEN` and revocation
`NOT_EXECUTED`. A well-formed file alone is insufficient: retention/return can
still fail afterward. The host must also admit the original terminal and timing.

### Authored tests versus executed checks

`src/acceptanceTestSupport/java` is included only in the Android host-test and
instrumentation source sets, not `main`. The
[20 recorder tests](../../samples/p2p-sample-android/src/test/java/dev/p2pkit/sample/android/runtime/LanReadbackCollectorTest.kt)
use that same recorder with synthetic reader/clock/identity/retention ports. They
cover exact call/object/default order, all four pairs, serialized shape, errors,
boundary drift, expiry, cancellation and retention failures. They are
**authored but uncompiled/unexecuted** under the no-local-build/held-dispatch
instruction. No source-string check substitutes for executing them.

When hosted execution is legitimately admitted, the focused test command is:

```bash
./gradlew :p2p-sample-android:testDebugUnitTest \
  --tests dev.p2pkit.sample.android.runtime.LanReadbackCollectorTest --console=plain
```

Use the owned hosted executor and its actual toolchain/strict/retirement policy,
not an unowned local invocation. Share the fresh app/test producer with compatible
317/324 work: `:p2p-sample-android:assembleDebug`,
`:p2p-sample-android:assembleDebugAndroidTest`, and
`:p2p-sample-android:retainDebugAcceptanceArtifacts`. Those builds must verify
the selected public SDK/error surface and unchanged three-component manifest.
Host tests do not execute the Android adapter or establish actual flag semantics.

## Verification and the still-missing bridge

Run the dependency-free controls explicitly:

```bash
python3 -I -B -S scripts/tests/android-lan-readback-test.py -v
```

These test malformed records, the four pairs, order/type/default errors,
cross-source/APK/profile/install/UID/PID drift, error and clock records, and the
inability to promote even consistently fabricated input. They do not execute
Android or re-prove the unchanged legacy compat model. This helper is not wired
into a runtime or ordinary hosted gate yet; the future coordinator must integrate
the command and its independent review when that path becomes executable.

The next separate increment is the original command/profile custody coordinator,
then actual collector execution with qualified public stubs/loaded implementation.
The selected source's defaults, cached membership,
mapped bytes and consumer getter/initialization behavior require their own
binding. Matching reads do not prove storage validity, generated getter state,
cache refresh, loaded modules, compat resolution or real permission enforcement.
The retained source investigation is linked in the
[#372 checkpoint](https://github.com/p2pKit/P2pKit/issues/372#issuecomment-5708744916).
No more general AOSP acquisition is needed for the authored collector/content layer.

Preserve `android_compat_model.py` as `MODEL_ONLY` and the old peer's
`p2pkitSameInstanceRevocation=NOT_EXECUTED`. A separate live-revoke/reentry mode
must prove the surviving original manager or attributable normal permission
death followed by unchanged-install denied reentry; a force-stop, new manager
or manufactured old terminal PASS is not a substitute. Actual fresh no-Nearby
install, denial, grant, authenticated bidirectional **ordinary LAN** traffic,
revocation/lifecycle and bounded retirement remain required. The old loopback/
emulator-gateway route is not renamed into that proof. Suitable runtime/host
inputs remain unqualified, not proven unavailable. Physical phones stay deferred.
