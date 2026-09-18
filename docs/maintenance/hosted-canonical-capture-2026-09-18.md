# Canonical retained-stream bounds — 18 September 2026

Refs [#437](https://github.com/p2pKit/P2pKit/issues/437) and shared
[#424](https://github.com/p2pKit/P2pKit/issues/424). **Source/offline repair only;
apps are not in Releases.** Base `5b06c1f2750f89f18a2678851f86a302724d1e94`, tree
`2a2fd4bd0cd27f5288bdafc0d3984128e7963719`, already preserves the
[configuration-custody parent](hosted-bootstrap-configuration-custody-parent-2026-09-18.md).
Its accepted work is not rerun or replaced here.

## Root cause and correction

The canonical [`Tee`](../../scripts/run-audit-command.py) previously requested
65536-byte chunks without limiting cumulative retained bytes. It also ignored
both evidence and live write acknowledgements. The original product wait checked
cancellation but not its already-recorded capture errors. These are reproduced
source defects, not claims about a historical native or hosted incident. An outer
controller's bounded stdout cannot bound these separate inner files.

Each Tee now has a source-owned **64MiB ceiling**. A keyword-only `max_bytes`
accepts only exact integers0..64MiB, solely to shorten that limit; bad values
refuse before event/output/thread acquisition and leave the caller's source alone.
The existing five positional parameters, including deferred start, remain intact.
The original allowance is captured for the worker and consumed by source position,
not mutable counters, successful writes or a later constant lookup.

Reads always request a positive65536-byte chunk, including at zero remaining.
Exact bytes and returned length are validated before EOF truth testing. Malformed
or oversized supplier returns fail without slicing/retrying the broken supplier.
Valid overflow latches one finite failure **before** fallible sinks, writes/live-
delivers only the original permitted prefix, and drains later bounded chunks
without accumulating their tail. Real EOF at the exact cap is not overflow.

Both nonempty writes require an exact integer acknowledgement equal to the offered
length. Short/invalid writes, OSError and closed-stream ValueError disable only
that sink; the other sink and drain continue within the same original allowance.
No replay, truncation/deletion of previously retained bytes, synthetic marker or
replacement success is introduced. Evidence is flushed before live delivery.

The product-only callback calls the original cancellation supplier first, then
examines the original live error list. A visible capture error fails even when the
child polls0 and enters the existing pre-stop drain/stop/finalization path. **Stop
keeps the cancellation-only callback**: a failed product cannot prevent the exact
same-home/same-wrapper stop. Late capture/close errors still make final125. Errors
not yet observable at the pre-stop branch are not claimed as earlier observations.

Register-before-start, pending-Tee carriage after uncertain eager start, worker-
only entered-stream close, unstarted once-close, and the original **3-second
UNKNOWN** finish remain. Test cleanup does not erase production uncertainty.
Receipt schema, CLI/environment options, Gradle flags, ownership domains, workflow
HOLDs and all configured deadlines are unchanged.

The ceiling bounds only four product/stop logs, at most256MiB per canonical
invocation. It is **not** a whole-custody/session/nested-invocation cap or the
Windows576MiB Snapshot solution for2GiB dependencies. The hosted lock writer's
stricter16MiB streams plus64/8MiB shared budgets and the Windows directory
controller's separate32MiB combined polling bound remain distinct and unchanged.
No historical writer/native campaign is replayed or qualified by this repair.

## Source and independent review

Implementation-only freeze: tree `d17e960ae676b884bf12a4e82fc1d57d669760c3`,
patch SHA-256 `6cd594042021463def4f6d7092be22ac597e440ce1b46875dcb1556ebf6cc78e`.

| Source | SHA-256 |
| --- | --- |
| Canonical executor | `7ef941538090e493ee80356c519cafcc7c8a42415628868db63d03ce4ec8553b` |
| Additive author test file | `fd75aef1adf88a170b4bbcc0dfd45877b8f67f258160fc3e2e27eb0f6c08589e` |

Independent design verdict was
**RECOMMEND_CANONICAL_STREAM_CAP_AND_PRODUCT_POLLING_WITH_REFINEMENTS_DESIGN_ONLY**,
report SHA-256 `6a1a7323d110791720543a4a2525fab17f7d8a47cc245f3878e1c78d52181bf4`.
Its24 desired-control families were frozen before author controls/implementation,
SHA-256 `fdd9755e6198bb8354a798fdb5552fdba825bf7c79a951ac2f609b9872c36e5d`.
These are not24 executed tests or implementation approval.

Independent implementation verdict:
**APPROVE_EXACT_CANONICAL_STREAM_CAP_IMPLEMENTATION_R1_SOURCE_AND_OFFLINE_ONLY**,
report SHA-256
`72178cd2ab0374ef5cec2b2150953a695de72906ddfb5cbe2b6d152622d4e463`.
The reviewer independently reconstructed the full1426-file tree and two-file
implementation delta before running controls. This verdict does not include
formal GitHub review or native/runtime acceptance; the final complete-patch
review and preservation are mapped against the containing commit in the issues.

The reviewer authored controls before reading the author-test source, from the
previously frozen24-family plan. **33 distinct methods passed once across four
disjoint invocations**, with zero failures/errors/skips and no whole33 aggregate:

| Independent original invocation | Methods | Result | Runtime / outer seconds |
| --- | ---: | --- | --- |
| Byte contract |13|PASS|0.186725 /0.429255|
| Lifecycle |7|PASS|3.170338 /3.407530|
| Modeled execute |11|PASS|0.189869 /0.451195|
| Structure / private reviewed-pin mutations |2|PASS|3.095156 /3.343605|

Original runtime/outer values, complete method names and artifact hashes remain
in the independent packet; timing is measured offline control duration, not
product/provider scheduling. Actual UID/EUID65534, isolated Python3.12.3,
full source/control/interpreter content and metadata stayed unchanged. The
external40-second limit,512MiB address-space/25CPU-second limits and poisoned
native/process/network routes admitted only the declared tiny controls. Only the
original main thread remained after each selection. The deliberately blocked
real worker returned UNKNOWN after3.000263363 seconds; fixture release/join did
not erase that original uncertainty.

Independent controls SHA-256:
`d9d60baa03b6163615dda520180f00d017d79742724ce703f76a014b065e7822`;
originals audit:
`35f9c016149dff2c88227d8c97091b496e8231e5473f4485eba21f57e04b1df0`.
The lead separately read back all original results, logs, launches, manifests
and observations without replaying the controls; readback SHA-256
`1ed5d746ea917f6876c8f7ea4b830084139796f77d2b98ffabc9ea88d801d70c`.

The unchanged original composition gate actually rejected this changed canonical
source, exit1, before any expectation update. This is expected review admission,
not a passing gate. The old independently frozen canonical expectation was
`70216745a371d41101a0c4f6d27ca1d73b5f3d82c3e7ea4fc70009fb44f51cc5`.
Only after exact independent implementation review, the reviewer supplied
replacement `c970c91a7eaf6998548ca0eaae3892313c0dbf96fbca51e75e813f9be069c261`.
The gate explicitly changes only that expectation; the other six expectations
and stable AST/roster/shadowing logic remain unchanged. It was not auto-refreshed.

On composition freeze tree `d974e254b441b8fbec17885d4c076c0128ca3bfd`, one
changed-input positive plus four new AST-only mutation methods actually passed
**5/5 in one invocation**,3.979 seconds unittest/4.127568 seconds outer. The four
methods contain13 rejection variants: cap/read/prefix accounting, both write
acknowledgements, product-vs-stop/cancellation order and late shadowing. These are
source tripwires, not supplier execution; the historical whole suite was not
replayed. The actual UID65534 isolated interpreter and1426 source bindings and
metadata were unchanged under external30+kill5/recorder45 limits. Result SHA-256:
`12525b4245a47bb9bc2e89c23f41b45f665191d81abf921c7f8a52e207288c03`.

Exact selected source-only command, through the retained guarded observer:

```bash
python3 -I -B -S scripts/tests/check-hosted-test-composition-test.py \
  CompositionPolicy.test_reviewed_programs_match \
  CompositionPolicy.test_canonical_capture_cap_read_contract_and_prefix_accounting_are_required \
  CompositionPolicy.test_canonical_capture_both_write_acknowledgements_remain_required \
  CompositionPolicy.test_canonical_capture_product_error_polling_keeps_stop_separate \
  CompositionPolicy.test_canonical_capture_late_shadowing_cannot_replace_the_bounded_worker -v
```

Final Markdown/layout/release-metadata/whitespace outcomes and complete-patch
review are mapped separately in the linked issues; they are not product tests.

## Actually executed author controls

The additive `CapturePolicyTests(unittest.TestCase)` in
[`run-audit-command-test.py`](../../scripts/tests/run-audit-command-test.py)
has31 own methods. **31 distinct postimage passes across five disjoint process
invocations**, no whole31 aggregate. The original preimage aggregate remains
**FAILED:0 pass/4 intended failures**, with no setup errors or skips. Its four
method bodies are unchanged in the postimage. Before their postimage execution,
the modeled execute helper gained explicit optional fault variants and unique
fixture roots; no original assertion was removed or weakened.

| Actual invocation | Methods / result | unittest / outer seconds |
| --- | --- | --- |
| Preimage four, tree `4c76b25d0773ddcdc8acd026799cfcd712e43ffc` | **0/4;4 intended failures** |0.120 /0.466410|
| Repaired four |4/4 PASS|0.016 /0.315001|
| Byte contract |8/8 PASS|0.022 /0.315124|
| Sinks/retirement |6/6 PASS|0.033 /0.365936|
| Lifecycle |5/5 PASS|3.009 /3.380345|
| Modeled execute |8/8 PASS|0.376 /0.717598|

This is35 method attempts across six invocations, not35 distinct tests. Every
postimage selection used the same implementation-only freeze and full1426-file
before/after content and metadata manifests. Actual UID/EUID65534, Python3.12.3
`-I -B -S`, original argv/launch environment, and same-process interpreter metadata/
SHA-256 observations were retained. Interpreter SHA-256:
`1643dacd9feaedc58f3cc581e4d22577dfe25c09b10282936186ccf0f2e61118`.
These are not whole-runtime/native/hosted admission. Bounds were external90+kill5
seconds with recorder105; only the lifecycle test deliberately waited3 seconds.

Actual tiny Tee files/threads and canonical execute/lock/receipt code run; source/
scope/process/report/signal suppliers in execute are explicit models. The64MiB+1
default-limit control uses generated chunks and constant-memory counted sinks,
not a64MiB file/download. Malformed/short writes and delayed/failing closes are
modeled; no Java, native child, Git subprocess, GPG, provider or network runs.
All test-owned threads retire. Real native factories/process/network routes are
poisoned by the isolated observer.

**Do not directly run that test file under this offline-only allowance.** Its
ordinary main selects native fixture suites. The actual recorded wrapper imports
it under a non-main name and explicitly constructs only the selected new methods.
Its additive normal registration preserves every existing policy/current-host
suite; none of those historical/native suites was run in this increment. The exact
selected methods are listed below; the complete wrapper argv, environment and
unabridged originals stay private in packet `20260918-canonical-capture-fw276yva`.
Passive author-original audit SHA-256:
`7d61e919351b748b90099175df4c6bb0109e9698c88f82e25319fe3248f861ab`.
That audit adds zero candidate tests.

## Still unaccepted

The separate original-clock defect remains: canonical `wait_process` creates a
relative timeout after spawn/stream setup and accepts a polled exit before checking
time. This cap repair does not enforce original shared-clock/job/phase/capture
fences or qualify the proposed5400 seconds. Producer launch/actual successful
configuration, same-home stop and complete enclosing native retirement, original
start/receipt/four-log/report collection, export/freeze/save/probe and encrypted
custody/seal remain unfinished. No bootstrap workflow or production caller of
`cache.export_snapshot`/`cache.save_set` exists. Help is not ordinary ABI,
simulator, transcript or complete-dependency acceptance.

Complete paginated metadata18:20:13UTC retained45 verified requests over29 domains:
78 open issues, seven unchanged dependency proposals, no campaign PR, zero queried
active Actions and two RC Releases with zero assets. Changes since17:34 are the
known parent push/maps and their repository/cross-reference metadata, not new
owner authorization. Required `complete-gate`, `review`, `scan / osv-scan` and
`osv-scanner` remain. Configured review count0 does not waive formal different-
account PR approval. Proposal-head/base/title/body/update identities are unchanged;
their detailed reviews remain separately dated.

Both ordinary HOLDs remain. The missing routine custodian, exact public key,
finite14-day trusted-original-base recipient policy and formal approval still
block activation. Native/provider/resolver/custody/scheduling/delivery qualification,
normal checked/formally reviewed main merge and preservation precede development
sample Releases.5400 remains **UNADMITTED/UNMEASURED**; NativeFile900 and
Snapshot576MiB are unchanged. No build/download/held dispatch, PR/merge, Release,
settings change or issue closure occurred.

Preview35070982169 already passed APK/MSI/ARM64-DMG/DEB and was not rebuilt or
redownloaded; its Actions artifacts expire September30 and are not Releases.
#424's writer35066719641/1 CLI9/diagnostics23 and six original exports retain their
accepted scope. #372's20 Kotlin tests stay uncompiled/unexecuted. OSV/advisory policy
was refreshed unchanged: **EXCEPTED_NOT_FIXED**, affected Kotlin2.4.10, expiry
2026-10-31, no remediation or exception extension. Physical phones and production/
Maven/Store publication stay excluded. Protected instructions, RC history,
compatibility limits and unrelated work/proposals are unchanged. Historical
206/234 repair-approved,207/234 resolved; audit/release **NOT_READY**.

## Exact author selections

### author-repaired-four-r1

The repaired-four selection also ran once against the unchanged preimage and failed as recorded above.

```text
CapturePolicyTests.test_default_capture_limit_enforced_without_a_caller_option
CapturePolicyTests.test_evidence_short_write_fails_but_live_and_drain_continue
CapturePolicyTests.test_live_short_write_fails_but_evidence_and_drain_continue
CapturePolicyTests.test_product_capture_failure_enters_drain_before_a_second_wait_poll
```

### author-byte-contract-r1

```text
CapturePolicyTests.test_cap_validation_precedes_allocation_and_caller_source_acquisition
CapturePolicyTests.test_cap_is_keyword_only_and_maximum_empty_stream_is_admitted
CapturePolicyTests.test_zero_below_and_exact_limit_eof_preserve_original_binary_bytes
CapturePolicyTests.test_first_excess_in_same_or_next_block_retains_only_prefix_and_drains
CapturePolicyTests.test_original_allowance_survives_mutable_aliases_and_supplier_constant_changes
CapturePolicyTests.test_each_tee_has_its_own_prefix_allowance
CapturePolicyTests.test_observed_overflow_precedes_all_sinks_and_no_tail_is_written
CapturePolicyTests.test_falsey_nonbytes_mutable_subclass_and_oversized_reads_fail_without_retry
```

### author-sink-retirement-r1

```text
CapturePolicyTests.test_invalid_evidence_ack_disables_only_evidence_and_cannot_refill_budget
CapturePolicyTests.test_evidence_write_and_flush_exceptions_disable_only_that_sink
CapturePolicyTests.test_invalid_live_ack_disables_only_live_and_cannot_refill_budget
CapturePolicyTests.test_live_write_and_flush_exceptions_leave_bounded_evidence_and_drain
CapturePolicyTests.test_read_failure_and_worker_interruption_preserve_prefix_and_first_error
CapturePolicyTests.test_first_errors_survive_both_sink_and_once_only_retirement_failures
```

### author-lifecycle-r1

```text
CapturePolicyTests.test_no_eof_keeps_three_second_unknown_without_owner_race_close_or_second_budget
CapturePolicyTests.test_valid_short_cap_allocation_failure_does_not_claim_the_source
CapturePolicyTests.test_short_cap_thread_allocation_failure_closes_only_the_new_output
CapturePolicyTests.test_deferred_short_cap_retirement_is_once_only_without_source_reads
CapturePolicyTests.test_eager_post_entry_start_error_preserves_pending_tee_and_worker_owned_close
```

### author-execute-r1

```text
CapturePolicyTests.test_modeled_clean_and_expected_red_products_keep_exact_stop_and_exit
CapturePolicyTests.test_product_error_callback_observes_original_errors_even_with_polled_zero
CapturePolicyTests.test_product_stdout_or_stderr_overflow_enters_original_drain_and_stop
CapturePolicyTests.test_product_live_failure_enters_drain_while_evidence_is_preserved
CapturePolicyTests.test_stop_pending_then_zero_is_not_aborted_by_prior_product_capture_failure
CapturePolicyTests.test_stop_stdout_or_stderr_overflow_remains_final_failure_without_aborting_stop
CapturePolicyTests.test_late_product_capture_close_failure_cannot_become_success
CapturePolicyTests.test_original_falsey_cancellation_precedes_capture_check_and_survives_later_failures
```
