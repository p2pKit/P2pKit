#!/usr/bin/env bash
#
# Build + install + launch the iOS sample app on a simulator.
# Invoked by `:iosApp:runIosSimulator` Gradle task — but it's also fine to
# run from a shell if you want to skip Gradle.
#
# Required tools (all of which the macOS dev box already has if Xcode is
# installed):
#   - xcodegen   (brew install xcodegen)
#   - xcodebuild (ships with Xcode)
#   - xcrun simctl (ships with Xcode)
#
# Environment overrides:
#   SIM_NAME    — simulator device name. Default: "iPhone 17".
#                 Use `xcrun simctl list devices available` to see what's
#                 installed.
#   BUNDLE_ID   — must match PRODUCT_BUNDLE_IDENTIFIER in iosApp/project.yml.

set -euo pipefail

SIM_NAME="${SIM_NAME:-iPhone 17}"
BUNDLE_ID="${BUNDLE_ID:-dev.p2pkit.sample}"
SCHEME="p2pkit-sample"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$REPO_ROOT/iosApp"
DERIVED_DATA_BASE="$HOME/Library/Developer/Xcode/DerivedData"

echo "[ios-run] Regenerating Xcode project (xcodegen)..."
(cd "$PROJECT_DIR" && xcodegen generate) | tail -3

echo "[ios-run] Building iOS app for simulator (${SIM_NAME})..."
BUILD_LOG="/tmp/p2pkit-ios-build.log"
if ! xcodebuild \
    -project "$PROJECT_DIR/p2pkit-sample.xcodeproj" \
    -scheme "${SCHEME}" \
    -sdk iphonesimulator \
    -destination "platform=iOS Simulator,name=${SIM_NAME}" \
    build > "$BUILD_LOG" 2>&1; then
    echo "[ios-run] xcodebuild failed — last 40 lines of log:"
    tail -40 "$BUILD_LOG"
    exit 1
fi
echo "[ios-run] Build succeeded (full log at $BUILD_LOG)."

APP_PATH="$(find "$DERIVED_DATA_BASE" \
    -name 'p2pkit-sample.app' \
    -path '*Debug-iphonesimulator*' \
    -print -quit)"
if [[ -z "${APP_PATH}" || ! -d "${APP_PATH}" ]]; then
    echo "[ios-run] FATAL: could not locate p2pkit-sample.app in DerivedData."
    exit 1
fi
echo "[ios-run] App bundle: ${APP_PATH}"

echo "[ios-run] Resolving simulator UDID for '${SIM_NAME}'..."
UDID="$(xcrun simctl list devices available \
    | grep -E "^[[:space:]]+${SIM_NAME} \(" \
    | head -1 \
    | grep -oE '[0-9A-F-]{36}' \
    | head -1)"
if [[ -z "${UDID}" ]]; then
    echo "[ios-run] FATAL: no available simulator named '${SIM_NAME}'. Run:"
    echo "         xcrun simctl list devices available"
    exit 1
fi
echo "[ios-run] UDID: ${UDID}"

echo "[ios-run] Booting simulator (no-op if already booted)..."
xcrun simctl boot "${UDID}" 2>/dev/null || true

echo "[ios-run] Installing app bundle..."
xcrun simctl install "${UDID}" "${APP_PATH}"

echo "[ios-run] Bringing Simulator.app to the foreground so you can see it..."
open -a Simulator

echo "[ios-run] Launching ${BUNDLE_ID}..."
xcrun simctl launch "${UDID}" "${BUNDLE_ID}"

echo "[ios-run] Done. Watch the Simulator window."
