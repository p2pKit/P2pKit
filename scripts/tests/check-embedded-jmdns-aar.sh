#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-aar-producer.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
JAVAC="${JAVA_HOME:+$JAVA_HOME/bin/}javac"
JAVA="${JAVA_HOME:+$JAVA_HOME/bin/}java"
"$JAVAC" -J-Xmx256m --release 17 -proc:none -encoding UTF-8 -Xlint:all -Werror \
    -d "$WORK/classes" \
    "$ROOT/buildSrc/src/main/java/dev/p2pkit/build/EmbeddedJmdnsAar.java" \
    "$ROOT/scripts/tests/EmbeddedJmdnsAarTest.java"
mkdir "$WORK/cases"
"$JAVA" -Xmx256m -XX:ActiveProcessorCount=2 -cp "$WORK/classes" \
    dev.p2pkit.build.EmbeddedJmdnsAarTest "$WORK/cases"
