#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VERSION="$(sed -n 's/^VERSION_NAME=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"

"$ROOT/scripts/check-release-tag.sh" "v$VERSION" >/dev/null

for invalid in "$VERSION" "v$VERSION-rc0" "v$VERSION-beta1" "v0.7.0" "v999.0.0"; do
    if "$ROOT/scripts/check-release-tag.sh" "$invalid" >/dev/null 2>&1; then
        echo "FATAL: invalid release tag was accepted: $invalid" >&2
        exit 1
    fi
done

echo "RESULT: PASS — only the exact version-derived release tag is accepted"
