# Local testing

Use JDK 17 and the checked-in Gradle wrapper. macOS with the configured Xcode
toolchain is required for Apple targets and the complete release gate.

Continuing the September audit on a new Mac? Start with the [Mac handoff](mac-handoff.md).
`main` contains the consolidated work; no retired audit branch or private build products are required.

The shell checks require Bash, Git, and Ruby with its standard library (`ruby --version`).
Ruby is used by both the Markdown-link and repository-layout policy checks. Install it if absent on Linux/Windows;
run `.sh` commands in Bash (for example, Git Bash on Windows), with Ruby available on `PATH`.

JVM file-transfer regressions require real symbolic links in `java.io.tmpdir`.
Use a symlink-capable temporary filesystem. On Windows/JDK 17, use NTFS and a
test-process token with `SeCreateSymbolicLinkPrivilege` (for example, an elevated
console for an account granted the **Create symbolic links** right). Developer
Mode alone is insufficient with JDK 17. Missing prerequisites fail the required
test with the original platform cause; they must not be treated as passed or
silently skipped coverage.

Fast project checks:

```bash
scripts/tests/check-repository-layout.sh
scripts/tests/check-osv-lockfile-coverage.sh
scripts/tests/check-markdown-links.sh
scripts/check-release-metadata.sh
./gradlew check --console=plain
git diff --check
```

Keep this six-command list aligned with `CONTRIBUTING.md` and the protected `CLAUDE.md` core commands.
The link checker resolves relative file targets in tracked, non-archived Markdown; it does not validate external
URLs, anchors, or fenced code. `git diff --check` checks unstaged changes; also use `git diff --cached --check`
when reviewing staged changes. Run `./gradlew --stop` after checks, including failure, and preserve reports before cleaning
only your disposable generated outputs.

The CI/release wrapper `scripts/check-git-whitespace.sh [<base> <head>]` checks the committed range, index and worktree.
Three immutable, pre-policy archives have exact-path formatting exceptions in `.gitattributes`; its helper
`scripts/check-archive-whitespace.sh` verifies their SHA-256 in all three layers. The dependency-update range gate
enforces the same integrity check. Plain `git diff --check` honors the attributes but does **not** verify those hashes.
Do not normalize or replace these historical bytes to satisfy a check, or extend the exceptions to new archived material.
If an older checkout converted their line endings, compare with a fresh checkout without overwriting local changes.

Release-shape checks:

```bash
scripts/check-sbom.sh
scripts/check-publish-artifacts.sh
scripts/check-published-consumers.sh
./gradlew :p2p-core:checkKotlinAbi \
  :p2p-transport-lan:checkKotlinAbi \
  :p2p-network-provisioning-android:checkKotlinAbi \
  :p2p-network-provisioning-desktop:checkKotlinAbi
./gradlew :p2p-core:checkAndroidAbi \
  :p2p-transport-lan:checkAndroidAbi \
  :p2p-network-provisioning-android:checkAndroidAbi
./gradlew :p2p-core:dokkaGeneratePublicationHtml \
  :p2p-transport-lan:dokkaGeneratePublicationHtml \
  :p2p-network-provisioning-android:dokkaGeneratePublicationHtml \
  :p2p-network-provisioning-desktop:dokkaGeneratePublicationHtml
```

The complete macOS gate is `scripts/run-release-gate.sh`. It includes module
tests, Android lint/host tests, Apple simulator tests, ABI, strict Dokka,
publication artifacts, isolated consumers, SBOM, Swift warnings-as-errors, and
release-XCFramework provenance.

## Kit diagnostic teardown

Kit/session/lifecycle regressions should observe soft failures as well as their primary result.
Use the common-test `withTestKit` scope and **install its supplied `RecordingLogger`** in the
existing legacy or authenticated fixture. Nest scopes for multiple kits. The scope stops each
kit and checks every WARN/ERROR after stop, including failed construction, body failure and
cancellation. It preserves the primary failure and attaches teardown/diagnostic failures as
suppressed evidence. Additional collectors, raw connections and identity stores still need
explicit, ordered cleanup; a timed-out stop is a failure, not proof that resources drained.

Do not throw from logger callbacks to fail a test: production deliberately isolates callback
exceptions. Record first, then assert outside that boundary. Do not overwrite a custom logger
whose behavior is under test; compose recording before delegation or keep an explicit reviewed
alternate assertion. Authenticated-v2 and strict-invariant fixture guards must stay enabled.
Expected warnings need an explicit `verifyDiagnostics` assertion of exact entries, levels,
causes and finite counts. A stopped retry episode can permit an ordered prefix of its
source-defined attempt budget; never derive that budget from the observed logs. Accepting
arbitrary repeats or a broad substring hides regressions. INFO/DEBUG are not failures. Keep
positive typed failure and runtime-termination assertions as well.

Core kit callers use the scope for lifecycle, session/ownership/recovery, secure integration,
transfer, permissions, identity and JVM storage tests. Existing backlog, mixed-profile and
terminal-acceptance suites retain their own post-stop nets; this does not add the new scope's
failure aggregation to those unchanged methods. Direct protocol/store/dispatcher tests still
own their component-specific diagnostics and runtime cleanup, not an artificial kit scope.

LAN, Desktop provisioning and sample suites use small module-local `KitTestDiagnostics`
adapters because core's test fixtures are not published. Install the supplied recorder on the
actual kit, register construction before calling the factory, and always call `finish` from
the existing teardown owner. It attempts every kit stop and every diagnostic check; deliberate
logger delegates record before forwarding. Preserve explicit lifecycle stop assertions and
caller-owned socket, settings, collector, store and file cleanup.

Adoption is not universal. Preserve these explicit exceptions rather than changing the
behavior under test or claiming a textual creator count as executed coverage:

- `LoggerIsolationTest` keeps its exact NoOp-identity method; the throwing-logger method
  instead composes recording before its delegate. Do not globally replace fixture defaults.
- Failed-builder/secure-construction rollback tests may return no kit; their typed cause,
  release and key-erasure assertions remain authoritative.
- KMP `PairingDemoTest` exercises public default/pinned factories without a logger seam.
  `KmpConsumerLoopbackTest` records the same underlying JVM factory through an internal seam,
  not every public-factory invocation. Do not add public test-only API or substitute builders.
- `KmpCallsiteSmokeTest` stores uninvoked factory references; `IosLanDiagnosticTest` is an
  explicitly ignored manual capture, not an automated diagnostic-net pass.

Source adoption/review is not runtime qualification. Share affected suites with the next
relevant module/platform cycle; investigate unexpected logs rather than broadening allowances.
Common-test JVM/Native results remain separate from filtered Android-host execution,
physical-device, hostile-network, independent interoperability and cryptographic validation.

### Subprocess transcript custody on failure

The CLI shutdown and diagnostic native-lock fixtures export original merged-output bytes
as `CLI_SHUTDOWN_RAW` / `NATIVE_LOCK_PROBE_RAW` Base64 records, including exact inherited
Java startup notes. Raw files are disposable only after successful export/error checking
and known child retirement/input closure. A failed step must not prevent the other
finalizers, replace the primary failure, or delete the unretained original. Diagnostics'
enclosing directory also stays intact on body failure, a remaining probe log or an
unknown listing. These are test-fixture safeguards, not universal stdout/disk fault tolerance.

Before running these suites, give the test JVM an explicitly owned `java.io.tmpdir`
through the maintained reviewed initializer (not ambient JVM-option admission overrides).
The outer run owner must preserve a **custody HOLD** on that root after a failed/incomplete
run, `PROBE_EVIDENCE_HOLD`, or missing/unverified export. Absence of a marker is not proof
of retention: stdout, the test worker or the report writer may have failed. Stop the same
wrapper/home and drain only owned workers first; unknown retirement remains a HOLD.

