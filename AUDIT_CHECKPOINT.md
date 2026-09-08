# P2pKit audit continuation checkpoint

**Updated: 8 September 2026. Requested transfer checkpoint; not a release approval.**
The #360 archive-whitespace prerequisite and #144 CI-scope correction are independently approved and pushed,
with separate final reviewers. Earlier repairs are preserved. Full check, Android assembly and strict core Dokka
pass at `6995130`. **67/174 repository repairs reviewed (38.5%); 107 rows remain (61.5%).**
Stop here for the device transfer; **next issue #145 has not started**. #133 independent interoperability remains
NOT STARTED. Read this with unchanged `AGENTS.md`/`CLAUDE.md` and the complete tracked issue/coverage ledgers.

## Resume from a fresh clone

```bash
git clone --single-branch --branch audit/complete-2026-09-04 https://github.com/p2pKit/P2pKit.git
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
- Latest independently reviewed source: **`6995130bcdb2594257c42bed006f7d23f5bc4d6a`** (#360 and #144 CI corrections).
- Its tree: **`323fc39587c626df7ac9da1edce7cc0ab80ac313`**; clean at final verification/review.
- #229's fourteen-file correction is `bf34f70b13ceab1549741b09647fec0b603b15c0`; all fourteen blobs were unchanged
  at combined revision `6d9cd3c`, not at current HEAD: #356 subsequently changed the common parser and release docs.
- Latest full `check`, Android sample assembly and strict core Dokka at **`6995130`**: **PASS**, **2,459 passes**, zero
  failures/errors and one unchanged manual LAN interop skip; 297 XMLs, 256 executed tasks. Twenty-three final static/policy
  gates and five actual YAML command replays pass, including actual Android ABI graph verification; API baselines are unchanged.
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

| Disposition at this checkpoint | Count | Percentage of 174 inventoried issues |
| --- | ---: | ---: |
| Repository repairs with independent approval | **67** | **38.5%** |
| Pending repairs | 85 | 48.9% |
| External/platform validation | 21 | 12.1% |
| Architecture/product decision (#120) | 1 | 0.6% |
| **Total remaining issue rows** | **107** | **61.5%** |

These percentages count repository-repair rows, not effort, file coverage, issue closure or production readiness.
#360 adds one distinct finding; #360 and #144 add two approved repairs. External acceptance still attached to
approved rows (including #133) is not counted complete; independent interoperability remains separately pending,
not implied by 67/174. The 8 September 06:34 UTC GitHub list refresh found 281 issues across all states and 174 open issues.
The ledger identifies **41 new-audit findings**, including #360. Refresh complete issue bodies, comments, timelines
and linked work before relying on any entry. Historical assessments retain their original scope.
Rounded category percentages may not sum to exactly 100%.

All 67 currently approved repository-repair rows are in this branch's history. #325's protected-file exception remains.
Issues remain OPEN under the completion policy; nothing has
been merged, closed or released by these pushes. See [every disposition](docs/audit/2026-09-04/issues.md) and
[scope, dependencies, commits and public outcomes](docs/audit/2026-09-04/issues.json).

## Completed work and verification

Recorded cycles include dependency/provenance/publication gates, coroutine cancellation/ownership, LAN rebind/cleanup,
secure-v2 tests, provisioning callbacks, sample pairing/privacy, file source/destination safeguards, diagnostics,
Android API24/25 diagnostics and iOS integration. These are scoped repairs, not proof of complete subsystem correctness.

Latest #360 repairs the pre-existing all-tree whitespace blocker without modifying historical evidence.
Three exact-path/category exceptions preserve bytes and require SHA-256 integrity in head, index and worktree at
both actual gate entry points. Fresh `/root/review_360_r1` **APPROVED** the complete seven-file correction at `6995130`.
The original pre-#144 manual gates both exited 2; the ordinary-range control passed. Final 51 labeled assertions and
ten expected-red controls/two positive controls establish the correction; #223's separate wrapper defect stays pending.
See [the #360 report](docs/audit/2026-09-04/repairs/360.md) and [verified outcome](https://github.com/p2pKit/P2pKit/issues/360#issuecomment-5580382007).

#144 now classifies every complete main-push delta instead of inferring passed checks from graph/tree equality.
Genuine nonempty Markdown-only changes remain lightweight; source, rename, empty and fallback safeguards remain.
The weekly Monday 04:17 UTC full backstop is isolated and non-cancelling, not a scheduling deadline. Existing
Linux/Windows jobs, permissions, required checks and release provenance are preserved. Fresh `/root/review_144_r1`
**APPROVED** the complete eight-file correction plus #360's prerequisite effects at the same frozen `6995130` tree.
See [the #144 report](docs/audit/2026-09-04/repairs/144.md) and [verified outcome](https://github.com/p2pKit/P2pKit/issues/144#issuecomment-5580383643).

Combined verification: **2,459 passes, zero failures/errors, one unchanged manual skip; 297 XMLs, 256 tasks**.
Resolver28/policy21 checks, five actual YAML command replays and 23 static gates pass; 13 #144 expected-red controls
and two positive controls pass as verification outcomes. Both reviews inspected shared sealed evidence:
3,558 files/18,444,319 bytes, 106 finalized cleanup receipts and 95 nonoverlapping leaf invocations.
Initial YAML replay, first #360 control-verifier and first evidence-sealer failures are retained, not relabeled.
No production/API/ABI/protocol/dependency or archived-content change. No hosted CI, Windows execution, administrator
bypass, physical-device or independent interoperability validation occurred in these cycles. The schedule is not
installed on the default branch until an authorized merge. Both issues remain OPEN; main is unchanged.

Earlier #359 completes failed-destination settlement despite caller cancellation during abort. Both generic
setup catches retire ownership, perform independently bounded abort, publish the original typed failure and attempt
the existing bounded entry-epoch-fenced terminal notice before restoring structural caller cancellation. Callback-only
cancellation remains distinct; no shared bounded helper, API/ABI, wire, authentication or durability implementation
changed. This is not an authentication bypass, budget leak or demonstrated file loss.

Fresh `/root/review_359_r1` **APPROVED** the complete four-file correction at `de88284`, independently verifying
1,797 sealed entries, 297 final XMLs, 26 new method executions and 28 finalized cleanup receipts. Original production
with final tests gives eight intended JVM failures/two controls and seven Android-host failures/nine controls.
Focused checks pass 33/33; three mutation controls and fourteen static gates pass. Full check, Android assembly and
strict core Dokka: **2,459 passes, zero failures/errors, one unchanged manual skip; 256 executed tasks**. Two genuine
compilation failures and the first evidence-verifier failure are retained, not counted as passes. Source and
[verified outcome](https://github.com/p2pKit/P2pKit/issues/359#issuecomment-5579078847) are pushed/refetched; issue OPEN. See
[the repair report](docs/audit/2026-09-04/repairs/359.md). Real pinned kits over in-memory wires preserve another transfer
and messaging; host/Native simulator results are not physical devices, real LAN or independent interoperability.

Earlier #358 fixes destination setup error classification without reclassifying actual channel authentication.
Both local catches are statically file-typed, preserving original local causes and existing file-error identity.
Tests establish terminal retirement/abort, sanitized replay, restored admission capacity and same-session recovery.
Pinned secure kits over exact/fragmented/coalesced in-memory wires retain another transfer and messaging.
No API/ABI, wire, authorization, dependency or durability implementation changed. The install sibling cast is removed
without claiming another currently reachable application-authentication callback there.

Fresh `/root/review_358_r1` **APPROVED** the complete four-file series through `d424a23`, independently verifying
1,736 sealed entries, 296 final XMLs, 26 targeted regression executions and 26 finalized cleanup receipts. Original
JVM production gives two intended failures/three controls; Android original-production control gives three intended
failures/five controls. Corrected focused tests pass 21/21; three mutation controls and fourteen static gates pass.
Full check, Android assembly and strict core Dokka: **2,433 passes, zero failures/errors, one unchanged manual skip;
256 executed tasks**. The first focused compilation failure is preserved, not counted as a pass. Source was pushed
and the [verified outcome](https://github.com/p2pKit/P2pKit/issues/358#issuecomment-5578319370) refetched; issue OPEN.
See [the repair report](docs/audit/2026-09-04/repairs/358.md). That review's then-unverified cancellation-during-abort
observation was subsequently reproduced, filed and independently repaired as [#359](docs/audit/2026-09-04/repairs/359.md).
The historical #358 report is unchanged; its cast approval does not itself cover the later cleanup correction.

Earlier #137 adds multiplatform volatile visibility to the four diagnostic-cause slots and documents the existing
prepublication-only attachment invariant. Copies deliberately omit causes; mangled Java setters remain callable but
unsupported. No constructors/value semantics/ABI, production attachment sites, dependencies or protocol/security
policy changed. The compatible correction is not an immutable-error redesign or proof of a previously active race.

Fresh `/root/review_137_r1` **APPROVED** the complete five-file correction at `a5d3145`, independently checking all
19 production attachment sites, 1,798 sealed entries, 295 final XMLs, five intended assertion-red controls and 25
finalized cleanup receipts. Original production plus new tests gives eight structural failures/six passing controls;
corrected focused checks pass 72/72. Full check, Android assembly and strict core Dokka pass **2,407/zero failures/
errors/one unchanged manual skip; 257 executed tasks**, with fourteen static gates and eight actual volatile-field
classfile inspections. Real secure-kit tests exercise different-thread feature-failure publication and retention
through shutdown using synthetic memory-only identity storage. StateFlow already synchronizes publication.
Source was pushed and the [verified outcome](https://github.com/p2pKit/P2pKit/issues/137#issuecomment-5577645103)
posted; the issue remains OPEN, not merged/released. See [the repair report](docs/audit/2026-09-04/repairs/137.md).
That review's then-unverified destination-error cast concern was subsequently reproduced, filed and repaired as
[#358](docs/audit/2026-09-04/repairs/358.md) above; the historical #137 report remains unchanged.
Host/arm64-simulator checks are not physical, ART/OEM or independent crypto evidence.

Earlier #130 makes both provisioning test registrars retain nullable fingerprint pins. Each platform now checks two
distinct remote pins against every ordered forwarded argument, with a different local identity; deprecated calls
assert null even with a local pin present. Exact value equality is the inline-class contract, not boxed identity.
No production, API/ABI, security, legacy behavior or dependency change was needed.

Fresh `/root/review_130_r1` **APPROVED** the complete two-file correction at `1847ed3`, independently checking
1,930 sealed entries, 310 retained XMLs (290 final), eight intended assertion-red controls and 30 finalized cleanup
receipts. The selected old manager unit classes accepted omitted pins (67 passes; Desktop integration excluded).
Corrected focused tests pass 4/4 and module checks pass 161/161. Full check plus Android assembly passes
2,389/zero failures/errors/one unchanged manual skip; fourteen static gates pass. Source was pushed and the
[verified outcome](https://github.com/p2pKit/P2pKit/issues/130#issuecomment-5576902316) posted; the issue remains OPEN,
not merged/released. See [the repair report](docs/audit/2026-09-04/repairs/130.md). Host fakes/Robolectric do not
establish physical Wi-Fi, ART/OEM or independent cryptographic assurance.

Earlier #332 Apple follow-up withdraws a previously admitted native service after malformed, semantically invalid or
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
| Latest clean `check`, Android assembly and strict core Dokka at **`6995130`** | **2,459 passes**, zero failures/errors, one unchanged manual skip; 297 XMLs, 256 executed tasks. Actual ABI, lint and sample assembly pass |
| #144/#360 CI/archive controls | Resolver28, workflow21, whitespace51; five actual YAML command replays and23static gates pass. Thirteen and ten respective expected-red controls detect regressions. Shared evidence/receipts are not additional product-test passes |
| Earlier clean `check`, Android assembly and strict core Dokka at **`de88284`** | **2,459 passes**, zero failures/errors, one unchanged manual skip; 297 XMLs, 256 executed tasks. Actual ABI, lint and sample assembly pass |
| #359 scoped regressions | Original production: JVM eight intended failures/two controls; Android host seven intended failures/nine controls. Focused33passes;three mutation controls and14static gates pass. No file-loss, real-LAN or independent interoperability claim |
| Earlier clean `check`, Android assembly and strict core Dokka at **`d424a23`** | **2,433 passes**, zero failures/errors, one unchanged manual skip; 296 XMLs, 256 executed tasks. Actual ABI, lint and sample assembly pass |
| #358 scoped regressions | JVM original production: two intended failures/three controls; Android original production: three intended failures/five controls. Final focused 21 passes; three mutation controls, fourteen static gates pass. Same-implementation pinned in-memory wires, not independent interoperability |
| Earlier clean `check`, Android assembly and strict core Dokka at **`a5d3145`** | **2,407 passes**, zero failures/errors, one unchanged manual skip; 295 XMLs, 257 executed tasks. Actual ABI/constants, lint, Android assembly and eight volatile-field inspections pass |
| #137 scoped regression checks | Original production plus regressions: eight structural failures/six controls; corrected focused 72 passes; five mutation controls rejected as intended. Fourteen static gates pass. Compatible visibility/contract coverage, not proof of an active stale-read race |
| Earlier clean `check` plus Android assembly at **`1847ed3`** | **2,389 passes**, zero failures/errors, one unchanged manual skip; 290 XMLs, 246 executed tasks. Actual ABI/constants, lint and Android assembly pass |
| #130 scoped regression checks | Selected old unit suites accepted omitted pins (67 passes); corrected focused 4 and module 161 passes; eight mutations rejected at the intended assertions. Fourteen static gates pass. Test coverage, not a production security correction |
| Earlier clean `check` plus Android assembly at **`78ef361`** | **2,387 passes**, zero failures/errors, one unchanged manual skip; 290 XMLs, 246 executed tasks. Actual ABI/constants, lint and Android assembly pass |
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
at `7127616`, not rerun for #144/#360; complete release/XCFramework/Swift gates remain pending. Exploratory harness/environment
failures are preserved separately, not acceptance evidence. #144/#360 share 106 finalized cleanup receipts,
including 95 serialized leaves (do not double-count them). The successful final sealer and administrative
checkpoint have separate receipts. #359's 28, #358's 26, #137's 25, #130's 30, #332 Apple's 28 and #356's 28 cleanup
receipts, #229's 34 and #357's six additional own receipts, plus #226's 37, #225's 101, #208's ten, #152's 33 and
#133's earlier 54 receipts are finalized, including failed and negative attempts; required evidence remains.
Do not add overlapping test totals. Controller/fake-manager tests and source wiring assertions are not rendered
Android UI, restoration, ART/OEM or physical-device proof. Final audit/release gates need the eventual combined tree;
whole-repository corroboration, eventual combined-tree release/consumer gates and external validation remain incomplete.

Earlier #317 corrected the diagnostic revision subscription and successful-clear invalidation through `f273b1b`.
Its [report](docs/audit/2026-09-04/repairs/317.md) preserves the real Compose regression evidence and the correction
to test-runtime wording: actual sample executor JDK21.0.7, not inferred from the JDK17 launcher. The latest passing integrated
tests at `6995130` include those regressions; host snapshots are not rendered/device performance measurements.
Earlier #354 corrected the hotspot Failed card's cleanup retry and stale permission-admission callbacks through
`b6af5b8`; its [review report](docs/audit/2026-09-04/repairs/354.md) retains exact historical evidence. The latest passing
integrated run at `6995130` also includes that correction; earlier `12e6cfa` results alone did not.
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

## Cleanup and transfer contents

The last full build removed ten generated build directories after preserving reports and stopping its owned workers.
The unused project-local `.gradle/`, `buildSrc/.gradle/` and `.kotlin/` caches were then removed after wrapper stop and
scoped no-open-file checks: **82,595,043 bytes reclaimed**, in addition to earlier module-output cleanup.
Shared dependency/toolchain caches, settings, protected files, stashes and other projects' workers were untouched.

No generated build output is a Git deliverable. The roughly 1 GiB private `.audit-evidence/` folder stays on the
source device, deliberately outside Git; cloning does not download it. It was not deleted to make the checkpoint
smaller. Use the branch clone above rather than copying the entire local directory. The clone includes the safe
reports, issue/coverage records and continuation prompt, but not private evidence, accounts or an active agent session.

## Next: resume #145 and the remaining queue

1. Stop at this requested checkpoint. #360's prerequisite and #144's complete correction are reviewed/pushed;
   do not reimplement them or treat the initial failed all-tree replay as the final result. The original failures
   remain historical evidence. Keep every prior repair and all protected-file/0.8.0+ compatibility constraints.
2. Next planned issue: [#145](https://github.com/p2pKit/P2pKit/issues/145), receive-backlog byte accounting.
   **No #145 repair or fresh reproduction has started.** Read the full body/comments/linked decisions, then trace
   current `P2pSessionImpl` admission, message ownership and `retainedSizeBytes()` callers before deciding a fix.
   Its inherited report may have line drift; verify allocation and accounting claims, text/binary/metadata and
   concurrent admission/drain/cancellation, and cross-platform behavior. Add bounded regressions; do not weaken limits.
3. Continue every actionable issue sequentially: **85 pending repair rows (84 low, one informational #333)**,
   21 external-validation rows and #120's architecture decision. Triage
   [unverified follow-ups](docs/audit/2026-09-04/followups.md) by reproduction and underlying-cause duplicate checks.
   #223 remains separate from #360. #301/#303's archive-retention decision is unchanged.
4. After an authorized merge installs the workflow on main, inspect actual manual/scheduled full CI and its exact
   source/results. No hosted run or schedule delivery was established locally; never promise a one-week deadline.

#133's repository scope is approved; independent interoperability remains **NOT STARTED**. Preserve #325's
protected-instruction caveat, #317's subscription regression, dependency/provenance tripwires, #226's short GPG-socket
ownership, #358's authentication/error distinction and #359's bounded cancellation/epoch settlement.
Whole-repository corroboration and eventual combined-tree release/consumer/Swift/XCFramework gates remain.

## Continue the full audit and repair queue

1. Read `AGENTS.md`, `CLAUDE.md`, this handoff, the complete issue ledger and
   [unverified follow-ups](docs/audit/2026-09-04/followups.md). Preserve all existing user changes.
2. Record exact branch/commit/tree/status and refresh full GitHub issues/comments/linked PRs. Reconcile new evidence
   by underlying cause, not similar titles. Use exact local drafts if access is unavailable; never claim remote writes.
3. Continue all actionable issues sequentially, prioritizing severity/dependencies. Start planned #145 with a
   complete history/current-code review; refresh the remaining queue and deduplicate other unverified follow-ups.
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

> Continue the complete P2pKit audit from AUDIT_CHECKPOINT.md and docs/audit/2026-09-04/. Use branch
> audit/complete-2026-09-04, record actual commit/tree/status, read AGENTS.md/CLAUDE.md and full GitHub histories,
> and preserve user changes. 67/174 independently reviewed repository repairs (38.5%);107 remaining rows (61.5%):
> 85 pending repairs,21 external rows,one #120 decision. External acceptance attached to approved rows is not done;
> #133 independent interoperability is NOT_STARTED. #360's seven-file archive prerequisite and #144's eight-file
> CI correction are separately APPROVED/pushed at 6995130bcdb2594257c42bed006f7d23f5bc4d6a, tree 323fc39587c626df7ac9da1edce7cc0ab80ac313.
> Both reviewers inspected the combined effects; later commits only update handoff docs, not fix blobs. Full check+Android
> assembly+strict core Dokka2459pass/0failure/error/1unchanged manual skip;297XMLs/256tasks,23static gates,
> five actual YAML command replays;shared3558sealed files/106cleanup receipts. Original failed YAML replay,
> control-verifier and evidence-sealer attempts are preserved,not passing results. No hosted scheduling or
> independent/physical/crypto assurance. Next#145 receive-backlog accounting:NOT STARTED;read history/reproduce
> current behavior before fixing. Do not repeat completed repairs or refile resolved follow-ups. Keep0.8.0+TXT
> admission restriction,exact archived bytes,protected AGENTS/CLAUDE and previous cancellation/ownership/security
> guarantees. Fix sequentially,spawn a fresh independent reviewer after each fix,resolve findings and review final
> revision. Serialize bounded builds and unconditionally stop only owned workers/clean disposable outputs after
> every check,including failure. Preserve source,stashes,evidence and shared caches;never blanket-delete build
> directories. Keep exact issue/coverage ledgers and safe outcomes current. Push only audit branch;no force-push,
> main merge,issue closure,tags or publication. Finish remaining repairs,whole-repository corroboration and final
> release/consumer/Swift/XCFramework verification. Physical devices,hostile networks,independent interoperability
> and professional crypto remain pending. Overall NOT READY. A clone transfers source/documented context,
> not account credentials,private raw logs,stashes or a running chat/agent session.
