#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
for script in "$ROOT/scripts/install-xcodegen.sh" "$ROOT/scripts/tests/install-xcodegen-test.sh"; do
    bash -n "$script"
done
# shellcheck source=../install-xcodegen.sh
source "$ROOT/scripts/install-xcodegen.sh"

# Fixture input from scripts/install-xcodegen.sh, not a release approval oracle.
# release-workflow-test.sh retains the independent version/checksum tripwires.
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-xcodegen-test.XXXXXX")"
trap 'rm -rf -- "$TMP_ROOT"' EXIT

create_fixture_archive() {
    local case_root="$1" fixture_version="$2" probe_status="${3:-0}"
    local fixture_root="$case_root/fixture"
    mkdir -p "$fixture_root/xcodegen/bin"
    printf '%s\n' \
        '#!/usr/bin/env bash' \
        "printf '%s\\n' 'Version: $fixture_version'" \
        "exit $probe_status" \
        > "$fixture_root/xcodegen/bin/xcodegen"
    chmod +x "$fixture_root/xcodegen/bin/xcodegen"
    (cd "$fixture_root" && zip -qr "$case_root/xcodegen.zip" xcodegen)
}

check_fixture_version() {
    local name="$1" fixture_version="$2"
    local case_root="$TMP_ROOT/$name"
    local archive_sha256 bin_dir
    create_fixture_archive "$case_root" "$fixture_version"
    archive_sha256="$(calculate_sha256 "$case_root/xcodegen.zip")"
    verify_xcodegen_archive "$case_root/xcodegen.zip" "$archive_sha256"

    if verify_xcodegen_archive "$case_root/xcodegen.zip" "$(printf '0%.0s' {1..64})" >/dev/null 2>&1; then
        echo "FAIL: incorrect archive checksum was accepted" >&2
        exit 1
    fi

    bin_dir="$(install_xcodegen_archive "$case_root/xcodegen.zip" "$case_root/installed" "$fixture_version")"
    if [[ "$bin_dir" != "$case_root/installed/bin" ]]; then
        echo "FAIL: installer returned the wrong binary directory" >&2
        exit 1
    fi
    if [[ "$("$bin_dir/xcodegen" --version)" != "Version: $fixture_version" ]]; then
        echo "FAIL: installed XcodeGen fixture does not run" >&2
        exit 1
    fi
    if install_xcodegen_archive "$case_root/xcodegen.zip" "$case_root/installed" "$fixture_version" >/dev/null 2>&1; then
        echo "FAIL: existing install destination was overwritten" >&2
        exit 1
    fi

    if install_xcodegen_archive "$case_root/xcodegen.zip" "$case_root/wrong-version" \
        "${fixture_version}-unexpected" >/dev/null 2>&1; then
        echo "FAIL: mismatched fixture version was accepted" >&2
        exit 1
    fi
    if [[ -e "$case_root/wrong-version" ]]; then
        echo "FAIL: mismatched fixture was installed" >&2
        exit 1
    fi
}

check_main_fixture() {
    local name="$1" fixture_version="$2" probe_status="$3" temp_name="$4" expected_status="$5"
    local case_root="$TMP_ROOT/$name"
    local temp_root="$case_root/$temp_name" install_root="$case_root/installed"
    local archive_sha256 status temporary
    create_fixture_archive "$case_root" "$fixture_version" "$probe_status"
    archive_sha256="$(calculate_sha256 "$case_root/xcodegen.zip")"
    mkdir -p "$temp_root"
    printf '%s\n' 'caller-owned temporary file' > "$temp_root/sentinel"
    case "$name" in
        existing-destination)
            mkdir -p "$install_root"
            printf '%s\n' 'caller-owned destination' > "$install_root/sentinel"
            ;;
        blocked-parent)
            printf '%s\n' 'caller-owned parent file' > "$case_root/parent-file"
            install_root="$case_root/parent-file/installed"
            ;;
    esac

    # Source the real installer in a child, replace only its network boundary,
    # and call main normally. An if/! caller would suppress Bash's errexit.
    set +e
    TMPDIR="$temp_root" FIXTURE_ARCHIVE="$case_root/xcodegen.zip" CALLER_EXIT_MARKER="$case_root/caller-exit" \
        bash -s -- "$ROOT/scripts/install-xcodegen.sh" "$archive_sha256" "$install_root" \
        > "$case_root/stdout" 2> "$case_root/stderr" <<'MAIN_FIXTURE'
