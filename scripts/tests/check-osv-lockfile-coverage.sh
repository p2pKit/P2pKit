#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORKFLOW="$ROOT/.github/workflows/osv-scanner.yml"

fail() {
    echo "FATAL: $*" >&2
    exit 1
}

declare -a expected=()
while IFS= read -r lockfile; do
    if [[ "$lockfile" == "settings-gradle.lockfile" ]]; then
        expected+=("--lockfile=gradle.lockfile:./$lockfile")
    else
        expected+=("--lockfile=./$lockfile")
    fi
done < <(git -C "$ROOT" ls-files '*gradle.lockfile' | LC_ALL=C sort)
expected+=("--lockfile=./gradle/verification-metadata.xml")

for argument in "${expected[@]}"; do
    count="$(grep -Fxc "        $argument" "$WORKFLOW" || true)"
    [[ "$count" == "1" ]] ||
        fail "OSV workflow must contain exactly one '$argument' entry (found $count)"
done

actual_count="$(grep -Ec '^[[:space:]]+--lockfile=' "$WORKFLOW")"
[[ "$actual_count" == "${#expected[@]}" ]] ||
    fail "OSV workflow has $actual_count lockfile arguments; expected ${#expected[@]} tracked dependency inputs"

echo "RESULT: PASS — OSV scans all ${#expected[@]} tracked Gradle lock and verification inputs"
