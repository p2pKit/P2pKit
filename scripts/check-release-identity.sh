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

actual_head="$(git rev-parse --verify HEAD)"
[[ "$actual_head" == "$release_sha" ]] ||
    fail "checked-out HEAD $actual_head does not equal approved release SHA $release_sha"
git cat-file -e "$release_sha^{commit}" 2>/dev/null ||
    fail "approved release SHA is not an available commit"

main_commit="$(git rev-parse --verify "$main_ref^{commit}" 2>/dev/null)" ||
    fail "release main reference is unavailable: $main_ref"
git merge-base --is-ancestor "$release_sha" "$main_commit" ||
    fail "approved release SHA is not contained in $main_ref"

if tag_commit="$(git rev-parse -q --verify "refs/tags/$release_tag^{commit}")"; then
    [[ "$tag_commit" == "$release_sha" ]] ||
        fail "existing tag $release_tag resolves to $tag_commit, not approved SHA $release_sha"
    tag_status="existing tag resolves to the approved commit"
elif [[ "$tag_mode" == "require-tag" ]]; then
    fail "required release tag does not exist: $release_tag"
else
    tag_status="tag is absent; candidate is explicitly pre-tag"
fi

echo "RESULT: PASS — $release_tag is bound to $release_sha ($tag_status; contained in $main_ref)"
