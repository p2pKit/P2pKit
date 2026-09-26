# Release Foundation ordinary workflow migration

**Status: source and focused offline results independently reviewed; the initial
failed packet is preserved. Neither ordinary activation HOLD nor the whole-JVM Stage2
interlock is lifted. This is not a one-shot 9/9 aggregate or hosted qualification.**

This increment connects the preserved ordinary FULL/Desktop custody composition
to the newer Release Foundation without importing the historical campaign
workflow menu. It resolves the direct-FULL caller incompatibility recorded in
the [cache extraction note](release-foundation-cache-prerequisites-2026-09-26.md),
but is not provider, custody, bootstrap or Release qualification.

## Source provenance and scope

- Foundation parent: `85f220c4921e2e0503be99ec9e30e17f81b751c9`, tree
  `72a0fccc9a1996d8396a0f838821081f3526f9fd`.
- Isolated implementation branch:
  `work/ordinary-wiring-foundation-20260926.8gxNHeiN`.
- Exact prerequisites applied without committing before this delta:
  - `8831e589176aa0b3f2df3b8810d070abf46f3ec6`: source extraction;
  - `694685b9d2515995a415d70adce9190c650ac883`: schema3 consumer adaptation;
  - `3006e6915aeb3d9ca3f1b7c6569ea5f1131755a5`: separately reviewed composition
    binding and source controls.
- Their combined index tree on this Foundation parent, before ordinary edits:
  `0ebe165414804805c60573b917d8992f3c568998`.
- Ordinary workflow/policy donor:
  `72cae80c0057257dd0b32b4b91cdcb8449734afc`.
  Files are adapted selectively, not a donor merge or a wholesale Desktop
  workflow replacement. The two prerequisite notes retain their original dated
  evidence and limitations; they do not qualify this new composition.

The ordinary delta is limited to these **21 files**:

| Group | Files |
| --- | --- |
| Four workflows | `.github/workflows/ci.yml`, `.github/workflows/desktop-cross-host.yml`, `.github/workflows/ios-x64-tests.yml`, `.github/workflows/dependency-submission.yml` |
| Queue policy and controls | `scripts/check-heavy-job-queue-policy.rb`, `scripts/tests/check-heavy-job-queue-policy-test.rb` |
| Ordinary caller policy and controls | `scripts/check-hosted-test-workflow-policy.rb`, `scripts/tests/check-hosted-test-workflow-policy-test.rb` |
| Sample workflow policy and controls | `scripts/check-sample-app-workflow-policy.rb`, `scripts/tests/check-sample-app-workflow-policy-test.rb` |
| Existing gate/fixture migrations | `scripts/check-android-abi-guard.sh`, `scripts/tests/check-android-abi-guard-policy-test.sh`, `scripts/tests/check-kotlin-toolchain-policy-test.sh`, `scripts/tests/check-platform-test-policy-test.rb`, `scripts/tests/check-jvm-cross-host-policy-test.rb`, `scripts/tests/run-platform-tests-test.py` |
| Input-free manual identity and controls | `scripts/hosted_test_identity.py`, `scripts/tests/hosted-test-identity-test.py` |
| Existing aggregates | `scripts/run-release-gate.sh`, `scripts/tests/release-workflow-test.sh` |
| Source/evidence status | This maintenance note |

No product, fixture Kotlin, packager/version producer, Maven/recovery/publisher
workflow, key, recipient policy, repository setting or protected instruction is
changed by this delta. The CLI9/diagnostics23 fixture postimages already retained
by Foundation commit `14605296` are not recopied or rerun. Historical reader,
current-authority, canonical, fixture and preview results remain limited to their
original source/input/environment scope.

## Actual ordinary callers and retained gates

Both FULL and Desktop keep the literal failure:

```text
ORDINARY_TEST_ACTIVATION=HOLD; QUALIFIED_DEPENDENCY_CACHE_REQUIRED
```

