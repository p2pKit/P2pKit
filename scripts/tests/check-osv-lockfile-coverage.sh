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
    if ! grep -Eq '^[^#[:space:]][^=]*:[^=]*=' "$ROOT/$lockfile"; then
        continue
    fi
    if [[ "$(basename "$lockfile")" != "gradle.lockfile" ]]; then
        expected+=("--lockfile=gradle.lockfile:./$lockfile")
    else
        expected+=("--lockfile=./$lockfile")
    fi
done < <(git -C "$ROOT" ls-files '*gradle.lockfile' | LC_ALL=C sort)

buildscript_lock="buildscript-gradle.lockfile"
git -C "$ROOT" ls-files --error-unmatch "$buildscript_lock" >/dev/null 2>&1 ||
    fail "root build-plugin lock is not tracked: $buildscript_lock"
grep -Eq '^[^#[:space:]][^=]*:[^=]*=([^,]*,)*classpath(,|$)' "$ROOT/$buildscript_lock" ||
    fail "root build-plugin lock contains no classpath dependencies"

# Gradle verification metadata is a checksum allowlist that retains historical
# artifacts. It is not resolved dependency state, so treating it as a lockfile
# reports removed versions as current vulnerabilities.
if grep -Fq -- '--lockfile=./gradle/verification-metadata.xml' "$WORKFLOW"; then
    fail "OSV workflow must not scan Gradle verification metadata as dependency state"
fi

for argument in "${expected[@]}"; do
    count="$(grep -Fxc "        $argument" "$WORKFLOW" || true)"
    [[ "$count" == "1" ]] ||
        fail "OSV workflow must contain exactly one '$argument' entry (found $count)"
done

actual_count="$(grep -Ec '^[[:space:]]+--lockfile=' "$WORKFLOW")"
[[ "$actual_count" == "${#expected[@]}" ]] ||
    fail "OSV workflow has $actual_count lockfile arguments; expected ${#expected[@]} non-empty dependency inputs"

echo "RESULT: PASS — OSV scans all ${#expected[@]} non-empty Gradle dependency locks, including build plugins"
