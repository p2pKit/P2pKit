# Feature-only GitHub Actions validation

The owner separately authorized GitHub-hosted macOS execution, required hosted
SDK/dependency downloads and sanitized artifacts for the RPC feature branch.
This is not authorization to publish, merge, tag, use release secrets or run
physical/security/capacity experiments. Release Foundation remains **NOT_READY**.

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

These checks can expose compiler/API issues independently while the complete
lock writer awaits a multicast-capable host. They do not turn that failed gate
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

The full writer remains blocked by genuine multicast readiness, consistent with
the unchanged main [Mac prerequisite handoff](../testing/mac-handoff.md), not by
the independently corrected external JmDNS lock entry. It must wait for a newly
admitted supported Mac with functioning multicast/simulator prerequisites; no
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
capacity. No partial lock/checksum/ABI candidate has been imported.

## Remaining admission and gates

The complete writer still needs a newly admitted supported isolated Mac with
working multicast and simulator prerequisites: Apple Silicon/macOS 26/Xcode 26.5
or genuine Intel/macOS 15/Xcode 26.3, following the
[Mac prerequisite handoff](../testing/mac-handoff.md). A different toolchain needs
reviewed admission, not silent substitution. The unchanged-main JmDNS failure
must be resolved by genuine admission/evidence, not a different assertion, longer
deadline, route/privacy override or an unchanged blind hosted retry.

After complete reviewed inputs are committed, normal strict Native ABI and fresh
platform-evidence checks must run against the exact committed source. Intel
simulator execution requires its matching hosted architecture; an Apple Silicon
run does not establish that result. The scoped compiler passes above do not replace
complete release/consumer qualification. Consumer scripts that publish, even
locally, remain unauthorized by this workflow.

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
