# P2pKit audit continuation checkpoint

**Updated: 7 September 2026. Work in progress, not a release approval.** The owner authorized pushing the local
audit work and continuing remediation. #152 now has independent approval and a passing full check;
#133's external interoperability acceptance remains NOT STARTED. #208 is next. This tracked handoff
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
- Latest independently reviewed source: **`27fec6a2268acf7a5b0246168ddc55315a5fc27f`** (#152).
- Its tree: **`1e728fdfce2e1fb68275ecfeed15078835817876`**; clean at final verification/review.
- Latest full `check` plus Android sample assembly: **PASS**, 2,276 passes, zero failures/errors and one unchanged
  manual LAN interop skip; 278 XML reports, 246 executed tasks. #152's 21 policy mutation cases and twelve static/graph
  gates also pass. Earlier #133 generator/publication/isolated-consumer evidence remains bound to `7127616`, not rerun
  for this policy-only fix. The historical #355-era #133 draft lint failure remains superseded.
- This is not whole-audit final combined-tree/release approval. Independent interoperability and other external
  acceptance remain pending, including obligations on already approved repository-repair rows.
- Source is pushed to the audit branch. `main` remains `eb444cccfc290be5435c5c10629c24183293606f`.
- The earlier unchanged #337 draft was preserved in `eb564e9487f2887f83f519575c82d4e7657864cb`.
  That commit was preservation, not a completed fix; final review covered the whole range from `32dc5c0` through
  corrections `5f454a9` and `170cc86`, including the draft. Do not resume the old unfinished-draft instructions.
- Documentation commits can follow the reviewed source; record actual `HEAD`, tree and working changes before checks.
- Machine-readable state: [checkpoint.json](docs/audit/2026-09-04/checkpoint.json).

| Disposition at this checkpoint | Count | Percentage of 169 inventoried issues |
| --- | ---: | ---: |
| Repository repairs with independent approval | **55** | **32.5%** |
| Pending repairs | 92 | 54.4% |
| External/platform validation | 21 | 12.4% |
| Architecture/product decision (#120) | 1 | 0.6% |
| **Total remaining issue rows** | **114** | **67.5%** |

These percentages count repository-repair rows, not effort, file coverage, issue closure or production readiness.
They do **not** count completion of external acceptance still attached to approved rows (including #133); independent
interoperability remains separately pending and is not implied complete by 55/169. The 7 September GitHub list refresh
found 276 issues across all states and 169 open issues. The ledger identifies **36 new-audit findings**, including
newly filed #355. Refresh complete issue bodies, comments, timelines and linked work before relying on any entry.
Historical assessment wording records its original local phase; branch availability does not imply a merge.

All 55 recorded repository repairs are in this branch's history. #325's protected-file exception is recorded below.
Issues remain OPEN under the completion policy; nothing has
been merged, closed or released by these pushes. See [every disposition](docs/audit/2026-09-04/issues.md) and
[scope, dependencies, commits and public outcomes](docs/audit/2026-09-04/issues.json).

## Completed work and verification

Recorded cycles include dependency/provenance/publication gates, coroutine cancellation/ownership, LAN rebind/cleanup,
secure-v2 tests, provisioning callbacks, sample pairing/privacy, file source/destination safeguards, diagnostics,
Android API24/25 diagnostics and iOS integration. These are scoped repairs, not proof of complete subsystem correctness.

Latest #152 protects the already-running Android ABI graph probe against silent removal. Full CI and the release
gate each have one explicit unflagged command; the nested toolchain call is static-only. Fourteen new caller controls
supplement seven existing fixtures. No production, ABI baseline, task-registration or dependency change was needed.
Fresh reviewer `/root/review_152_r1` **APPROVED the complete six-file correction**, independently verifying all 1,600
evidence entries, 278 XML reports and 33 cleanup receipts. See the [#152 report](docs/audit/2026-09-04/repairs/152.md)
and [verified outcome](https://github.com/p2pKit/P2pKit/issues/152#issuecomment-5570568984).

Earlier #133 adds twelve immutable synthetic wire fixtures, composed secure-channel role replay, four envelope
variants and both repeated mixed-profile kit directions. Actual Android host lint consumers now depend on the
test-only generator. No production/API/ABI/wire/security behavior changed. Coordinated encoder/decoder mutations
prove fixed-byte failures while symmetric controls pass. Fresh reviewer `/root/review_133_r1` **APPROVED the complete
23-path draft plus final correction**, independently checking all 2,011 evidence entries and 54 cleanup receipts.
See the [#133 report](docs/audit/2026-09-04/repairs/133.md) and
[verified public outcome](https://github.com/p2pKit/P2pKit/issues/133#issuecomment-5570024058).
The same-implementation goldens are compatibility-regression coverage, **not independent interoperability**.

Earlier #355 corrects terminal inbound acceptance recovery using the existing sealed setup registry. Expected normal,
error and transport-owned cancellation completion no longer warns/retries after observing terminal shutdown. Live
recovery/backoff, structural cancellation and late raw ownership remain intact. Nine deterministic common tests and
an all-warnings real-kit stop assertion cover the defect without relaxing #133's mixed-profile net. Fresh reviewer
`/root/review_355_r1` **APPROVED the three-file correction**, independently verifying all 1,635 evidence entries.
See the [#355 report](docs/audit/2026-09-04/repairs/355.md) and
[verified public outcome](https://github.com/p2pKit/P2pKit/issues/355#issuecomment-5569027807).
That issue-scoped approval did not approve the then-failing combined gate. The later #133 full run now passes;
the original failure evidence remains historical, not a current blocker.

Earlier #187 closes the compiled-public-constant gap in ordinary JVM/Android ABI checks without removing any legacy
field or changing its value. The guard inspects actual compiler-producer classfiles with JDK `javap`, derives supported
owners/signatures from committed baselines and retains only two omitted-JVM exceptions. It rejects new unrecorded
accessible constants, missing/ambiguous/wrong artifacts and incomplete inspection without loading application classes.
Actual Native metadata refutes the title's public-leak claim: the core sentinel is in a private companion, not the
exported ABI; Android/Desktop provisioning have no Native targets. Signature guards do not record constant values.
All ABI baselines, dependencies and the legacy publication gate are unchanged; production Kotlin edits are comments
only. #283's cleanup allegation remains refuted; #152's separate dynamic-caller assertion is now reviewed above.
Fresh reviewer `/root/review_187_r1` **APPROVED** the entire ten-file correction, independently rehashing 2,064 evidence
entries and parsing all 269 test reports. See the [#187 repair report](docs/audit/2026-09-04/repairs/187.md) for the
verified public outcome, commands, exact hashes and limits. Future breaking-version retirement remains a decision,
not permission to remove published fields now.

Earlier #190 clarifies supported consumer languages (Kotlin and Swift), distinguishes Kotlin ABI guarding from
Java-source callability, and retains the narrow Java `FileTransferFailed` mapping promise. It changes only three
Markdown documents, not production code, ABI baselines, dependencies or build/test sources. Actual JVM/Android
bytecode and javac **refute the issue's constructor claim**: the builder constructor is JVM-public and the companion
creation lambda is Java-callable; the required mangled `appId` setter is the ordinary Java-source blocker.
Fresh reviewer `/root/review_190_r1` **APPROVED** the final correction, independently rehashing 272 evidence entries.
See the [#190 repair report](docs/audit/2026-09-04/repairs/190.md) and
[verified public outcome](https://github.com/p2pKit/P2pKit/issues/190#issuecomment-5566533684).

Earlier #325 corrects editable Android onboarding guidance. The canonical
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
| Latest clean `check` plus Android assembly at **`27fec6a`** | **2,276 passes**, zero failures/errors, one unchanged manual skip; 278 XMLs, 246 executed tasks. Actual ABI/constants, lint and Android assembly pass |
| #152 static/caller controls | 21 mutation cases pass; old guard rejected by new suite; four actual outer-policy removal/downgrade controls reject. Twelve static/policy gates pass, including one real strict graph probe |
| Earlier clean `check` plus Android assembly at **`7127616`** | **2,276 passes**, zero failures/errors, one unchanged manual skip; 278 XMLs, 246 executed tasks, all 22 new #133 cases and ordinary ABI/lint guards pass |
| #133 mutation, generator, publication and consumer controls | Coordinated drift detected; sixteen generator stages pass; 15 publication sets and 23 isolated consumer tasks pass; all 54 archives/10,064 entries scanned per publication without fixtures; ten static gates pass |
| Historical #355 clean combined attempt at **`1820631`** | **FAIL** at Android host lint model: missing producer dependency in #133 draft; 1,615 test results passed before failure, 80 tasks. Not completed Android assembly |
| #355 focused core and additional LAN checks | Core726 pass; separate LAN369 pass/one unchanged manual skip; five static gates pass. Do not add overlapping totals |
| Clean `./gradlew check :p2p-sample-android:assembleDebug` at **`bf3932e`**, strict/rerun/no-cache/bounded options | **2,236 passed, 0 failures/errors, 1 unchanged manual interop-capture skip**; 243 executed tasks; all six new guards, existing ABI checks and Android assembly/lint pass |
| #187 old-gap reproduction and corrected Kotlin controls | Old checks accepted injected constants (34 tasks); all six corrected ordinary ABI surfaces reject them. Retained-field removal is rejected; temporary edits restored exactly |
| #187 compiled policy and actual producer/check graph | 26 compiled controls pass in final full check; all six guards and the root fixture task are in the realized graph. Earlier standalone policy run had 25 controls, not the final total |
| Final local publication and isolated consumers at **`bf3932e`** | 15 publication sets pass; 23 executed tasks in the isolated JVM/Java/Android/KMP/iOS consumer compile/link gate pass; Android permissions and simulator framework minimum iOS14.0 inspected. No remote publication or consumer runtime claim |
| Ten final #187 static/policy gates and independent review | PASS; full correction APPROVED. Unchanged release-workflow checker passed using system Python after Homebrew Python/expat linkage failure |
| Earlier #190 real bytecode/javac and final ABI checks | 28 intended rejections, two positive compilations and two JDK17 host executions; 14 final ABI tasks. Session examples compile-only; no ART/device claim |
| Earlier #325 isolated SDK resolution, downloads disabled | Platform36-only fails finding `android-37.0`; adding installed Platform37.0 resolves sample bootclasspath. Not a fresh SDK download or isolated full assembly |
| Inherited #352 Swift XCTest on Xcode26.5/iOS26.5 arm64 simulator | 46 passed at earlier `32dc5c0` inputs, **not re-run for #187** |

The latest successful integrated run includes JVM, Android host and Kotlin/Native arm64 iOS simulator tests,
**not Swift XCTest**, Intel execution, ART/OEM or physical devices. #133 publication/isolated-consumer checks executed
at `7127616`, not rerun for #152; complete release/XCFramework/Swift gates remain pending. Exploratory harness/environment
failures are preserved separately, not acceptance evidence. #152's 33 cleanup receipts and #133's earlier 54 receipts
are finalized, including failed and negative attempts; required evidence remains.
Do not add overlapping test totals. Controller/fake-manager tests and source wiring assertions are not rendered
Android UI, restoration, ART/OEM or physical-device proof. Final audit/release gates need the eventual combined tree;
whole-repository corroboration, eventual combined-tree release/consumer gates and external validation remain incomplete.

Earlier #317 corrected the diagnostic revision subscription and successful-clear invalidation through `f273b1b`.
Its [report](docs/audit/2026-09-04/repairs/317.md) preserves the real Compose regression evidence and the correction
to test-runtime wording: actual sample executor JDK21.0.7, not inferred from the JDK17 launcher. The latest passing integrated
tests at `27fec6a` include those regressions; host snapshots are not rendered/device performance measurements.
Earlier #354 corrected the hotspot Failed card's cleanup retry and stale permission-admission callbacks through
`b6af5b8`; its [review report](docs/audit/2026-09-04/repairs/354.md) retains exact historical evidence. The latest passing
integrated run at `27fec6a` also includes that correction; earlier `12e6cfa` results alone did not.
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

## Next: #208, then the remaining queue

[#133](https://github.com/p2pKit/P2pKit/issues/133) is **repository-scope approved**, not an unfinished draft. The full
range from preserved `ce350c8` through correction `7127616` was reviewed; do not recreate/discard those fixtures or
repeat the resolved lint-producer repair. #355's runtime correction remains intact. #133's external acceptance is still
**NOT STARTED** in `docs/validation/secure-v2-interoperability.md`; leave #133 OPEN.

1. #152 is approved and pushed at `27fec6a`; do not repeat its completed repair. Preserve its explicit graph calls,
   #187's actual-constant guards and the deliberate policy tripwires.
2. Read [#208](https://github.com/p2pKit/P2pKit/issues/208) completely, including comments/timeline/linked work,
   and correct the verified fast-gate documentation gap. No #208 repair has started at this checkpoint. Then assess
   #225 and continue all remaining actionable issues sequentially. There are **92 pending repairs: 91 low, one
   informational (#333)**. Severity is not permission to skip functional defects.
3. Continue feasible work on the 21 external-validation rows and #120's architecture/product decision without
   manufacturing hardware/access or deciding product scope silently. Document precise blockers and owners.

Preserve #317's subscription regression, #325's protected-instruction caveat and all previous reviewed repairs.
Record any new independently trackable defect only after reproduction and deduplication; update existing issues
for new evidence of the same underlying problem.

## Continue the full audit and repair queue

1. Read `AGENTS.md`, `CLAUDE.md`, this handoff, the complete issue ledger and
   [unverified follow-ups](docs/audit/2026-09-04/followups.md). Preserve all existing user changes.
2. Record exact branch/commit/tree/status and refresh full GitHub issues/comments/linked PRs. Reconcile new evidence
   by underlying cause, not similar titles. Use exact local drafts if access is unavailable; never claim remote writes.
3. Continue all actionable issues sequentially, prioritizing severity/dependencies. #208 is next; refresh the
   remaining queue and its dependencies rather than relying only on historical issue titles.
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
> This checkpoint has 55/169 independently reviewed repository repairs (32.5%) and 114 remaining issue rows (67.5%).
> These percentages exclude completion of external acceptance on approved rows, including #133. #152 is approved/pushed
> at 27fec6a (tree 1e728fdfce2e1fb68275ecfeed15078835817876): latest full check+Android assembly passes 2,276/zero
> failures/one manual skip; 21 policy mutation cases and twelve static/graph gates pass. Earlier #133 publication/consumer
> evidence remains bound to 7127616, not rerun for #152. Independent interoperability stays NOT STARTED. Next: #208/#225 and
> the remaining queue. Preserve protected instructions, published constants and all prior reviewed repairs. Read full
> issues and work sequentially, create a fresh independent reviewer after every fix, resolve/re-review findings,
> serialize bounded builds and always stop owned workers/clean disposable outputs. Update safe Git/GitHub handoffs
> and push only the audit branch; no force-push, merge, release or issue closure is authorized. Full release/XCFramework/
> Swift, whole-repository corroboration and external/device/crypto validation remain pending. Overall NOT READY.
