# Audit-branch hosted validation

The [audit host workflow](../../.github/workflows/audit-host-validation.yml) is an
additive, read-only execution facility for one frozen audit-branch revision. It
neither replaces normal CI/release checks nor records a successful execution by
being present. Inspect the actual run, retained evidence and independent review
before claiming any host result. The overall audit and physical/independent
acceptance remain pending.

The maintained [host driver](../../scripts/run-audit-host.py) runs **components**.
Its `releaseGateMonolith` value is `NOT_EXECUTED_COMPONENT_REPLAY`: the unchanged
[`scripts/run-release-gate.sh`](../../scripts/run-release-gate.sh) has **not** been
executed by this workflow. Individual real component results are not permission
to print that script's complete-release-gate PASS or publish a release.

## Trigger, source and execution ownership

Only a push to `audit/complete-2026-09-04` that changes
`.github/workflows/audit-host-validation.yml` requests this workflow. There is no
PR, tag, schedule or manual-dispatch trigger. A branch-only push can bootstrap the
workflow without merging it into `main`; do not merge or change repository settings
just to register a manual workflow. Helper/document-only pushes intentionally do
not request another expensive run. Change the workflow's documented run-revision
comment in a focused, reviewed push when a new exact source revision needs testing.

Before that push, the operator must:

1. Finish the current repair and obtain fresh independent approval of its final
   revision. Review the execution infrastructure before its first triggering push.
2. Refresh queued/running Actions and hold the audit's **global build lease**.
   Pause local builds/tests and do not dispatch other workflows during this run,
   including cleanup and artifact retention. Do not cancel unrelated tasks.
3. Freeze the exact source and record the expected commit/tree. Inspect toolchain,
   disk/memory and external-access prerequisites; do not restore private evidence,
   credentials, machine settings or another user's cache into the checkout.
4. Push normally to the audit branch, then verify the run API's `head_sha`, each
   checkout/admission record and retained artifacts against that exact revision.

All three jobs use the same `${{ github.sha }}`, full Git history and
`persist-credentials: false`. The token has only `contents: read`; actions are
pinned by full commit. Runtime admission also verifies repository, existing-branch
push, exact ref/SHA/tree, clean tracked/untracked state, ancestry, non-deletion and
non-force, and the workflow path in the actual before/after diff. A GitHub path
filter fallback is not permission to execute a different event. A zero-before/new
branch event is rejected rather than silently substituted with `main`.

A single non-cancelling concurrency group and explicit `needs` jobs serialize this
workflow. There is **no matrix**. The group cannot serialize other workflows or
local builds, and GitHub can replace an older pending run even with
`cancel-in-progress: false`. Do not queue another triggering push while a run is
active or pending; preserve earlier failure/cancellation records.

## Ordered host scope

| Order | Role and fixed label | Selected tools | Components, not broader acceptance |
| --- | --- | --- | --- |
| 1 | Native Windows x64, `windows-2025` | Native Python, Java 21 then 17, checked-in `gradlew.bat` | Fresh core/LAN/provisioning library JVM suites; CLI/Desktop sample checks and distribution builds |
| 2 | Native Apple Silicon, `macos-26` | Xcode 26.5, native Python 3, Java 21 then 17 | Full platform `check`, policy/script gates, Android/Desktop samples, ABI/Dokka/SBOM, local publications/isolated consumers, XCFramework and Swift build/unit/UI simulator tests |
| 3 | Native Intel, `macos-15-intel` | Xcode 26.3, native Python 3, Java 21 then 17 | Original `ios-x64` platform profile: both core and LAN `iosX64Test` suites |

`macos-15` without `-intel` is not the Intel role. Rosetta, cross-compilation and an
ARM simulator pass do not establish native Intel execution. The Intel job's two
Kotlin suites are not an execution of the complete Swift bridge/sample `ENV-04`
procedure. Windows product commands do not run through WSL or a POSIX wrapper.
A sample packaging pass is not rendered headful Desktop observation.

Windows shell prerequisites use Git for Windows: the driver resolves native
`git.exe` from its `cmd` or `bin` installation layout, requires that installation's
`bin/bash.exe` and `usr/bin` tools, and validates native Git's `.windows.N` version
and Bash's `x86_64-pc-msys` or `x86_64-pc-cygwin` build target. The Cygwin target is
also used by bundled Git-for-Windows Bash; it does not admit standalone Cygwin Git.
The same absolute Bash executable is recorded and used for the wrapper-checkout
fixture, even if the ambient `bash` command selects WSL. Only its version probe and
fixture receive the Git `bin`/`usr/bin` PATH prefix for nested shell utilities;
native Python and `gradlew.bat` product commands keep the original host PATH.
Missing or unusable Git Bash fails closed with retained prerequisite diagnostics;
installing WSL or skipping the fixture is not a substitute. Linux process-boundary
fixtures do not establish actual Windows execution or checkout compatibility.

