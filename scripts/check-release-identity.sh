#!/usr/bin/env bash
# Bind a release candidate to the exact checked-out commit, main history, and tag.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

fail() {
    echo "FATAL: $*" >&2
    exit 1
}

if [[ $# -lt 2 || $# -gt 3 ]]; then
    fail "usage: scripts/check-release-identity.sh <tag> <40-hex-sha> [require-tag|allow-missing-tag]"
fi

release_tag="$1"
release_sha="$2"
tag_mode="${3:-require-tag}"
main_ref="${RELEASE_MAIN_REF:-origin/main}"

[[ "$release_sha" =~ ^[0-9a-f]{40}$ ]] ||
    fail "release SHA must be an exact lowercase 40-hex commit"
case "$tag_mode" in
    require-tag|allow-missing-tag) ;;
    *) fail "unsupported tag mode: $tag_mode" ;;
esac

cd "$ROOT"
scripts/check-release-tag.sh "$release_tag"

actual_head="$(git rev-parse --verify 'HEAD^{commit}')"
[[ "$actual_head" == "$release_sha" ]] ||
    fail "checked-out HEAD $actual_head does not equal approved release SHA $release_sha"
[[ "$(git cat-file -t "$release_sha" 2>/dev/null)" == "commit" ]] ||
    fail "approved release SHA is not an available commit"

main_commit="$(git rev-parse --verify "$main_ref^{commit}" 2>/dev/null)" ||
    fail "release main reference is unavailable: $main_ref"
git merge-base --is-ancestor "$release_sha" "$main_commit" ||
    fail "approved release SHA is not contained in $main_ref"

tag_ref="refs/tags/$release_tag"
tag_ref_status=0
git show-ref --verify --quiet "$tag_ref" || tag_ref_status=$?
case "$tag_ref_status" in
    0)
        if ! tag_commit="$(git rev-parse --verify "$tag_ref^{commit}" 2>/dev/null)"; then
            tag_target="$(git rev-parse --verify "$tag_ref^{}" 2>/dev/null)" ||
                fail "existing tag $release_tag cannot be resolved"
            tag_target_type="$(git cat-file -t "$tag_target" 2>/dev/null)" ||
                fail "existing tag $release_tag targets an unavailable object"
            fail "existing tag $release_tag resolves to a $tag_target_type object, not a commit"
        fi
        [[ "$tag_commit" == "$release_sha" ]] ||
            fail "existing tag $release_tag resolves to $tag_commit, not approved SHA $release_sha"
        tag_status="existing tag resolves to the approved commit"
        ;;
    1)
        if [[ "$tag_mode" == "require-tag" ]]; then
            fail "required release tag does not exist: $release_tag"
        fi
        tag_status="tag is absent; candidate is explicitly pre-tag"
        ;;
    *)
        fail "cannot determine whether release tag exists: $release_tag"
        ;;
esac

echo "RESULT: PASS — $release_tag is bound to $release_sha ($tag_status; contained in $main_ref)"
