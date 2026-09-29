# Supplemental Mac VPS validation — 2026-09-27–29

## Scope and current status

**September 29 update:** the [new runtime continuation](mac-vps-runtime-20260929.md)
verified 122 native controls and all six supplemental phases on `62716271`:
original-bound readiness, all 20 strict platform tasks (**2,959 passes**, one
pre-existing ignored diagnostic), fresh Apple framework provenance, **88 Swift
unit and six UI passes**, fresh peer preparation and one real Swift/JVM sample
case with **204,800 bytes in each direction**. Source,
actual XML/native results, worker cleanup and owned simulator Shutdown were
independently checked. The earlier failures below remain failed and retained.
Supported-host/cancellation, ART, physical/security and capacity qualification
are still incomplete; Foundation remains **NOT_READY**, with all HOLDs intact.

### September 27–28 checkpoint (historical)

**Qualification is not complete. Supplemental Mac admission, the complete
dependency writer/input review, strict full-profile tests, ABI/compiler/SBOM
checks and the existing Android/Desktop/iOS sample builds passed. Private
21-publication artifact/complete-consumer checks and compilation of all three
Swift test bundles subsequently passed. Swift unit/UI runtime remains failed
at simulator readiness, before any XCTest ran.**
The owner authorized installation and testing on an isolated Intel macOS 26.6.2 /
Xcode 26.6 VPS. This is supplemental evidence, not the retained supported-Intel
configuration, physical device/network/security validation, or capacity
qualification. Release Foundation remains **NOT_READY**; every existing HOLD
and gate remains intact.

The [earlier hosted results](hosted-validation.md) and every failed VPS attempt
are preserved below. The owner subsequently authorized one restart; a changed
kernel boot epoch proved that the unclassified login-window lifetime ended.
Separate Apple simulator initialization completed the remaining execution-policy
scans. The original bounded Native-startup diagnostic then passed without a
test-timeout, assertion, launch-policy or security-setting change.

A fresh complete writer at `a1733de2cb839a75be7f967939e9dd266aecded2` passed,
including independent signature review and owned cleanup. All 14 lockfiles,
verification metadata and three unchanged Native baselines were reviewed. The
four changed dependency inputs were committed separately as
`ec44b7d03c0391f4e2ac34ddde8b70405d5ba1ed`. Fresh admission of that clean candidate
passed all 122 controls and its enclosing finalizer. **A separate strict
full-profile candidate run passed 2,957 tests across all 20 required tasks,
with zero failures/errors and one pre-existing ignored diagnostic.** This is
fresh immutable execution evidence, not an inference from the mutable writer.
The subsequent ABI, Dokka, framework and Swift compiler checks passed, but the
SBOM privacy validator rejected five VCS references inherited from the clone's
private transfer-bundle origin. That phase remains **FAIL**. A fresh same-commit
clone with the canonical GitHub origin passed new admission and repeated the
unchanged full profile and all ten ABI/compiler/SBOM commands successfully.
No product-source or validator change was needed to correct the clone provenance.
The existing iOS application build also passed. The subsequent Swift unit/UI
attempt failed its 120-second simulator-readiness gate while waiting on the
system app, before any XCTest launch; cleanup and Shutdown were verified.
Independent Android/Desktop package builds subsequently passed. Read-only
graphics/session observations identify prerequisites to investigate, not a proven
root cause or a passing runtime gate. Later private artifact/consumer checks
passed on `5ed6dbed`; the `ec44b7d0` Swift compile-only follow-up verified all
three test bundles without running XCTest. Supported-host, Swift/ART runtime,
physical/security and capacity qualification remain incomplete. The recovery
chronology and exact evidence bindings follow below.

The isolated feature branch remains
`work/rpc-lan-20260927-054728-8b1b11da`. Freshly fetched `origin/main` is still
`3bc76f956f8f47447b51a62474fc878b9c43173c`. No unfinished Foundation source was
used. This continuation ran no local Java/Gradle/Xcode/application build or local
SDK/dependency installation. Separate approvals cover the feature-only hosted
jobs and private Mac staging recorded below; no external publication or shared
Foundation/release workflow was started.
`AGENTS.md`, `CLAUDE.md` and the approved `RPC_MODULE_PLAN.md` remain unchanged.

## Completed supplemental work

- Installed task-owned JDK 17/21, native Python 3.12.14, Android platforms 36
  and literal 37.0, pinned XcodeGen 2.45.4, GitHub CLI 2.101.0 and GnuPG 2.5.24.
  The corrected GnuPG build passed its complete upstream checks; its earlier
  failed configuration remains a failed record. No custodian credentials or
  another session's caches were imported.
- An earlier executor admission passed **122 tests**: 75 policy/scripted
  controls and 47 real Darwin fixtures. The ownership implementation uses
  pre-exec lifetime admission, inherited kernel-pipe capabilities and observed
  ancestry, without disabling SIP or using PID/process-group/name signaling.
  See the [ownership contract](../testing/darwin-process-ownership.md).
- The direct-source JmDNS diagnostic passed `control`, `failed_recovery`,
  `shared_close`, `close_wins`, `recovery_wins`, `responder_close`,
  `callback_executor` and `cleanup_retry`. It retained the original 10-second
  readiness and 45-second child deadlines, used no interface override, and
  required natural PASS markers without rescue. This is **not** a successful
  complete Gradle writer/platform run or a repair of the failed hosted attempt.
- On clean source `74c826ae5cf2e2e8e7b4068432ee5cadbf8187de`, the maintained
  `:p2p-core:internalDumpKotlinAbi`,
  `:p2p-transport-lan:internalDumpKotlinAbi` and
  `:p2p-rpc:internalDumpKotlinAbi` tasks succeeded: 39 executed tasks, 6m42s,
  unchanged source and verified cleanup. Kotlin reported the deprecated
  `macos_x64` build-host diagnostic; this limitation is retained.
- All three generated JVM dumps matched the committed JVM baselines
  byte-for-byte. The generated Native aggregates were read/reviewed and committed
  separately as `1b2bc035f8a65cd5fdc363d1270999ad3897be72`: core adds 127 lines,
  LAN adds 28 net lines with an unchanged declaration relocation, and RPC adds
  its 485-line baseline. No existing public declaration was removed. Generation
  and additive review do **not** establish full strict Native compatibility,
  execution of every target, or a successful complete writer.

The stale external `org.jmdns` lock correction remains a separate, previously
verified baseline change described in the
[implementation checkpoint](implementation-status.md). It was not copied from
Foundation and is not the current VPS blocker.

