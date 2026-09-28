# Supplemental Mac VPS validation — 2026-09-27–28

## Scope and current status

**Qualification is not complete; executor admission has recovered.** The owner
authorized installation and testing on an isolated Intel macOS 26.6.2 / Xcode 26.6 VPS. This is
supplemental evidence, not the retained supported-Intel configuration, physical
device/network/security validation, or capacity qualification. Release Foundation
remains **NOT_READY**; every existing HOLD and gate remains intact.

The [earlier hosted results](hosted-validation.md) are preserved. On this VPS,
all eight direct-source JmDNS lifecycle modes subsequently passed, and genuine
Native ABI generation/review completed. However, the complete writer stalled at
the first core Intel simulator test task and was cancelled. A fresh executor
recheck then failed, including synthetic script startup and wrapper teardown. The
September 28 investigation identified a long-running Gatekeeper/XProtect scan of
the iOS 26.5 simulator runtime holding up new executable scripts. After that scan
finished without a restart or security-policy change, all nine unchanged startup
probes and a fresh complete 122-test executor admission passed.
**The failed writer remains failed; no Native/product rerun or full qualification
is inferred from the recovered executor.** No product work was resumed while
admission was failing.

The isolated feature branch remains
`work/rpc-lan-20260927-054728-8b1b11da`. Freshly fetched `origin/main` is still
`3bc76f956f8f47447b51a62474fc878b9c43173c`. No unfinished Foundation source was
used. This continuation ran no local Java/Gradle/Xcode/application build or local
SDK/dependency installation, no new shared hosted job, and no publication.
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

## Complete writer: failed, with evidence retained

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
remain available for diagnosis. No diagnostic invocation of that binary has
followed the cancellation. The only source differences in the failed writer
clone were the three imported ABI baselines: **no complete new locks or
verification metadata were produced or imported**.

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

## Required next steps

1. Keep OS/runtime preparation separate from bounded product tests. After a
   runtime installation/change, establish completed security assessment and
   fresh native admission rather than extending product deadlines or bypassing
   scanning. If the queue stalls again, retain targeted evidence; any service/VM
   restart or policy change still requires owner coordination. The supplemental
   VPS does not replace the retained **Apple Silicon/macOS 26/Xcode 26.5** or
   **true Intel/macOS 15/Xcode 26.3** qualification configurations in the
   [Mac handoff](../testing/mac-handoff.md).
2. With the recovered admission, diagnose actual Native runtime/test startup using
   bounded source/binary-bound observations before another full writer. A
   retained failed-writer binary is diagnostic input, never a successful
   immutable producer or complete-suite pass.
3. Run the complete writer with fresh owned state; independently review every
   generated dependency/checksum change, commit the reviewed candidate, then
   run the complete strict platform, ABI, compiler and packaging gates in a
   fresh immutable context. Preserve failed attempts. Maven-local publication
   and consumer operations remain separately gated.
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
