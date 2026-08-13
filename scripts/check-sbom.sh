#!/usr/bin/env bash
# Generates (or validates) the aggregate release SBOM and rejects incomplete or
# build-environment-contaminated output.
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

command -v jq >/dev/null 2>&1 || { echo "FATAL: jq is required" >&2; exit 2; }
command -v xmllint >/dev/null 2>&1 || { echo "FATAL: xmllint is required" >&2; exit 2; }
[[ -s "$JSON" ]] || { echo "FATAL: missing JSON SBOM: $JSON" >&2; exit 1; }
[[ -s "$XML" ]] || { echo "FATAL: missing XML SBOM: $XML" >&2; exit 1; }

jq --arg group "$GROUP" --arg version "$VERSION" -e '
    .bomFormat == "CycloneDX" and
    .specVersion == "1.6" and
    .metadata.component.group == $group and
    .metadata.component.name == "p2pkit" and
    .metadata.component.version == $version and
    (.components | length > 0) and
    ([.components[].name] | contains([
        "p2p-core",
        "p2p-transport-lan",
        "p2p-network-provisioning-android",
        "p2p-network-provisioning-desktop",
        "kotlinx-coroutines-core",
        "jmdns",
        "cryptography-provider-jdk-jvm",
        "cryptography-provider-cryptokit-iosarm64",
        "cryptography-provider-cryptokit-iossimulatorarm64",
        "cryptography-provider-cryptokit-iosx64"
    ])) and
    ([.components[].name] | any(startswith("p2p-sample")) | not) and
    ([.components[].name] | any(. == "dokka-base" or . == "gradle-api") | not)
' "$JSON" >/dev/null || { echo "FATAL: JSON SBOM content gate failed" >&2; exit 1; }

xmllint --noout "$XML"
if rg -q '/Users/|/home/|p2p-sample|dokka-base|gradle-api' "$JSON" "$XML"; then
    echo "FATAL: SBOM leaks a workstation path or includes sample/build dependencies" >&2
    exit 1
fi

COMPONENTS="$(jq '.components | length' "$JSON")"
echo "RESULT: PASS — CycloneDX 1.6 JSON/XML SBOM contains $COMPONENTS release components and no build/sample contamination"
