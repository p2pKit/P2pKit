#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-lock-policy-test.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

fail() {
    echo "FATAL: $*" >&2
    exit 1
}

run_gradle() {
    local output="$1"
    shift
    local status=0
    set +e
    (cd "$ROOT" && ./gradlew "$@" --no-daemon --max-workers=2 --console=plain) \
        >"$output" 2>&1
    status=$?
    set -e
    (cd "$ROOT" && ./gradlew --stop) >"$WORK/gradle-stop.log" 2>&1 || true
    return "$status"
}

snapshot_locks() {
    while IFS= read -r lockfile; do
        shasum -a 256 "$lockfile"
    done < <(find "$ROOT" -name '*gradle.lockfile' -type f -print | LC_ALL=C sort)
}

expect_policy_failure() {
    local label="$1"
    local expected="$2"
    shift 2
    local output="$WORK/${label}.log"
    if run_gradle "$output" "$@"; then
        fail "$label unexpectedly succeeded"
    fi
    grep -Fq -- "$expected" "$output" ||
        fail "$label did not report '$expected'"
    if grep -E '^> Task :' "$output" | grep -Fqv '> Task :buildSrc:'; then
        fail "$label executed a project task before rejecting the invocation"
    fi
}

snapshot_locks >"$WORK/locks-before"

# Gradle's abbreviated and indirect task selectors must receive the same
# pre-execution policy as the full task name.
expect_policy_failure abbreviated \
    'resolveAndLockAll must be invoked with --write-locks' \
    rALl --dry-run

cat >"$WORK/indirect.init.gradle.kts" <<'KOTLIN'
gradle.beforeProject {
    if (path == ":") {
        tasks.register("indirectLockRefresh") {
            dependsOn("resolveAndLockAll")
        }
    }
}
KOTLIN
expect_policy_failure indirect \
    'resolveAndLockAll must be invoked with --write-locks' \
    indirectLockRefresh --dry-run --init-script "$WORK/indirect.init.gradle.kts"

# The converse guard prevents partial lock updates through an ordinary graph.
expect_policy_failure ordinary-write \
    '--write-locks may only be used with resolveAndLockAll' \
    help --write-locks --dry-run

# Configuration on demand can omit unevaluated subproject tasks from a
# dynamically derived refresh graph. Fail before graph execution instead of
# accepting a partial lock rewrite.
expect_policy_failure configure-on-demand-write \
    '--write-locks requires --no-configure-on-demand' \
    rALl --write-locks --dry-run --configure-on-demand

# The one sanctioned graph remains selectable by any Gradle-supported name.
if ! run_gradle "$WORK/authorized.log" rALl --write-locks --dry-run; then
    cat "$WORK/authorized.log" >&2
    fail "authorized abbreviated lock refresh was rejected"
fi
grep -Fq ':resolveAndLockAll SKIPPED' "$WORK/authorized.log" ||
    fail "authorized dry run did not select resolveAndLockAll"

# Every Gradle subproject except the documented Swift-only wrapper currently
# owns a check task. Derive the expected set from settings so a new module
# cannot silently fall outside the refresh graph.
while IFS= read -r project; do
    [[ "$project" == "iosApp" ]] && continue
    grep -Fq ":$project:check SKIPPED" "$WORK/authorized.log" ||
        fail "lock refresh omitted :$project:check"
done < <(sed -n 's/^include(":\([^"]*\)")$/\1/p' "$ROOT/settings.gradle.kts")

snapshot_locks >"$WORK/locks-after"
cmp -s "$WORK/locks-before" "$WORK/locks-after" ||
    fail "lock-policy regression test modified a dependency lockfile"

echo "RESULT: PASS — lock writes require the complete resolved refresh graph"
