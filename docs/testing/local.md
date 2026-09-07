# Local testing

Use JDK 17 and the checked-in Gradle wrapper. macOS with the configured Xcode
toolchain is required for Apple targets and the complete release gate.

JVM file-transfer regressions require real symbolic links in `java.io.tmpdir`.
Use a symlink-capable temporary filesystem. On Windows/JDK 17, use NTFS and a
test-process token with `SeCreateSymbolicLinkPrivilege` (for example, an elevated
console for an account granted the **Create symbolic links** right). Developer
Mode alone is insufficient with JDK 17. Missing prerequisites fail the required
test with the original platform cause; they must not be treated as passed or
silently skipped coverage.

Fast project checks:

```bash
scripts/tests/check-repository-layout.sh
scripts/tests/check-osv-lockfile-coverage.sh
scripts/check-release-metadata.sh
./gradlew check --console=plain
```

Release-shape checks:

```bash
scripts/check-sbom.sh
scripts/check-publish-artifacts.sh
scripts/check-published-consumers.sh
./gradlew :p2p-core:checkKotlinAbi \
  :p2p-transport-lan:checkKotlinAbi \
  :p2p-network-provisioning-android:checkKotlinAbi \
  :p2p-network-provisioning-desktop:checkKotlinAbi
./gradlew :p2p-core:checkAndroidAbi \
  :p2p-transport-lan:checkAndroidAbi \
  :p2p-network-provisioning-android:checkAndroidAbi
./gradlew :p2p-core:dokkaGeneratePublicationHtml \
  :p2p-transport-lan:dokkaGeneratePublicationHtml \
  :p2p-network-provisioning-android:dokkaGeneratePublicationHtml \
  :p2p-network-provisioning-desktop:dokkaGeneratePublicationHtml
```

The complete macOS gate is `scripts/run-release-gate.sh`. It includes module
tests, Android lint/host tests, Apple simulator tests, ABI, strict Dokka,
publication artifacts, isolated consumers, SBOM, Swift warnings-as-errors, and
release-XCFramework provenance.

## JVM host coverage

Run the library suites without requesting Apple/Android tasks:

```bash
./gradlew :p2p-core:jvmTest :p2p-transport-lan:jvmTest \
  :p2p-network-provisioning-desktop:test --continue --no-build-cache \
  --dependency-verification strict --max-workers=2 --no-parallel --console=plain
./gradlew --stop
```

On Windows PowerShell, use `.\gradlew.bat` and one command line instead of
Bash continuations. The symlink prerequisites above still apply; do not skip
tests when a runner lacks them. Stop Gradle after failures as well as success.

`CI` runs these tasks on Ubuntu and Windows for every pull request, main push,
and manual run. macOS retains the complete `check` gate. Keep `complete-gate`
required in repository rules: it waits for both JVM hosts and explicitly rejects
failure, cancellation, or a skipped matrix before running either its lightweight
or full checks. No new required-check name is needed. The separate Desktop
matrix remains sample-test/packaging coverage.

Each JVM host uploads XML/HTML reports as
`jvm-library-tests-<matrix.os>-<run_attempt>` even after a test failure (seven-day
retention). A setup/compilation failure may have no reports and still fails the
job. Record the source SHA, OS/JDK, task outcomes, test counts, and any skips;
a configured workflow or another OS's pass is not host-execution evidence.
`scripts/tests/release-workflow-test.sh` checks the matrix, actual task command,
report paths, and fail-closed dependency guard, with negative policy controls.

## Platform execution evidence

On macOS with JDK 17, Xcode, and the configured Android SDKs, use:

```bash
python3 scripts/run-platform-tests.py full
# Native Intel Mac only; not an arm64/Rosetta substitute:
python3 scripts/run-platform-tests.py ios-x64
```

The full profile runs `./gradlew check --console=plain` with strict dependency
verification, task reruns, build/configuration caches disabled, two workers,
and no parallel tasks. Shared dependency caches remain available.
Both simulator architectures share the network-test serialization service.
The Intel profile requests only core and LAN `iosX64Test` tasks. CI uses the
full profile; `ios-x64-tests.yml` provides a secret-free weekly/manual Intel job.
Keep failures blocking; a configured workflow is not hosted execution evidence.

