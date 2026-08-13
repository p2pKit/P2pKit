#!/usr/bin/env bash
# Verifies the complete checked-in Gradle wrapper against reviewed Gradle 9.7.0
# release material. An optional repository root supports deterministic fixtures.
set -euo pipefail

ROOT="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
PROPERTIES="$ROOT/gradle/wrapper/gradle-wrapper.properties"
WRAPPER_JAR="$ROOT/gradle/wrapper/gradle-wrapper.jar"
GRADLEW="$ROOT/gradlew"
GRADLEW_BAT="$ROOT/gradlew.bat"

EXPECTED_URL='https\://services.gradle.org/distributions/gradle-9.7.0-bin.zip'
EXPECTED_DISTRIBUTION_SHA='84fbba45c7f4c64abc77460e1c00f541e9f960e3c7ed2538f1ede19eacd873ae'
EXPECTED_WRAPPER_JAR_SHA='7a9ce74cff467ca1bf60a4fcd9f05185acceda4d0f382434d393e17864262c5d'
EXPECTED_GRADLEW_SHA='a5a5c199ba02189ae8c46a334223371a20599d9c298ef65e7540ede4a3f72d59'
EXPECTED_GRADLEW_BAT_SHA='59328c7a17f673b1a63040bfb380a0c749e5d6df3406f7f18641060314cd9aa1'

fail() {
    echo "FATAL: $*" >&2
    exit 1
}

sha256() {
    if command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | awk '{print $1}'
    elif command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    else
        fail "neither shasum nor sha256sum is available"
    fi
}

property() {
    local key="$1"
    sed -n "s/^${key}=//p" "$PROPERTIES"
}

for file in "$PROPERTIES" "$WRAPPER_JAR" "$GRADLEW" "$GRADLEW_BAT"; do
    [[ -f "$file" ]] || fail "missing wrapper component: $file"
done

[[ "$(property distributionUrl)" == "$EXPECTED_URL" ]] || fail "unexpected Gradle distribution URL"
[[ "$(property distributionSha256Sum)" == "$EXPECTED_DISTRIBUTION_SHA" ]] || fail "unexpected Gradle distribution checksum"
[[ "$(property validateDistributionUrl)" == "true" ]] || fail "distribution URL validation is not enabled"
[[ "$(sha256 "$WRAPPER_JAR")" == "$EXPECTED_WRAPPER_JAR_SHA" ]] || fail "gradle-wrapper.jar checksum mismatch"
[[ "$(sha256 "$GRADLEW")" == "$EXPECTED_GRADLEW_SHA" ]] || fail "gradlew checksum mismatch"
[[ "$(sha256 "$GRADLEW_BAT")" == "$EXPECTED_GRADLEW_BAT_SHA" ]] || fail "gradlew.bat checksum mismatch"

echo "RESULT: PASS — Gradle 9.7.0 wrapper URL and all component checksums match reviewed values"
