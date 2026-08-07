#!/usr/bin/env bash
# Ensures a release tag is derived exactly from the version source of truth.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(sed -n 's/^VERSION_NAME=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
TAG="${1:-${GITHUB_REF_NAME:-}}"

[[ -n "$VERSION" ]] || { echo "FATAL: VERSION_NAME is empty" >&2; exit 2; }
[[ -n "$TAG" ]] || { echo "FATAL: pass a release tag or set GITHUB_REF_NAME" >&2; exit 2; }
[[ "$VERSION" != *-SNAPSHOT ]] || {
    echo "FATAL: snapshot VERSION_NAME=$VERSION cannot be released or tagged" >&2
    exit 1
}

if [[ "$TAG" != "v$VERSION" ]]; then
    echo "FATAL: tag '$TAG' does not exactly match VERSION_NAME=$VERSION (expected v$VERSION)" >&2
    exit 1
fi

echo "RESULT: PASS — release tag $TAG matches VERSION_NAME=$VERSION"
