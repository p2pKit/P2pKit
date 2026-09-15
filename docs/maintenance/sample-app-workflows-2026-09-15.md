# Sample-app workflow source milestone — 15 September 2026

**Dated evidence, not a mutable status ledger or a claim that main builds apps.**
This supplements the [consolidated continuation](nonphysical-continuation-2026-09-15.md).
GitHub [#437](https://github.com/p2pKit/P2pKit/issues/437) and
[#438](https://github.com/p2pKit/P2pKit/issues/438) own subsequent decisions and delivery evidence.
Both are **ACTIONABLE_NONPHYSICAL / OPEN**, with the execution holds below.
Held builds, dependency acquisition, emulators and CI dispatches were not restarted.

## Exact source and tracker snapshot

Continue on **`work/nonphysical-integration-20260915-022112`**. These are coherent,
separately reviewed commits on that integration branch, not changes merged to main:

| Source | Commit | Tree |
| --- | --- | --- |
| Main, remotely rechecked 2026-09-15 11:10 UTC | `3bc76f956f8f47447b51a62474fc878b9c43173c` | `2a1105fde1d1ac299448489501e29d7a0d4a407a` |
| #437 sample workflow | `7497df07cd98fa44fdc0c361b3c2e5b7a44819eb` | `87991f8cd03cf245128d10b603763df32e618c3e` |
| #438 consumer source-policy correction | `e3084393cb915e5e30d4b2567b000d2516e7d53d` | `debe57fa3c4bc85348252d3bfb6c4f3e8b3b1c84` |

Every file in each focused review binding was read back from its commit and
hash/length matched: twelve inputs for #437 and thirteen for #438. The latter
includes the actual unchanged consumer script and fixture helpers. This document's
containing commit adds documentation only; it does not manufacture execution evidence.
Protected `AGENTS.md`/`CLAUDE.md`, library/consumer behavior, dependency locks,
verification metadata and ABI baselines are unchanged by these two repairs.

The 11:10 UTC remote inventory contained **60 open issues, six dependency PRs,
no campaign PR and eight remote branches**: main, integration and the six retained
dependency proposals. Complete #437/#438 bodies, comments and timelines were
refreshed through **11:11:36 UTC**: both unchanged, open, with zero comments/events.
Other complete conversations remain the dated evidence in the earlier continuation;
this small refresh is not another all-history download. No additional branch deletion
is needed or performed here. The earlier branch-deletion hold is historical; the
owner's later separately authorized consolidation cleanup is not undone by it.

Historical accounting stays **206/234 repair-approved (88.0%)** and **207/234
historically resolved (88.5%)**. #437/#438 are outside that denominator. No closure
credit is added. **Whole audit/release: NOT_READY.**

## #437 — downloadable development samples

Main's Desktop workflow already requested sample test/distribution tasks, but had
no main-push trigger or application upload. Main CI did not explicitly assemble
and retain the Android sample APK. A consumer APK is not the sample application.

The repair extends the existing [Desktop workflow](../../.github/workflows/desktop-cross-host.yml):

- Relevant main/PR paths and ordinary manual operation; original three native
  hosts, job names, six Desktop tasks, shared queue and witness/admission isolation remain.
- Android `:p2p-sample-android:assembleDebug` joins **only Linux's** existing Gradle batch.
- Explicit Java 21 then Java 17; strict verification, two workers, no parallel
  Gradle, in-process Kotlin and no automatic JDK acquisition.
- An exclusively created job-owned Gradle home, same-wrapper/home finalization,
  and packaging/upload only after successful build **and** stop.
- Complete UI runtime images and CLI distributions; Linux also retains the
  Android debug APK. Native images are archived before upload to preserve modes/links.
- Commit/tree, actual run/attempt/job/OS/architecture, manifest/checksums and
  notices accompany the outputs; artifact retention is fourteen days.

The [packager](../../scripts/package-sample-apps.py) bounds archive parsing,
rejects unsafe/missing inputs and checks archive bytes, native headers/layout and
APK ZIP/CRC. It does not launch applications or validate an APK signer/binary
manifest. These are not installers or production-signed/notarized releases.
See the [sample download guide](../guides/samples.md#download-development-apps-from-actions).

### Actual offline evidence

Host: native arm64 macOS 26.2 (25C56), Python 3.9.6, Ruby 2.6.10.
For the commands below, `PYTHON` was
`/Applications/Xcode.app/Contents/Developer/usr/bin/python3`.

| Executed command/check | Observed result and limit |
| --- | --- |
| `"$PYTHON" -I -B -S scripts/tests/package-sample-apps-test.py` | **24 tests PASS** after repair, 0.126 s; synthetic/offline fixtures, not real app artifacts. |
| `ruby scripts/tests/check-sample-app-workflow-policy-test.rb` | **71 pure controls PASS** on final workflow bytes; rerun after #438's shared-entrypoint changes also passed. |
| `ruby scripts/tests/check-windows-directory-control-policy-test.rb` | PASS; source/mutation policy, not a Windows run. |
| `ruby scripts/tests/check-heavy-job-queue-policy-test.rb` | PASS; source policy, not observed hosted scheduling. |
| `ruby scripts/tests/check-mac-host-admission-policy-test.rb` | PASS; source policy, not host admission. |
| `ruby scripts/tests/check-ci-scope-policy-test.rb` | PASS; source policy, not hosted CI. |
| Private `lint-bash.rb` extractor, run using `ruby` | Seven YAML-derived Bash blocks passed `bash -n` and ShellCheck; extracted bodies were **not executed**. |
| `/opt/homebrew/bin/actionlint -oneline -no-color -shellcheck= .github/workflows/desktop-cross-host.yml .github/workflows/ci.yml` | **Exit 1 retained** with exactly five existing `queue: max` schema diagnostics in actionlint 1.7.12; not a lint/full-gate pass. |
| `git diff --check`, later `git diff --cached --check` | PASS for the reviewed/staged changes. |

The independent first review found ZIP64/false-count preallocation bypasses and
omitted wrapper/checkout trigger inputs. Three newly added `PackageFixtures`
methods (`test_zip_preflight_rejects_zip64_override_before_zipfile`,
`test_zip_preflight_counts_actual_records_before_zipfile`,
`test_zip_preflight_validates_record_extents_and_no_zip64_entries`) were actually
run together with the same Python prefix against the pre-fix packager: **exit 1,
fourteen failing assertions/subtests**. The pre-fix policy also exited 1 at missing
`push` input `gradlew`. Final passing results above are separate records.

Real actionlint additionally rejected the draft's job-level `runner.temp` context.
Moving exclusive home creation/export into the prepare step removed that diagnostic.
The five older schema diagnostics remain; expected-nonzero accounting is not success.
All findings were resolved before scoped source approval. No full release script,
real sample build, artifact upload/download or launch was executed for this candidate.

## #438 — false consumer-policy rejection

The actually executed `bash scripts/tests/check-kotlin-toolchain-policy-test.sh`
initially exited **1**: `the isolated publication fixture may leave a Gradle daemon
racing cleanup`. The guard still required literal `publishToMavenLocal`, although
the unchanged consumer correctly selects `publish_tasks` for complete/default or
the explicit five-task LAN profile. All four ordinary/executor publication and
consumer-build calls already retained `--no-daemon`. This was a **stale assertion,
not an observed daemon leak**; the two pre-repair files also matched main.

The [replacement checker](../../scripts/check-consumer-gradle-policy.rb) independently
pins those four maintained call forms and task selection. It rejects lost/extra
flags, omitted/commented/changed calls, ignored failures and altered arrays.
Pure controls also catch removed/commented/ignored invocation. Both outer release
test entrypoints call the controls. Actual consumer behavior and other Kotlin,
version, checksum and real Android ABI-graph checks are unchanged. The checker
is deliberately a source-format tripwire, **not a general Bash parser or proof of
actual daemon retirement**.

### Actual corrected checks

All **twelve selected command records exited 0**:

- `ruby scripts/check-consumer-gradle-policy.rb scripts/check-published-consumers.sh`.
- `ruby scripts/tests/check-consumer-gradle-policy-test.rb`: **43 pure controls PASS**.
- `bash scripts/tests/check-kotlin-toolchain-policy-test.sh`: PASS, including its
  unchanged version-input negative controls and static ABI/toolchain checks.
- Four individual invocations of `"$PYTHON" -I -B -S scripts/tests/audit-consumer-test.py`
  with the exact method arguments below; one test OK per invocation.
- `ruby scripts/tests/check-sample-app-workflow-policy-test.rb`: **71 controls PASS**.
- `bash -c 'bash -n scripts/tests/check-kotlin-toolchain-policy-test.sh && bash -n scripts/run-release-gate.sh && bash -n scripts/tests/release-workflow-test.sh'`.
- `/opt/homebrew/bin/shellcheck scripts/tests/check-kotlin-toolchain-policy-test.sh scripts/run-release-gate.sh scripts/tests/release-workflow-test.sh`.
- `bash scripts/tests/check-repository-layout.sh` and `git diff --check`.

| Exact existing fixture method argument | Recorded duration |
| --- | --- |
| `ConsumerGateTest.test_default_keeps_exact_two_commands_and_disposes_work` | 4.161 s |
| `ConsumerGateTest.test_focused_profile_uses_only_five_publications_and_exact_embedded_tasks_without_native_tools` | 0.831 s |
| `ConsumerGateTest.test_supported_borrowed_adapter_preserves_argv_cwd_home_and_retains_work_and_receipts` | 3.648 s |
| `ConsumerGateTest.test_focused_executor_keeps_exact_tasks_and_stops_each_leaf_with_retained_receipts` | 3.083 s |

Those four tests execute the real shell recipe with **fake Gradle/Xcode/curl
boundaries and synthetic artifacts**. They prove selected argv, cwd/home and
fixture retention/finalization behavior, not dependency resolution, publication,
consumer compilation, native lifetime or runtime success. Other fixture methods
and the whole `release-workflow-test.sh` were not executed for this narrow repair.
The original failure remains retained; it is not rewritten as a pass.

## Independent review and source-bound reuse

| Review, independent of implementation | Verdict | Private report SHA-256 |
| --- | --- | --- |
| `review_sample_workflow`, final follow-up | `APPROVE_SCOPED_SOURCE_AND_OFFLINE_GUARDS` | `e86077a0927c1343ad2cf6035d823e592cb9c801b5008f43ce2a8893ef6d009c` |
| `review_consumer_policy_438` | `APPROVE_SOURCE_AND_OFFLINE_SCOPE`, no actionable findings | `f26cf97a25e7fda7c6f1acd6c7cba544ec4320e973068c3d736e921b0b3d6c35` |

Reviewers inspected exact source, complete supplied issue conversations, failure
paths and original command/stream hashes. Neither started tests/builds/downloads.
These are **not formal GitHub PR approvals**, runtime acceptance or closure verdicts.
A separate combined source/public-evidence review and remote preservation result
are to be linked on the issues with this document's containing commit.

Private packet handle: `main-sample-builds-fzt_6pq7`. No raw receipts or payloads
are committed. Retain these identities for private owner-approved evidence transfer:

| Binding/result | SHA-256 |
| --- | --- |
| #437 final `offline-r3/SOURCE-INPUTS.json` | `f8214ed527ceafaa7a901cd0d36a1bcc6b8075c814179d2ae843f47e875d7017` |
| #437 final `offline-r3/RESULT.json` | `48a5d2d380dc25e157eb799eedc82c26765a3ad43648e317d15d2c055864b2d3` |
| #438 `consumer-policy-438/SOURCE-INPUTS.json` | `eef7cf0d8c0d6092380140b1f9249592e63aed09665f5524ea9dd51a82e9eed5` |
| #438 `consumer-policy-438/RESULT.json` | `9ad82d8114566feca58426d0022339228cd806aae8447565f1c91c6d3a362be5` |

The 24-test packager result was reused from R2 only after its implementation/test
bytes were hash-matched at R3 and commit. Changed workflow bytes received fresh
R3 policies/lint; #438's shared-entrypoint delta received the 71-control rerun.
Future source changes require a new binding and checks for affected risks, not a
borrowed old commit's green result. No historical full/native gate is promoted here.

Dependency/wrapper caches remain supported, while the affected Kotlin build cache
is excluded. Compatible sample tasks share one Gradle batch **per real host**, not
one Mac build pretending to produce Windows/Linux proof. Cache reuse is neither a
zero-download promise nor permission to copy another machine's products or relax
locks/provenance. No dependencies were acquired during this offline milestone.

## Unwaived blockers and exact resumption boundary

1. **Strict locks:** main run [34830657874](https://github.com/p2pKit/P2pKit/actions/runs/34830657874),
   jobs `103932958484` and `103932958641`, failed at
   `:p2p-transport-lan:compileKotlinJvm`: unresolved locked `org.jmdns:jmdns:3.6.3`.
   Original logs were inspected, not rerun. Six stale memberships still require
   the **complete maintained writer**, independent provenance review and applicable
   scan/submission. Do not hand-edit locks, re-add removed dependencies, disable
   verification or promote partial writer outputs.
2. **#424 custody:** existing CLI `check` executes `CliShutdownTest`. Its
   [owned test-JVM temporary-root, retirement and private transcript-retention contract](../testing/local.md#subprocess-transcript-custody-on-failure)
   remains required. No portable checked-in outer initializer/retention envelope
   supplies it yet. App uploads, daemon-only temp settings or `--stop` alone are
   not that proof. Eleven new #424 methods remain uncompiled/unexecuted; diagnostics
   tests are not run just because the Desktop sample depends on diagnostics.
3. **Hosted acceptance:** after those prerequisites and explicit resumption of held
   execution, obtain genuine current Android/Windows/macOS/Linux builds and inspect
   retained source-bound archives/manifests. Native toolchain/host admission and
   cleanup holds in the earlier continuation still apply. No physical phone is needed
   to compile these apps; physical-phone campaigns remain deferred, not substituted.
4. **Reviewed delivery:** effective main rules were refreshed: strict up-to-date
   `complete-gate`, `review`, `scan / osv-scan`, `osv-scanner`, PR/thread-resolution
   rules and no force/deletion permission. The legacy branch-protection endpoint
   returned HTTP 404; effective **ruleset** protections remain present. The configured
   reviewer count of zero does not waive the owner's formal PR-review requirement.
   Opening a PR triggers held checks, so none was opened. No merge, bypass or closure
   is authorized by a source-only approval. Preserve the integration branch until
   accepted normal merge and source-preservation proof.

Current advisory metadata still lists **GHSA-r937-wjx7-w2jp / CVE-2026-53914**, not
withdrawn, affecting the current Kotlin 2.4.10. Status remains **EXCEPTED_NOT_FIXED**,
exception expiry **2026-10-31**; no qualified upgrade, fresh OSV scan or remediation
is claimed here. Production publication, tags/releases and settings changes remain
outside scope.

Recorded offline commands retired their direct children/owned process groups;
their owned fixture temporary roots were removed and shared leases released.
That is not host-global native retirement. No real Gradle daemon, emulator or
simulator was started. Required evidence and useful dependency caches are retained.
The observed disk reserve was approximately 39 GiB; no large cleanup was performed.

To resume elsewhere, fetch the integration branch normally, inspect local changes
before switching, read this report and the linked issue conversations, then use
the [Mac handoff](../testing/mac-handoff.md). Do **not** automatically run a writer,
build, emulator or workflow dispatch. First obtain permission to resume held
execution and resolve the listed ownership/input prerequisites. Complete applicable
checks and formal review, merge normally, verify preservation, then close **only**
issues whose entire current acceptance criteria are satisfied.