source "$1"
XCODEGEN_SHA256="$2"
trap 'status=$?; printf "%s\n" caller >> "$CALLER_EXIT_MARKER"; exit "$status"' EXIT
curl() {
    local destination=""
    while [[ $# -gt 0 ]]; do
        if [[ "$1" == --output ]]; then
            destination="$2"
            shift 2
        else
            shift
        fi
    done
    cp -- "$FIXTURE_ARCHIVE" "$destination"
}
main "$3"
MAIN_FIXTURE
    status=$?
    set -e
    if [[ "$status" -ne "$expected_status" ]]; then
        cat "$case_root/stderr" >&2
        echo "FAIL: $name returned $status, expected $expected_status" >&2
        exit 1
    fi
    if [[ ! -f "$case_root/caller-exit" || "$(cat "$case_root/caller-exit")" != caller ]]; then
        echo "FAIL: $name changed or prematurely ran the caller's EXIT trap" >&2
        exit 1
    fi
    if [[ "$(cat "$temp_root/sentinel")" != 'caller-owned temporary file' ]]; then
        echo "FAIL: $name removed unrelated temporary content" >&2
        exit 1
    fi
    for temporary in "$temp_root"/p2pkit-xcodegen-*; do
        if [[ -e "$temporary" || -L "$temporary" ]]; then
            echo "FAIL: $name left an owned temporary path: $temporary" >&2
            exit 1
        fi
    done
    if [[ "$expected_status" -eq 0 ]]; then
        if [[ "$(cat "$case_root/stdout")" != "$install_root/bin" ]] ||
            ! cmp -s "$case_root/fixture/xcodegen/bin/xcodegen" "$install_root/bin/xcodegen"; then
            echo "FAIL: $name did not install and report the exact fixture" >&2
            exit 1
        fi
    elif [[ "$name" == existing-destination ]]; then
        if [[ "$(cat "$install_root/sentinel")" != 'caller-owned destination' || -e "$install_root/bin" ]]; then
            echo "FAIL: existing destination was modified" >&2
            exit 1
        fi
    elif [[ -e "$install_root" || -L "$install_root" ]]; then
        echo "FAIL: $name installed a rejected fixture" >&2
        exit 1
    fi
    if [[ "$name" == blocked-parent && "$(cat "$case_root/parent-file")" != 'caller-owned parent file' ]]; then
        echo "FAIL: blocked parent file was modified" >&2
        exit 1
    fi
    case "$name" in
        failed-probe) grep -Fq 'FATAL: XcodeGen version probe failed (exit 7).' "$case_root/stderr" ;;
        wrong-main-version) grep -Fq 'FATAL: XcodeGen version mismatch:' "$case_root/stderr" ;;
        existing-destination) grep -Fq 'FATAL: XcodeGen install destination already exists:' "$case_root/stderr" ;;
    esac
}

check_fixture_version current "$XCODEGEN_VERSION"
# A synthetic second input ensures the installer tests cannot quietly depend
# on today's literal. This is not a proposed or independently approved release.
check_fixture_version synthetic "99.98.97"

check_main_fixture spaced-temp "$XCODEGEN_VERSION" 0 'space in temp' 0
check_main_fixture failed-probe "$XCODEGEN_VERSION" 7 temp 7
check_main_fixture wrong-main-version "${XCODEGEN_VERSION}-unexpected" 0 temp 1
check_main_fixture blocked-parent "$XCODEGEN_VERSION" 0 temp 1
check_main_fixture existing-destination "$XCODEGEN_VERSION" 0 temp 1

echo "install-xcodegen tests: 14 fixture assertions and 5 actual-main cases passed"
