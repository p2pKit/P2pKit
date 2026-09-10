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
action="${1:-}"
case "$action" in
    "") [[ $# -eq 0 ]] ;;
    prepare-jvm-transfer|run-jvm-transfer|run-cancellation-probe)
        [[ $# -eq 1 && -n "$RUN_DIR" && -n "${P2PKIT_AUDIT_STATE_DIR:-}" ]] || {
            echo "[ios-run] Scoped XCTest requires an owned audit invocation and explicit IOS_RUN_DIR." >&2
            exit 2
        }
        ;;
    *) echo "usage: $0 [prepare-jvm-transfer|run-jvm-transfer|run-cancellation-probe]" >&2; exit 2 ;;
esac
if [[ "$action" == "run-cancellation-probe" && -z "$SIM_UDID" ]]; then
    echo "[ios-run] Cancellation investigation requires the outer owner's exact simulator UDID." >&2
    exit 2
fi

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
# Neither terminal run action may bootstrap/regenerate its already prepared
# source-bound project/framework; the Xcode provenance phase remains mandatory.
if [[ "$action" != "run-jvm-transfer" && "$action" != "run-cancellation-probe" ]]; then
    ensure_ios_xcframework_present "$REPO_ROOT"
    (cd "$PROJECT_DIR" && run_ios_mutation xcodegen generate) | tail -3
fi
boot_and_wait_for_simulator "$udid"

if [[ -z "$action" ]]; then
    run_ios_xcodebuild \
        -project "$PROJECT_DIR/p2pkit-sample.xcodeproj" \
        -scheme p2pkit-sample-ui \
        -configuration Debug \
        -sdk iphonesimulator \
        -destination "platform=iOS Simulator,id=$udid" \
        -derivedDataPath "$DERIVED_DATA" \
        -parallel-testing-enabled NO \
        test

    echo "RESULT: PASS — iOS simulator launched the sample and completed start/stop UI automation"
elif [[ "$action" == "prepare-jvm-transfer" ]]; then
    run_ios_xcodebuild \
        -project "$PROJECT_DIR/p2pkit-sample.xcodeproj" \
        -scheme p2pkit-sample-jvm-transfer \
        -configuration Debug \
        -sdk iphonesimulator \
        -destination "platform=iOS Simulator,id=$udid" \
        -derivedDataPath "$DERIVED_DATA" \
        -parallel-testing-enabled NO \
        SWIFT_TREAT_WARNINGS_AS_ERRORS=YES \
        build-for-testing
elif [[ "$action" == "run-jvm-transfer" ]]; then
    run_ios_mutation python3 "$SCRIPT_DIR/run-swift-jvm-transfer.py" \
        --derived-data "$DERIVED_DATA" --simulator "$udid"
else
    # This one-method host is retired by Host.swift_cancellation_probe, including
    # when XCTest fails. Never append normal acceptance tests to this invocation.
    run_ios_xcodebuild \
        -project "$PROJECT_DIR/p2pkit-sample.xcodeproj" \
        -scheme p2pkit-sample-cancellation-probe \
        -configuration Debug \
        -sdk iphonesimulator \
        -destination "platform=iOS Simulator,id=$udid" \
        -derivedDataPath "$DERIVED_DATA" \
        -resultBundlePath "$DERIVED_DATA/Logs/Test/swift-cancellation-probe.xcresult" \
        -parallel-testing-enabled NO \
        -maximum-concurrent-test-simulator-destinations 1 \
        -test-iterations 1 \
        -only-testing:p2pkit-sample-cancellation-probe-tests/SwiftFlowCancellationProbeTests/testSwiftTaskCancellationFinishesActualDiagnosticCollection \
        SWIFT_TREAT_WARNINGS_AS_ERRORS=YES \
        test
fi
