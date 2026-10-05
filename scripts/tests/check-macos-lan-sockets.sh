#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
if [[ "$(uname -s)" != Darwin ]]; then
    echo 'NOT EXECUTABLE: Darwin native socket contract requires a Mac' >&2
    exit 2
fi
SOURCE="$ROOT/library/p2p-transport-lan/src/nativeInterop/macosJvm"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-macos-lan-sockets.XXXXXX")"
trap 'status=$?; rm -rf -- "$WORK"; exit "$status"' EXIT
# No application install, system setting, non-loopback endpoint or dependency download.
# Instrument the exact same core twice; failed attempts are not replaced with a non-sanitized pass.
for mode in strict sanitized; do
    flags=(-g)
    if [[ "$mode" == sanitized ]]; then
        flags=(-fsanitize=address,undefined -fno-omit-frame-pointer)
    fi
    xcrun clang -DP2P_LAN_SOCKET_TESTING -std=c11 -Wall -Wextra -Werror -pedantic -pthread -g -O1 "${flags[@]}" \
        "$SOURCE/p2pkit_lan_socket.c" "$SOURCE/p2pkit_lan_socket_test.c" -o "$WORK/test-$mode"
    echo "MODE $mode"
    "$WORK/test-$mode"
done
