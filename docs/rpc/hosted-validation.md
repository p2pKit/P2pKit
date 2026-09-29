# Feature-only GitHub Actions validation

The owner separately authorized GitHub-hosted macOS execution, required hosted
SDK/dependency downloads and sanitized artifacts for the RPC feature branch.
That hosted authorization did not itself authorize publication, merging, tags,
release secrets or physical/security/capacity experiments. Later scoped local
permissions are recorded in [qualification](qualification.md), not inferred from
a hosted run. Release Foundation remains **NOT_READY**.

This page retains the hosted run history. The separately authorized
[September 27–28 Mac work](mac-vps-validation.md) passed reviewed dependency
inputs, strict full-profile/ABI/compiler/SBOM and sample-build checks, followed
by private artifact/complete-consumer validation. Its failed attempts remain
failed and retained at their original source commits.

The [September 29 Mac runtime continuation](mac-vps-runtime-20260929.md) now
verifies 122 native controls and all six supplemental phases on `62716271`:
original-bound readiness, all 20 strict platform tasks (2,959 passes, one
pre-existing ignored diagnostic), fresh framework provenance, all 88 Swift unit
and six UI cases, fresh peer preparation and one real Swift/JVM sample case
with 204,800 bytes in each direction. Actual execution
and owned cleanup were independently checked. These results are not repairs of
failed hosted lanes or supported-host, dedicated cancellation, ART/device,
physical/security or capacity qualification. No shared hosted job or runner
permission change was started by that VPS continuation.

The later [RPC lab continuation](vps-lab-runtime-20260929.md) records actual
API-24 software-emulator probes on Linux and Intel Mac, eight Android RPC controls,
nine iPhone application-hosted XCTest methods and an unsigned iPhone device app. These
are separately source-bound local results, not a repair or rerun of the hosted
KVM/Apple-ownership failures below, and not deployed LAN/capacity qualification.

The [optional workflow](../../.github/workflows/rpc-feature-validation.yml) is
restricted to `work/rpc-lan-20260927-054728-8b1b11da`. Its branch-specific push
trigger registers the workflow without modifying main. It uses a disposable
`macos-26` Apple Silicon runner with explicitly selected Xcode 26.5, Java 17/21,
fresh owned Gradle/Native/home state, no cache restoration, a read-only repository
token and no signing secrets or environments. Its distinct concurrency group
does not cancel any run. Existing CI, Foundation and release workflows are not
modified or dispatched by this workflow.

The checkout is shallow only during initial acquisition; an explicit `--no-tags
--unshallow` fetch obtains full feature/main history before validation. The driver
rejects shallow history or any tag refs. Review of the first run's checkout log
found that `actions/checkout` with `fetch-depth: 0` fetches tag refs despite
`fetch-tags: false`; the workflow now avoids that behavior. Those were read-only
ephemeral runner refs, not created/pushed repository tags. The isolated working
clone was already full-history without tags and remains so.
The corrected full-history/no-tags checks subsequently passed in the compiler run
recorded below; the driver also checked that condition before execution/collection.

## Explicit execution, not an automatic retry

Ordinary feature pushes do not allocate a runner. Use an owner-coordinated
feature-ref dispatch with a selected mode, or an intentional `[rpc-diagnose]`,
`[rpc-native]`, `[rpc-apple-compile]` or `[rpc-generate]` head-commit marker if branch-only workflow
dispatch is unavailable.
The markers select an already-authorized operation; they grant no new permission.
This prevents a documentation/checkpoint push from blindly repeating a failed
host admission. Never mark an unchanged full-writer rerun as a prerequisite probe.

## Diagnostic mode

Before repeating an expensive failed full graph, `diagnose` executes the unchanged
JmDNS real-resource JVM regression and the complete LAN ARM simulator test task.
Both run once, even when the first fails; there is no automatic retry. The driver
requires fresh invocation-token-bound execution counts and matching nonempty XML,
not just a zero Gradle exit (Native failures can be deferred to `allTests`). JmDNS
also requires all eight natural-exit fixture successes without rescue markers.
The existing fixed test deadlines/assertions and ignored diagnostic-only interop
test are unchanged. No interface override or network workaround is supplied.

