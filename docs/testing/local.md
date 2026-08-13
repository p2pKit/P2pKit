# Local testing

Use JDK 17 and the checked-in Gradle wrapper. macOS with the configured Xcode
toolchain is required for Apple targets and the complete release gate.

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

## Dependency updates

Dependency and wrapper updates remain fail closed. A version-catalog change
must carry reviewed SHA-256 verification metadata; a wrapper change must carry
the complete wrapper plus its pinned distribution and file checksums. AGP and
the Gradle wrapper are grouped into one Dependabot update because they form one
compatibility unit.

From a dedicated update branch, generate candidates and independently verify
every newly admitted artifact against its repository bytes and detached OpenPGP
signature before committing:

```bash
scripts/prepare-dependency-update.sh origin/main
```

The reviewer also compares an authoritative repository SHA-256 sidecar when
one is published. Maven Central does not publish such a sidecar consistently,
so those entries require both an exact match between downloaded bytes and the
committed SHA-256 and a valid detached signature whose issuer fingerprint
matches the independently retrieved public key. The script uses an isolated
temporary keyring and never adds broad artifact/key trust to Gradle metadata.

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
