# Branch cleanup record — 2026-08-08

This record captures the non-destructive branch cleanup performed after pull
request #59 was merged into `main` as
`98a210e3572ad59b9256cf2ba3113f7b9a912099`.

The audit used fetched remote refs immediately before deletion. A branch was
eligible only when its exact tip was an ancestor of `origin/main` and
`git rev-list --count origin/main..<tip>` returned zero. No branch with unique
work was removed, no tag was changed, and no history was rewritten.

## Removed merged branches

| Branch | Remote tip before deletion | Relationship to `main` | Preserving tag or ref | Reason removal is safe |
| --- | --- | --- | --- | --- |
| `audit/exhaustive-review-2026-06` | `28086e2dca63c130ea6d4804f715d91888290f06` | ancestor; 0 unique commits | `v0.7.0-rc1`, `v0.7.0-rc2`, and `main` | Fully integrated audit history. |
| `chore/jmdns-loopback-macos-flake` | `564e150458f30f59b745f99b211695bd0ae4f593` | ancestor; 0 unique commits | `v0.7.0-rc1`, `v0.7.0-rc2`, and `main` | Fully integrated test-stability correction. |
| `remediation/full-register-2026-07` | `28443675b2b27361732fe565475953868776900b` | ancestor; 0 unique commits | `main` | Tip was the pre-cleanup `main`; all remediation history remains reachable from `main`. |
| `v0.2-dev` | `a9d683dda21244e19a1cc437a4229f48eebf26f9` | ancestor; 0 unique commits | `v0.2-internal` and later release-history tags | Superseded development line with tagged and merged history. |
| `v0.2.1-dev` | `1465a7a83ef4abcaf5fcfcf36c9de4ace5e4b917` | ancestor; 0 unique commits | `v0.4-internal` and later release-history tags | Superseded development line with tagged and merged history. |
| `v0.2.2-dev` | `0d99695992d5bffe9b7f06e252d2d9ee41295d1a` | ancestor; 0 unique commits | `v0.4-internal` and later release-history tags | Superseded development line with tagged and merged history. |
| `v0.3.0-dev` | `0bc3c29416b65c1d137e68b2d89eea395035a730` | ancestor; 0 unique commits | `v0.4-internal` and later release-history tags | Superseded development line with tagged and merged history. |
| `v0.4.0-dev` | `21216e44197d6227e6620ff163e0cdda66fc769c` | ancestor; 0 unique commits | `v0.4-internal` and later release-history tags | Superseded development line with tagged and merged history. |
| `v0.5.0-dev` | `1f93d666c0aa7d1517aff25999c91c0bcd5727b6` | ancestor; 0 unique commits | `v0.5-internal` and later release-history tags | Superseded development line with tagged and merged history. |
| `v0.5.1-dev` | `5fcabc4b7b37e0cbddbe9a41470339015c7f9d2f` | ancestor; 0 unique commits | `v0.5.1-internal` and later release-history tags | Superseded development line with tagged and merged history. |
| `chore/repository-cleanup-2026-08` | `ecc0df9b81b6a2e79d26031e943426c2e7ff0d34` | ancestor; 0 unique commits | merge commit `98a210e3572ad59b9256cf2ba3113f7b9a912099` | Pull request #59 was merged and its remote branch was deleted by GitHub. |

Matching local branches were deleted with `git branch -d` where they existed.
The local remediation branch had the later ancestor tip
`c1161d0b7dda4827069763c3cd039bd5aa073ce2`; it also had zero commits outside
`main`, so its local name was safe to remove.

## Final consolidation audit

The branches initially retained above were re-audited file-by-file against
`main` at `e6091eeeff1d86aad266bf2d43f33aa8e80e575e`. The left/right counts below
were captured after fetching/pruning on 2026-08-08. “Behind” counts are not the
reason for deletion; the unique behavior and its current replacement are.

