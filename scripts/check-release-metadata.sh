#!/usr/bin/env bash
# Cross-check the version/security namespace claims that consumers copy.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

fail() {
    echo "FATAL: $*" >&2
    exit 1
}

require_file() {
    [[ -f "$ROOT/$1" && -r "$ROOT/$1" ]] || fail "guarded file is missing or unreadable: $1"
}

match_file() {
    local file="$1" status=0
    shift
    require_file "$file"
    # Do not use -q: an early match must not hide a later input error.
    grep "$@" "$ROOT/$file" >/dev/null || status=$?
    [[ "$status" -le 1 ]] || fail "cannot inspect $file (grep exited $status)"
    return "$status"
}

require_text() {
    match_file "$1" -F -- "$2" || fail "$1 is missing release contract text: $2"
}

require_pattern() {
    match_file "$1" -E -- "$2" || fail "$1 is missing release contract token: $2"
}

forbid_text() {
    if match_file "$1" -F -- "$2"; then
        fail "$3"
    fi
}

require_file gradle.properties
VERSION="$(sed -n 's/^VERSION_NAME=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
LATEST_PUBLISHED="$(sed -n 's/^LATEST_PUBLISHED_VERSION=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
GROUP="$(sed -n 's/^GROUP=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
EXPECTED_GROUP="io.github.apdelrahman1911"
RELEASE_RECORD="docs/releases/$LATEST_PUBLISHED.md"

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

# Validated versions contain only letters, digits, dots and hyphens. Escape dots
# and require a token boundary so rc3 cannot match rc30 or rc3-extra.
VERSION_PATTERN="${VERSION//./\\.}"
PUBLISHED_PATTERN="${LATEST_PUBLISHED//./\\.}"
VERSION_END='($|[^[:alnum:].+-]|[.]($|[[:space:]]))'

if [[ "$VERSION" == *-SNAPSHOT ]]; then
    require_pattern README.md \
        "^[[:space:]*_]*Development[[:space:]]+version[[:space:]*_]*:[[:space:]*_\`]*$VERSION_PATTERN$VERSION_END"
    require_pattern CHANGELOG.md '^##[[:space:]]+Unreleased($|[[:space:][:punct:]])'
else
    require_pattern README.md \
        "^[[:space:]*_]*Current[[:space:]]+source[[:space:]]+version[[:space:]*_]*:[[:space:]*_\`]*$VERSION_PATTERN$VERSION_END"
    require_pattern CHANGELOG.md "^##[[:space:]]+\`?$VERSION_PATTERN$VERSION_END"
fi
require_pattern README.md \
    "^[[:space:]*_]*Latest[[:space:]]+published[[:space:]]+version[[:space:]*_]*:[[:space:]*_\`]*$PUBLISHED_PATTERN$VERSION_END"
require_text README.md "\`$GROUP:p2p-core:$LATEST_PUBLISHED\`"
# This maintained document is deliberately high-level, not an independent
# byte-level protocol oracle. Keep that distinction without freezing typography.
require_pattern docs/architecture/specification.md \
    '^#[[:space:]]+Current[[:space:]]+high-level[[:space:]]+API[[:space:]]+and[[:space:]]+protocol[[:space:]]+contract([[:space:]]|$)'
require_pattern CHANGELOG.md "^##[[:space:]]+\`?$PUBLISHED_PATTERN$VERSION_END"
require_pattern docs/guides/migrating-to-0.7.md \
    "^#[[:space:]]+Migrating[[:space:]]+from[[:space:]]+0\\.6\\.x[[:space:]]+to[[:space:]]+\`?$PUBLISHED_PATTERN$VERSION_END"
require_text docs/guides/migrating-to-0.7.md "\`$GROUP\`"
require_text "$RELEASE_RECORD" "\`$GROUP:p2p-core:$LATEST_PUBLISHED\`"
require_text docs/releasing/maven-central.md "\`$GROUP\`"
require_text build.gradle.kts "?: \"$GROUP\""

POM_METADATA=buildSrc/src/main/java/dev/p2pkit/build/P2pPomMetadata.java
require_file "$POM_METADATA"
ruby - "$ROOT/$POM_METADATA" <<'RUBY'
# Keep strings atomic and discard comments; a quoted/commented declaration is
# not the provenance-bearing field. Whitespace and modifier order are immaterial.
source = File.read(ARGV.fetch(0), encoding: "UTF-8")
tokens = source.scan(%r{
    """(?:\\.|(?!""").)*""" |
    "(?:\\.|[^"\\])*" | '(?:\\.|[^'\\])*' |
    //[^\n]* | /\*.*?(?:\*/|\z) |
    [A-Za-z_$][A-Za-z0-9_$]* | \S
}mx)
tokens.reject! { |token| token.start_with?("//", "/*") }
values = tokens.each_cons(8).select do |parts|
    parts[0, 3].sort == %w[final private static] &&
        parts[3, 3] == ["String", "REPOSITORY_URL", "="] && parts[7] == ";"
end.map { |parts| parts[6] }
abort("FATAL: P2pPomMetadata.java must declare the expected REPOSITORY_URL literal exactly once") unless
    values == ['"https://github.com/p2pKit/P2pKit"']
RUBY

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

forbid_text samples/iosApp/Info.plist "<string>_p2pkit._tcp</string>" \
    "maintained secure-v2 iOS sample still declares legacy Bonjour"
forbid_text samples/iosApp/project.yml '- "_p2pkit._tcp"' \
    "generated secure-v2 iOS sample still declares legacy Bonjour"

for current_release_file in \
    README.md \
    CLAUDE.md \
    gradle.properties \
    build.gradle.kts \
    "$RELEASE_RECORD" \
    docs/guides/migrating-to-0.7.md \
    docs/releasing/maven-central.md \
    scripts/check-published-consumers.sh; do
    forbid_text "$current_release_file" 'dev.p2pkit:' \
        "$current_release_file still contains the former Maven group"
done

echo "RESULT: PASS — source $VERSION and published $GROUP:*:$LATEST_PUBLISHED metadata agree"
