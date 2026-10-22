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
cp "$ROOT/scripts/central-http.sh" "$RELEASE_ROOT/scripts/"
cp "$ROOT/scripts/check-maven-central-version.sh" "$RELEASE_ROOT/scripts/check-maven-central-version.sh"
printf '%s\n' \
    "GROUP=$GROUP" \
    'VERSION_NAME=9.8.7-rc6' \
    'LATEST_PUBLISHED_VERSION=9.8.7-rc5' \
    > "$RELEASE_ROOT/gradle.properties"
SCRIPT="$RELEASE_ROOT/scripts/check-maven-central-version.sh"

bash -n "$SCRIPT"
EXPECTED_ARTIFACTS=(
    p2p-core p2p-core-jvm p2p-core-android
    p2p-core-iosarm64 p2p-core-iossimulatorarm64 p2p-core-iosx64
    p2p-transport-lan p2p-transport-lan-jvm p2p-transport-lan-android
    p2p-transport-lan-iosarm64 p2p-transport-lan-iossimulatorarm64 p2p-transport-lan-iosx64
    p2p-network-provisioning-android p2p-network-provisioning-android-android
    p2p-network-provisioning-desktop
    p2p-rpc p2p-rpc-jvm p2p-rpc-android
    p2p-rpc-iosarm64 p2p-rpc-iossimulatorarm64 p2p-rpc-iosx64
)
: >"$WORK_DIR/state/maven-requests"
PATH="$WORK_DIR/bin:$PATH" FAKE_CENTRAL_STATE_DIR="$WORK_DIR/state" \
    FAKE_MAVEN_CODE=404 FAKE_MAVEN_REQUIRED_PATH="/maven2/$GROUP_PATH/" \
    "$SCRIPT" absent >/dev/null
for artifact in "${EXPECTED_ARTIFACTS[@]}"; do
    printf 'https://repo.maven.apache.org/maven2/%s/%s/9.8.7-rc6/%s-9.8.7-rc6.pom\n' \
        "$GROUP_PATH" "$artifact" "$artifact"
done | LC_ALL=C sort >"$WORK_DIR/expected-requests"
LC_ALL=C sort "$WORK_DIR/state/maven-requests" >"$WORK_DIR/actual-requests"
diff -u "$WORK_DIR/expected-requests" "$WORK_DIR/actual-requests"

if PATH="$WORK_DIR/bin:$PATH" FAKE_CENTRAL_STATE_DIR="$WORK_DIR/state" \
    FAKE_MAVEN_CODE=404 "$SCRIPT" --latest-published absent >/dev/null 2>&1; then
    echo "FATAL: existing latest-published version was accepted as an absence target" >&2
    exit 1
fi

for artifact in "${EXPECTED_ARTIFACTS[@]}"; do
    if PATH="$WORK_DIR/bin:$PATH" FAKE_CENTRAL_STATE_DIR="$WORK_DIR/state" \
        FAKE_MAVEN_CODE=404 FAKE_MAVEN_REQUIRED_PATH="/maven2/$GROUP_PATH/" \
        FAKE_MAVEN_EXISTING_ARTIFACT="$artifact" \
        "$SCRIPT" absent >"$WORK_DIR/collision-$artifact.log" 2>&1; then
        echo "FATAL: existing immutable coordinate $artifact was accepted" >&2
        exit 1
    fi
    grep -Fq "immutable coordinate already exists: $GROUP:$artifact:9.8.7-rc6" \
        "$WORK_DIR/collision-$artifact.log"
done