| Branch | Tip and relationship to audited `main` | Unique work | Final decision and preservation rationale |
| --- | --- | --- | --- |
| `diag/issue-10-addServiceListener-timing` | `100b049f4a9df1e7d1ac279be72823f69d9f4736`; 173 behind, 1 unique | Five temporary `Log.d` timing markers in Android JmDNS listener registration; commit is explicitly diagnostic/not for merge. | **Delete local and remote.** Current structured diagnostics provide bounded, correlated lifecycle events. The exact commit/file/intent is preserved here; merging unbounded ad-hoc logging would regress diagnostic policy. |
| `diag/issue-10-p3-measurement` | `d778b3338cf3c92f3fad02d74711d604e54b7ef2`; 173 behind, 2 unique | Old “prefer Wi-Fi/Ethernet” initial bind patch plus the same five temporary markers. | **Delete local and remote.** Current `bestLanNetwork`, `AndroidLanNetworkState`, lifecycle coordinator, and selected-network socket factory implement the production correction more completely. The remaining issue-specific hardware work is tracked by issues #26/#28/#33. |
| `diag/issue-21-android-discovery-trace` | `ea436b9b2a16bb7f13295d0a8f79599248f2ab10`; 173 behind, 5 topology commits | The branch tip is exactly `v0.6-dev`; it contains no trace commit. The trace itself exists only in the retained stash below. | **Delete local branch.** It duplicates `v0.6-dev` and has no distinct evidence. Issue #21 remains open and its operational evidence procedure is in the Android handbook. |
| `fix/issue-19-ios-auto-mesh` | `03fa81451af4db5c41ff2a0bd527ff6ff464a59d`; 173 behind, 2 unique including its inherited issue-10 patch | Old iOS automatic-connect tie-break sample behavior. | **Delete local and remote.** The production library does not require sample auto-mesh, and the post-secure-v2 sample uses explicit authenticated/session controls and stronger diagnostics. Reapplying the old pre-v2 sample patch would conflict with later consent/authorization/UI architecture. PR #22 preserves authorship and discussion. |
| `fix/issue-45-manual-peer-ids-thread-safe` | `6f45d5369f6b3a5e103f1f530d225ac2ad1c3d46`; 172 behind, 1 unique | Synchronizes the former standalone `manualPeerIds` set. | **Delete local and remote.** Commit `ee2cae5` removed the split state and atomically stores manual/discovery contributions in `TrackedPeer`; focused `PeerRegistryTest` passed on 2026-08-08. Issue #45 and PR #46 were closed with this evidence; the PR preserves the contributor patch. |
| `perf/issue-20-android-startup-lock` | `3e2b4d8877a719fd5cb709700c57548fdae11499`; 173 behind, 4 topology commits | Wraps the old startup entrypoints in `Dispatchers.Default`, plus inherited issue-10 and iOS sample work. | **Delete local and remote.** Current `P2pKitImpl` owns a Default-dispatcher scope and a transactional, mutex-serialized feature lifecycle with rollback/cancellation semantics absent from the old patch. PR #24 preserves authorship/history. |
| `v0.6-dev` | `ea436b9b2a16bb7f13295d0a8f79599248f2ab10`; 173 behind, 5 topology commits (3 non-merge) | Historical issue-10 bind selection, PR #22 iOS sample change, and PR #24 startup change. | **Delete local and remote.** All useful root causes were incorporated or superseded by the 0.7 lifecycle, selected-network, secure-v2, and sample architecture. The merge PRs and this record preserve provenance; keeping an untagged divergent development line would imply unsupported 0.6 maintenance. |

### Final deletion execution

After this record and the consolidation candidate were preserved remotely in
[PR #60](https://github.com/p2pKit/P2pKit/pull/60), the five extant obsolete
remote branches were deleted: `diag/issue-10-addServiceListener-timing`,
`fix/issue-19-ios-auto-mesh`, `fix/issue-45-manual-peer-ids-thread-safe`,
`perf/issue-20-android-startup-lock`, and `v0.6-dev`. The two remaining audited
diagnostic names existed only locally. All seven local names in the table were
then deleted.

A fresh `git fetch --prune` and `git ls-remote --heads origin` confirmed that no
audited diagnostic, fix, performance, or `v0.6-dev` branch remained. At that
checkpoint, the only non-`main` remote branches were PR #60 and the live
Dependabot PR branches. PR #60 subsequently merged normally as
`0a6c6bac28f9f99bab96d3753992994b867d6dad`; GitHub deleted its temporary
branch. The superseded action-update branches were also removed. The final
remote branch set was `main` plus the five actionable Dependabot branches for
PRs #52–#56. No tag changed, and the issue-21 stash described below remained
present.

### Local diagnostic stash

`stash@{0}` (`5ae6b82201e631ec9966742284aff7e8d46b1ff0`) remains intentionally retained.
It contains 72 lines of uncommitted issue-21 Android trace instrumentation plus
obsolete `dev.p2pkit`/`0.6.0` publication edits. It is unsafe to merge and is not
part of the clean worktree/index, but it is the only surviving copy of the
original issue-21 diagnostic experiment. Keep it until issue #21's physical
validation is complete; do not apply its publication changes. This is a
concrete diagnostic-evidence retention reason, not a second development line.

### Automated dependency branches

Dependabot branches are not historical development branches. PR #49 merged;
the applicable updates from PRs #50, #51, #57, and #58 were integrated with
Dependabot authorship through PR #60, after which their redundant PRs closed
and their branches were removed. PRs #52–#56 remain open with their branches
retained because their acceptance gates have not passed. Their applicability
and exact blockers are recorded in
[`../maintenance/github-audit-2026-08.md`](../maintenance/github-audit-2026-08.md).

The temporary `cleanup/final-consolidation-2026-08` branch was used only for
[PR #60](https://github.com/p2pKit/P2pKit/pull/60) and was deleted after the
protected merge. No permanent development branch is retained beside `main`.

Published tags were not moved, deleted, or rewritten. In particular,
`v0.7.0-rc2^{commit}` remained
`90acb29583ea11d18685cf1315476756e7618245` throughout the audit.