`diagnose-native` runs only the LAN ARM simulator task after a Native correction;
it does not blindly repeat the unchanged JmDNS failure. Current diagnostic modes
use normal strict resolution, **never write locks/checksums**, and require
committed inputs to remain unchanged. Their manifests are
`DIAGNOSTIC_ONLY_DO_NOT_IMPORT`. Select `generate` explicitly for the complete
writer below; diagnostic success is not a replacement for it or whole-repository
strict-input qualification.

## Independent compiler checks

`compile-apple` selects normal strict core/LAN/RPC Dokka and the example's
three Apple debug-framework links, then typechecks the public
[Swift façade fixture](../../samples/p2p-sample-rpc/verification/RpcSwiftApiCheck.swift)
against each actual framework and matching SDK/target. Warnings remain errors;
the iOS 14 minimum is checked in framework metadata. Receipts hash nonempty
compiler/header/module-map/HTML outputs, but no compiled binary is uploaded.
Swift uses the maintained sample's Swift 5 language compatibility mode. No
application, physical device, network experiment, JmDNS test or publication is
selected, and committed inputs may not change. Cross-compiling Intel/device
slices is not Intel or physical-device runtime evidence.

These checks exposed compiler/API issues independently while the complete
lock writer awaited an admitted host. They do not turn that failed hosted run
green or admit partial dependency/ABI inputs. The driver retains each failure
and does not run Swift checks if genuine framework generation/output checks fail.

## First stage: generated inputs for review

The [driver](../../scripts/run-rpc-hosted-validation.py) first executes genuine
core/LAN/RPC `updateKotlinAbi` tasks, then the complete supported
`resolveAndLockAll --write-locks --write-verification-metadata sha256
--no-configure-on-demand` graph. It does not disable checks, narrow the graph,
weaken test assertions/timeouts, fabricate Native ABI or silently accept partial
locks. Gradle's dependency verification and warning-as-error policies remain
enabled. Generation mode admits **candidates**, not independently trusted new
artifact checksums; review must precede a normal strict verification run.

The job uploads only an allowlisted generated-input patch, its hashes,
source/toolchain/command outcomes, compiler/task diagnostics and XML test counts
with failed/skipped test names. Failure details retain only fixed exception types
and in-range public-source locations. JmDNS summaries allowlist fixed phase,
startup counter, thread-state and route-observation markers; no address, interface
name, native error message or arbitrary frame is retained. These post-failure
observations do not establish packet delivery or a network-policy diagnosis.
Raw logs, assertion/trace bodies, test stdout/stderr,
homes, caches, identities, keys and compiled artifacts are not uploaded.
Publication and consumer-publication commands are not selected.

- `INCOMPLETE_DO_NOT_IMPORT`: setup, ABI generation, the full writer, cleanup or
  required outputs did not complete. **Never import partial lockfiles.**
- `REVIEW_REQUIRED`: all generation commands and cleanup succeeded and expected
  inputs exist. Inspect the entire patch, preserve reviewed checksum history,
  independently authenticate every new dependency artifact, and compare ABI for
  unintended removals before committing to the feature branch. This status is
not a readiness or release result, even if the Actions job is green.

## Observed first run (failed; no candidates imported)

