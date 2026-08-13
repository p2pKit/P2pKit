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
