#!/usr/bin/env bash
# Complete secret-free gate for the exact commit intended for publication.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPORT_DIR="$ROOT/build/reports/release"
mkdir -p "$REPORT_DIR"

cd "$ROOT"
scripts/check-gradle-wrapper.sh
scripts/tests/check-repository-layout.sh
scripts/tests/check-osv-lockfile-coverage.sh
scripts/tests/check-markdown-links.sh
scripts/tests/classify-ci-scope-test.sh
scripts/tests/resolve-ci-scope-test.sh
scripts/tests/check-git-whitespace-test.sh
scripts/tests/check-release-identity-test.sh
scripts/tests/check-kotlin-toolchain-policy-test.sh
scripts/check-release-metadata.sh
scripts/check-git-whitespace.sh
./gradlew check --console=plain
scripts/check-sbom.sh
scripts/check-publish-artifacts.sh
scripts/check-published-consumers.sh
./gradlew :p2p-transport-lan:verifyP2pKitSharedReleaseXCFrameworkProvenance --console=plain
scripts/check-xcframework-minimum-os.sh
./gradlew :iosApp:regenerateXcodeProject --console=plain

set +e
xcodebuild \
    -project samples/iosApp/p2pkit-sample.xcodeproj \
    -scheme p2pkit-sample-ui \
    -configuration Debug \
    -sdk iphonesimulator \
    -destination 'generic/platform=iOS Simulator' \
    CODE_SIGNING_ALLOWED=NO \
    SWIFT_TREAT_WARNINGS_AS_ERRORS=YES \
    build >"$REPORT_DIR/xcodebuild.log" 2>&1
xcode_status=$?
set -e
if [[ $xcode_status -ne 0 ]]; then
    tail -100 "$REPORT_DIR/xcodebuild.log" >&2
    exit "$xcode_status"
fi
grep -Fq '** BUILD SUCCEEDED **' "$REPORT_DIR/xcodebuild.log" || {
    echo "FATAL: xcodebuild returned success without the success marker" >&2
    exit 1
}

git rev-parse HEAD >"$REPORT_DIR/commit-sha.txt"
sed -n 's/^GROUP=//p; s/^VERSION_NAME=//p; s/^LATEST_PUBLISHED_VERSION=//p' gradle.properties >"$REPORT_DIR/coordinates.txt"
echo "RESULT: PASS — complete release gate succeeded"
