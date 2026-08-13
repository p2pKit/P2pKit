#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CHECKER="$ROOT/scripts/check-android-abi-guard.sh"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-android-abi-policy.XXXXXX")"
FIXTURE="$TMP_ROOT/repository"
trap 'rm -rf "$TMP_ROOT"' EXIT

fail() {
    echo "FATAL: $*" >&2
    exit 1
}

reset_fixture() {
    rm -rf "$FIXTURE"
    mkdir -p \
        "$FIXTURE/.github/workflows" \
        "$FIXTURE/library/p2p-core/api/android" \
        "$FIXTURE/library/p2p-transport-lan/api/android" \
        "$FIXTURE/library/p2p-network-provisioning-android/api/android"
    cp "$ROOT/build.gradle.kts" "$FIXTURE/build.gradle.kts"
    cp "$ROOT/.github/workflows/ci.yml" "$FIXTURE/.github/workflows/ci.yml"
    cp "$ROOT/library/p2p-core/build.gradle.kts" "$FIXTURE/library/p2p-core/build.gradle.kts"
    cp "$ROOT/library/p2p-core/api/android/p2p-core.api" \
        "$FIXTURE/library/p2p-core/api/android/p2p-core.api"
    cp "$ROOT/library/p2p-transport-lan/build.gradle.kts" \
        "$FIXTURE/library/p2p-transport-lan/build.gradle.kts"
    cp "$ROOT/library/p2p-transport-lan/api/android/p2p-transport-lan.api" \
        "$FIXTURE/library/p2p-transport-lan/api/android/p2p-transport-lan.api"
    cp "$ROOT/library/p2p-network-provisioning-android/build.gradle.kts" \
        "$FIXTURE/library/p2p-network-provisioning-android/build.gradle.kts"
    cp "$ROOT/library/p2p-network-provisioning-android/api/android/p2p-network-provisioning-android.api" \
        "$FIXTURE/library/p2p-network-provisioning-android/api/android/p2p-network-provisioning-android.api"
}

remove_matching_lines() {
    local file="$1"
    local text="$2"
    local replacement="$file.new"
    awk -v text="$text" 'index($0, text) == 0 { print }' "$file" >"$replacement"
    mv "$replacement" "$file"
}

expect_rejected() {
    local name="$1"
    local expected="$2"
    local log="$TMP_ROOT/$name.log"
    if "$CHECKER" --root "$FIXTURE" --static-only >"$log" 2>&1; then
        fail "$name mutation was accepted"
    fi
    grep -Fq "$expected" "$log" || {
        cat "$log" >&2
        fail "$name failed for an unexpected reason"
    }
}

reset_fixture
"$CHECKER" --root "$FIXTURE" --static-only >/dev/null

reset_fixture
remove_matching_lines "$FIXTURE/build.gradle.kts" '    ":p2p-network-provisioning-android",'
expect_rejected "missing-module" "project set must contain exactly"

reset_fixture
remove_matching_lines \
    "$FIXTURE/library/p2p-transport-lan/build.gradle.kts" \
    'inputClassesDirs.from(compileAndroidMain.flatMap { it.destinationDirectory })'
expect_rejected "missing-compiler-provider" "compiler-owned class-directory provider"

reset_fixture
remove_matching_lines "$FIXTURE/build.gradle.kts" 'dependsOn(checkAndroidAbi)'
expect_rejected "missing-check-edge" "do not depend on the Android ABI comparison"

reset_fixture
remove_matching_lines \
    "$FIXTURE/.github/workflows/ci.yml" \
    ':p2p-core:checkAndroidAbi :p2p-transport-lan:checkAndroidAbi :p2p-network-provisioning-android:checkAndroidAbi'
expect_rejected "missing-ci-edge" "CI must invoke every Android ABI comparison"

reset_fixture
printf '%s\n' 'public final class dev/p2pkit/transport/lan/AndroidLanDataTransport {' \
    >>"$FIXTURE/library/p2p-transport-lan/api/android/p2p-transport-lan.api"
expect_rejected "internal-symbol-leak" "incorrectly freeze internal symbol"

reset_fixture
remove_matching_lines \
    "$FIXTURE/library/p2p-transport-lan/api/android/p2p-transport-lan.api" \
    'dev/p2pkit/transport/lan/AndroidLanDiag'
expect_rejected "missing-public-symbol" "LAN Android ABI baseline omits"

reset_fixture
printf '%s\n' '// classes/kotlin/android/main' >>"$FIXTURE/build.gradle.kts"
expect_rejected "hardcoded-output" "reconstructs compiler output ownership"

echo "RESULT: PASS — Android ABI policy rejects missing modules, providers, check/CI edges, public symbols, internal leaks, and hardcoded outputs"
