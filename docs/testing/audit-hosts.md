# Audit-branch hosted validation

The [audit host workflow](../../.github/workflows/audit-host-validation.yml) is an
additive, read-only execution facility for one frozen audit-branch revision. It
neither replaces normal CI/release checks nor records a successful execution by
being present. Inspect the actual run, retained evidence and independent review
before claiming any host result. The overall audit and physical/independent
acceptance remain pending.

The maintained [host driver](../../scripts/run-audit-host.py) runs **components**.
Its `releaseGateMonolith` value is `NOT_EXECUTED_COMPONENT_REPLAY`: the unchanged
[`scripts/run-release-gate.sh`](../../scripts/run-release-gate.sh) has **not** been
executed by this workflow. Individual real component results are not permission
to print that script's complete-release-gate PASS or publish a release.

## Trigger, source and execution ownership

Only a push to `audit/complete-2026-09-04` that changes
`.github/workflows/audit-host-validation.yml` requests this workflow. There is no
PR, tag, schedule or manual-dispatch trigger. A branch-only push can bootstrap the
workflow without merging it into `main`; do not merge or change repository settings
just to register a manual workflow. Helper/document-only pushes intentionally do
not request another expensive run. Change the workflow's documented run-revision
comment in a focused, reviewed push when a new exact source revision needs testing.

Before that push, the operator must:

1. Obtain independent source/execution-request approval before a verification
   push. Final repair approval additionally requires the resulting evidence;
   obtain it before starting the next repair. Review new execution infrastructure.
2. Reconcile the preceding terminal attempt and retain its evidence; refresh
   queued/running Actions and hold the audit's **global build lease**. Require no
   competing queued/running work before starting another independently allocated host.
   Pause local builds/tests and do not dispatch other workflows during this run,
   including cleanup and artifact retention. Do not cancel unrelated tasks.
3. Freeze the exact source and record the expected commit/tree. Inspect toolchain,
   disk/memory and external-access prerequisites; do not restore private evidence,
   credentials, machine settings or another user's cache into the checkout.
4. Push normally to the audit branch, then verify the run API's `head_sha`, each
   checkout/admission record and retained artifacts against that exact revision.

The single `selected_host` job uses `${{ github.sha }}`, full Git history and
`persist-credentials: false`. The token has only `contents: read`; actions are
pinned by full commit. Runtime admission also verifies repository, existing-branch
push, exact ref/SHA/tree, clean tracked/untracked state, ancestry, non-deletion and
non-force, and the workflow path in the actual before/after diff. A GitHub path
filter fallback is not permission to execute a different event. A zero-before/new
branch event is rejected rather than silently substituted with `main`.

A single non-cancelling concurrency group and **one literal native job** bound
this workflow. There is no matrix, selector, dispatch input or automatic Apple
chain. A later host requires a separate reviewed source change selecting its
native role, runner label, tools and budgets. The group cannot serialize other
workflows or local builds, and GitHub can replace an older pending run even with
`cancel-in-progress: false`. Do not queue another triggering push while a run is
active or pending; preserve earlier failure/cancellation records.

## Prior Apple native-compilation admission — revision20

