#!/usr/bin/env bash
set -euo pipefail

output=""
authorization=0
url=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --output)
            output="$2"
            shift 2
            ;;
        --write-out|--request|--form)
            shift 2
            ;;
        --header)
            [[ "$2" == "Authorization: Bearer "* ]] && authorization=1
            shift 2
            ;;
        --silent|--show-error|--location|--fail)
            shift
            ;;
        *)
            url="$1"
            shift
            ;;
    esac
done

[[ -n "$output" && -n "$url" ]] || exit 64
mkdir -p "$(dirname "$output")"
STATE_DIR="${FAKE_CENTRAL_STATE_DIR:?}"
mkdir -p "$STATE_DIR"

next_value() {
    local values="$1" index="$2" value last=""
    IFS=',' read -r -a entries <<<"$values"
    for value in "${entries[@]}"; do
        last="$value"
    done
    if (( index <= ${#entries[@]} )); then
        printf '%s' "${entries[index - 1]}"
    else
        printf '%s' "$last"
    fi
}

if [[ "$url" == *"/api/v1/publisher/upload?"* ]]; then
    count_file="$STATE_DIR/upload-count"
    count=$(( $(cat "$count_file" 2>/dev/null || printf '0') + 1 ))
    printf '%s\n' "$count" >"$count_file"
    [[ $authorization -eq 1 && "$url" == *"publishingType=AUTOMATIC"* ]] || {
        printf '{"error":"invalid request"}' >"$output"
        printf '400'
        exit 0
    }
    case "${FAKE_CENTRAL_UPLOAD_MODE:-success}" in
        success)
            printf '%s\n' "${FAKE_CENTRAL_DEPLOYMENT_ID:-123e4567-e89b-12d3-a456-426614174000}" >"$output"
            printf '201'
            ;;
        ambiguous)
            : >"$output"
            exit 7
            ;;
        malformed)
            printf 'not-a-deployment-id\n' >"$output"
            printf '201'
            ;;
        unauthorized)
            printf '{"error":"unauthorized"}' >"$output"
            printf '401'
            ;;
        *) exit 65 ;;
    esac
    exit 0
fi

if [[ "$url" == *"/api/v1/publisher/status?id="* ]]; then
    count_file="$STATE_DIR/status-count"
    count=$(( $(cat "$count_file" 2>/dev/null || printf '0') + 1 ))
    printf '%s\n' "$count" >"$count_file"
    code="$(next_value "${FAKE_CENTRAL_STATUS_CODES:-200}" "$count")"
    if [[ "$code" != "200" ]]; then
        printf '{"error":"synthetic status error"}' >"$output"
        printf '%s' "$code"
        exit 0
    fi
    state="$(next_value "${FAKE_CENTRAL_STATES:-PUBLISHED}" "$count")"
    if [[ "$state" == "MALFORMED" ]]; then
        printf 'not-json' >"$output"
    elif [[ "$state" == "FAILED" ]]; then
        printf '{"deploymentState":"FAILED","errors":["synthetic failure"]}' >"$output"
    else
        printf '{"deploymentId":"123e4567-e89b-12d3-a456-426614174000","deploymentState":"%s"}' "$state" >"$output"
    fi
    printf '200'
    exit 0
fi

if [[ "$url" == https://repo.maven.apache.org/maven2/* ]]; then
    if [[ -n "${FAKE_MAVEN_REQUIRED_PATH:-}" && "$url" != *"${FAKE_MAVEN_REQUIRED_PATH}"* ]]; then
        exit 67
    fi
    artifact="${FAKE_MAVEN_EXISTING_ARTIFACT:-}"
    code="${FAKE_MAVEN_CODE:-404}"
    if [[ -n "$artifact" && "$url" == *"/$artifact/"* ]]; then
        code=200
    fi
    printf 'fixture' >"$output"
    printf '%s' "$code"
    exit 0
fi

exit 66
