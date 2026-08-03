#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="$ROOT/scripts/build-central-portal-bundle.sh"
WORK_DIR="$(mktemp -d "${P2PKIT_RELEASE_TMPDIR:-/tmp}/p2pkit-central-bundle-test.XXXXXX")"
PHASE="initialization"
cleanup() {
    status=$?
    if [[ $status -ne 0 ]]; then
        echo "FATAL: disposable-key bundle test failed during: $PHASE" >&2
    fi
    rm -rf "$WORK_DIR"
    exit "$status"
}
trap cleanup EXIT
OUTPUT="$WORK_DIR/p2pkit-test-central-bundle.zip"
GNUPGHOME="$WORK_DIR/gnupg"
PASSWORD="p2pkit-disposable-test-key"
mkdir -m 700 "$GNUPGHOME"

secret_appears_in_log() {
    local secret="$1" log="$2" offset=0 chunk
    if [[ ${#secret} -le 128 ]]; then
        grep -Fq -- "$secret" "$log"
        return
    fi
    while (( offset < ${#secret} )); do
        chunk="${secret:offset:128}"
        if [[ ${#chunk} -ge 32 ]] && grep -Fq -- "$chunk" "$log"; then
            return 0
        fi
        offset=$((offset + 128))
    done
    return 1
}

bash -n "$SCRIPT"
"$SCRIPT" --help >/dev/null

PHASE="missing-key rejection"
if env -u ORG_GRADLE_PROJECT_signingInMemoryKey \
    -u ORG_GRADLE_PROJECT_signingInMemoryKeyBase64 \
    -u ORG_GRADLE_PROJECT_signingInMemoryKeyPassword \
    -u MAVEN_SIGNING_KEY_FINGERPRINT \
    "$SCRIPT" "$OUTPUT" >/dev/null 2>&1; then
    echo "FATAL: bundle builder accepted a release without a signing key" >&2
    exit 1
fi

PHASE="disposable key generation"
gpg --batch --homedir "$GNUPGHOME" \
    --pinentry-mode loopback \
    --passphrase "$PASSWORD" \
    --quick-generate-key \
    "P2pKit disposable CI key <ci-test@p2pkit.dev>" rsa2048 sign 1d \
    >"$WORK_DIR/keygen.log" 2>&1 || {
        tail -n 20 "$WORK_DIR/keygen.log" >&2
        exit 1
    }
FINGERPRINT="$(
    gpg --batch --homedir "$GNUPGHOME" --with-colons --list-secret-keys 2>/dev/null |
        awk -F: '$1 == "fpr" { print toupper($10); exit }'
)"
[[ "$FINGERPRINT" =~ ^[A-F0-9]{40}$ ]] || {
    echo "FATAL: disposable signing-key fingerprint is invalid" >&2
    exit 1
}
PHASE="disposable key export"
gpg --batch --homedir "$GNUPGHOME" \
    --pinentry-mode loopback \
    --passphrase "$PASSWORD" \
    --armor --export-secret-keys "$FINGERPRINT" >"$WORK_DIR/key.asc"
KEY_BASE64="$(base64 <"$WORK_DIR/key.asc" | tr -d '\r\n')"

PHASE="signed bundle build"
ORG_GRADLE_PROJECT_signingInMemoryKeyBase64="$KEY_BASE64" \
ORG_GRADLE_PROJECT_signingInMemoryKeyPassword="$PASSWORD" \
MAVEN_SIGNING_KEY_FINGERPRINT="$FINGERPRINT" \
    "$SCRIPT" "$OUTPUT" >"$WORK_DIR/bundle.log" 2>&1 || bundle_status=$?

for secret in "$KEY_BASE64" "$PASSWORD"; do
    if secret_appears_in_log "$secret" "$WORK_DIR/bundle.log"; then
        echo "FATAL: bundle builder leaked disposable credential material" >&2
        exit 1
    fi
done

if [[ ${bundle_status:-0} -ne 0 ]]; then
    echo "FATAL: disposable-key bundle builder failed; sanitized tail follows" >&2
    tail -n 80 "$WORK_DIR/bundle.log" >&2
    exit "$bundle_status"
fi

PHASE="bundle verification"
unzip -tq "$OUTPUT" >/dev/null
[[ -s "${OUTPUT%.zip}.manifest.sha256" ]] || { echo "FATAL: bundle manifest is missing" >&2; exit 1; }
jq -e \
    --arg fingerprint "$FINGERPRINT" \
    '.schemaVersion == 1 and .signingKeyFingerprint == $fingerprint and .signedFiles > 0' \
    "${OUTPUT%.zip}.summary.json" >/dev/null

echo "RESULT: PASS — disposable-key signed bundle, signatures, checksums, manifest, and secret safety passed"
