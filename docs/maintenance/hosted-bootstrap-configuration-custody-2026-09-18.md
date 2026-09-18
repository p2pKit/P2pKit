# Dormant configuration-custody reservation — 18 September 2026

**Source/offline scope only; apps are not in repository Releases.** This follows
the [producer-command descriptor](hosted-bootstrap-producer-command-2026-09-18.md)
at `3d21a0ffb002cc1a967db2137aa05312ee3390c1`, tree
`a4f73d1b18af20423efbf9d263883a6c0e5a4696`. The containing commit, complete-patch
review and remote preservation are mapped separately in
[#437](https://github.com/p2pKit/P2pKit/issues/437) and shared
[#424](https://github.com/p2pKit/P2pKit/issues/424).

## Separate file-only leaf

[`reserve_configuration(parent, originals, phase, staged)`](../../scripts/hosted_cache_bootstrap_custody.py)
checks supplied initializer/stage/empty-seed data and reserves configuration-only
custody. It does not authenticate original same-call returns or implement their
parent. Copied consistent records remain non-authoritative data.

The strict counterpart distinguishes seed **leaf** ancestry from seed **parent**
ancestry, requires the complete all-artifact ABSENT inventory and zero dependency
counters, and binds final seed-parent RAW/LOCAL high-waters. It reuses the existing
bounded staging readers/window unchanged. Actual context/properties/stage/source
bytes and identities are reread; H remains properties-only, S and canonical
evidence/cancellation directories empty. Point-in-time observations are not an
atomic filesystem freeze.

The entire new operation, including writes, readbacks, closes and final checks,
fits **custody-prepare at most120 seconds**, shortened by original cumulative/job
and independent LOCAL fences. It consumes no additional prepare-final/read
allowance and manufactures no completed phase record for those reservations.
Proposed5400 remains **UNADMITTED / UNMEASURED**.

Exclusive creation is limited to:

```text
<initializer-session>/configuration-custody/
    request.json
    retained/          # empty
```

One UUIDv4 is reserved, without retry, for the eventual canonical product and
its same-home stop. The job is the **canonical context job**, not the initializer
outer job. Known job/invocation collisions and existing custody paths refuse.
The leaf does **not** create `state/evidence/<id>`; canonical execution owns that
exclusive allocation. It accepts no caller-selected ID, command, path, deadline,
recipient or ancestry and does not call the command descriptor with invented
ancestor IDs. Only this module joins its separate custody source roster; ordinary
rosters, cache keys, accepted suppliers and workflow selectors stay unchanged.

No Test loader is installed, no canonical state is initialized, and no stage/seed
leaf is replayed. No producer, collector, uninstall, dependency transfer, deletion,
encryption, provider or public workflow is invoked. First exceptions, partial
files and actual acquired references survive failure; UNKNOWN grants no new
ownership or cleanup authority. A successful reservation still reports budget
`NOT_ADMITTED`, tests `NOT_PERFORMED`, enclosing retirement `NOT_OBSERVED_HERE`
and false successor/export/save authority.

## Exact source and author originals

Two-file source/test tree: `f5ba5f91b73fc7ac1042e2dd384678e4917107cc`.
Patch SHA-256: `37050dffa4281e7d0b5abf2f3be8dcbf4f7f95bcc569322c33662e1195b908d8`.

| File under `scripts/` | SHA-256 |
| --- | --- |
| `hosted_cache_bootstrap_custody.py` | `2ccc97810bd5b414619f28ea2a6f087b5edc22e9263217c55f5999eea7dd5dd8` |
| `tests/hosted-cache-bootstrap-custody-test.py` | `c0cbf2b39852295081482c13887ca8916bce29b91529409b1342d4965caef782` |

The own class is `ReservationModels`. Actual invocations used its selected
methods through an original same-process interpreter observer, actual UID65534,
Python3.12.3 `-I -B -S`, immutable-to-test source, external90 seconds plus kill5,
and recorder105. All1423 source bindings/rosters matched before/after.

| Invocation / exact selection scope | Original result | Outer / unittest seconds |
| --- | --- | --- |
| `author-smoke-r1`: `ReservationModels.test_reserves_one_id_without_loader_command_or_canonical_evidence_allocation` | 1/1 PASS | 0.767927 /0.124 |
| `author-remaining-r1`: all other39 own methods in that frozen test file | **FAILED:38 PASS /1 FAIL** | 2.524124 /1.943 |
| `author-fixture-r2`: only `ReservationModels.test_missing_declared_artifact_cannot_be_a_complete_empty_inventory` | 1/1 PASS | 0.667021 /0.063 |

Thus **40 distinct individual methods have applicable passes across three
invocations**, not a passing whole40 aggregate. The failed fixture changed seed
bytes but retained the old parent `leafSha256`. Source correctly refused
`PARENT_BINDING` before the intended `SEED_INVENTORY` assertion. R2 coherently
rebinds that synthetic parent; implementation, assertion meaning and bounds are
unchanged. Only this method's AST changed; the39 other individual passes were
not replayed to manufacture a green aggregate.

Historical test modules supply setup/cleanup fixtures only, not selected test
methods. Stage/seed and producer routes are poisoned. Actual new reservation,
existing file-owner behavior and tiny POSIX reads/writes/closes execute. Original
admission/service/source bindings, staged returns and RAW/LOCAL clocks are models.
No canonical initialization, Java/Gradle, native/Git process, GPG, provider or
download occurs. The original argv, selected rosters, logs, failures, manifests
and observer/recorder bytes remain private in
`20260918-bootstrap-configuration-custody-27ppurtj`.

## Independent review and original fixture failure

Verdict **`APPROVE_EXACT_CONFIGURATION_CUSTODY_RESERVATION_R1_SOURCE_AND_OFFLINE_ONLY`**,
report SHA-256 `0e6fe878592a23fe75596b93c70916231089c7d75fc6d0883883af6b0bed83ab`.
No blocking implementation finding. This two-file approval excludes subsequent
documentation/callers and is not formal different-account GitHub PR approval.

Independent assertions were frozen before reading new author assertions. The
implementation-only freeze is tree `33f44582d7b0264d1a8c5da7e0f82e555ef2b623`;
the implementation bytes are identical. All1422 imported-source files and control
content/metadata remained unchanged. No author or historical test module was
imported by those controls.

- R1 original16-method aggregate remains **FAILED**: six passing methods,
  ten nonpassing; seven failure records (two subcases in one method) and four
  errors. Outer0.567093/unittest0.204 seconds. The reviewer mistakenly used the
  root-owned immutable import freeze as ordinary-UID public-source **data**.
  The actual owner guard correctly refused `SEED_PUBLIC_SOURCE_MODE`.
- R2 changes only fixture setup: a separate UID65534-owned data root contains
  the exact frozen module bytes. Imported implementation/controls remain
  root-owned immutable; public-root ownership checks are not patched. All16
  assertion ASTs remain identical. Only the ten unsuccessful methods ran:
  **10/10 PASS**, outer0.616972/unittest0.250 seconds. Twelve per-fixture data
  identity/metadata/hash pairs matched before/after.
- The six earlier passes reach unchanged pre-source guards and remain narrowly
  applicable. There are **16 individual independent method passes across two
  invocations**, not a green whole16 aggregate. No assertion, source or timeout
  was weakened; both failed aggregates remain preserved.

Independent upstream admission/initializer/stage/allowlist/root/RAW/file-owner
protocol suppliers are modeled. The new counterparts/reservation and shared
window/byte/file readers execute with actual tiny POSIX operations. These controls
do not establish the upstream native chain or original parent-return authority.
Both independent invocations retain actual UID65534, isolated Python3.12.3 and
same-process before/after executable metadata/hash observations, under90+kill5/
recorder105. The observed `/usr/bin/python3.12` SHA-256 in author and reviewer runs
is `1643dacd9feaedc58f3cc581e4d22577dfe25c09b10282936186ccf0f2e61118`;
this is not whole-runtime or hosted admission.

Independent original audit SHA-256:
`2b730bf1f0287c6b521e4c8b87eef65b2656e0459d58544ea0998ee48bee867a`.
Lead independent-original readback audit SHA-256:
`3b61b36ec49b3bd570189ebf7602a3d9895518f776dc687156be2fbd08e59af8`.
These are passive receipt audits, not more candidate tests. Complete-patch review,
passive document gates and commit preservation are mapped separately in the issues.

## Next integration and unchanged delivery blockers

The next source-owned caller must bind actual same-call staging/seed returns,
registry identities and transitive private frames before creating distinct new
ownership. Existing `_StagingClosedGraph` does not traverse `StagingPrefix` or
`_StagingSequence`; capturing either alone is not a complete pin. This is a future
caller caution, not a request to redo accepted staging source or reopen its owners.

Producer launch, original successful product/same-home stop/actual outer return
and complete native retirement remain unexecuted. Future collection must retain
original start/receipt, four product/stop logs, report manifest and exactly declared
optional reports, not fabricate Test XML or uninstall. The current canonical Tee
has no independent total-byte cap; bounded raw capture/collection and overflow
semantics need review before producer execution. A no-loader observation is not
an uninstall. Export/freeze/save/probe/encrypted custody/seal integration remains;
there is no bootstrap workflow or production `cache.export_snapshot`/`cache.save_set`
caller. Configuration-only help cannot satisfy ordinary ABI/simulator/transcript
acceptance. NativeFile900 and Snapshot576MiB remain unchanged, not a2GiB solution.

Complete paginated metadata at **16:55:04 UTC**:44 successful/hash-verified requests,
all29 compared domains unchanged from16:33;78 open issues, seven dependency PRs,
no campaign PR, no queried active Actions, and two RC Releases with **zero assets**.
Relevant #437/#424/#457/#143/#144 conversations/timelines, effective rules and advisory
were refreshed. Detailed dependency-PR reviews remain separately dated. Required
checks remain `complete-gate`, `review`, `scan / osv-scan`, `osv-scanner`; repository
review count0 does not waive the owner's formal different-account approval rule.

Both ordinary HOLDs remain. The missing named routine custodian, exact public key,
finite14-day legitimately trusted-original-base policy and formal approval are
unresolved; candidate source cannot authorize itself. Genuine native/provider/
resolver/custody/scheduling/delivery qualification and normal checked/reviewed main
merge with preservation still precede development sample Releases.

No build/download, held dispatch, PR/merge, Release, settings change or issue closure
occurred here. Preview35070982169 was not rebuilt/redownloaded; its APK/MSI/ARM64-DMG/
DEB remain older Actions artifacts expiring September30. #424 writer35066719641/1
already passed CLI9/diagnostics23 with six inspected originals; no repeat or downgrade.
#372's20 Kotlin tests remain uncompiled/unexecuted. OSV remains **EXCEPTED_NOT_FIXED**,
Kotlin2.4.10 affected, expiry2026-10-31; no scan/remediation/extension. Physical phones
and production/Maven/Store publication remain excluded. Protected instructions,
RC history, compatibility limits and unrelated work/proposals stay unchanged.
Historical206/234 repair-approved,207/234 resolved; audit/release **NOT_READY**.