Behind that HOLD they call the existing source admission, original job timing
and consume-plan preparation, exact pinned cache restore without fallback or
save, restore guard, private controller, separate post-return seal, original
before/upload/after guards and complete terminal result guard. Only
`prepare-consume` receives the read token. FULL retains its 60-minute job;
Desktop retains its 30-minute job and native three-host matrix. Required task
selectors, wrapper Java17/daemon Java21, native Xcode/SDK choices, strict
dependency verification and original timing/ownership checks are not relaxed.

Desktop has one `verify` job, input-free manual dispatch, unfiltered main pushes
and PR paths covering its suppliers, sample/library sources and version/policy
inputs. This is an explicit identity-contract adaptation: absent, null or empty
manual inputs are admitted; any submitted legacy campaign field, even empty,
or arbitrary override is refused before policy acquisition. Ordinary manual
runs still obtain their recipient policy only from actual main, not inputs.
No preview, lock writer, phone, probe or campaign-menu job is imported.

The whole-JVM fail-only interlock is retained as a separate job with no checkout,
credential, protected environment or heavy lease:

```text
INITIAL_RECIPIENT_STAGE2=HOLD; WHOLE_JVM_JOB_ADMISSION_REQUIRED
```

JVM tests depend on it. `complete-gate` remains `always()` and first requires the
actual successful JVM dependency result, so a skipped JVM job cannot give a
successful required check. The interlock does not pretend to implement Stage2.

Existing gates move from old direct YAML commands/raw uploads to the selected
executable owner, rather than disappearing:

| Previous assertion | Current ownership and retained requirement |
| --- | --- |
| Direct FULL invocation | Exact FULL caller policy plus unchanged executable composition binding; standalone tag/release FULL remains direct |
| Android ABI YAML flags/tasks | Selected ordinary primary ABI owner, all three comparisons and unflagged graph ownership; release/tag direct path remains |
| Desktop task strings in YAML | Bound custody controller retains actual tasks and options; caller/policy controls reject inserted direct/cache/cleanup/preview routes |
| Raw iOS failure, SBOM and XCFramework uploads | Bound private FULL supplements retain originals and disposition; selected caller uploads only sealed evidence and safe manifest through original guards |
| Ordinary project-generation command in YAML | Bound FULL supplement; the standalone release gate keeps its existing direct regression call |
| Previous aggregate lists | New source controls added while all newer Foundation/version/schema3/package/publisher/frozen-set/bundle/deployment/recovery/topology registrations remain |

The FULL prefix policy uses explicit expected step mappings, not expectations
derived from the workflow under test. The exact tail, closed Desktop topology,
input-free event contract and actual executable composition are independently
asserted. All seven composition expectations are unchanged by this delta.

Sample production still requires exact ordinary admission of the case-sensitive
`[release ci]` marker in the actual main merge commit. Required CI does not
require that marker. Unencrypted sample bundles have their separate guarded
delivery paths; encrypted evidence remains separate. Source wiring creates no
public Release and does not authorize publication.

## Synthetic fixture isolation and scheduling scope

The standalone fake-wrapper lifecycle fixture previously inherited the outer
runner's `GITHUB_ACTIONS=true` / `GITHUB_JOB=complete-gate` identity and could be
refused before its fake Gradle invocation by the required canonical-context
guard. Its synthetic environment now allowlists only process essentials and
the fixture mode. It does not mutate production environment admission or copy
outer identity, ownership, credentials, Gradle home or simulator bindings into
the unrelated fake invocation. Explicit controls retain ordinary missing-context
refusal and tag-label/partial-marker anti-fallback coverage. The new environment
controls check isolation and preservation of the outer environment.

