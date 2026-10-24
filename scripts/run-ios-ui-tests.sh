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
    run-keyboard-readiness|run-keyboard-query-cause)
        [[ $# -eq 1 ]] || {
            echo "[ios-run] Keyboard readiness diagnostic accepts no additional arguments." >&2
            exit 2
        }
        ;;
    prepare-jvm-transfer|run-jvm-transfer|run-cancellation-probe|run-owned-flow-lifecycle|run-owned-cancellation)
        [[ $# -eq 1 && -n "$RUN_DIR" && -n "${P2PKIT_AUDIT_STATE_DIR:-}" ]] || {
            echo "[ios-run] Scoped XCTest requires an owned audit invocation and explicit IOS_RUN_DIR." >&2
            exit 2
        }
        ;;
    *) echo "usage: $0 [run-keyboard-readiness|run-keyboard-query-cause|prepare-jvm-transfer|run-jvm-transfer|run-cancellation-probe|run-owned-flow-lifecycle|run-owned-cancellation]" >&2; exit 2 ;;
esac
if [[ "$action" == "run-cancellation-probe" && -z "$SIM_UDID" ]]; then
    echo "[ios-run] Cancellation investigation requires the outer owner's exact simulator UDID." >&2
    exit 2
fi

if [[ ( "$action" == "run-owned-flow-lifecycle" || "$action" == "run-owned-cancellation" ) && -z "$SIM_UDID" ]]; then
    echo "[ios-run] Owned-flow checks require the outer owner's exact simulator UDID." >&2
    exit 2
fi

# shellcheck source=run-ios-app.sh
source "$SCRIPT_DIR/run-ios-app.sh"

initialize_ios_run_cleanup "$PROJECT_DIR" "ios-ui-run"

# Hosted compatibility selects its exact reviewed runtime before ordinary
# launcher admission. Never silently pick the first duplicate device name.
if [[ -n "${SIM_RUNTIME:-}" ]]; then
    selected_udid="$(select_runtime_simulator_udid "$SIM_NAME" "$SIM_RUNTIME" \
        "$(xcrun simctl list --json devices available)")"
    if [[ -n "$SIM_UDID" && "$SIM_UDID" != "$selected_udid" ]]; then
        echo "[ios-run] Explicit SIM_UDID conflicts with the selected runtime/device." >&2
        exit 1
    fi
    SIM_UDID="$selected_udid"
fi

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
if [[ "$action" == "run-keyboard-query-cause" ]]; then
    # These investigative sources do not import P2pKitShared. Diagnose Swift
    # compiler failures before spending time building the unchanged framework;
    # this is not a substitute for the real app build or XCTest execution.
    query_sdk="$(xcrun --sdk iphonesimulator --show-sdk-path)"
    query_platform="$(xcrun --sdk iphonesimulator --show-sdk-platform-path)"
    query_arch="$(uname -m)"
    case "$query_arch" in arm64|x86_64) ;; *) echo "[ios-run] Unsupported query diagnostic architecture." >&2; exit 2 ;; esac
    run_ios_mutation xcrun swiftc -typecheck -warnings-as-errors -swift-version 5 \
        -sdk "$query_sdk" -target "$query_arch-apple-ios15.0-simulator" \
        -module-cache-path "$DERIVED_DATA/ModuleCache.noindex" \
        -D DEBUG -D P2PKIT_KEYBOARD_QUERY_PROBE "$PROJECT_DIR/KeyboardQueryGate.swift"
    run_ios_mutation xcrun swiftc -typecheck -warnings-as-errors -swift-version 5 \
        -sdk "$query_sdk" -target "$query_arch-apple-ios15.0-simulator" \
        -module-cache-path "$DERIVED_DATA/ModuleCache.noindex" \
        -F "$query_platform/Developer/Library/Frameworks" \
        -F "$query_sdk/Developer/Library/Frameworks" \
        "$PROJECT_DIR/UITests/KeyboardReadiness.swift" \
        "$PROJECT_DIR/KeyboardQueryCauseUITests/KeyboardQueryCauseUITests.swift"
