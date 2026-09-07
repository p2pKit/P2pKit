# Comprehensive audit continuation ledger

Start with the root [continuation checkpoint](../../../AUDIT_CHECKPOINT.md). Clone the
`audit/complete-2026-09-04` branch, not just the default branch, to obtain the reviewed source and these records.

## Records

- [Checkpoint metadata](checkpoint.json): source revisions, issue-count denominator and evidence limitations.
- [Issue index](issues.md): all 171 inventoried open issues grouped by checkpoint disposition.
- [Issue records](issues.json): reported scope, dependencies, recorded commits and public investigation/outcome links.
- [Coverage ledger](coverage.tsv): inherited per-path review claims, provenance revisions and reopened work.
- [Unverified follow-ups](followups.md): hypotheses needing reproduction and deduplication, not confirmed bug claims.

The inventory snapshot is a continuation aid, not GitHub's live state. It contains 61 repository repairs with recorded
independent approval, 88 pending repairs, 21 external-validation items and one architecture decision: **35.7% reviewed
repository repairs, 64.3% remaining issue rows**. These percentages do not count external acceptance still attached
to approved rows (including #133); independent interoperability remains separately pending. Thirty-eight entries
originated in the audit. Branch availability does not imply merge/release or a new verification result.

#332's complete four-file Apple follow-up is approved/pushed at `78ef361`, tree
`0f8ab1465d257baac8110e3bd1ecf95859abe93c`. Invalid current-browser re-resolution withdraws only the admitted native
service's cache, endpoint and relay ownership; stale callbacks, manual hints and existing dial/session ownership
remain independent. Full check/Android assembly: **2,387 passes, zero failures/errors, one unchanged manual skip;
290 XMLs, 246 tasks**. Twenty transition methods/both profiles, 480 focused LAN passes/one manual skip, eight mutation
controls and fourteen static gates establish the scoped correction. The reviewer verified 1,992 sealed entries and
28 finalized cleanup receipts. See [the Apple report](repairs/332-apple.md). The reopened row returns to approved,
not a duplicate/new completed issue; prior JVM/Android approval remains intact. The planned next issue is #130;
read its complete history before repair. Native-input/control-state tests are not live multicast/TCP-handshake proof.

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
completion. The #332 Apple, #356, #229, #357, #226, #225, #208, #152, #133, #355, #187, #190 and #325 paths have scoped final review records;
other domains still need current corroboration. The ledger inventories **1,024 paths with 321 recorded blob bindings**;
inventory is not equivalent to completed review.
Added handoff documents are inventory entries, not runtime-verification claims.

## Maintaining cloneable progress

After each issue's final independent review, update checkpoint totals, issue disposition/commits/outcome URLs and
affected coverage entries. Bind each new summary to exact commits, commands, results, review verdicts and external gaps.
Commit source/tests separately from administrative checkpoint updates; push only the authorized audit branch.
Do not mark an issue complete simply because an unfinished checkpoint was committed or a push succeeded.

Never commit raw diagnostic payloads, credentials, personal device identifiers, local SDK paths, generated build
artifacts, caches or transfer archives. Keep them out of issue comments too. Store safe textual summaries here and
private raw verification in an ignored, durable directory. Preserve the original stashes/backups on the source device;
Git cloning does not transfer them and they are not required for the current continuation.
