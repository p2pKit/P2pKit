# Official local ARM27 qualification continuation

## Accepted baseline and scope

On October 2 the owner accepted native **macOS27 / Xcode27** instead of the
unavailable macOS26/Xcode26.5 environment, from
`e1ae3f37b27780cc4d9efaa16228fcb75c8e159b`. This is the official ARM continuation,
not supplemental host evidence. The older hosted ARM26 matrix is historical;
its environment is **not** a prerequisite for this command. Intel and ART remain
separate lanes. Original failures, prior receipt scopes, and Foundation
**NOT_READY** remain unchanged.

`scripts/run-rpc-local-arm-qualification.py` executes only the outstanding
ordinary Swift, actual production-adapter lifecycle/cancellation, and current
iPhone app gates, with their required source-matched producers. It does not
repeat the already-passed full-platform, ABI, Dokka, SBOM or capacity suites.
It also prepares, but does not execute, the current-source JVM mobile driver;
an older transferred JAR manifest cannot be relabeled as the current phone source.
The plan also runs the real 125-second Mac generator clock/memory preflight,
which requires native authorization but **does not require a phone**. Each later
physical workload still needs a fresh immediately preceding health observation.
New native controls are necessary because a new product-execution session needs
its own admission: the old pure-command readiness proof is not a product receipt.

The controller uses the **same** native executor, original deadlines, individual
XCTest assessors, nested provenance and exact simulator/native finalizers as the
maintained qualification. No fake hosted-runner variables, skipped methods,
timeout extensions, prebuilt P2pKit application execution, private signing, device queries,
permission changes or system installation are admitted. Installed JDK17/JDK21,
XcodeGen2.45.4 and Android compile platforms36/37 are reused. Strict Gradle and
Kotlin/Native dependencies populate fresh private homes; previous build caches
and artifacts are not restored.

### Wrapper dependency preparation is not finalization

The first local product attempt at `8783cc9d` passed all129 controls, but its
mandatory wrapper stop downloaded Gradle into the empty private home and failed
the unchanged120-second finalizer. Its receipt remains failed; neither its
partial ZIP nor its consumed session may be reused.

Download a **fresh data-only distribution ZIP** from the checked-in wrapper URL.
Preparation verifies its checked-in SHA-256, bounded regular-file identity and
copy readback before publishing a usable session request. The first plan phase
places only that verified ZIP in the new context-bound home. It does not extract
or execute it, copy an old cache/runtime, create a wrapper `.ok` marker, or grant
native admission. The actual wrapper still validates/extracts the ZIP and must
complete the original same-home stop and every native cleanup check. The plan
now has thirteen phases, including this data-only prerequisite.

### Installed tool resources are part of the input

The `f45584cd` run passed129 controls and all39 outer native finalizers, but
Xcode could not resolve the ordinary, lifecycle, cancellation or phone test
hosts. No XCTest methods ran. The private XcodeGen copy contained only its
binary, not its installed `share/xcodegen/SettingPresets` resources. XcodeGen
returned success while reporting missing base/debug/release/iOS settings.

Preparation now hashes the complete installed package; execution stages and
independently reads back the binary and settings with their original relative
layout. Missing, changed, linked or unsafe inputs are refused. Do not work around
this by editing generated projects or removing test-host/provenance requirements.
The separate clock failure was its command stream being created as0644 instead
of0600. Streams now use private create-only descriptors; the strict reader and
original125-second clock,100ms gap and6GiB requirements are unchanged.

### Fresh process signal environment

The first dialog-launched `e8158bbd` session authenticated correctly and dropped
privilege, but two native SIGTERM controls failed: the controller never recorded
cancellation, and a kernel-accepted opaque-token signal did not terminate its
child. All386 outer owned lifetimes were retired and the wrapper stop passed;
the product failure still blocks later phases. Its incoming signal mask was not
recorded, so do not retrospectively label its exact mask as observed.

The local controller now records the incoming signal mask, pending signals and
cancellation dispositions **after** validating the unprivileged fresh kernel
session, but **before** even its Git subprocesses. It restores an empty mask and
ordinary SIGINT/SIGTERM dispositions for its own future children, then verifies
readback. Pending signals, custom handlers or extra threads cause refusal, not
silent cancellation loss. Both before/after records are private and create-only.
This changes only that process, not system policy, the original bootstrap,
identity-scoped signaling, any test assertion or a deadline. Controlled local
child regressions are not replacement native receipts; a fresh source-bound
dialog session must establish actual inheritance and execute the original tests.

