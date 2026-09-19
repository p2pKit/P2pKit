# Canonical retained-report parents — 19 September 2026

**Source/offline correction, not bootstrap collection or hosted acceptance.**
This follows [the dormant inventory increment](hosted-bootstrap-report-inventory-2026-09-18.md)
at `5a917b38b59a11b044538b1770e7f0a3c39d9fa8`. The containing commit and exact
review/readback are mapped to [#437](https://github.com/p2pKit/P2pKit/issues/437);
#424 is only a shared ordinary-CI prerequisite, not another fixture repair.

## Confirmed cause and narrow correction

Canonical `retain_reports` previously used `Path.mkdir(parents=True, mode=0700)`.
Python applies that mode only to the last directory; intermediate parents use
the process umask. The unchanged strict POSIX private reader requires current
UID and no group/other mode bits at **every selected child**. One tiny original
diagnostic found0755/0775 intermediate directories under umask022/002 and the
reader's `SEED_PRIVATE_MODE` refusal; umask077 produced0700 and permitted reading.
Its exit0 confirms the mismatch, not a desired-compatibility or hosted pass.
Diagnostic result SHA256:
`989cdf82e556be664e52517eefbc5f5de3b0c14f919c1a3f2e6f39f7a288c1a7`.

The [canonical helper](../../scripts/run-audit-command.py) now creates each new
relative parent separately with mode0700, anchored at the existing evidence
directory. It validates that root and every selected child before descending:
physical directory, no symlink/reparse, and on POSIX current UID/zero group-other
bits. Both newly created and FileExists-raced paths are checked. Missing anchors,
broad/wrong-owner directories and unsafe types refuse; ordinary mkdir/lstat
errors propagate. No chmod, process-global umask change, ancestor adoption,
replacement or deletion occurs. Existing payload and manifest creation remain
exclusive. Report paths, classifications, hashes, bytes and existing512MiB/
20,000-entry/report-depth256 bounds are unchanged. Output-root prefixes do not
consume that original report-depth limit.

The original canonical evidence root0700 already protects traversal: this is
**not an observed outside-user disclosure**. Path checks are not atomic custody
against same-UID replacement. Windows Python mkdir0700 is not the native file
supplier's exact protected ACL; Windows compatibility remains separate and
unqualified. This does not redo the earlier test-harness `retained_directory`
repair or change the strict file supplier's basename/member/depth admission.

## Original focused controls

The new [ReportRetentionPosixTests class](../../scripts/tests/run-audit-command-test.py)
has18 methods and is additionally selected by the maintained current-host main
only on POSIX. Windows' existing native selection is not skipped or replaced.
Only the new class was selected for this increment; the full current-host main,
old suites, fake wrappers and native-owner factories were **not executed**.

| Original author invocation | Actual result |
| --- | --- |
| Unchanged desired-private-parent1 on accepted canonical preimage | FAILED, exit1; three failed subcases at umask000/002/022;077 succeeded; no errors/skips |
| Same test bytes, exact implementation R1, all18 selected methods |18/18 PASS, exit0, no failures/errors/skips;2.399 seconds unittest |

Actual UID/EUID65534, Python3.12.3 `-I -B -S`; root-owned0444/0555 source copy,
CPU30s/AS512MiB/output2MiB/FD96, wall60s+kill5s, recorder75s. These are tiny real
POSIX report/manifest files plus explicit filesystem-fault/wrong-owner models,
and the unchanged strict POSIX reader—not native process retirement, original
producer authentication, application execution or cache/provider qualification.
The depth256/257 controls use tiny paths, not hundreds of held descriptors.
Process/network/native-owner/thread operations and nonfixture writes were
forbidden. Production chmod/fchmod/umask calls were separately forbidden;
fixture setup/race faults prepare their own modes explicitly. All1,433 source
bindings, interpreter identity and descriptor roster were unchanged. Original
fixtures and stdout/stderr/exits remain privately retained, including failures.

| Binding | SHA-256 |
| --- | --- |
| Canonical helper | `04e921eb5ba1e715078d9b315e366cc8f970151c9c1e5e0a4e5dfae0f0ed1ccc` |
| Author test file | `251b0e49c84e475c9c4f56c0813987da695c418d8cb9f644a4f30071f458d09e` |
| Author preimage result | `66284649a976590315fa801cf7f78f6b7123a95537b67c814baf26b1ab4a544a` |
| Author postimage18 result | `100a3519d7877781d75468ef46ed937a9e404be5986609bda54cdb51624dda0a` |

Implementation-only tree `03adb9091baedc6cc002d8464598aacc464cdedc`; patch SHA256
`06828947f4c647ee4a7ca05aa80df2ae1a2569f6db358cd15872d6137ecdb860`.
Private original packet: `20260919-canonical-report-parent-repair-hx8ycyfu`.
Hashes are navigation, not public raw evidence or substitutes for missing originals.

## Independent review and composition guards

Independent nonimplementing verdict:
**APPROVE_EXACT_CANONICAL_RETAINED_REPORT_PARENTS_IMPLEMENTATION_R1_SOURCE_ONLY**.
The full two-file delta, transitive import graph and original author evidence
were reviewed without replaying the author suite. Prospective controls were
frozen before implementation/new-author-test inspection. The old umask diagnosis
was disclosed, so independent discovery of that cause is not claimed.

One separate selected13 invocation passed **13/13**, exit0, no failures/errors/
skips/expected failures;1.810 seconds unittest. It used actual Linux UID/EUID/
GID/EGID65534, Python3.12.3 `-I -S -B`, immutable inputs, CPU45s/AS768MiB/
output2MiB/FD128 and wall90s+kill5s. Tiny actual POSIX cases include strict readback,
private shared parents, physical links, broad directories and a real root-owned
0700 anchor. Explicit reparse/label/error/mkdir models are not native qualification.
All1,433 source files/metadata, interpreter, input package and that wrong-owner
anchor stayed unchanged. No rerun, source edit, old suite or product execution.

| Independent binding | SHA-256 |
| --- | --- |
| Implementation review | `a1c47e180b9a2aa1e39f5b4e2fe1f8900b7a7ef97f63804450bb1a51d8c61c85` |
| Original independent13 result | `853243a738a42b0f0ba7ad81f2b4891cac452b33612ddaeaf3876e6f7bacfaab` |
| Separate canonical-only AST expectation approval | `5bcc53f539c50d8bf1d87981edbbee5bc9c7520dd496502dccd0d0febf936c2d` |

Only after implementation and separate expectation approval did the
[composition policy](../../scripts/check-hosted-test-composition.py) change its
canonical pin from `840a952e56cea3aa1f29afe0a46cf825452b5d2b452c2ae3ac0fb9c6d4ae8e8f`
to `bba4d4137571c32205fbf0bc1ff3d7d4682eff6d0f6ed5a6e92af8d6415cc639`.
The seven-program roster, other six pins and AST algorithm are unchanged. The
reviewer independently reproduced old/new values without importing any supplier.

Five new [AST mutation methods](../../scripts/tests/check-hosted-test-composition-test.py)
cover the actual anchor/descent, type/owner/private-mode validation, per-component
creation/narrow race handling, report call and late shadowing. Each first checks
the unchanged seven-source positive baseline, preventing a stale pin from passing
negative controls accidentally. The existing positive method plus those five
passed **6/6**, exit0, no failures/errors/skips,6.851 seconds unittest in one
selected invocation—not the whole historical composition suite. No executable
supplier was imported. Actual ordinary UID65534/Python3.12.3 `-I -B -S`, immutable
source, CPU30s/AS512MiB/output2MiB/FD96, wall45s+kill5s/recorder60s; process/network/
thread/native operations and writes forbidden. All1,433 source/metadata bindings,
repository bytes and interpreter/descriptor roster stayed unchanged.

Composition-only tree `ec3f577c8f2e596c33f35cffe9f3418afbf20a11`;
original selected6 result SHA256
`0f8681bffecae9b15e158231057b776d4e40069d60fbb86617187cd4e58115a1`.
The later complete patch adds documentation only; complete-patch static gates and
final independent review are separately bound in the containing commit's issue
mapping. Neither these parser controls nor source gates are hosted execution.

## Unchanged acceptance boundary

This makes selected retained directories compatible in the tested POSIX scope;
it is **not an actual configuration collector**. Original-call collection with
NEW handles after the closed producer, final RAW/LOCAL high-waters, all seven
canonical metadata/log files and already-retained changed reports still needs
its own bounded integration. Never re-open the producer's owner/READ30 or
recollect live checkout reports. No-loader observation, streamed positive
export/freeze/save/probe and encrypted custody/seal/delivery remain unfinished.

Both ordinary activation HOLDs, exact selectors, credential boundaries and all
deadlines remain. Proposed5400 is unadmitted/unmeasured; NativeFile900 and
Snapshot576MiB unchanged. No production caller invokes `cache.export_snapshot`
or `cache.save_set`. Missing routine custodian/exact key/finite14-day recipient
policy/trusted-original-base bootstrap/formal approval and genuine native/
provider/resolver/custody/scheduling/delivery qualification still block activation.
Required checks, different-account PR approval and normal checked main merge/
preservation precede development sample Releases. Agent review is not formal
GitHub approval.

Apps are not in Releases. Preview35070982169 and #424 writer35066719641/1/six
exports were not repeated; #372's20 Kotlin tests remain uncompiled/unexecuted.
OSV remains EXCEPTED_NOT_FIXED, Kotlin2.4.10 affected, expiry2026-10-31, without
new scan/remediation/extension. No local app/Java/Gradle/Xcode build, SDK or
dependency download, guest, held CI, phone, production/Maven/Store publication,
PR/merge, release/tag/settings change or closure. Main/protected instructions,
immutable RC history/compatibility and seven dependency proposals remain intact.
Historical206/234 repair-approved,207/234 resolved; audit/release **NOT_READY**.
