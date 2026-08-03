#!/usr/bin/env bash
# Cross-check the version/security namespace claims that consumers copy.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(sed -n 's/^VERSION_NAME=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"

[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z]+([.-][0-9A-Za-z]+)*)?$ ]] || {
    echo "FATAL: VERSION_NAME must be a release SemVer with an optional prerelease, got '$VERSION'" >&2
    exit 1
}

require_text() {
    local file="$1"
    local text="$2"
    if ! grep -qF -- "$text" "$ROOT/$file"; then
        echo "FATAL: $file is missing release contract text: $text" >&2
        exit 1
    fi
}

require_text README.md "**Current source version:** \`$VERSION\` release candidate."
require_text P2pKit-Spec.md "**Version:** 0.7 specification"
require_text CHANGELOG.md "## $VERSION — release candidate"
require_text docs/MIGRATING_TO_0.7.md "# Migrating from 0.6.x to $VERSION"
require_text docs/STABILIZATION_AND_RELEASE.md "\`$VERSION\` release candidate"
require_text p2p-core/build.gradle.kts 'url.set("https://github.com/p2pKit/P2pKit")'
require_text p2p-transport-lan/build.gradle.kts 'url.set("https://github.com/p2pKit/P2pKit")'
require_text p2p-network-provisioning-android/build.gradle.kts 'url.set("https://github.com/p2pKit/P2pKit")'
require_text p2p-network-provisioning-desktop/build.gradle.kts 'url.set("https://github.com/p2pKit/P2pKit")'
require_text iosApp/Info.plist "<string>_p2pkit2._tcp</string>"
require_text iosApp/project.yml '- "_p2pkit2._tcp"'
require_text scripts/run-ios-app.sh "_p2pkit2._tcp"

if grep -qF -- "<string>_p2pkit._tcp</string>" "$ROOT/iosApp/Info.plist"; then
    echo "FATAL: maintained secure-v2 iOS sample still declares legacy Bonjour" >&2
    exit 1
fi
if grep -qF -- '- "_p2pkit._tcp"' "$ROOT/iosApp/project.yml"; then
    echo "FATAL: generated secure-v2 iOS sample still declares legacy Bonjour" >&2
    exit 1
fi

echo "RESULT: PASS — $VERSION release metadata and secure-v2 iOS namespace agree"
