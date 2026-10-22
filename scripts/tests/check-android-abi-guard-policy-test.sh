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
        "$FIXTURE/library/p2p-core/api/android-bcv" \
        "$FIXTURE/library/p2p-transport-lan/api/android-bcv" \
        "$FIXTURE/library/p2p-rpc/api/android-bcv" \
        "$FIXTURE/library/p2p-network-provisioning-android/api/android-bcv"
    cp "$ROOT/build.gradle.kts" "$FIXTURE/build.gradle.kts"
    cp "$ROOT/.github/workflows/"*.yml "$FIXTURE/.github/workflows/"
    cp "$ROOT/scripts/run-release-gate.sh" "$FIXTURE/scripts/run-release-gate.sh"
    for policy_input in check-modular-ci-policy.rb ci_component.py; do
        cp "$ROOT/scripts/$policy_input" "$FIXTURE/scripts/$policy_input"
    done
    cp "$ROOT/scripts/tests/check-kotlin-toolchain-policy-test.sh" \
        "$FIXTURE/scripts/tests/check-kotlin-toolchain-policy-test.sh"
    cp "$ROOT/library/p2p-core/build.gradle.kts" "$FIXTURE/library/p2p-core/build.gradle.kts"
    cp "$ROOT/library/p2p-core/api/android-bcv/p2p-core.api" \
        "$FIXTURE/library/p2p-core/api/android-bcv/p2p-core.api"
    cp "$ROOT/library/p2p-transport-lan/build.gradle.kts" \
        "$FIXTURE/library/p2p-transport-lan/build.gradle.kts"
    cp "$ROOT/library/p2p-transport-lan/api/android-bcv/p2p-transport-lan.api" \
        "$FIXTURE/library/p2p-transport-lan/api/android-bcv/p2p-transport-lan.api"
    cp "$ROOT/library/p2p-rpc/build.gradle.kts" "$FIXTURE/library/p2p-rpc/build.gradle.kts"
    cp "$ROOT/library/p2p-rpc/api/android-bcv/p2p-rpc.api" "$FIXTURE/library/p2p-rpc/api/android-bcv/p2p-rpc.api"
    cp "$ROOT/library/p2p-network-provisioning-android/build.gradle.kts" \
        "$FIXTURE/library/p2p-network-provisioning-android/build.gradle.kts"
    cp "$ROOT/library/p2p-network-provisioning-android/api/android-bcv/p2p-network-provisioning-android.api" \
        "$FIXTURE/library/p2p-network-provisioning-android/api/android-bcv/p2p-network-provisioning-android.api"
    # Keep original source read-only; mutations belong to this private copy.
    chmod -R u+w "$FIXTURE"
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
rm "$FIXTURE/scripts/ci_component.py"
expect_rejected "missing-component-supplier" "Modular ABI command policy failed"

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
ci_run='    uses: ./.github/workflows/ci-component.yml'
[[ "$(grep -Fxc "$ci_run" "$FIXTURE/.github/workflows/ci.yml")" == 1 ]] ||
    fail "fixture must remove the actual component route exactly once"
remove_matching_lines "$FIXTURE/.github/workflows/ci.yml" "$ci_run"
expect_rejected "missing-ci-edge" "Modular CI policy failed"

reset_fixture
sed 's/:checkAndroidAbi/:checkKotlinAbi/g' "$FIXTURE/scripts/ci_component.py" >"$FIXTURE/scripts/ci_component.py.new"
mv "$FIXTURE/scripts/ci_component.py.new" "$FIXTURE/scripts/ci_component.py"
expect_rejected "missing-four-android-comparisons" "Modular ABI command policy failed"

# Mutate the actual modular graph command, not a retired custody supplier.
for mutation in removed static-only commented duplicated ignored-failure; do
    reset_fixture
    python3 -I -B -S - "$FIXTURE/scripts/ci_component.py" "$mutation" <<'PY'
from pathlib import Path
import sys
path, mutation = Path(sys.argv[1]), sys.argv[2]
before = "        return [('abi-graph', bash + ['scripts/check-android-abi-guard.sh']),"
after = {
    "removed": "        return [",
    "static-only": "        return [('abi-graph', bash + ['scripts/check-android-abi-guard.sh', '--static-only']),",
    "commented": "        return [ # ('abi-graph', bash + ['scripts/check-android-abi-guard.sh']),",
    "duplicated": before + "\n                ('abi-graph', bash + ['scripts/check-android-abi-guard.sh']),",
    "ignored-failure": "        return [('abi-graph', bash + ['-c', 'scripts/check-android-abi-guard.sh || true']),",
}[mutation]
source = path.read_text(encoding="utf-8")
assert source.count(before) == 1, "fixture must mutate the actual graph command once"
path.write_text(source.replace(before, after), encoding="utf-8")
PY
    expect_rejected "ci-graph-$mutation" "Modular ABI command policy failed"
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
    >>"$FIXTURE/library/p2p-transport-lan/api/android-bcv/p2p-transport-lan.api"
expect_rejected "internal-symbol-leak" "incorrectly freeze internal symbol"

for signature in \
    'public final class dev/p2pkit/rpc/internal/RpcHostEngine {' \
    '    public fun <init> (Ldev/p2pkit/rpc/internal/RpcHostEngine;)V' \
    '    public fun getEngine ()Ldev/p2pkit/rpc/internal/RpcHostEngine;' \
    '    public static synthetic fun accessor ()Ldev/p2pkit/rpc/internal/RpcHostEngine;' \
    '    public static final field engine Ldev/p2pkit/rpc/internal/RpcHostEngine;' \
    '    public synthetic fun <init> (Ldev/p2pkit/rpc/internal/RpcHostEngine;)V'; do
    reset_fixture
    printf '%s\n' "$signature" >>"$FIXTURE/library/p2p-rpc/api/android-bcv/p2p-rpc.api"
    expect_rejected "rpc-internal-api-leak" "incorrectly freeze internal symbol"
done

# The genuine generated baseline already includes the private-constructor bridge.
# Exercise that exact permitted shape separately without making internal classes
# or non-constructor synthetic accessors acceptable API.
reset_fixture
printf '%s\n' \
    '    public synthetic fun <init> (Ldev/p2pkit/rpc/internal/RpcHostEngine;Lkotlin/jvm/internal/DefaultConstructorMarker;)V' \
    >>"$FIXTURE/library/p2p-rpc/api/android-bcv/p2p-rpc.api"
"$CHECKER" --root "$FIXTURE" --static-only >/dev/null

reset_fixture
remove_matching_lines \
    "$FIXTURE/library/p2p-transport-lan/api/android-bcv/p2p-transport-lan.api" \
    'dev/p2pkit/transport/lan/AndroidLanDiag'
expect_rejected "missing-public-symbol" "LAN Android ABI baseline omits"

reset_fixture
printf '%s\n' '// classes/kotlin/android/main' >>"$FIXTURE/build.gradle.kts"
expect_rejected "hardcoded-output" "reconstructs compiler output ownership"

echo "RESULT: PASS — Android ABI policy rejects broken module/compiler/check/CI wiring, missing or nonblocking full-mode graph probes, duplicate hidden probes, public-symbol loss, internal leaks, and hardcoded outputs"
