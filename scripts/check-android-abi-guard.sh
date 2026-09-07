#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STATIC_ONLY=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --root)
            [[ $# -ge 2 ]] || {
                echo "FATAL: --root requires a path" >&2
                exit 2
            }
            ROOT="$2"
            shift 2
            ;;
        --static-only)
            STATIC_ONLY=true
            shift
            ;;
        *)
            echo "FATAL: unsupported argument: $1" >&2
            exit 2
            ;;
    esac
done

fail() {
    echo "FATAL: $*" >&2
    exit 1
}

ROOT_BUILD="$ROOT/build.gradle.kts"
CI_WORKFLOW="$ROOT/.github/workflows/ci.yml"
RELEASE_GATE="$ROOT/scripts/run-release-gate.sh"
TOOLCHAIN_POLICY="$ROOT/scripts/tests/check-kotlin-toolchain-policy-test.sh"
CORE_BUILD="$ROOT/library/p2p-core/build.gradle.kts"
LAN_BUILD="$ROOT/library/p2p-transport-lan/build.gradle.kts"
PROVISIONING_BUILD="$ROOT/library/p2p-network-provisioning-android/build.gradle.kts"
CORE_API="$ROOT/library/p2p-core/api/android/p2p-core.api"
LAN_API="$ROOT/library/p2p-transport-lan/api/android/p2p-transport-lan.api"
PROVISIONING_API="$ROOT/library/p2p-network-provisioning-android/api/android/p2p-network-provisioning-android.api"

for required_file in \
    "$ROOT_BUILD" \
    "$CI_WORKFLOW" \
    "$RELEASE_GATE" \
    "$TOOLCHAIN_POLICY" \
    "$CORE_BUILD" \
    "$LAN_BUILD" \
    "$PROVISIONING_BUILD" \
    "$CORE_API" \
    "$LAN_API" \
    "$PROVISIONING_API"; do
    [[ -f "$required_file" ]] || fail "Android ABI policy input is missing: $required_file"
done

grep -Fq 'alias(libs.plugins.binary.compatibility.validator) apply false' "$ROOT_BUILD" ||
    fail "the Kotlin-aware Android ABI dumper is not available to the build"

project_block="$(sed -n \
    '/^val androidAbiProjects = setOf($/,/^)/p' \
    "$ROOT_BUILD")"
