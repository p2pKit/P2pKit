#!/usr/bin/env bash
#
# Build, install, and launch the iOS sample app on one exact simulator.
# Invoked by `:iosApp:runIosSimulator`; it can also run directly.
#
# Environment overrides:
#   SIM_NAME     — exact simulator device name. Default: "iPhone 17".
#   SIM_UDID     — exact available simulator UDID. Required when SIM_NAME is
#                  ambiguous across installed runtimes; takes precedence.
#   BUNDLE_ID    — must match PRODUCT_BUNDLE_IDENTIFIER in iosApp/project.yml.
#   IOS_RUN_DIR  — optional caller-owned build directory. By default every
#                  invocation gets an isolated temporary directory.
#   KEEP_IOS_RUN_ARTIFACTS=1 — retain an automatically created run directory.

set -euo pipefail

resolve_simulator_udid() {
    local requested_name="$1"
    local requested_udid="$2"
    local device_list="$3"
    local line device_name device_udid
    local -a device_names=()
    local -a device_udids=()

    while IFS= read -r line; do
        if [[ "$line" =~ ^[[:space:]]*(.*[^[:space:]])[[:space:]]+\(([0-9A-Fa-f-]{36})\)[[:space:]]+\((Booted|Shutdown)\)[[:space:]]*$ ]]; then
            device_name="${BASH_REMATCH[1]}"
            device_udid="${BASH_REMATCH[2]}"
            device_names+=("$device_name")
            device_udids+=("$device_udid")
        fi
    done <<< "$device_list"

    if [[ -n "$requested_udid" ]]; then
        local index
        for index in "${!device_udids[@]}"; do
            if [[ "${device_udids[$index]}" == "$requested_udid" ]]; then
                printf '%s\n' "${device_udids[$index]}"
                return 0
            fi
        done
        echo "[ios-run] FATAL: simulator UDID '$requested_udid' is not available." >&2
        return 1
    fi

    local -a matching_udids=()
    local index
    for index in "${!device_names[@]}"; do
        if [[ "${device_names[$index]}" == "$requested_name" ]]; then
            matching_udids+=("${device_udids[$index]}")
        fi
    done

    case "${#matching_udids[@]}" in
        0)
            echo "[ios-run] FATAL: no available simulator named '$requested_name'." >&2
            return 1
            ;;
        1)
            printf '%s\n' "${matching_udids[0]}"
            ;;
        *)
            echo "[ios-run] FATAL: simulator name '$requested_name' is ambiguous." >&2
            echo "         Matching UDIDs: ${matching_udids[*]}" >&2
            echo "         Set SIM_UDID to select one exact runtime/device." >&2
            return 1
            ;;
    esac
}

create_ios_run_dir() {
    local build_root="$1"
    mkdir -p -- "$build_root"
    mktemp -d "$build_root/ios-run.XXXXXX"
}

acquire_ios_run_lock() {
    local lock_dir="$1"
    if ! mkdir -- "$lock_dir" 2>/dev/null; then
        local owner="unknown"
        if [[ -f "$lock_dir/pid" ]]; then
            owner="$(<"$lock_dir/pid")"
        fi
        echo "[ios-run] FATAL: another launcher owns $lock_dir (pid $owner)." >&2
        echo "         Concurrent xcodegen/XCFramework writes are not safe; wait for it to finish." >&2
        return 1
    fi
    printf '%s\n' "$$" > "$lock_dir/pid"
}

release_ios_run_lock() {
    local lock_dir="$1"
    rm -f -- "$lock_dir/pid"
    rmdir -- "$lock_dir"
}

