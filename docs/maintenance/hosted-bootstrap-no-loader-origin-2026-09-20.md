# Dormant original collection return binding — 20 September 2026

Refs [#437](https://github.com/p2pKit/P2pKit/issues/437) and shared
[#424](https://github.com/p2pKit/P2pKit/issues/424). Base:
`8ff4015b2f1617bd4aed642e625dd3340b07d5a6`, tree
`a4bf4d31094442ba25669662b87becfd9194dc93`. Main remains
`3bc76f956f8f47447b51a62474fc878b9c43173c`. The
[accepted no-loader leaf](hosted-bootstrap-no-loader-2026-09-19.md) is unchanged.
This is the next private return-binding component, **not** its NEW-owner parent.

**Source/offline work only. Apps are not in Releases; audit/release NOT_READY.**
Both ordinary activation HOLDs remain. No new owner/deadline, absence-leaf call,
bootstrap workflow or production `cache.export_snapshot` / `cache.save_set`
caller is introduced. No accepted producer, collector or preview was rerun.

## Root cause and narrow source change

A supplied `CollectionPrefix`, or a snapshot first taken by a later consumer,
does not bind the original collector call. The final collection `parent.check()`
also replaces its private frame through roster bookkeeping even when no file or
clock is touched. Publishing before that check would pin the wrong frame.

The original collection tail now publishes after the last check and both public
COMPLETE/result assignments. Its private registry keeps the exact final frame,
result, original dictionary and five typed fields. The publication attempt is
consumed before fallible graph capture; a failed publication cannot be retried to
create a new baseline. A subsequently changed/FAILED frame cannot reuse its pin.

The new graph explicitly traverses selected collection/producer/staging record
and tuple families, mutable query/leaf/result containers and the older witnesses
themselves. Dictionary pointers, original nodes/paths and selected retained native
path/identity facts are bound. The new claim/result-publication registries remain
outside graph roots. Independent
10,000-node/edge/path ceilings fail on exhaustion; edges are charged before
materializing container contents, including scalar-only lists/maps. Older graph
limits are not widened. Earlier retained validators run before this capture;
the new local traversal caps do not globally bound their cost. Real composed
capacity/cost remains unqualified. Native identity components preserve the
existing runner's role grammar and exact original types/values. Normalized
tuple/list values do not attest the original identity container's kind.

The private `_begin_no_loader_after_entry` claims before its fixed collector call,
releasing the claim lock across execution. It keeps the actual returned object
before fallible roots/lookup/validation, including malformed or copied returns
that must refuse. First exceptions survive falsey truth values and failed
annotation. Failed/reentrant/prior-direct calls cannot be adopted or retried.

Later lookup uses only the original published pins plus retained closed records.
It does not call closed parent/owner/window/query/file methods or clocks, mutate
predecessor frames, reopen resources or reconstruct original native observations.
Earlier `closedNs` may precede the original final checked high-water; the source
does not demand a new observation or relabel that earlier timestamp as current.
The [collection query pre-final limitation](hosted-bootstrap-collection-parent-2026-09-19.md)
is unchanged: no retroactive claim that a row could not have disappeared before
that original snapshot, descendant continuity or atomic freeze follows.

Private **BOUND** preserves scoped predecessor facts, not expanded acceptance,
current execution authority, a renewed budget or a no-loader result. The separate
NEW-owner phase must remain inside the original enclosing call and acquire fresh
RAW/LOCAL observations under original allocation/job fences. Old WORK/FINAL/READ
slots and closed owner lifetimes cannot be borrowed.

## Independent findings and actually executed author controls

Passive R1 verdict: **REQUEST_CHANGES_TWO_NEW_SOURCE_GAPS**, report SHA-256
`68f77377508c7a17e6d471b5bf9f3782a0aea30fc7cb1a58be3d323349f52b71`.
The reviewer confirmed two gaps confined to this new WIP:

- **F1:** tuple equality accepted bool/int or float/int identity substitutions
  and conflicting typed aliases for opaque retained directory fields. R2 calls
  the unchanged pure `directory_identity` after exact length2 checks, then
  compares original/current components by exact type and value. The original
  role grammar includes POSIX integer and Windows string file IDs; it is not
  tightened to another supplier's positive/nonzero grammar. The review's additive
  grammar clarification has SHA-256
  `5383f91fe4c0abb8c4d1a09044da05d66c35b65738cb333800a97615b612ee61`.
- **F2:** a changed resource row could reach `set(row)` before its key count was
  bounded. R2 checks exact four-key length first. A five-key row/set-call observer
  exercises this ordering without creating a large allocation.

These began as source findings, not reported native incidents. R1's original
8/47 invocations passed55 distinct methods but did not cover those gaps. Nine
new desired-state controls then actually ran against unchanged R1 source:
**2 PASS / 7 FAIL / 0 ERROR / 0 SKIP**, with no guard denial. Six failures observed
missing native-identity refusal; the seventh observed premature row projection.
The two positive controls preserve Windows-shaped data and POSIX tuple/list
normalization. That failed aggregate and all originals remain unchanged.

New test: `scripts/tests/hosted-cache-bootstrap-no-loader-origin-test.py`.
R2 **64 distinct methods PASS** across two disjoint invocations:

| Selectors | Methods | Actual result |
| --- | ---: | --- |
| `ReviewBoundaryModels` | 9 | PASS |
| `PublicationModels OriginModels GraphModels ClosedRecordModels` | 55 | PASS |

Both have zero failures, errors, skips and denied boundary events. The complete
new test/observer/recorder bytes were identical across the R1-boundary/R2 runs.
Subtest values are not additional methods. R2 requalifies this changed binding
source, not an unchanged accepted producer/collection/leaf/preview suite.

The fixture AST-selects actual registry/publication/original lookup/typed graph/
closed-result/binding code and the **original selected return-tail statements**.
It also selects the existing query pin predicates, leaf data-record capture and
pure native-identity grammar helper.
Earlier collection and the final `parent.check()` are explicit models; that final
check deliberately replaces the private frame to exercise publication ordering.
Producer/predecessor/host/query/leaf outcomes and scalar/encoding suppliers are
models. There is no full controller import or real collection/producer execution.
Selected lifecycle/file/query methods and original clocks are poisoned or absent;
not every inherited method/property is replaced. Passive source review separately
found no forbidden new lookup calls. Tiny path and identity values are model data,
not native or ordinary-user observations. Frozen-source/stdlib reads, compilation
and supervisor output writes occurred; no candidate native/file work ran.

Coverage includes exact final-frame publication, repeated passive lookup,
missing/repeated/failed publication, reentry and prior-call refusal, actual-return
custody, falsey/unannotatable first errors, copied objects and types, corruption
before **first** lookup and after BOUND, nested query/leaf/older-witness changes,
native path-pin changes without native verification, graph cycles/exhaustion,
closed resources/restoration, typed clocks/chronology and nonaccepting records.

The older `hosted-cache-bootstrap-collection-parent-test.py` now explicitly models
the added publication seam. **That changed fixture was not executed**; historical
78-method results remain bound to their earlier source and fixture, not this
revision. No new publication acceptance is attributed to those old results.

Exact command form, recorded separately with each frozen path and selector list:

```text
/usr/bin/timeout --kill-after=2s 20s /usr/bin/python3.12 -I -B -S
  <frozen-observer> <frozen-source> <selected-classes>
```

CPU10s, address space512MiB, descriptors64, core0 and a clean environment without
hosted identity. **Exclusive regular-file stdout/stderr** each use a1MiB
RLIMIT_FSIZE, not the old pipe-output claim. The observer guards subprocess,
network/ctypes, writes, directory operations, resource/environment/signal changes
and UID/GID mutators. Exact frozen-source/stdlib reads are allowed. This is an
audit/stub guard, not a kernel sandbox. Actual UID0 supplies no private-file,
ordinary-user, provider or hosted/native qualification.

All13 source/manifest/observer/recorder/interpreter/timeout byte/stat bindings
were unchanged per invocation, and the owned process groups were absent on
return. Original R1 wall times were0.617/1.170s, R1-boundary0.667s and R2
0.618/1.271s. These are model times, not productive-phase budget admission.
Original stdout/stderr, plans and results remain private.

| Exact binding | SHA-256 |
| --- | --- |
| R1 runner source | `128df8b36bc687d9a10c567a8bd2de6ca416c1a43e5b1dc198c401d9f9770da9` |
| R2 runner source | `1434fecbb06a327fe1a3b739119443167db048d10be5fa95161505f3e48b3cdf` |
| R1 initial author test | `105a971190fe21d3b4935f5f6686deb4e9c430251b7d2fc3902039633cc8ddf9` |
| R1-boundary/R2 author test | `228d23151a9072aeb31f355e57cd818689b1185d2b7f529e63e15bbde7699df2` |
| Changed old fixture, unexecuted | `1c3da8474ef9636350b989a60ba9f906a06428935d4d0455eb39f46c71ff50b9` |
| R1 initial execution-input freeze | `61399dc75974b3322a71e59b447d9075a178888aed41faeaa3a6fd0a26fd5301` |
| R2 execution-input freeze | `22af847190a085a13e70497b40805389b649f9c8ec5f3967e13fcf3dac0ca5ae` |
| R1 initial read-back author results | `4c076ce1b77503d2c7a224e5c9846ba10711b6b32c5f3312001d934e89081544` |
| R1-boundary/R2 read-back results | `67b8347fbbbfde769cc0cf7fc61016520c23c95e3f6556d007ac6e6e3943289e` |

Private packet: `20260920-no-loader-origin-x0fnyvi7`. Old Mac originals were
neither reconstructed nor used to justify another build/download. A preexecution
no-op patch attempt failed to match a misread fixture name; all source hashes
remained unchanged. It was not a candidate/test execution or a repaired defect.

## Independent review and remaining acceptance

Independent R2 verdict:
**APPROVE_EXACT_NO_LOADER_ORIGIN_R2_SOURCE_CONTROLS_AND_ORIGINAL_RESULT_SCOPE_ONLY_NOT_RUNTIME_QUALIFICATION**.
Report SHA-256:
`d7886065d30d741166f4359c1e73ee1f77f44a2b9213a3bb6d59a0e1345e0160`.
The reviewer inspected the original results without replay, verified input/output
hashes, confirmed F1/F2 resolved and found no remaining blocking implementation
finding in this narrow scope. No independent controls were authored/executed.
The earlier passive design review is not substituted for this implementation
review. Neither verdict supplies formal GitHub approval or runtime qualification.

That implementation verdict does not approve these later docs or a complete Git
tree. The containing commit's issue mapping separately binds final complete-patch
review, applicable source gates, commit/tree and remote preservation. Windows
zero-volume/all-zero-ID grammar compatibility is preserved by unchanged-source
inspection, not claimed as a specifically executed boundary test.

Complete paginated metadata refreshed00:32:00 UTC:78 open issues, unchanged seven
dependency PRs, no campaign PR, zero queried active Actions and two RC Releases
with zero assets. Required checks remain `complete-gate`, `review`,
`scan / osv-scan`, `osv-scanner`; configured approval count0 does not waive the
owner-required formal different-account approval. The source branch advanced
only by the already-reviewed no-loader leaf; main did not advance. Known comment
and embedded repository-update deltas are separate from new approval or runtime.

The NEW-owner no-loader parent, positive export/freeze/save/probe and encrypted
custody/seal/delivery remain unfinished. Approved named routine custodian, exact
public key, finite14-day policy, legitimate trusted-original-base bootstrap and
formal approval remain absent; candidate source cannot authorize its own
recipient. Genuine current native/provider/resolver/custody/scheduling/delivery
qualification and all required checks remain necessary.

Both HOLDs, exact selectors/credentials/deadlines, proposed5400
UNADMITTED/UNMEASURED and NativeFile900/Snapshot576MiB are unchanged. No local
Java/Gradle/Xcode/app build, SDK/dependency/preview download, guest, held dispatch,
phone task, PR/merge/Release/closure or production publication occurred. Accepted
preview35070982169 and #424 writer35066719641/1/six exports were not repeated or
expanded. #372's20 Kotlin tests remain uncompiled/unexecuted. OSV remains
EXCEPTED_NOT_FIXED, affected Kotlin2.4.10, expiry2026-10-31; advisory/policy
readback is not a new scan, remediation or exception extension. Historical
206/234 repair-approved and207/234 resolved accounting remains unchanged.
