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

## Deliberately retained

| Branch or ref | Tip | Unique commits relative to `main` | Reason retained |
| --- | --- | ---: | --- |
| `diag/issue-10-addServiceListener-timing` | `100b049f4a9df1e7d1ac279be72823f69d9f4736` | 1 | Unique diagnostic work; local and remote refs retained. |
| `diag/issue-10-p3-measurement` | `d778b3338cf3c92f3fad02d74711d604e54b7ef2` | 2 | Unique local diagnostic work. |
| `diag/issue-21-android-discovery-trace` | `ea436b9b2a16bb7f13295d0a8f79599248f2ab10` | 5 | Unique local diagnostic work. |
| `fix/issue-19-ios-auto-mesh` | `03fa81451af4db5c41ff2a0bd527ff6ff464a59d` | 2 | Unique fix work; local and remote refs retained. |
| `fix/issue-45-manual-peer-ids-thread-safe` | `6f45d5369f6b3a5e103f1f530d225ac2ad1c3d46` | 1 | Unique fix work; local and remote refs retained. |
| `perf/issue-20-android-startup-lock` | `3e2b4d8877a719fd5cb709700c57548fdae11499` | 4 | Unique performance work; local and remote refs retained. |
| `v0.6-dev` | `ea436b9b2a16bb7f13295d0a8f79599248f2ab10` | 5 | Contains unique unmerged history; local and remote refs retained. |
| `stash@{0}` | `5ae6b82201e631ec9966742284aff7e8d46b1ff0` | not a branch | User work was left untouched. |
| active Dependabot branches | varying | automated open updates | Left for their pull-request lifecycle. |

Published tags, including `v0.7.0-rc1` and `v0.7.0-rc2`, were not moved,
deleted, or rewritten.