Before any outer temporary-root cleanup, inspect the owned CLI/rolling-fixture directories
and retain/hash any remaining `child.log` / `native-lock-probe-*.log` originals in private
evidence with the source identity, exit statuses and original reports. Verify the copies
against the originals after known retirement. Preserve the root when that cannot be done;
record incomplete custody, not a pass. Do not read/copy another invocation's temporary files.
The immutable executor automatically retains build reports/test-results, **not arbitrary
Java temporary logs**; its normal cleanup is not this extra custody proof. On success,
retain and decode the Base64 records from the original reports before outer cleanup.
Only the tiny finalizer-control fixtures dispose of their source-defined synthetic bytes
directly; they are not child-process observations or substitute runtime evidence.

The opt-in [custody allocator/collector](../../scripts/test-transcript-custody.py) and
[Test initializer](../../gradle/test-transcript-custody.init.gradle) preserve this boundary
without changing the executor, test filters, framework, deadlines or production code.
They do not launch Gradle, observe/kill processes, acquire dependencies, encrypt or upload
anything. **Source/offline controls alone do not qualify the initializer on a real Test JVM.**
Run its offline, synthetic-owner/report controls with
`python3 -I -B -S scripts/tests/test-transcript-custody-test.py`.
The full current classes require 9 CLI methods/two original exports and 23 diagnostics
methods/four exports; these are expected counts, not an execution result.

For a new clean immutable state, install after any admitted cache restoration and before
the normal leaf. Use `--scope both` for `full`/whole-check; Desktop's six-task batch needs
`--scope cli` because it does not execute diagnostics tests. Bind the exact leaf's original
argv after `--`, not an approximate task label. For example, the following is a recipe,
not evidence that the full gate ran:

```bash
CUSTODY="$P2PKIT_AUDIT_STATE_DIR/custody"
python3 scripts/test-transcript-custody.py prepare --root "$ROOT" \
  --directory "$CUSTODY" --home "$GRADLE_USER_HOME" \
  --owner-state "$P2PKIT_AUDIT_STATE_DIR" --owner-kind audit --scope both \
  -- python3 scripts/run-platform-tests.py full
INVOCATION="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["owner"]["productInvocation"])' \
  "$CUSTODY/request.json")"
# Pass --id "$INVOCATION" to the normal run-audit-command.py leaf. Preserve its
# original status even on failure; no other leaf may use this reservation.
# After its finally/stop/native-worker drain, collect UNCONDITIONALLY:
python3 scripts/test-transcript-custody.py collect --directory "$CUSTODY" \
  --owner-result "$P2PKIT_AUDIT_STATE_DIR/host-mac-platform-full.json"
```

The allocator reserves fresh native invocation IDs; an audit job comes from the
actual context. The existing executor consumes the product ID with `--id`. A
preexisting invocation is rejected. Task events validate and record the inherited
native job/ownership-chain/domain and selected state/home, not just the request's
token. The direct last domain must match; a genuinely nested leaf needs a new
request bound to that leaf. The unchanged full-profile runner uses direct Gradle
children and retains its outer leaf's domain.

The collector cross-checks those reserved IDs, the original canonical receipt/context, source/home/argv,
task start/outcome records, current class XML and exact Base64 record identities/lengths.
It independently attempts report retention and remaining-log inventory. Missing/stale
reports, failed execution, unverified originals, or unknown retirement remain **HOLD**;
the absence of a marker never makes them green. `RETAINED` is only custody, not native
acceptance, the complete gate, independent review or permission to merge/close an issue.
Its 64-MiB aggregate/16-MiB individual evidence bounds fail closed with originals left in
place. It does not defend against a malicious same-user process replacing the controller
and its records. Windows Java `fileKey()` may be null; the controller's physical directory
identities remain required. Inspect retained originals independently before acceptance.

Keep the private root outside the checkout and outside the executor's disposable-root
allowlist (`state/custody`, **not** `state/fixtures`). The collector never deletes originals.
After known retirement, `uninstall --directory "$CUSTODY"` removes only that request's
exact `init.d` loader, preserving other initialization and all custody evidence. Do this
before cache save or a later leaf; allocate a new request for the later command rather
than reusing task events. Dependency inputs can remain in the same admitted home.

The mutable writer needs its separately reviewed outer controller to install with
`--owner-kind writer --writer-job <actual-controller-job>`, consume the request's
distinct product/stop IDs when constructing its existing native command scopes,
retain its actual post-stop/drain owner snapshot, call collection
before outer cleanup, and bind the custody result into its final result. Lock/metadata
mutation is allowed only for that owner; the helper does not promote a writer candidate
or replace the complete dependency procedure. Do not run a retired private controller
unchanged. Ordinary hosted Desktop has no canonical native-retirement receipt yet:
its adapter and approved private/encrypted evidence delivery are still prerequisites.
Do not upload raw XML, child logs or Gradle failure output as public app artifacts.

## Android ABI graph verification

`scripts/check-android-abi-guard.sh` runs a strict Gradle dry-run of the three Android modules' `check` tasks and
requires their compiler, ABI extraction and comparison tasks in the realized graph. It does not execute those
tasks or replace a real `check`/ABI comparison. Configure the SDKs below first, and stop Gradle afterward even
on failure. Full CI and `scripts/run-release-gate.sh` each invoke this unflagged command explicitly once.

`scripts/tests/check-kotlin-toolchain-policy-test.sh` now runs only the static ABI policy and its mutation fixtures;
it is not the graph probe. Static policy rejects removal, `--static-only` downgrade, comments, duplication or
ignored failure at either full-mode call site. Keep the explicit commands when reorganizing either gate.
Run `scripts/tests/check-android-abi-guard-policy-test.sh` for these no-Gradle fixture checks.

## Android SDK setup

The compile SDKs are separate inputs in [the version catalog](../../gradle/libs.versions.toml).
Install **both** for `./gradlew check` or Android sample builds; installing only the library platform is insufficient.

| Consumer | Catalog key | Compile platform | SDK Manager package |
| --- | --- | --- | --- |
| Libraries and shared KMP sample | `android-compileSdk` | Android SDK Platform 36 | `platforms;android-36` |
| Android app sample | `android-sample-compileSdk` | Android SDK Platform 37 | `platforms;android-37.0` |

The runtime minimum remains **Android API 24+** (`android-minSdk`); a compile SDK is not a device minimum.
The preserved [agent guide](../../AGENTS.md) names only the library platform, not the complete sample prerequisites.
Use this table for sample and repository-wide checks. The device/emulator validation matrix is separate from these
build requirements; installing a platform does not verify that Android runtime.

Install Android SDK Command-line Tools (latest) through Android Studio's SDK Manager or the Android command-line
tools distribution. Set `ANDROID_HOME` to that SDK directory, then review/accept the licenses and install the platforms:

```bash
export ANDROID_HOME="/absolute/path/to/Android/sdk"
"$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" --sdk_root="$ANDROID_HOME" --licenses
"$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" --sdk_root="$ANDROID_HOME" \
    "platforms;android-36" "platforms;android-37.0" "platform-tools"
```

In Windows PowerShell, set `$env:ANDROID_HOME` and invoke `sdkmanager.bat` with `&`; do not paste Bash continuations.
AGP selects the Build Tools version and can install it with accepted licenses and network access. Preinstall those
tools before an offline build. The sample's package ID is `platforms;android-37.0`, not `platforms;android-37`;
no manual directory rename or symlink is required. Keep `sdk.dir` in untracked `local.properties`, if present, pointed
at the same SDK; it takes precedence over `ANDROID_HOME`. Remove conflicting deprecated `ANDROID_SDK_ROOT` settings.
Do not commit machine-specific SDK paths or copy another device's credentials/caches.

Verify with `./gradlew :p2p-sample-android:assembleDebug --console=plain`; run `./gradlew --stop` afterward,
including on failure. `scripts/tests/check-repository-layout.sh` also checks the setup table, installation command,
and contributor/validation links against the catalog and CI installer. This documentation-consistency check does
not replace the independent dependency/toolchain approval tripwires.

## JVM host coverage

Run the library suites without requesting Apple/Android tasks:

```bash
./gradlew :p2p-core:jvmTest :p2p-transport-lan:jvmTest \
  :p2p-network-provisioning-desktop:test --continue --no-build-cache \
  --dependency-verification strict --max-workers=2 --no-parallel --console=plain
./gradlew --stop
```

