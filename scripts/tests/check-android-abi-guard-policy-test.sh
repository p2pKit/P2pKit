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
        "$FIXTURE/scripts/tests" \
        "$FIXTURE/library/p2p-core/api/android" \
        "$FIXTURE/library/p2p-transport-lan/api/android" \
        "$FIXTURE/library/p2p-network-provisioning-android/api/android"
    cp "$ROOT/build.gradle.kts" "$FIXTURE/build.gradle.kts"
    cp "$ROOT/.github/workflows/ci.yml" "$FIXTURE/.github/workflows/ci.yml"
    cp "$ROOT/scripts/run-release-gate.sh" "$FIXTURE/scripts/run-release-gate.sh"
    for policy_input in \
        check-heavy-job-queue-policy.rb check-hosted-test-workflow-policy.rb check-hosted-test-composition.py \
        run-hosted-test-custody.py hosted_full_supplements.py hosted_primary_abi.py \
        run-platform-tests.py run-audit-command.py hosted_dependency_seed_files.py; do
        cp "$ROOT/scripts/$policy_input" "$FIXTURE/scripts/$policy_input"
    done
    cp "$ROOT/scripts/tests/check-kotlin-toolchain-policy-test.sh" \
        "$FIXTURE/scripts/tests/check-kotlin-toolchain-policy-test.sh"
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
    'scripts/run-hosted-test-custody.py run --profile full --seed-dependencies'
expect_rejected "missing-ci-edge" "CI ordinary FULL caller policy failed"

reset_fixture
sed 's/"checkAndroidAbi"/"checkKotlinAbi"/g' "$FIXTURE/scripts/hosted_primary_abi.py" \
    >"$FIXTURE/scripts/hosted_primary_abi.py.new"
mv "$FIXTURE/scripts/hosted_primary_abi.py.new" "$FIXTURE/scripts/hosted_primary_abi.py"
expect_rejected "missing-three-android-comparisons" \
    "ordinary executable composition changed: scripts/hosted_primary_abi.py"

# Mutate the real composed graph command instead of a no-longer-executable
# YAML/comment string. No supplier module is imported or executed by this test.
for mutation in removed static-only commented duplicated ignored-failure; do
    reset_fixture
    python3 -I -B -S - "$FIXTURE/scripts/hosted_full_supplements.py" "$mutation" <<'PY'
from pathlib import Path
import sys
path, mutation = Path(sys.argv[1]), sys.argv[2]
before = '        ("command", ["bash", "scripts/check-android-abi-guard.sh"]),'
after = {
    "removed": "",
    "static-only": '        ("command", ["bash", "scripts/check-android-abi-guard.sh", "--static-only"]),',
    "commented": "#" + before,
    "duplicated": before + "\n" + before,
    "ignored-failure": '        ("command", ["bash", "-c", "scripts/check-android-abi-guard.sh || true"]),',
}[mutation]
source = path.read_text(encoding="utf-8")
assert source.count(before) == 1, "fixture must mutate the actual graph command once"
path.write_text(source.replace(before, after), encoding="utf-8")
PY
    expect_rejected "ci-graph-$mutation" \
        "ordinary executable composition changed: scripts/hosted_full_supplements.py"
done

# Keep the actual graph probe reachable exactly once from each complete gate.
# These fixtures need no wrapper: --static-only must enforce the caller policy.
for mutation in removed static-only commented duplicated ignored-failure; do
        reset_fixture
        caller="$FIXTURE/scripts/run-release-gate.sh"
        awk -v mutation="$mutation" '
            /scripts\/check-android-abi-guard\.sh/ {
                if (mutation == "removed") next
                if (mutation == "static-only") { print $0 " --static-only"; next }
                if (mutation == "commented") { print "#" $0; next }
                if (mutation == "duplicated") { print; print; next }
                if (mutation == "ignored-failure") { print $0 " || true"; next }
            }
            { print }
        ' "$caller" >"$caller.new"
        mv "$caller.new" "$caller"
        expect_rejected "release-graph-$mutation" \
            "release gate must invoke the Android ABI task-graph verification in full mode exactly once"
done

reset_fixture
sed 's/ --static-only$//' "$FIXTURE/scripts/tests/check-kotlin-toolchain-policy-test.sh" \
    >"$FIXTURE/scripts/tests/check-kotlin-toolchain-policy-test.sh.new"
mv "$FIXTURE/scripts/tests/check-kotlin-toolchain-policy-test.sh.new" \
    "$FIXTURE/scripts/tests/check-kotlin-toolchain-policy-test.sh"
expect_rejected "hidden-full-probe" "toolchain policy must invoke Android ABI verification with --static-only"

reset_fixture
printf '%s\n' "\"\$ROOT/scripts/check-android-abi-guard.sh\"" \
    >>"$FIXTURE/scripts/tests/check-kotlin-toolchain-policy-test.sh"
expect_rejected "duplicate-hidden-probe" "toolchain policy must not duplicate the Android ABI verification"

reset_fixture
remove_matching_lines "$FIXTURE/scripts/tests/check-kotlin-toolchain-policy-test.sh" \
    'scripts/check-android-abi-guard.sh'
expect_rejected "missing-static-policy-call" "toolchain policy must invoke Android ABI verification with --static-only"

reset_fixture
printf '%s\n' "\"\$ROOT/scripts/check-android-abi-guard.sh\" --static-only" \
    >>"$FIXTURE/scripts/tests/check-kotlin-toolchain-policy-test.sh"
expect_rejected "duplicate-static-policy-call" "toolchain policy must invoke Android ABI verification with --static-only"

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

echo "RESULT: PASS — Android ABI policy rejects broken module/compiler/check/CI wiring, missing or nonblocking full-mode graph probes, duplicate hidden probes, public-symbol loss, internal leaks, and hardcoded outputs"
