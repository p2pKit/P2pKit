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
    . as $document |
    [
        $document.components[] |
        select(
            .group == $group and
            (.name == "p2p-core" or
             .name == "p2p-transport-lan" or
             .name == "p2p-network-provisioning-android" or
             .name == "p2p-network-provisioning-desktop")
        ) |
        .["bom-ref"]
    ] | sort as $publishedRefs |
    ($document.metadata.component["bom-ref"]) as $rootRef |
    $document.bomFormat == "CycloneDX" and
    $document.specVersion == "1.6" and
    $document.metadata.component.group == $group and
    $document.metadata.component.name == "p2pkit" and
    $document.metadata.component.version == $version and
    ($document.components | length > 0) and
    ([$document.components[].name] | contains([
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
    ([$document.components[].name] | any(startswith("p2p-sample")) | not) and
    ([$document.components[].name] | any(. == "dokka-base" or . == "gradle-api") | not) and
    ($publishedRefs | length == 4) and
    ([$document.dependencies[] | select(.ref == $rootRef)] | length == 1) and
    ([
        $document.dependencies[] |
        select(.ref == $rootRef) |
        .dependsOn[]
    ] | sort == $publishedRefs)
' "$JSON" >/dev/null || { echo "FATAL: JSON SBOM content gate failed" >&2; exit 1; }

xmllint --noout "$XML"
ROOT_REF="$(jq -r '.metadata.component["bom-ref"]' "$JSON")"
while IFS= read -r ref; do
    count="$(xmllint --xpath "count(/*[local-name()='bom']/*[local-name()='dependencies']/*[local-name()='dependency'][@ref='$ROOT_REF']/*[local-name()='dependency'][@ref='$ref'])" "$XML")"
    [[ "$count" == "1" ]] || {
        echo "FATAL: XML SBOM root is not linked exactly once to $ref" >&2
        exit 1
    }
done < <(
    jq -r --arg group "$GROUP" '
        .components[] |
        select(
            .group == $group and
            (.name == "p2p-core" or
             .name == "p2p-transport-lan" or
             .name == "p2p-network-provisioning-android" or
             .name == "p2p-network-provisioning-desktop")
        ) |
        .["bom-ref"]
    ' "$JSON"
)
if rg -q '/Users/|/home/|p2p-sample|dokka-base|gradle-api' "$JSON" "$XML"; then
    echo "FATAL: SBOM leaks a workstation path or includes sample/build dependencies" >&2
    exit 1
fi

COMPONENTS="$(jq '.components | length' "$JSON")"
echo "RESULT: PASS — CycloneDX 1.6 JSON/XML SBOM contains $COMPONENTS release components, a connected four-module root, and no build/sample contamination"
