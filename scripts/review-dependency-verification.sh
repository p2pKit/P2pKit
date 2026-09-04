#!/usr/bin/env bash
# Independently review every artifact newly admitted to Gradle verification
# metadata against downloaded bytes and publisher provenance. Detached OpenPGP
# signatures remain the default. A version-specific checked-in policy may use
# GitHub artifact attestations for a canonical plugin implementation JAR;
# unsigned marker/module metadata is accepted only after strict semantic
# validation binds it to that attested JAR and the locked dependency graph.
# When a repository publishes a SHA-256 sidecar, it must also agree.
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
for command in curl gh gpg awk comm sort shasum; do
    command -v "$command" >/dev/null 2>&1 || fail "required review tool is missing: $command"
done
PYTHON3="${P2PKIT_PYTHON3:-/usr/bin/python3}"
if [[ ! -x "$PYTHON3" ]] || ! "$PYTHON3" -c 'import json, xml.etree.ElementTree' 2>/dev/null; then
    PYTHON3="$(command -v python3 || true)"
fi
[[ -n "$PYTHON3" ]] && "$PYTHON3" -c 'import json, xml.etree.ElementTree' 2>/dev/null ||
    fail "a working Python 3 with JSON and XML support is required"

provenance_policy="$ROOT/gradle/plugin-provenance-policy.txt"
[[ -f "$provenance_policy" ]] || fail "missing Gradle plugin provenance policy"

# Keep GNUPGHOME short enough for the agent's Unix-domain socket on macOS.
# The system TMPDIR path can already approach the platform socket limit.
work="$(mktemp -d "/tmp/p2pkit-dependency-review.XXXXXX")"
trap 'rm -rf "$work"' EXIT
chmod 700 "$work"
gnupg="$work/gnupg"
mkdir -p "$gnupg"
chmod 700 "$gnupg"
marker_requirements="$work/marker.requirements"
module_requirements="$work/module.requirements"
trusted_implementations="$work/trusted.implementations"
: >"$marker_requirements"
: >"$module_requirements"
: >"$trusted_implementations"

lookup_provenance_policy() {
    local group="$1" module="$2" version="$3" matches
    matches="$(awk -F'|' -v group="$group" -v module="$module" -v version="$version" '
        /^[[:space:]]*#/ || /^[[:space:]]*$/ { next }
        NF != 7 { print "MALFORMED"; next }
        $1 == group && $2 == module && $3 == version { print }
    ' "$provenance_policy")"
    [[ "$matches" != *MALFORMED* ]] || fail "malformed Gradle plugin provenance policy"
    [[ "$(printf '%s\n' "$matches" | grep -c . || true)" -eq 1 ]] || return 1
    printf '%s\n' "$matches"
}

