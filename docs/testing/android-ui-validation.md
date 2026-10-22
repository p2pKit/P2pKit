# Android rendered UI validation

This opt-in lane executes the existing repaired production UI for issues **#317**
and **#324**. It is not the API37 LAN permission lane, a physical-phone campaign,
an API29/OEM result, or a replacement for release CI.

## Run the exact committed source

The workflow `.github/workflows/android-ui-validation.yml` accepts `case=317`,
`case=324`, or `case=both`; reusable `workflow_call` accepts the same string
input (default `both`). Dispatch that workflow on the exact committed ref, or
select its optional diagnostic from modular `ci.yml`. It has no marker-triggered
push route: `[android-ui-validation]` in a commit message does not start it.
Ordinary PR/main qualification does not imply this emulator diagnostic ran.

The hosted job uses Linux KVM, a fresh Google APIs API35 x86_64 AVD, targetSdk37,
Java17/21, the checked-in Gradle wrapper, strict dependency locks/checksums, and
NDK **29.0.14206865**. The exact installed emulator/image revisions are retained;
this lane does not claim the API37 runtime/module/flag profile. Dependencies and
SDK licenses must already be authorized; the workflow does not accept licenses.

The controller refuses dirty source, builds both APKs, inspects their actual
binary manifests, checks the maintained explicit instrumentation-runner inventory, and
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
and cleanup against the original issues: #317 requires an untouched rendered
update; #324 requires executable Compose restoration and lifecycle coverage,
including absent restored plaintext and default masking. State-object or source-
string tests alone do not satisfy these criteria. A green workflow alone does
not close either issue.

The September preparation campaign additionally proposed an inert delegated-
local collector mutant and nine #324 mutants. These are optional stronger
sensitivity checks, not new prerequisites for the original issue criteria. Keep
any existing host negative-control results in their original scope; do not call
them rendered mutant execution. Historical comments and the runner's legacy
`independentVisualAndMutationReview` marker are retained unchanged: the runner
does not perform that review or execute mutants. Record actual independent
rendered/restoration review separately and identify unexecuted mutations as
`NOT_RUN`; do not claim completion of the stronger historical campaign.

If executing optional mutants, use isolated, clean, committed candidates. The
collector mutant must reach baseline and fail the hands-off refresh; credential
mutants must fail their intended save/restore, display, expiry or clear/reentry
observation. Compilation/setup failure, unrelated crash or an earlier timeout
is not a successful mutant. No runtime assertion, frame/visual requirement or
cleanup check is relaxed by separating original acceptance from this extra work.

Offline controller checks, which are not Android execution:

```sh
python3 -B scripts/tests/run-android-ui-validation-test.py
python3 -B scripts/tests/run-android-art-smoke-test.py
```

## Foreground pixels and stopped-task previews

On API33+, `MainActivity` disables recents screenshots before its first content
using `setRecentsScreenshotEnabled(false)`: Android can represent a stopped task
with its theme rather than retain an explicitly revealed credential. This is
not `FLAG_SECURE`; normal foreground screenshots and explicit-reveal pixel
positive controls remain available and required on API33+. On API24–32 the sample
instead sets `FLAG_SECURE` before its first content and retains it for the whole
window lifetime, including stop/reentry and recreation. This deliberate legacy
privacy tradeoff also blocks foreground screenshots, screen recordings and
non-secure displays; it is not a task-preview-only switch. Credential clearing
and permission/no-replay behavior remain unchanged. Local flag/unit checks do not
qualify OS snapshots: API24/32 source-bound lifecycle, positive-control and actual
Recents captures require separate runtime review; no all-OEM claim follows.

The three previously disputed clear/reentry captures retain the first original
full-display screenshot alongside a separately timestamped owned-Window
PixelCopy and finite window identities/frame statistics. These are diagnostic,
not interchangeable proof: an empty owned buffer never excuses exposed global
pixels. Observation and capture share the original five-second deadline; late
or blank first captures remain failures, with their evidence retained. This
preview policy does not establish the cause of every historical contradictory capture
or replace any masking, reveal, restoration, lifecycle or cleanup assertion.

## #372 is deliberately separate

The original no-mode `LanPermissionRuntimeInstrumentation` and its existing
driver still declare `p2pkitSameInstanceRevocation=NOT_EXECUTED`; do not reinterpret
that result. The separate [API37 permission lane](android-permission-validation.md)
adds explicitly selected real revocation/reentry modes without widening this UI
lane. It requires fresh API37/target37/no-prior-Nearby installation, original
runtime/module/mandatory-flag/compat observations, actual denied → UI grant →
pinned authenticated duplex controlled traffic → OS revocation/reentry evidence.
An eligible emulator may satisfy that scope; a physical phone is not inherently
required. A force-stop, modeled callback, API35 emulator, Android loopback or
generic CI success does not satisfy it. The API35 UI lane makes no availability
claim about an eligible API37 runtime.
