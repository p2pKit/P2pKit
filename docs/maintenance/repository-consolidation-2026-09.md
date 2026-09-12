# Main consolidation and Mac handoff — 2026-09-12

This is a dated preservation/cleanup record, not product or release qualification.
Use the [Mac handoff](../testing/mac-handoff.md) and [current audit checkpoint](../../AUDIT_CHECKPOINT.md).
GitHub remains the live source for branches and PRs; the inventory below binds the inspected tips.

## Integrated history

The owner authorized consolidation into `main`, normal pushes and deletion of obsolete
branches after preservation. The clean starting checkout had no stash or other worktree.
All nine remote heads were fetched without pruning; the single-branch clone's **local**
fetch mapping was expanded to all heads. No repository settings were changed.

`main` at `eb444cccfc290be5435c5c10629c24183293606f` is an ancestor of the audit
tip `85c72e530d2881f8a7387c665d8331c553e5d26f`, tree
`2d9b7db68f5a2cbc2403193949c1d323029cee8a`. The fast-forward retains all **310**
audit commits, without squash, conflict resolution, cherry-pick or rewritten history.
It includes the source, tests, native candidates, vendor/dependency state, release
tooling, independent review records and acknowledged failures—not just approved rows.

Product verification remains bound to its original sources, including latest product
change `7d21aef17712671b9a0577ab6c24115710dada82`, not to a new cleanup execution.
No pending dependency upgrade is applied merely to retire a branch.

## Branch dispositions

Retirement is permitted **only after** a normal main push and remote SHA/tree/ancestry
verification. Recheck the remote head at deletion; an advanced tip requires renewed
inspection. No force-push or tag change is part of this plan.

