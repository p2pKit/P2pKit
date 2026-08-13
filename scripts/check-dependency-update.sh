#!/usr/bin/env bash
# Fail fast when a dependency or wrapper update has not carried its reviewed
# lock, checksum, and wrapper-policy changes into the same exact tree.
set -euo pipefail

ROOT="${P2PKIT_ROOT_OVERRIDE:-$(cd "$(dirname "$0")/.." && pwd)}"
STATE_CHECK="$ROOT/scripts/check-dependency-verification.sh"

fail() {
    echo "FATAL: $*" >&2
    exit 1
}

is_commit() {
    local value="$1"
    [[ "$value" =~ ^[0-9a-f]{40}$|^[0-9a-f]{64}$ ]] &&
        [[ "$(git -C "$ROOT" cat-file -t "$value" 2>/dev/null)" == "commit" ]]
}

"$STATE_CHECK"

if [[ $# -eq 0 ]]; then
    echo "RESULT: PASS — committed dependency-verification state is fail closed"
    exit 0
fi
[[ $# -eq 2 ]] || fail "usage: scripts/check-dependency-update.sh [<base> <head>]"

base="$1"
head="$2"
empty_tree="$(git -C "$ROOT" hash-object -t tree /dev/null)"
if [[ "$base" != "$empty_tree" ]] && ! is_commit "$base"; then
    fail "dependency-update base is not an available commit or the empty tree"
fi
is_commit "$head" || fail "dependency-update head is not an available commit"
[[ "$(git -C "$ROOT" rev-parse 'HEAD^{commit}')" == "$head" ]] ||
    fail "dependency-update head does not equal the checked-out exact tree"

# Check the complete update range, not merely HEAD^..HEAD or the worktree.
# Dependabot updates can span several commits (for example AGP + wrapper +
# maintainer corrections), so a defect in an earlier bot commit must fail the
# local pre-push check before CI constructs its synthetic merge commit.
git -C "$ROOT" diff --check "$base" "$head" --

changed="$(mktemp "${TMPDIR:-/tmp}/p2pkit-dependency-changed.XXXXXX")"
base_config="$(mktemp "${TMPDIR:-/tmp}/p2pkit-dependency-base-config.XXXXXX")"
head_config="$(mktemp "${TMPDIR:-/tmp}/p2pkit-dependency-head-config.XXXXXX")"
metadata_diff="$(mktemp "${TMPDIR:-/tmp}/p2pkit-dependency-metadata-diff.XXXXXX")"
trap 'rm -f "$changed" "$base_config" "$head_config" "$metadata_diff"' EXIT
git -C "$ROOT" diff --no-renames --name-only "$base" "$head" -- >"$changed"

changed_path() {
    grep -Fxq -- "$1" "$changed"
}

catalog_changed=false
metadata_changed=false
wrapper_changed=false
changed_path gradle/libs.versions.toml && catalog_changed=true
changed_path gradle/verification-metadata.xml && metadata_changed=true
if grep -Eq '^gradle/wrapper/|^gradlew$|^gradlew\.bat$' "$changed"; then
    wrapper_changed=true
fi

if [[ "$catalog_changed" == true && "$metadata_changed" != true ]]; then
    fail "version catalog changed without reviewed verification metadata"
fi

if [[ "$wrapper_changed" == true ]]; then
    for path in \
        gradle/wrapper/gradle-wrapper.properties \
        gradle/wrapper/gradle-wrapper.jar \
        gradlew \
        gradlew.bat \
        scripts/check-gradle-wrapper.sh \
        scripts/tests/check-gradle-wrapper-test.sh; do
        changed_path "$path" || fail "wrapper update omitted required reviewed file: $path"
    done
    "$ROOT/scripts/check-gradle-wrapper.sh"
    "$ROOT/scripts/tests/check-gradle-wrapper-test.sh"
fi

if [[ "$metadata_changed" == true ]]; then
    git -C "$ROOT" diff --unified=0 "$base" "$head" -- \
        gradle/verification-metadata.xml >"$metadata_diff"
    if [[ "$base" != "$empty_tree" ]]; then
        git -C "$ROOT" show "$base:gradle/verification-metadata.xml" |
            sed -n '/<configuration>/,/<\/configuration>/p' >"$base_config"
        git -C "$ROOT" show "$head:gradle/verification-metadata.xml" |
            sed -n '/<configuration>/,/<\/configuration>/p' >"$head_config"
        cmp -s "$base_config" "$head_config" ||
            fail "dependency update changed verification trust policy"
    fi

    if grep -Eq '^-[^-].*<(component|artifact|sha256)([ >])' "$metadata_diff"; then
        fail "dependency update removed existing verified component/artifact history"
    fi
    if [[ "$catalog_changed" == true ]] &&
        ! grep -Eq '^\+[^+].*<component ' "$metadata_diff"; then
        fail "catalog update added no explicitly checksummed component version"
    fi
fi

echo "RESULT: PASS — dependency update carries fail-closed wrapper and verification evidence"
