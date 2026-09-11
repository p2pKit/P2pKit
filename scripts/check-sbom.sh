#!/usr/bin/env bash
# Generates (or validates) the aggregate release SBOM and rejects incomplete or
# build-environment-contaminated output. Existing-pair mode also requires the
# checked-in vendor inputs and the owned LAN producer JAR; it does not rebuild.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(sed -n 's/^VERSION_NAME=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
GROUP="$(sed -n 's/^GROUP=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
if [[ $# -ge 1 ]]; then
    JSON="$1"
    XML="${2:-${1%.json}.xml}"
else
    (cd "$ROOT" && ./gradlew cyclonedxBom --console=plain)
    JSON="$ROOT/build/reports/cyclonedx/bom.json"
    XML="$ROOT/build/reports/cyclonedx/bom.xml"
fi

command -v python3 >/dev/null 2>&1 || { echo "FATAL: Python 3 is required" >&2; exit 2; }
[[ -s "$JSON" ]] || { echo "FATAL: missing JSON SBOM: $JSON" >&2; exit 1; }
[[ -s "$XML" ]] || { echo "FATAL: missing XML SBOM: $XML" >&2; exit 1; }

python3 "$ROOT/scripts/validate-sbom.py" "$JSON" "$XML" "$GROUP" "$VERSION"
