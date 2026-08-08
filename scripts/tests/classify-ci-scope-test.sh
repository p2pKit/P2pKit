#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CLASSIFIER="$ROOT/scripts/classify-ci-scope.sh"

classify() {
    printf '%s\0' "$@" | "$CLASSIFIER"
}

expect_scope() {
    local expected="$1"
    shift
    local actual
    actual="$(classify "$@")"
    [[ "$actual" == "$expected" ]] || {
        echo "FATAL: expected CI scope $expected, got $actual for: $*" >&2
        exit 1
    }
}

expect_scope lightweight README.md docs/README.md docs/validation/android-physical-device.md
expect_scope lightweight $'docs/line\nbreak.md'
expect_scope full README.md library/p2p-core/src/commonMain/kotlin/P2pKit.kt
expect_scope full docs/README.md .github/workflows/ci.yml
expect_scope full docs/README.md LICENSE

empty_scope="$("$CLASSIFIER" </dev/null)"
[[ "$empty_scope" == "full" ]] || {
    echo "FATAL: an empty changed-file list must fail closed to the complete gate" >&2
    exit 1
}

echo "RESULT: PASS — CI scope is lightweight only for non-empty Markdown-only changes"
