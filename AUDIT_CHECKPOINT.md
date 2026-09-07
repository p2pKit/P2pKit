# P2pKit audit continuation checkpoint

**Updated: 7 September 2026. Work in progress, not a release approval.** The owner authorized pushing the local
audit work and continuing remediation. #337 now has final independent approval; #354 is next. This tracked handoff
replaces the earlier private archive-only instructions.
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

The clone includes source changes, repair commits, the reviewed repairs and the small
[audit ledger](docs/audit/2026-09-04/README.md). No archive or patch application is needed to resume coding.
Open your coding agent in this directory and give it the prompt at the end. This transfers documented working context,
not an account login, a native chat export, running agents or build processes.

## Exact checkpoint and progress

- Repository: <https://github.com/p2pKit/P2pKit>.
- Audit branch: `audit/complete-2026-09-04`; not merged into `main`.
- Latest independently reviewed source: **`170cc86b652d421b9d3118735c63cdf4a5530a66`** (#337).
- Its tree: **`23d44d3a59f0051b4475b637930263f84aed7c8a`**; clean at final integrated verification.
- Source is pushed to the audit branch. `main` remains `eb444cccfc290be5435c5c10629c24183293606f`.
- The earlier unchanged #337 draft was preserved in `eb564e9487f2887f83f519575c82d4e7657864cb`.
  That commit was preservation, not a completed fix; final review covered the whole range from `32dc5c0` through
  corrections `5f454a9` and `170cc86`, including the draft. Do not resume the old unfinished-draft instructions.
- Documentation commits can follow the reviewed source; record actual `HEAD`, tree and working changes before checks.
- Machine-readable state: [checkpoint.json](docs/audit/2026-09-04/checkpoint.json).

| Disposition at this checkpoint | Count | Percentage of 168 inventoried issues |
| --- | ---: | ---: |
| Repairs with recorded independent approval | **47** | **28.0%** |
| Pending repairs, including #354 | 99 | 58.9% |
| External/platform validation | 21 | 12.5% |
| Architecture/product decision (#120) | 1 | 0.6% |
| **Total remaining** | **121** | **72.0%** |

These percentages count issues, not effort, file coverage or production readiness. The 7 September GitHub list refresh
found 275 issues across all states and 168 open issues. The ledger identifies **35 new-audit findings**, including
newly filed #354. Refresh complete issue bodies, comments, timelines and linked work before relying on any entry.
Historical assessment wording records its original local phase; branch availability does not imply a merge.

All 47 recorded repairs are in this branch's history. Issues remain OPEN under the completion policy; nothing has
been merged, closed or released by these pushes. See [every disposition](docs/audit/2026-09-04/issues.md) and
[scope, dependencies, commits and public outcomes](docs/audit/2026-09-04/issues.json).

## Completed work and verification

Recorded cycles include dependency/provenance/publication gates, coroutine cancellation/ownership, LAN rebind/cleanup,
secure-v2 tests, provisioning callbacks, sample pairing/privacy, file source/destination safeguards, diagnostics,
Android API24/25 diagnostics and iOS integration. These are scoped repairs, not proof of complete subsystem correctness.

Latest #337 corrects Android provisioning cards after OS stop/release. It preserves resource independence, terminal-
before-result behavior, repeated calls, cancellation, kit replacement and #324's credential clearing. Independent R1
found that a dismissed old binding could hide a new join. Two regression tests reproduced it; the final correction
uses exact resource identity. Fresh reviewer `/root/review_337_r2` **APPROVED the full final range**, independently
corroborating source, test counts, evidence hashes and cleanup. Read the [safe repair report](docs/audit/2026-09-04/repairs/337.md)
and [public outcome](https://github.com/p2pKit/P2pKit/issues/337#issuecomment-5564403296).

| Evidence | Result and limitation |
| --- | --- |
| Clean `./gradlew check --console=plain` at `170cc86`, strict/rerun/no-cache/bounded options | **2,216 passed, 0 failed, 1 unchanged manual interop-capture skip**; 205 executed tasks |
| Final affected Android check/assembly/lint and provisioning/ABI checks | **75 sample + 144 provisioning tests passed**; 150 executed tasks; inputs exactly match committed correction |
| Layout, OSV lockfile coverage, Markdown links, release metadata, full-range whitespace | PASS for #337 inputs |
| Independent final #337 review | APPROVE; no remaining actionable #337 finding; #354 is separate |
| Inherited #352 Swift XCTest on Xcode26.5/iOS26.5 arm64 simulator | 46 passed at earlier `32dc5c0` inputs, **not re-run for #337** |

The current integrated run includes JVM, Android host and Kotlin/Native arm64 iOS simulator tests, **not Swift XCTest**.
Do not add overlapping test totals. Controller/fake-manager tests and source wiring assertions are not rendered
Android UI, restoration, ART/OEM or physical-device proof. The full release gate has not been re-run for this revision;
whole-repository corroboration, release/consumer gates and external validation remain incomplete.

Inherited #352 corrected selective diagnostic clearing and truthful storage failures, ending at
`32dc5c03658145741c6e23cdfec3c14cd2eba5e7`; its [posted outcome](https://github.com/p2pKit/P2pKit/issues/352#issuecomment-5562438288)
retains that exact earlier verification. Current approval does not manufacture missing historical raw evidence.

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
diagnostic trace experiment is intentionally private and is not required for current continuation. Neither stash was
dropped or pushed; do not blindly apply either over reviewed code. Authenticate GitHub and the coding agent normally
on the new device rather than copying token stores or SSH keys.

## Next: fix #354, then continue the queue

[#354](https://github.com/p2pKit/P2pKit/issues/354), **Low**, is a distinct pre-existing recovery defect discovered while
following #337's actual callers. It is filed but **not fixed**. After hotspot close fails, the manager retains cleanup
ownership. The Failed card offers Retry but calls `startHotspot()`, which refuses retained cleanup instead of retrying
`stopHotspot()`. Repeating Retry cannot recover; whole-kit Stop is a workaround that unnecessarily disrupts other work.

Start from the fully reviewed #337 source, not its old draft. Read the full #354 issue and relevant #198/#187/#283/#284
history, then trace these files:

```text
samples/p2p-sample-android/src/main/java/dev/p2pkit/sample/android/MainActivity.kt
samples/p2p-sample-android/src/main/java/dev/p2pkit/sample/android/P2pKitViewModel.kt
samples/p2p-sample-android/src/main/java/dev/p2pkit/sample/android/ProvisioningUiState.kt
library/p2p-network-provisioning-android/src/androidMain/kotlin/dev/p2pkit/provisioning/android/AndroidNetworkProvisioningManager.kt
```

Required behavior and verification:

- Preserve failed cleanup intent separately from a live-resource claim. The actual recovery action must retry cleanup,
  not restart hosting or request acquisition permissions; successful cleanup must leave an independent join intact.
- Do not attribute untagged `CleanupFailed` events from another retired resource to the hotspot. Keep ordinary start
  failure recovery, busy/cancellation/kit-replacement fencing and the newly approved #337/#324 behavior intact.
- Reproduce failure once then successful cleanup through the actual selected card action. Cover repeated failures,
  start failures, coexistence and cancellation/replacement, and distinguish controller/static wiring from rendered UI.
- Run affected Android checks/assembly/lint and retained-cleanup manager regressions with unconditional cleanup.
  Create a fresh independent reviewer after the fix and resolve/re-review all findings before advancing.

## Continue the full audit and repair queue

1. Read `AGENTS.md`, `CLAUDE.md`, this handoff, the complete issue ledger and
   [unverified follow-ups](docs/audit/2026-09-04/followups.md). Preserve all existing user changes.
2. Record exact branch/commit/tree/status and refresh full GitHub issues/comments/linked PRs. Reconcile new evidence
   by underlying cause, not similar titles. Use exact local drafts if access is unavailable; never claim remote writes.
3. Continue all actionable issues sequentially, prioritizing severity/dependencies. After #354, known candidates are
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

An existing moderate Dependabot alert remains open: [alert 14](https://github.com/p2pKit/P2pKit/security/dependabot/14),
`GHSA-r937-wjx7-w2jp`. The existing OSV exception expires 31 October 2026; cache isolation/KAPT non-use are mitigations,
not a patched-dependency or dismissed-alert claim. Reassess it in the dependency/release gates.

Overall status: **NOT PRODUCTION READY**. Report exact commits/state, issue dispositions, fix/review evidence,
verification scope, blockers, cleanup and practical readiness limits at each handoff.

## Prompt for the next agent

> Continue the complete P2pKit audit from AUDIT_CHECKPOINT.md and docs/audit/2026-09-04/. Verify the audit branch,
> current commit/tree/status, read repository instructions and full GitHub issue histories, and preserve user work.
> This checkpoint has 47/168 reviewed repairs (28.0%) and 121 remaining (72.0%). #337 is finally reviewed and pushed
> through 170cc86; its old draft instructions are superseded. Fix the separately filed #354 next, then continue the queue.
> Work sequentially through every actionable issue with meaningful regressions and a fresh independent reviewer after
> every fix. Resolve/re-review all findings. Serialize bounded builds and always stop owned workers and clean only
> disposable outputs. Track safe outcomes in Git so another clone can resume, keep raw/private evidence out of Git,
> and distinguish pushed branch work from merged/released work. Do not claim unavailable platform or external gates passed.
