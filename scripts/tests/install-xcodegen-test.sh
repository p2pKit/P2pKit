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

check_fixture_version() {
    local name="$1" fixture_version="$2"
    local case_root="$TMP_ROOT/$name"
    local fixture_root="$case_root/fixture"
    local archive_sha256 bin_dir
    mkdir -p "$fixture_root/xcodegen/bin"
    printf '%s\n' \
        '#!/usr/bin/env bash' \
        "printf '%s\\n' 'Version: $fixture_version'" \
        > "$fixture_root/xcodegen/bin/xcodegen"
    chmod +x "$fixture_root/xcodegen/bin/xcodegen"
    (cd "$fixture_root" && zip -qr "$case_root/xcodegen.zip" xcodegen)

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

check_fixture_version current "$XCODEGEN_VERSION"
# A synthetic second input ensures the installer tests cannot quietly depend
# on today's literal. This is not a proposed or independently approved release.
check_fixture_version synthetic "99.98.97"

echo "install-xcodegen tests: 14 passed (current and synthetic version inputs)"
