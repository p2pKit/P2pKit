#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
GROUP="$(sed -n 's/^GROUP=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
VERSION="$(sed -n 's/^VERSION_NAME=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
GROUP_PATH="${GROUP//.//}"
FIXTURE_CURL="$ROOT/scripts/tests/fixtures/fake-central-curl.sh"
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-central-version-test.XXXXXX")"
trap 'rm -rf "$WORK_DIR"' EXIT
mkdir -p "$WORK_DIR/bin" "$WORK_DIR/state"
ln -s "$FIXTURE_CURL" "$WORK_DIR/bin/curl"

if [[ "$VERSION" == *-SNAPSHOT ]]; then
    if PATH="$WORK_DIR/bin:$PATH" FAKE_CENTRAL_STATE_DIR="$WORK_DIR/state" \
        FAKE_MAVEN_CODE=404 "$ROOT/scripts/check-maven-central-version.sh" absent >/dev/null 2>&1; then
        echo "FATAL: snapshot VERSION_NAME was accepted as a release collision target" >&2
        exit 1
    fi
fi

RELEASE_ROOT="$WORK_DIR/release-repo"
mkdir -p "$RELEASE_ROOT/scripts"
cp "$ROOT/scripts/check-maven-central-version.sh" "$RELEASE_ROOT/scripts/check-maven-central-version.sh"
printf '%s\n' \
    "GROUP=$GROUP" \
    'VERSION_NAME=9.8.7-rc6' \
    'LATEST_PUBLISHED_VERSION=9.8.7-rc5' \
    > "$RELEASE_ROOT/gradle.properties"
SCRIPT="$RELEASE_ROOT/scripts/check-maven-central-version.sh"

bash -n "$SCRIPT"
PATH="$WORK_DIR/bin:$PATH" FAKE_CENTRAL_STATE_DIR="$WORK_DIR/state" \
    FAKE_MAVEN_CODE=404 FAKE_MAVEN_REQUIRED_PATH="/maven2/$GROUP_PATH/" \
    "$SCRIPT" absent >/dev/null

if PATH="$WORK_DIR/bin:$PATH" FAKE_CENTRAL_STATE_DIR="$WORK_DIR/state" \
    FAKE_MAVEN_CODE=404 "$SCRIPT" --latest-published absent >/dev/null 2>&1; then
    echo "FATAL: existing latest-published version was accepted as an absence target" >&2
    exit 1
fi

if PATH="$WORK_DIR/bin:$PATH" FAKE_CENTRAL_STATE_DIR="$WORK_DIR/state" \
    FAKE_MAVEN_CODE=404 FAKE_MAVEN_REQUIRED_PATH="/maven2/$GROUP_PATH/" \
    FAKE_MAVEN_EXISTING_ARTIFACT=p2p-core \
    "$SCRIPT" absent >/dev/null 2>&1; then
    echo "FATAL: existing immutable coordinate was accepted" >&2
    exit 1
fi

if PATH="$WORK_DIR/bin:$PATH" FAKE_CENTRAL_STATE_DIR="$WORK_DIR/state" \
    FAKE_MAVEN_CODE=500 FAKE_MAVEN_REQUIRED_PATH="/maven2/$GROUP_PATH/" \
    "$SCRIPT" absent >/dev/null 2>&1; then
    echo "FATAL: Maven Central availability failure was treated as absence" >&2
    exit 1
fi

echo "RESULT: PASS — Central coordinate checks reject snapshots, collisions, and unsafe version selection"
