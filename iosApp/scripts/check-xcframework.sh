#!/bin/sh
#
# V0.4-PROVENANCE (L3): Xcode pre-build validation for the
# P2pKitShared XCFramework.
#
# Wired as a Run Script build phase in iosApp/p2pkit-sample.xcodeproj
# BEFORE the "Compile Sources" phase. Guarantees that every Xcode build
# links against an XCFramework whose framework sources match the current
# `git rev-parse HEAD`. A stale XCFramework cannot silently reach the
# device through the normal build flow.
#
# Two layers of protection:
#   1. Run the Gradle XCFramework task — Gradle's own up-to-date check
#      makes this cheap (<2s) when no Kotlin source changed.
#   2. After the task, compare BUILD_COMMIT.txt against `git rev-parse HEAD`.
#      On mismatch, pass only if no framework-relevant sources changed
#      between the stamped commit and HEAD (an UP-TO-DATE assembly is
#      skipped by Gradle and legitimately keeps the older stamp — see
#      AUDIT #10 below); otherwise fail the Xcode build.
#
# Soft-warn on dirty working tree (uncommitted changes are reproducible
# under active development; we don't want to break the inner loop).

set -e

# When invoked as an Xcode build phase, $SRCROOT is iosApp/. Step out to
# the repo root so Gradle finds the wrapper.
cd "${SRCROOT:-$(dirname "$0")/..}/.."

echo "→ V0.4-PROVENANCE: ensuring P2pKitShared XCFramework is up to date..."
sh ./gradlew :p2p-transport-lan:assembleP2pKitSharedReleaseXCFramework \
  -q --console=plain

XCF_DIR="p2p-transport-lan/build/XCFrameworks/release"
XCF_COMMIT_FILE="$XCF_DIR/BUILD_COMMIT.txt"

# AUDIT-2026-06 (A-G9-samples-desktop-ios-13): check every slice, not just
# the ios-arm64 device slice — the simulator slice is the one
# scripts/run-ios-app.sh actually links and runs, and a malformed/partial
# simulator slice previously passed this gate unnoticed.
for XCF_SLICE in ios-arm64 ios-arm64_x86_64-simulator; do
    XCF_BIN="$XCF_DIR/P2pKitShared.xcframework/$XCF_SLICE/P2pKitShared.framework/P2pKitShared"
    if [ ! -f "$XCF_BIN" ]; then
        echo "error: XCFramework binary missing at $XCF_BIN"
        echo "       The XCFramework assembly task did not produce the expected output."
        exit 1
    fi
done

if [ ! -f "$XCF_COMMIT_FILE" ]; then
    echo "error: BUILD_COMMIT.txt sidecar missing at $XCF_COMMIT_FILE"
    echo "       writeXcframeworkCommit did not finalize the assemble task."
    echo "       Run: sh ./gradlew :p2p-transport-lan:assembleP2pKitSharedReleaseXCFramework"
    exit 1
fi

XCF_COMMIT="$(tr -d '[:space:]' < "$XCF_COMMIT_FILE")"
HEAD_COMMIT="$(git rev-parse HEAD)"

# AUDIT-2026-06 (#10): the stamp is written in the assemble task's own
# `doLast`, which Gradle SKIPS when the task is UP-TO-DATE. After a commit
# touching only non-framework files (docs, Swift, project.yml) HEAD moves but
# the framework — and its stamp — legitimately stay at the older commit. A
# raw equality check bricked every Xcode build in that state, and its
# suggested fix was a no-op (re-running the assemble task is still
# UP-TO-DATE). So on mismatch, accept the stamp iff the stamped commit is
# resolvable AND no framework-relevant source changed between it and HEAD:
# both modules' src/ trees, their build scripts, and the version catalog
# (dependency bumps). Anything unprovable (empty/"unknown" stamp, unknown
# commit — e.g. shallow clone) still hard-fails: can't prove freshness →
# refuse. All git calls sit in `if` conditions so `set -e` stays correct.
if [ "$XCF_COMMIT" != "$HEAD_COMMIT" ]; then
    STAMP_OK=0
    if [ -n "$XCF_COMMIT" ] && [ "$XCF_COMMIT" != "unknown" ] \
        && git cat-file -e "$XCF_COMMIT^{commit}" 2>/dev/null; then
        if git diff --quiet "$XCF_COMMIT" HEAD -- \
            p2p-transport-lan/src p2p-core/src \
            p2p-transport-lan/build.gradle.kts p2p-core/build.gradle.kts \
            gradle/libs.versions.toml; then
            STAMP_OK=1
        fi
    fi
    if [ "$STAMP_OK" -eq 0 ]; then
        echo "error: XCFramework identity mismatch — refusing to build against stale code:"
        echo "  expected (git HEAD):  $HEAD_COMMIT"
        echo "  actual (framework):   $XCF_COMMIT"
        echo "  Fix: sh ./gradlew :p2p-transport-lan:assembleP2pKitSharedReleaseXCFramework"
        exit 1
    fi
fi

# Soft-warn on dirty tree — common during active dev; not a build failure.
if ! git diff-index --quiet HEAD --; then
    echo "warning: working tree is dirty"
    echo "  The XCFramework you're about to link against includes uncommitted changes."
    echo "  Test results are non-reproducible from a clean checkout of $HEAD_COMMIT."
fi

# AUDIT-2026-06 (A-G9-samples-desktop-ios-13): ${VAR:0:7} is a bash-only
# substring expansion; this script declares #!/bin/sh and must stay POSIX
# (sh is dash on some hosts). printf %.7s is the portable equivalent.
SHORT=$(printf %.7s "$XCF_COMMIT")
if [ "$XCF_COMMIT" = "$HEAD_COMMIT" ]; then
    echo "✅ XCFramework is fresh: ${SHORT} (matches HEAD)"
else
    echo "✅ XCFramework stamped at ${SHORT}; no framework sources changed through HEAD — OK"
fi
