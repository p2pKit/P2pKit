> **Current state:** #369 source APPROVED/localbd61175, NOT_PUSHED; trial1 failed before audit build/test
> invocations, remote cleanup/full-tree NOT_PROVEN. See the dated continuation sections below.
> The original250-line pre-trial report is preserved as historical evidence, not current publication/host status.

# Serialized hosted validation facility — source and Linux evidence

**8 September 2026: approved source, locally committed; publication and hosted execution are not recorded here.**
This is an unnumbered verification facility, not an additional approved repair or a release decision.
The audit remains **71/182 approved repository-repair rows (39.0%), 111 remaining (61.0%)**:
89 repairs (88 Low and informational #333), 21 external rows and architecture decision #120.
#223 remains the latest numbered approval; #268 is **NOT_STARTED**. Independent #133 is **NOT_STARTED**;
whole audit **NOT_READY**. Preserve [earlier repair reports](README.md) and every recorded failure.

## Exact source and independent review

- Commit: `731f98db90668f098c6025d3a0df6e863a951197`.
- Tree: `6b259c267299be73f5c089fc401b965eea48c307`.
- Parent: `6a32df43bc04742075fd124306eacb4515c0fb03`, tree
  `e48b5f527b4079612f3544f2e8efb5974f787ec0`.
- Exact 18-file diff SHA-256:
  `a95f3cb5817cf20c9ac2c373fbe58a6682c480b00584a8925c50ee98c955a32a`.
- Local commit receipt: **18:14:47.552411–18:14:47.607116 UTC**. This is not a push/ref or hosted-run receipt.
  The earlier candidate executions/readings remain explicitly precommit; the identical later tree does not
  retroactively turn them into clean-commit executions.

Twelve new and six modified paths provide the serialized workflow, native command ownership/receipts,
host prerequisite/source/artifact checks, consumer metadata/retention, audited leaf hooks and regressions.
The complete path list is in [checkpoint metadata](checkpoint.json), and the operational contract is
[the hosted-check guide](../../testing/audit-hosts.md). Protected `AGENTS.md` and `CLAUDE.md` remain unchanged.

All three fresh scoped reviewers approved the **final exact revision**, after actionable N1–N3, C1–C3 and
W1–W2 findings were resolved. Each inspected the complete issue/context for its boundaries, actual callers,
source/delta bindings, final evidence and peer integration boundaries. No open actionable finding remains.

| Scope / reviewer | Final verdict | Private report SHA-256 |
| --- | --- | --- |
| Native executor — `/root/review_host_native_r1` | APPROVE | `a109212cf47b1d9780d3909b8f2d4020957897a942dcdf2c48aa401a3a111246` |
| Consumer/leaf — `/root/review_host_consumers_r1` | APPROVE | `176c0e1f2baf1f1b96066199f1030afa35575da5a625e0fb78927a96b0bf432b` |
| Workflow/host/guide — `/root/review_host_workflow_r1` | APPROVE | `238cadaa30641f175df096fd784a231fccd94c56afff14435ed12dd8fcbfcd51` |

Approval is for **source publication and a controlled hosted trial**, not actual Windows/macOS/Apple,
product/release or whole-audit acceptance. The immutable source-review packet indexes **1,363 files /
26,023,704 bytes**, manifest SHA-256 `d52968620e98117b45c9a31bf71908256d3143cafa1ef9a7ee29a74bb3239b39`.
Its original approval-pending metadata is preserved; the later final verdicts and commit are additive.
This report and the administrative increment require their own final-byte review; source approval does
not automatically approve later authored ledgers.

## Final Linux fixture/static cohort

**22 serialized commands PASS**, **17:28:33.459860–17:32:54.519947 UTC**, at parent `6a32df4` plus the
staged `a95f3cb…` diff, not clean `731f98d`. Every command/final/wrapper-stop exit is zero, source remains
unchanged and outer receipts record no owned survivors. This cohort has no product-test XML.

| Main fixture command | Observed scope |
| --- | --- |
| `python3 scripts/tests/run-audit-command-test.py --expected-host linux-x64 --evidence-root <owned-private-evidence>` | 49 methods: 15 pure + 34 Linux native/inherited |
| `python3 scripts/tests/audit-consumer-test.py` | 32 methods |
| `python3 scripts/tests/audit-leaf-hooks-test.py` | 27 methods |
| `python3 scripts/tests/audit-host-test.py` | 65 methods |
| `python3 scripts/tests/audit-host-workflow-test.py` | 51 methods |
| `bash scripts/tests/run-ios-app-test.sh` | 23 lifecycle methods and 17 shell assertions |

The native command's private evidence-directory argument is a safe placeholder above; exact arguments
and timestamps are retained privately. The other sixteen commands are wrapper integrity, wrapper tests,
dependency verification, dependency-update policy, repository layout, OSV lock coverage, Markdown links,
release metadata, Git whitespace, CI policy, release-workflow fixtures, Kotlin toolchain policy,
platform-test policy, platform-driver fixtures, sample profiles and `git diff --check`.
[Checkpoint metadata](checkpoint.json) binds all 22 invocation receipts individually. Do not add Python
methods/shell assertions to product XML counts or reinterpret Linux fixtures as foreign-host execution.

Historical correction controls and limitations remain:

- N1: the actual Gradle 9.7 parser accepted **16 of 18 attempted forms**, not all 18. N1/N3's red probe
  was four methods/243 assertions; two original module assertions did not inject the old APIs.
- N2: old cleanup caused one intended ERROR before archival; authentic recovery was a separate action.
- C1: a UUID-qualified whole-chain-retirement obligation is retained, with cleanup registered before producer
  startup; absent/partial bindings retain work.
  The strip mutant gives two intended failures. Authentic cancellation records final125/stop0 **before**
  fallback; five of six identities needed fallback. Fallback always fails the native control and is not
  a cancellation-cleanup PASS. Those failures and original REQUEST_CHANGES reports are not overwritten.
- C2 uses the real Linux executor and actual consumer script with **synthetic wrappers and metadata=0**,
  not actual artifact publication, consumer compilation or metadata=1 dependency resolution.
- C3 preserves explicit borrowed STATE/work on every outcome; namespace ownership alone is not native
  cleanup proof. Outer fixture receipts' `removedOutputs=[]` is not proof that no nested fixture cleaned up.

## Separate fresh Linux product verification

`hosted-final-r1-linux-integrated`, **17:41:47.894987 → 17:50:29.240746 UTC**, finalized
**17:50:31.073763 UTC**, ran:

```bash
./gradlew check :p2p-sample-android:assembleDebug :p2p-core:dokkaGeneratePublicationHtml \
  --rerun-tasks --no-build-cache --no-configuration-cache --dependency-verification strict \
  -Pkotlin.compiler.execution.strategy=in-process \
  '-Dorg.gradle.jvmargs=-Xmx2048m -XX:MaxMetaspaceSize=768m -XX:ActiveProcessorCount=2 -Dfile.encoding=UTF-8' \
  --max-workers=2 --no-parallel --console=plain
```

**PASS: 1,607 cases / 199 TEST XMLs / 234 executed tasks**, zero XML failures/errors/skips. This executed
on **`6a32df4` plus staged `a95f3cb…`**, not a clean `731f98d` or future administrative commit, and used
the existing private local runner, **not the new hosted executor**. The later clean-source invocation below
has a different sample-task scope and its own receipt/review; these records are not interchangeable.

`/root/core_protocol_fixture_corroboration` independently parsed all current and prior XML, lint/HTML
summary counters, source bindings and finalizer records: **CORROBORATED within local Linux product scope**.
All **1,607 task-qualified case identities/outcomes match** the earlier #368 run; none added, lost,
duplicated or changed. Overlapping runs are not 3,214 unique cases. All twelve XML-producing tasks remain:
core789+62; Android provisioning145; Desktop provisioning16; LAN197+106; Android sample95;
CLI46; Desktop UI35; diagnostics110; shared KMP5+1. Backlog regressions remain present.

ABI/constant/build-info/lock gates, Android lint/sample assembly and strict core Dokka complete. No APK or
rendered Dokka output tree is retained for content inspection. A **Java21 Gradle daemon** was observed;
`JAVA_HOME=17` and XML without JVM-version properties do not prove every test JVM was17. Apple tests
remain **SKIPPED**; six cinterop/KLib warnings, Android native-strip warning and SLF4J NOP diagnostics
are retained. Zero XML skips is not Apple/ART/device execution, visual sample or published-consumer acceptance.

- Independent product report SHA-256: `3aa9780b60acbdd8e9cc91e79b326aa2ad4db7ff0f01cbad3e6308f58dfb608f`.
- Current retained files: **889 / 5,398,248 bytes**; prior comparison: **889 / 4,720,005 bytes**.
- Invocation receipt SHA-256: `ae5dcfa46a6b297fbe6f8273b77df0415f2e1e8e90025ae65e64613f7affb124`.
- Command log SHA-256: `29e87ecadad69f929601430fbbcfa48d725ffaee061f7fe8f4964170a69569f7`.

## Later clean-source Linux check and Desktop samples

`hosted-731-clean-linux-check-samples` executes at **clean731/tree6b259**, with empty source diff and
unchanged before/after snapshots. **18:16:25.687320 → 18:24:22.385600UTC**, finalized
**18:24:24.350269UTC**; command/stop/final exits0. It does not overlap the earlier finalized run.

```bash
./gradlew check :p2p-sample-desktop:check :p2p-sample-desktop:installDist \
  :p2p-sample-desktop-ui:test :p2p-sample-desktop-ui:checkRuntime \
  :p2p-sample-desktop-ui:hotRunArgfile :p2p-sample-desktop-ui:createDistributable \
  --rerun-tasks --no-build-cache --no-configuration-cache --dependency-verification strict \
  -Pkotlin.compiler.execution.strategy=in-process \
  '-Dorg.gradle.jvmargs=-Xmx2048m -XX:MaxMetaspaceSize=768m -XX:ActiveProcessorCount=2 -Dfile.encoding=UTF-8' \
  --max-workers=2 --no-parallel --console=plain
```

**PASS1,607 /199TEST XMLs /205executed tasks**, zero failures/errors/XMLskips.
Fresh independent `/root/review_linux_731` verdict: **CORROBORATED within this Linux execution's scope**.
All1,607 task-qualified identities/outcomes match the precommit run, noadded/lost/duplicates; not additive.
The successful rootcheck and CLI/Desktop tasks include CLI installation and Desktop runtime/argfile/distribution
creation, but **no retained package/runtime/argfile contents or launched sample application** were inspected.
This run does **not** execute Android `assembleDebug` or core Dokka; those remain in the precommit run.
It is a combined rootcheck+Desktop command, not a newly executed standalone-only `check` command.
AppleSKIPPED/sixcinterop-KLib warnings remain; Java21Gradle daemon observation is not alltestJVM17 attestation.

The independent reviewer rehashed **889current files /4,717,315bytes** and889prior files/5,398,248bytes.
The stop reports one daemon stopped; one invocation-owned daemon before retirement, no final survivors;
**11disposable roots /1,196,181,541bytes** removed after retention. These are retained cleanup records,
not independent live historical removal. Source/shared caches are preserved. No hosted or external acceptance.

- Independent report SHA-256: `3d617f28efcd675fd0efcaa5546ba11fbea566c5f90bbdc0c58ff4942fb731d4`.
- Review manifest SHA-256: `b3d1d83a81a458183376c9b9836e2a17cf3e8c789efa08405fcd643880e4a6a6`.
- Receipt SHA-256: `40090db9e9c9e80d781bb78df0cb17a1d95f67a294c7f153d5b1205733180286`.
- Command log SHA-256: `533a7f46687f1835bd1f93b17b0502013ee2ff6c5a91430c2f0c8e642fa6b615`.

## GitHub reconciliation and latest list-only refresh, not an execution lease

A fresh local capture at **16:02:38.964754–16:08:26.627459 UTC** obtains **289 issues (182 open/107 closed)
and 79 PRs (7 open/72 closed)**. All **368** own bodies/comments/timelines and all PR detail/review/inline/
file/commit collections are fresh; zero reused current histories. Effective counts:490 comments,
4,204 timeline events, zero PR reviews/inline comments,1,817 PR files and277 commits. All182 open IDs
match the ledger. No new distinct defect or product/architecture decision was established by this refresh.
This captures/programmatically compares full narratives; it is not a fresh semantic/caller audit of each.

The exact end-list request is **16:08:14.099011–16:08:18.882642 UTC**, SHA-256
`d4866aa4cf570e77ffe9c2068c095d84d94bfebc1739c97458a36fe9ff3ff6b1`. Earlier10:30 capture,12:28 list,
individual outcomes and historical row-level GitHub observations remain unchanged, not rebound.

Bounded first-hop context captures all returned pages for117 upstream PRs;109 reconcile every expected
aggregate. Eight objects still lack **seven reported inline and three reported conversation records**
despite recapture/controls and65 alternate per-review endpoints. These are checkout1941/1977/2044/2194/
2286/2356/2454 and dependency-review-action1077. Their reported-count completeness is **not established**;
no cause or missing text is invented. Local402/upstream33 patch fields are omitted by the API; full textual
patch reconstruction is not claimed.117 upstream PRs are dependency context, not additional audit rows.

All **2,927 GET attempts** returned200. The separate operational observation ended **16:33:33.620426 UTC**,
with active union0, audit ref `6a32df4`, main `eb444ccc…`; this is **not current idle proof or a lease**.
Refresh before any trigger. The later upstream supplement (through16:38:36) does not extend local freshness.
Private refresh seal: **9,535 files / 438,832,855 bytes**, manifest SHA-256
`a87ea8b3356129c2348413a15fb4e367ff7f10741383836fb9e306ccbad9b9a1`; report SHA-256
`222c6c58e604c75950fd8eba2c1c1d208d18d11d41eb2b471b3e35eb719312da`.

A later **18:28:29.801258–18:28:54.005611UTC** incremental observation has fresh own-body/all-state lists,
with final issue/PR list requests **18:28:41.929318–18:28:47.756256UTC**, value-identical to16:08.
All182open IDs still reconcile. **Zero histories/PRdetailsets were refetched**: all368histories/79PRsets
are explicitly **reused16:02–16:08**, and117upstream context/gaps retain their older scope. Unchanged
counts/updated_at/bodies do **not** prove unchanged comment payloads or timeline-only decisions at18:28.
The latest Actions/ref point **18:28:48.059338–18:28:51.724627UTC** returns active0,audit6a32/main eb444;
not pre-push idle proof or a lease. Refresh immediately before any controlled trigger.

The first private collector stopped closed after2successful GETs on a legitimate numeric-repository alias;
its partial/error history remains. The corrected capture completes26GETs/14collections/20pages.
All28GET attempts returned200; that does not erase the initial collector failure. No source/Git/remote writes.
Latest incremental report SHA-256: `771874f6b78359c0e1aff94ccc1fe4cd429f3a8e85e4bc19b80237bbe3e9fa19`;
manifest SHA-256: `880bed193de749fcab8d5c84afe6dd27f7db29bef109594c1ba0c979c0ebcc9b`.

## Read-scope projection and administrative correction

The source read receipts support **nine complete-text final-byte bindings and nine composed semantic-delta
bindings**, not eighteen fresh full-file scans. Complete prior source reads plus every correction delta are
credited as delta-composed; hash-only peer observations do not upgrade another scope. Exact SHA/blob/reviewer
bindings and the six replaced existing read rows are preserved in checkpoint metadata. Precommit reads retain
`NOT_RECORDED` readCommit; later commit731 is a separate exact-byte binding, not a retroactive read event.

The final projection has **1,060 paths**: the preceding1,047 plus12 new facility paths and this report,
checked against actual tracked membership. **All5,235 historical five-column cells** from the preceding
projection remain unchanged (the transfer5,190 and previous5,230 also remain). Six reopened administration
rows and the self-excluded coverage row remain byte-identical. Unchanged callers are not silently reapproved.
The report row needs a separate actual final-byte full-text receipt, not source-review credit or an invented
future commit; report authorship/read is not independent administrative approval. The final ledger records
**783 full-text,10 semantic-delta,259 structural-only,one partial XML,six reopened and one self-excluded**.
These are read dispositions, not repaired-issue percentages or whole-current-source semantic certification.

One existing navigation reference is narrowly corrected: `previousScopedVerification368.focusedExecutionBinding`
now points to `previousAffectedGateAttempt368`, not the #223 object in `latestAffectedGateAttempt`.
The identical old pointer was correct at `b4a9248`; administration `6a32df4` moved368 into historical keys
without retargeting it. Original text and diagnosis are retained additively. No product consumer/defect or
new approved issue row follows; no commands, outcomes, candidate hashes or historical approvals are changed.
#223's original issue assessment and all original repair reports remain verbatim, with a dated successor note.

## Cleanup, publication and continuation

Every final fixture/product invocation retains required logs and runs the applicable task-isolated wrapper
`--stop`; all stops exit0, and final receipts record no owned survivors. The precommit product stop reports one daemon
stopped; one owned daemon was recorded immediately before escalation. **11 disposable output roots /
948,478,230 bytes** were removed after report retention. This is corroborated helper/log/receipt evidence,
not independent live observation of historical termination/removal. No blanket `build` deletion is authorized:
`buildSrc/src/main/java/dev/p2pkit/build` is source. Preserve source, user changes, shared caches, raw evidence
and unrelated tasks. Metadata/document preparation itself runs no tests and owns no Gradle workers.

Next steps, without a checkpoint stop:

1. Preserve both separately corroborated Linux product runs/cleanup, and obtain final-byte independent
   administrative approval; source reviews do not approve these later ledgers. Verify any subsequent audit-branch
   push separately. No push or hosted execution is established by the local commit receipt above.
2. Refresh Actions and hold one global local/hosted build lease. Run **Windows2025 → Mac26 ARM/Xcode26.5 →
   Mac15 Intel/Xcode26.3**, with mandatory actual-host native controls, strict same-source receipts, full evidence
   manifest and successful artifact-upload ID inspection before advancing. Do not cancel unrelated work.
3. Preserve every failed/uncertain component as red. The release monolith remains
   **NOT_EXECUTED_COMPONENT_REPLAY**; component replays are not its execution. Windows facility success alone
   would not prove Windows Native/AAPT2 or all #367 acceptance. #144 scheduling still needs separately
   authorized default-branch merge/manual-or-scheduled complete-CI evidence; no merge is authorized.
4. Continue planned#268 and the remaining dependency-aware repairs, after any actually reproduced prerequisite
   receives sequential correction and a fresh independent final-revision review. Preserve defensive ownership,
   security, assertions and0.8.0+ admission restrictions. Keep suspicions separate and deduplicate confirmed causes.
5. Finish current whole-repository corroboration, `./gradlew check --console=plain`, applicable real samples/
   isolated consumers and inspected release/Apple gates. Physical Android/Apple, ART/API24–25/OEM/radio,
   hostile-network/headful/fault-injection, independent secure-v2#133, professional crypto and architecture#120
   remain separate participants/equipment/decision blockers, never inferred from a host/simulator pass.

Raw evidence, credentials, payloads, device identifiers and generated artifacts stay outside Git. Push only
focused approved source and safe checkpoint documents to the audit branch; no force-push, main merge,
settings/tag change, release publication or issue closure is authorized.

## Prior administrative approval and verified publication

The original250-line pre-trial report above is preserved verbatim; its publication/hosted-pending statements,
71/182 counts and then-next steps are historical, not the current state. The exact eight administrative files
were independently **APPROVED** by `/root/review_host_admin`:616initial comparisons/zero discrepancies,
then applied-state98comparisons plus112immutable rechecks/zero discrepancies. Review SHA-256
`acb7332405c101ef54bff5c844a3e7cd6dc759a7596324f2615c2c76ab90cb42`; applied addendum
`65d9091555342c4ee1670a5146a0723131a01020c36ec463157c61b7676a8e25`.
Eight serialized application/static gates19:12:24–19:12:33UTC passed:4,980invariants;354links/72active files;
10projects/15layout negatives;10OSVlocks;release metadata;whitespace;both diff checks. All command/stop/final
exits0, no owned survivors or deleted outputs; zero product XML. Original private newline-oracle false
findings and corrected inspection are retained; no product failure was erased.

Administrative commit **`bb0fd25f9ac40ca9bceb8bdfbb0ad104baae6d63`**, tree
`7568fd93ac50fafe09f5fad91f03f5d8be138622`, parent731, committed19:20:06UTC.
Push19:21:43.614854–19:21:46.322010UTC returned0. Its receipt explicitly did not verify the remote ref;
a **separate19:22:14.560386–19:22:22.361426UTC** observation matched auditbb0 and main
`eb444cccfc290be5435c5c10629c24183293606f`, and observed the resulting active run below.
This publishes the facility and approved safe administration, not a product/host acceptance or later369push.

## First hosted trial — terminal prerequisite failure

**CORROBORATED terminal prerequisite failure before audit build/test invocations**, not infrastructure,
product, cleanup, release or external approval. Run **[34268510397](https://github.com/p2pKit/P2pKit/actions/runs/34268510397)**,
attempt1, audit-branch push, sourcebb0/tree7568. Windows job102203889802 ran19:21:53–19:22:16UTC on
windows-2025, image `win25-vs2026`/`20260824.214.3`; driver19:22:05–19:22:09.
Host summary19:22:06.236774–19:22:09.765212; handoff19:22:09.898192; upload19:22:11.447717.
ARM102204036742 and Intel102204037776 were skipped without steps or allocated runners.

Native Python's `Host.prerequisites` used bare `["bash", "--version"]`; it returned1 with WSL's
no-installed-distributions diagnostic. Python/Git/Java17/Java21 queries returned0; RAM17,174,360,064bytes.
Exception: `Required tool version query failed`. The log identifies Git's native executable but establishes
neither an exact Bash executable path nor Git Bash's existence/success. The same ambiguous bare Bash
also existed in the later wrapper fixture. This distinct cause is [#369](repairs/369.md), not #223 or #367.

Admission/initialization/source/native/JDK/version subprocesses ran. Initialization is not a Gradle invocation
or native ownership test suite. Bound source ordering plus `components=[]` establish failure before first
`invoke`: **native controls, Android setup, wrapper fixture, Windows library/Desktop builds and all Apple
components NOT_STARTED**. No audit build/test leaf began, so **no applicable Gradle stop existed; none ran**.
This does not imply no host subprocesses or prove their descendants retired.

Artifact **10072826523**, `audit-host-windows-x64-34268510397-1`, has7,741bytes, SHA-256
`7ff7102aa8deaa509ca2e065e70566bf6247b69feeb3ffd6ce66d811fbd10816`.
Fresh independent `/root/corroborate_host_trial1` decoded saved authenticated run/job/commit/acquisition/
upload records and CRC/SHA-inspected all13members/13,435expanded bytes offline, without another authenticated
GET. Returned bootstrap12entries/12,239bytes, salvage7/9,462 and nested5/8,440 manifests match; these sets
overlap and are not additive. Salvage copied6files/8,864bytes with0omissions, yet full-tree completeness
explicitly remains **NOT_PROVEN**. No omissions is not a remote-tree or process-ownership proof.

**Preserve `safeToContinue=false`, `driverSafeOutput=false`, `PARTIAL_SALVAGE`, full-tree/remote cleanup
NOT_PROVEN.** Unsafe finalization skipped output/work disposal; terminal job/orphan-cleanup text is not
per-identity retirement. Original private inspector falsely rejected the real no-colon/is Artifact ID syntax;
independent identity corroboration resolves that parsing diagnosis only. Its valid partial-evidence finding,
original failed inspection and all raw bytes remain. Private parser correction does not create a repo issue.

Operator reconciliation19:57:07.281264UTC retained archive/raw failure evidence and recorded **no raw/archive/
remote-state/local-output deletion**. An all-five-active-status-empty observation19:55:59.733652–19:56:06.576158
returned auditbb0/mainunchanged, but is a point observation, not a current/server-side lease. The **local
cooperative build lock only** was released19:57:23.815919, with no source-freeze violations, on the narrow
terminal-pre-first-audit-invocation basis. This does not turn the remote unsafe handoff into safe continuation,
certify cleanup or accept a host/component. Subsequent trials require a fresh lease and evidence of their own.

- Independent trial report SHA-256: `9abcdd77bf321eb304c5fbb06e17f2414a5d9775be1618edc861b48d8462e65f`.
- Exact safe retention/ref/release bindings are recorded in [checkpoint metadata](checkpoint.json), not private paths.

## Later complete GitHub capture and individual #369 addition

Fresh local own histories/PRsets **19:17:06.237470–19:22:50.252664UTC**:289issues/182open/107closed,
79PRs/7open/72closed; all368histories and79PRdetailsets fresh, zero reuse.490comments/4,204timeline/
0reviews/0inline/1,817files/277commits. All182then-open IDs reconcile. Actual complete own body/comment/
timeline payload comparisons versus16h find0changes;44PRdetails differ only embedded pushed_at,
79PRlist records only embedded repository metadata. This is not inferred from equal counters.

117first-hop PRs were freshly captured19:24:05.838850–19:30:42.647956, supplemented19:33:09.567975–19:33:23.885385.
109count-complete; same8upstream gaps/7reported inline+3conversation records persist.465existing timeline
payload deltas are metadata only:457repository,5nested milestone,3nested author-association. No body/decision
change or new defect was established by that capture.402local/33upstream patch omissions remain.
**2,927GETs/0failures;1,891collections/1,982pages**. The seal binds9,556files/432,388,200bytes,
manifest SHA-256 `095bb682626fdf4c39b1858cbfebcaa4dfd1eb7f51ad007c87856d86b36b10a5`;
report `9334f2dd63347a2518459233e32a67597e802b92e8747c8766dca6123d8c285b`.
Sealing19:50:01 does not extend local freshness; first-hop collection is bounded, not a semantic re-audit
of every unchanged narrative/caller or reconstruction of missing text. Earlier captures/gaps remain intact.

A fresh **19:59:24.646456–19:59:29.370117UTC list-only** preflight is unchanged. #369 was individually
created20:00:00Z/refetched20:00:01.894153UTC, OPEN; known totals then290issues/183open/79PRs, not a
post-addition full inventory capture. The initial71/183approved,112remaining,90repair filing state stays
historical. Its later independent source approval changes the current repair numerator separately.

## Current continuation after the #369 source approval

[#369's exact four-file repair](repairs/369.md) is final independently **APPROVED** with no findings and locally
committed **`bd61175167337fee585855cbbe5bfae9c0122dc5`**, tree`95bb599cebc45d80d0a5c632fb2b84e240e14a30`.
Its19final Linux fixture/static gates pass atbb0+staged1187, not cleanbd61175;24total leaves retain earlier
mistakes/intended failures. Verification manifest binds203files/11,950,534bytes. No product Gradle check,
native rerun, push or public outcome is recorded for369; no second trial is invented. Original731/precommit
product results remain at their own source and are not rebound. Release monolith remains
**NOT_EXECUTED_COMPONENT_REPLAY**. Source approval alone does not complete #367 foreign-host acceptance.

Current counts: **72/183approved(39.3%),111remaining(60.7%)**,89repairs/21external/#120;50new auditfindings.
The new report adds one coverage path; four changed source rows have actual complete final precommit reads
by the fresh369reviewer. Earlier5,300historical cells and all prior source/read records remain; six reopened
admin rows/self-excluded output are not promoted. Final report reads and independent administration approval
are separate from the source approval. A shell-CRLF checkout-policy concern is **unconfirmed**, not an actual
trial failure; no speculative repair/issue is bundled. #268 and independent#133 remainNOT_STARTED.

Obtain independent final-byte administrative review, then publish safe source/ledgers only to auditbranch and
record matching ref/outcome separately. Refresh live Actions, freeze exact source under one global local/hosted
build lease, rerun Windows→ARM Mac→Intel Mac with mandatory native controls and inspected strict/source/
stop/ownership/full-artifact receipts; failed/uncertain components stay red. Serialize bounded-memory builds,
at most two Gradle workers/no parallel. Retain required logs, stop only owned invocations/workers and remove
only confirmed disposable outputs after dependent checks; preserve shared caches/source/user work/private evidence.
Continue all feasible sequential repairs without a checkpoint stop; physical devices, hostile networks,
independent interoperability, professional crypto and #120 decision remain separate. Whole audit **NOT_READY**.
