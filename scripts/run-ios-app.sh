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
# IOSB-3 (2026-07): build into a repo-local DerivedData instead of the global
# ~/Library/Developer/Xcode/DerivedData. The old flow located the app with a
# `find` over global DerivedData and took the FIRST match in arbitrary
# filesystem order — with more than one checkout/worktree it could silently
# install a stale bundle from a different tree. A repo-local path plus a
# fixed products path below makes "run what THIS checkout just built" a
# structural guarantee. (iosApp/build/ is already git-ignored.)
DERIVED_DATA_DIR="$PROJECT_DIR/build/DerivedData"

echo "[ios-run] Regenerating Xcode project (xcodegen)..."
(cd "$PROJECT_DIR" && xcodegen generate) | tail -3

echo "[ios-run] Building iOS app for simulator (${SIM_NAME})..."
BUILD_LOG="/tmp/p2pkit-ios-build.log"
if ! xcodebuild \
    -project "$PROJECT_DIR/p2pkit-sample.xcodeproj" \
    -scheme "${SCHEME}" \
    -sdk iphonesimulator \
    -destination "platform=iOS Simulator,name=${SIM_NAME}" \
    -derivedDataPath "$DERIVED_DATA_DIR" \
    build > "$BUILD_LOG" 2>&1; then
    echo "[ios-run] xcodebuild failed — last 40 lines of log:"
    tail -40 "$BUILD_LOG"
    exit 1
fi
echo "[ios-run] Build succeeded (full log at $BUILD_LOG)."

# IOSB-3 (2026-07): deterministic product path under the repo-local
# DerivedData — no `find`, no ambiguity about which checkout produced it.
APP_PATH="$DERIVED_DATA_DIR/Build/Products/Debug-iphonesimulator/${SCHEME}.app"
if [[ ! -d "${APP_PATH}" ]]; then
    echo "[ios-run] FATAL: expected app bundle missing at:"
    echo "         ${APP_PATH}"
    echo "         xcodebuild reported success but did not produce the bundle"
    echo "         at the fixed Debug-iphonesimulator products path."
    exit 1
fi
echo "[ios-run] App bundle: ${APP_PATH}"

# P1-30 (2026-07): post-build check that the BUILT bundle carries the
# load-bearing local-network keys. iOS 14+ silently zeroes out
# NWListener/NWBrowser without them (the documented "zero discovery" failure
# mode); until now only a comment in iosApp/project.yml guarded them.
# `plutil -p` renders binary and XML plists alike, so a plain grep works.
echo "[ios-run] Checking load-bearing Info.plist keys in the built bundle..."
PLIST_DUMP="$(plutil -p "${APP_PATH}/Info.plist")"
for REQUIRED in NSLocalNetworkUsageDescription NSBonjourServices _p2pkit._tcp; do
    if ! printf '%s' "$PLIST_DUMP" | grep -qF "$REQUIRED"; then
        echo "[ios-run] FATAL: built Info.plist is missing '${REQUIRED}'."
        echo "         Without NSLocalNetworkUsageDescription + NSBonjourServices"
        echo "         (_p2pkit._tcp), iOS silently disables Bonjour and the app"
        echo "         discovers nothing. These keys MUST live in iosApp/project.yml"
        echo "         (info.properties block) — xcodegen regenerates the project,"
        echo "         so keys added anywhere else are silently dropped."
        exit 1
    fi
done
echo "[ios-run] Info.plist keys OK (NSLocalNetworkUsageDescription + NSBonjourServices/_p2pkit._tcp)."

echo "[ios-run] Resolving simulator UDID for '${SIM_NAME}'..."
# IOSB-2 (2026-07): SIM_NAME is interpolated into an ERE — escape regex
# metacharacters first, or every parenthesized stock name ("iPad Pro
# (11-inch)") fails to resolve. IOSB-1 (2026-07): `|| true` keeps the
# empty-result (and grep-SIGPIPE) pipeline from killing the script under
# `set -e -o pipefail` before the FATAL diagnostic below can print.
SIM_NAME_ERE="$(printf '%s' "$SIM_NAME" | sed -E 's/[][(){}.^$?*+|\\]/\\&/g')"
UDID="$(xcrun simctl list devices available \
    | grep -E "^[[:space:]]+${SIM_NAME_ERE} \(" \
    | head -1 \
    | grep -oE '[0-9A-F-]{36}' \
    | head -1 \
    || true)"
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

# IOSB-3 (2026-07) post-install provenance check: the executable inside the
# simulator's installed container must be byte-identical to the one this
# build just produced. Catches any remaining stale-install path regardless
# of where simctl places the bundle. (Companion of the pre-build XCFramework
# stamp gate in iosApp/scripts/check-xcframework.sh.)
INSTALLED_PATH="$(xcrun simctl get_app_container "${UDID}" "${BUNDLE_ID}" 2>/dev/null || true)"
if [[ -z "${INSTALLED_PATH}" || ! -d "${INSTALLED_PATH}" ]]; then
    echo "[ios-run] FATAL: simctl reports no installed container for ${BUNDLE_ID}."
    exit 1
fi
EXEC_NAME="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' "${APP_PATH}/Info.plist")"
BUILT_SHA="$(shasum -a 256 "${APP_PATH}/${EXEC_NAME}" | awk '{print $1}')"
INSTALLED_SHA="$(shasum -a 256 "${INSTALLED_PATH}/${EXEC_NAME}" | awk '{print $1}')"
if [[ "${BUILT_SHA}" != "${INSTALLED_SHA}" ]]; then
    echo "[ios-run] FATAL: installed app does not match this build (stale install)."
    echo "         built:     ${APP_PATH} (sha256 ${BUILT_SHA})"
    echo "         installed: ${INSTALLED_PATH} (sha256 ${INSTALLED_SHA})"
    exit 1
fi
echo "[ios-run] Provenance OK: installed executable matches this build (sha256 $(printf %.12s "${BUILT_SHA}")…)."
echo "[ios-run] Installed container: ${INSTALLED_PATH}"

echo "[ios-run] Bringing Simulator.app to the foreground so you can see it..."
open -a Simulator

echo "[ios-run] Launching ${BUNDLE_ID}..."
xcrun simctl launch "${UDID}" "${BUNDLE_ID}"

echo "[ios-run] Done. Watch the Simulator window."
