# Dormant bootstrap staging and empty seed — 18 September 2026

**Source/offline scope only; apps are not in repository Releases.** This follows
[reviewed canonical initialization](hosted-bootstrap-initialization-2026-09-18.md)
at `a8058c329098a31bbcc813caa0193d7cd339d6f0`. The containing commit and final
complete-patch review will be mapped after approval and remote preservation to
[#437](https://github.com/p2pKit/P2pKit/issues/437), with the shared prerequisite
recorded in [#424](https://github.com/p2pKit/P2pKit/issues/424).

## Source boundary

The separate `hosted_cache_bootstrap_staging.py` leaf supplier exposes
`stage_empty(parent, originals, phase)` and
`observe_empty_seed(parent, originals, phase, stage_evidence)`. There is no CLI,
workflow or production caller. Neither operation consumes `InitializationPrefix`
as authority or retrofits execution onto a closed predecessor. The missing
same-call parent must still own original returns, single use, live readmission,
phase/owner transitions and failure custody.

Before callbacks, the leaf snapshots independent immutable admission, original
attempt/jobs response, proposal, initializer/context/property, directory and
clock values. It rederives the service-bound allocation and derives the byte
cohort only from bootstrap admission. Supplied consistent records cannot
establish their provenance, actual successful execution or a trusted step outcome.
Original indented canonical JSON is hash-bound and reread without normalization.

Stage exclusively creates an absent container and `restore-home` (S). Its final
complete roster is exactly `restore-home` and `staging.json`. An existing empty
container is rejected, not adopted, replaced or deleted. The seed is read-only:
complete S emptiness, exact properties-only canonical H, empty evidence and
cancellation directories, source inputs, supplied original directory identities,
phase-local file stamps and exact bytes are rechecked. File stamps are first
observed by this leaf, not reconstructed initializer-time stamps. These are
point-in-time observations, not an atomic filesystem snapshot. All declared
artifacts have `ABSENT` inventory entries and all dependency counters are zero.
This is not a copier budget omission, cache
provider result or dependency population. Metadata I/O did occur.

Seed binds the actual supplied stage-return bytes and final RAW/LOCAL observations,
not merely `staging.json`. Stage has hard120; seed has hard120/new-work90. Both
are shortened by their original proposed cumulative/job fences and independent
LOCAL ceilings. Final RAW-supplier return, serialization, callbacks and leaf
closure spend those same intervals; equality is expired. These are dormant
source limits, not admitted or measured bootstrap scheduling.

New factory returns are independently retained before the parent's fallible
post-allocation check. Actual matching new ledger rows may be closed; unregistered
returns remain retained UNKNOWN obligations, not optimistic known cleanup.
Preexisting parent resources are never adopted and remain with their caller.
Original errors, including falsey exceptions, survive later close failures.
UNKNOWN forbids further acquisition;
partial evidence/resource references remain attached to the original exception.
The enclosing parent is not closed or claimed retired by the leaf.

All results remain budget `NOT_ADMITTED`, tests `NOT_PERFORMED`, and next-phase/
export/save authority false. Existing ordinary seed/export/save bootstrap
refusals, `files.INPUTS`, cache-key grammar and ordinary controllers/workflows
are unchanged. `BOOTSTRAP_INPUTS` is a separate source-provenance roster, not a
new provider-key component. There is no dependency copy, producer, export/save,
provider or encrypted-custody execution in this increment.

## Root causes and preserved failures

Independent static inspection and lead investigation found three R1 defects;
three unchanged desired-state author oracles actually failed on R2 before repair:

1. A factory returning a preexisting parent resource was rejected by real
   `Owner.acquire`, but the leaf then adopted that old row and closed it.
2. Final extra-source-directory verification failed first, but a later close
   failure replaced that original exception.
3. The last RAW-clock supplier returned at LOCAL120 while RAW remained live;
   the stale pre-supplier LOCAL observation still allowed success.

R3 snapshots pre-call row/resource identities, records the source failure before
cleanup, and samples LOCAL again after retaining the returned valid RAW
high-water. The same three controls then passed. No existing supplier assertion
or deadline was relaxed.

Independent follow-up inspection found an impossible successful initializer
window: the exact cumulative fence formulas could still put `firstNs` after
`workEndNs`. The added desired-state control failed on unchanged implementation
R4. R5 also requires `first < work <= native <= prefix`; that control and the
complete new author class passed. A separate lead question and independent
inspection then identified a missing lower bound: initializer first could precede
its original service-response completion while later observations recovered.
The desired-state R6 control failed before R7 additionally required
`serviceLast <= first`, without changing service-clock translation or treating
the conservative job-start basis as an earliest execution time. These are
source/model failures and repairs, not observed hosted/native incidents or
changes to the earlier accepted initializer.

## Exact source and executed author controls

R7 two-file freeze: tree `f138fabfed9ae4deffcb75bbfb4ce511227cb003`;
patch SHA-256 `63e3c39e26d0cd2fec7cc96e751ad32e40e9c91a023da9d6fedd80c466de2c32`.

| File under `scripts/` | SHA-256 |
| --- | --- |
| `hosted_cache_bootstrap_staging.py` | `bc09030f833203edeb077377ef55a9e7a7903e5febc7ced7e979c96d0c34a870` |
| `tests/hosted-cache-bootstrap-staging-test.py` | `9e4256732ceb57b22fe6522fd1ebe36493d6200eace5d430b26fb6015c8c6961` |

Python3.12.3, actual UID65534, `-I -B -S`, serial external90-second limits plus
5-second kill and105-second recorders. Executable modules come from root-owned
read-only frozen source; modeled file-binding inputs use tiny ordinary-UID POSIX
fixtures. Real bootstrap `Owner` and POSIX file suppliers run. Admission,
service/initializer originals and RAW/LOCAL clocks are modeled. **Unlike the
preceding initializer controls, these tests do not execute canonical initialize(),
even in process.** Native, Git, GPG, network, Java/Gradle, dependency copy,
export/save and provider operations are modeled or prohibited, not qualified.

All invocations use this command with the indicated selectors under the exact
frozen source, preceded by `timeout --kill-after=5s 90s runuser -u nobody --`:

```text
python3 -I -B -S scripts/tests/hosted-cache-bootstrap-staging-test.py <selectors> -v
```

| Freeze / actual selection | Result / unittest seconds |
| --- | --- |
| R1: `LeafModels.test_stage_exclusively_creates_only_two_container_members_and_keeps_parent_live LeafModels.test_seed_is_read_only_complete_absence_not_budget_omission_or_provider_result` | 2/2 PASS /0.241 |
| R2: the three adverse methods listed below | 0PASS/3FAIL /0.133 |
| R3: the same three adverse methods | 3/3 PASS /0.149 |
| R3: `LeafModels` | 45/45 PASS /2.500 |
| R4: `LeafModels.test_initializer_claim_with_no_original_work_interval_is_refused_before_acquisition` | 0PASS/1FAIL /0.093 |
| R5: `LeafModels` | 46/46 PASS /2.397 |
| R6: `LeafModels.test_initializer_first_must_not_precede_original_service_response_completion` | 0PASS/1FAIL /0.106 |
| R7: `LeafModels` | 47/47 PASS /2.317 |

Exact three adverse selectors:

```text
LeafModels.test_factory_return_of_preexisting_parent_resource_is_not_a_leaf_allocation
LeafModels.test_final_source_verification_error_survives_a_later_directory_close_error
LeafModels.test_final_raw_supplier_return_at_local120_cannot_use_its_earlier_local_sample
```

R1/R2 implementation hash `b8784324586ec680b5f23b3178e57bf7982e5aa046580ee7c0b00b237cd6a5b3`;
R3/R4 implementation `dfa0e28844bd6b7d492077e3590c854b4f4feb4076032678e8eadb368f8a7e20`;
R5/R6 implementation `ca0bff7610c6da79f06ee4801c28842131887eab65d471c221bf98b3862a408f`.
Results and original failures remain separate, not added into a larger passing
aggregate. All1,415 frozen source bindings, repository source/roster and absence
of extra source-copy files were checked before/after each recorded execution.
The new class is standalone, not registered in ordinary CI or an activated
bootstrap workflow. No accepted historical suite, writer or preview was rerun.

## Independent implementation review

**APPROVE_EXACT_STAGING_EMPTY_SEED_R7_SOURCE_AND_OFFLINE_ONLY**, report SHA-256
`4bc282547b48cb419635d33e151c93cf05ac0d41b3057baf9a01d4b8babec10f`.
This approves the exact implementation/test source, not native/provider execution,
same-call parent integration, budget admission or formal GitHub approval. Final
complete-patch/document review is mapped separately with the containing commit.

The reviewer froze its independent A–K oracles before reading the new author
assertions. **11/11 PASS** on exact R7 in one execution:0.852s unittest,
1.371s recorder, exit0, no timeout. This uses a separate three-artifact fixture,
real POSIX leaf/Owner calls and exact executable-source binding files, modeled
originals/clocks and prohibited native/network/dependency/provider operations.
The author fixture instead uses two artifacts and synthetic nonexecuted binding
files. Neither executes canonical `initialize()` or generated argv.

Independent controls cover stage/seed success and nonauthority, duplicate-owner
rejection, falsey first-error preservation, registered post-return allocation
failure, coherent original-input mutation, unexpected empty S subdirectories,
final serialization failure, original soft90 equality and both impossible
initializer chronologies. Its final-RAW-at-LOCAL120 control runs on **seed**,
complementing the author's **stage** case. Private r1/r2 control drafts were
statically corrected before execution; r3 was the first and only execution.
They are not failed implementation preimages or earlier passing suites.

Actual independent UID/GID65534, cleared supplementary groups and capabilities,
no-new-privileges, `-I -B -S`, external90+kill5/recorder105. All1,415 source
hashes/modes/roster and control bytes match before/after; no owned process remains.
Independent control SHA-256:
`f4b0f1f29307f851443324b04ed717de5ca49c6d1a34cc0be454056db36ac4a8`;
original execution JSON:
`5bbb84a03fb431bb48f9b911f337ef120251656bfa02fe0f79befec01437e02a`;
stderr:`3c25c5b3f335016579d0cbd44c4188aacd0d6a95fcaf3258d2745f0678e633df`.

The independent passive audit inspected all eight original author invocations,
their exact argv/results/stdout/stderr/manifests, and all seven complete source
freezes. All1,413 base blobs/modes remain exact. The original42 tests and11
fixture/helper methods are AST-unchanged through R7; exactly five desired-state
methods were added, unchanged across their failing preimages and corrected runs.
Audit SHA-256:`da0c421872339928ad9726b81c549bf84fbfb4226227db5f71c5cc67b53e0155`.
No author suite was replayed for that audit. Author47/47 and independent11/11
remain separate scoped results, not a larger aggregate or hosted acceptance.
Agent review is not formal different-account GitHub PR approval.

## Remaining delivery prerequisites

Complete paginated read-only metadata at **13:44:48 UTC** matched13:25 originals
in every inspected domain:78 open issues, seven dependency PRs, no campaign PR,
no queried queued/in-progress/waiting/requested/pending Actions, and zero assets
on the two existing Releases. Complete #437/#424/#457/#143/#144 conversations and
timelines, refs, effective rules and advisory were unchanged; detailed dependency
PR reviews remain separately dated. Required contexts remain `complete-gate`,
`review`, `scan / osv-scan`, `osv-scanner`; main remains
`3bc76f956f8f47447b51a62474fc878b9c43173c`.

Next is the original same-call staging/seed parent, then configuration-producer
custody, original same-home stop/known native retirement, positive streamed
export, frozen save-set/provider save/probe and encrypted custody/sealing.
No production caller invokes `cache.export_snapshot` or `cache.save_set`.
Configuration-only help cannot satisfy ordinary ABI/simulator/transcript tests.

Both ordinary HOLDs and the missing named routine custodian, exact public key,
finite14-day legitimately trusted-original-base policy and formal approval
remain. Proposed5400 stays UNADMITTED/UNMEASURED. Windows NativeFile900 and
Snapshot576MiB stay unchanged; the latter cannot contain a2GiB dependency cohort.
Genuine native/provider/resolver/custody/scheduling/delivery qualification,
current required checks, formal nonauthor PR review and normal main merge and
preservation still precede development sample Releases.

No build/download, held dispatch, PR/merge, Release, settings change or closure
occurred. Accepted preview35070982169 and #424 writer35066719641/1 were not
rebuilt/redownloaded; CLI9/diagnostics23 and six inspected original exports
remain accepted in their original scope. #372's20 Kotlin tests remain
uncompiled/unexecuted. Physical phones and production/Maven/Store publication
remain outside this work. OSV remains EXCEPTED_NOT_FIXED, Kotlin2.4.10 affected,
expiry2026-10-31; no scan/remediation/extension is claimed.

Protected instructions, immutable RC history, compatibility restrictions and
unrelated branches/proposals remain unchanged. All23 historical worktrees,
including20 retained dirty patches, matched their preserved statuses/diffs/
untracked hashes at this resume. Historical accounting remains206/234
repair-approved,207/234 resolved; audit/release **NOT_READY**.
