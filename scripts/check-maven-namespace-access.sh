#!/usr/bin/env bash
# Read-only verification that the configured Central Portal token can see the
# exact release namespace in VERIFIED state. Raw credentials and API responses
# are never printed or retained.
set -euo pipefail

fail() {
    echo "FATAL: $*" >&2
    exit 1
}

for name in MAVEN_CENTRAL_USERNAME MAVEN_CENTRAL_PASSWORD MAVEN_CENTRAL_NAMESPACE; do
    [[ -n "${!name:-}" ]] || fail "$name is required"
done

[[ "$MAVEN_CENTRAL_NAMESPACE" =~ ^[a-zA-Z]{2,}\.[a-zA-Z0-9.-]+$ ]] ||
    fail "MAVEN_CENTRAL_NAMESPACE is malformed"
command -v jq >/dev/null 2>&1 || fail "jq is required"

curl_bin="${CURL_BIN:-curl}"
endpoint="${CENTRAL_NAMESPACE_API_URL:-https://central.sonatype.com/api/internal/publisher/namespace}"
report_dir="${MAVEN_NAMESPACE_REPORT_DIR:-build/reports/maven-central}"
mkdir -p "$report_dir"

response_file="$(mktemp "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/p2pkit-central-namespace.XXXXXX")"
cleanup() {
    rm -f "$response_file"
}
trap cleanup EXIT

credential_pair="${MAVEN_CENTRAL_USERNAME}:${MAVEN_CENTRAL_PASSWORD}"
bearer="$(printf '%s' "$credential_pair" | base64 | tr -d '\r\n')"
unset credential_pair
if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
    echo "::add-mask::$bearer"
fi

set +e
http_code="$("$curl_bin" \
    --silent \
    --show-error \
    --output "$response_file" \
    --write-out '%{http_code}' \
    --header "Accept: application/json" \
    --header "Authorization: Bearer $bearer" \
    "$endpoint")"
curl_status=$?
set -e
unset bearer

[[ "$curl_status" -eq 0 ]] || fail "Central namespace query failed before an HTTP response"
[[ "$http_code" == "200" ]] || fail "Central namespace query returned HTTP $http_code"
jq -e 'type == "array"' "$response_file" >/dev/null ||
    fail "Central namespace query returned an unexpected response shape"

matching_count="$(jq --arg namespace "$MAVEN_CENTRAL_NAMESPACE" \
    '[.[] | select(.name == $namespace)] | length' "$response_file")"
[[ "$matching_count" == "1" ]] ||
    fail "exact namespace $MAVEN_CENTRAL_NAMESPACE was not uniquely visible to the configured token"

state="$(jq -r --arg namespace "$MAVEN_CENTRAL_NAMESPACE" \
    '.[] | select(.name == $namespace) | .state' "$response_file")"
[[ "$state" == "VERIFIED" ]] ||
    fail "exact namespace $MAVEN_CENTRAL_NAMESPACE is visible but not VERIFIED"

checked_at="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
jq -n \
    --arg namespace "$MAVEN_CENTRAL_NAMESPACE" \
    --arg state "$state" \
    --arg checkedAt "$checked_at" \
    --arg commitSha "${GITHUB_SHA:-local}" \
    '{schemaVersion: 1, namespace: $namespace, state: $state, tokenPublisherAccess: true, checkedAt: $checkedAt, commitSha: $commitSha}' \
    >"$report_dir/namespace-access.json"

echo "RESULT: PASS — configured Central token has publisher access to verified namespace $MAVEN_CENTRAL_NAMESPACE"
