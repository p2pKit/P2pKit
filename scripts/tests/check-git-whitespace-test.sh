#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CHECKER="$ROOT/scripts/check-git-whitespace.sh"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-whitespace-test.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

fail() {
    echo "FATAL: $*" >&2
    exit 1
}

new_repo() {
    local repo="$WORK/$1"
    mkdir -p "$repo"
    git -C "$repo" init -q
    git -C "$repo" config user.name "P2pKit Test"
    git -C "$repo" config user.email "test@p2pkit.invalid"
    printf 'clean\n' >"$repo/fixture.txt"
    git -C "$repo" add fixture.txt
    git -C "$repo" commit -qm "initial"
    printf '%s\n' "$repo"
}

expect_failure() {
    local description="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        fail "$description unexpectedly passed"
    fi
}

clean_repo="$(new_repo clean)"
(
    cd "$clean_repo"
    "$CHECKER" >/dev/null
    base="$(git rev-parse HEAD)"
    printf 'also clean\n' >>fixture.txt
    git add fixture.txt
    git commit -qm "clean change"
    "$CHECKER" "$base" "$(git rev-parse HEAD)" >/dev/null
)

committed_repo="$(new_repo committed)"
printf 'bad trailing space \n' >>"$committed_repo/fixture.txt"
git -C "$committed_repo" add fixture.txt
git -C "$committed_repo" commit -qm "bad committed whitespace"
expect_failure "committed whitespace" bash -c "cd \"$committed_repo\" && \"$CHECKER\""

staged_repo="$(new_repo staged)"
printf 'bad staged tab\t\n' >>"$staged_repo/fixture.txt"
git -C "$staged_repo" add fixture.txt
expect_failure "staged whitespace" bash -c "cd \"$staged_repo\" && \"$CHECKER\""

worktree_repo="$(new_repo worktree)"
printf 'bad worktree space \n' >>"$worktree_repo/fixture.txt"
expect_failure "worktree whitespace" bash -c "cd \"$worktree_repo\" && \"$CHECKER\""

marker_repo="$(new_repo marker)"
printf '<<<<<<< ours\nconflict\n=======\nother\n>>>>>>> theirs\n' >>"$marker_repo/fixture.txt"
git -C "$marker_repo" add fixture.txt
git -C "$marker_repo" commit -qm "committed conflict markers"
expect_failure "committed conflict markers" bash -c "cd \"$marker_repo\" && \"$CHECKER\""

expect_failure "invalid commit range" bash -c \
    "cd \"$clean_repo\" && \"$CHECKER\" 0000000000000000000000000000000000000000 \"$(git -C "$clean_repo" rev-parse HEAD)\""

echo "RESULT: PASS — committed, staged, worktree, conflict-marker, and invalid-range defects fail closed"
