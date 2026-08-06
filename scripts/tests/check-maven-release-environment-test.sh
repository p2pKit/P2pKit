#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="$ROOT/scripts/check-maven-release-environment.sh"
FUTURE_YEAR=$((10#$(date -u '+%Y') + 2))
FUTURE_ROTATION="$(printf '%04d-12-31' "$FUTURE_YEAR")"
USERNAME="synthetic-user"
PASSWORD="synthetic-password"
KEY="synthetic-base64-key"
KEY_PASSWORD="synthetic-key-password"
FINGERPRINT="0123456789ABCDEF0123456789ABCDEF01234567"
NAMESPACE="io.github.apdelrahman1911"

bash -n "$SCRIPT"
MAVEN_CENTRAL_USERNAME="$USERNAME" \
MAVEN_CENTRAL_PASSWORD="$PASSWORD" \
MAVEN_SIGNING_KEY_B64="$KEY" \
MAVEN_SIGNING_PASSWORD="$KEY_PASSWORD" \
MAVEN_CENTRAL_NAMESPACE="$NAMESPACE" \
MAVEN_SIGNING_KEY_FINGERPRINT="$FINGERPRINT" \
MAVEN_CENTRAL_TOKEN_ROTATE_BY="$FUTURE_ROTATION" \
    "$SCRIPT" >"${TMPDIR:-/tmp}/p2pkit-release-environment-test.log"

for secret in "$USERNAME" "$PASSWORD" "$KEY" "$KEY_PASSWORD"; do
    if grep -Fq -- "$secret" "${TMPDIR:-/tmp}/p2pkit-release-environment-test.log"; then
        echo "FATAL: release environment checker leaked credential material" >&2
        exit 1
    fi
done

if MAVEN_CENTRAL_USERNAME= \
    MAVEN_CENTRAL_PASSWORD="$PASSWORD" \
    MAVEN_SIGNING_KEY_B64="$KEY" \
    MAVEN_SIGNING_PASSWORD="$KEY_PASSWORD" \
    MAVEN_CENTRAL_NAMESPACE="$NAMESPACE" \
    MAVEN_SIGNING_KEY_FINGERPRINT="$FINGERPRINT" \
    MAVEN_CENTRAL_TOKEN_ROTATE_BY="$FUTURE_ROTATION" \
    "$SCRIPT" >/dev/null 2>&1; then
    echo "FATAL: missing release credential was accepted" >&2
    exit 1
fi

if MAVEN_CENTRAL_USERNAME="$USERNAME" \
    MAVEN_CENTRAL_PASSWORD="$PASSWORD" \
    MAVEN_SIGNING_KEY_B64="$KEY" \
    MAVEN_SIGNING_PASSWORD="$KEY_PASSWORD" \
    MAVEN_CENTRAL_NAMESPACE="$NAMESPACE" \
    MAVEN_SIGNING_KEY_FINGERPRINT=bad \
    MAVEN_CENTRAL_TOKEN_ROTATE_BY="$FUTURE_ROTATION" \
    "$SCRIPT" >/dev/null 2>&1; then
    echo "FATAL: malformed public fingerprint was accepted" >&2
    exit 1
fi

if MAVEN_CENTRAL_USERNAME="$USERNAME" \
    MAVEN_CENTRAL_PASSWORD="$PASSWORD" \
    MAVEN_SIGNING_KEY_B64="$KEY" \
    MAVEN_SIGNING_PASSWORD="$KEY_PASSWORD" \
    MAVEN_CENTRAL_NAMESPACE=io.github.p2pkit \
    MAVEN_SIGNING_KEY_FINGERPRINT="$FINGERPRINT" \
    MAVEN_CENTRAL_TOKEN_ROTATE_BY="$FUTURE_ROTATION" \
    "$SCRIPT" >/dev/null 2>&1; then
    echo "FATAL: unapproved Maven Central namespace was accepted" >&2
    exit 1
fi

echo "RESULT: PASS — release environment fails closed without exposing secrets"
