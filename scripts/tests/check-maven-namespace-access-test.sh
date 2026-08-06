#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="$ROOT/scripts/check-maven-namespace-access.sh"
FAKE_CURL="$ROOT/scripts/tests/fixtures/fake-central-namespace-curl.sh"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-namespace-access-test.XXXXXX")"
trap 'rm -rf "$TEST_ROOT"' EXIT

USERNAME="synthetic-user"
PASSWORD="synthetic-password"
NAMESPACE="io.github.apdelrahman1911"

bash -n "$SCRIPT"
bash -n "$FAKE_CURL"

run_check() {
    MAVEN_CENTRAL_USERNAME="$USERNAME" \
    MAVEN_CENTRAL_PASSWORD="$PASSWORD" \
    MAVEN_CENTRAL_NAMESPACE="$NAMESPACE" \
    MAVEN_NAMESPACE_REPORT_DIR="$TEST_ROOT/report" \
    CURL_BIN="$FAKE_CURL" \
        "$SCRIPT"
}

FAKE_CENTRAL_NAMESPACE_RESPONSE='[{"id":"namespace-id","name":"io.github.apdelrahman1911","state":"VERIFIED","userIds":["private-user-id"]}]' \
    run_check >"$TEST_ROOT/success.log"
jq -e \
    --arg namespace "$NAMESPACE" \
    '.namespace == $namespace and .state == "VERIFIED" and .tokenPublisherAccess == true' \
    "$TEST_ROOT/report/namespace-access.json" >/dev/null

for secret in "$USERNAME" "$PASSWORD" "private-user-id"; do
    if grep -R -Fq -- "$secret" "$TEST_ROOT/success.log" "$TEST_ROOT/report"; then
        echo "FATAL: namespace access check leaked credential or private response data" >&2
        exit 1
    fi
done

if FAKE_CENTRAL_NAMESPACE_RESPONSE='[{"name":"io.github.p2pkit","state":"VERIFIED"}]' \
    run_check >/dev/null 2>&1; then
    echo "FATAL: a different verified namespace was accepted" >&2
    exit 1
fi

if FAKE_CENTRAL_NAMESPACE_RESPONSE='[{"name":"io.github.apdelrahman1911","state":"VERIFYING"}]' \
    run_check >/dev/null 2>&1; then
    echo "FATAL: a non-verified namespace was accepted" >&2
    exit 1
fi

if FAKE_CENTRAL_NAMESPACE_HTTP_CODE=401 \
    FAKE_CENTRAL_NAMESPACE_RESPONSE='{"message":"unauthorized"}' \
    run_check >/dev/null 2>&1; then
    echo "FATAL: an unauthorized token was accepted" >&2
    exit 1
fi

if FAKE_CENTRAL_NAMESPACE_CURL_STATUS=7 run_check >/dev/null 2>&1; then
    echo "FATAL: a transport failure was accepted" >&2
    exit 1
fi

echo "RESULT: PASS — exact verified Central namespace access fails closed without leaking secrets"
