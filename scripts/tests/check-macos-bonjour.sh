#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
if [[ "$(uname -s)" != Darwin ]]; then
    echo 'NOT EXECUTABLE: DNS-SD native contract requires a Mac' >&2
    exit 2
fi
SOURCE="$ROOT/library/p2p-transport-lan/src/nativeInterop/macosJvm"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-macos-bonjour.XXXXXX")"
echo "Evidence: $WORK (retained, including failures)"
# Exact core with deterministic DNSService doubles. No daemon/network/privilege/signing/installation.
for mode in strict sanitized; do
    flags=(-g)
    if [[ "$mode" == sanitized ]]; then
        flags=(-fsanitize=address,undefined -fno-omit-frame-pointer)
    fi
    xcrun clang -std=c11 -Wall -Wextra -Werror -Wpedantic -pthread -g -O1 "${flags[@]}" \
        "$SOURCE/p2pkit_bonjour.c" "$SOURCE/p2pkit_bonjour_test.c" -o "$WORK/test-$mode"
    echo "MODE $mode"
    "$WORK/test-$mode" | tee "$WORK/$mode.log"
done
