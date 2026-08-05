#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
bash -n "$REPO_ROOT/scripts/run-ios-app.sh" "$REPO_ROOT/scripts/tests/run-ios-app-test.sh"
sh -n "$REPO_ROOT/iosApp/scripts/check-xcframework.sh"
# shellcheck source=../run-ios-app.sh
source "$REPO_ROOT/scripts/run-ios-app.sh"

UUID_PHONE_17_A="11111111-1111-1111-1111-111111111111"
UUID_PHONE_17_B="22222222-2222-2222-2222-222222222222"
UUID_IPAD="33333333-3333-3333-3333-333333333333"
DEVICE_LIST="$(printf '%s\n' \
    '== Devices ==' \
    '-- iOS 26.0 --' \
    "    iPhone 17 ($UUID_PHONE_17_A) (Shutdown)" \
    "    iPad Pro (11-inch) (M5) ($UUID_IPAD) (Booted)" \
    '-- iOS 25.0 --' \
    "    iPhone 17 ($UUID_PHONE_17_B) (Shutdown)")"

assert_equal() {
    local expected="$1"
    local actual="$2"
    local label="$3"
    if [[ "$actual" != "$expected" ]]; then
        echo "FAIL: $label: expected '$expected', got '$actual'" >&2
        exit 1
    fi
}

assert_fails() {
    local label="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        echo "FAIL: $label: expected failure" >&2
        exit 1
    fi
}

assert_fails \
    "duplicate simulator names are rejected" \
    resolve_simulator_udid "iPhone 17" "" "$DEVICE_LIST"

assert_equal \
    "$UUID_PHONE_17_B" \
    "$(resolve_simulator_udid "ignored when UDID is set" "$UUID_PHONE_17_B" "$DEVICE_LIST")" \
    "exact UDID selection"

assert_equal \
    "$UUID_IPAD" \
    "$(resolve_simulator_udid "iPad Pro (11-inch) (M5)" "" "$DEVICE_LIST")" \
    "parenthesized exact name selection"

assert_fails \
    "unavailable UDID is rejected" \
    resolve_simulator_udid "iPhone 17" "44444444-4444-4444-4444-444444444444" "$DEVICE_LIST"

DEVICE_JSON="$(printf '%s\n' \
    '{"devices":{' \
    '"com.apple.CoreSimulator.SimRuntime.iOS-25-4":[' \
    "{\"name\":\"iPhone 17\",\"udid\":\"$UUID_PHONE_17_A\",\"isAvailable\":true}]," \
    '"com.apple.CoreSimulator.SimRuntime.iOS-26-0":[' \
    "{\"name\":\"iPhone 17\",\"udid\":\"$UUID_PHONE_17_B\",\"isAvailable\":true}]," \
    '"com.apple.CoreSimulator.SimRuntime.iOS-27-0":[' \
    '{"name":"iPhone 17","udid":"44444444-4444-4444-4444-444444444444","isAvailable":false}],' \
    '"com.apple.CoreSimulator.SimRuntime.tvOS-27-0":[' \
    '{"name":"iPhone 17","udid":"55555555-5555-5555-5555-555555555555","isAvailable":true}]' \
    '}}')"

assert_equal \
    "$UUID_PHONE_17_B" \
    "$(select_latest_available_simulator_udid "iPhone 17" "$DEVICE_JSON")" \
    "newest available iOS runtime selection"

assert_fails \
    "missing CI simulator name is rejected" \
    select_latest_available_simulator_udid "iPhone 18" "$DEVICE_JSON"

TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-ios-run-test.XXXXXX")"
trap 'rm -rf -- "$TMP_ROOT"' EXIT

FAKE_BIN="$TMP_ROOT/fake-bin"
FAKE_XCRUN_LOG="$TMP_ROOT/xcrun.log"
mkdir -p "$FAKE_BIN"
printf '%s\n' \
    '#!/bin/sh' \
    'printf '\''%s\n'\'' "$*" >> "$FAKE_XCRUN_LOG"' \
    '[ "$1" = simctl ] || exit 64' \
    'case "$2" in' \
    '  bootstatus) exit "${FAKE_BOOTSTATUS_EXIT:-0}" ;;' \
    '  list) printf '\''%s\n'\'' "$FAKE_DEVICE_LIST" ;;' \
    '  *) exit 64 ;;' \
    'esac' \
    > "$FAKE_BIN/xcrun"