# Only the selected RPC coordinate fails; all preceding legacy probes return 404.
# This proves the checker reaches each new coordinate and fails closed there.
for artifact in p2p-rpc p2p-rpc-jvm p2p-rpc-android \
    p2p-rpc-iosarm64 p2p-rpc-iossimulatorarm64 p2p-rpc-iosx64; do
    for code in 403 429 500; do
        if PATH="$WORK_DIR/bin:$PATH" FAKE_CENTRAL_STATE_DIR="$WORK_DIR/state" \
            FAKE_MAVEN_CODE=404 FAKE_MAVEN_EXISTING_ARTIFACT="$artifact" FAKE_MAVEN_ARTIFACT_CODE="$code" \
            "$SCRIPT" absent >"$WORK_DIR/http-$artifact-$code.log" 2>&1; then
            echo "FATAL: RPC HTTP $code was treated as absence for $artifact" >&2
            exit 1
        fi
        grep -Fq "Maven Central returned HTTP $code for $artifact" "$WORK_DIR/http-$artifact-$code.log"
    done
    if PATH="$WORK_DIR/bin:$PATH" FAKE_CENTRAL_STATE_DIR="$WORK_DIR/state" \
        FAKE_MAVEN_CODE=404 FAKE_MAVEN_EXISTING_ARTIFACT="$artifact" FAKE_MAVEN_ARTIFACT_EXIT=7 \
        "$SCRIPT" absent >"$WORK_DIR/transport-$artifact.log" 2>&1; then
        echo "FATAL: RPC transport failure was treated as absence for $artifact" >&2
        exit 1
    fi
    grep -Fq "could not check Maven Central for $artifact" "$WORK_DIR/transport-$artifact.log"
done

if PATH="$WORK_DIR/bin:$PATH" FAKE_CENTRAL_STATE_DIR="$WORK_DIR/state" \
    FAKE_MAVEN_CODE=500 FAKE_MAVEN_REQUIRED_PATH="/maven2/$GROUP_PATH/" \
    "$SCRIPT" absent >/dev/null 2>&1; then
    echo "FATAL: Maven Central availability failure was treated as absence" >&2
    exit 1
fi

# Historical releases do not acquire RPC artifacts retroactively. Published mode
# verifies the supplied bundle rather than imposing the current absence inventory.
historical="$WORK_DIR/historical/$GROUP_PATH/p2p-core/9.8.7-rc5"
mkdir -p "$historical"
printf 'fixture' >"$historical/p2p-core-9.8.7-rc5.pom"
(cd "$WORK_DIR/historical" && zip -qr "$WORK_DIR/historical.zip" .)
: >"$WORK_DIR/state/maven-requests"
PATH="$WORK_DIR/bin:$PATH" FAKE_CENTRAL_STATE_DIR="$WORK_DIR/state" FAKE_MAVEN_CODE=200 \
    FAKE_MAVEN_REQUIRED_PATH="/maven2/$GROUP_PATH/p2p-core/9.8.7-rc5/" \
    "$SCRIPT" --latest-published published "$WORK_DIR/historical.zip" >/dev/null
if grep -q '/p2p-rpc' "$WORK_DIR/state/maven-requests"; then
    echo "FATAL: historical bundle verification required unpublished RPC artifacts" >&2
    exit 1
fi

# Current bundle verification must also inspect each actual RPC publication file.
for artifact in p2p-rpc p2p-rpc-jvm p2p-rpc-android \
    p2p-rpc-iosarm64 p2p-rpc-iossimulatorarm64 p2p-rpc-iosx64; do
    directory="$WORK_DIR/current/$GROUP_PATH/$artifact/9.8.7-rc6"
    mkdir -p "$directory"
    printf 'fixture' >"$directory/$artifact-9.8.7-rc6.pom"
done
(cd "$WORK_DIR/current" && zip -qr "$WORK_DIR/current.zip" .)
: >"$WORK_DIR/state/maven-requests"
PATH="$WORK_DIR/bin:$PATH" FAKE_CENTRAL_STATE_DIR="$WORK_DIR/state" FAKE_MAVEN_CODE=200 \
    FAKE_MAVEN_REQUIRED_PATH="/maven2/$GROUP_PATH/" \
    "$SCRIPT" published "$WORK_DIR/current.zip" >/dev/null
for artifact in p2p-rpc p2p-rpc-jvm p2p-rpc-android \
    p2p-rpc-iosarm64 p2p-rpc-iossimulatorarm64 p2p-rpc-iosx64; do
    grep -Fxq "https://repo.maven.apache.org/maven2/$GROUP_PATH/$artifact/9.8.7-rc6/$artifact-9.8.7-rc6.pom" \
        "$WORK_DIR/state/maven-requests"
done

echo "RESULT: PASS — 21 coordinate collisions, 24 RPC failures, exact probe inventory, historical/current bundles and version guards"
