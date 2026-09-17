# API37 LAN readback content contract

Refs [#372](https://github.com/p2pKit/P2pKit/issues/372). This is an additive
**source/offline preparation**, not the missing runtime campaign. The existing
production permission correction is not changed. The collector, loaded-platform
qualification, ordinary-LAN route and live revoke/reentry still need execution.

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
label. The eventual producer must check the actual same Java object directly;
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

## Verification and the still-missing bridge

Run the dependency-free controls explicitly:

```bash
python3 -I -B -S scripts/tests/android-lan-readback-test.py -v
```

These test malformed records, the four pairs, order/type/default errors,
cross-source/APK/profile/install/UID/PID drift, error and clock records, and the
inability to promote even consistently fabricated input. They do not execute
Android or re-prove the unchanged legacy compat model. This helper is not wired
into a runtime or ordinary hosted gate yet; the future collector must integrate
the command and its independent review when that path becomes executable.

The next separate increment is an ordinary-UID public reader on one actual
loaded instance, with original command/profile custody and qualified public
stubs/loaded implementation. The selected source's defaults, cached membership,
mapped bytes and consumer getter/initialization behavior require their own
binding. Matching reads do not prove storage validity, generated getter state,
cache refresh, loaded modules, compat resolution or real permission enforcement.
The retained source investigation is linked in the
[#372 checkpoint](https://github.com/p2pKit/P2pKit/issues/372#issuecomment-5708744916).
No more general AOSP acquisition is needed to implement this content layer.

Preserve `android_compat_model.py` as `MODEL_ONLY` and the old peer's
`p2pkitSameInstanceRevocation=NOT_EXECUTED`. A separate live-revoke/reentry mode
must prove the surviving original manager or attributable normal permission
death followed by unchanged-install denied reentry; a force-stop, new manager
or manufactured old terminal PASS is not a substitute. Actual fresh no-Nearby
install, denial, grant, authenticated bidirectional **ordinary LAN** traffic,
revocation/lifecycle and bounded retirement remain required. The old loopback/
emulator-gateway route is not renamed into that proof. Suitable runtime/host
inputs remain unqualified, not proven unavailable. Physical phones stay deferred.
