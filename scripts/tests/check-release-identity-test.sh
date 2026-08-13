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
    local description="$1" expected_fragment="$2"
    shift 2
    if "$@" >"$WORK/check.stdout" 2>"$WORK/check.stderr"; then
        fail "$description unexpectedly passed"
    fi
    grep -Fq -- "$expected_fragment" "$WORK/check.stderr" ||
        fail "$description did not report '$expected_fragment': $(<"$WORK/check.stderr")"
    if grep -Fq ' is bound to ' "$WORK/check.stdout"; then
        fail "$description emitted a final identity PASS before failing"
    fi
}

expect_success() {
    local repo="$1" tag="$2" sha="$3" mode="$4" tag_status="$5" actual expected
    actual="$(check "$repo" "$tag" "$sha" "$mode")" ||
        fail "identity check unexpectedly failed"
    expected="$(printf 'RESULT: PASS — release tag %s matches VERSION_NAME=1.2.3-rc1\n' "$tag"
        printf 'RESULT: PASS — %s is bound to %s (%s; contained in main)\n' \
            "$tag" "$sha" "$tag_status")"
    [[ "$actual" == "$expected" ]] ||
        fail "identity output differs; expected [$expected], got [$actual]"
}

missing_repo="$(new_repo missing-tag)"
missing_sha="$(git -C "$missing_repo" rev-parse HEAD)"
expect_success "$missing_repo" v1.2.3-rc1 "$missing_sha" allow-missing-tag \
    "tag is absent; candidate is explicitly pre-tag"
expect_failure "required missing tag" \
    "required release tag does not exist: v1.2.3-rc1" check \
    "$missing_repo" v1.2.3-rc1 "$missing_sha" require-tag
expect_failure "malformed SHA" \
    "release SHA must be an exact lowercase 40-hex commit" check \
    "$missing_repo" v1.2.3-rc1 deadbeef allow-missing-tag
expect_failure "tag/version mismatch" \
    "does not exactly match VERSION_NAME=1.2.3-rc1" check \
    "$missing_repo" v1.2.3 "$missing_sha" allow-missing-tag
expect_failure "unsupported tag mode" "unsupported tag mode: guess" check \
    "$missing_repo" v1.2.3-rc1 "$missing_sha" guess

approved_tag_repo="$(new_repo approved-tag-object)"
approved_commit="$(git -C "$approved_tag_repo" rev-parse HEAD)"
git -C "$approved_tag_repo" tag -a approved-object -m approved-object HEAD
approved_tag_object="$(git -C "$approved_tag_repo" rev-parse refs/tags/approved-object)"
git -C "$approved_tag_repo" reset -q --hard "$approved_tag_object^{}"
expect_failure "annotated tag object as approved SHA" \
    "checked-out HEAD $approved_commit does not equal approved release SHA $approved_tag_object" check \
    "$approved_tag_repo" v1.2.3-rc1 "$approved_tag_object" allow-missing-tag

blob_tag_repo="$(new_repo blob-tag)"
blob_tag_sha="$(git -C "$blob_tag_repo" rev-parse HEAD)"
blob_target="$(printf 'not a commit\n' | git -C "$blob_tag_repo" hash-object -w --stdin)"
git -C "$blob_tag_repo" update-ref refs/tags/v1.2.3-rc1 "$blob_target"
expect_failure "existing blob tag in allow-missing mode" \
    "existing tag v1.2.3-rc1 resolves to a blob object, not a commit" check \
    "$blob_tag_repo" v1.2.3-rc1 "$blob_tag_sha" allow-missing-tag

tree_tag_repo="$(new_repo tree-tag)"
tree_tag_sha="$(git -C "$tree_tag_repo" rev-parse HEAD)"
tree_target="$(git -C "$tree_tag_repo" rev-parse 'HEAD^{tree}')"
git -C "$tree_tag_repo" update-ref refs/tags/v1.2.3-rc1 "$tree_target"
expect_failure "existing tree tag in allow-missing mode" \
    "existing tag v1.2.3-rc1 resolves to a tree object, not a commit" check \
    "$tree_tag_repo" v1.2.3-rc1 "$tree_tag_sha" allow-missing-tag

tagged_repo="$(new_repo tagged)"
tagged_sha="$(git -C "$tagged_repo" rev-parse HEAD)"
git -C "$tagged_repo" tag -a v1.2.3-rc1 -m "release"
expect_success "$tagged_repo" v1.2.3-rc1 "$tagged_sha" require-tag \
    "existing tag resolves to the approved commit"
printf 'post-tag\n' >>"$tagged_repo/content.txt"
git -C "$tagged_repo" add .
git -C "$tagged_repo" commit -qm "post tag"
post_tag_sha="$(git -C "$tagged_repo" rev-parse HEAD)"
expect_failure "existing tag at another commit" \
    "not approved SHA $post_tag_sha" check \
    "$tagged_repo" v1.2.3-rc1 "$post_tag_sha" require-tag
expect_failure "approved SHA differs from HEAD" \
    "does not equal approved release SHA $tagged_sha" check \
    "$tagged_repo" v1.2.3-rc1 "$tagged_sha" require-tag

ancestry_repo="$(new_repo ancestry)"
git -C "$ancestry_repo" switch -qc candidate
printf 'not merged\n' >>"$ancestry_repo/content.txt"
git -C "$ancestry_repo" add .
git -C "$ancestry_repo" commit -qm "unmerged candidate"
ancestry_sha="$(git -C "$ancestry_repo" rev-parse HEAD)"
expect_failure "candidate outside main" "is not contained in main" check \
    "$ancestry_repo" v1.2.3-rc1 "$ancestry_sha" allow-missing-tag

echo "RESULT: PASS — exact HEAD, deterministic success output, absent tags, non-commit tags, version, SHA, and main ancestry fail closed"
