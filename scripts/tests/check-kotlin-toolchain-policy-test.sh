#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CATALOG="$ROOT/gradle/libs.versions.toml"
PROPERTIES="$ROOT/gradle.properties"
ROOT_BUILD="$ROOT/build.gradle.kts"
CORE_BUILD="$ROOT/library/p2p-core/build.gradle.kts"
LAN_BUILD="$ROOT/library/p2p-transport-lan/build.gradle.kts"
ANDROID_PROVISIONING_BUILD="$ROOT/library/p2p-network-provisioning-android/build.gradle.kts"
DESKTOP_PROVISIONING_BUILD="$ROOT/library/p2p-network-provisioning-desktop/build.gradle.kts"
CONSUMER_GATE="$ROOT/scripts/check-published-consumers.sh"
PUBLICATION_GATE="$ROOT/scripts/check-publish-artifacts.sh"
XCFRAMEWORK_GATE="$ROOT/scripts/check-xcframework-minimum-os.sh"
CI_WORKFLOW="$ROOT/.github/workflows/ci.yml"
RELEASE_GATE="$ROOT/scripts/run-release-gate.sh"

fail() {
    echo "FATAL: $*" >&2
    exit 1
}

grep -Fq 'kotlin = "2.4.10"' "$CATALOG" || fail "Kotlin 2.4.10 is not the catalog toolchain"
grep -Fq 'binary-compatibility-validator = "0.18.1"' "$CATALOG" ||
    fail "the Android ABI metadata reader is not pinned"
grep -Fqx 'IOS_MIN_VERSION=14.0' "$PROPERTIES" || fail "the iOS 14 floor is not canonical"
grep -Fqx 'kotlin.native.ignoreDisabledTargets=true' "$PROPERTIES" ||
    fail "Apple Silicon host-mismatch handling is not explicit"

[[ "$(grep -Fc 'compilerOptions.moduleName.set(project.name)' "$CORE_BUILD")" == "2" ]] ||
    fail "p2p-core does not preserve both JVM and Android module names"
[[ "$(grep -Fc 'compilerOptions.moduleName.set(project.name)' "$LAN_BUILD")" == "2" ]] ||
    fail "p2p-transport-lan does not preserve both JVM and Android module names"
grep -Fq 'compilerOptions.moduleName.set(project.name)' "$ANDROID_PROVISIONING_BUILD" ||
    fail "Android provisioning does not preserve its module name"
grep -Fq 'compilerOptions.moduleName.set(project.name)' "$DESKTOP_PROVISIONING_BUILD" ||
    fail "Desktop provisioning does not preserve its module name"

grep -Fq 'alias(libs.plugins.binary.compatibility.validator) apply false' "$ROOT_BUILD" ||
    fail "the Kotlin-aware Android ABI dumper is not available to the build"
for android_abi_project in \
    ':p2p-core' \
    ':p2p-transport-lan' \
    ':p2p-network-provisioning-android'; do
    grep -Fq "\"$android_abi_project\"" "$ROOT_BUILD" ||
        fail "$android_abi_project is missing from Android ABI coverage"
done
grep -Fq 'tasks.register<KotlinApiBuildTask>("buildAndroidAbi")' "$ROOT_BUILD" ||
    fail "the Android ABI extraction task is missing"
grep -Fq 'tasks.register<KotlinApiCompareTask>("checkAndroidAbi")' "$ROOT_BUILD" ||
    fail "the Android ABI comparison task is missing"
grep -Fq ':p2p-core:checkAndroidAbi :p2p-transport-lan:checkAndroidAbi :p2p-network-provisioning-android:checkAndroidAbi' "$CI_WORKFLOW" ||
    fail "CI does not invoke every Android ABI comparison explicitly"

CORE_ANDROID_ABI="$ROOT/library/p2p-core/api/android/p2p-core.api"
LAN_ANDROID_ABI="$ROOT/library/p2p-transport-lan/api/android/p2p-transport-lan.api"
PROVISIONING_ANDROID_ABI="$ROOT/library/p2p-network-provisioning-android/api/android/p2p-network-provisioning-android.api"
for required_signature in \
    'dev/p2pkit/core/AndroidNetworkPathObserver' \
    'dev/p2pkit/core/android/P2pKitAndroid' \
    'dev/p2pkit/core/transfer/FileTransferAndroidKt'; do
    grep -Fq "$required_signature" "$CORE_ANDROID_ABI" ||
        fail "the core Android ABI baseline omits $required_signature"
