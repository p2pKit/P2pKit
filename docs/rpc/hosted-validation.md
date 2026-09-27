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

## Diagnostic mode (the default for a feature push)

Before repeating an expensive failed full graph, `diagnose` executes the unchanged
JmDNS real-resource JVM regression and the complete LAN ARM simulator test task.
Both run once, even when the first fails; there is no automatic retry. The driver
requires fresh invocation-token-bound execution counts and matching nonempty XML,
not just a zero Gradle exit (Native failures can be deferred to `allTests`). JmDNS
also requires all eight natural-exit fixture successes without rescue markers.
The existing fixed test deadlines/assertions and ignored diagnostic-only interop
test are unchanged. No interface override or network workaround is supplied.

This mode may generate provisional checksum candidates needed for Apple
resolution, but **never writes locks or qualifies committed dependency inputs**.
Its candidates are `DIAGNOSTIC_ONLY_DO_NOT_IMPORT`. Select `generate` explicitly
for the complete writer below; diagnostic success is not a replacement for it.

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
source corrections/regressions; their hosted result must be recorded separately.
The unchanged-main `JmdnsCloseLifecycleTest.realResourceCloseRegressionsExitNaturally`
also failed; the original summary is insufficient to attribute its cause. Do not
conflate it with the separately corrected historical external JmDNS lock entry.
The skipped `IosLanDiagnosticTest` is the pre-existing explicitly ignored
physical-observation diagnostic, not a newly skipped regression.

After reviewed inputs are committed, normal strict Native ABI/Dokka and fresh
platform-evidence checks must run against the exact committed source. Intel
simulator execution requires its matching hosted architecture; an Apple Silicon
run does not establish that result. Swift/framework consumers and complete
release/consumer qualification remain separate until actually executed within
the authorized scope. Consumer scripts that publish, even locally, are not
implicitly authorized by this workflow.

No result from hosted compilation or simulators establishes actual LAN path
enforcement, physical interoperability, foreground/background operation or the
approved 128-client capacity targets. Follow [qualification](qualification.md)
for those still-separate experiments and the [implementation checkpoint](implementation-status.md)
for checks that actually completed.
