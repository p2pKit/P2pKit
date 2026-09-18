# Dormant configuration-custody parent — 18 September 2026

**Source/offline scope only; apps are not in repository Releases.** This extends
the [approved reservation leaf](hosted-bootstrap-configuration-custody-2026-09-18.md)
at `ff82415eb2c1fd98bc71aa6bb6c0f6819508e5f2`, tree
`eaa27ffc0527f7d0d82a93a6b2452dc75c36e2d9`. The containing commit, complete-patch
review and remote preservation are mapped separately in
[#437](https://github.com/p2pKit/P2pKit/issues/437) and shared
[#424](https://github.com/p2pKit/P2pKit/issues/424). Main is not changed.

## Original same-call provenance, not more supplied-data authority

The internal single-argument `reserve_configuration_after_entry(transition)` in
[`run-hosted-cache-bootstrap.py`](../../scripts/run-hosted-cache-bootstrap.py)
selects exact boolean reserve⇒stage⇒initialize intent before the original shared
claim. Recipient registration appends field7; initializer registration remains6
with its existing indices. Existing wrappers explicitly select reserve=False,
keeping their signatures and original return plans. Failed claims remain consumed;
stage-only return data cannot retrofit reservation intent.

The existing coordinator stays RUNNING through a third distinct file-only
`_StagingPhaseParent`/`_StagingFileOwner`/`_StagingWindow`, not COMPLETE then reopened.
Its original plan, registries, control tuple and result are pinned separately from
the completed stage/seed parent instances and exact private frames. The graph now
traverses completed `StagingPrefix` and typed custody inputs/results, deliberately
not the still-live sequence's entire dictionary. Legitimate advancement is not
predecessor mutation. No old owner/window/resource method is called by the third
parent; downstream failures cannot error or reopen those completed parents.

The approved leaf receives typed `StagedEvidence` captured from the exact seed
parent return. Its distinct `ReservationEvidence.request_raw` is not a renamed
staging field. The new parent retains `leaf-evidence.json` and
`request-original.json` under `custody-prepare-parent`. It separately pins the actual
request path, directory identities and file binding before later suppliers, then
reopens/rereads `configuration-custody/request.json` and empty `retained/`. Intact
parent copies do not mask original mutation or replacement. These are point-in-time
checks, not an atomic freeze, original hosted identity or provider qualification.

Exactly seven custody labels extend this phase's allowlist in both acquire and
roster checks; old phases retain their original label set. The lexical request-reader
facade borrows this same owner/window, adds no independent owner or new deadline,
and propagates even a falsey first close error that the owner only recorded.

All admission, reads, reservation, readbacks, closes, handler restoration and final
serialization stay inside **custody-prepare at most120 seconds**, with soft==hard,
shortened by original cumulative/job and directed LOCAL fences. First RAW/LOCAL
must follow the seed parent's final checks. Final parent high-waters follow the
leaf, close and serialization; a valid RAW is retained even if subsequent LOCAL
fails. No prepare-final/read reservation is borrowed or recorded as performed.

Private cleanup pins retain actual allocations before fallible postchecks. Rejected
public aliases cannot redirect known cleanup; actual row/cap/resource corruption
remains UNKNOWN, retains original references and forbids unsafe acquisition/close.
First errors survive secondary close/handler failures. Returned
`ConfigurationCustodyPrefix` still has budget `NOT_ADMITTED`, tests `NOT_PERFORMED`
and false next-phase/export/save authority. There is no public command, workflow,
producer, collector, loader/uninstall, dependency transfer or encrypted delivery.

## Exact implementation review

Independent design disposition: **RECOMMEND_THIRD_DISTINCT_FILE_PARENT_B_DESIGN_ONLY**,
SHA-256 `caa6e8c791cfd51e5a92efc95a60440f9f30f24dabe29e5d27ad1570ebf9451b`.
The24-family independent assertion plan was frozen before implementation/author-test
inspection, SHA-256 `0abc9318693c50c3961089a9afcaac76e4f0f1812f87b032977bdaa77b9f91d9`.

Implementation verdict:
**APPROVE_EXACT_CONFIGURATION_CUSTODY_PARENT_IMPLEMENTATION_R1_SOURCE_AND_OFFLINE_ONLY**,
report SHA-256 `5cd23f5a594d0712da1e8aa6289d2fe52b7a708fe55c466e8cf50ae100691cbd`.
No implementation blocker was found. This is not formal GitHub PR approval,
complete-patch approval or native/provider/hosted acceptance. Final complete-patch
review, passive gates and commit/readback bindings are mapped separately in the issues.

| Binding | SHA-256 |
| --- | --- |
| Driver | `c8b9c390ac44f58b3a1d2d8fd148eb4133f656097cf8585978853abd7a0e35f2` |
| New author control file | `91d92ba1f00287228cd0142f724d497dab1379e295ee029f40b8be62313448b1` |
| Existing staging-parent fixture migration | `dbda85f11c4fc09d36a1d6b0f5acde108083e3e06950d33b1ecc6f75da32610f` |
| Unchanged approved custody leaf | `2ccc97810bd5b414619f28ea2a6f087b5edc22e9263217c55f5999eea7dd5dd8` |
| Independent31 controls | `334be46f514fb32479f8ecc171534308afbca91e57bc724a76382605724a8134` |

The implementation-only tree was `94f69b84863a767b0675614d22b188a185905b68`,
patch SHA-256 `950d772490942114cc49368942f8406a209263cb019ea701fe3eaa32cd0b6d40`.
The legacy fixture migration only appends False, supplies reserve=False and checks
the seventh original field. Its historical test methods were **not replayed** on
this changed source; new focused wrapper/intent controls exercise those boundaries.

## Actually executed offline controls

The new [author class](../../scripts/tests/hosted-cache-bootstrap-custody-parent-test.py)
has54 own methods, with **54 distinct individual passes across seven invocations**.
There was no whole54 aggregate. The original cleanup/policy9 aggregate remains
**FAILED:7 pass/2 fixture failures**. Both failed methods mistakenly called the
seed-files `_PosixDirectory(path)` constructor; that class actually accepts retained
pins and a private-mode argument. The intended path factory is `private_root(path)`.
Only those two fixture calls changed; assertions and implementation stayed unchanged.
Only the two unsuccessful controls were rerun, both passing. No successful test was
replayed for a green aggregate or to hide this original failure.

| Actual author invocation | Result | unittest / outer seconds |
| --- | --- | --- |
| Initial smoke |1/1 PASS|1.498 /2.174821|
| Identity/plan |12/12 PASS|1.736 /2.325102|
| Ancestry/first clocks |14/14 PASS|1.869 /2.474731|
| Original request |9/9 PASS|7.292 /7.896192|
| Labels/final return |9/9 PASS|5.218 /5.785094|
| Original cleanup/policy |**FAILED7/9;2 fixture failures**|0.652 /1.270678|
| Corrected unsuccessful methods only |2/2 PASS|0.121 /0.717858|

The smoke used tree `ab3df83970c3fcf20bb543a544508f556a7dca13`; first negative
batches used `d14d65ed6df107e7b9ddf77f388f8e2da4d1c693`; corrected-only execution
used `ca885769dd7f5dc12a55442a3fe4b3321147a91f`. Driver/legacy-fixture bytes stayed
identical. The smoke's method/setup remained unchanged; the later changed rejection
helper is not invoked by that smoke. These bindings do not qualify unrelated input
changes or constitute a whole-campaign gate.

All seven author invocations used actual UID65534, Python3.12.3 `-I -B -S`, external
timeout90+kill5/recorder105, with1425-file before/after source manifests and actual
same-process interpreter observations. Interpreter SHA-256:
`1643dacd9feaedc58f3cc581e4d22577dfe25c09b10282936186ccf0f2e61118`.
These are interpreter metadata/bytes, not whole-runtime or hosted admission.

Actual changed coordinator/private registries/third parent/window/file owner,
approved custody leaf and tiny ordinary-UID POSIX I/O execute. Upstream original
entry/recipient/initializer/stage/seed returns, original reads, admission, clocks
and host facts are explicit models. Old leaf/initializer/native-query/process,
network/GPG/provider/build operations are poisoned, not executed. Cleanup only
retires test-owned tiny fixtures; production UNKNOWN is never reclassified.

The independent31 methods passed in four disjoint invocations: smoke1,
identity11, request/clock12 and cleanup7 (outer1.371007/1.619161/5.680374/1.471226s).
Their controls import production modules only, not author tests, and cover the
frozen24-family matrix with explicit limits. Actual new parent/leaf/POSIX operations
execute over modeled upstream/native/clock/signal facts and counted test resources.
Full1424-file source/control content **and metadata**, original argv/environment,
actual UID/EUID65534 and same-process Python bindings were unchanged. No whole31
aggregate, failed test, skip or successful-control replay occurred.

One independent recorder preflight failed **before candidate import/launch** because
it used1425 instead of the implementation-only freeze's1424 files. Exact manifests
matched; a new recorder revision corrected only that count, without changing source
or controls. This is not a hidden candidate failure or test retry. The lead's first
passive original audit separately failed to parse unittest's two-line docstring
record; its corrected parser retained every count/hash/selected-method assertion.
Neither passive audit adds a candidate-test count; both original mistakes remain
recorded privately.

Independent original audit SHA-256:
`3dd3e1fda4da30797989a34f908cf85df01df8532c9e0664d589fe42d9dfae7c`.
Lead saved-original readback SHA-256:
`5ad8fcc6f7afe099e560b6f1438bdb188e4cd598231d9341bb24689a8c2f22ca`.
Private packet: `20260918-bootstrap-custody-parent-mad7x7qm`; raw path-bearing
logs/receipts/manifests stay outside Git. Exact author selections appear below.

## Next prerequisites and unchanged Release boundary

Producer launch/actual return, original successful configuration plus same-home
stop and complete enclosing native retirement remain unexecuted. The canonical
Tee lacks an independent total-byte cap; bounded original raw capture/collection
and overflow handling must be resolved before producer execution. Collection must
retain original start/receipt, four product/stop logs, report manifest and only
declared optional reports. No fabricated Test XML or uninstall for this no-loader
path is allowed. Export/freeze/save/probe/encrypted custody/seal integration remains;
there is no bootstrap workflow or production `cache.export_snapshot`/`cache.save_set`
caller. Configuration-only help is not ordinary ABI/simulator/transcript acceptance.

Complete paginated metadata **17:34:40UTC**:44 successful/hash-verified requests,
29 compared domains;78 open issues/seven dependency PRs/no campaign PR/no queried
active Actions; two RC Releases with **zero assets**. The ten changed domains are
the prior verified #437/#424 issue-map comments, related issue metadata/census and
cross-reference timeline data, not new owner authorization. Rules/advisory/main/
candidate/dependency PR list remain unchanged. Required checks are `complete-gate`,
`review`, `scan / osv-scan`, `osv-scanner`; required review count0 does not waive the
owner's formal different-account approval rule. Detailed dependency-PR reviews remain
separately dated; this is not another complete historical campaign audit.

Both ordinary HOLDs remain. Missing named routine custodian/exact public key/finite
14-day legitimately trusted-original-base policy/formal approval remains unresolved.
Native/provider/resolver/custody/scheduling/delivery qualification and normal checked,
formally reviewed main merge with preservation still precede development sample
Releases.5400 remains **UNADMITTED / UNMEASURED**; NativeFile900/Snapshot576MiB stay
unchanged, not a2GiB dependency-cohort solution.

No app build/download/held dispatch, PR/merge, Release, settings change or issue
closure occurred. Preview35070982169 was not rebuilt/redownloaded; older APK/MSI/
ARM64-DMG/DEB remain Actions artifacts expiring September30. #424 writer35066719641/1
already passed CLI9/diagnostics23 with six inspected originals, not repeated or
downgraded. #372's20 Kotlin tests remain uncompiled/unexecuted. OSV remains
**EXCEPTED_NOT_FIXED**, Kotlin2.4.10 affected, expiry2026-10-31; no scan/remediation/
extension. Phones and production/Maven/Store publication remain excluded. Protected
instructions/RC history/compatibility/unrelated work/proposals remain unchanged.
Historical206/234 repair-approved,207/234 resolved; audit/release **NOT_READY**.

## Exact author selections

These are the selected unit-test entries, run from the immutable copies above
through the recorded ordinary-UID observer/timeout wrapper, not a command to run
the whole suite again. Original argv, environment, results and hashes are retained
privately. Commands below omit only that external recorder/immutable-copy prefix.

### author-smoke-r1

```bash
python3 -I -B -S scripts/tests/hosted-cache-bootstrap-custody-parent-test.py \
  CustodyParentModels.test_third_parent_reserves_with_exact_originals_one_window_and_known_close
```

Original result SHA-256: `8e7b4b50bf2f34b693efe3dc5524d29c0de080627d543bcfadc6137a72f28a96`.

### author-identity-r1

```bash
python3 -I -B -S scripts/tests/hosted-cache-bootstrap-custody-parent-test.py \
  CustodyParentModels.test_existing_wrappers_keep_exact_signatures_and_reservation_false \
  CustodyParentModels.test_new_wrapper_fixes_reservation_intent_before_the_original_claim \
  CustodyParentModels.test_invalid_intents_fail_before_validation_claim_or_suppliers \
  CustodyParentModels.test_failed_shared_claim_cannot_retry_with_another_wrapper \
  CustodyParentModels.test_stage_only_intent_keeps_two_phase_return_and_cannot_upgrade \
  CustodyParentModels.test_completed_reservation_sequence_is_not_replayable \
  CustodyParentModels.test_copied_seed_prefix_is_refused_before_third_registration \
  CustodyParentModels.test_seed_leaf_is_not_the_seed_parent_return \
  CustodyParentModels.test_missing_seed_completion_cannot_start_custody \
  CustodyParentModels.test_live_coordinator_phase_alias_is_not_accepted \
  CustodyParentModels.test_live_coordinator_plan_cannot_discard_original_reservation_intent \
  CustodyParentModels.test_live_coordinator_cannot_publish_a_result_early
```

Original result SHA-256: `1f61869556c4786d1c80a2929363af30a68db0802354aab0fb2d447eb4905a78`.

### author-ancestry-clock-r1

```bash
python3 -I -B -S scripts/tests/hosted-cache-bootstrap-custody-parent-test.py \
  CustodyParentModels.test_equal_recipient_registry_alias_cannot_redirect_new_cleanup \
  CustodyParentModels.test_equal_initializer_registry_alias_cannot_redirect_new_cleanup \
  CustodyParentModels.test_equal_control_registry_alias_cannot_redirect_new_cleanup \
  CustodyParentModels.test_equal_sequence_registry_alias_cannot_redirect_new_cleanup \
  CustodyParentModels.test_completed_seed_private_frame_identity_is_rechecked \
  CustodyParentModels.test_typed_staged_argument_nested_identity_is_not_opaque \
  CustodyParentModels.test_nested_original_seed_bytes_are_pinned_before_suppliers \
  CustodyParentModels.test_nested_original_prefix_checked_scalar_type_is_pinned \
  CustodyParentModels.test_first_raw_must_follow_final_seed_parent_not_only_seed_leaf \
  CustodyParentModels.test_first_local_must_follow_final_seed_parent_not_only_seed_leaf \
  CustodyParentModels.test_original_cumulative_custody_fence_can_only_shorten_120 \
  CustodyParentModels.test_raw_120_equality_fails_without_borrowing_final_or_read_reserve \
  CustodyParentModels.test_local_120_equality_is_not_a_new_readback_window \
  CustodyParentModels.test_valid_raw_is_retained_when_later_local_observation_rolls_back
```

Original result SHA-256: `e1bf31baa6d5403167ac0c7e589db5eff6562febe36dd0be9ee95f4cb47ace92`.

### author-request-r1

```bash
python3 -I -B -S scripts/tests/hosted-cache-bootstrap-custody-parent-test.py \
  CustodyParentModels.test_staging_leaf_cannot_substitute_for_custody_request_return \
  CustodyParentModels.test_duck_typed_staging_raw_alias_is_not_a_reservation \
  CustodyParentModels.test_changed_custody_leaf_scope_is_refused_before_parent_copies \
  CustodyParentModels.test_changed_request_scope_is_not_accepted_with_a_matching_return_hash \
  CustodyParentModels.test_actual_request_mutation_after_parent_copy_is_not_masked_by_the_copy \
  CustodyParentModels.test_byte_identical_original_request_replacement_is_refused \
  CustodyParentModels.test_byte_identical_reservation_in_a_replaced_directory_is_refused \
  CustodyParentModels.test_retained_directory_contamination_is_not_reservation_success \
  CustodyParentModels.test_mutating_the_captured_return_record_cannot_rebind_original_request
```

Original result SHA-256: `6e565babd5757b5308d18aef5ebe7a7b336b6eb4c463a6fbf862f73232762a2f`.

### author-label-return-r1

```bash
python3 -I -B -S scripts/tests/hosted-cache-bootstrap-custody-parent-test.py \
  CustodyParentModels.test_only_seven_new_labels_are_phase_specific_in_acquire_and_roster \
  CustodyParentModels.test_arbitrary_custody_resource_label_refuses_before_factory \
  CustodyParentModels.test_roster_cannot_admit_an_unknown_label_even_when_private_row_matches \
  CustodyParentModels.test_raw_rollback_is_not_hidden_by_later_recovery \
  CustodyParentModels.test_late_actual_leaf_return_cannot_use_its_earlier_checked_clock \
  CustodyParentModels.test_falsey_final_serialization_error_is_not_a_successful_closed_return \
  CustodyParentModels.test_late_final_serialization_cannot_borrow_prepare_final_or_read \
  CustodyParentModels.test_final_raw_highwater_survives_a_late_local_sample_after_serialization \
  CustodyParentModels.test_handler_restoration_remains_inside_the_same_custody_window
```

Original result SHA-256: `99839c7f3ee1cd1dde6cec4a26a92193626ffdb29fbd2b002efe6127f9deb97e`.

### author-cleanup-policy-r1

```bash
python3 -I -B -S scripts/tests/hosted-cache-bootstrap-custody-parent-test.py \
  CustodyParentModels.test_public_owner_alias_cannot_redirect_actual_known_cleanup \
  CustodyParentModels.test_actual_allocation_is_retained_before_fallible_postcheck \
  CustodyParentModels.test_forged_public_flags_cannot_attest_actual_close \
  CustodyParentModels.test_removed_resource_row_is_retained_not_reclassified_as_closed \
  CustodyParentModels.test_equal_replacement_row_cannot_supply_original_resource_registration \
  CustodyParentModels.test_foreign_resource_row_never_becomes_new_close_authority \
  CustodyParentModels.test_unknown_close_keeps_first_failure_and_forbids_new_acquisition \
  CustodyParentModels.test_falsey_first_failure_survives_secondary_close_and_handler_errors \
  CustodyParentModels.test_no_cli_workflow_export_save_or_budget_authority_is_added
```

Original result SHA-256: `b0620d50284c7f2de92a93e29e260f6c99a9ab747c4bff879abd3678b5eb245c`.

### author-fixture-r2

```bash
python3 -I -B -S scripts/tests/hosted-cache-bootstrap-custody-parent-test.py \
  CustodyParentModels.test_actual_allocation_is_retained_before_fallible_postcheck \
  CustodyParentModels.test_foreign_resource_row_never_becomes_new_close_authority
```

Original result SHA-256: `335d42dc45c3c3c784c99725e646f318f2fa7b45c95d8ff6f8fb9d7b3e898a49`.