main() {
    local sim_name="${SIM_NAME:-iPhone 17}"
    local sim_udid="${SIM_UDID:-}"
    local bundle_id="${BUNDLE_ID:-dev.p2pkit.sample}"
    local scheme="p2pkit-sample"
    local script_dir repo_root project_dir device_list udid
    local run_dir derived_data_dir build_log app_path plist_dump lock_dir
    local installed_path exec_name built_sha installed_sha
    local owns_run_dir=0
    local owns_run_lock=0

    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    repo_root="$(cd "$script_dir/.." && pwd)"
    project_dir="$repo_root/iosApp"

    echo "[ios-run] Resolving one exact available simulator..."
    device_list="$(xcrun simctl list devices available)"
    if ! udid="$(resolve_simulator_udid "$sim_name" "$sim_udid" "$device_list")"; then
        echo "         Run: xcrun simctl list devices available" >&2
        return 1
    fi
    echo "[ios-run] UDID: $udid"

    if [[ -n "${IOS_RUN_DIR:-}" ]]; then
        mkdir -p -- "$IOS_RUN_DIR"
        run_dir="$(cd "$IOS_RUN_DIR" && pwd)"
    else
        run_dir="$(create_ios_run_dir "$project_dir/build")"
        owns_run_dir=1
    fi
    derived_data_dir="$run_dir/DerivedData"
    build_log="$run_dir/xcodebuild.log"
    lock_dir="$project_dir/build/.ios-launch.lock"

    cleanup_ios_run() {
        local status=$?
        trap - EXIT
        if [[ "$owns_run_lock" -eq 1 ]]; then
            release_ios_run_lock "$lock_dir"
        fi
        if [[ "$owns_run_dir" -eq 1 && "$status" -eq 0 && "${KEEP_IOS_RUN_ARTIFACTS:-0}" != "1" ]]; then
            case "$run_dir" in
                "$project_dir"/build/ios-run.*) rm -rf -- "$run_dir" ;;
                *) echo "[ios-run] Refusing to remove unexpected run directory: $run_dir" >&2 ;;
            esac
        else
            echo "[ios-run] Run artifacts retained at $run_dir"
        fi
        exit "$status"
    }
    trap cleanup_ios_run EXIT

    if ! acquire_ios_run_lock "$lock_dir"; then
        return 1
    fi
    owns_run_lock=1

    echo "[ios-run] Regenerating Xcode project (xcodegen)..."
    (cd "$project_dir" && xcodegen generate) | tail -3

    echo "[ios-run] Building iOS app for simulator UDID $udid..."
    if ! xcodebuild \
        -project "$project_dir/p2pkit-sample.xcodeproj" \
        -scheme "$scheme" \
        -configuration Debug \
        -sdk iphonesimulator \
        -destination "platform=iOS Simulator,id=$udid" \
        -derivedDataPath "$derived_data_dir" \
        build > "$build_log" 2>&1; then
        echo "[ios-run] xcodebuild failed — last 40 lines of log:"
        tail -40 "$build_log"
        return 1
    fi
    echo "[ios-run] Build succeeded (log: $build_log)."

    app_path="$derived_data_dir/Build/Products/Debug-iphonesimulator/${scheme}.app"
    if [[ ! -d "$app_path" ]]; then
        echo "[ios-run] FATAL: expected app bundle missing at:"
        echo "         $app_path"
        return 1
    fi
    echo "[ios-run] App bundle: $app_path"

    echo "[ios-run] Checking load-bearing Info.plist keys in the built bundle..."
    plist_dump="$(plutil -p "$app_path/Info.plist")"
    local required
    for required in NSLocalNetworkUsageDescription NSBonjourServices _p2pkit2._tcp; do
        if ! printf '%s' "$plist_dump" | grep -qF "$required"; then
            echo "[ios-run] FATAL: built Info.plist is missing '$required'."
            echo "         Keep local-network keys in iosApp/project.yml; xcodegen regenerates the project."
            return 1
        fi
    done
    echo "[ios-run] Info.plist keys OK."

    echo "[ios-run] Booting simulator (no-op if already booted)..."
    xcrun simctl boot "$udid" 2>/dev/null || true

    echo "[ios-run] Installing app bundle..."
    xcrun simctl install "$udid" "$app_path"

    installed_path="$(xcrun simctl get_app_container "$udid" "$bundle_id" 2>/dev/null || true)"
    if [[ -z "$installed_path" || ! -d "$installed_path" ]]; then
        echo "[ios-run] FATAL: simctl reports no installed container for $bundle_id."
        return 1
    fi
    exec_name="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' "$app_path/Info.plist")"
    built_sha="$(shasum -a 256 "$app_path/$exec_name" | awk '{print $1}')"
    installed_sha="$(shasum -a 256 "$installed_path/$exec_name" | awk '{print $1}')"
    if [[ "$built_sha" != "$installed_sha" ]]; then
        echo "[ios-run] FATAL: installed app does not match this build (stale install)."
        echo "         built:     $app_path (sha256 $built_sha)"
        echo "         installed: $installed_path (sha256 $installed_sha)"
        return 1
    fi
    echo "[ios-run] Provenance OK: installed executable matches this build (sha256 $(printf %.12s "$built_sha")…)."

    echo "[ios-run] Bringing Simulator.app to the foreground..."
    open -a Simulator

    echo "[ios-run] Launching $bundle_id..."
    xcrun simctl launch "$udid" "$bundle_id"
    echo "[ios-run] Done."
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
