#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RESOLVER="$ROOT/scripts/resolve-ci-scope.sh"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-ci-scope-test.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

fail() {
    echo "FATAL: $*" >&2
    exit 1
}

new_repo() {
    local repo="$WORK/$1"
    mkdir -p "$repo/docs"
    git -C "$repo" init -q -b main
    git -C "$repo" config user.name "P2pKit Test"
    git -C "$repo" config user.email "test@p2pkit.invalid"
    printf 'source\n' >"$repo/source.kt"
    printf '# Documentation\n' >"$repo/docs/old.md"
    git -C "$repo" add .
    git -C "$repo" commit -qm "initial"
    printf '%s\n' "$repo"
}

resolve() {
    local repo="$1" event="$2" ref="$3" event_sha="$4" before="$5" pr_base="$6" pr_head="$7"
    (
        cd "$repo"
        EVENT_NAME="$event" \
            REF_NAME="$ref" \
            GITHUB_SHA="$event_sha" \
            BEFORE_SHA="$before" \
            PR_BASE_SHA="$pr_base" \
            PR_HEAD_SHA="$pr_head" \
            RUNNER_TEMP="$WORK" \
            "$RESOLVER"
    )
}

expect_scope() {
    local expected_scope="$1" expected_base="$2" expected_head="$3" expected_reason="$4"
    shift 4
    local expected_full actual_output expected_output actual_diagnostic expected_diagnostic
    if [[ "$expected_scope" == "full" ]]; then
        expected_full=true
    else
        expected_full=false
    fi

    if ! resolve "$@" >"$WORK/resolver.stdout" 2>"$WORK/resolver.stderr"; then
        fail "resolver unexpectedly failed: $(<"$WORK/resolver.stderr")"
    fi
    actual_output="$(<"$WORK/resolver.stdout")"
    expected_output="$(printf 'full=%s\nbase=%s\nhead=%s\nreason=%s\n' \
        "$expected_full" "$expected_base" "$expected_head" "$expected_reason")"
    [[ "$actual_output" == "$expected_output" ]] ||
        fail "resolver outputs differ; expected [$expected_output], got [$actual_output]"

    actual_diagnostic="$(<"$WORK/resolver.stderr")"
    expected_diagnostic="CI scope: $expected_scope ($expected_reason)"
    [[ "$actual_diagnostic" == "$expected_diagnostic" ]] ||
        fail "resolver diagnostic differs; expected [$expected_diagnostic], got [$actual_diagnostic]"
}

expect_failure() {
    local description="$1" expected_fragment="$2"
    shift 2
    if resolve "$@" >"$WORK/resolver.stdout" 2>"$WORK/resolver.stderr"; then
        fail "$description unexpectedly passed"
    fi
    [[ ! -s "$WORK/resolver.stdout" ]] ||
        fail "$description emitted partial GitHub outputs: $(<"$WORK/resolver.stdout")"
    grep -Fq -- "$expected_fragment" "$WORK/resolver.stderr" ||
        fail "$description did not report '$expected_fragment': $(<"$WORK/resolver.stderr")"
}

zero=0000000000000000000000000000000000000000
missing=1111111111111111111111111111111111111111

docs_pr_repo="$(new_repo docs-pr)"
docs_pr_base="$(git -C "$docs_pr_repo" rev-parse HEAD)"
git -C "$docs_pr_repo" switch -qc topic
printf 'more docs\n' >>"$docs_pr_repo/docs/old.md"
git -C "$docs_pr_repo" add .
git -C "$docs_pr_repo" commit -qm "docs"
docs_pr_head="$(git -C "$docs_pr_repo" rev-parse HEAD)"
git -C "$docs_pr_repo" switch -q main
git -C "$docs_pr_repo" merge -q --no-ff topic -m "synthetic PR merge"
docs_pr_merge="$(git -C "$docs_pr_repo" rev-parse HEAD)"
expect_scope lightweight "$docs_pr_base" "$docs_pr_merge" \
    "pull request merge-result changed-file classification" \
    "$docs_pr_repo" pull_request '17/merge' "$docs_pr_merge" '' \
    "$docs_pr_base" "$docs_pr_head"

source_pr_repo="$(new_repo source-pr)"
source_pr_base="$(git -C "$source_pr_repo" rev-parse HEAD)"
git -C "$source_pr_repo" switch -qc topic
printf 'code\n' >>"$source_pr_repo/source.kt"
git -C "$source_pr_repo" add .
git -C "$source_pr_repo" commit -qm "source"
source_pr_head="$(git -C "$source_pr_repo" rev-parse HEAD)"
git -C "$source_pr_repo" switch -q main
git -C "$source_pr_repo" merge -q --no-ff topic -m "synthetic PR merge"
source_pr_merge="$(git -C "$source_pr_repo" rev-parse HEAD)"
expect_scope full "$source_pr_base" "$source_pr_merge" \
    "pull request merge-result changed-file classification" \
    "$source_pr_repo" pull_request '18/merge' "$source_pr_merge" '' \
    "$source_pr_base" "$source_pr_head"