## Earlier complete writer: failed, with evidence retained

A fresh mutable clone/state at `74c826ae5cf2e2e8e7b4068432ee5cadbf8187de` received
only the three reviewed Native baseline files, then invoked the complete
maintained command:

```text
scripts/prepare-dependency-update.sh 74c826ae5cf2e2e8e7b4068432ee5cadbf8187de
```

No required task, assertion or deadline was removed or relaxed. Graph resolution,
aggregate SBOM work and core Native compile/link tasks progressed. The ARM runtime
task was appropriately disabled on Intel. At `:p2p-core:iosX64Test`, the writer
then produced no output for 1,225 seconds and no completed core x64 XML report.
The operator requested exact-invocation cooperative cancellation for diagnosis.
This is **not** a measured product timeout or a passing test run.

The failed result retains all of the following:

- Product exit code unknown after cancellation; unconditional same-home stop
  exited zero.
- A transient pre-stop `DarwinObservationExhausted` / Mach task-name-access
  failure, even though later final discovery had no errors or owned survivors.
- Selected task-owned simulator verified Shutdown after finalization.
- Cancellation and the earlier teardown failure remain **FAIL**, not erased
  by eventual cleanup.

The mutable clone, logs, 19 retained report files and compiled core `test.kexe`
remain available for diagnosis. At that checkpoint, no diagnostic invocation of
that binary had followed cancellation. Later startup-only diagnostics used it
without promoting it to a successful producer. The only source differences in
this failed writer clone were the three imported ABI baselines: **this attempt
produced no complete new locks or verification metadata and supplied no imported
dependency candidates**.

## Fresh executor recheck: failed

A separate clean clone of the same source reran the unchanged complete executor
controls. Unittest ran 122 tests in 590.255 seconds and recorded **30 failure
entries across 23 distinct test methods**, including cleanup assertions. These
are not 30 RPC test failures. The outer result retained product exit 1,
wrapper-stop timeout/exit -15 and infrastructure exit 125. Final owned survivors
and discovery errors were empty; that does not turn this failed admission into
a pass or authorize disposal of separately retained failed fixtures.

Subsequent bounded, synthetic, lifetime-owned diagnostics narrowed the problem:

| Diagnostic | Observed result |
| --- | --- |
| `/bin/sh -c` with a literal marker | Passed. |
| System `dirname` on the exact synthetic script path | Passed. |
| Identical executable `#!/bin/sh` wrappers under short and long task-owned paths | Both timed out before the first script marker. |
| Explicit `/bin/sh -x <same-script>` | Passed, including the Python fixture invoked by the script. |
| Executable scripts with `/bin/bash` or installed Python shebangs | Both timed out. |
| Minimal `#!/bin/sh` marker script, and a shebang script exec'd from system Bash | Both timed out. |

Each probe retained its original five-second diagnostic bound, exact launch
record, stdout/stderr and native finalization. All diagnostic scopes finished
with no owned survivors or discovery errors. No PID/group/name signaling was
used. A further identity-bound observation of only the synthetic children
confirmed the expected interpreter and script arguments, not a substituted
`/dev/fd` script reference. No arbitrary process arguments/environment were
retained. Both task paths and the system temporary directory report the same
filesystem device; a different filesystem has not been established as a cause.

At this checkpoint the underlying cause was not established. The results ruled
out path length alone, but had not separated the executor from ordinary launch
behavior. The subsequent investigation below does that. Switching interpreters
in the maintained tests, extending deadlines, disabling SIP, or blindly repeating
the complete writer is not an accepted fix.

## September 28 diagnosis: queued execution-policy scans

The blocker was **macOS execution-policy scanning**, not an interpreter error or
an established inability of Intel hardware to execute the workload:

- Ordinary Python `Popen`, `posix_spawn` and shell-created children reproduced
  the same five-second shebang hang. Removing the inherited capability FD or
  new-session option from these synthetic descendant launches did not resolve
  it. The genuine native owner and inherited domain/ancestry remained intact;
  these comparisons were diagnostics, not alternative production launchers.
- A one-second, read-only sample of a positively owned synthetic Python child
  found its main thread at `_dyld_start + 0`, before script execution. The child
  was held unreaped throughout sampling so its PID could not refer to a
  replacement. Read-only task observations found a waiting thread, an 8 KiB
  resident image and task suspend count zero. All diagnostic children and the
  independently owned sampler were finalized without survivors/discovery errors.
- Timestamp-correlated `syspolicyd`, TCC and `AppleSystemPolicy` logs identified
  the actual execution-policy wait. Kernel messages saying the policy would not
  allow the process appeared when the diagnostic deadline caused termination;
  they are **not** evidence that the script was classified as malware.

The retained OS logs connect one queued synthetic script to the runtime scan:

| UTC time | Observed event |
| --- | --- |
| September 27, 22:37:41.757 | Gatekeeper begins the scan later identified as `com.apple.CoreSimulator.SimRuntime.iOS-26-5`. |
| September 28, 00:30:31.482 | The minimal synthetic shell script is queued for a scan. Its process fails the unchanged five-second bound. |
| September 28, 00:35:04.889 | XProtect returns the iOS 26.5 `.simruntime` result and Gatekeeper records scan completion; waiters are awakened. |
| September 28, 00:35:14.614–00:35:15.068 | Work on that same retained synthetic script finally starts and completes. |

The runtime assessment occupied **7,043.132 seconds (117 minutes 23 seconds)**.
The tiny script waited **283.132 seconds in the scan queue**, while its subsequent
scan took about **0.453 seconds**. Its original timed-out process remains a
failed attempt; later background assessment of its retained file does not make
that process a pass. This is direct evidence of the blocking queue, not a need
for a longer script/test timeout. The runtime scan also overlaps the earlier
Native startup stall; the Native task still needs an actual rerun.

The logs do **not** establish why Apple's runtime assessment took so long.
No CPU/storage benchmark or security-service stack dump was collected. A logged
`errSecCSWeakResourceRules` during that assessment does not by itself establish
the cause. Similarly, SSH's `sshd-keygen-wrapper` lacked TCC Developer Tools
permission **both before successful earlier work and during the failure**; that
permission was not changed and must not be presented as the sole cause or a
required security bypass. The synthetic file had no extended attributes.
`spctl --status` returned normally; its explicit assessments of a shell tool
and an unsigned script returned ordinary rejection results, not a service-wide
hang. No trust databases, custodian material or other session's evidence were
accessed, and no SIP/Gatekeeper setting, service or VM was changed/restarted.

## Fresh post-scan verification: passed

