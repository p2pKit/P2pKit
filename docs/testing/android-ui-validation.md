# Android rendered UI validation

This opt-in lane executes the existing repaired production UI for issues **#317**
and **#324**. It is not the API37 LAN permission lane, a physical-phone campaign,
an API29/OEM result, or a replacement for release CI.

## Run the exact committed source

The workflow `.github/workflows/android-ui-validation.yml` accepts `case=317`,
`case=324`, or `case=both`. Before the workflow exists on the default branch, push
an authorized `work/**` candidate with `[android-ui-validation]` in its tip commit
message to select the same lane. Ordinary branch pushes do not run an emulator.

The hosted job uses Linux KVM, a fresh Google APIs API35 x86_64 AVD, targetSdk37,
Java17/21, the checked-in Gradle wrapper, strict dependency locks/checksums, and
NDK **29.0.14206865**. The exact installed emulator/image revisions are retained;
this lane does not claim the API37 runtime/module/flag profile. Dependencies and
SDK licenses must already be authorized; the workflow does not accept licenses.

The controller refuses dirty source, builds both APKs, inspects their actual
binary manifests, checks the exact five explicit instrumentation runners, and
binds commit/tree, APK hashes, runtime and synthetic evidence token. The API37
permission instrumentation remains the default runner; this lane explicitly
selects only the UI runner. Each case uses a fresh install and the invocation's
private adb server, not attached personal devices or existing AVDs. The viewport
is configured before launch (1600x2560 pixels at 200dpi); no input or viewport
change is introduced during #317's hands-off observation interval.

For an already provisioned Linux/KVM host, use the same outer owner/exporter:

```sh
python3 -B scripts/ci_evidence.py --component android-ui --timeout-seconds 3600 \
  --output-dir "$RUNNER_TEMP/android-ui-evidence" \
  --report-glob 'build/reports/android-ui/**/*' -- \
  python3 -B scripts/run-android-ui-validation.py --case both
```

Use a clean disposable checkout and a fresh report/output directory. The existing
CI evidence recipient public-key pins must be configured. The outer runner owns
native descendants, bounds execution/output, proves cleanup, and encrypts raw
output. Only its manifest and encrypted bundle are uploaded. No private key is
needed. The controller copies only `no_backup/ui-<case>-<token>` synthetic files,
never general app/device storage. Fresh emulator tool state is left to the
outer job's ephemeral cleanup, not deleted while descendants may still be alive.

## What a completed harness means

- **#317:** real sample `MainActivity` and Diagnostics screen; seed one event,
  settle filters, then add a second event without input, recreation or incidental
  state changes. Retain before/after trees and screenshots, committed frames,
  recorder/revision data, lifecycle/window/input traces and cleanup observations.
- **#324:** render the production join card in a real Activity with a read-only
  credential-owner observer. Save before clearing through the real Compose
  registry and Parcel; restore SSID without secret. Observe default masking,
  show/hide, real 15-second expiry, Activity stop/reentry and disposal, plus join
  success/failure and permission-result clearing. Provisioning and permission
  callbacks are explicitly modeled: **not OS permission, network or whole-process
  death acceptance**.

The result remains `HARNESS_PASS_PENDING_REVIEW`, never issue-closure `PASS`.
Independently inspect the original screenshots/Parcel/lifecycle/input interval
and cleanup. Execute isolated, clean, committed negative-control candidates: the
inert delegated-local diagnostic collector must reach its baseline and fail the
hands-off refresh; the nine #324 controls must fail their intended save/restore,
secret-display, expiry or clear/reentry observations. Compile failure, setup
failure, unrelated crash or timeout before the intended observation is not a
successful mutant. A green workflow alone does not close either issue.

Offline controller checks, which are not Android execution:

```sh
python3 -B scripts/tests/run-android-ui-validation-test.py
python3 -B scripts/tests/run-android-art-smoke-test.py
```

## #372 is deliberately separate

`LanPermissionRuntimeInstrumentation` and its existing driver still declare
`p2pkitSameInstanceRevocation=NOT_EXECUTED`. Do not reinterpret it as a complete
revocation result. Remaining acceptance needs a fresh API37/target37 install with
no inherited Nearby grant, admissible actual runtime/permission-controller module
and mandatory flag/compat readbacks, real denial → UI grant → authenticated
controlled ordinary-LAN duplex traffic, then live OS revocation. Verify denial on
the same manager if its process survives; otherwise retain attributable OS
permission-kill evidence and unchanged-install denied reentry. A force-stop,
modeled callback, API35 emulator, loopback connection or generic CI success does
not satisfy this requirement. The API35 UI lane makes no availability claim about
an eligible API37 runtime.
