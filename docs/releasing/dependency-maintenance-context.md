# Dependency maintenance context

This is the fixed maintenance bridge's operational contract, not execution
admission or a qualification result. Source review and focused controls must
precede an explicitly admitted hosted run. Adding these files proves no test,
native control, generated dependency delta or Release gate has passed.

## Separate entries and identities

These entries use `scripts/hosted_dependency_update_context.py`, with source-fixed
GENERATION, QUALIFICATION and STARTUP profiles, not a public command/case selector.
Use the workflow's checked absolute interpreter with `-I -B -S`; do not reconstruct
hosted identity or invoke a private entry from an interactive shell.

| Entry | Workflow/job | Public command suffixes |
| --- | --- | --- |
| `scripts/run-hosted-dependency-update.py` | `dependency-update-candidate.yml` / `generate` | `generate`, `before-upload`, `after-upload`, `before-failed-upload`, `after-failed-upload` |
| `scripts/run-hosted-dependency-context-qualification.py` | `dependency-update-context-qualification.yml` / `dependency_context_qualification` | `qualify`, `before-upload`, `after-upload` |
| `scripts/run-hosted-jmdns-startup.py` | `audit-jmdns-startup-context.yml` / `jmdns_startup` | `run`, `before-upload`, `after-upload`, `before-failed-upload`, `after-failed-upload` |

Executable jobs are owner-bound `workflow_dispatch` only, on GitHub-hosted
`macos-26` ARM64, using the existing serialized `p2pkit-nonphysical-heavy` queue.
Registration pushes do not run the jobs. Read back actual workflow registration,
source/tree, workflow/job/ref and run/attempt before admitting or accepting a run.

- Generation accepts exactly `controller_sha`, `controller_tree`, `candidate_sha`,
  `candidate_tree`, `dependency_base_sha`. J is the actual controller/workflow
  source, S the separately reviewed dependency candidate, B its unchanged lock/XML
  ancestor. Preserve the generation workflow's existing branch/owner checks.
- Qualification accepts exactly `source_sha`, `source_tree`, binding actual J;
  its ref must match
  `refs/heads/work/release-foundation-dependency-context-[A-Za-z0-9-]+` completely.
  Synthetic fixture commit T and each genuine canonical context A are separate
  identities, never replacements for J, S, B or a real generated result.
- Startup accepts only `source_sha`, `source_tree` for its actual controller and
  Java source. Its ref must match
  `refs/heads/work/release-foundation-dependency-context-startup-[A-Za-z0-9-]+`.
  It has no mutable dependency candidate or generated lock/XML output.

## Original owners and retirement

F is the actual workflow foreground and alone retains its original validated
Recipient, exporter and `GITHUB_OUTPUT`. Its constructor captures ordinary inputs
and the original RAW Step start only. After recipient validation and closed
prefix captures, `prepare_case` acquires the one passive F native identity;
`run_case` starts the fixed nonroot service D and its direct producer P. Private
`_service <directory>` and `_produce <fd>` are internal entries, not new commands.

The current source adds a **conditional daemon-startup experiment**, not an
accepted network-permission fix. Launchd first enters the one-purpose native
`scripts/hosted_dependency_context_launcher.c` prelude as root. It performs no
arbitrary network command or project execution while privileged. It checks the
original daemon identity and joins the compiled account name, UID and primary
GID through public `getpwuid_r` and `getpwnam_r`, using one fixed 16 KiB buffer.
Each lookup must return zero and a non-NULL record with all three exact values;
absence, mismatch or buffer exhaustion refuses without an application retry.
One supported `initgroups` call initializes the original account's groups;
there is no `setgroups` fallback or application truncation of its complete
captured roster. Fixed GID/UID drop, real/effective/saved-ID checks, both complete
group comparisons and both root-reacquisition refusals remain mandatory. The
same account join repeats after drop, before final descriptor closure and
`/dev/null` stdio revalidation. Only then does the unchanged isolated Python D
entry run by same-PID `execve`. There is no command/UID argument, forked root
monitor, project interpreter as root, or privacy-database change.

The captured name must satisfy `[A-Za-z_][A-Za-z0-9_-]{0,63}`. Header preparation
rejoins it by both original UID and captured name before and after compilation,
requiring exact canonical name/UID/GID matches. One octal-escaped name constant
joins the unchanged numeric account, full group set and closed argv/environment;
no runtime account selector or replacement lookup values are adopted.

These fixed supported OS lookups may use the trusted configured resolver,
OpenDirectory/XPC and library-managed resources; they are not a no-network or
no-thread guarantee. Internal OS retries have no caller timeout argument, so
the unchanged external clocks and retirement rules remain binding. Account
joins and full `getgroups` comparisons are non-atomic: they cannot prove the
private membership-UID state. An internal named-lookup failure can leave that
state NONE despite `initgroups` success, losing permissions outside its advisory
cache. No SPI, second roster or per-group proof is substituted. Fresh native
functional and timing qualification, including the actual LAN path, is still
required; source checks do not establish that this residual is absent.

