#!/usr/bin/env bash
# Resolve the required CI scope from one exact GitHub event and repository graph.
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
        git cat-file -e "$value^{commit}" 2>/dev/null
}

classify_range() {
    local range_kind="$1" base="$2" head="$3" changed_files
    changed_files="$(mktemp "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/p2pkit-ci-changed-files.XXXXXX")"
    # Disable rename detection deliberately. A source/configuration file renamed
    # to Markdown must contribute both its non-Markdown deletion and Markdown
    # addition, rather than being classified from the destination suffix alone.
    case "$range_kind" in
        pull-request)
            git diff --no-renames --name-only -z "$base...$head" -- >"$changed_files"
            ;;
        push)
            git diff --no-renames --name-only -z "$base" "$head" -- >"$changed_files"
            ;;
        *)
            rm -f "$changed_files"
            fail "unsupported comparison kind: $range_kind"
            ;;
    esac
    "$CLASSIFIER" <"$changed_files"
    rm -f "$changed_files"
}

event_name="${EVENT_NAME:-}"
ref_name="${REF_NAME:-}"
event_sha="${GITHUB_SHA:-}"
before_sha="${BEFORE_SHA:-}"
pr_base_sha="${PR_BASE_SHA:-}"
pr_head_sha="${PR_HEAD_SHA:-}"

[[ -n "$event_name" ]] || fail "EVENT_NAME is required"
is_commit "$event_sha" || fail "GITHUB_SHA is not an available exact commit"

scope="full"
reason="fail-closed default"
base="$event_sha"
head="$event_sha"

case "$event_name" in
    workflow_dispatch)
        reason="manual dispatch"
        ;;
    pull_request)
        is_commit "$pr_base_sha" || fail "PR_BASE_SHA is not an available exact commit"
        is_commit "$pr_head_sha" || fail "PR_HEAD_SHA is not an available exact commit"
        base="$pr_base_sha"
        head="$pr_head_sha"
        scope="$(classify_range pull-request "$base" "$head")"
        reason="pull request changed-file classification"
        ;;
    push)
        head="$event_sha"
        read -r -a parents <<<"$(git show -s --format=%P "$head")"
        parent_count="${#parents[@]}"
        if [[ "$parent_count" -gt 1 ]]; then
            base="${parents[0]}"
            if [[ "$ref_name" == "main" && "$parent_count" -eq 2 &&
                "$before_sha" == "${parents[0]}" ]]; then
                merge_tree="$(git rev-parse "$head^{tree}")"
                verified_parent_tree="$(git rev-parse "${parents[1]}^{tree}")"
                if [[ "$merge_tree" == "$verified_parent_tree" ]]; then
                    scope="lightweight"
                    reason="single protected merge exactly reuses its verified PR-parent tree"
                else
                    reason="merge result differs from the PR-parent tree"
                fi
            elif [[ "$ref_name" == "main" && "$parent_count" -eq 2 ]]; then
                reason="push range is not exactly the single two-parent merge"
            else
                reason="multi-parent push is not eligible for exact-tree reuse"
            fi
        elif is_commit "$before_sha" && git merge-base --is-ancestor "$before_sha" "$head"; then
            base="$before_sha"
            scope="$(classify_range push "$base" "$head")"
            reason="direct push changed-file classification"
        elif is_commit "$before_sha"; then
            reason="push base is not an ancestor of the pushed head"
        else
            reason="push base unavailable"
        fi
        ;;
    *)
        reason="unsupported event uses fail-closed default"
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