## Prepare once, then execute the newly authorized session

Use **only** `$HOME/Projects/P2pKit-RPC-current`, with a clean committed descendant
of the baseline. Never modify the old `$HOME/Projects/P2pKit` checkout.

```bash
cd "$HOME/Projects/P2pKit-RPC-current"
umask 077
input=$(mktemp -d "$HOME/Projects/P2pKit-gradle-input.XXXXXXXX")
# HTTPS data download only; no extraction, installation, retry or old-cache reuse.
# The prepare command below checks the exact checked-in SHA-256 before admission.
/usr/bin/curl --disable --fail --show-error --location \
  --proto '=https' --proto-redir '=https' --tlsv1.2 \
  --connect-timeout 15 --max-time 600 --max-filesize 268435456 --retry 0 \
  --output "$input/gradle-9.7.0-bin.zip" \
  https://services.gradle.org/distributions/gradle-9.7.0-bin.zip
# Stop here if curl fails. Preserve the partial input; do not prepare or retry it.
parent=$(mktemp -d "$HOME/Projects/P2pKit-arm27-product.XXXXXXXX")
python=/opt/homebrew/opt/python@3.14/bin/python3.14
"$python" -B scripts/run-rpc-local-arm-qualification.py prepare \
  --owner-authorized-arm27 --parent "$parent" --expected-commit "$(git rev-parse HEAD)" \
  --java-home /opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home \
  --jdk21 /opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home \
  --android-sdk "$HOME/Library/Android/sdk" \
  --xcodegen /opt/homebrew/opt/xcodegen/bin/xcodegen \
  --gradle-distribution "$input/gradle-9.7.0-bin.zip"
```

Preparation copies/hashes the pinned ZIP and inventories the installed XcodeGen
binary/settings. It does **not** invoke sudo, extract the ZIP or run native tools. Product execution
requires one new authorized isolated audit session, not a rerun of either used
readiness session. The existing bootstrap allocates only the process-local
audit session and permanently drops privilege before any observer or product:

```bash
sudo "$python" -I -S "$PWD/scripts/with-darwin-audit-session.py" \
  --bootstrap "$parent/private-session/session-config.json"
```

### Agent-initiated macOS authentication instead of Terminal copy/paste

The agent can instead run the unprivileged `scripts/authorize-rpc-local-arm.py`
with `--owner-authorized-arm27 --parent "$parent" --expected-commit "$sha"`.
Use `--check-only` for read-only admission without a dialog. Execution requests
the standard macOS administrator dialog for the **same one-shot bootstrap**;
the owner authenticates in macOS, never in chat or through password stdin.
The launcher binds the prepared clean source, inputs and invoking console user,
refuses consumed requests/preexisting outputs, and records the attempt once.
Cancellation is not retried. macOS may request authentication for each new run;
no persistent root broker, passwordless sudo rule or approval-policy change is
created. Codex Full Access does not replace this OS authentication boundary.

Do not repeat a consumed command/configuration or retry a failed product phase.
If authentication is unavailable, retain that boundary and continue independent
offline engineering. A prepared request is not a qualification result.

## Evidence and remaining boundaries

The create-only parent retains `prepared.json`, fresh session admission,
`state/context.json`, every native receipt/log, individual XCTest manifests,
`state/private/result.json`, phone diagnostics, and source/tool hashes.
`local-signal-environment-before.json` and `local-signal-environment.json` retain
the process-local signal preparation, without granting native admission.
Dialog-launched runs also retain `gui-authorization-{request,result}.json` and
private transport logs. A successful dialog is not a qualification receipt;
independently validate the native/product evidence afterward.
Only a successfully assessed phone app with verified outer/native and simulator
cleanup can export `p2pkit-rpc-iphone-unsigned.app.zip` and `phone-export.json`.
The app is unsigned and **not physically installable** without owner signing.

Report every phase separately. An ordinary assertion failure does not suppress
independent cancellation/phone controls; unproven native ownership does. No
overall percentage follows from adding overlapping methods. Simulator results
do not replace USB publication, physical resource measurements, trust/signing,
real LAN infrastructure or independent external campaigns.
