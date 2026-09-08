# P2pKit audit continuation checkpoint

**Updated: 8 September 2026. Continuation resumed; not a release approval.**
The completed transfer stop is superseded by the owner's authorization to continue. #145, #144/#360 and
earlier repairs remain approved. #367's five-file repository-source correction is independently approved and
pushed at `0d88be3`; its Windows/Intel acceptance remains NOT_EXECUTED.
**69/182 repository-repair rows reviewed (37.9%); 113 rows remain (62.1%).**
**Next repair: #368 API24 export-failure fixture**, then #223 and the serialized hosted facility/remaining queue.
The #367 affected Linux gates pass, but both full-check commands at `0d88be3` FAIL on the separately filed #368.
This records the approved #367 cycle; newer #368 source/executions are separate and must not be overwritten.
#133 independent interoperability remains NOT_STARTED. Overall **NOT_READY**. Read this with unchanged
`AGENTS.md`/`CLAUDE.md` and the complete tracked issue/coverage ledgers. GitHub Actions is authorized for
supported Mac/Windows/Apple gates, not a substitute for physical-device or independent acceptance.

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

- Repository: <https://github.com/p2pKit/P2pKit>; branch `audit/complete-2026-09-04`, not merged into `main`.
- Completed transfer baseline: `d823bb9cc0d187ec746714af67b08904a28331b6`, tree
  `44cd608fb05d16d3593d496b355e690af928a247`. Preserve every later commit and working change; never reset to it.
