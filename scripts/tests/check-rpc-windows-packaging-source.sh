#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-windows-packaging-source.XXXXXX")"
trap 'rm -rf "$TMP_ROOT"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
JAVAC="${JAVA_HOME:+$JAVA_HOME/bin/}javac"
JAVA="${JAVA_HOME:+$JAVA_HOME/bin/}java"
"$JAVAC" -J-Xmx256m --release 17 -proc:none -encoding UTF-8 -Xlint:all -Werror \
    -d "$TMP_ROOT/runner" \
    "$ROOT/buildSrc/src/main/java/dev/p2pkit/build/GitProcess.java" \
    "$ROOT/buildSrc/src/main/java/dev/p2pkit/build/WindowsProfilePackagingSource.java" \
    "$ROOT/scripts/tests/WindowsProfilePackagingSourceTest.java"
"$JAVA" -Xmx256m -XX:ActiveProcessorCount=2 -cp "$TMP_ROOT/runner" \
    dev.p2pkit.build.WindowsProfilePackagingSourceTest "$TMP_ROOT"
