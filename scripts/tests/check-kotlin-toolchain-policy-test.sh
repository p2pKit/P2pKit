#!/usr/bin/env bash
# The quoted expressions below are intentional literal source-policy probes.
# shellcheck disable=SC2016
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CATALOG="$ROOT/gradle/libs.versions.toml"
PROPERTIES="$ROOT/gradle.properties"
CORE_BUILD="$ROOT/library/p2p-core/build.gradle.kts"
LAN_BUILD="$ROOT/library/p2p-transport-lan/build.gradle.kts"
RPC_BUILD="$ROOT/library/p2p-rpc/build.gradle.kts"
RPC_SAMPLE_BUILD="$ROOT/samples/p2p-sample-rpc/build.gradle.kts"
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

# Tripwire: gradle/libs.versions.toml [versions].kotlin; review both on updates,
# never derive this expectation from its subject. See docs/testing/local.md.
grep -Fq 'kotlin = "2.4.20"' "$CATALOG" || fail "Kotlin 2.4.20 is not the catalog toolchain"
# Tripwire: gradle/libs.versions.toml [versions].binary-compatibility-validator.
# This independent metadata-reader expectation must move only after review.
grep -Fq 'binary-compatibility-validator = "0.18.1"' "$CATALOG" ||
    fail "the Android ABI metadata reader is not pinned"
# A current-host refresh cannot discover all Native/AAPT2 host archives.
# Require the independently reviewed classifier set in the pre-build policy.
python3 "$ROOT/scripts/check-host-toolchain-verification.py"
python3 "$ROOT/scripts/tests/check-host-toolchain-verification-test.py"
grep -Fqx 'IOS_MIN_VERSION=14.0' "$PROPERTIES" || fail "the iOS 14 floor is not canonical"
grep -Fqx 'kotlin.native.ignoreDisabledTargets=true' "$PROPERTIES" ||
    fail "Apple Silicon host-mismatch handling is not explicit"

# Stable Kotlin 2.4.20 is the remediation candidate for CVE-2026-53914;
# changing the pin alone does not establish qualification. Keep the existing
# cache isolation even after the compiler update: GitHub builds may retain
# dependency/wrapper caches, never caches/build-cache-1 across trust boundaries.
ruby "$ROOT/scripts/check-gradle-cache-policy.rb"
ruby "$ROOT/scripts/tests/check-gradle-cache-policy-test.rb"
# Maintained modular workers need the JDK21 daemon and JDK17 launcher.
ruby "$ROOT/scripts/tests/check-ci-owned-jdk-policy-test.rb"
python3 -I -B -S "$ROOT/scripts/tests/rpc-apple-ci-setup-test.py"

[[ "$(grep -Fc 'compilerOptions.moduleName.set(project.name)' "$CORE_BUILD")" == "2" ]] ||
    fail "p2p-core does not preserve both JVM and Android module names"
[[ "$(grep -Fc 'compilerOptions.moduleName.set(project.name)' "$LAN_BUILD")" == "2" ]] ||
    fail "p2p-transport-lan does not preserve both JVM and Android module names"
[[ "$(grep -Fc 'compilerOptions.moduleName.set(project.name)' "$RPC_BUILD")" == "2" ]] ||
    fail "p2p-rpc does not declare both JVM and Android module names"
for rpc_build in "$RPC_BUILD" "$RPC_SAMPLE_BUILD"; do
    grep -Fq 'target.binaries.configureEach {' "$rpc_build" ||
        fail "$rpc_build does not apply its iOS floor to all binaries, including tests"
    grep -Fq -- '-Xoverride-konan-properties=minVersion.ios=$minimum' "$rpc_build" ||
        fail "$rpc_build does not use its configured iOS floor"
done
grep -Fq 'compilerOptions.moduleName.set(project.name)' "$ANDROID_PROVISIONING_BUILD" ||
    fail "Android provisioning does not preserve its module name"
grep -Fq 'compilerOptions.moduleName.set(project.name)' "$DESKTOP_PROVISIONING_BUILD" ||
    fail "Desktop provisioning does not preserve its module name"

# The real Gradle graph probe is an explicit full CI/release command. Keep
# this policy-only entry static so each complete gate probes the graph once.
"$ROOT/scripts/check-android-abi-guard.sh" --static-only
"$ROOT/scripts/tests/check-android-abi-guard-policy-test.sh"

grep -Fq -- '-Xoverride-konan-properties=minVersion.ios=$iosMinimumVersion' "$LAN_BUILD" ||
    fail "the repository XCFramework does not apply the canonical iOS floor"
grep -Fq 'KOTLIN_VERSION="$(sed ' "$CONSUMER_GATE" ||
    fail "the isolated consumer does not derive Kotlin from the catalog"
grep -Fq 'AGP_VERSION="$(sed ' "$CONSUMER_GATE" ||
    fail "the isolated consumer does not derive AGP from the catalog"
grep -Fq -- '-Xoverride-konan-properties=minVersion.ios=$IOS_MIN_VERSION' "$CONSUMER_GATE" ||
    fail "the isolated KMP consumer does not link at the canonical iOS floor"
# The caller selects fixed publication tasks through an array. Guard the actual
# ordinary/executor publication AND consumer calls, not an obsolete literal task.
ruby "$ROOT/scripts/check-consumer-gradle-policy.rb" "$CONSUMER_GATE"
# Consumer versions are inputs, unlike the catalog tripwires above. Enforce
# the variable-based recipe rather than banning one historical Kotlin pin.
ruby "$ROOT/scripts/check-version-input-policy.rb" consumer "$CONSUMER_GATE"
ruby "$ROOT/scripts/tests/check-version-input-policy-test.rb"

# Retain only the previously reviewed isolated ABI-reader exceptions while
# the maintained writer establishes the new KGP ABI graph. The Android-only
# guard still pins its separate 2.3.21 metadata reader; it is not the affected
# Kotlin Gradle plugin. No 2.3.21 component may leak into compiler, application,
# test, publication, or consumer classpaths.
while IFS= read -r legacy_match; do
    legacy_entry="${legacy_match#*:}"
    legacy_entry="${legacy_entry#*:}"
    ruby "$ROOT/scripts/check-version-input-policy.rb" kotlin-abi-entry "$legacy_entry" >/dev/null ||
        fail "stale Kotlin 2.3.21 dependency escaped the isolated ABI toolchain: $legacy_match"
done < <(grep -R -n -E --include='gradle.lockfile' '2\.3\.21' "$ROOT" || true)

grep -Fq 'check_rc2_legacy_jvm_symbols' "$PUBLICATION_GATE" ||
    fail "published artifacts do not retain the supplemental RC2 JVM-symbol guard"

[[ -x "$XCFRAMEWORK_GATE" ]] || fail "the XCFramework minimum-OS gate is not executable"
# Ordinary CI uses the maintained modular worker and component commands.
# Retired custody AST fingerprints are not contracts for the replacement.
ruby "$ROOT/scripts/check-hosted-test-workflow-policy.rb" "$CI_WORKFLOW"
ruby "$ROOT/scripts/tests/check-modular-ci-policy-test.rb"
grep -Fq 'scripts/check-xcframework-minimum-os.sh' "$RELEASE_GATE" ||
    fail "the release gate does not verify the linked XCFramework deployment floor"

bash -n "$CONSUMER_GATE"
bash -n "$PUBLICATION_GATE"
bash -n "$XCFRAMEWORK_GATE"

echo "RESULT: PASS — Kotlin 2.4 module identities, compiler-owned Android ABI guards, dynamic consumers, and the iOS 14 binary floor are locked"