After the runtime scan finished, new isolated evidence directories ran the
**same diagnostic drivers** against clean source
`74c826ae5cf2e2e8e7b4068432ee5cadbf8187de`:

- All five original shell/path probes passed, including both direct executable
  wrappers. All four original shebang variants passed, including Bash and Python.
  Every case retained its original five-second bound, exit zero, empty owned
  survivors/discovery errors and successful output finalization.
- A new source-bound complete executor admission passed **122 tests in 196.199
  seconds**: 75 policy/scripted controls and 47 real Darwin fixtures. The outer
  receipt records product exit 0, same-home stop 0, infrastructure exit 0, no
  errors and no owned survivors/discovery errors. Source before/after was clean
  and identical. The receipt finished at September 28, **00:45:25 UTC**.

No product code, fixture assertion, deadline, launch method or ownership policy
was changed to obtain these passes. All earlier failed evidence remains retained,
including two setup-only diagnostic attempts that failed before launching cases.
These new results restore this source's **supplemental executor admission**, not
the failed writer, supported-Intel qualification, product/platform tests or any
performance claim. A new complete qualification candidate still needs fresh
source-bound evidence.

## Earlier September 28 follow-up: simulator readiness and admission HOLD

The next bounded diagnostic used the recovered clean source
`74c826ae5cf2e2e8e7b4068432ee5cadbf8187de` and the retained failed-writer binary,
whose size and SHA-256 were rechecked before and after. Binary-format/library
inspection and the selected simulator's boot command succeeded. However,
`simctl bootstatus` exceeded its **120-second** bound while reporting
`Waiting on Data Migration` and the Apple
`com.apple.-0LaunchServicesMigrator` plugin. The readiness command exited -15
through the owned deadline finalizer; same-home stop exited zero, and discovery
errors/owned survivors were empty. Only the selected simulator was shut down,
and its final Shutdown state was verified.

This attempt ended at **01:07:16 UTC**. The Native list-tests command and all
product test execution were **NOT_RUN**. It is a simulator-initialization failure,
not an RPC assertion failure or proof that the earlier Gatekeeper queue recurred.
The original readiness failure remains failed; no deadline was extended.

A fresh full-history/no-tags clone and new admission state then tested current
source `a1c9e3ebe363731a2d12793475cc927bda8cd744`. The unchanged executor suite
ran **122 tests in 228.594 seconds, OK**. Nevertheless, its enclosing admission
receipt ended at **01:12:09 UTC** with:

- Product exit 0 and same-home stop 0; source unchanged.
- Failed pre-stop and final ownership drains, with an **UNKNOWN** survivor
  status and one unresolved same-user process lifetime.
- Repeated `task_name_for_pid` denial, **Mach result 5**, preventing the required
  audit-session classification. This is not a new product-test failure.

A separate read-only observation matched that exact kernel unique ID and start
time, then inspected only its executable path. It identified macOS
`loginwindow`, started during the admission at **01:08:52 UTC**, with real UID
root and effective UID the ordinary user. It was still live; no signaling
authority was established. The observer read no arbitrary arguments, environment,
process memory or private user files. An executable name/path is diagnostic
information, **not** permission to classify or terminate a process.

That admission remains **FAIL**, even though all 122 contained tests passed.
Further simulator preparation and another writer were held at this checkpoint.
A fresh census treating the unresolved lifetime as preexisting could not prove
the failed scope's cleanup. The subsequent owner-authorized restart and positive
lifetime-end verification below resolved the prerequisite for new work; they do
not turn this old receipt into a pass. No process-name/PID sweep was used.

## September 28 recovery and complete generated candidate

- The one owner-authorized restart was independently checked at **01:48:15 UTC**:
  a new kernel boot epoch and absence of the retained process identity proved
  that the unclassified lifetime had ended. Source and protected instruction/plan
  hashes were unchanged. No additional restart or security-policy change was
  authorized or performed by the later checks.
- The public simulator runtime's installed/mounted state was independently
  verified. New Native-startup attempts still exceeded the original **120-second**
  startup bound while macOS assessed six simulator dyld cache files. The first
  attempt encountered the base cache and `.01`; the next encountered `.02` and
  `.03`. Timestamp-bound OS logs identify execution-policy waits before Native
  test startup, not failing RPC assertions or a malware classification. Both
  failed attempts remain failed.
