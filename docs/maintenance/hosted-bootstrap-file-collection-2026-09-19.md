# Dormant configuration-file collection — 19 September 2026

**Source/offline work, not original-call collection or hosted acceptance.**
This follows the [canonical retained-parent correction](hosted-canonical-report-parents-2026-09-19.md)
at `e6342a00c9b3ff44960957d1ca38468abe0f9056` and the earlier
[inventory grammar](hosted-bootstrap-report-inventory-2026-09-18.md).
The containing commit and final review are mapped to
[#437](https://github.com/p2pKit/P2pKit/issues/437). No public command or workflow
invokes this new leaf; the original-call collection parent remains unfinished.

## Exact file-only boundary

[`collect_inventory`](../../scripts/hosted_cache_bootstrap_collect_files.py)
accepts six supplied request/admission/context/start/receipt/manifest byte
records, a supplied successful exit, two directory identities and metadata-file
bindings. It rederives the unchanged inventory, canonical evidence source and
`configuration-custody/retained` destination. It does **not** accept or authenticate
a raw reservation request, returned `ConfigurationPrefix` or original call.
Reservation/producer-call binding belongs to the future enclosing parent.

The copy includes exactly three metadata files, four canonical product/stop logs
and already-retained changed reports. It never follows live checkout outputs or
reruns canonical `retain_reports`; unchanged reports remain metadata-only.
All three metadata originals are checked before copy output. Each file uses
positive reads of at most64KiB, same-reader prehash/rewind/copy, full exact write
acknowledgments, sync/verify/close and a new destination reader. Partial writes
fail with requested/acknowledged counts separate; no retry disguises them.
Identity/stamp/size/hash, exact membership and final directory/file rechecks
remain required. Partial files and original failures are not deleted.

One nonrenewable local120 ceiling only shortens the caller's deadlines. Later
callbacks cannot renew an earlier caller ceiling; equality expires. This is not
a shared RAW allocation, admitted phase/job budget or preemptible filesystem
watchdog. Native basename128/alnum-first, absolute depth64,10,000 observed-member
and4,096 cumulative resource limits remain narrower than inventory grammar.
Three metadata4MiB, four log64MiB and aggregate declared report512MiB limits
remain; the copy is streamed, not a576MiB aggregate Snapshot or a2GiB cohort test.

Windows `NativeFile.read(1)` at declared-size exhaustion returns empty without
issuing another API read. The leaf explicitly labels that boundary and requires
unchanged same-descriptor verification; it does not claim kernel EOF or native
Windows qualification. No shared Windows/POSIX supplier or its900-second lifetime
is changed.

The leaf retains independent references to its returned resources, refuses
borrowed/repeated factories and registration uncertainty, and closes only its
new resources. New-row labels are diagnostic strings, not authoritative dispatch
identities; a future original-call parent must pin its own authoritative labels.
The enclosing owner stays open. Output explicitly denies original-call/single-use,
enclosing retirement, no-loader, population/test and next-phase/export/save
authority. Known leaf-handle close is not original producer/native retirement.

## Original failures and scoped corrections

Independent R1 desired-behavior controls exposed two distinct errors:

1. An earlier leaf resource returned again was treated as a new unregistered
   obligation, fabricating UNKNOWN and losing its known original close duty.
2. Propagating the same primary after every successful cleanup close consumed
   the parent's64-error cap, stranding six of70 modeled obligations.

R2 pins pre-call owner identities before reconciliation and does not re-record
the identical first exception after a known successful close. Its same-four
independent postimage passed. Whole-leaf review then found a different path:
re-observing the same expired local ceiling twice per successful close consumed
the same error cap. The separately executed R2 expiry preimage closed32/70,
recorded64 errors and stranded38 known models with fabricated UNKNOWN.

R3 still samples before and after every close. Only a fresh exception actually
created by that sample can identify the fixed local-expiry observation; its
already-recorded repetition is not another error event. The marker clears
**before** the clock supplier, so matching text or a rethrown old exception is
not a new leaf observation. Actual close errors, other clock errors, first
failure and UNKNOWN remain unconditional. No cap, deadline, acquisition or
success requirement is relaxed.

Separate R3 owner-barrier controls confirmed two further defects: lost new
registration could replace an earlier actual falsey acquisition exception with
the later registration error, and preclose clock/error-recorder UNKNOWN could
still allow one original close dispatch. R4 retains the actual acquisition
exception before recording newly discovered registration uncertainty, without
inventing an earlier error for plain registration loss. It rechecks the same
live/known close binding after preclose sampling and **before** attempted marking
or dispatch. Existing parent-primary precedence, independent references, UNKNOWN
and the no-fallback-close rule remain. No new label invariant is introduced.

## Exact executed controls and unexecuted proposals

The [author class](../../scripts/tests/hosted-cache-bootstrap-collect-files-test.py)
now contains47 authored test methods. There is **no whole47-method run**. The
R2 original39 and R4 focused10 are separate source-bound invocations, not49
distinct tests or a final47 aggregate. All39 prior test bodies remain unchanged;
AST identity is not final-source execution. The original R1 author37 were never
executed.

| Exact invocation | Actual outcome |
| --- | --- |
| Author R2,39 selected methods |39/39 PASS, exit0,0.952s |
| Independent R1 ownership4 | FAILED, two assertion failures/two passes, exit1,0.028s |
| Same independent ownership4 on R2 |4/4 PASS, exit0,0.027s |
| Separate independent R2 expiry2 | FAILED, one assertion failure/one pass, exit1,0.036s |
| Separate independent R3 owner-barrier3 | FAILED, two assertion failures/one pass, exit1,0.003s |
| Author R4 focused10 |10/10 PASS, exit0,0.124s |
| Unchanged independent expiry2 on R4 |2/2 PASS, exit0,0.037s |
| Unchanged independent owner-barrier3 on R4 |3/3 PASS, exit0,0.002s |
| Distinct independent R4 file-protocol9 |9/9 PASS, exit0,0.015s |

R3 author6/expiry2 postimage proposals were **never executed**; final-source
selections superseded them. The earlier distinct9 fixture was also unexecuted;
its modeled readback uses the captured writer's preclose stamp rather than
calling modeled verification after close. That fixture correction was preserved
and reviewed before execution, without changing the desired assertions.

Executed invocations above had zero errors/skips/expected failures/unexpected
successes. Failed aggregates remain failed, not relabeled by later passes.
Author R2 used tiny actual ordinary-UID POSIX files plus explicit parent,
Windows-API and bound models. R4 focused10 covers the five new expiry controls,
three new first-error/UNKNOWN regressions and two existing actual-file/plain-
registration counter-controls. Independent expiry2 closed all70 known directory
models with one expiry record; its genuine close-failure counter-control stayed
UNKNOWN. Owner-barrier3 retained the real first error and made zero close calls
after preclose UNKNOWN. All independent invocations used inert models, not
actual file/native-process acquisition. The distinct9 exercises stream types,
positive reads, write acknowledgments, rewind, readback, listings and callback
timing; it does **not** execute `collect_inventory`/`_Inputs` or authenticate any
original records. The48-family review map is not48 tests or all-variant coverage.

Author envelope: UID/GID65534, Python3.12.3 `-I -B -S`, CPU40s/AS768MiB/output2MiB/
FD128, wall75s+kill5s/recorder90s. Independent ownership/expiry envelope: same
ordinary identity/isolation, CPU10s/AS384MiB/output2MiB/FD64,
wall20s+kill5s/recorder30s; owner-barrier/protocol controls use that same envelope.
Immutable source, interpreter, harness and descriptor bindings were checked:
1,436 source files in the earlier R1/R2 runs and1,437 in R4, including draft
documentation bound to those executions but not thereby approved. Original
stdout/stderr/plans/results, before/after source bindings and harness copies are
retained privately. On resumption at18:16 UTC, the earlier R1–R4 temporary source
copies and both author temporary fixture/harness directories were absent. Their
unobserved lifetime/cause is unknown; the tiny file fixtures cannot now be
reinspected. Current equal source bytes and newly created copies are **not** the
old files or substitute original fixtures. No reconstruction or rerun hides this
loss. No old product suite, native owner, producer, network, dependency download
or build executed.

| Binding | SHA-256 |
| --- | --- |
| R4 implementation | `f3a563874fd723ea6aae973a41e76db1cbef74f90f6fcbf9adfe05b5fad8fec3` |
| R4 author source | `e4d1182c04c39652dd5be3900b264003c548c72fb970361a8da80bcd335b290a` |
| Original author R2 result | `8607f5e04c13e27c77d1933756686bf9cb24cb7f44957b266ebb9e5f8343d243` |
| Independent R1 failed ownership4 result | `532e0493a25059d0466e2fd29331c8e163d90dbc5af26f67b81327fe7ec6a64e` |
| Independent R2 ownership4 result | `5f0d7dc5508bf74dbcac43fca0e97890d37fd5fc241143b8616ce5ead43497b4` |
| Independent R2 failed expiry2 result | `a555b19ac97ab262fdbad80fade8304b74d77220239fe7fb93b9c36069551245` |
| Independent R3 failed owner-barrier3 result | `ee89b12f8fe20c70a84c132bdc5fc5a9f3c0a6f16577b89722f427de3150a153` |
| Author R4 focused10 result | `b9fefb190fb12787488f15a07ac6ce25d9aa2142f9f035ca9a54c6f9c2b0c3d3` |
| Independent R4 expiry2 result | `69a8511eada976fb6c36c3d7492078cf0d63b54f1d8e192fe0d653d3466c616c` |
| Independent R4 owner-barrier3 result | `faf1cdeb7ae66f8dfefc509491c3b776358fb75b8abd98926d9513d1ffa85829` |
| Independent R4 file-protocol9 result | `caa4e86d00fe7270bf8dc4448ba882e715db088418dade493645fee3b3b69d31` |

R4 execution-snapshot tree `832b881ffc57e7812edd301420ed95ad0c69b64c`;
patch `ccd63a7a6938418f67c50ad489afe0169176c4b22b6a9d0aff08beb5a9da38bb`;
freeze `1efa5544a16ccd64457336c6c584388355cc928d89985dfd10e8b38c36e90f51`.
That snapshot included earlier draft docs, not these finalized execution notes.
Private lead packet: `20260919-bootstrap-collection-d1jtr_84`. Hashes are
navigation, not public raw evidence or substitutes for missing originals.
Independent whole-leaf verdict:
**APPROVE_EXACT_DORMANT_CONFIGURATION_FILE_COPY_LEAF_SOURCE_ONLY**;
report SHA-256 `903e1add75d4a453e51d2c311a446dd98942e7d1af0a33b2119fa571ecf9c51f`.
No scoped implementation finding remains. The review explicitly retains the
missing temporary-copy limitation and R2-only evidence/omitted-variant boundaries.
Complete-patch review is separate; its final verdict and exact bytes are mapped
to #437. Agent implementation/harness review is not formal GitHub PR approval.

The R4 author invocation used the private `run-controls.py` recorder with
`/usr/bin/python3.12 -I -B -S`, arguments `implementation-r4 author10-r4-original`
and these exact selectors, in order (an execution record, not replay permission):

```text
FileLeafControls.test_known_local_expiry_is_one_event_but_every_original_close_is_sampled
FileLeafControls.test_matching_supplier_error_text_does_not_preconsume_leaf_expiry
FileLeafControls.test_clock_rethrowing_previous_leaf_expiry_is_not_a_new_leaf_observation
FileLeafControls.test_backward_clock_after_recorded_expiry_is_not_suppressed
FileLeafControls.test_actual_close_error_matching_expiry_text_still_becomes_unknown
FileLeafControls.test_post_factory_registration_loss_preserves_actual_first_acquire_error
FileLeafControls.test_preclose_error_cap_unknown_prevents_any_original_close
FileLeafControls.test_preclose_error_recorder_failure_prevents_any_original_close
FileLeafControls.test_local_expiry_after_read_stops_new_work_but_attempts_known_close
FileLeafControls.test_post_factory_registration_loss_is_unknown_without_fallback_close
```

Author plan SHA-256 `b138b9a2619d260e4d627677eff32660ebd9a3858c7dea90e89e98a1844e2c17`.
The three independent private `run_independent.py` recorders each ran once with
the same isolated interpreter and respectively `expiry-postimage-original-01`,
`owner-barrier-postimage-original-01`, `distinct-file-protocol-original-01`.
Their original plan hashes are `9325732c0dfbd6f5209540d70aa12a8bbb397b64f1adbc8477db9e393811f4fa`,
`73b6470f5178c48c5cbaab74e7bd71d8ec6de057306f742d2cf737a8d7b3e320`,
`39ea6464e56651aa47d62a3fad3f0e74561c35a1c031ddcfd8e5644ef2c88084`.
Complete originals were read back and rehashed, not replayed. The final complete-
patch static gates and independent verdict are mapped separately in #437;
none is a product/native pass or a current required hosted-CI result.

Eight static gates passed on the first complete-patch tree
`bc03bcf57d5a3b5c27d0ad3b4e55fed707183e8e`: Markdown612 links/124 files,
layout10 projects/15 policy models, release metadata, OSV **input coverage, not a
scan**, ordinary composition, FULL workflow policy, sample/Desktop policy and
whitespace/archive integrity. Result SHA-256
`e6007a62a38ae2d6700b8147ecff31d634828b2334ae9399371303e3751f514d`.
Later edits only add this result and the review/preservation qualifications;
their final-byte checks are separately recorded, not another eight-gate run.

## Remaining integration and acceptance

The next parent must once-claim **before invoking the producer itself**, require
its actual successful close/return and final RAW/LOCAL high-waters, and open NEW
owners/handles under the original cumulative allocation. It must not adopt a
returned prefix, reopen an old owner/window/READ30 or recollect live reports.
No-loader observation, positive export/freeze/save/probe, encrypted custody/seal
and development-sample delivery remain separate unfinished integration.

Both ordinary activation HOLDs, exact selectors, credential boundaries and
deadlines remain. Proposed5400 stays UNADMITTED/UNMEASURED; NativeFile900 and
Snapshot576MiB are unchanged. No production caller invokes `cache.export_snapshot`
or `cache.save_set`. Missing routine custodian/exact key/finite14-day policy,
trusted-original-base bootstrap/formal approval and genuine native/provider/
resolver/custody/scheduling/delivery qualification still block activation.
Required checks, formal different-account approval and a normal main PR merge
precede development sample Releases. Agent review cannot supply that approval.

Complete paginated metadata refreshed **2026-09-19 18:08:02 UTC**:78 open issues,
the same seven dependency PRs, no campaign PR, zero queried active Actions and
two existing RC Releases with zero assets. #437/#424/#457/#143/#144 conversations,
main/candidate refs, effective rules and advisory had no semantic change from
the10:25 refresh. Required checks remain `complete-gate`, `review`,
`scan / osv-scan`, `osv-scanner`; configured review count0 does not waive the
owner's formal different-account requirement.

Apps are **not in Releases**. Preview35070982169 and #424 writer35066719641/1/six
exports were not repeated; #372's20 Kotlin tests remain uncompiled/unexecuted.
OSV remains EXCEPTED_NOT_FIXED, affected Kotlin2.4.10, expiry2026-10-31; no new
scan, remediation or extension. No local Java/Gradle/Xcode/app build, SDK or
dependency download, guest, held CI, phone, production/Maven/Store publication,
release/tag/settings change or closure occurred. Main, protected instructions,
immutable RC history/compatibility and seven dependency proposals remain intact.
Historical206/234 repair-approved,207/234 resolved; audit/release **NOT_READY**.
