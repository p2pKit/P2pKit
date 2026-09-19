# Dormant producer-to-collection binding — 19 September 2026

**Private source/memory controls, not collection or hosted acceptance.** This
follows the [supplied-original file-copy leaf](hosted-bootstrap-file-collection-2026-09-19.md)
at `c5f4b793c8c06ead97b1fbe2ce5ef935fd7b8fbe`. The binding is deliberately a
separate increment before the NEW-owner collection phase. No public operation
or workflow calls it. Its containing commit and final review belong in
[#437](https://github.com/p2pKit/P2pKit/issues/437); shared ordinary-CI prerequisites
also concern [#424](https://github.com/p2pKit/P2pKit/issues/424).

## Exact in-call boundary

The private `_begin_collection_after_entry` in the
[bootstrap caller](../../scripts/run-hosted-cache-bootstrap.py) once-claims the
original transition **before invoking** the captured configuration operation.
Copies, reentry, prior direct producer claims and failed attempts cannot select
another call or adopt a returned `ConfigurationPrefix`. The actual producer
return is retained before fallible lookup/validation. The first exception,
including a falsey exception, and original references remain with the claim.
No claim lock is held across producer execution.

At the original producer's existing result publication, a private pin captures
its exact final frame, result dictionary, five original byte fields and two
high-waters. It also snapshots the selected closed owner/window/query/stream
dictionaries, query resource/record/readback containers and nested predecessor
graph witnesses. Failed publication attempts are consumed too. The producer's
public result/state bookkeeping follows that publication, so its dictionary is
added only at the later collection snapshot. It is not incorrectly frozen in
its pre-return state. Recipient tuple7 and initializer tuple6 stay unchanged.

Every graph has separate private dictionary/nodes/paths pins. A query ledger
cleared or replaced before the first collection snapshot cannot become the new
original; neither can an erased older graph witness. Mandatory unique closed
native-scope/stdout/stderr rows, query private-root/query-home/session-result rows
and original private/home references are compared. Stream identities, paths,
size/stamp/high-water/readback/max/deadline, child PID/direct-output facts and
typed native scope fields have separate passive cross-checks.

Typed phase chronology, successful cancellation/retirement facts and exact
retained request/descriptor/outer/native/parent bytes are checked without calling
old owner/window/query/resource methods. Existing pure native and canonical
observation guards remain the record validators; no current descriptor/source
loader, native observation, clock or file acquisition is substituted. Original
parent `closedNs` may legitimately precede its final `checked_ns`.

The query supplier's immutable LOCAL work/final pair governed its own operations.
The producer's **later outer** query-return observation is a different sample:
its original bounds are query RAW final and enclosing WORK LOCAL. It may follow
a conservatively contracted supplier LOCAL deadline without establishing late
supplier work. No missing supplier sample is invented, and no actual deadline
is renewed or widened.

This is finite same-process binding, not a sandbox against arbitrary Python-code
replacement or authentication of supplied native records. Both graph traversals
retain their independent 10,000-node ceilings. Traversing older witnesses costs
additional nodes: an older graph that fits its own ceiling need not fit this
composition. Exhaustion refuses; real composed capacity is **unqualified**.
Final retained high-waters are historical observations, not a fresh clock sample
or permission to spend time after an original phase/job fence.

Successful private state is only **BOUND**. It contains no collection owner,
window, manifest, file-copy return, no-loader observation, provider or public
acceptance record. It must stay inside the future original enclosing call;
serialization/copying cannot transfer it into execution authority. No closed
owner, resource, window or READ30 is reopened, advanced or assigned new cleanup.

## Retained review findings and actual controls

R1 independent passive review requested changes for unpinned graph witnesses,
replaceable pre-capture result bytes, opaque query/stream/child fields and missing
terminal relationships. R1's four basic author controls passed, but its ten
selected negative controls all failed because the expected refusal was absent.
Those failed aggregates remain failures, not later successes.

R2 added original result-byte publication and passive relationships, but passive
review found three remaining problems: supplier/witness containers were still
first-pinned too late; a later outer LOCAL sample was compared with the supplier's
different contracted deadline; and post-publication private-frame mutation made
several tests stop at the early frame pin instead of their named predicates.
R2's 51 authored methods were **never executed**.

R3 pins selected containers at original publication and compares each observation
with its actual original fence. Its
[author controls](../../scripts/tests/hosted-cache-bootstrap-collection-origin-test.py)
use a separate pre-publication modeled-facts seam for terminal-predicate tests,
asserting the exact refusal and that the intended guard was reached. Deliberate
post-publication changes remain distinct binding controls. Representative query
ledgers and older path witnesses are nonempty. Scope-field subclass equality is
rejected without dispatch, and graph-cap failure consumes both claims.

| Original invocation | Actual outcome |
| --- | --- |
| R1 author4 | 4/4 PASS, exit0, 0.318s |
| R1 selected negative10 | FAILED, 10 assertion failures, exit1, 0.338s |
| R2 author51 | AUTHORED, NOT EXECUTED |
| R3 author71 | 71/71 PASS, exit0, 1.440s |

Executed invocations had zero errors/skips; durations above are original unittest
durations, not hosted timing measurements. The R1 fixture used an opaque query
model; R3 models the actual tuple5 shape and additional synthetic native/parent
records. R1 positives are not promoted to R3 or original producer execution.

R3 executes AST-extracted new binding/registry/container code, the existing graph
engine and pure native guards. The producer operation, predecessor validation,
canonical observation validator and scalar/parser boundaries are **explicit
models**. Old live methods are poisoned. Windows/macOS layouts are memory data,
not those operating systems. No earlier accepted test fixture or product suite is
imported/replayed. No canonical producer, query, host identity, filesystem
collection, Java/Gradle, network or provider operation ran.

The private recorder invocation was:

```text
python3 -I -B -S <private-packet>/run-binding.py freeze-r3 author71-r3-original BindingModels
```

It owned `/usr/bin/python3.12 -I -B -S` under wall20s+kill2s, CPU10s, AS512MiB,
output8MiB and FD64, with audit-denied writes/network/children/native execution.
Only named source/probe and stdlib reads were allowed. No denied event occurred;
before/after source/stat and probe bindings matched. UID0 is used only for these
memory controls, **not private-file/native qualification**. Original plans,
stdout/stderr/results and harness copies remain in the private
`20260919-collection-origin-jhyfrwc1` packet, not disposable source `/tmp` copies.

| Binding | SHA-256 |
| --- | --- |
| R1 passive review | `6b59c159067421cdb48ebcad70d2a84799ede0323d5754728d05e866627ccbea` |
| R2 passive review | `67bee8f0f0cbf1ff47d9793e68f6ce135259126b98934c10e97c37fec7aaf7f2` |
| R3 passive source/control-design review | `f6792ee91b82e3c0e1f4d7efa12c60beed94ff1301ccb850a45a8e818217edfc` |
| R1 author4 result | `d8641d5f721d1f9e857b4bb14a92cb7a1166c9d320eee9bcbfd2e261297794eb` |
| R1 negative10 result | `f5b6ea6a2cda1d39acc4056e779b3f7e6e42f35ba854b63b2ed7f3c914ffa64d` |
| R3 implementation | `a2825b522dbbb91e8e80b6567874a7c432c5530d012a815b98540c37a74e4ca1` |
| R3 author controls | `86047fe902a25c7ba873b7be4ff058305fcd7f53f0037baf5dd297cc92d252d3` |
| R3 author71 plan | `5b8d1c5882d09f6abcd65792b32a77a896fdfd8ebec713ad280835af12bd7916` |
| R3 author71 result | `4c82f5584983dca23a853d64ea84e4f3672b38a6057b0113251c33decd8df7a8` |

R3's executed two-file tree is `8975465ef494450db565e7864df1d04918086b65`;
patch SHA-256 `70df5aa5b4b14da10737cf9b2e47f3151648623469e665e592d31ce53c15f6d6`.
These are execution-snapshot bindings, not a committed complete-patch tree or
approval of subsequently authored documentation. Independent passive verdict
**APPROVE_EXACT_R3_BINDING_SOURCE_AND_CONTROL_DESIGN_ONLY** closes the three R2
findings for R3 source/design, not R2 or new-owner integration.

### Separate independent execution

After full lead review of the immutable probe, supervisor and manifests, the
reviewer ran R2 once, retained/read back that failed aggregate, and received
separate authorization for R3 once. The same24 fixed oracles in12 groups were
applied to both inputs: **48 revision observations, not48 distinct controls**.
No author test file or earlier accepted runtime fixture was imported/replayed.

| Independent invocation | Actual outcome | Original supervisor wall time |
| --- | --- | --- |
| R2 controls C01–C24 | FAILED:14 PASS/10 FAIL/0 ERROR; child/supervisor exit1 |0.792s |
| R3 controls C01–C24 |24/24 PASS; child/supervisor exit0 |1.285s |

R2 accepted the eight post-publication query/witness mutations C03–C10,
incorrectly rejected the later outer LOCAL sample C16, and dispatched custom
scope equality three times in C19. These remain actual failures, not passing
reproductions. The independent pre-publication C12–C15 reached their intended
terminal guards without early frame-pin masking on both revisions. R2's51
authored methods remain unexecuted; this different probe does not execute them.

R3 refused the mutations and custom equality without dispatch, accepted the
distinct valid LOCAL/RAW case, and retained strict equality-expiry, graph-cap,
one-call, first-error and original-return boundaries. Each invocation used fresh
memory objects/registries and AST-selected binding/graph/pure native guards over
explicit producer/predecessor/observation/scalar/native-record models. The
actual producer and old live methods did not run. Linux/Windows/macOS layouts
remain synthetic data, not platform qualification or real composed-graph capacity.

The exact private invocation pattern was:

```text
/usr/bin/python3.12 -I -B -S <private-plan>/supervisor.py <private-plan>/R2.manifest.json <R2-manifest-sha256> <private-plan>/R2-original
# Only after original R2 readback and separate approval:
/usr/bin/python3.12 -I -B -S <private-plan>/supervisor.py <private-plan>/R3.manifest.json <R3-manifest-sha256> <private-plan>/R3-original
```

Each supervisor owned one isolated child, wall20s plus at most2s kill/reap,
CPU10s, AS256MiB and FD64. The combined256KiB output ceiling reserved240KiB for
child output and16KiB for metadata. R2 retained6,775 original child bytes; R3
retained7,300. Both stderr originals are empty, children reaped normally, with
zero denied/live events, no envelope violation and unchanged source/probe/
supervisor/interpreter hash/stat bindings. No repair or retry occurred. UID0
memory execution is not ordinary-UID private-file or native acceptance.

| Independent binding | SHA-256 |
| --- | --- |
| Control plan | `279ca18fb219fddae48827a8bae889404ee2181dafb52b9225f39de537a60c94` |
| Probe | `1e2fd77cce64013e7b14d974018de714a4d4b0a8c2dc1e79b6c715419d99a4b1` |
| Supervisor | `b179c318a8f80ef2b7f7919a737e936592cf9a1ef32bc1f3b52b7aec25af6238` |
| R2 manifest | `960201a4a834f01fde51529d4f7fd93b2272257e6816cc29d9c80f6026b3f263` |
| R3 manifest | `c7193c18f8883f48682999bb8adc95caab15bf971ca8b820976f4aa7d33c8366` |
| R2 failed result | `b70ee505a6d1a14e036f5c7826f1420f8f85ca1ea1ce3b463fdad54f9d26fda6` |
| R3 passing result | `7c6659b03ce4410cf4b814bb2d817f0d23b821ca562a1dcb722cb63621725a64` |
| R2 original stdout | `045758fa219b767e267ed0dad86b2e260950080eaa1b6d536c70be1718bee3a3` |
| R3 original stdout | `ca2fe32d3eae9bb742ff199f891e8364aff46f0fcd407e4700f2d56ad2a90239` |
| Independent execution review | `18d85621b2b042b77320732263b7275908e99858cc1a1e3f407a86edd3e99407` |

Both lead and reviewer read/hash-checked the originals. Independent verdict:
**APPROVE_EXACT_R3_BINDING_SOURCE_WITH_24_INDEPENDENT_MEMORY_CONTROLS_ONLY**.
It approves neither later documentation nor the NEW-owner collection phase.
Complete-patch static gates and final review are separately bound in the
containing commit's #437 mapping. They cannot be inferred from author71 or
combined with these controls into product-test counts.

### Static checks and private recorder limitation

Eight individual static gates exited0 on the first four-file tree
`791a116407a5d9b21c7766b22805f35bc9fdf5a9`, patch SHA-256
`6b2b8443c66ad61231226575f27d7062ec4b00779465798613f32044a4d093ae`:
Markdown616 links/125 files, layout10 projects/15 policy controls, release
metadata, OSV input coverage **not a scan**, ordinary composition, ordinary FULL
workflow policy, sample/Desktop workflow policy and whitespace/archive integrity.
All1,439 source bindings and the primary worktree index stayed unchanged.

The outer recorder nevertheless **FAILED, exit1** because the separate private
Git index changed bytes. Its original failed result is preserved, SHA-256
`9719c3a74d7ce406794545257a93a30a07a59dbb00014ba0b48e506dca685888`.
The surviving private index still describes the exact frozen tree. Its earlier
raw bytes were held only in recorder memory and are unavailable; tree equality
does not recover them or make that failed preservation aggregate pass.

A separate fresh-index metadata experiment identified `git diff --check --`
refreshing1,435 stat-cache entries despite `GIT_OPTIONAL_LOCKS=0`. Blob/mode/name/
flag entries and the TREE extension stayed identical in that experiment. Its
analysis SHA-256 is
`99f7806a81830a20b139c81c656254ef8a14fb3d03d9695183ddaaf42f99c37d`.
A single process-local `diff.autoRefreshIndex=false` counter-control retained
its exact fresh index bytes and still exited0, result SHA-256
`97cf31f8c5b1af1a881de1df8c553c24f3f24aab0861289ad4b9d033ce32d77d`.
No repository configuration or gate assertion changed. This diagnoses the
metadata-writing behavior without reconstructing the missing old index,
rerunning the eight-gate aggregate or changing source/test results. Later
documentation-only checks retain both raw index snapshots; their final-byte
records and the complete-patch review are separately mapped to the commit.

### Preservation observations

The 21:38 UTC preservation snapshot found all 24 worktree tips in HEAD ancestry;
the other 23 worktrees' raw indices, staged/unstaged diffs, untracked files and
status matched the 20:21 baseline. Twenty of those worktrees remain dirty, not
cleaned or adopted. The first preservation aggregate failed only because its
status command used newline rather than the baseline's NUL termination. The
original failed result remains; the separately corrected exact-format comparison
passed. Earlier disclosed index/stat-cache and missing temporary-fixture caveats
remain; no missing original was reconstructed. Protected instructions are unchanged.

## Remaining integration and unchanged acceptance

Next is the distinct NEW-owner collection phase inside this original call, under
the original cumulative allocation, with live original/source/native readmission,
first manifest read, actual file leaf and honest no-loader observations. Positive
export/freeze/save/probe, encrypted custody/seal and sample delivery remain separate
unfinished work. No production caller invokes `cache.export_snapshot` or
`cache.save_set`; no bootstrap workflow exists.

Both ordinary activation HOLDs, exact selectors, credential boundaries and
deadlines remain. Proposed5400 is UNADMITTED/UNMEASURED; NativeFile900 and
Snapshot576MiB remain unchanged. The approved named routine custodian/exact key/
finite14-day policy/trusted-original-base bootstrap, genuine native/provider/
resolver/custody/scheduling/delivery, current required checks, formal different-
account PR review and normal main merge remain prerequisites. Agent review is
not formal GitHub approval. Candidate source cannot authorize its own recipient.

The complete paginated **21:32:20 UTC** metadata snapshot has 78 open issues,
the same seven dependency PRs, no campaign PR, zero queried active Actions and
two RC Releases with zero assets. All 29 complete saved endpoint records are
unchanged from the 20:22 snapshot, including the relevant complete issue comments
and timelines. Comparison SHA-256:
`eff9d5ed084948188fc9f7e14a51c053a5502af8b42eaa0bcac455f4225eaf0b`.
The earlier nested timeline comparison retained only embedded push/size and
already-preserved file-leaf comment/update metadata changes; no later owner
decision is present. A source fetch without tags during this resume also found
main/integration unchanged from the base above. Required checks remain
`complete-gate`, `review`, `scan / osv-scan`, `osv-scanner`; settings do not waive
formal different-account review. Later preservation observations are separately
bound to the containing commit and its issue mapping.

**Apps are not in Releases; audit/release NOT_READY.** Accepted preview35070982169,
#424 writer35066719641/1 and six exports, and prior file-copy tests were not repeated.
#372's20 Kotlin tests remain uncompiled/unexecuted. No held CI, local application
build, SDK/dependency download, guest, phone campaign, production/Maven/Store
publication, tag/settings change, merge or closure occurred. OSV remains
EXCEPTED_NOT_FIXED, affected Kotlin2.4.10, expiry2026-10-31; no scan/remediation/
exception extension. Historical206/234 repair-approved and207/234 resolved remain.
