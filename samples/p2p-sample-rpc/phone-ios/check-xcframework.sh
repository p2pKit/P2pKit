#!/bin/sh
# The lab never accepts a stale or dirty framework for an installable test app.
set -eu
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/../../.." && pwd -P)
cd "$ROOT"
TASK=:p2p-sample-rpc:verifyP2pKitRpcExampleDebugXCFrameworkProvenance
if [ -n "${P2PKIT_GRADLE_EXECUTOR:-}" ]; then
    case "$P2PKIT_GRADLE_EXECUTOR" in
        /*) ;;
        *) echo "error: Native executor must be absolute" >&2; exit 1 ;;
    esac
    test -x "$P2PKIT_GRADLE_EXECUTOR"
    "$P2PKIT_GRADLE_EXECUTOR" --cwd "$ROOT" --wrapper "$ROOT/gradlew" \
        --purpose rpc-phone-xcode-provenance -- "$TASK" -q --console=plain
else
    sh ./gradlew "$TASK" -q --console=plain
fi
DIR=samples/p2p-sample-rpc/build/XCFrameworks/debug
for SLICE in ios-arm64 ios-arm64_x86_64-simulator; do
    test -f "$DIR/P2pKitRpcExample.xcframework/$SLICE/P2pKitRpcExample.framework/P2pKitRpcExample"
done
test "$(cat "$DIR/BUILD_COMMIT.txt")" = "$(git rev-parse HEAD)"
test "$(cat "$DIR/BUILD_SOURCE_STATE.txt")" = clean
for NAME in BUILD_INPUTS_SHA256.txt BUILD_ARTIFACTS_SHA256.txt; do
    VALUE=$(cat "$DIR/$NAME")
    case "$VALUE" in *[!0123456789abcdef]*|'') echo "error: Invalid RPC provenance digest" >&2; exit 1 ;; esac
    test "${#VALUE}" -eq 64
done
printf '%s\n' 'RPC example provenance verified against the current clean framework sources.'
