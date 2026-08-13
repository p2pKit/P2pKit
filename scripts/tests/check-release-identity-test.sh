#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CHECKER="$ROOT/scripts/check-release-identity.sh"
TAG_CHECKER="$ROOT/scripts/check-release-tag.sh"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-release-identity-test.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

fail() {
    echo "FATAL: $*" >&2
    exit 1
}

new_repo() {
    local repo="$WORK/$1"
    mkdir -p "$repo/scripts"
    git -C "$repo" init -q -b main
    git -C "$repo" config user.name "P2pKit Test"
    git -C "$repo" config user.email "test@p2pkit.invalid"
    cp "$CHECKER" "$repo/scripts/check-release-identity.sh"
    cp "$TAG_CHECKER" "$repo/scripts/check-release-tag.sh"
    chmod +x "$repo/scripts/check-release-identity.sh" "$repo/scripts/check-release-tag.sh"
    printf 'VERSION_NAME=1.2.3-rc1\n' >"$repo/gradle.properties"
    printf 'candidate\n' >"$repo/content.txt"
    git -C "$repo" add .
    git -C "$repo" commit -qm "candidate"
    printf '%s\n' "$repo"
}

check() {
    local repo="$1"
    shift
    (cd "$repo" && RELEASE_MAIN_REF=main scripts/check-release-identity.sh "$@")
}

expect_failure() {
    local description="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        fail "$description unexpectedly passed"
    fi
}

missing_repo="$(new_repo missing-tag)"
missing_sha="$(git -C "$missing_repo" rev-parse HEAD)"
check "$missing_repo" v1.2.3-rc1 "$missing_sha" allow-missing-tag >/dev/null
expect_failure "required missing tag" check \
    "$missing_repo" v1.2.3-rc1 "$missing_sha" require-tag
expect_failure "malformed SHA" check \
    "$missing_repo" v1.2.3-rc1 deadbeef allow-missing-tag
expect_failure "tag/version mismatch" check \
    "$missing_repo" v1.2.3 "$missing_sha" allow-missing-tag
expect_failure "unsupported tag mode" check \
    "$missing_repo" v1.2.3-rc1 "$missing_sha" guess

tagged_repo="$(new_repo tagged)"
tagged_sha="$(git -C "$tagged_repo" rev-parse HEAD)"
git -C "$tagged_repo" tag -a v1.2.3-rc1 -m "release"
check "$tagged_repo" v1.2.3-rc1 "$tagged_sha" require-tag >/dev/null
printf 'post-tag\n' >>"$tagged_repo/content.txt"
git -C "$tagged_repo" add .
git -C "$tagged_repo" commit -qm "post tag"
post_tag_sha="$(git -C "$tagged_repo" rev-parse HEAD)"
expect_failure "existing tag at another commit" check \
    "$tagged_repo" v1.2.3-rc1 "$post_tag_sha" require-tag
expect_failure "approved SHA differs from HEAD" check \
    "$tagged_repo" v1.2.3-rc1 "$tagged_sha" require-tag

ancestry_repo="$(new_repo ancestry)"
git -C "$ancestry_repo" switch -qc candidate
printf 'not merged\n' >>"$ancestry_repo/content.txt"
git -C "$ancestry_repo" add .
git -C "$ancestry_repo" commit -qm "unmerged candidate"
ancestry_sha="$(git -C "$ancestry_repo" rev-parse HEAD)"
expect_failure "candidate outside main" check \
    "$ancestry_repo" v1.2.3-rc1 "$ancestry_sha" allow-missing-tag

echo "RESULT: PASS — exact HEAD, tag resolution, tag absence mode, version, SHA, and main ancestry fail closed"
