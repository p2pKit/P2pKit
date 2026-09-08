#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

fail() {
    echo "FATAL: $*" >&2
    exit 1
}

if [[ -n "${P2PKIT_GRADLE_EXECUTOR:-}" ]]; then
    [[ "$P2PKIT_GRADLE_EXECUTOR" == /* && -x "$P2PKIT_GRADLE_EXECUTOR" ]] ||
        fail "P2PKIT_GRADLE_EXECUTOR must be an absolute executable path"
    # An opt-in leaf may exit before stop/drain/receipt finalization is known.
    # Its inputs, logs and optional receipt must not be deleted by this shell's
    # EXIT trap, even when the expected policy diagnostic was printed. Allocate
    # only under the host's initialized work root and leave ALL audited cleanup
    # to that outer owner, after evidence retention and finalization proof.
    if ! WORK="$(python3 - "$ROOT" "${P2PKIT_AUDIT_STATE_DIR:-}" <<'PYTHON'
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile


def require(condition, message):
    if not condition:
        raise ValueError(message)


def physical(path):
    require(path.is_absolute() and ".." not in path.parts and
            not any(char in str(path) for char in "\r\n\0"), "Unsafe audit work path")
    for candidate in (path, *path.parents):
        info = candidate.lstat()
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
                "Symlink/reparse audit work path")
    return path.stat()


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "Duplicate audit context key")
        result[key] = value
    return result


try:
    root = Path(sys.argv[1]).resolve(strict=True)
    state = Path(sys.argv[2])
    parent = state / "work"
    require(not state.is_relative_to(root) and not root.is_relative_to(state),
            "Audit state must be outside the checkout")
    state_info, parent_info = physical(state), physical(parent)
    require(all(stat.S_ISDIR(info.st_mode) for info in (state_info, parent_info,
                physical(state / "evidence"), physical(state / "gradle-home"))),
            "Audit state/work must already be initialized directories")
    context_path = state / "context.json"
    before = physical(context_path)
    limit = 4 * 1024 * 1024
    require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= limit, "Invalid audit context file")
    with context_path.open("rb") as stream:
        raw = stream.read(limit + 1)
    after = physical(context_path)
    require(len(raw) == before.st_size == after.st_size and before.st_mtime_ns == after.st_mtime_ns and
            before.st_ino == after.st_ino, "Audit context changed during allocation")
    context = json.loads(raw, object_pairs_hook=pairs,
                         parse_constant=lambda _: require(False, "Nonfinite audit context"))
    # Namespace binding only. Actual executor leaves still own source/native
    # admission and stop/drain proof; this metadata never replaces those checks.
    require(type(context) is dict and type(context.get("schema")) is int and context["schema"] == 1 and
            context.get("root") == str(root) and type(context.get("id")) is str and
            re.fullmatch(r"[0-9a-f]{32}", context["id"]) and
            context.get("gradleHome") == str(state / "gradle-home") and
            type(context.get("host")) is str and context["host"], "Audit context does not bind this work namespace")
    work = Path(tempfile.mkdtemp(prefix="lock-policy.", dir=parent))
    physical(work)
    for path, original in ((state, state_info), (parent, parent_info)):
        current = physical(path)
        require((current.st_dev, current.st_ino) == (original.st_dev, original.st_ino),
                "Audit work owner changed during allocation")
    record = {
        "schema": 1, "purpose": "lock-policy-work", "jobId": context["id"], "host": context["host"],
        "root": str(root), "stateDirectory": str(state), "workDirectory": str(work),
        "contextSha256": hashlib.sha256(raw).hexdigest(),
        "stateIdentity": {"device": state_info.st_dev, "inode": state_info.st_ino},
        "workParentIdentity": {"device": parent_info.st_dev, "inode": parent_info.st_ino},
        "cleanupOwner": "run-audit-host.py", "preserveUntilOuterFinalization": True,
        "leafFinalization": "NOT_ASSESSED",
    }
    with (work / "ownership.json").open("x", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    print(work)
except (OSError, ValueError, KeyError, TypeError) as failure:
    print("FATAL: cannot allocate retained audit lock-policy work: " + str(failure), file=sys.stderr)
    raise SystemExit(1)
PYTHON
)"; then
        fail "audit lock-policy work allocation failed; no wrapper was started"
    fi
    printf 'AUDIT_LOCK_POLICY_WORK=%s\n' "$WORK" >&2
    LOCKS_BEFORE="$WORK/locks-before.txt"
    LOCKS_AFTER="$WORK/locks-after.txt"
else
    WORK="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-lock-policy-test.XXXXXX")"
    trap 'rm -rf "$WORK"' EXIT
    LOCKS_BEFORE="$WORK/locks-before"
    LOCKS_AFTER="$WORK/locks-after"
fi

run_gradle() {
    local output="$1"
    shift
    local status=0
    if [[ -n "${P2PKIT_GRADLE_EXECUTOR:-}" ]]; then
        [[ "$P2PKIT_GRADLE_EXECUTOR" == /* && -x "$P2PKIT_GRADLE_EXECUTOR" ]] ||
            fail "P2PKIT_GRADLE_EXECUTOR must be an absolute executable path"
        local purpose="lock-policy-$(basename "$output" .log)"
        local receipt="$output.receipt.json"
        [[ ! -e "$receipt" && ! -L "$receipt" ]] || fail "audit receipt already exists"
        set +e
        "$P2PKIT_GRADLE_EXECUTOR" --cwd "$ROOT" --wrapper "$ROOT/gradlew" \
            --purpose "$purpose" --receipt "$receipt" -- \
            "$@" --no-daemon --max-workers=2 --console=plain >"$output" 2>&1
        status=$?
        set -e
        # A policy diagnostic in the log must not hide failed stop/ownership or
        # missing evidence. In adapter mode the executor owns every wrapper stop.
        if ! python3 "$ROOT/scripts/check-audit-receipt.py" \
            --purpose "$purpose" --cwd "$ROOT" --wrapper "$ROOT/gradlew" \
            "$receipt" "$status" -- "$@" --no-daemon --max-workers=2 --console=plain; then
            cat "$output" >&2
            fail "audit leaf finalization failed for $purpose"
        fi
    else
        set +e
        (cd "$ROOT" && ./gradlew "$@" --no-daemon --max-workers=2 --console=plain) \
            >"$output" 2>&1
        status=$?
        set -e
        (cd "$ROOT" && ./gradlew --stop) >"$WORK/gradle-stop.log" 2>&1 || true
    fi
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

snapshot_locks >"$LOCKS_BEFORE"

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

snapshot_locks >"$LOCKS_AFTER"
cmp -s "$LOCKS_BEFORE" "$LOCKS_AFTER" ||
    fail "lock-policy regression test modified a dependency lockfile"

echo "RESULT: PASS — lock writes require the complete resolved refresh graph"
