#!/usr/bin/env bash
set -euo pipefail

# Build and run the iOS sample XCTest UI target on one exact simulator.
# Uses the same simulator-selection and mutation lock as run-ios-app.sh.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$REPO_ROOT/iosApp"
SCRIPT_NAME="run-ios-ui-tests"
SIM_NAME="${SIM_NAME:-iPhone 17}"
SIM_UDID="${SIM_UDID:-}"
RUN_DIR="${IOS_RUN_DIR:-}"
OWN_RUN_DIR=0
LOCK_DIR="$PROJECT_DIR/build/.ios-launch.lock"
OWN_LOCK=0

# shellcheck source=run-ios-app.sh
source "$SCRIPT_DIR/run-ios-app.sh"

cleanup() {
    local status=$?
    trap - EXIT
    if [[ "$OWN_LOCK" -eq 1 ]]; then
        release_ios_run_lock "$LOCK_DIR"
    fi
    if [[ "$OWN_RUN_DIR" -eq 1 && "$status" -eq 0 && "${KEEP_IOS_RUN_ARTIFACTS:-0}" != "1" ]]; then
        case "$RUN_DIR" in
            "$PROJECT_DIR"/build/ios-ui-run.*) rm -rf -- "$RUN_DIR" ;;
            *) echo "[$SCRIPT_NAME] Refusing to remove unexpected run directory: $RUN_DIR" >&2 ;;
        esac
    elif [[ -n "$RUN_DIR" ]]; then
        echo "[$SCRIPT_NAME] Run artifacts retained at $RUN_DIR"
    fi
    exit "$status"
}
trap cleanup EXIT

device_list="$(xcrun simctl list devices available)"
udid="$(resolve_simulator_udid "$SIM_NAME" "$SIM_UDID" "$device_list")"
if [[ -z "$RUN_DIR" ]]; then
    RUN_DIR="$(mktemp -d "$PROJECT_DIR/build/ios-ui-run.XXXXXX")"
    OWN_RUN_DIR=1
else
    mkdir -p -- "$RUN_DIR"
    RUN_DIR="$(cd "$RUN_DIR" && pwd)"
fi
DERIVED_DATA="$RUN_DIR/DerivedData"

acquire_ios_run_lock "$LOCK_DIR"
OWN_LOCK=1
(cd "$PROJECT_DIR" && xcodegen generate) | tail -3
xcrun simctl boot "$udid" 2>/dev/null || true

xcodebuild \
    -project "$PROJECT_DIR/p2pkit-sample.xcodeproj" \
    -scheme p2pkit-sample-ui \
    -configuration Debug \
    -sdk iphonesimulator \
    -destination "platform=iOS Simulator,id=$udid" \
    -derivedDataPath "$DERIVED_DATA" \
    -parallel-testing-enabled NO \
    test

echo "RESULT: PASS — iOS simulator launched the sample and completed start/stop UI automation"