rename_pr_repo="$(new_repo rename-pr)"
rename_pr_base="$(git -C "$rename_pr_repo" rev-parse HEAD)"
git -C "$rename_pr_repo" switch -qc topic
git -C "$rename_pr_repo" mv source.kt notes.md
git -C "$rename_pr_repo" commit -qm "rename source to Markdown"
rename_pr_head="$(git -C "$rename_pr_repo" rev-parse HEAD)"
git -C "$rename_pr_repo" switch -q main
git -C "$rename_pr_repo" merge -q --no-ff topic -m "synthetic PR merge"
rename_pr_merge="$(git -C "$rename_pr_repo" rev-parse HEAD)"
expect_scope full "$rename_pr_base" "$rename_pr_merge" \
    "pull request merge-result changed-file classification" \
    "$rename_pr_repo" pull_request '19/merge' "$rename_pr_merge" '' \
    "$rename_pr_base" "$rename_pr_head"

# Even a two-parent commit with the advertised graph is classified from its
# actual merge-result tree, so an unexpected non-Markdown result cannot inherit
# a lightweight decision from the advertised PR head.
result_repo="$(new_repo adversarial-merge-result)"
result_base="$(git -C "$result_repo" rev-parse HEAD)"
git -C "$result_repo" switch -qc topic
printf 'topic docs\n' >>"$result_repo/docs/old.md"
git -C "$result_repo" add .
git -C "$result_repo" commit -qm "topic docs"
result_pr_head="$(git -C "$result_repo" rev-parse HEAD)"
git -C "$result_repo" switch -q main
printf 'unexpected merge content\n' >>"$result_repo/source.kt"
git -C "$result_repo" add source.kt
result_tree="$(git -C "$result_repo" write-tree)"
git -C "$result_repo" reset -q --hard "$result_base"
result_merge="$(printf 'adversarial merge result\n' | git -C "$result_repo" commit-tree \
    "$result_tree" -p "$result_base" -p "$result_pr_head")"
git -C "$result_repo" reset -q --hard "$result_merge"
expect_scope full "$result_base" "$result_merge" \
    "pull request merge-result changed-file classification" \
    "$result_repo" pull_request '20/merge' "$result_merge" '' \
    "$result_base" "$result_pr_head"

expect_failure "mismatched PR base" \
    "pull-request GITHUB_SHA first parent does not equal PR_BASE_SHA" \
    "$docs_pr_repo" pull_request '17/merge' "$docs_pr_merge" '' \
    "$docs_pr_head" "$docs_pr_base"
expect_failure "mismatched PR head" \
    "pull-request GITHUB_SHA second parent does not equal PR_HEAD_SHA" \
    "$docs_pr_repo" pull_request '17/merge' "$docs_pr_merge" '' \
    "$docs_pr_base" "$docs_pr_base"
expect_failure "PR event/check-out mismatch" \
    "GITHUB_SHA does not equal the checked-out HEAD" \
    "$docs_pr_repo" pull_request '17/merge' "$docs_pr_head" '' \
    "$docs_pr_base" "$docs_pr_head"
git -C "$docs_pr_repo" switch -q topic
expect_failure "non-merge PR event" \
    "pull-request GITHUB_SHA must have exactly two parents" \
    "$docs_pr_repo" pull_request '17/merge' "$docs_pr_head" '' \
    "$docs_pr_base" "$docs_pr_head"
git -C "$docs_pr_repo" switch -q main

direct_docs_repo="$(new_repo direct-docs-push)"
direct_docs_base="$(git -C "$direct_docs_repo" rev-parse HEAD)"
printf 'pushed docs\n' >>"$direct_docs_repo/docs/old.md"
git -C "$direct_docs_repo" add .
git -C "$direct_docs_repo" commit -qm "docs push"
direct_docs_head="$(git -C "$direct_docs_repo" rev-parse HEAD)"
expect_scope full "$direct_docs_base" "$direct_docs_head" \
    "main push requires complete gate" \
    "$direct_docs_repo" push main "$direct_docs_head" "$direct_docs_base" '' ''

exact_tree_repo="$(new_repo exact-tree-push)"
exact_tree_base="$(git -C "$exact_tree_repo" rev-parse HEAD)"
git -C "$exact_tree_repo" switch -qc topic
printf 'topic source\n' >>"$exact_tree_repo/source.kt"
git -C "$exact_tree_repo" add .
git -C "$exact_tree_repo" commit -qm "topic"
exact_tree_topic="$(git -C "$exact_tree_repo" rev-parse HEAD)"
git -C "$exact_tree_repo" switch -q main
git -C "$exact_tree_repo" merge -q --no-ff topic -m "exact-tree merge"
exact_tree_merge="$(git -C "$exact_tree_repo" rev-parse HEAD)"
[[ "$(git -C "$exact_tree_repo" rev-parse "$exact_tree_merge^{tree}")" == \
    "$(git -C "$exact_tree_repo" rev-parse "$exact_tree_topic^{tree}")" ]] ||
    fail "exact-tree push fixture is not exact"