Original nonroot F compiles this small infrastructure input with the fixed
already-installed Apple Command Line Tools ARM64 toolchain and macOS SDK, within
the existing case deadline. Its compiler-local `DEVELOPER_DIR` selects this
infrastructure toolchain only; product tools retain Xcode 26.5.
The real compiler/linker, resource directory and SDK/header dependencies must
pass root-only, non-writable input checks and before/after binding. A shim path
alone is not sufficient. The returned executable must fit 65,536 bytes and the
checked Mach-O OS-loader/libSystem/libproc dependency boundary. This preparation
is not a product build or native acceptance result. Local compilation is not
part of the offline controls. Actual CLT input custody and native execution
remain unqualified.

Admin creates the original root-private launcher exclusively and installs only
the original bounded F bytes, in chunks of at most 16,384 bytes. It never copies
a mutable runner path as root. Exact readback/metadata precedes execution; the
registered plist launches only this executable from `/`, with a closed OS-only
environment. Both original root files and the exact member set are rechecked
and retired after D/P closure. The first-case call ceiling is 130: the original
96 calls, three metadata calls for `chmod`, 19 fixed launcher-install calls, at
most four chunk writes, and eight launcher-retirement calls. This is an
operation-count bound only: no command, case, Step, job, byte, retry or policy
deadline is extended.

All three profiles share this launch path. Old qualifier results do not qualify
the changed bridge. The prelude source, generated closed header, compiler
returns, dependency manifests, exact binary and input inspection are retained
as private case evidence. A failed pre-HELLO start is still a refusal, not
original D/P closure or permission to export an incomplete case.

P initializes canonical state once and calls the unchanged executor. D watches
actual F-channel EOF and P's original pipes; F watches original D/P native events.
D's real EOF reaction and F's real D-exit/orphan reaction signal only the retained
original P, at most once per reaction. No PID/group sweep, identity rebinding,
clock renewal or extra Gradle stop is a recovery path. D/P receive no Recipient,
credentials or public command-file authority. Closed JSON is DATA, not an owner.

Require original command/stop/source/native/direct-wait/stream returns and exact
service registration/plist/root retirement before freezing evidence. Unknown
status, timeout, cancellation or incomplete custody refuses production; a final
frame or EOF alone is not success. Failures are sticky: preserve them, do not retry
automatically or export after speculative cleanup.

## Fixed qualifier; not productive generation

One invocation runs these four serial cases once through the same bridge. K is
the independently joined live canonical product child; no case/argv input exists.

| Case | Fixed action after live K join | Required synthetic observation |
| --- | --- | --- |
| Q1 NORMAL | Release K | Canonical/product 0, stop 0, complete normal custody. |
| Q2 NONZERO | Release K | Actual canonical/product 23 and stop 0; never normalize 23 to success. |
| Q3 F_EOF_ACTIVE | Close only F's write half | D's actual EOF reaction; canonical/P 125, product -15, stop 0; production refusal. |
| Q4 D_LOSS_ACTIVE | Signal original D with SIGKILL | F's actual D-exit/orphan reaction; canonical/P 125, product -15, stop 0; production refusal. |

Both negative cases require original cancellation/native/source receipts and
unrelated sentinel survival. Q4's missing D wait/frame/pipe EOF stays
`ABSENT_D_DIED`; unfinished D-owned captures stay `INCOMPLETE_D_DIED`. Never invent
D userspace closure from kernel writer death. Unexpected failure is not a control
PASS. The fixture runs no Java, Gradle, SDK, dependency resolution or network work.

## Original clocks and refusal ceilings

Allocation schema 2 binds `sourceTree` and
`darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)`. F/D/P share that RAW domain and the
original allocation/Step/policy ends. Canonical internal monotonic receipt values
are not RAW deadlines. Finalization starts at P's immediately captured RAW return
of the last eligible original command, not later DATA receipt or report copying.

| Layer | Generation seconds | Qualifier seconds |
| --- | ---: | ---: |
| Job / productive or qualifier Step | 12600 / 9900 | 2460 / 1740 |
| Prerequisites / product / stop | 900 / 7200 / 120 | Fixed synthetic product 20 / stop 5 / ready 15 |
| Native headroom / finalization / export | 180 / 300 / 120 | Suite 1200; four cases at most 300 each; export 120 |
| Upload tail | 1320 | 420 |

Generation retains writer reserve 9240, entry reserve 10440 and productive-Step
reserve 9120; setup/retirement must fit existing slack. Qualifier admin calls remain
at most 10 seconds, with one reserved unexpected-abort window of 120 seconds and
freeze 60. Every wait is clamped to its original enclosing ends. Qualifier ceilings
are unmeasured refusal bounds, not guaranteed completion or canonical-init120
qualification. The owner-approved policy window is `2026-10-06T18:26:00Z`
inclusive through `2026-10-20T18:26:00Z` exclusive. Full-job admission remains
strictly before `2026-10-20T14:56:00Z` (policy end minus the unchanged 12600-second
reserve). No further extension is authorized here; renewal does not restart
original Actions artifact retention.