chmod +x "$FAKE_BIN/xcrun"

run_fake_boot_wait() (
    export PATH="$FAKE_BIN:$PATH"
    export FAKE_XCRUN_LOG
    export FAKE_BOOTSTATUS_EXIT="$1"
    export FAKE_DEVICE_LIST="$2"
    boot_and_wait_for_simulator "$UUID_PHONE_17_B"
)

: > "$FAKE_XCRUN_LOG"
run_fake_boot_wait 0 "$DEVICE_LIST"
if ! grep -qF "simctl bootstatus $UUID_PHONE_17_B -b" "$FAKE_XCRUN_LOG" ||
    ! grep -qF "simctl list devices available" "$FAKE_XCRUN_LOG"; then
    echo "FAIL: simulator readiness must synchronously boot and revalidate the exact UDID" >&2
    exit 1
fi
assert_fails \
    "simulator bootstatus failure is not ignored" \
    run_fake_boot_wait 42 "$DEVICE_LIST"
assert_fails \
    "simulator disappearance after boot is rejected" \
    run_fake_boot_wait 0 "${DEVICE_LIST//$UUID_PHONE_17_B/66666666-6666-6666-6666-666666666666}"

RUN_A="$(create_ios_run_dir "$TMP_ROOT")"
RUN_B="$(create_ios_run_dir "$TMP_ROOT")"
if [[ "$RUN_A" == "$RUN_B" || ! -d "$RUN_A" || ! -d "$RUN_B" ]]; then
    echo "FAIL: concurrent run directories must be distinct and materialized" >&2
    exit 1
fi
MISSING_PARENT="$TMP_ROOT/not-created/ui"
UI_RUN="$(create_ios_run_dir "$MISSING_PARENT" "ios-ui-run")"
if [[ ! -d "$UI_RUN" || "$UI_RUN" != "$MISSING_PARENT"/ios-ui-run.* ]]; then
    echo "FAIL: UI run directory must create its missing parent with the requested prefix" >&2
    exit 1
fi
assert_fails "unsupported run-directory prefix is rejected" create_ios_run_dir "$TMP_ROOT" "../escape"

FAKE_REPO="$TMP_ROOT/fake-repo"
mkdir -p "$FAKE_REPO"
printf '%s\n' \
    '#!/bin/sh' \
    'framework=p2p-transport-lan/build/XCFrameworks/release/P2pKitShared.xcframework' \
    'mkdir -p "$framework/ios-arm64/P2pKitShared.framework" "$framework/ios-arm64_x86_64-simulator/P2pKitShared.framework"' \
    ': > "$framework/ios-arm64/P2pKitShared.framework/P2pKitShared"' \
    ': > "$framework/ios-arm64_x86_64-simulator/P2pKitShared.framework/P2pKitShared"' \
    'printf '\''invoked\n'\'' >> gradle-invocations.txt' \
    > "$FAKE_REPO/gradlew"
chmod +x "$FAKE_REPO/gradlew"
ensure_ios_xcframework_present "$FAKE_REPO"
ensure_ios_xcframework_present "$FAKE_REPO"
if [[ "$(wc -l < "$FAKE_REPO/gradle-invocations.txt" | tr -d '[:space:]')" != "1" ]]; then
    echo "FAIL: missing XCFramework must bootstrap exactly once" >&2
    exit 1
fi

EMPTY_REPO="$TMP_ROOT/empty-repo"
mkdir -p "$EMPTY_REPO"
printf '%s\n' '#!/bin/sh' 'exit 0' > "$EMPTY_REPO/gradlew"
chmod +x "$EMPTY_REPO/gradlew"
assert_fails \
    "successful Gradle exit without XCFramework is rejected" \
    ensure_ios_xcframework_present "$EMPTY_REPO"

LOCK_DIR="$TMP_ROOT/launcher.lock"
acquire_ios_run_lock "$LOCK_DIR"
assert_fails "concurrent launcher lock is rejected" acquire_ios_run_lock "$LOCK_DIR"
release_ios_run_lock "$LOCK_DIR"
acquire_ios_run_lock "$LOCK_DIR"
release_ios_run_lock "$LOCK_DIR"

echo "run-ios-app tests: 17 passed"
