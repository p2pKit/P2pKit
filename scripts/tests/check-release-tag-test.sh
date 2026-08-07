#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VERSION="$(sed -n 's/^VERSION_NAME=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"

if [[ "$VERSION" == *-SNAPSHOT ]]; then
    if "$ROOT/scripts/check-release-tag.sh" "v$VERSION" >/dev/null 2>&1; then
        echo "FATAL: snapshot version was accepted as a release tag" >&2
        exit 1
    fi
else
    "$ROOT/scripts/check-release-tag.sh" "v$VERSION" >/dev/null
fi

WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-release-tag-test.XXXXXX")"
trap 'rm -rf "$WORK_DIR"' EXIT
mkdir -p "$WORK_DIR/scripts"
cp "$ROOT/scripts/check-release-tag.sh" "$WORK_DIR/scripts/check-release-tag.sh"
printf '%s\n' 'VERSION_NAME=9.8.7-rc6' > "$WORK_DIR/gradle.properties"
SCRIPT="$WORK_DIR/scripts/check-release-tag.sh"
RELEASE_VERSION="9.8.7-rc6"

"$SCRIPT" "v$RELEASE_VERSION" >/dev/null

printf '%s\n' 'VERSION_NAME=9.8.7-SNAPSHOT' > "$WORK_DIR/gradle.properties"
if "$SCRIPT" 'v9.8.7-SNAPSHOT' >/dev/null 2>&1; then
    echo "FATAL: fixture snapshot version was accepted as a release tag" >&2
    exit 1
fi
printf '%s\n' 'VERSION_NAME=9.8.7-rc6' > "$WORK_DIR/gradle.properties"

for invalid in "$RELEASE_VERSION" "v$RELEASE_VERSION-rc0" "v$RELEASE_VERSION-beta1" "v0.7.0-rc2" "v0.7.0" "v999.0.0"; do
    if "$SCRIPT" "$invalid" >/dev/null 2>&1; then
        echo "FATAL: invalid release tag was accepted: $invalid" >&2
        exit 1
    fi
done

echo "RESULT: PASS — snapshots are rejected and only an exact release-version tag is accepted"
