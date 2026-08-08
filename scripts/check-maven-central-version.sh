#!/usr/bin/env bash
# Fail closed when release coordinates already exist, or verify that a published
# Central deployment byte-matches the reviewed upload bundle.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(sed -n 's/^VERSION_NAME=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
LATEST_PUBLISHED="$(sed -n 's/^LATEST_PUBLISHED_VERSION=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
GROUP="$(sed -n 's/^GROUP=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
GROUP_PATH="${GROUP//.//}"
CENTRAL_REPOSITORY="https://repo.maven.apache.org/maven2"

usage() {
    cat <<EOF
Usage:
  scripts/check-maven-central-version.sh absent
  scripts/check-maven-central-version.sh published BUNDLE.zip
  scripts/check-maven-central-version.sh --latest-published published BUNDLE.zip
EOF
}

fail() {
    echo "FATAL: $*" >&2
    exit 1
}

http_code() {
    local url="$1" output="$2"
    curl --silent --show-error --location \
        --output "$output" --write-out '%{http_code}' "$url"
}

ARTIFACTS=(
    p2p-core
    p2p-core-jvm
    p2p-core-android
    p2p-core-iosarm64
    p2p-core-iossimulatorarm64
    p2p-core-iosx64
    p2p-transport-lan
    p2p-transport-lan-jvm
    p2p-transport-lan-android
    p2p-transport-lan-iosarm64
    p2p-transport-lan-iossimulatorarm64
    p2p-transport-lan-iosx64
    p2p-network-provisioning-android
    p2p-network-provisioning-android-android
    p2p-network-provisioning-desktop
)

use_latest_published=0
if [[ "${1:-}" == "--latest-published" ]]; then
    use_latest_published=1
    VERSION="$LATEST_PUBLISHED"
    shift
fi

[[ $# -ge 1 ]] || {
    usage >&2
    exit 2
}
command -v curl >/dev/null 2>&1 || fail "curl is required"
MODE="$1"
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-central-check.XXXXXX")"
trap 'rm -rf "$WORK_DIR"' EXIT

case "$MODE" in
    absent)
        [[ $# -eq 1 ]] || fail "absent mode does not accept a bundle"
        [[ $use_latest_published -eq 0 ]] || fail "absent mode must check VERSION_NAME, not an existing release"
        [[ "$VERSION" != *-SNAPSHOT ]] || fail "snapshot VERSION_NAME=$VERSION cannot be a release collision target"
        collision=0
        for artifact in "${ARTIFACTS[@]}"; do
            url="$CENTRAL_REPOSITORY/$GROUP_PATH/$artifact/$VERSION/$artifact-$VERSION.pom"
            output="$WORK_DIR/$artifact.pom"
            set +e
            code="$(http_code "$url" "$output")"
            curl_status=$?
            set -e
            [[ $curl_status -eq 0 ]] || fail "could not check Maven Central for $artifact"
            case "$code" in
                404) ;;
                200)
                    echo "FAIL immutable coordinate already exists: $GROUP:$artifact:$VERSION" >&2
                    collision=$((collision + 1))
                    ;;
                *) fail "Maven Central returned HTTP $code for $artifact" ;;
            esac
        done
        [[ $collision -eq 0 ]] || fail "$collision release coordinates already exist"
        echo "RESULT: PASS — $GROUP:*:$VERSION is absent from Maven Central"
        ;;
    published)
        [[ $# -eq 2 && -f "$2" ]] || fail "published mode requires an existing bundle ZIP"
        [[ "$VERSION" != *-SNAPSHOT ]] ||
            fail "snapshot VERSION_NAME=$VERSION cannot be verified as a published release; use --latest-published"
        if [[ $use_latest_published -eq 1 ]]; then
            [[ -n "$LATEST_PUBLISHED" && "$LATEST_PUBLISHED" != *-SNAPSHOT ]] ||
                fail "LATEST_PUBLISHED_VERSION must identify a non-snapshot release"
        fi
        command -v openssl >/dev/null 2>&1 || fail "openssl is required"
        command -v unzip >/dev/null 2>&1 || fail "unzip is required"
        BUNDLE="$2"
        unzip -tq "$BUNDLE" >/dev/null || fail "bundle ZIP integrity check failed"
        EXTRACTED="$WORK_DIR/bundle"
        mkdir -p "$EXTRACTED"
        unzip -q "$BUNDLE" -d "$EXTRACTED"
        BASE="$EXTRACTED/$GROUP_PATH"
        [[ -d "$BASE" ]] || fail "bundle does not contain the expected group path"

        poll_seconds=15
        max_polls=120
        if [[ "${P2PKIT_CENTRAL_TEST_MODE:-}" == "1" ]]; then
            poll_seconds="${P2PKIT_CENTRAL_POLL_SECONDS:-0}"
            max_polls="${P2PKIT_CENTRAL_MAX_POLLS:-5}"
        fi
        probe="$CENTRAL_REPOSITORY/$GROUP_PATH/p2p-core/$VERSION/p2p-core-$VERSION.pom"
        available=0
        for ((poll = 1; poll <= max_polls; poll++)); do
            set +e
            code="$(http_code "$probe" "$WORK_DIR/probe.pom")"
            curl_status=$?
            set -e
            if [[ $curl_status -eq 0 && "$code" == "200" ]]; then
                available=1
                break
            fi
            if [[ $curl_status -eq 0 && "$code" != "404" && "$code" != "429" && ! "$code" =~ ^5[0-9][0-9]$ ]]; then
                fail "Maven Central propagation probe returned HTTP $code"
            fi
            if (( poll < max_polls )); then
                sleep "$poll_seconds"
            fi
        done
        [[ $available -eq 1 ]] || fail "published coordinates did not propagate within the bounded window"

        checked=0
        mismatched=0
        while IFS= read -r file; do
            case "$file" in
                *.md5|*.sha1|*.sha256|*.sha512) continue ;;
            esac
            relative="${file#"$EXTRACTED/"}"
            remote="$WORK_DIR/remote-$checked"
            set +e
            code="$(http_code "$CENTRAL_REPOSITORY/$relative" "$remote")"
            curl_status=$?
            set -e
            if [[ $curl_status -ne 0 || "$code" != "200" ]]; then
                echo "FAIL missing published file: $relative" >&2
                mismatched=$((mismatched + 1))
            else
                expected="$(openssl dgst -sha256 "$file" | awk '{print $NF}')"
                actual="$(openssl dgst -sha256 "$remote" | awk '{print $NF}')"
                if [[ "$expected" != "$actual" ]]; then
                    echo "FAIL published bytes differ: $relative" >&2
                    mismatched=$((mismatched + 1))
                fi
            fi
            checked=$((checked + 1))
        done < <(find "$BASE" -type f | LC_ALL=C sort)
        [[ $checked -gt 0 ]] || fail "bundle contains no publication files"
        [[ $mismatched -eq 0 ]] || fail "$mismatched of $checked published files failed verification"
        echo "RESULT: PASS — $checked published files byte-match the reviewed Central bundle"
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac
