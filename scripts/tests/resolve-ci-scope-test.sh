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
            "$RESOLVER" 2>/dev/null
    )
}

expect_scope() {
    local expected="$1" reason_fragment="$2"
    shift 2
    local output full_value reason
    output="$(resolve "$@")"
    full_value="$(sed -n 's/^full=//p' <<<"$output")"
    reason="$(sed -n 's/^reason=//p' <<<"$output")"
    [[ "$(grep -Ec '^(full|base|head|reason)=' <<<"$output")" == "4" ]] ||
        fail "resolver did not emit exactly four GitHub outputs: $output"
    if [[ "$expected" == "full" ]]; then
        [[ "$full_value" == "true" ]] || fail "expected full, got: $output"
    else
        [[ "$full_value" == "false" ]] || fail "expected lightweight, got: $output"
    fi
    [[ "$reason" == *"$reason_fragment"* ]] ||
        fail "reason '$reason' does not contain '$reason_fragment'"
}

zero=0000000000000000000000000000000000000000

docs_repo="$(new_repo direct-docs)"
docs_base="$(git -C "$docs_repo" rev-parse HEAD)"
printf 'more docs\n' >>"$docs_repo/docs/old.md"
git -C "$docs_repo" add .
git -C "$docs_repo" commit -qm "docs"
docs_head="$(git -C "$docs_repo" rev-parse HEAD)"
expect_scope lightweight "direct push changed-file" \
    "$docs_repo" push main "$docs_head" "$docs_base" '' ''
expect_scope lightweight "pull request changed-file" \
    "$docs_repo" pull_request feature "$docs_head" '' "$docs_base" "$docs_head"

source_repo="$(new_repo direct-source)"
source_base="$(git -C "$source_repo" rev-parse HEAD)"
printf 'code\n' >>"$source_repo/source.kt"
git -C "$source_repo" add .
git -C "$source_repo" commit -qm "source"
source_head="$(git -C "$source_repo" rev-parse HEAD)"
expect_scope full "direct push changed-file" \
    "$source_repo" push main "$source_head" "$source_base" '' ''

rename_repo="$(new_repo rename-source-to-markdown)"
rename_base="$(git -C "$rename_repo" rev-parse HEAD)"
git -C "$rename_repo" mv source.kt notes.md
git -C "$rename_repo" commit -qm "rename source to Markdown"
rename_head="$(git -C "$rename_repo" rev-parse HEAD)"
expect_scope full "pull request changed-file" \
    "$rename_repo" pull_request feature "$rename_head" '' "$rename_base" "$rename_head"
expect_scope full "direct push changed-file" \
    "$rename_repo" push main "$rename_head" "$rename_base" '' ''

markdown_rename_repo="$(new_repo rename-markdown)"
markdown_rename_base="$(git -C "$markdown_rename_repo" rev-parse HEAD)"
git -C "$markdown_rename_repo" mv docs/old.md docs/new.md
git -C "$markdown_rename_repo" commit -qm "rename Markdown"
markdown_rename_head="$(git -C "$markdown_rename_repo" rev-parse HEAD)"
expect_scope lightweight "pull request changed-file" \
    "$markdown_rename_repo" pull_request feature "$markdown_rename_head" '' \
    "$markdown_rename_base" "$markdown_rename_head"

identical_repo="$(new_repo exact-tree-merge)"
identical_base="$(git -C "$identical_repo" rev-parse HEAD)"
git -C "$identical_repo" switch -qc topic
printf 'topic source\n' >>"$identical_repo/source.kt"
git -C "$identical_repo" add .
git -C "$identical_repo" commit -qm "topic"
topic_head="$(git -C "$identical_repo" rev-parse HEAD)"
git -C "$identical_repo" switch -q main
git -C "$identical_repo" merge -q --no-ff topic -m "merge topic"
identical_merge="$(git -C "$identical_repo" rev-parse HEAD)"
[[ "$(git -C "$identical_repo" rev-parse "HEAD^{tree}")" == \
    "$(git -C "$identical_repo" rev-parse "$topic_head^{tree}")" ]] ||
    fail "exact-tree merge fixture is not exact"
expect_scope lightweight "exactly reuses its verified PR-parent tree" \
    "$identical_repo" push main "$identical_merge" "$identical_base" '' ''
expect_scope full "not exactly the single two-parent merge" \
    "$identical_repo" push main "$identical_merge" "$zero" '' ''
expect_scope full "not eligible for exact-tree reuse" \
    "$identical_repo" push maintenance "$identical_merge" "$identical_base" '' ''

changed_repo="$(new_repo changed-tree-merge)"
git -C "$changed_repo" switch -qc topic
printf 'topic source\n' >>"$changed_repo/source.kt"
git -C "$changed_repo" add .
git -C "$changed_repo" commit -qm "topic"
git -C "$changed_repo" switch -q main
printf '# Main-only change\n' >"$changed_repo/docs/main.md"
git -C "$changed_repo" add .
git -C "$changed_repo" commit -qm "main change"
git -C "$changed_repo" merge -q --no-ff topic -m "merge changed tree"
changed_merge="$(git -C "$changed_repo" rev-parse HEAD)"
changed_first_parent="$(git -C "$changed_repo" rev-parse HEAD^1)"
expect_scope full "differs from the PR-parent tree" \
    "$changed_repo" push main "$changed_merge" "$changed_first_parent" '' ''

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
expect_scope full "not an ancestor" \
    "$rewritten_repo" push main "$rewritten_head" "$previous_head" '' ''

octopus_repo="$(new_repo octopus)"
octopus_base="$(git -C "$octopus_repo" rev-parse HEAD)"
git -C "$octopus_repo" switch -qc one
printf '# One\n' >"$octopus_repo/docs/one.md"
git -C "$octopus_repo" add .
git -C "$octopus_repo" commit -qm "one"
git -C "$octopus_repo" switch -q main
git -C "$octopus_repo" switch -qc two
printf '# Two\n' >"$octopus_repo/docs/two.md"
git -C "$octopus_repo" add .
git -C "$octopus_repo" commit -qm "two"
git -C "$octopus_repo" switch -q main
git -C "$octopus_repo" merge -q --no-ff one two -m "octopus"
octopus_head="$(git -C "$octopus_repo" rev-parse HEAD)"
expect_scope full "multi-parent push" \
    "$octopus_repo" push main "$octopus_head" "$octopus_base" '' ''

expect_scope full "push base unavailable" \
    "$docs_repo" push main "$docs_head" "$zero" '' ''
expect_scope full "push base unavailable" \
    "$docs_repo" push main "$docs_base" "$zero" '' ''
expect_scope full "manual dispatch" \
    "$docs_repo" workflow_dispatch main "$docs_head" '' '' ''
expect_scope full "unsupported event" \
    "$docs_repo" schedule main "$docs_head" '' '' ''

if resolve "$docs_repo" push main "$zero" "$docs_base" '' '' >/dev/null 2>&1; then
    fail "unavailable GITHUB_SHA did not fail closed"
fi

echo "RESULT: PASS — rename, direct, PR, exact-tree merge, changed merge, rewritten push, octopus, and invalid-SHA scopes are fail closed"
