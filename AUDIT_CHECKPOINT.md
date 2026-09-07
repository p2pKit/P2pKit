# P2pKit audit continuation checkpoint

**Updated: 7 September 2026. Work in progress, not a release approval.** The owner authorized pushing the local
audit work and continuing remediation. #325 now has final independent approval; #190 is next. This tracked handoff
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
- Latest independently reviewed source: **`6ebfb9f81de45164cc2f148db753c65a7061f835`** (#325).
- Its tree: **`79c25845132f7851bfec746a2582a8bf102b5636`**; clean at integrated/static verification and review.
- The latest clean full `check` plus Android sample assembly ran at **`6ebfb9f`**.
  Whole-audit final combined-tree/release verification remains pending, not completed by this scoped repair.
- Source is pushed to the audit branch. `main` remains `eb444cccfc290be5435c5c10629c24183293606f`.
- The earlier unchanged #337 draft was preserved in `eb564e9487f2887f83f519575c82d4e7657864cb`.
  That commit was preservation, not a completed fix; final review covered the whole range from `32dc5c0` through
  corrections `5f454a9` and `170cc86`, including the draft. Do not resume the old unfinished-draft instructions.
- Documentation commits can follow the reviewed source; record actual `HEAD`, tree and working changes before checks.
- Machine-readable state: [checkpoint.json](docs/audit/2026-09-04/checkpoint.json).

| Disposition at this checkpoint | Count | Percentage of 168 inventoried issues |
| --- | ---: | ---: |
| Repairs with recorded independent approval | **50** | **29.8%** |
| Pending repairs, including #190 | 96 | 57.1% |
| External/platform validation | 21 | 12.5% |
| Architecture/product decision (#120) | 1 | 0.6% |
| **Total remaining** | **118** | **70.2%** |

These percentages count issues, not effort, file coverage or production readiness. The 7 September GitHub list refresh
found 275 issues across all states and 168 open issues. The ledger identifies **35 new-audit findings**, including
newly filed #354. Refresh complete issue bodies, comments, timelines and linked work before relying on any entry.
Historical assessment wording records its original local phase; branch availability does not imply a merge.

All 50 recorded repairs are in this branch's history. #325's protected-file exception is recorded below.
Issues remain OPEN under the completion policy; nothing has
been merged, closed or released by these pushes. See [every disposition](docs/audit/2026-09-04/issues.md) and
[scope, dependencies, commits and public outcomes](docs/audit/2026-09-04/issues.json).

## Completed work and verification

Recorded cycles include dependency/provenance/publication gates, coroutine cancellation/ownership, LAN rebind/cleanup,
secure-v2 tests, provisioning callbacks, sample pairing/privacy, file source/destination safeguards, diagnostics,
Android API24/25 diagnostics and iOS integration. These are scoped repairs, not proof of complete subsystem correctness.

Latest #325 corrects editable Android onboarding guidance. The canonical
[SDK setup](docs/testing/local.md#android-sdk-setup) distinguishes Platform36 for library/shared modules,
Platform37 for the Android sample (SDK Manager package **`platforms;android-37.0`**), and runtime minimum API24.
Contributor and validation entry points link there. The layout gate now checks catalog/table/install-command/CI
consistency with 15 negative controls and a coherent future-SDK positive control; independent tripwires remain intact.

Fresh reviewer `/root/review_325_r1` **APPROVED the complete five-file correction**, independently rehashing 1,501
evidence entries and parsing 269 XML reports. No production, ABI, dependency or SDK pin changed.
**Protected-file exception:** `AGENTS.md:9` still names only the library SDK because the owner prohibited editing it.
Canonical setup warns about this omission. Feasible remediation is complete, but literal alignment of that sentence
requires new owner authorization; do not claim every originally cited file was corrected. `CLAUDE.md` is unchanged.
Read the [safe repair report](docs/audit/2026-09-04/repairs/325.md) and
[public outcome](https://github.com/p2pKit/P2pKit/issues/325#issuecomment-5565989401).

| Evidence | Result and limitation |
| --- | --- |
| Clean `./gradlew check :p2p-sample-android:assembleDebug` at **`6ebfb9f`**, strict/rerun/no-cache/bounded options | **2,236 passed, 0 failures/errors, 1 unchanged manual interop-capture skip**; 236 executed tasks; Android assembly/lint and library ABI gates pass |
| Isolated baseline SDK resolution, downloads disabled | Platform36-only fails finding `android-37.0`; adding installed Platform37.0 resolves actual sample bootclasspath. No legacy alias; not a fresh SDK download or isolated full assembly |
| Eight final static gates | PASS: layout, OSV lockfile coverage, Markdown links, release metadata, full-range whitespace, new checker under system Ruby2.6.10, independent toolchain/ABI graph and release-workflow policies |
| Independent final #325 review | APPROVE of feasible correction, with protected `AGENTS.md` caveat retained; no actionable finding |
| Inherited #352 Swift XCTest on Xcode26.5/iOS26.5 arm64 simulator | 46 passed at earlier `32dc5c0` inputs, **not re-run for #325** |

The integrated run includes JVM, Android host and Kotlin/Native arm64 iOS simulator tests, **not Swift XCTest**.
Do not add overlapping test totals. Controller/fake-manager tests and source wiring assertions are not rendered
Android UI, restoration, ART/OEM or physical-device proof. Final audit/release gates need the eventual combined tree;
whole-repository corroboration, release/consumer gates and external validation remain incomplete.

Earlier #317 corrected the diagnostic revision subscription and successful-clear invalidation through `f273b1b`.
Its [report](docs/audit/2026-09-04/repairs/317.md) preserves the real Compose regression evidence and the correction
to test-runtime wording: actual sample executor JDK21.0.7, not inferred from the JDK17 launcher. Current integrated
tests include those regressions; host snapshots are not rendered/device performance measurements.
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

## Next: fix #190, then continue the queue

[#190](https://github.com/p2pKit/P2pKit/issues/190), **Medium**, remains **unfixed**. The recommended correction is
documentation-only: remove ambiguity between binary ABI checks and Java-language consumption support. Kotlin and
Swift are the supported consumer languages; retain the narrower Java `FileTransferFailed` mapping contract. Do not
retrofit a Java facade or change the immutable RC ABI. Its complete issue/comment/timeline history was refreshed for
read-ahead; no #190 implementation or completed review is recorded here.

Trace the actual source, emitted bytecode and public contracts before repeating issue claims:

```text
docs/compatibility.md
docs/architecture/specification.md
library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/Identity.kt
library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/dsl/Builders.kt
library/p2p-core/api/{jvm,android}/p2p-core.api
```

Required behavior and verification:

- Verify mangled identity/builder accessors and unmangled error mapping against emitted bytecode and a bounded javac
  probe. The issue's claim that an `internal` builder constructor is absent from the JVM ABI must not be inferred from
  a Kotlin-filtered baseline alone. Enumerate accurate limitations, not an unsupported blanket Java claim.
- Run documentation checks and affected ABI checks; keep the `.api` baseline diff empty. Create a fresh independent
  reviewer, resolve findings and review the final revision. Preserve protected `AGENTS.md` and `CLAUDE.md`.
- Then address the remaining medium integration/compatibility work: #187 (preserve already-public RC2/RC3 constants;
  read consolidated closed #283) and #133 (composed wire fixtures and v1/v2 fail-closed coverage). Same-implementation
  goldens are not independent interoperability. #208's fast-gate/Ruby docs and #225's tripwires remain separate/pending.
- Preserve #317's observed revision and successful-clear invalidation. Closed #294/#315 remain separate/invalid;
  #316 is still pending. Do not replace the real snapshot regression with a source-string-only check.

## Continue the full audit and repair queue

1. Read `AGENTS.md`, `CLAUDE.md`, this handoff, the complete issue ledger and
   [unverified follow-ups](docs/audit/2026-09-04/followups.md). Preserve all existing user changes.
2. Record exact branch/commit/tree/status and refresh full GitHub issues/comments/linked PRs. Reconcile new evidence
   by underlying cause, not similar titles. Use exact local drafts if access is unavailable; never claim remote writes.
3. Continue all actionable issues sequentially, prioritizing severity/dependencies. #190 is next; assess the remaining
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
  JDK21. Libraries compile against Android Platform36; the sample needs **Platform37** (`platforms;android-37.0`).
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
> This checkpoint has 50/168 reviewed repairs (29.8%) and 118 remaining (70.2%). #325 is reviewed and pushed at
> 6ebfb9f; clean full check plus Android assembly there passed 2236 cases with one manual skip. Preserve the explicit
> protected-AGENTS prerequisite exception. Fix #190 next (documentation-only Java-consumer limits, verified against
> actual bytecode), then #187/#133 and the rest of the queue; do not infer independent interoperability from goldens.
> Work sequentially through every actionable issue with meaningful regressions and a fresh independent reviewer after
> every fix. Resolve/re-review all findings. Serialize bounded builds and always stop owned workers and clean only
> disposable outputs. Track safe outcomes in Git so another clone can resume, keep raw/private evidence out of Git,
> and distinguish pushed branch work from merged/released work. Do not claim unavailable platform or external gates passed.
