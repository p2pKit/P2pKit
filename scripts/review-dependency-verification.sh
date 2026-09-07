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

# Parse ASCII protocol fields and compare sorted records byte-wise. GPG's
# human diagnostics may contain non-UTF-8 bytes even beside valid VALIDSIG
# status records; the caller's locale must not make those signatures fail.
export LC_ALL=C

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE_REF="${1:-origin/main}"

fail() {
    echo "FATAL: $*" >&2
    exit 1
}

git -C "$ROOT" cat-file -e "$BASE_REF^{commit}" 2>/dev/null ||
    fail "base ref is not an available commit: $BASE_REF"
for command in curl gh gpg gpgconf awk comm sort shasum; do
    command -v "$command" >/dev/null 2>&1 || fail "required review tool is missing: $command"
done
PYTHON3="${P2PKIT_PYTHON3:-/usr/bin/python3}"
if [[ ! -x "$PYTHON3" ]] || ! "$PYTHON3" -c 'import json, xml.etree.ElementTree' 2>/dev/null; then
    PYTHON3="$(command -v python3 || true)"
fi
if [[ -z "$PYTHON3" ]] || ! "$PYTHON3" -c 'import json, xml.etree.ElementTree' 2>/dev/null; then
    fail "a working Python 3 with JSON and XML support is required"
fi

provenance_policy="$ROOT/gradle/plugin-provenance-policy.txt"
[[ -f "$provenance_policy" ]] || fail "missing Gradle plugin provenance policy"

# Large downloads follow the operator's volume choice, independently of GPG's
# short socket paths. Install cleanup before either allocation can fail.
work=""
gnupg=""
gnupg_ready=false
cleanup_review() {
    local result=$? cleanup_failed=false
    trap - EXIT
    trap '' HUP INT TERM
    if [[ "$gnupg_ready" == true ]] &&
        ! gpgconf --homedir "$gnupg" --kill all >/dev/null 2>&1; then
        # Keep the socket directory reachable for an explicit cleanup retry.
        printf 'FATAL: could not stop review GPG workers; retry gpgconf --homedir %q --kill all\n' "$gnupg" >&2
        cleanup_failed=true
    elif [[ -n "$gnupg" ]] && ! rm -rf -- "$gnupg"; then
        cleanup_failed=true
    fi
    if [[ -n "$work" ]] && ! rm -rf -- "$work"; then
        cleanup_failed=true
    fi
    if [[ "$result" -eq 0 && "$cleanup_failed" == true ]]; then
        result=1
    fi
    exit "$result"
}
trap cleanup_review EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
work="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-dependency-review.XXXXXX")"
chmod 700 "$work"

# Keep GNUPGHOME short enough for the agent's Unix-domain sockets on macOS.
# A long system TMPDIR must not redirect the large artifact workspace to /tmp.
# Hosts without /tmp may explicitly select another existing, short directory.
gnupg="$(mktemp -d "${P2PKIT_GPG_TMPDIR:-/tmp}/p2pkit-gpg.XXXXXX")"
gnupg_physical="$(cd "$gnupg" && pwd -P)"
gnupg="$gnupg_physical"
gpg_socket="$gnupg/S.gpg-agent.browser"
# LC_ALL=C counts bytes. libassuan rejects strlen(path)+1 >= sizeof(sun_path).
# macOS/BSD's 104-byte field therefore permits at most 102 pathname bytes;
# account for the longest standard agent socket, not just S.gpg-agent.
[[ "${#gpg_socket}" -lt 103 ]] ||
    fail "GPG socket path is too long; set P2PKIT_GPG_TMPDIR to a shorter physical directory"
chmod 700 "$gnupg"
gnupg_ready=true
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
            if (length(fingerprint) == 40) {
                derived_key_id = substr(fingerprint, 25, 16)
            } else if (length(fingerprint) == 64) {
                derived_key_id = substr(fingerprint, 1, 16)
            } else {
                derived_key_id = ""
            }
            if ((type == "fingerprint" && fingerprint == expected) ||
                (type == "keyid" && key_id == expected && derived_key_id == expected)) {
                print fingerprint
            }
            key_id = ""
        }
    ' | LC_ALL=C sort -u
}

verify_downloaded_checksum() {
    local data="$1" expected_sha="$2" repository="$3" relative="$4" label="$5"
    local actual_sha checksum_evidence remote_sha
    actual_sha="$(shasum -a 256 "$data" | awk '{print $1}')"
    [[ "$actual_sha" == "$expected_sha" ]] ||
        fail "downloaded bytes disagree with metadata for $label"

    checksum_evidence="signature-bound-bytes"
    rm -f "$work/remote.sha256"
    if curl -fsSL --connect-timeout 20 --max-time 120 \
        -o "$work/remote.sha256" "$repository/$relative.sha256" 2>/dev/null; then
        remote_sha="$(grep -Eo '[0-9a-fA-F]{64}' "$work/remote.sha256" |
            head -1 | tr '[:upper:]' '[:lower:]')"
        [[ "$remote_sha" == "$expected_sha" ]] ||
            fail "repository checksum disagrees with metadata for $label"
        checksum_evidence="sha256-sidecar+signature"
    fi

    printf '%s\n' "$checksum_evidence"
}

