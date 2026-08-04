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

LOCK_DIR="$TMP_ROOT/launcher.lock"
acquire_ios_run_lock "$LOCK_DIR"
assert_fails "concurrent launcher lock is rejected" acquire_ios_run_lock "$LOCK_DIR"
release_ios_run_lock "$LOCK_DIR"
acquire_ios_run_lock "$LOCK_DIR"
release_ios_run_lock "$LOCK_DIR"

echo "run-ios-app tests: 11 passed"
