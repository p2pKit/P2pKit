# Dormant exact-loader absence leaf — 19 September 2026

Refs [#437](https://github.com/p2pKit/P2pKit/issues/437) and shared
[#424](https://github.com/p2pKit/P2pKit/issues/424). Base:
`0c6bb56288b6a930f6ba936a070baa78f84e60f3`, tree
`57313658adaf584c2d156b0566803618f326d067`. The reviewed
[collection parent](hosted-bootstrap-collection-parent-2026-09-19.md) and accepted
producer/collection repairs are unchanged, not repeated. Main remains
`3bc76f956f8f47447b51a62474fc878b9c43173c`.

**Source/offline work only. Apps are not in Releases; audit/release NOT_READY.**
Both ordinary activation HOLDs remain. There is no caller of this new leaf,
bootstrap workflow or production `cache.export_snapshot` / `cache.save_set` caller.

## Why a separate observation

Configuration reservation does not install the ordinary Test transcript loader.
Ordinary `test-transcript-custody.py uninstall` first verifies its own installed
original, records removal intent, deletes it and verifies absence. Reusing that
operation for a never-installed loader would manufacture uninstall evidence.

The new read-only leaf rederives its exact configuration request from supplied
admission/canonical bytes. It derives only canonical H and the fixed
`init.d/p2pkit-test-transcript-custody.gradle` target, not an arbitrary caller path.
NEW source-directory handles bind original H identity, same-volume descendants,
exact paths/kinds and nonaliased identities. Two complete bounded H listings and,
if present, two `init.d` listings must retain bindings and membership. The exact
target or a selected case/trailing-dot/space alias refuses. Unrelated names are
counted, not opened. There are no file-content reads, writes or deletions.

This is current listing observation, **not atomic or historical absence**, proof
of nonexecution, inspection of other initializer contents or original-call
authority. Supplied consistent records cannot authenticate a producer. Success
denies producer/collection return, enclosing retirement, dependency population,
tests, admitted budget and next-phase/export/save authority. The parent remains
open; the leaf closes only its NEW handles and retains original failures/pins.

Both local ceilings narrow from inherited120 to90. Known expiry does not excuse
once-only known cleanup; UNKNOWN quarantines rather than inventing retirement.
Root acquisition has no native deadline argument in the reused supplier, so
surrounding checks are not a filesystem watchdog. A distinct original-call
parent must eventually supply original RAW/job fences after its actual producer
and collection returns. Proposed uninstall90/final45/read30 integration remains
unfinished/unadmitted/unmeasured; this leaf cannot authorize those phases.

## Independent finding and actual author controls

Passive R1 verdict: **REQUEST_CHANGES_EXACT_NO_LOADER_R1_SOURCE_NOT_APPROVED**.
Report SHA-256:
`90f2aec6eeaaef1f33a5604c2cdeb947064f059ea912fed050b9d21d13aeba80`.
The reviewer found that child open captured85 before the acquisition adapter
observed70, then still forwarded85 to the directory supplier. Later rejection
cannot undo a stale I/O allowance. This was a source finding, not a native incident.

The unchanged R1 source's initial4-method aggregate actually **FAILED:
3 PASS / 1 intended FAIL / 0 ERROR / 0 SKIP**. The regression observed the actual
modeled `open_directory` argument85 where70 was required. R2 checks inside the
factory immediately before open. The accepted collection helper, test bytes,
assertions and observer are unchanged between R1 and R2.

R2 actually passed **49 distinct author methods** in three disjoint invocations:

| Selectors | Passed methods |
| --- | ---: |
| `InitialModels` | 4 |
| `InputModels ListingModels` | 30 |
| `LifetimeModels ScopeModels` | 15 |

There were no failures, errors, skips or denied boundary events in those R2
invocations. Subtest input values are not extra methods. R1 remains a separate
failed aggregate; its4 observations are not4 additional distinct controls.
New tests: `scripts/tests/hosted-cache-bootstrap-no-loader-test.py`.

Coverage includes both absence branches, unselected dotfiles, present/aliased
targets, wrong paths/kinds/identities/volume, changed stamps/membership, malformed
and exact/overflow listings, invalid/mutating originals, ordinary substitution,
actual forwarded deadline shrink, nonrenewal/equality/backward/nonfinite clocks,
cancellation, final-encoding expiry, post-factory errors, erased registration,
falsey first errors, secondary close uncertainty and nonaccepting result scope.
No old test fixture or test suite was imported or rerun.

The retained exact command form was:

```text
/usr/bin/timeout --kill-after=2s 20s /usr/bin/python3.12 -I -B -S
  <frozen-observer> <frozen-source> <selected-classes>
```

CPU10s, address space512MiB, regular-file RLIMIT_FSIZE8MiB, descriptors64, core0. A clean
environment contained no GitHub identity. Required stdlib modules, including
ctypes for portable class definitions, preloaded before the guard. Complete
frozen bodies of10 repository modules loaded in dependency order, including the
transitive `hosted_primary_abi`. Only the pure request/encoding and leaf/ownership
operations executed; loading modules is not executing every function in them.

Parent, clocks and directories are explicit **memory models**. No real file,
native handle, original producer, hosted admission or UID/role override exists.
The guard denied subprocess/network/native ctypes calls, writes, directory
operations, signals and environment changes; UID/GID mutators had forbidden-call
stubs. Reads were limited to exact frozen sources and stdlib. This guard is not
a kernel sandbox. All17 bound source/manifest/observer/recorder/tool byte and
native-stat pairs remained unchanged in each run. Wall times were0.255–0.285s
for the three R2 invocations, not measured productive-phase timing.
The supervisor captured stdout/stderr through pipes: RLIMIT_FSIZE does **not**
impose an8MiB pipe-output limit. Actual small originals were inspected; no hard
8MiB stdout containment is claimed. The original recorder/plan is retained,
not retroactively rewritten or rerun to supply a different envelope.

Before any candidate compilation, a first **source-freeze recorder failed** by
comparing read-access time as part of full stat values. Its11 completed copies
and missing test copy remain. The next input's observed atime advanced while
mtime/ctime remained unchanged; no before-stat survives for that failed input.
The recorder now compares device/inode/mode/size/mtime/ctime, excluding atime.
No production/test assertion was changed to fix this recorder. The failed tool
output remains in tool history, not an invented original stderr file; it is not
a failed test or a passing freeze. A separate expanded freeze then succeeded.

| Exact binding | SHA-256 |
| --- | --- |
| R1 no-loader source | `cf5810c7e01e369c4a4c2fcbb8a93f719bdf07a975e6a449593a5ce2c312863c` |
| R2 no-loader source | `f5676322e00bb6a36d34d539476bb3e0ad5519db3b4a5dff32b320a95d78c133` |
| Unchanged author test | `25e181f0f2ec5c2c98b832975f0c675513f487efc116fff801bcf376a0ad0ff4` |
| R2 expanded freeze | `803f2104e7d18f7003f61818aafea26846c671b96dc2131bddb8832184ba990c` |
| Read-back author result summary | `9579ffdecbd4b4f4f0fefb2c1d10864fbdb1709bfd5b364022a8871576036d80` |

Private originals: packet `20260919-no-loader-u5hwc7rn`. Its per-invocation plan,
stdout/stderr and results retain exact commands/selectors/hashes. Missing old Mac
originals were neither reconstructed nor used to justify expensive reruns.

## Review status and remaining acceptance

Independent R2 verdict:
**APPROVE_EXACT_NO_LOADER_R2_SOURCE_CONTROLS_AND_ORIGINAL_RESULT_SCOPE_ONLY_NOT_RUNTIME_QUALIFICATION**.
Report SHA-256:
`bc7e9a77bc446ea1a2e3c2bf91ceb8a4c274b95e17c5c603c5daaed7d037c272`.
The nonimplementing reviewer inspected the complete source/test/observer and all
four original invocations without replay, confirmed F1 repaired and independently
counted49 unique R2 methods. No further blocking implementation finding was
identified in that scope. The optional seven independent controls were **not
authored or executed** and earn no test count. A review-service rate-limit error
interrupted reporting, not a candidate execution; review resumed without replay.

That implementation verdict does not approve these later docs or the complete
Git tree. The containing commit's issue mapping separately binds the final
complete-patch review, applicable source gates, commit/tree, remote readback and
preservation. Source review cannot supply formal GitHub approval or runtime
acceptance, and no independent probe execution is inferred from author counts.

Complete paginated metadata refreshed23:57:20 UTC:78 open issues, the same seven
dependency PRs, no campaign PR, zero queried active Actions and two RC Releases
with zero assets.19/29 saved endpoint values match the previous23:40 snapshot;
the remaining deltas are the two already-read-back collection comments and their
comment counts/update timestamps, including embedded cross-reference copies.
Both new bodies/IDs match the original retained POST/GET records. No new owner
policy or approval appeared. Required checks remain `complete-gate`, `review`,
`scan / osv-scan`, `osv-scanner`; configured approval count0 does not waive the
formal different-account review requirement. Saved-value comparison details
SHA-256: `5ce01a9727cb357db319bff8637fdc5653fe1cab1fbba02c1ba252ecd0a0ce30`.

The original-call no-loader parent, positive export/freeze/save/probe and
encrypted custody/seal/delivery remain unfinished. Approved named routine
custodian, exact public key, finite14-day policy, legitimate trusted-original-base
bootstrap and formal different-account approval remain missing; candidate source
cannot authorize its own recipient. Genuine native/provider/resolver/custody/
scheduling/delivery qualification and current required GitHub checks are separate.

Both HOLDs, exact selectors/credentials/deadlines, proposed5400
UNADMITTED/UNMEASURED and NativeFile900/Snapshot576MiB remain unchanged. No local
Java/Gradle/Xcode/app build, SDK/dependency download, guest, held dispatch, preview
download, phone task, PR/merge/Release or issue closure occurred. Accepted preview
35070982169 and #424 writer35066719641/1/six exports were not repeated; #372's20
Kotlin tests remain uncompiled/unexecuted. Production/Maven/Store publication is
not authorized. OSV remains EXCEPTED_NOT_FIXED, affected Kotlin2.4.10, expiry
2026-10-31, without a new scan/remediation/exception extension. Historical
206/234 repair-approved and207/234 resolved accounting remains unchanged.