Five participating jobs across four workflows share the existing exact
`p2pkit-nonphysical-heavy`, `queue: max`, `cancel-in-progress: false` job lease:
CI JVM, CI FULL, Desktop, native Intel and dependency submission. Matrix maximum
parallelism remains one. Intel and dependency submission change only by adding
that job-level queue. Workflow supersession remains separate and unchanged;
this is not a claim that it cannot cancel its own older run. The source policy
rejects duplicate/merge YAML keys, conflicting participants and reserved-group
reuse. Future bootstrap jobs are not silently added to this closed roster;
their integration needs separate reviewed coverage and genuine timing evidence.

## Verification status and remaining blockers

Before first execution, only source/Git/shell inspection, prerequisite
provenance, hashes and whitespace checks had been performed. The lead's
independent implementation verdict was
`APPROVE_EXACT_ORDINARY_WIRING_SOURCE_A9C7BDBF_ONLY_NOT_ACTIVATION` against index
tree `a9c7bdbfb7affc40ecedeb80b1f8c931a9941879`. The following two bounded offline
packets then ran; earlier prerequisite passes were not substituted for these
new-workflow controls.

### Initial packet: first failure retained, not retried automatically

Packet `ordinary-wiring-controls.R2XmVomi` executed only the first three of nine
planned top-level invocations at the reviewed tree:

1. `bash -n scripts/run-release-gate.sh`: exit0, syntax PASS only.
2. `bash -n scripts/tests/release-workflow-test.sh`: exit0, syntax PASS only.
3. `ruby scripts/tests/check-heavy-job-queue-policy-test.rb`: exit1, stopped at
   `queue mutation had no effect: ci.yml max-parallel=1.0`.

Invocations4–9 were not started. The cause was the new fixture's mutation-effect
precondition: Ruby deep `==` treats integer1 and float1.0 as equal, although the
actual queue policy correctly requires an `Integer`. It was a fixture failure,
not an observed queue-policy acceptance or a resource-limit failure. No partial
heavy-suite pass count is claimed. The original failure-output SHA-256 is
`cf80cadb271a6a7ac4dad1e8c3d087dd8718e366c703ba329de05c3b8ca08191`.

After independent plan review, exactly one test line changed to compare
`Marshal.dump(changed)` with the existing frozen `original` Marshal snapshot.
The actual policy, Integer requirement and complete adverse roster stayed
unchanged. The lead independently reviewed successor tree
`d86c8686191ee3c78fd70f7d77bbfc4240655c8a` with verdict
`APPROVE_EXACT_TYPE_SENSITIVE_QUEUE_FIXTURE_SOURCE_ONLY` before further execution.
The repaired test SHA-256 is
`65a089c87adf204e33709350aa7f1132b2c9df00df3f6b4b0a2a59d584ff84ca`.

### Successor packet: seven remaining invocations passed

Packet `ordinary-wiring-controls-fixed.VciVk4UB` ran invocations3–9 once at the
reviewed successor tree, stopping on any unexpected failure. All seven exited0.
The two already-passed syntax invocations were not repeated; their files were
unchanged by the fixture repair.

| Original invocation | Exact entrypoint/selection | Result |
| --- | --- | --- |
| 3 | `ruby scripts/tests/check-heavy-job-queue-policy-test.rb` | 205 regression controls PASS |
| 4 | `ruby scripts/tests/check-hosted-test-workflow-policy-test.rb` | 560 offline policy/synthetic-shell controls PASS |
| 5 | `ruby scripts/tests/check-sample-app-workflow-policy-test.rb` | 122 pure policy controls PASS |
| 6 | `python3 -I -B -S scripts/tests/hosted-test-identity-test.py -f IdentityTests` | 33 selected unittest methods PASS |
| 7 | `ruby scripts/tests/check-platform-test-policy-test.rb` | 32 policy controls PASS |
| 8 | `bash scripts/tests/check-kotlin-toolchain-policy-test.sh` | Maintained source-policy aggregate PASS; nested coverage below |
| 9 | `python3 -I -B -S scripts/tests/run-platform-tests-test.py -f OrdinarySimulatorModels DriverFixtureEnvironmentModels DriverLifecycleTest` | 34 selected model/fake-wrapper unittest methods PASS |

