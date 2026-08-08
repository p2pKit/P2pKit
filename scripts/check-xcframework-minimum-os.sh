#!/usr/bin/env bash
# Verifies that every release XCFramework slice retains P2pKit's declared
# iOS deployment floor after Kotlin/Xcode toolchain changes.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IOS_MIN_VERSION="$(sed -n 's/^IOS_MIN_VERSION=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
XCFRAMEWORK="${1:-$ROOT/library/p2p-transport-lan/build/XCFrameworks/release/P2pKitShared.xcframework}"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

[[ "$(uname -s)" == "Darwin" ]] || fail "XCFramework deployment inspection requires macOS"
command -v xcrun >/dev/null 2>&1 || fail "xcrun is required"
[[ "$IOS_MIN_VERSION" =~ ^[0-9]+\.[0-9]+$ ]] ||
    fail "IOS_MIN_VERSION must be a major.minor value"

check_binary() {
    local binary="$1" expected_platform="$2" expected_load_commands="$3"
    shift 3
    local expected_architectures=("$@")
    [[ -f "$binary" ]] || fail "missing XCFramework binary: $binary"

    local build_info platform_count minos_count invalid_platform invalid_minos
    build_info="$(xcrun vtool -show-build "$binary")"
    platform_count="$(printf '%s\n' "$build_info" | awk '$1 == "platform" { count++ } END { print count + 0 }')"
    minos_count="$(printf '%s\n' "$build_info" | awk '$1 == "minos" { count++ } END { print count + 0 }')"
    invalid_platform="$(printf '%s\n' "$build_info" | awk -v expected="$expected_platform" '$1 == "platform" && $2 != expected { print $2 }')"
    invalid_minos="$(printf '%s\n' "$build_info" | awk -v expected="$IOS_MIN_VERSION" '$1 == "minos" && $2 != expected { print $2 }')"

    [[ "$platform_count" == "$expected_load_commands" ]] ||
        fail "$(basename "$binary") has $platform_count platform records; expected $expected_load_commands"
    [[ "$minos_count" == "$expected_load_commands" ]] ||
        fail "$(basename "$binary") has $minos_count minimum-OS records; expected $expected_load_commands"
    [[ -z "$invalid_platform" ]] ||
        fail "$(basename "$binary") contains unexpected platforms: $invalid_platform"
    [[ -z "$invalid_minos" ]] ||
        fail "$(basename "$binary") contains an unexpected minimum OS: $invalid_minos"

    local architectures architecture
    architectures="$(xcrun lipo -archs "$binary")"
    for architecture in "${expected_architectures[@]}"; do
        [[ " $architectures " == *" $architecture "* ]] ||
            fail "$(basename "$binary") is missing architecture $architecture ($architectures)"
    done
    [[ "$(wc -w <<<"$architectures" | tr -d '[:space:]')" == "${#expected_architectures[@]}" ]] ||
        fail "$(basename "$binary") contains unexpected architectures: $architectures"
}

check_binary \
    "$XCFRAMEWORK/ios-arm64/P2pKitShared.framework/P2pKitShared" \
    IOS \
    1 \
    arm64
check_binary \
    "$XCFRAMEWORK/ios-arm64_x86_64-simulator/P2pKitShared.framework/P2pKitShared" \
    IOSSIMULATOR \
    2 \
    arm64 \
    x86_64

echo "RESULT: PASS — release XCFramework device and simulator slices target iOS $IOS_MIN_VERSION"
