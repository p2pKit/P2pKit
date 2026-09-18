# Dormant bootstrap staging/seed parents — 18 September 2026

**Source/offline scope only; apps are not in repository Releases.** This follows
the [separate staging/empty-seed leaf](hosted-bootstrap-staging-2026-09-18.md)
at `26e29dfecf818b33613a3e7b9cb4532dafc5e5ca`. The containing commit and final
complete-patch review are mapped after review and remote preservation to
[#437](https://github.com/p2pKit/P2pKit/issues/437), with the shared prerequisite
recorded in [#424](https://github.com/p2pKit/P2pKit/issues/424).

## Same-call source boundary

The internal `stage_after_entry(transition)` selects recipient validation,
canonical initialization and the two new file-only staging/seed parents.
The shared once-claim fixes exact initialize/stage booleans before suppliers,
including failed attempts. Existing recipient-only and initializer-only wrappers
keep stage false; returned JSON or replay cannot retrofit their intent.

Actual `_initialize_claimed` return precedes a separate one-use staging claim.
The initializer's COMPLETE state/result and original closed graph stay unchanged
on later success or failure. Neither old failure handler encloses the new phases,
and no old Owner/Fence/resource method is called to continue them. The new exact
historical reader uses new handles and the new phase's live bounds. Typed pins
include initializer inputs, installed-toolchain originals, return identities,
paths and original registry/control bindings. These finite checks are not a
sandbox against arbitrary Python-code replacement.

Stage has **soft/hard120**; seed has **soft90/hard120**. Both shorten against
original proposed cumulative/job fences and independent LOCAL ceilings.
Fresh query work/final deadlines and the supplier's actual finalizer return fit
SOFT. All new file acquisition, including `final=True`, spends SOFT; HARD's
remaining tail covers already-owned completion/close, not another acquisition.
Equality is expired. No existing deadline or proposed allowance is enlarged.

Complete original preparation/adoption/entry/recipient/initializer bytes are
reread around readmission and retention; there is no second service HTTP call.
Leaf originals and pending records stay outside canonical state/H, its evidence/
cancellation directories and restore-home S. The unchanged leaf creates an absent
staging container and checks an all-artifact ABSENT, zero-dependency seed.
Metadata I/O occurs; this is not a dependency copy, provider result or population.

The actual leaf-return and later parent-return RAW/LOCAL high-waters remain
separate. Seed starts after the actual stage-parent return in both domains,
not its earlier leaf or pending file. A valid final RAW observation remains
retained when a subsequent LOCAL observation fails. Final results follow resource
close, handler restoration and final checks, but remain `NOT_ADMITTED`,
`NOT_PERFORMED` and false successor/export/save authority.

There is no public CLI/workflow caller, producer, export/save/provider operation
or encrypted failure-delivery implementation. Failure keeps original references
and first errors, including falsey exceptions. Custody may honestly remain
UNAVAILABLE/INCOMPLETE; no new failure writer/owner, key, retry or allowance is
invented. Known file-resource close is not native process/job retirement.

## Review findings and two distinct resource ledgers

Independent static review found missing continued registry-alias checks (F1)
and cleanup/live dispatch through changed actual fence/resource rows (F2).
R3 pins the original publications/private frames and adds an exact staging-only
`_StagingFileOwner(Owner)`. Rejected public aliases cannot erase known cleanup;
actual owner/fence/roster corruption is retained UNKNOWN, not dispatched.
The original `Owner`, including `Owner.bind`, and approved staging leaf are
byte-identical. No executable F1/F2 preimage is claimed.

The unchanged desired-state F3 author oracle then genuinely failed on R4:
caller-written attempted/closed flags could attest a close that never occurred.
R5 makes private flags authoritative; only actual close attempts/returns advance
them. The R6 F4 oracle separately failed: a public allowed-label False/False row,
never returned by source acquisition, was promoted into close authority.

R7 keeps two ledgers. Only an actual unique factory return creates an authorized
pin, before any fallible post-return check, in the original bound public list.
A duplicate return creates no second row or close obligation. Discovered or
substituted rows enter a separate sticky foreign ledger: retained UNKNOWN,
never closed or promoted. Removing a row or restoring public flags cannot clear
that private uncertainty. Success requires private UNKNOWN false, no foreign
rows and every authorized resource actually closed. The earlier design-only
approval did not itself approve this implementation.

## Exact source and executed author controls

R7 two-file source/test freeze: tree
`3d69748966be5870fa04dccc164bccde48a1bae7`; patch SHA-256
`2e14b0c8d519b0da121107f63c7cba9240e23e9b38993c6064cf567ca861c127`.

| File under `scripts/` | SHA-256 |
| --- | --- |
| `run-hosted-cache-bootstrap.py` | `c34e33271e279049c96ddd4ce2d53a70c77037f10570805013aecc65a4ab153a` |
| `tests/hosted-cache-bootstrap-staging-parent-test.py` | `cf753320038436f0020812d9acba0aa77d915f9006ddf422922a1c3712dd4915` |

All **40 own methods passed exactly once across 17 disjoint invocations** on R7,
not one whole-file aggregate and not inherited historical methods. Each used
`python3 -I -B -S`, actual UID65534, root-owned immutable-to-test executable source,
external90 seconds plus5-second kill and recorder105. The original receipts do
not retain an exact per-invocation Python version; a previous host observation
is not substituted for that missing binding.
All1,417 executable/source bindings, complete rosters and absence of extra source
files matched before/after. Longest recorder duration was68.587937 seconds.
No deadline or assertion was relaxed.

The command form below elides only the original immutable source-copy prefix.
Each table row supplies the exact selected arguments for one invocation:

```text
timeout --kill-after=5s 90s runuser -u nobody -- python3 -I -B -S <freeze>/scripts/tests/hosted-cache-bootstrap-staging-parent-test.py <selectors> -v
```

| Exact selectors | Result / unittest seconds |
| --- | --- |
| `ParentModels.test_unregistered_public_resource_row_is_retained_without_close_authority` `ParentModels.test_actual_acquisition_is_registered_before_a_fallible_post_return_clock` `ParentModels.test_duplicate_factory_return_keeps_only_its_existing_close_obligation` | 3/3 PASS /20.803 |
| `ParentModels.test_actual_new_parents_and_leaves_close_distinct_owners_with_complete_original_reads` | 1/1 PASS /67.810 |
| `ParentModels.test_new_reader_kind_is_exact_and_has_no_public_command` `ParentModels.test_recipient_only_original_shared_claim_keeps_both_intents_false` `ParentModels.test_initialize_only_original_shared_claim_keeps_stage_intent_false` `ParentModels.test_staging_original_shared_claim_selects_initialization_before_any_owner` | 4/4 PASS /4.611 |
| `ParentModels.test_initializer_only_intent_cannot_be_retrofitted_from_its_exact_return` `ParentModels.test_copied_initializer_result_is_not_a_handoff_and_consumes_the_attempt` `ParentModels.test_first_stage_raw_precedes_actual_initializer_return_is_refused` `ParentModels.test_first_stage_local_precedes_actual_initializer_return_is_refused` `ParentModels.test_complete_initializer_inputs_are_typed_pins_not_an_opaque_object` | 5/5 PASS /12.070 |
| `ParentModels.test_failed_query_consumes_sequence_without_second_supplier_or_service_call` `ParentModels.test_stage_query_finalizer_return_at_soft_equality_is_not_success` `ParentModels.test_original_initialization_bytes_are_reread_after_query` `ParentModels.test_original_service_bytes_are_reread_after_query` `ParentModels.test_existing_stage_container_is_never_adopted` | 5/5 PASS /52.222 |
| `ParentModels.test_public_owner_alias_rejection_still_closes_original_owner` `ParentModels.test_public_registry_alias_rejection_does_not_redirect_cleanup` `ParentModels.test_equal_recipient_registry_alias_is_not_the_original` `ParentModels.test_equal_initializer_registry_alias_is_not_the_original` `ParentModels.test_equal_parent_control_registry_alias_is_not_the_original` | 5/5 PASS /33.106 |
| `ParentModels.test_resource_close_cannot_redirect_the_following_cleanup_fence` `ParentModels.test_resource_close_cannot_redirect_a_still_pending_resource_row` `ParentModels.test_live_owner_end_checks_original_fence_before_dispatch` `ParentModels.test_public_attempted_closed_flags_cannot_attest_an_actual_unclosed_resource` `ParentModels.test_corrupted_actual_error_container_cannot_erase_first_failure` | 5/5 PASS /35.561 |
| `ParentModels.test_mutated_actual_owner_fence_is_quarantined_not_invoked_on_close` `ParentModels.test_removed_resource_row_is_retained_as_unknown_not_a_clean_close` `ParentModels.test_falsey_first_error_survives_handler_restore_failure` | 3/3 PASS /20.397 |
| `ParentModels.test_completed_sequence_cannot_be_replayed` | 1/1 PASS /65.579 |
| `ParentModels.test_closed_old_owners_and_windows_are_never_called_again` | 1/1 PASS /67.122 |
| `ParentModels.test_final_seed_raw_return_cannot_replace_the_original_entry_registry` | 1/1 PASS /66.553 |
| `ParentModels.test_public_alias_after_large_leaf_roster_still_closes_known_originals` | 1/1 PASS /29.378 |
| `ParentModels.test_seed_query_finalizer_must_fit_soft90_not_hard120` | 1/1 PASS /36.364 |
| `ParentModels.test_seed_new_file_at_soft90_refuses_even_with_final_true` | 1/1 PASS /36.361 |
| `ParentModels.test_seed_first_follows_parent_return_not_earlier_stage_leaf` | 1/1 PASS /30.283 |
| `ParentModels.test_final_seed_raw_return_at_local_hard_retains_raw_and_refuses_success` | 1/1 PASS /64.501 |
| `ParentModels.test_final_serialization_failure_does_not_promote_closed_resources` | 1/1 PASS /30.105 |

These execute the actual new capture, parents, file Owner, historical-original
readers and unchanged leaves over tiny POSIX files. Recipient/initializer
predecessors are **modeled typed closed graphs**; canonical `initialize()` is
not executed, even in process. The three shared-intent probes stop before
recipient Owner construction. Host/service/query/clocks are models; tiny query
files really open/write/close, but no native Git runs. Nonfunctional JDK fixtures
are metadata-inspected, not executed. The inherited author signal fixture models
getsignal/signal; its restoration-failure control is not real host signal setup.

No full recipient→canonical-initializer→staging execution, generated native argv,
GPG, network, dependency copy, export/save, provider or build acceptance follows.

### Earlier originals retained separately

| Freeze / selection | Actual result | Cause or limited scope |
| --- | --- | --- |
| R1 two-method smoke | 1PASS/1ERROR | Root-owned code export incorrectly used as ordinary-UID public-source data; SEED_PUBLIC_SOURCE_MODE. |
| R2 one-method fixture smoke | 0PASS/1ERROR | Tiny XML lacked mandatory schemaLocation; XML_ATTRIBUTES. A later handoff prose count was corrected from the original argv/log, not by rerunning it. |
| R3 two-method smoke | 2/2 PASS | Older source only. |
| R4 F3 desired-state preimage | 0PASS/1FAIL | Private UNKNOWN remained false after forged public close flags; no setup error. |
| R5 four owner controls | 4/4 PASS | Older source only. |
| R6 F4 desired-state preimage | 0PASS/1FAIL | Private UNKNOWN remained false after an unregistered public row; no setup error. |

R4/R5 entire test bytes match; R6/R7 entire test bytes match. All existing R5
test/helper ASTs remain unchanged through R7; three methods were added in R6.
Fixture ownership/parser checks and existing desired-state assertions were not
weakened. No independent F4 preimage ran: an earlier review-tool interruption
occurred before any test/session started. It is not another failed or passed run.

The lead and reviewer separately audited all23 original packets and seven
source freezes without replaying controls. Lead audit SHA-256:
`1dd757713295208d085a322a75b15e79564bafce083866d7e41dbb7742dce2b8`.
Independent audit:
`919ec7b44f7dd921d68ade4be55a7b842bdbf8005e964af07103d4e0cef6ea33`.
Original audit-only count and LF-representation mismatches remain retained with
their diagnoses; neither is a candidate test failure or source repair.

## Independent implementation review

**APPROVE_EXACT_STAGING_PARENT_R7_SOURCE_AND_OFFLINE_ONLY**, report SHA-256:
`2e00f7381e22068dc7c38b00035373d364a472f929bd39d7de4a71f846d062e6`.
All four findings above are resolved in this exact two-file scope. The final
complete-document-patch verdict is separate and mapped with the containing commit.
Agent review is not formal different-account GitHub PR approval.

The reviewer froze its own controls before reading the new author assertions.
**14/14 passed in two invocations**, first one positive, then13 negatives only
after that pass. Unittest3.240/8.315 seconds; recorders3.778890/8.847564 seconds;
both exit0, no timeout. Actual UID/GID65534, cleared groups/capabilities,
no-new-privileges, isolated Python and external90/kill5/recorder105.
These extra capability restrictions are not inferred for the author commands.
All1,417 source files/modes/roster and frozen control bytes remained unchanged.

Independent controls cover the real new parents/leaves, nonauthority, exact
intents/copied returns, all five registry aliases,70-resource cleanup without
error64 saturation, actual fence/pending-row redirection, late close-flag forgery,
foreign-ledger stickiness, post-return acquisition failure, duplicate single-close,
seed query SOFT equality, separate RAW/LOCAL parent-return floors, final LOCAL
expiry after valid RAW, and typed initializer/toolchain/path mutation.
They use modeled initializer capture/history/host/query/clocks; the actual capture
and historical readers are separately covered by audited author controls.
Independent handler restoration is real. Neither set executes canonical init
or establishes the complete native/hosted chain.

Control SHA-256:
`174a538e372129033dee854c661f549e3d182c1172f2958080cce609df0aa29a`.
Positive execution JSON:
`08017a24182057a489fef07bc1ebbfdf4b46a4c07f627fb64c50547b20bf3e0b`;
negative execution JSON:
`0a05f90c6d0bdf51ed0e6ef7b3faa81c3f1b5f96780de6899b0d4b9bddf7ad68`.

The separate shared-path static assessment checked every production tuple writer,
width and consumer, generic suffix-identity binding and exact initializer return.
It found no residual source issue requiring an old-suite replay for this dormant
increment; it does not call older results current R7 full-chain execution.
Assessment SHA-256:
`dd47891342facdcdedf8e387d79e4915e504cc8cd590220ec6e315f6cd7ca093`.

## Remaining delivery prerequisites

Complete paginated relevant metadata at **15:14:46 UTC** found78 open issues,
seven unchanged dependency PRs, no campaign PR, no queried queued/in-progress/
waiting/requested/pending Actions, and zero assets on the two existing Releases.
Complete #437/#424/#457/#143/#144 conversations/timelines, source refs, effective
rules and advisory had no new decision delta from14:19; only repository-reported
size differed. Detailed dependency-PR reviews remain separately dated.
Required contexts remain `complete-gate`, `review`, `scan / osv-scan`,
`osv-scanner`; main remains `3bc76f956f8f47447b51a62474fc878b9c43173c`.
A repository approving-review count of0 does not waive formal nonauthor approval.

Next is separate configuration-custody preparation, original configuration
producer/same-home stop/known enclosing native retirement, positive streamed
export/freeze/save-set/provider save/probe and encrypted custody/sealing.
No production caller invokes `cache.export_snapshot` or `cache.save_set`.
Configuration-only help cannot satisfy ordinary ABI/simulator/transcript tests.

Both ordinary HOLDs and the missing named routine custodian, exact public key,
finite14-day legitimately trusted-original-base policy and formal approval
remain. Candidate source cannot authorize its own recipient. Proposed5400 stays
UNADMITTED/UNMEASURED; Windows NativeFile900 and Snapshot576MiB remain, not a
2GiB-cohort solution. Genuine native/provider/resolver/custody/scheduling/delivery
qualification, required checks, formal PR review and normal main merge and
preservation still precede development sample Releases.

No build/download, held dispatch, PR/merge, Release, settings change or closure
occurred for this source increment. Preview35070982169 and #424 writer35066719641/1
were not rebuilt/redownloaded; CLI9/diagnostics23 and six inspected original
exports retain their accepted original scope. #372's20 Kotlin tests remain
uncompiled/unexecuted. OSV remains EXCEPTED_NOT_FIXED, Kotlin2.4.10 affected,
expiry2026-10-31; no scan/remediation/extension. Physical phones and production/
Maven/Store publication remain outside this work.

Protected instructions, immutable RC history, compatibility restrictions and
unrelated branches/proposals remain unchanged. The23 historical worktrees,
including20 dirty patches, are preserved rather than reset/cleaned; containing
commit preservation is separately read back. Private originals remain outside
Git. Historical206/234 repair-approved,207/234 resolved; audit/release **NOT_READY**.