On Windows PowerShell, use `.\gradlew.bat` and one command line instead of
Bash continuations. The symlink prerequisites above still apply; do not skip
tests when a runner lacks them. Stop Gradle after failures as well as success.

`CI` runs these tasks on Ubuntu and Windows for every pull request, main push,
manual run and weekly schedule. macOS uses the conservative
[CI scope policy](../../CONTRIBUTING.md#ci-scope-policy): non-Markdown changes,
manual dispatches and the weekly backstop request the full gate; no main-merge
check is inferred from tree equality. Keep `complete-gate`
required in repository rules: it waits for both JVM hosts and explicitly rejects
failure, cancellation, or a skipped matrix before running either its lightweight
or full checks. No new required-check name is needed. The separate Desktop
matrix remains sample-test/packaging coverage.

Each JVM host uploads XML/HTML reports as
`jvm-library-tests-<matrix.os>-<run_attempt>` even after a test failure (seven-day
retention). A setup/compilation failure may have no reports and still fails the
job. Record the source SHA, OS/JDK, task outcomes, test counts, and any skips;
a configured workflow or another OS's pass is not host-execution evidence.
`scripts/tests/release-workflow-test.sh` checks the matrix, actual task command,
report paths, and fail-closed dependency guard, with negative policy controls.

### Participating hosted job queue

CI's `jvm-library-checks` and `complete-gate`, Desktop's `verify` and opt-in
`windows-directory-fsync-control`, Intel's `ios-x64`, and dependency submission's
`submit` share the **job-level** concurrency group
`p2pkit-nonphysical-heavy`, with `queue: max` and `cancel-in-progress: false`.
Both matrices keep their existing hosts/tasks and `fail-fast: false`, with
`max-parallel: 1`. The lease covers each whole job, including existing cleanup
and evidence steps; no workflow holds the same group while waiting for its jobs.
Existing workflow-level supersession remains independent: ordinary CI/Desktop
runs can still be superseded, while CI schedules retain their separate group.
The Windows control uses its own run/attempt workflow group, so an ordinary
Desktop update does not supersede its two-case retention/cleanup obligation.

[GitHub's queue policy](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency)
admits at most 100 pending jobs/runs; overflow is cancelled. This is not an
unlimited or global execution lease: local builds, older workflow revisions and
unparticipating workflows still need external coordination. Do not cancel
unrelated work or infer host acceptance from this configuration.

`ruby scripts/tests/check-heavy-job-queue-policy-test.rb` validates the focused
YAML contract and mutations, reusing the existing CI guard policies. Released
actionlint 1.7.12 rejects the new `queue` property: retain that incompatibility
alongside other syntax/action-pin checks, rather than stripping the property or
suppressing lint errors. Static checks do not establish actual GitHub parser or
hosted queue acceptance; that remains a separate execution/review gate.

### Scoped Windows directory-fsync witness

The optional [Windows directory-control handbook](windows-directory-control.md)
describes #141's exact current-positive / historical-method-preimage witness.
It uses the existing unchanged durable-destination test on genuine hosted Windows,
not an injected OS name, a full historical-revision build, or a whole-library pass.
Normal Desktop PR/manual runs retain their three-host sample matrix by default.

`ruby scripts/tests/check-windows-directory-control-policy-test.rb` and
`python3 -B scripts/tests/run-windows-directory-control-test.py` check the dispatch,
source, expected-red, receipt and retention policies without Gradle/native execution.
The Python fixtures need full Git history for three read-only preimage queries;
all wrapper/native/process operations are mocked. Native ownership controls and
the selected product witness run only in the separately reviewed explicit dispatch.

## Platform execution evidence

On macOS with JDK 17, Xcode, and the configured Android SDKs, use:

```bash
python3 scripts/run-platform-tests.py full
# Native Intel Mac only; not an arm64/Rosetta substitute:
python3 scripts/run-platform-tests.py ios-x64
```

The full profile runs `./gradlew check --console=plain` with strict dependency
verification, task reruns, build/configuration caches disabled, two workers,
and no parallel tasks. Shared dependency caches remain available.
Both simulator architectures share the network-test serialization service.
The Intel profile requests only core and LAN `iosX64Test` tasks. CI uses the
full profile; `ios-x64-tests.yml` provides a secret-free weekly/manual Intel job.
Keep failures blocking; a configured workflow is not hosted execution evidence.

Reports live in `build/reports/platform-tests/<invocation-token>/`:
`invocation.json` binds the command to the commit/tree and complete tracked diff;
`execution.json` records Gradle task outcomes and actual passed/failed/skipped
test events; `summary.json` includes the final verdict, source recheck and
per-target limitations. Review and stage new source files before invoking the
gate: untracked nonignored inputs or source changes during execution fail it.
CI, release verification and dry-run uploads retain this directory. Each required
task must freshly execute nonzero successful cases; old XML, cache hits,
no-source results and dry-runs cannot satisfy the gate. Skipped case counts
remain visible, including the intentionally ignored Apple LAN diagnostic.

Review changes to `gradle/platform-test-policy.json` together with target/task
changes; never remove an entry to silence a missing suite. The script regressions
exercise model/outcome mutations and fake-wrapper failure/cancellation paths,
not Kotlin execution. The driver stops Gradle in `finally` and uses bounded
TERM/KILL escalation to drain its owned process groups, even if a wrapper exits
before its workers. Separately detached helpers are outside that group guarantee;
callers must track and stop their own survivors. Preserve evidence and any outputs
needed by dependent consumer validation before deleting disposable build directories.

The report distinguishes the other-host simulator slice, device-only
`iosArm64`, compilation-only metadata, and separately run Swift tests. Android
host/shadow tests do not run ART. The sample's dependency-free
`LanPermissionRuntimeInstrumentation` is one targeted API37 case, invoked by
`scripts/run-android-art-smoke.py` with an owned JVM CLI and raw-socket control.
It checks an outstanding real permission request across Activity recreation,
completed-result UI, retained VM/process/default-manager grant observation, and
actual authenticated traffic. Android retains default `RejectUnknown` plus an exact
manual/per-connect fingerprint pin; the maintained CLI uses its disclosed
sample-only `AcceptAnyAuthenticatedSameApp` policy, not symmetric pinning.
It requires actual pregrant socket denial; a gateway exemption is not a pass.
Assembly/source review is not execution, and this is not a general device suite. Core's
intentional `*AndroidHostTest` filter still excludes its common suite because
host stubs are not an Android runtime. JVM/native common-test passes do not
substitute for unexecuted Android runtime/catalog cases. See
[validation status](validation-status.md#kotlin-target-execution-and-structural-gaps).

The historical optional `audit-android-art.yml` workflow runs only after a reviewed change to
that workflow on `audit/complete-2026-09-04` with `[audit-art]` in the pushed head
commit message. Hold the shared audit execution lease before requesting it.
A skipped job is not runtime evidence and does not replace any required gate.
This audit-branch trigger is dormant after main consolidation; do not recreate the branch
or fabricate an Actions event to run it. A future hosted relocation requires separate review.

The separate [API37 LAN readback content contract](android-lan-readback.md)
prepares strict, dependency-free declared-input checks for #372. Even matching
readbacks remain `COMPAT_STATE_UNPROVEN`; this is not the missing ordinary-UID
collector, runtime admission or same-instance revocation acceptance.

## iOS launcher cleanup and recovery

`./gradlew :iosApp:runIosSimulator` and `:iosApp:runIosUiTests` require Python 3
alongside Xcode/XcodeGen. They share a process-owned launcher lock. Successful
runs remove their automatic `ios-run.*`/`ios-ui-run.*` directories; failures,
`KEEP_IOS_RUN_ARTIFACTS=1`, and caller-owned `IOS_RUN_DIR` directories retain evidence.
SIGINT/SIGTERM preserve failure status and release ownership after foreground work
ends. A signal sent only to Bash is deferred while its foreground command runs;
it does not release a lock underneath an active build.

Dead launcher locks are reclaimed only after both the recorded launcher and its
mutating foreground worker have exited. Unknown, malformed, or live owners fail
closed: stop the relevant launchers/build workers, inspect the records, then remove
only `samples/iosApp/build/.ios-launch.lock/{pid,worker}` and the empty lock directory.
The empty `.ios-launch.lock.guard` file is intentional: Python's standard-library
kernel lock serializes metadata recovery without the nonstandard `flock` command.
Never unlink that guard or remove the build directory while a launcher is running.

`scripts/tests/run-ios-app-test.sh` drives both real shell entry points with fake
macOS tool boundaries, including repeat runs, failure/signal cleanup, stale/live
owners, simultaneous recovery, and external output directories. These lifecycle
tests do not constitute a simulator build, UI execution, or device validation.

On macOS, `./gradlew :iosApp:checkIosProjectGeneration` uses real XcodeGen and
`xcodebuild -list` in a disposable source fixture. It verifies the application,
UI-test, and release callers' generated schemes, product names, and load-bearing
configuration without building or booting a simulator. CI and the release gate
run this separately from the fake-tool lifecycle tests.

## Stream-delivery regression matrix

`FakeConnectionPair()` preserves exact write boundaries by default. Opt in to
`WireDelivery.Fragmented(seed = 138)` or `WireDelivery.Coalesced()` for stream
coverage; `forEachWireDelivery` runs all three and prints the selected mode
and seed. Coalescing drains only queued writes, never waits for a full batch,
and caps reads at 8 KiB. Write logs and byte order are unchanged.

Fixture contract tests pin byte conservation, deterministic fragments, queued
coalescing, bounds, EOF, and error propagation. Selected Noise transport,
envelope, session, file-transfer, and authenticated kit integration cases run
the same assertions under every mode. Run them with
`./gradlew :p2p-core:jvmTest :p2p-core:iosSimulatorArm64Test --console=plain`.
These are in-process tests, not kernel short-write/backpressure, independent
interoperability, real filesystem durability, or physical-network evidence.

## Frozen wire compatibility checks

The [secure-v2 golden suite](wire-goldens.md) consumes committed synthetic hex independently of the live encoder,
then checks the production encoder against the same bytes. It covers the composed handshake/HELLO/message prefix,
four envelope variants and both kit-level v1/v2 rejection directions. Common suites run on JVM/Native; selected
Android-source wrappers run on the host JVM. See that guide for focused commands, exact provenance and the policy
against automatically refreshing fixtures. These are regression checks, not independent or device interoperability.

## Authenticated kit fixtures

Use `commonTest/.../testfixtures/createSecureTestKit` for new secure session
tests. It uses the production builder, real platform cryptography, synthetic
in-memory identity storage, explicit peer authorization, and strict session
invariants. The older `createTestKit` intentionally defaults to plaintext v1;
it is not representative of the shipped security default. Copy fake raw writes
with `CopyingRawConnection` so production buffer wiping cannot mutate queued
fixture bytes. Own kits with the diagnostic scope (or an existing equivalent teardown),
and clear stores owned by the test after terminal stop.

`SecureSessionLifecycleTest` gates all four authenticated simultaneous-open
setups before registration, verifies the surviving wire and actual losing
cipher-array wipes, and covers cancellation, outgoing-only reconnect, fresh
epochs, disabled reconnect, and terminal shutdown under all three wire modes.
`KitStrictInvariantsTest` proves the secure fixture's store invariant net.
Run these alongside `SecureSessionIntegrationTest` with the core JVM/native
command above. Provider-internal key erasure, OS identity persistence, physical
network behavior and independent cryptographic assurance are not established
by these synthetic tests.

## Failure assertion precision

Prefer `assertFailsWith`/`assertIs` plus the error's classification fields and
original cause over diagnostic wording. For `P2pError.FileTransferFailed`, pin
`kind`, `phase`, `retryability`, and `transferId`; when a fixture supplied a
cause, compare its identity. Do not duplicate that contract with a substring
of the same cause message.

Do not remove strings mechanically: parser field/packet-family discriminators,
non-disclosure assertions, explicit timeout/cleanup reason contracts, and
intentional logger diagnostics remain meaningful when no typed alternative
exists. A broad `ProtocolError` or `IllegalArgumentException` alone may not
identify the failed check. Do not change public error ABI just to simplify tests.

## Android diagnostic compatibility

The shared sample diagnostics use the pinned Kotlin clock's API-24/25 fallback,
not unguarded `java.time`. UTC evidence naming uses Kotlin's ISO parser while
preserving leap-second/end-of-day normalization and the invalid-input epoch fallback.
NIO file APIs are isolated behind an availability check. Android 24/25 replaces
same-directory evidence through checked POSIX-backed `File.renameTo`, without
deleting the original first; JVM/API-26+ retains the existing NIO provider policy.
No extra desugaring dependency or higher minimum SDK is required. Diagnostic ZIPs
do not promise power-loss durability or atomic publication on every NIO provider.

```bash
./gradlew :p2p-sample-diagnostics:test :p2p-sample-android:lintDebug \
  :p2p-sample-android:assembleDebug --console=plain
```

Missing-class tests exercise actual recorder/export code, failures and repeated replacement;
classloader-local SDK stubs also execute the pinned Kotlin clock's 24/25 branches.
These are host models, not ART. POSIX rename replacement is exercised on supporting
hosts; other hosts assert failure preserves existing bytes rather than skipping.
Inspect packaged call sites and the API guard when changing this boundary. On a
real API24/25 runtime, enable test diagnostics, record a session, export twice and
verify both ZIP checksums and the second export's new events. Repeat on API26+.
Keep that runtime/device validation pending until actually executed.

## Android diagnostic composition tests

```bash
./gradlew :p2p-sample-android:testDebugUnitTest \
  --tests 'dev.p2pkit.sample.android.DiagnosticCompositionTest' --console=plain
```

This suite runs the screen's production snapshot bridge in a real Compose
`Composition`/`Recomposer`, with explicit virtual frames and one collector. It
covers event-only and session-only invalidation, summary refresh, filters,
pause/resume, successful harness clearing without another event, source replacement,
disposal/re-entry and a 20,000-event burst against a bounded recorder. Separate
clear tests preserve failure/retry behavior; source assertions connect the bridge
to the actual screen. Do not substitute an unread delegated local for the revision
key or cache history without invalidating successful clears.

Robolectric supplies API35 tracing/snapshot services in the Android unit-test JVM.
These tests use the configured Gradle daemon JVM; Java17 source/target compatibility
does not select the test fork's runtime. Add `--info` to inspect the actual test-executor
command. The framework is locked/checksummed, an explicit test input, and resolved offline at test runtime;
the test fork is bounded to 1 GiB with a two-minute task deadline. This is host
Compose/snapshot evidence, **not rendered Android UI, ART, physical-device behavior
or frame timing**. On a device, leave the viewer untouched while traffic arrives,
then verify pause, filter changes, resume, clearing and reopening separately.

The separate [rendered #317 harness](android-diagnostics-ui.md) uses an explicitly
named framework instrumentation component on an admitted, owned emulator. It
requires actual display/frame evidence, an untouched interval and an inert-bridge
mutation control. Its source or APK assembly is not a rendered pass, and it does
not replace the default API37 permission runner or any physical-device matrix.

## Shared Android acceptance artifacts

The debug app/test APK pair can serve compatible #317/#324/#372 cases without
rebuilding the whole repository per issue. First admit the actual SDK and host,
freeze a reviewed clean candidate, and initialize a new
[immutable executor state and `leaf` helper](mac-handoff.md#4-branch-agnostic-immutable-execution).
The Android sample's `build` directory must be absent when that state is initialized.
Then run one producer and inspect its exact outputs in the same owned state:

```bash
leaf gradle android-acceptance-build 2400 \
  :p2p-sample-android:assembleDebug :p2p-sample-android:assembleDebugAndroidTest \
  :p2p-sample-android:retainDebugAcceptanceArtifacts --console=plain
# Continue only after the producer and its checked receipt both succeed.
leaf command android-acceptance-inspect 240 python3 scripts/verify-android-acceptance-artifacts.py \
  --build-receipt "$P2PKIT_AUDIT_STATE_DIR/host-android-acceptance-build.json" \
  --build-purpose android-acceptance-build
```

The explicit, uncached producer consumes public AGP artifact providers for both
merged manifests and the sole unfiltered `SINGLE` APK per component. It retains
manifests plus `artifacts.json` under the sample's
`build/reports/android-acceptance/debug/`; task paths are actual provider
dependencies, not guessed names or claims that every task ran. The map is an
**AGP API metadata projection**, not original AGP metadata or source/run authority.
It refuses existing/partial captures and requires a POSIX-permission filesystem.
Maps/manifests are bounded to 1 MiB each and APK reads to 512 MiB each; version
names are limited to 4096 UTF-16 code units without characters below U+0020.

The read-only inspector requires the successful canonical same-state Gradle
receipt, newly retained hash-matching reports, and unchanged live outputs. It
runs the selected SDK's actual `apkanalyzer manifest print` against both APKs
and compares generated and packaged identities with the maintained manifest
comparator. Keep `ANDROID_HOME` unchanged from the admitted build. Windows
analyzer launch is not admitted here. Results live at
`$P2PKIT_AUDIT_STATE_DIR/evidence/android-acceptance-artifacts/`; success remains
provisional until the inspector's outer receipt confirms source and worker cleanup.

Retain both APKs, maps, generated/packaged XML, original logs and receipts before
scoped cleanup; the executor does not automatically retain the APKs. Keep these
bytes while dependent UI cases need them. This artifact check neither runs nor
admits a guest: rendered untouched updates, actual save/restore and secret-display
cases, API37 compat/permission/LAN/revocation behavior, and distinct mutation
controls still need their own applicable runtime evidence. It does not replace
the guarded Linux smoke profile or any physical-phone criterion.

`python3 scripts/tests/verify-android-acceptance-artifacts-test.py` exercises only
map/receipt guards and small file fixtures, not AGP compilation, real APK inspection
or Android behavior. The producer is not added to ordinary `check`, assembly or
publication tasks.

## Android UI controller primitives (not a launcher)

`scripts/android_ui_controller.py` contains reusable #317/#324 controller
boundaries, **not an admitted runtime entrypoint**. It has no SDK/image allowlist,
guest allocator/booter, host resource sampler or ART-lifetime observer. There is
no runtime CLI or `trusted`/`passed` bypass in that module. The separate
[native adapter](#owned-mac-android-ui-adapter) composes these primitives; its
source review, exact tool/image and real command-format admission remain required,
not evidence that a phone or another computer is intrinsically required. Do not instantiate the
Linux-only `Smoke`, adopt an owner's AVD, or treat installed SDK metadata as a
reviewed native profile.

The core composes the existing producer map/file checks and generated/packaged
manifest comparator with successful **canonical same-state** build and inspection
receipts. It requires the producer's exact three-task request, strict fresh
executed arguments, original inspector arguments, source/job/host/home identity,
stop0 and no unresolved workers/errors. The inspector's provisional result is
insufficient without its finalized outer receipt and agreeing original
stdout/map/manifests/APK bindings. The new core neither generates another map nor
runs another inspector. `installed_pair` separately reads back both complete
installed base APKs and compares their actual hashes with that producer; it also
requires actual User0, distinct package UIDs and target37 observations.

Command retention keeps original stdout/stderr, argv, deadlines, exit and both
EOF observations. Exit0 without EOF is incomplete. Bounds/timeout failures keep
their real prefix and original failure; only the maintained outer Darwin ownership
adapter may drain unresolved descendants. There is no process-name killing.
The exact UI selector accepts only case317 or324 with the four existing guest
arguments and fixed180s/240s instrumentation deadlines.

Whole-tree collection uses narrowly quoted `adb exec-out run-as` `toybox stat`,
`ls -1a` and `cat` against only `no_backup/ui-<case>-<token>`, with an immediate
`no_backup` parent identity check. It retains hidden zero-byte locks and empty
directories, rejects links/aliases/foreign UIDs/unsafe names, and preserves unknown
safe entries rather than filtering them to make the content checker pass.
Listings/stat/read outcomes, hashes, incomplete originals and before/after graph
observations remain private. A new-only `before-retirement-partial` snapshot is
never relabeled as an `after-retirement` capture. Stable metadata and complete
reads are not proof that ART retired, nor hostile-filesystem atomicity.

Collection reuses the passive verifier's256-file/64-directory/depth6, PNG16MiB,
Parcel1MiB, text2MiB and aggregate64MiB/1GiB bounds. Each collection has a separate
120s cap; each ordinary metadata command at most40s. Unknown oversized entries
remain in the owned guest with a failed capture, not a truncated accepted packet.
`attempt_all` attempts every source-owned finally action despite earlier failures
or interruption, but labels a returned action only `RETURNED`, **not `RETIRED`**.
The separate exact handle waits retain original statuses and stay20s for the
emulator and10s for adb. The content verifier's raw result is written unchanged;
its `UNPROVEN`/`NOT_ACCEPTED` and missing visual/mutation reviews remain intact.

Before native execution, the adapter and its operator must:

1. Admit exact native Mac SDK/emulator/image provenance and actual command formats,
   read-only shared dependencies, rendering/display/interactive eligibility and
   fresh disk/RAM observations. Hold the shared serial execution lease and the
   same-state Gradle lease; do not overlap a build with the guest.
2. Enter the maintained immutable command ownership domain and create one wholly
   new `state/fixtures` tree, private homes/keys/tmp/AVD/userdata and foreground adb
   server. Refuse existing state/devices, bind actual handles/ports/AVD identity,
   and install the unchanged APK pair without `-g`. No snapshot or account sign-in.
3. Observe actual package PID/start/UID and Activity/ART lifetime with supported
   guest mechanisms. Preserve failure/partial evidence before destructive actions,
   prove exact target retirement before stable final capture, explicitly shut down
   the owned emulator/server, attempt both handle waits, and require the terminal
   outer receipt's same-home stop and Darwin worker retirement. Unknown retirement
   blocks another conflicting run; a successful query is not absence by itself.
4. Review the bounded whole-host envelope and every failure/cancellation path,
   retaining required originals before guarded exact-root cleanup. Only then run
   the positive and separate mutation cases and obtain independent actual-result
   review. No whole-issue, #372 LAN/compat, physical-phone or release credit follows
   from this controller preparation.

Focused modeled controls (no Gradle, SDK, real child or guest):

```bash
/usr/bin/python3 -I -B -S scripts/tests/android-ui-controller-test.py -v
```

## Owned Mac Android UI adapter

`scripts/run-android-ui-tests.py` is the explicit local #317/#324 execution adapter,
not a recorded runtime pass. After independent source review, use the ordinary
admitted Mac ARM session, shared host/Actions lease and clean immutable state.
Its same-state `LeafLock` prevents a concurrent Gradle leaf during the guest.
The successful canonical APK producer, manifest inspector and **archive capture**
receipts must all belong to that same source/state/home. The adapter rechecks the
archive originals and installed members itself; a separate `admit` receipt is not
a substitute for the genuine capture receipt. Shared SDK tools/images stay read-only.

After those prerequisites and current resource admission, retain the **exact root
launch below**, including the 2100-second outer timeout, then check its terminal
receipt with the [maintained `leaf` helper](mac-handoff.md#4-branch-agnostic-immutable-execution):

```bash
leaf command android-ui-positive 2100 /usr/bin/python3 -I -B -S scripts/run-android-ui-tests.py \
  --cases 317+324 \
  --build-receipt "$P2PKIT_AUDIT_STATE_DIR/host-android-acceptance-build.json" \
  --build-purpose android-acceptance-build \
  --inspection-receipt "$P2PKIT_AUDIT_STATE_DIR/host-android-acceptance-inspect.json" \
  --inspection-purpose android-acceptance-inspect \
  --archive-receipt "$P2PKIT_AUDIT_STATE_DIR/host-android-archives-capture.json" \
  --archive-purpose android-archives-capture
```

Only `317`, `324` and ordered `317+324` selections are admitted. There is no
caller-supplied serial, AVD, command, component, token, source, profile or timeout.
The adapter binds the active owner to this isolated product request. Maintained
`start.json`/receipts do **not** record the outer timeout; neither their presence
nor the adapter's declared bounds certifies it. The root's original launch is a
separate required review input. The product has one 1800-second monotonic budget
with a 420-second finalization reserve, not a fresh deadline for each case.
Instrumentation stays at 180s/240s; boot at 180s, each collection at 120s, the
whole ART-retirement phase at 20s, and emulator/server handle waits at 20s/10s.

The single fresh fixture owns private homes/adb keys/tmp/AVD/userdata and foreground
adb/emulator handles. It refuses preexisting `state/fixtures`, busy fixed console
ports, unowned listeners, additional devices and unsupported command formats.
It selects the archive gate's exact ARM image/emulator, with pre-boot portrait
1600×2560 at 200dpi, two cores, 2048MiB RAM, host GPU and no snapshots. Version text
and tool hashes are identity observations, **not independent SDK authenticity or
native-architecture admission**. Real listener, adb/AVD, property, numeric process,
`/proc` and Activity dump formats still require actual retained native review;
unknown formats HOLD rather than becoming successful absence. Archive recheck
retains its 8GiB free-space floor; guest checks require 5GiB free disk, normal Mac
memory pressure and 4GiB free-plus-inactive pages (not Linux `MemAvailable`).

Each case installs the unchanged APK pair without `-g`, reads both installed APKs
back, then runs its exact component with a fresh token. The observer does not
inject input during the harness. Actual PID/UID/kernel start ticks remain distinct
from the harness's Java elapsed-start milliseconds. It preserves partial originals,
explicitly force-stops only the fresh packages, proves ART/Activity absence, captures
stable final originals and runs the unchanged passive verifier. A two-case episode
requires successful retention and retirement, exact uninstall/absence, then a new
install/token; any failure stops before the next case. Explicit teardown is not a
claim that ART exited naturally, nor a rescue of a failed harness.

Finally attempts both foreground shutdowns, both handle waits and both original
stream retirements even after earlier failure. The outer executor alone performs
fallback Darwin-domain drain and same-home wrapper stop. Keep
`state/evidence/<owner>/android-ui/`, all APKs/archive originals and required private
screenshots/Parcels through terminal receipt and independent review; then hash and
clean only proved-owned disposable fixture/output paths. Unknown retirement blocks
the next conflicting operation. No automatic deletion, global adb stop or owner AVD
adoption occurs. `CAPTURED_PENDING_OUTER_RECEIPT_AND_REVIEW` and the passive verifier's
unchanged `UNPROVEN`/`NOT_ACCEPTED` fields are not visual or whole-issue acceptance.
Both positives still need their separate source-bound mutation controls and pixel/
Parcel/lifecycle review. This lane does not execute #372, LAN permission enforcement,
physical phones or publication. Use one case for each separately reviewed mutant.

`/usr/bin/python3 -I -B -S scripts/tests/run-android-ui-tests-test.py -v` checks only
modeled parser, budget, ownership, ordering and failure-finalization boundaries;
it does not admit the real command formats, launch a guest or review rendered UI.

## Android archive-input capture (not runtime qualification)

`scripts/android_archive_admission.py` is a separate read-only archive/installed-byte
gate for the exact Mac ARM emulator36.6.11 build15507667 and Android37.0
`google_apis_playstore_ps16k;arm64-v8a` r05 image. It does not extract, install,
accept licenses, run SDK tools, boot a guest, alter the shared SDK or admit a native
runtime profile. The native controller adapter and its host/guest acceptance
remain separate prerequisites; this is not a replacement Linux smoke profile.

The operator must first hold the campaign's shared local/remote execution lease,
check actual Actions queues and current resources, and use the ordinary admitted
native Mac session and existing owner-accepted SDK. That shared coordination is
**not** a repository lock or a caller `trusted` flag. Inside an active immutable
`kind=command` leaf, this helper separately acquires the maintained same-state
`LeafLock`; it releases that lock before the outer executor's same-home wrapper
stop and worker drain. No concurrent SDK writer/build/guest is permitted. An
unknown or failed retirement blocks the next conflicting operation.

With a clean reviewed source, the [Mac handoff's executor and `leaf`](mac-handoff.md)
initialized, and literal `ANDROID_HOME` consistent with any `sdk.dir`, the commands are:

```bash
leaf command android-archives-capture 2100 python3 -I -B -S scripts/android_archive_admission.py capture
# Inspect originals and the canonical terminal capture receipt before reuse.
leaf command android-archives-recheck 2100 python3 -I -B -S scripts/android_archive_admission.py admit \
  --producer-receipt "$P2PKIT_AUDIT_STATE_DIR/host-android-archives-capture.json" \
  --producer-purpose android-archives-capture
```

Capture starts new private originals from the fixed official URLs with system
`/usr/bin/curl`, normal certificate/hostname validation and controlled credential-free
configuration. Proxy/CA/loader overrides reject; no insecure option, retries, ranges,
resume or GET redirects are allowed. Curl globbing is disabled: admitted query text
remains one literal URL for both HEAD and GET. The emulator's published redirector
may use at most three HTTPS HEAD redirects to the exact archive path on `dl.google.com` or
the constrained Google `r<number>---sn-<route>.gvt1.com` CDN host form. Unknown
origins/paths and HTTP framing reject. Each archive gets exactly one whole GET;
HEAD is not download evidence. Original argv, headers, bytes, curl TLS/status fields,
EOF/exit observations, times and binary identity remain private.

The image must be exactly2,216,674,212 bytes and all32 expected regular members;
its label means **the content supplied by the authenticated official origin at
capture time**, not publisher build/signing/history attestation. Its
`publisherWholeArchiveChecksum.image` stays `null`; the computed capture SHA256
is not renamed a Google-published digest. The separate383,903,546-byte emulator
must match its source-pinned Google-published SHA256. Both complete ZIP32 graphs,
local/central headers, extents, descriptors, decompressor EOF, lengths/CRC and
every installed member's bytes/mode are checked without extraction. Inferred
directories count too. Links require identical safe in-root text and cycle-free
targets. Only exact, identity-checked, hash-retained `package.xml` installer records
may be extra; they cannot redirect the package or confer code/license authority.
Unknown/missing/aliased/changing entries reject before unknown file content is read.
These are coordinated stable-input checks, not hostile-filesystem atomicity.

The archive-only policy requires a continuous 8 GiB free-space floor on the same
filesystem as the state/evidence. Before capture, free bytes must be at least
8 GiB + 3 GiB spare reserve + the sum of both exact compressed archive byte pins:
**14,411,737,822 bytes** for this pair. The 3 GiB is additional spare capacity, not
the archive allocation. No extraction, SDK mutation, build or guest may consume
this phase's margin. The dependency writer's separate **16 GiB floor is unchanged**
and requires fresh resource/lease admission afterward; archive success never
admits the writer.

Other bounds include 64KiB stream chunks/HTTP headers,4MiB JSON,16MiB total metadata,
4,096 ZIP members,
8,192 installed graph nodes,3GiB/member and4GiB expansion/archive. Image/emulator
GET caps are900s/300s, each HEAD/connect/stall cap30s, each comparison300s and the
complete helper1800s. Unsupported structure or a bound failure is HOLD, not
permission to expand the profile silently. Failure prefixes and partial reports
remain incomplete; the outer owner alone drains unresolved curl children.

Each command prints the path/size/SHA256 binding of its new result beneath its
canonical invocation evidence directory. Recheck requires the exact isolated
capture request, successful canonical same-source/state/host receipt, stop0/no
survivors, agreeing original stdout, all retained bindings and a fresh whole
installed comparison. Neither result is accepted without its own terminal receipt
and independent actual-result review. Preserve both whole archives, metadata,
partial failures and review evidence until reviewed retention/owned cleanup.
No automatic cleanup deletes mismatches or shared dependencies.

`python3 -I -B -S scripts/tests/android-archive-admission-test.py -v` uses only tiny
synthetic archives/files and modeled curl/receipt observations, never network or
native tools. Even genuine archive equality proves neither #317/#324 rendering
and lifetime behavior nor #372 loaded APEX/system-flag/cache/grant/LAN semantics.
It is not physical-phone, independent-interoperability or release qualification.

## Retained Android UI content checks

`scripts/verify-android-ui-evidence.py` passively checks already-retained #317 or
#324 originals. It does not collect files, install APKs, run instrumentation,
import input-supplied code, or admit a guest. Keep the complete private originals
in an exclusively owned `ui-317-<token>` or `ui-324-<token>` directory, with the
original instrumentation stdout **outside** that directory. Use physical paths
without symlinks/reparse points or hard-linked aliases. Supplied source/token
expectations are declarations, not source/install provenance.

With the reviewed clean-source executor and `leaf` helper initialized, for example:

```bash
leaf command android-ui-317-content 120 python3 scripts/verify-android-ui-evidence.py \
  --case 317 --token "$UI_TOKEN" --source-commit "$SOURCE_COMMIT" --source-tree "$SOURCE_TREE" \
  --evidence-dir "$RETAINED_UI_DIR" --instrumentation-stdout "$RAW_INSTRUMENTATION_STDOUT"
```

Use case `324` and a unique purpose for the credential case. Both exact named
components emit one terminal status bundle and an identical result bundle; the
LAN runner's multi-frame parser is not their contract. #317 emits a terminal
cleanup field and report schema/token/UID fields; #324 does not. No invented
collector/install receipt or caller-set `trusted`/`passed` flag grants acceptance.

The JSON result distinguishes:

| `contentStatus` | Exit | Meaning |
| --- | --- | --- |
| `CONSISTENT` | 0 | Positive harness claims and checked retained bytes agree; still pending review. |
| `HARNESS_FAILED` | 1 | The retained terminal/report describe a failure, not a passing mutation control. |
| `INCOMPLETE` | 2 | A required terminal, field or companion is absent/truncated. |
| `REJECTED` | 3 | Malformed, contradictory, unsupported or out-of-bounds input. |

Every result keeps `provenance=UNPROVEN`, `runtimeAcceptance=NOT_ACCEPTED` and
visual/mutation review `NOT_PERFORMED`. Inputs are never rewritten or removed;
a rejected packet may have only a partial output file manifest. Preserve its
whole original directory independently, including failed/partial evidence.

The checker enumerates/hashes admitted files and checks case-specific claims:
#317's six positive files, active-session recorder prefix, single revision/event
addition, untouched interval and displayed-tree/count/frame references; #324's
32 PNG/tree pairs, original Parcel/report, 13 cells, eight cleanup steps, modeled
permission/join claims, reveal timing and layout hashes. Retain the entire #324
`fixture` subtree, including the empty hidden diagnostic `.lock`. Raw editable
text containing the synthetic secret is not by itself a pixel-exposure finding.
PNG checking covers the signature/IHDR/CRC, byte hash and dimensions, **not**
complete image decoding or visual review. Parcel checking compares original
length/hash and reported inspection/order; it does not deserialize Android state.

Existing writer limits remain PNG16 MiB/16,777,216 pixels, Parcel1 MiB and
result/events/#317 trees/each rolling diagnostic generation2 MiB. Additional
**passive-host** guards are: #324 tree/saved-state JSON2 MiB (those writers have
no explicit byte cap), stdout8 MiB, signed-64-bit JSON integers, 256 files,
64 directories, depth6, aggregate64 MiB for #317/1 GiB for #324, 64 KiB read
chunks and a 60-second internally checked deadline. Keep an outer command bound;
these snapshot/change checks are not hostile-filesystem atomicity. Never truncate
an original or enlarge a limit mid-run to make it pass.

`python3 scripts/tests/verify-android-ui-evidence-test.py -v` exercises this policy
using tiny synthetic files, not ART, real UI pixels or a decoded Android Parcel.
Actual runtime admission still needs the reviewed collector, current source and
installed-APK bindings, raw EOF/exit/deadline records, complete retention, exact
ART/guest retirement, positive and distinct mutation runs, and independent
full-resolution review. The shared artifact producer above still requires its
exact three-task argument list; do not append a Desktop CLI build to that leaf.

## Android framework-adapter tests

Run `./gradlew :p2p-network-provisioning-android:verifyAndroidAdapterTests --console=plain`
for the provisioning adapter tier, also required by the module's `check` task.
The tests instantiate the production `WifiManagerWrapperImpl`, handles, and
ownership helpers; Robolectric framework shadows deliver controlled callbacks
and record native calls. Hotspot credentials and lifecycle run on APIs 26/29
and 30/35; Wi-Fi joining, cancellation, binding ownership, and cleanup run on
APIs 29/30/35. The gate rejects missing, empty, failed, or skipped suites and
missing SDK execution markers. The host-test task has a two-minute deadline
enforced by Gradle outside the test JVM; an uninterruptible monitor deadlock
fails the task and terminates the fork, including stuck coroutine/fixture teardown.

Framework JARs are pinned in the version catalog, resolved through Gradle's
locks/checksums, and registered as test inputs. Robolectric's runtime resolver
is offline; it cannot fetch unverified SDKs. API 35 is the newest selected host
SDK compatible with the JDK 17 test toolchain (API 36 requires Java 21).
These are host/shadow tests, not ART, Binder, radio, OEM, permission-revocation,
or physical-device evidence. The broader runtime/target matrix remains tracked
in [#157](https://github.com/p2pKit/P2pKit/issues/157); permission-error mapping
is a separate correction in [#195](https://github.com/p2pKit/P2pKit/issues/195).

## Dependency updates

### Independent pin expectations versus fixture inputs

Positive version/checksum literals in policy gates are deliberate **tripwires**, not stale copies. A source-only
bump must fail until the maintainer independently reviews the new artifacts and updates the matching expectation.
Never calculate an expected value from the file being checked; that would turn the approval check into a tautology.
Counterparts are named by stable keys/sections, not line numbers that drift during updates:

| Independent gate | Counterpart to review and update together |
| --- | --- |
| `scripts/tests/check-kotlin-toolchain-policy-test.sh` | `gradle/libs.versions.toml`: `kotlin`, `binary-compatibility-validator` |
| `scripts/check-host-toolchain-verification.py` | Catalog `kotlin`/`agp`, reviewed AGP/AAPT2 version pair, and all current Native/AAPT2 host classifiers in `gradle/verification-metadata.xml` |
| `scripts/check-gradle-wrapper.sh` | `gradle/wrapper/gradle-wrapper.properties`: URL/distribution checksum; reviewed wrapper JAR and both launchers |
| `scripts/tests/release-workflow-test.sh` | `scripts/install-xcodegen.sh`: version/archive checksum; `build.gradle.kts`: Netty and both jsoup floors; Android sample's Netty lock |

`scripts/tests/release-workflow-test.sh` checks every active `io.netty` lock entry, not a list of historical bad versions.
It compares numeric `major.minor.patch.Final` values with an independently supplied floor; unknown qualifiers fail
closed for review. The separate positive HTTP pin still requires the reviewed version in the lock.

Consumer generation and fake XcodeGen binaries instead use versions as **inputs**. The consumer guard recognizes the
maintained expanding root-build heredoc and requires Kotlin/AGP input variables, rejecting numeric plugin pins elsewhere
too. Review the guard when changing that generator's shape. XcodeGen's normal fixture input follows the sourced installer;
a second synthetic version exercises the same assertions without today's pin. Its independent release tripwires remain
in the release-workflow test. Run `ruby scripts/tests/check-version-input-policy-test.rb`
for deterministic future-version/negative controls (also called by the toolchain policy); it performs no Gradle build.
These are static source/lock and synthetic installer checks, not dependency resolution or publisher authentication.

The isolated consumer's build tools use `scripts/consumer-buildscript.gradle.kts`
before its plugin requests. Exact constraints come from a data copy of the reviewed
root `buildscript-gradle.lockfile`; unused root plugins are not pulled into this
smaller graph. Unknown modules and changed selections fail during classpath
resolution, before plugin application. Only the buildscript classpath is affected,
not the published library dependencies being tested. Audit mode also binds the
copied lock and generated root recipe before/after compilation. Root lock/floor
and checksum review still applies; a checksum for an older tool is not permission
to bypass this version binding. Changes to this policy require an actual strict
consumer configuration check, not only the shell fixture's synthetic success.

### Reviewed update workflow

Dependency and wrapper updates remain fail closed. A version-catalog change
must carry reviewed SHA-256 verification metadata; a wrapper change must carry
the complete wrapper plus its pinned distribution and file checksums. AGP and
the Gradle wrapper are grouped into one Dependabot update because they form one
compatibility unit.

From a dedicated update branch, generate candidates and independently verify
every newly admitted artifact against its repository bytes and publisher
provenance before committing. This maintainer workflow requires `curl`, `gpg`, `gpgconf`,
an authenticated GitHub CLI (`gh`), and Python 3:

```bash
scripts/prepare-dependency-update.sh origin/main
```

The base must be an available, independently accepted ancestor, not an invented
older ref chosen to manufacture new artifacts. The caller freezes its commit
identity before the complete writer and strict post-write checks. For a
lock-membership-only refresh, it may reuse that base's provenance **only** when
valid, nonempty verification metadata is byte-identical and every other tracked
input is unchanged, except existing regular project `gradle.lockfile` files.
The root `buildscript-gradle.lockfile` and `settings-gradle.lockfile`, provenance
policy, catalog, wrapper, scripts and source must remain unchanged; nonignored
untracked inputs also prevent reuse. After independently reviewing source-only
changes with unchanged dependency/provenance inputs, select that reviewed commit
explicitly (for example `scripts/prepare-dependency-update.sh "$(git rev-parse HEAD)"`).

This narrow `REUSE` result is **not fresh remote cryptographic verification** or
proof that the operator selected an accepted base. Retain the base's acceptance,
the emitted source/base/metadata identities, all before/after locks and metadata,
and the complete original phase results for independent candidate review. Added
artifacts still require the existing remote curator; deleted history, changed
existing hashes/trust configuration, invalid metadata/base, and failed earlier
phases cannot pass through reuse. The standalone curator still rejects empty
new-artifact input. Never promote partial writer output or use this path to
qualify an unrelated dependency proposal or an advisory exception.

The artifact-review workspace follows `${TMPDIR:-/tmp}`; an unusable selected directory fails rather than silently
moving downloads to another volume. Its small GPG home is separately created under `${P2PKIT_GPG_TMPDIR:-/tmp}`.
Both parent directories must already exist. Choose a short GPG root: its physical path, random directory name and
longest standard agent socket must be at most 102 bytes: libassuan's strict guard reserves two bytes in macOS/BSD's
104-byte Unix-socket field. Long or space-containing artifact paths remain usable without regressing macOS GPG. For example:

```bash
TMPDIR=/large-volume/tmp P2PKIT_GPG_TMPDIR=/short/tmp scripts/prepare-dependency-update.sh origin/main
```

Normal completion, errors and handled HUP/INT/TERM signals remove the workspace and stop workers belonging to the
review keyring before removing it. If worker shutdown fails, the invocation fails and reports the retained keyring
path for an explicit `gpgconf --homedir <path> --kill all` retry; remove that directory after shutdown succeeds.
SIGKILL/power loss cannot run shell cleanup. These paths contain public artifacts/keys, not a personal secret keyring.

The reviewer also compares an authoritative repository SHA-256 sidecar when
one is published. Maven Central does not publish such a sidecar consistently,
so the normal path requires both an exact match between downloaded bytes and
the committed SHA-256 and a valid detached signature whose issuer identity
matches the independently retrieved public key. If a v4 signature supplies
only its 64-bit issuer key ID, the reviewer requires one exact matching
primary key or subkey and reports the full fingerprint established by
cryptographic verification. A narrowly pinned entry in
`gradle/plugin-provenance-policy.txt` may instead authorize a canonical Gradle
plugin JAR whose GitHub SLSA attestation matches the exact repository, release
tag, workflow, and source commit. Unsigned plugin marker and module metadata is
parsed fail closed and must bind to that trusted JAR and the locked dependency
graph. The script uses an isolated temporary keyring and never adds broad
artifact/key trust to Gradle metadata.

The plugin validator rejects empty input and reads at most one byte beyond
each limit before parsing: marker POMs 64 KiB, module metadata 1 MiB, and
attestation results 8 MiB. The dependency-policy tests cover exact limits,
oversized/growing files, bounded reads, and stream cleanup on failure.

Dependency submission explicitly passes `--dependency-verification strict`:
the pinned Gradle action otherwise disables verification for its entire build.
The injected graph plugin's JAR, module metadata, and POM are checksum-listed
after detached-signature review. When updating that action, review its injected
tooling as well; never disable verification to accommodate new artifacts.
`scripts/tests/release-workflow-test.sh` enforces the strict argument policy.
Local graph generation is not evidence of successful GitHub API submission.

When a direct artifact lookup finds no file, the reviewer can use that
component's checksum-listed, detached-signed `.module` as a locator. It accepts
only an unambiguous local file or sibling-version file within the same
repository, group, and module; metadata is limited to 1 MiB. Both the locator
and the relocated artifact must independently pass checksum and signature
verification. Remote URLs, redirects, ambiguous paths, and unsigned locators
are not supported. This does not expand the unsigned-plugin exception above.

Before pushing, inspect the complete lock and metadata diff and run:

```bash
scripts/check-dependency-update.sh <base-commit> <head-commit>
scripts/run-release-gate.sh
```

CI executes the range-aware update check before Gradle so an incomplete bot PR
fails quickly instead of spending the Complete Gate discovering missing
artifacts. Candidate generation is deliberately not automatic: newly downloaded
checksums are not trusted until the maintainer review succeeds.

Toolchain updates must curate foreign-host artifacts as well as the updating machine's resolved graph.
The pre-build Kotlin policy requires all four Kotlin/Native host archives (Linux x64, macOS arm64/x64,
Windows x64) and all three AAPT2 classifiers (Linux, macOS `osx`, Windows), with independently pinned
Kotlin and AGP/AAPT2 versions. Run `python3 scripts/check-host-toolchain-verification.py` and
`python3 scripts/tests/check-host-toolchain-verification-test.py` after curation. The checker enforces
complete, unambiguous exact SHA-256 records; it does not authenticate an arbitrary well-formed hash.
Every newly added archive still needs the byte/signature review above, and host execution remains a
separate gate. Preserve reviewed historical artifacts and strict verification; do not disable Native
tasks or checksum verification to work around an incomplete current-host refresh.

Kotlin's built-in ABI validator covers JVM and KLIB outputs but not Android
KMP artifacts. The separate `checkAndroidAbi` tasks read Kotlin metadata from
the compiled Android bytecode, so Android-only declarations such as
`P2pKitAndroid`, the URI file-transfer helper, and Android LAN/provisioning
entry points cannot change silently. An intentional Android API change
requires a manual review followed by the affected module's
`updateAndroidAbi` task.

The supplemental `checkJvmPublicConstants` and `checkAndroidPublicConstants`
tasks inspect compiled fields on baselined public owners, closing Kotlin-metadata
blind spots without freezing all Kotlin-internal bytecode. They run under each
applicable ABI check and module `check`; a full JDK with `javap` is required.
`./gradlew checkPublicConstantAbiPolicy` (or
`bash scripts/tests/check-public-constant-abi.sh`) exercises real compiled
positive/negative fixtures. See the [constant ABI policy](../compatibility.md#jvm-family-constant-abi-checks)
before changing any retained legacy symbol. Constant values and cross-platform
wire behavior still need their own tests; these are signature checks.

To revalidate the latest published artifacts rather than the source snapshot:

```bash
P2PKIT_CONSUMER_REPOSITORY_URL=https://repo.maven.apache.org/maven2 \
  scripts/check-published-consumers.sh --latest-published
```

Automated success is not physical-device or hostile-network evidence. See
[validation status](validation-status.md).
