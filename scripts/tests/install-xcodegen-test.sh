#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
bash -n "$ROOT/scripts/install-xcodegen.sh" "$ROOT/scripts/tests/install-xcodegen-test.sh"
# shellcheck source=../install-xcodegen.sh
source "$ROOT/scripts/install-xcodegen.sh"

TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-xcodegen-test.XXXXXX")"
trap 'rm -rf -- "$TMP_ROOT"' EXIT
FIXTURE_ROOT="$TMP_ROOT/fixture"
mkdir -p "$FIXTURE_ROOT/xcodegen/bin"
printf '%s\n' \
    '#!/usr/bin/env bash' \
    'printf '\''Version: 2.45.4\n'\''' \
    > "$FIXTURE_ROOT/xcodegen/bin/xcodegen"
chmod +x "$FIXTURE_ROOT/xcodegen/bin/xcodegen"
(cd "$FIXTURE_ROOT" && zip -qr "$TMP_ROOT/xcodegen.zip" xcodegen)

archive_sha256="$(calculate_sha256 "$TMP_ROOT/xcodegen.zip")"
verify_xcodegen_archive "$TMP_ROOT/xcodegen.zip" "$archive_sha256"

if verify_xcodegen_archive "$TMP_ROOT/xcodegen.zip" "$(printf '0%.0s' {1..64})" >/dev/null 2>&1; then
    echo "FAIL: incorrect archive checksum was accepted" >&2
    exit 1
fi

bin_dir="$(install_xcodegen_archive "$TMP_ROOT/xcodegen.zip" "$TMP_ROOT/installed" "2.45.4")"
if [[ "$bin_dir" != "$TMP_ROOT/installed/bin" ]]; then
    echo "FAIL: installer returned the wrong binary directory" >&2
    exit 1
fi
if [[ "$($bin_dir/xcodegen --version)" != "Version: 2.45.4" ]]; then
    echo "FAIL: installed XcodeGen fixture does not run" >&2
    exit 1
fi
if install_xcodegen_archive "$TMP_ROOT/xcodegen.zip" "$TMP_ROOT/installed" "2.45.4" >/dev/null 2>&1; then
    echo "FAIL: existing install destination was overwritten" >&2
    exit 1
fi

echo "install-xcodegen tests: 5 passed"