- A separate OS-initialization command ran only Apple's installed `launchctl
  help` in the selected simulator, with a distinct 900-second setup budget. It
  completed the `.04` and `.05` assessments, then verified simulator Shutdown.
  **No product test ran and no product deadline was extended.**
- The unchanged Native-startup diagnostic then passed at **02:50:03 UTC**.
  Readiness completed in 21.333 seconds and the guarded Native list-tests command
  in 2.835 seconds, both within their original 120-second bounds. Source/binary
  hashes, command exits, cleanup and simulator Shutdown were verified. This
  retained failed-writer binary remains **diagnostic input only**.
- A fresh current-source admission at `a1733de2` passed **122 tests in 192.323
  seconds** and its enclosing receipt: product/stop/final exit zero, unchanged
  source, no errors, discovery errors or owned survivors.

The new mutable writer then ran the **entire unchanged maintained command**:

```text
scripts/prepare-dependency-update.sh a1733de2cb839a75be7f967939e9dd266aecded2
```

Its original 7,200-second bound was unchanged. It finished at **03:38:17 UTC**
with product/stop exit zero, no errors/discovery errors/owned survivors and
verified simulator Shutdown. `resolveAndLockAll` reported **333 executed tasks**
in 39m51s. All 381 retained XML suites were hash-checked: **2,957 passed, zero
failures/errors, one pre-existing ignored interop diagnostic**. This includes
792 core, 194 LAN, 45 RPC and three RPC-sample Intel simulator passes. These are
mutable-writer observations, not immutable platform or supported-Intel
qualification. The deprecated `macos_x64` host and compiler thread-count
diagnostics remain in the original logs.

Independent review matched all **55 added POM checksums** to the successful
downloaded-byte/publisher-signature review records. There were no removals,
changes to existing checksums, new component versions or trust-policy changes.
All 14 lockfiles and three Native baselines were compared in full. Only four
dependency inputs changed:

- New complete RPC and RPC-sample lockfiles.
- The existing SLF4J 2.0.7 lock additionally covers `embeddedJmdnsCompileClasspath`.
- The 55 reviewed POM entries in verification metadata.

No failed-writer inputs, unfinished Foundation files or dependency caches were
imported. The historical external `org.jmdns` correction is separate. Six local
source-only checks passed (wrapper pins, dependency policy, OSV lock coverage,
repository layout, Markdown links and release metadata), plus whitespace checks.
OSV coverage now verifies all **12 nonempty** dependency lock inputs; that is
coverage validation, not a newly executed vulnerability scan.

These inputs were committed as `ec44b7d0` before documentation changes. A new
full-history/no-tags immutable Mac clone of that commit passed **122 admission
tests in 195.753 seconds**, including verified outer cleanup.

## Strict committed full-profile check: passed

The separate immutable run at `ec44b7d0` finished at **04:31:45 UTC** on
September 28. It used the admitted native leaf and the unchanged execution-token/
model assessor, not the legacy PID-based platform wrapper. The complete `check`
profile retained strict dependency verification, forced-fresh tasks, two workers,
no parallel/cache/configuration-cache reuse, warning policy and the original
**7,200-second** command bound. An initialization script bound Native tests to
the one previously selected task-owned simulator; no required task was removed.

- Gradle reported **279 executed tasks** and `BUILD SUCCESSFUL in 34m 37s`.
- The unchanged assessor verified every one of the **20 required test tasks**
  as freshly executed with nonzero successful counts.
- Independent review hash-checked all **381 JUnit XML suites** against the
  retained coverage record: **2,957 passed, zero failures/errors**, plus only
  the existing ignored `IosLanDiagnosticTest.advertiseForSixtySecondsForInteropCapture`.
- Intel simulator counts were **792 core, 194 LAN, 45 RPC and three RPC-sample**
  passes. The other **1,923** passes were JVM/Android-host tests. Android host
  execution is not ART/device execution; the opposite simulator architecture
  still needs a matching host.
- All four command receipts had product/stop/final exit zero, matching canonical
  and alias bytes, unchanged exact clean source, and no errors, discovery errors
  or owned survivors. Final simulator state was **VERIFIED_SHUTDOWN**.

This establishes the complete strict profile on this supplemental VPS, not the
retained supported-host matrix, Swift application/runtime, consumer packaging,
physical/security or capacity qualification. Compiler diagnostics remain in the
original logs; a successful command is not a claim that all diagnostic text was
absent. The subsequent ABI/compiler/SBOM phase is separate and failed as follows.

## SBOM provenance failure and fresh-clone follow-up

The ABI/compiler/SBOM phase ran from **04:34:57 to 04:53:57 UTC** at the same
clean `ec44b7d0` source. Nine command receipts passed: strict core/LAN/RPC ABI,
strict Dokka, all three RPC-sample Apple debug frameworks, matching SDK queries,
Swift API typechecking for all three iOS-14 targets, and actual SBOM generation.
The tenth command, `strict-sbom-validation`, returned product/final exit **1**:
the generated SBOM contained a workstation path. Stop/finalization, source
integrity and all receipt aliases were independently verified; no owned survivor
or discovery error remained.

Independent inspection of the generated **88-component JSON/XML pair** found
exactly five affected VCS references: the aggregate component, core, Android
provisioning, desktop provisioning and RPC. Each matched the validation clone's
task-private Git bundle origin. LAN already had an explicit canonical reference.
CycloneDX derives those references from Git configuration; the existing
[`check-sbom.sh`](../../scripts/check-sbom.sh) /
[`validate-sbom.py`](../../scripts/validate-sbom.py) privacy gate correctly
rejected them. This is a **validation-clone provenance/setup failure**, not a
demonstrated RPC defect, renewed simulator-startup failure or JmDNS-lock issue.
The driver's `sbom: NOT_RUN` field was only advanced after a successful check;
the original receipts establish that generation and failing validation both ran.

The failed clone, SBOMs and receipts remain unchanged. No SBOM was sanitized and
no gate was relaxed. A new full-history/no-tags clone of the **same commit/tree**
was prepared with `origin` set to `https://github.com/p2pKit/P2pKit.git` **before
admission**. All 18 reviewed dependency/Native input files and protected
instruction/plan hashes matched. New admission passed **122 tests in 196.122
seconds**, plus its enclosing source/ownership/cleanup checks, with matching
canonical and alias receipts. The unchanged full-profile rerun ran from
**05:11:47 to 05:47:37 UTC** and passed: Gradle reported **279 executed tasks**
and `BUILD SUCCESSFUL in 35m 29s`. Independent verification again matched all
**20 required tasks**, **381 XML suites**, **2,957 passes**, zero failures/errors
and the same one pre-existing ignored diagnostic. Intel simulator counts remained
792 core, 194 LAN, 45 RPC and three RPC-sample; the other 1,923 passes remain
JVM/Android-host evidence, not Android ART/device execution. All four canonical/
alias command receipts, exact source integrity, cleanup and final simulator
**VERIFIED_SHUTDOWN** passed. These are repeated same-commit results, not 5,914
distinct tests or additional platform coverage.

The fresh compiler/SBOM phase ran from **05:48:17 to 06:07:36 UTC** and passed
all **ten commands**. Independent verification matched every canonical/alias
receipt, exact clean source, zero product/stop/final exits and successful owned
cleanup. Strict core/LAN/RPC ABI and Dokka, all three RPC-sample debug frameworks,
SDK-bound Swift API checks for all three iOS-14 targets, SBOM generation and
unchanged SBOM validation passed. The actual **88-component CycloneDX 1.6
JSON/XML pair** passed the connected five-module, embedded-JmDNS provenance and
privacy checks. No contaminated SBOM bytes were rewritten or reused.

All **11 genuinely generated ABI dumps** were separately retained and compared
byte-for-byte with the clean candidate's baselines: four JVM, four Android and
three Native. Their timestamps fall within the verified platform/compiler
producer phases; this is not a copy of baselines presented as generated output.
Downstream Apple application/runtime checks are separate, as recorded below.
No additional restart, remount, security-policy change, dependency-cache copy,
test skip or deadline extension was used.

The unchanged offline SBOM validator suite also passed **23 tests**, including
29 XML mutation subcases and JSON/XML/escaped-path contamination controls.
These used only synthetic files and a fake wrapper; no local Java, Gradle,
application build or dependency download ran. Wrapper pins, dependency policy,
OSV input coverage, layout, Markdown links, release metadata and whitespace
checks passed separately. Coverage validation is not a vulnerability scan.

## Existing iOS sample application: build passed

The canonical candidate's application-build phase ran from **06:08:54 to
06:24:38 UTC**. All four top-level commands and the mandatory nested provenance
command passed, independently verified against their original receipts:

- A forced-fresh release `P2pKitShared.xcframework` producer, with retained
  source/input/artifact sidecars bound to the same clean commit and execution job.
