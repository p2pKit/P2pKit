#!/usr/bin/env bash
# Cross-check the version/security namespace claims that consumers copy.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(sed -n 's/^VERSION_NAME=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
GROUP="$(sed -n 's/^GROUP=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
EXPECTED_GROUP="io.github.apdelrahman1911"

[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z]+([.-][0-9A-Za-z]+)*)?$ ]] || {
    echo "FATAL: VERSION_NAME must be a release SemVer with an optional prerelease, got '$VERSION'" >&2
    exit 1
}

[[ "$GROUP" == "$EXPECTED_GROUP" ]] || {
    echo "FATAL: GROUP must equal owner-verified Central namespace $EXPECTED_GROUP, got '$GROUP'" >&2
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
require_text README.md "\`$GROUP:p2p-core:$VERSION\`"
require_text P2pKit-Spec.md "**Version:** 0.7 specification"
require_text CHANGELOG.md "## $VERSION — release candidate"
require_text docs/MIGRATING_TO_0.7.md "# Migrating from 0.6.x to $VERSION"
require_text docs/MIGRATING_TO_0.7.md "\`$GROUP\`"
require_text docs/STABILIZATION_AND_RELEASE.md "\`$VERSION\` release candidate"
require_text docs/STABILIZATION_AND_RELEASE.md "Coordinates \`$GROUP:<module>:<VERSION_NAME>\`"
require_text docs/MAVEN_CENTRAL_RELEASE.md "\`$GROUP:*:$VERSION\`"
require_text build.gradle.kts "?: \"$GROUP\""
require_text library/p2p-core/build.gradle.kts 'url.set("https://github.com/p2pKit/P2pKit")'
require_text library/p2p-transport-lan/build.gradle.kts 'url.set("https://github.com/p2pKit/P2pKit")'
require_text library/p2p-network-provisioning-android/build.gradle.kts 'url.set("https://github.com/p2pKit/P2pKit")'
require_text library/p2p-network-provisioning-desktop/build.gradle.kts 'url.set("https://github.com/p2pKit/P2pKit")'
require_text samples/iosApp/Info.plist "<string>_p2pkit2._tcp</string>"
require_text samples/iosApp/project.yml '- "_p2pkit2._tcp"'
require_text scripts/run-ios-app.sh "_p2pkit2._tcp"

if grep -qF -- "<string>_p2pkit._tcp</string>" "$ROOT/samples/iosApp/Info.plist"; then
    echo "FATAL: maintained secure-v2 iOS sample still declares legacy Bonjour" >&2
    exit 1
fi
if grep -qF -- '- "_p2pkit._tcp"' "$ROOT/samples/iosApp/project.yml"; then
    echo "FATAL: generated secure-v2 iOS sample still declares legacy Bonjour" >&2
    exit 1
fi

for current_release_file in \
    README.md \
    CLAUDE.md \
    gradle.properties \
    build.gradle.kts \
    docs/MAVEN_CENTRAL_RELEASE.md \
    docs/MIGRATING_TO_0.7.md \
    docs/STABILIZATION_AND_RELEASE.md \
    scripts/check-published-consumers.sh; do
    if grep -qF -- 'dev.p2pkit:' "$ROOT/$current_release_file"; then
        echo "FATAL: $current_release_file still contains the former Maven group" >&2
        exit 1
    fi
done

echo "RESULT: PASS — $GROUP:$VERSION release metadata and secure-v2 iOS namespace agree"