## Evidence and remaining gates

Only original F exports once with its same Recipient, after required writers and
resources retire. Keep closed source/input/canonical/native/admin/stream records
and truthful negative annotations. Exporter limits remain 512 MiB/10,000 members,
ciphertext 576 MiB; no tail archive, omitted evidence or plaintext-log upload.

Generation success retains the public patch/metadata and encrypted originals in
the existing separate artifacts. Only eligible, completely closed actual codes
1–123 use its encrypted failed-product branch; infrastructure/cancellation does
not. Qualification has one pass-only encrypted
`dependency-context-evidence-<runId>-<attempt>` artifact, containing only
`evidence.tar.gz.gpg` and `manifest.json`. All retain 14 days. Preserve mutually
exclusive guards and original export/output/upload returns; inspect actual
artifact metadata and source-bound originals, not just Actions success.

After implementation review and focused controls, require genuine four-case
original-result acceptance, then one fresh exact J/S/B full supported generator
result, including all eight real JmDNS lifecycle modes and lock/XML provenance.
Synthetic controls do not qualify that JVM chain, canonical-init120,
Stage1/current authority/provider/cache, C1/C2, ordinary FULL/Desktop, four future
apps, Maven, owner merge or publication. **All HOLDs and Release NOT_READY remain.**

## Focused direct-Java startup diagnosis

The STARTUP entry uses the same original F/D/P nonroot bridge and unchanged
canonical executor, but removes the Gradle/JUnit layers from the Java invocation.
It compiles the sixty tracked vendored Java sources and the unchanged lifecycle
fixture once using JDK17, with the existing hash-pinned SLF4J API dependency.
All eight existing modes run in their fixed order, once each, stopping at the
first failure. Each retains the existing 45-second child ceiling, READY 10-second
assertion, JVM resource limits, bounded transcript, exact PASS and natural-exit
requirements. Later modes are NOT_RUN after failure, not skipped passes.

All source, compiler/runtime and produced classpath identities are retained.
JDK21 is admitted and identified but does not run the JDK17-only fixture. No
Android SDK setup, dependency lock generation, shared/cross-run cache reuse,
socket-family flag or alternate sender is introduced. The native prelude above
must drop privileges before Java or any project entry. The real canonical
`gradlew --stop` still runs, and can require its hash-pinned wrapper download.
The fixture's existing bounded route observation remains part of a failed run;
opt-in extra network probes are not enabled.

STARTUP retains the generation job/Step and finalization/export/upload ceilings
above, with individually bounded fixed commands. These are refusal ceilings,
not measured canonical-init120 qualification. It uses the same finite recipient
policy and 14-day encrypted-only artifacts: `jmdns-startup-evidence-<run>-<attempt>`
or `jmdns-startup-failed-evidence-<run>-<attempt>`. Only known-closed actual product
failures may use the latter; the job remains failed. Unknown native/stop/stream
closure and post-return validation failure refuse export. No plaintext logs or
dependency candidate are uploaded.

A pass is direct-Java diagnostic evidence only, not `:p2p-transport-lan:allTests`
or ordinary/Release acceptance. A failure is not by itself proof of macOS privacy,
native errno or kernel socket-family causation. The full supported generator and
the ordinary required gates must still pass their genuine execution paths.

STARTUP alone has a **fail-only startup observation**: thirty seconds after the
original bootstrap returns, if still waiting for a connection or complete HELLO,
F may query its exact retained registration once through the original bounded
Admin path. An already-ready connection/complete HELLO is processed first; the
original enclosing deadlines still take precedence. Consuming this observation
always refuses with `STARTUP_OBSERVATION_ONLY`, even for a running registration.
Public hints contain only finite foreground phase, registration state and
last-exit DATA, never raw output or proof of native ownership/exit/closure.
Ordinary timeout hints without a query say `NOT_OBSERVED`. The thirty seconds
are a diagnostic safety trigger, not canonical-init120 or a Release acceptance
limit. GEN/Q, the normal 130-call ceiling and all required checks are unchanged;
unknown closure remains ineligible for evidence export.

The original `36742212640/1` STARTUP result at `76c7fa5e3a6b92b33572c8d9915bce1b21a4b20d`
passed its four preparation commands, then failed `startup-control` with
`NoRouteToHostException`, `host_not_announced` and the fixture rescue marker.
Seven later modes were NOT_RUN. This isolates the failure away from Gradle/JUnit;
it does not establish its OS/provider cause. The changed prelude requires a fresh
single STARTUP observation and, if successful, a fresh four-case qualifier and
full supported generator before any productive or Release claim.
