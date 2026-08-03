#!/usr/bin/env bash
# Upload one reviewed bundle to Central Portal with AUTOMATIC publishing.
# The upload request is deliberately never retried: a transport failure after
# request transmission is ambiguous and a duplicate release is not safe.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(sed -n 's/^VERSION_NAME=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
CENTRAL_API="https://central.sonatype.com/api/v1/publisher"
DEFAULT_POLL_SECONDS=15
DEFAULT_MAX_POLLS=120

usage() {
    cat <<EOF
Usage: scripts/publish-central-portal-bundle.sh BUNDLE.zip [EVIDENCE_DIRECTORY]

Requires MAVEN_CENTRAL_USERNAME and MAVEN_CENTRAL_PASSWORD. The bundle is
uploaded once with publishingType=AUTOMATIC and status is polled for at most
30 minutes. Do not run this command unless immutable publication is authorized.
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi

fail() {
    echo "FATAL: $*" >&2
    exit 1
}

record_event() {
    local event="$1" state="${2:-}" detail="${3:-}"
    jq -cn \
        --arg timestamp "$(date -u '+%Y-%m-%dT%H:%M:%S.000Z')" \
        --arg event "$event" \
        --arg state "$state" \
        --arg detail "$detail" \
        '{timestamp: $timestamp, event: $event, state: $state, detail: $detail}' \
        >>"$EVENTS"
}

[[ $# -ge 1 && $# -le 2 ]] || {
    usage >&2
    exit 2
}
for command in base64 curl jq openssl unzip; do
    command -v "$command" >/dev/null 2>&1 || fail "$command is required"
done
[[ -n "${MAVEN_CENTRAL_USERNAME:-}" ]] || fail "MAVEN_CENTRAL_USERNAME is required"
[[ -n "${MAVEN_CENTRAL_PASSWORD:-}" ]] || fail "MAVEN_CENTRAL_PASSWORD is required"

BUNDLE="$1"
[[ -f "$BUNDLE" && "$BUNDLE" == *.zip ]] || fail "bundle must be an existing .zip file"
unzip -tq "$BUNDLE" >/dev/null || fail "bundle ZIP integrity check failed"
EVIDENCE="${2:-$ROOT/build/reports/maven-central}"
mkdir -p "$EVIDENCE"
EVENTS="$EVIDENCE/portal-events.jsonl"
STATUS_FILE="$EVIDENCE/status.json"
RESPONSE_FILE="$EVIDENCE/upload-response.txt"
: >"$EVENTS"
: >"$STATUS_FILE"
: >"$RESPONSE_FILE"

POLL_SECONDS="$DEFAULT_POLL_SECONDS"
MAX_POLLS="$DEFAULT_MAX_POLLS"
if [[ "${P2PKIT_CENTRAL_TEST_MODE:-}" == "1" ]]; then
    POLL_SECONDS="${P2PKIT_CENTRAL_POLL_SECONDS:-0}"
    MAX_POLLS="${P2PKIT_CENTRAL_MAX_POLLS:-5}"
fi
[[ "$POLL_SECONDS" =~ ^[0-9]+$ && "$MAX_POLLS" =~ ^[1-9][0-9]*$ ]] ||
    fail "invalid Portal polling configuration"

COMMIT_SHA="${GITHUB_SHA:-$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || true)}"
[[ "$COMMIT_SHA" =~ ^[0-9a-fA-F]{40}$ ]] || fail "a complete release commit SHA is required"
DEPLOYMENT_NAME="p2pkit-$VERSION-${COMMIT_SHA:0:12}"
BUNDLE_SHA256="$(openssl dgst -sha256 "$BUNDLE" | awk '{print $NF}')"
printf '%s\n' "$BUNDLE_SHA256" >"$EVIDENCE/bundle.sha256"
printf '%s\n' "$COMMIT_SHA" >"$EVIDENCE/commit-sha.txt"

BEARER_TOKEN="$(printf '%s:%s' "$MAVEN_CENTRAL_USERNAME" "$MAVEN_CENTRAL_PASSWORD" | base64 | tr -d '\r\n')"
[[ -n "$BEARER_TOKEN" ]] || fail "could not construct Central authorization token"
if [[ "${GITHUB_ACTIONS:-}" == "true" ]]; then
    printf '::add-mask::%s\n' "$BEARER_TOKEN"
fi
AUTHORIZATION="Authorization: Bearer $BEARER_TOKEN"

record_event "upload_started" "LOCAL" "$DEPLOYMENT_NAME"
set +e
UPLOAD_HTTP_CODE="$(
    curl --silent --show-error \
        --request POST \
        --header "$AUTHORIZATION" \
        --form "bundle=@$BUNDLE;type=application/octet-stream" \
        --output "$RESPONSE_FILE" \
        --write-out '%{http_code}' \
        "$CENTRAL_API/upload?publishingType=AUTOMATIC&name=$DEPLOYMENT_NAME"
)"
UPLOAD_CURL_STATUS=$?
set -e
if [[ $UPLOAD_CURL_STATUS -ne 0 ]]; then
    record_event "upload_ambiguous" "UNKNOWN" "curl_exit_$UPLOAD_CURL_STATUS"
    fail "Central upload outcome is ambiguous; inspect Portal and do not retry automatically"
fi
if [[ "$UPLOAD_HTTP_CODE" != "201" ]]; then
    record_event "upload_rejected" "FAILED" "http_$UPLOAD_HTTP_CODE"
    fail "Central rejected the upload with HTTP $UPLOAD_HTTP_CODE"
fi

DEPLOYMENT_ID="$(tr -d '[:space:]' <"$RESPONSE_FILE")"
[[ "$DEPLOYMENT_ID" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]] ||
    fail "Central returned a malformed deployment ID"
printf '%s\n' "$DEPLOYMENT_ID" >"$EVIDENCE/deployment-id.txt"
rm -f "$RESPONSE_FILE"
record_event "upload_accepted" "PENDING" "$DEPLOYMENT_ID"

poll=0
last_state=""
while (( poll < MAX_POLLS )); do
    poll=$((poll + 1))
    STATUS_TMP="$EVIDENCE/status.tmp"
    set +e
    STATUS_HTTP_CODE="$(
        curl --silent --show-error \
            --request POST \
            --header "$AUTHORIZATION" \
            --output "$STATUS_TMP" \
            --write-out '%{http_code}' \
            "$CENTRAL_API/status?id=$DEPLOYMENT_ID"
    )"
    STATUS_CURL_STATUS=$?
    set -e

    if [[ $STATUS_CURL_STATUS -ne 0 ]]; then
        record_event "status_retry" "$last_state" "curl_exit_$STATUS_CURL_STATUS"
    elif [[ "$STATUS_HTTP_CODE" == "429" || "$STATUS_HTTP_CODE" =~ ^5[0-9][0-9]$ ]]; then
        record_event "status_retry" "$last_state" "http_$STATUS_HTTP_CODE"
    elif [[ "$STATUS_HTTP_CODE" == "401" || "$STATUS_HTTP_CODE" == "403" ]]; then
        record_event "status_rejected" "$last_state" "http_$STATUS_HTTP_CODE"
        fail "Central status authentication failed with HTTP $STATUS_HTTP_CODE"
    elif [[ "$STATUS_HTTP_CODE" != "200" ]]; then
        record_event "status_rejected" "$last_state" "http_$STATUS_HTTP_CODE"
        fail "Central status request failed with HTTP $STATUS_HTTP_CODE"
    elif ! jq -e 'type == "object" and (.deploymentState | type == "string")' "$STATUS_TMP" >/dev/null 2>&1; then
        record_event "status_invalid" "$last_state" "malformed_json"
        fail "Central returned malformed deployment status JSON"
    else
        cp "$STATUS_TMP" "$STATUS_FILE"
        state="$(jq -r '.deploymentState' "$STATUS_FILE")"
        if [[ "$state" != "$last_state" ]]; then
            record_event "deployment_state" "$state" "poll_$poll"
            last_state="$state"
        fi
        case "$state" in
            PENDING|VALIDATING|VALIDATED|PUBLISHING)
                ;;
            PUBLISHED)
                rm -f "$STATUS_TMP"
                record_event "publication_completed" "PUBLISHED" "$DEPLOYMENT_ID"
                echo "RESULT: PASS — Maven Central deployment reached PUBLISHED"
                echo "Deployment ID: $DEPLOYMENT_ID"
                echo "Evidence: $EVIDENCE"
                exit 0
                ;;
            FAILED)
                rm -f "$STATUS_TMP"
                record_event "publication_failed" "FAILED" "$DEPLOYMENT_ID"
                fail "Central deployment failed validation or publication; inspect $STATUS_FILE"
                ;;
            *)
                rm -f "$STATUS_TMP"
                record_event "status_unknown" "$state" "$DEPLOYMENT_ID"
                fail "Central returned unknown deployment state '$state'"
                ;;
        esac
    fi
    rm -f "$STATUS_TMP"
    if (( poll < MAX_POLLS )); then
        sleep "$POLL_SECONDS"
    fi
done

record_event "publication_timeout" "$last_state" "polls_$MAX_POLLS"
fail "Central did not reach PUBLISHED within the bounded polling window"
