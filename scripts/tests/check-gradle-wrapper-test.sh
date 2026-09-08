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

# Exercise Git's actual checkout conversion, not copies of already-normalized
# working files. Re-checkout only the launchers: other text files have independent
# checkout policies and must not hide a launcher failure behind a properties error.
CHECKOUT="$FIXTURE/git checkout with spaces"
mkdir -p "$CHECKOUT/gradle/wrapper" "$FIXTURE/no-hooks"
: >"$FIXTURE/empty-config"

git_fixture() (
    unset GIT_DIR GIT_COMMON_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY
    unset GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_NAMESPACE GIT_CONFIG_COUNT GIT_CONFIG_PARAMETERS
    export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL="$FIXTURE/empty-config" GIT_ATTR_NOSYSTEM=1
    git -C "$CHECKOUT" -c core.attributesFile="$FIXTURE/empty-config" \
        -c core.hooksPath="$FIXTURE/no-hooks" -c commit.gpgsign=false \
        -c user.name='Wrapper checkout fixture' -c user.email=fixture@example.invalid "$@"
)

git_fixture init -q --template="$FIXTURE/no-hooks"
cp "$ROOT/.gitattributes" "$ROOT/gradlew" "$ROOT/gradlew.bat" "$CHECKOUT/"
cp "$ROOT/gradle/wrapper/gradle-wrapper.properties" "$ROOT/gradle/wrapper/gradle-wrapper.jar" \
    "$CHECKOUT/gradle/wrapper/"
git_fixture -c core.autocrlf=false add -- .gitattributes gradlew gradlew.bat gradle/wrapper
git_fixture -c core.autocrlf=false commit -q -m 'Synthetic reviewed wrapper inputs'
INDEX_LAUNCHERS="$(git_fixture rev-parse :gradlew :gradlew.bat)"

checkout_launchers() {
    local mode="$1"
    rm "$CHECKOUT/gradlew" "$CHECKOUT/gradlew.bat"
    git_fixture -c core.autocrlf="$mode" checkout -- gradlew gradlew.bat
    [[ "$(git_fixture rev-parse :gradlew :gradlew.bat)" == "$INDEX_LAUNCHERS" ]] || {
        echo "FATAL: checkout changed the reviewed launcher index blobs" >&2
        exit 1
    }
    git_fixture ls-files --eol -- gradlew gradlew.bat
}

for mode in false input true; do
    checkout_launchers "$mode"
    "$ROOT/scripts/check-gradle-wrapper.sh" "$CHECKOUT"
    git_fixture -c core.autocrlf="$mode" diff --exit-code HEAD -- gradlew gradlew.bat
    echo "PASS: reviewed launcher bytes survive core.autocrlf=$mode"
done

EXPECTED_ATTRIBUTES=$'gradlew: text: set\ngradlew: eol: lf\ngradlew.bat: text: set\ngradlew.bat: eol: lf'
[[ "$(git_fixture check-attr text eol -- gradlew gradlew.bat)" == "$EXPECTED_ATTRIBUTES" ]] || {
    echo "FATAL: both launchers must explicitly resolve to text eol=lf" >&2
    exit 1
}

expect_checkout_failure() {
    local label="$1" output status=0
    checkout_launchers true
    output="$("$ROOT/scripts/check-gradle-wrapper.sh" "$CHECKOUT" 2>&1)" || status=$?
    [[ "$status" == 1 && "$output" == 'FATAL: gradlew checksum mismatch' ]] || {
        printf 'FATAL: checkout mutation did not fail at the POSIX checksum: %s\n%s\n' "$label" "$output" >&2
        exit 1
    }
    echo "PASS: $label rejected with $output"
}

sed '/^gradlew text eol=lf$/d' "$ROOT/.gitattributes" >"$CHECKOUT/.gitattributes"
git_fixture -c core.autocrlf=false add -- .gitattributes
expect_checkout_failure 'missing POSIX LF attribute'
sed 's/^gradlew text eol=lf$/gradlew text eol=crlf/' "$ROOT/.gitattributes" >"$CHECKOUT/.gitattributes"
git_fixture -c core.autocrlf=false add -- .gitattributes
expect_checkout_failure 'CRLF POSIX attribute'

cp "$ROOT/.gitattributes" "$CHECKOUT/.gitattributes"
git_fixture -c core.autocrlf=false add -- .gitattributes
checkout_launchers true
"$ROOT/scripts/check-gradle-wrapper.sh" "$CHECKOUT"
git_fixture -c core.autocrlf=true diff --exit-code HEAD -- .gitattributes gradlew gradlew.bat

echo "RESULT: PASS — valid wrapper and LF checkouts accepted; four wrapper and two checkout mutations rejected"