verify_detached_signature() {
    local data="$1" signature="$2" label="$3"
    local packet_output issuer_fingerprints issuer_key_ids fingerprint_count key_id_count
    local reference_type issuer_reference derived_key_id existing_listing matching_fingerprints
    local key_downloaded key_urls key_url key_listing import_output fingerprint verification valid_fingerprints
    packet_output="$(gpg --batch --list-packets "$signature" 2>/dev/null)" ||
        fail "detached signature packet is malformed for $label"
    [[ "$(grep -c '^:signature packet:' <<<"$packet_output" || true)" -eq 1 ]] ||
        fail "detached signature must contain exactly one signature packet for $label"
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
            fail "signature contains conflicting issuer key IDs for $label"
        fi
        if [[ "$key_id_count" -eq 1 ]]; then
            if [[ "${#issuer_reference}" -eq 40 ]]; then
                derived_key_id="${issuer_reference: -16}"
            else
                derived_key_id="${issuer_reference:0:16}"
            fi
            [[ "$derived_key_id" == "$issuer_key_ids" ]] ||
                fail "signature issuer fingerprint and key ID disagree for $label"
        fi
    elif [[ "$fingerprint_count" -eq 0 && "$key_id_count" -eq 1 &&
        "$issuer_key_ids" =~ ^[0-9A-F]{16}$ ]]; then
        reference_type="keyid"
        issuer_reference="$issuer_key_ids"
    else
        fail "signature has no unambiguous issuer identity for $label"
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
                fail "could not import the exact signing key $issuer_reference: $import_output"
            fi
            key_downloaded=true
            break
        done
        [[ "$key_downloaded" == true ]] ||
            fail "could not retrieve one exact signing key for $issuer_reference over HTTPS"
    fi
    fingerprint="$matching_fingerprints"
    verification="$(GNUPGHOME="$gnupg" gpg --batch --status-fd 1 \
        --verify "$signature" "$data" 2>&1)" ||
        fail "invalid detached signature for $label"
    valid_fingerprints="$(sed -n 's/^\[GNUPG:\] VALIDSIG \([^ ]*\) .*/\1/p' \
        <<<"$verification" | tr '[:lower:]' '[:upper:]' | LC_ALL=C sort -u)"
    [[ "$(grep -c . <<<"$valid_fingerprints" || true)" -eq 1 &&
        "$valid_fingerprints" == "$fingerprint" ]] ||
        fail "signature fingerprint mismatch for $label"

    printf '%s\n' "$fingerprint"
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
    relocated=false
    if [[ -z "$repository" ]]; then
        # Gradle component identity is not always the artifact's directory:
        # e.g. Guava's -jre component also publishes a sibling -android JAR.
        # Authenticate the checksum-listed locator BEFORE consulting its URLs.
        locator_artifact="$module-$version.module"
        [[ "$artifact" != "$locator_artifact" ]] ||
            fail "no repository artifact for $group:$module:$version:$artifact"
        locator_sha="$(awk -F'|' -v group="$group" -v module="$module" -v version="$version" \
            -v artifact="$locator_artifact" '
            $1 == group && $2 == module && $3 == version && $4 == artifact { print $5 }
        ' "$work/current.entries")"
        [[ "$locator_sha" =~ ^[0-9a-f]{64}$ ]] ||
            fail "no unique checksum-listed module metadata for $group:$module:$version:$artifact"
        locator_relative="${group//.//}/$module/$version/$locator_artifact"
        for candidate in "${repositories[@]}"; do
            if ! curl -fsSL --retry 5 --retry-all-errors --retry-delay 2 \
                --connect-timeout 20 --max-time 300 --max-filesize 1048576 \
                -o "$work/variant.module" "$candidate/$locator_relative"; then
                continue
            fi
            locator_evidence="$(verify_downloaded_checksum "$work/variant.module" "$locator_sha" \
                "$candidate" "$locator_relative" "$group:$module:$version:$locator_artifact")" ||
                fail "variant metadata checksum review failed"
            curl -fsSL --retry 5 --retry-all-errors --retry-delay 2 \
                --connect-timeout 20 --max-time 120 \
                -o "$work/variant.module.asc" "$candidate/$locator_relative.asc" ||
                fail "no detached signature for variant metadata: $group:$module:$version:$locator_artifact"
            locator_fingerprint="$(verify_detached_signature "$work/variant.module" "$work/variant.module.asc" \
                "$group:$module:$version:$locator_artifact")" || fail "variant metadata signature review failed"
            relative="$("$PYTHON3" "$ROOT/scripts/resolve-gradle-variant-artifact.py" \
                "$work/variant.module" "$group" "$module" "$version" "$artifact" "$expected_sha")" ||
                fail "variant artifact location review failed"
            # Do not switch repositories or relax provenance for a relocated file.
            curl -fsSL --retry 5 --retry-all-errors --retry-delay 2 \
                --connect-timeout 20 --max-time 300 \
                -o "$work/artifact" "$candidate/$relative" ||
                fail "no artifact at verified variant location: $candidate/$relative"
            repository="$candidate"
            relocated=true
            printf 'VERIFIED-LOCATOR %s:%s:%s %s sha256=%s signer=%s evidence=%s repository=%s path=%s\n' \
                "$group" "$module" "$version" "$locator_artifact" "$locator_sha" \
                "$locator_fingerprint" "$locator_evidence" "$repository" "$relative"
            break
        done
        [[ -n "$repository" ]] ||
            fail "no repository module metadata for $group:$module:$version:$artifact"
    fi

    checksum_evidence="$(verify_downloaded_checksum "$work/artifact" "$expected_sha" \
        "$repository" "$relative" "$group:$module:$version:$artifact")" || fail "artifact checksum review failed"

    rm -f "$work/artifact.asc"
    if ! curl -fsSL --retry 5 --retry-all-errors --retry-delay 2 \
        --connect-timeout 20 --max-time 120 \
        -o "$work/artifact.asc" "$repository/$relative.asc"; then
        [[ "$relocated" == false ]] ||
            fail "no detached signature for relocated artifact: $group:$module:$version:$artifact"
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

    fingerprint="$(verify_detached_signature "$work/artifact" "$work/artifact.asc" \
        "$group:$module:$version:$artifact")" || fail "artifact signature review failed"

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