[[ -n "$project_block" ]] || fail "the Android ABI project set is missing"
[[ "$(grep -Ec '^    ":[^"]+",$' <<<"$project_block")" == "3" ]] ||
    fail "the Android ABI project set must contain exactly the three published Android modules"

android_abi_projects=(
    ':p2p-core'
    ':p2p-transport-lan'
    ':p2p-network-provisioning-android'
)
for project in "${android_abi_projects[@]}"; do
    [[ "$(grep -Fxc "    \"$project\"," <<<"$project_block")" == "1" ]] ||
        fail "$project is missing or duplicated in Android ABI coverage"
done

[[ "$(grep -Fc 'tasks.register<KotlinApiBuildTask>("buildAndroidAbi")' "$ROOT_BUILD")" == "1" ]] ||
    fail "the Android ABI extraction task must be registered exactly once"
[[ "$(grep -Fc 'tasks.register<KotlinApiCompareTask>("checkAndroidAbi")' "$ROOT_BUILD")" == "1" ]] ||
    fail "the Android ABI comparison task must be registered exactly once"
[[ "$(grep -Fc 'tasks.matching { it.name == "check" }.configureEach' "$ROOT_BUILD")" == "1" ]] ||
    fail "module check tasks do not select the Android ABI comparison exactly once"
[[ "$(grep -Fc 'dependsOn(checkAndroidAbi)' "$ROOT_BUILD")" == "1" ]] ||
    fail "module check tasks do not depend on the Android ABI comparison exactly once"
if grep -Fq 'classes/kotlin/android/main' "$ROOT_BUILD" ||
    grep -Fq 'dependsOn("compileAndroidMain")' "$ROOT_BUILD"; then
    fail "the Android ABI guard reconstructs compiler output ownership"
fi

module_builds=("$CORE_BUILD" "$LAN_BUILD" "$PROVISIONING_BUILD")
for module_build in "${module_builds[@]}"; do
    [[ "$(grep -Fc 'tasks.named<KotlinCompile>("compileAndroidMain")' "$module_build")" == "1" ]] ||
        fail "$module_build must select exactly one typed Android compiler task"
    [[ "$(grep -Fc 'inputClassesDirs.from(compileAndroidMain.flatMap { it.destinationDirectory })' "$module_build")" == "1" ]] ||
        fail "$module_build must consume exactly one compiler-owned class-directory provider"
done

ci_command=':p2p-core:checkAndroidAbi :p2p-transport-lan:checkAndroidAbi :p2p-network-provisioning-android:checkAndroidAbi'
[[ "$(grep -Fc "$ci_command" "$CI_WORKFLOW")" == "1" ]] ||
    fail "CI must invoke every Android ABI comparison together exactly once"

# An explicit comparison does not prove module check owns it. The full-mode
# graph probe is a separate, load-bearing command in both complete gates.
# Match executable, unflagged lines, not comments, --static-only or || true.
require_full_graph_call() {
    local file="$1"
    local gate="$2"
    [[ "$(grep -Ec '^[[:space:]]*scripts/check-android-abi-guard\.sh[[:space:]]*$' "$file")" == "1" ]] ||
        fail "$gate must invoke the Android ABI task-graph verification in full mode exactly once"
}

require_full_graph_call "$CI_WORKFLOW" "CI"
require_full_graph_call "$RELEASE_GATE" "release gate"

# Static policy (also exercised by its own fixture suite) protects the direct
# calls even when a maintainer removes them. Do not hide a second Gradle run
# in this nested script or remove its independently exercised static check.
static_call="\"\$ROOT/scripts/check-android-abi-guard.sh\" --static-only"
[[ "$(grep -Fxc "$static_call" "$TOOLCHAIN_POLICY")" == "1" ]] ||
    fail "toolchain policy must invoke Android ABI verification with --static-only exactly once"
[[ "$(grep -Ec '^[[:space:]]*"[$]ROOT/scripts/check-android-abi-guard\.sh"([[:space:]]|$)' "$TOOLCHAIN_POLICY")" == "1" ]] ||
    fail "toolchain policy must not duplicate the Android ABI verification invocation"

required_core=(
    'dev/p2pkit/core/AndroidNetworkPathObserver'
    'dev/p2pkit/core/android/P2pKitAndroid'
    'dev/p2pkit/core/transfer/FileTransferAndroidKt'
)
required_lan=(
    'dev/p2pkit/transport/lan/AndroidLanDiag'
    'dev/p2pkit/transport/lan/AndroidLanDslKt'
)
required_provisioning=(
    'dev/p2pkit/provisioning/android/AndroidNetworkProvisioningManager'
    'dev/p2pkit/provisioning/android/AndroidProvisioningFactory'
)
for signature in "${required_core[@]}"; do
    grep -Fq "$signature" "$CORE_API" || fail "the core Android ABI baseline omits $signature"
done
for signature in "${required_lan[@]}"; do
    grep -Fq "$signature" "$LAN_API" || fail "the LAN Android ABI baseline omits $signature"
done
for signature in "${required_provisioning[@]}"; do
    grep -Fq "$signature" "$PROVISIONING_API" ||
        fail "the provisioning Android ABI baseline omits $signature"
done

# Metadata-aware extraction intentionally omits Kotlin-internal implementation
# classes even though their JVM bytecode is present in the compiler output.
for internal_signature in \
    'dev/p2pkit/core/AndroidNetworkPathListener' \
    'dev/p2pkit/transport/lan/AndroidLanDataTransport' \
    'dev/p2pkit/provisioning/android/WifiManagerWrapper'; do
    if grep -Fq "$internal_signature" "$CORE_API" ||
        grep -Fq "$internal_signature" "$LAN_API" ||
        grep -Fq "$internal_signature" "$PROVISIONING_API"; then
        fail "Android ABI baselines incorrectly freeze internal symbol $internal_signature"
    fi
done

if [[ "$STATIC_ONLY" == "false" ]]; then
    [[ -x "$ROOT/gradlew" ]] || fail "Gradle wrapper is unavailable for Android ABI graph verification"
    task_graph="$(
        cd "$ROOT"
        ./gradlew \
            :p2p-core:check \
            :p2p-transport-lan:check \
            :p2p-network-provisioning-android:check \
            --dependency-verification=strict \
            --dry-run --console=plain
    )" || fail "Android ABI task graph dry-run failed"
    for project in "${android_abi_projects[@]}"; do
        grep -Fq "$project:compileAndroidMain SKIPPED" <<<"$task_graph" ||
            fail "$project check does not own the Android compiler producer"
        grep -Fq "$project:buildAndroidAbi SKIPPED" <<<"$task_graph" ||
            fail "$project check omits Android ABI extraction"
        grep -Fq "$project:checkAndroidAbi SKIPPED" <<<"$task_graph" ||
            fail "$project check omits Android ABI comparison"
    done
fi

echo "RESULT: PASS — Android ABI module coverage, typed compiler ownership, metadata filtering, and check/CI wiring are intact"
