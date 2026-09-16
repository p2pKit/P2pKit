#!/usr/bin/env bash
# Build a signed, checksummed Central Publisher Portal upload bundle.
# This command never performs a network upload.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(sed -n 's/^VERSION_NAME=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
GROUP="$(sed -n 's/^GROUP=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"

usage() {
    cat <<EOF
Usage: scripts/build-central-portal-bundle.sh [absolute-or-relative-output.zip]

Requires exactly one of ORG_GRADLE_PROJECT_signingInMemoryKey or
ORG_GRADLE_PROJECT_signingInMemoryKeyBase64, plus
ORG_GRADLE_PROJECT_signingInMemoryKeyPassword and the public
MAVEN_SIGNING_KEY_FINGERPRINT. The output is created locally and never uploaded.
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

decode_base64_file() {
    local encoded="$1" destination="$2"
    if printf '%s' "$encoded" | base64 --decode >"$destination" 2>/dev/null; then
        return
    fi
    if printf '%s' "$encoded" | base64 -D >"$destination" 2>/dev/null; then
        return
    fi
    fail "MAVEN signing key is not valid base64"
}

file_size() {
    local file="$1"
    if stat -f '%z' "$file" >/dev/null 2>&1; then
        stat -f '%z' "$file"
    else
        stat -c '%s' "$file"
    fi
}

valid_signature_fingerprint() {
    local status="$1"
    awk '$2 == "VALIDSIG" && fingerprint == "" { fingerprint = toupper($3) }
         END { if (fingerprint != "") print fingerprint }' <<<"$status"
}

[[ -n "$VERSION" && -n "$GROUP" ]] || fail "GROUP/VERSION_NAME is missing from gradle.properties"
[[ "$VERSION" != *-SNAPSHOT ]] || fail "Central release bundle cannot use a SNAPSHOT version"

plain_key="${ORG_GRADLE_PROJECT_signingInMemoryKey:-}"
base64_key="${ORG_GRADLE_PROJECT_signingInMemoryKeyBase64:-}"
if [[ -n "$plain_key" && -n "$base64_key" ]]; then
    fail "configure only one in-memory signing-key representation"
fi
[[ -n "$plain_key" || -n "$base64_key" ]] || fail "an in-memory signing key is required"
[[ -n "${ORG_GRADLE_PROJECT_signingInMemoryKeyPassword:-}" ]] ||
    fail "ORG_GRADLE_PROJECT_signingInMemoryKeyPassword is required"
expected_fingerprint="$(printf '%s' "${MAVEN_SIGNING_KEY_FINGERPRINT:-}" | tr -d '[:space:]' | tr '[:lower:]' '[:upper:]')"
[[ "$expected_fingerprint" =~ ^[A-F0-9]{40}$|^[A-F0-9]{64}$ ]] ||
    fail "MAVEN_SIGNING_KEY_FINGERPRINT must be a complete 40- or 64-hex fingerprint"

for command in base64 gpg gpgconf jq openssl unzip zip; do
    command -v "$command" >/dev/null 2>&1 || fail "$command is required"
done

OUTPUT="${1:-$ROOT/build/central/p2pkit-$VERSION-central-bundle.zip}"
if [[ "$OUTPUT" != /* ]]; then
    OUTPUT="$(pwd)/$OUTPUT"
fi
[[ "$OUTPUT" == *.zip ]] || fail "output must have a .zip extension: $OUTPUT"
MANIFEST="${OUTPUT%.zip}.manifest.sha256"
SUMMARY="${OUTPUT%.zip}.summary.json"
for output_file in "$OUTPUT" "$MANIFEST" "$SUMMARY"; do
    [[ ! -e "$output_file" ]] || fail "refusing to overwrite existing output: $output_file"
done

AUDIT="${P2PKIT_CENTRAL_BUNDLE_AUDIT:-0}"
[[ "$AUDIT" == 0 || "$AUDIT" == 1 ]] || fail "invalid Central bundle audit opt-in"
REPOSITORY=""
GNUPGHOME=""
AUDIT_ADMITTED=0
METADATA="$ROOT/scripts/prepare-audit-central-bundle-metadata.py"
cleanup_bundle() {
    local status=$? stop_status=0 final
    final="$status"
    trap - EXIT
    trap '' HUP INT TERM
    if [[ "$AUDIT" == 1 ]]; then
        if [[ "$AUDIT_ADMITTED" == 1 ]]; then
            if [[ -n "$GNUPGHOME" ]]; then
                python3 "$METADATA" stop --role verifier || stop_status=$?
            fi
            python3 "$METADATA" finish-builder --status "$status" || final=125
            [[ "$stop_status" == 0 ]] || final=125
            # The outer regression/controller retains and retires borrowed work.
            # gpgconf success alone does not establish native retirement.
        fi
    else
        if [[ -n "$GNUPGHOME" ]]; then
            gpgconf --homedir "$GNUPGHOME" --kill all >/dev/null 2>&1 || stop_status=$?
        fi
        if [[ "$stop_status" == 0 ]]; then
            [[ -z "$GNUPGHOME" ]] || rm -rf -- "$GNUPGHOME" || stop_status=$?
            [[ -z "$REPOSITORY" ]] || rm -rf -- "$REPOSITORY" || stop_status=$?
        fi
        if [[ "$stop_status" != 0 ]]; then
            echo "FATAL: bundle cleanup failed; owned repository/GPG home retained: $REPOSITORY / $GNUPGHOME" >&2
            [[ "$final" != 0 ]] || final=125
        fi
    fi
    exit "$final"
}
trap cleanup_bundle EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
if [[ "$AUDIT" == 1 ]]; then
    ADMITTED_ROOT="$(python3 "$METADATA" builder --root "$ROOT" --output "$OUTPUT")"
    AUDIT_ADMITTED=1
    REPOSITORY="$P2PKIT_CENTRAL_BUNDLE_WORK_DIR/repository"
    GNUPGHOME="$(python3 "$METADATA" home --role verifier)"
else
    REPOSITORY="$(mktemp -d "${P2PKIT_RELEASE_TMPDIR:-/tmp}/p2pkit-central-bundle.XXXXXX")"
    GNUPGHOME="$(mktemp -d "${P2PKIT_GPG_TMPDIR:-/tmp}/p2pkit-gpg.XXXXXX")"
    GNUPGHOME="$(cd "$GNUPGHOME" && pwd -P)"
    socket="$GNUPGHOME/S.gpg-agent.browser"
    [[ "$(LC_ALL=C printf '%s' "$socket" | wc -c | tr -d '[:space:]')" -lt 103 ]] ||
        fail "GPG socket path is too long; set a shorter P2PKIT_GPG_TMPDIR"
    chmod 700 "$GNUPGHOME"
fi
KEY_FILE="$REPOSITORY/release-key.asc"
if [[ -n "$base64_key" ]]; then
    decode_base64_file "$base64_key" "$KEY_FILE"
else
    printf '%s' "$plain_key" >"$KEY_FILE"
fi
chmod 600 "$KEY_FILE"

actual_fingerprint="$(
    gpg --batch --homedir "$GNUPGHOME" --show-keys --with-colons "$KEY_FILE" 2>/dev/null |
        awk -F: '$1 == "fpr" && fingerprint == "" { fingerprint = toupper($10) }
                 END { if (fingerprint != "") print fingerprint }'
)"
[[ -n "$actual_fingerprint" ]] || fail "could not read a fingerprint from the signing key"
[[ "$actual_fingerprint" == "$expected_fingerprint" ]] ||
    fail "signing key fingerprint does not match MAVEN_SIGNING_KEY_FINGERPRINT"

echo "==> Publishing signed $GROUP:*:$VERSION into an isolated repository"
signing_isolation_args=()
if [[ -n "$base64_key" ]]; then
    # Override any legacy user-level plaintext Gradle property without reading it.
    signing_isolation_args+=("-PsigningInMemoryKey=")
else
    signing_isolation_args+=("-PsigningInMemoryKeyBase64=")
fi
if [[ "$AUDIT" == 1 ]]; then
    # The helper binds the entire version-only derivative and the exact nested
    # request/receipt. The canonical admitted-root wrapper selects it with -p;
    # it also supplies strict/fresh flags, same-home stop and native ownership.
    python3 "$ADMITTED_ROOT/scripts/prepare-audit-central-bundle-metadata.py" publish
else
(
    cd "$ROOT"
    # Release signatures are key-specific outputs, but Gradle's Sign task does
    # not safely encode private key material into cache/up-to-date identities.
    # Rebuild in an ephemeral daemon with caches disabled so a prior local key
    # rotation or reused local build state cannot contribute stale .asc files
    # to the immutable Central bundle. Release builds must not run concurrently
    # in the same worktree.
    ./gradlew --no-daemon --no-build-cache --rerun-tasks --console=plain \
        publishToMavenLocal \
        "${signing_isolation_args[@]}" \
        -PreleasePublication=true \
        -Dmaven.repo.local="$REPOSITORY"
)
fi

"$ROOT/scripts/check-publish-artifacts.sh" "$REPOSITORY"

GROUP_PATH="${GROUP//.//}"
BASE="$REPOSITORY/$GROUP_PATH"
[[ -d "$BASE" ]] || fail "expected published group directory is missing: $BASE"

# Maven-local metadata is mutable repository state, not an immutable deployment.
find "$BASE" -type f -name 'maven-metadata*' -delete

gpg --batch --homedir "$GNUPGHOME" --import "$KEY_FILE" >/dev/null 2>&1 ||
    fail "could not import the release key into the isolated verification keyring"

unsigned=0
invalid_signature=0
checked=0
while IFS= read -r -d '' artifact; do
    signature="$artifact.asc"
    checked=$((checked + 1))
    if [[ ! -s "$signature" ]]; then
        echo "FAIL missing signature: ${artifact#"$REPOSITORY/"}" >&2
        unsigned=$((unsigned + 1))
        continue
    fi
    verify_status=0
    if [[ "$AUDIT" == 1 ]]; then
        status_file="$P2PKIT_CENTRAL_BUNDLE_WORK_DIR/signatures/$checked.status"
        gpg --batch --homedir "$GNUPGHOME" --status-fd 1 \
            --verify "$signature" "$artifact" >"$status_file" 2>"$status_file.stderr.log" || verify_status=$?
        status="$(cat "$status_file")"
    else
        status="$({
            gpg --batch --homedir "$GNUPGHOME" --status-fd 1 \
                --verify "$signature" "$artifact" 2>/dev/null
        } || true)"
    fi
    signature_fingerprint="$(valid_signature_fingerprint "$status")"
    if [[ "$AUDIT" == 1 ]]; then
        python3 "$METADATA" signature --artifact "${artifact#"$REPOSITORY/"}" --status-file "$status_file" \
            --status "$verify_status" --fingerprint "$signature_fingerprint"
    fi
    if [[ "$signature_fingerprint" != "$expected_fingerprint" || "$verify_status" != 0 ]]; then
        echo "FAIL invalid or unexpected signature: ${artifact#"$REPOSITORY/"}" >&2
        invalid_signature=$((invalid_signature + 1))
    fi
done < <(
    find "$BASE" -type f \
        ! -name '*.asc' \
        ! -name '*.md5' \
        ! -name '*.sha1' \
        ! -name '*.sha256' \
        ! -name '*.sha512' \
        -print0
)

[[ $checked -gt 0 ]] || fail "no publication files found under $BASE"
[[ $unsigned -eq 0 ]] || fail "$unsigned of $checked publication files lack PGP signatures"
[[ $invalid_signature -eq 0 ]] ||
    fail "$invalid_signature of $checked publication files have invalid or unexpected signatures"

echo "==> Generating Central-required checksums"
while IFS= read -r -d '' artifact; do
    for algorithm in md5 sha1 sha256 sha512; do
        digest="$(openssl dgst "-$algorithm" "$artifact" | awk '{print $NF}')"
        [[ -n "$digest" ]] || fail "failed to calculate $algorithm for $artifact"
        printf '%s\n' "$digest" >"$artifact.$algorithm"
    done
done < <(
    find "$BASE" -type f \
        ! -name '*.asc' \
        ! -name '*.md5' \
        ! -name '*.sha1' \
        ! -name '*.sha256' \
        ! -name '*.sha512' \
        -print0
)

mkdir -p "$(dirname "$OUTPUT")"
: >"$MANIFEST"
while IFS= read -r artifact; do
    relative="${artifact#"$REPOSITORY/"}"
    digest="$(openssl dgst -sha256 "$artifact" | awk '{print $NF}')"
    printf '%s  %s\n' "$digest" "$relative" >>"$MANIFEST"
done < <(find "$BASE" -type f | LC_ALL=C sort)

(
    cd "$REPOSITORY"
    zip -X -q -r "$OUTPUT" "$GROUP_PATH"
)
unzip -tq "$OUTPUT" >/dev/null

BUNDLE_SIZE="$(file_size "$OUTPUT")"
[[ "$BUNDLE_SIZE" -lt 1073741824 ]] || fail "Central bundle exceeds the 1 GiB upload limit"
BUNDLE_SHA256="$(openssl dgst -sha256 "$OUTPUT" | awk '{print $NF}')"
jq -n \
    --arg group "$GROUP" \
    --arg version "$VERSION" \
    --arg signingKeyFingerprint "$expected_fingerprint" \
    --arg bundleFile "$(basename "$OUTPUT")" \
    --arg bundleSha256 "$BUNDLE_SHA256" \
    --argjson bundleSizeBytes "$BUNDLE_SIZE" \
    --argjson signedFiles "$checked" \
    '{
        schemaVersion: 1,
        group: $group,
        version: $version,
        signingKeyFingerprint: $signingKeyFingerprint,
        bundleFile: $bundleFile,
        bundleSha256: $bundleSha256,
        bundleSizeBytes: $bundleSizeBytes,
        signedFiles: $signedFiles
    }' >"$SUMMARY"

if [[ "$AUDIT" == 1 ]]; then
    echo "Signed disposable Central bundle created (not uploaded); enclosing retention/retirement pending"
else
    echo "RESULT: PASS — signed Central Portal bundle created (not uploaded)"
fi
echo "Bundle: $OUTPUT"
echo "Manifest: $MANIFEST"
echo "Summary: $SUMMARY"
echo "SHA-256: $BUNDLE_SHA256"