fi
# Terminal/focused run actions never bootstrap/regenerate their already prepared
# source-bound project/framework; the Xcode provenance phase remains mandatory.
if [[ "$action" != "run-jvm-transfer" && "$action" != "run-cancellation-probe" &&
      "$action" != "run-owned-flow-lifecycle" && "$action" != "run-owned-cancellation" ]]; then
    ensure_ios_xcframework_present "$REPO_ROOT"
    (cd "$PROJECT_DIR" && run_ios_mutation xcodegen generate) | tail -3
fi
boot_and_wait_for_simulator "$udid"

keyboard_passive_flags=()
if [[ "${GITHUB_ACTIONS:-}" == "true" &&
  ( ( -z "$action" && "${COMPONENT:-}" == "compatibility" ) ||
    ( "$action" == "run-keyboard-query-cause" && "${COMPONENT:-}" == "apple-keyboard-query-diagnostic" ) ) ]]; then
    # Reuse the same post-return reader for ordinary passive observation and
    # the explicit native-query comparison. No GUI or preference mutation.
    keyboard_passive_flags=('OTHER_SWIFT_FLAGS=$(inherited) -D P2PKIT_KEYBOARD_CAUSE_PROBE')
    keyboard_command_status=UNOBSERVED
    keyboard_signal_status=0
    finish_keyboard_observation() {
        local status="$1" capture_status=0
        trap - EXIT
        trap '' INT TERM
        if [[ "$keyboard_command_status" == UNOBSERVED && "$keyboard_signal_status" -eq 0 ]]; then
            keyboard_command_status="$status"
        fi
        # Register this foreground reader under the still-held launcher
        # lock. The helper owns only its log child, never this borrowed device.
        if python3 "$IOS_LAUNCH_HELPER" run "$IOS_LAUNCH_LOCK" "$$" \
            python3 -B "$SCRIPT_DIR/ios_keyboard_passive_capture.py" \
            "$udid" "$keyboard_command_status" "$status"; then
            :
        else
            capture_status="$?"
            echo "[ios-run] Passive keyboard capture failed; original command result is retained." >&2
        fi
        if [[ "$status" -eq 0 && "$capture_status" -ne 0 ]]; then status=125; fi
        cleanup_ios_run "$status"
    }
    trap 'keyboard_signal_status=130; exit 130' INT
    trap 'keyboard_signal_status=143; exit 143' TERM
    trap 'finish_keyboard_observation "$?"' EXIT
fi

if [[ -z "$action" ]]; then
    # Do not put this function in an if/||/! context: that disables Bash's
    # existing errexit semantics inside the original launcher helpers.
    run_ios_xcodebuild \
        -project "$PROJECT_DIR/p2pkit-sample.xcodeproj" \
        -scheme p2pkit-sample-ui \
        -configuration Debug \
        -sdk iphonesimulator \
        -destination "platform=iOS Simulator,id=$udid" \
        -derivedDataPath "$DERIVED_DATA" \
        -parallel-testing-enabled NO \
        ${keyboard_passive_flags[@]+"${keyboard_passive_flags[@]}"} \
        test
    keyboard_command_status=0

    echo "RESULT: PASS — iOS simulator launched the sample and completed start/stop UI automation"
elif [[ "$action" == "run-keyboard-readiness" ]]; then
    # Diagnostic only: the same generated app and real Host/Port/pairing inputs,
    # with exactly the two existing locale cases. The ordinary suite is unfiltered.
    # Keep the default run-directory ownership, simulator selection and cleanup.
    run_ios_xcodebuild \
        -project "$PROJECT_DIR/p2pkit-sample.xcodeproj" \
        -scheme p2pkit-sample-ui \
        -configuration Debug \
        -sdk iphonesimulator \
        -destination "platform=iOS Simulator,id=$udid" \
        -derivedDataPath "$DERIVED_DATA" \
        -resultBundlePath "$DERIVED_DATA/Logs/Test/swift-keyboard-readiness.xcresult" \
        -parallel-testing-enabled NO \
        -maximum-concurrent-test-simulator-destinations 1 \
        -only-testing:p2pkit-sample-uitests/ContentViewPresentationUITests/testRenderedPortRoundTripsThroughManualInputInEnglishLocale \
        -only-testing:p2pkit-sample-uitests/ContentViewPresentationUITests/testRenderedPortRoundTripsThroughManualInputInGermanLocale \
        SWIFT_TREAT_WARNINGS_AS_ERRORS=YES \
        test
