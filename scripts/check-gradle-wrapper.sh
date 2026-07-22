#!/usr/bin/env bash
# Verifies the complete checked-in Gradle wrapper against reviewed Gradle 9.3.1
# release material. An optional repository root supports deterministic fixtures.
set -euo pipefail

ROOT="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
PROPERTIES="$ROOT/gradle/wrapper/gradle-wrapper.properties"
WRAPPER_JAR="$ROOT/gradle/wrapper/gradle-wrapper.jar"
GRADLEW="$ROOT/gradlew"
GRADLEW_BAT="$ROOT/gradlew.bat"

EXPECTED_URL='https\://services.gradle.org/distributions/gradle-9.3.1-bin.zip'
EXPECTED_DISTRIBUTION_SHA='b266d5ff6b90eada6dc3b20cb090e3731302e553a27c5d3e4df1f0d76beaff06'
EXPECTED_WRAPPER_JAR_SHA='b3a875ddc1f044746e1b1a55f645584505f4a10438c1afea9f15e92a7c42ec13'
EXPECTED_GRADLEW_SHA='fb68debc1b1acf8ec55dc0d5e5495e1dedd0bd6b61f304bee61613eeb2bd9b92'
EXPECTED_GRADLEW_BAT_SHA='9ca26d733ada3a45f27b2151288f54e75c9f95b287d1f82ef942ec5cc2d4f006'

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

echo "RESULT: PASS — Gradle 9.3.1 wrapper URL and all component checksums match reviewed values"
