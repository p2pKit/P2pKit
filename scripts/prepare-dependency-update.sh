#!/usr/bin/env bash
# Produce lock/checksum candidates, verify them strictly, then perform the
# independent remote checksum/signature review. Nothing is committed or pushed.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE_REF="${1:-origin/main}"

cd "$ROOT"
run_phase() {
    local phase="$1" result
    shift
    if "$@"; then result=0; else result=$?; fi
    # Fixed source-owned labels only; command arguments and diagnostics remain
    # in the private capture. Preserve the original status, including failures.
    printf 'DEPENDENCY_GENERATOR_PHASE %s EXIT %s\n' "$phase" "$result" >&2 || :
    return "$result"
}

run_phase WRAPPER scripts/check-gradle-wrapper.sh
# Only the reviewed hosted candidate adapter opts in; the Terminal helper
# independently admits its fixed workflow/source/ownership/deadline inputs.
# Integrity, strict verification and authenticated provenance stay outside it.
if [[ "${P2PKIT_DEPENDENCY_TERMINAL_GENERATE:-}" == 1 ]]; then
    run_phase GENERATE python3 -B scripts/run-ci-terminal-component.py --component dependency-generate
else
    run_phase GENERATE ./gradlew resolveAndLockAll --write-locks --write-verification-metadata sha256 \
        --continue --no-configure-on-demand --no-daemon --console=plain
fi
run_phase INTEGRITY scripts/check-dependency-verification.sh
run_phase STRICT ./gradlew verifyBuildPluginSecurityFloors help --dependency-verification=strict --no-daemon --console=plain
run_phase PROVENANCE scripts/review-dependency-verification.sh "$BASE_REF"
run_phase DIFF git diff --check

echo "RESULT: PASS — dependency lock/checksum candidates are generated and independently reviewed; inspect the complete diff before committing"