elif [[ "$action" == "run-keyboard-query-cause" ]]; then
    # Actual native A/B comparison, not replacement/passage of a failed original.
    # Each matrix cell owns a distinct app process on the selected simulator.
    run_ios_xcodebuild \
        -project "$PROJECT_DIR/p2pkit-sample.xcodeproj" \
        -scheme p2pkit-sample-keyboard-query \
        -configuration Debug \
        -sdk iphonesimulator \
        -destination "platform=iOS Simulator,id=$udid" \
        -derivedDataPath "$DERIVED_DATA" \
        -resultBundlePath "$DERIVED_DATA/Logs/Test/swift-keyboard-query-cause.xcresult" \
        -parallel-testing-enabled NO \
        -maximum-concurrent-test-simulator-destinations 1 \
        'OTHER_SWIFT_FLAGS=$(inherited) -D P2PKIT_KEYBOARD_CAUSE_PROBE -D P2PKIT_KEYBOARD_QUERY_PROBE' \
        SWIFT_TREAT_WARNINGS_AS_ERRORS=YES \
        test
    keyboard_command_status=0
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
elif [[ "$action" == "run-cancellation-probe" ]]; then
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
        -only-testing:p2pkit-sample-cancellation-probe-tests/SwiftFlowCancellationProbeTests/testSwiftTaskCancellationFinishesActualDiagnosticCollection \
        SWIFT_TREAT_WARNINGS_AS_ERRORS=YES \
        test
elif [[ "$action" == "run-owned-flow-lifecycle" ]]; then
    run_ios_xcodebuild \
        -project "$PROJECT_DIR/p2pkit-sample.xcodeproj" \
        -scheme p2pkit-sample-ui \
        -configuration Debug \
        -sdk iphonesimulator \
        -destination "platform=iOS Simulator,id=$udid" \
        -derivedDataPath "$DERIVED_DATA" \
        -resultBundlePath "$DERIVED_DATA/Logs/Test/swift-owned-flow-lifecycle.xcresult" \
        -parallel-testing-enabled NO \
        -maximum-concurrent-test-simulator-destinations 1 \
        -only-testing:p2pkit-sample-tests/OwnedFlowCollectionTests \
        -only-testing:p2pkit-sample-tests/SampleRunLifecycleTests \
        -only-testing:p2pkit-sample-tests/IosLanDiagnosticsLeaseTests \
        SWIFT_TREAT_WARNINGS_AS_ERRORS=YES \
        test
elif [[ "$action" == "run-owned-cancellation" ]]; then
    # Positive production-adapter case, alone and last; never rerun the raw probe here.
    run_ios_xcodebuild \
        -project "$PROJECT_DIR/p2pkit-sample.xcodeproj" \
        -scheme p2pkit-sample-cancellation-probe \
        -configuration Debug \
        -sdk iphonesimulator \
        -destination "platform=iOS Simulator,id=$udid" \
        -derivedDataPath "$DERIVED_DATA" \
        -resultBundlePath "$DERIVED_DATA/Logs/Test/swift-owned-cancellation.xcresult" \
        -parallel-testing-enabled NO \
        -maximum-concurrent-test-simulator-destinations 1 \
        -only-testing:p2pkit-sample-cancellation-probe-tests/SwiftOwnedFlowCancellationTests/testOwnedAdapterCancellationFinishesActualDiagnosticCollection \
        SWIFT_TREAT_WARNINGS_AS_ERRORS=YES \
        test
fi