Revision20 selects one `macos-26` job, `Audit native Apple compilation admission`,
using native ARM64 Python 3, Java 21 then 17, the checked-in `gradlew` and
`DEVELOPER_DIR=/Applications/Xcode_26.5.app/Contents/Developer`. This focused #413
prerequisite was **NOT_RUN** at selection time. Its later
[run34639822412/1](https://github.com/p2pKit/P2pKit/actions/runs/34639822412/attempts/1)
succeeded on `4973859d416c62246e303259bbaab21f4f854f0c` /
tree `2c8196da4417376c9b39df14c8c49d1727f8f442`: 91 ownership controls and
12/12 executed compilation tasks, including LAN production and test compilation.
The #413 candidate was absent. Independent review approved only baseline native
compilation admission and retained owned cleanup, not cancellation or ABI.

The unchanged native/non-Rosetta admission, resource and tool prerequisites,
complete real `executor-native-controls` leaf, and SDK platforms **36 and 37.0**
installation/metadata checks still precede the only requested product graph:

```text
:p2p-transport-lan:compileTestKotlinIosSimulatorArm64
```

The `413-native-compilation-admission` leaf compiles the selected source's native
production and test classpaths with their normal prerequisites; it does not run
tests or request test linking, frameworks, Swift, ABI, consumers, publication,
policies or a JVM product graph. It returns before XcodeGen or simulator selection.
No platform-test profile or test-count assessment is substituted for compilation.
Retain and independently inspect actual native compilation task outcomes in the
raw source-bound log; an aggregate PASS alone is not proof of fresh compilation.

Strict dependency verification, forced freshness, resource limits and same-home
wrapper stop/drain remain unchanged. The leaf keeps its default 3600-second bound;
the workflow keeps 180-minute job, 150-minute step and 8400-second driver budgets.
The unconditional finalizer validates receipts, performs proved-owned output/work
cleanup and seals evidence. An ordinary compilation failure remains FAIL; an
ownership, stop, source or cleanup failure cannot export safe continuation.

That compilation graph admitted strict locks; other graphs can still encounter
stale JmDNS lock entries. This scope
does not write locks, relax verification or request a producer fallback. Inspect
actual prerequisites rather than infer native-only resolution from the task name.
Compilation establishes no linking, simulator/runtime, Swift naming or cancellation
behavior. The later #413 helper/runtime and ABI gates remain required; in particular,
`checkKotlinAbi` also requires JVM compilation and is neither passed nor waived here.

Admission, summary and handoff retain `requestedScope=apple-native-compilation`
and `hostQualification=NOT_ESTABLISHED_BY_FOCUSED_SCOPE`, even on PASS. The release
monolith and external acceptance remain unexecuted/unvalidated. Prior selections
and retained outcomes below are not replayed, promoted or reset by this selection.

## Selected Apple owned-flow native helper — revision22

Revision22 selects the ARM-only `apple-owned-helper` route and job
`Audit native Apple owned Flow helper`. It is **NOT_RUN at selection time**;
request approval is not native execution or final #413 repair approval.
Keep `macos-26`, Java 21 then 17, Xcode26.5 and the unchanged 8400-second driver,
150-minute step and 180-minute job ceilings. The exact-source freeze and global
execution lease remain required before the triggering audit-branch push.

After the unchanged native/non-Rosetta, tool/resource, complete native ownership
controls and SDK36/37.0 admission, the only product leaf is `owned-flow-helper`:

```text
:p2p-transport-lan:iosSimulatorArm64Test --device <owned-shutdown-UUID>
  --tests dev.p2pkit.transport.lan.IosOwnedFlowCollectionTest
```

The shared `owned_flow_native` implementation uses explicit `aggregate_abi=False`
only for this scope. The original `apple-owned-cancellation` route still requires
its default aggregate ABI graph and assessment; it cannot opt out under that scope.
The fresh coverage token/init-script, `--continue`, strict dependency verification,
forced-fresh tasks and at-most-two-worker/no-parallel budgets are unchanged.
Exactly four unique successful helper methods, matching fresh retained XML/event
counts, zero errors/skips and no other modeled test task remain mandatory.
Compilation alone or a zero Gradle exit without those reports cannot pass.

Select one exact available **originally Shutdown** iPhone17, pass its UUID through
KGP's existing `--device` option and retain the pre-state. The shared `finally`
retirement observes and, when necessary, shuts down only that device, including
on failure/interruption; unknown retirement blocks continuation. Retain native
reports and product/stop logs before immediate owned-output cleanup, followed by
the unchanged unconditional finalizer and sealed handoff. A failed product or
assessment remains failed; safe cleanup is not test success.

This route returns before XcodeGen, project generation, framework/provenance,
Swift or other product graphs. It does not replay revision21's independent
framework/Swift28/isolated1 evidence, or request the known-failing aggregate ABI.
Earlier results retain their original source/run bindings and require reviewed
reuse; omitted work is not newly passed. Revision21's ABI failure remains failed,
and a successful **actual additive Apple aggregate ABI** gate remains required
for final #413 approval. No lock rewrite, relaxed dependency check or synthetic
native-only ABI substitute is introduced. The helper result records
`aggregateAbiRequested=false` and no `abiTasks`, explicitly leaving ABI required.

Admission, summary and handoff retain `requestedScope=apple-owned-helper` and
`hostQualification=NOT_ESTABLISHED_BY_FOCUSED_SCOPE`, even on PASS. This is not
full-host, release-monolith, physical-device or independent acceptance.

## Prior Apple owned-flow cancellation — revision21

Revision21 selected the ARM-only `apple-owned-cancellation` route and job
`Audit native Apple owned Flow cancellation`, separate from revision20's
compile-only admission and the failed raw revision18 probe. It was **NOT_RUN at
selection time**. Actual [run34647991698/1](https://github.com/p2pKit/P2pKit/actions/runs/34647991698/attempts/1)
on `43a67394b66601e81156d5aead6257c939f0a8f4` / tree
`112c92b8deb3e2dac32231473d4257abefd559e2` remained **FAIL**: native helper
compilation failed at three generic assertions before its four cases could run,
and aggregate ABI did not complete because of stale JmDNS lock membership.
Independent downstream framework/provenance and Swift **28 + 1** cases recorded
success with owned cleanup; they do not erase either earlier failure or supply
final #413 approval. The original route below remains available and unchanged in
scope; a new selection still requires exact-source and global-lease admission. Keep native
`macos-26`, Java 21 then 17, Xcode26.5 and the existing 8400-second driver,
150-minute step and 180-minute job ceilings. Do not silently select the larger
unselected constructor default.

After unchanged native ownership, SDK36/37.0, tool and resource admission:

1. Install the pinned XcodeGen and run one focused real project-generation check
   for the added app source, unchanged test containers, both ordinary test targets
   and mandatory provenance/local-network declarations. Do not replay the full
   policy suite or the two unrelated provenance-policy graphs.
2. Run one `owned-flow-helper-abi` leaf with the exact selectors:

   ```text
   :p2p-transport-lan:iosSimulatorArm64Test --device <owned-shutdown-UUID>
     --tests dev.p2pkit.transport.lan.IosOwnedFlowCollectionTest
   :p2p-transport-lan:checkKotlinAbi
   ```

   Select one exact available originally-Shutdown iPhone17 and retain its native
   pre-state. The KGP `--device` option binds this test leaf to that UUID without
   changing standalone execution. Observe and, if necessary, shut down only that
   owned device in `finally` before any framework work, also on failure or
   interruption. Unknown or failed retirement blocks continuation. Later Swift
   cleanup is not a substitute for this earlier native-leaf evidence.

   The normal fresh coverage token/init-script, `--continue`, forced freshness,
   strict verification and resource/finalization controls remain. The existing
   ARM LAN platform assessor checks the complete model; the focused assessor also
   requires exactly the helper's four unique successful methods, zero errors or
   skips, matching retained XML/event counts and no other modeled test task in
   the graph. It requires executed native-klibrary inputs for all three iOS targets
   and the actual aggregate `internalDumpKotlinAbi`/`checkKotlinAbi` task lines.
   Retain their full original logs; no per-target compare task names are invented.
   `checkKotlinAbi` also has JVM compilation/public-constant prerequisites, not a
   JVM test matrix. A finalized helper/ABI product or assessment failure remains
   **FAIL**, including a distinct failed assessment; no helper or ABI completion is
   awarded from that row. After proved owned stop/source/evidence finalization and
   output cleanup, independent fresh-producer/Swift evidence may still proceed.
   Ownership, stop, source or cleanup exceptions block continuation. Any required
   failed leaf/assessment keeps the final host **FAIL**, even if Swift later passes.
   Final #413 repair approval still requires actual successful additive Apple ABI
   execution; a lock/prerequisite failure is not waived or repaired by this route.
3. Retain those reports and clean their owned outputs **before** one fresh
   `xcframework-build`. Keep its exact single original provenance task, existing
   minimum-OS/header/binary inspections and four producer-bound sidecars, project
   generation, visible `xcode-provenance` verification (`same task, --console=plain`) and mandatory
   nested Xcode phase. Use unchanged #408 same-producer reuse checks; inspect the
   actual verifier task outcomes, not only matching hashes. No borrowed framework,
   rebuilding graph, cleanup or source mutation may intervene before consumers.
4. On one exact **originally Shutdown** iPhone17 simulator, use
   `run-owned-flow-lifecycle`, existing `p2pkit-sample-ui` scheme, selecting only
   `OwnedFlowCollectionTests`, `SampleRunLifecycleTests` and
   `IosLanDiagnosticsLeaseTests`: **9 + 12 + 7 = 28** source-inventoried methods.
   `swift-owned-flow-lifecycle.xcresult` must show every method exactly once as
   Success, without unknown/failed/skipped cases or another executed target.
   This is not ordinary UI, presentation, live-peer or complete Swift acceptance.
5. After lifecycle-host retirement, run `run-owned-cancellation` **alone and last**:
   `p2pkit-sample-cancellation-probe-tests/SwiftOwnedFlowCancellationTests/testOwnedAdapterCancellationFinishesActualDiagnosticCollection`.
   Its distinct `swift-owned-cancellation.xcresult` must contain exactly that one
   successful native case. It checks normal live delivery, idle native Job and
   accepted callback-task retirement in **one unchanged two-second window**, and
   replacement/post-terminal controls. The outer case bound stays **900 seconds**.

Both focused launch actions require audit state, explicit `IOS_RUN_DIR` and the
outer owner's exact `SIM_UDID`; neither bootstraps/regenerates the prepared
project/framework. Serial XCTest, warnings-as-errors, mutation-lock and source
provenance checks remain. The exact owned simulator is retired on success,
failure or interruption, and failed raw bundles survive before output disposal.
A cleaned lifecycle assertion failure remains failed even if the independent
isolated case later passes. Retirement or a printed marker never substitutes for
native case success. Missing ownership/retirement proof blocks continuation.

The raw `run-cancellation-probe` method, legacy collector, two-second oracle,
`swift-cancellation-probe.xcresult`, names and observational verdict are unchanged;
this route neither reruns nor relabels revision18. Default ordinary both-target
assessment is unchanged. Even a fully green focused run keeps
`hostQualification=NOT_ESTABLISHED_BY_FOCUSED_SCOPE`, release-monolith nonexecution
and all physical/ART, hostile-network, independent interoperability and
professional cryptographic validation limits.

## Unselected Windows core diagnostic caller follow-through

Revision19 selected exactly one `windows-2025` job, `Audit native Windows core
diagnostic caller follow-through`, using native Python, Java 21 then 17 and the
checked-in `gradlew.bat`. The existing `windows-x64`/`windows-followup` route was
narrowed to the seven core JVM classes below; it was **NOT_RUN** at selection time.
This is the #207 caller follow-through, not a new full-host or release result.

The unchanged native Windows x64, Git for Windows Bash, JDK and resource admission
remains required; WSL is not a substitute. The full ordinary
`executor-native-controls` invocation still precedes SDK setup and product work.
The current default Windows loader source-enumerates 92 methods, including pure
and modeled fixtures; this is neither a current 92-method PASS nor product-test
coverage. No reduced control profile or historical PASS substitutes for that run.
SDK platforms **36 and 37.0** and their literal metadata checks remain required
for project configuration even though no Android test or assembly is requested.

The only product graph is:

```text
:p2p-core:jvmTest
  --tests dev.p2pkit.core.internal.KitLifecycleTest
  --tests dev.p2pkit.core.internal.NetworkProvisioningCloseTest
  --tests dev.p2pkit.core.internal.TransportCapabilityTest
  --tests dev.p2pkit.core.internal.KitStrictInvariantsTest
  --tests dev.p2pkit.core.internal.PermissionGateTest
  --tests dev.p2pkit.core.PublicConfigurationValidationTest
  --tests dev.p2pkit.core.PublicModelImmutabilityTest
```

It retains `--continue`, a fresh nonce, the source-bound platform-test init script,
strict dependency verification, forced-fresh tasks and the existing resource
limits. Normal core production/commonTest/JVM compilation prerequisites may run.
The success-conditional `windows-followup-execution` assessor requires fresh,
nonzero successful `:p2p-core:jvmTest` execution while still validating the complete
configured task model. It does **not** establish exact class/method coverage alone.
The graph retains its per-invocation same-home wrapper stop and one owned-output
cleanup, plus the unchanged finalizer and sealed handoff.

The expected product coverage is **78 actual core cases**: the 44 previously failed
Windows17 cases plus 34 retained passes. Retain and independently compare original
XML/listener identities; require all 78 to succeed with no failure, error or skip,
including the four suppressed-list cases with their original assertions. Neither
source selection nor an aggregate task PASS supplies this pending native evidence.

Revision19 does not request LAN, Android-host tests, provisioning, samples,
packaging, wrapper-checkout fixtures, isolated consumers or a separate
Kotlin/Native distribution download. Earlier results keep their exact source/run
bindings and original limits; omitted work is not newly passed or waived.
Admission, summary and handoff retain `requestedScope=windows-followup` and
`hostQualification=NOT_ESTABLISHED_BY_FOCUSED_SCOPE`, even if every selected
component passes. No Apple, ART/device, hostile-network, interoperability or
release acceptance follows from this request.

## Unselected Apple Silicon provenance and isolated cancellation scope

The retained `macos-arm64`/`apple-provenance` route uses `macos-26`, native Python 3,
Java 21 then 17, the checked-in `gradlew` and
`/Applications/Xcode_26.5.app/Contents/Developer`. Revision18 selected it as
`Audit native Apple provenance reuse and isolated cancellation`; revision20 does
not select it. Its actual revision18 outcome is recorded below, not reset to
NOT_RUN or promoted to a full-host, release or physical-device result.

After the unchanged native/non-Rosetta ownership controls, tool prerequisites,
Android SDK admission and pinned XcodeGen installation, this scope runs only:

1. The two pending real policy commands, preserving their original indexes/order:
   `policy-3-check-lock-write-policy-test` runs
   `scripts/tests/check-lock-write-policy-test.sh`; then
   `policy-13-check-android-abi-guard` runs `scripts/check-android-abi-guard.sh`.
   Their existing audit opt-ins, real expected-red/task-graph commands and receipt
   checks remain active. Neither is replaced with a static-only check. Each
   completes its existing owned output cleanup before the fresh framework build.
2. One forced-fresh `xcframework-build`, all existing minimum-OS checks, four
   retained sidecars, generated device/fat-simulator headers and native binary
   inspections. These remain required prerequisites, not downloaded old artifacts.
3. Existing Xcode project generation, then one visible, nonquiet `xcode-provenance`
   leaf with exact arguments
   `:p2p-transport-lan:verifyP2pKitSharedReleaseXCFrameworkProvenance --console=plain`.
   Its successful receipt must identify the same producer, prove unchanged reuse
   bindings and omit forced rerun before the probe may proceed. The retained
   `xcframework-reuse-receipt` inspection does not itself prove no compilation:
   independently inspect actual verifier execution and producer task outcomes in
   the visible Gradle log. Same hashes or a short runtime alone are insufficient.
4. The existing exact available iPhone17 admission and **only** the existing
   isolated Swift Task/Flow cancellation probe, under its unchanged **900-second**
   deadline. Its required XCTest build and mandatory nested Xcode provenance phase
   still execute; no provenance bypass or assertion change is permitted. The
   originally Shutdown device is retired before and unconditionally after the
   probe; an originally Booted/unowned device is not stopped. Raw xcresult and
   exact shutdown observations remain required. Retirement is fallback cleanup,
   never cancellation success.

No core/LAN suites, full policy matrix, ABI comparison batch, consumers/publication,
Dokka/SBOM, strict standalone Swift build,79 ordinary Swift cases or live-peer
fixture are requested by this scope. Retained unaffected results keep their original
source/run bindings; omitted work is not a new PASS. Policy failures remain failed
while independently safe framework/probe work may proceed. Failed required
framework inspections, reuse proof or simulator ownership do not become passes.

Admission, summary and workflow handoff bind `requestedScope=apple-provenance`.
Even if all selected components pass, `hostQualification` remains
`NOT_ESTABLISHED_BY_FOCUSED_SCOPE`. Review the actual producer, visible and nested
verifier receipts/task outcomes, exact probe result and owned cleanup separately.
The two policy commands were pending #395 corroborations in revision18, not
another repair; this scope supplied #408 evidence and does not resolve the
separate live-peer fixture defect or establish independent interoperability (#133).

### Revision18 retained outcome

Actual run **34548459632/1**, job **103106086350**, used clean source
`7f5752729166537d2379d4878545751eaf811d82`. The independent final review approved
**#408's repair as native-proven**, with no further #408 replay required. Both
policy commands, the fresh framework producer, and the visible and nested live
provenance verifiers passed. The visible Gradle log proved the verifier executed
without rebuilding its producer prerequisites; receipt bindings and unchanged
sidecars alone were not treated as that proof.

The **run and host remain FAIL**. The isolated cancellation probe actually
executed **one method and failed one**, with no skip. Its retained outcome was
`POST_CANCEL_CALLBACK_WITH_NO_RETURN_WITHIN_2S`: ready callback, Swift cancel flag
and post-cancel callback were true, while collection had not returned within the
two-second waiter. Its product/stop/final exits were **65/0/65**, within the
unchanged 900-second outer deadline. This is a bounded non-return observation,
not an outer timeout, indefinite non-return proof or cancellation success.

Evidence was **FULL_SEALED**, completeness **PROVED**, with a safe handoff. All 18
stops succeeded with empty errors/survivors, and the exact owned simulator was
retired. `state/work` removal is corroborated by the bound finalizer; deletion of
the outer Gradle home or all caches is **NOT_PROVEN**. Cleanup does not turn the
probe into a pass. No full-host, ordinary 79-case Swift, core/LAN/consumer/ABI matrix,
ART/device or release approval follows from revision18.

## Unselected native Windows full components

The retained `windows-x64`/`full` route uses `windows-2025`, native `python`, Java 21
then 17 and the checked-in `gradlew.bat`. It selects the existing library and sample
graphs, with Native-distribution and Android-assembly tasks added only to the
Windows sample batch. It is unselected by revision19; no full Windows or Apple
host precedes or follows the selected focused job automatically. The earlier
literal request and its actual results retain their original source/run bindings.
Record execution and independent evidence review separately; workflow text is not
a passing result.

The unchanged prerequisites require native Windows x64, real Job Object ownership
controls, Java/tool versions, Git for Windows Bash and both Android SDK platforms.
Then the existing full route runs, serially:

1. `wrapper-checkouts`: the maintained wrapper-checkout fixture through the exact
   admitted Git for Windows `bash.exe`, not ambient Bash/WSL.
2. `windows-libraries`: whole `:p2p-core:jvmTest`, `:p2p-transport-lan:jvmTest` and
   `:p2p-network-provisioning-desktop:test` with `--continue` and a fresh
   source/model/nonce-bound platform event report, then owned output cleanup.
3. `windows-desktop-samples`: `:p2p-sample-desktop:check` and `installDist`, plus
   `:p2p-sample-desktop-ui:test`, `checkRuntime`, `hotRunArgfile` and
   `createDistributable`, together with `:p2p-core:downloadKotlinNativeDistribution`
   and `:p2p-sample-android:assembleDebug`, then owned output cleanup. The shared
   graph uses `--continue` without suppressing any failure.

The explicit Native task exercises strict Windows compiler-archive admission;
it is not Windows iOS or native application execution. Android assembly exercises
the Windows AAPT2 classifier, not ART or device behavior. Inspect those actual
task/download outcomes separately: SDK installation alone proves neither one.

The CLI and Desktop UI consume project dependencies. This route does **not**
invoke isolated published-artifact consumers, KMP consumer checks, a Maven
publication, Android instrumentation or the full repository `check`/release gate.
Do not infer those results from sample compilation or packaging. All native
Gradle commands keep the original Windows PATH; only the admitted Bash probe and
wrapper fixture receive that Git installation's utility PATH prefix.

Earlier focused Windows results retain their own source bindings. The full route
covers the broader component scope rather than separately repeating the
filtered follow-up/diagnostic graphs. Their JVM classes remain within the whole
library suites; the historical mixed follow-up's Android-host task is not selected
by this full route.
`FULL_COMPONENT_SCOPE` describes requested components,
not a successful host/release verdict. Inspect actual tests, package cleanup and
sealed stop/ownership/evidence outcomes. Desktop packaging is not headful UI or
physical/hostile-network/independent-interoperability acceptance.

## Unselected native Intel ABI and Swift follow-through

The retained `macos-x64`/`full` route uses `macos-15-intel`, native Python 3,
Java 21 then 17, the checked-in `gradlew` and fixed
`/Applications/Xcode_26.3.app/Contents/Developer`. It requires real
Intel/non-Rosetta and Xcode 26.3 admission. It is unselected by this workflow
revision; record its actual execution and independent review separately.
Workflow text is an obligation, not a result.

After the unchanged native ownership controls and SDK admission, an Intel-only
read-only preflight retains actual `simctl list --json runtimes` and
`simctl list --json devices available` output. It requires an available iOS runtime
joined to an exact available iPhone 17 with a valid UDID and Booted/Shutdown state;
a missing, unavailable or failed inventory blocks product builds with retained
raw diagnostics. This inspection neither boots nor acquires ownership of a device,
and is not x86_64 execution or a qualification pass. The later existing Apple
selection and exact-device boot/revalidation remain authoritative.

Only then does the driver run `scripts/run-platform-tests.py ios-x64`: exactly
core and LAN `iosX64Test`, with the existing strict source/model/nonce assessor.
After their owned output cleanup and pinned XcodeGen installation, the maintained
isolated-consumer gate performs one fresh source-local publication and its
JVM Kotlin/Java, Android compilation/manifest and KMP JVM/Android/iOS consumer
checks. Strict external metadata and exact local-publication checksums remain
required. The consumer's maintained simulator-arm64 compile/link is not ARM
runtime execution and does not substitute for native Intel tests.

The independent artifact gate reuses that same repository **only after its exact
successful nested `consumer-publish` receipt**: original arguments, source,
parent invocation, initially absent repository, stop/drain and retained evidence
must all bind. A later consumer compile failure stays failed but no longer prevents
the independent inspection. Missing/failed publication does not admit partial
files; malformed finalization blocks subsequent product work. The existing gate
must actually inspect all **54 archives across15 coordinates**:45 exact canonical
embedded licenses plus9 explicit main/cinterop KLIB exemptions, with unchanged
readability, Dokka, POM, module and native-identity checks. This is not a legal
waiver, remote publication or release. Publication/framework evidence is retained
before owned output cleanup; there is no second publisher.

Next, one `swift-jvm-cli-prepare` Gradle graph runs:

```text
:p2p-core:checkKotlinAbi
:p2p-transport-lan:checkKotlinAbi
:p2p-network-provisioning-android:checkKotlinAbi
:p2p-network-provisioning-desktop:checkKotlinAbi
:p2p-core:checkAndroidAbi
:p2p-transport-lan:checkAndroidAbi
:p2p-network-provisioning-android:checkAndroidAbi
:p2p-sample-desktop:installDist
--continue
```

This batches the seven outstanding supported-Mac ABI comparisons with the one
CLI distribution needed by its live Swift counterpart. Inspect all seven actual
task outcomes and native dump work in this receipt's original product log;
platform `execution.json` inventories test tasks, not ABI execution. Missing,
skipped or failed ABI work is not acceptance. `--continue` allows independent
tasks to finish but leaves the combined graph failed if any task fails.

The existing Apple sequence follows even after a cleanly finalized graph failure:
release XCFramework provenance/inspection and headers, Xcode project generation,
Swift warnings-as-errors build, ordinary unit/UI tests, then the existing isolated
real Swift/JVM transfer case. The CLI output is retained through its dependent
live peer; there is no cleanup or second CLI build between preparation and Apple
work. A nonzero preparation receipt blocks the live peer even if partial CLI files
exist or the installDist task happened to succeed. Do not fabricate a successful
CLI receipt or retry it automatically. Independent Apple successes cannot erase
an ABI failure or turn the overall host summary green.

After successful ordinary Swift tests, the live peer retains advertising=true
through natural quit. Only if its unchanged30s exit deadline fails, the controller
may collect **one** JDK17 `jcmd Thread.print -l` observation before the existing
outer drain: the original direct CLI child remains unreaped, Darwin lifetime,
parent and ownership-domain checks plus opaque audit-token acquisition bind it,
and the tool uses a10s wait and2MiB per-stream file limit. A failed or truncated
attach is recorded; it does not retry, extend acceptance time or make quit PASS.
HotSpot attach can perturb the failed JVM; this is diagnostic evidence, not a
repair. No manual SIGQUIT, process-name scan, daemonization or `System.exit`
workaround is introduced. Unresolved diagnostic children remain owned by the
same executor's bounded drain; raw `.log` files are retained by its normal seal.

The explicit Intel/full route finally reuses the existing **one isolated** Swift
Task/Flow cancellation probe and exact initially-Shutdown simulator retirement.
It remains separate from both acceptance schemes, after the live peer, with no
invalid iteration option. No owned initially-Shutdown device means NOT_EXECUTED,
not a hardware pass; fallback shutdown is not cancellation success. Record actual
Intel source/case evidence without inferring architecture-specific ARM acceptance.

The current official Intel image advertises Universal Xcode 26.3 with the shared
iOS 26.2 runtime and iPhone 17, but actual allocated-runner availability and x86_64
execution remain required. Missing native support fails precisely without a
runtime/model fallback, SDK downgrade, ARM substitution or fabricated evidence.
This extends the original two-suite-only Intel plan toward the complete
[test-catalog ENV-04](../validation/test-catalog.md)
procedure. Its older two-suite scope and NOT_RUN history are not retroactively
changed or promoted to a Swift/sample pass. No ARM policy/core/LAN/Swift replay,
full `check`, standalone Dokka/SBOM or unrelated Android/Desktop sample batch is
introduced. Fresh publication still builds its required real Dokka Javadoc inputs.

Here `full` is **role-relative**: `FULL_COMPONENT_SCOPE` records the requested
Intel component graph, not successful whole-repository or release qualification.
Inspect actual receipts and exact native tests/transfer evidence. ARM execution,
Rosetta and fat-framework inspection cannot substitute for native Intel results;
host/simulator transfer remains same-codebase integration, not #133 independent
interoperability. Unaffected accepted evidence retains its original bindings.

## Unselected Apple Silicon follow-up scope retained by the driver

The retained `macos-arm64`/`apple-followup` route uses `macos-26`, native Python 3,
Java 21 then 17, checked-in `gradlew` and fixed
`/Applications/Xcode_26.5.app/Contents/Developer`. It is not selected by this
workflow revision and is not repeated merely to reassure a different-host execution.
Its mandatory native ownership controls and SDK admission remain unchanged.
A later selection must pass actual ARM64/non-Rosetta and Xcode-version admission;
an advertised image label or workflow text is not execution evidence.

This residual route retains the complete current-host executor admission suite,
but does not repeat the already executed core ARM suite or the two unchanged
#157 process-group controls. Their earlier native results retain their original
source/run bindings; omitted work is not a new pass and earlier failures remain
historical evidence. Full-profile policy selection and all ownership, failure
and cleanup checks remain unchanged.

The focused route invokes `scripts/run-platform-tests.py ios-lan-arm64` for exactly
`:p2p-transport-lan:iosSimulatorArm64Test`. This additive Apple-Silicon-only profile
uses the same complete committed model, native host admission, fresh nonce and
successful nonzero-case assessment. Other task records remain present and are
classified as actually observed; core ARM is not requested by this invocation.
A LAN-only report cannot satisfy either `ios-arm64` or `full`. The existing
`ios-arm64` two-suite, `ios-x64` and full profiles remain unchanged. This is native
simulator execution, not physical iOS-device or Intel qualification.

The downstream callers perform isolated source-local publication and
consumer builds, inspect all15 publication sets after the exact successful
publisher receipt independently of later consumer failure,
retain publication/framework evidence, then run the existing XCFramework
provenance, Swift warnings-as-errors, and unit/UI simulator sequence. The new
runner still needs these source-bound framework prerequisites; do not bypass the
Xcode provenance phase or use old header observations as Swift execution.

One separately selected Swift UI/JVM CLI integration case follows successful
ordinary Swift tests. It uses the real installed CLI, explicit receiver consent,
one pinned secure-v2 connection, and two distinct 204800-byte files with both
endpoints' transfer records and independent durable-file hash checks. The CLI
distribution is prepared once immediately before Apple work and retained until
the live peer finishes. This is same-codebase simulator/host integration, **not
independent interoperability (#133)**.

The focused route finally runs one isolated Swift Task/Flow cancellation probe,
outside both acceptance schemes. It reuses an exact simulator positively observed
initially Shutdown, preferring such an available device, and proves its shutdown
before and unconditionally after the probe. An initially Booted/unowned device is
never retired. No available owned device produces an explicit NOT_EXECUTED
investigation record, not a pass or a physical-hardware claim. Probe failures and
raw xcresults remain separate from acceptance outcomes; process retirement is
fallback cleanup, never proof that Flow cancellation succeeded.

This route does **not** repeat full `check`, the unrelated Android/Desktop sample
artifact batch, a standalone Dokka/SBOM graph, or selected TCP SDK-header
inspection. Required fresh-source publication still builds its real Dokka Javadoc
artifacts; these dependencies are not skipped. Existing successful results keep
their original source/evidence bindings; omitted work is not newly passed or
waived. Full-profile checks remain required; its live peer preparation likewise
reuses one CLI distribution instead of packaging it twice.

`requestedScope` is bound across admission, summary and workflow bootstrap/handoff.
For `apple-followup`, `hostQualification` remains
`NOT_ESTABLISHED_BY_FOCUSED_SCOPE`, even when every selected component passes.
Inspect every actual result, receipt, source binding and cleanup outcome. The
monolithic release gate and external acceptance remain separate.

Before the unselected full Mac scope's component builds, a read-only inspection
retains the actual selected `iphoneos` and `iphonesimulator` SDK path, version and
build queries plus each complete `Network.framework/Headers/tcp_options.h`. SDK
and framework aliases may resolve only inside the selected Developer/SDK roots.
The header is bounded to 1 MiB and retained verbatim as
`apple-sdk-<sdk>-tcp_options.h.log`; its binding records both resolved paths,
SHA-256, size, exact source and the retained Xcode prerequisite record. Original
query stdout/stderr and failure records remain available if inspection fails.
This supplies declarations for #156 inspection, **not** compilation, actual
socket-option state, latency improvement or issue acceptance. It never copies
an entire SDK or changes installed tools. Independent later components may run
after a failed read-only inspection, but the failed component cannot become PASS.
This inspection is not repeated by the focused follow-up.

## Unselected Windows diagnostics scope retained by the driver

The optional `windows-diagnostics` scope remains available only for `windows-x64`,
using native Python, Java 21 then 17 and the checked-in `gradlew.bat`. It is **not
executed by this workflow revision**. A later reviewed literal Windows selection
would retain the unchanged native ownership controls and SDK admission, then
select only the affected strict LAN diagnostic callers:

```text
:p2p-transport-lan:jvmTest
  --tests dev.p2pkit.transport.lan.JvmLanAcceptLoopResilienceTest
  --tests dev.p2pkit.transport.lan.JvmLanAdmissionControlTest
```

The existing source-bound event assessor requires fresh nonzero successful LAN
JVM execution and rejects stale, failed or incomplete task evidence. Inspect both
selected class XMLs and exact cases, including the expected-diagnostic negative
control. Admission, strict dependency verification, resource limits, per-invocation
wrapper stop, owned-output cleanup and sealed handoff are unchanged. The distinct
`windows-diagnostics-execution` record is not the full/follow-up scope's assessment.
Core durability, the broader LAN selection and Desktop packaging are not repeated;
reuse earlier successful evidence only with its original source and reviewed limits.
This scope does not supply native discovery, whole-host or external qualification.

## Historical mixed Windows follow-up scope

At revision18's source, the unselected `windows-followup` route retained the mixed
core/Android-host/LAN and Desktop-packaging graph below, after native ownership
controls and SDK admission. This describes historical selection, not a run result
or **another callable preserved variant**. Revision19 reuses the same scope name
for only the
[seven core JVM classes above](#selected-windows-core-diagnostic-caller-follow-through).
Earlier results keep their original source/run bindings; they are not rewritten
by this narrower selection.

```text
:p2p-core:jvmTest
  --tests dev.p2pkit.core.transfer.FileTransferJvmTest
  --tests dev.p2pkit.core.internal.PeerRegistryTest
  --tests dev.p2pkit.core.internal.PeerSubscriptionHookTest
  --tests dev.p2pkit.core.internal.PeerPublicationConcurrencyTest
  --tests dev.p2pkit.core.internal.DiscoveryReemitContractTest
:p2p-core:testAndroidHostTest
  --tests dev.p2pkit.core.transfer.AndroidDurableFileDestinationAndroidHostTest
:p2p-transport-lan:jvmTest
  --tests dev.p2pkit.transport.lan.JvmRawConnection*
  --tests dev.p2pkit.transport.lan.KitTestDiagnosticsTest
  --tests dev.p2pkit.transport.lan.JvmLanLoopbackTest
  --tests dev.p2pkit.transport.lan.JvmLanAcceptLoopResilienceTest
  --tests dev.p2pkit.transport.lan.JvmLanAdmissionControlTest
  --tests dev.p2pkit.transport.lan.JvmLanDiscoveryHeartbeatTest
:p2p-sample-desktop-ui:checkRuntime
:p2p-sample-desktop-ui:createDistributable
```

That graph used `--continue`, the source-bound platform-test init script and a
fresh nonce, plus the executor's strict verification/resource/fresh-task flags.
Each `--tests` option belonged to its immediately preceding test task. The
historical event assessor required both core tasks and the filtered LAN JVM task
to execute nonzero successful cases on native Windows while validating the
complete configured task inventory and rejecting any failed event. Historical
coverage still requires the original class XMLs and exact case names, not a task's
aggregate count. The durability classes covered close-only retry and
non-POSIX/lazy-staging controls; registry classes covered subscription hooks,
interrupted publication waiting, terminal/reentrant updates and retained StateFlow
fusion. The raw-I/O classes covered real TCP half-close, cancellation and late
worker completion. Those LAN callers used real Windows TCP sockets and
deterministic test-discovery callbacks, not native JmDNS/multicast validation.
None of these tests or packaging tasks is requested by revision19.

### Current focused-scope limits

For every focused scope, `hostQualification` is always
`NOT_ESTABLISHED_BY_FOCUSED_SCOPE`, including when the selected components pass.
The CLI accepts `full` for the existing roles, `windows-followup` and
`windows-diagnostics` only for Windows, and `apple-followup`, `apple-provenance`,
`apple-native-compilation`, `apple-owned-cancellation` and `apple-owned-helper` only
for Apple Silicon, rejecting other pairs before state initialization. Full defaults remain
unchanged; `FULL_COMPONENT_SCOPE` describes their requested scope, not a successful
qualification. Omitted Windows full-profile components are **NOT_EXECUTED by
such a focused run**, not waived. The narrowed `windows-followup` graph does not
repeat wrapper-checkout, whole library suites, provisioning, CLI/KMP consumers,
Desktop UI tests or packaging. Gradle exit zero or failure to reproduce an earlier
cleanup error does not establish a repair. The mandatory native executor suite
retains the actual Windows read-only-file recovery/hardlink refusal controls;
those fixtures are not a new product packaged-image cleanup result. When a
separately selected route requests packaging, its packaged-image cleanup must
also succeed.

### Full profiles supported by the driver

These profiles describe each role's component graph, not equivalent whole-host
qualification. All full profiles are unselected by this revision's focused
request. Any later native selection requires a separately reviewed literal
change and terminal-attempt reconciliation.

| Role and fixed label | Selected tools | Components, not broader acceptance |
| --- | --- | --- |
| Native Windows x64, `windows-2025` | Native Python, Java 21 then 17, checked-in `gradlew.bat` | Fresh core/LAN/provisioning library JVM suites; CLI/Desktop checks and distributions; strict Windows Native archive admission and Android sample assembly |
| Native Apple Silicon, `macos-26` | Xcode 26.5, native Python 3, Java 21 then 17 | Full platform `check`, policy/script gates, Android/Desktop samples, ABI/Dokka/SBOM, local publications/isolated consumers, XCFramework and Swift build/unit/UI simulator tests |
| Native Intel, `macos-15-intel` | Xcode 26.3, native Python 3, Java 21 then 17 | Both core and LAN `iosX64Test` suites; one publication/isolated-consumer/archive gate; seven ABI checks batched with CLI preparation; existing XCFramework and Swift build/unit/UI/live-peer sequence, then isolated cancellation observation |

`macos-15` without `-intel` is not the Intel role. Rosetta, cross-compilation and an
ARM simulator pass do not establish native Intel execution. The original Intel
profile's two Kotlin suites alone were not the complete Swift bridge/sample
`ENV-04` procedure; the retained extension still needs actual independent review
of all required native evidence. Windows product commands do not run through WSL
or a POSIX wrapper.
A sample packaging pass is not rendered headful Desktop observation.

Windows shell prerequisites use Git for Windows: the driver resolves native
`git.exe` from its `cmd` or `bin` installation layout, requires that installation's
`bin/bash.exe` and `usr/bin` tools, and validates native Git's `.windows.N` version
and Bash's `x86_64-pc-msys` or `x86_64-pc-cygwin` build target. The Cygwin target is
also used by bundled Git-for-Windows Bash; it does not admit standalone Cygwin Git.
The same absolute Bash executable is recorded and, in the full Windows profile,
used for the wrapper-checkout fixture, even if the ambient `bash` command selects
WSL. Only its version probe and
fixture receive the Git `bin`/`usr/bin` PATH prefix for nested shell utilities;
native Python and `gradlew.bat` product commands keep the original host PATH.
Missing or unusable Git Bash fails closed with retained prerequisite diagnostics;
installing WSL or skipping the fixture is not a substitute. Linux process-boundary
fixtures do not establish actual Windows execution or checkout compatibility.

Runner/image documentation advertises availability, not actual allocation or
compatible installed tools. The driver records the real OS/image, architecture,
CPU/disk and tool versions; it requires the explicitly selected Xcode and supported
simulator. Missing tools/runtimes or native process-ownership capabilities fail
closed, without changing deployment targets, disabling required tasks or using
preview Xcode as a silent fallback. See [canonical Android setup](local.md#android-sdk-setup)
for platforms **36 and 37.0**; installing only platform 36 is insufficient for the
Android application sample. Windows/JDK 17 tests need the
[real symbolic-link prerequisites](local.md#jvm-host-coverage), not skipped tests.

After the SDK manager succeeds, the driver requires each requested platform's
`source.properties` to name its literal `AndroidVersion.ApiLevel`: `36` for
`android-36` and `37.0` for `android-37.0`. An integer `37` is not the latter
package's canonical metadata. Both property contents and file hashes are retained;
missing or mismatched metadata blocks product execution rather than skipping a platform.

### What the full Apple Silicon component replay requires

The driver preserves actual policy/fixture checks and real full graph probes,
including the lock-policy expected-red leaves, Android ABI graph, version/toolchain
approval tripwires, real Xcode project generation and launcher/consumer regressions.
A fixture test is labeled as a fixture; it is not a Kotlin/Native, device or remote
publication pass.

The original `scripts/run-platform-tests.py full` assessor runs
`./gradlew check --console=plain` with its fresh source/model/task/nonce evidence.
Required host tasks must execute nonzero successful cases; old XML, cache hits,
no-source tasks and compilation cannot stand in for tests. Report every skipped
case and the configured other-host/device-only targets. Do not reduce the platform
policy or replace the assessor with an XML-only success check.

The additional components retain:

- Four Kotlin and three published Android ABI comparisons in the existing full
  `check` graph, not a redundant standalone ABI rebuild. Inspect all seven actual
  task outcomes and supported native dump work in `mac-platform-full`'s retained
  product log; platform `execution.json` records test tasks, not ABI results.
  Missing, skipped or failed ABI work is not acceptance.
- One `mac-artifact-build` graph combines Android sample assembly, CLI checks/
  installable distribution, Desktop UI tests/runtime/argument-file/application
  image, all four strict Dokka publications and aggregate JSON/XML SBOM generation.
  `--continue` allows independent tasks to finish but never turns a failed graph
  green. Explicit JSON/XML SBOM inspection runs only after this graph succeeds,
  before owned output cleanup. A failed graph leaves that inspection unexecuted,
  even if partial SBOM files exist; retain its original failure and narrow any retry.
- The maintained isolated-consumer script performs the one local-only publication
  to its fresh owned Maven repository. After the exact successful publisher receipt, the artifact checker
  inspects all 15 expected macOS publication sets in that **same repository**;
  a second standalone publication is not built. Its JVM Kotlin/Java, Android
  compilation/manifest and KMP JVM/Android/iOS simulator compile/link checks and
  iOS minimum-OS/permission assertions remain. Later consumer failure does not
  prevent this independent archive inspection or become a pass. Missing/failed
  publication never admits partial files; invalid receipt finalization stops
  product work. Partial metadata/hashes and native observations remain retained.
- Strict consumer dependency verification: reviewed external metadata plus exact
  source-bound local publication hashes, not a broad trusted group, disabled
  verification, arbitrary Maven-directory trust or remote publication fallback.
  A missing external checksum remains a failure requiring separate investigation.
- Separate post-consumer native `vtool`/`lipo` inspection retains raw output,
  binary hash/size, source/time and the original consumer invocation ID. This is
  an additional observation, not recovery of the original tool output captured
  inside the consumer checker. An absent binary is explicitly `NOT_EXECUTED`.
- Real release XCFramework provenance/minimum-OS inspection, all four build
  sidecars, authoritative XcodeGen generation and the unremoved provenance
  pre-build phase. All platform slices are inspected; inspection is not execution
  of the device or opposite-host slice. Additional post-gate `vtool`/`lipo` output
  is hash-bound to the device and fat-simulator binaries before later rebuilding;
  it is separate from the original gate's captured shell variables.
- Before dependent rebuilding or cleanup, the device and fat-simulator slices'
  generated `Headers/P2pKitShared.h` are retained verbatim as
  `xcframework-<device|simulator>-header.h.log`. Each must be a physical regular,
  nonempty file of at most 1 MiB; copies are exclusive and source/retained bytes
  are rechecked. The matching `*-header.json` records inspection PASS/FAIL and,
  on success, original path, size/hash, source/run admission and XCFramework-build
  invocation ID. Partial raw evidence survives a failed inspection; no missing
  declaration is fabricated. Inspect `NSError.kotlinException`, exported typed
  errors and synchronous/suspend error boundaries alongside actual Swift
  compilation and throwing-call XCTest evidence. Header retention alone does not
  prove bridging, SDK runtime behavior or issue acceptance.
- A real Swift warnings-as-errors build, separately followed by XCTest for both
  `p2pkit-sample-tests` and `p2pkit-sample-uitests` on one recorded exact available
  simulator. A build-success marker is not a test count; retain actual xcresult
  and nonzero successful cases for both targets.

These scope descriptions are obligations, **not results**. Inspect the exact
component command/status/receipt list for the run; a dependency failure can leave
later dependent components unexecuted. Independent components may still run only
when cleanup is proved. No unexecuted row becomes PASS because a later step passes.

## Resource, process and failure contract

A native Python bootstrap creates a randomized fresh parent under resolved
`RUNNER_TEMP`, outside the source checkout. It owns `bootstrap-evidence/`; the
separate `state/` does not exist until the driver admits and initializes it.
Setup failures can therefore retain metadata without reusing or taking ownership
of an old state directory. Java 21 is installed first and its path retained as
`P2PKIT_AUDIT_JDK21`; Java 17 is selected last as `JAVA_HOME`. Record actual launcher,
daemon and test runtimes rather than inferring runtime from source compatibility.

The [leaf executor](../../scripts/run-audit-command.py) uses an exclusive job-owned
Gradle home and per-invocation lease. There is no cross-run cache action, build cache,
configuration cache or parallel Gradle execution. Dependency/wrapper downloads may
be reused within the exclusively owned job home. Direct product invocations keep
strict dependency verification, task rerun by default, at most two workers, bounded heap and
metaspace, and an in-process Kotlin compiler. Intentional negative-control arguments
such as `--configure-on-demand` are preserved, not masked by appended opposites.

Only `kind=gradle`, purpose `xcode-provenance`, and the exact
`:p2p-transport-lan:verifyP2pKitSharedReleaseXCFrameworkProvenance` task with
`-q --console=plain` or `--console=plain` may omit the appended `--rerun-tasks`.
Reuse requires the same job's successful source-bound forced-fresh producer,
matching canonical receipt, and all four retained/live sidecar bindings checked
before and after the invocation. An absent producer keeps forced-fresh behavior;
present invalid bindings fail closed. The real no-output Gradle verifier still
executes against current source, inputs, binaries and headers. All other flags,
source checks, resource limits, wrapper stops and ownership controls remain unchanged.

### Audited consumer and policy-fixture work

With `P2PKIT_GRADLE_EXECUTOR` set, the maintained consumer script supports only
source-local publication with no positional arguments or remote repository.
`P2PKIT_CONSUMER_WORK_DIR` must explicitly name a new or empty physical child
beneath initialized `P2PKIT_AUDIT_STATE_DIR/work`. Implicit temporary work,
remote/`--latest-published` modes, aliases and foreign work paths are rejected.
Both values of `P2PKIT_CONSUMER_AUDIT_METADATA` obey this contract; value `0`
does not prepare local-publication trust or disable strict Gradle verification.
Every supported audited consumer directory is borrowed and retained, regardless
of product status, receipt availability or the keep-artifacts switch. The outer
host finalizer owns its eventual disposal. Historical nonexecutor default and
remote behavior remain unchanged.

The audited lock-policy fixture similarly allocates fresh `work/lock-policy.*`
and retains its init script, logs, optional receipts and `.txt` lock snapshots
on success, failure or cancellation. Its `ownership.json` binds the work namespace;
`leafFinalization: NOT_ASSESSED` is not native cleanup proof. The actual executor
and receipt checker still decide each leaf's finalization before an expected
policy rejection can be accepted. Unopted fixture cleanup remains unchanged.
Synthetic caller tests preserve the real controller's complete ancestor domains
when introducing a fixture state/home; fake wrappers are not product execution.

### Per-invocation finalization

After **every** build/test, including failure/cancellation, the executor retains
product and finalizer logs, runs the applicable checked-in wrapper `--stop` under
the same owned home and drains only invocation-owned workers. Product failure,
source failure, stop failure, evidence failure and unresolved workers are separate
outcomes. Infrastructure exit 125 must never be accepted as an expected policy
rejection just because an old error string also appears. Outer command supervision
must not hold the Gradle leaf lease while a nested consumer/provenance call needs it.

Every host first executes native ownership controls before product tasks. Windows
requires actual before-resume Job Object containment, not name-based `taskkill` or
post-spawn assignment. macOS requires real identity/marker discovery and scoped
signal behavior, including detached children and an unrelated surviving sentinel.
These mechanisms supervise controlled build descendants, not hostile code stripping
ownership markers or delegating to unrelated OS services. Source inspection and
mocked APIs do not prove native ownership capability.

Darwin reconciles failed environment/task-token observations against the original
process lifetime and each attempt's exec version. The retry policy allows at most
26 attempts within a 250 ms window; it does not bound a blocking kernel call or
extend product deadlines. `INEXIT` is only a pending transition, never completed
cleanup; normal `EXEC` flags and stopped processes remain live. Persistent denial,
malformed observations and unfinished exits fail closed. Every acquired Mach right
is released, and a release failure is never retried or suppressed as process exit.
Bounded `observationReconciliations` receipt entries retain first/last failures,
status/flags and final disposition without argv/environment contents or changes
to stdout/stderr. These observations do not replace the actual native controls.

The workflow redirects stdout/stderr to separate fresh bootstrap logs and invokes
the exact checked-out driver with `runpy` in the **same native Python process**.
There is no extra unsupervised wrapper child, launcher replacement or product
monkeypatch. The driver's own deadline, cancellation and ownership finalizers run.
The selected focused driver retains the explicit 8,400-second budget and
150/180-minute step/job ceilings used by revision18; narrowing the route does not
change these bounds. The unselected Apple probe's 900-second deadline is unchanged.
Constructor defaults remain 8,400 seconds on Windows/Intel and19,200 on Apple Silicon. The unselected expanded Intel route's
prior literal request used an explicit 19,200 seconds and 330/360-minute ceilings
for its consumer/archive/ABI/CLI/framework/Swift components, not the old two-suite budget.
A later selection must review its native tools and explicit budget.
The driver retains its 360-second finalization reserve. These are resource
ceilings, not elapsed-time estimates, relaxed assertions or automatic retries.

A safe completed handoff requires all of the following; it does not dispatch a
later host:

1. The selected driver emits literal `safe_to_continue=true` after source,
   worker/stop cleanup and evidence finalization.
2. The always-run handoff inspection validates the strict summary/context/receipt
   schemas and types, exact SHA/tree/role/scope/run/attempt, clean post-run source,
   successful native ownership controls, and every retained invocation's stop,
   source and empty-survivor/error records. It hashes the complete manifest/file
   set, rejecting duplicates, traversal, symlinks/reparse points, missing or
   unlisted files, changed bytes and oversized evidence/control files.
3. Bootstrap path/file validation and its separate checksum manifest succeed;
   the artifact step succeeds **and returns a nonempty artifact ID**. Upload paths
   come from the validated handoff, not unchecked environment paths.

A cleaned product failure keeps its driver step/job **failed**; there is no
`continue-on-error`. A focused component pass is not whole-host qualification.
A missing output/summary, failed handoff, failed upload, cancellation, source
uncertainty or unresolved ownership blocks a safe handoff. Any later independently
allocated host still requires explicit terminal-attempt reconciliation, reviewed
source selection and the global lease. A shell observation that no `java` process
is visible is not proof of cleanup.

## Evidence, cleanup and recovery

Artifacts are named
`audit-host-<role>-<run-id>-<run-attempt>` and retained for 14 days. An always-run
upload follows setup/product/handoff failure only if the handoff proves an owned,
physical bootstrap upload path. Failed allocation or unsafe bootstrap ancestry
leaves no safe directory to upload: keep the Actions job log, record the missing
artifact, and leave downstream work blocked.

The upload allowlist is **`bootstrap-evidence/` and a validated `state/evidence/`**.
Hidden files are included within these checked paths so a manifest-listed file is
not silently omitted; this is not permission to upload hidden homes or caches.
Never upload the whole state/home, Gradle/Native caches, credentials, private device
data, raw user payloads or local machine settings. Hosted tests use synthetic data.

A rejected or unfinished driver tree is **not** handed to the artifact action,
which might otherwise follow a rejected symlink. Instead, the handoff physically
traverses only the allocated `state/evidence/` and copies safe regular JSON, log,
text, XML and checksum controls into a fresh `bootstrap-evidence/evidence-salvage/`.
Receipt/start/product/stop files take priority. Salvage is bounded to 10,000 files,
128 MiB per file, 1 GiB total and 100,000 traversed entries; unsafe ancestors,
nonregular nodes, binary reports, changed files and excess data are omitted with
explicit reasons. If the evidence root is unsafe or absent, only bootstrap metadata
and its omission explanation are uploaded. Salvage has its own checksum manifest,
but **full-tree completeness remains `NOT_PROVEN` and safe continuation is not established**.
It is partial historical evidence, not repaired cleanup or a fabricated complete
artifact. Investigate unavailable required reports rather than claiming them.

Retain the workflow start/handoff records, raw driver stdout/stderr, per-invocation
product/stop logs and receipts, source/tool metadata, platform execution JSON/test
reports, relevant publication/consumer manifests, XCFramework sidecars and Swift
xcresult. Download before expiry and independently verify the complete checksum
manifest and source/run binding. The driver manifest covers `state/evidence/`
excluding that manifest itself; `bootstrap-manifest.sha256` independently covers
bootstrap files and any salvage, excluding itself. Compare artifact IDs and actual
run/job outcomes; a successful upload alone is neither cleanup proof nor a passing test.

Default failure logs are historical evidence. Do not edit them into successes,
replace them with a later attempt or combine different source trees into a single
claimed pass. Reruns get fresh state and artifacts. Prefer a new complete run/attempt
after root-cause investigation rather than silently assembling “green” hosts from
unrelated attempts. Any partial reuse must be explicitly source-bound and reviewed.

Disposable output removal happens only after required evidence is retained and
all dependent consumers have finished. Cleanup uses exact newly-owned output paths,
not a search for directories named `build`. Preserve shared caches, source and user
changes. In particular, `buildSrc/src/main/java/dev/p2pkit/build` is **source**.
Metadata retention may prune and record explicitly unselected symlink/reparse
entries without following them. Selected or raw-evidence links still reject
retention; exclusions do not authorize reading or deleting a link's target.
Do not delete an active iOS launcher lock/guard or a caller-owned fixture before its
workers and consumers finish; see [launcher recovery](local.md#ios-launcher-cleanup-and-recovery).

On a removal failure, the executor adds bounded diagnostics (at most 32 KiB) to
the failed cleanup record: the admitted root/index, known removal operation,
lexically relative failing path, exception class, numeric errno/WinError and
timestamped metadata observation. Path admission precedes metadata access;
physical ancestors are checked root-to-parent, then the leaf is inspected with
`lstat`. No link target or payload is read, and arbitrary exception text/foreign
filenames are not retained. Missing native attributes mean unknown, not false.
Metadata can be `OBSERVED`, `ABSENT`, `REFUSED` or `UNAVAILABLE`; diagnostic or
encoding failure cannot erase the original removal error. An ineligible or
unrecovered failure rethrows that same error, and cleanup stops without advancing
to another output root. Final cleanup JSON retains its existing 4 MiB bound, with
space reserved before deletion.

One narrowly admitted Windows recovery is available for an exact `os.unlink`
`PermissionError` with `EACCES`/WinError 5: an already-owned regular, singly-linked
leaf with only READONLY and optional ARCHIVE attributes. It durably retains the
original failure before any change, revalidates the physical root/ancestors and
same leaf identity, clears only READONLY, revalidates identity/remaining attributes,
and retries that exact unlink at most once. Symlinks/reparse entries, directories,
hardlinks, foreign roots and unknown attribute combinations are refused. There is
no blanket chmod, ACL change, worker kill or suppression of an unrecovered error.
The recovery record retains the original failure even on success; admission,
journal, chmod, revalidation or retry failure preserves the original removal error
as authoritative. This uses the existing quiescent-owned-output contract, not
containment of a hostile actor concurrently changing filesystem names.

These observations are post-failure, not an atomic statement about an earlier
racing instant. A read-only attribute or WinError 5 does not alone establish the
cause; WinError 32 would support a sharing violation without identifying an owner.
Trial4 remains **failed**, with **PARTIAL_SALVAGE** and full remote cleanup
**NOT_PROVEN**. Its scheduling lease release is not remote-cleanup acceptance.
The focused scope and diagnostics do not automatically request another run; a
fresh runner cannot clean or prove destruction of the earlier runner.

There is no generic workflow recovery command that can retroactively prove cleanup
following controller/runner/host loss. Abrupt termination can prevent Python finally
or artifact upload. Such cleanup is **UNKNOWN**, not PASS; it cannot authorize safe
automatic continuation. Preserve available ownership receipts/logs, identify any surviving workers
through their actual recorded identities, and let the operator resolve the global
execution lease. Never run a blanket kill, attach an ambient Gradle home for `--stop`,
delete unknown output, force-push, or manufacture a safe output. A fresh verified
invocation does not erase the earlier UNKNOWN result.

## Acceptance that hosted work cannot supply

Keep the [validation status](validation-status.md),
[external handbook](../validation/README.md) and
[test catalog](../validation/test-catalog.md) separate from these host results.
Android host stubs/shadows are not ART/instrumentation, OEM callbacks or physical
radios. iOS simulators are not physical Local Network/AWDL/path rotation,
background/locked-device filesystem, backup or restart campaigns. Packaged samples
and synthetic UI tests do not complete controlled headful/fault-injection or
hostile two-machine network campaigns.

Independent secure-v2 interoperability (#133), professional cryptographic review,
and owner architecture/product decisions (#120) require their own participants,
inputs and evidence. This facility does not supply them or change their dispositions.
Actual OSV results and successful dependency submission also remain separate from
policy fixtures/lockfile coverage. Full Windows, Intel, Linux and Apple Silicon
corroboration are not supplied by a focused host request.

Follow the [release checklist](../releasing/checklist.md) for any future release.
The audit's 0.8.0+ compatibility decisions remain in force despite snapshot naming.
No hosted pass authorizes a tag, merge to main, issue closure, remote publication,
repository-setting change or declaration that the entire audit is complete.
