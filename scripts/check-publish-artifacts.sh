#!/usr/bin/env bash
# P1-29 (BLD-2, 2026-07): executable release gate for the publishing artifact set.
#
# Publishes all modules to a throwaway Maven-local repository (never touches
# ~/.m2) and asserts that every publication of the four library modules carries
# the full Maven-Central-required artifact set:
#   main artifact (.jar / .aar / .klib) + -sources.jar + -javadoc.jar + .pom + .module
#
# Referenced from docs/STABILIZATION_AND_RELEASE.md Part B (local dry-run gate).
# The six iOS klib publications require a macOS host (iOS targets compile only
# there); on other hosts those rows are skipped with a warning.
#
# Usage: scripts/check-publish-artifacts.sh [existing-repo-dir]
#   No argument:   runs `./gradlew publishToMavenLocal -Dmaven.repo.local=<tmp>`
#                  and verifies the result (the temp repo is removed on exit).
#   With argument: skips publishing and verifies the given repo directory
#                  (e.g. "$HOME/.m2/repository" after a manual dry-run).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(sed -n 's/^VERSION_NAME=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
GROUP="$(sed -n 's/^GROUP=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
if [[ -z "$VERSION" || -z "$GROUP" ]]; then
    echo "FATAL: could not read GROUP/VERSION_NAME from $ROOT/gradle.properties" >&2
    exit 2
fi
GROUP_PATH="${GROUP//.//}"

if [[ $# -ge 1 ]]; then
    REPO_DIR="$1"
    echo "==> Verifying existing repo: $REPO_DIR (group $GROUP, version $VERSION)"
else
    REPO_DIR="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-publish-check.XXXXXX")"
    trap 'rm -rf "$REPO_DIR"' EXIT
    echo "==> Publishing $GROUP:*:$VERSION to throwaway repo: $REPO_DIR"
    (cd "$ROOT" && ./gradlew --console=plain publishToMavenLocal -Dmaven.repo.local="$REPO_DIR")
fi

BASE="$REPO_DIR/$GROUP_PATH"
fail=0
checked=0

# check <artifactId> <main-artifact-suffix>
check() {
    local artifact="$1" main_suffix="$2"
    local dir="$BASE/$artifact/$VERSION"
    local missing=""
    local f
    for f in "$artifact-$VERSION$main_suffix" \
             "$artifact-$VERSION-sources.jar" \
             "$artifact-$VERSION-javadoc.jar" \
             "$artifact-$VERSION.pom" \
             "$artifact-$VERSION.module"; do
        [[ -f "$dir/$f" ]] || missing="$missing $f"
    done
    checked=$((checked + 1))
    if [[ -z "$missing" ]]; then
        echo "OK   $artifact  ($main_suffix -sources.jar -javadoc.jar .pom .module)"
    else
        fail=1
        echo "FAIL $artifact — missing under $dir:"
        local m
        for m in $missing; do echo "       $m"; done
    fi
}

# All hosts: root KMP metadata publication, JVM, Android, plain-JVM sidecar.
check p2p-core                                 .jar
check p2p-core-jvm                             .jar
check p2p-core-android                         .aar
check p2p-transport-lan                        .jar
check p2p-transport-lan-jvm                    .jar
check p2p-transport-lan-android                .aar
check p2p-network-provisioning-android         .jar
check p2p-network-provisioning-android-android .aar
check p2p-network-provisioning-desktop         .jar

# iOS targets publish only from a macOS host.
if [[ "$(uname -s)" == "Darwin" ]]; then
    for target in iosarm64 iossimulatorarm64 iosx64; do
        check "p2p-core-$target"          .klib
        check "p2p-transport-lan-$target" .klib
    done
else
    echo "WARN non-macOS host: skipped the 6 iOS klib publications"
fi

echo
if [[ $fail -ne 0 ]]; then
    echo "RESULT: FAIL — publishing artifact set incomplete (see FAIL rows above)"
    exit 1
fi
echo "RESULT: PASS — $checked publications carry the full Central artifact set"
