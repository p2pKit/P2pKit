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
command -v jq >/dev/null 2>&1 || { echo "FATAL: jq is required" >&2; exit 2; }
command -v xmllint >/dev/null 2>&1 || { echo "FATAL: xmllint is required" >&2; exit 2; }
command -v unzip >/dev/null 2>&1 || { echo "FATAL: unzip is required" >&2; exit 2; }
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
    local main="$dir/$artifact-$VERSION$main_suffix"
    local sources="$dir/$artifact-$VERSION-sources.jar"
    local javadoc="$dir/$artifact-$VERSION-javadoc.jar"
    local pom="$dir/$artifact-$VERSION.pom"
    local module="$dir/$artifact-$VERSION.module"
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
    if [[ -n "$missing" ]]; then
        fail=1
        echo "FAIL $artifact — missing under $dir:"
        local m
        for m in $missing; do echo "       $m"; done
        return
    fi

    local invalid=""
    unzip -tq "$main" >/dev/null 2>&1 || invalid="$invalid unreadable-main"
    unzip -tq "$sources" >/dev/null 2>&1 || invalid="$invalid unreadable-sources"
    unzip -tq "$javadoc" >/dev/null 2>&1 || invalid="$invalid unreadable-javadoc"

    local source_entries javadoc_entries
    source_entries="$(unzip -Z1 "$sources")"
    javadoc_entries="$(unzip -Z1 "$javadoc")"
    if [[ "$artifact" != "p2p-network-provisioning-android" ]]; then
        [[ "$source_entries" =~ \.kt$ ]] || invalid="$invalid sources-without-kotlin"
    fi
    [[ "$javadoc_entries" =~ (^|$'\n')([^$'\n']*/)?index\.html($|$'\n') ]] ||
        invalid="$invalid javadoc-without-index"

    xmllint --noout "$pom" >/dev/null 2>&1 || invalid="$invalid malformed-pom"
    local pom_group pom_artifact pom_version pom_name pom_description pom_url
    local pom_license pom_developer pom_scm
    pom_group="$(xmllint --xpath "string(/*[local-name()='project']/*[local-name()='groupId'])" "$pom")"
    pom_artifact="$(xmllint --xpath "string(/*[local-name()='project']/*[local-name()='artifactId'])" "$pom")"
    pom_version="$(xmllint --xpath "string(/*[local-name()='project']/*[local-name()='version'])" "$pom")"
    pom_name="$(xmllint --xpath "string(/*[local-name()='project']/*[local-name()='name'])" "$pom")"
    pom_description="$(xmllint --xpath "string(/*[local-name()='project']/*[local-name()='description'])" "$pom")"
    pom_url="$(xmllint --xpath "string(/*[local-name()='project']/*[local-name()='url'])" "$pom")"
    pom_license="$(xmllint --xpath "string(/*[local-name()='project']/*[local-name()='licenses']/*[local-name()='license']/*[local-name()='name'])" "$pom")"
    pom_developer="$(xmllint --xpath "string(/*[local-name()='project']/*[local-name()='developers']/*[local-name()='developer']/*[local-name()='id'])" "$pom")"
    pom_scm="$(xmllint --xpath "string(/*[local-name()='project']/*[local-name()='scm']/*[local-name()='url'])" "$pom")"

    [[ "$pom_group" == "$GROUP" ]] || invalid="$invalid pom-group"
    [[ "$pom_artifact" == "$artifact" ]] || invalid="$invalid pom-artifact"
    [[ "$pom_version" == "$VERSION" ]] || invalid="$invalid pom-version"
    [[ -n "$pom_name" && -n "$pom_description" && "$pom_url" == "https://github.com/p2pKit/P2pKit" ]] ||
        invalid="$invalid pom-project-metadata"
    [[ "$pom_license" == "The Apache License, Version 2.0" ]] || invalid="$invalid pom-license"
    [[ -n "$pom_developer" && "$pom_scm" == "https://github.com/p2pKit/P2pKit" ]] ||
        invalid="$invalid pom-ownership"

    local component_artifact="$artifact"
    case "$artifact" in
        p2p-core-*) component_artifact="p2p-core" ;;
        p2p-transport-lan-*) component_artifact="p2p-transport-lan" ;;
        p2p-network-provisioning-android-android)
            component_artifact="p2p-network-provisioning-android"
            ;;
    esac
    jq -e --arg group "$GROUP" --arg artifact "$component_artifact" --arg version "$VERSION" '
        .formatVersion == "1.1" and
        .component.group == $group and
        .component.module == $artifact and
        .component.version == $version
    ' "$module" >/dev/null || invalid="$invalid module-metadata"

    if [[ -n "$invalid" ]]; then
        fail=1
        echo "FAIL $artifact — invalid:$invalid"
    else
        echo "OK   $artifact  (readable main/sources, Dokka index, POM, module metadata)"
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
echo "RESULT: PASS — $checked publications carry readable artifacts, real Dokka docs, and complete release metadata"