while IFS='|' read -r policy_group policy_module policy_version policy_repo \
    policy_workflow policy_ref policy_digest extra; do
    [[ -z "$policy_group" || "$policy_group" == \#* ]] && continue
    [[ -z "${extra:-}" ]] || fail "malformed Gradle plugin provenance policy"
    [[ "$policy_group" =~ ^[A-Za-z0-9_.-]+$ &&
        "$policy_module" =~ ^[A-Za-z0-9_.-]+$ &&
        "$policy_version" =~ ^[A-Za-z0-9_.-]+$ ]] ||
        fail "invalid component in Gradle plugin provenance policy"
    [[ "$policy_repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] ||
        fail "invalid repository in Gradle plugin provenance policy"
    [[ "$policy_workflow" =~ ^${policy_repo}/\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml$ ]] ||
        fail "invalid signer workflow in Gradle plugin provenance policy"
    [[ "$policy_ref" =~ ^refs/tags/[A-Za-z0-9._/-]+$ ]] ||
        fail "plugin provenance policy must pin a release tag"
    [[ "$policy_digest" =~ ^[0-9a-f]{40}$|^[0-9a-f]{64}$ ]] ||
        fail "plugin provenance policy must pin a source digest"
done <"$provenance_policy"

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

matching_key_fingerprints() {
    local listing="$1" reference_type="$2" reference="$3"
    printf '%s\n' "$listing" | awk -F: -v type="$reference_type" -v expected="$reference" '
        $1 == "pub" || $1 == "sub" {
            key_id = toupper($5)
            next
        }
        $1 == "fpr" {
            fingerprint = toupper($10)
            if ((type == "fingerprint" && fingerprint == expected) ||
                (type == "keyid" && key_id == expected &&
                    substr(fingerprint, length(fingerprint) - 15) == expected)) {
                print fingerprint
            }
            key_id = ""
        }
    ' | LC_ALL=C sort -u
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
        repository="$candidate"
        break
    done
    [[ -n "$repository" ]] ||
        fail "no repository artifact for $group:$module:$version:$artifact"

    actual_sha="$(shasum -a 256 "$work/artifact" | awk '{print $1}')"
    [[ "$actual_sha" == "$expected_sha" ]] ||
        fail "downloaded bytes disagree with metadata for $group:$module:$version:$artifact"

    checksum_evidence="signature-bound-bytes"
    rm -f "$work/remote.sha256"
    if curl -fsSL --connect-timeout 20 --max-time 120 \
        -o "$work/remote.sha256" "$repository/$relative.sha256" 2>/dev/null; then
        remote_sha="$(grep -Eo '[0-9a-fA-F]{64}' "$work/remote.sha256" |
            head -1 | tr '[:upper:]' '[:lower:]')"
        [[ "$remote_sha" == "$expected_sha" ]] ||
            fail "repository checksum disagrees with metadata for $group:$module:$version:$artifact"
        checksum_evidence="sha256-sidecar+signature"
    fi

    rm -f "$work/artifact.asc"
    if ! curl -fsSL --retry 5 --retry-all-errors --retry-delay 2 \
        --connect-timeout 20 --max-time 120 \
        -o "$work/artifact.asc" "$repository/$relative.asc"; then
        expected_marker="$module-$version.pom"
        expected_jar="$module-$version.jar"
        expected_module="$module-$version.module"
        if [[ "$module" == "$group.gradle.plugin" && "$artifact" == "$expected_marker" ]]; then
            implementation="$("$ROOT/scripts/validate-gradle-plugin-marker.sh" \
                "$work/artifact" "$group" "$module" "$version" \
                "$work/current.entries" "$ROOT/buildscript-gradle.lockfile")"
            printf '%s\n' "$implementation" >>"$marker_requirements"
            printf 'REVIEWED %s:%s:%s %s sha256=%s signer=none evidence=semantic-marker+trusted-implementation-pending repository=%s\n' \
                "$group" "$module" "$version" "$artifact" "$expected_sha" "$repository"
            reviewed=$((reviewed + 1))
            continue
        fi

        policy="$(lookup_provenance_policy "$group" "$module" "$version" || true)"
        [[ -n "$policy" ]] ||
            fail "no detached signature or approved provenance for $group:$module:$version:$artifact"
        IFS='|' read -r _ _ _ attestation_repo attestation_workflow \
            attestation_ref attestation_digest <<<"$policy"

        if [[ "$artifact" == "$expected_jar" ]]; then
            attestation_json="$work/attestation.json"
            gh attestation verify "$work/artifact" \
                --hostname github.com \
                --repo "$attestation_repo" \
                --signer-workflow "$attestation_workflow" \
                --source-ref "$attestation_ref" \
                --source-digest "$attestation_digest" \
                --cert-oidc-issuer "https://token.actions.githubusercontent.com" \
                --deny-self-hosted-runners \
                --format json >"$attestation_json" ||
                fail "GitHub provenance verification failed for $group:$module:$version:$artifact"
            "$PYTHON3" "$ROOT/scripts/validate-gradle-plugin-metadata.py" attestation \
                "$attestation_json" "$expected_sha" "$attestation_repo" \
                "$attestation_workflow" "$attestation_ref" "$attestation_digest"
            printf '%s|%s|%s\n' "$group" "$module" "$version" >>"$trusted_implementations"
            printf 'REVIEWED %s:%s:%s %s sha256=%s signer=%s evidence=github-slsa-provenance repository=%s\n' \
                "$group" "$module" "$version" "$artifact" "$expected_sha" \
                "$attestation_workflow@$attestation_ref" "$repository"
            reviewed=$((reviewed + 1))
            continue
        fi

        if [[ "$artifact" == "$expected_module" ]]; then
            jar_sha="$(awk -F'|' -v group="$group" -v module="$module" -v version="$version" \
                -v artifact="$expected_jar" '
                $1 == group && $2 == module && $3 == version && $4 == artifact { print $5 }
            ' "$work/current.entries")"
            [[ "$jar_sha" =~ ^[0-9a-f]{64}$ ]] ||
                fail "plugin module has no unique implementation JAR checksum: $group:$module:$version"
            implementation="$("$PYTHON3" "$ROOT/scripts/validate-gradle-plugin-metadata.py" module \
                "$work/artifact" "$group" "$module" "$version" "$jar_sha" \
                "$work/current.entries" "$ROOT/buildscript-gradle.lockfile")"
            printf '%s\n' "$implementation" >>"$module_requirements"
            printf 'REVIEWED %s:%s:%s %s sha256=%s signer=none evidence=semantic-module+attested-jar-pending repository=%s\n' \
                "$group" "$module" "$version" "$artifact" "$expected_sha" "$repository"
            reviewed=$((reviewed + 1))
            continue
        fi

        fail "no detached signature or approved provenance for $group:$module:$version:$artifact"
    fi

    packet_output="$(gpg --batch --list-packets "$work/artifact.asc" 2>/dev/null)" ||
        fail "detached signature packet is malformed for $group:$module:$version:$artifact"
    [[ "$(grep -c '^:signature packet:' <<<"$packet_output" || true)" -eq 1 ]] ||
        fail "detached signature must contain exactly one signature packet for $group:$module:$version:$artifact"
    issuer_fingerprints="$(sed -n \
        's/.*issuer fpr v[0-9][[:space:]]\([0-9A-Fa-f]*\)).*/\1/p' \
        <<<"$packet_output" | tr '[:lower:]' '[:upper:]' | LC_ALL=C sort -u)"
    issuer_key_ids="$(sed -n \
        -e 's/.*issuer key ID \([0-9A-Fa-f]*\)).*/\1/p' \
        -e 's/^:signature packet:.* keyid \([0-9A-Fa-f]*\)$/\1/p' \
        <<<"$packet_output" | tr '[:lower:]' '[:upper:]' | LC_ALL=C sort -u)"
    fingerprint_count="$(grep -c . <<<"$issuer_fingerprints" || true)"
    key_id_count="$(grep -c . <<<"$issuer_key_ids" || true)"
    if [[ "$fingerprint_count" -eq 1 &&
        "$issuer_fingerprints" =~ ^[0-9A-F]{40}$|^[0-9A-F]{64}$ ]]; then
        reference_type="fingerprint"
        issuer_reference="$issuer_fingerprints"
        if [[ "$key_id_count" -gt 1 ]]; then
            fail "signature contains conflicting issuer key IDs for $group:$module:$version:$artifact"
        fi
        if [[ "$key_id_count" -eq 1 &&
            "$issuer_reference" != *"$issuer_key_ids" ]]; then
            fail "signature issuer fingerprint and key ID disagree for $group:$module:$version:$artifact"
        fi
    elif [[ "$fingerprint_count" -eq 0 && "$key_id_count" -eq 1 &&
        "$issuer_key_ids" =~ ^[0-9A-F]{16}$ ]]; then
        reference_type="keyid"
        issuer_reference="$issuer_key_ids"
    else
        fail "signature has no unambiguous issuer identity for $group:$module:$version:$artifact"
    fi

    existing_listing="$(GNUPGHOME="$gnupg" gpg --batch --with-colons \
        --with-subkey-fingerprint --list-keys "$issuer_reference" 2>/dev/null || true)"
    matching_fingerprints="$(matching_key_fingerprints \
        "$existing_listing" "$reference_type" "$issuer_reference")"
    if [[ "$(grep -c . <<<"$matching_fingerprints" || true)" -ne 1 ]]; then
        key_downloaded=false
        key_urls=(
            "https://keyserver.ubuntu.com/pks/lookup?op=get&options=mr&search=0x$issuer_reference"
        )
        if [[ "$reference_type" == "fingerprint" ]]; then
            key_urls+=("https://keys.openpgp.org/vks/v1/by-fingerprint/$issuer_reference")
        else
            key_urls+=("https://keys.openpgp.org/vks/v1/by-keyid/$issuer_reference")
        fi
        for key_url in "${key_urls[@]}"; do
            if ! curl -fsSL --retry 5 --retry-all-errors --retry-delay 2 \
                --connect-timeout 20 --max-time 120 \
                -o "$work/signing-key.asc" "$key_url"; then
                continue
            fi
            key_listing="$(gpg --batch --show-keys --with-colons \
                --with-subkey-fingerprint "$work/signing-key.asc" 2>/dev/null || true)"
            matching_fingerprints="$(matching_key_fingerprints \
                "$key_listing" "$reference_type" "$issuer_reference")"
            if [[ "$(grep -c . <<<"$matching_fingerprints" || true)" -ne 1 ]]; then
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
            fail "could not retrieve one exact signing key for $issuer_reference over HTTPS"
    fi
    fingerprint="$matching_fingerprints"
    verification="$(GNUPGHOME="$gnupg" gpg --batch --status-fd 1 \
        --verify "$work/artifact.asc" "$work/artifact" 2>&1)" ||
        fail "invalid detached signature for $group:$module:$version:$artifact"
    valid_fingerprints="$(sed -n 's/^\[GNUPG:\] VALIDSIG \([^ ]*\) .*/\1/p' \
        <<<"$verification" | tr '[:lower:]' '[:upper:]' | LC_ALL=C sort -u)"
    [[ "$(grep -c . <<<"$valid_fingerprints" || true)" -eq 1 &&
        "$valid_fingerprints" == "$fingerprint" ]] ||
        fail "signature fingerprint mismatch for $group:$module:$version:$artifact"

    if [[ "$artifact" == "$module-$version.jar" ]]; then
        printf '%s|%s|%s\n' "$group" "$module" "$version" >>"$trusted_implementations"
    fi

    printf 'REVIEWED %s:%s:%s %s sha256=%s signer=%s evidence=%s repository=%s\n' \
        "$group" "$module" "$version" "$artifact" "$expected_sha" "$fingerprint" \
        "$checksum_evidence" "$repository"
    reviewed=$((reviewed + 1))
done <"$work/new.entries"

LC_ALL=C sort -u -o "$trusted_implementations" "$trusted_implementations"
cat "$marker_requirements" "$module_requirements" | LC_ALL=C sort -u |
    while IFS= read -r implementation; do
        [[ -z "$implementation" ]] && continue
        grep -Fxq "$implementation" "$trusted_implementations" ||
            fail "plugin metadata implementation did not pass JAR provenance review: ${implementation//|/:}"
    done

echo "RESULT: PASS — reviewed $reviewed newly admitted artifacts by exact SHA-256 and publisher provenance; unsigned Gradle metadata is structurally bound to a trusted implementation JAR"
