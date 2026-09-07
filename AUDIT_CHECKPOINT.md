# P2pKit audit continuation checkpoint

**Updated: 7 September 2026. Work in progress, not a release approval.** The owner authorized pushing the local
audit work and continuing remediation. This tracked handoff replaces the earlier private archive-only instructions.
Read it together with the unchanged `AGENTS.md` and `CLAUDE.md`.

## Resume from a fresh clone

```bash
git clone --branch audit/complete-2026-09-04 https://github.com/p2pKit/P2pKit.git
cd P2pKit
git status --short --branch
git rev-parse HEAD 'HEAD^{tree}'
git log -5 --oneline
```

Use **this branch**: a default clone checks out `main`, not the unfinished audit. In an existing clean clone, fetch
and switch to the remote audit branch without resetting local work. Do not force-push, change the default branch,
merge unfinished work, move published tags or publish releases as part of continuation.

The clone includes source changes, repair commits, the current draft and the small
[audit ledger](docs/audit/2026-09-04/README.md). No archive or patch application is needed to resume coding.
Open your coding agent in this directory and give it the prompt at the end. This transfers documented working context,
not an account login, a native chat export, running agents or build processes.

## Exact checkpoint and progress

- Repository: <https://github.com/p2pKit/P2pKit>.
- Audit branch: `audit/complete-2026-09-04`; not merged into `main`.
- Last inherited independently reviewed source revision: `32dc5c03658145741c6e23cdfec3c14cd2eba5e7` (#352).
- Its tree: `a6144952d3592b6e189114bc73822d0af1ab0853`.
- Unfinished #337 draft preserved unchanged in **`eb564e9487f2887f83f519575c82d4e7657864cb`**.
- Draft tree: `69161ac65e02bbf33d390bde2575d3131a9d7996`.
- The draft is committed for transfer, **not compiled, tested or independently approved after its last edits**.
  Documentation commits can follow it; record actual `HEAD`, tree and working changes before verification.
- Machine-readable state: [checkpoint.json](docs/audit/2026-09-04/checkpoint.json).

| Disposition at this checkpoint | Count | Percentage of 167 inventoried issues |
| --- | ---: | ---: |
| Repairs with recorded independent approval | **46** | **27.5%** |
| Pending repairs, including #337 | 99 | 59.3% |
| External/platform validation | 21 | 12.6% |
| Architecture/product decision (#120) | 1 | 0.6% |
| **Total remaining** | **121** | **72.5%** |

These percentages count issues, not engineering effort, file coverage or production readiness. A GitHub refresh on
7 September found 274 issues across all states and the same 167 open issues as the previous snapshot. The ledger
identifies 34 new-audit issues. Refresh live issue bodies, comments, timelines and linked work before relying on an
entry. Historical assessment wording records its original local phase; branch availability does not imply a merge.

The 46 recorded repairs are in this branch's history; issues remain open pending the appropriate merge/completion
policy. A push is not a new verification result. This handoff does not close issues or claim production readiness.
See [every issue and its disposition](docs/audit/2026-09-04/issues.md) and
[public investigation/outcome links and commit references](docs/audit/2026-09-04/issues.json).

## Completed work and inherited verification

Recorded repair/review cycles include dependency/provenance/publication gates, coroutine cancellation and ownership,
LAN rebind/cleanup and invalid-peer handling, secure-v2 tests, provisioning callbacks, sample pairing/privacy,
file-source/destination safeguards, session diagnostics, Android API24/25 diagnostics and iOS integration.
These are scoped repairs, not proof that every problem in those areas is resolved.

Latest completed #352 corrected selective diagnostic clearing, retained-session preservation and truthful storage
failure reporting. Its five-commit series ends at `32dc5c0`. Earlier review findings were corrected and a fresh
independent final reviewer approved the complete 26-file range. The
[posted outcome](https://github.com/p2pKit/P2pKit/issues/352#issuecomment-5562438288) records its verification.
That approval **does not cover #337**.

| Inherited evidence at final #352 inputs | Result and limitation |
| --- | --- |
| Clean integrated `./gradlew check --console=plain` with strict/bounded options | 2,173 passed, 0 failed, 1 existing manual skip; predates #337 |
| Focused Kotlin checks | 223 passed; overlaps integrated counts |
| Xcode26.5 / iOS26.5 arm64 simulator XCTest | 46 passed; not physical Apple hardware |
| Android assembly/lint, CLI packaging, specified XCFramework/static gates | Recorded PASS for those exact inputs; not a current-tree pass |
| #337 extracted pre-correction tests | Two expected stale-card assertion failures; not untouched-baseline execution |
| Current #337 draft | **NOT RUN / NOT REVIEWED** |

Do not add overlapping test totals together. Neither simulator success nor compilation proves physical-device,
hostile-network, power-loss durability or independent cryptographic assurance.

## Evidence continuity and intentionally excluded local files

Some original raw audit evidence and the original file-by-file ledger were lost before this checkpoint. Surviving
commits, GitHub outcome comments and recovered records preserve context, but reconstructed outcomes are not original
raw logs or fresh independent verification. The [coverage ledger](docs/audit/2026-09-04/coverage.tsv) preserves dated
review claims and reopened paths, not complete current-tree corroboration. Repeat affected verification and corroborate
the entire repository before declaring the audit complete.

This public repository deliberately excludes `.audit-evidence/`, private diagnostic payloads, local settings,
credentials, shared caches, archives, binary reports and historical stashes. Originals remain on the source device
and in private backups; no local evidence was deleted to publish this handoff. A clone has enough source and context
to continue, but cannot independently recheck historical artifacts that were not published. Run fresh checks or
request specific private evidence if needed; do not invent passing results.

The historical #196 adapter stash is superseded by later reviewed adapter/provenance work in this branch. The old #21
diagnostic trace experiment is intentionally private and is not required for current #337 work. Neither stash was
dropped or pushed; do not blindly apply either over reviewed code. Authenticate GitHub and the coding agent normally
on the new device rather than copying token stores or SSH keys.

## Finish #337 first

[#337](https://github.com/p2pKit/P2pKit/issues/337) reports Android provisioning cards retaining success after an OS
hotspot stop or joined-network release. The ViewModel cached one-shot results without observing manager lifecycle
events/state, leaving credentials/endpoints or a live routing claim visible after resource loss. Manager-side #198
did not fix this sample consumer. Preserve #324's credential behavior.

The unfinished source is already committed in these three paths:

```text
samples/p2p-sample-android/src/main/java/dev/p2pkit/sample/android/P2pKitViewModel.kt
samples/p2p-sample-android/src/main/java/dev/p2pkit/sample/android/ProvisioningUiState.kt
samples/p2p-sample-android/src/test/java/dev/p2pkit/sample/android/ProvisioningUiStateTest.kt
```

Only the two initial tests exist. The pre-correction extraction compiled and both assertions failed as expected;
the subsequent controller draft has not been run or reviewed. Commit `eb564e9` is preservation, not remediation.
Re-read the full #337/#198/#324 discussions and actual public contracts, Android manager publishers and UI callers.

Remaining design work and regression requirements:

- Manager snapshots are **last-owner publications, not a resource inventory**. Hotspot and join can coexist, including
  repeated starts; snapshot-only live confirmation is insufficient when the other resource owns the latest snapshot.
- Terminal signals can precede successful returns. Queued old events/results must not resurrect ended resources,
  including across retries and kit replacement. Verify subscription timing and both terminal-before-result paths.
- `joinDismissed` currently does not fence publication. Define/test established-join dismissal and late completions;
  dismissal must never release the network. Pending, busy state and enabled independent controls must agree.
- Test cancellation before dispatch, during acquisition and during finalization. Do not depend on cancellable `yield()`
  to clear busy state. Old-run callbacks/finalizers must not modify a replacement run.
- Repeat-join refusal is not resource release. Untagged `CleanupFailed` can concern a retired resource; unknown network
  state alone cannot identify which resource ended. Neither should erase another live card.
- Preserve ephemeral/masked passphrases, clearing on genuine success/stop/disposal and no permission-result auto-join.
  Preserve native cleanup ownership; do not invent a leave-network API or infer native acknowledgement from an event.
- Cover manager close, parent cancellation, repeated controls, coexistence, failures, event/state ordering, dismissal,
  Pending, busy cleanup and actual ViewModel wiring. Sample-state tests are not rendered UI, ART or hardware tests.

Run focused sample/provisioning/#324 regressions and affected Android assembly/lint with unconditional cleanup. Freeze
the whole issue diff against `32dc5c0`, **including** the preserved draft commit, for a fresh independent reviewer.
Resolve and re-review every actionable finding before counting #337 as fixed or advancing to another issue.

## Continue the full audit and repair queue

1. Read `AGENTS.md`, `CLAUDE.md`, this handoff, the complete issue ledger and
   [unverified follow-ups](docs/audit/2026-09-04/followups.md). Preserve all existing user changes.
2. Record exact branch/commit/tree/status and refresh full GitHub issues/comments/linked PRs. Reconcile new evidence
   by underlying cause, not similar titles. Use exact local drafts if access is unavailable; never claim remote writes.
3. Continue all actionable issues sequentially, prioritizing severity/dependencies. After #337, known candidates are
   #317 (read related closed #294) and #325 (SDK prerequisite inconsistency; **do not edit protected `AGENTS.md`**).
4. Track verified distinct discoveries with severity, platforms, paths/lines, reproduction, root cause, impact,
   correction and regression plan. Respect `SECURITY.md`. Keep suspicions separate; do not duplicate existing issues.
5. For every issue: confirm behavior/callers, fix the whole root cause, add meaningful regressions, run focused checks,
   and **create a fresh independent reviewer agent** with the full issue/diff, context and raw evidence. Require a
   clear evidence-backed verdict. Address findings and review the final revision before the next issue. If independent
   agents are unavailable, report that limitation; self-review is not a substitute for the owner's requirement.
6. Update the tracked checkpoint/issue/coverage ledgers and GitHub with verified outcomes. Keep raw evidence private,
   publish only safe summaries, and distinguish branch fixes from merged/released fixes. Keep continuation checkpoints
   on the audit branch; no force-push, merge, release or issue closure is implied by the push authorization.
7. Finish with fresh whole-repository corroboration, `./gradlew check --console=plain`, applicable sample/isolated-consumer
   builds and inspected `scripts/run-release-gate.sh` gates. Do not skip or weaken checks to make the result green.

Review implementation, APIs, lifecycle, concurrency, flows, platform LAN/provisioning, sessions/reconnection, protocol
limits, authentication/identity, file integrity/durability, consumer integrations, build/release configuration, tests
and docs. Missing internet signaling, NAT traversal, relays, accounts, rooms or application-level authorization are
not automatically defects outside the documented scope. Keep unavailable hardware/product decisions accurately pending
while completing feasible work on the rest of the queue.

## Toolchain, resource control and device limits

- Inspect checked-in configuration before building. Current wrapper: Gradle9.7.0; Kotlin2.4.10; AGP9.3.1.
- Use JDK17 for the documented launcher/library contract; `gradle/gradle-daemon-jvm.properties` separately requests
  JDK21. Libraries compile against Android Platform36; the sample needs **Platform37**, as tracked by #325.
- Configure local SDK paths and authenticate on the destination. Do not commit personal paths or copy shared caches.
  Inspect scripts and prerequisites before executing them; private old helpers were machine-specific, not portable tools.
- Serialize builds. Use at most two workers, `--no-parallel`, strict dependency verification and bounded memory.
  Coordinate reviewers as source/evidence-only so they do not run competing builds.
- After **every** build/test, including failure/cancellation: preserve required evidence; run the applicable wrapper's
  `--stop`; stop only invocation-owned survivors; then remove confirmed disposable generated outputs after dependent
  validation no longer needs them. Use unconditional finalization, not success-only cleanup. A dedicated work account
  or task-scoped `GRADLE_USER_HOME` prevents `--stop` from disturbing unrelated daemons.
- Never blanket-kill Java/Gradle or recursively delete every `build` directory:
  **`buildSrc/src/main/java/dev/p2pkit/build` is source**. Preserve shared dependency caches, user settings, `.git`,
  private evidence and artifacts needed for active validation. Apply the same discipline to consumer/Apple builds.
- Linux can perform supported JVM/Android host/static checks, not Xcode/iOS simulator/XCFramework checks. Use an
  authorized Mac for Apple gates. Record actual platform coverage; unsupported checks are not passes.
- Physical Android/Apple devices and OEM/API24-25 ART behavior, hostile networks, headful UI/accessibility,
  other-host filesystems, independent secure-v2 interoperability and professional cryptographic review remain external.

Overall status: **NOT PRODUCTION READY**. Report exact commits/state, issue dispositions, fix/review evidence,
verification scope, blockers, cleanup and practical readiness limits at each handoff.

## Prompt for the next agent

> Continue the complete P2pKit audit from AUDIT_CHECKPOINT.md and docs/audit/2026-09-04/. Verify the audit branch,
> current commit/tree/status, read repository instructions and full GitHub issue histories, and preserve user work.
> The inherited checkpoint has 46/167 reviewed repairs (27.5%) and 121 remaining (72.5%). The committed #337 draft
> is unfinished and untested after its last edits; finish it first, including all preserved draft changes in review.
> Work sequentially through every actionable issue with meaningful regressions and a fresh independent reviewer after
> every fix. Resolve/re-review all findings. Serialize bounded builds and always stop owned workers and clean only
> disposable outputs. Track safe outcomes in Git so another clone can resume, keep raw/private evidence out of Git,
> and distinguish pushed branch work from merged/released work. Do not claim unavailable platform or external gates passed.
