#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VERSION="$(sed -n 's/^VERSION_NAME=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"

"$ROOT/scripts/check-release-tag.sh" "v$VERSION" >/dev/null
"$ROOT/scripts/check-release-tag.sh" "v$VERSION-rc0" >/dev/null
"$ROOT/scripts/check-release-tag.sh" "v$VERSION-rc17" >/dev/null

for invalid in "$VERSION" "v$VERSION-rc" "v$VERSION-beta1" "v999.0.0"; do
    if "$ROOT/scripts/check-release-tag.sh" "$invalid" >/dev/null 2>&1; then
        echo "FATAL: invalid release tag was accepted: $invalid" >&2
        exit 1
    fi
done

echo "RESULT: PASS — three valid release tags accepted and four invalid tags rejected"