Reports live in `build/reports/platform-tests/<invocation-token>/`:
`invocation.json` binds the command to the commit/tree and complete tracked diff;
`execution.json` records Gradle task outcomes and actual passed/failed/skipped
test events; `summary.json` includes the final verdict, source recheck and
per-target limitations. Review and stage new source files before invoking the
gate: untracked nonignored inputs or source changes during execution fail it.
CI, release verification and dry-run uploads retain this directory. Each required
task must freshly execute nonzero successful cases; old XML, cache hits,
no-source results and dry-runs cannot satisfy the gate. Skipped case counts
remain visible, including the intentionally ignored Apple LAN diagnostic.

Review changes to `gradle/platform-test-policy.json` together with target/task
changes; never remove an entry to silence a missing suite. The script regressions
exercise model/outcome mutations and fake-wrapper failure/cancellation paths,
not Kotlin execution. The driver stops Gradle in `finally` and uses bounded
TERM/KILL escalation to drain its owned process groups, even if a wrapper exits
before its workers. Separately detached helpers are outside that group guarantee;
callers must track and stop their own survivors. Preserve evidence and any outputs
needed by dependent consumer validation before deleting disposable build directories.

The report distinguishes the other-host simulator slice, device-only
`iosArm64`, compilation-only metadata, and separately run Swift tests. Android
host/shadow tests do not run ART; no instrumented suite is authored. Core's
intentional `*AndroidHostTest` filter still excludes its common suite because
host stubs are not an Android runtime. JVM/native common-test passes do not
substitute for the missing Android runtime tier. See
[validation status](validation-status.md#kotlin-target-execution-and-structural-gaps).

## iOS launcher cleanup and recovery

`./gradlew :iosApp:runIosSimulator` and `:iosApp:runIosUiTests` require Python 3
alongside Xcode/XcodeGen. They share a process-owned launcher lock. Successful
runs remove their automatic `ios-run.*`/`ios-ui-run.*` directories; failures,
`KEEP_IOS_RUN_ARTIFACTS=1`, and caller-owned `IOS_RUN_DIR` directories retain evidence.
SIGINT/SIGTERM preserve failure status and release ownership after foreground work
ends. A signal sent only to Bash is deferred while its foreground command runs;
it does not release a lock underneath an active build.

Dead launcher locks are reclaimed only after both the recorded launcher and its
mutating foreground worker have exited. Unknown, malformed, or live owners fail
closed: stop the relevant launchers/build workers, inspect the records, then remove
only `samples/iosApp/build/.ios-launch.lock/{pid,worker}` and the empty lock directory.
The empty `.ios-launch.lock.guard` file is intentional: Python's standard-library
kernel lock serializes metadata recovery without the nonstandard `flock` command.
Never unlink that guard or remove the build directory while a launcher is running.

`scripts/tests/run-ios-app-test.sh` drives both real shell entry points with fake
macOS tool boundaries, including repeat runs, failure/signal cleanup, stale/live
owners, simultaneous recovery, and external output directories. These lifecycle
tests do not constitute a simulator build, UI execution, or device validation.

On macOS, `./gradlew :iosApp:checkIosProjectGeneration` uses real XcodeGen and
`xcodebuild -list` in a disposable source fixture. It verifies the application,
UI-test, and release callers' generated schemes, product names, and load-bearing
configuration without building or booting a simulator. CI and the release gate
run this separately from the fake-tool lifecycle tests.

## Stream-delivery regression matrix

`FakeConnectionPair()` preserves exact write boundaries by default. Opt in to
`WireDelivery.Fragmented(seed = 138)` or `WireDelivery.Coalesced()` for stream
coverage; `forEachWireDelivery` runs all three and prints the selected mode
and seed. Coalescing drains only queued writes, never waits for a full batch,
and caps reads at 8 KiB. Write logs and byte order are unchanged.

Fixture contract tests pin byte conservation, deterministic fragments, queued
coalescing, bounds, EOF, and error propagation. Selected Noise transport,
envelope, session, file-transfer, and authenticated kit integration cases run
the same assertions under every mode. Run them with
`./gradlew :p2p-core:jvmTest :p2p-core:iosSimulatorArm64Test --console=plain`.
These are in-process tests, not kernel short-write/backpressure, independent
interoperability, real filesystem durability, or physical-network evidence.

## Authenticated kit fixtures

Use `commonTest/.../testfixtures/createSecureTestKit` for new secure session
tests. It uses the production builder, real platform cryptography, synthetic
in-memory identity storage, explicit peer authorization, and strict session
invariants. The older `createTestKit` intentionally defaults to plaintext v1;
it is not representative of the shipped security default. Copy fake raw writes
with `CopyingRawConnection` so production buffer wiping cannot mutate queued
fixture bytes. Stop every kit in `finally` and clear stores owned by the test.

`SecureSessionLifecycleTest` gates all four authenticated simultaneous-open
setups before registration, verifies the surviving wire and actual losing
cipher-array wipes, and covers cancellation, outgoing-only reconnect, fresh
epochs, disabled reconnect, and terminal shutdown under all three wire modes.
`KitStrictInvariantsTest` proves the secure fixture's store invariant net.
Run these alongside `SecureSessionIntegrationTest` with the core JVM/native
command above. Provider-internal key erasure, OS identity persistence, physical
network behavior and independent cryptographic assurance are not established
by these synthetic tests.

## Android diagnostic compatibility

The shared sample diagnostics use the pinned Kotlin clock's API-24/25 fallback,
not unguarded `java.time`. UTC evidence naming uses Kotlin's ISO parser while
preserving leap-second/end-of-day normalization and the invalid-input epoch fallback.
NIO file APIs are isolated behind an availability check. Android 24/25 replaces
same-directory evidence through checked POSIX-backed `File.renameTo`, without
deleting the original first; JVM/API-26+ retains the existing NIO provider policy.
No extra desugaring dependency or higher minimum SDK is required. Diagnostic ZIPs
do not promise power-loss durability or atomic publication on every NIO provider.

```bash
./gradlew :p2p-sample-diagnostics:test :p2p-sample-android:lintDebug \
  :p2p-sample-android:assembleDebug --console=plain
```

Missing-class tests exercise actual recorder/export code, failures and repeated replacement;
classloader-local SDK stubs also execute the pinned Kotlin clock's 24/25 branches.
These are host models, not ART. POSIX rename replacement is exercised on supporting
hosts; other hosts assert failure preserves existing bytes rather than skipping.
Inspect packaged call sites and the API guard when changing this boundary. On a
real API24/25 runtime, enable test diagnostics, record a session, export twice and
verify both ZIP checksums and the second export's new events. Repeat on API26+.
Keep that runtime/device validation pending until actually executed.

## Android diagnostic composition tests

```bash
./gradlew :p2p-sample-android:testDebugUnitTest \
  --tests 'dev.p2pkit.sample.android.DiagnosticCompositionTest' --console=plain
```

This suite runs the screen's production snapshot bridge in a real Compose
`Composition`/`Recomposer`, with explicit virtual frames and one collector. It
covers event-only and session-only invalidation, summary refresh, filters,
pause/resume, successful harness clearing without another event, source replacement,
disposal/re-entry and a 20,000-event burst against a bounded recorder. Separate
clear tests preserve failure/retry behavior; source assertions connect the bridge
to the actual screen. Do not substitute an unread delegated local for the revision
key or cache history without invalidating successful clears.

Robolectric supplies API35 tracing/snapshot services in the Android unit-test JVM.
These tests use the configured Gradle daemon JVM; Java17 source/target compatibility
does not select the test fork's runtime. Add `--info` to inspect the actual test-executor
command. The framework is locked/checksummed, an explicit test input, and resolved offline at test runtime;
the test fork is bounded to 1 GiB with a two-minute task deadline. This is host
Compose/snapshot evidence, **not rendered Android UI, ART, physical-device behavior
or frame timing**. On a device, leave the viewer untouched while traffic arrives,
then verify pause, filter changes, resume, clearing and reopening separately.

## Android framework-adapter tests

Run `./gradlew :p2p-network-provisioning-android:verifyAndroidAdapterTests --console=plain`
for the provisioning adapter tier, also required by the module's `check` task.
The tests instantiate the production `WifiManagerWrapperImpl`, handles, and
ownership helpers; Robolectric framework shadows deliver controlled callbacks
and record native calls. Hotspot credentials and lifecycle run on APIs 26/29
and 30/35; Wi-Fi joining, cancellation, binding ownership, and cleanup run on
APIs 29/30/35. The gate rejects missing, empty, failed, or skipped suites and
missing SDK execution markers. The host-test task has a two-minute deadline
enforced by Gradle outside the test JVM; an uninterruptible monitor deadlock
fails the task and terminates the fork, including stuck coroutine/fixture teardown.

Framework JARs are pinned in the version catalog, resolved through Gradle's
locks/checksums, and registered as test inputs. Robolectric's runtime resolver
is offline; it cannot fetch unverified SDKs. API 35 is the newest selected host
SDK compatible with the JDK 17 test toolchain (API 36 requires Java 21).
These are host/shadow tests, not ART, Binder, radio, OEM, permission-revocation,
or physical-device evidence. The broader runtime/target matrix remains tracked
in [#157](https://github.com/p2pKit/P2pKit/issues/157); permission-error mapping
is a separate correction in [#195](https://github.com/p2pKit/P2pKit/issues/195).

## Dependency updates

Dependency and wrapper updates remain fail closed. A version-catalog change
must carry reviewed SHA-256 verification metadata; a wrapper change must carry
the complete wrapper plus its pinned distribution and file checksums. AGP and
the Gradle wrapper are grouped into one Dependabot update because they form one
compatibility unit.

From a dedicated update branch, generate candidates and independently verify
every newly admitted artifact against its repository bytes and publisher
provenance before committing. This maintainer workflow requires `curl`, `gpg`,
an authenticated GitHub CLI (`gh`), and Python 3:

```bash
scripts/prepare-dependency-update.sh origin/main
```

The reviewer also compares an authoritative repository SHA-256 sidecar when
one is published. Maven Central does not publish such a sidecar consistently,
so the normal path requires both an exact match between downloaded bytes and
the committed SHA-256 and a valid detached signature whose issuer identity
matches the independently retrieved public key. If a v4 signature supplies
only its 64-bit issuer key ID, the reviewer requires one exact matching
primary key or subkey and reports the full fingerprint established by
cryptographic verification. A narrowly pinned entry in
`gradle/plugin-provenance-policy.txt` may instead authorize a canonical Gradle
plugin JAR whose GitHub SLSA attestation matches the exact repository, release
tag, workflow, and source commit. Unsigned plugin marker and module metadata is
parsed fail closed and must bind to that trusted JAR and the locked dependency
graph. The script uses an isolated temporary keyring and never adds broad
artifact/key trust to Gradle metadata.

The plugin validator rejects empty input and reads at most one byte beyond
each limit before parsing: marker POMs 64 KiB, module metadata 1 MiB, and
attestation results 8 MiB. The dependency-policy tests cover exact limits,
oversized/growing files, bounded reads, and stream cleanup on failure.

Dependency submission explicitly passes `--dependency-verification strict`:
the pinned Gradle action otherwise disables verification for its entire build.
The injected graph plugin's JAR, module metadata, and POM are checksum-listed
after detached-signature review. When updating that action, review its injected
tooling as well; never disable verification to accommodate new artifacts.
`scripts/tests/release-workflow-test.sh` enforces the strict argument policy.
Local graph generation is not evidence of successful GitHub API submission.

When a direct artifact lookup finds no file, the reviewer can use that
component's checksum-listed, detached-signed `.module` as a locator. It accepts
only an unambiguous local file or sibling-version file within the same
repository, group, and module; metadata is limited to 1 MiB. Both the locator
and the relocated artifact must independently pass checksum and signature
verification. Remote URLs, redirects, ambiguous paths, and unsigned locators
are not supported. This does not expand the unsigned-plugin exception above.

Before pushing, inspect the complete lock and metadata diff and run:

```bash
scripts/check-dependency-update.sh <base-commit> <head-commit>
scripts/run-release-gate.sh
```

CI executes the range-aware update check before Gradle so an incomplete bot PR
fails quickly instead of spending the Complete Gate discovering missing
artifacts. Candidate generation is deliberately not automatic: newly downloaded
checksums are not trusted until the maintainer review succeeds.

Kotlin's built-in ABI validator covers JVM and KLIB outputs but not Android
KMP artifacts. The separate `checkAndroidAbi` tasks read Kotlin metadata from
the compiled Android bytecode, so Android-only declarations such as
`P2pKitAndroid`, the URI file-transfer helper, and Android LAN/provisioning
entry points cannot change silently. An intentional Android API change
requires a manual review followed by the affected module's
`updateAndroidAbi` task.

To revalidate the latest published artifacts rather than the source snapshot:

```bash
P2PKIT_CONSUMER_REPOSITORY_URL=https://repo.maven.apache.org/maven2 \
  scripts/check-published-consumers.sh --latest-published
```

Automated success is not physical-device or hostile-network evidence. See
[validation status](validation-status.md).
