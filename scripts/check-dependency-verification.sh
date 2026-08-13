#!/usr/bin/env bash
# Validate the committed Gradle dependency-verification allowlist without
# resolving or trusting any new artifact.
set -euo pipefail

ROOT="${P2PKIT_ROOT_OVERRIDE:-$(cd "$(dirname "$0")/.." && pwd)}"
METADATA="$ROOT/gradle/verification-metadata.xml"

fail() {
    echo "FATAL: $*" >&2
    exit 1
}

[[ -f "$METADATA" ]] || fail "missing Gradle verification metadata"
grep -Fq 'dependency-verification-1.4.xsd' "$METADATA" ||
    fail "verification metadata does not use the reviewed Gradle 9.7 schema"
[[ "$(grep -Fc '<verify-metadata>true</verify-metadata>' "$METADATA")" == "1" ]] ||
    fail "artifact metadata verification is not enabled exactly once"
[[ "$(grep -Fc '<verify-signatures>false</verify-signatures>' "$METADATA")" == "1" ]] ||
    fail "signature policy changed without an explicit repository-wide migration"

if grep -Eq '<(trusted-artifacts|trusted-keys|ignored-keys|sha1|md5)([ >])' "$METADATA"; then
    fail "broad trust, ignored signing keys, or a weak checksum entered verification metadata"
fi

entries="$(mktemp "${TMPDIR:-/tmp}/p2pkit-verification-entries.XXXXXX")"
trap 'rm -f "$entries"' EXIT

awk -v entries="$entries" '
    function fatal(message) {
        print "FATAL: " message > "/dev/stderr"
        exit 1
    }
    /<component group=/ {
        split($0, fields, "\"")
        if (length(fields) < 7) fatal("malformed component declaration")
        component = fields[2] "|" fields[4] "|" fields[6]
        next
    }
    /<artifact name=/ {
        if (artifact != "") fatal("nested artifact declaration")
        split($0, fields, "\"")
        if (length(fields) < 3 || component == "") fatal("malformed artifact declaration")
        artifact = fields[2]
        checksum_count = 0
        next
    }
    /<sha256 value=/ {
        if (artifact == "") fatal("SHA-256 outside an artifact")
        split($0, fields, "\"")
        checksum = fields[2]
        if (checksum !~ /^[0-9a-f]{64}$/) fatal("invalid SHA-256 for " component "|" artifact)
        checksum_count++
        print component "|" artifact "|" checksum >> entries
        next
    }
    /<\/artifact>/ {
        if (artifact == "") fatal("artifact close without an open artifact")
        if (checksum_count != 1) fatal("artifact must have exactly one SHA-256: " component "|" artifact)
        artifact = ""
        checksum_count = 0
        next
    }
    END {
        if (artifact != "") fatal("unterminated artifact declaration")
    }
' "$METADATA" || fail "verification metadata structure is invalid"

[[ -s "$entries" ]] || fail "verification metadata contains no artifact checksums"
duplicate="$(LC_ALL=C sort "$entries" | uniq -d | head -1)"
[[ -z "$duplicate" ]] || fail "duplicate verified artifact entry: $duplicate"

stale_utp="$(find "$ROOT" -name gradle.lockfile -type f -exec \
    grep -H -m1 -E '(^|[=,])_internal-unified-test-platform-' {} + 2>/dev/null | head -1 || true)"
[[ -z "$stale_utp" ]] ||
    fail "dependency lock retains a removed AGP internal UTP configuration: $stale_utp"

echo "RESULT: PASS — strict SHA-256 metadata and current dependency locks are fail closed"
