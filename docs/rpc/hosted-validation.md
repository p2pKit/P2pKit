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
with failed test names. Raw logs, assertion/trace bodies, test stdout/stderr,
homes, caches, identities, keys and compiled artifacts are not uploaded.
Publication and consumer-publication commands are not selected.

- `INCOMPLETE_DO_NOT_IMPORT`: setup, ABI generation, the full writer, cleanup or
  required outputs did not complete. **Never import partial lockfiles.**
- `REVIEW_REQUIRED`: all generation commands and cleanup succeeded and expected
  inputs exist. Inspect the entire patch, preserve reviewed checksum history,
  independently authenticate every new dependency artifact, and compare ABI for
  unintended removals before committing to the feature branch. This status is
  not a readiness or release result, even if the Actions job is green.

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