expect_scope full "$exact_tree_base" "$exact_tree_merge" \
    "main push requires complete gate" \
    "$exact_tree_repo" push main "$exact_tree_merge" "$exact_tree_base" '' ''

# A multi-commit push ending in a merge must retain github.event.before, not
# silently narrow the whitespace comparison to the merge's first parent.
multi_repo="$(new_repo multi-commit-merge-push)"
multi_base="$(git -C "$multi_repo" rev-parse HEAD)"
git -C "$multi_repo" switch -qc topic
printf 'topic source\n' >>"$multi_repo/source.kt"
git -C "$multi_repo" add .
git -C "$multi_repo" commit -qm "topic source"
git -C "$multi_repo" switch -q main
printf '# Main push commit\n' >"$multi_repo/docs/main.md"
git -C "$multi_repo" add .
git -C "$multi_repo" commit -qm "first pushed commit"
multi_first_parent="$(git -C "$multi_repo" rev-parse HEAD)"
git -C "$multi_repo" merge -q --no-ff topic -m "last pushed merge"
multi_head="$(git -C "$multi_repo" rev-parse HEAD)"
[[ "$multi_base" != "$multi_first_parent" ]] || fail "multi-push fixture did not advance"
expect_scope full "$multi_base" "$multi_head" \
    "main push requires complete gate" \
    "$multi_repo" push main "$multi_head" "$multi_base" '' ''

rewritten_repo="$(new_repo rewritten-push)"
git -C "$rewritten_repo" switch -qc previous
printf 'previous\n' >>"$rewritten_repo/source.kt"
git -C "$rewritten_repo" add .
git -C "$rewritten_repo" commit -qm "previous line"
previous_head="$(git -C "$rewritten_repo" rev-parse HEAD)"
git -C "$rewritten_repo" switch -q main
printf 'replacement\n' >>"$rewritten_repo/source.kt"
git -C "$rewritten_repo" add .
git -C "$rewritten_repo" commit -qm "replacement line"
rewritten_head="$(git -C "$rewritten_repo" rev-parse HEAD)"
rewritten_empty_tree="$(git -C "$rewritten_repo" hash-object -t tree /dev/null)"
expect_scope full "$rewritten_empty_tree" "$rewritten_head" \
    "push base is not an ancestor; using all-tree fallback" \
    "$rewritten_repo" push main "$rewritten_head" "$previous_head" '' ''

direct_docs_empty_tree="$(git -C "$direct_docs_repo" hash-object -t tree /dev/null)"
expect_scope full "$direct_docs_empty_tree" "$direct_docs_head" \
    "push base unavailable; using all-tree fallback" \
    "$direct_docs_repo" push main "$direct_docs_head" "$zero" '' ''
expect_scope full "$direct_docs_empty_tree" "$direct_docs_head" \
    "push base unavailable; using all-tree fallback" \
    "$direct_docs_repo" push main "$direct_docs_head" "$missing" '' ''
expect_scope full "$direct_docs_empty_tree" "$direct_docs_head" \
    "manual dispatch uses all-tree fallback" \
    "$direct_docs_repo" workflow_dispatch main "$direct_docs_head" '' '' ''
expect_scope full "$direct_docs_empty_tree" "$direct_docs_head" \
    "unsupported event uses all-tree fallback" \
    "$direct_docs_repo" schedule main "$direct_docs_head" '' '' ''

expect_failure "non-main push" "push REF_NAME must be main" \
    "$direct_docs_repo" push maintenance "$direct_docs_head" "$direct_docs_base" '' ''
expect_failure "unavailable GITHUB_SHA" \
    "GITHUB_SHA is not an available exact commit" \
    "$direct_docs_repo" push main "$zero" "$direct_docs_base" '' ''
annotated_event_tag="$(git -C "$direct_docs_repo" tag -a event-object -m event-object HEAD &&
    git -C "$direct_docs_repo" rev-parse refs/tags/event-object)"
expect_failure "annotated tag object as GITHUB_SHA" \
    "GITHUB_SHA is not an available exact commit" \
    "$direct_docs_repo" push main "$annotated_event_tag" "$direct_docs_base" '' ''
expect_failure "push event/check-out mismatch" \
    "GITHUB_SHA does not equal the checked-out HEAD" \
    "$direct_docs_repo" push main "$direct_docs_base" "$zero" '' ''

echo "RESULT: PASS — exact PR graphs/results, deterministic outputs, full main pushes, complete push ranges, and all-tree fallbacks are fail closed"
