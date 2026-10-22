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
RPC_BUILD="$ROOT/library/p2p-rpc/build.gradle.kts"
PROVISIONING_BUILD="$ROOT/library/p2p-network-provisioning-android/build.gradle.kts"
CORE_API="$ROOT/library/p2p-core/api/android-bcv/p2p-core.api"
LAN_API="$ROOT/library/p2p-transport-lan/api/android-bcv/p2p-transport-lan.api"
RPC_API="$ROOT/library/p2p-rpc/api/android-bcv/p2p-rpc.api"
PROVISIONING_API="$ROOT/library/p2p-network-provisioning-android/api/android-bcv/p2p-network-provisioning-android.api"

for required_file in \
    "$ROOT_BUILD" \
    "$CI_WORKFLOW" \
    "$RELEASE_GATE" \
    "$TOOLCHAIN_POLICY" \
    "$CORE_BUILD" \
    "$LAN_BUILD" \
    "$RPC_BUILD" \
    "$PROVISIONING_BUILD" \
    "$CORE_API" \
    "$LAN_API" \
    "$RPC_API" \
    "$PROVISIONING_API"; do
    [[ -f "$required_file" ]] || fail "Android ABI policy input is missing: $required_file"
done

grep -Fq 'alias(libs.plugins.binary.compatibility.validator) apply false' "$ROOT_BUILD" ||
    fail "the Kotlin-aware Android ABI dumper is not available to the build"

project_block="$(sed -n \
    '/^val androidAbiProjects = setOf($/,/^)/p' \
    "$ROOT_BUILD")"
