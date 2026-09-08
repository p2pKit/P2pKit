#!/usr/bin/env bash
# The three exact-path whitespace exceptions are for immutable historical
# bytes, not permission to add unchecked content to those files. Do not print
# archived payloads when reporting an integrity failure.
set -euo pipefail

fail() {
    echo "FATAL: $*" >&2
    exit 1
}

[[ $# -eq 1 ]] || fail "usage: scripts/check-archive-whitespace.sh <head-commit>"
head="$1"
ROOT="$(git rev-parse --show-toplevel)"
[[ "$head" =~ ^[0-9a-f]{40}$|^[0-9a-f]{64}$ ]] &&
    [[ "$(git -C "$ROOT" cat-file -t "$head" 2>/dev/null)" == commit ]] ||
    fail "archive-whitespace head is not an available exact commit"

if command -v sha256sum >/dev/null 2>&1; then
    SHA256=(sha256sum)
elif command -v shasum >/dev/null 2>&1; then
    SHA256=(shasum -a 256)
else
    fail "sha256sum or shasum is required for archived whitespace integrity"
fi

digest() {
    "${SHA256[@]}" | awk '{print $1}'
}

verify_blob() {
    local layer="$1" object="$2" path="$3" expected="$4" actual
    actual="$(git -C "$ROOT" cat-file blob "$object" 2>/dev/null | digest)" ||
        fail "archived whitespace exception missing from $layer: $path"
    [[ "$actual" == "$expected" ]] ||
        fail "archived whitespace exception bytes changed in $layer: $path"
}

while read -r expected path; do
    verify_blob "range head" "$head:$path" "$path" "$expected"
    verify_blob index ":$path" "$path" "$expected"
    [[ -f "$ROOT/$path" && ! -L "$ROOT/$path" ]] ||
        fail "archived whitespace exception missing or non-regular in worktree: $path"
    actual="$(digest <"$ROOT/$path")" || fail "cannot read archived whitespace exception: $path"
    [[ "$actual" == "$expected" ]] ||
        fail "archived whitespace exception bytes changed in worktree: $path"
done <<'ARCHIVES'
7994521ea430c15f748acbbb925970d33dfbafcceab3ae1bb776dd6e1f27ec3c docs/archive/evidence/v0.3/jvm-cli.log
edc4723a50445bf95d927c56d39aa4ba0600cd363adaa658bddd7a06ddf0d32e docs/archive/remediation/2026-06/PROBLEMS_P2PKIT.md
4a7b7d8f5dcc4ba32f8410d7e78781c139e21c25f18c6ba192adb28f4fb8bff3 docs/archive/remediation/2026-07/OPEN_DECISIONS_2026-07.md
ARCHIVES

echo "RESULT: PASS — archived whitespace exceptions retain their exact historical bytes"