The nested entrypoints were not hidden extra production executions:

- Invocation3 executed the queue CLI twice, JVM policy three times, CI-scope
  policy three times and scope classifier three times. Each three-call policy
  set contains its full positive baseline and two expected input refusals.
- Invocation4 launched 381 synthetic Bash guards as part of its 560 controls;
  its modeled Python calls are shell stubs, not the custody controller.
- Invocation8 executed the host-toolchain CLI88 times: one real-source policy
  check and87 fixture calls within ten unittest methods. It ran one24-case ABI
  policy fixture (one positive,23 deliberate refusals), plus one real-source
  static ABI guard. Across those paths, the actual source composition checker
  ran21 times and the FULL caller policy22 times, including deliberate adverse
  inputs. Five Python-stdin helpers mutated temporary supplier text; they did
  not execute those suppliers. The consumer/version policy CLIs and41 version
  negative controls passed; three existing shell files received syntax-only
  checks. No ABI compiler or Gradle graph was executed.
- Invocation9's24 wrapper starts all targeted owned temporary fake-wrapper
  fixtures, not the repository wrapper. No Kotlin test, simulator, native
  provider, previously passed1,066-file reader or unrelated process-group
  qualification was repeated.

Both packets used an allowlisted environment, isolated temporary directories
and effective UID0 limits set immediately before execution, with no privilege
transition: CPU60seconds **per process, not aggregate**, address space1GiB,
regular file16MiB,512 descriptors and no core dumps; wall120seconds per
invocation with a five-second termination grace and900seconds per packet.
Execve-only trace records retained child argv, not environment values. The
successor's measured summed child CPU was51.175308seconds and total packet wall
time63.206202seconds. These are external offline-probe safety budgets and
measurements, not new native/Release requirements. Every recorded before/after
source binding matched; no observed execve PID remained when checked afterward.

Successor preserved-record SHA-256 values:

- Results: `5d24e94e87f9f79f2bed99ddebf39bff8099caefb7314987e53ea88cbfdf981d`.
- Summary: `7b85ea35fbd315d96fc3c4e39534dc61c1f30a17aedd9a77cf5046de5b2d3d40`.
- Logical execution inventory:
  `0e810301d0626c2a894f719841fa1c9a2c0a7a28c78a040196c76375b00e698f`.

The inventory distinguishes a shell script's shebang/interpreter execs from
one logical script start, and Python-stdin mutation inputs from executable
suppliers. Original logs remain outside source; no raw packet is published by
this note. The lead independently reviewed the original packets with verdict
`APPROVE_EXACT_ORDINARY_OFFLINE_RESULTS_D86C8686_ONLY_NOT_ACTIVATION`.
This note-only successor does not change tested executable bytes.
No real Gradle/Java/Xcode/application build, download, CI, provider, encryption
or private-key operation was performed. The complete release gate and complete
script aggregate have not been run by this increment.

Remaining hard dependencies include the real Stage1 typed-origin/current-return
and productive provider/custody bridge, genuine canonical initialization and
runner continuity/timing, original producer/retirement/export/freeze/save/probe
evidence, Stage2 original acquisition/qualification and whole-job admission,
trusted-main recipient policy delivery and actual required checks/approvals.
Old integration-ref/source bindings are not silently reauthorized for Foundation.

The public recipient policy's September21–October5 finite window is unchanged;
calendar time alone is not activation. Bootstrap 5,400 seconds remains
unadmitted/unmeasured; native-file lifetime900 seconds and Snapshot576MiB remain
unchanged. Configuration-only execution cannot substitute for ordinary ABI,
simulator or transcript acceptance. Qualified cache bytes do not reuse test
results. No HOLD removal, required-check/settings change, personal owner
approval, merge, publication, issue closure or Release readiness is claimed.