done
for required_signature in \
    'dev/p2pkit/transport/lan/AndroidLanDiag' \
    'dev/p2pkit/transport/lan/AndroidLanDslKt'; do
    grep -Fq "$required_signature" "$LAN_ANDROID_ABI" ||
        fail "the LAN Android ABI baseline omits $required_signature"
done
for required_signature in \
    'dev/p2pkit/provisioning/android/AndroidNetworkProvisioningManager' \
    'dev/p2pkit/provisioning/android/AndroidProvisioningFactory'; do
    grep -Fq "$required_signature" "$PROVISIONING_ANDROID_ABI" ||
        fail "the provisioning Android ABI baseline omits $required_signature"
done

grep -Fq -- '-Xoverride-konan-properties=minVersion.ios=$iosMinimumVersion' "$LAN_BUILD" ||
    fail "the repository XCFramework does not apply the canonical iOS floor"
grep -Fq 'KOTLIN_VERSION="$(sed ' "$CONSUMER_GATE" ||
    fail "the isolated consumer does not derive Kotlin from the catalog"
grep -Fq 'AGP_VERSION="$(sed ' "$CONSUMER_GATE" ||
    fail "the isolated consumer does not derive AGP from the catalog"
grep -Fq -- '-Xoverride-konan-properties=minVersion.ios=$IOS_MIN_VERSION' "$CONSUMER_GATE" ||
    fail "the isolated KMP consumer does not link at the canonical iOS floor"
grep -Fq './gradlew --no-daemon --console=plain publishToMavenLocal' "$CONSUMER_GATE" ||
    fail "the isolated publication fixture may leave a Gradle daemon racing cleanup"
grep -Fq './gradlew --no-daemon --console=plain -p "$FIXTURE_DIR"' "$CONSUMER_GATE" ||
    fail "the isolated consumer fixture may leave a Gradle daemon racing cleanup"
if grep -Fq 'version "2.3.21"' "$CONSUMER_GATE"; then
    fail "the isolated consumer retains a stale hardcoded Kotlin version"
fi

# Kotlin 2.4.10 intentionally embeds the preceding ABI-tools release in its
# isolated kotlinInternalAbiValidation configuration. The Android-only ABI
# guard uses the same metadata reader in its isolated androidAbiRuntime
# configuration. No 2.3.21 component may leak into compiler, application,
# test, publication, or consumer classpaths.
while IFS= read -r legacy_match; do
    legacy_entry="${legacy_match#*:}"
    legacy_entry="${legacy_entry#*:}"
    case "$legacy_entry" in
        org.jetbrains.kotlin:abi-tools-api:2.3.21=kotlinInternalAbiValidation | \
        org.jetbrains.kotlin:abi-tools:2.3.21=kotlinInternalAbiValidation | \
        org.jetbrains.kotlin:kotlin-klib-abi-reader:2.3.21=kotlinInternalAbiValidation | \
        org.jetbrains.kotlin:kotlin-metadata-jvm:2.3.21=kotlinInternalAbiValidation | \
        org.jetbrains.kotlin:kotlin-metadata-jvm:2.3.21=androidAbiRuntime,kotlinInternalAbiValidation | \
        org.jetbrains.kotlin:kotlin-stdlib:2.3.21=kotlinInternalAbiValidation | \
        org.jetbrains.kotlin:kotlin-stdlib:2.3.21=androidAbiRuntime,kotlinInternalAbiValidation)
            ;;
        *)
            fail "stale Kotlin 2.3.21 dependency escaped the isolated ABI toolchain: $legacy_match"
            ;;
    esac
done < <(rg -n '2\.3\.21' --glob 'gradle.lockfile' "$ROOT" || true)

grep -Fq 'check_rc2_legacy_jvm_symbols' "$PUBLICATION_GATE" ||
    fail "published artifacts do not retain the supplemental RC2 JVM-symbol guard"

[[ -x "$XCFRAMEWORK_GATE" ]] || fail "the XCFramework minimum-OS gate is not executable"
grep -Fq 'scripts/check-xcframework-minimum-os.sh' "$CI_WORKFLOW" ||
    fail "CI does not verify the linked XCFramework deployment floor"
grep -Fq 'scripts/check-xcframework-minimum-os.sh' "$RELEASE_GATE" ||
    fail "the release gate does not verify the linked XCFramework deployment floor"

bash -n "$CONSUMER_GATE"
bash -n "$PUBLICATION_GATE"
bash -n "$XCFRAMEWORK_GATE"

echo "RESULT: PASS — Kotlin 2.4 module identities, dynamic consumers, and the iOS 14 binary floor are locked"