[[ -n "$project_block" ]] || fail "the Android ABI project set is missing"
[[ "$(grep -Ec '^    ":[^"]+",$' <<<"$project_block")" == "4" ]] ||
    fail "the Android ABI project set must contain exactly the four configured Android library modules"

android_abi_projects=(
    ':p2p-core'
    ':p2p-transport-lan'
    ':p2p-rpc'
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
# The custom BCV format must not overwrite or compare against Kotlin's newly
# enrolled Android target dump. Keep its compiled-field guard on the same view.
for binding in \
    '        projectApiFile.set(layout.projectDirectory.file("api/android-bcv/${project.name}.api"))' \
    '        apiBaseline.set(layout.projectDirectory.file("api/android-bcv/${project.name}.api"))' \
    '        into(layout.projectDirectory.dir("api/android-bcv"))'; do
    [[ "$(grep -Fxc "$binding" "$ROOT_BUILD")" == "1" ]] ||
        fail "the custom Android ABI namespace must bind comparison, constants and update exactly once"
done
if grep -Fq 'classes/kotlin/android/main' "$ROOT_BUILD" ||
    grep -Fq 'dependsOn("compileAndroidMain")' "$ROOT_BUILD"; then
    fail "the Android ABI guard reconstructs compiler output ownership"
fi

module_builds=("$CORE_BUILD" "$LAN_BUILD" "$RPC_BUILD" "$PROVISIONING_BUILD")
for module_build in "${module_builds[@]}"; do
    [[ "$(grep -Fc 'tasks.named<KotlinCompile>("compileAndroidMain")' "$module_build")" == "1" ]] ||
        fail "$module_build must select exactly one typed Android compiler task"
    [[ "$(grep -Fc 'inputClassesDirs.from(compileAndroidMain.flatMap { it.destinationDirectory })' "$module_build")" == "1" ]] ||
        fail "$module_build must consume exactly one compiler-owned class-directory provider"
done

# The modular command roster and its negative tests enforce actual Android ABI
# tasks. The retired recipient/custody workflow structure is not an ABI rule.
ruby "$ROOT/scripts/check-modular-ci-policy.rb" || fail "Modular CI policy failed"
# Inspect the maintained command supplier too: a workflow route alone cannot
# prove that its compatibility component still executes the graph/comparisons.
python3 -I -B -S - "$ROOT" <<'PY_MODULAR_ABI' || fail "Modular ABI command policy failed"
import importlib.util
from pathlib import Path
import sys
root = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location('abi_component_policy', root / 'scripts/ci_component.py')
component = importlib.util.module_from_spec(spec)
spec.loader.exec_module(component)
commands = component.commands('compatibility')
assert [argv for task, argv in commands if task == 'abi-graph'] == [
    ['bash', 'scripts/check-android-abi-guard.sh']], 'exactly one unflagged graph probe required'
checks = [argv for task, argv in commands if task == 'api-abi']
assert len(checks) == 1, 'exactly one comparison invocation required'
modules = ['p2p-core', 'p2p-transport-lan', 'p2p-network-provisioning-android',
           'p2p-network-provisioning-desktop', 'p2p-rpc']
expected = [':' + name + ':checkKotlinAbi' for name in modules]
expected += [':' + name + ':checkAndroidAbi' for name in modules if name != 'p2p-network-provisioning-desktop']
wrapper = str(root / 'gradlew.bat') if component.os.name == 'nt' else './gradlew'
flags = ['--no-daemon', '--no-build-cache', '--no-configuration-cache',
         '--dependency-verification', 'strict', '--max-workers=2', '--no-parallel', '--console=plain']
assert checks[0] == [wrapper, *flags, *expected], 'complete actual strict ABI comparison invocation required'

PY_MODULAR_ABI


# An explicit comparison does not prove module check owns it. The full-mode
# graph probe is a separate, load-bearing command in both complete gates. CI's
# actual supplier is bound above; the standalone release call remains direct.
# Match executable, unflagged lines, not comments, --static-only or || true.
require_full_graph_call() {
    local file="$1"
    local gate="$2"
    [[ "$(grep -Ec '^[[:space:]]*scripts/check-android-abi-guard\.sh[[:space:]]*$' "$file")" == "1" ]] ||
        fail "$gate must invoke the Android ABI task-graph verification in full mode exactly once"
}

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
for signature in 'dev/p2pkit/rpc/RpcHost' 'dev/p2pkit/rpc/RpcClient' 'dev/p2pkit/rpc/RpcPlatformAndroidKt'; do
    grep -Fq "$signature" "$RPC_API" || fail "the RPC Android ABI baseline omits $signature"
done
for signature in "${required_provisioning[@]}"; do
    grep -Fq "$signature" "$PROVISIONING_API" ||
        fail "the provisioning Android ABI baseline omits $signature"
done

# These published binary symbols are omitted by the built-in format but remain
# in BCV's Android view. A same-shaped member on another owner is not retention.
require_core_binary_symbol() {
    local owner="$1" member="$2"
    awk -v owner="$owner" -v member="$member" '
        $0 == owner { inside = 1; owners++; next }
        $0 == "}" { inside = 0 }
        inside && $0 == member { members++ }
        END { exit !(owners == 1 && members == 1) }
    ' "$CORE_API" || fail "the custom Android ABI baseline lost retained binary symbol on $owner"
}
require_core_binary_symbol \
    'public abstract class dev/p2pkit/core/P2pError : java/lang/Exception {' \
    $'\tpublic synthetic fun <init> (Ljava/lang/String;Ljava/lang/Throwable;ILkotlin/jvm/internal/DefaultConstructorMarker;)V'
require_core_binary_symbol \
    'public final class dev/p2pkit/core/provisioning/UnsupportedNetworkProvisioningManager : dev/p2pkit/core/provisioning/NetworkProvisioningManager {' \
    $'\tpublic static final field NOT_IN_V01 Ljava/lang/String;'

# Metadata-aware extraction intentionally omits Kotlin-internal implementation
# classes even though their JVM bytecode is present in the compiler output.
# A private constructor called by its companion has a synthetic JVM accessor,
# which the dumper retains even when its descriptor references internal types.
# Keep that genuine bridge in the baseline; it does not export those classes.
# Non-synthetic constructors, methods, fields and class declarations still fail.
has_internal_api() {
    local signature="$1"
    shift
    awk -v signature="$signature" '
        index($0, signature) == 0 { next }
        /^[[:space:]]+public synthetic fun <init> [(].*Lkotlin\/jvm\/internal\/DefaultConstructorMarker;[)]V$/ { next }
        { found = 1 }
        END { exit !found }
    ' "$@"
}

for internal_signature in \
    'dev/p2pkit/core/AndroidNetworkPathListener' \
    'dev/p2pkit/transport/lan/AndroidLanDataTransport' \
    'dev/p2pkit/rpc/internal/RpcHostEngine' \
    'dev/p2pkit/provisioning/android/WifiManagerWrapper'; do
    if has_internal_api "$internal_signature" "$CORE_API" "$LAN_API" "$RPC_API" "$PROVISIONING_API"; then
        fail "Android ABI baselines incorrectly freeze internal symbol $internal_signature"
    fi
done

if [[ "$STATIC_ONLY" == "false" ]]; then
    [[ -x "$ROOT/gradlew" ]] || fail "Gradle wrapper is unavailable for Android ABI graph verification"
    if [[ -n "${P2PKIT_GRADLE_EXECUTOR:-}" ]]; then
        [[ "$P2PKIT_GRADLE_EXECUTOR" == /* && -x "$P2PKIT_GRADLE_EXECUTOR" ]] ||
            fail "P2PKIT_GRADLE_EXECUTOR must be an absolute executable path"
        task_graph="$(
            "$P2PKIT_GRADLE_EXECUTOR" --cwd "$ROOT" --wrapper "$ROOT/gradlew" \
                --purpose android-abi-graph -- \
                :p2p-core:check \
                :p2p-transport-lan:check \
                :p2p-rpc:check \
                :p2p-network-provisioning-android:check \
                --dependency-verification=strict \
                --dry-run --console=plain
        )" || fail "Android ABI task graph dry-run failed"
    else
        task_graph="$(
            cd "$ROOT"
            ./gradlew \
                :p2p-core:check \
                :p2p-transport-lan:check \
                :p2p-rpc:check \
                :p2p-network-provisioning-android:check \
                --dependency-verification=strict \
                --dry-run --console=plain
        )" || fail "Android ABI task graph dry-run failed"
    fi
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
