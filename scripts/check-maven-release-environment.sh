#!/usr/bin/env bash
# Validate production release credential presence and public metadata without
# printing any credential value.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GROUP="$(sed -n 's/^GROUP=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
EXPECTED_NAMESPACE="io.github.apdelrahman1911"

fail() {
    echo "FATAL: $*" >&2
    exit 1
}

for name in \
    MAVEN_CENTRAL_USERNAME \
    MAVEN_CENTRAL_PASSWORD \
    MAVEN_SIGNING_KEY_B64 \
    MAVEN_SIGNING_PASSWORD; do
    [[ -n "${!name:-}" ]] || fail "$name is required"
done

namespace="${MAVEN_CENTRAL_NAMESPACE:-}"
[[ "$namespace" == "$EXPECTED_NAMESPACE" ]] ||
    fail "MAVEN_CENTRAL_NAMESPACE must be the owner-verified namespace $EXPECTED_NAMESPACE"
[[ "$GROUP" == "$namespace" ]] ||
    fail "published GROUP does not match MAVEN_CENTRAL_NAMESPACE"

fingerprint="$(printf '%s' "${MAVEN_SIGNING_KEY_FINGERPRINT:-}" | tr -d '[:space:]' | tr '[:lower:]' '[:upper:]')"
[[ "$fingerprint" =~ ^[A-F0-9]{40}$|^[A-F0-9]{64}$ ]] ||
    fail "MAVEN_SIGNING_KEY_FINGERPRINT must be a complete 40- or 64-hex fingerprint"

echo "RESULT: PASS — required release credentials are present; namespace and fingerprint metadata are valid"
