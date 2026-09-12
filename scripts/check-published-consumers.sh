#!/usr/bin/env bash
# Publishes every library to an isolated Maven repository, verifies the target
# POM scopes, then qualifies fresh JVM/Android/KMP/iOS consumers that depend
# only on staged P2pKit coordinates. The explicit source-local lan-jvm-android
# profile is supplemental, never a replacement for the complete native gate.
# Its optional executor retains each Gradle invocation's own stop/receipt.
# Project dependencies and repository sources are unavailable to consumers.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(sed -n 's/^VERSION_NAME=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
LATEST_PUBLISHED="$(sed -n 's/^LATEST_PUBLISHED_VERSION=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
GROUP="$(sed -n 's/^GROUP=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
KOTLIN_VERSION="$(sed -n 's/^kotlin = "\([^"]*\)"/\1/p' "$ROOT/gradle/libs.versions.toml")"
AGP_VERSION="$(sed -n 's/^agp = "\([^"]*\)"/\1/p' "$ROOT/gradle/libs.versions.toml")"
COROUTINES_VERSION="$(sed -n 's/^coroutines = "\([^"]*\)"/\1/p' "$ROOT/gradle/libs.versions.toml")"
IOS_MIN_VERSION="$(sed -n 's/^IOS_MIN_VERSION=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
GROUP_PATH="${GROUP//.//}"
# Default invocations retain the historical disposable work directory. Explicit
# retention/borrowed directories remain available without the audit executor.
# The opt-in executor supports only source-local publication into a new/empty
# borrowed directory beneath its initialized physical STATE/work. This script
# never deletes executor work, including failed or unfinished invocations.
KEEP_CONSUMER_ARTIFACTS="${P2PKIT_KEEP_CONSUMER_ARTIFACTS:-0}"
AUDIT_CONSUMER_METADATA="${P2PKIT_CONSUMER_AUDIT_METADATA:-0}"
GRADLE_EXECUTOR="${P2PKIT_GRADLE_EXECUTOR:-}"
REMOTE_REPOSITORY_URL="${P2PKIT_CONSUMER_REPOSITORY_URL:-}"
CONSUMER_PROFILE="${P2PKIT_CONSUMER_PROFILE:-complete}"
CURRENT_SOURCE_CONSUMER=1
AUDIT_WORK_STATE=""
for boolean_value in "$KEEP_CONSUMER_ARTIFACTS" "$AUDIT_CONSUMER_METADATA"; do
    [[ "$boolean_value" == 0 || "$boolean_value" == 1 ]] || {
        echo "FAIL: consumer retention/audit switches accept only 0 or 1" >&2
        exit 2
    }
done
case "$CONSUMER_PROFILE" in
    complete) ;;
    lan-jvm-android)
        [[ "$AUDIT_CONSUMER_METADATA" == 0 && -z "$REMOTE_REPOSITORY_URL" && $# -eq 0 ]] || {
            echo "FAIL: lan-jvm-android is source-local; no audit metadata, remote repository or arguments" >&2
            exit 2
        }
        ;;
    *)
        echo "FAIL: P2PKIT_CONSUMER_PROFILE accepts only complete or lan-jvm-android" >&2
        exit 2
        ;;
esac
if [[ -n "$GRADLE_EXECUTOR" ]]; then
    [[ "$GRADLE_EXECUTOR" == /* && -f "$GRADLE_EXECUTOR" && -x "$GRADLE_EXECUTOR" ]] || {
        echo "FAIL: P2PKIT_GRADLE_EXECUTOR must be an absolute executable file, not a shell fragment" >&2
        exit 2
    }
    [[ "${P2PKIT_AUDIT_STATE_DIR:-}" == /* && -d "$P2PKIT_AUDIT_STATE_DIR" &&
       ! -L "$P2PKIT_AUDIT_STATE_DIR" && -f "$P2PKIT_AUDIT_STATE_DIR/context.json" &&
       ! -L "$P2PKIT_AUDIT_STATE_DIR/context.json" ]] || {
        echo "FAIL: the consumer executor requires an initialized P2PKIT_AUDIT_STATE_DIR" >&2
        exit 2
    }
    [[ -z "$REMOTE_REPOSITORY_URL" && $# -eq 0 ]] || {
        echo "FAIL: the consumer executor supports only source-local publication (no remote or --latest-published mode)" >&2
        exit 2
    }
    [[ -n "${P2PKIT_CONSUMER_WORK_DIR:-}" ]] || {
        echo "FAIL: the consumer executor requires an explicit borrowed P2PKIT_CONSUMER_WORK_DIR beneath STATE/work" >&2
        exit 2
    }
    AUDIT_WORK_STATE="$P2PKIT_AUDIT_STATE_DIR"
fi
if [[ "$AUDIT_CONSUMER_METADATA" == 1 ]]; then
    [[ -n "$GRADLE_EXECUTOR" && -z "$REMOTE_REPOSITORY_URL" && $# -eq 0 ]] || {
        echo "FAIL: audit consumer metadata requires the executor and source-local publication mode" >&2
        exit 2
    }
fi

OWN_CONSUMER_WORK_DIR=0
if [[ -n "${P2PKIT_CONSUMER_WORK_DIR:-}" ]]; then
    WORK_DIR="$(python3 - "$P2PKIT_CONSUMER_WORK_DIR" "$AUDIT_WORK_STATE" <<'PY_WORK_DIR'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
if not path.is_absolute() or path.is_symlink() or path.resolve() != path:
    sys.exit("FAIL: P2PKIT_CONSUMER_WORK_DIR must be a physical absolute non-symlink path")
if sys.argv[2]:
    state = pathlib.Path(sys.argv[2])
    work = state / "work"
    for directory in (state, work):
        if not directory.is_dir() or directory.is_symlink() or directory.resolve(strict=True) != directory:
            sys.exit("FAIL: the consumer executor requires an initialized physical STATE/work directory")
    if work not in path.parents:
        sys.exit("FAIL: executor consumer work must be a strict descendant of initialized STATE/work")
if path.exists():
    if not path.is_dir() or any(path.iterdir()):
        sys.exit("FAIL: P2PKIT_CONSUMER_WORK_DIR must be a new or empty directory")
else:
    path.mkdir(mode=0o700)
print(path)
PY_WORK_DIR
)"
else
    WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-consumer-check.XXXXXX")"
    WORK_DIR="$(cd "$WORK_DIR" && pwd -P)"
    OWN_CONSUMER_WORK_DIR=1
fi
REPO_DIR="$WORK_DIR/repository"
FIXTURE_DIR="$WORK_DIR/consumer"
cleanup_consumer_work() {
    local result=$?
    trap - EXIT
    if [[ -z "$GRADLE_EXECUTOR" && "$OWN_CONSUMER_WORK_DIR" == 1 && "$KEEP_CONSUMER_ARTIFACTS" != 1 ]]; then
        if ! rm -rf -- "$WORK_DIR"; then
            echo "FAIL: could not remove owned consumer work directory: $WORK_DIR" >&2
            [[ "$result" != 0 ]] || result=125
        fi
    else
        echo "==> Retained consumer work directory: $WORK_DIR (script-owned=$OWN_CONSUMER_WORK_DIR)" >&2
    fi
    exit "$result"
}
trap cleanup_consumer_work EXIT

CONSUMER_RECEIPT_DIR=""
if [[ -n "$GRADLE_EXECUTOR" ]]; then
    # Evidence is outside disposable fixture outputs and is never removed here.
    CONSUMER_RECEIPT_DIR="$(mktemp -d "$P2PKIT_AUDIT_STATE_DIR/consumer-receipts.XXXXXX")"
    CONSUMER_RECEIPT_DIR="$(cd "$CONSUMER_RECEIPT_DIR" && pwd -P)"
fi
AUDIT_METADATA_HELPER="$ROOT/scripts/prepare-audit-consumer-metadata.py"

run_audit_consumer_gradle() {
    local purpose="$1" receipt="$2" result
    shift 2
    if "$GRADLE_EXECUTOR" --cwd "$ROOT" --wrapper "$ROOT/gradlew" \
        --purpose "$purpose" --receipt "$receipt" -- "$@"; then
        result=0
    else
        result=$?
    fi
    # A missing/malformed receipt or failed finalization is never a successful
    # consumer, even when the executor process reports product exit zero.
    python3 "$ROOT/scripts/check-audit-receipt.py" --purpose "$purpose" \
        --cwd "$ROOT" --wrapper "$ROOT/gradlew" "$receipt" "$result" -- "$@" || return 125
    return "$result"
}

for required_value in KOTLIN_VERSION AGP_VERSION COROUTINES_VERSION IOS_MIN_VERSION; do
    [[ -n "${!required_value}" ]] || {
        echo "FAIL: $required_value is missing from the repository version sources" >&2
        exit 2
    }
done

if [[ "${1:-}" == "--latest-published" ]]; then
    [[ $# -eq 1 ]] || { echo "FAIL: --latest-published accepts no additional arguments" >&2; exit 2; }
    [[ -n "$LATEST_PUBLISHED" && "$LATEST_PUBLISHED" != *-SNAPSHOT ]] || {
        echo "FAIL: LATEST_PUBLISHED_VERSION must identify a non-snapshot release" >&2
        exit 2
    }
    [[ -n "$REMOTE_REPOSITORY_URL" ]] || {
        echo "FAIL: --latest-published requires P2PKIT_CONSUMER_REPOSITORY_URL" >&2
        exit 2
    }
    VERSION="$LATEST_PUBLISHED"
    # Published RC3 bytes and their original dependency graph are immutable.
    # Only this explicit historical mode retains the upstream-JmDNS fixture.
    CURRENT_SOURCE_CONSUMER=0
elif [[ $# -ne 0 ]]; then
    echo "FAIL: usage: scripts/check-published-consumers.sh [--latest-published]" >&2
    exit 2
fi

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

pom_scope() {
    local pom="$1" artifact="$2"
    awk -v artifact="$artifact" '
        /<dependency>/ { in_dependency = 1; matched = 0 }
        in_dependency && index($0, "<artifactId>" artifact "</artifactId>") { matched = 1 }
        in_dependency && matched && /<scope>/ {
            line = $0
            sub(/^.*<scope>/, "", line)
            sub(/<\/scope>.*$/, "", line)
            print line
            exit
        }
        /<\/dependency>/ { in_dependency = 0; matched = 0 }
    ' "$pom"
}

assert_scope() {
    local pom="$1" artifact="$2" expected="$3" actual
    actual="$(pom_scope "$pom" "$artifact")"
    [[ "$actual" == "$expected" ]] ||
        fail "$(basename "$(dirname "$pom")")/$artifact scope was '${actual:-missing}', expected '$expected'"
}

if [[ -n "$REMOTE_REPOSITORY_URL" ]]; then
    [[ "$REMOTE_REPOSITORY_URL" == https://* ]] ||
        fail "remote consumer repository must use HTTPS"
    command -v curl >/dev/null 2>&1 || fail "curl is required for remote consumer verification"
    echo "==> Downloading $VERSION POMs from remote repository"
    mkdir -p "$REPO_DIR/$GROUP_PATH"
    remote_pom_artifacts=(
        p2p-core-jvm \
        p2p-transport-lan-jvm \
        p2p-network-provisioning-android-android \
        p2p-network-provisioning-desktop
    )
    if [[ "$CURRENT_SOURCE_CONSUMER" == 1 ]]; then
        remote_pom_artifacts+=(p2p-transport-lan-android)
    fi
    for artifact in "${remote_pom_artifacts[@]}"; do
        directory="$REPO_DIR/$GROUP_PATH/$artifact/$VERSION"
        mkdir -p "$directory"
        curl --fail --silent --show-error --location \
            "$REMOTE_REPOSITORY_URL/$GROUP_PATH/$artifact/$VERSION/$artifact-$VERSION.pom" \
            --output "$directory/$artifact-$VERSION.pom"
    done
    if [[ "$CURRENT_SOURCE_CONSUMER" == 1 ]]; then
        for artifact in p2p-transport-lan-jvm p2p-transport-lan-android; do
            directory="$REPO_DIR/$GROUP_PATH/$artifact/$VERSION"
            curl --fail --silent --show-error --location \
                "$REMOTE_REPOSITORY_URL/$GROUP_PATH/$artifact/$VERSION/$artifact-$VERSION.module" \
                --output "$directory/$artifact-$VERSION.module"
        done
    fi
    CONSUMER_REPOSITORY="$REMOTE_REPOSITORY_URL"
else
    echo "==> Publishing $VERSION to isolated repository"
    if [[ "$AUDIT_CONSUMER_METADATA" == 1 ]]; then
        ownership=borrowed
        [[ "$OWN_CONSUMER_WORK_DIR" != 1 ]] || ownership=owned
        python3 "$AUDIT_METADATA_HELPER" admit --root "$ROOT" --work-dir "$WORK_DIR" \
            --publication-receipt "$CONSUMER_RECEIPT_DIR/consumer-publish.json" --ownership "$ownership"
    fi
    publish_tasks=(publishToMavenLocal)
    if [[ "$CONSUMER_PROFILE" == lan-jvm-android ]]; then
        # Fixed source-local qualification request, not a smaller metadata
        # trust policy. LAN GMM depends on the core root, whose available-at variants
        # select these target publications. Never discover tasks dynamically
        # or silently publish native targets.
        publish_tasks=(
            :p2p-core:publishJvmPublicationToMavenLocal
            :p2p-core:publishAndroidPublicationToMavenLocal
            :p2p-transport-lan:publishJvmPublicationToMavenLocal
            :p2p-transport-lan:publishAndroidPublicationToMavenLocal
            :p2p-core:publishKotlinMultiplatformPublicationToMavenLocal
        )
    fi
    if [[ -n "$GRADLE_EXECUTOR" ]]; then
        (cd "$ROOT" && run_audit_consumer_gradle consumer-publish \
            "$CONSUMER_RECEIPT_DIR/consumer-publish.json" \
            --no-daemon --console=plain "${publish_tasks[@]}" -Dmaven.repo.local="$REPO_DIR")
    else
        (cd "$ROOT" && ./gradlew --no-daemon --console=plain "${publish_tasks[@]}" -Dmaven.repo.local="$REPO_DIR")
    fi
    CONSUMER_REPOSITORY="$REPO_DIR"
fi

BASE="$REPO_DIR/$GROUP_PATH"
CORE_JVM="$BASE/p2p-core-jvm/$VERSION/p2p-core-jvm-$VERSION.pom"
LAN_JVM="$BASE/p2p-transport-lan-jvm/$VERSION/p2p-transport-lan-jvm-$VERSION.pom"
LAN_ANDROID="$BASE/p2p-transport-lan-android/$VERSION/p2p-transport-lan-android-$VERSION.pom"
PROV_ANDROID="$BASE/p2p-network-provisioning-android-android/$VERSION/p2p-network-provisioning-android-android-$VERSION.pom"
PROV_DESKTOP="$BASE/p2p-network-provisioning-desktop/$VERSION/p2p-network-provisioning-desktop-$VERSION.pom"

required_poms=("$CORE_JVM" "$LAN_JVM")
if [[ "$CONSUMER_PROFILE" == complete ]]; then
    required_poms+=("$PROV_ANDROID" "$PROV_DESKTOP")
fi
if [[ "$CURRENT_SOURCE_CONSUMER" == 1 ]]; then
    required_poms+=("$LAN_ANDROID")
fi
for pom in "${required_poms[@]}"; do
    [[ -f "$pom" ]] || fail "missing generated POM: $pom"
done

assert_scope "$CORE_JVM" kotlinx-coroutines-core-jvm compile
assert_scope "$CORE_JVM" kotlinx-io-core-jvm compile
assert_scope "$CORE_JVM" kotlinx-serialization-json-jvm runtime
assert_scope "$CORE_JVM" cryptography-core-jvm runtime
assert_scope "$CORE_JVM" cryptography-provider-jdk-jvm runtime
assert_scope "$CORE_JVM" bcprov-jdk18on runtime

assert_scope "$LAN_JVM" p2p-core-jvm compile
assert_scope "$LAN_JVM" kotlinx-coroutines-core-jvm compile
if [[ "$CURRENT_SOURCE_CONSUMER" == 0 ]]; then
    assert_scope "$LAN_JVM" jmdns runtime
else
    assert_scope "$LAN_JVM" slf4j-api runtime
    assert_scope "$LAN_ANDROID" p2p-core-android compile
    assert_scope "$LAN_ANDROID" kotlinx-coroutines-core-jvm compile
    assert_scope "$LAN_ANDROID" slf4j-api runtime
fi

if [[ "$CONSUMER_PROFILE" == complete ]]; then
assert_scope "$PROV_ANDROID" p2p-core-android compile
assert_scope "$PROV_ANDROID" kotlinx-coroutines-core-jvm compile

assert_scope "$PROV_DESKTOP" p2p-core-jvm compile
assert_scope "$PROV_DESKTOP" kotlinx-coroutines-core-jvm compile
[[ -z "$(pom_scope "$PROV_DESKTOP" p2p-transport-lan-jvm)" ]] ||
    fail "desktop provisioning still publishes its test-only LAN dependency"
fi

if [[ "$CURRENT_SOURCE_CONSUMER" == 1 ]]; then
    # A successful project-local build cannot prove that the embedded component
    # ships. Inspect both published metadata formats before isolated resolution;
    # an unknown/file/private edge is a failure, not a dependency to auto-admit.
    python3 - "$BASE" "$GROUP" "$VERSION" "$KOTLIN_VERSION" "$COROUTINES_VERSION" <<'PY_LAN_METADATA'
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

base = Path(sys.argv[1])
group, version, kotlin_version, coroutines_version = sys.argv[2:]


def require(condition, message):
    if not condition:
        sys.exit(f"FAIL: embedded LAN publication metadata: {message}")


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, f"duplicate JSON key {key}")
        value[key] = item
    return value


def document(path):
    require(path.is_file() and not path.is_symlink(), f"missing/nonregular metadata {path.name}")
    with path.open("rb") as stream:
        value = stream.read(16 * 1024 * 1024 + 1)
    require(len(value) <= 16 * 1024 * 1024, f"oversized metadata {path.name}")
    return value


def local_name(element):
    return element.tag.rsplit("}", 1)[-1]


for platform in ("jvm", "android"):
    artifact = f"p2p-transport-lan-{platform}"
    stem = base / artifact / version / f"{artifact}-{version}"
    try:
        pom_text = document(Path(f"{stem}.pom")).decode("utf-8-sig")
    except UnicodeError:
        require(False, f"{artifact} POM must be UTF-8")
    # Decode before checking declarations so UTF-16/32 NUL bytes cannot hide
    # a DTD from the guard while remaining meaningful to the XML parser.
    require("\x00" not in pom_text, f"{artifact} POM must be UTF-8 without NUL bytes")
    require("<!DOCTYPE" not in pom_text.upper() and "<!ENTITY" not in pom_text.upper(),
            f"{artifact} POM DTD/entity declaration")
    try:
        pom = ET.fromstring(pom_text)
    except ET.ParseError:
        require(False, f"{artifact} malformed POM")
    direct = {local_name(child): child.text for child in pom}
    require(local_name(pom) == "project" and
            all(sum(local_name(child) == name for child in pom) == 1 for name in ("groupId", "artifactId", "version")),
            f"{artifact} ambiguous POM coordinates")
    require((direct.get("groupId"), direct.get("artifactId"), direct.get("version")) == (group, artifact, version),
            f"{artifact} POM coordinate mismatch")
    require(sum(local_name(child) == "dependencies" for child in pom) == 1,
            f"{artifact} missing/duplicate POM dependencies")
    allowed_pom = {
        (group, f"p2p-core-{platform}"): (version, "compile"),
        ("org.jetbrains.kotlinx", "kotlinx-coroutines-core-jvm"): (coroutines_version, "compile"),
        ("org.jetbrains.kotlin", "kotlin-stdlib"): (kotlin_version, "compile"),
        ("org.slf4j", "slf4j-api"): ("2.0.7", "runtime"),
    }
    dependencies = {}
    for dependency in pom.findall("{*}dependencies/{*}dependency"):
        fields = [local_name(child) for child in dependency]
        require(len(fields) == len(set(fields)) and
                set(fields) <= {"groupId", "artifactId", "version", "scope", "optional", "type"} and
                {"groupId", "artifactId", "version"} <= set(fields) and
                not dependency.attrib and all(not list(child) and not child.attrib for child in dependency),
                f"{artifact} POM duplicate/unsupported dependency fields")
        key = (dependency.findtext("{*}groupId"), dependency.findtext("{*}artifactId"))
        require(key in allowed_pom and key not in dependencies, f"{artifact} POM unexpected/duplicate dependency {key}")
        actual = (dependency.findtext("{*}version"), dependency.findtext("{*}scope", "compile"))
        require(actual == allowed_pom[key], f"{artifact} POM dependency version/scope mismatch: {key}")
        require(dependency.findtext("{*}optional", "false") == "false", f"{artifact} POM optional runtime dependency")
        expected_type = "aar" if key == (group, "p2p-core-android") else "jar"
        require(dependency.findtext("{*}type", expected_type) == expected_type,
                f"{artifact} POM unexpected dependency type: {key}")
        dependencies[key] = actual
    for key in ((group, f"p2p-core-{platform}"),
                ("org.jetbrains.kotlinx", "kotlinx-coroutines-core-jvm"), ("org.slf4j", "slf4j-api")):
        require(key in dependencies, f"{artifact} POM missing dependency {key}")

    module_path = Path(f"{stem}.module")
    try:
        module = json.loads(document(module_path), object_pairs_hook=unique_object)
    except (ValueError, UnicodeError):
        require(False, f"{artifact} malformed Gradle module metadata")
    require(isinstance(module, dict) and module.get("formatVersion") == "1.1",
            f"{artifact} unsupported Gradle module format")
    component = module.get("component")
    # This is the same root-component identity used by the complete metadata
    # admission; a platform publication is not a separately owned component.
    require(isinstance(component, dict) and
            (component.get("group"), component.get("module"), component.get("version")) ==
            (group, "p2p-transport-lan", version), f"{artifact} module coordinate mismatch")
    allowed_module = {
        (group, "p2p-core"): version,
        (group, f"p2p-core-{platform}"): version,
        ("org.jetbrains.kotlinx", "kotlinx-coroutines-core"): coroutines_version,
        ("org.jetbrains.kotlinx", "kotlinx-coroutines-core-jvm"): coroutines_version,
        ("org.jetbrains.kotlin", "kotlin-stdlib"): kotlin_version,
        ("org.slf4j", "slf4j-api"): "2.0.7",
    }
    usages = set()
    variants = module.get("variants")
    require(isinstance(variants, list) and variants, f"{artifact} missing module variants")
    variant_names = set()
    for variant in variants:
        require(isinstance(variant, dict) and isinstance(variant.get("name"), str) and
                variant["name"] not in variant_names, f"{artifact} invalid/duplicate module variant")
        variant_names.add(variant["name"])
        declared = set()
        for collection in ("dependencies", "dependencyConstraints"):
            entries = variant.get(collection, [])
            require(isinstance(entries, list), f"{artifact} module invalid {collection}")
            seen = set()
            for dependency in entries:
                require(isinstance(dependency, dict) and isinstance(dependency.get("group"), str) and
                        isinstance(dependency.get("module"), str), f"{artifact} malformed module dependency")
                key = (dependency.get("group"), dependency.get("module"))
                require(set(dependency) <= {"group", "module", "version"},
                        f"{artifact} module has unsupported dependency fields")
                require(key in allowed_module, f"{artifact} module unexpected/private dependency {key}")
                require(dependency.get("version") == {"requires": allowed_module[key]},
                        f"{artifact} module dependency version mismatch: {key}")
                require(key not in seen, f"{artifact} module duplicate {collection}: {key}")
                seen.add(key)
                if collection == "dependencies":
                    declared.add(key)
        attributes = variant.get("attributes", {})
        require(isinstance(attributes, dict), f"{artifact} module invalid attributes")
        usage = attributes.get("org.gradle.usage")
        if usage in ("java-api", "java-runtime") and attributes.get("org.gradle.category") != "documentation":
            usages.add(usage)
            require(bool(declared & {(group, "p2p-core"), (group, f"p2p-core-{platform}")}),
                    f"{artifact} {usage} missing core dependency")
            require(bool(declared & {("org.jetbrains.kotlinx", "kotlinx-coroutines-core"),
                                     ("org.jetbrains.kotlinx", "kotlinx-coroutines-core-jvm")}),
                    f"{artifact} {usage} missing coroutines dependency")
            require((("org.slf4j", "slf4j-api") in declared) == (usage == "java-runtime"),
                    f"{artifact} {usage} must keep SLF4J as runtime implementation")
            files = variant.get("files")
            require(isinstance(files, list) and len(files) == 1 and isinstance(files[0], dict),
                    f"{artifact} {usage} must ship one embedded runtime archive")
            suffix = ".jar" if platform == "jvm" else ".aar"
            filename = f"{artifact}-{version}{suffix}"
            names = {filename} if platform == "jvm" else {filename, "p2p-transport-lan.aar"}
            require(files[0].get("name") in names and files[0].get("url") == filename,
                    f"{artifact} {usage} has a local/private/noncanonical runtime archive")
    require(usages == {"java-api", "java-runtime"}, f"{artifact} missing API/runtime module variants")
print("OK: LAN JVM/Android POM and module dependencies describe embedded JmDNS plus SLF4J API")
PY_LAN_METADATA
fi

mkdir -p \
    "$FIXTURE_DIR/lanJvm/src/main/kotlin/consumer" \
    "$FIXTURE_DIR/androidConsumer/src/main/kotlin/consumer"
if [[ "$CONSUMER_PROFILE" == complete ]]; then
mkdir -p \
    "$FIXTURE_DIR/coreJvm/src/main/kotlin/consumer" \
    "$FIXTURE_DIR/coreJvm/src/main/java/consumer" \
    "$FIXTURE_DIR/desktopJvm/src/main/kotlin/consumer" \
    "$FIXTURE_DIR/kmpConsumer/src/commonMain/kotlin/consumer" \
    "$FIXTURE_DIR/kmpConsumer/src/jvmMain/kotlin/consumer" \
    "$FIXTURE_DIR/kmpConsumer/src/androidMain/kotlin/consumer" \
    "$FIXTURE_DIR/kmpConsumer/src/iosMain/kotlin/consumer"
fi

if [[ -z "${ANDROID_HOME:-}" && -z "${ANDROID_SDK_ROOT:-}" ]]; then
    SDK_LINE="$(sed -n '/^sdk\.dir=/p' "$ROOT/local.properties" 2>/dev/null | tail -n 1)"
    [[ -n "$SDK_LINE" ]] || fail "Android SDK is unavailable (set ANDROID_HOME/ANDROID_SDK_ROOT or local.properties sdk.dir)"
    printf '%s\n' "$SDK_LINE" > "$FIXTURE_DIR/local.properties"
fi

cat > "$FIXTURE_DIR/settings.gradle.kts" <<'EOF'
pluginManagement {
    repositories {
        google {
            content {
                includeGroupByRegex("com\\.android.*")
                includeGroupByRegex("com\\.google.*")
                includeGroupByRegex("androidx.*")
            }
        }
        mavenCentral()
        gradlePluginPortal()
    }
}
EOF
cat >> "$FIXTURE_DIR/settings.gradle.kts" <<EOF
val currentSourceConsumer = $CURRENT_SOURCE_CONSUMER == 1
val publishedGroup = "$GROUP"
EOF
cat >> "$FIXTURE_DIR/settings.gradle.kts" <<'EOF'
// Separate repository eligibility, not a fabricated POM dependency graph.
// These configurations must resolve the same published coordinates without
// Gradle-metadata redirection; no project dependency/substitution is available.
val pomOnlyConfigurations = arrayOf(
    "publishedPomRuntimeClasspath",
    "publishedPomDebugRuntimeClasspath",
    "publishedPomCoexistRuntimeClasspath"
)
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        maven {
            name = "publishedGradleMetadata"
            url = uri(providers.gradleProperty("consumerRepo").get())
            if (currentSourceConsumer) {
                content {
                    includeGroup(publishedGroup)
                    notForConfigurations(*pomOnlyConfigurations)
                }
                metadataSources { gradleMetadata() }
            }
        }
        if (currentSourceConsumer) {
            maven {
                name = "publishedPomOnly"
                url = uri(providers.gradleProperty("consumerRepo").get())
                content {
                    includeGroup(publishedGroup)
                    onlyForConfigurations(*pomOnlyConfigurations)
                }
                metadataSources {
                    mavenPom()
                    ignoreGradleMetadataRedirection()
                }
            }
        }
        google { if (currentSourceConsumer) content { excludeGroup(publishedGroup) } }
        mavenCentral { if (currentSourceConsumer) content { excludeGroup(publishedGroup) } }
    }
}
rootProject.name = "p2pkit-published-consumers"
EOF
if [[ "$CONSUMER_PROFILE" == complete ]]; then
    echo 'include(":coreJvm", ":lanJvm", ":desktopJvm", ":androidConsumer", ":kmpConsumer")' \
        >> "$FIXTURE_DIR/settings.gradle.kts"
else
    echo 'include(":lanJvm", ":androidConsumer")' >> "$FIXTURE_DIR/settings.gradle.kts"
fi

cat "$ROOT/scripts/consumer-buildscript.gradle.kts" > "$FIXTURE_DIR/build.gradle.kts"
cp "$ROOT/buildscript-gradle.lockfile" "$FIXTURE_DIR/consumer-plugin-versions.lock"
cat >> "$FIXTURE_DIR/build.gradle.kts" <<EOF
plugins {
    kotlin("jvm") version "$KOTLIN_VERSION" apply false
    kotlin("multiplatform") version "$KOTLIN_VERSION" apply false
    id("com.android.application") version "$AGP_VERSION" apply false
    id("com.android.kotlin.multiplatform.library") version "$AGP_VERSION" apply false
}
EOF

if [[ "$CONSUMER_PROFILE" == complete ]]; then
cat > "$FIXTURE_DIR/coreJvm/build.gradle.kts" <<EOF
plugins { kotlin("jvm") }
kotlin { jvmToolchain(17) }
dependencies { implementation("$GROUP:p2p-core-jvm:$VERSION") }
EOF
cat > "$FIXTURE_DIR/coreJvm/src/main/kotlin/consumer/CoreConsumer.kt" <<'EOF'
package consumer

import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.P2pState
import dev.p2pkit.core.FeatureState
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.FileTransferFailureKind
import dev.p2pkit.core.FileTransferPhase
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.Retryability
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.provisioning.JoinNetworkResult
import dev.p2pkit.core.provisioning.LocalNetworkConfig
import dev.p2pkit.core.provisioning.LocalNetworkResult
import dev.p2pkit.core.provisioning.ManualConnectionInfo
import dev.p2pkit.core.provisioning.NetworkProvisioningEvent
import dev.p2pkit.core.provisioning.NetworkProvisioningManager
import dev.p2pkit.core.provisioning.NetworkProvisioningState
import dev.p2pkit.core.provisioning.NetworkState
import dev.p2pkit.core.provisioning.WifiCredentials
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportDescriptor
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.core.transfer.FileTransferDestination
import dev.p2pkit.core.transfer.PreparedFileSource
import dev.p2pkit.core.transfer.Sha256Digest
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.io.RawSink
import kotlinx.io.RawSource
import kotlinx.io.Buffer

fun coreState(kit: P2pKit, sink: RawSink): StateFlow<P2pState> {
    sink.flush()
    return kit.state
}

fun featureStates(kit: P2pKit): Pair<StateFlow<FeatureState>, StateFlow<FeatureState>> =
    kit.advertisingState to kit.discoveryState

fun pendingOffers(session: P2pSession): StateFlow<List<P2pFileOffer>> =
    session.pendingFileOffers

fun classifyTransferFailure(error: P2pError.FileTransferFailed): String =
    "${error.kind}:${error.phase}:${error.retryability}:${error.transferId}:${error.reason}"

fun constructTransferFailure(): P2pError.FileTransferFailed =
    P2pError.FileTransferFailed(
        kind = FileTransferFailureKind.STORAGE,
        phase = FileTransferPhase.DURABLE_COMMIT,
        retryability = Retryability.RETRY_AFTER_USER_ACTION,
        transferId = "0123456789abcdef0123456789abcdef",
        reason = "fixture"
    )

class ExternalPreparedFileSource(private val content: ByteArray) : PreparedFileSource {
    override val sizeBytes: Long = content.size.toLong()
    override val sha256: Sha256Digest = Sha256Digest(ByteArray(32))
    override fun open(): RawSource = Buffer().apply { write(content) }
}

class ExternalFileDestination : FileTransferDestination {
    override fun openSink(): RawSink = Buffer()
    override suspend fun commit() = Unit
    override suspend fun abort(cause: P2pError.FileTransferFailed?) = Unit
}

suspend fun secureTransferSurface(
    session: P2pSession,
    offer: P2pFileOffer,
    source: PreparedFileSource,
    destination: FileTransferDestination
) {
    session.sendFile("fixture.bin", "application/octet-stream", source)
    offer.accept(destination)
    P2pError.UnsupportedFeature("fixture-feature").feature
}

fun copyPeer(peer: Peer): Peer {
    val (id, name, platform, transports) = peer
    return peer.copy(id, name, platform, transports)
}

class ExternalDataTransport : DataTransport {
    override val type: TransportKind = TransportKind.LAN
    override val priority: Int = 1
    override suspend fun stop() = Unit
    override fun canConnect(peer: InternalPeer): Boolean = false
    override suspend fun connect(peer: InternalPeer): RawConnection = error("not supported")
    override fun incomingConnections(): Flow<RawConnection> = emptyFlow()
    override suspend fun close() = Unit
}

class ExternalTransportFactory : TransportFactory {
    override val descriptor: TransportDescriptor =
        TransportDescriptor.dataOnly(TransportKind.LAN)

    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = ExternalDataTransport())
}

@OptIn(ExperimentalP2pApi::class)
class ExternalProvisioningManager : NetworkProvisioningManager {
    override val state: StateFlow<NetworkProvisioningState> =
        MutableStateFlow(NetworkProvisioningState.Idle)
    override val networkState: StateFlow<NetworkState> = MutableStateFlow(NetworkState.Unknown)
    override val events: Flow<NetworkProvisioningEvent> = emptyFlow()

    override suspend fun startLocalNetwork(config: LocalNetworkConfig): LocalNetworkResult =
        LocalNetworkResult.Unsupported("external fixture")
    override suspend fun stopLocalNetwork() = Unit
    override suspend fun joinLocalNetwork(credentials: WifiCredentials): JoinNetworkResult =
        JoinNetworkResult.Unsupported("external fixture")
    override suspend fun getManualConnectionInfo(): ManualConnectionInfo? = null

    @Deprecated("legacy fixture overload")
    override suspend fun createManualPeer(host: String, port: Int): Peer = error("not supported")

    override suspend fun createManualPeer(
        host: String,
        port: Int,
        expectedFingerprint: PeerFingerprint
    ): Peer = error("not supported")

    override suspend fun close() = Unit
}
EOF
cat > "$FIXTURE_DIR/coreJvm/src/main/java/consumer/ImmutableModelJavaConsumer.java" <<'EOF'
package consumer;

import dev.p2pkit.core.P2pMessage;
import dev.p2pkit.core.P2pError;
import dev.p2pkit.core.FileTransferFailureKind;
import dev.p2pkit.core.FileTransferPhase;
import dev.p2pkit.core.Retryability;
import dev.p2pkit.core.TransportKind;
import dev.p2pkit.core.provisioning.NetworkState;
import dev.p2pkit.core.transport.TransportCapability;
import dev.p2pkit.core.transport.TransportDescriptor;
import dev.p2pkit.core.transport.TransportPair;
import dev.p2pkit.core.transport.TransportHint;
import dev.p2pkit.core.transfer.Sha256Digest;
import dev.p2pkit.core.transfer.PreparedFileSource;
import dev.p2pkit.core.transfer.FileTransferDestination;
import java.util.List;
import java.util.Map;

final class ImmutableModelJavaConsumer {
    static void compilePublicSurface() {
        P2pMessage.Text text = new P2pMessage.Text("hello", Map.of("key", "value"));
        P2pMessage.Text copied = text.copy(text.getValue(), text.getMetadata());
        TransportHint hint = new TransportHint(
            TransportKind.LAN,
            "192.0.2.1",
            4242,
            Map.of("scope", "lan")
        );
        NetworkState.ConnectedToEthernet ethernet =
            new NetworkState.ConnectedToEthernet(List.of("192.0.2.10"));
        TransportDescriptor descriptor =
            TransportDescriptor.Companion.dataOnly(TransportKind.LAN);
        TransportPair pair = new TransportPair(new ExternalDataTransport(), null);
        copied.getMetadata();
        hint.getMetadata();
        ethernet.getLocalIpAddresses();
        descriptor.getCapabilities().contains(TransportCapability.DATA);
        pair.getData();
        P2pError.FileTransferFailed failure = new P2pError.FileTransferFailed(
            FileTransferFailureKind.STORAGE,
            FileTransferPhase.FLUSH,
            Retryability.RETRY_AFTER_USER_ACTION,
            "0123456789abcdef0123456789abcdef",
            "fixture"
        );
        failure.getKind();
        failure.getPhase();
        failure.getRetryability();
        failure.getTransferId();
        Sha256Digest digest = new Sha256Digest(new byte[32]);
        digest.getBytes();
        Class<PreparedFileSource> preparedType = PreparedFileSource.class;
        Class<FileTransferDestination> destinationType = FileTransferDestination.class;
        preparedType.getName();
        destinationType.getName();
        new P2pError.UnsupportedFeature("fixture-feature").getFeature();
    }
}
EOF
fi

cat > "$FIXTURE_DIR/lanJvm/build.gradle.kts" <<EOF
import java.time.Duration
import org.gradle.jvm.toolchain.JavaLanguageVersion

plugins { kotlin("jvm") }
kotlin { jvmToolchain(17) }
dependencies { implementation("$GROUP:p2p-transport-lan-jvm:$VERSION") }
EOF
cat > "$FIXTURE_DIR/lanJvm/src/main/kotlin/consumer/LanConsumer.kt" <<'EOF'
package consumer

import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pState
import dev.p2pkit.transport.lan.JvmLanDiag
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow

fun lanEvents(): SharedFlow<String> = JvmLanDiag.events
fun lanCoreState(kit: P2pKit): StateFlow<P2pState> = kit.state
EOF

if [[ "$CURRENT_SOURCE_CONSUMER" == 1 ]]; then
cat >> "$FIXTURE_DIR/lanJvm/build.gradle.kts" <<'EOF'

val upstreamJmdns by configurations.creating {
    isCanBeConsumed = false
    isCanBeResolved = true
}
dependencies { add(upstreamJmdns.name, "org.jmdns:jmdns:3.6.3") }
val publishedPomRuntimeClasspath by configurations.creating {
    isCanBeConsumed = false
    isCanBeResolved = true
    extendsFrom(configurations.getByName("implementation"), configurations.getByName("runtimeOnly"))
}
val ordinaryRuntime = configurations.getByName("runtimeClasspath")
for (attribute in ordinaryRuntime.attributes.keySet()) {
    @Suppress("UNCHECKED_CAST")
    val key = attribute as org.gradle.api.attributes.Attribute<Any>
    publishedPomRuntimeClasspath.attributes.attribute(key, requireNotNull(ordinaryRuntime.attributes.getAttribute(key)))
    upstreamJmdns.attributes.attribute(key, requireNotNull(ordinaryRuntime.attributes.getAttribute(key)))
}

fun requirePlainRuntime(configuration: org.gradle.api.artifacts.Configuration) {
    val modules = configuration.resolvedConfiguration.resolvedArtifacts.map { it.moduleVersion.id }
    check(modules.none { it.group == "org.jmdns" }) { "Plain LAN consumer unexpectedly resolves upstream JmDNS" }
    check(modules.single { it.group == "org.slf4j" && it.name == "slf4j-api" }.version == "2.0.7")
    check(modules.none { it.group == "org.slf4j" && it.name != "slf4j-api" }) { "Unexpected SLF4J provider" }
}

fun embeddedSmoke(
    name: String,
    pomOnly: Boolean = false,
    coexist: Boolean = false,
    upstreamFirst: Boolean = false
) =
    tasks.register<JavaExec>(name) {
        dependsOn(tasks.named("classes"))
        val runtime = if (pomOnly) publishedPomRuntimeClasspath else ordinaryRuntime
        val consumer = files(sourceSets.main.get().output, runtime)
        classpath = when {
            !coexist -> consumer
            upstreamFirst -> files(upstreamJmdns, consumer)
            else -> files(consumer, upstreamJmdns)
        }
        mainClass.set("consumer.EmbeddedJmdnsSmokeKt")
        javaLauncher.set(javaToolchains.launcherFor { languageVersion.set(JavaLanguageVersion.of(17)) })
        maxHeapSize = "256m"
        jvmArgs("--add-opens=java.base/java.util=ALL-UNNAMED", "-XX:ActiveProcessorCount=2")
        args(if (coexist) "coexist" else "plain", if (pomOnly) "pom" else "module")
        timeout.set(Duration.ofMinutes(2))
        doFirst {
            requirePlainRuntime(runtime)
            if (coexist) {
                val modules = upstreamJmdns.resolvedConfiguration.resolvedArtifacts.map { it.moduleVersion.id }
                check(modules.single { it.group == "org.jmdns" && it.name == "jmdns" }.version == "3.6.3")
            }
        }
    }
val plainSmoke = embeddedSmoke("runEmbeddedJmdnsSmoke")
val coexistSmoke = embeddedSmoke("runEmbeddedJmdnsCoexistenceSmoke", coexist = true)
val upstreamFirstSmoke = embeddedSmoke(
    "runEmbeddedJmdnsCoexistenceUpstreamFirstSmoke", coexist = true, upstreamFirst = true
)
val pomSmoke = embeddedSmoke("runEmbeddedJmdnsPomSmoke", pomOnly = true)
coexistSmoke.configure { mustRunAfter(plainSmoke) }
upstreamFirstSmoke.configure { mustRunAfter(coexistSmoke) }
pomSmoke.configure { mustRunAfter(upstreamFirstSmoke) }
EOF
cat > "$FIXTURE_DIR/lanJvm/src/main/kotlin/consumer/EmbeddedJmdnsSmoke.kt" <<'EOF'
package consumer

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.dsl.jvmSecureIdentityStore
import dev.p2pkit.core.security.JvmSecureIdentityStore
import dev.p2pkit.transport.lan.JvmLanDiag
import dev.p2pkit.transport.lan.internal.jmdns.JmDNS
import dev.p2pkit.transport.lan.internal.jmdns.impl.DNSTaskStarter
import dev.p2pkit.transport.lan.internal.jmdns.impl.JmDNSImpl
import dev.p2pkit.transport.lan.lan
import java.net.MulticastSocket
import java.util.Properties
import java.util.Timer
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.ExecutorService
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout

// Consumer-only memory storage: synthetic, fresh-process identity; not a
// production durable-store example. No credentials or peer identifiers are logged.
private class EphemeralIdentityStore : JvmSecureIdentityStore {
    private val values = ConcurrentHashMap<String, ByteArray>()

    override fun read(namespace: String): ByteArray? = values[namespace]?.clone()

    override fun putIfAbsent(namespace: String, value: ByteArray): ByteArray =
        (values.putIfAbsent(namespace, value.clone()) ?: value).clone()

    override fun delete(namespace: String): Boolean = values.remove(namespace)?.let {
        it.fill(0)
        true
    } ?: false

    fun clear() {
        values.values.forEach { it.fill(0) }
        values.clear()
    }
}

private fun field(owner: Any, name: String): Any =
    owner.javaClass.getDeclaredField(name).apply { isAccessible = true }.get(owner)

@Suppress("UNCHECKED_CAST")
private fun installedStarters(factory: Any): Map<Any, Any> = field(factory, "_instances") as Map<Any, Any>

private fun timerThread(starter: Any, name: String): Thread {
    val timer = field(starter, name) as Timer
    return Timer::class.java.getDeclaredField("thread").apply { isAccessible = true }.get(timer) as Thread
}

private data class NativeOwner(
    val dns: JmDNSImpl,
    val socket: MulticastSocket,
    val timer: Thread,
    val stateTimer: Thread,
    val executor: ExecutorService
) {
    fun requireDisposed(factory: Any) {
        // Passive joins of the exact original resources. Never allocate a
        // starter after close, cancel timers, daemonize, force GC, or exit().
        timer.join(5_000)
        stateTimer.join(5_000)
        check(!timer.isAlive && !stateTimer.isAlive) { "Production close retained an original JmDNS timer" }
        check(socket.isClosed && dns.socket == null) { "Production close retained its multicast socket" }
        check(executor.isShutdown && executor.awaitTermination(5, TimeUnit.SECONDS))
        check(dns !in installedStarters(factory)) { "Production close retained its factory entry" }
    }
}

private fun captureOwners(factory: Any): List<NativeOwner> = installedStarters(factory).map { (key, starter) ->
    val dns = key as JmDNSImpl
    val timer = timerThread(starter, "_timer")
    val stateTimer = timerThread(starter, "_stateTimer")
    check(timer.isAlive && stateTimer.isAlive && !stateTimer.isDaemon)
    NativeOwner(dns, checkNotNull(dns.socket), timer, stateTimer, field(dns, "_executor") as ExecutorService)
}

private fun requirePackaging(coexist: Boolean): Any? {
    val loader = JmDNS::class.java.classLoader
    val resource = "dev/p2pkit/transport/lan/internal/jmdns/version.properties"
    check(loader.getResources(resource).toList().size == 1) { "Missing/duplicate private version resource" }
    val properties = Properties().apply { checkNotNull(loader.getResourceAsStream(resource)).use { load(it) } }
    check(properties.getProperty("jmdns.version") == "3.6.3-p2pkit.410.5")
    check(properties.getProperty("jmdns.upstream.version") == "3.6.3")
    check(JmDNS.VERSION == properties.getProperty("jmdns.version"))
    val privateJar = JmDNS::class.java.protectionDomain.codeSource.location
    check(privateJar == JvmLanDiag::class.java.protectionDomain.codeSource.location) {
        "Private JmDNS must be embedded in the published LAN JAR, not an unpublished helper"
    }
    check(!loader.getResources("META-INF/services/org.slf4j.spi.SLF4JServiceProvider").hasMoreElements())
    check(!loader.getResources("org/slf4j/impl/StaticLoggerBinder.class").hasMoreElements())
    check(DNSTaskStarter.Factory.classDelegate() == null)
    val upstreamClasses = loader.getResources("javax/jmdns/JmDNS.class").toList()
    if (!coexist) {
        check(upstreamClasses.isEmpty()) { "Plain consumer contains unrelocated upstream JmDNS" }
        return null
    }
    check(upstreamClasses.size == 1)
    val upstream = Class.forName("javax.jmdns.JmDNS")
    check(upstream != JmDNS::class.java && upstream.getField("VERSION").get(null) == "3.6.3")
    check(upstream.protectionDomain.codeSource.location != privateJar)
    val upstreamProperties = Properties().apply {
        checkNotNull(upstream.getResourceAsStream("/version.properties")).use { load(it) }
    }
    check(upstreamProperties.getProperty("jmdns.version") == "3.6.3")
    val factoryType = Class.forName("javax.jmdns.impl.DNSTaskStarter\$Factory")
    check(factoryType.getMethod("classDelegate").invoke(null) == null)
    val factory = factoryType.getMethod("getInstance").invoke(null)
    check(factory !== DNSTaskStarter.Factory.getInstance() && installedStarters(factory).isEmpty())
    check(!Class.forName("javax.jmdns.ServiceInfo").isAssignableFrom(
        dev.p2pkit.transport.lan.internal.jmdns.ServiceInfo::class.java
    ))
    return factory
}

fun main(arguments: Array<String>) = runBlocking {
    require(
        arguments.size == 2 && arguments[0] in setOf("plain", "coexist") && arguments[1] in setOf("module", "pom")
    )
    val upstreamFactory = requirePackaging(arguments[0] == "coexist")
    val factory = DNSTaskStarter.Factory.getInstance()
    check(installedStarters(factory).isEmpty())
    val stores = listOf(EphemeralIdentityStore(), EphemeralIdentityStore())
    val kits = mutableListOf<P2pKit>()
    var owners = emptyList<NativeOwner>()
    var failure: Throwable? = null
    fun recordFailure(error: Throwable) {
        val original = failure
        if (original == null) failure = error else if (original !== error) original.addSuppressed(error)
    }
    try {
        val app = AppId("p2pkit.consumer.${UUID.randomUUID()}")
        stores.forEachIndexed { index, store ->
            kits += P2pKit.create {
                appId = app
                deviceName = "Published consumer $index"
                jvmSecureIdentityStore(store)
                transports { lan() }
            }
        }
        // Public production callers, no discovery test backend, native factory
        // replacement, transport injection, fabricated callback, or timer fault.
        // This requires an up multicast-capable LAN interface and sends mDNS.
        withTimeout(30_000) {
            kits.forEach {
                it.startAdvertising()
                it.startDiscovery()
            }
            owners = captureOwners(factory)
            check(owners.size == kits.size)
            for (kit in kits) {
                val info = owners.flatMap { it.dns.services.values }
                    .single { it.getPropertyString("pid") == kit.localPeerId.value }
                check(info.type == "_p2pkit2._tcp.local." && info.port in 1..65_535)
                check(info.getPropertyString("app") == app.value)
                check(info.getPropertyString("name") == kit.localDeviceName)
                check(info.getPropertyString("pv") == "2")
                check(info.getPropertyString("caps").split(',').contains("LAN"))
                check(info.getPropertyString("fp") == checkNotNull(kit.localFingerprint).value)
                val other = kits.single { it !== kit }
                val observed = kit.peers.first { peers -> peers.any { it.id == other.localPeerId } }
                    .single { it.id == other.localPeerId }
                check(observed.name == other.localDeviceName && TransportKind.LAN in observed.supportedTransports)
            }
        }
        if (upstreamFactory != null) check(installedStarters(upstreamFactory).isEmpty())
    } catch (error: Throwable) {
        recordFailure(error)
    } finally {
        withContext(NonCancellable) {
            kits.asReversed().forEach { kit ->
                try {
                    withTimeout(30_000) { kit.stop() }
                } catch (error: Throwable) {
                    recordFailure(error)
                }
            }
        }
        owners.forEach { owner ->
            try {
                owner.requireDisposed(factory)
            } catch (error: Throwable) {
                recordFailure(error)
            }
        }
        stores.forEach { it.clear() }
    }
    failure?.let { throw it }
    check(installedStarters(factory).isEmpty())
    println(
        "PASS: published LAN native creation, service/TXT callbacks and normal disposal (${arguments.joinToString()})"
    )
    // Natural JavaExec completion is required. This is normal-close packaging
    // smoke, not the separate #410 failed-recovery regression or API24 runtime.
}
EOF
fi

if [[ "$CONSUMER_PROFILE" == complete ]]; then
cat > "$FIXTURE_DIR/desktopJvm/build.gradle.kts" <<EOF
plugins { kotlin("jvm") }
kotlin { jvmToolchain(17) }
dependencies { implementation("$GROUP:p2p-network-provisioning-desktop:$VERSION") }
EOF
cat > "$FIXTURE_DIR/desktopJvm/src/main/kotlin/consumer/DesktopConsumer.kt" <<'EOF'
package consumer

import dev.p2pkit.core.provisioning.NetworkProvisioningManager
import dev.p2pkit.core.provisioning.NetworkProvisioningState
import dev.p2pkit.core.provisioning.ProvisioningContext
import dev.p2pkit.provisioning.desktop.JvmNetworkProvisioningManager
import kotlinx.coroutines.flow.StateFlow

fun desktopManager(context: ProvisioningContext): NetworkProvisioningManager =
    JvmNetworkProvisioningManager(context)

fun desktopState(manager: NetworkProvisioningManager): StateFlow<NetworkProvisioningState> =
    manager.state
EOF
fi

cat > "$FIXTURE_DIR/androidConsumer/build.gradle.kts" <<EOF
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.Properties
import java.util.zip.ZipFile

plugins { id("com.android.application") }
android {
    namespace = "consumer.p2pkit.android"
    compileSdk = 36
    defaultConfig {
        applicationId = "consumer.p2pkit.android"
        minSdk = 24
    }
}
dependencies { implementation("$GROUP:p2p-transport-lan-android:$VERSION") }
EOF
if [[ "$CONSUMER_PROFILE" == complete ]]; then
    echo "dependencies { implementation(\"$GROUP:p2p-network-provisioning-android-android:$VERSION\") }" \
        >> "$FIXTURE_DIR/androidConsumer/build.gradle.kts"
fi
cat > "$FIXTURE_DIR/androidConsumer/src/main/AndroidManifest.xml" <<'EOF'
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <application />
</manifest>
EOF
if [[ "$CONSUMER_PROFILE" == complete ]]; then
cat > "$FIXTURE_DIR/androidConsumer/src/main/kotlin/consumer/AndroidConsumer.kt" <<'EOF'
package consumer

import android.content.Context
import dev.p2pkit.core.dsl.NetworkProvisioningConfigBuilder
import dev.p2pkit.core.provisioning.NetworkProvisioningManager
import dev.p2pkit.core.provisioning.NetworkProvisioningState
import dev.p2pkit.provisioning.android.android
import kotlinx.coroutines.flow.StateFlow

fun configureAndroidProvisioning(builder: NetworkProvisioningConfigBuilder, context: Context) {
    builder.android(context)
}

fun androidState(manager: NetworkProvisioningManager): StateFlow<NetworkProvisioningState> =
    manager.state
EOF
fi

if [[ "$CURRENT_SOURCE_CONSUMER" == 1 ]]; then
cat >> "$FIXTURE_DIR/androidConsumer/build.gradle.kts" <<'EOF'

android {
    buildFeatures { buildConfig = true }
    defaultConfig {
        targetSdk = 36
        buildConfigField("boolean", "UPSTREAM_JMDNS", "false")
    }
    buildTypes {
        val debugType = getByName("debug")
        val releaseType = getByName("release") {
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "consumer-rules.pro")
        }
        create("coexistDebug") {
            initWith(debugType)
            matchingFallbacks += "debug"
            buildConfigField("boolean", "UPSTREAM_JMDNS", "true")
        }
        create("coexistRelease") {
            initWith(releaseType)
            matchingFallbacks += "release"
            buildConfigField("boolean", "UPSTREAM_JMDNS", "true")
            proguardFiles("upstream-consumer-rules.pro")
        }
    }
}
dependencies {
    add("coexistDebugImplementation", "org.jmdns:jmdns:3.6.3")
    add("coexistReleaseImplementation", "org.jmdns:jmdns:3.6.3")
}

val publishedPomDebugRuntimeClasspath by configurations.creating {
    isCanBeConsumed = false
    isCanBeResolved = true
    extendsFrom(configurations.getByName("implementation"), configurations.getByName("runtimeOnly"))
}
val publishedPomCoexistRuntimeClasspath by configurations.creating {
    isCanBeConsumed = false
    isCanBeResolved = true
    extendsFrom(
        configurations.getByName("implementation"), configurations.getByName("runtimeOnly"),
        configurations.getByName("coexistDebugImplementation"), configurations.getByName("coexistDebugRuntimeOnly")
    )
}
afterEvaluate {
    for ((target, sourceName) in listOf(
        publishedPomDebugRuntimeClasspath to "debugRuntimeClasspath",
        publishedPomCoexistRuntimeClasspath to "coexistDebugRuntimeClasspath"
    )) {
        val source = configurations.getByName(sourceName)
        for (attribute in source.attributes.keySet()) {
            @Suppress("UNCHECKED_CAST")
            val key = attribute as org.gradle.api.attributes.Attribute<Any>
            target.attributes.attribute(key, requireNotNull(source.attributes.getAttribute(key)))
        }
    }
}

// Inspect actual class definitions, not a descriptor string that might remain
// solely because a reflective probe mentioned a class R8 removed.
fun dexDefinitions(bytes: ByteArray): List<String> {
    check(bytes.size >= 112 && bytes.copyOfRange(0, 4).contentEquals(byteArrayOf(100, 101, 120, 10)))
    val data = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
    fun uint(offset: Int): Int {
        check(offset >= 0 && offset <= bytes.size - 4)
        return data.getInt(offset).also { check(it >= 0) }
    }
    val stringsCount = uint(56)
    val stringsOffset = uint(60)
    val typesCount = uint(64)
    val typesOffset = uint(68)
    val classesCount = uint(96)
    val classesOffset = uint(100)
    check(classesCount <= bytes.size / 32 && classesOffset <= bytes.size - classesCount * 32)
    return (0 until classesCount).map { index ->
        val type = uint(classesOffset + index * 32)
        check(type < typesCount && typesCount <= bytes.size / 4)
        val stringIndex = uint(typesOffset + type * 4)
        check(stringIndex < stringsCount && stringsCount <= bytes.size / 4)
        var cursor = uint(stringsOffset + stringIndex * 4)
        var lengthBytes = 0
        do {
            check(cursor in bytes.indices && lengthBytes++ < 5)
            val next = bytes[cursor++].toInt() and 0xff
        } while (next and 0x80 != 0)
        val start = cursor
        while (cursor in bytes.indices && bytes[cursor] != 0.toByte()) cursor++
        check(cursor < bytes.size)
        String(bytes, start, cursor - start, Charsets.UTF_8)
    }
}

tasks.register("verifyEmbeddedJmdnsPackaging") {
    dependsOn("assembleDebug", "assembleRelease", "assembleCoexistDebug", "assembleCoexistRelease")
    doLast {
        for ((configuration, coexist) in listOf(
            publishedPomDebugRuntimeClasspath to false,
            publishedPomCoexistRuntimeClasspath to true
        )) {
            val modules = configuration.resolvedConfiguration.resolvedArtifacts.map { it.moduleVersion.id }
            val upstream = modules.filter { it.group == "org.jmdns" }
            check(
                if (coexist) upstream.single().let { it.name == "jmdns" && it.version == "3.6.3" }
                else upstream.isEmpty()
            )
            check(modules.single { it.group == "org.slf4j" && it.name == "slf4j-api" }.version == "2.0.7")
            check(modules.none { it.group == "org.slf4j" && it.name != "slf4j-api" })
        }
        for ((variant, suffix) in listOf(
            "debug" to "debug", "release" to "release-unsigned",
            "coexistDebug" to "coexistDebug", "coexistRelease" to "coexistRelease-unsigned"
        )) {
            val coexist = variant.startsWith("coexist")
            val apk = file("build/outputs/apk/$variant/androidConsumer-$suffix.apk")
            check(apk.isFile) { "Missing D8/R8 consumer APK: $variant" }
            ZipFile(apk).use { zip ->
                val entries = zip.entries().toList()
                check(entries.map { it.name }.distinct().size == entries.size) { "Duplicate APK ZIP entries" }
                val privateVersion = "dev/p2pkit/transport/lan/internal/jmdns/version.properties"
                val properties = Properties().apply {
                    zip.getInputStream(checkNotNull(zip.getEntry(privateVersion))).use { load(it) }
                }
                check(properties.getProperty("jmdns.version") == "3.6.3-p2pkit.410.5")
                check(properties.getProperty("jmdns.upstream.version") == "3.6.3")
                check(zip.getEntry("META-INF/services/org.slf4j.spi.SLF4JServiceProvider") == null)
                val definitionNames = entries.filter { it.name.matches(Regex("classes[0-9]*\\.dex")) }
                    .flatMap { entry -> zip.getInputStream(entry).use { dexDefinitions(it.readBytes()) } }
                check(definitionNames.distinct().size == definitionNames.size) { "Duplicate APK class definitions" }
                val definitions = definitionNames.toSet()
                check("Lconsumer/EmbeddedLanActivity;" in definitions)
                check("Ldev/p2pkit/transport/lan/internal/jmdns/JmDNS;" in definitions)
                check("Ldev/p2pkit/transport/lan/internal/jmdns/impl/JmDNSImpl;" in definitions)
                check("Lorg/slf4j/impl/StaticLoggerBinder;" !in definitions)
                if (coexist) {
                    check("Ljavax/jmdns/JmDNS;" in definitions)
                    val upstream = Properties().apply {
                        zip.getInputStream(checkNotNull(zip.getEntry("version.properties"))).use { load(it) }
                    }
                    check(upstream.getProperty("jmdns.version") == "3.6.3")
                } else {
                    check(definitions.none { it.startsWith("Ljavax/jmdns/") })
                }
            }
            if (variant == "release" || variant == "coexistRelease") {
                check(file("build/outputs/mapping/$variant/mapping.txt").isFile) { "Missing R8 mapping: $variant" }
            }
        }
        val report = file("build/reports/embedded-jmdns/packaging.txt")
        check(report.parentFile.isDirectory || report.parentFile.mkdirs())
        report.writeText("PASS: embedded JmDNS Android D8/R8 plain+coexistence; POM-only runtime graphs\n")
    }
}
EOF
cat > "$FIXTURE_DIR/androidConsumer/consumer-rules.pro" <<'EOF'
# Fixture entry point and two inspected type names only. The production LAN
# calls remain reachable from the manifest Activity; no blanket vendor keep,
# missing-class suppression, resource exclusion, or disabled optimization.
-keep,allowoptimization class consumer.EmbeddedLanActivity { public <init>(); void onCreate(android.os.Bundle); }
-keep,allowoptimization class dev.p2pkit.transport.lan.internal.jmdns.JmDNS { public static java.lang.String VERSION; }
-keep,allowoptimization class dev.p2pkit.transport.lan.internal.jmdns.impl.JmDNSImpl { }
EOF
cat > "$FIXTURE_DIR/androidConsumer/upstream-consumer-rules.pro" <<'EOF'
# Reflective version coexistence probe, not an embedded production dependency.
-keep,allowoptimization class javax.jmdns.JmDNS { public static java.lang.String VERSION; }
EOF
cat > "$FIXTURE_DIR/androidConsumer/src/main/AndroidManifest.xml" <<'EOF'
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <application android:theme="@android:style/Theme.Material.Light.NoActionBar">
        <activity android:name="consumer.EmbeddedLanActivity" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
EOF
cat > "$FIXTURE_DIR/androidConsumer/src/main/kotlin/consumer/EmbeddedLanActivity.kt" <<'EOF'
package consumer

import android.app.Activity
import android.os.Bundle
import android.util.Log
import consumer.p2pkit.android.BuildConfig
import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.android.P2pKitAndroid
import dev.p2pkit.transport.lan.internal.jmdns.JmDNS
import dev.p2pkit.transport.lan.internal.jmdns.ServiceInfo
import dev.p2pkit.transport.lan.lan
import java.util.Properties
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout

// Assembly retains this actual entry point; assembly is NOT API24 execution.
// A separately authorized device run must observe its success and cleanup.
class EmbeddedLanActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Thread({ runSmoke() }, "published-lan-consumer").start()
    }

    private fun runSmoke() = runBlocking {
        val loader = JmDNS::class.java.classLoader
        val path = "dev/p2pkit/transport/lan/internal/jmdns/version.properties"
        val properties = Properties().apply { checkNotNull(loader.getResourceAsStream(path)).use { load(it) } }
        check(properties.getProperty("jmdns.version") == "3.6.3-p2pkit.410.5")
        check(properties.getProperty("jmdns.upstream.version") == "3.6.3")
        check(JmDNS.VERSION == "3.6.3-p2pkit.410.5")
        val service = ServiceInfo.create(
            "_p2pkit2._tcp.local.", "consumer", 4242, 0, 0, mapOf("fixture" to "android")
        )
        check(service.getPropertyString("fixture") == "android")
        if (BuildConfig.UPSTREAM_JMDNS) {
            val upstream = Class.forName("javax.jmdns.JmDNS")
            check(upstream != JmDNS::class.java && upstream.getField("VERSION").get(null) == "3.6.3")
        }
        P2pKitAndroid.initialize(applicationContext)
        val kit = P2pKit.create {
            appId = AppId("p2pkit.published.android.${BuildConfig.BUILD_TYPE}")
            deviceName = "Published Android consumer"
            transports { lan(applicationContext) }
        }
        try {
            withTimeout(30_000) {
                kit.startAdvertising()
                kit.startDiscovery()
            }
        } finally {
            withContext(NonCancellable) { withTimeout(30_000) { kit.stop() } }
        }
        Log.i("PublishedLanConsumer", "PASS: private version and production LAN start/stop")
    }
}
EOF
fi

if [[ "$CONSUMER_PROFILE" == complete ]]; then
cat > "$FIXTURE_DIR/kmpConsumer/build.gradle.kts" <<EOF
plugins {
    kotlin("multiplatform")
    id("com.android.kotlin.multiplatform.library")
}

kotlin {
    jvm()
    android {
        namespace = "consumer.p2pkit.kmp"
        compileSdk = 36
        minSdk = 24
    }
    iosSimulatorArm64 {
        binaries.framework {
            baseName = "P2pKitConsumer"
            freeCompilerArgs +=
                "-Xoverride-konan-properties=minVersion.ios=$IOS_MIN_VERSION"
        }
    }

    sourceSets {
        commonMain.dependencies {
            implementation("$GROUP:p2p-transport-lan:$VERSION")
        }
    }
}
EOF
cat > "$FIXTURE_DIR/kmpConsumer/src/commonMain/kotlin/consumer/CommonConsumer.kt" <<'EOF'
package consumer

import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pState
import dev.p2pkit.core.FeatureState
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.FileTransferFailureKind
import dev.p2pkit.core.FileTransferPhase
import dev.p2pkit.core.Retryability
import dev.p2pkit.core.transfer.FileTransferDestination
import dev.p2pkit.core.transfer.PreparedFileSource
import dev.p2pkit.core.transfer.Sha256Digest
import dev.p2pkit.core.provisioning.NetworkState
import kotlinx.coroutines.flow.StateFlow
import kotlinx.io.RawSink
import kotlinx.io.RawSource
import kotlinx.io.Buffer

fun commonState(kit: P2pKit, sink: RawSink): StateFlow<P2pState> {
    sink.flush()
    return kit.state
}

fun commonFeatureState(kit: P2pKit): StateFlow<FeatureState> = kit.discoveryState

fun commonTransferFailure(): P2pError.FileTransferFailed =
    P2pError.FileTransferFailed(
        FileTransferFailureKind.TIMEOUT,
        FileTransferPhase.OFFER,
        Retryability.RETRY_SAME_SESSION,
        null,
        "fixture"
    )

class CommonPreparedSource(private val content: ByteArray) : PreparedFileSource {
    override val sizeBytes: Long = content.size.toLong()
    override val sha256: Sha256Digest = Sha256Digest(ByteArray(32))
    override fun open(): RawSource = Buffer().apply { write(content) }
}

class CommonDestination : FileTransferDestination {
    override fun openSink(): RawSink = Buffer()
    override suspend fun commit() = Unit
    override suspend fun abort(cause: P2pError.FileTransferFailed?) = Unit
}

fun immutableValues(): Pair<P2pMessage.Text, NetworkState.ConnectedToEthernet> =
    P2pMessage.Text("hello", mapOf("key" to "value")) to
        NetworkState.ConnectedToEthernet(listOf("192.0.2.10"))
EOF
cat > "$FIXTURE_DIR/kmpConsumer/src/jvmMain/kotlin/consumer/JvmConsumer.kt" <<'EOF'
package consumer

import dev.p2pkit.transport.lan.JvmLanDiag
import kotlinx.coroutines.flow.SharedFlow

fun jvmEvents(): SharedFlow<String> = JvmLanDiag.events
EOF
cat > "$FIXTURE_DIR/kmpConsumer/src/androidMain/kotlin/consumer/AndroidConsumer.kt" <<'EOF'
package consumer

import android.content.Context
import dev.p2pkit.core.dsl.TransportsBuilder
import dev.p2pkit.transport.lan.lan

fun configureAndroidLan(builder: TransportsBuilder, context: Context) {
    builder.lan(context)
}
EOF
cat > "$FIXTURE_DIR/kmpConsumer/src/iosMain/kotlin/consumer/IosConsumer.kt" <<'EOF'
package consumer

import dev.p2pkit.transport.lan.IosLanDebug
import kotlinx.coroutines.flow.SharedFlow

fun iosEvents(): SharedFlow<String> = IosLanDebug.events
EOF
fi

if [[ "$AUDIT_CONSUMER_METADATA" == 1 ]]; then
    # This explicit opt-in is separate from the generic executor. Only immutable
    # reviewed external records plus exact source-local publication hashes enter
    # the generated fixture; no remote checksums are downloaded or auto-trusted.
    python3 "$AUDIT_METADATA_HELPER" prepare --root "$ROOT" --work-dir "$WORK_DIR" \
        --publication-receipt "$CONSUMER_RECEIPT_DIR/consumer-publish.json"
fi

echo "==> Compiling isolated published consumers"
echo "==> Consumer profile: $CONSUMER_PROFILE (current-source=$CURRENT_SOURCE_CONSUMER)"
consumer_tasks=()
if [[ "$CONSUMER_PROFILE" == complete ]]; then
    # These original ten tasks remain mandatory in every complete invocation,
    # including the immutable --latest-published compatibility check.
    consumer_tasks=(
        :coreJvm:compileKotlin
        :coreJvm:compileJava
        :lanJvm:compileKotlin
        :desktopJvm:compileKotlin
        :androidConsumer:compileDebugKotlin
        :androidConsumer:processDebugManifest
        :kmpConsumer:compileKotlinJvm
        :kmpConsumer:compileAndroidMain
        :kmpConsumer:compileKotlinIosSimulatorArm64
        :kmpConsumer:linkDebugFrameworkIosSimulatorArm64
    )
fi
if [[ "$CURRENT_SOURCE_CONSUMER" == 1 ]]; then
    # Keep this exact list aligned with the complete audit consumer admission;
    # source-local qualification does not reduce that separate metadata trust gate.
    consumer_tasks+=(
        :lanJvm:runEmbeddedJmdnsSmoke
        :lanJvm:runEmbeddedJmdnsCoexistenceSmoke
        :lanJvm:runEmbeddedJmdnsCoexistenceUpstreamFirstSmoke
        :lanJvm:runEmbeddedJmdnsPomSmoke
        :androidConsumer:assembleDebug
        :androidConsumer:assembleRelease
        :androidConsumer:assembleCoexistDebug
        :androidConsumer:assembleCoexistRelease
        :androidConsumer:verifyEmbeddedJmdnsPackaging
    )
fi
run_consumer_gradle() {
    if [[ -n "$REMOTE_REPOSITORY_URL" ]]; then
        GRADLE_USER_HOME="$WORK_DIR/gradle-home" "$@"
    else
        "$@"
    fi
}
if [[ -n "$GRADLE_EXECUTOR" ]]; then
    (cd "$ROOT" && run_consumer_gradle run_audit_consumer_gradle consumer-build \
        "$CONSUMER_RECEIPT_DIR/consumer-build.json" --no-daemon --console=plain -p "$FIXTURE_DIR" \
        -PconsumerRepo="$CONSUMER_REPOSITORY" \
        ${REMOTE_REPOSITORY_URL:+--refresh-dependencies} \
        "${consumer_tasks[@]}")
else
    (cd "$ROOT" && run_consumer_gradle ./gradlew --no-daemon --console=plain -p "$FIXTURE_DIR" \
        -PconsumerRepo="$CONSUMER_REPOSITORY" \
        ${REMOTE_REPOSITORY_URL:+--refresh-dependencies} \
        "${consumer_tasks[@]}")
fi

if [[ "$CONSUMER_PROFILE" == complete ]]; then
CONSUMER_FRAMEWORK="$FIXTURE_DIR/kmpConsumer/build/bin/iosSimulatorArm64/debugFramework/P2pKitConsumer.framework/P2pKitConsumer"
[[ -f "$CONSUMER_FRAMEWORK" ]] || fail "iOS 14 consumer framework was not linked"
CONSUMER_BUILD_INFO="$(xcrun vtool -show-build "$CONSUMER_FRAMEWORK")"
[[ "$(printf '%s\n' "$CONSUMER_BUILD_INFO" | awk '$1 == "platform" { print $2 }')" == "IOSSIMULATOR" ]] ||
    fail "isolated iOS consumer framework is not an iOS Simulator binary"
[[ "$(printf '%s\n' "$CONSUMER_BUILD_INFO" | awk '$1 == "minos" { print $2 }')" == "$IOS_MIN_VERSION" ]] ||
    fail "isolated iOS consumer framework does not preserve the $IOS_MIN_VERSION deployment floor"
fi

if [[ "$CURRENT_SOURCE_CONSUMER" == 1 ]]; then
    python3 - "$FIXTURE_DIR/androidConsumer/build/reports/embedded-jmdns/packaging.txt" <<'PY_PACKAGING_REPORT'
from pathlib import Path
import sys

report = Path(sys.argv[1])
expected = b"PASS: embedded JmDNS Android D8/R8 plain+coexistence; POM-only runtime graphs\n"
if not report.is_file() or report.is_symlink():
    sys.exit("FAIL: missing or invalid embedded Android consumer packaging report")
with report.open("rb") as stream:
    actual = stream.read(len(expected) + 1)
if actual != expected:
    sys.exit("FAIL: missing or invalid embedded Android consumer packaging report")
PY_PACKAGING_REPORT
    for apk in \
        debug/androidConsumer-debug.apk \
        release/androidConsumer-release-unsigned.apk \
        coexistDebug/androidConsumer-coexistDebug.apk \
        coexistRelease/androidConsumer-coexistRelease-unsigned.apk; do
        [[ -f "$FIXTURE_DIR/androidConsumer/build/outputs/apk/$apk" &&
           ! -L "$FIXTURE_DIR/androidConsumer/build/outputs/apk/$apk" ]] ||
            fail "missing embedded Android consumer APK: $apk"
    done
fi

MERGED_MANIFEST="$(find "$FIXTURE_DIR/androidConsumer/build/intermediates" \
    -path '*/processDebugManifest/AndroidManifest.xml' -print -quit)"
[[ -f "$MERGED_MANIFEST" ]] || fail "Android consumer merged manifest was not produced"
for permission in \
    android.permission.INTERNET \
    android.permission.ACCESS_NETWORK_STATE \
    android.permission.ACCESS_WIFI_STATE \
    android.permission.CHANGE_WIFI_MULTICAST_STATE; do
    grep -Fq "android:name=\"$permission\"" "$MERGED_MANIFEST" ||
        fail "Android consumer merged manifest is missing $permission"
done

if [[ "$AUDIT_CONSUMER_METADATA" == 1 ]]; then
    python3 "$AUDIT_METADATA_HELPER" verify --root "$ROOT" --work-dir "$WORK_DIR" \
        --publication-receipt "$CONSUMER_RECEIPT_DIR/consumer-publish.json"
fi

if [[ "$CONSUMER_PROFILE" == lan-jvm-android ]]; then
    echo "RESULT: PASS — supplemental lan-jvm-android published runtime/packaging checks; not the complete native gate"
elif [[ "$CURRENT_SOURCE_CONSUMER" == 1 ]]; then
    echo "RESULT: PASS — published scopes, Android LAN permissions, isolated JVM/Android/KMP/iOS 14 consumers, and embedded JmDNS consumer checks are complete"
else
    echo "RESULT: PASS — published scopes, Android LAN permissions, and isolated JVM/Android/KMP/iOS 14 consumers are complete"
fi
if [[ "$CURRENT_SOURCE_CONSUMER" == 1 ]]; then
    echo "SCOPE: JVM normal-close smoke and Android D8/R8 packaging; no failed-recovery or Android API24 runtime claim"
fi
