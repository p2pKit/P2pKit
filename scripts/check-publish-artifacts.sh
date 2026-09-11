#!/usr/bin/env bash
# P1-29 (BLD-2, 2026-07): executable release gate for the publishing artifact set.
#
# Publishes all modules to a throwaway Maven-local repository (never touches
# ~/.m2) and asserts that every publication of the four library modules carries
# the full Maven-Central-required artifact set:
#   main artifact (.jar / .aar / .klib) + -sources.jar + -javadoc.jar + .pom + .module
# Native coordinates also require -metadata.jar; LAN's native coordinates
# additionally require the named -cinterop-p2pkit_nw.klib dependency artifact.
#
# Referenced from docs/releasing/checklist.md (local release-shape gate).
# The six iOS klib publications require a macOS host (iOS targets compile only
# there); on other hosts those rows are skipped with a warning.
#
# Usage: scripts/check-publish-artifacts.sh [existing-repo-dir]
#        scripts/check-publish-artifacts.sh --embedded-jmdns-only <existing-repo-dir>
#   Embedded only: checks the two LAN runtime/source sets and portable metadata;
#                  requires the same-source embeddedJmdnsJar producer, never publishes,
#                  and is not the complete publication/release gate.
#   No argument:   runs `./gradlew publishToMavenLocal -Dmaven.repo.local=<tmp>`
#                  and verifies the result (the temp repo is removed on exit).
#   With argument: skips publishing and verifies the given repo directory
#                  (e.g. "$HOME/.m2/repository" after a manual dry-run).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EMBEDDED_ONLY=0
if [[ "${1:-}" == "--embedded-jmdns-only" ]]; then
    [[ $# == 2 && -d "$2" ]] || {
        echo "FATAL: --embedded-jmdns-only requires one existing repository directory" >&2
        exit 2
    }
    EMBEDDED_ONLY=1
    shift
fi
command -v python3 >/dev/null 2>&1 || { echo "FATAL: Python 3 is required" >&2; exit 2; }
if [[ "$EMBEDDED_ONLY" == 0 ]]; then
    command -v jq >/dev/null 2>&1 || { echo "FATAL: jq is required" >&2; exit 2; }
    command -v xmllint >/dev/null 2>&1 || { echo "FATAL: xmllint is required" >&2; exit 2; }
    command -v unzip >/dev/null 2>&1 || { echo "FATAL: unzip is required" >&2; exit 2; }
    command -v javap >/dev/null 2>&1 || { echo "FATAL: javap from JDK 17 is required" >&2; exit 2; }
fi
VERSION="$(sed -n 's/^VERSION_NAME=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
GROUP="$(sed -n 's/^GROUP=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
KOTLIN_VERSION="$(sed -n 's/^kotlin = "\([^"]*\)"/\1/p' "$ROOT/gradle/libs.versions.toml")"
COROUTINES_VERSION="$(sed -n 's/^coroutines = "\([^"]*\)"/\1/p' "$ROOT/gradle/libs.versions.toml")"
if [[ -z "$VERSION" || -z "$GROUP" || -z "$KOTLIN_VERSION" || -z "$COROUTINES_VERSION" ]]; then
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
    local native_metadata="" cinterop=""
    local required_artifacts=("$artifact-$VERSION$main_suffix"
                              "$artifact-$VERSION-sources.jar"
                              "$artifact-$VERSION-javadoc.jar"
                              "$artifact-$VERSION.pom"
                              "$artifact-$VERSION.module")
    if [[ "$main_suffix" == ".klib" ]]; then
        native_metadata="$dir/$artifact-$VERSION-metadata.jar"
        required_artifacts+=("$artifact-$VERSION-metadata.jar")
        case "$artifact" in
            p2p-transport-lan-iosarm64|p2p-transport-lan-iossimulatorarm64|p2p-transport-lan-iosx64)
                cinterop="$dir/$artifact-$VERSION-cinterop-p2pkit_nw.klib"
                required_artifacts+=("$artifact-$VERSION-cinterop-p2pkit_nw.klib")
                ;;
        esac
    fi
    local missing=""
    local f
    for f in "${required_artifacts[@]}"; do
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
    if [[ -n "$native_metadata" ]]; then
        unzip -tq "$native_metadata" >/dev/null 2>&1 || invalid="$invalid unreadable-native-metadata"
    fi
    if [[ -n "$cinterop" ]]; then
        unzip -tq "$cinterop" >/dev/null 2>&1 || invalid="$invalid unreadable-cinterop"
    fi

    local source_entries javadoc_entries
    source_entries="$(unzip -Z1 "$sources")"
    javadoc_entries="$(unzip -Z1 "$javadoc")"
    if [[ "$artifact" != "p2p-network-provisioning-android" ]]; then
        grep -Eq '\.kt$' <<<"$source_entries" || invalid="$invalid sources-without-kotlin"
    fi
    [[ "$javadoc_entries" =~ (^|$'\n')([^$'\n']*/)?index\.html($|$'\n') ]] ||
        invalid="$invalid javadoc-without-index"

    # Embedded-license policy: main JAR/AAR, native metadata and every sources/Dokka JAR.
    # Keep the KLIB packaging exception explicit; it is not a legal waiver.
    local license_archives=("$sources" "$javadoc")
    case "$main_suffix" in
        .jar|.aar) license_archives+=("$main") ;;
        .klib)
            license_archives+=("$native_metadata")
            echo "EXEMPT $artifact main KLIB — embedded-license check only; POM license remains required"
            if [[ -n "$cinterop" ]]; then
                echo "EXEMPT $(basename "$cinterop") — embedded-license check only; POM license remains required"
            fi
            ;;
        *) invalid="$invalid unsupported-main-license-policy" ;;
    esac
    local license_archive license_entries license_count
    local license_copy="$INSPECTION_DIR/$artifact-LICENSE"
    for license_archive in "${license_archives[@]}"; do
        if ! license_entries="$(unzip -Z1 "$license_archive" 2>/dev/null)"; then
            invalid="$invalid unreadable-license-archive-$(basename "$license_archive")"
            continue
        fi
        license_count="$(awk '$0 == "META-INF/LICENSE" { n++ } END { print n+0 }' <<<"$license_entries")"
        if [[ "$license_count" != "1" ]]; then
            invalid="$invalid missing-or-duplicate-license-$(basename "$license_archive")"
        elif ! unzip -p "$license_archive" META-INF/LICENSE >"$license_copy" 2>/dev/null; then
            invalid="$invalid unreadable-license-$(basename "$license_archive")"
        elif ! cmp -s "$ROOT/LICENSE" "$license_copy"; then
            invalid="$invalid noncanonical-license-$(basename "$license_archive")"
        else
            echo "OK   $(basename "$license_archive")  (one canonical META-INF/LICENSE)"
        fi
    done
    # End embedded-license policy.

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

# Embedded-JmDNS policy: shared by the complete gate and its explicit LAN-only mode.
check_embedded_jmdns() {
    if ! python3 -B - "$ROOT" "$BASE" "$GROUP" "$VERSION" "$KOTLIN_VERSION" "$COROUTINES_VERSION" <<'PY'
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import stat
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT, BASE = map(Path, sys.argv[1:3])
GROUP, VERSION = sys.argv[3:5]
KOTLIN_VERSION, COROUTINES_VERSION = sys.argv[5:7]
LAN_PREFIX = "dev/p2pkit/transport/lan/"
PREFIX = "dev/p2pkit/transport/lan/internal/jmdns/"
NOTICES = "META-INF/p2pkit/third-party/jmdns/"
KOTLIN_MODULE = "META-INF/p2p-transport-lan.kotlin_module"
VENDOR = ROOT / "library/p2p-transport-lan/vendor/jmdns"
PRODUCER = ROOT / "library/p2p-transport-lan/build/embedded-jmdns/p2pkit-internal-jmdns.jar"
MAX_ARCHIVE = 64 * 1024 * 1024
MAX_MEMBER = 16 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_file(path):
    require(path.is_file() and not path.is_symlink(), "missing/nonregular artifact or input: " + str(path))
    with path.open("rb") as stream:
        data = stream.read(MAX_ARCHIVE + 1)
    require(0 < len(data) <= MAX_ARCHIVE, "empty/oversized input: " + str(path))
    return data


def archive(data, label):
    result, seen, total = {}, set(), 0
    with zipfile.ZipFile(io.BytesIO(data)) as source:
        require(len(source.infolist()) <= 4096, label + ": too many ZIP entries")
        for entry in source.infolist():
            name = entry.filename
            parts = name.rstrip("/").split("/")
            require(name == entry.orig_filename and name not in seen and
                    all(part not in ("", ".", "..") for part in parts) and
                    "\\" not in name and "\0" not in name and not re.match(r"^[A-Za-z]:", name),
                    label + ": duplicate/unsafe ZIP entry " + repr(name))
            seen.add(name)
            kind = stat.S_IFMT(entry.external_attr >> 16)
            require(kind in (0, stat.S_IFDIR if entry.is_dir() else stat.S_IFREG) and not entry.flag_bits & 1,
                    label + ": linked/nonregular/encrypted ZIP entry " + name)
            total += entry.file_size
            require(entry.file_size <= MAX_MEMBER and total <= MAX_ARCHIVE, label + ": ZIP content exceeds bound")
            if not entry.is_dir():
                with source.open(entry) as stream:
                    content = stream.read(MAX_MEMBER + 1)
                require(len(content) == entry.file_size, label + ": ZIP member size mismatch")
                result[name] = content
    return result


def class_constants(name, data):
    # Header/namespace inspection only; never load code or claim JVM verification.
    require(len(data) >= 10 and data[:4] == b"\xca\xfe\xba\xbe", "invalid class file: " + name)
    minor, major, count = struct.unpack_from(">HHH", data, 4)
    if name.startswith(PREFIX):
        require((minor, major) == (0, 52), "embedded class is not Java 8 bytecode: " + name)
    position, index, strings, classes = 10, 1, {}, {}
    while index < count:
        require(position < len(data), "truncated constant pool: " + name)
        tag = data[position]
        position += 1
        if tag == 1:
            require(position + 2 <= len(data), "truncated UTF8 length: " + name)
            size = struct.unpack_from(">H", data, position)[0]
            position += 2
            strings[index] = data[position:position + size]
            position += size
        elif tag == 7:
            require(position + 2 <= len(data), "truncated class reference: " + name)
            classes[index] = struct.unpack_from(">H", data, position)[0]
            position += 2
        elif tag in (3, 4, 9, 10, 11, 12, 18):
            position += 4
        elif tag in (5, 6):
            position += 8
            index += 1
        elif tag in (8, 16):
            position += 2
        elif tag == 15:
            position += 3
        elif tag in (17, 19, 20) and major >= (55 if tag == 17 else 53):
            position += 4 if tag == 17 else 2
        else:
            raise ValueError("unsupported constant-pool tag in " + name)
        require(position <= len(data), "truncated constant pool payload: " + name)
        index += 1
    require(count > 1 and position + 6 <= len(data), "missing class identity: " + name)
    this_class = struct.unpack_from(">H", data, position + 2)[0]
    require(strings.get(classes.get(this_class)) == name[:-6].encode("utf-8"), "class entry/identity mismatch: " + name)
    require(not any(b"javax/jmdns" in value or b"javax.jmdns" in value for value in strings.values()),
            "unrelocated JmDNS class reference: " + name)
    return set(strings.values())


def inspect_entries(entries, label):
    for name, data in entries.items():
        require(not re.search(r"(?:^|/)javax/jmdns/", name) and not name.startswith("org/slf4j/") and
                not name.startswith(("META-INF/maven/org.jmdns/", "META-INF/maven/javax.jmdns/")) and
                name not in ("version.properties", "META-INF/INDEX.LIST") and
                not name.startswith("META-INF/services/org.slf4j."), label + ": upstream/provider entry " + name)
        if name.endswith(".class"):
            require(name.startswith(LAN_PREFIX), label + ": bundled non-LAN class " + name)
            class_constants(name, data)
        if name.upper() == "META-INF/MANIFEST.MF":
            manifest = data.decode("utf-8", errors="strict").replace("\r\n", "\n").replace("\r", "\n").replace("\n ", "")
            require(not re.search(r"javax[./]jmdns|org[./]jmdns|^Main-Class:|^Bundle-|"
                                  r"^(?:Implementation|Specification)-[^:]+:.*(?:\bjmdns\b|\b3\.6\.3\s*$)",
                                  manifest, re.M | re.I),
                    label + ": upstream executable/module manifest")


def match_resources(entries, resources, label, required=True):
    actual = {name for name in entries if name.startswith(NOTICES) or
              (name.startswith(PREFIX) and not name.endswith((".class", ".java")))}
    expected = set(resources) - {"META-INF/LICENSE"}
    require(actual == expected if required else actual <= expected, label + ": private resource inventory differs")
    for name in (resources if required else set(resources) & set(entries)):
        require(entries.get(name) == resources[name], label + ": changed/missing resource " + name)


def portable(value):
    if isinstance(value, dict):
        for key, item in value.items():
            portable(key)
            portable(item)
    elif isinstance(value, list):
        for item in value:
            portable(item)
    elif isinstance(value, str):
        require(not any(token in value for token in ("file:", "/root/", "/home/", "/Users/", "\\")) and
                not re.match(r"^[A-Za-z]:[/\\]", value), "nonportable publication metadata")


def metadata(directory, artifact, suffix, validator, artifacts):
    allowed = {(GROUP, "p2p-core"): VERSION, (GROUP, "p2p-core-" + suffix): VERSION,
               ("org.jetbrains.kotlinx", "kotlinx-coroutines-core"): COROUTINES_VERSION,
               ("org.jetbrains.kotlinx", "kotlinx-coroutines-core-jvm"): COROUTINES_VERSION,
               ("org.jetbrains.kotlin", "kotlin-stdlib"): KOTLIN_VERSION, ("org.slf4j", "slf4j-api"): "2.0.7"}
    pom_coordinates = set(allowed) - {(GROUP, "p2p-core"), ("org.jetbrains.kotlinx", "kotlinx-coroutines-core")}

    def dependency(group, module, version):
        require((group, module) in allowed and isinstance(version, str) and
                re.fullmatch(r"[A-Za-z0-9_.+-]+", version), "unexpected/unpublished dependency in " + artifact)
        require(version == allowed[group, module], "wrong published dependency version in " + artifact + ": " + module)

    ns = "{http://maven.apache.org/POM/4.0.0}"
    pom = ET.fromstring(read_file(directory / (artifact + "-" + VERSION + ".pom")),
                       parser=ET.XMLParser(target=validator.NoDtdBuilder()))
    require(pom.tag == ns + "project", "invalid POM root in " + artifact)

    def field(parent, key, default=None):
        nodes = parent.findall(ns + key)
        if not nodes and default is not None:
            return default
        require(len(nodes) == 1 and not list(nodes[0]), "missing/duplicate POM field " + key)
        return (nodes[0].text or "").strip()

    require([field(pom, key) for key in ("groupId", "artifactId", "version")] == [GROUP, artifact, VERSION],
            "public POM identity changed: " + artifact)
    require(field(pom, "packaging", "jar") == ("jar" if suffix == "jvm" else "aar"), "public POM packaging changed")
    portable(ET.tostring(pom, encoding="unicode"))
    require(not any(pom.findall(".//" + ns + name) for name in (
        "systemPath", "parent", "profiles", "build", "dependencyManagement", "repositories", "pluginRepositories")),
        "private repository/system or inherited dependency in " + artifact)
    scopes = {}
    containers = pom.findall(ns + "dependencies")
    items = pom.findall(ns + "dependencies/" + ns + "dependency")
    require(len(containers) == 1 and len(items) == len(list(containers[0])) and
            len(items) == len(pom.findall(".//" + ns + "dependency")), "invalid POM dependencies container")
    for item in items:
        require({node.tag for node in item} <= {ns + key for key in (
            "groupId", "artifactId", "version", "scope", "optional", "type")}, "unsupported POM dependency fields")
        group, module, version = [field(item, key) for key in ("groupId", "artifactId", "version")]
        dependency(group, module, version)
        require((group, module) in pom_coordinates, "unexpected POM root dependency")
        require(field(item, "optional", "false") == "false", "optional POM dependency")
        allowed_types = {"jar", "aar"} if (group, module) == (GROUP, "p2p-core-android") else {"jar"}
        require(field(item, "type", "jar") in allowed_types, "unexpected POM dependency type")
        scope = field(item, "scope", "compile")
        require((group, module) not in scopes and scope in ("compile", "runtime"), "invalid POM dependency scope")
        scopes[group, module] = scope
    require(scopes.get((GROUP, "p2p-core-" + suffix)) == "compile" and
            scopes.get(("org.jetbrains.kotlinx", "kotlinx-coroutines-core-jvm")) == "compile" and
            scopes.get(("org.slf4j", "slf4j-api")) == "runtime" and
            scopes.get(("org.jetbrains.kotlin", "kotlin-stdlib"), "compile") == "compile",
            "LAN POM API/runtime edges changed: " + artifact)

    document = json.loads(read_file(directory / (artifact + "-" + VERSION + ".module")),
                          object_pairs_hook=validator.no_duplicate_keys, parse_constant=validator.no_nonfinite)
    require(type(document) is dict and document.get("formatVersion") == "1.1", "invalid Gradle module metadata")
    portable(document)
    component = document.get("component", {})
    require([component.get(key) for key in ("group", "module", "version")] == [GROUP, "p2p-transport-lan", VERSION],
            "public Gradle module identity changed: " + artifact)
    root_module_url = "../../p2p-transport-lan/" + VERSION + "/p2p-transport-lan-" + VERSION + ".module"
    require("url" not in component or component["url"] == root_module_url, "nonpublic Gradle component URL")
    main_name = artifact + "-" + VERSION + (".jar" if suffix == "jvm" else ".aar")
    source_name = artifact + "-" + VERSION + "-sources.jar"
    allowed_files = {name: name for name in (main_name, source_name, artifact + "-" + VERSION + "-javadoc.jar")}
    if suffix == "android":
        # Existing LOGICAL_ARTIFACT_ALIASES in prepare-audit-consumer-metadata.py:
        # AGP's logical name differs, but it still downloads the canonical AAR.
        allowed_files["p2p-transport-lan.aar"] = main_name
    variants, usages, names, source_variants = document.get("variants"), set(), set(), 0
    require(isinstance(variants, list) and variants, "missing Gradle variants")
    for variant in variants:
        require(isinstance(variant, dict) and isinstance(variant.get("name"), str) and
                variant["name"] not in names and "available-at" not in variant, "invalid/redirected Gradle variant")
        names.add(variant["name"])
        deps = set()
        for collection in ("dependencies", "dependencyConstraints"):
            items, seen = variant.get(collection, []), set()
            require(isinstance(items, list), "invalid Gradle dependency list")
            for item in items:
                require(isinstance(item, dict) and set(item) == {"group", "module", "version"} and
                        isinstance(item.get("version"), dict) and set(item["version"]) == {"requires"},
                        "invalid Gradle dependency")
                group, module = item.get("group"), item.get("module")
                dependency(group, module, item["version"]["requires"])
                require((group, module) not in seen, "duplicate Gradle dependency")
                seen.add((group, module))
            if collection == "dependencies":
                deps = seen  # Constraints can restrict a version but cannot supply a runtime/API edge.
        files = variant.get("files", [])
        require(isinstance(files, list), "invalid Gradle variant files")
        for item in files:
            require(isinstance(item, dict) and item.get("name") in allowed_files and
                    item.get("url") == allowed_files[item["name"]],
                    "private/unpublished Gradle variant artifact")
            if item["url"] in (main_name, source_name):
                data = artifacts[item["url"]]
                require(type(item.get("size")) is int and item["size"] == len(data) and
                        item.get("sha256") == hashlib.sha256(data).hexdigest(), "stale Gradle artifact hash/size")
        attributes = variant.get("attributes", {})
        require(isinstance(attributes, dict), "invalid Gradle variant attributes")
        if any(item["name"] == source_name for item in files):
            require([item["name"] for item in files] == [source_name] and
                    attributes.get("org.gradle.category") == "documentation" and
                    attributes.get("org.gradle.docstype") == "sources", "invalid Gradle sources variant")
            source_variants += 1
        usage = attributes.get("org.gradle.usage")
        if attributes.get("org.gradle.category") == "library" and usage in ("java-api", "java-runtime"):
            usages.add(usage)
            require([item["url"] for item in files] == [main_name], "runtime/API variant does not carry its public archive")
            require(deps & {(GROUP, "p2p-core"), (GROUP, "p2p-core-" + suffix)} and
                    deps & {("org.jetbrains.kotlinx", "kotlinx-coroutines-core"),
                            ("org.jetbrains.kotlinx", "kotlinx-coroutines-core-jvm")}, "LAN Gradle API edges changed")
            require((("org.slf4j", "slf4j-api") in deps) == (usage == "java-runtime"), "SLF4J Gradle runtime edge changed")
    require(usages == {"java-api", "java-runtime"}, "missing LAN Gradle API/runtime variants")
    require(source_variants == 1, "missing/duplicate LAN Gradle sources variant")


def inspect():
    spec = importlib.util.spec_from_file_location("publication_vendor_policy", ROOT / "scripts/validate-sbom.py")
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    manifest, manifest_hash = validator.load_vendor_manifest(VENDOR)

    def bound_bytes(row):
        data = read_file(VENDOR / row["path"])
        require(hashlib.sha256(data).hexdigest() == row["sha256"], "vendor input changed during inspection: " + row["path"])
        return data

    resources = {row["entry"]: bound_bytes(row) for row in manifest["resources"]}
    manifest_bytes = read_file(VENDOR / "PROVENANCE.json")
    require(hashlib.sha256(manifest_bytes).hexdigest() == manifest_hash, "vendor manifest changed during inspection")
    resources[manifest["manifestEntry"]] = manifest_bytes
    for patch in [manifest["lifecyclePatch"], *manifest["followupPatches"]]:
        resources[NOTICES + patch["path"]] = bound_bytes(patch)
    canonical = read_file(ROOT / "LICENSE")
    require(resources["META-INF/LICENSE"] == canonical, "vendor/repository canonical licenses differ")
    properties = validator.no_duplicate_keys(line.split("=", 1) for line in
                                             resources[PREFIX + "version.properties"].decode().splitlines()
                                             if line and not line.startswith("#"))
    require(properties == {"jmdns.version": manifest["component"]["version"], "jmdns.upstream.version": "3.6.3"},
            "private/upstream version resource differs")
    source_entries = {row["path"].removeprefix("src/main/java/"): bound_bytes(row)
                      for row in manifest["sources"]}
    producer_bytes = read_file(PRODUCER)
    producer = archive(producer_bytes, "private producer")
    inspect_entries(producer, "private producer")
    match_resources(producer, resources, "private producer")
    classes = {name: data for name, data in producer.items() if name.endswith(".class")}
    require(classes and set(producer) == set(classes) | set(resources) | {"META-INF/MANIFEST.MF"},
            "private producer contains undeclared/missing entries")
    # Source-roster coverage and exact archive joins do not attest compilation.
    # The source-bound producer build and native tests remain separate gates.
    owners = {name[:-5] for name in source_entries}
    require(all(name.startswith(PREFIX) and name[:-6].split("$", 1)[0] in owners for name in classes),
            "private producer class has no declared Java source")
    require(all(name + ".class" in classes for name in owners if not name.endswith("/package-info")),
            "private producer is missing a declared top-level class")
    for name, resource in ((PREFIX + "JmDNS.class", PREFIX + "version.properties"),
                           (PREFIX + "impl/JmDNSImpl.class", "/" + PREFIX + "version.properties")):
        require(resource.encode() in class_constants(name, classes[name]), "private resource lookup missing: " + name)

    for suffix, extension in (("jvm", ".jar"), ("android", ".aar")):
        artifact = "p2p-transport-lan-" + suffix
        directory = BASE / artifact / VERSION
        main_name = artifact + "-" + VERSION + extension
        source_name = artifact + "-" + VERSION + "-sources.jar"
        runtime_bytes = read_file(directory / main_name)
        runtime = archive(runtime_bytes, artifact)
        inspect_entries(runtime, artifact)
        require(runtime.get("META-INF/LICENSE") == canonical, artifact + ": missing/noncanonical outer license")
        if suffix == "jvm":
            require(not any(name.endswith(".jar") for name in runtime), "JVM private component must be flat, not a nested JAR")
            require({name: data for name, data in runtime.items() if name.startswith(PREFIX) and name.endswith(".class")} == classes,
                    "JVM embedded classes differ from the actual private producer")
            match_resources(runtime, resources, artifact)
            module_entries = runtime
        else:
            nested = {name for name in runtime if name.endswith(".jar")}
            embedded = "libs/p2pkit-internal-jmdns.jar"
            require(nested == {"classes.jar", embedded} and not any(name.endswith(".class") for name in runtime),
                    "AAR must contain classes.jar and exactly the one declared private JAR")
            require(runtime[embedded] == producer_bytes, "AAR embedded JAR differs from the actual private producer")
            module_entries = archive(runtime["classes.jar"], "AAR classes.jar")
            inspect_entries(module_entries, "AAR classes.jar")
            require(not any(name.endswith(".jar") for name in module_entries), "AAR classes.jar contains a nested JAR")
            require(not any(name.startswith(PREFIX) or name.startswith(NOTICES) for name in module_entries),
                    "AAR classes.jar duplicates the private component")
            require("META-INF/LICENSE" not in module_entries or module_entries["META-INF/LICENSE"] == canonical,
                    "AAR classes.jar has a noncanonical license")
            match_resources(runtime, resources, artifact, required=False)
        require([name for name in module_entries if name.startswith("META-INF/") and name.endswith(".kotlin_module")] ==
                [KOTLIN_MODULE], artifact + ": public Kotlin module identity changed")
        source_bytes = read_file(directory / source_name)
        sources = archive(source_bytes, artifact + " sources")
        inspect_entries(sources, artifact + " sources")
        require({name: data for name, data in sources.items() if name.endswith(".java")} == source_entries and
                not any(name.endswith((".class", ".jar")) for name in sources), artifact + ": corrected Java sources differ")
        require(any(name.endswith(".kt") for name in sources), artifact + ": existing Kotlin sources missing")
        match_resources(sources, resources, artifact + " sources")
        metadata(directory, artifact, suffix, validator, {main_name: runtime_bytes, source_name: source_bytes})
        print("OK   " + artifact + " (exact embedded producer, corrected sources, notices/license, portable metadata)")
    print("OK   embedded JmDNS (" + str(len(classes)) + " Java-8 classes; source/producer/archive joins, not native lifecycle proof)")


try:
    inspect()
except (OSError, ValueError, KeyError, TypeError, AttributeError, RuntimeError,
        ET.ParseError, zipfile.BadZipFile, struct.error) as error:
    print("FAIL embedded JmDNS — " + str(error), file=sys.stderr)
    raise SystemExit(1)
PY
    then
        fail=1
    fi
}
# End embedded-JmDNS policy.

if [[ "$EMBEDDED_ONLY" == 1 ]]; then
    check_embedded_jmdns
    [[ "$fail" == 0 ]] || { echo "RESULT: FAIL — embedded JmDNS publication checks"; exit 1; }
    echo "RESULT: PASS — LAN JVM/Android runtime/source and metadata checks only; full publication gate NOT_EXECUTED"
    exit 0
fi

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
check_embedded_jmdns

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
