#!/usr/bin/env bash
# P1-29 (BLD-2, 2026-07): executable release gate for the publishing artifact set.
#
# Publishes all modules to a throwaway Maven-local repository (never touches
# ~/.m2) and asserts that every publication of the four library modules carries
# the full Maven-Central-required artifact set:
#   main artifact (.jar / .aar / .klib) + -sources.jar + -javadoc.jar + .pom + .module
#
# Referenced from docs/releasing/checklist.md (local release-shape gate).
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
command -v javap >/dev/null 2>&1 || { echo "FATAL: javap from JDK 17 is required" >&2; exit 2; }
VERSION="$(sed -n 's/^VERSION_NAME=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
GROUP="$(sed -n 's/^GROUP=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
KOTLIN_VERSION="$(sed -n 's/^kotlin = "\([^"]*\)"/\1/p' "$ROOT/gradle/libs.versions.toml")"
if [[ -z "$VERSION" || -z "$GROUP" || -z "$KOTLIN_VERSION" ]]; then
    echo "FATAL: could not read publication/toolchain versions from repository sources" >&2
    exit 2
fi
GROUP_PATH="${GROUP//.//}"
INSPECTION_DIR="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-artifact-inspection.XXXXXX")"
OWN_REPO=0

cleanup() {
    rm -rf "$INSPECTION_DIR"
    if [[ "$OWN_REPO" == "1" ]]; then
        rm -rf "$REPO_DIR"
    fi
}
trap cleanup EXIT

if [[ $# -ge 1 ]]; then
    REPO_DIR="$1"
    echo "==> Verifying existing repo: $REPO_DIR (group $GROUP, version $VERSION)"
else
    REPO_DIR="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-publish-check.XXXXXX")"
    OWN_REPO=1
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
        grep -Eq '\.kt$' <<<"$source_entries" || invalid="$invalid sources-without-kotlin"
    fi
    [[ "$javadoc_entries" =~ (^|$'\n')([^$'\n']*/)?index\.html($|$'\n') ]] ||
        invalid="$invalid javadoc-without-index"

    # Published JVM jars and Android AARs must carry the exact canonical
    # repository license, not merely a POM URL.
    local license_copy="$INSPECTION_DIR/$artifact-LICENSE"
    if [[ "$main_suffix" == ".aar" ]]; then
        if ! unzip -p "$main" META-INF/LICENSE >"$license_copy"; then
            invalid="$invalid missing-embedded-license"
        fi
    elif [[ "$main_suffix" == ".jar" ]]; then
        if ! unzip -p "$main" META-INF/LICENSE >"$license_copy"; then
            invalid="$invalid missing-embedded-license"
        fi
    fi
    if [[ -f "$license_copy" ]] && ! cmp -s "$ROOT/LICENSE" "$license_copy"; then
        invalid="$invalid noncanonical-embedded-license"
    fi

    xmllint --noout "$pom" >/dev/null 2>&1 || invalid="$invalid malformed-pom"
    local pom_group pom_artifact pom_version pom_name pom_description pom_url
    local pom_license pom_developer pom_developer_email pom_developer_org
    local pom_developer_org_url pom_scm
    pom_group="$(xmllint --xpath "string(/*[local-name()='project']/*[local-name()='groupId'])" "$pom")"
    pom_artifact="$(xmllint --xpath "string(/*[local-name()='project']/*[local-name()='artifactId'])" "$pom")"
    pom_version="$(xmllint --xpath "string(/*[local-name()='project']/*[local-name()='version'])" "$pom")"
    pom_name="$(xmllint --xpath "string(/*[local-name()='project']/*[local-name()='name'])" "$pom")"
    pom_description="$(xmllint --xpath "string(/*[local-name()='project']/*[local-name()='description'])" "$pom")"
    pom_url="$(xmllint --xpath "string(/*[local-name()='project']/*[local-name()='url'])" "$pom")"
    pom_license="$(xmllint --xpath "string(/*[local-name()='project']/*[local-name()='licenses']/*[local-name()='license']/*[local-name()='name'])" "$pom")"
    pom_developer="$(xmllint --xpath "string(/*[local-name()='project']/*[local-name()='developers']/*[local-name()='developer']/*[local-name()='id'])" "$pom")"
    pom_developer_email="$(xmllint --xpath "string(/*[local-name()='project']/*[local-name()='developers']/*[local-name()='developer']/*[local-name()='email'])" "$pom")"
    pom_developer_org="$(xmllint --xpath "string(/*[local-name()='project']/*[local-name()='developers']/*[local-name()='developer']/*[local-name()='organization'])" "$pom")"
    pom_developer_org_url="$(xmllint --xpath "string(/*[local-name()='project']/*[local-name()='developers']/*[local-name()='developer']/*[local-name()='organizationUrl'])" "$pom")"
    pom_scm="$(xmllint --xpath "string(/*[local-name()='project']/*[local-name()='scm']/*[local-name()='url'])" "$pom")"

    [[ "$pom_group" == "$GROUP" ]] || invalid="$invalid pom-group"
    [[ "$pom_artifact" == "$artifact" ]] || invalid="$invalid pom-artifact"
    [[ "$pom_version" == "$VERSION" ]] || invalid="$invalid pom-version"
    [[ -n "$pom_name" && -n "$pom_description" && "$pom_url" == "https://github.com/p2pKit/P2pKit" ]] ||
        invalid="$invalid pom-project-metadata"
    [[ "$pom_license" == "The Apache License, Version 2.0" ]] || invalid="$invalid pom-license"
    [[ -n "$pom_developer" && "$pom_scm" == "https://github.com/p2pKit/P2pKit" ]] ||
        invalid="$invalid pom-ownership"
    [[ "$pom_developer_email" == "apdelrahman1911@users.noreply.github.com" &&
       "$pom_developer_org" == "p2pKit" &&
       "$pom_developer_org_url" == "https://github.com/p2pKit" ]] ||
        invalid="$invalid pom-developer-metadata"

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

check_kotlin_module() {
    local artifact="$1" packaging="$2" expected_module="$3"
    local container="$BASE/$artifact/$VERSION/$artifact-$VERSION.$packaging"
    if [[ ! -f "$container" ]]; then
        fail=1
        echo "FAIL $artifact — cannot inspect missing $packaging"
        return
    fi

    local module_container="$container"
    if [[ "$packaging" == "aar" ]]; then
        module_container="$INSPECTION_DIR/$artifact-classes.jar"
        if ! unzip -p "$container" classes.jar >"$module_container"; then
            fail=1
            echo "FAIL $artifact — classes.jar is missing or unreadable"
            return
        fi
    fi

    local actual expected
    actual="$(unzip -Z1 "$module_container" | awk '/^META-INF\/.*\.kotlin_module$/ { print }')"
    expected="META-INF/$expected_module.kotlin_module"
    if [[ "$actual" != "$expected" ]]; then
        fail=1
        echo "FAIL $artifact — Kotlin module identity was '${actual:-missing}', expected '$expected'"
    else
        echo "OK   $artifact  (Kotlin module identity $expected_module)"
    fi
}

check_klib_identity() {
    local artifact="$1" expected_short_name="$2" expected_native_target="$3"
    local klib="$BASE/$artifact/$VERSION/$artifact-$VERSION.klib"
    if [[ ! -f "$klib" ]]; then
        fail=1
        echo "FAIL $artifact — cannot inspect missing klib"
        return
    fi

    local manifest compiler_version short_name unique_name native_targets
    if ! manifest="$(unzip -p "$klib" default/manifest)"; then
        fail=1
        echo "FAIL $artifact — default/manifest is missing or unreadable"
        return
    fi
    compiler_version="$(printf '%s\n' "$manifest" | sed -n 's/^compiler_version=//p')"
    short_name="$(printf '%s\n' "$manifest" | sed -n 's/^short_name=//p')"
    unique_name="$(printf '%s\n' "$manifest" | sed -n 's/^unique_name=//p')"
    native_targets="$(printf '%s\n' "$manifest" | sed -n 's/^native_targets=//p')"

    local expected_unique_name="${GROUP}\\:${expected_short_name}"
    local invalid=""
    [[ "$compiler_version" == "$KOTLIN_VERSION" ]] || invalid="$invalid compiler-version"
    [[ "$short_name" == "$expected_short_name" ]] || invalid="$invalid short-name"
    [[ "$unique_name" == "$expected_unique_name" ]] || invalid="$invalid unique-name"
    [[ "$native_targets" == "$expected_native_target" ]] || invalid="$invalid native-target"
    if [[ -n "$invalid" ]]; then
        fail=1
        echo "FAIL $artifact — invalid KLIB identity:$invalid"
    else
        echo "OK   $artifact  (Kotlin $KOTLIN_VERSION KLIB identity, $expected_native_target)"
    fi
}

check_rc2_legacy_jvm_symbols() {
    local core_jar="$BASE/p2p-core-jvm/$VERSION/p2p-core-jvm-$VERSION.jar"
    local desktop_jar="$BASE/p2p-network-provisioning-desktop/$VERSION/p2p-network-provisioning-desktop-$VERSION.jar"
    if [[ ! -f "$core_jar" || ! -f "$desktop_jar" ]]; then
        fail=1
        echo "FAIL JVM artifacts — cannot inspect RC2 compatibility symbols"
        return
    fi

    local p2p_error unsupported_manager desktop_manager
    p2p_error="$(javap -classpath "$core_jar" -p -s dev.p2pkit.core.P2pError)"
    unsupported_manager="$(
        javap -classpath "$core_jar" -p -s \
            dev.p2pkit.core.provisioning.UnsupportedNetworkProvisioningManager
    )"
    desktop_manager="$(
        javap -classpath "$desktop_jar" -p -s \
            dev.p2pkit.provisioning.desktop.JvmNetworkProvisioningManager
    )"

    # Kotlin 2.4's ABI dumper no longer lists these compiler-generated public
    # symbols even though its JVM backend still emits them. They exist in rc2,
    # so inspect the actual class files rather than weakening binary coverage.
    local invalid=""
    grep -Fq \
        'descriptor: (Ljava/lang/String;Ljava/lang/Throwable;ILkotlin/jvm/internal/DefaultConstructorMarker;)V' \
        <<<"$p2p_error" || invalid="$invalid P2pError-default-constructor"
    grep -Fq 'public static final java.lang.String NOT_IN_V01;' \
        <<<"$unsupported_manager" || invalid="$invalid provisioning-constant"
    grep -Fq 'public static final long DEFAULT_POLL_INTERVAL_MS;' \
        <<<"$desktop_manager" || invalid="$invalid desktop-poll-constant"

    if [[ -n "$invalid" ]]; then
        fail=1
        echo "FAIL JVM artifacts — missing RC2 compatibility symbols:$invalid"
    else
        echo "OK   JVM artifacts  (RC2 compiler-generated symbols preserved)"
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

# Kotlin 2.4 changes default JVM module names. These checks prevent a toolchain
# update from silently changing the rc2 module identity embedded in JAR/AAR
# consumers even when the public declarations remain ABI-compatible.
check_kotlin_module p2p-core-jvm                             jar p2p-core
check_kotlin_module p2p-core-android                         aar p2p-core
check_kotlin_module p2p-transport-lan-jvm                    jar p2p-transport-lan
check_kotlin_module p2p-transport-lan-android                aar p2p-transport-lan
check_kotlin_module p2p-network-provisioning-android-android aar p2p-network-provisioning-android
check_kotlin_module p2p-network-provisioning-desktop         jar p2p-network-provisioning-desktop
check_rc2_legacy_jvm_symbols

# iOS targets publish only from a macOS host.
if [[ "$(uname -s)" == "Darwin" ]]; then
    for target in iosarm64 iossimulatorarm64 iosx64; do
        check "p2p-core-$target"          .klib
        check "p2p-transport-lan-$target" .klib
        case "$target" in
            iosarm64) native_target="ios_arm64" ;;
            iossimulatorarm64) native_target="ios_simulator_arm64" ;;
            iosx64) native_target="ios_x64" ;;
        esac
        check_klib_identity "p2p-core-$target" p2p-core "$native_target"
        check_klib_identity "p2p-transport-lan-$target" p2p-transport-lan "$native_target"
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
