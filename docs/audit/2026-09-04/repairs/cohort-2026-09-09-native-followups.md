# Native and local continuation — 9–10 September 2026

> Current outcome: [Intel R16 readiness and current technical observations](#intel-r16-readiness-and-current-technical-observations) below; prior failures and dated source bindings remain unchanged.

## Preserved pre-R10 state

162/207 independently approved repository repairs (78.3%); 163/207 independently resolved rows (78.7%) including one reviewed no-repair disposition; 44 unresolved (21.3%): 20 repair/native rows, 21 external-validation rows and 3 owner decisions (#120/#274/#284). 74 new audit findings. **Whole audit NOT_READY; #133 independent NOT_STARTED.**
#287 is independently resolved without a fix; it does not inflate repair credit.
#389 now has final independent Linux-executed repair approval; its original filing/failure remains historical. Current queue is in [issues.md](../issues.md).

PRE-R10 local source `41909f43b65a96af5bc689aa29aa33d319c308a6`, tree
`8e3dfd566f570fbaa0809184d41d1a809f89f9d0`, contains final-source-approved #393
fix07bc plus the mechanical workflow comment9-to10. **Not pushed; R10 NOT_RUN**. Last verified publication
`165e4e9263cd6ddfe73a51ed401259d149b63731`, tree
`2ebd1faba818c0bdcb3b6ed79e7cc523f89e2f69`, binds actual R9. Only #392 receives
new final native approval; #390/#391/#393 remain pending. Earlier rootcheck/CLI
0dbc+exactpatch, Windows655 and OSV598 keep their original scopes, not a new07bc pass.

| Source commit | Scoped disposition |
| --- | --- |
| `d9ad18bbeff62a77c91e50c1d11f391dc728254a` | #207 construction-only Windows persistence diagnostics; Windowsr6 follow-up independently accepted, whole207Apple pending. |
| `b027b8f2b2a830bc7ae1ecc58723886e6ffd8235` | #207 responder-admission readiness in2core test files; source-approved, rootr3 all15methods pass; native pending. |
| `86d4ca832242d9d8e5a420b81c5f3b92ad58d4e0` | #383 exact-run Swift lifecycle fencing; source-approved/native pending. |
| `c9bd57ef4700a8cb4ce10dbaf7987264c38a300e` | #341/#363 actual rendered presentation/consent regressions; source-approved/native pending. |
| `eea101d47aab6aef1c549e4f94dc6cda333f43a0` | #388 fail-closed OSV boundary; final local+hosted execution approved, unchanged expiring advisory exception retained. |
| `0dbcbeab4c030be526991e0d4e81bea4d0a33b60` | Narrow Windows diagnostic host route; source/local controls and focusedWindowsr6 accepted, not fullWindows. |
| `655203775f6cb4f35fa9e7386ba4faead8c5ae5e` | #389 single-owner CLI shutdown; final independent Linux-executed repair approval. |
| `598512081d8abfeb58b2b8e0d639a2fb7a0721e5` | Reviewed Apple gate composition;13host+1workflow fixtures pass, actualr7 fails before product. #388 hosted acceptance later uses this unchanged repair source. |
| `3c038f6ed8f4d877a4cd78a14e5f83946b851567` | #390 bounded Darwin lifecycle reconciliation; exact source approved, final native acceptance withheld. |
| `4a20f74224140e414ccdaec30d706f3efe5effed` | Approved comment-only r8 trigger; authentic native control failure, all products NOT_RUN. |
| `49f05c62cbf9e46bbd31a100e835e16b6c2d384a` | #391 supported Darwin fixture identity observation; source approved, three R9 methods pass, final native approval withheld. |
| `5a36362a4daa053b125ca3714c8ab808b034472e` | #392 faithful wrong-home child domain; final native repair approved. |
| `165e4e9263cd6ddfe73a51ed401259d149b63731` | Mechanical revision9 trigger; authentic79/80 native suite failure, no products. |
| `07bc74eaa4afdcb2a91ce248d033803a95d5cf3f` | #393 target readiness and original-child guard; final source approved after F1, local/native pending. |
| `41909f43b65a96af5bc689aa29aa33d319c308a6` | Mechanical R10 request comment only; prepush, no native execution yet. |

Latest verified push receipt SHA256 `bfc1f0d249a1cf5744c4051694eaeda52cd18c30680549b6f24027d04c72cb23`;
prior publications remain separately bound. Planned admin/R10 publication is not inferred.
No main merge/settings/tag/release/issue closure is implied.

## Native Windows: approved repair scopes inside an authentic failed run

[34372057622](https://github.com/p2pKit/P2pKit/actions/runs/34372057622), attempt1,
job102535470887, native windows-2025x64, atf73: **FAILURE**,92/95fresh Kotlin
cases pass/14XML,38executed tasks; product/owned-stop/final1/0/1.
Independent Windows reviewer **APPROVE_NATIVE_REPAIR172/176/378**,
**REJECT product graph/#207**, **APPROVE this-attempt owned cleanup/FULL_SEALED**.
Review `f31dc71f5cb212fc8aaab6038d15c3a5ad152da2d7f117526b61c0d99f8f660a`;
bindings `62018042d8417feb1ac29492a2e08b8a8c35c524454d34531bb98176f5f09bee`.

Durable JVM14/14 proves lazy/failed-open/terminal ownership and sibling/non-POSIX
behavior, not0600/private Windows ACL or power-loss guarantees; Android-host10/10
is not ART.52othercore cases pass. LAN16pass/3fail: two accept-loop and one admission
teardown cardinality failures retain directory-fsync AccessDeniedException guard tails.
The subsequent207 corrections above do not retroactively make that graph pass.

All30pure-policy+39native executor controls pass, including exact READONLY success
and hardlink refusal. Actual Desktop runtime/image/distributable tasks execute;
real540160-byte single-link launcher WinError5 was recorded before guarded33→32
READONLY change and one successful retry. All8admitted roots removed after retention,
all39fixture final teardowns complete, task-owned wrapper stops0/no survivors;
source unchanged and FULL_SEALED/PROVED handoff preserves hostFAIL. Source directory
`buildSrc/src/main/java/dev/p2pkit/build` is not a cleanup root. No hostile path-race
immunity, headful launch or whole-host acceptance is claimed.

Original deliberately failed fixture teardown and private inspector exit2 remain.
The inspector's CRLF summary mismatch was independently reconciled, not relabelled
PASS or used to explain away the3LAN failures. Root's16:20 final Actions/ref point
found no active work/auditf73/main unchanged; actual lease release16:23:58UTC is
scheduling only. Prior34332414989 remains **FAILED/PARTIAL_SALVAGE/fullcleanupNOT_PROVEN**.

## Windows r6: exact #207 follow-up accepted, not whole-host qualification

[34393352130](https://github.com/p2pKit/P2pKit/actions/runs/34393352130), attempt1,
job102606887013,19:09:20–19:14:20UTC, clean655/treeb681: **SUCCESS**.
Independent **APPROVE_207_WINDOWS_FOLLOWUP** and
**APPROVE_FULL_SEALED_OWNED_CLEANUP**, no findings; report
`7c1603ce45fb066ffe6ea31562e7805fd5cce6e6bdb5709b501b4daac9fbeb6f`, bindings
`c9245fb9edafeec96cb0b90be54304700b2c7e9186b1e0c394862e9e13f5d79b`.

Real `gradlew.bat :p2p-transport-lan:jvmTest` selects the two affected classes:
**4fresh methods/2XML/0failures/errors/skips**,11/11executed tasks. Three real-TCP
contracts and the combined constructor/late-diagnostic rejection control pass;
exact source afterimages/token/task model and XML freshness were inspected. Other
product-model tasks remain NOT_REQUESTED. The actual constructor helper retains
filesystem probing and strict prefix/suffix assertions; no unexported branch count
is invented. Earlier r5three failures remain failures, not rewritten passes.

Executor controls separately pass **69/69** (30pure policy +39Windows native),
64.321s. Controls, SDK setup and product each0/0/0 with isolated wrapper stops,
unchanged source/no owned survivors. After retained reports, six exact generated
roots are removed; source/shared caches are not blanket cleanup targets.
Artifact10120692600:732256bytes, SHA256
`2bc25d7fa520f06f61805b655544d2d3783ad6dcc3a3bb1ed1fcdfd07ba5415b`.
All872ZIP members/1562958uncompressed bytes match retained extraction; all866state
and4bootstrap entries agree, no gaps/differences. **FULL_SEALED / PROVED** is
independently corroborated. Reviewer did not release root's lease; any release
requires its own later operational receipt, not this successful run label.

Whole **#207 remains Apple/common pending**, no denominator or repair-count change.
FullWindows qualification **NOT_ESTABLISHED_BY_FOCUSED_SCOPE**; accepted172/176/378
work was not redundantly rerun. Final independent Linux follow-up review also
approves19affected fresh methods in rootr3 (15core+4LAN), not extra1780execution.
No Apple/physical/hostile/independent133/crypto/release/whole-audit credit follows.

## #287 reviewed no-repair, not blocked work

Fresh independent **APPROVE_NO_REPAIR_CURRENT_CONTRACT**, report
`254b85c7c8f1da3fb0c0645e91aa1bc26ad45793bafaa9314040249a4ccf9642`, binds the
complete allegation/correction, actual runtime-only API, finite selector/mapping,
manifest diagnostics and callers. #372 is a separate runtime LAN requirement.
No source/fix commit or test was created; GitHub stays open. Add1resolved row and
zero repaired rows. Owner decisions120/274/284 remain separate.

## Linux and local controls: preserve failures and actual source bindings

Final Linux r1 rejects bad argument ordering125 **before product Gradle**, stop0;
237oldXML/stale-only and old-output disposal are not new test execution.
R2 runs16:46:15–16:58:45UTC atf73+diff
`68f595a41e514b4f7ec712874a92e337f2aa91e83d24e7981807e341b904f636`, not clean0dbc:
**1776/1778fresh pass/227XML**,1/0/1, no owned survivors; outputs retained for
imminent dependent inspection. The manual-identity/deadline-retry tests fail the
strict teardown net when Bob is stopped before admission. b027's6positive-method
readiness additions preserve behavior assertions/timeouts and all15class methods;
source review `6bfb033b7c838d8746f4a954bd02e5af7c7f9e0b249a44fb84e205ca70072717`
required fresh execution, now supplied by rootr3 all15methodsPASS; no new blanket warning allowance.

Android/CLI/Desktop tasks,3other Dokka tasks, ABI and SBOM generation succeed;
strict LAN Dokka still fails34warnings. Investigation
`24d1132b1bb6a7679c494dd493b1e0d48280d63e890b6e3daf693cb5723b2a0b`
finds empty shared-Apple classpaths/cinterop skipped on unsupported Linux, not34
proven source defects.32warnings are historical plus2new279references. Keep strict
Mac execution and correct rendered signatures/link inspection; internal/generated
link residue is not preapproved. Neither original failure becomes a pass; subsequent rootr3 check is a distinct source-bound execution and does not discharge strictLAN Dokka.

17:05 focused controls0/0/0: OSV6, Windows-routing13/workflow12, license9,
metadata11, real coverage/checkout/SBOM82-component/488-link checks pass.
The copied1778-case/227XML snapshot including2failures is stale, not additional
product tests. Exact logs/receipts and source diffs are in checkpoint nativeFollowups.


### Fresh root check and installed CLI correction

`final-linux-check-20260909-r3`,18:17:35–18:24:10UTC: actual
`./gradlew check --console=plain` plus CLI installDist, strict verification,
max2workers/no parallel,100executed/96up-to-date tasks, **1780fresh/228XML/0failures,
errors or skips**,0/0/0/sourceunchanged/no owned survivors. Both new shutdown tests
(real child hook probe0.614s and normal/failure/cancellation control0.006s) and all15
readiness methods execute. Base0dbc+patch
`f749728040838ac0def5417d9861f264575e7a57d76d2d4b28b19b79607ddff0`, later
source-identical655, not clean655. Receipt
`de9a6b9aec554e6669f07dbef207eca3b6559dbae4d1a720f0eb52137ad417d2`.

Clean655 local forced dependency-graph generation also passes0/0/0 with retained
actual JSON:657components/2351edges/no missing refs from11forced project tasks.
Snapshot SHA256 `466a182bd4ce80324c859670da88c6a1262b420f664105b91d30afebe72d51f9`.
After normal audit push, genuine **HTTP201 ACCEPTED**, id98932531 at19:13:07.210UTC,
returns: "The snapshot was accepted, but it is not for the default branch. It will
not update dependency results for the repository." This is audit-branch submission
acceptance, not default-branch dependency publication, OSV/SARIF or vulnerability
remediation. Generation and submission are separately retained. Root removes
1,302,487,045bytes of confirmed disposable product outputs after dependent retention;
no owned survivors/source/shared-cache removal. Copied later XML is not new testing.

## Apple r7: authentic pre-product failure, incomplete remote cleanup

[34397957269/1](https://github.com/p2pKit/P2pKit/actions/runs/34397957269),
job102622296616,19:55:45–19:56:30UTC, clean598: **FAILURE**. Independent terminal
report `df9964f39e4f7480e34fde17f5f72e6d80d0fb786e3c2adad340b4e67f44c02f`, bindings
`7054ad50597c2d8db60a837e1704ef59cdfc69f04cd1170b462715706530b908` confirm **PARTIAL_SALVAGE / REMOTE_CLEANUP_NOT_PROVEN / PRODUCT_NOT_RUN**.

Only executor controls start: **-15/0/125**,24.227s, Darwin task-name Mach5 error.
Wrapper stop0/no daemons and empty observed survivors do not erase identity/fixture
retirement uncertainty.30pure-policyOK+5DarwinOK,3FAIL+1ERROR events concern two
failing cases; no completed suite summary. Actual SDKsetup/product/Swift/native/
ABI/Dokka/publication/consumer/release gates never start. Version probes are not gates.

Artifact10122284639,226095bytes, SHA256
`ab2d2a185a5ac8534c020429d7c1f51d91dba99658bdc10c1ce95feacf594617`:
225retained regular files/693831bytes match extraction. Bootstrap224/salvage219
entries verify only the retained subset; original226-entry manifest has exactly
nine declared omissions (8JSONL+1Gradle properties, Not allowed text). Full tree,
remote cleanup and safe continuation stay **NOT_PROVEN/false**, not FULL_SEALED.
Local lease release20:21:11UTC only permits other locally serialized work; no remote
runner cleanup or product approval. Later390source repair and r8 narrow native corroboration do not
rehabilitate r7; original hostedMach5exactkernel attribution remains unknown.

The exact composed gate had13host+1workflow fixtures PASS at655+diff
`83f698523e5a02a3fe1e80c2cdb5b6971f06b3713026b40c5131971d4f7cf7f9`,0/0/0,
no productXML/generated output/owned survivor. Those are source-bound fixture tests,
not successful Apple execution. All17native rows remain, including207Apple/common.

## #388: final hosted repair approval, policy-qualified scan

[34401669960/1](https://github.com/p2pKit/P2pKit/actions/runs/34401669960),
job102634803208, `scan / osv-scan`,20:32:47–20:33:04UTC atclean598: **SUCCESS**.
Independent **APPROVE_FINAL_REPAIR_HOSTED_EXECUTED**, no findings; report
`b43687f8e3142005616040ca55b7a67a1696c2b40cde42403c083cf1a3862895`. Exact five repair paths/tenlocks/policy match the previously
approvedeea101dsource; real local success and malformed-config127 are retained,
not unnecessarily rerun or called hosted negative cases.

Actual checksum-admittedv2.5.0 scanner executes all10locks with original exit0.
It filters **GHSA-r937-wjx7-w2jp plus one alias** under the unchanged exception
expiring2026-10-31: **not zero advisories or vulnerability remediation**.
Fresh SARIF2.1.0/1168bytes has zero unignored results. Artifact10123691898,
4files/1690bytes, SHA256
`e17c425f2a6dcbe78a078e0ecf5f88ebb44b4f73cc8c0ad06d5cae222f74825f` matches
the server/upload/retention bytes. Actual CodeScanning processing completes20:33:02.994;
analysis**1750724614** binds auditref/598/osv2.5.0, empty error/warning fields.
Same clean SARIF content as local is not staleness: actual command/extraction/run
provenance establishes freshness. Empty results cannot prove nonempty locations,
fingerprints or old/new alert identity.

Successful fail-fast cleanup removes owned scanner/temp/cache/workspace after artifact
retention; no Gradle ran, so no irrelevant wrapper stop was required. No postmortem
VM/global-process proof is claimed. Actual local lease release20:55:59.204UTC has
no freeze violations; receipt `69ae08451a52f488134b7631d7b1a2942f8c2cb71d52f924e819667530f363d4`. Original source-confirmed
fail-open cause/local failures remain. Approval adds one repaired row, no closure,
platform/default-branch/professionalcrypto/release or whole-audit acceptance.
The [safe public outcome](https://github.com/p2pKit/P2pKit/issues/388#issuecomment-5608874152)
was posted21:17UTC; the issue remains open.

## #389: original installed SIGTERM failure and final approved correction

[Filed #389](https://github.com/p2pKit/P2pKit/issues/389), server creation18:07:44UTC;
client creation receipt retains18:07:42.635183–18:07:43.443963UTC. Body
`0bcbde1d8dd48476bf740c582be3eee053837da6d472e6bb3a4088b32fdbccdc`;
evidence/dedup review `a6d243f6aef1d6bcfd8825a0622a0d2607b814984e8d5054f15c311867a852ae`.
At17:29 the actual installed Linux/JDK17CLI, pidfd SIGTERM with stdin still open,
exits143/~0.414s with **zero Stopping/shutdown/completion**, unchanged pre-signal
export and no survivor. Missing JVM shutdown integration is distinct from existing
203/228/329/336/380/381/PR102 causes; no core protocol/data-loss claim.
EOF/quit pair/replacement/exact-once messages/consented4096-byte transfer controls
pass; orchestration0 is not graceful SIGTERM or fullPS-T05PASS. Catchable signal
cleanup must be exact-once/bounded/truthful; SIGKILL cannot promise finally.
The filed text had no severity; its filing-time inventory field remains unclassified,
not an unresolved repair. Final independent **APPROVE_FINAL_REPAIR_LINUX_EXECUTED**,
no findings, report `fa68ed91ea32dd405f7509e3633624a15fac9c8334cd802f5d2af30fd7482c8f` and execution bindings
`1e64a5bcba0dc3a2661ade0c0394098d80e0f1f5f0620604dd06565082d00b34` approve exact patch above; commit655 binds identical source.

Actual installed-launcher runtime r2,18:26:11–18:26:33UTC at0dbc+samepatch, keeps
stdin open and sends pidfdSIGTERM: exit143/~0.408s, exactly1Stopping/1completion/
1shutdown, finalState/outcome **CANCELLATION**, changed finalZIP SHA256
`de71116d36d3851c489c3bee988994eda3185649213dd41fb265e50e5925be9a`, all5entry
checksums valid. A/B EOF/quit/pairing/message/file controls pass. Independent reviewer
reopened transcripts/JSONL/ZIP; driver0 alone is only orchestration success. All3
children reaped,0/0/0/no survivors or forced escalation. Required evidence retained;
root removes184202bytes of owned fixture/home/tmp disposable data after review.
Originalr1 remains a real missing-finally failure. Approval is idleLinux/JDK17 repair,
not fullPS-T05, connected/in-flight/everyhost signals, SIGKILL/power-loss, physical/
hostile-network or independent-interoperability qualification. After source push,
[the safe public outcome](https://github.com/p2pKit/P2pKit/issues/389#issuecomment-5607333480)
was posted19:13:56UTC; the issue remains open.

## Darwin continuation #390–#393: current verdicts and preserved failures

| Issue | Exact source / evidence | Current disposition |
| --- | --- | --- |
| #390 | 3c038; four-path patchc85e1e2;11modeled methods PASS at598+two-pathdiffa132d25; actualr8environment/token reconciliation. | Source approved, native mechanism corroborated; final native approval withheld. |
| #391 | 49f05; patch0c10dd6;12modeled methods PASS at4a20+patch; three affectedR9methods pass. | Source approved; final native approval withheld while genuine opaque-token control fails. |
| #392 | 5a363; patche69f4a1; shared7Linux controls PASS at49f05+patch; actualR9wrong-home refusal/discovery/retirement. | **APPROVE_FINAL_REPAIR_NATIVE_EXECUTED**, no findings; only new repair credit. |
| #393 | 07bc; finalpatch40508a8; source approval after original-Popen F1 guard. | Local/not pushed; actual final native execution pending. Initial AST is zero tests, not final-guard execution. |

Source reviews #390/#391/#392 respectively:
`704e2b168a60e5b2fa85a02e0d306b5a87dccdb716175deb5a0acf5d5de7f909`,
`62bd9c8374d7b4216760571cd12db055cd263839cc63c31c579285da999ad9f2`,
`32ab9fa7f93e5b17850f65f8f5a25b3760481302423eadf6a53b559db5ec3b7f`.
The11modeled,12modeled and7Linux controls each retain0/0/0, unchanged exact source,
no owned survivors/generated outputs. The seven-method run takes21.302s; its real
Linux wrong-home leaf125/null/null and enclosing retirement are independently read.
These are Python controls, not XML counts, native Apple or product builds.

Original #390 two-method reproduction at598+test-onlydiff
`ee11730b0747b156a68d1d06a847003aef66d36fb39ef1b40ec7bc745bd54423`
remains2environmentFAIL+2tokenERRORsubcases,1/0/1. Its correction preserves pending
INEXIT, real audit tokens, lifetime/exec/domain/port checks and fail-closed stable
denial; retry/sleep bounds are not wall-clock kernel guarantees. Original r7's exact
Mach5 kernel branch is unobserved. Filing and full exact evidence hashes remain in JSON.

### Apple r8: authentic failure, no final repair credit

[34409424013/1](https://github.com/p2pKit/P2pKit/actions/runs/34409424013),
job102660114268,9September21:54:23–21:56:16UTC, clean4a20: **78-method suite FAILED**,
9failure+4error events across4methods;30policy+10modeled+34actualDarwin methods OK.
Three consumers fail unsupported signal0/EINVAL22; wrong-home fixture fails correct
domain refusal. Outer **null/null/125**, owned survivors **UNKNOWN**, incomplete
fixture cleanup. Stop text alone never establishes a stop exit or retirement.

R8 independently corroborates11distinct reconciliation events on attempt2 (six
receipt duplicates excluded), including actual environment and Mach5→absence
paths; consumer integration and real-token methods pass their own cleanup. These
positives are not final390acceptance. Review
`1409708b47f34a5ed8bb5ca9d818b59961343f50e96a6440e8b02628df8a6e33`, bindings
`b346deffa5d9ff546acd5d36178e1a9e928b903bdb539384f71c48e7b5181293`.
Artifact10126687596/818274bytes,
`cb531a00c731838f8e57d15dce1f00d0dbc7a43aa3aa231528eef4530ba4acb8`:
868retained files/2414587bytes verified; **24 omissions**, PARTIAL_SALVAGE,
full tree/remote cleanup **NOT_PROVEN**, safe=false, SDK/products **NOT_RUN**.
Local release22:48:41.916UTC is administrative. Originalr7failure remains above.

### Apple r9: #392 accepted inside a failed suite

[34418616858/1](https://github.com/p2pKit/P2pKit/actions/runs/34418616858),
job102688937279,9September23:49:45–23:51:30UTC, nativeARM/Python3.14.7/clean165e4:
**79/80 methods OK, one FAIL, no errors**,78.521s. The genuine opaque-token method's
**first SIGTERM returns ESRCH3**; later stale/sentinel assertions are not reached.
Outer native-controls **1/0/1**, no errors/owned survivors; same-owned wrapperstop0
and enclosing retirement are corroborated. This is a unittest command, not product work.

#392 final review `99cd24e93209ef8479de6224c959f64a79b81a476d1c670cbbbe9e555fa6036d`
checks27files/237583bytes including complete14/14original wrong-home subset. Actual
Darwin controller/descendant discovery, exact leaf125/null/null home refusal,
preserved ancestors, no product/wrapper calls and complete fixture/enclosing
retirement establish **APPROVE_FINAL_REPAIR_NATIVE_EXECUTED**, not a suite pass.
The [safe public outcome](https://github.com/p2pKit/P2pKit/issues/392#issuecomment-5610893829)
is posted10September00:42:41serverUTC/clientfinished00:42:40.187480; issue stays open.

#391 review `5a71b373ade06f9bbd605d376761715a1d0a7bf97c3cb5fdb8e1680b16984a0b`
binds26selected files: all three cancellation/recovery methods pass with complete
final retirement, including6/6capability proofs and explicit resolution after
injected1/6 or0/6failures. Initial deliberate failed cleanup remains evidence.
**FINAL_NATIVE_APPROVAL_WITHHELD**: genuine-token control is still required; no new
391source finding. #390also receives no final credit from this failed control.

Artifact10130085543/907930bytes,
`61842cff8f6f11baa9904bb128d40940fc41ed51d8ca76d428c065add7a8d3eb`:
directory/extraction record944files/2484555bytes; independent scoped inspections
above do not invent a new full-corpus audit. **31 omissions** (30JSONL+1properties),
**PARTIAL_SALVAGE**, full tree/full remote cleanup **NOT_PROVEN**, safe=false.
SDK/library/Swift/UI/ABI/Dokka/publication/consumer/release products **NOT_RUN**.
Actual local lease release10September00:19:32.661UTC, zero freeze violations,
follows a point-in-time00:17:51–00:17:58 no-active-Actions observation. It is
administrative only; clean invocation retirement does not seal the evidence tree.

### #393 source repair and next acceptance

[#393](https://github.com/p2pKit/P2pKit/issues/393) was actually filed Low,
body `09ef3820d66b75ec8b8a526df8d6f0b2a7539ebaea57a80f58029fb7d12f30e5`;
client10September00:24:28.719–00:24:29.487UTC/server00:24:30UTC. Bounded duplicate
inspection392bodies+542comments finds no owner. Missing target-body readiness and
officialCPythonframework SETEXEC/execve are confirmed, **not the particular R9
epoch/kernel cause**; acquisition/pre-signal epochs were not retained.

Initial REQUEST_CHANGES report
`2f9c03a4183e8cb396122d535d7a0dd56cecbe9e2e18a572ddc5559adeccb680` retains F1:
readiness discovery can reap an unexpectedly exited original child. The final
one-line `child.poll()`-is-None assertion before authority binding resolves it.
Final **APPROVE_SOURCE_REVISION_NATIVE_PENDING**, no unresolved findings, report
`4c4035f1bae6535f431bde6dc9463cf6c765e9812521f5c6133a02dcc033c6b9` binds patch
`40508a813b50ae14e5ed9d58c597eedd419505411ae28a4074cb44f3c11ea40d`, commit07bc.
Initial00:25:28–00:25:29 AST syntax inspection atpatch567412 executes **zero tests**,
0/0/0/no survivors or outputs; it is not rebound to the final one-line revision.
Actual final Darwin readiness→saved-tokenSIGTERM0→same-tokenpost-exitESRCH3→live
sentinel and complete owned cleanup remain required, then final393/390/391 reviews.
No arbitrary sleep, deadline extension, fresh-token/PID fallback or weakened
assertion is authorized. Refresh Actions/refs and hold the task-owned execution
lease/source freeze BEFORE any audit-branch push that triggers R10. Publish only
independently reviewed safe PRE-R10 documents/source while that lease/freeze is
already held; no future run/publication is inferred by this checkpoint.

## Continuation and corroboration limits

[Current queue](../issues.md) and [follow-ups](../followups.md) govern.
Preserve all earlier failures, including AppleR7/R8/R9partial evidence and cleanup limits. Use exact
source and non-overlapping owned runs; don't repeat unchanged successful scopes.
Current whole-source/coverage, required check/samples/consumers/nativeIntel/fullWindows
and strict supportedMacDokka/ABI/Swift/release gates remain. Component replay is not
the release monolith. Physical/hostile/independent133/crypto and owner decisions remain.

Live GitHub19:51:13–20:18:04UTC:35successful reads,310issues(203open/107closed),
79PRs(7open),all203open+79PR bodies and541complete retained comments/366openissue
comments reconcile; no new owner decision or extra inventory row. Report
`98a5c0fc70717dc7e42936dbeecce420e58aca1f7bd0e8ab4ce52f05e9848205` preserves reused closed/detailed-history scopes and
historical patch/inline/comment/backlink gaps. Its160repair count predates388approval;
203membership applies to that historical census. A three-endpoint item/comment/inline
21:06:02–21:06:04UTC delta since20:18:03 is empty (receipt
`a006a58f2e9bc90509fda487cd7c290d0efda38157a6f7b1b73b9e3e99fb0de3`). Actual390creation then yields204inventory rows;
not a fresh204fullhistory/census or new repairapproval. Later22:29bounded delta
and actual391/392/393filings yield207inventory rows, still not a new207fullhistory
refresh. OSV and392outcomes are individual comments, not issue additions.

All required logs/failures stay private; hashes identify evidence, not cloneable raw
payloads. Task-owned stops/cleanup preserve source/caches/evidence. Seven current
admin sections are synchronized; historical narratives retained once. Coverage binds
current authored administrative deltas only; historical text is not freshly
re-corroborated, and no cyclic coverage hash or independent admin approval is invented. Protected AGENTS.md/CLAUDE.md unchanged. This preparation
ran no build/test/API/native probe or cleanup and grants no issue-closure/main/tag/
settings/release authority.

## Apple R10: final fixture approvals, later policy failure

**Current outcome,10September2026.** 165/208 independently approved repository repairs (79.3%); 166/208 independently resolved rows (79.8%) including #287 without a repair; 42 unresolved (20.2%): 18 repair/native rows, 21 external-validation rows and 3 owner decisions (#120/#274/#284). 75 new audit findings. **Whole audit NOT_READY; #133 independent NOT_STARTED.**

Actual normal push/ref verification01:10:40.964UTC published `9ecd4e5be7fbbbae1c250c5de9170090fa8676a7`,
tree `8c443ebeddfdeec32c60a32b9719f18552730b58`, while the task-ownedlease/sourcefreeze was held;
receipt SHA256 `61b84b26a88bfd9dbbc310a6854510d675d64fd9ce17665a94481053a10fbdb1`.
[Run34424409933/1](https://github.com/p2pKit/P2pKit/actions/runs/34424409933),
job102706473770,01:10:51–01:13:59UTC onmacos-26ARM/Python3.14.7, **FAILS overall**.

- **#393 APPROVE_FINAL_REPAIR_NATIVE_EXECUTED**, no findings; report
  `c165ee7fa3f8797229e0a17cc1389e3affbad46ab78765c135def581aa08c6b1`.29selected retained evidence hashes checked;
  target readiness/original-child-live preconditions, same-tokenSIGTERM0,
  targetexit-15, post-exitESRCH3 and unrelated-sentinel survival pass. Complete
  scoped fixture/enclosing retirement; readiness marker itself not retained.
  [Actual safe outcome](https://github.com/p2pKit/P2pKit/issues/393#issuecomment-5611405568)
  posted01:44:01serverUTC; issue stays open. HistoricalR9exactcause remains unobserved.
- **#391 APPROVE_FINAL_REPAIR_NATIVE_EXECUTED**, no findings; report
  `fdac4094be187383d9642c98502c8f7bbb64581d1922cd9f60f3ec7bfc4a5e9f`.46selected files/9essentialZIPcomparisons,
  all3 actual Darwin cancellation/recovery methods and required393control pass.
  Complete6/6 chain proofs, preserved1/6and0/6 deliberate primary failures and
  separate full recovery/resolution; final fixture cleanup complete.10JSONLcall
  journals omitted inside affected trees, not the required identity/proof/receipt/
  control/cleanup records. [Actual safe outcome](https://github.com/p2pKit/P2pKit/issues/391#issuecomment-5611405453)
  posted01:44:00serverUTC; issue stays open. #392 keeps its earlierR9 approval.

Native executor **80/80 PASS**,87.040s:30pure policy,12modeled Darwin,38Darwin-selected
methods, not80independent native experiments. Outer command/ownedstop/final0/0/0,
sourceunchanged/noerrors/survivors; actual same-owned wrapperstop0. AndroidSDK36/37.0
provisioning, SDK TCP-header inspection, XcodeGen and policy0wrapper/1verification
pass. Header inspection is not compilation or generated Swift bridge approval.

Later `policy-2-check-dependency-update-policy-test` leaf
`8e120e53c8654925820d72caf1bca4a8` fails
`OwnershipError: Cannot reinspect a recorded Darwin process identity`:
**null/null/125**, failed pre/finaldrain and wrapperstop/pipe completion,
**UNKNOWN survivors**. **#390 remains unapproved**; exact failing identity/cause
not established. All library/native/Swift/UI/ABI/Dokka/publication/consumer/release
products **NOT_RUN**, simulatornull, release monolithNOT_EXECUTED_COMPONENT_REPLAY.

Artifact10132152568/984192bytes SHA256
`c81e231577a221b52e5b797460fb4c74be2bd7c67ccac540ae2e4b8d5b28da4e`;
existing extraction inventory1008regularfiles/3012868bytes. Independent scoped
inspections above do not invent a new complete-corpus audit. **PARTIAL_SALVAGE,
62omissions**, full tree/full remote cleanup **NOT_PROVEN**, safe=false.
Clean accepted invocation retirement does not seal the whole host/evidence tree.

Fresh global idle01:36:23–01:36:29UTC precedes actual lease release01:37:27.051UTC,
sourceunchanged/zero freeze violations; release SHA256
`279da5db5a40a6455ff79abe5cf67b223d8dd80c2556a88e51320708d129c19b`.
Administrative only, not remote cleanup or a standing execution lease.

Bounded GitHub refresh00:45:15–01:00:15UTC:39successful reads,314issues207open/107closed,
79PRs7open,286freshopen/PRbodies,543completevisiblecomments/368openissuecomments,
812openlinkevents and28reconciledtimeline deltas. No new owner decision/untracked
defect; unchanged107closed bodies/decisions and detailedPR/117firsthop histories
reused. Report SHA256 `5b4cf6726024d3ad6b2194fc1d17d671f6f96b2ff9988c113e284aa177c3be2e`.
Its201-row committed-ledger observation predates9ecd; the bounded207rows were corroborated before the separate394filing.
Two01:44outcomecomments above are later individual deltas, not a fresh census.
Historical missingpatch/inline/comment/backlink gaps and preliminary offline parser/
REST-MERGED representation failures remain. Only separately bound completed local-run outcomes are included; no future source
result is inferred. Continue plannedR11/390native and the18repair/native queue, final
whole-source/check/sample/consumer/release and separately required external gates.

### Post-R10 filing and scoped CLI follow-up

[#394](https://github.com/p2pKit/P2pKit/issues/394) was actually filed Low at02:00:34serverUTC,
client02:00:33.010–02:00:33.706; bodySHA256 `b3ac157d70deb7c144f6b2e34457b4bd8fb29b62466b7e65d7d5bdc184f7239a`.
BufferedTee retained-file writes wait for EOF despite live prefix delivery;
actual2,551-byte stderr prefix is absent from retained0-byte leaf stderr. This
is distinct from390 and371; loststdout and exactremote buffering/kernelstate are
not established. No reproduction/repair existed at filing; the finalrepair section below supersedes
that original filing-only scope.
The02:00:04 three-endpoint delta since01:00:15 found onlyexpected391/393bodies/
outcomecomments, inline0. Actual filing yields208rows, not fresh208fullcensus.

#390's current candidate patch`a3c6768a46a6e24b7632db6fa52521ce1c2f294f202ec31eb8703aa361837682`
at9ecd+diff passes14modeledmethods/0.032s,02:05:42–02:05:43UTC,0/0/0/noownedworkers.
**APPROVE_SOURCE_EXECUTION_PENDING**, no findings; final reportSHA256
`f132e33f1d413ffb7e7bfd0fa21a262aabfbca3282a0bbee68cb277c9e0bfeb6`. Exact approved patch is locally committed
`21339c1dc769470b622a04cd8105198db6f4c43a`, tree`6800534bca12c7235a03fe3ec3c5ce69836e67ef`,
**NOT_PUSHED/final nativeNOT_RUN**, no newcredit.14modeledPASS remains9ecd+diff,
not clean21339execution. Initialred/R1review/green evidence is retained. Relevant
realidentity/sentinel/consumer controls and actualpolicy2/GPGcaller still required.

Actual clean9ecd installed-CLI follow-up is independently **APPROVE_SCOPED_LINUX_RUNTIME**:
installDist17tasks/zero tests and runtime both0/0/0; receiverFDlimit restored in
0.104195s, same-session4KiB recovery, pending-unaccepted-offer SIGTERM143/0.407201s.
32,867,485 disposable bytes removed after review; logs/JSONL/allZIPs retained,
no owned workers. This is not fullPS-T05/D2/D5 or external/native qualification.
Review SHA256 `ae4c3ae2414d6f931b007f722d4b0be53c946620d2f090ea1b3f2e4dd70ba944`; disposal receipt
`ecdf2232ebe987b836cf58e326da07a48c3f8fedf24aa7ccdde26ee62e2fc776`.
This completed15.807s Linux/JDK17 paired-loopback slice retains cancellation,
sevenZIPsnapshots/35manifesthashes and exactchild-limit restoration. No in-flight/
SIGKILL/restart/sustainedpressure/disk/otherhost/device/hostile/interop/crypto claim.
JSON currentevent: `nativeFollowups.postR10Followups`; whole audit **NOT_READY**.

### #394 final repair and R11 boundary

**#394 APPROVE_FINAL_REPAIR**, no findings; final review SHA256
`a1245ff8b89baf6678055b23d5f618d8ec832cd7f58904924f6e56c9f93abfb5`. Exact patch
`493d262ac4faabdb6bea0430254491780555d009feb0b32937d2a4a9b0bccb86` is locally committed as
`79a18dee1f9b4196db29ecf14b5bd2638849cef7`, tree`8e536701ba2e94dfdd37702dc9b3afd4685dd66e`,
parent21339. Shared same-reader chunk flush publishes exact evidence before live
output; finalfsync/noEOF/errors/ownership unchanged, no per-chunkpowerloss claim.
Original2FAIL/3.009s/1-0-1 at21339+testonlypatch is retained; final5PASS/7.302s/0-0-0
ran at21339+493d, not clean79a18. TwoactualTee binaryprefix/flusherror controls and
3realLinux nested success/raw, timeout/cancel controls pass their strict assertions;
negative leaves remain-15/0/125. Complete3fixture cleanup/realouterstop0/noownedworkers
or projectoutputs. Fixture wrappers are fake; these are not product/Gradle tests.
Required logs/receipts remain. OldmissingR10logs/UNKNOWN/62omissions are not repaired
retroactively; no exactremote buffer/kernel attribution or390nativecredit follows.

Currentlocal `557156171d1f642c12ad6c7f87591b1af7ceaf23`, tree`71d48f59513731e65f9f803ba2f2bd016bbdabb4`, adds only the
mechanicalcomment10-to11 after79a18. **NOT_PUSHED; nextARM R11 planned NOT_RUN.**
Refresh Actions/refs and hold task-ownedlease/sourcefreeze **BEFORE triggeringpush**;
require relevantchangedDarwin controls/actualpolicy2caller and independentnative
verdicts before advancing. Currentcount165repair/166resolved of208,42unresolved;
wholeauditNOT_READY/independent133NOT_STARTED. No futurepublication/run inferred.

### Post-#394 GitHub inventory refresh

Current API window02:24:47.699838–02:37:32.433205UTC:30 successful reads, closing
item/conversation/inline deltas empty. **315 issues,208 open/107 closed;79 PRs,7 open**.
All394 local full bodies and545 visible comments freshly returned/count-matched;
old393 bodies/543 comments unchanged. Known394 filing and391/393 outcome comments
are the only new text. All818 open-issue links,2 open-PR links and7 open-PR REST
timelines refreshed. No missed distinct defect, changed owner decision or conflict.
All208 open inventory members now freshly corroborated; prior203 adds390–394,
prior207 adds394 alone. Repair numerators remain independent-verdict based.

Report SHA256 `5bfaab9875a356a05266acaebe27c8e604fd44ba27486de73c3b7282679e6b01`;
reconciliation SHA256 `4cef93794435099ec7f340aa87be4f2cb3ad31e5570c4b2fd29986a3c5ab6d42`.
`checkpoint.json` `nativeFollowups.githubPost394Refresh` binds the concise scope.
All107 closed bodies/comments are now fresh and unchanged; detailed79local/117upstream
PR histories remain reused after metadata equality, not recrawled or newly manually
reread. Earlier freshness statements above remain their dated observations. Preserve
missing patch/inline/comment/backlink limits and initial private parsing stops; no API
or product test failure. Serial metadata only, no Actions lease/native/repair approval.

### #394 pre-push fixture portability follow-up

Final composition **APPROVE_FINAL_REPAIR**, no findings; review SHA256
`83dee9c983b74319462b103c88d928cf7a1688824e5b310973fa44260e20154f`. Focused commit `bf65e7a921a32bbdcca42bd868cf3ae306d8c8a0`,
tree`4da795235429a5c4167ec276acca3ab8760e1f3e`, adds only `resolve()` on the two newly created,
test-owned temporary roots. Production no-follow checks, raw-byte assertions,
error/drain behavior and teardown are unchanged. This follows the existing fixture
contract; it is not an observed macOS failure or an extra repair row.

Controlled owned symlink temporary root: original two methods ERROR in0.002s
before their behavior assertions, command/stop/final1/0/1; final two methods PASS
in3.009s,0/0/0. Both logs/receipts retained, physical temporary roots and aliases
disposed, no owned workers/project outputs. Eight administrative changes stayed
identical across both runs; neither was a clean-commit execution. Original #394
five-method evidence/production approval reused unchanged. See JSON
`nativeFollowups.postR10Followups.fixturePortability394` for exact bindings.

Current focused source bf65e7a is **NOT_PUSHED**, R11 **PLANNED_NOT_RUN**.
The earlier557156 record remains its dated mechanical-request observation.
No #390native/product/whole-audit credit. The previously completed497-link check
passes; this wording-only follow-up adds no new link. No redundant build/link
cycle is needed; JSON parsing and whitespace checks still apply.

## Apple R11: scoped native approvals and product failures

**Current successor,10September2026, bound to source65f3 after final395 and source-only396–398 reviews.**
170/214 independently approved repository repairs (79.4%); 171/214 independently resolved rows (79.9%) including #287 without a repair; 43 unresolved (20.1%): 19 repair/native rows, 21 external-validation rows and 3 owner decisions (#120/#274/#284). 81 new audit findings. **Whole audit NOT_READY; #133 independent NOT_STARTED.**
This section supersedes earlier planned-R11/current-pending statements only for the
actual observations below. All earlier report text and failed evidence are retained.

Actual [R11/1](https://github.com/p2pKit/P2pKit/actions/runs/34432810650), job102731677129,
executes published clean `18681d6b93165e4fa7557aed95b92a09da6c8c90` / tree`0dec0fd73aed47223fd8b9f5e254e8428c35f88a`;
job03:18:29–03:53:03UTC, host03:18:38–03:52:53UTC, macOS26.6.2ARM/Python3.14.7/Xcode26.5.
**Whole result FAIL.** Artifact10135840583/4,737,391bytes SHA256
`fcfd14de335ccd558cc337604af9f49a922842ebbc77d8536e39bcda338a27ec` is **FULL_SEALED,
fullTreeCompletenessPROVED**, not salvage. Independent390 review checked all2,569
manifest members; existing authenticated extraction2,575files and full-hash review
were reused, not repeated. ManifestSHA256`a18d439562cd78703b948df7fe1292215a57163c8b14fd1df7cffc271e2c31a8`;
hostSummarySHA256`5763c4b3b69c0ac90ae65d401271c64663a54cde0759e1fe3970fd528fea7aa2`.
`safeToContinue=true` concerns complete evidence/owned cleanup, never product acceptance.

### Final native repair verdicts

- **#390 APPROVE_FINAL_REPAIR_NATIVE_EXECUTED**, no findings; finalcensus21339
  unchangedat18681. ReviewSHA256`ebaf20cc808008674c6f600ca12baeeb1561105930e3a1434834d0628f071285`.
  Actual saved-tokenSIGTERM0/targetexit-15/same-tokenESRCH3/live sentinel and allthree
  six-identity cancellation/partial/prebind recovery controls pass. Four actual
  known-PID identityEPERM events resolve to positively observed absence (attempts
  2/3/2/2),17reconciliations resolved. Actualpolicy2/GPGcaller0/0/0. This does **not**
  identify those PIDs as setuidps or establish R10's exact kernel cause.
  [Published390outcome](https://github.com/p2pKit/P2pKit/issues/390#issuecomment-5613203287),04:33:28serverUTC.
- **#250/#261/#379 APPROVE_FINAL_REPAIR_NATIVE_EXECUTED**, no findings; shared
  independentreviewSHA256`3c4cd265e7f07c13e2053baf8506719d40c6c92c6d5d37483a32014e32e145dd`. All21original repairpostimages unchanged:
  250`d4ce3598a1d139721e0a2744a3779f2f38bfc7de`,261`e0e52cb9598e9ba367420fa7f5d1c012832223c6`,379`f260136be7b6e5115c785965b3ee29e6d791439d`.
  Actualnative **17/8/50methods PASS**:3namespace-lock+14storage/recovery;
  1shared24-literalvector+7NSUserDefaults;4hooks+43registry+3discovery-reemit.
  Fresh matching XML/execution/task/source bindings independently inspected; prior
  successful host/source reviews reused. These75methods are not75newtests.
  Publicoutcomes [250](https://github.com/p2pKit/P2pKit/issues/250#issuecomment-5613317013),
  [261](https://github.com/p2pKit/P2pKit/issues/261#issuecomment-5613317195),
  [379](https://github.com/p2pKit/P2pKit/issues/379#issuecomment-5613317360),04:46:12–14serverUTC,
  after the refresh window; individually bound, not a later census. Allissues remainopen.

No physicalKeychain/first-unlock/powerloss, AndroidART/persistence-device, lock-free/
hard-time guarantee, SwiftTask-to-KotlinFlow, #207whole-row, Intelruntime, ABI, LAN/
remainingrootgraph or external/release credit follows from these scoped approvals.

### Actual component results and failed gates

| Component | Actual R11 result / remaining boundary |
| --- | --- |
| Executor controls | 84mixed methodsPASS83.808s,0/0/0; not84independentnativeexperiments. |
| Policy2/GPG | PASS0/0/0; previousR10failure remains historical. |
| Policies3/13/18/27/30/33 | FAIL1/0/1 each; other28policy scripts PASS. |
| Root platform profile | FAIL1/0/1: coreARMsim774PASS,Androidhost82PASS,JVM838PASS+1FAIL. Remaining LAN/provisioning/sample graphNOT_COMPLETED; ABI not reached. iosX64compiles/links,testSKIPPED. |
| Artifact tasks/SBOM | PASS0/0/0: AndroidassembleDebug,CLIcheck/installDist,DesktopUItest/checkRuntime/hotRunArgfile/createDistributable,four strict supportedMacDokka publications,CycloneDX; SBOMinspectionPASS. |
| Isolated consumers | FAIL1/0/1 at publication duplicateconsole parser; actual consumerbuild/15licensechecksNOT_RUN. |
| XCFramework/XcodeGen | Build/minimumOSinspection/actualprojectgenerationPASS; both404857-byteheaders retained,SHA256`c4304db73e64cd944cd991505b0c50a05a0ea4a0addf2cafabe6b8b3e9f7a179`. |
| Swift warnings build | FAIL65/0/65 in nestedprebuild provenance1/0/1 **beforeSwiftcompilation**; unit/UI NOT_RUN,simulatornull. |
| Release monolith | NOT_EXECUTED_COMPONENT_REPLAY; component passes are not releaseapproval. |

Corefailure is `NetworkPathRecoveryTest.pathSatisfiedWakesParkedReconnectHandlerBeforeDelayExpires`:
second dial absent within10s; strict-logger incoming-handshake timeout is retained
as suppressed teardown failure. Source triage identifies two feasible schedules:
testReconnecting can precede Unsatisfied consumption; productionReconnecting is
published before onWillReconnect captures wakegeneration. Actual R11trace does not
identify which happened. Deterministic causality/regressions, not timeout extension,
are required. Separate399/400actualfilings05:17:05 track these causes; no repair approval
or cause-specific freshreproduction is inferred from filing or the shared R11failure.

Policy27 group-drainEPERM stays **#157 follow-up**, not a proven zombie defect or
#390duplicate. Earlier identical20methodsPASS; later resistant-worker failure lacks
failure-time raw workerstate/signalphase. XNUzombie-onlygroups are a hypothesis;
never turnEPERM into disappearance. Outer cleanup success does not excuse failed
inner fixture cleanup/assertions. Triage hashes are retained inJSONappleR11.triage.

### Actual findings395–400 and source/repair boundaries

Root filed four distinct Low causes04:36:13–15serverUTC after currentbody/comment/
linkedPR/closed-decision duplicate reconciliation:

- [#395](https://github.com/p2pKit/P2pKit/issues/395): one adapter-appended singleton
  cause shared by Swiftprovenance/consumers/policy3/policy13, not four defects.
- [#396](https://github.com/p2pKit/P2pKit/issues/396): generationfixture omits two
  sibling diagnosticJSONresources, distinct from346scheme/313352diagnosticbehavior.
- [#397](https://github.com/p2pKit/P2pKit/issues/397): canonicalhash POSIXranges depend
  on locale; actualnativeuppercase accepted, distinct from343GPG/314phase docs.
- [#398](https://github.com/p2pKit/P2pKit/issues/398): fixture mocksPath.lstat while
  actualguard callsPath.is_symlink; Python3.14 boundary differs, not demonstrated
  production symlink bypass or373/378cause.

**#395 APPROVE_FINAL_REPAIR**, no findings; independentreviewSHA256`9c97b5b312c2e791d4310383b4871b2e6c434ea070f8a41935c08d1094ee4b8b`;
exactpatchSHA256`98f3939367aaca3d491e2ec447c6e876e518620040b266e844ad673bebd86b69` committed`1ea177bc4e3094e1e33f3cd3dac355b65db7faa4`,
tree`89f4c45ce2e6e317e64b4fce39b951ecab516a56`. **Normal audit push/ref verified05:00:51.957775UTC**,
[actual395outcome](https://github.com/p2pKit/P2pKit/issues/395#issuecomment-5613440522) posted05:01:31serverUTC.
Twofiles only; original raw callerprefix and all unsafeoption/resource/provenance/
ownership rejections remain. Only validated matching singleton defaults are omitted;
callerduplicates remain untouched. Existing syntheticconsumer assertion also updated.

Freshred04:40:10–11: newmethod15subcasesFAIL1/0/1 at18681+testonlypatch
`c70eb58938eb3726b1bcb94eb7018637bd8c69aceceae018447ae96c22b11775`.
Freshgreen04:41:11–19:9methodsPASS6.338s plus actual checked-inGradle9.7parser0,
0/0/0 at18681+98f393, not clean1eaexecution. RealLinuxexecutor/syntheticconsumer
integration retains exactrequestedargv/isolatedMavenpaths/receipts. Payload wrappers
are synthetic, not productcompilation. All40retainedarchiveentries independently
checked; fixturedeleted/noownedworkers or generatedoutputs, realouterwrapperstop0.
Nativeaffected callers/policies remainpending. Required original red/green logs and receipts remain.

Source-only finalreviews have no findings and **add no repaircount**:
396`583d9ba239d4904320fbc401038abf862245e743` adds only twoexacttracked resources;
397`3db03bb08521547edf77b9a923eb4fc6ddce208d` replaces the shellrange with literalASCII;
398`65f3f2c8d6b827285704cc54093d9368dc86cccc` models the exactis_symlinkpredicate.
Currentlocal65f3/tree`f0d2345ae1c7976874793d7d13f603ca002dc79d` is **not yet pushed at this observation**.
396's actualthreeXcodeGenmethods pending (R11setup0tests).397's twoexistingLinuxsh
methods PASS C1.157s/en_US.utf8 1.161s,0/0/0; exactR11localeunknown, nativepending.
398's twoexistinginlinecontrols PASS0.012s/r2,0/0/0; r1wrongclassselector2ERROR
preserved, not redproductfailures; actualnativePython3.14 pending. No survivors or
outputs in localinvocations; all actualownership/assertions remain.
ReviewSHA256s:396`b3c0e9f25505ad012319db16832cee7d5c67ee1e723a6518e856f95076712338`,
397`df8ac8ba1d0e627a6d0c7216bc89adab557136ea2a3ae41b1ef9f66eacc1c2c5`,
398`671eacffc44779db5b2a58aa7d0102fcaaafaa459f9e5dc3d85b8e477cd62301`.

[399](https://github.com/p2pKit/P2pKit/issues/399) productionpublication and
[400](https://github.com/p2pKit/P2pKit/issues/400) fixtureconsumption were actuallyfiled
05:17:05serverUTC. Distinctcauses/currentcallers plus205/207/245/closed15/20 inspected;
sourceconfirmed, freshcause-specific localreproduction NOT_STARTED **atfiling**.
PriorR11doesnotuniquelyattributeonefailure. Fix399before400 sequentially, preserve
watchdogregistration/terminalfencing and strengthen testcausality withouttimeouts.
Laterrootworkingchanges remain outside this65f3source-bound successor.

### GitHub, cleanup and continuation bindings

GET-only04:30:17.527902–04:42:16.717296UTC,146success/zero APIparserfailures.
Initial315issues208open/107closed;79PRs7open;all394fullbodies fresh/unchanged.
Prior545completevisiblecomments explicitlyreused plus known394outcome5612132413:
546projection countmatches all394initialitems, not fresh endpoint retrieval/manual
reread ofall546comments.79localPRlistmetadata and117firsthop fullRESTmetadata match;
REST lacks historicalGraphQLlastEdited/reviewthread/countfields, not relabeledfresh.
Detailed unchangedhistories reused. Closing bounded delta has only390outcome and
four actualfilings; fullaffectedbodies/comments/timelines fresh. **212=fresh208+four
separatelyboundfilings** at04:42, not a new212fullcensus. Later05:17:03pointdelta
returns only known250/261/379/395outcomes; actual399/400filings then yield214, not a
new214census. Allfour lateroutcomes are separatepublications. RefreshreportSHA256`876e69e59d60b546f27ad9211c43ae395d978d5b62bc9cb3cf5e7516bf62b6be`;
reconciliationSHA256`89bdaf96c66d21abd9ff4db081fd1cd39ab9e7c4e82f6118cb3f98feab60d11f`. Prior402local/33upstream
omittedpatchfields,7inlinegaps,3historicalconversationdiscrepancies and checkout2454
unexplainedbacklink preserved. No unrelated decision/conflict or fabricated lostbytes.

All45outerreceipts: applicableownedwrapperstop0, unchangedsource, errors[] and
ownedSurvivors[]. Four outputcleanupreceipts errors[]; precise disposableproducts
removed after retaineddependent evidence. Source/sharedcaches/requiredlogs retained.
FreshglobalActionsidle04:25:22–28 precedes lease release04:27:47.671895UTC, zero
sourcefreezeviolations; releaseSHA256`270cd9a6e158e3448920129f5743a48da3a316149276c3b838ef9bf6483638a4`.
This is administrative release, not a futurelease. R10UNKNOWN/null-null-125/62omissions/
PARTIAL_SALVAGE/fullremoteCleanupNOT_PROVEN and allpriorfailures stay unchanged.

Continue [currentqueue](../issues.md)/[follow-ups](../followups.md), sequential fixes
and fresh independentfinalreviews, then affectednative replay under lease/freeze.
Currentwhole-source/check/samples/consumers/Intel/fullWindows/ABI/Swift/release and
physical/hostile/independent133/professionalcrypto/ownerdecisions remain. Sixadminfiles
retain scopedcurrent-delta/readhistorical limitations; report composes unchangedprior
fullread with completeauthorread ofthisdelta. No cycliccoveragehash/selfapproval.
This preparation used private data/GET-onlyrefresh/read-onlygit; no projectbuild/test,
repositoryedits/imports/APIwrites/processcontrol or subagents. Root owns application,
currentcommit/publication reconciliation and finaladministrativeacceptance.

## Post-R11 sequential repairs and fixture follow-up

**Current repair head,10September2026, `f0b5789f665b585d8f4d6508bdfbbb42a4f1f8a5`, tree `e6b39e865ea257669c3bf2d2d1a2cc17b6498a00`; locally committed/not pushed.**
173/215 independently approved repository repairs (80.5%); 174/215 independently resolved rows (80.9%) including #287 without a repair; 41 unresolved (19.1%): 17 repair/native rows, 21 external-validation rows and 3 owner decisions (#120/#274/#284). 82 new audit findings. Whole audit **NOT_READY**;133independent **NOT_STARTED**.
The preceding65f3-bound R11 section is the earlier snapshot, not current399/400/401 disposition.

| Issue | Exact final repair | Independent verdict | Focused evidence |
| --- | --- | --- | --- |
| [399](https://github.com/p2pKit/P2pKit/issues/399) | `243d0a241adf65e3eaee1b2e3232306ea5dac222`; diffSHA`5d4acb55f31d095123df95ede2e6fb7d31fdb6cbf5d9776e45a681325a0efc1c` | APPROVE_FINAL_REPAIR/no findings; reviewSHA`5d3c316da2ce2b7e159c15a5a8a608e48bc349da1a11f274b28714f88b8c02b6` | Original production1test/1intended baseline0vs1 failure; exact same regression then23PASS across watchdog/path/retry classes. |
| [400](https://github.com/p2pKit/P2pKit/issues/400) | `810d8c9a0e04e6cf98d98b9578bca720fd28d733`; diffSHA`3d9002f10a227875f711bec03d9e9a4802034c16f053a04659eeaa10f283c645` | APPROVE_FINAL_REPAIR/no findings; reviewSHA`4b8ea99a49197845ae84dbd493bcb9e78f1eb75d888514de4763644e76672748` | Existing six-method path classPASS; no claimed fresh cause-specific red. |
| [401](https://github.com/p2pKit/P2pKit/issues/401) | `f0b5789f665b585d8f4d6508bdfbbb42a4f1f8a5`; diffSHA`034ae6ad10335ad0e40ea9667ccd67a849bf6bcd7623da2bb207e18829cdf89f` | APPROVE_FINAL_REPAIR/no findings; reviewSHA`3036ae09a6e4ffa6a73a7153c00f2eebf307b865e1d777debbf0bae77afeec9c` | Actualfixture red1method/twofailedsubcases; final4PASS0.676s, including2realLinuxresistant-worker controls. |

399snapshots path-wake generation before state publication; lazy-watchdog/terminal
fences remain.400uses consumed Unsatisfied as sole initial loss trigger, preserving
second-dial2, Connected rearm and shorter-than-retry bounds while removing obsolete
wire-warning allowance. Native/common-test replay remains; R11 cannot distinguish
which schedule caused its historical failure. No authenticated-v2/physical/independent
or release qualification follows from these Linux/JVM in-memory fixtures.

Red05:23:20–05:24:39UTC had1/0/1; green05:26:13–05:26:59 had0/0/0;400run05:44:37–
05:45:51 had0/0/0. Allsourceunchanged/noownedSurvivors.399deferred generated outputs
were disposed after400dependent verification:26,405,623bytes, evidence/caches/source
retained. Exact receipts and verdicts are in `nativeFollowups.postR11SequentialFollowups`.

[401](https://github.com/p2pKit/P2pKit/issues/401) actually filed05:52:20Z: fixture
finalizer exception coupling skips remaining retirements after group-signal or
leader-wait failure. Final401nestedfinally correction attempts all four retirements
with unchanged deadlines/ownership and visible/chained errors; no swallowing EPERM.
Red05:54:19–20UTC was1/0/1; green05:56:36–38 was0/0/0, unchangedsource/no survivors/
nooutputs. Counts are Pythoncommand.log methods, not empty GradleXML counters.
Keep the unknown native group-EPERM cause under157 separate:401is not its fix.
Full filing/request/response equality checked; requestSHA`07186f572b748bb20c653f7a3da9dcc45469983eb21fbc2f6f1fe05552864f1e`,
responseSHA`c46dae2000849d72dd33312dff739a4c7d6b972cdae4f05273861e7b0f5d2a94`. Root05:48:17–19fourGETs found only399/400
filings/no comments and returned157body/fourcomments unchanged. No fresh215census:
initial208membership+sevenfilings. Earlier history/visibility/failed-run limits stand.

Coverage composes three399/400semantic deltas with prior reads; watchdog is
conservatively semantic-delta, not a claimed full-file reread.401reviewer explicitly
read its complete changed testfile, retaining FULL_TEXT. Sixadminsiblings stay
scoped/reopened; selfrowunbound. R12plannedonly; future workflow/admin integration
needs separate binding. No whole-repository/native/physical/external/release credit.


## Apple R12 terminal failure and discovery follow-up

R12 published `6d11f7336da3892e302efab0c35ef9d2d83494dc` / tree`2b1fc516425fe81cdee0dc01eca9ef3e26b6c112`; normal push/ref
verification06:38:57–06:39:05UTC. Actual outcome comments created06:41:14–17UTC:
[399](https://github.com/p2pKit/P2pKit/issues/399#issuecomment-5614299643),
[400](https://github.com/p2pKit/P2pKit/issues/400#issuecomment-5614299993),
[401](https://github.com/p2pKit/P2pKit/issues/401#issuecomment-5614300222).
Captured response bodies equal authored bytes; earlier final repair approvals stand.

[Run34446158462/1](https://github.com/p2pKit/P2pKit/actions/runs/34446158462), job102771292014,
completed **failure**06:45:17UTC, macOS26.6.2 ARM64/Python3.14.7. Independent verdict
**ACCEPT_FAILED_RUN_DISPOSITION_ONLY**, SHA
`69b0267ac117cb46dff51e2ae939d34328abf5c598e34a42efb5bb777c9bfebc`.
85executor-native controlsPASS89.946s/0/0/0; platform preparation/XcodeGen installation
also0/0/0. First real lock-policy caller reached the intended --write-locks rejection,
not #395's former parser error; ownership failure still makes policy3FAIL.

Nested935acecce457431999f0ebaf94a61833 and enclosing7eaa078ba44c4b68b0314105cc6c6343
both1/0/125: new same-UID PID5470 environmenterrno5 unresolved after10/8attempts,
first/last same live identity. No later positive outcome proves ownership, kernel
cause or eventual state. Not a #157 group-EPERM, zombie/absence or audit-owned claim.
Five actual stops0 and source snapshots unchanged do not establish complete discovery,
remote zero survivors or disposal. Safe-only finalizer refused cleanup.

**PARTIAL_SALVAGE/safe=false/fullTreeCompleteness/remoteCleanupNOT_PROVEN** retained:
62untruncated omissions31yml/30jsonl/1properties. Artifact10139883092,953728bytes,
ZIP SHA`7a50f9c28002f653c76e2ca1b146eb297a6d9e0234bc5e7ed772205a598f0203`;
981bootstrap/976salvage entries independently rehashed, no mismatch; extracted982files/
2757759bytes. Transferred integrity is not remote completeness. Driver selected no
simulator; no VM-wide process assertion. Policies13/18/27/30/33/34, ARMcore/LAN,
consumers/all15publication inspections and all Swift/probe scopes **NOT_REACHED**.

Local lease released07:02:02.507936UTC, zero freezeviolations, following07:01:20–27
fresh idle observation and authoritative terminal retention/review. ReleaseSHA
`87a92cfc0d374efa26fb0bdc6a2bff2fc5776b8de0b9ab3a302afaf7591e79da`; idleSHA
`0f8ba00a699162517b6407304ab74ad8aca79cc8490a972914b209ac361fa870`.
Administrative scheduling only, not safe handoff, VM destruction or standing lease.

### Subsequent390 source prerequisite, not native approval

Commit`0822edebff523ef5299fd8943ca572b8ec3a7ccf`, tree`a6066351079a3fda635e45d9fec99883cf55f8a6`,
two-file diffSHA`de86ca9952f6113fc4b47e0e939c38f3fa337ce1fabcacce785d825de9c215ac`.
Independent **APPROVE_FINAL_SOURCE_NATIVE_PENDING/no findings**, reviewSHA
`00c03749e24c80b1ae54c8f94f2638fa107b6c0a9658018a6a383a0cc66513f5`.
Already-owned390cause: an exhausted environment observation stayed permanently in
current discoveryErrors after later positive reconciliation. New pending records bind
full lifetime identity; later positive environment/terminal/replacement evidence may
remove only that matching exhausted error, never EIO/permission/time alone. Persistent/
structural failures and token/domain checks stay fatal; original failure events remain.
No new distinct filing or repair numerator. Native Darwin qualification remains pending.

Original production red2methods/fivefailedsubcases1/0/1; exact final22PASS4.455s,
19modeled Darwin plus3realLinux executor controls,0/0/0/sourceunchanged/noownedworkers/
nooutputs. Real fixture timeout/cancel leaves intentionally-15/0/125, not product passes;
all three fixture teardowns complete. ReceiptSHA
`de2fe36ee796880237f08221ca5986877f1fcafb246293fa34d0a92352d04911`.
R12ownership/kernelcause/eventualstate remainUNKNOWN; failed salvage not repaired.

Latest local`91e8a9a287333be52ca114022b0cd6c4a9664e23`/tree`f24ef0a0bdd4faa3b22a2b2d90231ccf04f1a250` adds only root-reviewed
workflow comment12→13, ARMfollowup selection unchanged. R13planned/notpushed at this
binding; private Intel candidate is not applied. Bind later publication/execution.
Fresh06:36census215open/322issues/79PRs/401bodies,551visiblecomments via retained/delta
chain; no whole-history recrawl. Coverage projects1150paths at6d11 (659fulltext/
224semanticdelta/259structural/6qualifiedadmin/1semanticinventory/1unboundself), not
new0822/91e8coverage or whole correctness. Structural233historicalXML+17binary+
8lockfiles+1wrapper and opaque dependency-inventory limits remain.173repair/174resolved
of215,17native+21external+3decisions unchanged;133NOT_STARTED/auditNOT_READY.
Current wholecheck/samples/consumers/nativeIntel/fullWindows/ABI/Swift/release and
physical/hostile/independent/crypto remain. Earlier report prefix/failures retained.


## Apple R13 results and post-R13 repairs

179/218 independently approved repository repairs (82.1%); 180/218 independently resolved rows (82.6%) including #287 without a repair; 38 unresolved (17.4%): 14 repair/native rows, 21 external-validation rows and 3 owner decisions (#120/#274/#284). 85 new audit findings.
**Whole audit NOT_READY; #133 independent NOT_STARTED.** Current source `3995f4fbe276b14680b860fc7ade71d419601470`,
tree `71fde927476dfb4e8eb8a58a70ebc9e95b4c15cc`; locally committed/not pushed at this binding.

### Retained R13 boundary

Run34450916806/1, job102786220217 executed `ae37c18f21f6e35ff128abe98d6b7975fbf547d2`,
tree `d26ec08568fcd2c1fdf59dd0d4c555e72e4eca1f`. Artifact10142124367 (1493025bytes), SHA256
`3dd85f26720d61eea2e3d9aa3aa498dfa38d5d605689b90471f6e9b89eb75034`.
Whole **FAIL/PARTIAL_SALVAGE,365omissions/details truncated,safe=false**, full remote
cleanup/tree **NOT_PROVEN**. Local lease release08:13:44.184491UTC is scheduling only.
No scoped pass or later repair retroactively proves remote cleanup.

- Complete executor suite90/90PASS on Darwin (85.826s tests;94.604s leaf), not90native
  product cases. #390 retained independent verdict: **APPROVE_FINAL_FOLLOWUP**, review SHA256
`0dfd05f1e94be8fdbf1d7f53c544e31d123c3dd20369c542d6a0c5c2b4525c7d`. The new retained verdict covers the observer/native
  callers, not a missing historical report or a second repair. The exact natural race was
  NOT observed; deterministic transitions and actual native controls support this scope.
  Six raw call streams and one fixture properties member remain omitted; no sealed
  fixture archive claim. R12 ownership/kernel cause/eventual state remain UNKNOWN.
- #396 XcodeGen5PASS/17.094s, #397 Darwinsh27PASS/39.851s, #398 Python3.14.7
  51PASS/7.305s: **APPROVE_FINAL_REPAIR**, no findings. Native #397 locale UNKNOWN;
  earlier successful unchanged Linux locale controls are reused, not fresh. Review SHA256
  `ac8e5b849176d1eab764fe4ac1344298726a83cb4ef72de65a03a9371194d5b5`.
- Core774/775PASS,1FAIL,0errors/skips,84XML; LAN0cases/NOT_COMPLETED. #207scoped15readiness
  and4helper cases accepted, whole row pending. #399ordering6/6PASS/no second credit;
  #400native integration fails10.965s timeout, wait phase/causeUNKNOWN. Review SHA256
  `77d80d4390c9055091536b1127a1bdb832989f06fdc79511d6c4c9bf81944280`.
- Actual publication208tasksPASS/5m6s/0-0-0, then tooling-sidecar rejection#402:
  outer125-0-125; consumers/all15 inspections/XCFramework/Swift NOT_REACHED.
  Whole policy27FAIL is retained, regardless of future two-method #157 acceptance.

### Sequential approved corrections

| Issue | Exact commit | Final verdict and sufficient scoped evidence |
| --- | --- | --- |
| #402 | `fe1b2e13edc4abc6103e95842269c48fdb7d7490` | APPROVE_FINAL_REPAIR; one red method, seven green methods/64.584s. Exactly three separately hashed optional tooling sidecars;15publications/75trusted artifacts unchanged. Actual consumers still pending. |
| #157 follow-up | `a4b44651d85d712b9ba52eed7da6dc1c714d7136` | APPROVE (final source; native pending); two red methods, seven green controls/0.760s. Zero-signal PermissionError waits only within original deadlines for ESRCH; signal denial/other errors remain fatal. No extra repair count. |
| #403 | `4d6813f06d7c9bab91fd16e8696249378c8a68b2` | APPROVE_FINAL_REPAIR by source review; Rejected reads winner state, Replaced still loser. Existing store tests inspected, not rerun; no admission/privacy/lifecycle/protocol change. |
| #404 | `9f53043c7af7825d4d44e52c2ee7a814d5d311fb` | APPROVE_FINAL_REPAIR after corrections; fresh41/41PASS,5XML,0failures/errors/skips,1m27s. Bounded installed-transport retirement before dial preserves buffered secure authentication/CLOSE, epoch/identity and duplicate rejection. |

Final review SHA256: #402 `6fdc42401dc905c8ebdd03c88d156df299aab3cf16f9c5e431eb08733b8608fc`;
#157 `f988cac97d20c7130d2b90459ec900c6f0e7b75bb5cf3a23fd20754ddf5775ba`;
#403 `770c90a7e76d5e6a6122492351c1426a8684fc4f242dfa871b20c787aaa78201`;
#404 `5c2ec6ecca069081237fc955f0a673f3f8d324c5a4f3c97ffce39b936112fa6d`. Exact patches/receipts are in
`checkpoint.json` → `nativeFollowups.postR13Repairs`; private raw payloads are not committed.

#404 characterization's bad-behavior assertions are not acceptance. First acceptance
72/73PASS/1FAIL and initial review blockers remain historical. Final41 tests cover
NetworkPathRecovery7, SecureSessionLifecycle6, SessionFlow11, SessionReconnectFailure9,
SecureV2Transport8. Final receiptSHA256
`37578a57fa1757b974cae3015c8eb47a99d86972637f81f9a234054936da6362`.
Local close does **not** acknowledge remote store retirement; no R13 timeout-cause claim.
Final executed focused validations had invocation/isolated stop/final exits0/0/0; no owned
survivors. #403 required no new execution. After evidence
retention, only archived root/buildSrc/core outputs (26857523bytes) were removed;
shared caches, source, protected `buildSrc/src/main/java/dev/p2pkit/build` and evidence kept.

### Next scope and provenance

R14 operational commit `3995f4fbe276b14680b860fc7ade71d419601470` is **APPROVE_FINAL_REVISION**, not repair credit;
reviewSHA256 `b278e31b9daf244e3b6c30052ba4b925a9764534089cb86f314c4ce94e087d9c`. Three existing focused route/workflow controlsPASS,
0/0/0/no survivors. Keep full executor admission, replacing broad policy replays with
only existing #157 methods `test_term_resistant_worker_is_killed_after_leader_exits_on_term`
and `test_surviving_group_is_drained_even_when_leader_already_exited`. No `--suite`
selector or fabricated historical PASS rows. Core/LAN ARM, real consumers/all15 artifact
inspections, CLI once, XCFramework/headers/provenance, Swift warnings/unit/UI/live Swift-JVM
and isolated cancellation probe remain. SDK36+37.0/Xcode26.5/nativeARM source binding,
strict ownership/finalization and isolated cleanup are unchanged. R14 not pushed/run here.

Latest GitHub observation09:52:06.876398–09:56:51.920670UTC:325issues/218open/107closed,
79PRs/7open,404fresh full bodies;554unchanged comments (379on open issues) explicitly reused.
No changed existing requirements/closed decisions/PR metadata; only402–404added.
Observation reportSHA256 `edaff961a30321946db0c0fcfb0efccbc964c758b3eb9bfd05c0cce7cefe18eb`. Preserve402local/33upstream omitted
patches,7inline gaps,3historical counters and checkout2454 backlink uncertainty. One capture
was corrected after181 redundant reads; exact-owned cancellation and corrected continuation
are retained, not hidden. No issue closure/API mutation by the refresh.

Coverage composes current3995 source/review deltas, one entirely added #404 file, unchanged
prior reads and scoped new administrative text;1,151paths, all5,750 inherited historical
cells preserved,259structural rows/six qualified administrative histories/self-row unbound.
It is not whole-repository semantic correctness, a new full historical read, or platform
execution. Latest successful root check remains `final-linux-check-20260909-r3`, at0dbc+exactdiff
(later identical655203),1780freshPASS/228XML; it is not current3995 or strict LAN Dokka.
Continue pending14platform rows, Intel/fullWindows/strict supportedMacDokka/ABI, final
current root check/applicable samples/consumers and inspected release gates. Only genuine
physical/hostile-network/ART/independent133/professionalcrypto and owner120/274/284 decisions
remain external; ordinary available gates are not excused. No release/main/tag/closure authority.


## R14 prepublication Linux gates and existing #207 follow-up

Counts unchanged: **179/218 repairs (82.1%),180/218 resolved (82.6%),38 unresolved
(17.4%)**. Source `47d568c3b02e93c0e2f142f50c5cb5c76a264fd2`, tree `b07bb80006ef75c675edcc380299a96d08c9284d`;
R14 still **NOT_PUSHED/NOT_RUN**, whole auditNOT_READY, #133independentNOT_STARTED.

- Original current Linux check/sample attempt at clean3995 **FAIL:926/927PASS,1FAIL**,
  111XML,1/0/1. Positive `HandshakeIdentityTest` tore down Bob before his independent
  incoming lifecycle commit; the strict diagnostic net caught it. This is an existing
  missed #207 readiness adopter, not a new defect/count or weakened production identity
  check. R1receiptSHA256 `d8396d2761c64a97940bdeed7ecab59a0e92c871b83c331a353fc65331a0faf4`.
- Final one-file responder-publication barrier keeps original connect deadlines,
  local/remote identity assertions and strict post-stop diagnostics. Independent
  **APPROVE_FINAL_REPAIR (host/source follow-up only)**; reviewSHA256 `2f87fb9fd88876d7b2eb90af2d184f65ea0d9186f9b7e99a78628a4458b47caa`.
  Actual changed JVM suite3/3PASS includes both anti-spoof rejection cases. Apple/common
  native acceptance for whole#207 remains pending; no second repair credit.
- Actual `./gradlew check :p2p-sample-android:assembleDebug
  :p2p-sample-desktop-ui:createDistributable --console=plain` with strict dependency
  verification, no parallel/build/configuration caches and max2workers **PASS**:
  **1786fresh cases/228XML/12testtasks**,211executed+17up-to-date,8m28s. Actual source
  was3995+diff `b097b2c1417d0159438c014a2c9ee03767d2804756d81abd6784ac581e682a0b`, later identically committed47d;
  **not clean47d execution**. Invocation10:32:24.353131–10:40:54.132954UTC,0/0/0,
  source unchanged/no owned survivors. LauncherJAVA_HOME17/recorded Gradle9.7 daemon21;
  no all-test-JVM17 or ART/device attestation. R2receiptSHA256
  `a13a26290f77c08563dc8f1c7ff2032f96c6adb42099ee32968b2df3692e074f`.
- Separate clean3995 Linux/JVM CLI runtime **APPROVE_SCOPED_RUNTIME_OBSERVATIONS**,
  reviewSHA256 `9b3a202339d76e8d34befb4c96d9c4aec6c0361ebbedb647983db09082e15d72`: real49MiB source, receiver stopped at
  filesystem-visible65536-byte partial, catchable TERM/CONT then143exit without KILL,
  empty exit inventory; same-home **new-identity/new-session4096byte** transfer has
  matching hash/durable commit/ack. No explicit receiver-negative diagnostic is invented;
  diagnostic session remains intentional CANCELLATION, not whole-testSUCCESS. Outgoing
  current fingerprint pins use development incoming authorization, **not mutual incoming
  PinnedOnly**. No same-key reconnect/resume, partial-byte fsync durability, completed-file
  preservation, SIGKILL/powerloss, full PS-T05/PS-T06, native/physical/hostile/#133/crypto
  or release acceptance. All7exports/direct/persisted streams reconciled.

After independent inspection, root removed11exact generated output roots
**1,282,374,300bytes** at10:44:37.793899UTC;228XML/reports/logs/diffs/failure history retained.
Cleanup receiptSHA256 `0fd7dff720668755a067a93c58ab673c96e40615eeda83e138e376e7ee03e461`.
Earlier10:43CLI cleanup removed51,485,435bytes, retaining16evidence files including
**all7ZIPs** and direct streams; cleanupSHA256
`1ef2ffe6e19d3f979c97d987fd3e911a729779073d232ca7a21b76e85b9cd7fe`.
Isolated stops/drain already complete; no cleanup signals, source/shared-cache/unrelated
job deletion. Protected `buildSrc/src/main/java/dev/p2pkit/build` remains source.

Current coverage advances only `HandshakeIdentityTest.kt` beyond the private3995projection;
1,151paths and prior read categories/historical cells unchanged. Root/sample confidence
is current to47d-equivalent bytes; do not rerun unchanged expensive gates merely for
reassurance. Continue source-bound R14 ARM, then remaining Intel/fullWindows,
strict supported-MacDokka/ABI, actual consumers and inspected release gates. Earlier
R13FAIL/PARTIAL_SALVAGE365/fullremoteCleanupNOT_PROVEN and all external/owner obligations
remain. Later affected source/environment changes require only their appropriate scope.


## Apple R14 results and R15 residual continuation

**179/218 independently approved repository repairs (82.1%); 180/218 independently resolved rows (82.6%) including #287 without a repair; 38 unresolved (17.4%): 14 repair/native rows, 21 external-validation rows and 3 owner decisions (#120/#274/#284). 85 new audit findings. Whole audit NOT_READY; #133 independent NOT_STARTED.**
Current source `5bf2e7bb9d3fbf914d7e1ab17318a644e86c3b53`, tree `eb49c744a564963e5cd58ff0b2cfbf2031d67136`: four focused commits local/not pushed at
this binding. R15native NOT_RUN. Earlier source/failure narratives above remain dated history.

### Actual R14 and scoped independent verdicts

Run[34469526553/1](https://github.com/p2pKit/P2pKit/actions/runs/34469526553),
job102845906065, exact3b06/tree9f5c98ee; artifact10149303925 SHA256
`2903ca26c34f3b4d1691d4309bd424a6ffc3150058c1996137ea808b2381382a`.
**Aggregate FAIL/PARTIAL_SALVAGE,367omissions/truncated details,safe=false;
full remote cleanup/tree NOT_PROVEN.** All1122retained ZIP member hashes reconcile;
this does not supply missing original contents. Original manifest1481members,
1114available originals plus its manifest retained;1115driver files/3998659bytes.

| Scope | Actual evidence / verdict |
| --- | --- |
| Full executor admission |90/90PASS,93.090s;33pure/19modeledDarwin/38real-host fixtures, not product tests. |
| #157 group probes |2/2nativePASS,1.114s;both observed transient zero-probeEPERM then positiveESRCH. **APPROVE_FINAL_FOLLOWUP_NATIVE_EXECUTED**, no secondcredit. |
| Core/#207/#404 |780freshPASS/84XML/0failures/errors/skips. **APPROVE_CORE_NATIVE_SCOPE**;#20724classes/291declared methods and#40441methods overlap. Whole207pendingLAN. |
| LAN |0cases/NOT_COMPLETED;compileTestKotlinIosSimulatorArm64 fails three unusedUnit expressions at64/79/88 under unchanged-Werror. Combined platform1/0/1; helper/main compilation is not test/runtime acceptance. |
| Publication |208executed tasksPASS/3m22s/0-0-0. |
| Isolated consumers |125/0/125: exact policy rejected real native metadata JAR; six metadata JARs+three LANcinteropKLIBs missing from policy. Actual consumers/all15archive inspections not reached. |
| Swift seven pending rows |**NO_NATIVE_APPROVAL/NOT_RUN**:191/291/322/330/341/363/383;framework/headers/strictSwift/unit/UI/livepeer and separate cancellation probe not reached. |

Seven top-level leaf stops0/recorded owned-survivors empty and earlier six-root cleanup
are scoped observations. Consumer cleanupComplete=false and later publication outputs
prevent whole cleanup approval. The11:32:38.870316UTC lease release is **scheduling only**,
following11:31:26–11:31:33idle/ref observation. R12PID5470 and R13timeout causes/unknowns
remain unchanged; no after-the-fact aggregate pass.

Independent report SHA256: core `033d10dc95c24c104af0970d25d8ad3947a519d40b7c6387aecd85e077bfb890`;
LAN/publication `419570ca4eafe51eb332d6b31f13db6f1ab729b4fa6248de66b30819bb85d833`;
Swift `2a787a9d0bbbe8b607554fcb1bea281b67e303453168bcf3d63094b3d6440be1`;
#157 `8a44ede065e4111d2e3bd1ce57a767a9fb6949a90cd3ae4572a5e950a69949ed`;
terminal `fbb62ac8b33dd2e0f00ad0dc86b4d053771956f6a25ace04cce0fb1debe4660a`.
Full safe bindings: `checkpoint.json` → `nativeFollowups.r14Continuation`.

### Sequential reviewed corrections, no new row count

| Commit | Correction | Final evidence boundary |
| --- | --- | --- |
|`526397908b725b994d36b27602e9617b8de7e60d` #209|Remove only three redundant native-void Unit tails; completions/FIN/EOF/deadlines/Werror unchanged.|**APPROVE_SOURCE_ONLY**; actual corrected native compile/link/runtime pending. No redundant new test.|
|`d0f37f6d84f5de7e8039ea614d860d63cbbac7a2` #402|Exact six metadataJAR+three LANinteropKLIB inputs:15coordinates/84trusted artifacts; three ancillary tooling sidecars remain separately bound.|**APPROVE_FINAL_REPAIR**, source/helper;8focused methodsPASS/81.498s. Actual nativeconsumer pending; sameissue/zero secondcredit.|
|`44ab597714fa5959c2843486f39abe7ecfef0375` #236|Require/read54archives:45canonical-license-covered+9explicitKLIB exemptions across15coordinates. No rewrite of KLIB/native binaries.|**APPROVE_SOURCE_ONLY**;11ZIPfixtures plus Bashsyntax/whitespacePASS. Actual45license+9exemption/native inspection pending; no absent-license allegation.|
|`5bf2e7bb9d3fbf914d7e1ab17318a644e86c3b53` R15|Exactios-lan-arm64 profile in apple-followup; reuse780core and157two-method native acceptance. Full executor admission and downstream consumer/framework/Swift path unchanged.|**APPROVE_SOURCE_ONLY**;4focused controlsPASS. Six applied postimages match reviewed candidate; nativeNOT_RUN.|

Source review SHA256:209 `0d539012c6d07126ebd2aeb8e0ad97af8bbe9840d097c9e7467dcbd4aeb9fab8`;
402 `3b575b5b3c6d5078dd6f2342b4da28780c2747bee57a429205c4e72b9916feea`;
236 `be45c17a08b7689ded18db1edee037f2d557075425e23aff9a19efeb596d6c01`;
R15 `215435d0ccc4926e95499cddc1862436ef5a40939f6c6876eeffcdb54fed7fa8`.
Three focused run receipts all0/0/0,source unchanged,owned survivors empty,no disposable
outputs:402 `d83ea8ab5c07f2f8731f3a72f7e53762f370636ea4dbb2dc3a9e3a1b706cab89`;
236 `e4903630da43811d9e7ff57697d88c47f9099d6a9fb052fc19bda9cb84f382a0`;
R15 `c5de39a7cabf8f82711dadd2d2965b7ba66134b725565f70f80456865feeef04`.
These executed priorcommits+exactdiffs, not clean5bf2native/product tests. R15root
application binding SHA256 `7bd2e46dfe6146bbf206804f5ac81701bc79e3b7297f835631c7ab8c54e11288`
reconciles the reviewed candidate with actualpatch `c64067184fcaaff8116599048970f8b14b68d79e6edfa62a164a1e3a63c266f8`.

### Reused gates, current inventory and next step

Linux rootcheck+Androiddebug+Desktopdistributable1786freshPASS remains precisely at
3995+reviewed207diff(later identical47d), not clean5bf2execution. Prior clean3995CLI
SIGTERM partial-abort/new-identity4096byte recovery and its exclusions remain unchanged.

### Actual Linux CLI abrupt exit and same-home restart

Clean `5bf2e7bb9d3fbf914d7e1ab17318a644e86c3b53` / tree
`eb49c744a564963e5cd58ff0b2cfbf2031d67136`: focused `:p2p-sample-desktop:installDist`
PASS (17 executed tasks / 1m3s / no test-method credit), then a 22.130810-second
actual Linux/JVM observation. **APPROVE_SCOPED_RUNTIME_OBSERVATIONS**, no actionable
findings; review SHA256 `1564cf7ff4b7c362918ab1c4374bdd277444541821855a067863fd0ca3458d8e`.

A prior 4 KiB committed file survived. A 49 MiB offer produced a positively observed
131,072-byte partial before owned STOP then SIGKILL (receiver exit -9); the old
sender failed. Same-home B2 had a new identity/current outgoing pin and completed
a distinct hash-verified 4 KiB transfer. Stale part cleanup occurs on first ACCEPT,
not startup. The original empty reservation remains, **not a committed file**.
Incoming policy remained development same-AppId, not mutual PinnedOnly; startup
was not advertisement-free. A/B/B2 exits were 0/-9/0, all reaped. No invented old
receiver terminal, interruption resume, stable identity or power-loss guarantee.

All seven ZIPs, direct streams/transcripts and two unfiltered raw home journals
are retained; shared B history includes B then B2 with no incomplete tail/rotation.
Manifest SHA256 `9fae7c6ec42cc90b49ff9fcb8a15deaca548a07a0c4fa4ff2a45289d18de513d`.
Observation receipt `08df1f70fd31d716fb038d3fcdb2e203261507c6ab6e0756db19ba64bd0171b6`; producer/runtime receipts
`a0c1bbd0cbfd47d0ae8cd1dc09fbcbd2015cc9d79b3883fb6f1db34330be76ab` /
`3b73d77cd3beaad9e266dc2cef02eb8d2b8dd58a2d5bc50b71de15942a39e7ad`.

After independent inspection release, exact cleanup completed at 12:18:34.924505
UTC: 8 synthetic paths / 51,495,787 bytes and 8 generated roots / 32,842,527 bytes
removed; 19 required evidence files (including the seven ZIPs) byte-preserved.
Build/runtime/cleanup envelopes each 0/0/0, unchanged source and no owned survivors.
Cleanup receipt `dca060fde583864d9bf5d2fd9789fb8bbcb7fda48d25980834d01b0e89ceac8a`;
removal manifest `ddd563b747d7be9d51a3697222438df6aae04f035a1e947c55cbbe7fc0d7c31b`.
Source/shared caches/unrelated tasks untouched. No full PS-T05/D2/D5, headful
PS-T06, physical/hostile/independent #133/crypto/release credit or row promotion.

### Current census and remaining supported-host work

12:15:42.039644–12:15:49.669649 UTC refresh: 325 issues / 218 open / 107 closed,
79 PRs / 7 open, 404 fresh full bodies. No issue, comment, inline, membership or
substantive PR change. All 79 raw head/base PR deltas are solely nested repository
size statistics, 9629→9863; full deep reconciliation found no source refs/SHAs,
body/state/decision/label/reviewer change. The six known earlier outcome comments
remain in the separate 11:44 observation. Unchanged complete visible comments and
linked histories explicitly reused; prior missing-patch/upstream visibility gaps
persist. Summary SHA256 `d418eb34d818ff3911bbd5dc363d35bb679422968aab205949b2ad85783258a1`; PR reconciliation SHA256
`f5d9e9a8417e291bb8e51edfb52b237dd66ae17017af3215753cd17b442c205b`. Not an atomic
census, human full-history reread or future lease.

Coverage projects1151tracked paths at5bf2 with13exact independently reviewed source
deltas. All5750original and5755current-preimage first-five cells preserved(nonadditive);
earlier readcells remain in immutable3b06coverage Git blob`71908d3d4f5f06258f773ef28ecb1f1375899513`.
Current administration is author-only delta with qualified histories/self-row, not a
fresh whole-file/corpus correctness claim. No protected instruction changes.

Before push: fresh Actions/refs, one source-freeze/owned execution lease. R15must run
repaired LAN, actual15publication inspections/isolated consumers, CLI once, framework/
provenance/headers and strictSwift/unit/UI/livepeer plus separate cancellation probe.
No repeat unchanged core/#157 cycle. Reconcile prepared Intel16/fullWindows17; Android
ART extension remains pending. Reuse unaffected strictMacDokka/SBOM/OSV/dependency
components; hosted replay is **not** literal monolithic release-scriptPASS. Keep only
real physical/OEM/AWDL/hostile/headful/independent/crypto and owner120/274/284 blockers;
unexecuted feasible process cells are not automatically hardware-blocked. Max2workers,
no parallel/overlapping builds; retained logs, isolated stops, exact-owned cleanup and
removal only after dependent inspection. No main/tag/settings/closure/release authority.

## Apple R15 scoped acceptance and follow-up repairs

Current implementation `047ee2bd6d68e7d957b84b9f972c418376398690` / tree
`deae51eb77f2e9f28b323f3d63f83bd9eeec8571`; three approved405/406/402 commits after
pushed4a409a8 are local/notpushed at this binding. Separate dirty wire documents
and the private IntelR16 packet are excluded; R16 is unapplied/unexecuted.

**194/220 independently approved repairs (88.2%);195 resolved (88.6%);25 unresolved
(11.4%)** =236 +21external rows +owner120/274/284. Repair complement26includes
no-repair287. 133pre-existing+87new findings. Counts are rows, not effort/readiness.
**Whole audit NOT_READY; #133 independent NOT_STARTED.**

### Actual R15: aggregate failure, scoped final approvals

Run34476944789/1, job102869909133, artifact10153389356; clean
`4a409a8f60ad4b4f23db58725f71de0523a29bf5` / tree
`f45afc779049d6557485efe77936871dfeeb70a9`, macOS26.6.2ARM/Xcode26.5(17F42)/SDK26.5.
Artifact145788531bytes, SHA256
`c57b2797311fd12591803153bd21039ef6d2a00444a1d3d32ae51d121ffa70cc`.

| Scope | Actual result / independent verdict |
| --- | --- |
| LAN156/158/207/209/275/279 | **APPROVE_FINAL_REPAIR_SCOPED_REPOSITORY**;184PASS,0failures/errors,1unchanged manual skip/29XML/18tasks;0/0/0. #20713LAN methods complete reused R14core291within780 and prior Linux/Windows acceptance; subsets overlap. No measured Nagle/physicalAWDL/17realhandshakes/universal syscall interruption claim. |
| Swift191/291/322/330/341/363/383 | **APPROVE repository-repair/native scope**;73unit+6UI=79uniquePASS; generated headers/framework/provenance and strictSwift pass. #291physical backup-set absence remains unperformed;341notOSclipboard/successfuldial;383notTask.cancel-to-Flow proof. |
| Publication/402 |208tasksPASS;15coordinates/84physicalinputs actually admitted. **ACCEPT_REAL_NATIVE_PUBLICATION_ADMISSION**, no second402credit. Consumers fail before tasks at Portal/Central marker checksum mismatch; finalhelperverify not reached. |
| 236 |**NATIVE_ARTIFACT_ACCEPTANCE_NOT_EXECUTED**.54archives=45license-covered+9explicitKLIB exemptions absent from retained artifact; hashes/POMs are not embedded-license proof. |
| Swift/JVM transfer |Two actual204800-byte endpoint/hash transfersPASS; enclosing1/0/1 because CLI did not exit. Export precedes earliest possible adapter rescue by30.442114s: quit-path finalization completed, linger cause unknown/not automatically389. |
| Cancellation probe |64/0/64,failedToStart/no build/zero methods due invalid-test-iterations1. **NOT_RUN**, not a Flow failure. |
| Terminal/owned cleanup |**APPROVE_SCOPED_TERMINAL_HANDOFF**;FULL_SEALED/all4657members verified,21canonical leaves/16outer,all applicable stops0/no survivors. Executor90/90PASS; selected simulator restoredShutdown and owned disposable work/generated outputs removed. |

R15 remains **FAIL**, not full-host/monolithic release acceptance. Earlier
R12/R13/R14 failures, UNKNOWN ownership and partial-salvage limits are unchanged.
Source-suspected responder-readiness race did not reproduce; SwiftUI runtime frame
warnings remain untriaged suspicions, not additional confirmed issue filings.

Independent review SHA256:
LAN `22b8ce1c73dce6f1abaf93c8224a91732cfca7096871b650c7017fd6766e4099`;
Swift `389c9397a830ce347513f808a2755fe741da18b2c109e4ae0f60942deed4bcd8`;
publication `6eb36c89ad039862e6c4ecef19095b4f2b2590a92d841045d863342c3309ea56`;
terminal `4376a7bc43f332f565cad70825370a225120704e6930e5db4a0c26e7ea327a7e`.

### Sequential focused repairs after R15

| Issue / commit | Final approved scope and verification |
| --- | --- |
| [405](https://github.com/p2pKit/P2pKit/issues/405) /`50e48b443cfd3e05c61e92718f112279410f16ee` |FilteredGoogle→Central→Portal matches existing reviewed marker route; no new checksum/trust. Official source bytes corroborate mismatch.2focusedmethodsPASS7.108s,39version negatives,syntax/whitespace;0/0/0. |
| [406](https://github.com/p2pKit/P2pKit/issues/406) /`403ee7000bc60c98c8f81037a3882b3c121ba20a` |Remove invalid-iterations1 only; retain exact one-method probe/provenance/strict warnings/owned retirement.2focusedmethodsPASS0.817s,syntax/whitespace;0/0/0. |
| [402](https://github.com/p2pKit/P2pKit/issues/402) /`047ee2bd6d68e7d957b84b9f972c418376398690` |84physicalinputs+18exactGMMaliases=102records, same-component basename/hash/size and post-build checks.5methodsPASS72.462s;0/0/0. All15realR15GMMs independently corroborate alias policy, not unretained binaries. No second credit. |

All three **APPROVE_FINAL_REPAIR_SCOPED_REPOSITORY**, no actionable findings.
Actual corrected consumers/final-helper verification and native cancellation probe
remain **NOT_RUN**; focused fixtures fake Gradle/Xcode boundaries.402aliases solve
a latent supported non-changing-version gap, not R15's first error; source-local
SNAPSHOT integrity relies on owned pre/post-byte checks, not claimed Gradle XML
verification of changing artifacts. Review SHA256:405
`3e43937541b4cb84395239201606717493fbed8e6f31c25fa4eb2c78da5c4c05`;
406 `07a38fc1e52f158ea9792658655407367af10c531ca101a0c4a19ea30042d045`;
402 `e289b290cd30bc10027b6bd19943616040caa2fb17cd59f60549b8598c261d42`.

### Actual Linux CLI idle same-process/key recovery

Clean4a409a8 producer:installDist17executedtasks/58s, no test-method credit;
actual44.714693-second Linux/JDK17 observation, both envelopes0/0/0/no survivors.
**APPROVE_SCOPED_RUNTIME_OBSERVATIONS**, reviewSHA256
`3a7d9ee966c3619ed8c644496cc91177c67b6d65f502c5a93135d9defc3d2b22`.
Positive owned STOP/CONT held30.055999962s; actual timeout/automatic retry, original
sender owner recovered and incoming owner replaced without manual reconnect.
Both processes/keys unchanged. A new consented hash-correct4096-byte durable
transfer passes, prior4096-byte commit survives, original sender observes clean
peerClosed/no late retry; bothCLIs exit0/reaped. Final catalog outcomes remain
operatorCANCELLATION, not campaignSUCCESS; incoming admission is development
same-AppId, not mutualPinnedOnly. No interrupted-transfer/power-loss/fullPS-T05/
headfulPS-T06/independent133/crypto acceptance or repaired-row increment.

All sixZIPs/directstreams/transcripts and unfiltered raw journals retained.
Post-review14:13:52UTC cleanup removes exact synthetic homes/tmp/fixtures; required
CLI distribution/generated inputs retained for root's next dependent verification.
CleanupSHA256 `e94a3488afef122d4609538ec6779b3b7ffa8c4eae86306df1937c382f243479`;
runtimeenvelope `b642ad4adbf0272109628c8e9dff4cd9e393247ced6455c8cee1c7448d1248ea`.
No unrelated source/shared-cache/process deletion.

### Current census, coverage and remaining work

15:20:35.606590–15:20:43.558178UTC:327issues/220open/107closed,79PRs/7open,
406freshfullbodies; new405/406 and one known402comment delta only; no inline or
substantivePR delta. Complete unchanged visible histories/linkedPRs/closed decisions
explicitly reused, prior gaps preserved; not a full-history reread/atomic lease.
SummarySHA256 `a74a760dd964674237d3eb4b689520bc5b0502d88d55a510a09bc3efc5023207`.
Coverage1151trackedpaths:five exact reviewed source-delta rebindings; all5755current
first-five cells preserved, original5750subset nonadditive. Prior full readrows at
047ee2b coverageGitblob`2eb98eca739a6dfc14e90e8732ceef5d24b5eaed` remain immutable;
current administration is author-only delta, not a fresh full-corpus correctness claim.

Review/reconcile private IntelR16, then Windows and sequential hosted AndroidART;
none executed here. Run corrected consumers/final metadata verification and actual
54archive inspector after successful owned publisher even if consumer build fails.
Run selected cancellation probe/timeout-only CLI thread dump; avoid redoing unchanged
successful ARM suites solely for reassurance. Continue feasible CLI fault cells;
private technical-peer preparation is not independent133 campaign acceptance.
Reuse unaffected Linux1786check/sample and strictMacDokka/SBOM/OSV/dependency
components; finish current-source corroboration, final rootcheck, applicable samples/
consumers and inspected release gates. Monolithic release execution remains separate.
Fresh refs/Actions/owned freeze before push/dispatch, serialized bounded builds,
isolated stops/retained logs/exact-owned cleanup. External291physicalbackup,
133independent/physical/OEM/AWDL/hostile/headful/crypto and owner120/274/284 remain.
Planning range:3–7engineeringdays accessible work;2–6+weeks external qualification
once equipment/participants/access exist, longer for owner/professional/legal scheduling;
not a promise or an effort estimate inferred from row percentages.


## Intel R16 readiness and current technical observations

**195/221 independently approved repository repairs (88.2%); 196/221 resolved rows (88.7%) including #287 without a repair; 25 unresolved (11.3%): one repair/native row (#236), 21 external-validation rows and three owner decisions (#120/#274/#284). 88 new findings. Repair-approval complement is26 (11.8%), not the unresolved count; percentages count rows, not effort or readiness. Whole audit NOT_READY; #133 independent NOT_STARTED.**
Source `8765e3ea66f119bf6d48e5c866798ed798fc2aa5` / tree `6375e7ab10967a22512e19b8c086ff3ee23e6c5f` includes seven local commits after pushed
`4a409a8`; **NOT_PUSHED at this binding**. This administrative successor is separate.
Earlier R15 and failed-run sections retain their original evidence; no historical
product result is rebound to this source.

### Consumer boundary completed, full consumers still pending

- **#407 / `e5bd38d` APPROVE_FINAL_REPAIR_SCOPED_REPOSITORY**: remove unused
  Android library plugin only. Existing shell method and39negative policy controls
  pass. Real strict configuration advances to a separate SLF4J1.7.30 rejection,
  not full PASS. Review SHA256
  `04fdeada3680db0f46e5270caf6f255011b7f2f9d13441fadd959d147ae36953`.
- **Canonical #112 / `5fac409` APPROVE_FINAL_REPAIR_SCOPED_REPOSITORY**:
  bind generated build tools to an allowed subset of the existing reviewed root
  lock before plugin application. Actual strict configuration passes with115
  selected exact components from177entries;62unrelated components stay absent.
  Unknown-module and contradictory-strict-version controls fail before tasks.
  Two shell methods and41negative policy controls pass. No product dependency
  forcing, new metadata trust, duplicate issue or extra repair credit.
  [Canonical continuation](https://github.com/p2pKit/P2pKit/issues/112#issuecomment-5622049988).
  Review SHA256 `91d22451c8f19418b2825d2ee8cd68332195509848e0c7779a346855eb1983fe`.
- Original executed112patch `1ac8f684092a6f67eb742eb34313fb0b05f5fba32f07c6478c775927774e5119`
  remains bound separately from final `d7c274a0b1136ea7297fbd7cc603da5715cc6b0384153532e02af3c0503d7bf2`:
  only logger line wrapping differs, so no redundant rerun. Strict constraints
  can pin an ordinary higher request downward; final exact selection is the
  contract, not rejection of every higher request. All three owned stops0,
  no survivors; released private probe outputs removed, reports retained.

### Useful technical interoperability, not independent #133 acceptance

Reused clean`4a409a8` product artifacts against an **AI-authored spec-only Python
peer** on Linux loopback; no new build or published-Maven qualification. Both
reversed Noise roles genuinely exchanged10messages/540386contentbytes, with
mutual pins, Unicode/nonempty metadata, large binaries, PING/PONG, ACK-aware close.
Four children naturally exit0/reaped; wrapper0/0/0.
**APPROVE_SCOPED_TECHNICAL_INTEROPERABILITY**, review SHA256
`0f41eae8864f8c3695957c37a3978fa014885bbf703f53152d1c5757b753d9b4`.

A separate one-role wrong-manual-pin observation receives exact JVM
`AuthenticatedIdentityMismatch`, zero accepted sessions/messages and natural
exit1/reaped for both children, no signals; expected-negative wrapper0/0/0.
**APPROVE_SCOPED_WRONG_MANUAL_PIN_TECHNICAL_OBSERVATION**, review SHA256
`0ace0ac5acdea41e71c52c8fea13383a34a25d0590e553f331fcf663b204fb46`.
The public manual API derives internal PeerId from its supplied pin: this is
not fingerprint-only isolation with a correct internal ID. Python terminal
failure is generic corroboration, not a typed EOF/authentication oracle.

All23JARs and161pinned installed wheel members were independently rebound.
Raw logs, reports, source and provenance remain; released synthetic controls,
empty homes/tmp, private endpoint build and Python environment are removed.
Maintained CLI distribution remains solely for upcoming Android peer work.
**No independent human/vendor campaign, physical/hostile-network, professional
crypto, files/reconnect matrix or release credit; #133 remains NOT_STARTED.**
Wire-doc rebind`639185c` preserves original70input history and composes current71
sources with the sparse TSV; its independent review SHA256 is
`6476ab1cf6b2f79f60b22cc4298251a0dd23180861da99ab75249482a1ecef10`.

### R16: exact readiness, not native execution

`8765e3e` is **APPROVE_FINAL_EXECUTION_READINESS**, review SHA256
`c6f5ba7e7525d78e2b38be37500be1c9a57fde1767a0b11ec8f5d0906388207a`.
All9focused selectors pass (6host+2peer+1workflow), command/stop/final0/0/0,
unchanged executed5fac409+exactdiff`795d8d4c8a3e3388178a75a9f8046fd74d695833b1af1857246c1c24bf91a10d`,
no owned survivors. This is no new native test result or repair approval.

One genuine Intel/Xcode26.3 campaign runs core/LAN, one publisher/consumer pass,
54archive inspection after its exact successful publisher even if consumers fail,
sevenABI+CLI once, framework/strictSwift/unit/UI/live peer and isolated cancellation.
The unchanged30s CLI quit failure permits only one bounded owned thread dump;
attach cannot rescue PASS. Intel success would not resolve the earlier ARM linger.
R15 aggregateFAIL/FULL_SEALED and all prior failures remain unchanged.

Fresh17:08:28–35UTC:328issues/221open/107closed,79PRs/7open,407fullbodies;
only407creation and known112comment5622049988, no substantivePR/inline delta.
Complete unchanged visible histories/linkedPRs/closeddecisions reused explicitly;
prior gaps preserved. Summary SHA256
`a3c1a333472506fc8ab55ecbb13ec9329a1c65a7eed48ea438084e7f91d8f01b`.
Coverage1153paths, preserving5755existing historical cells; the two new paths
have no inherited assessment. Source/delta corroboration is not blanket correctness.

Next: fresh Actions/refs and held global source-freeze lease before audit push;
then inspect actual Intel evidence, Windows17, one combinedART37→24→25 campaign
and the smallest genuine372recreation/controlled-peer extension. No simulated
same-instance revocation or repeated unchanged fullARM suites. Finish final current
rootcheck/sample/consumer/release components; last1786Linuxpasses remain old-source.
Approximate remaining accessible work **3–7engineering days**; external qualification
**2–6+weeks after access/reviewers exist**, conditional estimates, not measured effort
or promises. Serialize builds, max2workers/no parallel; logs, isolated stops and
exact-owned cleanup. Only genuine external/owner/account/hardware/release blockers
may remain; no main/tag/settings/closure/release authority.
