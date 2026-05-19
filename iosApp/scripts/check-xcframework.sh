#!/bin/sh
#
# V0.4-PROVENANCE (L3): Xcode pre-build validation for the
# P2pKitShared XCFramework.
#
# Wired as a Run Script build phase in iosApp/p2pkit-sample.xcodeproj
# BEFORE the "Compile Sources" phase. Guarantees that every Xcode build
# links against an XCFramework freshly produced from the current
# `git rev-parse HEAD`. A stale XCFramework cannot silently reach the
# device through the normal build flow.
#
# Two layers of protection:
#   1. Run the Gradle XCFramework task — Gradle's own up-to-date check
#      makes this cheap (<2s) when no Kotlin source changed.
#   2. After the task, compare BUILD_COMMIT.txt against `git rev-parse HEAD`
#      and fail the Xcode build if they differ.
#
# Soft-warn on dirty working tree (uncommitted changes are reproducible
# under active development; we don't want to break the inner loop).

set -e

# When invoked as an Xcode build phase, $SRCROOT is iosApp/. Step out to
# the repo root so Gradle finds the wrapper.
cd "${SRCROOT:-$(dirname "$0")/..}/.."

echo "→ V0.4-PROVENANCE: ensuring P2pKitShared XCFramework is up to date..."
sh ./gradlew :p2p-transport-lan:assembleP2pKitSharedReleaseXCFramework \
  -q --console=plain

XCF_DIR="p2p-transport-lan/build/XCFrameworks/release"
XCF_BIN="$XCF_DIR/P2pKitShared.xcframework/ios-arm64/P2pKitShared.framework/P2pKitShared"
XCF_COMMIT_FILE="$XCF_DIR/BUILD_COMMIT.txt"

if [ ! -f "$XCF_BIN" ]; then
    echo "error: XCFramework binary missing at $XCF_BIN"
    echo "       The XCFramework assembly task did not produce the expected output."
    exit 1
fi

if [ ! -f "$XCF_COMMIT_FILE" ]; then
    echo "error: BUILD_COMMIT.txt sidecar missing at $XCF_COMMIT_FILE"
    echo "       writeXcframeworkCommit did not finalize the assemble task."
    echo "       Run: sh ./gradlew :p2p-transport-lan:assembleP2pKitSharedReleaseXCFramework"
    exit 1
fi

XCF_COMMIT="$(tr -d '[:space:]' < "$XCF_COMMIT_FILE")"
HEAD_COMMIT="$(git rev-parse HEAD)"

if [ "$XCF_COMMIT" != "$HEAD_COMMIT" ]; then
    echo "error: XCFramework identity mismatch — refusing to build against stale code:"
    echo "  expected (git HEAD):  $HEAD_COMMIT"
    echo "  actual (framework):   $XCF_COMMIT"
    echo "  Fix: sh ./gradlew :p2p-transport-lan:assembleP2pKitSharedReleaseXCFramework"
    exit 1
fi

# Soft-warn on dirty tree — common during active dev; not a build failure.
if ! git diff-index --quiet HEAD --; then
    echo "warning: working tree is dirty"
    echo "  The XCFramework you're about to link against includes uncommitted changes."
    echo "  Test results are non-reproducible from a clean checkout of $HEAD_COMMIT."
fi

SHORT="${XCF_COMMIT:0:7}"
echo "✅ XCFramework is fresh: ${SHORT} (matches HEAD)"
