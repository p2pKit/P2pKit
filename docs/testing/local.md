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
