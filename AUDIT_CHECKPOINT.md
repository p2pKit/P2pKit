# P2pKit audit continuation checkpoint

**Updated: 7 September 2026. Work in progress, not a release approval.** The owner authorized pushing the local
audit work and continuing remediation. #317 now has final independent approval; #325 is next. This tracked handoff
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
- Latest independently reviewed source: **`f273b1b98e955ebaf6f1d4e5273c1959702e4984`** (#317).
- Its tree: **`a9ea232f7974781646db3b8cffc0290ebf17f872`**; clean at final static verification/review.
- The latest clean full `check` ran at **`99b7cc1`**. Only test-runtime documentation changed afterward;
  production/build/test/dependency inputs are identical. Final static checks and review cover `f273b1b`.
  Whole-audit final combined-tree/release verification remains pending, not completed by this scoped repair.
- Source is pushed to the audit branch. `main` remains `eb444cccfc290be5435c5c10629c24183293606f`.
- The earlier unchanged #337 draft was preserved in `eb564e9487f2887f83f519575c82d4e7657864cb`.
  That commit was preservation, not a completed fix; final review covered the whole range from `32dc5c0` through
  corrections `5f454a9` and `170cc86`, including the draft. Do not resume the old unfinished-draft instructions.
- Documentation commits can follow the reviewed source; record actual `HEAD`, tree and working changes before checks.
- Machine-readable state: [checkpoint.json](docs/audit/2026-09-04/checkpoint.json).

| Disposition at this checkpoint | Count | Percentage of 168 inventoried issues |
| --- | ---: | ---: |
| Repairs with recorded independent approval | **49** | **29.2%** |
| Pending repairs, including #325 | 97 | 57.7% |
| External/platform validation | 21 | 12.5% |
| Architecture/product decision (#120) | 1 | 0.6% |
| **Total remaining** | **119** | **70.8%** |

These percentages count issues, not effort, file coverage or production readiness. The 7 September GitHub list refresh
found 275 issues across all states and 168 open issues. The ledger identifies **35 new-audit findings**, including
newly filed #354. Refresh complete issue bodies, comments, timelines and linked work before relying on any entry.
Historical assessment wording records its original local phase; branch availability does not imply a merge.

All 49 recorded repairs are in this branch's history. Issues remain OPEN under the completion policy; nothing has
been merged, closed or released by these pushes. See [every disposition](docs/audit/2026-09-04/issues.md) and
[scope, dependencies, commits and public outcomes](docs/audit/2026-09-04/issues.json).

## Completed work and verification

Recorded cycles include dependency/provenance/publication gates, coroutine cancellation/ownership, LAN rebind/cleanup,
secure-v2 tests, provisioning callbacks, sample pairing/privacy, file source/destination safeguards, diagnostics,
Android API24/25 diagnostics and iOS integration. These are scoped repairs, not proof of complete subsystem correctness.

Latest #317 corrects the Android diagnostic viewer's inert revision subscription. The production Compose bridge
reads the revision and keys filtered snapshots by revision/filter/source. Successful clearing now invalidates the
cache without manufacturing an event; failed clears preserve memory. Seven real Compose regressions exercise
event/session refresh, summary, filters, pause/resume, clearing, disposal/source replacement and a bounded 20,000-event
burst. These are host snapshot tests, not rendered UI or measured device performance.

Fresh reviewer `/root/review_317_r1` **APPROVED the whole final range** after catching an inaccurate JDK17 test-runtime
claim. An actual `--info` test run established the sample fork uses **JDK21.0.7**, independently of the JDK17 launcher
and source/target compatibility; `f273b1b` corrects the wording. The reviewer rehashed 4,539 evidence entries.
Read the [safe repair report](docs/audit/2026-09-04/repairs/317.md) and
[public outcome](https://github.com/p2pKit/P2pKit/issues/317#issuecomment-5565557697).

| Evidence | Result and limitation |
| --- | --- |
| Clean `./gradlew check --console=plain` at **`99b7cc1`**, strict/rerun/no-cache/bounded options | **2,236 passed, 0 failed, 1 unchanged manual interop-capture skip**; 206 executed tasks; before the docs-only runtime clarification |
| Final affected Android check/assembly/lint, provisioning/ABI and diagnostics checks | **95 sample + 144 provisioning + 110 diagnostics tests passed**; 155 executed tasks; inputs exactly match `99b7cc1` |
| Canonical negative extraction | Event-only regression fails with stale empty list under the original unread bridge; not untouched-baseline/device execution |
| Full lock refresh, strict Dokka, root security floors and SBOM validation | PASS; only sample test locks changed; 82 release SBOM components, no sample/build contamination; 12 POMs admitted with exact-byte/signature review |
| Layout, OSV lockfile coverage, Markdown links, release metadata, full-range whitespace | PASS at clean final `f273b1b` |
| Independent final #317 review | APPROVE; runtime-wording finding corrected and re-reviewed; no remaining actionable #317 finding |
| Inherited #352 Swift XCTest on Xcode26.5/iOS26.5 arm64 simulator | 46 passed at earlier `32dc5c0` inputs, **not re-run for #354** |

The integrated run includes JVM, Android host and Kotlin/Native arm64 iOS simulator tests, **not Swift XCTest**.
Do not add overlapping test totals. Controller/fake-manager tests and source wiring assertions are not rendered
Android UI, restoration, ART/OEM or physical-device proof. Final audit/release gates need the eventual combined tree;
whole-repository corroboration, release/consumer gates and external validation remain incomplete.

Earlier #354 corrected the hotspot Failed card's cleanup retry and stale permission-admission callbacks through
`b6af5b8`; its [review report](docs/audit/2026-09-04/repairs/354.md) retains exact historical evidence. The current
integrated run also includes that correction; earlier `12e6cfa` results alone did not.
Earlier #337 corrected independent provisioning-card lifetimes and dismissal identity through `170cc86`:
[repair summary](docs/audit/2026-09-04/repairs/337.md). Its earlier full-check results are not a new run.
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

## Next: fix #325, then continue the queue

[#325](https://github.com/p2pKit/P2pKit/issues/325), **Medium**, remains **unfixed**. Canonical setup text names only
Android Platform36, but the Android sample consumes the separate Platform37 compile SDK. This is onboarding drift,
not a change to Android API24+ support. #208's fast-gate omissions and #225's policy-script literals are separate.
Their issue/comment/timeline records have been captured; read the full histories before implementing the next fix.

Trace the catalog, actual consumers and maintained setup guidance:

```text
gradle/libs.versions.toml
samples/p2p-sample-android/build.gradle.kts
library/*/build.gradle.kts
CONTRIBUTING.md
docs/validation/test-catalog.md
docs/testing/local.md
```

Required behavior and verification:

- Document Platform36 for libraries and Platform37 for the sample, with actionable installation/setup commands.
- Add repository-policy coverage that reads both catalog values and detects setup drift without duplicating pins.
- **Do not modify protected `AGENTS.md` or `CLAUDE.md`.** Make the canonical setup guidance clear and explicitly
  account for any residual protected wording; never claim those files were corrected when they were preserved.
- Verify actual sample configuration/assembly and documentation checks, with unconditional cleanup. Create a fresh
  independent reviewer, resolve findings and review the final revision. No #325 implementation is recorded here.
- Preserve #317's observed revision and successful-clear invalidation. Closed #294/#315 remain separate/invalid;
  #316 is still pending. Do not replace the real snapshot regression with a source-string-only check.

## Continue the full audit and repair queue

1. Read `AGENTS.md`, `CLAUDE.md`, this handoff, the complete issue ledger and
   [unverified follow-ups](docs/audit/2026-09-04/followups.md). Preserve all existing user changes.
2. Record exact branch/commit/tree/status and refresh full GitHub issues/comments/linked PRs. Reconcile new evidence
   by underlying cause, not similar titles. Use exact local drafts if access is unavailable; never claim remote writes.
3. Continue all actionable issues sequentially, prioritizing severity/dependencies. #325 is next; assess the remaining
   medium integration/compatibility items and their dependencies before the lower-severity queue.
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
> This checkpoint has 49/168 reviewed repairs (29.2%) and 119 remaining (70.8%). #317 is finally reviewed and pushed
> through f273b1b; full check at 99b7cc1 passed 2236 cases with one manual skip. Only runtime documentation changed
> afterward, with final static checks/re-review; do not mislabel the old run's commit. Fix #325 next, then the queue.
> Work sequentially through every actionable issue with meaningful regressions and a fresh independent reviewer after
> every fix. Resolve/re-review all findings. Serialize bounded builds and always stop owned workers and clean only
> disposable outputs. Track safe outcomes in Git so another clone can resume, keep raw/private evidence out of Git,
> and distinguish pushed branch work from merged/released work. Do not claim unavailable platform or external gates passed.
