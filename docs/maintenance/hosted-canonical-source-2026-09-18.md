# Shared canonical source preparation — 18 September 2026

**Source/offline scope only; apps are not in repository Releases.** This follows
the [recipient-parent increment](nonphysical-source-resume-2026-09-17.md#18-september-internal-recipient-only-parent-and-bounded-cleanup)
at `1fc4d4f2aaf08c04dbd9acbac4746e3f5fc42ed1`. The containing commit and final
complete-patch verdict will be mapped after review and remote preservation in
[#437](https://github.com/p2pKit/P2pKit/issues/437), with the shared prerequisite
recorded in [#424](https://github.com/p2pKit/P2pKit/issues/424).

## Bounded implementation, not initialization

Importing the entire ordinary controller just to reuse canonical argv would
expose the bootstrap adapter to its unrelated sibling/module/bytecode graph.
`-B` prevents bytecode writes, not reads. The minimal shared extraction instead
keeps the existing two-supplier canonical child-loader literal byte-identical.
Both callers compile only captured, bounded helper bytes checked against their
separately retained source hash; no ambient alias, import path or cached bytecode
selects this helper. Ordinary binding/error/encoding/argument behavior is retained.

The new bootstrap `init_request` only describes fixed canonical initialization
argv for the current interpreter and supplied finite state/source/role labels.
It creates no state/home, imports no ordinary controller, executes no command,
consumes no `RecipientPrefix` and grants no next-phase/export/save authority.
Its source/interpreter rechecks are point-in-time observations, not admission,
state ownership or a filesystem freeze. See the
[cache contract](../testing/hosted-dependency-cache.md#shared-canonical-argv-not-bootstrap-initialization).

Exact implementation SHA-256 values (under `scripts/`):

| File | SHA-256 |
| --- | --- |
| `hosted_canonical_python.py` | `432c06f0be8f98db286979b7adc58365d9eafde739c023ac13af1f227acaeba4` |
| `hosted_cache_bootstrap_canonical.py` | `3e9f4c5cd99aca8c1e28625f7f811ca2a866ef170ff81fc7401d35a9111f15d4` |
| `run-hosted-test-custody.py` | `211fbaf9be2630a3e5b503cb00f2a8704c6035ad4b9a68ef89f6b4d574910bb3` |
| `hosted_dependency_seed_files.py` | `96f1373a42b83ad93803f1036e90e2ffb02360050a8270468e9d74335b519a9b` |

The shared helper is an additional **source/seed-provenance** input, not a third
canonical child supplier or a new reusable provider-key component. The semantic
allowlist/wrapper/profile/role key remains unchanged. Independent core review
explicitly authorized the two changed composition expectations and additional
seventh supplier; the other four suppliers and normalization/check algorithm
are unchanged. CI/release-script registration and Desktop path-filter controls
cover the new focused test. Neither ordinary activation HOLD is lifted.

## Executed checks and retained failures

Python3.12.3, actual UID65534, serial externally bounded source tests. Author
command envelope: `timeout --kill-after=5s 90s runuser -u nobody --` followed by
the command below against an exact source copy. Tiny POSIX files are real;
native/Git/GPG/service/provider/product execution is modeled or prohibited.
The Ruby policy suite also executes its bounded synthetic HOLD/terminal shells,
not a workflow or product. No generated initializer argv ran.

| Command under the source copy | Actual result |
| --- | --- |
| `python3 -I -B -S scripts/tests/hosted-canonical-python-test.py -v` | Corrected author R2 **32/32 PASS**, 0.520s unittest. |
| `python3 -I -B -S scripts/tests/hosted-controller-import-test.py -v` | R2 **4/4 PASS**, 0.358s. |
| `python3 -I -B -S scripts/tests/hosted-test-controller-test.py WholeControllerModels.test_desktop_whole_composition_and_post_return_seal_pass_in_model WholeControllerModels.test_seed_full_model_preserves_primary_supplement_abi_simulator_and_clock_contracts -v` | R3 selected **2/2 PASS**, 8.093s; not the whole controller suite. |
| `python3 -I -B -S scripts/tests/hosted-dependency-seed-files-test.py SeedFiles.test_source_inputs_reads_only_closed_roster_and_parser_remains_authority -v` | R3 selected **1/1 PASS**, 0.006s. |
| `python3 -I -B -S scripts/tests/check-hosted-test-composition-test.py -v` | R4 **20/20 PASS**, 13.358s, including four new methods. |
| `ruby scripts/tests/check-hosted-test-workflow-policy-test.rb` | R5 **524 controls PASS**. |
| `ruby scripts/tests/check-sample-app-workflow-policy-test.rb` | R5 **136 controls PASS**. |
| `ruby scripts/check-hosted-test-workflow-policy.rb` and `ruby scripts/check-sample-app-workflow-policy.rb` | Both R5 current source policies **PASS**. |
| `bash scripts/tests/check-android-abi-guard-policy-test.sh` | R6 **PASS**; all checker invocations use `--static-only`, no Gradle/ABI execution. |

Each run retained its complete 1,409-file source/fixture/repository manifests and
unchanged rosters. R1–R6 are exact private source freezes, not commit identities
or one combined test aggregate. The four implementation files above did not
change across them; later deltas are independently reviewed registrations,
tripwires, tests and documentation. Tests are reused only within those inputs.

Three failed originals remain separate:

- Author R1 **31 PASS /1 FAIL**, exit1. Its blanket import prohibition rejected
  Python3.12 `pathlib`'s lookup of already-loaded `ntpath`, before helper execution.
  The test-only correction allows only that exact stdlib lookup; all helper/
  other imports remain forbidden. No implementation/assertion was weakened.
- R4 hosted-policy **FAIL**, exit1, before its control loop. The independently
  frozen FULL-prefix expectation had not yet been updated for the one new
  offline command. Independent complete old/new YAML comparison authorized only
  the new exact prefix hash; the original 16-step tail/HOLD is unchanged.
- R5 Android static aggregate **FAIL**, exit1, on a fixture write. The recorder's
  0444/0555 source modes propagated through `cp` into the ordinary-UID-owned
  mutation copy. A new, exact-byte R6 copy uses root-owned 0644/0755 files and
  0555 directories; actual UID65534 still cannot write any source. No repository
  test/source/timeout changed for this correction. Only this suite was rerun.

Review also found an inherited Android fixture no-op: its old seed-mode removal
matched zero current CI lines. Static inspection preserved that fact, not a
fabricated failing test run. The corrected fixture requires the exact current
consume command once before removing it and retains the original rejection.

## Independent review and current boundaries

**APPROVE_EXACT_CANONICAL_CORE_SOURCE_AND_OFFLINE_ONLY**, report SHA-256
`696bac9cc4aa328830f515af9af563c28b70cc0431d54923a5420565ae0d3271`.
Independent controls were frozen before reading author assertions and passed
**28/28**, 0.597s unittest, under actual UID/GID65534 and a45-second external
bound plus5-second kill. Original stdout/stderr, failed/corrected author results,
complete manifests, caller parity and adverse cases were inspected without
replaying accepted tests. Explicit FULL-prefix review SHA-256:
`2673b7ec6fc2ddcea0c760c978c0e15cdc07a06f927c2b9f9c114380074be54c`.
Agent review is **not formal different-account GitHub PR approval**.

Complete paginated metadata at **10:59:21 UTC**: 78 open issues, seven dependency
PRs, no campaign PR, no queried active Actions and no Release app assets.
All29 inspected metadata domains match the10:39 originals, including complete
#437/#424/#457/#143/#144 conversations/timelines, effective rules and advisory.
Required contexts remain `complete-gate`, `review`, `scan / osv-scan`,
`osv-scanner`. Dependency-PR detailed-review originals remain separately dated.

Next is actual same-live-call canonical initialization with distinct pinned
phase/Owner/native resources, original proposal/job fences and failure custody;
initializer120 cannot renew recipient first315/read30 or revive its closed
prefix. Producer/stop/native retirement, positive streamed export, freeze,
provider save/probe and encrypted custody/seal remain unfinished. No production
caller invokes `cache.export_snapshot` or `cache.save_set`.

The named routine custodian, exact public key, finite14-day policy, legitimate
trusted-original-base bootstrap and formal approval remain absent. Candidate
source cannot authorize its own recipient. Both ordinary HOLDs stay;5400 is
UNADMITTED/UNMEASURED, Windows NativeFile900/Snapshot576MiB unchanged. Genuine
native/provider/resolver/custody/scheduling/delivery qualification, required
checks, formal approval and normal reviewed main merge/preservation still
precede development sample Releases. No build/download/dispatch, PR/merge,
Release, production/Maven/Store publication or issue closure occurred here.

Accepted preview35070982169 and #424 writer35066719641/1 were not rebuilt or
redownloaded; the four preview artifacts are still not Releases. #372's20 Kotlin
tests remain uncompiled/unexecuted. OSV remains **EXCEPTED_NOT_FIXED** through
2026-10-31; no scan, remediation or extension. Physical phones remain deferred;
protected instructions/history and unrelated dependency proposals are unchanged.
Historical accounting stays206/234 repair-approved and207/234 resolved;
audit/release remain **NOT_READY**.
