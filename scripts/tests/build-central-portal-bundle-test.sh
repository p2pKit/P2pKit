#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORK_DIR="$(mktemp -d "${P2PKIT_RELEASE_TMPDIR:-/tmp}/p2pkit-central-bundle-test.XXXXXX")"
PHASE="initialization"
RELEASE_WORKTREE=""
cleanup() {
    status=$?
    if [[ $status -ne 0 ]]; then
        echo "FATAL: disposable-key bundle test failed during: $PHASE" >&2
    fi
    if [[ -n "$RELEASE_WORKTREE" ]]; then
        git -C "$ROOT" worktree remove --force "$RELEASE_WORKTREE" >/dev/null 2>&1 || true
    fi
    rm -rf "$WORK_DIR"
    exit "$status"
}
trap cleanup EXIT
OUTPUT="$WORK_DIR/p2pkit-test-central-bundle.zip"
GNUPGHOME="$WORK_DIR/gnupg"
PASSWORD="p2pkit-disposable-test-key"
GROUP="$(sed -n 's/^GROUP=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
VERSION="$(sed -n 's/^VERSION_NAME=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
mkdir -m 700 "$GNUPGHOME"

ORIGINAL_SCRIPT="$ROOT/scripts/build-central-portal-bundle.sh"
bash -n "$ORIGINAL_SCRIPT"
"$ORIGINAL_SCRIPT" --help >/dev/null

if [[ "$VERSION" == *-SNAPSHOT ]]; then
    PHASE="snapshot rejection"
    if env -u ORG_GRADLE_PROJECT_signingInMemoryKey \
        -u ORG_GRADLE_PROJECT_signingInMemoryKeyBase64 \
        -u ORG_GRADLE_PROJECT_signingInMemoryKeyPassword \
        -u MAVEN_SIGNING_KEY_FINGERPRINT \
        "$ORIGINAL_SCRIPT" "$OUTPUT" >"$WORK_DIR/snapshot.log" 2>&1; then
        echo "FATAL: bundle builder accepted a SNAPSHOT version" >&2
        exit 1
    fi
    grep -Fq 'cannot use a SNAPSHOT version' "$WORK_DIR/snapshot.log" || {
        echo "FATAL: bundle builder did not identify the SNAPSHOT rejection" >&2
        exit 1
    }

    PHASE="release fixture checkout"
    RELEASE_WORKTREE="$WORK_DIR/release-source"
    git -C "$ROOT" worktree add --detach "$RELEASE_WORKTREE" HEAD >/dev/null
    VERSION="9.8.7-rc6"
    sed -i.bak "s/^VERSION_NAME=.*/VERSION_NAME=$VERSION/" "$RELEASE_WORKTREE/gradle.properties"
    rm -f "$RELEASE_WORKTREE/gradle.properties.bak"
    if [[ -f "$ROOT/local.properties" ]]; then
        cp "$ROOT/local.properties" "$RELEASE_WORKTREE/local.properties"
    fi
    # Exercise the script under test, including uncommitted development edits,
    # against an otherwise clean non-SNAPSHOT release fixture.
    cp "$ORIGINAL_SCRIPT" "$RELEASE_WORKTREE/scripts/build-central-portal-bundle.sh"
    SCRIPT="$RELEASE_WORKTREE/scripts/build-central-portal-bundle.sh"
else
    SCRIPT="$ORIGINAL_SCRIPT"
fi

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

PHASE="signature-status parser regression"
PARSER_FINGERPRINT="0123456789ABCDEF0123456789ABCDEF01234567"
parser_body="$(
    awk '
        /^valid_signature_fingerprint\(\) \{/ { capture = 1 }
        capture { print }
        capture && /^\}/ { exit }
    ' "$SCRIPT"
)"
[[ -n "$parser_body" ]] || {
    echo "FATAL: bundle builder signature-status parser is missing" >&2
    exit 1
}
parser_output="$(
    bash -c "$parser_body
status=\$(printf '[GNUPG:] VALIDSIG %s 20260812 0 4 0 1 10 00\n' '$PARSER_FINGERPRINT';
         awk 'BEGIN { for (i = 0; i < 20000; i++) print \"[GNUPG:] NOTATION_DATA trailing-status\" }')
valid_signature_fingerprint \"\$status\""
)"
[[ "$parser_output" == "$PARSER_FINGERPRINT" ]] || {
    echo "FATAL: signature-status parser rejected a valid signature with trailing status" >&2
    exit 1
}

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
    "P2pKit disposable CI key <p2pkit-ci@users.noreply.github.com>" rsa2048 sign 1d \
    >"$WORK_DIR/keygen.log" 2>&1 || {
        tail -n 20 "$WORK_DIR/keygen.log" >&2
        exit 1
    }
FINGERPRINT="$(
    gpg --batch --homedir "$GNUPGHOME" --with-colons --list-secret-keys 2>/dev/null |
        awk -F: '$1 == "fpr" && fingerprint == "" { fingerprint = toupper($10) }
                 END { if (fingerprint != "") print fingerprint }'
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
    --arg group "$GROUP" \
    --arg version "$VERSION" \
    '.schemaVersion == 1 and .group == $group and .version == $version and
     .signingKeyFingerprint == $fingerprint and .signedFiles > 0' \
    "${OUTPUT%.zip}.summary.json" >/dev/null

echo "RESULT: PASS — disposable-key signed bundle, signatures, checksums, manifest, and secret safety passed"
