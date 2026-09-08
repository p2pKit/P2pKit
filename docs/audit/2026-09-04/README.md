# Comprehensive audit continuation ledger

Start with the root [continuation checkpoint](../../../AUDIT_CHECKPOINT.md). Clone the
`audit/complete-2026-09-04` branch, not just the default branch, to obtain the reviewed source and these records.

## Records

- [Checkpoint metadata](checkpoint.json): source revisions, issue-count denominator and evidence limitations.
- [Issue index](issues.md): all 182 inventoried issue rows grouped by checkpoint disposition.
- [Issue records](issues.json): reported scope, dependencies, recorded commits and public investigation/outcome links.
- [Coverage ledger](coverage.tsv): inherited per-path review claims, provenance revisions and reopened work.
- [Unverified follow-ups](followups.md): hypotheses needing reproduction and deduplication, not confirmed bug claims.

The inventory is a continuation aid, not live GitHub state: **69 independently approved repository repairs,
91 pending repairs, 21 external-validation rows and one architecture decision**. Using **182 rows**, this is
**37.9% reviewed / 62.1% remaining**; pending repairs are 90 Low and one informational (#333).
**49 findings** originated in this audit. #133 independent interoperability remains NOT_STARTED; #367 source
approval does not complete its unexecuted Windows/Intel acceptance. These are not effort, closure or readiness
percentages. The completed transfer stop is superseded. Next #368, then #223 and serialized hosted facility/
remaining repairs; no #368 repair is approved by this #367 checkpoint. Overall **NOT_READY**.
This records #367's approved-source cycle at `0d88be3`, not later #368 executions/results. The separate
source-reading receipts at `c221d54` do not themselves approve #368 or retarget #367 verification.

The exhaustive **10:24:33–10:30:05 UTC** GitHub capture refreshed all 288 issues (181 open/107 closed),
79 PRs (7 open/72 closed), all 367 issue-style histories and every PR metadata/review/file/commit collection.
**1,519 GETs** including preflight, zero failures, zero reused current histories; start/end lists stable.
Thirteen newly observed timeline identities include three older uncaptured backlinks, not new defects/decisions.
Earlier 09:17–09:28 capture/reuse evidence and initial #367-addition records remain historical and unchanged.
#368 was individually filed/refetched **10:50:42 UTC**, bringing known totals to 289 issues/182 open/79 PRs;
#367's approved outcome was individually refetched 11:01:17 UTC. Neither is a complete post-write refresh.
See [checkpoint metadata](checkpoint.json) for exact bindings, retained prior evidence and limitations.
GitHub snapshots are per-endpoint, not transactional or permanently current; refresh before work.

## Latest #367 repository-source correction

The complete five-file host-classifier correction is independently **APPROVED** and pushed at
`0d88be3e3769b5133a985e4fe2fca782ba0ef2a6`, tree `db432eb14791d9637e812333305e811edceb834e`.
Fresh `/root/review_367_r1` found no actionable source/provenance findings. Source/ref verification was
10:59:45 UTC; the [safe outcome](https://github.com/p2pKit/P2pKit/issues/367#issuecomment-5584111070)
was refetched at 11:01:17 UTC. The issue remains OPEN. See [the scoped report](repairs/367.md).

Exactly five current Native/AAPT2 classifier records were added after byte/signature curation anchored to
official publisher fingerprints. Three Native hashes also match official archive digests; both AAPT2 hashes
match authoritative SHA-256 sidecars. All old records, versions, locks, wrapper, trust and required tasks remain.
The maintained pre-build policy independently requires four Native and three AAPT2 hosts, with ten regression
methods and an exact-original-metadata outer-gate negative control. This is a completeness/format tripwire,
not authentication of arbitrary well-formed hashes or foreign-host execution.

- Strict, clean Linux affected command **PASS**: **851/851** core tests (789 JVM, 62 Android-host),
  100 XMLs, 110 executed tasks; Native Linux download, AAPT2 processing, Android sample assembly,
  strict core Dokka and Android ABI/compiled-constant guards pass.
- Both clean combined `check`/sample/Dokka and separate `./gradlew check --console=plain` commands **FAIL**:
  each **1,297 passes plus one failure**, 1,298 cases/151 XMLs/172 tasks, no errors/skips.
  The distinct downstream test-fixture mismatch is [#368](https://github.com/p2pKit/P2pKit/issues/368),
  not an exporter exception or #367 regression. Message-only instrumentation proved export succeeded at the
  normalized uppercase path and was then restored exactly. No #368 repair is approved by this checkpoint.
- All provenance/completeness/control/toolchain checks and twelve static/range gates pass. The private seal
  retains **2,160 files / 21,605,300 bytes**, 20 own serialized leaves plus a separate successful sealer.
  Shared #145 failures and the #368 diagnostic are not additional own leaves or passing tests. All stops
  exited zero; no owned survivors remained; dependent disposable outputs and owned GPG/artifact workspaces
  were removed after evidence preservation. Protected source, shared caches and unrelated tasks remain.

The original #145 failures below remain historical failures. Last successful full integration recorded in this
#367 checkpoint is historical `6995130`, not `0d88be3`; newer #368 executions are outside this cycle's record.
Windows/Intel/Apple acceptance is **NOT_EXECUTED** in this cycle;
source approval does not discharge those #367 acceptance gates. Next is #368, then #223 and the serialized
hosted facility/remaining sequential queue. #133 independent interoperability remains **NOT_STARTED**;
physical-device/ART, hostile-network, independent-implementation and professional-crypto acceptance remain
separate. Whole audit **NOT_READY**. No merge, closure, release, tag or settings change is authorized.

## Historical #145 approval and verification

Earlier #145's complete nine-file receive-backlog correction is independently **APPROVED** and pushed at
`0423e96e15c894c26a7d45a5dfb2a012e0c1ba8e`, tree `26984a1b7d2048bdbda8e1808bb38f299e7a6866`.
Fresh `/root/review_145_r1` inspected the complete diff, actual admission/ownership/cancellation/rearm callers and
sealed raw evidence; no actionable findings. See [the #145 report](repairs/145.md) and
[verified outcome](https://github.com/p2pKit/P2pKit/issues/145#issuecomment-5582924265). Source/ref verification was at 09:37 UTC; the outcome was refetched at 09:42 UTC.
The issue remains OPEN, not merged or released.

Both the 64-message and 8 MiB caps already bounded growth. The confirmed Low issue is post-session-admission
allocation/retention amplification. The default v2 route requires authenticated/authorized admission; this is not
a pre-admission LAN finding. Explicit plaintext mode also reaches this accounting. Binary under-reporting remains
refuted. Admission now checks count before measurement and stores a charge of 512 bytes/message plus twice each
Text UTF-16 code-unit length (or actual private Binary payload length), and 256 bytes plus twice the key/value
UTF-16 length per metadata pair. Arithmetic widens before addition/multiplication; delivery, rollback and drain
release the same stored charge. Defensive ownership copies, public API/ABI, wire/security policy and dependencies remain.
This is a bounded policy estimate, **not** a universal heap upper bound, constant-time metadata walk or literal
zero-allocation guarantee; no Native heap/allocation profiling was performed.

Tighter admission is reserved for **0.8.0+**: without metadata/backlog, 4,194,048 ASCII UTF-16 code units reach 8 MiB;
one more is refused. A wire-legal 4 MiB ASCII Text costs 8 MiB plus 512 bytes and fails the receiving session even
with otherwise empty backlog. Do not change published 0.7 artifacts or weaken the documented limit.

Original production with the corrected final regressions produces **33 intended AssertionErrors** (17 JVM,
16 Android-host). Three restored mutations detect the Text multiplier, metadata allowance and inclusive boundary.
Final focused checks pass **805/805** (89 XMLs, 19 tasks). Affected Linux gates pass **851/851 core tests**
(789 JVM, 62 Android-host; 100 XMLs, 97 tasks), actual Android ABI and JVM/Android public-constant guards, but
**the aggregate command FAILS** on missing strict Native/AAPT2 classifier metadata. The combined `check`/Android
assembly/strict Dokka attempt **FAILS before tests** (six tasks); sample assembly and Dokka are not complete.
These two commands are not current whole-check or release passes. Twelve static/policy gates pass.

The original harness/deprecation failure, later assertion-oracle/Android Log fixture failures and both integrated
failures remain historical failures; oracles/fixture were corrected, not skipped or weakened. A JDK estimator-only
allocation probe establishes removal of payload-length scaling, not retained-heap, enqueue or Native behavior.
The independent reviewer rechecked **1,754 sealed files / 17,292,499 bytes**, 25 finalized serialized invocation
receipts plus a separate sealer receipt. All task-isolated wrapper stops exited zero; no owned survivors remained,
and dependent disposable outputs were removed while preserving source, shared caches and required evidence.
Android-host is not ART/emulator/device evidence. No Mac/Windows/Apple, physical-network, independent-interop,
professional-crypto or final consumer/release pass is implied by this issue-scoped approval.

The original #145 failures above established the distinct Medium, non-security, fail-closed #367
host-classifier prerequisite; they remain historical failures. The later five-file correction and
independent source approval at `0d88be3` are recorded above. Windows/Intel execution remains pending;
the current downstream full-check failure is separately tracked as [#368](https://github.com/p2pKit/P2pKit/issues/368).

## Earlier approved repairs and historical verification

Earlier #360 repairs the pre-existing all-tree whitespace blocker without modifying historical evidence.
Three exact-path/category exceptions preserve bytes and require SHA-256 integrity in head, index and worktree at
both actual gate entry points. Fresh `/root/review_360_r1` **APPROVED** the complete seven-file correction at `6995130`.
The original pre-#144 manual gates both exited 2; the ordinary-range control passed. Final 51 labeled assertions and
ten expected-red controls/two positive controls establish the correction; #223's separate wrapper defect stays pending.
See [the #360 report](repairs/360.md) and [verified outcome](https://github.com/p2pKit/P2pKit/issues/360#issuecomment-5580382007).

#144 now classifies every complete main-push delta instead of inferring passed checks from graph/tree equality.
Genuine nonempty Markdown-only changes remain lightweight; source, rename, empty and fallback safeguards remain.
The weekly Monday 04:17 UTC full backstop is isolated and non-cancelling, not a scheduling deadline. Existing
Linux/Windows jobs, permissions, required checks and release provenance are preserved. Fresh `/root/review_144_r1`
**APPROVED** the complete eight-file correction plus #360's prerequisite effects at the same frozen `6995130` tree.
See [the #144 report](repairs/144.md) and [verified outcome](https://github.com/p2pKit/P2pKit/issues/144#issuecomment-5580383643).

Historical #144/#360 combined verification: **2,459 passes, zero failures/errors, one unchanged manual skip;
297 XMLs, 256 tasks**. This is the last successful full run, bound to `6995130`, not current #367 integration.
Resolver28/policy21 checks, five actual YAML command replays and 23 static gates pass; 13 #144 expected-red controls
and two positive controls pass as verification outcomes. Both reviews inspected shared sealed evidence:
3,558 files/18,444,319 bytes, 106 finalized cleanup receipts and 95 nonoverlapping leaf invocations.
Initial YAML replay, first #360 control-verifier and first evidence-sealer failures are retained, not relabeled.
No production/API/ABI/protocol/dependency or archived-content change. No hosted CI, Windows execution, administrator
bypass, physical-device or independent interoperability validation occurred in these cycles. The schedule is not
installed on the default branch until an authorized merge. Both issues remain OPEN; main is unchanged.

Earlier #359 completes failed-destination settlement despite caller cancellation during abort. Both generic
setup catches retire ownership, perform independently bounded abort, publish the original typed failure and attempt
the existing bounded entry-epoch-fenced terminal notice before restoring structural caller cancellation. Callback-only
cancellation remains distinct; no shared bounded helper, API/ABI, wire, authentication or durability implementation
changed. This is not an authentication bypass, budget leak or demonstrated file loss.

Fresh `/root/review_359_r1` **APPROVED** the complete four-file correction at `de88284`, independently verifying
1,797 sealed entries, 297 final XMLs, 26 new method executions and 28 finalized cleanup receipts. Original production
with final tests gives eight intended JVM failures/two controls and seven Android-host failures/nine controls.
Focused checks pass 33/33; three mutation controls and fourteen static gates pass. Full check, Android assembly and
strict core Dokka: **2,459 passes, zero failures/errors, one unchanged manual skip; 256 executed tasks**. Two genuine
compilation failures and the first evidence-verifier failure are retained, not counted as passes. Source and
[verified outcome](https://github.com/p2pKit/P2pKit/issues/359#issuecomment-5579078847) are pushed/refetched; issue OPEN. See
[the repair report](repairs/359.md). Real pinned kits over in-memory wires preserve another transfer
and messaging; host/Native simulator results are not physical devices, real LAN or independent interoperability.

Earlier #358 fixes destination setup error classification without reclassifying actual channel authentication.
Both local catches are statically file-typed, preserving original local causes and existing file-error identity.
Tests establish terminal retirement/abort, sanitized replay, restored admission capacity and same-session recovery.
Pinned secure kits over exact/fragmented/coalesced in-memory wires retain another transfer and messaging.
No API/ABI, wire, authorization, dependency or durability implementation changed. The install sibling cast is removed
without claiming another currently reachable application-authentication callback there.

Fresh `/root/review_358_r1` **APPROVED** the complete four-file series through `d424a23`, independently verifying
1,736 sealed entries, 296 final XMLs, 26 targeted regression executions and 26 finalized cleanup receipts. Original
JVM production gives two intended failures/three controls; Android original-production control gives three intended
failures/five controls. Corrected focused tests pass 21/21; three mutation controls and fourteen static gates pass.
Full check, Android assembly and strict core Dokka: **2,433 passes, zero failures/errors, one unchanged manual skip;
256 executed tasks**. The first focused compilation failure is preserved, not counted as a pass. Source was pushed
and the [verified outcome](https://github.com/p2pKit/P2pKit/issues/358#issuecomment-5578319370) refetched; issue OPEN.
See [the repair report](repairs/358.md). Its then-unverified cancellation-during-abort observation was later
reproduced and independently repaired as [#359](repairs/359.md); the historical cast report is unchanged.

Earlier #137's complete five-file compatible correction is approved/pushed at `a5d3145`, tree
`bcef6e91cd92e990ac37efd3e2e2840cd89ff2f9`. Four diagnostic slots are volatile; KDoc states the prepublication-only
attachment invariant, retained unsupported Java setters and deliberate cause-dropping copies. All 19 production
attachment sites and constructors/value/ABI/protocol/security policy are unchanged; no active stale-read race or
immutable-error guarantee is claimed. Baseline 14 tests give eight structural failures/six controls; corrected focused
checks pass 72/72. Five mutation controls, fourteen static gates, eight actual compiled-field inspections and strict
Dokka pass. Full check/Android assembly: **2,407 passes, zero failures/errors, one unchanged manual skip; 295 XMLs,
257 tasks**. The reviewer verified all 1,798 sealed entries and 25 finalized cleanup receipts. See
[the #137 report](repairs/137.md). Its then-unverified cast observation was later reproduced and repaired as #358;
the historical report is unchanged. Different-thread StateFlow tests use a real secure kit, not physical devices or
proof of a race. The separate cleanup-cancellation observation is now repaired as #359; the then-planned #144
work is also approved above. Neither historical next-step note supersedes the current #368 → #223 queue.

Earlier #130's complete two-test-file correction is approved/pushed at `1847ed3`, tree
`3fe527a16a52e536dedad610aebff53a7a026cdb`. Both recorders retain pins; repeated distinct remote values and intentional
legacy null delegation are asserted. Production pin forwarding already worked; no production/API/ABI/security change.
Selected old manager unit classes accepted omitted pins (67 passes; Desktop integration excluded); corrected focused
4/4 and module 161/161 checks pass. Eight mutation controls, fourteen static gates and the full check/Android assembly
pass: **2,389 passes, zero failures/errors, one unchanged manual skip; 290 XMLs, 246 tasks**. The reviewer verified
1,930 sealed entries and 30 finalized cleanup receipts. See [the #130 report](repairs/130.md).
Host/fake tests are not physical Wi-Fi or ART/OEM validation.

Earlier #332's complete four-file Apple follow-up is approved/pushed at `78ef361`, tree
`0f8ab1465d257baac8110e3bd1ecf95859abe93c`. Invalid current-browser re-resolution withdraws only the admitted native
service's cache, endpoint and relay ownership; stale callbacks, manual hints and existing dial/session ownership
remain independent. Full check/Android assembly: **2,387 passes, zero failures/errors, one unchanged manual skip;
290 XMLs, 246 tasks**. Twenty transition methods/both profiles, 480 focused LAN passes/one manual skip, eight mutation
controls and fourteen static gates establish the scoped correction. The reviewer verified 1,992 sealed entries and
28 finalized cleanup receipts. See [the Apple report](repairs/332-apple.md). The reopened row returns to approved,
not a duplicate/new completed issue; prior JVM/Android approval remains intact.
Native-input/control-state tests are not live multicast/TCP-handshake proof.

Earlier #356's complete six-file Apple original-key/byte-boundary correction is approved/pushed at `183b6c9`, tree
`d93f93f05f63a9933e0ab894327f94a995f28b36`. Full check/Android assembly: **2,367 passes, zero failures/errors,
one unchanged manual skip; 289 XMLs, 246 tasks**. Fourteen static gates, four mutation controls and 460 focused LAN
passes/one manual skip establish the correction; 1,955 sealed entries and 28 finalized cleanup receipts were independently
verified. See [#356](repairs/356.md). No cache-lifecycle correction or authentication bypass is claimed.

Earlier #229's complete original-byte TXT correction and #357's independent test-clock prerequisite are approved/pushed
through `6d9cd3c` (tree `5f6b6d437cc695ae2912a281663290ee625d2b8f`). Full check/Android assembly: **2,333 passes, zero
failures/errors, one unchanged manual skip; 285 XMLs, 246 tasks**. Thirteen static gates pass. #229's fourteen source
blobs were unchanged from `bf34f70` at `6d9cd3c`; #356 subsequently changed some of those files. Eight TXT controls and
two watcher controls detect the original defects.
The initial full failure is retained, not relabeled. See [#229](repairs/229.md) and [#357](repairs/357.md).
That earlier approval covers canonical known-key value parity only; #356's separate key-boundary approval is above. Admission tightening
is reserved for **0.8.0+**. Physical devices, independent interoperability/crypto and final release gates remain pending.

Earlier #226's complete four-file correction is independently approved/pushed at `f085dc8`: artifacts honor TMPDIR while a
separate GPG root preserves the measured 102-byte physical socket bound. Partial/error/signal cleanup stops only owned
keyring workers; failed shutdown retains an explicit retry path. Fourteen real synthetic-GPG tests, thirteen red controls,
thirteen final static gates and the full check/Android assembly pass: 2,276 passes, zero failures/errors, one unchanged
manual skip. See the [#226 report](repairs/226.md). No production/API/ABI, dependency/lock, workflow or protected-file change.

Earlier #225's complete seven-file correction is independently approved/pushed through `46ed124`: persistent consumer/Netty
policies replace historical denylists, independent approval tripwires remain, and XcodeGen fixtures use current and
synthetic inputs. Fourteen final static gates and the full check/Android assembly pass: 2,276 passes, zero failures/errors,
one unchanged manual skip. Twenty-four actual-caller controls stay bound to `82be9c5`; only one documentation line
changed afterward. See the [#225 report](repairs/225.md). No production/API/ABI, dependency, lock or workflow change.

Earlier #208's two-document correction is independently approved/pushed at `3a96a77`: all three fast-gate command blocks are
byte-identical, Ruby prerequisites/scope are documented, and static checks pass. See the [#208 report](repairs/208.md).
No full build was rerun for that docs-only change; its then-current full check remains bound to `27fec6a`.

Earlier #152's complete six-file graph-caller correction is independently approved and pushed at `27fec6a`: the full check
and Android sample assembly pass with 2,276 passes, zero failures/errors and one unchanged manual skip. All 21 policy
mutation cases and twelve static/graph gates pass. See the [#152 report](repairs/152.md). No production/ABI change;
publication/isolated-consumer/Swift/XCFramework checks were not rerun for this policy-only correction.

Earlier #133's complete repository correction is independently approved at `7127616`: the full check and Android sample
assembly pass with 2,276 passes, zero failures/errors and one unchanged manual skip. The same frozen source passed
coordinated mutation/generator/publication-exclusion controls, local publications and 23 isolated consumer tasks.
See the [#133 scope, evidence and remaining acceptance](repairs/133.md). The earlier
[#355 draft-integration failure](repairs/355.md) is historical and superseded, not the current gate result.
See the [#187 compiled-constant guard/verification report](repairs/187.md),
[#190 documentation/bytecode verification report](repairs/190.md),
[#325 repair/verification summary](repairs/325.md), [#317 report](repairs/317.md),
[#354 report](repairs/354.md) and [earlier #337 report](repairs/337.md). Whole-audit final/release verification remains
pending. Historical #229/#356 reports retain their then-unconfirmed Apple #332 wording; the separately reproduced,
corrected and reviewed follow-up above supersedes that hypothesis without expanding the earlier parser reviews.
Preserve the #226 macOS GPG socket bound and all earlier provenance fixes. #325's feasible correction
preserves `AGENTS.md:9` by owner instruction; literal alignment of that SDK prerequisite requires new authorization.

## Newly tracked findings, not approved repairs

| Issue | Confirmed scope | Verification still required |
| --- | --- | --- |
| [#361](https://github.com/p2pKit/P2pKit/issues/361) | Android hotspot reason labels shifted from SDK constants | Actual manager/state-message regressions; host and required module checks |
| [#362](https://github.com/p2pKit/P2pKit/issues/362) | Android initializer KDoc falsely promises legacy fallback under secure defaults | Correct documentation, preserve fail-closed runtime; Dokka/docs checks |
| [#363](https://github.com/p2pKit/P2pKit/issues/363) | First iOS incoming offer lacks visible Accept/Reject controls | Actual view-state regression and supported simulator UI checks; physical consent stays separate |
| [#364](https://github.com/p2pKit/P2pKit/issues/364) | Interoperability criterion confuses security profile with optional features | Current-caller documentation correction; #133 external campaign remains NOT_STARTED |
| [#365](https://github.com/p2pKit/P2pKit/issues/365) | iOS catalog requests bare fingerprint in full pairing-QR field | Correct recipe and parser/sample contract; preserve physical/scoped-IPv6 acceptance |
| [#366](https://github.com/p2pKit/P2pKit/issues/366) | Android URI KDoc recommends unavailable JVM-only overload | Android-supported recipe/consumer compile checks; no runtime/API weakening |
| [#368](https://github.com/p2pKit/P2pKit/issues/368) | API24 export-failure fixture obstructs raw instead of normalized target | Summary-derived target, exact-string invariant, raw-ID mutation, diagnostics and full gates; independent review |

#361–#366 and #368 are Low pending repairs; their discovery did not execute physical/device campaigns.
#368 has fresh Linux failing-host evidence, not a production exporter failure. #367 has the bounded source
approval above, with foreign-host acceptance still NOT_EXECUTED. Every next repair requires sequential
implementation and fresh independent final-revision review. Investigation is not repair approval.
GitHub Actions is authorized for supported Mac/Windows/Apple gates; physical devices, hostile networks,
independent implementations and professional crypto remain separate acceptance.

## Provenance and scope

These small, safe records are curated from the surviving checkpoint and public GitHub issues/outcome comments.
Issue assessment text describes the time it was recorded, including then-local fixes and then-pending integration.
Some original raw evidence and the initial file-by-file ledger were lost. Later private logs/manifests are not Git
deliverables. Neither recovered summaries nor absent historical artifacts are fresh verification or passing gates.

Read each issue's complete body, comments, linked PRs and prior decisions on GitHub before correcting it. Local evidence
paths from earlier reports are deliberately not presented as links that would resolve in a new clone. If old raw
artifacts are necessary, request the private backup; otherwise run fresh, scoped verification and retain new evidence.

Coverage rows preserve the last recorded scoped assessment at their recorded revisions. This is not complete current
coverage: later changes invalidate affected paths/callers; the original full audit must be corroborated before final
completion. The #145 and #367 repairs have exact scoped reviews above; the inherited #144/#360, #359, #358, #137, #130, #332 Apple,
#356, #229, #357, #226, #225, #208, #152, #133, #355, #187, #190 and #325 paths retain historical review records;
other domains still need current corroboration. The inherited transfer ledger inventoried **1,038 paths with
334 recorded blob bindings**; those figures are historical, not a new current-tree aggregation. Changed paths
and actual callers must be reopened/rebound whenever revisions advance. #367 metadata review is full-diff and
affected-subtree scope, not full-file XML text review. Administrative updates do not inherit a current read/hash
binding from their inputs. Inventory, hashing and structural parsing are not completed semantic review.
Added handoff documents are inventory entries, not runtime-verification claims.

The expanded coverage projection preserves all **5,190 cells in the five historical columns** and
adds nine read-scope/provenance columns. It uses source-reading context `c221d54` (1,044 source paths),
plus the actually read new #367 report: **1,045 projected paths**. It records **777 full-text**,
**259 structural-only**, **one semantic-delta**, **one partial XML**, **six reopened administrative**
paths and **one self-excluded coverage output**. Six changed ledgers retain historical full-read
input bindings; independent complete-delta review is not a full reread of their new bytes. The two
#368 test-file reads at `c221d54` are source inspection, not #368 repair approval or execution evidence.
This differs from the older `0d88be3` input map (783 full-text including the old coverage input)
and its earlier generated output (782 full-text plus self-exclusion). No final administrative commit,
self-hash or complete current semantic review is inferred. Private receipt names are provenance
identifiers, not links or raw evidence transferred by cloning. These scope counts do not alter
the 69/182 repository-repair denominator or retarget #367 verification to newer #368 executions.

## Maintaining cloneable progress

After each issue's final independent review, update checkpoint totals, issue disposition/commits/outcome URLs and
affected coverage entries. Bind each new summary to exact commits, commands, results, review verdicts and external gaps.
Commit source/tests separately from administrative checkpoint updates; push only the authorized audit branch.
Do not mark an issue complete simply because an unfinished checkpoint was committed or a push succeeded.

Never commit raw diagnostic payloads, credentials, personal device identifiers, local SDK paths, generated build
artifacts, caches or transfer archives. Keep them out of issue comments too. Store safe textual summaries here and
private raw verification in an ignored, durable directory. Preserve the original stashes/backups on the source device;
Git cloning does not transfer them and they are not required for the current continuation.
