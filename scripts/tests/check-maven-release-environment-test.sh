#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="$ROOT/scripts/check-maven-release-environment.sh"
USERNAME="synthetic-user"
PASSWORD="synthetic-password"
KEY="synthetic-base64-key"
KEY_PASSWORD="synthetic-key-password"
FINGERPRINT="0123456789ABCDEF0123456789ABCDEF01234567"
NAMESPACE="io.github.apdelrahman1911"
umask 077
work="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-release-environment-test.XXXXXX")"
trap 'rm -rf -- "$work"' EXIT

bash -n "$SCRIPT"
checks=0
run_case() {
    local label="$1" expected="$2" actual log
    shift 2
    log="$work/$label.log"
    if (
        export MAVEN_CENTRAL_USERNAME="$USERNAME"
        export MAVEN_CENTRAL_PASSWORD="$PASSWORD"
        export MAVEN_SIGNING_KEY_B64="$KEY"
        export MAVEN_SIGNING_PASSWORD="$KEY_PASSWORD"
        export MAVEN_CENTRAL_NAMESPACE="$NAMESPACE"
        export MAVEN_SIGNING_KEY_FINGERPRINT="$FINGERPRINT"
        unset MAVEN_CENTRAL_TOKEN_ROTATE_BY
        if [[ "$#" == 1 ]]; then unset "$1"
        elif [[ "$#" == 2 ]]; then export "$1=$2"; fi
        "$SCRIPT"
    ) >"$log" 2>&1; then actual=0
    else actual=$?; fi
    for secret in "$USERNAME" "$PASSWORD" "$KEY" "$KEY_PASSWORD"; do
        if grep -Fq -- "$secret" "$log"; then
            echo "FATAL: release environment checker leaked credential material" >&2
            exit 1
        fi
    done
    if [[ "$actual" != "$expected" ]]; then
        echo "FATAL: unexpected release environment result for $label" >&2
        exit 1
    fi
    if [[ "$expected" == 0 ]]; then
        grep -Fq 'RESULT: PASS' "$log"
    else
        grep -Fq 'FATAL:' "$log"
        if grep -Fq 'RESULT: PASS' "$log"; then
            echo "FATAL: failed release environment check reported success" >&2
            exit 1
        fi
    fi
    checks=$((checks + 1))
}

# Old calendar metadata has no effect, including when inherited by a local caller.
run_case rotation-absent 0
run_case rotation-blank 0 MAVEN_CENTRAL_TOKEN_ROTATE_BY ''
run_case rotation-past 0 MAVEN_CENTRAL_TOKEN_ROTATE_BY 2000-01-01
run_case rotation-malformed 0 MAVEN_CENTRAL_TOKEN_ROTATE_BY not-a-date
run_case rotation-invalid-calendar 0 MAVEN_CENTRAL_TOKEN_ROTATE_BY 2026-99-99
run_case rotation-future 0 MAVEN_CENTRAL_TOKEN_ROTATE_BY 9999-12-31

# Removing calendar policy must not remove any required credential-presence gate.
for name in MAVEN_CENTRAL_USERNAME MAVEN_CENTRAL_PASSWORD MAVEN_SIGNING_KEY_B64 MAVEN_SIGNING_PASSWORD; do
    run_case "$name-unset" 1 "$name"
    run_case "$name-blank" 1 "$name" ''
done
run_case fingerprint-malformed 1 MAVEN_SIGNING_KEY_FINGERPRINT bad
run_case fingerprint-unset 1 MAVEN_SIGNING_KEY_FINGERPRINT
run_case fingerprint-64 0 MAVEN_SIGNING_KEY_FINGERPRINT "${FINGERPRINT}0123456789ABCDEF01234567"
run_case namespace-wrong 1 MAVEN_CENTRAL_NAMESPACE io.github.p2pkit
run_case namespace-unset 1 MAVEN_CENTRAL_NAMESPACE

echo "RESULT: PASS — $checks release environment controls; no calendar expiry or credential leaks"
