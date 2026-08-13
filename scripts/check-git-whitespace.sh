#!/usr/bin/env bash
# Reject whitespace/conflict-marker defects in a committed delta, index, or
# working tree. The explicit base may be a commit or the canonical empty tree,
# which makes an unavailable/rewritten event base check the complete head tree.
set -euo pipefail

fail() {
    echo "FATAL: $*" >&2
    exit 1
}

is_commit() {
    local value="$1"
    [[ "$value" =~ ^[0-9a-f]{40}$|^[0-9a-f]{64}$ ]] &&
        [[ "$(git cat-file -t "$value" 2>/dev/null)" == "commit" ]]
}

if [[ $# -ne 0 && $# -ne 2 ]]; then
    fail "usage: scripts/check-git-whitespace.sh [<base-commit-or-empty-tree> <head-commit>]"
fi

if [[ $# -eq 2 ]]; then
    base_commit="$1"
    range_head_commit="$2"
    empty_tree="$(git hash-object -t tree /dev/null)"
    if ! is_commit "$base_commit" && [[ "$base_commit" != "$empty_tree" ]]; then
        fail "base is neither an available exact commit nor the canonical empty tree"
    fi
    is_commit "$range_head_commit" || fail "head is not an available exact commit"
else
    range_head_commit="$(git rev-parse --verify 'HEAD^{commit}')"
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