| Branch | Inspected tip | Disposition / preservation |
| --- | --- | --- |
| `main` | `eb444cccfc290be5435c5c10629c24183293606f` | Sole integration/continuation trunk; advance by fast-forward plus consolidation commits. |
| `audit/complete-2026-09-04` | `85c72e530d2881f8a7387c665d8331c553e5d26f` | Retire after main verification: every commit is an ancestor of main. |
| `dependabot/github_actions/google/osv-scanner-action/dot-github/workflows/osv-scanner-reusable.yml-2.5.1` | `a5172023da2bdc4dd36d0b8197929a0d14e3cf22` | Retire as obsolete, not merged: #388 replaced this upstream workflow dependency. Complete unique edit preserved below. |
| `dependabot/github_actions/actions/setup-java-6.0.0` | `d78c007797056649e66bd6f8e201c84f1ba7e525` | **KEEP / NOT_APPLIED**, [PR #319](https://github.com/p2pKit/P2pKit/pull/319): six setup-java pins in five old-base workflows, 5.7.0 → 6.0.0. |
| `dependabot/gradle/org.cyclonedx.bom-3.4.0` | `e9c101c49922c1de142f1b0355776a025e05538e` | **KEEP / NOT_APPLIED**, [PR #95](https://github.com/p2pKit/P2pKit/pull/95): actual proposal is **3.4.1**, despite branch name; main uses 3.4.0. |
| `dependabot/gradle/org.jetbrains.kotlin-kotlin-metadata-jvm-2.4.10` | `9f64b120f233e27dd88f2aa21a4db79ca3f5ff16` | **KEEP / NOT_APPLIED**, [PR #106](https://github.com/p2pKit/P2pKit/pull/106): Android ABI metadata reader 2.3.21 → 2.4.10, not the Kotlin compiler. |
| `dependabot/gradle/org.jetbrains.kotlinx-kotlinx-io-core-0.9.1` | `eb98196ebb8b5ca7e31fef960edfba00512212a5` | **KEEP / NOT_APPLIED**, [PR #97](https://github.com/p2pKit/P2pKit/pull/97): published KMP runtime 0.9.0 → 0.9.1. |
| `dependabot/gradle/org.ow2.asm-asm-tree-9.10.1` | `4d2ffd064dcc5afd492f68a4190e54b02dd6c852` | **KEEP / NOT_APPLIED**, [PR #108](https://github.com/p2pKit/P2pKit/pull/108): **both** ASM and ASM-tree 9.9.1 → 9.10.1 in ABI tooling. |
| `dependabot/gradle/org.slf4j-slf4j-nop-2.0.18` | `e021dadeea80ded010fa4b9e9d248a159560d49c` | **KEEP / NOT_APPLIED**, [PR #107](https://github.com/p2pKit/P2pKit/pull/107): runtime 2.0.13 → 2.0.18. |

Each bot branch has one unique version-only commit, no matching patch in audit history,
and no accompanying lock/checksum qualification. Historical August greens are not current
audit-composition validation; several proposals also have failed full gates. PR #95/#97
have explicit owner retention/qualification comments. Keep these six branches/PRs until
separate artifact, affected-platform and consumer review; their work is **visible here,
not silently integrated, lost, or represented as approved**.

### Complete obsolete #109 change

Parent: `6d97169d9d8f12480e88077b63c09b8df3b9845f`; only changed file:
`.github/workflows/osv-scanner.yml`. The entire semantic change was:

```diff
-    uses: google/osv-scanner-action/.github/workflows/osv-scanner-reusable.yml@8deb546fdb875b9996d27d4950be7312dac076a1 # v2.5.0
+    uses: google/osv-scanner-action/.github/workflows/osv-scanner-reusable.yml@6e4298ebc4db23e847df9b2e2de2939d6f066c67 # v2.5.1
```

Audit commit `eea101d47aab6aef1c549e4f94dc6cda333f43a0` replaced that dependency
with the local fail-closed reusable workflow and checksum-admitted standalone scanner.
Restoring the removed upstream action is not an upgrade of the standalone scanner.
The obsolete tip is **not** claimed as an ancestor or a patch-equivalent merge.

## Working-tree cleanup and preservation

- Removed **2,518 lines / 252,944 bytes** of repeated historical tails from
  `AUDIT_CHECKPOINT.md` and audit `README.md`, `followups.md`, `issues.md`, before
  adding concise history/navigation pointers. Kept the four paths and six historical
  anchors used by nine retained repair-report links.
- Retired the rejected, zero-reuse July draft
  `docs/archive/remediation/2026-07/review-campaign/CODEBASE_FINDINGS_2026-07.OPUS-PROVISIONAL.md`
  (**72,705 bytes**). Blob `3b373a91827bbdacfb1ce59fd0707038ba2e56f3`, SHA-256
  `b1ba95d0001ca1ecd280f9b952d514fbfa6864878a6243dad24245507db303a4`.
  Its archive index now points to the immutable original; accepted findings are untouched.
- No module moves, project/artifact renames, lock edits, dependency changes, API-baseline
  changes or product behavior edits. `AGENTS.md`, `CLAUDE.md`, all three exact-byte
  protected archives, source, scripts, test fixtures, release records and legal notices stay.
- Kept complete structured checkpoint/issue history, substantive repair/hosted reports,
  233 original July XML reports (including failures) and 17 original binary evidence files.
  These are provenance, not disposable live build outputs. Changed coverage rows describe
  only consolidation deltas; earlier row bindings remain at the preservation commit.
- Added one current Mac handoff and this branch/preservation record. No private raw
  evidence, credentials, machine settings, caches or generated packages belong in Git.

All retired working-tree files and narratives remain in the **reachable main ancestor**
`85c72e530d2881f8a7387c665d8331c553e5d26f`, not an unreferenced stash or a new tag:

```bash
git show 85c72e530d2881f8a7387c665d8331c553e5d26f:AUDIT_CHECKPOINT.md
git show 85c72e530d2881f8a7387c665d8331c553e5d26f:docs/audit/2026-09-04/coverage.tsv
git show 85c72e530d2881f8a7387c665d8331c553e5d26f:docs/archive/remediation/2026-07/review-campaign/CODEBASE_FINDINGS_2026-07.OPUS-PROVISIONAL.md
```

Use a full-history clone. A shallow checkout must obtain the relevant history before
these retrievals; never reset over local work. Earlier missing private raw evidence
remains missing—Git-backed cleanup cannot manufacture it.

## Automation and remaining acceptance

Normal main CI, OSV, dependency submission and native Intel scheduling remain operative;
main push is not a release trigger. The four historical audit workflows retain their
old branch/path/admission contracts and gain job-level deletion guards. This avoids
runner allocation for a deletion event using these definitions, not a guarantee that
GitHub creates no run record. Observe real Actions after main push and branch retirement.
Do not retarget those workflows to main or emulate their hosted identity on a Mac.

The audit remains **NOT_READY**: **206/234 approved repairs (88.0%)**, **207/234
resolved (88.5%)**, **27 unresolved (11.5%)**. #409/#410/#413 and current strict
locks/native/ABI/release gates remain; 21 external rows and three owner decisions
stay deferred. #133 is NOT_STARTED. OSV is **EXCEPTED_NOT_FIXED**, expiring
2026-10-31; affected Kotlin 2.4.10 is not fixed by this consolidation.

Check documentation/layout, protected-byte/whitespace integrity and the affected
workflow policy for consolidation. Do not replay expensive unchanged product tests
for a documentation cleanup or promote an inherited failure to PASS. Full Mac
qualification is the next campaign, not a prerequisite invented to delete duplicate prose.
