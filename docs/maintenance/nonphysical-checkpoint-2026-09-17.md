# Paused nonphysical integration — 17 September 2026

**Owner-requested preservation checkpoint, not acceptance or permission to
restart execution.** Implementation is stopped so work can resume on another
device. This dated record supplements, rather than rewrites, earlier results.
GitHub conversations remain authoritative for subsequent issue decisions.

## Source and navigation

Resume branch **`work/nonphysical-integration-20260915-022112`**, not an older
topic branch or main alone. The containing checkpoint commit preserves the WIP
below; its exact commit/tree and push readback are mapped in
[#437](https://github.com/p2pKit/P2pKit/issues/437). It is **not merge-ready**.

| Identity observed before checkpoint commit | Exact value |
| --- | --- |
| Fetched main | `3bc76f956f8f47447b51a62474fc878b9c43173c` |
| Main tree | `2a1105fde1d1ac299448489501e29d7a0d4a407a` |
| Latest reviewed source increment, already pushed | `3c2c6fe728ffdfe6fe3537dd6a468726f74f093e` |
| That increment's tree | `c5c1af13fecd249828ed7ea3b2de62a2334317e8` |

GitHub metadata refreshed **2026-09-17 15:35:54 UTC**: **77 open issues, seven
dependency PRs, no campaign PR**; the adjacent Actions queries found zero queued
and zero in-progress runs. This is not a new complete conversation census.
Keep proposals #95/#97/#106/#107/#108/#452/#453 and unrelated work untouched.

Read the [earlier issue/review map](nonphysical-continuation-2026-09-15.md),
[hosted results](hosted-ci-continuation-2026-09-16.md),
[held consume/delivery record](hosted-consume-delivery-2026-09-17.md), and each
issue's later comments. Old stale-lock and no-caller statements are dated:
accepted locks and consume-only source wiring already exist. Do not redo them.

## Most recent preserved work

- **#372:** commit `3c2c6fe728ffdfe6fe3537dd6a468726f74f093e` adds the
  ordinary-UID public-flag collector. Independent nonimplementing verdict:
  **APPROVE_EXACT_COLLECTOR_SOURCE_ONLY**, no actionable source finding.
  [Issue evidence and exact commands](https://github.com/p2pKit/P2pKit/issues/372#issuecomment-5716801081)
  and the [collector guide](../testing/android-lan-readback.md) distinguish
  **three executed synthetic parser tests**, **20 reviewer binding assertions**,
  and **20 authored but uncompiled/unexecuted Kotlin tests**. Original Markdown
  (510 links / 109 files), layout (10 projects / 15 negative controls) and
  whitespace checks passed. They were not rerun as Android evidence. No app/test
  build, Android API/filesystem execution or permission/runtime acceptance exists
  for this collector. #372 remains open; its production fix was not reimplemented.
- **#437; shared #424 prerequisite:** commit
  `8808cf2c3c14775785ca0cb81d30f63657d8f65b` connects ordinary consume/delivery
  source **behind both unchanged activation HOLDs**. Commands, selected model
  passes, independent findings and incomplete historical aggregate are in the
  linked delivery record. This is not a successful ordinary hosted run.
- **#437:** commit `8c9b70c23e1b283dfe1d51a145d162ab7afbcd45` adds dormant live
  save-set checks. **75/75 author offline controls** and **5/5 final independent
  controls** passed; the unchanged independent preimage was 3 pass / 2 fail.
  [Scoped independent approval and evidence](https://github.com/p2pKit/P2pKit/issues/437#issuecomment-5716306167)
  do not establish a cache producer, provider save/restore or resolver reuse.
  No production caller invokes `cache.export_snapshot` or `cache.save_set` yet.

## Exact unfinished source preserved, not approved

[`scripts/hosted_cache_bootstrap_identity.py`](../../scripts/hosted_cache_bootstrap_identity.py)
is the only implementation WIP added by this checkpoint:

```text
SHA-256 769e5de7725d95058bec54843fda631f979e9c1dd70a8e100596b37589be766b
Status: UNREVIEWED / UNTESTED / DORMANT / NOT_WORKFLOW_WIRED
```

Its proposed manual `cache-bootstrap` identity separates execution identity
from the Desktop/FULL cache cohort. It sketches six native selections, exact
source/tree and original-main recipient-policy binding, and a fixed future
`help --console=plain --no-configure-on-demand` configuration-only request.
These are authored source intentions, **not verified security properties**.
Admission cannot constitute product tests, FULL acceptance or cache population.

There is no CLI/caller, producer, cache action or downloader in this increment.
The named future `.github/workflows/dependency-cache-bootstrap.yml` **does not
exist**. Neither does `scripts/tests/hosted-cache-bootstrap-identity-test.py`:
an attempted combined test/document patch failed without creating those tests
or modifying the cache guide. **No syntax check, import, test or execution of
this WIP has been performed.** Do not infer approval from its checkpoint commit
or from any checkpoint-document accuracy review.

When the owner resumes source work, inspect this file first; add meaningful
identity/negative controls and obtain independent review before building on it.
The [cache contract](../testing/hosted-dependency-cache.md) still requires a
separate bounded bootstrap controller, original successful producer/same-home
stop/known retirement, export/freeze, provider save/probe and encrypted custody.
Do not insert a save tail into ordinary FULL or instantiate its controller with
`help`: its ABI/simulator/transcript obligations cannot be fabricated. The
earlier 5,400-second bootstrap allowance is only a proposal, not an admitted or
measured budget. The Windows native-file 900-second lifetime and 576MiB Snapshot
limit remain; that Snapshot cannot hold a 2GiB dependency cohort.

## Holds and remaining acceptance

- No local Java/Gradle/Xcode/application builds, SDK/dependency downloads,
  emulators/simulators, or held CI dispatches. Only small offline/source work
  and Git/GitHub metadata were used for this checkpoint. No merge, issue closure,
  release, tag/settings change or branch deletion is part of this pause.
- `.github/test-evidence-recipient.json` is absent. A named routine custodian,
  exact public key, finite 14-day policy, legitimate trusted-original-base
  bootstrap and formal approval are still required. Candidate source cannot
  authorize its own recipient. Native/provider/resolver/custody/delivery and
  measured scheduling acceptance remain unexecuted for the connected path.
- **Do not redo #424's accepted fixture work:** writer **35066719641/1** at
  `ef8c42b0eea20152870c6c0e1966c6601ce60f03` already passed CLI9/diagnostics23,
  with all six original exports independently inspected. Preserve that
  [accepted writer scope](https://github.com/p2pKit/P2pKit/issues/424#issuecomment-5694563485),
  not current ordinary-CI proof. Remaining acceptance is the current ordinary
  cache/custody/native/scheduling path and common delivery boundary. Cache
  preparation is only a shared prerequisite, not another fixture repair.
- #372 still needs the source-bound original command/profile coordinator,
  qualified runtime/loaded semantics, fresh no-Nearby install, denial/grant,
  authenticated bidirectional ordinary-LAN traffic and revocation/reentry.
  #317/#324 rendered/restoration acceptance is not supplied by this collector.
- Required `complete-gate`, `review`, `scan / osv-scan`, `osv-scanner`, formal
  different-account PR review and normal main merge/preservation are outstanding.
  Agent source review does not satisfy formal PR approval. Reconcile current
  main, meaningful source deltas and actual original evidence before any gate.
- Historical [successful sample preview](https://github.com/p2pKit/P2pKit/actions/runs/35070982169)
  retained APK/MSI/ARM64-DMG/DEB as **Actions artifacts expiring 30 September**,
  not main Releases. Do not rebuild or redownload that unchanged preview merely
  to recreate this checkpoint; it does not qualify later collector/custody code.
- All physical-phone criteria remain **DEFERRED_PHYSICAL_PHONE**. Protected-file
  permission (#325), owner decisions (#120/#274/#284), unavailable nonphone
  prerequisites and production publication authority (#151) remain separate.
  Do not request a phone campaign as a resume prerequisite.

Historical accounting stays **206/234 repair-approved**, **207/234 historically
resolved**, with no new credit from this checkpoint. Audit/release **NOT_READY**.
OSV remains **EXCEPTED_NOT_FIXED**: GHSA-r937-wjx7-w2jp / CVE-2026-53914,
affected Kotlin 2.4.10, expiry **2026-10-31**. No new scan, upgrade or exception
extension is claimed. Existing qualified byte reuse can save downloads; older
test results cannot qualify changed source without an applicable input review.

## Private originals and safe resume

Raw evidence remains on this Mac under
`$HOME/P2pKit-local-evidence/mac-nonphysical.bsdV1M/`, including:

| Packet | Purpose |
| --- | --- |
| `android372-collector-228q6gfi/COMMITTED.json` | Collector commit, exact diff and 22 source bindings |
| `review-android372-collector-gnZt2N02/REVIEW.md` | Independent collector report; SHA-256 `f077d62c4e4dcecb25bbcf680dbf89ed56f7789d2b3c957122441e50d15360d7` |
| `cache-save-set-llFNChMI` / `review-cache-save-set-u3ya8p10` | Original offline save-set results and independent review |
| `cache-bootstrap-identity-qtbn2ywz` | WIP input bindings; no WIP test evidence |
| `pause-checkpoint-vyqcmixh` | Checkpoint diff, command/push/readback evidence and local retirement records |

Public summaries/hashes are portable navigation, not substitutes for raw
originals. Transfer only selected necessary originals through the owner's
private channel and verify their recorded hashes. Never upload credentials,
keys, payloads, private raw receipts, caches, packages or old binaries to Git.
Missing originals must be recorded, not reconstructed or replaced by blind runs.
Observed free space was **11GiB (98% used)**; no cleanup or space recovery is
claimed. This checkpoint creates no Gradle home/daemon, guest, server or build
output; no shared stop or cache deletion is appropriate.

On an existing full-history clone, after inspecting local work and origin:

```bash
git status --short --branch
git remote -v
git fetch --no-tags origin main work/nonphysical-integration-20260915-022112
TIP=origin/work/nonphysical-integration-20260915-022112
git rev-parse "$TIP" "$TIP^{tree}"
git merge-base --is-ancestor 3c2c6fe728ffdfe6fe3537dd6a468726f74f093e "$TIP"
# Choose unused names and an unused absolute path; never reset existing work.
git worktree add -b work/nonphysical-resume-UNIQUE /absolute/unused/path "$TIP"
```

A machine without a clone needs a full-history source clone when its network
budget permits. Match the #437 checkpoint SHA/tree and inspect any later commits
before proceeding. Read this record and later issue comments first. **The pause
does not authorize restarting held builds or lifting either workflow HOLD.**
