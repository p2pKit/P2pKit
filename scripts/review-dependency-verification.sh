#!/usr/bin/env bash
# Independently review every artifact newly admitted to Gradle verification
# metadata against downloaded bytes and detached OpenPGP signatures. When a
# repository publishes a SHA-256 sidecar, that independent value must also
# agree; Maven Central does not consistently publish SHA-256 sidecars.
# This is a maintainer curation tool, not an automatic trust step.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE_REF="${1:-origin/main}"

fail() {
    echo "FATAL: $*" >&2
    exit 1
}

git -C "$ROOT" cat-file -e "$BASE_REF^{commit}" 2>/dev/null ||
    fail "base ref is not an available commit: $BASE_REF"
for command in curl gpg awk comm sort shasum; do
    command -v "$command" >/dev/null 2>&1 || fail "required review tool is missing: $command"
done

# Keep GNUPGHOME short enough for the agent's Unix-domain socket on macOS.
# The system TMPDIR path can already approach the platform socket limit.
work="$(mktemp -d "/tmp/p2pkit-dependency-review.XXXXXX")"
trap 'rm -rf "$work"' EXIT
chmod 700 "$work"
gnupg="$work/gnupg"
mkdir -p "$gnupg"
chmod 700 "$gnupg"

parse_metadata() {
    local source="$1" destination="$2"
    awk '
        /<component group=/ {
            split($0, fields, "\"")
            component = fields[2] "|" fields[4] "|" fields[6]
            next
        }
        /<artifact name=/ {
            split($0, fields, "\"")
            artifact = fields[2]
            next
        }
        /<sha256 value=/ {
            split($0, fields, "\"")
            print component "|" artifact "|" fields[2]
        }
    ' "$source" | LC_ALL=C sort -u >"$destination"
}

git -C "$ROOT" show "$BASE_REF:gradle/verification-metadata.xml" >"$work/base.xml"
parse_metadata "$work/base.xml" "$work/base.entries"
parse_metadata "$ROOT/gradle/verification-metadata.xml" "$work/current.entries"
comm -13 "$work/base.entries" "$work/current.entries" >"$work/new.entries"
[[ -s "$work/new.entries" ]] || fail "no new verified artifacts relative to $BASE_REF"

reviewed=0
while IFS='|' read -r group module version artifact expected_sha; do
    relative="${group//.//}/$module/$version/$artifact"
    case "$group" in
        com.android*|com.google*|androidx*)
            repositories=(
                "https://dl.google.com/dl/android/maven2"
                "https://repo.maven.apache.org/maven2"
                "https://plugins.gradle.org/m2"
            )
            ;;
        *)
            repositories=(
                "https://repo.maven.apache.org/maven2"
                "https://plugins.gradle.org/m2"
                "https://dl.google.com/dl/android/maven2"
            )
            ;;
    esac

    repository=""
    for candidate in "${repositories[@]}"; do
        if ! curl -fsSL --retry 5 --retry-all-errors --retry-delay 2 \
            --connect-timeout 20 --max-time 300 \
            -o "$work/artifact" "$candidate/$relative"; then
            continue
        fi
        if ! curl -fsSL --retry 5 --retry-all-errors --retry-delay 2 \
            --connect-timeout 20 --max-time 120 \
            -o "$work/artifact.asc" "$candidate/$relative.asc"; then
            continue
        fi
        repository="$candidate"
        break
    done
    [[ -n "$repository" ]] ||
        fail "no repository artifact and detached signature for $group:$module:$version:$artifact"

    actual_sha="$(shasum -a 256 "$work/artifact" | awk '{print $1}')"
    [[ "$actual_sha" == "$expected_sha" ]] ||
        fail "downloaded bytes disagree with metadata for $group:$module:$version:$artifact"

    checksum_evidence="signature-bound-bytes"
    if curl -fsSL --connect-timeout 20 --max-time 120 \
        -o "$work/remote.sha256" "$repository/$relative.sha256" 2>/dev/null; then
        remote_sha="$(grep -Eo '[0-9a-fA-F]{64}' "$work/remote.sha256" |
            head -1 | tr '[:upper:]' '[:lower:]')"
        [[ "$remote_sha" == "$expected_sha" ]] ||
            fail "repository checksum disagrees with metadata for $group:$module:$version:$artifact"
        checksum_evidence="sha256-sidecar+signature"
    fi

    fingerprint="$(gpg --batch --list-packets "$work/artifact.asc" 2>/dev/null |
        sed -n 's/.*issuer fpr v[0-9][[:space:]]\([0-9A-F]*\)).*/\1/p' | head -1)"
    [[ "$fingerprint" =~ ^[0-9A-F]{40}$|^[0-9A-F]{64}$ ]] ||
        fail "signature has no issuer fingerprint for $group:$module:$version:$artifact"
    if ! GNUPGHOME="$gnupg" gpg --batch --list-keys "$fingerprint" >/dev/null 2>&1; then
        key_downloaded=false
        for key_url in \
            "https://keyserver.ubuntu.com/pks/lookup?op=get&options=mr&search=0x$fingerprint" \
            "https://keys.openpgp.org/vks/v1/by-fingerprint/$fingerprint"; do
            if ! curl -fsSL --retry 5 --retry-all-errors --retry-delay 2 \
                --connect-timeout 20 --max-time 120 \
                -o "$work/signing-key.asc" "$key_url"; then
                continue
            fi
            if ! gpg --batch --show-keys --with-colons "$work/signing-key.asc" 2>/dev/null |
                sed -n 's/^fpr:::::::::\([^:]*\):/\1/p' |
                grep -Fxq "$fingerprint"; then
                continue
            fi
            if ! import_output="$(GNUPGHOME="$gnupg" gpg --batch --import \
                "$work/signing-key.asc" 2>&1)"; then
                fail "could not import the exact signing key $fingerprint: $import_output"
            fi
            key_downloaded=true
            break
        done
        [[ "$key_downloaded" == true ]] ||
            fail "could not retrieve the exact signing key $fingerprint over HTTPS"
    fi
    verification="$(GNUPGHOME="$gnupg" gpg --batch --status-fd 1 \
        --verify "$work/artifact.asc" "$work/artifact" 2>&1)" ||
        fail "invalid detached signature for $group:$module:$version:$artifact"
    grep -Fq "[GNUPG:] VALIDSIG $fingerprint " <<<"$verification" ||
        fail "signature fingerprint mismatch for $group:$module:$version:$artifact"

    printf 'REVIEWED %s:%s:%s %s sha256=%s signer=%s evidence=%s repository=%s\n' \
        "$group" "$module" "$version" "$artifact" "$expected_sha" "$fingerprint" \
        "$checksum_evidence" "$repository"
    reviewed=$((reviewed + 1))
done <"$work/new.entries"

echo "RESULT: PASS — reviewed $reviewed newly admitted artifacts by exact SHA-256 and OpenPGP signature; repository SHA-256 sidecars also matched wherever published"
