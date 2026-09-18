# Canonical local launch deadlines — 18 September 2026

Refs [#437](https://github.com/p2pKit/P2pKit/issues/437) and shared
[#424](https://github.com/p2pKit/P2pKit/issues/424). **Source/offline repair only;
apps are not in Releases.** Base `b687429c3272225f7e2764b0db2c61a4f125f73e`, tree
`18f1a4202042fd5e887d1b3013e960a0f9b54603`, already preserves the
[canonical stream cap](hosted-canonical-capture-2026-09-18.md). Its accepted
results were not replayed. This corrects the separate local-clock gap identified
in that dated record, not the still-unfinished bootstrap shared-clock parent.

## Reproduced cause and bounded correction

Canonical `wait_process` used to start a new relative timeout after process spawn
and two stream setups. It also returned any polled exit before checking time or
the cancelled-product list. A late zero or expected-red exit could therefore be
accepted, including when discovery or the original callback consumed the budget.
Five old-API controls reproduced those defects with intended assertion failures,
not a missing-keyword TypeError. No historical native/hosted incident is inferred.

The keyword-only optional `local_deadline` is a **same-process Python-monotonic
end**, not wall time, an external authorization token or shared RAW/QPC identity.
Exact builtin finite int/float values are required; booleans, subclasses,
coercible objects, nonfinite values and unrepresentable arithmetic refuse before
child/discovery suppliers. Timeout stays positive. Legacy direct callers may
use small positive remaining intervals; no new0.1 minimum is imposed there.
A supplied end must be no later than the once-calculated relative ceiling:
enlargement is rejected, not clamped. Negative clock origins remain valid.
Precision loss giving end==now expires; no epsilon or grace extends the budget.

Canonical execute captures both original admitted budgets before child suppliers,
then computes distinct ends immediately before product and stop spawn. Each end
includes that spawn and its two stream setups. Stop's anchor is **after** the
existing pre-stop drain and lease admission. The same wrapper/home/flags, one
stop, capture ownership and receipt schema remain. Mutable args cannot renew
either captured allowance. Anchor admission failure before spawn is not recorded
as a launch attempt; a partially attempted spawn retains original cleanup.

An already-known expired iteration invokes the original callback first, then
product cancellation, then refuses without another poll/discover. Callback clock
recovery cannot reopen expiry. On-time iterations preserve poll -> discover ->
callback ordering; product cancellation and a fresh finite/nondecreasing local
observation with strict now<end precede every accepted exit. None results and
the unchanged0.1-second sleep cadence share the same end. Supplier exceptions
propagate without retry/wrapping; the original callback can still raise the first
cancellation/capture error. Stop ignores only the cancelled list and retains its
**cancellation-only** callback, never product capture checking.

The observed local high-water is per wait. It does not detect unobserved rollback,
authenticate prior anchors or shared epochs, define suspend accounting, preempt
blocked synchronous calls, or bound the entire invocation. Admission, pre-stop
drain/lease, stream finish, final native drain, reports and receipts retain their
separate bounds. Later final re-polls may record observed zero exits but cannot
erase latched timeout errors or final125. Original interruptions survive cleanup.

The unchanged `Command.wait` in `scripts/run-hosted-lock-candidate.py` still
computes relative remaining time
before calling wait without the new keyword. Its compute-to-entry gap remains;
only late-exit checking within its entered wait is improved. No historical writer
result or stricter16MiB/64MiB/8MiB capture budgets are requalified here.

## Exact author evidence

Implementation freeze tree `bf58e76d951aa3c523def534ca6a4c928d757ab4`, two-file
patch SHA-256 `f298d6dab4bee1c1b2d674e721bd683dcd34fb685fc5f0fd7f7cfd2698794da5`.

| File | SHA-256 |
| --- | --- |
| `scripts/run-audit-command.py` | `ce089c704386e2b8cba29c75081568f1a812a2d50964d1a0bc77658a0939ec84` |
| `scripts/tests/run-audit-command-test.py` | `795dacd4c4077fea7b2e3e3aaf4a64bf131fbf0f47beb3df8628da6f55794ea1` |

The additive `DeadlinePolicyTests(unittest.TestCase)` has25 own methods. All
**25 distinct postimage methods passed across two disjoint invocations**, not a
whole25 aggregate. The original preimage remains **FAILED:0 pass/5 intended
failures**, with zero setup errors/skips. The entire author test file, including
those five method bodies and helpers, is byte-identical between preimage and
postimage. Existing cap/policy/native suites and their normal main selection are
unchanged apart from the additive new class registration; they were not replayed.

| Original invocation | Outcome | unittest / outer seconds |
| --- | --- | --- |
| Preimage five, tree `69dc8d3edc8d325c86d36aecf75ad8a4418a6643` | **0/5;5 intended failures** |0.012 /0.366242|
| Repaired five |5/5 PASS|0.011 /0.366050|
| Additional twenty |20/20 PASS|0.046 /0.416275|

This is30 method attempts across three invocations, not30 distinct tests.
Actual UID/EUID65534, isolated Python3.12.3 `-I -B -S`, original argv/minimal
environment and interpreter/content/metadata observations are retained. All1427
frozen source and repository bindings stayed unchanged. Interpreter SHA-256
`1643dacd9feaedc58f3cc581e4d22577dfe25c09b10282936186ccf0f2e61118` describes the
actual interpreter, not whole-runtime/native admission. Outer limits were90+kill5
seconds and recorder105; measured controls took less than half a second each.

Direct waits use deterministic fake clocks and suppliers. Execute/wait/receipt
logic runs over explicitly modeled scope/process/Tee/source/lease/signal/report
boundaries and tiny actual temporary receipt files. No wrapper, native process,
Java/Gradle, GPG, provider, network, application or hosted path executes. The
observer poisons those routes and checks that no test-owned thread remains.

**Do not run `run-audit-command-test.py` directly under the offline-only allowance:**
its normal main runs native suites. Actual recorded invocations imported it under
a non-main name and constructed only the explicit new selections below. The full
observer/recorder/argv/environment/log originals stay private. Passive original
readback SHA-256 `064fc1006d273ab722e63e8d62cbe0ba77b8706604901d779bb6990fb78f8255`
adds zero test executions. An earlier inline passive-recorder SyntaxError occurred
before execution/output creation; it was not a failed candidate/test aggregate.

## Independent review and composition

Design-only verdict
`RECOMMEND_LOCAL_LAUNCH_DEADLINE_CONTINUITY_WITH_REFINEMENTS_DESIGN_ONLY`, report
SHA-256 `a1a0796d3bbb9fec1b2c6073208bd3c63a8c6731aeb09f77e7e9b08c2a6a253b`,
preceded implementation. Its20 desired assertion families are not20 executable
tests or implementation approval. The actual independent implementation and
complete-patch findings are recorded separately below and against the containing
commit in the issues; agent review never substitutes for formal GitHub approval.

Independent implementation verdict:
**APPROVE_EXACT_CANONICAL_LOCAL_DEADLINE_IMPLEMENTATION_R1_SOURCE_AND_OFFLINE_ONLY**,
report SHA-256 `2d7e3c4d7fe820e5903881b1ff865b8e958d6cd747f504547b920fa0e3bc9bce`.
The reviewer authored/froze38 methods before reading this canonical implementation
or any author deadline tests. Four disjoint serial invocations actually passed:

| Independent selection | Outcome | Outer seconds |
| --- | --- | ---: |
| Numeric admission |8/8 PASS|0.409839|
| Wait ordering |12/12 PASS|0.409301|
| Execute/cleanup |15/15 PASS|0.522308|
| Structural conservation/composition |3/3 PASS|5.192977|

These are38 distinct methods, zero failures/errors/skips, not a whole38 aggregate
or replay. The structure selection includes eight AST-only negative mutations.
Actual UID/EUID/GID/EGID65534, no supplementary groups, isolated Python3.12.3,
40-second external/CPU25/address-space512MiB/file16MiB/FD128/core0 limits and
complete source/control/runtime originals were observed. Execute uses actual
canonical execute/wait/Tee/receipts with synthetic scope/children, lease/source/
clock and synchronous worker scheduling; tiny files are real, native execution
is not. Original files9/9/291/9 were retained and compared without another run.
Independent original readback SHA-256
`5b6bc709375bf44f0142d33de4025d7a59100bb9607429fcd2ef71a40e196ed3`;
lead passive verification of353 review files/all1427 source files SHA-256
`f04f7bfce8d15142643d47c465c4c5ea31cefa8ee5ff38546b0aa11a27ef1076`.
This implementation verdict excludes author-test and complete-patch approval.

The original unchanged composition gate actually refused this implementation,
exit1, with `ordinary executable composition changed: scripts/run-audit-command.py`.
That expected refusal is not a passing gate. After that independent implementation review, only the canonical expectation
was changed to the explicitly supplied
`840a952e56cea3aa1f29afe0a46cf825452b5d2b452c2ae3ac0fb9c6d4ae8e8f`. Other six supplier pins,
normalization and roster remain unchanged. The earlier cap mutation's two caller
targets were adapted to the new local-variable/keyword call shape; original
capture/cancellation/stop assertions remain load-bearing.

The changed-input positive, that affected cap method and five new deadline
mutation methods passed **7/7 once**,24 negative variants, in6.931 unittest /
7.085690 outer seconds. Exact selection:

```text
CompositionPolicy.test_reviewed_programs_match
CompositionPolicy.test_canonical_capture_product_error_polling_keeps_stop_separate
CompositionPolicy.test_canonical_deadline_numeric_admission_and_no_enlargement_are_required
CompositionPolicy.test_canonical_deadline_original_launch_anchors_and_admitted_budgets_are_required
CompositionPolicy.test_canonical_deadline_strict_observation_and_high_water_cannot_be_bypassed
CompositionPolicy.test_canonical_deadline_expired_admission_and_cancellation_precedence_are_required
CompositionPolicy.test_canonical_deadline_late_shadowing_cannot_replace_wait_or_end_arithmetic
```

The observer selects only these methods under actual UID65534 / `-I -B -S`,
with supplier/network/native/child operations prohibited. All1427 source and
metadata bindings stayed unchanged. This is an AST policy pass, not another
canonical/native-suite execution. The containing commit's issue map supplies
the final diff/tree, separate complete-patch review and original passive
document/layout/release-metadata/whitespace results; no whole release gate is
inferred from those source checks.

## Still unaccepted

No shared-clock/job/phase/capture producer parent, actual successful configuration,
same-home stop/enclosing native retirement, original collection/export/freeze/save/
probe or encrypted custody/seal is established by this local timer repair. No
bootstrap workflow or production `cache.export_snapshot`/`cache.save_set` caller
exists. Configuration-only help cannot satisfy ordinary ABI/simulator/transcript
acceptance.5400 remains **UNADMITTED/UNMEASURED**; NativeFile900, Snapshot576MiB,
ordinary deadlines, both HOLDs, selectors and credential boundaries are unchanged.

The routine recipient file is absent. Named custodian, exact public key, finite
14-day legitimately trusted-original-base policy and formal approval remain
required, followed by genuine native/provider/resolver/custody/scheduling/delivery
qualification and normally checked/formally reviewed main merge/preservation.
Current required checks remain `complete-gate`, `review`, `scan / osv-scan` and
`osv-scanner`; configured approval count0 does not waive the owner's different-
account review requirement. Metadata19:17:08UTC retained78 open issues, seven
unchanged dependency proposals, no campaign PR, zero queried active Actions and
two existing RC Releases with zero assets. Full relevant conversations were
paginated; unchanged comment bodies were compared, not claimed newly executed.

Preview35070982169 and accepted writer35066719641/1 (CLI9/diagnostics23; six original
exports inspected) were not rerun or redownloaded. Preview APK/MSI/ARM64-DMG/DEB
remain Actions artifacts expiring September30, not Releases. #372's20 Kotlin tests
stay uncompiled/unexecuted. OSV GHSA-r937-wjx7-w2jp/CVE-2026-53914 remains
**EXCEPTED_NOT_FIXED**, affected Kotlin2.4.10, expiry2026-10-31; no remediation,
scan or extension. Physical phones and production/Maven/Store publication remain
excluded. Protected instructions, immutable RC history, compatibility and unrelated
work remain preserved. Historical206/234 repair-approved,207/234 resolved;
audit/release **NOT_READY**. No build/download/held dispatch, PR/merge, Release,
settings change or issue closure accompanies this source increment.

## Exact selected author methods

### author-repaired-five-r1

```text
DeadlinePolicyTests.test_exact_expiry_cannot_accept_product_zero
DeadlinePolicyTests.test_late_expected_red_exit_cannot_pass
DeadlinePolicyTests.test_callback_time_cannot_escape_exit_deadline
DeadlinePolicyTests.test_product_spawn_time_cannot_renew_relative_wait
DeadlinePolicyTests.test_stop_stream_setup_cannot_renew_relative_wait
```

### author-additional-twenty-r1

```text
DeadlinePolicyTests.test_legacy_equal_and_shortened_ends_keep_on_time_zero_and_red
DeadlinePolicyTests.test_local_end_is_keyword_only
DeadlinePolicyTests.test_invalid_numeric_inputs_refuse_before_process_suppliers
DeadlinePolicyTests.test_later_end_is_rejected_not_silently_clamped
DeadlinePolicyTests.test_known_expiry_never_polls_or_reopens_after_callback_clock_recovery
DeadlinePolicyTests.test_product_cancellation_precedes_exit_and_known_expiry_but_stop_ignores_list
DeadlinePolicyTests.test_original_callback_failure_identity_precedes_timeout_and_later_bad_clock
DeadlinePolicyTests.test_discovery_time_is_checked_after_original_callback
DeadlinePolicyTests.test_original_poll_and_discovery_exceptions_stop_later_suppliers
DeadlinePolicyTests.test_invalid_or_backward_observed_clock_is_not_retried
DeadlinePolicyTests.test_equal_negative_origin_and_subminimum_remaining_values_are_admitted
DeadlinePolicyTests.test_unrepresentable_future_end_expires_without_epsilon_extension
DeadlinePolicyTests.test_none_polls_and_sleep_share_one_end_and_expiry_stops_new_polling
DeadlinePolicyTests.test_remaining_product_and_stop_setup_positions_spend_original_launch_ends
DeadlinePolicyTests.test_original_admitted_budgets_are_not_reloaded_after_spawn_mutation
DeadlinePolicyTests.test_stop_anchor_is_after_original_pre_stop_drain_and_lease
DeadlinePolicyTests.test_expired_product_still_drains_and_runs_one_pending_stop_with_its_own_end
DeadlinePolicyTests.test_late_stop_final_zero_cannot_erase_timeout
DeadlinePolicyTests.test_invalid_product_anchor_does_not_fabricate_a_launch_or_stop_attempt
DeadlinePolicyTests.test_attempted_spawn_keeps_one_stop_and_original_interruption_through_finalizers
```
