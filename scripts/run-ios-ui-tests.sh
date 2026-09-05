#!/usr/bin/env bash
set -euo pipefail

# Build and run the iOS sample XCTest UI target on one exact simulator.
# Uses the same simulator-selection and mutation lock as run-ios-app.sh.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$REPO_ROOT/samples/iosApp"
SIM_NAME="${SIM_NAME:-iPhone 17}"
SIM_UDID="${SIM_UDID:-}"
RUN_DIR="${IOS_RUN_DIR:-}"

# shellcheck source=run-ios-app.sh
source "$SCRIPT_DIR/run-ios-app.sh"

initialize_ios_run_cleanup "$PROJECT_DIR" "ios-ui-run"

device_list="$(xcrun simctl list devices available)"
udid="$(resolve_simulator_udid "$SIM_NAME" "$SIM_UDID" "$device_list")"
if [[ -z "$RUN_DIR" ]]; then
    RUN_DIR="$(create_ios_run_dir "$PROJECT_DIR/build" "ios-ui-run")"
    IOS_LAUNCH_OWNS_DIR=1
else
    mkdir -p -- "$RUN_DIR"
    RUN_DIR="$(cd "$RUN_DIR" && pwd)"
fi
IOS_LAUNCH_RUN_DIR="$RUN_DIR"
DERIVED_DATA="$RUN_DIR/DerivedData"

acquire_ios_run_lock "$IOS_LAUNCH_LOCK"
IOS_LAUNCH_OWNS_LOCK=1
ensure_ios_xcframework_present "$REPO_ROOT"
(cd "$PROJECT_DIR" && run_ios_mutation xcodegen generate) | tail -3
boot_and_wait_for_simulator "$udid"

run_ios_mutation xcodebuild \
    -project "$PROJECT_DIR/p2pkit-sample.xcodeproj" \
    -scheme p2pkit-sample-ui \
    -configuration Debug \
    -sdk iphonesimulator \
    -destination "platform=iOS Simulator,id=$udid" \
    -derivedDataPath "$DERIVED_DATA" \
    -parallel-testing-enabled NO \
    test

echo "RESULT: PASS — iOS simulator launched the sample and completed start/stop UI automation"
