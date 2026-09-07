# P2pKit audit continuation checkpoint

**Updated: 8 September 2026. Work in progress, not a release approval.** The owner authorized pushing the local
audit work and continuing remediation. #332's Apple invalid-re-resolution follow-up is now independently approved/pushed,
retaining its prior JVM/Android approval and the #229/#356 parser and #357 test-clock corrections. The combined full
check and Android assembly pass. The reopened #332 row returns to approved; #130 is the planned next issue and must
be read completely before repair. #133's independent interoperability is NOT STARTED.
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
- Latest independently reviewed source: **`78ef36142fe79b4ff9672656c6f4c97f049678d0`** (#332 Apple follow-up).
- Its tree: **`0f8ab1465d257baac8110e3bd1ecf95859abe93c`**; clean at final verification/review.
- #229's fourteen-file correction is `bf34f70b13ceab1549741b09647fec0b603b15c0`; all fourteen blobs were unchanged
  at combined revision `6d9cd3c`, not at current HEAD: #356 subsequently changed the common parser and release docs.
- Latest full `check` plus Android sample assembly at **`78ef361`**: **PASS**, **2,387 passes**, zero failures/errors and
  one unchanged manual LAN interop skip; 290 XMLs, 246 executed tasks. Fourteen final static/caller gates pass.
  The first full run at `bf34f70` FAILED on the unchanged watcher test; #357 corrected its cause before this pass.
- Earlier #133 publication/isolated-consumer evidence remains bound to `7127616`, not rerun for these corrections.
- This is not whole-audit final combined-tree/release approval. Independent interoperability and other external
  acceptance remain pending, including obligations on already approved repository-repair rows.
- Source is pushed to the audit branch. `main` remains `eb444cccfc290be5435c5c10629c24183293606f`.
- The earlier unchanged #337 draft was preserved in `eb564e9487f2887f83f519575c82d4e7657864cb`.
  That commit was preservation, not a completed fix; final review covered the whole range from `32dc5c0` through
  corrections `5f454a9` and `170cc86`, including the draft. Do not resume the old unfinished-draft instructions.
- Documentation commits can follow the reviewed source; record actual `HEAD`, tree and working changes before checks.
- Machine-readable state: [checkpoint.json](docs/audit/2026-09-04/checkpoint.json).

| Disposition at this checkpoint | Count | Percentage of 171 inventoried issues |
| --- | ---: | ---: |
| Repository repairs with independent approval | **61** | **35.7%** |
| Pending repairs | 88 | 51.5% |
| External/platform validation | 21 | 12.3% |
| Architecture/product decision (#120) | 1 | 0.6% |
| **Total remaining issue rows** | **110** | **64.3%** |

These percentages count repository-repair rows, not effort, file coverage, issue closure or production readiness.
#332 returned to approved after its separately verified Apple repair; it is not a newly counted duplicate issue.
They do **not** count completion of external acceptance still attached to approved rows (including #133); independent
interoperability remains separately pending and is not implied complete by 61/171. The 7 September 22:45 UTC GitHub list refresh
found 278 issues across all states and 171 open issues. The ledger identifies **38 new-audit findings**, including
newly filed #356 and #357. Refresh complete issue bodies, comments, timelines and linked work before relying on any entry.
Historical assessment wording records its original local phase; branch availability does not imply a merge.

All 61 currently approved repository-repair rows are in this branch's history. #325's protected-file exception is recorded below.
Issues remain OPEN under the completion policy; nothing has
been merged, closed or released by these pushes. See [every disposition](docs/audit/2026-09-04/issues.md) and
[scope, dependencies, commits and public outcomes](docs/audit/2026-09-04/issues.json).

## Completed work and verification

Recorded cycles include dependency/provenance/publication gates, coroutine cancellation/ownership, LAN rebind/cleanup,
secure-v2 tests, provisioning callbacks, sample pairing/privacy, file source/destination safeguards, diagnostics,
Android API24/25 diagnostics and iOS integration. These are scoped repairs, not proof of complete subsystem correctness.

Latest #332 Apple follow-up withdraws a previously admitted native service after malformed, semantically invalid or
identity-mismatched re-resolution. Admission and withdrawal share the current-browser/generation/host-intent fence and
cache lock; the existing lost path removes cache, endpoint registry and relay ownership together. Rejected TXT cannot
select another peer; stale callbacks, manual hints, existing dial leases/sessions and independent advertising retain
their ownership. Recovery is fresh and bounded. No API/ABI, dependency, wire or authentication change.

Fresh `/root/review_332_apple_r1` **APPROVED** the complete four-file correction at `78ef361`, independently checking
1,992 sealed entries, 370 retained XMLs (290 final), eight expected-red controls and 28 finalized cleanup receipts.
The baseline produced ten intended assertion failures/four controls; the final 20 native-input transition methods
exercise both profiles. Focused LAN checks pass 480/one unchanged skip; final full check plus Android assembly passes
2,387/zero failures/errors/one unchanged skip. The source was pushed and the [verified outcome](https://github.com/p2pKit/P2pKit/issues/332#issuecomment-5576324322)
posted; the issue remains OPEN, not merged/released. See the [Apple repair report](docs/audit/2026-09-04/repairs/332-apple.md).
Tests inject native inputs after browse-result copying and control states on unstarted native connections: they are
not live NWBrowser/multicast or TCP-handshake proof. The **0.8.0+** admission restriction and external gates remain.

Earlier #356 removes Apple C-string TXT-key normalization. Native dictionaries and raw-buffer records now use the same
original-byte parser, with an unsigned 65,535-byte bound before narrowing/copying and no successful partial result on
access/framing/consumed-value failure. Unknown NUL aliases cannot supply or overwrite canonical fields. Actual native
probes, seven baseline assertion failures with five controls, 460 focused passes/one manual skip and four mutation
controls establish the boundary. Fresh `/root/review_356_r1` **APPROVED** the complete six-file correction at `183b6c9`,
independently checking 1,955 sealed entries, 289 final XMLs and 28 finalized cleanup receipts. No API/ABI, dependency,
authentication or cache-lifecycle correction is claimed. Admission changes remain **0.8.0+**. See the
[#356 report](docs/audit/2026-09-04/repairs/356.md) and
[verified outcome](https://github.com/p2pKit/P2pKit/issues/356#issuecomment-5575458398).
That report's then-unconfirmed #332 wording records its review-time scope; the later Apple transition cycle above
supersedes the hypothesis without rewriting or expanding the earlier parser approval.

Earlier #229 fixes JVM/Android TXT decoding at the original byte boundary; both JmDNS property APIs were already lossy.
Bounded raw parsing preserves valid Unicode/empty/NUL semantics, rejects malformed consumed occurrences and leaves
#332's existing JVM/Android ownership withdrawal intact. Eight negative controls, actual dependency/native probes,
baseline red/positive controls and the focused LAN check pass. Fresh `/root/review_229_r1` **APPROVED** the complete
correction at `6d9cd3c`, independently checking 3,513 sealed entries and 34 cleanup receipts. This is canonical known-key
**value** parity only; Apple key aliasing [#356](https://github.com/p2pKit/P2pKit/issues/356) was separately corrected above. Admission
tightening is reserved for **0.8.0+**, not the unchanged snapshot label. See the [#229 report](docs/audit/2026-09-04/repairs/229.md)
and [verified outcome](https://github.com/p2pKit/P2pKit/issues/229#issuecomment-5574771448).

Its first integrated run exposed distinct test defect #357: a virtual timeout outran a real executor. The one-file
correction retains the one-second bound/thread assertion, deliberately gates the executor and always retires resources.
Focused 6/6 and both negative controls pass; fresh `/root/review_357_r1` **APPROVED**, verifying 3,077 own/shared entries
and 22 own/shared cleanup receipts. Both issues share the final **2,333-pass** integrated run, not additive executions.
See the [#357 report](docs/audit/2026-09-04/repairs/357.md) and [verified outcome](https://github.com/p2pKit/P2pKit/issues/357#issuecomment-5574770193).

Earlier #226 separates artifact placement from the GPG socket constraint: artifacts honor `TMPDIR`; a documented
`P2PKIT_GPG_TMPDIR` selects the short keyring root. The complete physical socket path is limited to the measured
102 bytes before downloads/GPG. Partial setup, errors and handled signals clean both resources; scoped worker
shutdown precedes socket deletion, and failure retains a quoted retry path with nonzero exit. Fourteen real synthetic-GPG
tests, thirteen red controls and thirteen static gates pass. Fresh reviewer `/root/review_226_r1` **APPROVED the complete
four-file correction**, independently verifying all 1,644 sealed entries, 278 XMLs and 37 cleanup receipts. No production,
API/ABI, dependency/lock, workflow or protected-instruction change. See the [#226 report](docs/audit/2026-09-04/repairs/226.md)
and [verified outcome](https://github.com/p2pKit/P2pKit/issues/226#issuecomment-5572682691). The old baseline cleanup already worked;
no `noexec` failure or signature bypass was established. Ambient GPG packet/key inspection remains a separate
[unconfirmed follow-up](docs/audit/2026-09-04/followups.md#dependency-curator-ambient-gpg-packet-and-key-inspection).

Earlier #225 replaces historical consumer/Netty denylists with enduring input/lock policies while preserving independent
version/checksum approval tripwires. Every active Netty lock row is compared numerically against the independently
supplied floor; the maintained consumer recipe requires Kotlin/AGP input variables. XcodeGen's fixture input follows
the installer and the same assertions run with a synthetic future version; the real installer is unchanged.
Fresh reviewer `/root/review_225_r1` **APPROVED the complete seven-file correction**, including its final documentation
finding correction, independently verifying all 1,932 evidence entries, 278 XMLs and 101 cleanup receipts. Twenty-four
caller controls, fourteen final static gates and the full check/Android assembly pass. No production/API/ABI, dependency,
lock, workflow or Apple deployment policy changed. See the [#225 report](docs/audit/2026-09-04/repairs/225.md) and
[verified outcome](https://github.com/p2pKit/P2pKit/issues/225#issuecomment-5571608911).

Earlier #208 restores the omitted Markdown-link and whitespace commands in the local fast gate. All three six-command
blocks are byte-identical; editable guides now document Bash/Git/Ruby prerequisites and actual checking/cleanup scope.
Fresh reviewer `/root/review_208_r1` **APPROVED the two-file documentation correction**, independently verifying all 56
source-evidence entries and ten cleanup receipts. Five static gates, block equality and Ruby/scope smoke checks pass.
No permanent consistency guard or script/runtime/ABI change was made. See the [#208 report](docs/audit/2026-09-04/repairs/208.md)
and [verified outcome](https://github.com/p2pKit/P2pKit/issues/208#issuecomment-5570832503).

Earlier #152 protects the already-running Android ABI graph probe against silent removal. Full CI and the release
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
| Latest clean `check` plus Android assembly at **`78ef361`** | **2,387 passes**, zero failures/errors, one unchanged manual skip; 290 XMLs, 246 executed tasks. Actual ABI/constants, lint and Android assembly pass |
| #332 Apple transition regression checks | Ten intended baseline failures/four controls; 20 final methods/both profiles; 480 focused LAN passes/one manual skip; eight mutations detected. Fourteen final static gates pass. Native-input/control-state evidence, not live multicast/TCP-handshake proof |
| Earlier clean `check` plus Android assembly at **`183b6c9`** | **2,367 passes**, zero failures/errors, one unchanged manual skip; 289 XMLs, 246 executed tasks. Actual ABI/constants, lint and Android assembly pass |
| #356 scoped regression checks | Actual 25-case native accessor probe; seven intended baseline failures/five controls; 460 focused LAN passes/one manual skip; four mutations detected. Fourteen final static gates pass. Native/simulator evidence, not physical discovery or #332 lifecycle proof |
| Earlier clean `check` plus Android assembly at **`6d9cd3c`** | **2,333 passes**, zero failures/errors, one unchanged manual skip; 285 XMLs, 246 executed tasks. Shared #229/#357 result, not an additional #356 execution |
| #229 and #357 scoped regression checks | 426 LAN passes/one manual skip, eight TXT controls, six focused watcher passes and two watcher controls; 13 final static gates. Shared final results above are not additional executions |
| #226 tooling regression checks at **`f085dc8`** | Complete dependency policy including 14 real synthetic-GPG tests, 13 intended red controls and 13 static/caller gates pass. Measured 102-byte physical socket bound; no live curation or hosted-CI claim |
| #225 static/caller controls | Four baseline invalid cases reproduced; 24 final actual-caller controls at `82be9c5` have expected outcomes. Fourteen final gates at `46ed124`, including 39 negative input/lock controls and 14 installer assertions, pass. Independent approval tripwires retained |
| #208 documentation/static checks at **`3a96a77`** | Three blocks byte-identical; baseline regression fails; five static gates plus Mac Ruby/scope smoke checks pass. No full-build rerun |
| Earlier clean `check` plus Android assembly at **`27fec6a`** | **2,276 passes**, zero failures/errors, one unchanged manual skip; 278 XMLs, 246 executed tasks. Actual ABI/constants, lint and Android assembly pass |
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
at `7127616`, not rerun for #332 Apple; complete release/XCFramework/Swift gates remain pending. Exploratory harness/environment
failures are preserved separately, not acceptance evidence. #332 Apple's 28 and #356's 28 cleanup receipts, #229's 34 and #357's six additional own
receipts, plus #226's 37, #225's 101, #208's ten, #152's 33 and #133's earlier 54 receipts are finalized, including failed and negative attempts; required evidence remains.
Do not add overlapping test totals. Controller/fake-manager tests and source wiring assertions are not rendered
Android UI, restoration, ART/OEM or physical-device proof. Final audit/release gates need the eventual combined tree;
whole-repository corroboration, eventual combined-tree release/consumer gates and external validation remain incomplete.

Earlier #317 corrected the diagnostic revision subscription and successful-clear invalidation through `f273b1b`.
Its [report](docs/audit/2026-09-04/repairs/317.md) preserves the real Compose regression evidence and the correction
to test-runtime wording: actual sample executor JDK21.0.7, not inferred from the JDK17 launcher. The latest passing integrated
tests at `78ef361` include those regressions; host snapshots are not rendered/device performance measurements.
Earlier #354 corrected the hotspot Failed card's cleanup retry and stale permission-admission callbacks through
`b6af5b8`; its [review report](docs/audit/2026-09-04/repairs/354.md) retains exact historical evidence. The latest passing
integrated run at `78ef361` also includes that correction; earlier `12e6cfa` results alone did not.
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

## Next: read #130 completely, then continue the remaining queue

1. #332 Apple, #356, #229 and prerequisite #357 are reviewed/pushed; do not repeat their repairs or misreport historical failures.
   Preserve strict original-byte/exact-key decoding, valid literal U+FFFD, unsigned byte bounds, generation-owned
   JVM/Android and Apple withdrawal and the real-clock test. Maintain 0.8.0+ admission scope.
2. The planned next issue is [#130](https://github.com/p2pKit/P2pKit/issues/130). Refresh/read its full body, comments,
   linked work and relevant closed decisions; verify current behavior and dependencies before implementing a fix.
   No #130 repair is included in this checkpoint. The #332 Apple row is approved again, retaining prior JVM/Android
   approval; neither that return nor the extra regression file increases the issue denominator.
3. Continue every actionable issue sequentially: **88 pending repair rows (87 low, one informational #333)**,
   21 external-validation rows and #120's architecture decision. Resolve precise external/product blockers honestly.
4. Investigate the other [unverified follow-ups](docs/audit/2026-09-04/followups.md); do not invent findings from suspicions.

#133's repository scope is approved; its independent interoperability remains **NOT STARTED**. Preserve #325's
protected-instruction caveat, #317's subscription regression, independent dependency approval tripwires, #226's short
GPG-socket ownership and all previous reviewed repairs. Whole-repository corroboration and final release gates remain.

## Continue the full audit and repair queue

1. Read `AGENTS.md`, `CLAUDE.md`, this handoff, the complete issue ledger and
   [unverified follow-ups](docs/audit/2026-09-04/followups.md). Preserve all existing user changes.
2. Record exact branch/commit/tree/status and refresh full GitHub issues/comments/linked PRs. Reconcile new evidence
   by underlying cause, not similar titles. Use exact local drafts if access is unavailable; never claim remote writes.
3. Continue all actionable issues sequentially, prioritizing severity/dependencies. Read the planned next issue #130
   completely; refresh the remaining queue rather than relying only on historical issue titles.
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
> This checkpoint has 61/171 independently reviewed repository repairs (35.7%) and 110 remaining rows (64.3%).
> Percentages exclude external acceptance still attached to approved rows, including #133 (independent interoperability
> NOT_STARTED). #332 Apple is approved/pushed at78ef361/tree0f8ab1465d257baac8110e3bd1ecf95859abe93c; full
> check+Android assembly passes2387/0 failures/errors/1 unchanged manual skip;14 static gates pass. All builds stopped
> owned workers/removed disposable module outputs; private evidence/shared caches/stashes/protected files preserved.
> The #332 Apple follow-up is complete for repository scope, not live multicast/TCP-handshake/external proof; its
> prior JVM/Android approval remains intact. Read planned next issue#130 completely before repair. Preserve0.8.0+ TXT-admission restriction, valid U+FFFD,
> strict byte limits, prior ownership fixes and independent approval tripwires. Read full issues, repair sequentially,
> create a fresh independent reviewer after each fix, address findings and review the final revision. Serialize bounded
> builds with unconditional scoped cleanup. Push safe summaries only to the audit branch; no force-push, main merge,
> issue closure, tags or release. Complete all remaining repairs and whole-repository/final release/consumer/Swift/
> XCFramework checks. Physical devices, hostile networks, independent interoperability/crypto assurance remain pending.
> Overall NOT READY. A clone transfers these source/context records, not accounts, private logs or a running chat session.