- The maintained XCFramework minimum-OS check, preserving the library's iOS-14
  deployment floor.
- Maintained XcodeGen project generation, including all expected schemes and
  the unmodified pre-build provenance phase.
- Unsigned, warnings-as-errors `xcodebuild ... build` for the iOS Simulator,
  with the real `BUILD SUCCEEDED` marker and nonempty application outputs.

The compiled sample retains its **iOS-15** application floor, secure Bonjour
declaration and local-network usage description. The mandatory nested provenance
leaf proved unchanged reuse of this phase's genuine XCFramework producer; it was
not skipped or replaced by a fabricated marker. Source and owned cleanup passed.

This is compatibility evidence for the **existing P2P iOS sample**, not a turnkey
RPC installer, device execution or a measured RPC host. The separate RPC shared
façade/framework compiler checks are recorded above. The maintained Swift
unit/UI suite has 88 unit methods and six UI methods in source; the following
readiness failure prevented their execution.

## Swift runtime readiness: failed before XCTest

The next phase ran from **06:25:40 to 06:28:08 UTC**. Its original
`simctl bootstatus ... -b` command exceeded the unchanged **120-second** bound.
The retained output first reported `Waiting on BackBoard`, then repeatedly
`Status=4, isTerminal=NO` / `Waiting on System App`. This establishes the exact
failed readiness condition, **not its underlying OS/virtualization cause**.

The product command was stopped at the bound (product exit `-15`, infrastructure
exit `125`); Gradle-home stop/finalization succeeded. Four inventory/shutdown
commands passed. Independent review verified all five original canonical/alias
receipt bindings, unchanged clean source, no discovery errors/owned survivors,
and final **VERIFIED_SHUTDOWN** of the same selected simulator. The interim
device state was `Booted`, which does not establish completion of system-app
startup. The phase remains **FAIL**, not a successful runtime gate because its
cleanup passed.

**No Swift unit/UI test command or application was launched and no XCTest result
bundle was produced.** The 88 + 6 source methods remain unexecuted in this phase.
The earlier Kotlin/Native simulator test passes and successful iOS compilation
remain valid; neither proves UIKit/system-app readiness. No timeout/assertion
change, automatic retry, new restart, remount or security-policy override was
used. Independent Android/Desktop package checks subsequently passed after this
verified cleanup without booting a simulator; they cannot resolve or replace
this failure.

## Existing Android/Desktop sample package builds: passed

The canonical candidate's package-build phase ran from **06:36:50 to
06:43:59 UTC**. Each command retained strict dependency verification,
warnings-as-errors, forced-fresh tasks, bounded workers and its original
**1,800-second** limit:

| Task | Observed result |
| --- | --- |
| `:p2p-sample-android:assembleDebug` | Passed; Gradle reported 3m35s. |
| `:p2p-sample-desktop:installDist` | Passed; Gradle reported 1m21s. |
| `:p2p-sample-desktop-ui:createDistributable` | Passed; Gradle reported 1m57s. |

All three original command receipts, their canonical/alias bindings, unchanged
clean source and owned cleanup were independently verified. **Thirty recorded
output files** were hash-checked. Inspection covered the APK metadata/ZIP shape,
CLI launch scripts and JAR inventory, and Desktop application metadata/launcher.
This is not an inspection of every byte in a Maven publication set.

Outputs remain in the task-owned Mac candidate, relative to its source root:

- `samples/p2p-sample-android/build/outputs/apk/debug/p2p-sample-android-debug.apk`
- `samples/p2p-sample-desktop/build/install/p2p-sample-desktop/`
- `samples/p2p-sample-desktop-ui/build/compose/binaries/main/app/P2pKit Sample.app`

No packaged application was executed, and no binaries were exported or
published. These are **existing P2P compatibility packages**, not turnkey RPC
installers, Android ART/device execution, or RPC capacity evidence. Maven
artifact-shape and independent consumer qualification remain separate.

## Read-only system-app diagnosis: observations, not a root-cause finding

A private diagnostic helper initially failed before issuing any OS probe because
the installed Python lacked `time.tzset`. That failed record is preserved. A
separate portable helper used `datetime` to observe the actual UTC offset; no
product test, assertion or deadline changed.

The corrected read-only phase ran from **06:54:04 to 06:54:17 UTC**. Both bounded,
unprivileged commands and their source/receipt/cleanup checks passed:

- `system_profiler -json -detailLevel mini SPDisplaysDataType` reported display
  vendor `0x15ad`, device `0x0405`, **3 MB VRAM** and
  `sppci_kextnotloaded`. **No Metal capability was reported.**
- The SSH test user did not own `/dev/console`. This does **not** establish that
  no GUI session exists; another user could own it.
- A narrow `log show` query over the failed readiness interval, scoped to the
  selected simulator/runtime, returned only its 44-byte header. No matching
  events were available through this query. That is not proof that no OS error
  or security assessment occurred.

These observations raise a simulator graphics/session prerequisite concern;
they do not establish why system-app startup failed. **The underlying cause
remains unproven.** Owner/provider coordination should establish usable simulator
graphics and an ordinary GUI test session, or supply a working admitted Mac,
before another runtime attempt. No kernel/display driver installation, privileged
observer, restart, remount, security-policy change or blind retry was performed.

## Required next steps

An ordinary read-only capability check at **05:34:30 UTC** reported
`kern.hv_support: 0` on this Intel VPS. No task-owned Android emulator or system
image is installed. Hardware-accelerated Android emulator/ART qualification is
therefore unavailable in the current VM configuration; Android host-side JVM
tests above are not a substitute. No nested-virtualization/security-policy change
or unsupported software-emulation workaround was attempted. iOS simulator
execution is a separate mechanism and is already evidenced above.

1. Keep OS/runtime preparation separate from bounded product tests. After a
   runtime installation/change, establish completed security assessment and
   fresh native admission rather than extending product deadlines or bypassing
   scanning. If the queue stalls again, retain targeted evidence; any service/VM
   restart or policy change still requires owner coordination. The supplemental
   VPS does not replace the retained **Apple Silicon/macOS 26/Xcode 26.5** or
   **true Intel/macOS 15/Xcode 26.3** qualification configurations in the
   [Mac handoff](../testing/mac-handoff.md).
2. Establish genuinely working system-app readiness before a new Swift runtime
   attempt, preserving the failure above and the original bounds. Resolve the
   graphics/GUI-session prerequisite with the owner/provider or use another
   admitted host. The **88 Swift unit and six UI methods** remain unexecuted in
   this phase. The full profile, ABI/compiler/SBOM and sample-package passes do
   not replace these gates. No blind retry, additional restart or policy
   relaxation is authorized.
