#!/usr/bin/env bash
# Resolve the required CI scope and whitespace comparison from one exact
# GitHub event and repository graph.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLASSIFIER="$ROOT/scripts/classify-ci-scope.sh"

fail() {
    echo "FATAL: $*" >&2
    exit 1
}

is_commit() {
    local value="$1"
    [[ "$value" =~ ^[0-9a-f]{40}$|^[0-9a-f]{64}$ ]] &&
        [[ "$(git cat-file -t "$value" 2>/dev/null)" == "commit" ]]
}

empty_tree_oid() {
    git hash-object -t tree /dev/null
}

classify_delta() {
    local base="$1" head="$2" changed_files classification
    changed_files="$(mktemp "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/p2pkit-ci-changed-files.XXXXXX")"
    # Disable rename detection deliberately. A source/configuration file renamed
    # to Markdown must contribute both its non-Markdown deletion and Markdown
    # addition, rather than being classified from the destination suffix alone.
    if ! git diff --no-renames --name-only -z "$base" "$head" -- >"$changed_files"; then
        rm -f "$changed_files"
        fail "cannot inspect the bound CI tree delta"
    fi
    if ! classification="$("$CLASSIFIER" <"$changed_files")"; then
        rm -f "$changed_files"
        fail "CI scope classifier failed"
    fi
    rm -f "$changed_files"
    printf '%s\n' "$classification"
}

event_name="${EVENT_NAME:-}"
ref_name="${REF_NAME:-}"
event_sha="${GITHUB_SHA:-}"
before_sha="${BEFORE_SHA:-}"
pr_base_sha="${PR_BASE_SHA:-}"
pr_head_sha="${PR_HEAD_SHA:-}"

[[ -n "$event_name" ]] || fail "EVENT_NAME is required"
is_commit "$event_sha" || fail "GITHUB_SHA is not an available exact commit"
checked_out_sha="$(git rev-parse --verify 'HEAD^{commit}' 2>/dev/null)" ||
    fail "checked-out HEAD is unavailable"
[[ "$checked_out_sha" == "$event_sha" ]] ||
    fail "GITHUB_SHA does not equal the checked-out HEAD"

scope="full"
reason="fail-closed default"
base="$(empty_tree_oid)"
head="$event_sha"

case "$event_name" in
    workflow_dispatch)
        reason="manual dispatch uses all-tree fallback"
        ;;
    pull_request)
        is_commit "$pr_base_sha" || fail "PR_BASE_SHA is not an available exact commit"
        is_commit "$pr_head_sha" || fail "PR_HEAD_SHA is not an available exact commit"

        parent_line="$(git show -s --format=%P "$event_sha")" ||
            fail "cannot inspect pull-request GITHUB_SHA parents"
        read -r -a event_parents <<<"$parent_line"
        [[ "${#event_parents[@]}" -eq 2 ]] ||
            fail "pull-request GITHUB_SHA must have exactly two parents"
        [[ "${event_parents[0]}" == "$pr_base_sha" ]] ||
            fail "pull-request GITHUB_SHA first parent does not equal PR_BASE_SHA"
        [[ "${event_parents[1]}" == "$pr_head_sha" ]] ||
            fail "pull-request GITHUB_SHA second parent does not equal PR_HEAD_SHA"

        base="$pr_base_sha"
        # Classify and whitespace-check the exact synthetic merge result that
        # the rest of this job builds, rather than the separately advertised
        # head commit.
        scope="$(classify_delta "$base" "$head")"
        reason="pull request merge-result changed-file classification"
        ;;
    push)
        [[ "$ref_name" == "main" ]] || fail "push REF_NAME must be main"
        # A main commit has a distinct identity from its PR merge fixture, and
        # BuildInfo/release provenance embed that identity. Every main push
        # therefore runs the complete gate, even when its tree matches a PR
        # head.
        scope="full"
        if is_commit "$before_sha" && git merge-base --is-ancestor "$before_sha" "$head"; then
            base="$before_sha"
            reason="main push requires complete gate"
        elif is_commit "$before_sha"; then
            reason="push base is not an ancestor; using all-tree fallback"
        else
            reason="push base unavailable; using all-tree fallback"
        fi
        ;;
    *)
        reason="unsupported event uses all-tree fallback"
        ;;
esac

case "$scope" in
    full|lightweight) ;;
    *) fail "unsupported CI scope: $scope" ;;
esac

printf 'full=%s\n' "$([[ "$scope" == "full" ]] && printf true || printf false)"
printf 'base=%s\n' "$base"
printf 'head=%s\n' "$head"
printf 'reason=%s\n' "$reason"
printf 'CI scope: %s (%s)\n' "$scope" "$reason" >&2
