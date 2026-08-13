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
    local description="$1" expected_fragment="$2"
    shift 2
    if "$@" >"$WORK/check.stdout" 2>"$WORK/check.stderr"; then
        fail "$description unexpectedly passed"
    fi
    grep -Fq -- "$expected_fragment" "$WORK/check.stdout" "$WORK/check.stderr" ||
        fail "$description did not report '$expected_fragment'"
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
    empty_tree="$(git hash-object -t tree /dev/null)"
    "$CHECKER" "$empty_tree" "$(git rev-parse HEAD)" >/dev/null
)

committed_repo="$(new_repo committed)"
printf 'bad trailing space \n' >>"$committed_repo/fixture.txt"
git -C "$committed_repo" add fixture.txt
git -C "$committed_repo" commit -qm "bad committed whitespace"
expect_failure "committed whitespace" "trailing whitespace" \
    bash -c "cd \"$committed_repo\" && \"$CHECKER\""

all_tree_repo="$(new_repo all-tree-fallback)"
printf 'bad anywhere in head tree \n' >"$all_tree_repo/legacy.txt"
git -C "$all_tree_repo" add legacy.txt
git -C "$all_tree_repo" commit -qm "bad complete tree"
all_tree_head="$(git -C "$all_tree_repo" rev-parse HEAD)"
all_tree_base="$(git -C "$all_tree_repo" hash-object -t tree /dev/null)"
expect_failure "all-tree fallback whitespace" "trailing whitespace" \
    bash -c "cd \"$all_tree_repo\" && \"$CHECKER\" \"$all_tree_base\" \"$all_tree_head\""

staged_repo="$(new_repo staged)"
printf 'bad staged tab\t\n' >>"$staged_repo/fixture.txt"
git -C "$staged_repo" add fixture.txt
expect_failure "staged whitespace" "trailing whitespace" \
    bash -c "cd \"$staged_repo\" && \"$CHECKER\""

worktree_repo="$(new_repo worktree)"
printf 'bad worktree space \n' >>"$worktree_repo/fixture.txt"
expect_failure "worktree whitespace" "trailing whitespace" \
    bash -c "cd \"$worktree_repo\" && \"$CHECKER\""

marker_repo="$(new_repo marker)"
printf '<<<<<<< ours\nconflict\n=======\nother\n>>>>>>> theirs\n' >>"$marker_repo/fixture.txt"
git -C "$marker_repo" add fixture.txt
git -C "$marker_repo" commit -qm "committed conflict markers"
expect_failure "committed conflict markers" "leftover conflict marker" \
    bash -c "cd \"$marker_repo\" && \"$CHECKER\""

multi_repo="$(new_repo multi-commit-merge)"
multi_base="$(git -C "$multi_repo" rev-parse HEAD)"
multi_main_branch="$(git -C "$multi_repo" branch --show-current)"
git -C "$multi_repo" switch -qc topic
printf 'topic\n' >"$multi_repo/topic.txt"
git -C "$multi_repo" add topic.txt
git -C "$multi_repo" commit -qm "topic"
git -C "$multi_repo" switch -q "$multi_main_branch"
printf 'bad in earlier pushed commit \n' >"$multi_repo/earlier.txt"
git -C "$multi_repo" add earlier.txt
git -C "$multi_repo" commit -qm "earlier pushed commit"
git -C "$multi_repo" merge -q --no-ff topic -m "ending merge"
multi_head="$(git -C "$multi_repo" rev-parse HEAD)"
expect_failure "complete multi-commit merge range" "trailing whitespace" \
    bash -c "cd \"$multi_repo\" && \"$CHECKER\" \"$multi_base\" \"$multi_head\""

expect_failure "invalid commit range" \
    "base is neither an available exact commit nor the canonical empty tree" bash -c \
    "cd \"$clean_repo\" && \"$CHECKER\" 0000000000000000000000000000000000000000 \"$(git -C "$clean_repo" rev-parse HEAD)\""

nonempty_tree="$(git -C "$clean_repo" rev-parse 'HEAD^{tree}')"
expect_failure "non-empty tree as base" \
    "base is neither an available exact commit nor the canonical empty tree" bash -c \
    "cd \"$clean_repo\" && \"$CHECKER\" \"$nonempty_tree\" \"$(git -C "$clean_repo" rev-parse HEAD)\""

head_blob="$(git -C "$clean_repo" rev-parse 'HEAD:fixture.txt')"
expect_failure "blob as range head" "head is not an available exact commit" bash -c \
    "cd \"$clean_repo\" && \"$CHECKER\" \"$(git -C "$clean_repo" rev-parse HEAD^)\" \"$head_blob\""

annotated_head_tag="$(git -C "$clean_repo" tag -a head-object -m head-object HEAD &&
    git -C "$clean_repo" rev-parse refs/tags/head-object)"
expect_failure "annotated tag object as range head" \
    "head is not an available exact commit" bash -c \
    "cd \"$clean_repo\" && \"$CHECKER\" \"$(git -C "$clean_repo" rev-parse HEAD^)\" \"$annotated_head_tag\""

echo "RESULT: PASS — committed, staged, worktree, complete-range, all-tree, conflict-marker, and invalid-object defects fail closed"
