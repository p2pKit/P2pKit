#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="$ROOT/scripts/publish-central-portal-bundle.sh"
FIXTURE_CURL="$ROOT/scripts/tests/fixtures/fake-central-curl.sh"
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-central-api-test.XXXXXX")"
trap 'rm -rf "$WORK_DIR"' EXIT
mkdir -p "$WORK_DIR/bin" "$WORK_DIR/content"
ln -s "$FIXTURE_CURL" "$WORK_DIR/bin/curl"
printf 'fixture\n' >"$WORK_DIR/content/artifact.txt"
(cd "$WORK_DIR/content" && zip -q "$WORK_DIR/bundle.zip" artifact.txt)

bash -n "$SCRIPT"
"$SCRIPT" --help >/dev/null

USERNAME="synthetic-central-user"
PASSWORD="synthetic-central-password"
BEARER="$(printf '%s:%s' "$USERNAME" "$PASSWORD" | base64 | tr -d '\r\n')"
COMMIT="0123456789abcdef0123456789abcdef01234567"

run_case() {
    local name="$1" upload_mode="$2" states="$3" status_codes="$4" max_polls="$5"
    rm -rf "$WORK_DIR/state" "$WORK_DIR/evidence-$name"
    mkdir -p "$WORK_DIR/state"
    set +e
    # The runner interprets add-mask commands only when they reach its stdout.
    # This fixture captures subprocess output to a file, where an add-mask
    # command would instead be raw synthetic credential material.
    PATH="$WORK_DIR/bin:$PATH" \
        FAKE_CENTRAL_STATE_DIR="$WORK_DIR/state" \
        FAKE_CENTRAL_UPLOAD_MODE="$upload_mode" \
        FAKE_CENTRAL_STATES="$states" \
        FAKE_CENTRAL_STATUS_CODES="$status_codes" \
        P2PKIT_CENTRAL_TEST_MODE=1 \
        P2PKIT_CENTRAL_POLL_SECONDS=0 \
        P2PKIT_CENTRAL_MAX_POLLS="$max_polls" \
        GITHUB_ACTIONS=false \
        MAVEN_CENTRAL_USERNAME="$USERNAME" \
        MAVEN_CENTRAL_PASSWORD="$PASSWORD" \
        GITHUB_SHA="$COMMIT" \
        "$SCRIPT" "$WORK_DIR/bundle.zip" "$WORK_DIR/evidence-$name" \
        >"$WORK_DIR/$name.log" 2>&1
    CASE_STATUS=$?
    set -e
    for secret in "$USERNAME" "$PASSWORD" "$BEARER"; do
        if grep -Fq -- "$secret" "$WORK_DIR/$name.log"; then
            echo "FATAL: $name leaked credential material" >&2
            exit 1
        fi
    done
}

if MAVEN_CENTRAL_USERNAME= MAVEN_CENTRAL_PASSWORD= \
    "$SCRIPT" "$WORK_DIR/bundle.zip" "$WORK_DIR/missing" >/dev/null 2>&1; then
    echo "FATAL: missing Central credentials were accepted" >&2
    exit 1
fi

run_case success success PENDING,VALIDATING,VALIDATED,PUBLISHING,PUBLISHED 200 8
[[ $CASE_STATUS -eq 0 ]] || { echo "FATAL: successful Portal sequence failed" >&2; exit 1; }
[[ "$(cat "$WORK_DIR/state/upload-count")" == "1" ]] || { echo "FATAL: upload was not one-shot" >&2; exit 1; }
jq -e '.deploymentState == "PUBLISHED"' "$WORK_DIR/evidence-success/status.json" >/dev/null
grep -Fq 'publication_completed' "$WORK_DIR/evidence-success/portal-events.jsonl"

run_case retries success PUBLISHED 429,500,200 5
[[ $CASE_STATUS -eq 0 ]] || { echo "FATAL: bounded status retry sequence failed" >&2; exit 1; }

run_case failed success FAILED 200 2
[[ $CASE_STATUS -ne 0 ]] || { echo "FATAL: FAILED deployment was accepted" >&2; exit 1; }

run_case unknown success SURPRISE 200 2
[[ $CASE_STATUS -ne 0 ]] || { echo "FATAL: unknown deployment state was accepted" >&2; exit 1; }

run_case timeout success PENDING 200 2
[[ $CASE_STATUS -ne 0 ]] || { echo "FATAL: non-terminal deployment did not time out" >&2; exit 1; }

run_case malformed malformed PUBLISHED 200 2
[[ $CASE_STATUS -ne 0 ]] || { echo "FATAL: malformed deployment ID was accepted" >&2; exit 1; }

run_case ambiguous ambiguous PUBLISHED 200 2
[[ $CASE_STATUS -ne 0 ]] || { echo "FATAL: ambiguous upload was accepted" >&2; exit 1; }
[[ "$(cat "$WORK_DIR/state/upload-count")" == "1" ]] || { echo "FATAL: ambiguous upload was retried" >&2; exit 1; }

run_case unauthorized unauthorized PUBLISHED 200 2
[[ $CASE_STATUS -ne 0 ]] || { echo "FATAL: unauthorized upload was accepted" >&2; exit 1; }

echo "RESULT: PASS — Portal upload, state, retry, timeout, ambiguity, and secret-safety cases passed"