3. Private Maven artifact/consumer checks now passed on clean `5ed6dbed`,
   including the unchanged artifact gate and complete consumers. No normal
   `~/.m2`, external publication, private signing material or release workflow
   was used. Preserve the earlier failures and exact successful scope in the
   [continuation below](#authorized-packaging-and-consumer-continuation).
   Swift test bundles also compiled in the
   [compile-only follow-up](#additional-swift-test-bundle-compilation-not-runtime);
   that result does not remove the runtime prerequisite in step 2.
4. Perform the still-unmeasured
   [real-network/security and capacity experiments](qualification.md).
   Each actual JVM/Android/iOS host must sustain
   128 independently authenticated clients at 10 calls/second each for 30
   minutes, with 1 KiB requests/replies: **2,304,000 successful responses**.
   Actual host telemetry, physical interoperability and a separate bounded
   1 MiB experiment are required. No capacity result is inferred from any
   executor, unit test, compiler or simulator result.

The [RPC sample](../../samples/p2p-sample-rpc/README.md) is shared source and a
qualification driver, **not turnkey installable Android/iPhone applications**.
Application integration, permissions, approved trust/identity storage and actual
host telemetry must be supplied before device qualification.

## Authorized packaging and consumer continuation

The latest owner approval extends this work to remaining feature-only Actions
and disposable Mac-local Maven staging/consumer validation. The earlier closeout
below describes the `ec44b7d0` checkpoint, not this new work. No external
publication, normal Maven home, Foundation/campaign source or private custodian
material is authorized.

- The first actual `publishToMavenLocal` into owned temporary storage passed.
  The unchanged `check-publish-artifacts.sh` then failed: AGP retained all 133
  private JmDNS classes byte-for-byte but separated their resources into
  `classes.jar`. Its class-only nested JAR was therefore not the byte-exact
  producer required by the artifact contract. Independent retained evidence
  confirms the failure and diagnosis; it is not an artifact-gate pass.
- Commit `f2f516ce` preserves the original producer inside `BundleAar`, removes
  only identical duplicated private resources from `classes.jar`, and validates
  bounded ZIP structure/class bytes before an atomic output replacement.
  The root archive-license rule still feeds ordinary assembly before this
  final producer step. The artifact checker is unchanged. All 25 Java synthetic
  controls subsequently executed and passed on the supplemental Mac.
- Commit `cd04c228` adds six explicit published RPC coordinates and typed API
  use in JVM, Android and common/iOS consumers. The complete profile retains
  strict admission of 21 publications, 117 physical inputs and 141 verification
  records. The JVM value/API smoke explicitly performs no network or capacity
  experiment. All 52 offline consumer controls passed.
- The first fresh packaging candidate stopped before Java/build work: 121 of
  122 native executor controls passed; one integration expectation still listed
  the previous consumer task/report inventory. Commit `2cbea7dc` requires the
  added RPC tasks and exactly three reports, including the smoke's exact bytes
  and retained hash. It does not weaken assertions or remove a control. The
  failed receipt and its verified source/cleanup remain separately retained.
- The ART helper no longer signals retained children through bare `Popen`/PID
  handles. It fails the scenario and leaves identity-owned finalization to the
  enclosing executor. All 17 offline ART controls passed; this is not ART
  runtime evidence.

### Completed source-bound packaging and consumers

The preserved `06512d4a` attempt passed native controls, Java AAR controls,
staging and the unchanged artifact gate, then **failed complete consumers** on
unverified `kotlinx-io-core-0.6.0.module` metadata. Its original attempted/failed
status is retained; an independent report correction does not call it NOT_RUN.
Commit `397f0da1` uses explicit configuration creation and checked JVM/Android
classloader references in the consumer fixtures. All **53 offline consumer
controls** passed; no dependency graph or publication inventory was reduced.

The one required descriptor was reviewed against official Maven Central bytes,
its SHA-256 sidecar and the pinned JetBrains public signature. Commit `5ed6dbed`
adds only that exact checksum, not a dependency version, lock, existing checksum
or trust-policy change. The unchanged maintained provenance checker independently
verified exactly that artifact during the fresh attempt.

A new full-history/no-tags, canonical-origin clone at
`5ed6dbedc98082c0480546d7508e6b2a689a4638`, tree
`e45a8ecbc04f1db212043a0bce0f57047f67d81a`, completed all six phases from
**09:09:22 to 09:35:27 UTC**:

| Phase | Verified result |
| --- | --- |
| Native ownership controls | All 122 passed, including enclosing finalization. |
| AAR producer-preservation controls | All 25 Java synthetic controls passed. |
| Exact descriptor provenance | One descriptor passed checksum/sidecar/signature review. |
| Private Maven staging | Passed into owned disposable storage; 299 executed tasks. |
| Unchanged artifact-shape checker | All 21 publications passed artifact, real-Dokka and release-metadata checks. |
| Complete published consumers | Passed; 117 physical inputs / 141 verification records, 179 executed consumer tasks. |

Consumers retain the original JVM/Java/Android/common/iOS-14 framework checks,
embedded-JmDNS normal-close/coexistence/POM-only JVM smokes and Android D8/R8
plain/coexistence packaging, plus typed RPC API use. The RPC JVM value/API smoke
passed and performs no network or capacity experiment. Android packaging is
not ART/device execution. Both nested consumer receipts, publication bytes,
original external metadata, source integrity and cleanup were independently
verified. No normal Maven home or external publication was used.

Streaming-serialization metadata traverses the 0.6.0 descriptor in mixed
POM/GMM resolution; this does not mean a 0.6.0 artifact was selected for execution.
A separate strict, no-override observation checked Android's ordinary and
POM-only runtime graphs and the RPC JVM runtime. **All selected IO core and
bytestring artifacts are 0.9.0**, with hashes matching reviewed metadata.
Fixture inputs, trust metadata and publication bytes remained unchanged.
No dependency binaries were downloaded to the local coding workspace.

The [feature-only workflow](hosted-validation.md#remaining-qualification-workflow)
retains separate failed gates: Linux admission/JDK checks passed but KVM access
failed before ART; both Apple admission-only lanes failed ownership/finalization
before product work. Temporary Linux runner KVM access has been requested but
not granted or applied. No unchanged Apple or VPS Swift-runtime retry, capacity
experiment or physical-device test is claimed.

### Additional Swift test-bundle compilation: not runtime

The existing `ec44b7d0` candidate additionally ran `xcodebuild build-for-testing`,
with two build jobs, fresh DerivedData, warnings-as-errors, unsigned simulator
output and the original 7,200-second compiler bound. It did not boot a simulator
or use the legacy launcher/cancellation probe.

The unit/UI **compiler command passed**, including mandatory nested XCFramework
provenance and finalization. Its private inspector then failed because it
expected manifest format 2 while Xcode emitted format 1. The failed phase and
original receipts remain unchanged. Eight offline controls test the exact
observed format, rejecting unknown versions, missing/extra/mismatched targets,
disabled entries and test filters. A separate strict review validated the
preserved successful UI build **without rerunning its compiler**, then freshly
built the separate real-peer scheme.

The reviewed phase ran from **15:00:41 to 15:02:29 UTC**. Independent receipt,
manifest, source-input and output-hash checks establish:

| Maintained scheme / bundle | Source inventory compiled, not executed |
| --- | ---: |
| `p2pkit-sample-ui` / unit bundle | 88 test methods |
| `p2pkit-sample-ui` / UI bundle | 6 test methods |
| `p2pkit-sample-jvm-transfer` / real-peer UI bundle | 1 test method |

All three binaries contain **arm64 and x86_64 simulator slices** and preserve
the sample's **iOS 15** minimum. The `.xctestrun` manifests retain all expected
targets without filters. Both mandatory provenance receipts bind the same
verified XCFramework producer. A separate exporter rechecked each bundle's
metadata and compiled-byte hashes; no binaries were exported. Source/project
inputs stayed unchanged, all commands finalized and the selected simulator
remained **Shutdown**.

**Zero XCTest methods ran.** The failed 120-second system-app-readiness gate,
unknown OS root cause, supported-host requirements, physical/security/capacity
experiments and ART gate are unchanged. The real-peer scheme was compiled,
not connected to a peer. This is not a phone installer or evidence that the
VPS GUI/runtime problem has been repaired.

### Latest verification records

New task-owned evidence is under
`.git/rpc-remaining-validation-20260928.d7kfjhm3/` in the isolated clone.
Only bounded text, manifests and receipts were transferred; no compiled/
dependency binaries, keys or custodian evidence were exported or committed.
Key independently checked hashes:

| Record | SHA-256 |
| --- | --- |
| Successful six-phase packaging result | `949a04f6e1c84ca1a55d44d2d61487af26c850754285d4e045031027f754b48f` |
| Packaging text/receipt archive | `30f7e593c2f539121d064e6b19765841becadf64305ec38cedbb3bc3020f6b0d` |
| Packaging export receipt | `2f15afd34f170ee796b539c652396594dba9770a41acbf2818422e8396be6c67` |
| Selected IO graph receipt | `f2a4bca4a27a9d5fb05c9086b2aa7d3f970a4608eef74f6ae54bb3cb1995aa1a` |
| Preserved Swift manifest-inspection failure | `78d306498f9df24dad9f9482356128d2cbbfa5111fe4017c4f4a241297d76a1b` |
| Original unit/UI test-build receipt | `37231f2c8e78f9a975e47a5d5996241df427ec63d747f12a773013fced203d73` |
| Real-peer test-build receipt | `676cd1f8ede0ca114e859925d9a22d664fa3d895e503a8a2f8836400053a6112` |
| Reviewed Swift compile-only phase | `22c07104298c2b68d833672b6bc534241a105322abf03cab659dde34d673c798` |
| Reviewed Swift text/receipt archive | `d50f87dfdba3f25ab1813f7c462d94e37072879b562434692ca7f6c1ca5e7d6f` |
| Reviewed Swift export/output-check receipt | `f4f2939d01fc6f1f88c9a08ecd55eb491e08ad207e1033a1b5fb8bc4c69527d5` |

## Validation closeout — earlier ec44b7d0 checkpoint

The earlier canonical-candidate runtime/build results bind to exact source
`ec44b7d03c0391f4e2ac34ddde8b70405d5ba1ed`, tree
`9533c4494f24b9aebb9cec3837be6d95494a8096`. Later documentation-only changes do
not constitute execution of a newer commit. The completed phases and failed
attempts remain preserved separately; no successful scope is used to promote a
failed or unexecuted gate. The task's test phases have finished with verified
owned cleanup; the last selected-simulator retirement is **VERIFIED_SHUTDOWN**.

Final local checks cover wrapper pins, dependency-verification policy, OSV
lockfile coverage, repository layout, Markdown links, release metadata,
whitespace and protected instruction/plan hashes. These are bounded offline
checks, not local Java/Gradle/Xcode/application builds, dependency downloads or
a vulnerability scan. At that earlier closeout, no new shared hosted job or
Maven staging was started.
Full qualification, release readiness and the external HOLDs remain unchanged.

## Evidence locations

Task-owned records are retained privately under
`.git/rpc-vps-qualification.H7bcx3/` in the isolated clone and the task's Mac
evidence directories. Raw process records, simulator identifiers, SSH material,
generated binaries and logs are not source-control artifacts. Key receipt
SHA-256 values for verification:

| Record | SHA-256 |
| --- | --- |
| Successful Native ABI generation | `88468d8010adbbf58710ba5be515d5cdeff05c027873a4be06957e9438070c50` |
| Cancelled complete writer | `72203463ba5411b2d1e3c751382c42181d1e188e8253be2ac2b7619b93b8e2e8` |
| Failed fresh executor receipt | `0a2bff4fd1a62bd5bf164b8a6e73b5cdebe2e80228485066cc521ca4a9ed53ed` |
| Synthetic shell-startup diagnosis | `9aee7913b96785bd0a3f90f6444c14c48e8d516cb384b5f99f36af5678c1f076` |
| Synthetic shebang variants | `d0de94d92edf1e7dd0f818730ba2cb8bae2411493830962b4cbe75e5ee3d0850` |
| Runtime and queued-script scan recovery log | `413dc0b4dced8d343448c94cc984728d45aa138338c7e1b2a8023da3797725cb` |
| Post-scan original shell probes | `5dde56977b01caecc5b8ab72aea76f7c61128f67e432ca9e8d6808ff19a9683c` |
| Post-scan original shebang variants | `cd5f239c08a115065d47390585a875723bbfbd228b9000eb4acd6dce20f54a12` |
| Passed post-scan complete executor receipt | `5c6003dbd29f79b34f241c1c9987e39b843b2ad6b84854730b5fcd07899483e0` |
| Failed simulator-startup diagnostic | `9a381d388ab824ca39b09c6f2d475b635bf7fb0a4a15746bf01a59cd3b565ba0` |
| Failed current-source executor admission | `b1fac8997895a24cd7b38a8ecc86976c263ec56df0ab0b36c2eb21237eacb6a6` |
| Read-only unclassified-lifetime observation | `abd350734a5f7d7785613555f9a8c5427edda88bc58f197a5ea8869a17bf10c6` |
| Verified lifetime end after authorized restart | `38ad8159e5925a10e9fe3b85079950f3f9b790fa6d8ab5ebd0a375077960e4fc` |
| Separate Apple simulator-library initialization | `874aefd883853df260cd163d10578aa59886c3331c4514374cf9a687b24c1ef2` |
| Recovered original Native-startup diagnostic | `e6b7f81da7459699c905d5435b3c3038b020e195b20abd75c3570bab059d4f0d` |
| Fresh writer-source admission receipt | `9ee463ddcea8e1b9f3eb0271ddc8039b9c40a42e558b7b54ea49cd79809de0b2` |
| Successful complete mutable writer | `8466fc248c681974d6ba4282646cc4361d73080d31aeacedbe325263f68869fd` |
| Committed generated-input review | `3dbf31ec55f01209a3c3ca1e051e60d550470d68a652ae56a6904041744fe4f3` |
| Fresh committed-candidate admission receipt | `fd42d168e4fb12ee907d04ed2de3596de4b106b3faf4afc1e95d3d96d7fcce15` |
| Strict full-profile command receipt | `19cd457180e41bf4b16ba1829321393428702aaa164e2a1d1cbb1616369bbfbe` |
| Strict full-profile phase result | `d8ff954520c95699d8411433cbc82e51d66a6fc9293e4475c4f4150e00325205` |
| Strict full-profile execution-token/model record | `b0af0e524bc8a520ae9904b73401324ffad651f20c0a0a5e8872339db4d98d83` |
| Failed ABI/compiler/SBOM phase | `9ec3ef627deb4676b720fab1553b0336a7b4cbeda9312abd70902aeb90a3bf4b` |
| Failed SBOM privacy validation receipt | `4fd0ec1f206e2d44c11ef7dd820337f806a52cc0080c988b45b3a6af5a620d5f` |
| Preserved contaminated JSON SBOM | `150991fbb0f8ce152838e5ab05ed2af4f5a0097be4683690b5579c285b5a0c5e` |
| Preserved contaminated XML SBOM | `53bef2ceac3934f07deaa75ba897d296ca11b6335c1f47712d855009393adc82` |
| Fresh canonical-origin clone preparation | `5e70537cf47c500c28c138669ada6c69db465ba49c3cb04b0286f46dd8cadd0c` |
| Fresh canonical-origin admission receipt | `7e9c24367e31a52c5b46a7c71608d1698b141f3631f9d52c0597fec83a28a3e1` |
| Canonical-origin strict full-profile receipt | `bcf9d8bb8a8899fba96de20a1bc7396b83e35208294a8c6c191f04e3bbaaad40` |
| Canonical-origin strict full-profile result | `97320c5e09195161ed395ed563c432aa315d55c216df38938a7908494cf2b85b` |
| Canonical-origin execution-token/model record | `ed92195fcff69b60fb33eabc11eb7306ce31b4169aacb1b38fb693e1d9cef710` |
| Canonical-origin full-profile text/XML export | `06faf803331611d2acfa9457b137d9ddfffe038bb6d7017b0b70a6f6962cf8b1` |
| Canonical-origin ABI/compiler/SBOM result | `869abd75a50bb609f16984ce18314c90ab968e026667372cfe28b3d599b75dd2` |
| Canonical-origin SBOM validation receipt | `d18a57a75678576df2bcee5fa14b950b83d527c8a1084fa3df5711e716ae4b3d` |
| Canonical-origin JSON SBOM | `97a35eb224197d1752322e275a367f2a3190bfbcc2337b67b99301404e5ae8e7` |
| Canonical-origin XML SBOM | `afd9951fb34c39a8356afed4ae0cb541c40523bc7f88bd1fe20a2a7427979a04` |
| Eleven generated ABI text dumps/review packet | `ecd1698093b4ec34c758c3b8df963ac5c0301457524ed86d275af796f05d7df9` |
| Canonical-origin XCFramework/application-build result | `a05f697492be36f8b95faf03006fca30f21a97c014c26d48890754632759f071` |
| Fresh XCFramework producer receipt | `905dd81b561ef7ac41e0597667f85eb5d073db4c907000dc95526628ce154772` |
| Unsigned iOS application-build receipt | `1e7ab05807d90d6cf2268b2f1b725c5cdd6ecdef1a7ce151c158fad817461083` |
| Mandatory nested application provenance receipt | `09cb89a1fa1a8643c362c8c4cac9a920c2e21faaf1fa23ca0a376bc983928fed` |
| Failed Swift runtime-readiness phase | `e16934a0ebb5b6c9cbd7200dc879894e25c5dc12ba95702e792e81b4277a55c7` |
| Failed 120-second system-app readiness receipt | `55e30fc725574f9b6d5b884da7e141471aca7d2591cc2c3fea4cdb0130c4a4f3` |
| Preserved Swift readiness/cleanup text export | `18bce4758149d757162ee0a51eedd0ef19d4a0a90a7fa2286ce420029a0c39a7` |
| Existing Android/Desktop package-build result | `9fa1e099969d1e74a8836bf5bd1ffc43e85d9d0b161bef07f90e5eee5cc623d3` |
| Android APK build receipt | `be0b36c66b7a58d48c57bb67f7baa319367d1cde2bca32ea83b801c8c636c177` |
| Desktop CLI distribution receipt | `dc279511d9cb5fcda49ef32ea8f2be8c0cba117bf826423d7c3f1306a6912b05` |
| Desktop UI distribution receipt | `097fe65682cd3b0ae69c7170118518f3c27cb9ba9acb4ae0623c64e99449979b` |
| Package-build text/metadata export | `c50105ac680ffcac566fca241e4a1b95b4a96265db4f23d63479957ea0871109` |
| Initial read-only helper failure before OS probes | `f707def13f710ab016967c3c85050eb0f8012e8e0a6f216d42ae8e31da0d26de` |
| Corrected read-only graphics/session/log phase | `886327df1a278ddc052e11d725c91e3fb01ff119d12a5aaee8374b3bfe08ee92` |
| Read-only diagnosis text export | `addf25439bcb96433a636d3869eadc77d69b5981574287e93a42c4132ba8e9b8` |
