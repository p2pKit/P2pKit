#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FIXTURE="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-wrapper-test.XXXXXX")"
trap 'rm -rf "$FIXTURE"' EXIT

reset_fixture() {
    rm -rf "$FIXTURE/gradle"
    mkdir -p "$FIXTURE/gradle/wrapper"
    cp "$ROOT/gradle/wrapper/gradle-wrapper.properties" "$FIXTURE/gradle/wrapper/"
    cp "$ROOT/gradle/wrapper/gradle-wrapper.jar" "$FIXTURE/gradle/wrapper/"
    cp "$ROOT/gradlew" "$ROOT/gradlew.bat" "$FIXTURE/"
}

expect_failure() {
    local label="$1"
    if "$ROOT/scripts/check-gradle-wrapper.sh" "$FIXTURE" >/dev/null 2>&1; then
        echo "FATAL: mutation was accepted: $label" >&2
        exit 1
    fi
}

reset_fixture
"$ROOT/scripts/check-gradle-wrapper.sh" "$FIXTURE" >/dev/null

sed -i.bak 's/gradle-9\.7\.0-bin/gradle-9.6.1-bin/' "$FIXTURE/gradle/wrapper/gradle-wrapper.properties"
expect_failure "distribution URL"

reset_fixture
printf 'tamper' >> "$FIXTURE/gradle/wrapper/gradle-wrapper.jar"
expect_failure "wrapper JAR"

reset_fixture
printf '# tamper\n' >> "$FIXTURE/gradlew"
expect_failure "Unix launcher"

reset_fixture
printf 'rem tamper\r\n' >> "$FIXTURE/gradlew.bat"
expect_failure "Windows launcher"

echo "RESULT: PASS — valid wrapper accepted and four independent mutations rejected"
