#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
flags=(--dependency-verification=strict --no-daemon --console=plain --max-workers=2)
case "${1:-}" in
  jvm-linux|jvm-windows)
    bash ./gradlew :p2p-core:jvmTest :p2p-transport-lan:jvmTest :p2p-rpc:jvmTest \
      :p2p-sample-rpc:jvmTest "${flags[@]}"
    ;;
  macos)
    bash scripts/tests/check-macos-lan-sockets.sh
    bash ./gradlew :p2p-transport-lan:stageMacTcp :p2p-transport-lan:macTcpNativeTest "${flags[@]}"
    bash ./gradlew :p2p-transport-lan:jvmTest \
      --tests 'dev.p2pkit.transport.lan.SocketReadinessTest' \
      --tests 'dev.p2pkit.transport.lan.SocketPathWatchdogTest' \
      --tests 'dev.p2pkit.transport.lan.JvmRawConnectionPathWatchTest' \
      --tests 'dev.p2pkit.transport.lan.JvmNioConnectionTest' \
      --tests 'dev.p2pkit.transport.lan.JvmRawCapacityTest' "${flags[@]}"
    ;;
  macos-abi)
    # The additive host256 baseline was generated on macOS and reviewed. Check it without rewriting.
    bash ./gradlew :p2p-rpc:internalDumpKotlinAbi :p2p-rpc:buildAndroidAbi "${flags[@]}"
    python3 - <<'PY'
from pathlib import Path
import shutil
root = Path('library/p2p-rpc/build')
output = Path('build/reports/rpc-io-proposed-api')
for path in root.rglob('*.api'):
    target = output / path.relative_to(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, target)
PY
    bash ./gradlew :p2p-rpc:checkKotlinAbi :p2p-rpc:checkAndroidAbi "${flags[@]}"
    ;;
  android-24|android-35)
    python3 -B scripts/run-android-readiness.py --api "${1#android-}"
    ;;
  ios-phone)
    python3 -B scripts/run-rpc-io-phone-controls.py
    ;;
  *) echo 'Unknown scoped I/O component' >&2; exit 2 ;;
esac
