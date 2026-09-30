# Dependency maintenance context

This is the fixed maintenance bridge's operational contract, not execution
admission or a qualification result. Source review and focused controls must
precede an explicitly admitted hosted run. Adding these files proves no test,
native control, generated dependency delta or Release gate has passed.

## Separate entries and identities

Both entries use `scripts/hosted_dependency_update_context.py`, with source-fixed
GENERATION and QUALIFICATION profiles, not a public command/case selector.
Use the workflow's checked absolute interpreter with `-I -B -S`; do not reconstruct
hosted identity or invoke a private entry from an interactive shell.

| Entry | Workflow/job | Public command suffixes |
| --- | --- | --- |
| `scripts/run-hosted-dependency-update.py` | `dependency-update-candidate.yml` / `generate` | `generate`, `before-upload`, `after-upload`, `before-failed-upload`, `after-failed-upload` |
| `scripts/run-hosted-dependency-context-qualification.py` | `dependency-update-context-qualification.yml` / `dependency_context_qualification` | `qualify`, `before-upload`, `after-upload` |

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

## Original owners and retirement

F is the actual workflow foreground and alone retains its original validated
Recipient, exporter and `GITHUB_OUTPUT`. Its constructor captures ordinary inputs
and the original RAW Step start only. After recipient validation and closed
prefix captures, `prepare_case` acquires the one passive F native identity;
`run_case` starts the fixed nonroot service D and its direct producer P. Private
`_service <directory>` and `_produce <fd>` are internal entries, not new commands.

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
qualification. Full-job admission remains strictly before `2026-10-04T20:30:00Z`;
recipient policy expires `2026-10-05T00:00:00Z`. No extension is authorized here.

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