Runner/image documentation advertises availability, not actual allocation or
compatible installed tools. The driver records the real OS/image, architecture,
CPU/disk and tool versions; it requires the explicitly selected Xcode and supported
simulator. Missing tools/runtimes or native process-ownership capabilities fail
closed, without changing deployment targets, disabling required tasks or using
preview Xcode as a silent fallback. See [canonical Android setup](local.md#android-sdk-setup)
for platforms **36 and 37.0**; installing only platform 36 is insufficient for the
Android application sample. Windows/JDK 17 tests need the
[real symbolic-link prerequisites](local.md#jvm-host-coverage), not skipped tests.

After the SDK manager succeeds, the driver requires each requested platform's
`source.properties` to name its literal `AndroidVersion.ApiLevel`: `36` for
`android-36` and `37.0` for `android-37.0`. An integer `37` is not the latter
package's canonical metadata. Both property contents and file hashes are retained;
missing or mismatched metadata blocks product execution rather than skipping a platform.

### What the Apple Silicon component replay retains

The driver preserves actual policy/fixture checks and real full graph probes,
including the lock-policy expected-red leaves, Android ABI graph, version/toolchain
approval tripwires, real Xcode project generation and launcher/consumer regressions.
A fixture test is labeled as a fixture; it is not a Kotlin/Native, device or remote
publication pass.

The original `scripts/run-platform-tests.py full` assessor runs
`./gradlew check --console=plain` with its fresh source/model/task/nonce evidence.
Required host tasks must execute nonzero successful cases; old XML, cache hits,
no-source tasks and compilation cannot stand in for tests. Report every skipped
case and the configured other-host/device-only targets. Do not reduce the platform
policy or replace the assessor with an XML-only success check.

The additional components retain:

- Android sample assembly, CLI checks/installable distribution, and Desktop UI
  tests/runtime/argument-file/application-image builds.
- Four Kotlin ABI comparisons, the three published Android ABI comparisons,
  strict Dokka, and actual aggregate JSON/XML SBOM generation plus inspection.
- Local-only publication to a fresh owned Maven repository and all 15 expected
  publication sets on macOS, followed by the maintained isolated-consumer script.
  Its JVM Kotlin/Java, Android compilation/manifest and KMP JVM/Android/iOS
  simulator compile/link checks and iOS minimum-OS/permission assertions remain.
- Strict consumer dependency verification: reviewed external metadata plus exact
  source-bound local publication hashes, not a broad trusted group, disabled
  verification, arbitrary Maven-directory trust or remote publication fallback.
  A missing external checksum remains a failure requiring separate investigation.
- Separate post-consumer native `vtool`/`lipo` inspection retains raw output,
  binary hash/size, source/time and the original consumer invocation ID. This is
  an additional observation, not recovery of the original tool output captured
  inside the consumer checker. An absent binary is explicitly `NOT_EXECUTED`.
- Real release XCFramework provenance/minimum-OS inspection, all four build
  sidecars, authoritative XcodeGen generation and the unremoved provenance
  pre-build phase. All platform slices are inspected; inspection is not execution
  of the device or opposite-host slice. Additional post-gate `vtool`/`lipo` output
  is hash-bound to the device and fat-simulator binaries before later rebuilding;
  it is separate from the original gate's captured shell variables.
- A real Swift warnings-as-errors build, separately followed by XCTest for both
  `p2pkit-sample-tests` and `p2pkit-sample-uitests` on one recorded exact available
  simulator. A build-success marker is not a test count; retain actual xcresult
  and nonzero successful cases for both targets.

These scope descriptions are obligations, **not results**. Inspect the exact
component command/status/receipt list for the run; a dependency failure can leave
later dependent components unexecuted. Independent components may still run only
when cleanup is proved. No unexecuted row becomes PASS because a later step passes.

## Resource, process and failure contract

A native Python bootstrap creates a randomized fresh parent under resolved
`RUNNER_TEMP`, outside the source checkout. It owns `bootstrap-evidence/`; the
separate `state/` does not exist until the driver admits and initializes it.
Setup failures can therefore retain metadata without reusing or taking ownership
of an old state directory. Java 21 is installed first and its path retained as
`P2PKIT_AUDIT_JDK21`; Java 17 is selected last as `JAVA_HOME`. Record actual launcher,
daemon and test runtimes rather than inferring runtime from source compatibility.

The [leaf executor](../../scripts/run-audit-command.py) uses an exclusive job-owned
Gradle home and per-invocation lease. There is no cross-run cache action, build cache,
configuration cache or parallel Gradle execution. Dependency/wrapper downloads may
be reused within the exclusively owned job home. Direct product invocations keep
strict dependency verification, rerun tasks, at most two workers, bounded heap and
metaspace, and an in-process Kotlin compiler. Intentional negative-control arguments
such as `--configure-on-demand` are preserved, not masked by appended opposites.

### Audited consumer and policy-fixture work

With `P2PKIT_GRADLE_EXECUTOR` set, the maintained consumer script supports only
source-local publication with no positional arguments or remote repository.
`P2PKIT_CONSUMER_WORK_DIR` must explicitly name a new or empty physical child
beneath initialized `P2PKIT_AUDIT_STATE_DIR/work`. Implicit temporary work,
remote/`--latest-published` modes, aliases and foreign work paths are rejected.
Both values of `P2PKIT_CONSUMER_AUDIT_METADATA` obey this contract; value `0`
does not prepare local-publication trust or disable strict Gradle verification.
Every supported audited consumer directory is borrowed and retained, regardless
of product status, receipt availability or the keep-artifacts switch. The outer
host finalizer owns its eventual disposal. Historical nonexecutor default and
remote behavior remain unchanged.

The audited lock-policy fixture similarly allocates fresh `work/lock-policy.*`
and retains its init script, logs, optional receipts and `.txt` lock snapshots
on success, failure or cancellation. Its `ownership.json` binds the work namespace;
`leafFinalization: NOT_ASSESSED` is not native cleanup proof. The actual executor
and receipt checker still decide each leaf's finalization before an expected
policy rejection can be accepted. Unopted fixture cleanup remains unchanged.
Synthetic caller tests preserve the real controller's complete ancestor domains
when introducing a fixture state/home; fake wrappers are not product execution.

### Per-invocation finalization

After **every** build/test, including failure/cancellation, the executor retains
product and finalizer logs, runs the applicable checked-in wrapper `--stop` under
the same owned home and drains only invocation-owned workers. Product failure,
source failure, stop failure, evidence failure and unresolved workers are separate
outcomes. Infrastructure exit 125 must never be accepted as an expected policy
rejection just because an old error string also appears. Outer command supervision
must not hold the Gradle leaf lease while a nested consumer/provenance call needs it.

Every host first executes native ownership controls before product tasks. Windows
requires actual before-resume Job Object containment, not name-based `taskkill` or
post-spawn assignment. macOS requires real identity/marker discovery and scoped
signal behavior, including detached children and an unrelated surviving sentinel.
These mechanisms supervise controlled build descendants, not hostile code stripping
ownership markers or delegating to unrelated OS services. Source inspection and
mocked APIs do not prove native ownership capability.

The workflow redirects stdout/stderr to separate fresh bootstrap logs and invokes
the exact checked-out driver with `runpy` in the **same native Python process**.
There is no extra unsupervised wrapper child, launcher replacement or product
monkeypatch. The driver's own deadline, cancellation and ownership finalizers run.
Driver budgets are 8,400 seconds on Windows/Intel and 19,200 seconds on Apple Silicon;
step/job ceilings are respectively 150/180 and 330/360 minutes. The driver reserves
finalization time before its deadline. These are resource ceilings, not relaxed
product assertions or automatic retry allowances.

A later host is admitted only after all of the following:

1. The preceding driver emits literal `safe_to_continue=true` after source,
   worker/stop cleanup and evidence finalization.
2. The always-run handoff inspection validates the strict summary/context/receipt
   schemas and types, exact SHA/tree/role/run/attempt, clean post-run source,
   successful native ownership controls, and every retained invocation's stop,
   source and empty-survivor/error records. It hashes the complete manifest/file
   set, rejecting duplicates, traversal, symlinks/reparse points, missing or
   unlisted files, changed bytes and oversized evidence/control files.
3. Bootstrap path/file validation and its separate checksum manifest succeed;
   the artifact step succeeds **and returns a nonempty artifact ID**. Upload paths
   come from the validated handoff, not unchecked environment paths.

A cleaned product failure keeps its driver step/job **failed**; there is no
`continue-on-error`. It can permit the next independent host to collect evidence,
but the workflow as a whole cannot be successful unless every required host succeeds.
A missing output/summary, failed handoff, failed upload, cancellation, source
uncertainty or unresolved ownership blocks dependent jobs. A shell observation that
no `java` process is visible is not proof of cleanup.

## Evidence, cleanup and recovery

Artifacts are named
`audit-host-<role>-<run-id>-<run-attempt>` and retained for 14 days. An always-run
upload follows setup/product/handoff failure only if the handoff proves an owned,
physical bootstrap upload path. Failed allocation or unsafe bootstrap ancestry
leaves no safe directory to upload: keep the Actions job log, record the missing
artifact, and leave downstream work blocked.

The upload allowlist is **`bootstrap-evidence/` and a validated `state/evidence/`**.
Hidden files are included within these checked paths so a manifest-listed file is
not silently omitted; this is not permission to upload hidden homes or caches.
Never upload the whole state/home, Gradle/Native caches, credentials, private device
data, raw user payloads or local machine settings. Hosted tests use synthetic data.

A rejected or unfinished driver tree is **not** handed to the artifact action,
which might otherwise follow a rejected symlink. Instead, the handoff physically
traverses only the allocated `state/evidence/` and copies safe regular JSON, log,
text, XML and checksum controls into a fresh `bootstrap-evidence/evidence-salvage/`.
Receipt/start/product/stop files take priority. Salvage is bounded to 10,000 files,
128 MiB per file, 1 GiB total and 100,000 traversed entries; unsafe ancestors,
nonregular nodes, binary reports, changed files and excess data are omitted with
explicit reasons. If the evidence root is unsafe or absent, only bootstrap metadata
and its omission explanation are uploaded. Salvage has its own checksum manifest,
but **full-tree completeness remains `NOT_PROVEN` and downstream jobs stay blocked**.
It is partial historical evidence, not repaired cleanup or a fabricated complete
artifact. Investigate unavailable required reports rather than claiming them.

Retain the workflow start/handoff records, raw driver stdout/stderr, per-invocation
product/stop logs and receipts, source/tool metadata, platform execution JSON/test
reports, relevant publication/consumer manifests, XCFramework sidecars and Swift
xcresult. Download before expiry and independently verify the complete checksum
manifest and source/run binding. The driver manifest covers `state/evidence/`
excluding that manifest itself; `bootstrap-manifest.sha256` independently covers
bootstrap files and any salvage, excluding itself. Compare artifact IDs and actual
run/job outcomes; a successful upload alone is neither cleanup proof nor a passing test.

Default failure logs are historical evidence. Do not edit them into successes,
replace them with a later attempt or combine different source trees into a single
claimed pass. Reruns get fresh state and artifacts. Prefer a new complete run/attempt
after root-cause investigation rather than silently assembling “green” hosts from
unrelated attempts. Any partial reuse must be explicitly source-bound and reviewed.

Disposable output removal happens only after required evidence is retained and
all dependent consumers have finished. Cleanup uses exact newly-owned output paths,
not a search for directories named `build`. Preserve shared caches, source and user
changes. In particular, `buildSrc/src/main/java/dev/p2pkit/build` is **source**.
Metadata retention may prune and record explicitly unselected symlink/reparse
entries without following them. Selected or raw-evidence links still reject
retention; exclusions do not authorize reading or deleting a link's target.
Do not delete an active iOS launcher lock/guard or a caller-owned fixture before its
workers and consumers finish; see [launcher recovery](local.md#ios-launcher-cleanup-and-recovery).

There is no generic workflow recovery command that can retroactively prove cleanup
following controller/runner/host loss. Abrupt termination can prevent Python finally
or artifact upload. Such cleanup is **UNKNOWN**, not PASS; dependent jobs must not
start. Preserve available ownership receipts/logs, identify any surviving workers
through their actual recorded identities, and let the operator resolve the global
execution lease. Never run a blanket kill, attach an ambient Gradle home for `--stop`,
delete unknown output, force-push, or manufacture a safe output. A fresh verified
invocation does not erase the earlier UNKNOWN result.

## Acceptance that hosted work cannot supply

Keep the [validation status](validation-status.md),
[external handbook](../validation/README.md) and
[test catalog](../validation/test-catalog.md) separate from these host results.
Android host stubs/shadows are not ART/instrumentation, OEM callbacks or physical
radios. iOS simulators are not physical Local Network/AWDL/path rotation,
background/locked-device filesystem, backup or restart campaigns. Packaged samples
and synthetic UI tests do not complete controlled headful/fault-injection or
hostile two-machine network campaigns.

Independent secure-v2 interoperability (#133), professional cryptographic review,
and owner architecture/product decisions (#120) require their own participants,
inputs and evidence. This facility does not supply them or change their dispositions.
Actual OSV results and successful dependency submission also remain separate from
policy fixtures/lockfile coverage. Linux corroboration is not supplied by this
three-host workflow.

Follow the [release checklist](../releasing/checklist.md) for any future release.
The audit's 0.8.0+ compatibility decisions remain in force despite snapshot naming.
No hosted pass authorizes a tag, merge to main, issue closure, remote publication,
repository-setting change or declaration that the entire audit is complete.
