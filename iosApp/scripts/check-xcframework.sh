#!/bin/sh
#
# V0.4-PROVENANCE (L3): Xcode pre-build validation for the
# P2pKitShared XCFramework.
#
# Wired as a Run Script build phase in iosApp/p2pkit-sample.xcodeproj
# BEFORE the "Compile Sources" phase. Guarantees that every Xcode build
# links against an XCFramework whose framework sources match the current
# `git rev-parse HEAD`. A stale XCFramework cannot silently reach the
# device through the normal build flow.
#
# Gradle declares the commit, relevant source state, input fingerprint, and
# all three sidecars as assembly task inputs/outputs. Its verification task
# therefore rebuilds after relevant tracked or untracked changes, repairs a
# deleted sidecar, and refuses an unavailable/invalid git identity. This shell
# layer additionally checks the expected slices before Xcode links them.

set -e

# When invoked as an Xcode build phase, $SRCROOT is iosApp/. Step out to
# the repo root so Gradle finds the wrapper.
cd "${SRCROOT:-$(dirname "$0")/..}/.."

echo "→ V0.4-PROVENANCE: ensuring P2pKitShared XCFramework is up to date..."
sh ./gradlew :p2p-transport-lan:verifyP2pKitSharedReleaseXCFrameworkProvenance \
  -q --console=plain

XCF_DIR="p2p-transport-lan/build/XCFrameworks/release"
XCF_COMMIT_FILE="$XCF_DIR/BUILD_COMMIT.txt"
XCF_STATE_FILE="$XCF_DIR/BUILD_SOURCE_STATE.txt"
XCF_FINGERPRINT_FILE="$XCF_DIR/BUILD_INPUTS_SHA256.txt"

# AUDIT-2026-06 (A-G9-samples-desktop-ios-13): check every slice, not just
# the ios-arm64 device slice — the simulator slice is the one
# scripts/run-ios-app.sh actually links and runs, and a malformed/partial
# simulator slice previously passed this gate unnoticed.
for XCF_SLICE in ios-arm64 ios-arm64_x86_64-simulator; do
    XCF_BIN="$XCF_DIR/P2pKitShared.xcframework/$XCF_SLICE/P2pKitShared.framework/P2pKitShared"
    if [ ! -f "$XCF_BIN" ]; then
        echo "error: XCFramework binary missing at $XCF_BIN"
        echo "       The XCFramework assembly task did not produce the expected output."
        exit 1
    fi
done

for SIDECAR in "$XCF_COMMIT_FILE" "$XCF_STATE_FILE" "$XCF_FINGERPRINT_FILE"; do
    if [ ! -f "$SIDECAR" ]; then
        echo "error: XCFramework provenance sidecar missing at $SIDECAR"
        echo "       Run: sh ./gradlew :p2p-transport-lan:verifyP2pKitSharedReleaseXCFrameworkProvenance"
        exit 1
    fi
done

XCF_COMMIT="$(tr -d '[:space:]' < "$XCF_COMMIT_FILE")"
HEAD_COMMIT="$(git rev-parse HEAD)"
XCF_STATE="$(tr -d '[:space:]' < "$XCF_STATE_FILE")"
XCF_FINGERPRINT="$(tr -d '[:space:]' < "$XCF_FINGERPRINT_FILE")"

if [ "$XCF_COMMIT" != "$HEAD_COMMIT" ]; then
    echo "error: XCFramework identity mismatch after Gradle verification:"
    echo "  expected (git HEAD):  $HEAD_COMMIT"
    echo "  actual (framework):   $XCF_COMMIT"
    exit 1
fi

case "$XCF_STATE" in
    clean) ;;
    dirty)
        echo "warning: XCFramework contains relevant uncommitted or untracked inputs"
        echo "  Input fingerprint: $XCF_FINGERPRINT"
        echo "  The artifact is current for this workspace but not reproducible from $HEAD_COMMIT alone."
        ;;
    *)
        echo "error: invalid XCFramework source-state sidecar: $XCF_STATE"
        exit 1
        ;;
esac

case "$XCF_FINGERPRINT" in
    *[!0-9a-f]*|'')
        echo "error: invalid XCFramework input fingerprint"
        exit 1
        ;;
esac
if [ "${#XCF_FINGERPRINT}" -ne 64 ]; then
    echo "error: XCFramework input fingerprint must be a SHA-256 value"
    exit 1
fi

# AUDIT-2026-06 (A-G9-samples-desktop-ios-13): ${VAR:0:7} is a bash-only
# substring expansion; this script declares #!/bin/sh and must stay POSIX
# (sh is dash on some hosts). printf %.7s is the portable equivalent.
SHORT=$(printf %.7s "$XCF_COMMIT")
echo "✅ XCFramework is fresh: ${SHORT} (matches HEAD, source state: ${XCF_STATE})"
