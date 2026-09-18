# Dormant bootstrap initialization — 18 September 2026

**Source/offline scope only; apps are not in repository Releases.** This follows
the [canonical source-preparation increment](hosted-canonical-source-2026-09-18.md)
at `7d6c26b1938071891b073824f23821d17f829d19`. The containing commit and final
complete-patch verdict will be mapped after review and remote preservation to
[#437](https://github.com/p2pKit/P2pKit/issues/437), with the shared prerequisite
recorded in [#424](https://github.com/p2pKit/P2pKit/issues/424).

## Source boundary

The internal `initialize_after_entry(transition)` selects recipient validation
and canonical initialization in one original call. Its shared once-claim fixes
intent before the first clock/native/file supplier, including failed attempts.
The existing `run_recipient_after_entry(transition)` remains recipient-only; its
returned `RecipientPrefix` cannot authorize retroactive initialization.

The second exact parent starts only after the original recipient resources,
handlers, final callbacks and clocks have closed successfully. It does not call
the closed predecessor's methods or recreate authority from JSON. New handles
reread original recipient/preparation/adoption/entry bytes; retained in-process
graph/path pins bind the original closed objects. This is finite input binding,
not a sandbox against arbitrary Python or closure-code replacement.

The initializer has distinct source-owned Owner/window/native/capture resources:
**work120 / native165 / prefix195**, further shortened by original cumulative
allocation/job fences. Actual native finalization also has
**actual-final-start+45**; readback has **read-start+30**. Independent LOCAL
ceilings and RAW/LOCAL high-waters remain. The fresh Git-query supplier receives
one immutable work/final pair, with its actual finalizer return wholly inside
work120; it does not mutate Owner limits or spend native/read reserves.
No bound was widened. The proposed caps remain unadmitted/unmeasured.

The canonical request uses the existing captured-source loader and fixed `init`
argv, **not** recipient `--minimum-ns`. The parent pins explicit installed
`JAVA_HOME`/`P2PKIT_AUDIT_JDK21` paths and tool identities without executing Java
or qualifying versions. It repeats source/request/environment checks before
launch. State must be absent; canonical initialization creates its fresh home.
The exact ASCII state-path stdout contract admits native LF/CRLF, not a recipient
ACK or product receipt; unsupported Unicode state paths refuse before launch.

Native and capture close precede context/property reads. The helper checks exact
source/job/home/policy fields; the parent separately checks the complete
empty-state roster.
Shared ancestor directory timestamps may change from unrelated sibling work;
their identity/type/mode pins remain, and source directories retain timestamp
checks. These point-in-time checks are not an atomic filesystem snapshot.

Original recipient closure is retained as `recipient-closed.json`. Pending
initializer evidence cannot attest its own subsequent close. A successful
`InitializationPrefix` follows final resource/handler/clock/roster checks, with
next-phase/export/save authority false, budget `NOT_ADMITTED`, tests
`NOT_PERFORMED`. No public CLI/workflow calls the initializer, and no producer,
cache/export/save/provider or encrypted-delivery execution is added. See the
[current cache contract](../testing/hosted-dependency-cache.md#internal-same-call-initialization-not-producercache-execution).

## Cleanup finding and correction

Independent R4 controls found that the first cleanup registry retained the same
nominally frozen dataclass it published. Direct field mutation still redirected
cleanup: replacing its record closed only **31/72** resources, exhausted the
64-diagnostic capacity and left UNKNOWN; replacing its handlers restored **0/2**.
Those original failures remain preserved and are not passing aggregates.

R5 instead retains the original call/registry/key/record/handoff/handlers in a
separate immutable tuple frame inside a private closure map. The private
original-frame map does not escape. Known-resource cleanup and handler
restoration use these private originals; live work strictly rejects changed
publications without repairing them. Only existing staged source binds and
pre-install handler retention can replace a private frame after validating its
prior publication.

The unchanged independent adverse oracles **14/15 both passed on R5**:
72/72 resources close once, both handlers restore, the exact first exception
survives in caller/owner/raise, and no UNKNOWN or publication rehabilitation is
introduced. R6 adds only an earlier absent-state check after readmission and
original reads; immediate prelaunch checks remain. Its author old-owner guard
is changed at class/receiver level so the guard itself does not mutate the pinned
old Owner. These last two corrections were diagnosed statically, not presented
as executed failing preimages.

## Exact source and author executions

The R6 three-file source/test freeze is tree
`bfbf10075bfa0379733622b0366b487662edaf3f`, before documentation. SHA-256:

| File under `scripts/` | SHA-256 |
| --- | --- |
| `run-hosted-cache-bootstrap.py` | `232d9b43a8ff589de6d6f81d834b4336f7e60f7bf62444346f53ff8539a5591c` |
| `hosted_cache_bootstrap_initialization.py` | `7744460782b5ce263bb3ca459122de35a3563090be73313cf93882479457e19d` |
| `tests/hosted-cache-bootstrap-initialization-test.py` | `ab10131ed8afeedc0efa04b2e50a1bc4da162fbec115ec941989232a111af6b2` |

Python3.12.3, actual UID65534, isolated `-I -B -S`, serial external90-second
limits plus5-second kill, with105-second recorders. The actual canonical
`initialize()` runs **in process on tiny ordinary-UID files**. Git/host/native/
GPG/process suppliers are modeled or prohibited; installed-JDK fixtures contain
nonfunctional bytes. **No generated initializer argv/subprocess, Java, Gradle,
SDK/download, application build, emulator, simulator or held CI ran.**

All R6 rows below use this command under the exact source copy, preceded by
`timeout --kill-after=5s 90s runuser -u nobody --`:

```text
python3 -I -B -S scripts/tests/hosted-cache-bootstrap-initialization-test.py <selectors> -v
```

| Exact selectors (one row per execution) | Result / unittest seconds |
| --- | --- |
| `InitModels.test_recipient_only_has_no_retroactive_initializer_authority InitModels.test_init_first_clock_failure_consumes_claim_without_new_owner InitModels.test_foreign_parent_and_window_subclasses_do_not_select_engine PureReadback InputAndDirectoryModels` | 8/8 PASS /28.950 |
| `FirstOwnerModels.test_initializer_local_work120_expires_independently_of_raw FirstOwnerModels.test_initializer_actual_final_local45_is_not_native165 FirstOwnerModels.test_initializer_local_read30_cannot_use_unused_native_time FirstOwnerModels.test_returned_resource_survives_falsey_postreturn_clock_failure` | 4/4 PASS /53.927 |
| `InitModels.test_existing_state_refuses_without_replacing_original_bytes` | 1/1 PASS /23.120 |
| `InitModels.test_initializer_never_observes_or_reopens_old_recipient` | 1/1 PASS /57.106 |
| `InitModels.test_fresh_query_pair_never_spends_native_or_read_reserve` | 1/1 PASS /60.783 |
| `InitModels.test_work120_expires_after_query_return_without_launch_or_new_allowance` | 1/1 PASS /18.653 |
| `InitModels.test_source_request_change_before_launch_refuses` | 1/1 PASS /24.017 |
| `InitModels.test_installed_environment_change_at_scope_return_refuses` | 1/1 PASS /25.513 |
| `InitModels.test_bad_stdout_is_not_recipient_ack_or_product_receipt` | 1/1 PASS /33.431 |
| `InitModels.test_context_field_drift_refuses_after_native_and_capture_close` | 1/1 PASS /33.445 |
| `InitModels.test_extra_state_output_is_not_an_empty_initializer_result` | 1/1 PASS /30.882 |
| `InitModels.test_original_recipient_bytes_are_reread_under_new_owner` | 1/1 PASS /36.420 |
| `InitModels.test_final45_cannot_use_all_native165_after_early_exit` | 1/1 PASS /31.993 |
| `InitModels.test_read30_equality_cannot_retain_successful_pending` | 1/1 PASS /33.786 |

The author file contains27 own methods. These **24 disjoint R6 method passes**
are supplemented by three **separately scoped R5** passes, not a27-method R6
aggregate. R5 tree `c0fa168f8fc062958c375cb3490d99a0829be194` has engine SHA
`195cf6f8430d934c9e1df2541db269678c90b03edb511916b0f849a02f546aa9`.
The two direct-holder selectors below use the same command envelope, together;
the positive selector uses a bounded private profiling wrapper around that
test script under the same interpreter/external bounds:

| R5 exact selectors | Result / unittest seconds |
| --- | --- |
| `InitModels.test_same_live_parent_initializes_only_after_recipient_closure` | 1/1 PASS /66.113 |
| `FirstOwnerModels.test_direct_published_record_change_cannot_erase_original_cleanup FirstOwnerModels.test_direct_published_handlers_change_cannot_skip_original_restoration` | 2/2 PASS /31.805 |

The profile wrapper SHA is
`01ea82569cfb12f374af878124d15e9dece650610e89c842c459d875c73504f7`.
Bounded SIGPROF sampling identified graph-check cost as the dominant expense.
This is offline model timing, **not hosted scheduling qualification**. No deadline
or assertion was relaxed, no optimization added, and the planned R4 profile
never executed. Independent review inspected the R5-to-R6 delta: the holder
interceptions stop before the new absence check; independent R6 positive
execution supplies current full-path coverage, rather than relabeling R5.

Because common recipient mechanics changed, three existing methods ran
separately on R6 with the same envelope but
`scripts/tests/hosted-cache-bootstrap-recipient-parent-test.py`:

| Exact selector | Result / unittest seconds |
| --- | --- |
| `ParentModels.test_rejected_call_aliases_do_not_saturate_large_known_resource_cleanup` | 1/1 PASS /6.135 |
| `ParentModels.test_handler_restore_failure_is_not_success_or_postclose_file_acquisition` | 1/1 PASS /13.636 |
| `ParentModels.test_handler_restore_cannot_append_a_success_shaped_closed_resource` | 1/1 PASS /13.430 |

These are not the whole historical recipient suite. Explicit selection of an
inheriting test class also includes its historical methods; bounded full-parent
checks select individual methods. Controls remain standalone, not new ordinary
CI minutes or bootstrap workflow activation.

Earlier author originals remain: R1 smoke2PASS/1ERROR on exact `signal.Signals`
scalar handling; R2 positive1PASS before cleanup corrections; R3 focused6PASS/
1FAIL on a nondeterministic timestamp fixture. R4's deterministic owned-fixture
timestamp controls2/2PASS do not erase R3. Every completed author result retains
source/fixture/repository manifests and unchanged rosters. The original recorder's
ambiguous `NO_REAL...INITIALIZER` label is preserved; R6 clarifies only its
description to `NO_GENERATED_INITIALIZER_SUBPROCESS`, without changing execution.
In-process canonical initialization was real within the tiny-file/model scope.

## Independent implementation review

**APPROVE_EXACT_INITIALIZER_IMPLEMENTATION_R6_SOURCE_AND_OFFLINE_ONLY**, report
SHA-256 `980389018deb1f3135a458fa8eea663c8d155c320a55213ab7fd7bcc7ae699c3`.
Review covers all three implementation/test files and the complete common
recipient registration/handler/native/cleanup delta, not just the helper.
This corrected report fixes an earlier prose count: independent A asserted17
originals, not18. The original report is preserved; source, tests, actual results
and implementation verdict did not change.

Five independent full-init controls were frozen before reading the new author
assertions; **5/5 PASS** on exact R6, in separate90s+kill5s/105s processes:

| Independent oracle | unittest seconds |
| --- | ---: |
| Actual canonical initialization, full original roster and close-before-read | 62.801 |
| Fresh query return at original work120 | 19.824 |
| Coherent context source/tree substitution | 36.798 |
| Extra evidence entry | 33.892 |
| Actual context read returns at LOCAL30 while RAW remains live | 34.219 |

Actual UID/GID65534, capabilities cleared, no-new-privileges, and root-owned
read-only source; all1,411 independent source bindings, rosters and control bytes
matched before/after. The new author assertion file was excluded from that
independent source copy. Control SHA-256:
`1e9a0a4be9d0f7564eaf792785c7a3de5ea1337f296e60687791d274fefe75db`.
No independent full-init failure/timeout was hidden or retried. Two exception-
layer corrections were made to an unexecuted first control draft, not mislabeled
as failed preimages. Planned independent prelaunch-mutation control F was not
authored/executed: after freezing its own oracles, the reviewer audited the
author's exact request/environment adverse controls instead of duplicating them.

The reviewer independently inspected23 original author packets across six
freezes, including failed originals, raw output hashes, selected outcomes and
complete source/fixture/repository manifests. Audit SHA-256:
`d0b8bccd074d6e9e288db2d85b77fbc9e949f2245c8726db9b2c06b0302e4a6f`.
R2's19/19 independent interception/helper controls are not full initialization.
R4's18 invocations retain13PASS/5FAIL: three fixture mistakes plus the two genuine
holder defects above. R5 unchanged14/15 passed2/2 in28.975s; its raw execution
SHA-256 is `3072d5b25147f6c306edd843d1e46ccd7b8927a116152f7942b5c1c86f3770c4`.
None is an all-green R4/R6 aggregate. Agent review is not formal different-account
GitHub PR approval, native qualification or permission to lift a HOLD.

## Unchanged delivery prerequisites

Read-only complete paginated metadata at **12:42:51 UTC** exactly matches the
12:14 originals in every inspected domain:78 open issues, seven dependency PRs,
no campaign PR, no queried active Actions and no Release application assets.
Complete #437/#424/#457/#143/#144 conversations/timelines, refs, rules and
advisory are unchanged. Dependency-PR detailed reviews remain separately dated.
Required contexts remain `complete-gate`, `review`, `scan / osv-scan`,
`osv-scanner`. Main remains `3bc76f956f8f47447b51a62474fc878b9c43173c`.

The next source work is distinct producer/staging/empty-seed/custody preparation,
original same-home stop/known retirement, positive streamed export, freeze,
provider save/probe and encrypted custody/seal. No production caller invokes
`cache.export_snapshot` or `cache.save_set`. Configuration-only `help` cannot
satisfy ordinary ABI/simulator/transcript acceptance or prove full population.

The named routine custodian, exact public key, finite14-day policy, legitimate
trusted-original-base bootstrap and formal approval remain absent. Both ordinary
HOLDs remain;5400 is UNADMITTED/UNMEASURED, Windows NativeFile900 and
Snapshot576MiB are unchanged. Actual native/provider/resolver/custody/scheduling/
delivery qualification, current required checks and normal reviewed main merge
still precede development sample Releases. No PR/merge, Release, production/
Maven/Store publication or issue closure is part of this source work.

Accepted preview35070982169 and #424 writer35066719641/1 were not rebuilt or
redownloaded. #372's20 Kotlin tests remain uncompiled/unexecuted. OSV remains
**EXCEPTED_NOT_FIXED** through2026-10-31, with no scan/remediation/extension.
Physical phones stay deferred. Protected instructions, published RC history,
compatibility restrictions and unrelated branches/proposals remain unchanged.
All24 inspected worktree tips remain ancestors;23 historical worktrees are
untouched, including20 with retained dirty patches. Historical accounting stays
206/234 repair-approved,207/234 resolved; audit/release remain **NOT_READY**.
