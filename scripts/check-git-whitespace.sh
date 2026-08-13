#!/usr/bin/env bash
# Reject whitespace/conflict-marker defects introduced by the committed range,
# index, or working tree. With no explicit range, check the current commit.
set -euo pipefail

fail() {
    echo "FATAL: $*" >&2
    exit 1
}

is_commit() {
    local value="$1"
    [[ "$value" =~ ^[0-9a-f]{40}$|^[0-9a-f]{64}$ ]] &&
        git cat-file -e "$value^{commit}" 2>/dev/null
}

if [[ $# -ne 0 && $# -ne 2 ]]; then
    fail "usage: scripts/check-git-whitespace.sh [<base-commit> <head-commit>]"
fi

if [[ $# -eq 2 ]]; then
    base_commit="$1"
    range_head_commit="$2"
    is_commit "$base_commit" || fail "base is not an available exact commit"
    is_commit "$range_head_commit" || fail "head is not an available exact commit"
else
    range_head_commit="$(git rev-parse --verify HEAD)"
    is_commit "$range_head_commit" || fail "HEAD is not an available exact commit"
    if base_commit="$(git rev-parse --verify HEAD^ 2>/dev/null)"; then
        :
    else
        base_commit="$(git hash-object -t tree /dev/null)"
    fi
fi

git diff --check "$base_commit" "$range_head_commit" --
git diff --cached --check --
git diff --check --

echo "RESULT: PASS — committed range, index, and working tree contain no whitespace errors"
