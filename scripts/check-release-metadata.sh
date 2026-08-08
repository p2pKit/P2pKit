#!/usr/bin/env bash
# Cross-check the version/security namespace claims that consumers copy.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(sed -n 's/^VERSION_NAME=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
LATEST_PUBLISHED="$(sed -n 's/^LATEST_PUBLISHED_VERSION=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
GROUP="$(sed -n 's/^GROUP=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
EXPECTED_GROUP="io.github.apdelrahman1911"

[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z]+([.-][0-9A-Za-z]+)*)?$ ]] || {
    echo "FATAL: VERSION_NAME must be SemVer with an optional prerelease/snapshot, got '$VERSION'" >&2
    exit 1
}
[[ "$LATEST_PUBLISHED" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z]+([.-][0-9A-Za-z]+)*)?$ && "$LATEST_PUBLISHED" != *-SNAPSHOT ]] || {
    echo "FATAL: LATEST_PUBLISHED_VERSION must be a non-snapshot SemVer, got '$LATEST_PUBLISHED'" >&2
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

if [[ "$VERSION" == *-SNAPSHOT ]]; then
    require_text README.md "**Development version:** \`$VERSION\`."
    require_text CHANGELOG.md "## Unreleased"
else
    require_text README.md "**Current source version:** \`$VERSION\` release candidate."
    require_text CHANGELOG.md "## $VERSION — release candidate"
fi
require_text README.md "**Latest published version:** \`$LATEST_PUBLISHED\`."
require_text README.md "\`$GROUP:p2p-core:$LATEST_PUBLISHED\`"
require_text docs/architecture/specification.md "# Current API and protocol specification"
require_text CHANGELOG.md "## $LATEST_PUBLISHED — release candidate"
require_text docs/guides/migrating-to-0.7.md "# Migrating from 0.6.x to $LATEST_PUBLISHED"
require_text docs/guides/migrating-to-0.7.md "\`$GROUP\`"
require_text docs/releases/0.7.0-rc2.md "\`$GROUP:p2p-core:$LATEST_PUBLISHED\`"
require_text docs/releasing/maven-central.md "\`$GROUP\`"
require_text build.gradle.kts "?: \"$GROUP\""
require_text buildSrc/src/main/java/dev/p2pkit/build/P2pPomMetadata.java 'private static final String REPOSITORY_URL = "https://github.com/p2pKit/P2pKit";'
for publication_build in \
    library/p2p-core/build.gradle.kts \
    library/p2p-transport-lan/build.gradle.kts \
    library/p2p-network-provisioning-android/build.gradle.kts \
    library/p2p-network-provisioning-desktop/build.gradle.kts; do
    require_text "$publication_build" 'P2pPomMetadata.configure(this)'
done
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
    docs/releases/0.7.0-rc2.md \
    docs/guides/migrating-to-0.7.md \
    docs/releasing/maven-central.md \
    scripts/check-published-consumers.sh; do
    if grep -qF -- 'dev.p2pkit:' "$ROOT/$current_release_file"; then
        echo "FATAL: $current_release_file still contains the former Maven group" >&2
        exit 1
    fi
done

echo "RESULT: PASS — source $VERSION and published $GROUP:*:$LATEST_PUBLISHED metadata agree"
