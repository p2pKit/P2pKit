#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SETTINGS="$ROOT/settings.gradle.kts"

fail() {
    echo "FATAL: $*" >&2
    exit 1
}

declare -a mappings=(
    "p2p-core|library/p2p-core"
    "p2p-transport-lan|library/p2p-transport-lan"
    "p2p-network-provisioning-android|library/p2p-network-provisioning-android"
    "p2p-network-provisioning-desktop|library/p2p-network-provisioning-desktop"
    "p2p-sample-diagnostics|samples/p2p-sample-diagnostics"
    "p2p-sample-android|samples/p2p-sample-android"
    "p2p-sample-desktop|samples/p2p-sample-desktop"
    "p2p-sample-desktop-ui|samples/p2p-sample-desktop-ui"
    "sample-kmp-shared|samples/sample-kmp-shared"
    "iosApp|samples/iosApp"
)

for mapping in "${mappings[@]}"; do
    project_name="${mapping%%|*}"
    project_path="${mapping#*|}"
    grep -Fq "include(\":$project_name\")" "$SETTINGS" ||
        fail "settings.gradle.kts no longer includes :$project_name"
    grep -Fq "project(\":$project_name\").projectDir = file(\"$project_path\")" "$SETTINGS" ||
        fail "settings.gradle.kts does not map :$project_name to $project_path"
    [[ -f "$ROOT/$project_path/build.gradle.kts" ]] ||
        fail "$project_path/build.gradle.kts is missing"
    [[ -n "$(git -C "$ROOT" ls-files -- "$project_path")" ]] ||
        fail "$project_path contains no tracked files"
    [[ -z "$(git -C "$ROOT" ls-files -- "$project_name")" ]] ||
        fail "tracked module files remain at obsolete root path $project_name"
done

grep -Fq 'library/p2p-core/api/**' "$ROOT/.github/workflows/publish-maven-central.yml" ||
    fail "publication evidence upload still uses the old core API path"
grep -Fq 'library/p2p-transport-lan/build/XCFrameworks/release' "$ROOT/scripts/run-ios-app.sh" ||
    fail "iOS launcher does not use the relocated XCFramework"
grep -Fq 'samples/iosApp/p2pkit-sample.xcodeproj' "$ROOT/scripts/run-release-gate.sh" ||
    fail "release gate does not build the relocated iOS project"

echo "RESULT: PASS — 10 Gradle projects use the canonical library/ and samples/ layout"