- Latest independently reviewed source: **`0d88be3e3769b5133a985e4fe2fca782ba0ef2a6`** (#367), tree
  **`db432eb14791d9637e812333305e811edceb834e`**. Its parent `9316607618bf9710dffc36a3ba95185b24712152`
  is separate #145 administration; the five-file source diff also matches the earlier `0423e96` review packet.
  Later #368 drafts/commits or administrative edits are not implicitly approved or tested at this tree.
- #367 clean affected command **PASS**: 851 core tests/100 XMLs/110 tasks, Android ABI/constants, Android sample
  assembly and strict core Dokka. Both fresh combined and separate full-check commands **FAIL**: each 1,297
  passes plus one #368 fixture failure, 151 XMLs/172 tasks; no errors/skips. These are not full-check passes.
- #145 approval remains at `0423e96e15c894c26a7d45a5dfb2a012e0c1ba8e`, tree
  `26984a1b7d2048bdbda8e1808bb38f299e7a6866`. Its 805 focused passes, 851 partial affected passes and both
  strict-metadata command failures remain historical; the new prerequisite correction does not rewrite them.
- Last recorded **historical successful** full `check`, Android assembly and strict core Dokka within this #367 checkpoint:
  **`6995130bcdb2594257c42bed006f7d23f5bc4d6a`**, tree `323fc39587c626df7ac9da1edce7cc0ab80ac313`:
  **2,459 passes**, zero failures/errors, one unchanged manual LAN interop skip; 297 XMLs/256 tasks.
  This is not `0d88be3` integration evidence. Newer #368 executions/results belong to its separate cycle;
  this record does not imply no newer run exists. Earlier `bf34f70` watcher failure was corrected by #357.
- #229's fourteen source blobs were unchanged from `bf34f70` at `6d9cd3c`, not current HEAD; #356 and #145
  subsequently changed affected source/docs. #133 publication/isolated-consumer evidence remains at `7127616`.
- #367 source was pushed/ref-verified at 10:59:45 UTC; main was observed unchanged at
  `eb444cccfc290be5435c5c10629c24183293606f`. Safe outcome was posted/refetched at 11:01:17 UTC; issue OPEN.
  #145's earlier 09:37:43 source and 09:42:42 outcome publication receipts remain separately preserved.
- The old #337 draft `eb564e9487f2887f83f519575c82d4e7657864cb` was preservation, not a repair. Its final
  review covered the full range from `32dc5c0` through `5f454a9`/`170cc86`; do not resume old draft instructions.
- Record actual `HEAD`, tree and worktree before checks. Administrative publication can follow reviewed source
  without rebinding its verification. [Checkpoint metadata](docs/audit/2026-09-04/checkpoint.json) preserves scope.

| Disposition at this checkpoint | Count | Percentage of 182 inventoried issues |
| --- | ---: | ---: |
| Repository repairs with independent approval | **69** | **37.9%** |
| Pending repairs | 91 | 50.0% |
| External/platform validation | 21 | 11.5% |
| Architecture/product decision (#120) | 1 | 0.5% |
| **Total remaining issue rows** | **113** | **62.1%** |

These percentages count repository-repair rows, not effort, file coverage, issue closure or production readiness.
Rounded category percentages may not sum exactly to the separately rounded total.
Since the transfer checkpoint, #145 and #367 add two approved rows; #361–#368 add eight distinct findings.
Pending repairs are **90 Low and one informational (#333)**. The inventory includes **49 new-audit findings**.
External acceptance on approved rows remains incomplete: #133 NOT_STARTED and #367 Windows/Intel NOT_EXECUTED.

The exhaustive sealed **10:24:33–10:30:05 UTC** refresh captured 288 issues (181 open/107 closed) and 79 PRs
(7 open/72 closed): all 367 issue-style bodies/comments/timelines and all 79 PR metadata/review/file/commit sets
freshly fetched, no reused current histories. **1,519 GETs** (1,518 main plus one preflight), zero failures.
All-state lists stayed stable. Thirteen newly observed timeline identities include three older backlinks missing
from prior reused histories; they are not thirteen new defects. Earlier 09:17–09:28 refresh/initial #367-addition
records, raw captures and the initial reference-parser analysis remain historical and unchanged.
**#368 was individually filed/refetched at 10:50:42 UTC**: known totals become 289 issues / 182 open / 79 PRs,
not a complete post-addition refresh. #367's 11:01 outcome is also an individual observation. Per-endpoint
captures are not transactional or permanently current; refresh before relying on live state.

All 69 approved repository-repair rows are in branch history; none was closed, merged or released by these pushes.
#325's protected-file exception remains. #240's spurious dependency `0` is only an inventory extraction correction:
its body says `transport #0`, not GitHub issue 0. No new product defect, #240 repair or count change follows.
See [all dispositions](docs/audit/2026-09-04/issues.md) and
[scope/dependencies/commits/outcomes](docs/audit/2026-09-04/issues.json). Earlier assessments retain historical scope.

## Completed work and verification

Recorded cycles include dependency/provenance/publication gates, coroutine cancellation/ownership, LAN rebind/cleanup,
secure-v2 tests, provisioning callbacks, sample pairing/privacy, file source/destination safeguards, diagnostics,
Android API24/25 diagnostics and iOS integration. These are scoped repairs, not proof of complete subsystem correctness.

## Latest #367 repository-source correction

The complete five-file host-classifier correction is independently **APPROVED** and pushed at
`0d88be3e3769b5133a985e4fe2fca782ba0ef2a6`, tree `db432eb14791d9637e812333305e811edceb834e`.
Fresh `/root/review_367_r1` found no actionable source/provenance findings. Source/ref verification was
10:59:45 UTC; the [safe outcome](https://github.com/p2pKit/P2pKit/issues/367#issuecomment-5584111070)
was refetched at 11:01:17 UTC. The issue remains OPEN. See [the scoped report](docs/audit/2026-09-04/repairs/367.md).

Exactly five current Native/AAPT2 classifier records were added after byte/signature curation anchored to
official publisher fingerprints. Three Native hashes also match official archive digests; both AAPT2 hashes
match authoritative SHA-256 sidecars. All old records, versions, locks, wrapper, trust and required tasks remain.
The maintained pre-build policy independently requires four Native and three AAPT2 hosts, with ten regression
methods and an exact-original-metadata outer-gate negative control. This is a completeness/format tripwire,
not authentication of arbitrary well-formed hashes or foreign-host execution.

- Strict, clean Linux affected command **PASS**: **851/851** core tests (789 JVM, 62 Android-host),
  100 XMLs, 110 executed tasks; Native Linux download, AAPT2 processing, Android sample assembly,
  strict core Dokka and Android ABI/compiled-constant guards pass.
- Both clean combined `check`/sample/Dokka and separate `./gradlew check --console=plain` commands **FAIL**:
  each **1,297 passes plus one failure**, 1,298 cases/151 XMLs/172 tasks, no errors/skips.
  The distinct downstream test-fixture mismatch is [#368](https://github.com/p2pKit/P2pKit/issues/368),
  not an exporter exception or #367 regression. Message-only instrumentation proved export succeeded at the
  normalized uppercase path and was then restored exactly. No #368 repair is approved by this checkpoint.
- All provenance/completeness/control/toolchain checks and twelve static/range gates pass. The private seal
  retains **2,160 files / 21,605,300 bytes**, 20 own serialized leaves plus a separate successful sealer.
  Shared #145 failures and the #368 diagnostic are not additional own leaves or passing tests. All stops
  exited zero; no owned survivors remained; dependent disposable outputs and owned GPG/artifact workspaces
  were removed after evidence preservation. Protected source, shared caches and unrelated tasks remain.

The original #145 failures below remain historical failures. Last successful full integration recorded in this
#367 checkpoint is historical `6995130`, not `0d88be3`; newer #368 executions are outside this cycle's record.
Windows/Intel/Apple acceptance is **NOT_EXECUTED** in this cycle;
source approval does not discharge those #367 acceptance gates. Next is #368, then #223 and the serialized
hosted facility/remaining sequential queue. #133 independent interoperability remains **NOT_STARTED**;
physical-device/ART, hostile-network, independent-implementation and professional-crypto acceptance remain
separate. Whole audit **NOT_READY**. No merge, closure, release, tag or settings change is authorized.

### Historical #145 approval and verification

Earlier #145's complete nine-file receive-backlog correction is independently **APPROVED** and pushed at
`0423e96e15c894c26a7d45a5dfb2a012e0c1ba8e`, tree `26984a1b7d2048bdbda8e1808bb38f299e7a6866`.
Fresh `/root/review_145_r1` inspected the complete diff, actual admission/ownership/cancellation/rearm callers and
sealed raw evidence; no actionable findings. See [the #145 report](docs/audit/2026-09-04/repairs/145.md) and
[verified outcome](https://github.com/p2pKit/P2pKit/issues/145#issuecomment-5582924265). Source/ref verification was at 09:37 UTC; the outcome was refetched at 09:42 UTC.
The issue remains OPEN, not merged or released.

Both the 64-message and 8 MiB caps already bounded growth. The confirmed Low issue is post-session-admission
allocation/retention amplification. The default v2 route requires authenticated/authorized admission; this is not
a pre-admission LAN finding. Explicit plaintext mode also reaches this accounting. Binary under-reporting remains
refuted. Admission now checks count before measurement and stores a charge of 512 bytes/message plus twice each
Text UTF-16 code-unit length (or actual private Binary payload length), and 256 bytes plus twice the key/value
UTF-16 length per metadata pair. Arithmetic widens before addition/multiplication; delivery, rollback and drain
release the same stored charge. Defensive ownership copies, public API/ABI, wire/security policy and dependencies remain.
This is a bounded policy estimate, **not** a universal heap upper bound, constant-time metadata walk or literal
zero-allocation guarantee; no Native heap/allocation profiling was performed.

Tighter admission is reserved for **0.8.0+**: without metadata/backlog, 4,194,048 ASCII UTF-16 code units reach 8 MiB;
one more is refused. A wire-legal 4 MiB ASCII Text costs 8 MiB plus 512 bytes and fails the receiving session even
with otherwise empty backlog. Do not change published 0.7 artifacts or weaken the documented limit.

Original production with the corrected final regressions produces **33 intended AssertionErrors** (17 JVM,
16 Android-host). Three restored mutations detect the Text multiplier, metadata allowance and inclusive boundary.
Final focused checks pass **805/805** (89 XMLs, 19 tasks). Affected Linux gates pass **851/851 core tests**
(789 JVM, 62 Android-host; 100 XMLs, 97 tasks), actual Android ABI and JVM/Android public-constant guards, but
**the aggregate command FAILS** on missing strict Native/AAPT2 classifier metadata. The combined `check`/Android
assembly/strict Dokka attempt **FAILS before tests** (six tasks); sample assembly and Dokka are not complete.
These two commands are not current whole-check or release passes. Twelve static/policy gates pass.

The original harness/deprecation failure, later assertion-oracle/Android Log fixture failures and both integrated
failures remain historical failures; oracles/fixture were corrected, not skipped or weakened. A JDK estimator-only
allocation probe establishes removal of payload-length scaling, not retained-heap, enqueue or Native behavior.
The independent reviewer rechecked **1,754 sealed files / 17,292,499 bytes**, 25 finalized serialized invocation
receipts plus a separate sealer receipt. All task-isolated wrapper stops exited zero; no owned survivors remained,
and dependent disposable outputs were removed while preserving source, shared caches and required evidence.
Android-host is not ART/emulator/device evidence. No Mac/Windows/Apple, physical-network, independent-interop,
professional-crypto or final consumer/release pass is implied by this issue-scoped approval.

The original #145 failures above established the distinct Medium, non-security, fail-closed #367
host-classifier prerequisite; they remain historical failures. The later five-file correction and
independent source approval at `0d88be3` are recorded above. Windows/Intel execution remains pending;
the current downstream full-check failure is separately tracked as [#368](https://github.com/p2pKit/P2pKit/issues/368).

Earlier #360 repairs the pre-existing all-tree whitespace blocker without modifying historical evidence.
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

Historical #144/#360 combined verification: **2,459 passes, zero failures/errors, one unchanged manual skip;
297 XMLs, 256 tasks**. This remains bound to `6995130`, not the current #367 source.
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
| #145 combined Linux `check`, Android assembly and strict core Dokka at **`0423e96`** | **FAIL before tests**, six executed tasks; missing strict Native Linux checksum. Not a full-check/sample/Dokka pass |
| #145 affected Linux gates at **`0423e96`** | **851 core passes**, zero failures/errors/skips, 100 XMLs, 97 tasks; actual Android ABI/JVM+Android constant guards pass, but **aggregate FAIL** on Native/AAPT2 metadata (#367); sample/Dokka incomplete |
| #145 focused regressions and controls | **805/805 passes**; original production plus corrected tests yields 33 intended assertions; three restored mutations and twelve static gates pass. Do not add overlapping test totals |
| Historical last successful `check`, Android assembly and strict core Dokka at **`6995130`** | **2,459 passes**, zero failures/errors, one unchanged manual skip; 297 XMLs, 256 executed tasks. Actual ABI, lint and sample assembly pass |
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
to test-runtime wording: actual sample executor JDK21.0.7, not inferred from the JDK17 launcher. The historical passing integrated
tests at `6995130` include those regressions; host snapshots are not rendered/device performance measurements.
Earlier #354 corrected the hotspot Failed card's cleanup retry and stale permission-admission callbacks through
`b6af5b8`; its [review report](docs/audit/2026-09-04/repairs/354.md) retains exact historical evidence. The historical passing
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

Historical transfer-device cleanup: the then-last full build removed ten generated build directories after
preserving reports and stopping its owned workers. This is not a new Linux cleanup receipt.
The unused project-local `.gradle/`, `buildSrc/.gradle/` and `.kotlin/` caches were then removed after wrapper stop and
scoped no-open-file checks: **82,595,043 bytes reclaimed**, in addition to earlier module-output cleanup.
Shared dependency/toolchain caches, settings, protected files, stashes and other projects' workers were untouched.

No generated build output is a Git deliverable. The roughly 1 GiB private `.audit-evidence/` folder stays on the
source device, deliberately outside Git; cloning does not download it. It was not deleted to make the checkpoint
smaller. Use the branch clone above rather than copying the entire local directory. The clone includes the safe
reports, issue/coverage records and continuation prompt, but not private evidence, accounts or an active agent session.

The resumed #145 cycle separately sealed 1,754 files / 17,292,499 bytes and 25 finalized serialized invocation
receipts plus a sealer receipt. Final sealer cleanup ended at **09:18:44 UTC**. Every applicable task-isolated
wrapper stop exited zero, no invocation-owned survivors remained, and dependent disposable outputs were removed.
Required private evidence, source/protected files, shared caches and unrelated tasks were preserved.

The separate #367 seal covers 2,160 files / 21,605,300 bytes and 20 own serialized leaves plus the
separate sealer (final cleanup 10:58:38 UTC). Shared original #145 failures and the #368 diagnostic
are not additional own leaves or passing tests. Stops exited zero; no owned survivors remained.
GPG/artifact workspaces and dependent disposable outputs were retired after evidence preservation.
These receipts do not certify later #368 repair invocations or unrelated workers.

## Next: #368, #223 and the remaining queue

1. The transfer stop is completed and superseded. #145, #367, #360, #144 and earlier scoped source corrections
   are approved/pushed; do not reimplement them or relabel earlier failures. Preserve protected files, immutable
   archives/releases and all **0.8.0+** admission-tightening restrictions (#229/#356/#332/#145).
2. Next [#368](https://github.com/p2pKit/P2pKit/issues/368): derive the API24 export-failure obstacle from the
   same captured normalized summary used by the real exporter. Preserve every failure/preservation/staging/event
   assertion and classloader isolation. Add an exact-string target invariant and raw-ID mutation so a
   case-insensitive host cannot hide the mismatch. No production normalization change, relaxed exception check,
   host skip or timeout increase. Rerun focused/diagnostics and failed full gates, then a fresh independent reviewer.
   This #367 checkpoint contains no approved #368 revision; preserve later work instead of resetting to it.
3. Then [#223](https://github.com/p2pKit/P2pKit/issues/223), the separate wrapper LF issue, before the serialized
   Mac/Windows/Apple facility and remaining dependency-aware repairs. #301/#303 archive retention stays intact.
4. Continue **91 pending repairs (90 Low, one informational #333)**, 21 external rows and #120's architecture
   decision. #361–#366/#368 are filed findings, not completed repairs; do not refile them. Reproduce and
   duplicate-check [unverified follow-ups](docs/audit/2026-09-04/followups.md) separately.
5. #367's Windows/Intel acceptance is **NOT_EXECUTED**, not waived by source approval. GitHub Actions is
   authorized for supported host/simulator gates; bind exact source/run/artifacts and serialize local/hosted builds
   with unconditional owned cleanup. #144 default-branch scheduling still needs an authorized merge; no merge
   is authorized here and scheduling deadlines must not be promised.

#133 repository scope remains approved; independent interoperability remains **NOT_STARTED**. Preserve #325's
protected-instruction caveat, #317's subscription regression, provenance tripwires, #226's GPG socket ownership,
#358's error/authentication distinction and #359's bounded cancellation/epoch settlement. Final whole-repository
corroboration and combined-source consumer/release/Swift/XCFramework gates remain required.

## Continue the full audit and repair queue

1. Read `AGENTS.md`, `CLAUDE.md`, this handoff, the complete issue ledger and
   [unverified follow-ups](docs/audit/2026-09-04/followups.md). Preserve all existing user changes.
2. Record exact branch/commit/tree/status and refresh full GitHub issues/comments/linked PRs. Reconcile new evidence
   by underlying cause, not similar titles. Use exact local drafts if access is unavailable; never claim remote writes.
3. Continue all actionable issues sequentially, prioritizing severity/dependencies: #368, then #223 and the
   serialized hosted facility/remaining queue. Refresh complete histories/current callers and deduplicate new concerns.
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
  JDK21. #145 Linux evidence used JDK17.0.20 and configured daemon JDK21.0.12. Libraries compile against Android
  Platform36; the sample needs **Platform37** (`platforms;android-37.0`). #367 curates the missing host
  artifacts; foreign-host execution is still pending. Never skip strict verification or call an unrun gate passed.
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
- Linux can perform supported JVM/Android host/static checks, not Xcode/iOS simulator/XCFramework checks. The owner
  authorizes GitHub Actions for supported Mac/Windows/Apple gates; use exact source/run IDs and retained artifacts,
  with nonoverlapping bounded builds and unconditional task-owned cleanup. A supported Mac is also suitable.
  Hosted macOS/Windows/simulator results are not physical-device or independent validation; unsupported gates are not passes.
- Physical Android/Apple devices and OEM/API24-25 ART behavior, hostile networks, headful UI/accessibility,
  other-host filesystems, independent secure-v2 interoperability and professional cryptographic review remain external.

An existing moderate Dependabot alert remains open: [alert 14](https://github.com/p2pKit/P2pKit/security/dependabot/14),
`GHSA-r937-wjx7-w2jp`. The existing OSV exception expires 31 October 2026; cache isolation/KAPT non-use are mitigations,
not a patched-dependency or dismissed-alert claim. Reassess it in the dependency/release gates.

Overall status: **NOT PRODUCTION READY**. Report exact commits/state, issue dispositions, fix/review evidence,
verification scope, blockers, cleanup and practical readiness limits at each handoff.

## Prompt for the next agent

> Continue the complete P2pKit audit from AUDIT_CHECKPOINT.md and docs/audit/2026-09-04/. Use only branch
> audit/complete-2026-09-04; record actual HEAD/tree/status and preserve later commits/user changes. Read unchanged
> AGENTS.md/CLAUDE.md, complete ledgers, relevant reports/testing/release docs and full GitHub issue/comment/PR/
> decision histories. The transfer stop is completed and superseded. 69/182 approved repository-repair rows
> (37.9%),113 remaining(62.1%):91repairs(90Low,1informational333),21external,#120decision. Not effort or readiness.
> #367 five-file source correction APPROVED/pushed at0d88be3e3769b5133a985e4fe2fca782ba0ef2a6,
> tree db432eb14791d9637e812333305e811edceb834e; fresh reviewer /root/review_367_r1 had no actionable source/provenance
> findings. Source-only: its Windows/Intel/Apple acceptance remains NOT_EXECUTED. Strict Linux affected command
> PASS851/100XML/110tasks including Androidsample/Dokka; combined and separate rootcheck eachFAIL1297passes+1
> #368fixture failure/151XML/172tasks. No fullcheckPASS at0d88be3 or release/foreignhostpass in the367cycle.
> Newer368source/executions are separate, not erased by this checkpoint. Historical fullPASS6995130,
> 2459passes/one manualskip, is not a367run. Original145harness/oracle/fixture/integration failures remain failures.
> #145 approved0423e96 uses a bounded retention-policy estimate, not universal heap/Native/zero-allocation proof.
> Preserve0.8.0+ admission restrictions, security/ownership and immutable archive/release bytes. Do not repeat
> #145/#367/#144/#360. Next368raw-ID export-fixture repair: summary-derived target, exact-string invariant,
> original-ID mutation, unchanged assertions/production normalization, diagnostics/fullgate reruns and fresh review.
> Then223wrapperLF, serialized hosted facility and remaining sequential repairs. Preserve any later draft/commits.
> GitHub exhaustive10:24–10:30capture:288issues/181open/79PRs,all367histories and79PRdetails fresh,1519GETs.
> #368individual10:50:42addition gives known289issues/182open;367outcome11:01 is also individual, not a complete
> post-write refresh. Earlier captures/seals remain historical. Refresh before relying on live state.
> One active repair at a time. Delegate bounded independent investigations/reviews; create a fresh reviewer after
> every fix, give full issue/exactdiff/callers/platform/evidence and resolve every actionable finding before proceeding.
> Never overlap builds across local/hosted agents. Use bounded memory,twoGradleworkers,no parallel execution,
> strictverification; preserve logs after every build/test/failure/cancellation, run task-isolated wrapper--stop,
> retire only owned survivors and remove only confirmed disposable outputs after dependent checks. Never blanket
> delete build directories:buildSrc/src/main/java/dev/p2pkit/build is source. Preserve shared caches/private evidence.
> Owner authorizes GitHub Actions for supported Mac/Windows/Apple gates, not main merge/settings/tags/releases/closure.
> Track confirmed distinct defects after underlying-cause duplicate checks; keep suspicions separate. Update safe
> issue/coverage/verification/limitations/cleanup records and push focused source/checkpoints only to audit branch.
> Finish current whole-repository corroboration,./gradlew check --console=plain, applicable samples/consumers and
> inspected release/Apple gates. Physical devices,ART/OEM,hostile networks,independent implementations and professional
> crypto remain separate obligations. #133NOT_STARTED; whole auditNOT_READY. Cloning transfers source/context,
> not credentials/private logs/stashes/active sessions. Continue feasible work beyond administrative checkpoints.