[Run 36333670930](https://github.com/p2pKit/P2pKit/actions/runs/36333670930),
source `7f086509b1d3276e323a8bd89d3d8566e60ab460`, ran on ARM64 macOS 26.6.2,
Xcode 26.5, iOS simulator SDK 26.5 and Temurin 17/21. Genuine Apple compilation
and core/LAN/RPC ABI generation passed. The complete lock writer failed at
`:p2p-transport-lan:allTests`; its partial inputs are **INCOMPLETE_DO_NOT_IMPORT**.
Owned cleanup passed. No complete lock output was produced.

| Observed test row | Tests | Failures | Skips |
| --- | ---: | ---: | ---: |
| Core ARM simulator | 792 | 0 | 0 |
| RPC ARM simulator | 45 | 0 | 0 |
| RPC sample ARM simulator | 3 | 0 | 0 |
| LAN ARM simulator | 194 | 1 | 1 |
| LAN JVM | 231 | 1 | 0 |

The Native failure was
`AppleOrganizationLanInteropTest.numericComparisonAcceptsEquivalentIpv6ButNeverHostnamesOrAmbiguousIpv4`.
The original collector did not retain the precise failing assertion. Strict
numeric spelling checks and both NWEndpoint address representations now have
source corrections/regressions; their successful subsequent run is recorded below.
The unchanged-main `JmdnsCloseLifecycleTest.realResourceCloseRegressionsExitNaturally`
also failed; the original summary is insufficient to attribute its cause. Do not
conflate it with the separately corrected historical external JmDNS lock entry.
The skipped `IosLanDiagnosticTest` is the pre-existing explicitly ignored
physical-observation diagnostic, not a newly skipped regression.

## First diagnostic result (failed; cause not attributed)

[Run 36336684433](https://github.com/p2pKit/P2pKit/actions/runs/36336684433),
source `bc4ade3b92e2c783559b1d788b5efe097047a6ca`, preserved both failures and
passed owned cleanup. Its checksum-generation flag produced no input changes;
subsequent diagnostic modes remove that flag and enforce unchanged inputs.

- JmDNS: one JVM test failed. The `control` child failed `host_not_announced`
  before `ready`, after two sends and zero successful send returns; first error
  was `java.net.NoRouteToHostException`. Seven later modes did not run. The
  captured selected/host/socket interfaces matched. A post-failure scoped route
  query returned an up route with no reported reject/blackhole/gateway flag.
  These observations **do not prove the OS/privacy/provider/network cause**.
  Rescue retained the original failure. No timeout or assertion changed.
- Native: main/Cinterop compilation passed, but the new test could not import
  `platform.posix.inet_pton`; **zero Native tests ran**. The corrected fixture now
  populates sockaddr network-order bytes independently of the parser under test.
  Its subsequent Native-only result is recorded below.

At this hosted checkpoint, the full writer was blocked by genuine multicast
readiness, consistent with the unchanged main
[Mac prerequisite handoff](../testing/mac-handoff.md), not by the independently
corrected external JmDNS lock entry. Further execution required a newly admitted
supported Mac with functioning multicast/simulator prerequisites; no
unchanged full-graph retry, privacy/route override or partial-lock import is allowed.

## Native correction verified (scoped pass)

[Run 36337234887](https://github.com/p2pKit/P2pKit/actions/runs/36337234887),
source `06a0a5ec6038e081ec46657acac8bc2fbc3b7995`, passed the complete
`:p2p-transport-lan:iosSimulatorArm64Test` task under normal **strict** dependency
verification and warnings-as-errors, with fresh execution-token evidence and
32 matching nonempty XML reports: **194 passed, zero failures/errors, one
pre-existing ignored diagnostic**. All three `AppleOrganizationLanInteropTest`
tests passed. There was no JmDNS invocation, checksum/lock writing or tracked-input
change. Owned process-group drain and same-home Gradle stop passed.

Toolchain: ARM64 macOS 26.6.2 (25G83), Xcode 26.5 (17F42), simulator SDK 26.5,
Temurin 17.0.20.1+1 and 21.0.12.1+1. The sanitized artifact ZIP digest was checked
against GitHub metadata before allowlisted extraction:
`7fee3a42b3e49e48ad85a321a4580537cc3ad45b56d9fe34d3c19c843e44f233`.
Twenty Python-only driver controls also passed. This validates the bounded Native
regression scope, **not actual organization-LAN path enforcement, complete locks,
all-target compatibility, release or capacity qualification**.

## Framework, Swift surface and Dokka verified (scoped pass)

[Run 36337930630](https://github.com/p2pKit/P2pKit/actions/runs/36337930630),
source `de409d8543df1307c83df7c388bc3a315c1ee856`, passed all five compiler
commands plus owned cleanup under normal strict verification, warnings-as-errors
and unchanged committed inputs:

| Check | Observed result |
| --- | --- |
| Core/LAN/RPC `dokkaGeneratePublicationHtml` | All three succeeded; nonempty HTML indexes hashed. |
| RPC example debug frameworks | `iosSimulatorArm64`, `iosArm64`, `iosX64` linked; actual binaries, headers and module maps hashed; each framework's minimum-OS metadata was `14.0`. |
| Swift consumer fixture | `swiftc -typecheck -warnings-as-errors -swift-version 5` passed against each matching framework/SDK and iOS-14 target triple. |
| Input and process ownership | Full history/no tags, no tracked-input modifications, no restored caches, all five owned process groups drained, same-home Gradle stop succeeded. |
| Offline driver controls | All 22 passed, including output/target/input/secret-exclusion controls. |

The ARM64 host/toolchain versions match the Native run above. The verified
sanitized artifact ZIP digest is
`d6fb70ed2b433bab62e94e984868e03797b8fc4c22c5eb5d2f4ad9f711a92fca`.
Framework binaries and raw logs were **not** uploaded; only their bounded
hash/size receipts were retained in the sanitized run record. No application,
device, simulator test or JmDNS fixture ran in this compiler-only job.

This establishes compilation/public Swift API use, not Swift application linking,
execution/cancellation propagation, packaged XCFramework/published-consumer
qualification, native Intel runtime execution, physical iOS-14 compatibility or
capacity. No partial lock/checksum/ABI candidate from this hosted run was imported.

## Remaining admission and gates

The [later supplemental VPS results](mac-vps-validation.md) preserve the runtime
scan, simulator migration, startup and ownership failures, followed by positive
recovery evidence. One owner-authorized restart ended the unclassified lifetime;
separate Apple initialization completed the remaining library assessments.
Unchanged bounded Native startup, fresh admission, a new complete writer and
independent review then passed. No additional restart, security-policy change,
deadline extension or blind hosted retry is authorized. The historical hosted
multicast failure remains separate; its cause has not been established and its
failed record has not been replaced.

The new writer's reviewed dependency inputs are committed; they do not qualify
the retained supported configurations. Complete strict verification still needs
admitted hosts with working multicast/simulator prerequisites: Apple Silicon/
macOS 26/Xcode 26.5 and genuine Intel/macOS 15/Xcode 26.3, following the
[Mac prerequisite handoff](../testing/mac-handoff.md). A different toolchain needs
reviewed admission, not silent substitution. Working prerequisites must be
established by genuine admission/evidence, not a different assertion, longer
deadline, route/privacy override or an unchanged blind hosted retry.

Normal strict Native ABI and the full platform profile passed against the exact
committed candidate on the supplemental Intel VPS. Its later SBOM privacy failure
came from validation-clone provenance. The canonical-origin clone repeated the
full-profile pass and all ten compiler/SBOM commands, then successfully built the
existing Android/Desktop/iOS samples. Those packages are not turnkey RPC
installers. Swift unit/UI execution remains blocked at system-app readiness,
before XCTest. Intel simulator execution requires its matching host architecture;
an Apple Silicon run does not establish that result. These supplemental/scoped
passes do not replace complete release/Maven artifact/consumer qualification.
Consumer scripts that publish, even locally, remain outside this historical
workflow. Later owner approval covers private Mac-local staging; the complete
consumer fixtures now explicitly reference RPC coordinates and typed APIs.
Their offline controls and the complete current-source private consumer run
subsequently passed in the
[Mac continuation](mac-vps-validation.md#authorized-packaging-and-consumer-continuation).
The supplemental Mac also compiled the three Swift test bundles; that did not
run XCTest or replace supported-host/physical/security/capacity qualification.

All four hosted run records, metadata and verified sanitized ZIPs are retained
in this isolated clone under `.git/rpc-hosted-20260927-0k7TY6/run-<run-id>/`,
with digest/extraction receipts for the diagnostic and compiler runs.
Failed runs are preserved separately,
not overwritten or promoted by later scoped passes. No local Java/Gradle/Xcode
build was started during this hosted continuation. Changes and reports were
committed/pushed only on the feature branch; Foundation's status/HOLDs are untouched.

No result from hosted compilation or simulators establishes actual LAN path
enforcement, physical interoperability, foreground/background operation or the
approved 128-client capacity targets. Follow [qualification](qualification.md)
for those still-separate experiments and the [implementation checkpoint](implementation-status.md)
for checks that actually completed.

## Remaining qualification workflow

The latest owner approval covers the remaining feature-only Actions and Intel
Mac checks. The new [workflow](../../.github/workflows/rpc-qualification.yml)
uses only the exact feature ref and an intentional `[rpc-qualify]` head-commit
marker. Ordinary pushes allocate no runner. Its distinct non-cancelling queue
and non-fail-fast matrix leave other sessions' work untouched. It selects:

- Apple Silicon/macOS 26/Xcode 26.5;
- genuine Intel/macOS 15/Xcode 26.3;
- Ubuntu 24.04 Android ART, only if the runner already permits KVM access.

The [driver](../../scripts/run-rpc-qualification.py) requires canonical-origin,
full-history/no-tags clean source, fresh native executor controls, sequential
identity-owned commands and verified same-home finalization. No legacy
PID/process-group launcher, privilege elevation, firewall/route/permission
change, restored cache, signing secret, release writer or external publication
is selected. The maintained ART finalizer's broad export is not used; KVM
metadata/ACLs are inspected without modification and must remain unchanged.

Apple jobs first run the new host's unchanged real multicast readiness control
(10-second readiness, 45-second child bound). A failure blocks the complete
platform gate and is retained as such. Independent explicit scoped Native
checks can run, but never replace that full-profile pass. The jobs also select
ABI, strict Dokka, RPC frameworks/Swift API, actual SBOM, fresh XCFramework
provenance and the maintained 88 Swift unit/six UI methods with the original
120-second system-app-readiness bound. Only a newly created, exactly bound
simulator is eligible for shutdown/deletion by its owning job.

Raw logs, payloads, identities, receipt paths, generated binaries and XCTest
bundles remain private to the runner. Only the closed sanitized summary schema
(counts, fixed source-written command/failure labels, reviewed multicast markers,
source hashes and finalization verdicts) is uploaded. Admitted counts are not
counts of every attempted test; missing/failed coverage is never a pass. The
17 offline driver controls passed, including public-output leakage, incomplete
results, wrong-host/event admission and ownership/failure propagation controls.
These are policy tests, not evidence that a hosted runtime gate has passed.

### First remaining-qualification attempt

[Run 36397029526](https://github.com/p2pKit/P2pKit/actions/runs/36397029526),
source `06512d4a4a7eaaea016c4751f51e0bfe7e7bfb0e`, failed native executor
admission on all three lanes. Each enclosing receipt returned infrastructure
exit 125; no product gate was admitted. Source stayed unchanged. The three
sanitized ZIPs were independently checked against GitHub's SHA-256 digests and
exact run/source bindings. This is retained failed evidence, not a test pass.

| Lane | Sanitized ZIP SHA-256 |
| --- | --- |
| Apple ARM64 | `5e355019a892b5170522e2de726a670ae203d58f4aade74db561805c9262a65a` |
| Apple x64 | `c2ab42e54e669588cbb25b5e50945f3ebb7c6c7cc1c3baedc450b7ef5020c81d` |
| Android ART | `0cc8ab12c6af4f99fe65ff9a0db0673dd12b122d24df9bbff79c47c3dc1e9a4f` |

The initial summary deliberately excluded raw receipts but lacked sufficient
safe failure detail to diagnose exit 125. The driver now retains closed
error/stop markers, scalar exit/error/survivor counts, literal error messages
from the reviewed executor sources, and explicitly **unadmitted** unittest
output counts. No dynamic exception values, traces, paths, identities or
payloads are exported. Twenty-one offline controls passed, including these
failure/privacy cases.

An intentional `[rpc-admit]` marker selects a distinct **admission-only
diagnostic**: original native controls and same-home finalization, never
product/compiler/simulator/ART gates, even if admission succeeds. It adds
observability to investigate this failure; it is not an unchanged blind full
qualification retry. The original run remains failed. The private Intel Mac
candidate independently passed all 122 controls and 25 Java archive controls.
Its completed packaging/consumer continuation is recorded
[separately](mac-vps-validation.md#authorized-packaging-and-consumer-continuation).

Physical/LAN/security and real-host capacity qualification are unchanged
external gates. Record exact tested SHAs and individual results before making
any readiness claim.

### Admission diagnosis and scoped Linux correction

[Diagnostic run 36397963442](https://github.com/p2pKit/P2pKit/actions/runs/36397963442),
source `e2771596ca1c8e1c553eb43e4be7ca90e7547fe8`, ran **only** native admission.
All three failures and sanitized artifact digests were independently retained.
Linux's 114 controls printed success, but one unresolved process-observation
error made the enclosing receipt fail (125); same-home stop passed. Those
114 output counts are not admitted execution. Both Apple lanes reported 122
attempted controls with failures and genuinely unclassified Darwin lifetimes;
pre-stop/final drain could not prove cleanup. The ARM lane reported 25
observation errors; Intel reported seven. Neither a missing process marker nor
a purportedly harmless system-service name authorizes ignoring that failure.
No product/compiler/simulator/ART gate ran, and no process-name/PID sweep,
privileged observer, policy change or assertion/deadline relaxation was used.
The Apple admission condition remains unresolved; an unchanged rerun is not
selected by the next scoped operation.

Source investigation found a Linux-only observer defect: unlike the Darwin
backend, a transient `/proc` access denial was added to permanent error state
without a pending, exact-lifetime reconciliation record. The correction records
only recoverable access denials, rechecks them even when absent from a census,
and clears them only after positive ownership/nonownership or verified
exit/replacement. Live denial, UID change, unreadable recorded identity and
structural failures still fail closed. Failed pidfd acquisition rechecks also
close the acquired descriptor. No Darwin behavior or RPC contract is changed.
All 81 offline policy/scripted observer controls passed. The new real-lifetime
control uses an explicitly scripted visibility denial; it does not claim a
kernel-generated denial. [Run 36399194444](https://github.com/p2pKit/P2pKit/actions/runs/36399194444)
at `5b0669bf0185f5a311650337fcc61c679a624810` then passed the complete **121-test
Linux native inventory**, including the enclosing receipt/finalization and both
JDK checks. KVM admission failed: the runner user could not use `/dev/kvm`.
No Android emulator or ART test ran and no device permission was changed.
The sanitized ZIP was independently digest/source verified:
`360bb5391967e2e7ab0211a88629cd633051f5e97be5e8848c1568b481358d51`.

The intentional `[rpc-art]` marker selects **only** the Linux lane, with fresh
native admission before existing toolchain/KVM/ART gates. It cannot allocate an
Apple runner or turn the failed admission records into passes. KVM must already
be accessible: this workflow does not grant access or change its ACL. A narrowly
scoped temporary runner-access change requires the owner's separate permission;
requesting it is not authorization.

The Mac packaging attempt at `06512d4a` passed its 122 native controls, 25 Java
archive controls, complete staging and unchanged 21-publication artifact
checker, then **failed** complete consumers on an unverified transitive
`kotlinx-io-core:0.6.0` module descriptor. Its failure is preserved. The exact
descriptor has since been independently checked on the Mac against official
Maven bytes, SHA-256 sidecar and the pinned JetBrains signature. Source
`5ed6dbed` adds only that checksum; dependency versions, locks and trust policy
are unchanged. A fresh clean source-bound Mac attempt at `5ed6dbed` subsequently
passed all six phases, including the complete consumers and RPC API smoke. The
unchanged artifact gate accepted all 21 publications; consumer metadata retained
117 physical inputs and 141 verification records. Source, receipt aliases,
publication bytes and cleanup were independently verified. A separate strict
observation confirmed IO 0.9.0 artifacts in Android's ordinary and POM-only graphs
and the RPC JVM runtime, with no resolution override. The bounded private text/receipt
archive SHA-256 is
`30f7e593c2f539121d064e6b19765841becadf64305ec38cedbb3bc3020f6b0d`.
This private Mac pass does not promote the failed hosted lanes or ART/device/
capacity gates. See the [Mac continuation](mac-vps-validation.md#authorized-packaging-and-consumer-continuation).

### Bounded Apple observation diagnosis

The `[rpc-apple-admit]` marker selects only the two Apple **admission-only**
lanes, never Linux or product gates. A new diagnostic adds closed aggregate
observation-operation, outcome, pending process-state and known errno/Mach-failure
labels to sanitized summaries. It exports no PID, process name, audit-session
identifier, path, environment, token or raw exception. Unknown values become a
fixed `OTHER` label or fail schema validation, not arbitrary public text.

This is additional failure evidence, not a relaxed observer or unchanged attempt
to force product gates green. The native ownership rules, original bounds,
assertions and finalizer are unchanged. All **26 offline** qualification-driver
controls passed, including privacy/count mutation cases, original summary
compatibility and rejection of the Apple diagnostic marker for products or
Android. Even successful admission-only execution would not establish a
compiler or runtime pass.

[Run 36402025957](https://github.com/p2pKit/P2pKit/actions/runs/36402025957),
source `3acb99939d17ef82f3704115216360e31908ba7a`, subsequently **failed both
Apple admission-only lanes**. The ARM/Intel scopes retained 16/17 unclassified
live lifetimes respectively, reported in kernel state 2. Non-reaper original
parentage could not be established. The aggregate record also contains transient
environment `EIO`/`EINVAL`, Mach task-name failure and exec/token observation
errors; every recorded immediate observation was eventually recovered, absent
or nonrunning. Those reconciled transient errors alone do not explain away the
remaining live, unclassified lifetimes.

Both enclosing receipts returned 125 with pre-stop/final drain failures, while
same-home stop and source integrity passed. Each suite reported 122 attempted
controls with failures; **zero counts were admitted**. No product task or
simulator was started. The exact origins/ownership of those lifetimes remain
unproven; calling them harmless system services would not be evidence.

| Lane | Independently verified sanitized ZIP SHA-256 |
| --- | --- |
| Apple Silicon | `c23adf62b26ab02d12fffb09fd815bb4d513a65619181e62895d34dd7e95abba` |
| Intel | `8fd00b7d5ec4c5fcdca479323e8a59d37d4acc781594667f7c32fc912e91080c` |

The historical summary's `ownedSurvivorCount: 1` is a **receipt-record count**:
on drain failure the executor retains one `UNKNOWN` sentinel, not proof of one
known surviving process. A subsequent reporting correction explicitly emits
`MISSING`/`UNKNOWN` and a null count rather than miscounting that sentinel.
All 27 offline driver controls pass, including unknown-versus-zero inventory
and backward-readability controls. Original artifacts and failed verdicts are
preserved; the correction changes neither ownership rules nor a gate result.

No further unchanged Apple retry is selected. Continuing product qualification
requires an environment in which the existing ownership controls genuinely
pass, or separately reviewed lifecycle ownership—not ignoring missing markers,
whitelisting process names, a privileged observer or broader signal authority.
