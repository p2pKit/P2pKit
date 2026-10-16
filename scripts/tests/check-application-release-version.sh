#!/usr/bin/env bash
# JDK-only helper test. Run on an authorized build/test host, not during a
# source-only inspection that prohibits local Java execution.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
classes="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-version-classes.XXXXXXXX")"
trap 'rm -rf -- "$classes"' EXIT
javac --release 17 -d "$classes" \
    "$ROOT/buildSrc/src/main/java/dev/p2pkit/build/ApplicationReleaseVersion.java" \
    "$ROOT/scripts/tests/fixtures/ApplicationReleaseVersionTest.java"
java -cp "$classes" ApplicationReleaseVersionTest \
    "$ROOT/scripts/tests/fixtures/application-release-versions.tsv"
